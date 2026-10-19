"""Task-conditioned strategy memory. Development algorithm, not a scientific result.

Reuses the Evolution-1 catalogue, AdaptiveProposer features, and
TrainingFeedback. Does not replace AdaptiveProposer or Evolution-2 methods.
Does not read hidden family weights, holdout names, or H17 physics.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from nexus.evolution1.catalogue import ContractError
from nexus.evolution1.fixtures import PublicFixtureContext
from nexus.evolution1.toy_loop import VARIANTS, TrainingFeedback, features

SUPPORT_DIM = 12
DESCRIPTOR_DIM = SUPPORT_DIM
OBS_SKETCH_DIM = 8
MAX_OBS = 6
OBS_SCALE = 1.0
VARIANT_DIM = 6
RETRIEVED_DIM = 3
RIDGE = 1.0
UCB_ALPHA = 0.35
KERNEL_LENGTH = 1.25
MAX_MEMORY = 256
DESCRIPTOR_MODES = ("support", "obs", "combined")
SELECTORS = ("ucb", "retrieved_mean", "gated")


def _phi_dim(descriptor_dim: int) -> int:
    return int(descriptor_dim) + VARIANT_DIM + VARIANT_DIM + RETRIEVED_DIM


PHI_DIM = _phi_dim(SUPPORT_DIM)


@dataclass(frozen=True)
class SupportBatch:
    obs: np.ndarray
    action: np.ndarray
    next_obs: np.ndarray
    reward: np.ndarray

    def __post_init__(self):
        n = int(self.obs.shape[0])
        if n < 2 or self.action.shape[0] != n or self.next_obs.shape[0] != n or self.reward.shape[0] != n:
            raise ContractError("invalid_support_batch")


@dataclass
class MemoryRecord:
    descriptor: tuple[float, ...]
    variant_id: str
    score: float
    n: int = 1


def synthetic_support(context: PublicFixtureContext, seed: int, n: int = 32) -> SupportBatch:
    """Public-context support only. No hidden labels or family names."""
    rng = np.random.default_rng(int(seed) + 17 * int(context.obs_dim) + 13 * int(context.n_actions))
    obs = rng.normal(0.0, 1.0, size=(n, context.obs_dim)).astype(np.float64)
    action = rng.integers(0, context.n_actions, size=n)
    scale = 0.04 + 0.01 * (context.n_actions / 8.0)
    nxt = obs.copy()
    nxt[:, 0] = nxt[:, 0] + scale * (action.astype(np.float64) - (context.n_actions - 1) / 2.0)
    reward = -np.mean(obs * obs, axis=1) * (context.obs_dim / 16.0)
    return SupportBatch(obs, action, nxt, reward)


def support_from_arrays(obs, action, next_obs, reward=None, n: int = 32) -> SupportBatch:
    obs = np.asarray(obs, dtype=np.float64)[:n]
    action = np.asarray(action).reshape(-1)[:n]
    next_obs = np.asarray(next_obs, dtype=np.float64)[:n]
    if reward is None:
        reward = -np.mean(obs * obs, axis=1)
    else:
        reward = np.asarray(reward, dtype=np.float64).reshape(-1)[:n]
    return SupportBatch(obs, action, next_obs, reward)


def describe_support(support: SupportBatch, context: PublicFixtureContext, *, require_fit: bool = False) -> np.ndarray:
    """Fixed-length public descriptor. Works for different obs/action sizes."""
    obs = support.obs
    nxt = support.next_obs
    act = support.action.astype(np.float64)
    rew = support.reward
    cols = np.concatenate([obs, np.eye(context.n_actions)[support.action.astype(int)]], axis=1)
    try:
        coef, *_ = np.linalg.lstsq(cols, nxt, rcond=None)
        pred = cols @ coef
        err = nxt - pred
    except np.linalg.LinAlgError:
        if require_fit:
            raise
        err = nxt - obs
    desc = np.array(
        [
            context.obs_dim / 16.0,
            context.n_actions / 16.0,
            context.episode_steps / 16.0,
            float(np.mean(np.abs(obs))),
            float(np.std(obs)),
            float(np.mean(rew)),
            float(np.std(rew)),
            float(np.mean(np.abs(err))),
            float(np.std(err)),
            float(np.mean(act) / max(1, context.n_actions - 1)),
            float(np.std(act) / max(1, context.n_actions)),
            float(np.std(nxt)),
        ],
        dtype=np.float64,
    )
    if desc.shape[0] != SUPPORT_DIM:
        raise ContractError("descriptor_dim_mismatch")
    return desc


def describe_planning_obs(obs, context: PublicFixtureContext) -> np.ndarray:
    """Fixed-length sketch of the observation that will be passed to decide().

    Uses only the current public observation. No returns, labels, or scores.
    Pendulum (3) and Acrobot (6) are padded to the same 8-d vector.
    """
    if type(context) is not PublicFixtureContext:
        raise ContractError("public_training_context_required")
    arr = np.asarray(obs, dtype=np.float64).reshape(-1)
    if arr.size != context.obs_dim or not np.all(np.isfinite(arr)):
        raise ContractError("invalid_planning_observation")
    padded = np.zeros(MAX_OBS, dtype=np.float64)
    padded[: context.obs_dim] = np.tanh(arr / OBS_SCALE)
    mean_abs = float(np.mean(np.abs(arr)))
    rms = float(np.linalg.norm(arr) / math.sqrt(max(context.obs_dim, 1)))
    sketch = np.concatenate(
        [padded, np.array([math.tanh(mean_abs / OBS_SCALE), math.tanh(rms / OBS_SCALE)], dtype=np.float64)]
    )
    if sketch.shape[0] != OBS_SKETCH_DIM:
        raise ContractError("obs_sketch_dim_mismatch")
    return sketch


def compose_descriptor(
    support: SupportBatch,
    context: PublicFixtureContext,
    planning_obs=None,
    *,
    mode: str = "support",
) -> np.ndarray:
    if mode not in DESCRIPTOR_MODES:
        raise ContractError("unknown_descriptor_mode")
    support_desc = describe_support(support, context)
    if planning_obs is None:
        if mode != "support":
            raise ContractError("planning_observation_required")
        sketch = np.zeros(OBS_SKETCH_DIM, dtype=np.float64)
    else:
        sketch = describe_planning_obs(planning_obs, context)
    if mode == "support":
        return support_desc
    if mode == "obs":
        return sketch
    return np.concatenate([support_desc, sketch])


def _phi(descriptor: np.ndarray, variant, context: PublicFixtureContext, retrieved: tuple[float, float, float]) -> np.ndarray:
    vf = np.asarray(features(variant, context), dtype=np.float64)
    head = np.asarray(descriptor[:VARIANT_DIM], dtype=np.float64)
    if head.shape[0] < VARIANT_DIM:
        head = np.pad(head, (0, VARIANT_DIM - int(head.shape[0])))
    inter = head * vf
    extra = np.asarray(retrieved, dtype=np.float64)
    return np.concatenate([descriptor, vf, inter, extra])


class ContextualStrategyMemory:
    """Contextual LinUCB over catalogue arms with kernel strategy memory."""

    name = "contextual_strategy_memory"
    resets = False

    def __init__(
        self,
        seed: int = 7,
        *,
        retrieve: bool = True,
        persist_memory: bool = True,
        mode: str = "support",
        selector: str = "ucb",
    ):
        if type(seed) is not int or not 0 <= seed <= 10**9:
            raise ContractError("invalid_strategy_seed")
        if mode not in DESCRIPTOR_MODES:
            raise ContractError("unknown_descriptor_mode")
        if selector not in SELECTORS:
            raise ContractError("unknown_selector")
        self.seed = int(seed)
        self.retrieve = bool(retrieve)
        self.persist_memory = bool(persist_memory)
        self.mode = str(mode)
        self.selector = str(selector)
        self.descriptor_dim = {"support": SUPPORT_DIM, "obs": OBS_SKETCH_DIM, "combined": SUPPORT_DIM + OBS_SKETCH_DIM}[self.mode]
        self.phi_dim = _phi_dim(self.descriptor_dim)
        self._rng = np.random.default_rng(self.seed)
        self._A = np.eye(self.phi_dim, dtype=np.float64) * RIDGE
        self._b = np.zeros(self.phi_dim, dtype=np.float64)
        self._store: list[MemoryRecord] = []
        self._descriptor: np.ndarray | None = None
        self._context: PublicFixtureContext | None = None
        self._feedback_seen: set[str] = set()
        self._updates = 0
        self._allow_local = True
        order = list(VARIANTS)
        self._rng.shuffle(order)
        self._tie_rank = {v.fingerprint: i for i, v in enumerate(order)}

    def observe_support(self, support: SupportBatch, context: PublicFixtureContext, planning_obs=None) -> np.ndarray:
        self._context = context
        self._descriptor = compose_descriptor(support, context, planning_obs, mode=self.mode)
        return self._descriptor

    def learned_state(self):
        return {
            "weights": tuple(float(x) for x in (np.linalg.solve(self._A, self._b) if self._updates else self._b)),
            "updates": self._updates,
            "memory": len(self._store),
            "retrieve": self.retrieve,
        }

    def memory_state(self):
        return {
            "records": len(self._store),
            "retrieve": self.retrieve,
            "persist": self.persist_memory,
            "mode": self.mode,
            "selector": self.selector,
            "descriptor_dim": self.descriptor_dim,
        }

    def reset_task(self):
        if not self.persist_memory:
            self._store = []
            self._A = np.eye(self.phi_dim, dtype=np.float64) * RIDGE
            self._b = np.zeros(self.phi_dim, dtype=np.float64)
            self._updates = 0
        self._feedback_seen = set()
        return self.learned_state()

    def eval_clone(self, *, local_updates: bool):
        clone = ContextualStrategyMemory(
            seed=self.seed,
            retrieve=self.retrieve,
            persist_memory=self.persist_memory,
            mode=self.mode,
            selector=self.selector,
        )
        clone._A = self._A.copy()
        clone._b = self._b.copy()
        clone._store = [MemoryRecord(r.descriptor, r.variant_id, r.score, r.n) for r in self._store]
        clone._descriptor = None if self._descriptor is None else self._descriptor.copy()
        clone._context = self._context
        clone._tie_rank = dict(self._tie_rank)
        clone._updates = self._updates
        clone._allow_local = bool(local_updates)
        clone._feedback_seen = set()
        return clone

    def update_eval(self, feedback, context):
        if self._allow_local:
            self.update(feedback, context)

    def _retrieve(self, variant_id: str) -> tuple[float, float, float, float, float, float]:
        if not self.retrieve or self._descriptor is None or not self._store:
            return 0.5, 1.0, 0.0, 0.0, math.inf, 0.5
        desc = self._descriptor
        weights = []
        scores = []
        nearest = math.inf
        for row in self._store:
            if row.variant_id != variant_id:
                continue
            dist = float(np.linalg.norm(desc - np.asarray(row.descriptor, dtype=np.float64)))
            w = math.exp(-((dist / KERNEL_LENGTH) ** 2))
            weights.append(w)
            scores.append(row.score)
            nearest = min(nearest, dist)
        if not weights:
            return 0.5, 1.0, 0.0, 0.0, math.inf, 0.5
        w = np.asarray(weights, dtype=np.float64)
        s = np.asarray(scores, dtype=np.float64)
        raw_mass = float(np.sum(w))
        mean = float(np.sum(w * s) / raw_mass)
        shrunk = (float(np.sum(w * s)) + 0.5 * RIDGE) / (raw_mass + RIDGE)
        var = float(np.sum(w * (s - mean) ** 2) / raw_mass)
        mass = min(1.0, raw_mass / 3.0)
        conflict = 1.0 if var > 0.04 and mass > 0.4 else 0.0
        return mean, math.sqrt(max(var, 1e-8)), mass, conflict, nearest, shrunk

    def _uses_retrieved_mean(self, mass: float, conflict: float, min_dist: float) -> bool:
        if not self.retrieve:
            return False
        if self.selector == "retrieved_mean":
            return True
        if mass <= 0:
            return False
        if self.selector == "gated":
            return min_dist <= KERNEL_LENGTH and conflict < 1.0
        return False

    def _arm_score(self, variant, context: PublicFixtureContext) -> float:
        _mean, _std, mass, conflict, min_dist, shrunk = self._retrieve(variant.fingerprint)
        if self._uses_retrieved_mean(mass, conflict, min_dist):
            return shrunk
        return self._ucb(variant, context)

    def _ucb(self, variant, context: PublicFixtureContext) -> float:
        mean, std, mass, conflict, _min_dist, _shrunk = self._retrieve(variant.fingerprint)
        # High neighbor conflict downweights the retrieved mean and raises exploration.
        retrieved = (mean * (1.0 - 0.5 * conflict), std, mass)
        phi = _phi(self._descriptor, variant, context, retrieved)
        theta = np.linalg.solve(self._A, self._b)
        try:
            ainv_phi = np.linalg.solve(self._A, phi)
            explore = math.sqrt(max(float(phi @ ainv_phi), 0.0))
        except np.linalg.LinAlgError:
            explore = 1.0
        bonus = UCB_ALPHA * (explore + 0.25 * conflict)
        return float(theta @ phi + bonus)

    def choose(self, available, context, *, retrieve: bool | None = None):
        if type(context) is not PublicFixtureContext:
            raise ContractError("public_training_context_required")
        if self._descriptor is None:
            raise ContractError("support_descriptor_required")
        previous = self.retrieve
        if retrieve is not None:
            self.retrieve = bool(retrieve)
        try:
            return max(available, key=lambda v: (self._arm_score(v, context), -self._tie_rank[v.fingerprint]))
        finally:
            self.retrieve = previous

    def update(self, feedback, context):
        if type(feedback) is not TrainingFeedback or type(context) is not PublicFixtureContext:
            raise ContractError("permitted_training_feedback_only")
        if feedback.event_id in self._feedback_seen:
            raise ContractError("replayed_training_feedback")
        if self._descriptor is None:
            raise ContractError("support_descriptor_required")
        variant = next(v for v in VARIANTS if v.fingerprint == feedback.variant_id)
        y = 0.0 if feedback.failed else float(feedback.score)
        retrieved = self._retrieve(variant.fingerprint)[:3]
        phi = _phi(self._descriptor, variant, context, retrieved)
        self._A = self._A + np.outer(phi, phi)
        self._b = self._b + y * phi
        self._updates += 1
        self._feedback_seen.add(feedback.event_id)
        if self.persist_memory:
            desc = tuple(float(x) for x in self._descriptor)
            for row in self._store:
                if row.variant_id == feedback.variant_id and row.descriptor == desc:
                    row.score = (row.score * row.n + y) / (row.n + 1)
                    row.n += 1
                    break
            else:
                self._store.append(MemoryRecord(desc, feedback.variant_id, y))
            if len(self._store) > MAX_MEMORY:
                self._store = self._store[-MAX_MEMORY:]

    def retrieval_conflict(self, variant) -> float:
        return self._retrieve(variant.fingerprint)[3]

    def retrieval_trace(self, variant_id: str | None = None, *, k: int = 4) -> list[dict]:
        if self._descriptor is None or not self._store:
            return []
        desc = self._descriptor
        rows = []
        for row in self._store:
            if variant_id is not None and row.variant_id != variant_id:
                continue
            dist = float(np.linalg.norm(desc - np.asarray(row.descriptor, dtype=np.float64)))
            weight = math.exp(-((dist / KERNEL_LENGTH) ** 2))
            rows.append(
                {
                    "variant_id": row.variant_id,
                    "score": float(row.score),
                    "n": int(row.n),
                    "distance": dist,
                    "weight": weight,
                }
            )
        rows.sort(key=lambda item: (item["distance"], -item["weight"]))
        return rows[:k]

    def rank_table(self, available, context: PublicFixtureContext) -> list[dict]:
        rows = []
        for variant in available:
            mean, std, mass, conflict, min_dist, shrunk = self._retrieve(variant.fingerprint)
            rows.append(
                {
                    "variant_id": variant.fingerprint,
                    "score": float(self._arm_score(variant, context)),
                    "ucb": float(self._ucb(variant, context)),
                    "retrieved_mean": mean,
                    "retrieved_shrunk": shrunk,
                    "retrieved_std": std,
                    "mass": mass,
                    "conflict": conflict,
                    "min_dist": min_dist,
                    "uses_retrieved_mean": self._uses_retrieved_mean(mass, conflict, min_dist),
                }
            )
        rows.sort(key=lambda item: (-item["score"], item["variant_id"]))
        return rows


def make_memory_pair(seed: int = 7) -> dict[str, ContextualStrategyMemory]:
    return {
        "memory": ContextualStrategyMemory(seed=seed, retrieve=True, persist_memory=True, mode="support"),
        "memory_ablated": ContextualStrategyMemory(seed=seed, retrieve=False, persist_memory=False, mode="support"),
    }


def make_descriptor_configs(seed: int = 7) -> dict[str, ContextualStrategyMemory]:
    """Four matched memory configurations. Persist stays an external baseline."""
    return {
        "memory_support": ContextualStrategyMemory(seed=seed, retrieve=True, persist_memory=True, mode="support"),
        "memory_obs": ContextualStrategyMemory(seed=seed, retrieve=True, persist_memory=True, mode="obs"),
        "memory_combined": ContextualStrategyMemory(seed=seed, retrieve=True, persist_memory=True, mode="combined"),
        "memory_combined_noretrieve": ContextualStrategyMemory(
            seed=seed, retrieve=False, persist_memory=True, mode="combined"
        ),
    }


def make_selector_configs(seed: int = 7) -> dict[str, ContextualStrategyMemory]:
    """Combined-descriptor selectors. Persist stays an external baseline."""
    return {
        "memory_combined_ucb": ContextualStrategyMemory(
            seed=seed, retrieve=True, persist_memory=True, mode="combined", selector="ucb"
        ),
        "memory_combined_retrieved": ContextualStrategyMemory(
            seed=seed, retrieve=True, persist_memory=True, mode="combined", selector="retrieved_mean"
        ),
        "memory_combined_gated": ContextualStrategyMemory(
            seed=seed, retrieve=True, persist_memory=True, mode="combined", selector="gated"
        ),
    }
