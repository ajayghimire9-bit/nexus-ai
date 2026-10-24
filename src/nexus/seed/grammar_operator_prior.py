"""Experience-learned grammar operator prior.

Orders already-available constructions. Does not add primitives, change
acceptance, or invent operator semantics. Relational signatures are
programmer-supplied features. Output symmetry is not guard symmetry.
"""
from __future__ import annotations

from typing import Any

from .mechanism_beyond_catalog import BeyondMeter, _action_input, apply_leaf
from .mechanism_wave4_diagnostic import WAVE4_LEAVES, residual_exists

GUARDS = ("id", "pos", "neg", "even", "abs_ge2", "mod4_eq0", "is_zero")
PRIOR_FEATURES = (
    "residual_id", "residual_pos", "residual_neg", "residual_even",
    "residual_abs_ge2", "residual_mod4_eq0", "residual_is_zero",
    "n_pairs", "y_eq_x_frac", "y_gt_x_frac", "then_even_pairs",
    "budget_left_frac",
)


class Wave5Meter(BeyondMeter):
    def __init__(self) -> None:
        super().__init__()
        self.prior_scoring_evals = 0
        self.feature_extracts = 0
        self.mapping_evals = 0
        self.prior_train_cost = 0

    def as_dict(self) -> dict[str, int]:
        out = super().as_dict()
        out.update(
            prior_scoring_evals=int(self.prior_scoring_evals),
            feature_extracts=int(self.feature_extracts),
            mapping_evals=int(self.mapping_evals),
            prior_train_cost=int(self.prior_train_cost),
            total_acquisition_work=int(self.total_acquisition_work),
        )
        return out

    @property
    def total_acquisition_work(self) -> int:
        return (
            int(self.env_interactions)
            + int(self.confirmatory_env_probes)
            + int(self.hypothesis_evals)
            + int(self.probe_feature_and_policy_evals)
            + int(self.retrieval_evals)
            + int(self.distill_cost)
            + int(self.residual_synthesis_evals)
            + int(self.prior_scoring_evals)
            + int(self.feature_extracts)
            + int(self.mapping_evals)
            + int(self.prior_train_cost)
        )


def public_pairs(transcript: list[dict[str, Any]]) -> list[tuple[int, int]]:
    pairs = []
    for row in transcript:
        x = _action_input(row.get("action") or "")
        if x is None or row.get("observation") is None:
            continue
        pairs.append((int(x), int(row["observation"])))
    return pairs


def extract_features(transcript: list[dict[str, Any]], meter: Wave5Meter | None = None,
                     steps_left: int = 4) -> dict[str, float]:
    if meter is not None:
        meter.feature_extracts += 1
    pairs = public_pairs(transcript)
    n = max(len(pairs), 1)
    feats = {name: 0.0 for name in PRIOR_FEATURES}
    feats["n_pairs"] = float(len(pairs)) / 5.0
    feats["budget_left_frac"] = max(0.0, min(1.0, steps_left / 8.0))
    if pairs:
        feats["y_eq_x_frac"] = sum(1 for x, y in pairs if x == y) / n
        feats["y_gt_x_frac"] = sum(1 for x, y in pairs if y > x) / n
        feats["then_even_pairs"] = sum(1 for x, _y in pairs if x % 2 == 0) / n
    for guard in GUARDS:
        feats["residual_" + guard] = float(residual_exists(guard, transcript, meter))
    return feats


def audit_source_variation(labels: list[str]) -> dict[str, Any]:
    counts = {guard: labels.count(guard) for guard in GUARDS}
    present = [guard for guard, n in counts.items() if n > 0]
    enough = {"pos", "neg", "even", "id"} <= set(present) or (
        counts.get("pos", 0) >= 1 and counts.get("even", 0) >= 2
    )
    return dict(
        counts=counts,
        present=present,
        enough_variation=enough,
        disclosed_development_curriculum=True,
        note="up_source lacks even; w5_source is a disclosed development curriculum",
    )


class GrammarOperatorPrior:
    def __init__(self) -> None:
        self.frequency: dict[str, float] = {guard: 0.0 for guard in GUARDS}
        self.weights: dict[str, list[float]] = {
            guard: [0.0] * len(PRIOR_FEATURES) for guard in GUARDS
        }
        self.attempted: list[str] = []
        self.failed: list[str] = []
        self.succeeded: list[str] = []
        self.train_rows = 0
        self.frozen = False

    def snapshot(self) -> dict[str, Any]:
        return dict(
            frequency=dict(self.frequency),
            weights={g: list(w) for g, w in self.weights.items()},
            attempted=list(self.attempted),
            failed=list(self.failed),
            succeeded=list(self.succeeded),
            train_rows=self.train_rows,
            frozen=self.frozen,
        )

    @classmethod
    def from_snapshot(cls, snap: dict[str, Any]) -> "GrammarOperatorPrior":
        prior = cls()
        prior.frequency = {g: float((snap.get("frequency") or {}).get(g) or 0) for g in GUARDS}
        stored = snap.get("weights") or {}
        for guard in GUARDS:
            row = list(stored.get(guard) or [0.0] * len(PRIOR_FEATURES))
            prior.weights[guard] = (row + [0.0] * len(PRIOR_FEATURES))[:len(PRIOR_FEATURES)]
        prior.attempted = list(snap.get("attempted") or [])
        prior.failed = list(snap.get("failed") or [])
        prior.succeeded = list(snap.get("succeeded") or [])
        prior.train_rows = int(snap.get("train_rows") or 0)
        prior.frozen = bool(snap.get("frozen"))
        return prior

    def fit(self, rows: list[dict[str, Any]], meter: Wave5Meter | None = None) -> int:
        cost = 0
        for row in rows:
            guard = str(row.get("gold_guard") or "")
            if guard not in GUARDS:
                continue
            feats = row.get("features") or extract_features(row.get("transcript") or [], meter)
            self.frequency[guard] += 1.0
            for i, name in enumerate(PRIOR_FEATURES):
                self.weights[guard][i] += float(feats.get(name) or 0.0)
            self.succeeded.append(guard)
            self.train_rows += 1
            cost += 1 + len(PRIOR_FEATURES)
        if meter is not None:
            meter.prior_train_cost += cost
        return cost

    def freeze(self) -> None:
        self.frozen = True

    def score_guard(self, guard: str, feats: dict[str, float], meter: Wave5Meter | None = None) -> float:
        if meter is not None:
            meter.prior_scoring_evals += 1
        weights = self.weights.get(guard) or [0.0] * len(PRIOR_FEATURES)
        return sum(w * float(feats.get(name) or 0.0) for w, name in zip(weights, PRIOR_FEATURES))

    def frequency_order(self) -> list[str]:
        return sorted(GUARDS, key=lambda g: (-self.frequency.get(g, 0.0), g))

    def heuristic_order(self, feats: dict[str, float], meter: Wave5Meter | None = None) -> list[str]:
        scored = []
        for guard in GUARDS:
            if meter is not None:
                meter.prior_scoring_evals += 1
            residual = float(feats.get("residual_" + guard) or 0.0)
            scored.append((-residual, guard))
        return [guard for _score, guard in sorted(scored)]

    def learned_order(self, feats: dict[str, float], meter: Wave5Meter | None = None) -> list[str]:
        scored = []
        for guard in GUARDS:
            residual = float(feats.get("residual_" + guard) or 0.0)
            score = self.score_guard(guard, feats, meter)
            scored.append((-residual, -score, guard))
        return [guard for _r, _s, guard in sorted(scored)]

    def shuffled_order(self, seed: int) -> list[str]:
        import random
        order = list(GUARDS)
        random.Random(seed).shuffle(order)
        return order

    def record_attempt(self, guard: str, success: bool) -> None:
        self.attempted.append(guard)
        if success:
            self.succeeded.append(guard)
        else:
            self.failed.append(guard)
