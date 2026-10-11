"""Incremental online detect/adapt with decision-aware commit. GRU is not used in MPC."""

from __future__ import annotations

from typing import Any, Literal

import numpy as np

from nexus.tasks.spec import TaskSpec, make_task_env
from nexus.world.adapt import WindowThresholdDetector, adapt_method
from nexus.world.agent import InteractionLedger, _mae
from nexus.world.belief import BeliefEstimator, BeliefStepModel
from nexus.world.data import TransitionDataset
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_OBJECTIVE, FROZEN_PRIMARY_HORIZON
from nexus.world.planning import RandomShootingMPC
from nexus.world.planning import one_step_greedy

GatePolicy = Literal["never", "always", "mae", "action", "control"]


def _planner(wm: WorldModel) -> RandomShootingMPC:
    return RandomShootingMPC(
        model=BeliefStepModel(wm),
        n_actions=2,
        horizon=FROZEN_PRIMARY_HORIZON,
        n_candidates=FROZEN_CANDIDATES[FROZEN_PRIMARY_HORIZON],
        seed=0,
        objective=FROZEN_OBJECTIVE,  # type: ignore[arg-type]
        enforce_time_budget=True,
    )


def _pack(obs: list, act: list, nxt: list, rew: list, term: list, spec: TaskSpec) -> TransitionDataset:
    n = len(obs)
    if n == 0:
        z = np.zeros((0, spec.obs_dim), dtype=np.float32)
        return TransitionDataset(
            obs=z,
            action=np.zeros(0, dtype=np.int64),
            next_obs=z.copy(),
            reward=np.zeros(0, dtype=np.float32),
            terminated=np.zeros(0, dtype=np.bool_),
            truncated=np.zeros(0, dtype=np.bool_),
            task_id=spec.task_id,
            seed=np.zeros(0, dtype=np.int64),
            episode_id=np.zeros(0, dtype=np.int64),
            policy=np.array([], dtype=object),
            physics=dict(spec.params),
            env_interactions=0,
        )
    return TransitionDataset(
        obs=np.stack(obs, axis=0),
        action=np.asarray(act, dtype=np.int64),
        next_obs=np.stack(nxt, axis=0),
        reward=np.asarray(rew, dtype=np.float32),
        terminated=np.asarray(term, dtype=np.bool_),
        truncated=np.zeros(n, dtype=np.bool_),
        task_id=spec.task_id,
        seed=np.zeros(n, dtype=np.int64),
        episode_id=np.zeros(n, dtype=np.int64),
        policy=np.array(["online"] * n),
        physics=dict(spec.params),
        env_interactions=n,
    )


def _decide(
    policy: GatePolicy,
    deployed: WorldModel,
    cand: WorldModel,
    val: TransitionDataset,
    *,
    control_return: float | None,
    deployed_rate: float | None,
) -> tuple[bool, str]:
    if policy == "always":
        return True, "always"
    if policy == "never":
        return False, "never"
    if len(val) == 0 and policy != "control":
        return False, "empty_val"
    if policy == "mae":
        before, after = _mae(deployed, val), _mae(cand, val)
        if after <= before * 0.97:
            return True, "mae_improved"
        return False, "mae_reject"
    if policy == "action":
        before, after = _mae(deployed, val), _mae(cand, val)
        disag = 0.0
        n = min(len(val), 64)
        if n:
            d = [one_step_greedy(deployed, val.obs[i], 2) != one_step_greedy(cand, val.obs[i], 2) for i in range(n)]
            disag = float(np.mean(d))
        if disag < 0.15:
            return False, "action_too_similar"
        if after <= before * 1.02:
            return True, "action_changed"
        return False, "action_mae_worse"
    # control: commit if candidate val return rate >= deployed collect rate
    if control_return is None or deployed_rate is None:
        return False, "control_missing"
    if control_return >= deployed_rate:
        return True, "control_val_better"
    return False, "control_val_worse"


def run_online_learning(
    spec: TaskSpec,
    source: WorldModel,
    source_replay: TransitionDataset,
    est: BeliefEstimator,
    *,
    target_cap: int,
    policy: GatePolicy,
    epochs: int,
    seed: int,
    detector: WindowThresholdDetector,
    max_cycles: int = 3,
) -> dict[str, Any]:
    """Step-level OBSERVE→ESTIMATE(prev_a)→PLAN→ACT→ERROR→DETECT→ADAPT→VERIFY.

    Recurrent estimators are not unrolled inside MPC (estimation-only if not Identity).
    Confirmation returns are not used.
    """
    ledger = InteractionLedger(target_cap=int(target_cap))
    deployed = source.clone()
    commits: list[str] = []
    rejects: list[str] = []
    detected = False
    cycles = 0
    ep_i = 0
    collect_ret: list[float] = []
    buf_o: list[np.ndarray] = []
    buf_a: list[int] = []
    buf_n: list[np.ndarray] = []
    buf_r: list[float] = []
    buf_t: list[bool] = []

    if target_cap <= 0:
        return {
            "model": deployed,
            "ledger": ledger.snapshot(),
            "committed": False,
            "detected": False,
            "commits": commits,
            "rejects": rejects,
            "cycles": 0,
            "policy": policy,
            "gru_in_mpc": False,
        }

    while ledger.remaining > 0:
        env = make_task_env(spec, seed=int(seed) + 17 * ep_i)
        obs, _ = env.reset(seed=int(seed) + ep_i)
        est.reset()
        planner = _planner(deployed)
        planner.reset_episode(int(seed) + 1000 * ep_i)
        prev_a: int | None = None
        done = False
        ep_ret = 0.0
        while not done and ledger.remaining > 0:
            o = np.asarray(obs, dtype=np.float32).reshape(-1)
            b = est.observe(o, prev_a)
            a, _meta = planner.act(b)
            pred, _p = deployed.step(b, int(a))
            nxt, rew, term, trunc, _ = env.step(int(a))
            ledger.charge(1, "detect" if (policy == "never" or not detected) else "adapt_collect")
            nxt_a = np.asarray(nxt, dtype=np.float32).reshape(-1)
            b2 = est.observe(nxt_a, int(a))
            pred_v = np.asarray(pred, dtype=np.float32).reshape(-1)
            b2v = np.asarray(b2, dtype=np.float32).reshape(-1)
            m = min(pred_v.size, b2v.size)
            err = float(np.mean(np.abs(pred_v[:m] - b2v[:m])))
            flag = detector.update(err)
            if flag["alarm"]:
                detected = True
            buf_o.append(o)
            buf_a.append(int(a))
            buf_n.append(nxt_a)
            buf_r.append(float(rew))
            buf_t.append(bool(term))
            ep_ret += float(rew)
            prev_a = int(a)
            obs = nxt
            done = bool(term or trunc)
            if detected and policy != "never" and cycles < max_cycles and ledger.remaining > 0:
                # finish this step then maybe adapt after buffer grows
                if len(buf_o) >= 16:
                    break
        env.close()
        collect_ret.append(ep_ret)
        ep_i += 1
        if policy == "never":
            continue
        if detected and cycles < max_cycles and len(buf_o) >= 16:
            ds = _pack(buf_o, buf_a, buf_n, buf_r, buf_t, spec)
            val_n = 0
            if policy in ("mae", "action", "control") and ledger.remaining > 0:
                val_n = max(8, min(ledger.remaining, max(8, len(ds) // 4)))
            cand, _log = adapt_method("finetune", deployed, source_replay, ds, epochs=epochs, seed=seed + cycles, episode_disjoint=True)
            control_ret = None
            val_ds = ds
            if policy == "control" and val_n > 0:
                # act with candidate for val_n charged steps
                vo, va, vn, vr, vt = [], [], [], [], []
                envv = make_task_env(spec, seed=int(seed) + 9000 + cycles)
                ov, _ = envv.reset(seed=int(seed) + 9000 + cycles)
                est.reset()
                pc = _planner(cand)
                pc.reset_episode(int(seed) + 5000 + cycles)
                pa: int | None = None
                cret = 0.0
                steps = 0
                donev = False
                while steps < val_n and not donev and ledger.remaining > 0:
                    oo = np.asarray(ov, dtype=np.float32).reshape(-1)
                    bb = est.observe(oo, pa)
                    aa, _ = pc.act(bb)
                    nx, rw, tm, tr, _ = envv.step(int(aa))
                    ledger.charge(1, "online_val")
                    nxx = np.asarray(nx, dtype=np.float32).reshape(-1)
                    vo.append(oo)
                    va.append(int(aa))
                    vn.append(nxx)
                    vr.append(float(rw))
                    vt.append(bool(tm))
                    cret += float(rw)
                    pa = int(aa)
                    ov = nx
                    steps += 1
                    donev = bool(tm or tr)
                envv.close()
                control_ret = cret
                val_ds = _pack(vo, va, vn, vr, vt, spec)
            elif val_n > 0 and policy in ("mae", "action"):
                # extra val transitions under deployed, charged
                vo, va, vn, vr, vt = [], [], [], [], []
                envv = make_task_env(spec, seed=int(seed) + 8000 + cycles)
                ov, _ = envv.reset(seed=int(seed) + 8000 + cycles)
                est.reset()
                pd = _planner(deployed)
                pd.reset_episode(int(seed) + 4000 + cycles)
                pa = None
                steps = 0
                donev = False
                while steps < val_n and not donev and ledger.remaining > 0:
                    oo = np.asarray(ov, dtype=np.float32).reshape(-1)
                    bb = est.observe(oo, pa)
                    aa, _ = pd.act(bb)
                    nx, rw, tm, tr, _ = envv.step(int(aa))
                    ledger.charge(1, "online_val")
                    nxx = np.asarray(nx, dtype=np.float32).reshape(-1)
                    vo.append(oo)
                    va.append(int(aa))
                    vn.append(nxx)
                    vr.append(float(rw))
                    vt.append(bool(tm))
                    pa = int(aa)
                    ov = nx
                    steps += 1
                    donev = bool(tm or tr)
                envv.close()
                val_ds = _pack(vo, va, vn, vr, vt, spec)
            rate = float(np.mean(collect_ret)) if collect_ret else 0.0
            ok, reason = _decide(policy, deployed, cand, val_ds, control_return=control_ret, deployed_rate=rate)
            if ok:
                deployed = cand
                commits.append(reason)
            else:
                rejects.append(reason)
            cycles += 1
            buf_o, buf_a, buf_n, buf_r, buf_t = [], [], [], [], []
            detected = False
            detector._buf = []
            if ep_i > 40:
                break
        if ep_i > 80:
            break

    return {
        "model": deployed,
        "ledger": ledger.snapshot(),
        "committed": bool(commits),
        "detected": bool(commits or rejects or detected),
        "commits": commits,
        "rejects": rejects,
        "n_commit": len(commits),
        "n_reject": len(rejects),
        "cycles": cycles,
        "policy": policy,
        "collect_returns": collect_ret,
        "gru_in_mpc": False,
        "uses_confirmation": False,
    }
