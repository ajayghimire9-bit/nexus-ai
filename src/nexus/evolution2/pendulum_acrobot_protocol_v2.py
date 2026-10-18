"""Pendulum/Acrobot catalogue-proposer protocol v2. Source-only. No collection.

Locks Evolution-1 fairness, operators, Bonferroni, bundles, and the
97,600-step worksheet. Does not name a holdout, train, or authorize
collection. v1 remains historical evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from nexus.evolution1.catalogue import (
    HORIZONS,
    Generator,
    Rule,
    Variant,
    plan_bound,
)
from nexus.evolution2.pendulum_acrobot_protocol import (
    FORBIDDEN_FAMILIES,
    FORBIDDEN_HYPOTHESES,
    HOLD_RULE,
    occupied_acrobot,
    occupied_pendulum,
    physics_key,
    require_named_holdout,
)

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_V2.md"
V1_PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL.md"
CONFIG = ROOT / "configs" / "evolution2_pendulum_acrobot_protocol_v2.yaml"
ALLOCATION = ROOT / "configs" / "evolution2_pendulum_acrobot_allocation_v2.json"
READINESS = ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_READINESS.md"

VERSION = "v2"
SUPERSEDES = "v1"
HOLD_NAMED = False
LOCKED_TARGET = None
N_BUNDLES = 10
CI_DF = N_BUNDLES - 1
REPLICATION_UNIT = "independent_search_model_bundle"
N_VARIANTS = 12
PROPOSAL_SLOTS_PER_FAMILY = 6
ANCHOR_SLOTS = 2
SEARCH_SLOTS = PROPOSAL_SLOTS_PER_FAMILY - ANCHOR_SLOTS
EVOLUTION_POPULATION = 4
EVOLUTION_TOURNAMENT = 2
IMAGINED_CAP_PER_DECISION = 1536
EPISODE_STEPS = 200
SOURCE_TRAIN_STEPS = 1024
SOURCE_VAL_STEPS = 256
DEVELOPMENT_CONDITIONS = 6
PRACTICAL_MARGIN = 0.05
BONFERRONI_COMPARISONS = 5
BONFERRONI_T_CRIT_DF9 = 3.24983554401537
EXPLORATORY_T_CRIT_95_DF9 = 2.262
STANDING_TIME_CAP_S = 900
STANDING_ENV_CAP = 100_000
AUTHORIZED_TIME_CAP_S = 0
AUTHORIZED_ENV_CAP = 0
AUTHORIZED_IMAGINED_CAP = 0
SESSION_LEDGER_USED_S = 305.842
SESSION_LEDGER_REMAINING_S = 3294.158
N_ACTIONS = 3

ANCHORS = (
    Variant(Rule.FLAT, Generator.IID, 16),
    Variant(Rule.SUCCESSOR, Generator.IID, 16),
)
METHODS = (
    {"id": "A1", "name": "fixed_flat", "role": "baseline"},
    {"id": "A2", "name": "fixed_successor", "role": "baseline"},
    {"id": "B", "name": "random", "role": "baseline"},
    {"id": "C", "name": "reset", "role": "baseline"},
    {"id": "D", "name": "persist", "role": "treatment"},
    {"id": "E", "name": "evolution", "role": "baseline"},
)
PRIMARY_CONTROLS = ("B", "C", "E", "A1", "A2")
OUTCOMES = (
    "transfer_screen_passed",
    "development_screen_failed",
    "inconclusive",
    "negative_transfer",
    "incomplete_budget",
    "invalid_integrity",
    "invalid_leakage",
)
FAMILY_ORDERS = (
    ("pendulum", "acrobot"),
    ("acrobot", "pendulum"),
)

LOCKED_CONFIG = "34c5b6ac109506487830e55807850f403512c288e128d2b0f8181fa6531ba10f"
LOCKED_PROTOCOL = "234dc3f9b84441b3a2d08ce8ae4a99e294f5e7cc041a155d8d1fb4988a87d91d"
LOCKED_ALLOCATION = "7c8a0e61b21214b11ddcc7ef144a036f8fd1057ce0c649a3c1664375645dd783"


class ContractError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_scientific() -> None:
    raise RuntimeError(
        "Pendulum/Acrobot v2 collection is unauthorized: authorized=false, "
        "runs=0, v1 not ready, CPU enforcement BLOCKED"
    )


def live_named_holdout():
    return LOCKED_TARGET


def occupied_default_is_new_source(family: str, key) -> bool:
    row = physics_key(key)
    if family == "pendulum" and row == (10.0, 1.0, 1.0):
        return True
    if family == "acrobot" and row == (1.0, 1.0, 1.0):
        return True
    return False


def reject_new_instance(family: str, key) -> str | None:
    if family in FORBIDDEN_FAMILIES:
        return "forbidden_family"
    if occupied_default_is_new_source(family, key):
        return "occupied_default_not_a_new_source"
    if family == "pendulum" and physics_key(key) in occupied_pendulum():
        return "occupied_pendulum"
    if family == "acrobot" and physics_key(key) in occupied_acrobot():
        return "occupied_acrobot"
    if family not in {"pendulum", "acrobot"}:
        return "unknown_family"
    return None


def refuse_weight_transfer(source_family: str, target_family: str) -> None:
    if source_family != target_family:
        raise ContractError("cross_family_weight_transfer_forbidden")


def refuse_crossover(*_args, **_kwargs) -> None:
    raise ContractError("crossover_is_illegal")


def mutation_coordinates(parent: Variant, child: Variant) -> tuple[str, ...]:
    changed = []
    if parent.rule is not child.rule:
        changed.append("rule")
    if parent.generator is not child.generator:
        changed.append("generator")
    if parent.horizon != child.horizon:
        changed.append("horizon")
    return tuple(changed)


def assert_legal_mutation(parent: Variant, child: Variant) -> None:
    changed = mutation_coordinates(parent, child)
    if len(changed) != 1:
        raise ContractError("illegal_mutation")


def legal_mutants(parent: Variant) -> tuple[Variant, ...]:
    out = []
    other_rule = Rule.SUCCESSOR if parent.rule is Rule.FLAT else Rule.FLAT
    other_gen = (
        Generator.BALANCED if parent.generator is Generator.IID else Generator.IID
    )
    out.append(Variant(other_rule, parent.generator, parent.horizon))
    out.append(Variant(parent.rule, other_gen, parent.horizon))
    for horizon in HORIZONS:
        if horizon != parent.horizon:
            out.append(Variant(parent.rule, parent.generator, horizon))
    return tuple(out)


def bundle_family_order(bundle_id: int) -> tuple[str, str]:
    if type(bundle_id) is not int or not 0 <= bundle_id < N_BUNDLES:
        raise ContractError("invalid_bundle")
    return FAMILY_ORDERS[bundle_id % 2]


def paired_bundle_seeds(bundle_id: int) -> dict[str, dict[str, int]]:
    if type(bundle_id) is not int or not 0 <= bundle_id < N_BUNDLES:
        raise ContractError("invalid_bundle")
    model = 80_000_000 + bundle_id
    planner = 81_000_000 + bundle_id
    proposal = 82_000_000 + bundle_id
    return {
        row["name"]: {
            "bundle_id": bundle_id,
            "model_seed": model,
            "planner_seed": planner,
            "proposal_seed": proposal,
        }
        for row in METHODS
    }


def normalize_delta(delta: float, analytic_range: float) -> float:
    if type(analytic_range) is not float and type(analytic_range) is not int:
        raise ContractError("undefined_reward_range")
    span = float(analytic_range)
    if not math.isfinite(span) or span <= 0:
        raise ContractError("undefined_reward_range")
    value = float(delta)
    if not math.isfinite(value):
        raise ContractError("invalid_integrity")
    return value / span


def student_t_interval(xs: list[float], crit: float) -> tuple[float, float, float]:
    if len(xs) != N_BUNDLES:
        raise ContractError("invalid_replication")
    if any(not math.isfinite(float(x)) for x in xs):
        raise ContractError("invalid_integrity")
    mean = sum(float(x) for x in xs) / N_BUNDLES
    var = sum((float(x) - mean) ** 2 for x in xs) / CI_DF
    se = math.sqrt(var / N_BUNDLES)
    return mean, mean - crit * se, mean + crit * se


def primary_gate(per_control: dict[str, list[float]], analytic_range: float) -> str:
    if set(per_control) != set(PRIMARY_CONTROLS):
        raise ContractError("invalid_integrity")
    if any(len(xs) != N_BUNDLES for xs in per_control.values()):
        raise ContractError("invalid_integrity")
    normalized = {
        key: [normalize_delta(x, analytic_range) for x in xs]
        for key, xs in per_control.items()
    }
    passed = True
    for xs in normalized.values():
        mean, lo, _hi = student_t_interval(xs, BONFERRONI_T_CRIT_DF9)
        if mean < PRACTICAL_MARGIN or lo <= 0:
            passed = False
    if passed:
        return "transfer_screen_passed"
    _mean, _lo, reset_hi = student_t_interval(normalized["C"], BONFERRONI_T_CRIT_DF9)
    if reset_hi < 0:
        return "negative_transfer"
    return "inconclusive"


def budget_outcome(*, complete: bool, exhausted: bool) -> str | None:
    if exhausted and not complete:
        return "incomplete_budget"
    return None


def worksheet() -> dict[str, int]:
    source = N_BUNDLES * 2 * (SOURCE_TRAIN_STEPS + SOURCE_VAL_STEPS)
    matrix = N_BUNDLES * N_VARIANTS * 2 * EPISODE_STEPS
    development = N_BUNDLES * DEVELOPMENT_CONDITIONS * 2 * EPISODE_STEPS
    imagined = (matrix + development) * IMAGINED_CAP_PER_DECISION
    return {
        "independent_bundles": N_BUNDLES,
        "training_families": 2,
        "variant_count": N_VARIANTS,
        "proposal_slots_per_family": PROPOSAL_SLOTS_PER_FAMILY,
        "source_collection_steps": source,
        "training_matrix_steps": matrix,
        "development_evaluation_steps": development,
        "first_screen_total_steps": source + matrix + development,
        "imagined_cap_per_decision": IMAGINED_CAP_PER_DECISION,
        "first_screen_imagined_upper_bound": imagined,
        "authorized_env_cap": AUTHORIZED_ENV_CAP,
        "authorized_time_cap_s": AUTHORIZED_TIME_CAP_S,
        "standing_env_cap": STANDING_ENV_CAP,
        "standing_time_cap_s": STANDING_TIME_CAP_S,
    }


def worksheet_fits_standing_interactions() -> bool:
    return worksheet()["first_screen_total_steps"] <= STANDING_ENV_CAP


def wall_clock_risk() -> str:
    return "likely_incomplete_budget_under_900s"


def existing_evolution_implements_population_tournament() -> bool:
    return False


def anchors() -> tuple[Variant, Variant]:
    return ANCHORS


def three_action_bound(variant: Variant):
    return plan_bound(variant, N_ACTIONS, IMAGINED_CAP_PER_DECISION)


def allocation_record() -> dict:
    return json.loads(ALLOCATION.read_text())


def public_lock() -> dict:
    return {
        "version": VERSION,
        "supersedes": SUPERSEDES,
        "authorized": False,
        "runs": 0,
        "hold_named": HOLD_NAMED,
        "locked_target": LOCKED_TARGET,
        "hold_rule": HOLD_RULE,
        "n_bundles": N_BUNDLES,
        "replication_unit": REPLICATION_UNIT,
        "methods": [row["name"] for row in METHODS],
        "primary_controls": list(PRIMARY_CONTROLS),
        "outcomes": list(OUTCOMES),
        "practical_margin": PRACTICAL_MARGIN,
        "bonferroni_comparisons": BONFERRONI_COMPARISONS,
        "evolution_population": EVOLUTION_POPULATION,
        "evolution_tournament": EVOLUTION_TOURNAMENT,
        "crossover": False,
        "cross_family_weights": False,
        "authorized_time_cap_s": AUTHORIZED_TIME_CAP_S,
        "authorized_env_cap": AUTHORIZED_ENV_CAP,
        "collection": False,
        "claims_learning_to_learn": False,
        "is_agi": False,
        "forbidden_hypotheses": list(FORBIDDEN_HYPOTHESES),
    }
