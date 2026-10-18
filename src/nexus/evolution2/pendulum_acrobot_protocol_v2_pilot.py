"""v2-pilot resource worksheet. Source-only. Does not rewrite v2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_V2_PILOT.md"
CONFIG = ROOT / "configs" / "evolution2_pendulum_acrobot_protocol_v2_pilot.yaml"
ALLOCATION = ROOT / "configs" / "evolution2_pendulum_acrobot_allocation_v2_pilot.json"

VERSION = "v2-pilot"
DOES_NOT_REWRITE = "v2"
HOLD_NAMED = False
LOCKED_TARGET = None
REVEALED_VARIANTS_PER_FAMILY = 6
DEVELOPMENT_CONDITIONS = 2
HISTORICAL_SECONDS_PER_IMAGINED = 68.146 / 12_324_000

LOCKED_CONFIG = "b4336407e7b7735c02e673c9dbf08e164f636a0b7ad13d4925833a3ef0d471df"
LOCKED_PROTOCOL = "15faf55decc97216fc0c5372b9c50a673c75d28cf3e0d306a5887c7aba38b48f"
LOCKED_ALLOCATION = "d6951cb72a1d8b08f41c4e61842bede24bad51245f2b964ffef2baaa86011137"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_scientific() -> None:
    raise RuntimeError(
        "v2-pilot collection is unauthorized: authorized=false, runs=0, "
        "holdout unnamed, v2 hashes must stay frozen"
    )


def v2_hashes_frozen() -> bool:
    return (
        v2.file_sha256(v2.CONFIG) == v2.LOCKED_CONFIG
        and v2.file_sha256(v2.PROTOCOL) == v2.LOCKED_PROTOCOL
        and v2.file_sha256(v2.ALLOCATION) == v2.LOCKED_ALLOCATION
    )


def worksheet() -> dict:
    source = v2.N_BUNDLES * 2 * (v2.SOURCE_TRAIN_STEPS + v2.SOURCE_VAL_STEPS)
    revealed = v2.N_BUNDLES * REVEALED_VARIANTS_PER_FAMILY * 2 * v2.EPISODE_STEPS
    development = v2.N_BUNDLES * DEVELOPMENT_CONDITIONS * 2 * v2.EPISODE_STEPS
    imagined = (revealed + development) * v2.IMAGINED_CAP_PER_DECISION
    return {
        "version": VERSION,
        "does_not_rewrite": DOES_NOT_REWRITE,
        "independent_bundles": v2.N_BUNDLES,
        "bonferroni_comparisons": v2.BONFERRONI_COMPARISONS,
        "practical_margin": v2.PRACTICAL_MARGIN,
        "revealed_variants_per_family": REVEALED_VARIANTS_PER_FAMILY,
        "development_conditions": DEVELOPMENT_CONDITIONS,
        "source_collection_steps": source,
        "revealed_training_steps": revealed,
        "development_evaluation_steps": development,
        "first_screen_total_steps": source + revealed + development,
        "imagined_cap_per_decision": v2.IMAGINED_CAP_PER_DECISION,
        "first_screen_imagined_upper_bound": imagined,
        "historical_planning_s": imagined * HISTORICAL_SECONDS_PER_IMAGINED,
        "authorized_env_cap": 0,
        "authorized_time_cap_s": 0,
        "standing_env_cap": v2.STANDING_ENV_CAP,
        "standing_time_cap_s": v2.STANDING_TIME_CAP_S,
        "v2_first_screen_total_steps": v2.worksheet()["first_screen_total_steps"],
        "v2_first_screen_imagined_upper_bound": v2.worksheet()[
            "first_screen_imagined_upper_bound"
        ],
    }


def wall_clock_risk() -> str:
    return "more_plausible_than_v2_still_unproven"


def public_lock() -> dict:
    return {
        "version": VERSION,
        "does_not_rewrite": DOES_NOT_REWRITE,
        "authorized": False,
        "runs": 0,
        "hold_named": HOLD_NAMED,
        "locked_target": LOCKED_TARGET,
        "n_bundles": v2.N_BUNDLES,
        "primary_controls": list(v2.PRIMARY_CONTROLS),
        "collection": False,
        "claims_learning_to_learn": False,
        "is_agi": False,
    }


def allocation_record() -> dict:
    return json.loads(ALLOCATION.read_text())


class TrustedEvaluator:
    """Evaluator-owned scores. Methods cannot supply or overwrite values."""

    def __init__(self, allowed, *, family: str, bundle_id: int, produce_score):
        self.allowed = frozenset(allowed)
        self.family = family
        self.bundle_id = int(bundle_id)
        self._produce = produce_score
        self._training: dict = {}
        self._development: dict = {}
        self.physical = 0
        self.cached = 0
        self.charged = 0
        self.exposed: dict[str, list] = {row["name"]: [] for row in v2.METHODS}

    def evaluate(self, method: str, variant, *, family: str | None = None, bundle_id: int | None = None) -> float:
        if family is not None and family != self.family:
            raise RuntimeError("cross_family_contamination")
        if bundle_id is not None and int(bundle_id) != self.bundle_id:
            raise RuntimeError("cross_bundle_contamination")
        if variant not in self.allowed:
            raise RuntimeError("unused_variant_not_revealed")
        if variant in self._development:
            raise RuntimeError("hidden_development_outcome")
        self.charged += 1
        if variant in self._training:
            self.cached += 1
            score = self._training[variant]
        else:
            self.physical += 1
            score = float(self._produce(variant))
            self._training[variant] = score
        self.exposed.setdefault(method, []).append(variant)
        return score

    def reveal(self, method: str, variant, score=None):
        if score is not None:
            raise RuntimeError("score_substitution_forbidden")
        return self.evaluate(method, variant)

    def hide_development(self, variant, score: float) -> None:
        self._development[variant] = float(score)

    def training_feedback(self, method: str) -> dict:
        return {
            variant: self._training[variant]
            for variant in self.exposed.get(method, [])
            if variant in self._training
        }


def equal_information_cache(revealed, *, family="pendulum", bundle_id=0, produce_score=None):
    scores = {variant: float(i + 1) for i, variant in enumerate(revealed)}

    def _produce(variant):
        return scores[variant]

    shared = TrustedEvaluator(
        revealed,
        family=family,
        bundle_id=bundle_id,
        produce_score=produce_score or _produce,
    )
    return {row["name"]: shared for row in v2.METHODS}


def charge_imagined(decisions: int) -> int:
    return int(decisions) * v2.IMAGINED_CAP_PER_DECISION
