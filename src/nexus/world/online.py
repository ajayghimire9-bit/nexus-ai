"""Incremental online detect/adapt with decision-aware commit. GRU is not used in MPC."""

from __future__ import annotations

from typing import Any, Literal

import numpy as np

from nexus.tasks.spec import TaskSpec, make_task_env
from nexus.world.adapt import WindowThresholdDetector, adapt_method
from nexus.world.agent import InteractionLedger, _mae
from nexus.world.belief import BeliefEstimator, BeliefStepModel, IdentityBelief
from nexus.world.data import TransitionDataset
from nexus.world.dynamics import WorldModel
from nexus.world.planning import RandomShootingMPC, mpc_for_model
from nexus.world.planning import one_step_greedy

GatePolicy = Literal["never", "always", "mae", "action", "control"]


def _planner(wm: WorldModel) -> RandomShootingMPC:
    return mpc_for_model(BeliefStepModel(wm), seed=0)


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


FairGatePolicy = Literal["never", "always", "mae", "control_fair"]


class ObserveCounter:
    """Wraps an estimator and counts observe() calls (one per env step)."""

    name = "observe_counter"
    dim = 4
    uses_privileged_state = False

    def __init__(self, inner: BeliefEstimator) -> None:
        self.inner = inner
        self.n_observe = 0
        self.n_reset = 0

    def reset(self) -> None:
        self.n_reset += 1
        self.inner.reset()

    def observe(self, obs: np.ndarray, action: int | None = None) -> np.ndarray:
        self.n_observe += 1
        return self.inner.observe(obs, action)


def _fair_pack(
    obs: list,
    act: list,
    nxt: list,
    rew: list,
    term: list,
    trunc: list,
    seeds: list,
    eids: list,
    spec: TaskSpec,
    stop_reasons: list[str],
) -> TransitionDataset:
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
            notes={"stop_reasons": []},
        )
    return TransitionDataset(
        obs=np.stack(obs, axis=0),
        action=np.asarray(act, dtype=np.int64),
        next_obs=np.stack(nxt, axis=0),
        reward=np.asarray(rew, dtype=np.float32),
        terminated=np.asarray(term, dtype=np.bool_),
        truncated=np.asarray(trunc, dtype=np.bool_),
        task_id=spec.task_id,
        seed=np.asarray(seeds, dtype=np.int64),
        episode_id=np.asarray(eids, dtype=np.int64),
        policy=np.array(["online"] * n, dtype=object),
        physics=dict(spec.params),
        env_interactions=n,
        notes={"stop_reasons": list(stop_reasons)},
    )


def _pred_err(wm: WorldModel, belief: np.ndarray, action: int, next_obs: np.ndarray) -> float:
    pred, _p = wm.step(belief, int(action))
    p = np.asarray(pred, dtype=np.float32).reshape(-1)
    n = np.asarray(next_obs, dtype=np.float32).reshape(-1)
    m = min(p.size, n.size)
    return float(np.mean(np.abs(p[:m] - n[:m])))


def _reserve_steps(policy: FairGatePolicy) -> int:
    from nexus.world.verify import CONTROL_VAL_EPISODES, CONTROL_VAL_HORIZON

    if policy == "control_fair":
        return 2 * int(CONTROL_VAL_HORIZON) * int(CONTROL_VAL_EPISODES)
    if policy == "mae":
        return int(CONTROL_VAL_HORIZON)
    return 0


def run_fair_online(
    spec: TaskSpec,
    source: WorldModel,
    source_replay: TransitionDataset,
    est: BeliefEstimator,
    *,
    target_cap: int,
    policy: FairGatePolicy,
    epochs: int,
    seed: int,
    detector: WindowThresholdDetector,
    max_cycles: int = 3,
    audit_updates: bool = True,
) -> dict[str, Any]:
    """Matched-horizon control verification. Confirmation eval is never consulted."""
    from nexus.world.verify import (
        CONTROL_VAL_HORIZON,
        MIN_IMPROVE,
        ProposalTrace,
        control_decision,
        matched_control_compare,
        mpc_action_disagreement,
    )

    ledger = InteractionLedger(target_cap=int(target_cap))
    deployed = source.clone()
    traces: list[ProposalTrace] = []
    commits: list[str] = []
    rejects: list[str] = []
    n_insufficient = 0
    n_inconclusive = 0
    n_accept = 0
    n_reject = 0
    n_proposals = 0
    n_audit_harmful = 0
    n_audit_beneficial = 0
    detected = False
    cycles = 0
    ep_i = 0
    env_steps = 0
    counter = ObserveCounter(est)
    reserved = _reserve_steps(policy)
    can_reserve = int(target_cap) >= reserved > 0

    buf_o: list[np.ndarray] = []
    buf_a: list[int] = []
    buf_n: list[np.ndarray] = []
    buf_r: list[float] = []
    buf_term: list[bool] = []
    buf_trunc: list[bool] = []
    buf_seed: list[int] = []
    buf_eid: list[int] = []
    stop_reasons: list[str] = []

    if target_cap <= 0:
        return {
            "model": deployed,
            "ledger": ledger.snapshot(),
            "committed": False,
            "detected": False,
            "commits": commits,
            "rejects": rejects,
            "n_commit": 0,
            "n_accept": 0,
            "n_reject": 0,
            "n_proposals": 0,
            "n_insufficient": 0,
            "n_inconclusive": 0,
            "acceptance_rate": 0.0,
            "insufficient_evidence_rate": 0.0,
            "conditional_harm": "not_applicable",
            "proposal_traces": [],
            "cycles": 0,
            "policy": policy,
            "gru_in_mpc": False,
            "uses_confirmation": False,
            "n_env_steps": 0,
            "n_observe": 0,
            "observe_once": True,
            "min_improve": MIN_IMPROVE,
        }

    def _maybe_adapt() -> None:
        nonlocal deployed, detected, cycles, n_proposals, n_accept, n_reject, n_insufficient, n_inconclusive
        nonlocal n_audit_harmful, n_audit_beneficial
        nonlocal buf_o, buf_a, buf_n, buf_r, buf_term, buf_trunc, buf_seed, buf_eid, stop_reasons
        if policy == "never" or cycles >= max_cycles or len(buf_o) < 16:
            return
        n_proposals += 1
        pid = f"p{cycles}"
        ds = _fair_pack(buf_o, buf_a, buf_n, buf_r, buf_term, buf_trunc, buf_seed, buf_eid, spec, stop_reasons)
        inc_state = {k: v.detach().cpu().clone() for k, v in deployed.net.state_dict().items()}
        cand, clog = adapt_method("finetune", deployed, source_replay, ds, epochs=epochs, seed=seed + cycles, episode_disjoint=True)
        train_n = int(clog.get("train_n", len(ds)))
        decision = "reject"
        reason = "unevaluated"
        inc_scores: list[float] = []
        cand_scores: list[float] = []
        diff: float | None = None
        val_i = 0
        val_c = 0
        disag = None
        if policy == "always":
            decision, reason, diff = "accept", "always", None
        elif policy == "mae":
            need = reserved if can_reserve else 32
            if ledger.remaining < need:
                decision, reason = "reject", "insufficient_budget"
                n_insufficient += 1
            else:
                vo, va, vn, vr, vt, vtr, vs, ve, vrss = [], [], [], [], [], [], [], [], []
                envv = make_task_env(spec, seed=int(seed) + 8000 + cycles)
                ov, _ = envv.reset(seed=int(seed) + 8000 + cycles)
                val_est = IdentityBelief()
                val_est.reset()
                pd = _planner(deployed)
                pd.reset_episode(int(seed) + 4000 + cycles)
                pa: int | None = None
                steps = 0
                donev = False
                while steps < need and not donev and ledger.remaining > 0:
                    oo = np.asarray(ov, dtype=np.float32).reshape(-1)
                    bb = val_est.observe(oo, pa)
                    aa, _ = pd.act(bb)
                    nx, rw, tm, trc, _ = envv.step(int(aa))
                    ledger.charge(1, "online_val")
                    nxx = np.asarray(nx, dtype=np.float32).reshape(-1)
                    vo.append(oo)
                    va.append(int(aa))
                    vn.append(nxx)
                    vr.append(float(rw))
                    vt.append(bool(tm))
                    vtr.append(bool(trc))
                    vs.append(int(seed) + 8000 + cycles)
                    ve.append(10_000 + cycles)
                    vrss.append("natural" if (tm or trc) else "horizon")
                    pa = int(aa)
                    ov = nx
                    steps += 1
                    donev = bool(tm or trc)
                envv.close()
                val_ds = _fair_pack(vo, va, vn, vr, vt, vtr, vs, ve, spec, vrss)
                val_i = val_c = len(val_ds)
                if len(val_ds) == 0:
                    decision, reason = "reject", "insufficient_evidence"
                    n_insufficient += 1
                else:
                    before, after = _mae(deployed, val_ds), _mae(cand, val_ds)
                    if after <= before * 0.97:
                        decision, reason, diff = "accept", "mae_improved", float(before - after)
                    else:
                        decision, reason, diff = "reject", "mae_reject", float(before - after)
        else:
            cmp = matched_control_compare(
                spec,
                deployed,
                cand,
                ledger=ledger,
                seed=int(seed) + 9000 + cycles,
                bucket="online_val",
            )
            val_i = int(cmp.get("incumbent_steps", 0))
            val_c = int(cmp.get("candidate_steps", 0))
            if not cmp["ok"]:
                decision, reason = "reject", str(cmp.get("reason", "insufficient_budget"))
                n_insufficient += 1
            else:
                inc_scores = list(cmp["incumbent_scores"])
                cand_scores = list(cmp["candidate_scores"])
                decision, reason, dlt = control_decision(inc_scores, cand_scores)
                diff = None if dlt != dlt else float(dlt)
                if decision == "inconclusive":
                    n_inconclusive += 1
                    decision = "reject"
                elif decision == "reject" and reason in ("insufficient_evidence", "insufficient_budget"):
                    n_insufficient += 1
            disag = mpc_action_disagreement(deployed, cand, ds.obs, seed=seed + cycles)

        after_inc = {k: v.detach().cpu() for k, v in deployed.net.state_dict().items()}
        for k in inc_state:
            if not bool((inc_state[k] == after_inc[k]).all()):
                raise RuntimeError("validation mutated incumbent")

        audit_i = audit_c = None
        audit_steps = 0
        if audit_updates and decision == "accept":
            aud = matched_control_compare(
                spec,
                deployed,
                cand,
                ledger=ledger,
                seed=int(seed) + 50_000 + cycles,
                bucket="eval_only",
            )
            audit_steps = int(aud.get("incumbent_steps", 0)) + int(aud.get("candidate_steps", 0))
            if aud.get("ok") and aud["incumbent_scores"] and aud["candidate_scores"]:
                audit_i = float(np.mean(aud["incumbent_scores"]))
                audit_c = float(np.mean(aud["candidate_scores"]))
                if audit_c >= audit_i + MIN_IMPROVE:
                    n_audit_beneficial += 1
                elif audit_c <= audit_i - MIN_IMPROVE:
                    n_audit_harmful += 1

        if decision == "accept":
            deployed = cand
            commits.append(reason)
            n_accept += 1
        else:
            rejects.append(reason)
            n_reject += 1
        traces.append(
            ProposalTrace(
                proposal_id=pid,
                policy=policy,
                train_interactions=train_n,
                val_incumbent_steps=val_i,
                val_candidate_steps=val_c,
                horizon=CONTROL_VAL_HORIZON,
                n_episodes=1,
                incumbent_scores=inc_scores,
                candidate_scores=cand_scores,
                diff=diff,
                decision="accept" if decision == "accept" else "reject",
                reason=reason,
                target_used_after=int(ledger.target_used),
                audit_eval_only_steps=audit_steps,
                audit_incumbent=audit_i,
                audit_candidate=audit_c,
                mpc_action_disagreement=disag,
            )
        )
        cycles += 1
        buf_o, buf_a, buf_n, buf_r, buf_term, buf_trunc, buf_seed, buf_eid = [], [], [], [], [], [], [], []
        stop_reasons = []
        detected = False
        detector._buf = []

    while ledger.remaining > 0 and ep_i < 80:
        floor = reserved if can_reserve else 0
        if policy != "never" and detected and len(buf_o) >= 16 and ledger.remaining <= floor:
            _maybe_adapt()
            if ledger.remaining <= 0:
                break
        env_seed = int(seed) + 17 * ep_i
        env = make_task_env(spec, seed=env_seed)
        obs, _ = env.reset(seed=env_seed)
        counter.reset()
        planner = _planner(deployed)
        planner.reset_episode(int(seed) + 1000 * ep_i)
        prev_a: int | None = None
        done = False
        ep_stop = "budget"
        while not done and ledger.remaining > 0:
            floor = reserved if can_reserve else 0
            if policy != "never" and detected and len(buf_o) >= 16 and ledger.remaining <= floor:
                ep_stop = "adapt_cut"
                break
            o = np.asarray(obs, dtype=np.float32).reshape(-1)
            b = counter.observe(o, prev_a)
            a, _meta = planner.act(b)
            nxt, rew, term, trunc, _ = env.step(int(a))
            bucket = "detect" if (policy == "never" or not detected) else "adapt_collect"
            ledger.charge(1, bucket)
            env_steps += 1
            nxt_a = np.asarray(nxt, dtype=np.float32).reshape(-1)
            err = _pred_err(deployed, b, int(a), nxt_a)
            flag = detector.update(err)
            if flag["alarm"]:
                detected = True
            buf_o.append(o)
            buf_a.append(int(a))
            buf_n.append(nxt_a)
            buf_r.append(float(rew))
            buf_term.append(bool(term))
            buf_trunc.append(bool(trunc))
            buf_seed.append(int(env_seed))
            buf_eid.append(int(ep_i))
            prev_a = int(a)
            obs = nxt
            done = bool(term or trunc)
            if done:
                ep_stop = "natural"
            if detected and policy != "never" and cycles < max_cycles and len(buf_o) >= 16:
                floor = reserved if can_reserve else 0
                if ledger.remaining <= floor or policy == "always":
                    ep_stop = "adapt_cut" if not done else "natural"
                    break
        env.close()
        stop_reasons.append(ep_stop)
        ep_i += 1
        if policy != "never" and detected and len(buf_o) >= 16:
            floor = reserved if can_reserve else 0
            if policy == "always" or ledger.remaining <= floor or ledger.remaining == 0:
                _maybe_adapt()

    if policy != "never" and detected and len(buf_o) >= 16 and cycles < max_cycles:
        _maybe_adapt()

    cond_harm: float | str
    if n_accept == 0:
        cond_harm = "not_applicable"
    else:
        cond_harm = float(n_audit_harmful) / float(n_accept)

    return {
        "model": deployed,
        "ledger": ledger.snapshot(),
        "committed": bool(n_accept),
        "detected": bool(n_proposals or detected),
        "commits": commits,
        "rejects": rejects,
        "n_commit": n_accept,
        "n_accept": n_accept,
        "n_reject": n_reject,
        "n_proposals": n_proposals,
        "n_insufficient": n_insufficient,
        "n_inconclusive": n_inconclusive,
        "acceptance_rate": float(n_accept) / float(n_proposals) if n_proposals else 0.0,
        "insufficient_evidence_rate": float(n_insufficient) / float(n_proposals) if n_proposals else 0.0,
        "conditional_harm": cond_harm,
        "n_audit_beneficial": n_audit_beneficial,
        "n_audit_harmful": n_audit_harmful,
        "proposal_traces": [t.as_dict() for t in traces],
        "cycles": cycles,
        "policy": policy,
        "gru_in_mpc": False,
        "uses_confirmation": False,
        "n_env_steps": env_steps,
        "n_observe": counter.n_observe,
        "observe_once": counter.n_observe == env_steps,
        "min_improve": MIN_IMPROVE,
        "reserved_val_steps": reserved if can_reserve else 0,
    }
