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


# V0.8.5 reference protocol. Frozen before confirmation. Not used by run_gate.
V085_REF_HORIZON = 500
V085_REF_EPISODES = 2
V085_REF_MARGIN = 10.0
V085_H128 = 128
V085_MAE_STEPS = 32
V085_MAE_RATIO = 0.97  # frozen V0.8.5 threshold; do not retune on V0.8.6


@dataclass(frozen=True)
class GateInput:
    """Verifier input. Reference-evaluation scores are not a field and must not be added."""

    spec: TaskSpec
    incumbent: WorldModel
    candidate: WorldModel
    ledger: InteractionLedger
    seed: int
    val_data: Any | None = None
    horizon: int = CONTROL_VAL_HORIZON
    n_episodes: int = CONTROL_VAL_EPISODES
    min_improve: float = MIN_IMPROVE


def weights_hash(wm: WorldModel) -> str:
    import hashlib

    h = hashlib.sha256()
    for k, v in sorted(wm.net.state_dict().items()):
        h.update(k.encode())
        h.update(np.ascontiguousarray(v.detach().cpu().numpy()).tobytes())
    return h.hexdigest()[:16]


def classify_reference(incumbent_scores: list[float], candidate_scores: list[float], *, margin: float = V085_REF_MARGIN) -> str:
    if not incumbent_scores or not candidate_scores:
        return "unresolved"
    diff = float(np.mean(candidate_scores)) - float(np.mean(incumbent_scores))
    if diff >= float(margin):
        return "benefit"
    if diff <= -float(margin):
        return "harm"
    return "inconclusive"


def harm_status(*, n_accept: int, n_harmful_accept: int, n_unresolved_accept: int) -> dict[str, Any]:
    """Distinguish no acceptance, no detected harm, and inconclusive audits."""
    if int(n_accept) <= 0:
        return {"conditional_harm": "not_applicable", "status": "no_acceptance"}
    if int(n_unresolved_accept) > 0:
        rate = float(n_harmful_accept) / float(n_accept)
        return {"conditional_harm": rate, "status": "inconclusive_audits", "n_unresolved_accept": int(n_unresolved_accept)}
    rate = float(n_harmful_accept) / float(n_accept)
    return {
        "conditional_harm": rate,
        "status": "no_detected_harm" if n_harmful_accept == 0 else "detected_harm",
    }


def run_gate(name: str, inp: GateInput) -> dict[str, Any]:
    """Decision from GateInput only. Callers must not pass reference outcomes here."""
    from nexus.world.agent import _mae
    from nexus.world.belief import IdentityBelief
    from nexus.world.online import _planner
    from nexus.tasks.spec import make_task_env
    from nexus.world.data import TransitionDataset

    if name == "never":
        return {"decision": "reject", "reason": "never", "val_incumbent_steps": 0, "val_candidate_steps": 0, "ceiling_both": False, "incumbent_scores": [], "candidate_scores": []}
    if name == "always":
        return {"decision": "accept", "reason": "always", "val_incumbent_steps": 0, "val_candidate_steps": 0, "ceiling_both": False, "incumbent_scores": [], "candidate_scores": []}
    if name == "mae":
        need = V085_MAE_STEPS
        if inp.ledger.remaining < need:
            return {"decision": "reject", "reason": "insufficient_budget", "val_incumbent_steps": 0, "val_candidate_steps": 0, "ceiling_both": False, "incumbent_scores": [], "candidate_scores": []}
        spec = inp.spec
        vo, va, vn, vr, vt, vtr, vs, ve = [], [], [], [], [], [], [], []
        envv = make_task_env(spec, seed=int(inp.seed) + 8000)
        ov, _ = envv.reset(seed=int(inp.seed) + 8000)
        est = IdentityBelief()
        est.reset()
        pd = _planner(inp.incumbent)
        pd.reset_episode(int(inp.seed) + 4000)
        pa: int | None = None
        steps = 0
        donev = False
        while steps < need and not donev and inp.ledger.remaining > 0:
            oo = np.asarray(ov, dtype=np.float32).reshape(-1)
            bb = est.observe(oo, pa)
            aa, _ = pd.act(bb)
            nx, rw, tm, trc, _ = envv.step(int(aa))
            inp.ledger.charge(1, "online_val")
            nxx = np.asarray(nx, dtype=np.float32).reshape(-1)
            vo.append(oo)
            va.append(int(aa))
            vn.append(nxx)
            vr.append(float(rw))
            vt.append(bool(tm))
            vtr.append(bool(trc))
            vs.append(int(inp.seed) + 8000)
            ve.append(0)
            pa = int(aa)
            ov = nx
            steps += 1
            donev = bool(tm or trc)
        envv.close()
        n = len(vo)
        if n == 0:
            return {"decision": "reject", "reason": "insufficient_evidence", "val_incumbent_steps": 0, "val_candidate_steps": 0, "ceiling_both": False, "incumbent_scores": [], "candidate_scores": []}
        z = np.zeros((0, spec.obs_dim), dtype=np.float32)
        ds = TransitionDataset(
            obs=np.stack(vo),
            action=np.asarray(va, dtype=np.int64),
            next_obs=np.stack(vn),
            reward=np.asarray(vr, dtype=np.float32),
            terminated=np.asarray(vt, dtype=np.bool_),
            truncated=np.asarray(vtr, dtype=np.bool_),
            task_id=spec.task_id,
            seed=np.asarray(vs, dtype=np.int64),
            episode_id=np.asarray(ve, dtype=np.int64),
            policy=np.array(["mae_val"] * n, dtype=object),
            physics=dict(spec.params),
            env_interactions=n,
        )
        del z
        before, after = _mae(inp.incumbent, ds), _mae(inp.candidate, ds)
        if after <= before * V085_MAE_RATIO:
            dec, reason = "accept", "mae_improved"
        else:
            dec, reason = "reject", "mae_reject"
        return {
            "decision": dec,
            "reason": reason,
            "val_incumbent_steps": n,
            "val_candidate_steps": n,
            "ceiling_both": False,
            "incumbent_scores": [float(before)],
            "candidate_scores": [float(after)],
            "mae_before": float(before),
            "mae_after": float(after),
        }
    cmp = matched_control_compare(
        inp.spec,
        inp.incumbent,
        inp.candidate,
        ledger=inp.ledger,
        seed=int(inp.seed),
        horizon=int(inp.horizon),
        n_episodes=int(inp.n_episodes),
        bucket="online_val",
    )
    if not cmp["ok"]:
        return {
            "decision": "reject",
            "reason": str(cmp.get("reason", "insufficient_budget")),
            "val_incumbent_steps": 0,
            "val_candidate_steps": 0,
            "ceiling_both": False,
            "incumbent_scores": [],
            "candidate_scores": [],
        }
    inc_s = list(cmp["incumbent_scores"])
    cand_s = list(cmp["candidate_scores"])
    decision, reason, diff = control_decision(inc_s, cand_s, min_improve=float(inp.min_improve))
    if decision == "inconclusive":
        out_dec = "reject"
    else:
        out_dec = decision
    h = int(inp.horizon)
    ceil = bool(inc_s and cand_s and all(s >= h - 1e-6 for s in inc_s) and all(s >= h - 1e-6 for s in cand_s))
    return {
        "decision": out_dec,
        "reason": reason,
        "diff": None if diff != diff else float(diff),
        "val_incumbent_steps": int(cmp["incumbent_steps"]),
        "val_candidate_steps": int(cmp["candidate_steps"]),
        "ceiling_both": ceil,
        "incumbent_scores": inc_s,
        "candidate_scores": cand_s,
    }
