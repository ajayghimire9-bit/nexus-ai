"""Fair incumbent vs candidate control comparison. Frozen before confirmation.

Rule (development-frozen, not retuned on confirm):
- Identical horizon H=32, matched reset seeds, same noise/physics spec, same H=3 MPC budget.
- Both models frozen (eval, clones). Estimator/planner reset per rollout.
- Score = undiscounted return over the shared horizon (not reward/step).
- Accept iff candidate_mean >= incumbent_mean + MIN_IMPROVE.
- |diff| < MIN_IMPROVE is inconclusive (no accept).
- Need 2*H remaining target steps (both sides charged to online_val) else insufficient_budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from nexus.tasks.spec import TaskSpec, make_task_env
from nexus.world.agent import InteractionLedger
from nexus.world.belief import BeliefEstimator, BeliefStepModel, IdentityBelief
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_OBJECTIVE, FROZEN_PRIMARY_HORIZON
from nexus.world.planning import RandomShootingMPC

# Frozen 2026-10-12 before V0.8.4 confirmation. Do not edit after inspecting confirm.
CONTROL_VAL_HORIZON = 32
CONTROL_VAL_EPISODES = 1
MIN_IMPROVE = 2.0
MPC_ACTION_DIAGNOSTIC = True


@dataclass
class ProposalTrace:
    proposal_id: str
    policy: str
    train_interactions: int
    val_incumbent_steps: int
    val_candidate_steps: int
    horizon: int
    n_episodes: int
    incumbent_scores: list[float]
    candidate_scores: list[float]
    diff: float | None
    decision: str
    reason: str
    target_used_after: int
    audit_eval_only_steps: int = 0
    audit_incumbent: float | None = None
    audit_candidate: float | None = None
    mpc_action_disagreement: float | None = None
    uses_confirmation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "policy": self.policy,
            "train_interactions": self.train_interactions,
            "val_incumbent_steps": self.val_incumbent_steps,
            "val_candidate_steps": self.val_candidate_steps,
            "horizon": self.horizon,
            "n_episodes": self.n_episodes,
            "incumbent_scores": self.incumbent_scores,
            "candidate_scores": self.candidate_scores,
            "diff": self.diff,
            "decision": self.decision,
            "reason": self.reason,
            "target_used_after": self.target_used_after,
            "audit_eval_only_steps": self.audit_eval_only_steps,
            "audit_incumbent": self.audit_incumbent,
            "audit_candidate": self.audit_candidate,
            "mpc_action_disagreement": self.mpc_action_disagreement,
            "uses_confirmation": False,
        }


def control_decision(incumbent_scores: list[float], candidate_scores: list[float], *, min_improve: float = MIN_IMPROVE) -> tuple[str, str, float]:
    """Frozen accept/reject/inconclusive rule. Confirmation-blind."""
    if not incumbent_scores or not candidate_scores:
        return "reject", "insufficient_evidence", float("nan")
    inc = float(np.mean(incumbent_scores))
    cand = float(np.mean(candidate_scores))
    diff = cand - inc
    if diff >= float(min_improve):
        return "accept", "control_improved", diff
    if abs(diff) < float(min_improve):
        return "inconclusive", "tie_or_small_diff", diff
    return "reject", "control_worse", diff


def _rollout_frozen(
    spec: TaskSpec,
    wm: WorldModel,
    est: BeliefEstimator,
    *,
    horizon: int,
    seed: int,
    ledger: InteractionLedger,
    bucket: str,
) -> tuple[float, int, bool]:
    """One matched-horizon episode. Does not train. One observe per env step."""
    frozen = wm.clone()
    frozen.net.eval()
    env = make_task_env(spec, seed=seed)
    obs, _ = env.reset(seed=seed)
    est.reset()
    planner = RandomShootingMPC(
        model=BeliefStepModel(frozen),
        n_actions=2,
        horizon=FROZEN_PRIMARY_HORIZON,
        n_candidates=FROZEN_CANDIDATES[FROZEN_PRIMARY_HORIZON],
        seed=0,
        objective=FROZEN_OBJECTIVE,  # type: ignore[arg-type]
    )
    planner.reset_episode(seed)
    prev_a: int | None = None
    total = 0.0
    steps = 0
    natural = False
    while steps < int(horizon):
        if bucket == "eval_only":
            ledger.charge(1, "eval_only")
        else:
            if ledger.remaining <= 0:
                break
            ledger.charge(1, bucket)
        o = np.asarray(obs, dtype=np.float32).reshape(-1)
        b = est.observe(o, prev_a)
        a, _ = planner.act(b)
        nxt, rew, term, trunc, _ = env.step(int(a))
        total += float(rew)
        steps += 1
        prev_a = int(a)
        obs = nxt
        if term or trunc:
            natural = True
            break
    env.close()
    return total, steps, natural


def matched_control_compare(
    spec: TaskSpec,
    incumbent: WorldModel,
    candidate: WorldModel,
    *,
    ledger: InteractionLedger,
    seed: int,
    horizon: int = CONTROL_VAL_HORIZON,
    n_episodes: int = CONTROL_VAL_EPISODES,
    bucket: str = "online_val",
    est_factory: Any = IdentityBelief,
) -> dict[str, Any]:
    need = 2 * int(horizon) * int(n_episodes)
    if bucket != "eval_only" and ledger.remaining < need:
        return {
            "ok": False,
            "reason": "insufficient_budget",
            "need": need,
            "remaining": ledger.remaining,
            "incumbent_scores": [],
            "candidate_scores": [],
            "incumbent_steps": 0,
            "candidate_steps": 0,
        }
    inc_s: list[float] = []
    cand_s: list[float] = []
    inc_steps = 0
    cand_steps = 0
    for i in range(int(n_episodes)):
        rs = int(seed) + 17 * i
        r_i, n_i, _nat = _rollout_frozen(spec, incumbent, est_factory(), horizon=horizon, seed=rs, ledger=ledger, bucket=bucket)
        r_c, n_c, _natc = _rollout_frozen(spec, candidate, est_factory(), horizon=horizon, seed=rs, ledger=ledger, bucket=bucket)
        inc_s.append(r_i)
        cand_s.append(r_c)
        inc_steps += n_i
        cand_steps += n_c
        if n_i != n_c and n_i < horizon and n_c < horizon:
            pass  # both ended naturally at possibly different times; scores are returns over that shared max horizon cap
    return {
        "ok": True,
        "reason": "compared",
        "incumbent_scores": inc_s,
        "candidate_scores": cand_s,
        "incumbent_steps": inc_steps,
        "candidate_steps": cand_steps,
        "horizon": horizon,
        "n_episodes": n_episodes,
        "matched_reset_seeds": True,
        "used_mpc": True,
        "reward_per_step_not_used": True,
    }


def mpc_action_disagreement(
    incumbent: WorldModel,
    candidate: WorldModel,
    obs_batch: np.ndarray,
    *,
    seed: int,
) -> float:
    """Diagnostic only: fraction of states where H=3 MPC first actions differ (matched RNG)."""
    if obs_batch.size == 0:
        return 0.0
    o = np.asarray(obs_batch, dtype=np.float32)
    o = o.reshape(-1, o.shape[-1])
    n = min(int(o.shape[0]), 32)
    differ = 0
    for i in range(n):
        pi = RandomShootingMPC(BeliefStepModel(incumbent), n_actions=2, horizon=3, n_candidates=16, seed=0, objective="both")  # type: ignore[arg-type]
        pc = RandomShootingMPC(BeliefStepModel(candidate), n_actions=2, horizon=3, n_candidates=16, seed=0, objective="both")  # type: ignore[arg-type]
        pi.reset_episode(int(seed) + i)
        pc.reset_episode(int(seed) + i)
        ai, _ = pi.act(o[i])
        ac, _ = pc.act(o[i])
        if int(ai) != int(ac):
            differ += 1
    return float(differ / max(n, 1))
