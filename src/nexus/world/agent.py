"""Bounded OBSERVE→ESTIMATE→PLAN→ACT→DETECT→ADAPT→VERIFY→COMMIT/ROLLBACK loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from nexus.tasks.spec import TaskSpec
from nexus.world.adapt import WindowThresholdDetector, adapt_method, collect_with_actor
from nexus.world.baselines import run_episodes
from nexus.world.belief import BeliefEstimator, BeliefStepModel
from nexus.world.data import TransitionDataset, split_by_episodes
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_OBJECTIVE, FROZEN_PRIMARY_HORIZON
from nexus.world.planning import InferenceCounter, RandomShootingMPC
from nexus.world.train import one_step_errors


class BudgetExceededError(RuntimeError):
    pass


@dataclass
class InteractionLedger:
    """Target-learning cap is independent of pretrain and eval-only counters."""

    target_cap: int
    target_used: int = 0
    pretrain: int = 0
    eval_only: int = 0
    buckets: dict[str, int] = field(default_factory=lambda: {"detect": 0, "adapt_collect": 0, "online_val": 0})

    @property
    def remaining(self) -> int:
        return max(0, int(self.target_cap) - int(self.target_used))

    def charge(self, n: int, bucket: str) -> int:
        n = int(n)
        if n < 0:
            raise ValueError("negative interactions")
        if bucket == "pretrain":
            self.pretrain += n
            return n
        if bucket == "eval_only":
            self.eval_only += n
            return n
        if self.target_used + n > int(self.target_cap):
            raise BudgetExceededError(f"{self.target_used}+{n} exceeds cap {self.target_cap}")
        self.target_used += n
        self.buckets[bucket] = int(self.buckets.get(bucket, 0)) + n
        return n

    def snapshot(self) -> dict[str, Any]:
        return {
            "target_cap": int(self.target_cap),
            "target_used": int(self.target_used),
            "remaining": self.remaining,
            "pretrain": int(self.pretrain),
            "eval_only": int(self.eval_only),
            "buckets": dict(self.buckets),
            "within_cap": self.target_used <= self.target_cap,
        }


def plan_with_belief(
    spec: TaskSpec,
    wm: WorldModel,
    est: BeliefEstimator,
    *,
    seed: int,
    episodes: int,
) -> dict[str, Any]:
    step = BeliefStepModel(wm)
    inf = InferenceCounter(step)
    planner = RandomShootingMPC(
        model=step,
        n_actions=2,
        horizon=FROZEN_PRIMARY_HORIZON,
        n_candidates=FROZEN_CANDIDATES[FROZEN_PRIMARY_HORIZON],
        seed=0,
        inference=inf,
        objective=FROZEN_OBJECTIVE,  # type: ignore[arg-type]
    )

    def act(obs: np.ndarray) -> int:
        b = est.observe(obs, None)
        a, _meta = planner.act(b)
        return int(a)

    def on_start(ep: int) -> None:
        est.reset()
        planner.reset_episode(int(seed) + 1000 * int(ep))

    row = run_episodes(spec, act_fn=act, episodes=episodes, seed=seed, on_episode_start=on_start)
    rets = [float(x) for x in row["returns"]]
    return {
        "mean_return": float(row["mean_return"]),
        "fail_rate": float(np.mean([r < 500.0 for r in rets])) if rets else None,
        "env_interactions": int(row["env_interactions"]),
        "model_states": int(inf.states),
        "used_simulator": False,
        "used_privileged_physics": False,
        "used_privileged_state": False,
    }


def collect_planned_belief(
    spec: TaskSpec,
    wm: WorldModel,
    est: BeliefEstimator,
    n: int,
    *,
    env_seeds: tuple[int, ...],
    base_seed: int,
) -> TransitionDataset:
    if n <= 0:
        ds = collect_with_actor(spec, n_transitions=1, env_seeds=(1,), base_seed=1, actor=lambda o: 0)
        return ds.slice(np.zeros(0, dtype=np.int64))
    step = BeliefStepModel(wm)
    planner = RandomShootingMPC(
        model=step,
        n_actions=2,
        horizon=FROZEN_PRIMARY_HORIZON,
        n_candidates=FROZEN_CANDIDATES[FROZEN_PRIMARY_HORIZON],
        seed=0,
        objective=FROZEN_OBJECTIVE,  # type: ignore[arg-type]
    )

    def act(obs: np.ndarray) -> int:
        b = est.observe(obs, None)
        a, _ = planner.act(b)
        return int(a)

    def on_start(ep: int) -> None:
        est.reset()
        planner.reset_episode(int(base_seed) + 1000 * int(ep))

    return collect_with_actor(
        spec,
        n_transitions=n,
        env_seeds=env_seeds,
        base_seed=base_seed,
        actor=act,
        policy_name="belief_mpc",
        on_episode_start=on_start,
    )


def _mae(wm: WorldModel, ds: TransitionDataset) -> float:
    if len(ds) == 0:
        return float("inf")
    return float(one_step_errors(wm, ds)["mae"])


def gated_adapt(
    deployed: WorldModel,
    source_replay: TransitionDataset,
    target: TransitionDataset,
    *,
    policy: str,
    epochs: int,
    seed: int,
    mae_improve: float = 0.03,
) -> dict[str, Any]:
    """Train a candidate on episode-disjoint train; commit iff val MAE drops by ``mae_improve``.

    ``policy``: never | always | gated. Confirmation outcomes are not used.
    """
    checkpoint = deployed.clone()
    if policy == "never" or len(target) == 0:
        return {
            "committed": False,
            "reason": "never_or_empty",
            "model": checkpoint,
            "val_mae_before": None,
            "val_mae_after": None,
        }
    rng = np.random.default_rng(seed)
    tr, va = split_by_episodes(target, val_frac=0.25, rng=rng)
    before = _mae(checkpoint, va) if len(va) else _mae(checkpoint, tr)
    cand, log = adapt_method("finetune", checkpoint, source_replay, tr, epochs=epochs, seed=seed, episode_disjoint=True)
    after = _mae(cand, va) if len(va) else _mae(cand, tr)
    if policy == "always":
        return {"committed": True, "reason": "always", "model": cand, "val_mae_before": before, "val_mae_after": after, "log": {k: v for k, v in log.items() if k != "history"}}
    improved = bool(np.isfinite(after) and np.isfinite(before) and after <= before * (1.0 - float(mae_improve)))
    if improved:
        return {"committed": True, "reason": "val_mae_improved", "model": cand, "val_mae_before": before, "val_mae_after": after}
    return {"committed": False, "reason": "rollback", "model": checkpoint, "val_mae_before": before, "val_mae_after": after}


def run_closed_loop(
    spec: TaskSpec,
    source: WorldModel,
    source_replay: TransitionDataset,
    est: BeliefEstimator,
    *,
    target_cap: int,
    policy: str,
    epochs: int,
    seed: int,
    env_seeds: tuple[int, ...],
    detector: WindowThresholdDetector | None = None,
) -> dict[str, Any]:
    ledger = InteractionLedger(target_cap=int(target_cap))
    deployed = source.clone()
    if target_cap <= 0:
        return {"model": deployed, "ledger": ledger.snapshot(), "committed": False, "detected": False, "policy": policy}
    ds = collect_planned_belief(spec, deployed, est, target_cap, env_seeds=env_seeds, base_seed=seed)
    ledger.charge(int(ds.env_interactions), "adapt_collect")
    from nexus.world.adapt import per_transition_mae
    from nexus.world.belief import beliefs_from_dataset

    bds = beliefs_from_dataset(est, ds) if len(ds) else ds
    detected = False
    if detector is not None and len(bds):
        err = per_transition_mae(deployed, bds.obs, bds.action, bds.next_obs)
        scan = detector.scan(err)
        detected = bool(scan["first_alarm"] is not None)
        ledger.buckets["detect"] = int(ds.env_interactions)
    adapt_ds = bds
    # Source replay must match belief dim.
    if policy == "never":
        gate = gated_adapt(deployed, source_replay, adapt_ds, policy="never", epochs=epochs, seed=seed)
    elif not detected and policy == "gated":
        gate = gated_adapt(deployed, source_replay, adapt_ds, policy="never", epochs=epochs, seed=seed)
        gate["reason"] = "no_change_detected"
    else:
        gate = gated_adapt(deployed, source_replay, adapt_ds, policy=policy, epochs=epochs, seed=seed)
    return {
        "model": gate["model"],
        "ledger": ledger.snapshot(),
        "committed": gate["committed"],
        "detected": detected,
        "reason": gate.get("reason"),
        "val_mae_before": gate.get("val_mae_before"),
        "val_mae_after": gate.get("val_mae_after"),
        "policy": policy,
        "collect_n": len(ds),
    }
