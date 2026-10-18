"""Refuse-only scientific persist-versus-reset runner.

Defines the later-authorized stages without enabling them. Does not import
Gymnasium, collect transitions, fit models, or name a holdout.
"""
from __future__ import annotations

from nexus.evolution2 import persist_reset_readiness as ready
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2


def require_refusal(stage: str) -> None:
    raise RuntimeError(f"{stage}_blocked_until_independent_authorization")


def bundle_schedule(n_bundles: int = 3) -> tuple[dict, ...]:
    if int(n_bundles) != 3:
        raise RuntimeError("n10_not_this_request")
    return tuple(
        {
            "bundle_id": bundle_id,
            "family_order": list(v2.bundle_family_order(bundle_id)),
            "seeds": v2.paired_bundle_seeds(bundle_id),
        }
        for bundle_id in range(int(n_bundles))
    )


def collect_fresh_source(*_args, **_kwargs) -> None:
    require_refusal("fresh_source_collection")


def fit_source_models(*_args, **_kwargs) -> None:
    require_refusal("new_physics_source_fitting")


def reveal_training_feedback(*_args, **_kwargs) -> None:
    require_refusal("revealed_training_feedback")


def hidden_development_evaluation(*_args, **_kwargs) -> None:
    require_refusal("hidden_development_evaluation")


def run_scientific(*_args, **_kwargs) -> None:
    require_refusal("scientific_persist_versus_reset")


def dispatch(env_cap: int) -> None:
    """Scientific entry. Holdout gate first; then 17280-step freshness; then refuse."""
    lock.require_named_holdout()
    ready.require_scientific_prerequisites(int(env_cap))
    run_scientific(env_cap)
