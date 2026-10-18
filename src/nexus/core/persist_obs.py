"""Observation-aware persist wrapper. Does not replace AdaptiveProposer.

Adds the 8-d planning-observation sketch through rule/horizon
interactions so start-state can change catalogue rankings. The
historical 6-weight PersistentAdaptive is unchanged.
"""
from __future__ import annotations

from nexus.core.strategy_memory import OBS_SKETCH_DIM, describe_planning_obs
from nexus.evolution1.catalogue import ContractError
from nexus.evolution1.fixtures import PublicFixtureContext
from nexus.evolution1.toy_loop import AdaptiveProposer, TrainingFeedback, VARIANTS, features

INTER_DIM = OBS_SKETCH_DIM * 2
FEATURE_DIM = 6 + INTER_DIM


def persist_obs_features(variant, context: PublicFixtureContext, sketch) -> tuple[float, ...]:
    if type(context) is not PublicFixtureContext:
        raise ContractError("public_training_context_required")
    if sketch is None or len(sketch) != OBS_SKETCH_DIM:
        raise ContractError("planning_observation_required")
    base = features(variant, context)
    successor = base[1]
    horizon = base[3]
    return base + tuple(successor * x for x in sketch) + tuple(horizon * x for x in sketch)


class PersistentAdaptiveObs:
    """Persistent linear SGD with observation-conditioned catalogue features."""

    name = "persistent_adaptive_obs"
    resets = False

    def __init__(self, seed: int = 7):
        if type(seed) is not int or not 0 <= seed <= 10**9:
            raise ContractError("invalid_strategy_seed")
        self.seed = int(seed)
        template = AdaptiveProposer(seed=self.seed)
        self._tie_rank = dict(template._tie_rank)
        self._weights = (0.0,) * FEATURE_DIM
        self._updates = 0
        self._feedback_seen: set[str] = set()
        self._sketch: tuple[float, ...] | None = None
        self._context: PublicFixtureContext | None = None

    def observe_planning_obs(self, obs, context: PublicFixtureContext):
        sketch = describe_planning_obs(obs, context)
        self._sketch = tuple(float(x) for x in sketch)
        self._context = context
        return sketch

    def learned_state(self):
        return {"weights": self._weights, "updates": self._updates, "dim": FEATURE_DIM}

    def memory_state(self):
        return {"weights": FEATURE_DIM, "updates": self._updates, "has_obs": self._sketch is not None}

    def reset_task(self):
        return None

    def eval_clone(self, *, local_updates: bool):
        clone = PersistentAdaptiveObs(seed=self.seed)
        clone._tie_rank = dict(self._tie_rank)
        clone._weights = tuple(self._weights)
        clone._updates = int(self._updates)
        clone._sketch = None if self._sketch is None else tuple(self._sketch)
        clone._context = self._context
        clone._feedback_seen = set()
        clone._allow_local = bool(local_updates)
        return clone

    def _score(self, variant, context):
        x = persist_obs_features(variant, context, self._sketch)
        return sum(w * f for w, f in zip(self._weights, x))

    def choose(self, available, context):
        if type(context) is not PublicFixtureContext:
            raise ContractError("public_training_context_required")
        if self._sketch is None:
            raise ContractError("planning_observation_required")
        return max(available, key=lambda variant: (self._score(variant, context), -self._tie_rank[variant.fingerprint]))

    def update(self, feedback, context):
        if type(feedback) is not TrainingFeedback or type(context) is not PublicFixtureContext:
            raise ContractError("permitted_training_feedback_only")
        if feedback.event_id in self._feedback_seen:
            raise ContractError("replayed_training_feedback")
        if self._sketch is None:
            raise ContractError("planning_observation_required")
        variant = next(item for item in VARIANTS if item.fingerprint == feedback.variant_id)
        x = persist_obs_features(variant, context, self._sketch)
        y = 0.0 if feedback.failed else float(feedback.score)
        error = y - sum(w * f for w, f in zip(self._weights, x))
        scale = 0.5 * error / sum(f * f for f in x)
        self._weights = tuple(w + scale * f for w, f in zip(self._weights, x))
        self._updates += 1
        self._feedback_seen.add(feedback.event_id)

    def update_eval(self, feedback, context):
        if getattr(self, "_allow_local", False):
            self.update(feedback, context)
