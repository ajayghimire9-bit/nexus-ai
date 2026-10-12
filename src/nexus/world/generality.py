"""Planning-generality diagnostic on Pendulum. Does not overwrite H=3 cross-env confirm. Not AGI."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import source_policy_task
from nexus.tasks.pendulum_family import (
    PENDULUM_MAX_STEPS,
    pendulum_confirmation_targets,
    pendulum_default,
    pendulum_development,
)
from nexus.tasks.spec import TaskSpec, make_task_env
from nexus.world.agent import plan_with_belief
from nexus.world.baselines import heuristic_pendulum_pd, random_cartpole, run_episodes
from nexus.world.belief import IdentityBelief
from nexus.world.data import assert_disjoint_seeds, collect_transitions
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_EPOCHS, FROZEN_HIDDEN, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL, FROZEN_PRIMARY_HORIZON
from nexus.world.imagine import multi_step_errors
from nexus.world.planning import InferenceCounter, RandomShootingMPC
from nexus.world.protocol import (
    V089G_CARTPOLE_EVAL_SEED,
    V089G_COLLECT_SEED,
    V089G_CONFIRM_EVAL_SEED,
    V089G_DEV_EVAL_SEED,
    V089G_TRAIN_SEED,
    V089G_VAL_SEED,
    V089X_EVAL_SEED,
)
from nexus.world.rewards import pendulum_step_reward
from nexus.world.train import one_step_errors, train_world_model
from nexus.world.v072 import PLAN_BUDGET
from nexus.world.v085 import _git_meta

HORIZONS = (3, 8, 16, 32)
FIXED_CANDIDATES = int(FROZEN_CANDIDATES[FROZEN_PRIMARY_HORIZON])  # 16
IMAGINE_BUDGET = int(PLAN_BUDGET)  # 48 = 16*3
CROSS_ENV_HASH = "402ce4151837eb0d"


class PrivilegedPendulumDynamics:
    """Dev-only simulator step. Never a learned controller. Sets privileged (theta, thdot)."""

    uses_simulator = True
    uses_privileged_state = True

    def __init__(self, spec: TaskSpec) -> None:
        self.spec = spec
        self.env = make_task_env(spec, seed=0)
        self.env.reset(seed=0)

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        o = np.asarray(obs, dtype=np.float32)
        single = o.ndim == 1
        if single:
            o = o.reshape(1, -1)
        act = np.asarray(action).reshape(-1)
        if act.size == 1 and o.shape[0] > 1:
            act = np.repeat(act, o.shape[0])
        nxts = []
        inner = self.env.unwrapped
        for i in range(o.shape[0]):
            theta = float(np.arctan2(o[i, 1], o[i, 0]))
            thdot = float(o[i, 2])
            inner.state = np.array([theta, thdot], dtype=np.float64)
            a = int(act[i])
            nxt, _rew, _t, _tr, _ = self.env.step(a)
            nxts.append(np.asarray(nxt, dtype=np.float32).reshape(-1))
        p = np.zeros(o.shape[0], dtype=np.float64)
        out = np.stack(nxts, axis=0)
        return (out.reshape(-1) if single else out), (p.reshape(()) if single else p)

    def close(self) -> None:
        self.env.close()


def n_cand_for(horizon: int, *, mode: str) -> int:
    h = int(horizon)
    if mode == "fixed_candidates":
        return int(FIXED_CANDIDATES)
    return max(2, int(IMAGINE_BUDGET) // h)


def validate_cross_env_preserved(path: str | Path = "artifacts/cross_environment.json") -> dict[str, Any]:
    p = json.loads(Path(path).read_text())
    h = p.get("protocol", {}).get("protocol_hash")
    return {"ok": h == CROSS_ENV_HASH, "protocol_hash": h, "expected": CROSS_ENV_HASH}


def _eval_pendulum_mpc(
    spec: TaskSpec,
    model: Any,
    *,
    horizon: int,
    n_cand: int,
    seed: int,
    episodes: int,
) -> dict[str, Any]:
    inf = InferenceCounter(model)
    planner = RandomShootingMPC(
        model=inf,
        n_actions=3,
        horizon=int(horizon),
        n_candidates=int(n_cand),
        seed=0,
        objective="predicted_reward",
        step_reward=pendulum_step_reward,
        inference=inf,
        enforce_time_budget=False,
    )
    times: list[float] = []
    actions: list[int] = []

    def act(obs: np.ndarray) -> int:
        a, meta = planner.act(obs)
        times.append(float(meta["plan_ms"]))
        actions.append(int(a))
        return int(a)

    row = run_episodes(
        spec,
        act_fn=act,
        episodes=int(episodes),
        seed=int(seed),
        max_steps=PENDULUM_MAX_STEPS,
        on_episode_start=lambda ep, p=planner, s=seed: p.reset_episode(int(s) + 1000 * int(ep)),
    )
    hist = np.bincount(np.asarray(actions, dtype=np.int64), minlength=3).astype(float)
    hist = hist / max(float(hist.sum()), 1.0)
    return {
        "mean_return": float(row["mean_return"]),
        "env_interactions": int(row["env_interactions"]),
        "mean_plan_ms": float(np.mean(times)) if times else 0.0,
        "model_states": int(inf.states),
        "action_hist": [float(x) for x in hist],
        "used_simulator": bool(getattr(model, "uses_simulator", False)),
        "n_decisions": len(actions),
        "imagined_per_decision": int(n_cand) * int(horizon),
    }


def run_planning_generality(
    *,
    n_model_seeds: int = 10,
    n_dev_seeds: int = 5,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    eval_episodes: int = 2,
    dev_episodes: int | None = None,
    artifact_path: str | Path | None = "artifacts/planning_generality.json",
    checkpoint_dir: str | Path = "checkpoints/planning_generality",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    horizons: tuple[int, ...] = HORIZONS
    if quick:
        n_model_seeds, n_dev_seeds = min(n_model_seeds, 1), min(n_dev_seeds, 1)
        n_train, n_val, epochs, eval_episodes = 48, 24, 1, 1
        horizons = (3, 8)
    dev_ep = 1 if dev_episodes is None else int(dev_episodes)
    if quick:
        dev_ep = 1
    confirm_ep = int(eval_episodes)
    dev = pendulum_development()
    confirms = pendulum_confirmation_targets()
    cart = source_policy_task()
    if quick:
        confirms = confirms[:1]
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    modes = ("fixed_candidates", "fixed_imagine_budget")
    configs = [(h, m, n_cand_for(h, mode=m)) for h in horizons for m in modes]
    git = _git_meta()
    protocol = {
        "code_version": "planning_generality",
        "parent_commit": "3aceb76",
        "cross_env_hash_frozen": CROSS_ENV_HASH,
        "kind": FROZEN_KIND,
        "hidden": list(FROZEN_HIDDEN),
        "horizons_dev": list(horizons),
        "fixed_candidates": FIXED_CANDIDATES,
        "imagine_budget": IMAGINE_BUDGET,
        "n_train": n_train,
        "n_val": n_val,
        "epochs": epochs,
        "n_dev_seeds": n_dev_seeds,
        "n_confirm_seeds": n_model_seeds,
        "dev_eval_seed": V089G_DEV_EVAL_SEED,
        "confirm_eval_seed": V089G_CONFIRM_EVAL_SEED,
        "cartpole_eval_seed": V089G_CARTPOLE_EVAL_SEED,
        "prior_h3_eval_seed_not_reused": V089X_EVAL_SEED,
        "retuned_width": False,
        "oracle_on_confirmation": False,
        "is_agi": False,
        "claims_learning_to_learn": False,
        "quick": quick,
        "dev_episodes": dev_ep,
        "confirm_episodes": confirm_ep,
        "git": git,
    }
    preserved = validate_cross_env_preserved()

    def _fit(spec: TaskSpec, mseed: int) -> tuple[Any, dict[str, Any], Any, Any]:
        train = collect_transitions(
            spec, n_transitions=n_train, env_seeds=tuple(range(10 + 8 * mseed, 18 + 8 * mseed)),
            base_seed=V089G_COLLECT_SEED + 19 * mseed, mix=("random",),
        )
        val = collect_transitions(
            spec, n_transitions=n_val, env_seeds=tuple(range(400 + 8 * mseed, 408 + 8 * mseed)),
            base_seed=V089G_VAL_SEED + 19 * mseed, mix=("random",),
        )
        assert_disjoint_seeds(train, val)
        wm, slog = train_world_model(
            train, val, kind=FROZEN_KIND, epochs=epochs, seed=V089G_TRAIN_SEED + 13 * mseed, hidden=FROZEN_HIDDEN, n_actions=spec.n_actions,
        )  # type: ignore[arg-type]
        return wm, slog, train, val

    rng_rand = np.random.default_rng(V089G_DEV_EVAL_SEED)

    def _rand(_o: np.ndarray, r=rng_rand) -> int:
        return int(r.integers(0, 3))

    grid_means: dict[str, list[float]] = {f"h{h}_{mode}": [] for h, mode, _n in configs}
    oracle_means: dict[str, list[float]] = {k: [] for k in grid_means}
    rand_dev: list[float] = []
    heu_dev: list[float] = []
    mae_dev: list[float] = []
    ms3_dev: list[float] = []
    dev_rows: list[dict[str, Any]] = []

    for mseed in range(n_dev_seeds):
        wm, slog, _tr, val = _fit(dev, mseed)
        pred = one_step_errors(wm, val)
        ms = multi_step_errors(wm, val, (1, 3, 8))
        mae_dev.append(float(pred["mae"]))
        if ms.get("3", {}).get("mean_mae") is not None:
            ms3_dev.append(float(ms["3"]["mean_mae"]))
        ev_r = run_episodes(dev, act_fn=_rand, episodes=dev_ep, seed=V089G_DEV_EVAL_SEED, max_steps=PENDULUM_MAX_STEPS)
        ev_h = run_episodes(dev, act_fn=heuristic_pendulum_pd, episodes=dev_ep, seed=V089G_DEV_EVAL_SEED, max_steps=PENDULUM_MAX_STEPS)
        rand_dev.append(float(ev_r["mean_return"]))
        heu_dev.append(float(ev_h["mean_return"]))
        oracle = PrivilegedPendulumDynamics(dev)
        learned_cfg: dict[str, Any] = {}
        oracle_cfg: dict[str, Any] = {}
        for h, mode, nc in configs:
            key = f"h{h}_{mode}"
            learned_cfg[key] = _eval_pendulum_mpc(dev, wm, horizon=h, n_cand=nc, seed=V089G_DEV_EVAL_SEED, episodes=dev_ep)
            oracle_cfg[key] = _eval_pendulum_mpc(dev, oracle, horizon=h, n_cand=nc, seed=V089G_DEV_EVAL_SEED, episodes=dev_ep)
            grid_means[key].append(float(learned_cfg[key]["mean_return"]))
            oracle_means[key].append(float(oracle_cfg[key]["mean_return"]))
        oracle.close()
        dev_rows.append(
            {
                "model_seed": mseed,
                "val_mae": pred["mae"],
                "multi_step": {k: ms[k] for k in ms},
                "random": ev_r["mean_return"],
                "heuristic": ev_h["mean_return"],
                "learned": learned_cfg,
                "oracle_simulator": oracle_cfg,
                "pretrain": int(n_train + n_val),
            }
        )
        print(f"generality dev seed={mseed}", flush=True)
        del _tr

    def _mean(xs: list[float]) -> float:
        return float(np.mean(xs)) if xs else float("-inf")

    ranked = sorted(
        (
            {
                "key": k,
                "horizon": int(k.split("_")[0][1:]),
                "mode": k.split("_", 1)[1],
                "n_cand": n_cand_for(int(k.split("_")[0][1:]), mode=k.split("_", 1)[1]),
                "mean_return": _mean(v),
                "imagined": n_cand_for(int(k.split("_")[0][1:]), mode=k.split("_", 1)[1]) * int(k.split("_")[0][1:]),
            }
            for k, v in grid_means.items()
            if v
        ),
        key=lambda r: (r["mean_return"], -r["imagined"], -r["horizon"]),
        reverse=True,
    )
    selected = ranked[0] if ranked else {"key": "h3_fixed_candidates", "horizon": 3, "mode": "fixed_candidates", "n_cand": 16}
    protocol["selected"] = selected
    protocol["selection_rule"] = "dev_max_mean_return_then_cheaper_imagined"
    protocol["protocol_hash"] = hashlib.sha256(dumps_strict({k: protocol[k] for k in protocol if k != "protocol_hash"}).encode()).hexdigest()[:16]

    def _m(d: dict[str, list[float]], k: str) -> float:
        return _mean(d.get(k, []))

    diagnosis = {
        "world_model": {
            "oracle_minus_learned_h3_fixed_candidates": _m(oracle_means, "h3_fixed_candidates") - _m(grid_means, "h3_fixed_candidates"),
            "oracle_minus_learned_h32_fixed_candidates": _m(oracle_means, "h32_fixed_candidates") - _m(grid_means, "h32_fixed_candidates") if "h32_fixed_candidates" in grid_means else None,
        },
        "horizon": {
            "learned_h32_minus_h3_fixed_candidates": (_m(grid_means, "h32_fixed_candidates") - _m(grid_means, "h3_fixed_candidates")) if "h32_fixed_candidates" in grid_means else None,
            "oracle_h32_minus_h3_fixed_candidates": (_m(oracle_means, "h32_fixed_candidates") - _m(oracle_means, "h3_fixed_candidates")) if "h32_fixed_candidates" in oracle_means else None,
        },
        "search": {
            "learned_h32_fixed_candidates_minus_fixed_budget": (
                _m(grid_means, "h32_fixed_candidates") - _m(grid_means, "h32_fixed_imagine_budget")
            )
            if "h32_fixed_candidates" in grid_means
            else None,
        },
        "action_interface": {
            "n_actions": 3,
            "torques": [-2.0, 0.0, 2.0],
            "oracle_best_dev_mean": max((_mean(v) for v in oracle_means.values() if v), default=float("nan")),
        },
        "note": "Oracle is the simulator on development only. Not a learned or deployable controller.",
    }

    confirm_rows: list[dict[str, Any]] = []
    for mseed in range(n_model_seeds):
        by_task: dict[str, Any] = {}
        for spec in confirms:
            wm, slog, train, val = _fit(spec, mseed)
            pred = one_step_errors(wm, val)
            ms = multi_step_errors(wm, val, (1, 3, 8))
            ev_r = run_episodes(spec, act_fn=_rand, episodes=confirm_ep, seed=V089G_CONFIRM_EVAL_SEED, max_steps=PENDULUM_MAX_STEPS)
            ev_h = run_episodes(spec, act_fn=heuristic_pendulum_pd, episodes=confirm_ep, seed=V089G_CONFIRM_EVAL_SEED, max_steps=PENDULUM_MAX_STEPS)
            ev_sel = _eval_pendulum_mpc(
                spec, wm, horizon=int(selected["horizon"]), n_cand=int(selected["n_cand"]),
                seed=V089G_CONFIRM_EVAL_SEED, episodes=confirm_ep,
            )
            ev_h3 = _eval_pendulum_mpc(spec, wm, horizon=3, n_cand=FIXED_CANDIDATES, seed=V089G_CONFIRM_EVAL_SEED, episodes=confirm_ep)
            ev_h16 = _eval_pendulum_mpc(spec, wm, horizon=16, n_cand=FIXED_CANDIDATES, seed=V089G_CONFIRM_EVAL_SEED, episodes=confirm_ep)
            by_task[spec.task_id] = {
                "params": dict(spec.params),
                "val_mae": pred["mae"],
                "multi_step": {k: ms[k] for k in ms},
                "random": ev_r["mean_return"],
                "heuristic": ev_h["mean_return"],
                "selected": ev_sel,
                "h3_fixed16": ev_h3,
                "h16_fixed16": ev_h16,
                "pretrain": int(train.env_interactions + val.env_interactions),
            }
        confirm_rows.append({"model_seed": mseed, "tasks": by_task})
        print(f"generality confirm seed={mseed} sel={selected['key']}", flush=True)

    cart_rows: list[dict[str, Any]] = []
    for mseed in range(n_model_seeds):
        train = collect_transitions(
            cart, n_transitions=n_train, env_seeds=tuple(range(12 + 8 * mseed, 20 + 8 * mseed)),
            base_seed=V089G_COLLECT_SEED + 200 + mseed, mix=("random", "exploratory"),
        )
        val = collect_transitions(
            cart, n_transitions=n_val, env_seeds=tuple(range(500 + 8 * mseed, 508 + 8 * mseed)),
            base_seed=V089G_VAL_SEED + 200 + mseed, mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        wm, _slog = train_world_model(train, val, kind=FROZEN_KIND, epochs=epochs, seed=4 + 13 * mseed, hidden=FROZEN_HIDDEN, n_actions=2)  # type: ignore[arg-type]
        mpc = plan_with_belief(cart, wm, IdentityBelief(), seed=V089G_CARTPOLE_EVAL_SEED, episodes=confirm_ep)
        rnd = run_episodes(cart, act_fn=lambda o, r=np.random.default_rng(V089G_CARTPOLE_EVAL_SEED): random_cartpole(o, r), episodes=confirm_ep, seed=V089G_CARTPOLE_EVAL_SEED)
        cart_rows.append({"model_seed": mseed, "mpc": mpc["mean_return"], "random": rnd["mean_return"], "model_states": mpc["model_states"]})

    def _seed_task_mean(field: str) -> list[float]:
        out = []
        for s in confirm_rows:
            out.append(float(np.mean([s["tasks"][tid][field] if field != "selected" else s["tasks"][tid]["selected"]["mean_return"] for tid in s["tasks"]])))
        return out

    def _sel_ret(s: dict[str, Any]) -> float:
        return float(np.mean([s["tasks"][tid]["selected"]["mean_return"] for tid in s["tasks"]]))

    def _h3_ret(s: dict[str, Any]) -> float:
        return float(np.mean([s["tasks"][tid]["h3_fixed16"]["mean_return"] for tid in s["tasks"]]))

    def _h16_ret(s: dict[str, Any]) -> float:
        return float(np.mean([s["tasks"][tid]["h16_fixed16"]["mean_return"] for tid in s["tasks"]]))

    def _rnd(s: dict[str, Any]) -> float:
        return float(np.mean([s["tasks"][tid]["random"] for tid in s["tasks"]]))

    def _heu(s: dict[str, Any]) -> float:
        return float(np.mean([s["tasks"][tid]["heuristic"] for tid in s["tasks"]]))

    sel_vs_rand = [_sel_ret(s) - _rnd(s) for s in confirm_rows]
    h1_ok = bool(sel_vs_rand) and float(seed_level_ci(sel_vs_rand)["lo"]) > 0
    cart_delta = [float(r["mpc"]) - float(r["random"]) for r in cart_rows]
    cart_ok = bool(cart_delta) and float(seed_level_ci(cart_delta)["lo"]) > 0

    payload = {
        "protocol": protocol,
        "audit": {
            "cross_env_preserved": preserved,
            "reward": "gymnasium_pendulum_on_current_state",
            "train_val_disjoint_seeds": True,
            "confirm_eval_seed_new": V089G_CONFIRM_EVAL_SEED != V089X_EVAL_SEED,
            "oracle_never_on_confirm": True,
        },
        "development": {
            "random": seed_level_ci(rand_dev) if rand_dev else None,
            "heuristic": seed_level_ci(heu_dev) if heu_dev else None,
            "val_mae": seed_level_ci(mae_dev) if mae_dev else None,
            "multi_step_h3_mae": seed_level_ci(ms3_dev) if ms3_dev else None,
            "learned": {k: seed_level_ci(v) if v else None for k, v in grid_means.items()},
            "oracle_simulator": {k: seed_level_ci(v) if v else None for k, v in oracle_means.items()},
            "ranked": ranked,
            "diagnosis": diagnosis,
            "per_seed": dev_rows,
        },
        "confirmation": {
            "selected_return": seed_level_ci([_sel_ret(s) for s in confirm_rows]) if confirm_rows else None,
            "h3_return": seed_level_ci([_h3_ret(s) for s in confirm_rows]) if confirm_rows else None,
            "h16_return": seed_level_ci([_h16_ret(s) for s in confirm_rows]) if confirm_rows else None,
            "random": seed_level_ci([_rnd(s) for s in confirm_rows]) if confirm_rows else None,
            "heuristic": seed_level_ci([_heu(s) for s in confirm_rows]) if confirm_rows else None,
            "selected_minus_random": seed_level_ci(sel_vs_rand) if sel_vs_rand else None,
            "selected_minus_heuristic": seed_level_ci([_sel_ret(s) - _heu(s) for s in confirm_rows]) if confirm_rows else None,
            "h3_minus_random": seed_level_ci([_h3_ret(s) - _rnd(s) for s in confirm_rows]) if confirm_rows else None,
            "h16_minus_random": seed_level_ci([_h16_ret(s) - _rnd(s) for s in confirm_rows]) if confirm_rows else None,
            "per_seed": confirm_rows,
        },
        "cartpole_regression": {
            "mpc": seed_level_ci([float(r["mpc"]) for r in cart_rows]) if cart_rows else None,
            "random": seed_level_ci([float(r["random"]) for r in cart_rows]) if cart_rows else None,
            "mpc_minus_random": seed_level_ci(cart_delta) if cart_delta else None,
            "per_seed": cart_rows,
        },
        "decision": {
            "selected_protocol": selected,
            "pendulum_selected_beats_random": h1_ok,
            "cartpole_h3_still_beats_random": cart_ok,
            "proceed_to_meta_learning": bool(h1_ok and cart_ok),
            "reason": (
                "same recipe improves both families on untouched confirm"
                if (h1_ok and cart_ok)
                else "Pendulum confirm CI includes 0 or CartPole regression failed; do not meta-learn"
            ),
        },
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "Oracle uses the simulator on development only. Not learning-to-learn. Not AGI.",
    }
    del _seed_task_mean
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
