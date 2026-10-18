"""Four-role unused-instance rules. Source-only. Does not persist tuples or collect."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution2 import pendulum_acrobot_holdout_review as review
from nexus.evolution2 import pendulum_acrobot_protocol as v1
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_INSTANCE_RULES.md"
ARTIFACT = ROOT / "artifacts" / "evolution2_pendulum_acrobot_instance_rules.json"

VERSION = "instance-rules-v1"
HOLD_NAMED = False
LOCKED_TARGET = None
PENDULUM_RULE = "e2_pendulum_acrobot_pendulum_v1"
ACROBOT_RULE = v1.HOLD_RULE
ROLE_ORDER = (
    "acrobot_development",
    "acrobot_source",
    "pendulum_source",
    "pendulum_development",
)
PENDULUM_G = tuple(round(x * 0.5, 2) for x in range(10, 31))
PENDULUM_M = tuple(round(x * 0.05, 2) for x in range(12, 29))
PENDULUM_L = PENDULUM_M
ROLE_DIGESTS = {
    "acrobot_development": review.ACROBOT_UNUSED_SHA256,
    "acrobot_source": "e07be56987f4382bdd5087f34c3aa7ae86c79251f6cbebbdfd6f76d55b3402d3",
    "pendulum_source": "31b0989af2faa99e865b48d7a2d11a71a077df37367ae2891e31ff38a5a26ad0",
    "pendulum_development": "a9bd9aedf2a4f1e1bf0bdb3564d83ea789ccb15a1bc0d1dcf3873797aa7762c3",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pendulum_grid() -> tuple[tuple[float, float, float], ...]:
    return tuple((g, mass, length) for g in PENDULUM_G for mass in PENDULUM_M for length in PENDULUM_L)


def require_named_holdout() -> None:
    v1.require_named_holdout()


def live_named_holdout():
    return None


def _draw(role: str, occupied: frozenset, grid, rule: str, counter: int):
    key = v1.physics_key(
        v1.unused_instance_from_rule(
            occupied=occupied,
            grid=grid,
            rule=rule,
            counter=counter,
        )
    )
    if key in occupied:
        raise RuntimeError(f"{role}_landed_on_occupied")
    if role.startswith("pendulum") and key == (10.0, 1.0, 1.0):
        raise RuntimeError("pendulum_default_not_a_new_source")
    if role.startswith("acrobot") and key == (1.0, 1.0, 1.0):
        raise RuntimeError("acrobot_default_not_a_new_source")
    return key


def assign_roles() -> dict[str, tuple[float, float, float]]:
    acrobot_dev = _draw(
        "acrobot_development",
        v1.occupied_acrobot(),
        v1.acrobot_grid(),
        ACROBOT_RULE,
        0,
    )
    acrobot_src = _draw(
        "acrobot_source",
        v1.occupied_acrobot() | {acrobot_dev},
        v1.acrobot_grid(),
        ACROBOT_RULE,
        1,
    )
    pendulum_src = _draw(
        "pendulum_source",
        v1.occupied_pendulum(),
        pendulum_grid(),
        PENDULUM_RULE,
        0,
    )
    pendulum_dev = _draw(
        "pendulum_development",
        v1.occupied_pendulum() | {pendulum_src},
        pendulum_grid(),
        PENDULUM_RULE,
        1,
    )
    assigned = {
        "acrobot_development": acrobot_dev,
        "acrobot_source": acrobot_src,
        "pendulum_source": pendulum_src,
        "pendulum_development": pendulum_dev,
    }
    if len(set(assigned.values())) != 4:
        raise RuntimeError("role_collision")
    return assigned


def role_digests() -> dict[str, str]:
    return {role: v1.digest(key) for role, key in assign_roles().items()}


def public_lock() -> dict:
    return {
        "version": VERSION,
        "verdict": "FOUR_ROLE_RULES_LOCKED_UNNAMED",
        "authorized": False,
        "hold_named": HOLD_NAMED,
        "locked_target": LOCKED_TARGET,
        "pendulum_rule": PENDULUM_RULE,
        "acrobot_rule": ACROBOT_RULE,
        "role_order": list(ROLE_ORDER),
        "role_digests": dict(ROLE_DIGESTS),
        "pendulum_grid_size": len(pendulum_grid()),
        "collection": False,
        "claims_learning_to_learn": False,
        "is_agi": False,
        "v1_hashes_frozen": (
            v1.file_sha256(v1.CONFIG) == v1.LOCKED_CONFIG
            and v1.file_sha256(v1.PROTOCOL) == v1.LOCKED_PROTOCOL
            and v1.file_sha256(v1.ALLOCATION) == v1.LOCKED_ALLOCATION
        ),
        "v2_hashes_frozen": (
            v2.file_sha256(v2.CONFIG) == v2.LOCKED_CONFIG
            and v2.file_sha256(v2.PROTOCOL) == v2.LOCKED_PROTOCOL
            and v2.file_sha256(v2.ALLOCATION) == v2.LOCKED_ALLOCATION
        ),
        "pilot_hashes_frozen": (
            pilot.file_sha256(pilot.CONFIG) == pilot.LOCKED_CONFIG
            and pilot.file_sha256(pilot.PROTOCOL) == pilot.LOCKED_PROTOCOL
            and pilot.file_sha256(pilot.ALLOCATION) == pilot.LOCKED_ALLOCATION
        ),
    }


def artifact_record() -> dict:
    return json.loads(ARTIFACT.read_text())
