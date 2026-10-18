"""Pendulum→Acrobot catalogue-proposer protocol lock. Source-only. No collection.

Locks the cross-family persistence question, methods A–F, occupied
Pendulum/Acrobot exclusion, and a deterministic unused-instance rule
that does not name a holdout. Does not train, construct Gymnasium
environments, import family adapters, or authorize collection.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "configs" / "evolution2_pendulum_acrobot_protocol.yaml"
PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL.md"
ALLOCATION = ROOT / "configs" / "evolution2_pendulum_acrobot_allocation.json"

HOLD_RULE = "e2_pendulum_acrobot_dev_v1"
HOLD_NAMED = False
LOCKED_TARGET = None
N_SEEDS = 10
CI_INTERVAL = "student_t_95"
CI_DF = N_SEEDS - 1
REPLICATION_UNIT = "independent_source_training_seed"
TRAIN_FAMILY = "pendulum"
EVAL_FAMILY = "acrobot"
TRAIN_PHYSICS = (10.0, 1.0, 1.0)
STANDING_TIME_CAP_S = 900
STANDING_ENV_CAP = 100_000
PROPOSED_TIME_CAP_S = 300
PROPOSED_ENV_CAP = 40_000
PROPOSED_IMAGINED_CAP = 0
AUTHORIZED_TIME_CAP_S = 0
AUTHORIZED_ENV_CAP = 0
SESSION_LEDGER_USED_S = 305.842
SESSION_LEDGER_REMAINING_S = 3294.158
FORBIDDEN_FAMILIES = (
    "mountaincar",
    "mountaincar_continuous",
    "cartpole",
)
FORBIDDEN_HYPOTHESES = ("H12", "H13", "H14", "H15", "H16", "H17")
FORBIDDEN_IMPORTS = (
    "gymnasium",
    "nexus.evolution1.adapters",
    "nexus.tasks.spec",
    "nexus.tasks.pendulum_family",
    "nexus.tasks.acrobot_family",
)

# Occupied (g, m, l) from pendulum_family.py. Train source is occupied and
# may be reused only as the Pendulum training instance, never as a new holdout.
OCCUPIED_PENDULUM = (
    (10.0, 1.0, 1.0),
    (8.3, 1.0, 1.0),
    (12.1, 1.0, 1.0),
    (11.5, 1.0, 1.0),
    (6.5, 1.0, 1.0),
    (10.0, 1.8, 1.0),
    (10.0, 1.0, 1.45),
    (9.0, 1.0, 1.0),
    (10.0, 0.55, 1.0),
    (10.0, 1.0, 0.65),
    (13.5, 1.35, 1.25),
    (7.2, 1.0, 1.0),
    (10.0, 0.7, 1.0),
    (10.0, 1.0, 0.8),
    (10.8, 1.2, 1.1),
    (14.0, 1.0, 1.0),
    (10.0, 1.5, 0.9),
    (5.5, 1.0, 1.0),
    (10.0, 2.2, 1.0),
    (10.0, 1.0, 1.7),
    (12.8, 0.4, 1.35),
    (8.0, 1.0, 1.0),
    (10.0, 0.85, 1.0),
    (10.0, 1.0, 1.15),
    (9.4, 1.25, 0.95),
    (11.0, 0.9, 1.05),
    (7.6, 1.1, 1.2),
    (12.4, 0.6, 0.85),
    (10.5, 1.35, 1.3),
    (6.0, 1.0, 1.0),
    (10.0, 2.0, 1.0),
    (10.0, 1.0, 1.55),
    (4.8, 1.0, 1.0),
    (15.2, 1.0, 1.0),
    (10.0, 0.35, 1.0),
    (11.8, 1.6, 0.75),
    (16.4, 1.0, 1.0),
    (10.0, 2.6, 1.0),
    (10.0, 1.0, 0.5),
    (7.0, 1.45, 1.4),
    (7.3, 0.65, 0.78),
    (7.3, 0.65, 1.22),
    (7.3, 1.05, 0.78),
    (7.3, 1.05, 1.22),
    (8.7, 0.65, 0.78),
    (8.7, 0.65, 1.22),
    (8.7, 1.05, 0.78),
    (8.7, 1.05, 1.22),
    (13.2, 0.65, 0.78),
    (13.2, 0.65, 1.22),
    (13.2, 1.05, 0.78),
    (13.2, 1.05, 1.22),
    (5.1, 0.88, 0.96),
    (15.8, 0.92, 1.04),
    (10.4, 2.45, 0.58),
    (11.4, 0.48, 1.82),
    (3.6, 0.42, 1.35),
    (18.5, 1.85, 0.62),
    (9.1, 3.1, 1.05),
    (13.7, 0.22, 1.95),
    (8.2, 0.95, 1.08),
    (11.6, 1.12, 0.92),
    (9.8, 0.58, 1.18),
    (12.7, 1.42, 1.08),
    (17.1, 1.5, 0.8),
    (12.5, 0.65, 0.9),
    (4.2, 3.2, 1.7),
)

# Occupied (LINK_MASS_1, LINK_MASS_2, LINK_LENGTH_1) from acrobot_family.py.
OCCUPIED_ACROBOT = (
    (1.0, 1.0, 1.0),
    (0.95, 1.2, 0.8),
    (1.25, 1.35, 0.95),
    (0.75, 1.4, 1.4),
    (0.75, 0.6, 0.95),
    (1.3, 1.4, 1.4),
    (1.15, 0.85, 0.6),
)

ACROBOT_MASSES = tuple(round(x * 0.05, 2) for x in range(12, 29))
ACROBOT_LENGTHS = tuple(round(x * 0.05, 2) for x in range(12, 29))

METHODS = (
    {
        "id": "A",
        "name": "fixed",
        "role": "baseline",
        "description": (
            "One frozen catalogue architecture. No proposer update. "
            "Evaluate the same index on Acrobot."
        ),
    },
    {
        "id": "B",
        "name": "random",
        "role": "baseline",
        "description": (
            "Independent uniform catalogue draws on Acrobot with the "
            "same evaluation budget. No Pendulum proposer state."
        ),
    },
    {
        "id": "C",
        "name": "reset",
        "role": "baseline",
        "description": (
            "AdaptiveProposer trained on Pendulum, then proposer state "
            "discarded, then the same budget on Acrobot."
        ),
    },
    {
        "id": "D",
        "name": "persist",
        "role": "treatment",
        "description": (
            "AdaptiveProposer trained on Pendulum, proposer state "
            "retained, then the same budget on Acrobot. Weights of "
            "Pendulum networks are not copied."
        ),
    },
    {
        "id": "E",
        "name": "evolution",
        "role": "baseline",
        "description": (
            "Equal-budget catalogue mutation/crossover search started "
            "fresh on Acrobot. Not AdaptiveProposer persistence."
        ),
    },
    {
        "id": "F",
        "name": "retrieval",
        "role": "baseline",
        "description": (
            "Guarded memory of Pendulum artefacts. Family-incompatible "
            "weight transfer must fail closed. Retrieved proposer "
            "hyperparameters may be used; network weights may not."
        ),
    },
)

PRIMARY = {
    "estimand": "persist_minus_reset",
    "treatment": "D",
    "baseline": "C",
    "metric": "acrobot_mean_return",
    "n": N_SEEDS,
    "interval": CI_INTERVAL,
    "df": CI_DF,
    "replication_unit": REPLICATION_UNIT,
    "established_if": "student_t_95_interval_entirely_above_zero",
    "label_pass": "persist_beats_reset_established",
    "label_fail": "persist_beats_reset_not_established",
    "label_blocked": "persist_beats_reset_blocked",
    "not_learning_to_learn": True,
    "not_agi": True,
}

SECONDARY = (
    {"estimand": "persist_minus_random", "treatment": "D", "baseline": "B"},
    {"estimand": "persist_minus_evolution", "treatment": "D", "baseline": "E"},
    {"estimand": "persist_minus_retrieval", "treatment": "D", "baseline": "F"},
    {"estimand": "persist_minus_fixed", "treatment": "D", "baseline": "A"},
)

LOCKED_CONFIG = "e16be93ece31c0959f5d9d8c1f25f41a188e6be72dacf7b089e88d38c327afa2"
LOCKED_PROTOCOL = "c97f307b080daa1e8a4dfacfc9f3172ab8701f8203323ecc8245c026666c3ab2"
LOCKED_ALLOCATION = "f5c27ce875b31d542df3e5b09afeee3dbfd57be7ae9799fffac8c95dc6227ff6"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physics_key(values) -> tuple[float, float, float]:
    a, b, c = values
    return (round(float(a), 4), round(float(b), 4), round(float(c), 4))


def occupied_pendulum() -> frozenset[tuple[float, float, float]]:
    return frozenset(physics_key(row) for row in OCCUPIED_PENDULUM)


def occupied_acrobot() -> frozenset[tuple[float, float, float]]:
    return frozenset(physics_key(row) for row in OCCUPIED_ACROBOT)


def acrobot_grid() -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (m1, m2, length)
        for m1 in ACROBOT_MASSES
        for m2 in ACROBOT_MASSES
        for length in ACROBOT_LENGTHS
    )


def family_allowed(family: str) -> bool:
    return family in {TRAIN_FAMILY, EVAL_FAMILY} and family not in FORBIDDEN_FAMILIES


def reject_reason(family: str, key: tuple[float, float, float]) -> str | None:
    if family in FORBIDDEN_FAMILIES:
        return "forbidden_family"
    if family == "pendulum" and physics_key(key) in occupied_pendulum():
        if physics_key(key) == TRAIN_PHYSICS:
            return "occupied_train_source_not_a_holdout"
        return "occupied_pendulum"
    if family == "acrobot" and physics_key(key) in occupied_acrobot():
        return "occupied_acrobot"
    if family not in {TRAIN_FAMILY, EVAL_FAMILY}:
        return "unknown_family"
    return None


def unused_instance_from_rule(
    *,
    occupied: frozenset[tuple[float, float, float]],
    grid: tuple[tuple[float, float, float], ...],
    rule: str = HOLD_RULE,
    counter: int = 0,
) -> tuple[float, float, float]:
    """Deterministic unused-instance rule. Tests may pass a fake occupied set.

    The live protocol does not persist the accepted key as a named holdout.
    """
    if counter < 0:
        raise ValueError("counter must be >= 0")
    if not grid:
        raise ValueError("grid is empty")
    digest_bytes = hashlib.sha256(f"{rule}:{counter}".encode()).digest()
    idx = int.from_bytes(digest_bytes[:8], "big")
    n = len(grid)
    for offset in range(n):
        candidate = physics_key(grid[(idx + offset) % n])
        if candidate not in occupied:
            return candidate
    raise RuntimeError("no unused instance remains on the locked grid")


def live_named_holdout():
    return LOCKED_TARGET


def require_named_holdout() -> None:
    raise RuntimeError(
        "holdout remains unnamed; naming an unused Acrobot instance "
        "requires a later independent review"
    )


def require_scientific() -> None:
    raise RuntimeError(
        "Pendulum→Acrobot collection is unauthorized: authorized=false, "
        "runs=0, adapters blocked, H17 blocked"
    )


def allocation_record() -> dict:
    return json.loads(ALLOCATION.read_text())


def public_lock() -> dict:
    return {
        "authorized": False,
        "runs": 0,
        "consumed": False,
        "closed": False,
        "hold_named": HOLD_NAMED,
        "locked_target": LOCKED_TARGET,
        "hold_rule": HOLD_RULE,
        "train_family": TRAIN_FAMILY,
        "eval_family": EVAL_FAMILY,
        "train_physics": list(TRAIN_PHYSICS),
        "n_seeds": N_SEEDS,
        "methods": [row["name"] for row in METHODS],
        "primary": PRIMARY["estimand"],
        "label_blocked": PRIMARY["label_blocked"],
        "proposed_time_cap_s": PROPOSED_TIME_CAP_S,
        "proposed_env_cap": PROPOSED_ENV_CAP,
        "authorized_time_cap_s": AUTHORIZED_TIME_CAP_S,
        "authorized_env_cap": AUTHORIZED_ENV_CAP,
        "standing_time_cap_s": STANDING_TIME_CAP_S,
        "standing_env_cap": STANDING_ENV_CAP,
        "session_ledger_used_s": SESSION_LEDGER_USED_S,
        "session_ledger_remaining_s": SESSION_LEDGER_REMAINING_S,
        "forbidden_families": list(FORBIDDEN_FAMILIES),
        "forbidden_hypotheses": list(FORBIDDEN_HYPOTHESES),
        "claims_learning_to_learn": False,
        "is_agi": False,
        "cross_family_weights": False,
        "collection": False,
    }
