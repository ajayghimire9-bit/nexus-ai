"""Independent unused-instance naming review. Source-only. Does not name a holdout."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from nexus.evolution2 import pendulum_acrobot_protocol as v1
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_HOLDOUT_REVIEW.md"
PENDULUM_FAMILY = ROOT / "src" / "nexus" / "tasks" / "pendulum_family.py"
ACROBOT_FAMILY = ROOT / "src" / "nexus" / "tasks" / "acrobot_family.py"
ARTIFACT = ROOT / "artifacts" / "evolution2_pendulum_acrobot_holdout_review.json"

VERDICT = "NAMING_BLOCKED"
HOLD_NAMED = False
LOCKED_TARGET = None
HOLD_RULE = v1.HOLD_RULE
REQUIRED_ROLES = (
    "pendulum_source",
    "pendulum_development",
    "acrobot_source",
    "acrobot_development",
)
ACROBOT_UNUSED_EXISTS = True
ACROBOT_UNUSED_SHA256 = "f63b54f2ed140915b4ac8b3fd924bc7ae0c5c754496e417784603a206ea72f19"
GRAVITY_AXIS_LITERAL = (7.3, 8.7, 13.2)
IMPLIED_PENDULUM = (
    (10.0, 1.0, 1.0),
    (8.3, 1.0, 1.0),
    (12.1, 1.0, 1.0),
    (11.5, 1.0, 1.0),
)
LATENT_GRAVITIES = (7.3, 8.7, 13.2)
LATENT_MASSES = (0.65, 1.05)
LATENT_LENGTHS = (0.78, 1.22)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_named_holdout() -> None:
    v1.require_named_holdout()


def live_named_holdout():
    return None


def _triples(text: str) -> set[tuple[float, float, float]]:
    found: set[tuple[float, float, float]] = set()
    for match in re.finditer(
        r"\(\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\)",
        text,
    ):
        key = v1.physics_key(tuple(float(part) for part in match.groups()))
        if key != v1.physics_key(GRAVITY_AXIS_LITERAL):
            found.add(key)
    return found


def _gml_calls(text: str) -> set[tuple[float, float, float]]:
    found: set[tuple[float, float, float]] = set()
    for match in re.finditer(
        r"g\s*=\s*(-?\d+\.\d+)\s*,\s*m\s*=\s*(-?\d+\.\d+)\s*,\s*l\s*=\s*(-?\d+\.\d+)",
        text,
    ):
        found.add(v1.physics_key(tuple(float(part) for part in match.groups())))
    return found


def family_declared_pendulum() -> frozenset[tuple[float, float, float]]:
    text = PENDULUM_FAMILY.read_text()
    keys = _triples(text) | _gml_calls(text)
    keys.update(v1.physics_key(row) for row in IMPLIED_PENDULUM)
    keys.update(
        v1.physics_key((g, mass, length))
        for g in LATENT_GRAVITIES
        for mass in LATENT_MASSES
        for length in LATENT_LENGTHS
    )
    return frozenset(keys)


def family_declared_acrobot() -> frozenset[tuple[float, float, float]]:
    keys = _triples(ACROBOT_FAMILY.read_text())
    keys.add(v1.physics_key((1.0, 1.0, 1.0)))
    return frozenset(keys)


def occupied_covers_family_literals() -> bool:
    return family_declared_pendulum() <= v1.occupied_pendulum() and (
        family_declared_acrobot() <= v1.occupied_acrobot()
    )


def pendulum_unused_rule_exists() -> bool:
    return hasattr(v1, "pendulum_grid") or hasattr(v2, "pendulum_grid")


def acrobot_unused_digest() -> str:
    key = v1.unused_instance_from_rule(
        occupied=v1.occupied_acrobot(),
        grid=v1.acrobot_grid(),
        rule=HOLD_RULE,
        counter=0,
    )
    return v1.digest(key)


def blockers() -> tuple[str, ...]:
    return (
        "pendulum_unused_instance_rule_missing",
        "one_acrobot_key_cannot_fill_four_roles",
        "source_and_development_must_be_disjoint",
        "collection_unauthorized_even_if_named",
    )


def public_review() -> dict:
    return {
        "verdict": VERDICT,
        "authorized": False,
        "hold_named": HOLD_NAMED,
        "locked_target": LOCKED_TARGET,
        "hold_rule": HOLD_RULE,
        "required_roles": list(REQUIRED_ROLES),
        "occupied_covers_family_literals": occupied_covers_family_literals(),
        "pendulum_unused_rule_exists": pendulum_unused_rule_exists(),
        "acrobot_unused_exists": ACROBOT_UNUSED_EXISTS,
        "acrobot_unused_sha256": ACROBOT_UNUSED_SHA256,
        "blockers": list(blockers()),
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
        "collection": False,
        "claims_learning_to_learn": False,
        "is_agi": False,
    }


def artifact_record() -> dict:
    return json.loads(ARTIFACT.read_text())
