"""n=3 no-fit micro contracts. Source-only. Does not rewrite v2."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from nexus.evolution2 import nofit_inventory as nofit
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_N3_MICRO.md"
CONFIG = ROOT / "configs" / "evolution2_pendulum_acrobot_protocol_n3_micro.yaml"
ALLOCATION = ROOT / "configs" / "evolution2_pendulum_acrobot_allocation_n3_micro.json"

VERSION = "n3-micro"
DOES_NOT_REWRITE = ("v2", "v2-pilot")
HOLD_NAMED = False
LOCKED_TARGET = None
N_BUNDLES = 3
CI_DF = N_BUNDLES - 1
RECIPE_MATCHED = False
REVEALED_VARIANTS_PER_FAMILY = 6
DEVELOPMENT_CONDITIONS = 2
PRACTICAL_MARGIN = 0.05
BONFERRONI_COMPARISONS = 5
BONFERRONI_T_CRIT_DF2 = 9.924843200918293
EXPLORATORY_T_CRIT_95_DF2 = 4.302652729749464
BOUND_IDS = (
    "pendulum_mlp_u1000_seed0",
    "pendulum_mlp_u1000_seed1",
    "pendulum_mlp_u1000_seed2",
    "acrobot_lookahead_seed0",
    "acrobot_lookahead_seed1",
    "acrobot_lookahead_seed2",
)

LOCKED_CONFIG = "f9dccaa57c92828d23b6f79aafcba5c23c3dee6e063de0f53f9f30882297c0c9"
LOCKED_PROTOCOL = "b214a455dd0e129d1f51bb0eff7efe7acaa66c6076726fbf3e10fc5e29038489"
LOCKED_ALLOCATION = "d54ea64e1f1ffd09a8d523085015f2942ec761d745d32b629931073f43d4241a"


class ContractError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_scientific() -> None:
    raise RuntimeError(
        "n3-micro collection is unauthorized: recipe_matched=false, "
        "authorized=false, holdout unnamed, v2 hashes must stay frozen"
    )


def prior_hashes_frozen() -> bool:
    return (
        v2.file_sha256(v2.CONFIG) == v2.LOCKED_CONFIG
        and v2.file_sha256(v2.PROTOCOL) == v2.LOCKED_PROTOCOL
        and v2.file_sha256(v2.ALLOCATION) == v2.LOCKED_ALLOCATION
        and pilot.file_sha256(pilot.CONFIG) == pilot.LOCKED_CONFIG
        and pilot.file_sha256(pilot.PROTOCOL) == pilot.LOCKED_PROTOCOL
        and pilot.file_sha256(pilot.ALLOCATION) == pilot.LOCKED_ALLOCATION
    )


def bound_files() -> list[dict]:
    by_id = {row["id"]: row for row in nofit.inventory()}
    return [by_id[item] for item in BOUND_IDS]


def student_t_interval(xs: list[float], crit: float) -> tuple[float, float, float]:
    if len(xs) != N_BUNDLES:
        raise ContractError("invalid_replication")
    if abs(float(crit) - BONFERRONI_T_CRIT_DF2) > 1e-12 and abs(
        float(crit) - EXPLORATORY_T_CRIT_95_DF2
    ) > 1e-12:
        raise ContractError("v2_df9_crit_forbidden")
    if any(not math.isfinite(float(x)) for x in xs):
        raise ContractError("invalid_integrity")
    mean = sum(float(x) for x in xs) / N_BUNDLES
    var = sum((float(x) - mean) ** 2 for x in xs) / CI_DF
    se = math.sqrt(var / N_BUNDLES)
    return mean, mean - crit * se, mean + crit * se


def hypothetical_gate(per_control: dict[str, list[float]], analytic_range: float) -> str:
    if set(per_control) != set(v2.PRIMARY_CONTROLS):
        raise ContractError("invalid_integrity")
    if any(len(xs) != N_BUNDLES for xs in per_control.values()):
        raise ContractError("invalid_replication")
    normalized = {
        key: [v2.normalize_delta(x, analytic_range) for x in xs]
        for key, xs in per_control.items()
    }
    passed = True
    for xs in normalized.values():
        mean, lo, _hi = student_t_interval(xs, BONFERRONI_T_CRIT_DF2)
        if mean < PRACTICAL_MARGIN or lo <= 0:
            passed = False
    if passed:
        return "transfer_screen_passed"
    _mean, _lo, reset_hi = student_t_interval(normalized["C"], BONFERRONI_T_CRIT_DF2)
    if reset_hi < 0:
        return "negative_transfer"
    return "inconclusive"


def primary_gate(per_control: dict[str, list[float]], analytic_range: float) -> str:
    if not RECIPE_MATCHED:
        return "not_ready_recipe_mismatch"
    return hypothetical_gate(per_control, analytic_range)


def worksheet() -> dict:
    revealed = (
        N_BUNDLES * REVEALED_VARIANTS_PER_FAMILY * 2 * v2.EPISODE_STEPS
    )
    development = N_BUNDLES * DEVELOPMENT_CONDITIONS * 2 * v2.EPISODE_STEPS
    imagined = (revealed + development) * v2.IMAGINED_CAP_PER_DECISION
    return {
        "version": VERSION,
        "does_not_rewrite": list(DOES_NOT_REWRITE),
        "independent_bundles": N_BUNDLES,
        "df": CI_DF,
        "recipe_matched": RECIPE_MATCHED,
        "bonferroni_comparisons": BONFERRONI_COMPARISONS,
        "bonferroni_t_crit": BONFERRONI_T_CRIT_DF2,
        "practical_margin": PRACTICAL_MARGIN,
        "revealed_training_steps": revealed,
        "development_evaluation_steps": development,
        "first_screen_total_steps": revealed + development,
        "first_screen_imagined_upper_bound": imagined,
        "source_collection_steps": 0,
        "source_fitting_s": 0,
        "authorized_env_cap": 0,
        "authorized_time_cap_s": 0,
        "v2_first_screen_total_steps": v2.worksheet()["first_screen_total_steps"],
        "pilot_first_screen_total_steps": pilot.worksheet()["first_screen_total_steps"],
    }


def public_lock() -> dict:
    return {
        "version": VERSION,
        "does_not_rewrite": list(DOES_NOT_REWRITE),
        "authorized": False,
        "runs": 0,
        "hold_named": HOLD_NAMED,
        "locked_target": LOCKED_TARGET,
        "recipe_matched": RECIPE_MATCHED,
        "n_bundles": N_BUNDLES,
        "df": CI_DF,
        "collection": False,
        "claims_learning_to_learn": False,
        "is_agi": False,
        "status": "not_v2_not_ready",
    }


def allocation_record() -> dict:
    return json.loads(ALLOCATION.read_text())
