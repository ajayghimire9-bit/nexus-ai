"""Observation-conditioned strategy memory wrapping AdaptiveProposer.

Does not replace AdaptiveProposer, Evolution-2 methods, or
ContextualStrategyMemory. Retrieval uses family-normalized planning
observations only. Checkpoints and E2.17 science files are unused.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from nexus.evolution1.catalogue import ContractError, digest
from nexus.evolution1.fixtures import PublicFixtureContext
from nexus.evolution1.toy_loop import ANCHORS, AdaptiveProposer, TrainingFeedback, VARIANTS, features
from nexus.evolution2.bindings import reviewed_binding

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "artifacts" / "evolution2_source_arrays"
FAMILIES = ("pendulum", "acrobot")
CALIBRATE_BUNDLES = (0, 1)
FAR_SIGMA = 4.0
SOURCE_QUERY_PERCENTILE = 75.0
CROSS_BUNDLE_PERCENTILE = 95.0
CROSS_BUNDLE_BUNDLES = (0, 1)


def refuse_science_path(path: Path) -> None:
    if "persist_reset_science" in str(path):
        raise RuntimeError("e217_science_artifacts_forbidden")


def load_source_train_obs(family: str, bundles: tuple[int, ...] = CALIBRATE_BUNDLES) -> np.ndarray:
    if family not in FAMILIES:
        raise ContractError("unsupported_observation_family")
    blocks = []
    for bundle in bundles:
        path = SOURCE / family / f"bundle{bundle}_train.npz"
        refuse_science_path(path)
        if not path.is_file():
            raise RuntimeError("permitted_source_array_missing")
        data = np.load(path)
        blocks.append(np.asarray(data["obs"], dtype=np.float64))
    obs = np.concatenate(blocks, axis=0)
    expected = reviewed_binding(family).obs_dim
    if obs.ndim != 2 or obs.shape[1] != expected:
        raise ContractError("observation_schema_mismatch")
    return obs


@dataclass
class FamilyNormalizer:
    """Per-family z-score. Fitted on permitted source training observations."""

    family: str
    mean: np.ndarray
    std: np.ndarray
    obs_dim: int
    n: int

    @classmethod
    def fit(cls, family: str, obs: np.ndarray) -> "FamilyNormalizer":
        if family not in FAMILIES:
            raise ContractError("unsupported_observation_family")
        arr = np.asarray(obs, dtype=np.float64)
        expected = reviewed_binding(family).obs_dim
        if arr.ndim != 2 or arr.shape[1] != expected:
            raise ContractError("observation_schema_mismatch")
        std = np.std(arr, axis=0)
        std = np.where(std < 1e-6, 1.0, std)
        return cls(family, np.mean(arr, axis=0), std, expected, int(arr.shape[0]))

    def embed(self, obs) -> np.ndarray:
        arr = np.asarray(obs, dtype=np.float64).reshape(-1)
        if arr.size != self.obs_dim or not np.all(np.isfinite(arr)):
            raise ContractError("invalid_planning_observation")
        return (arr - self.mean) / self.std

    def far_observation(self, *, k: float = FAR_SIGMA) -> np.ndarray:
        return (self.mean + float(k) * self.std).astype(np.float32)


@dataclass(frozen=True)
class MemoryEntry:
    fingerprint: str
    score: float
    embedding: tuple[float, ...]
    family: str
    obs_dim: int
    provenance: str
    support_digest: str
    n: int = 1


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)))


@dataclass
class SourceCalibration:
    kernel_length: float
    gate_threshold: float
    pairwise_median: float
    source_nn_p75: float
    n_obs: dict[str, int]
    rule: str = "within_source_nn_p75"
    frozen: bool = False
    extra: dict = field(default_factory=dict)


def calibrate_from_source(normalizers: dict[str, FamilyNormalizer], *, seed: int = 7, cap: int = 256) -> SourceCalibration:
    """Similarity thresholds from source training embeddings only."""
    rng = np.random.default_rng(int(seed))
    distances = []
    nearest = []
    n_obs = {}
    for family, norm in normalizers.items():
        raw = load_source_train_obs(family)
        n_obs[family] = int(raw.shape[0])
        idx = rng.choice(raw.shape[0], size=min(int(cap), raw.shape[0]), replace=False)
        emb = np.stack([norm.embed(row) for row in raw[idx]])
        for i in range(emb.shape[0]):
            others = np.linalg.norm(emb - emb[i], axis=1)
            others[i] = np.inf
            nearest.append(float(np.min(others)))
            for j in range(i + 1, emb.shape[0]):
                distances.append(float(np.linalg.norm(emb[i] - emb[j])))
    pairwise = float(np.median(distances)) if distances else 1.0
    nn_p75 = float(np.percentile(nearest, SOURCE_QUERY_PERCENTILE)) if nearest else pairwise
    length = max(pairwise, 1e-3)
    return SourceCalibration(length, max(nn_p75, 1e-3), pairwise, nn_p75, n_obs, "within_source_nn_p75", True)


def _embed_bundle(family: str, bundle: int, norm: FamilyNormalizer, rng: np.random.Generator, cap: int) -> np.ndarray:
    raw = load_source_train_obs(family, (bundle,))
    idx = rng.choice(raw.shape[0], size=min(int(cap), raw.shape[0]), replace=False)
    return np.stack([norm.embed(row) for row in raw[idx]])


def calibrate_cross_bundle(normalizers: dict[str, FamilyNormalizer], *, seed: int = 7, cap: int = 256) -> SourceCalibration:
    """Leave-one-bundle-out NN gate. Bundles 0↔1 only. No eval labels."""
    rng = np.random.default_rng(int(seed))
    pos = []
    far = []
    zero = []
    shuffled = []
    n_obs = {}
    for family, norm in normalizers.items():
        left = _embed_bundle(family, CROSS_BUNDLE_BUNDLES[0], norm, rng, cap)
        right = _embed_bundle(family, CROSS_BUNDLE_BUNDLES[1], norm, rng, cap)
        n_obs[family] = int(left.shape[0] + right.shape[0])
        library = np.concatenate([left, right], axis=0)
        for query, bank in ((left, right), (right, left)):
            dmat = np.linalg.norm(query[:, None, :] - bank[None, :, :], axis=2)
            pos.extend(float(x) for x in np.min(dmat, axis=1))
            perm = rng.permutation(query.shape[1])
            shuf = np.linalg.norm(query[:, perm][:, None, :] - bank[None, :, :], axis=2)
            shuffled.extend(float(x) for x in np.min(shuf, axis=1))
        far_emb = norm.embed(norm.far_observation())
        far.append(float(np.min(np.linalg.norm(library - far_emb, axis=1))))
        zero_emb = norm.embed(np.zeros(norm.obs_dim, dtype=np.float64))
        zero.append(float(np.min(np.linalg.norm(library - zero_emb, axis=1))))
    pos_nn = np.asarray(pos, dtype=np.float64)
    threshold = float(max(np.percentile(pos_nn, CROSS_BUNDLE_PERCENTILE), 1e-3))
    length = float(max(np.median(pos_nn), 1e-3))
    within = calibrate_from_source(normalizers, seed=seed, cap=cap)
    extra = {
        "cross_nn_median": float(np.median(pos_nn)),
        "cross_nn_p95": threshold,
        "cross_nn_max": float(np.max(pos_nn)),
        "n_lobo_queries": int(pos_nn.size),
        "recall_at_cross_gate": float(np.mean(pos_nn <= threshold)),
        "recall_at_within_gate": float(np.mean(pos_nn <= within.gate_threshold)),
        "false_accept_far": float(np.mean(np.asarray(far) <= threshold)),
        "false_accept_zero": float(np.mean(np.asarray(zero) <= threshold)),
        "false_accept_shuffled": float(np.mean(np.asarray(shuffled) <= threshold)),
        "far_nn": [float(x) for x in far],
        "zero_nn": [float(x) for x in zero],
        "within_gate_threshold": within.gate_threshold,
        "percentile_rule": CROSS_BUNDLE_PERCENTILE,
        "used_e222_shifted_outcomes": False,
    }
    return SourceCalibration(length, threshold, float(np.median(pos_nn)), within.source_nn_p75, n_obs, "cross_bundle_lobo_p95", True, extra)


@dataclass
class ObservationAwareAdaptive:
    """AdaptiveProposer plus gated observation retrieval. Not a new evolution stack."""

    name: str = "observation_aware_memory"
    resets: bool = False
    seed: int = 7
    gated: bool = True
    shuffle: bool = False
    persist_memory: bool = True
    reset_inner: bool = False
    label: str | None = None
    arbitration: str = "legacy"
    quality_error: float = 1.0
    inner: AdaptiveProposer = field(init=False)
    normalizers: dict[str, FamilyNormalizer] = field(default_factory=dict)
    calibration: SourceCalibration | None = None
    _store: list[MemoryEntry] = field(default_factory=list)
    _family: str | None = None
    _embedding: np.ndarray | None = None
    _obs: np.ndarray | None = None
    _support_digest: str = "none"
    _provenance: str = "unspecified"
    _last: dict = field(default_factory=dict)
    _feedback_seen: set[str] = field(default_factory=set)
    _receipts: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if self.arbitration not in ("legacy", "consensus", "evidence"):
            raise ContractError("unknown_observation_arbitration")
        if not math.isfinite(self.quality_error) or self.quality_error < 0:
            raise ContractError("invalid_source_quality_error")
        if type(self.seed) is not int or not 0 <= self.seed <= 10**9:
            raise ContractError("invalid_observation_memory_seed")
        self.inner = AdaptiveProposer(seed=self.seed)
        if self.label:
            self.name = str(self.label)
        elif self.shuffle:
            self.name = "observation_shuffled_memory"
        elif not self.gated:
            self.name = "observation_ungated_memory"
        self.inner.name = self.name
        self.resets = bool(self.reset_inner)

    def observe(self, family: str, obs, context: PublicFixtureContext, *, provenance: str, support_digest: str = "none") -> np.ndarray:
        if family not in self.normalizers:
            raise ContractError("unfitted_observation_family")
        if context.obs_dim != self.normalizers[family].obs_dim:
            raise ContractError("observation_schema_mismatch")
        if str(provenance) != self._provenance:
            self._receipts = {}
        self._family = family
        self._obs = np.asarray(obs, dtype=np.float64).reshape(-1)
        self._embedding = self.normalizers[family].embed(self._obs)
        self._provenance = str(provenance)
        self._support_digest = str(support_digest)
        return self._embedding

    def learned_state(self):
        return {**self.inner.learned_state(), "memory": len(self._store), "gated": self.gated, "shuffle": self.shuffle}

    def memory_state(self):
        return {
            "records": len(self._store),
            "gated": self.gated,
            "shuffle": self.shuffle,
            "families": sorted({row.family for row in self._store}),
        }

    def reset_task(self):
        self._receipts = {}
        if self.reset_inner:
            tie = dict(self.inner._tie_rank)
            self.inner = AdaptiveProposer(seed=self.seed)
            self.inner.name = self.name
            self.inner._tie_rank = tie
        if not self.persist_memory:
            self._store = []
            self.inner = AdaptiveProposer(seed=self.seed)
            self.inner.name = self.name
        self._feedback_seen = set()
        return self.learned_state()

    def last_decision(self) -> dict:
        return dict(self._last)

    def retrieve(self, family: str, embedding: np.ndarray) -> dict:
        if family not in self.normalizers:
            raise ContractError("unfitted_observation_family")
        dim = self.normalizers[family].obs_dim
        # Exclude the active task so anchor writes cannot open the gate.
        rows = [
            row
            for row in self._store
            if row.family == family and row.obs_dim == dim and row.provenance != self._provenance
        ]
        if self.shuffle and rows:
            rng = np.random.default_rng(self.seed + 31 * len(rows))
            embeddings = [row.embedding for row in rows]
            rng.shuffle(embeddings)
            rows = [
                MemoryEntry(row.fingerprint, row.score, embeddings[i], row.family, row.obs_dim, row.provenance, row.support_digest, row.n)
                for i, row in enumerate(rows)
            ]
        length = 1.0 if self.calibration is None else self.calibration.kernel_length
        threshold = math.inf if (self.calibration is None or not self.gated) else self.calibration.gate_threshold
        per_arm: dict[str, list[tuple[float, float]]] = {}
        nearest = math.inf
        nearest_fp = None
        for row in rows:
            dist = _distance(embedding, row.embedding)
            weight = math.exp(-((dist / length) ** 2))
            per_arm.setdefault(row.fingerprint, []).append((weight, row.score))
            if dist < nearest:
                nearest = dist
                nearest_fp = row.fingerprint
        ridge = 1.0
        scores = {}
        for fingerprint, pairs in per_arm.items():
            w = np.asarray([p[0] for p in pairs], dtype=np.float64)
            s = np.asarray([p[1] for p in pairs], dtype=np.float64)
            scores[fingerprint] = (float(np.sum(w * s)) + 0.5 * ridge) / (float(np.sum(w)) + ridge)
        confident = (not self.gated) or (nearest <= threshold and nearest is not math.inf)
        mass = 0.0 if nearest is math.inf else math.exp(-((nearest / length) ** 2))
        # Source LOBO p95 ≫ median: soft mass at the acceptance radius is ~0.
        # An open gate therefore uses the accepted neighbor (hard NN), not a
        # vanished kernel weight.
        hard_nn = bool(self.gated and self.calibration is not None and self.calibration.rule == "cross_bundle_lobo_p95")
        if hard_nn:
            confidence = 1.0 if confident else 0.0
        else:
            confidence = 0.0 if not confident else float(mass)
        return {
            "scores": scores,
            "nearest": None if nearest is math.inf else float(nearest),
            "nearest_fingerprint": nearest_fp,
            "confidence": confidence,
            "fallback": confidence <= 0.0,
            "eligible": len(rows),
            "gate_threshold": None if threshold is math.inf else float(threshold),
            "kernel_length": float(length),
        }

    def _inner_score(self, variant, context: PublicFixtureContext) -> float:
        return float(sum(w * x for w, x in zip(self.inner._weights, features(variant, context))))

    def task_evidence(self) -> list[dict]:
        """One weight per observed support context, NOT per arm or receipt.

        These are distinct observed contexts, not independent physics samples.
        Unknown support identity is insufficient to certify distinct contexts.
        """
        groups = {}
        for row in self._store:
            if (row.family != self._family or row.provenance == self._provenance
                    or row.support_digest == "none"
                    or row.obs_dim != self.normalizers[self._family].obs_dim):
                continue
            key = (row.support_digest, row.embedding)
            group = groups.setdefault(key, {"support_digest": row.support_digest,
                                           "embedding": row.embedding, "scores": {}})
            # Repeated rows/receipts cannot increase evidence or sample size.
            group["scores"][row.fingerprint] = row.score
        length = 1.0 if self.calibration is None else self.calibration.kernel_length
        out = []
        for group in groups.values():
            dist = _distance(self._embedding, group["embedding"])
            out.append({**group, "distance": dist, "weight": math.exp(-((dist / length) ** 2))})
        return out

    def _choose_evidence(self, available, context):
        incumbent = self.inner.choose(available, context)
        groups = self.task_evidence()
        anchors = tuple(v.fingerprint for v in ANCHORS)
        anchors_ready = all(a in self._receipts for a in anchors)
        covered = {fp for g in groups for fp in g["scores"]}
        coverage = sum(v.fingerprint in covered for v in available) / len(available)
        comparisons = {}
        for variant in available:
            fp = variant.fingerprint
            paired = [g for g in groups if fp in g["scores"] and incumbent.fingerprint in g["scores"]
                      and all(a in g["scores"] for a in anchors)]
            weights = np.asarray([g["weight"] for g in paired])
            mass = float(weights.sum())
            if mass <= 1e-300:
                comparisons[fp] = {"paired_contexts": len(paired), "mass": mass, "ess": 0.0,
                                   "advantage": None, "anchor_error": None, "accepted": False}
                continue
            w = weights / mass
            deltas = np.asarray([g["scores"][fp] - g["scores"][incumbent.fingerprint] for g in paired])
            advantage = float(w @ deltas)
            ess = float(mass * mass / (weights @ weights))
            agreement = float(w @ (deltas > 1e-12))
            spread = float(np.sqrt(w @ ((deltas - advantage) ** 2)))
            anchor_error = (float(w @ np.asarray([
                sum(abs(g["scores"][a] - self._receipts[a]) for a in anchors) / len(anchors)
                for g in paired])) if anchors_ready else None)
            penalty = self.quality_error + (anchor_error if anchors_ready else 1.0) + spread / math.sqrt(ess)
            lower_advantage = advantage - penalty
            # Fixed evidence sufficiency rules, not fitted development thresholds.
            if self.arbitration == "consensus":
                accepted = len(paired) >= 2 and agreement >= 0.75 and advantage > 1e-12
            else:
                accepted = (anchors_ready and len(paired) >= 2 and mass >= 1.0 and ess >= 1.5
                            and agreement >= 0.75 and lower_advantage > 1e-12)
            confidence = (mass / (1 + mass)) * (ess / (1 + ess)) * agreement * coverage
            comparisons[fp] = {"paired_contexts": len(paired), "mass": mass, "ess": ess,
                               "advantage": advantage, "agreement": agreement,
                               "spread": spread, "anchor_error": anchor_error,
                               "quality_error": self.quality_error, "lower_advantage": lower_advantage,
                               "confidence": confidence, "accepted": bool(accepted)}
        eligible = [v for v in available if comparisons[v.fingerprint]["accepted"]]
        choice = (max(eligible, key=lambda v: (
            comparisons[v.fingerprint]["lower_advantage" if self.arbitration == "evidence" else "advantage"],
            -self.inner._tie_rank[v.fingerprint])) if eligible else incumbent)
        selected = comparisons[choice.fingerprint]
        self._last = {"action": "retrieve" if eligible else "fallback", "choice": choice.fingerprint,
                      "persistent_choice": incumbent.fingerprint, "override": choice != incumbent,
                      "confidence": selected.get("confidence", 0.0) if eligible else 0.0,
                      "fallback": not bool(eligible), "independent_contexts": len(groups),
                      "coverage": coverage, "anchors_ready": anchors_ready,
                      "anchor_receipts": dict(self._receipts), "comparisons": comparisons,
                      "source_evidence": [{k: v for k, v in g.items() if k != "embedding"} for g in groups]}
        return choice

    def choose(self, available, context):
        if type(context) is not PublicFixtureContext:
            raise ContractError("public_training_context_required")
        if self._family is None or self._embedding is None:
            raise ContractError("planning_observation_required")
        if self.arbitration != "legacy":
            return self._choose_evidence(available, context)
        retrieved = self.retrieve(self._family, self._embedding)
        if retrieved["fallback"]:
            choice = self.inner.choose(available, context)
            self._last = {
                **retrieved,
                "action": "fallback",
                "choice": choice.fingerprint,
                "fallback_kind": "current_task_only" if self.reset_inner else "persistent_proposer",
            }
            return choice
        inner_raw = {variant.fingerprint: self._inner_score(variant, context) for variant in available}
        lo = min(inner_raw.values())
        hi = max(inner_raw.values())
        span = hi - lo
        conf = retrieved["confidence"]
        def blended(variant):
            inner_n = 0.5 if span <= 1e-12 else (inner_raw[variant.fingerprint] - lo) / span
            retr = retrieved["scores"].get(variant.fingerprint, 0.5)
            return (1.0 - conf) * inner_n + conf * retr
        choice = max(available, key=lambda variant: (blended(variant), -self.inner._tie_rank[variant.fingerprint]))
        incumbent = self.inner.choose(available, context)
        self._last = {**retrieved, "action": "retrieve", "choice": choice.fingerprint, "blend_confidence": conf,
                      "persistent_choice": incumbent.fingerprint, "override": choice != incumbent,
                      "inner_raw": inner_raw,
                      "inner_normalized": {fp: 0.5 if span <= 1e-12 else (x-lo)/span for fp,x in inner_raw.items()},
                      "blended_scores": {v.fingerprint: blended(v) for v in available},
                      "missing_arms": [v.fingerprint for v in available if v.fingerprint not in retrieved["scores"]]}
        return choice

    def update(self, feedback, context):
        if type(feedback) is not TrainingFeedback or type(context) is not PublicFixtureContext:
            raise ContractError("permitted_training_feedback_only")
        if feedback.event_id in self._feedback_seen:
            raise ContractError("replayed_training_feedback")
        if self._family is None or self._embedding is None:
            raise ContractError("planning_observation_required")
        self.inner.update(feedback, context)
        self._feedback_seen.add(feedback.event_id)
        if not feedback.failed:
            self._receipts[feedback.variant_id] = float(feedback.score)
        if not self.persist_memory:
            return
        score = 0.0 if feedback.failed else float(feedback.score)
        key = (feedback.variant_id, tuple(float(x) for x in self._embedding), self._family)
        for row in self._store:
            if ((row.fingerprint, row.embedding, row.family) == key
                    and (self.arbitration == "legacy" or
                         (row.provenance == self._provenance and row.support_digest == self._support_digest))):
                row_score = (row.score * row.n + score) / (row.n + 1)
                self._store.remove(row)
                self._store.append(
                    MemoryEntry(row.fingerprint, row_score, row.embedding, row.family, row.obs_dim, row.provenance, row.support_digest, row.n + 1)
                )
                return
        self._store.append(
            MemoryEntry(
                feedback.variant_id,
                score,
                tuple(float(x) for x in self._embedding),
                self._family,
                int(self._embedding.size),
                self._provenance,
                self._support_digest,
            )
        )


def fit_family_normalizers() -> dict[str, FamilyNormalizer]:
    return {family: FamilyNormalizer.fit(family, load_source_train_obs(family)) for family in FAMILIES}


def support_digest(support) -> str:
    payload = {
        "obs_mean": [float(x) for x in np.mean(np.asarray(support.obs, dtype=np.float64), axis=0)],
        "n": int(support.obs.shape[0]),
    }
    return digest(payload)


def make_observation_methods(seed: int, normalizers: dict[str, FamilyNormalizer], calibration: SourceCalibration) -> dict[str, ObservationAwareAdaptive]:
    gated = ObservationAwareAdaptive(seed=seed, gated=True, shuffle=False)
    ungated = ObservationAwareAdaptive(seed=seed, gated=False, shuffle=False)
    shuffled = ObservationAwareAdaptive(seed=seed, gated=True, shuffle=True)
    for method in (gated, ungated, shuffled):
        method.normalizers = normalizers
        method.calibration = calibration
    return {
        gated.name: gated,
        ungated.name: ungated,
        shuffled.name: shuffled,
    }


def make_cross_bundle_methods(
    seed: int,
    normalizers: dict[str, FamilyNormalizer],
    within: SourceCalibration,
    cross: SourceCalibration,
) -> dict[str, ObservationAwareAdaptive]:
    rows = (
        ObservationAwareAdaptive(seed=seed, gated=True, label="observation_fixed_gate"),
        ObservationAwareAdaptive(seed=seed, gated=True, label="observation_cross_bundle"),
        ObservationAwareAdaptive(seed=seed, gated=True, reset_inner=True, label="observation_cross_reset_fallback"),
        ObservationAwareAdaptive(seed=seed, gated=False, label="observation_ungated_memory"),
    )
    rows[0].calibration = within
    rows[1].calibration = cross
    rows[2].calibration = cross
    rows[3].calibration = cross
    for method in rows:
        method.normalizers = normalizers
    return {method.name: method for method in rows}
