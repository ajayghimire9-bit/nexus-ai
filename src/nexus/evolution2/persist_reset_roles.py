"""Independent four-role assignment verification. No new selection.

Recomputes the locked unused-instance rule and checks SHA256 digests
against ROLE_DIGESTS plus historical occupied/H17 exclusion lists.
Does not name a live holdout or persist a new target.
"""
from __future__ import annotations

import json
from pathlib import Path

from nexus.evolution2 import pendulum_acrobot_holdout_review as review
from nexus.evolution2 import pendulum_acrobot_instance_rules as rules
from nexus.evolution2 import pendulum_acrobot_protocol as v1
from nexus.evolution2 import persist_reset_request as lock

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_roles.json"
H16 = ROOT / "artifacts" / "research_session_h16_same_state_library_usage.json"
H16_SHA = "ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117"
H17_REGISTRY = ROOT / "artifacts" / "h17_exclusion_registry_audit_validated.json"


def independent_assign() -> dict[str, tuple[float, float, float]]:
    acrobot_dev = v1.physics_key(
        v1.unused_instance_from_rule(
            occupied=v1.occupied_acrobot(),
            grid=v1.acrobot_grid(),
            rule=v1.HOLD_RULE,
            counter=0,
        )
    )
    acrobot_src = v1.physics_key(
        v1.unused_instance_from_rule(
            occupied=v1.occupied_acrobot() | {acrobot_dev},
            grid=v1.acrobot_grid(),
            rule=v1.HOLD_RULE,
            counter=1,
        )
    )
    pendulum_src = v1.physics_key(
        v1.unused_instance_from_rule(
            occupied=v1.occupied_pendulum(),
            grid=rules.pendulum_grid(),
            rule=rules.PENDULUM_RULE,
            counter=0,
        )
    )
    pendulum_dev = v1.physics_key(
        v1.unused_instance_from_rule(
            occupied=v1.occupied_pendulum() | {pendulum_src},
            grid=rules.pendulum_grid(),
            rule=rules.PENDULUM_RULE,
            counter=1,
        )
    )
    assigned = {
        "acrobot_development": acrobot_dev,
        "acrobot_source": acrobot_src,
        "pendulum_source": pendulum_src,
        "pendulum_development": pendulum_dev,
    }
    if tuple(assigned) != rules.ROLE_ORDER:
        raise RuntimeError("role_order_mismatch")
    if len(set(assigned.values())) != 4:
        raise RuntimeError("role_collision")
    return assigned


def digest_roles(assigned: dict[str, tuple[float, float, float]]) -> dict[str, str]:
    return {role: v1.digest(key) for role, key in assigned.items()}


def validate_named_roles(named: dict[str, str | tuple]) -> dict:
    assigned = independent_assign()
    locked = dict(rules.ROLE_DIGESTS)
    computed = digest_roles(assigned)
    if computed != locked:
        raise RuntimeError("locked_role_digest_mismatch")
    matched = {}
    for role in rules.ROLE_ORDER:
        if role not in named:
            return {"valid": False, "reason": f"missing_{role}", "matched": matched}
        value = named[role]
        if isinstance(value, str) and len(value) == 64:
            digest = value
        else:
            digest = v1.digest(v1.physics_key(value))
        if digest != locked[role]:
            return {"valid": False, "reason": f"digest_mismatch_{role}", "matched": matched}
        matched[role] = digest
    return {"valid": True, "reason": None, "matched": matched, "locked": locked}


def historical_exclusions(assigned: dict[str, tuple[float, float, float]]) -> dict:
    pend_occ = v1.occupied_pendulum()
    acr_occ = v1.occupied_acrobot()
    declared_p = review.family_declared_pendulum()
    declared_a = review.family_declared_acrobot()
    rows = {}
    for role, key in assigned.items():
        family = "pendulum" if role.startswith("pendulum") else "acrobot"
        occupied = pend_occ if family == "pendulum" else acr_occ
        declared = declared_p if family == "pendulum" else declared_a
        default = (10.0, 1.0, 1.0) if family == "pendulum" else (1.0, 1.0, 1.0)
        rows[role] = {
            "key": list(key),
            "digest": v1.digest(key),
            "in_occupied": key in occupied,
            "in_family_declared": key in declared,
            "is_occupied_default": key == default,
            "forbidden_family": family in v1.FORBIDDEN_FAMILIES,
        }
    h17 = json.loads(H17_REGISTRY.read_text())
    return {
        "roles": rows,
        "any_historical_hit": any(
            row["in_occupied"] or row["in_family_declared"] or row["is_occupied_default"]
            for row in rows.values()
        ),
        "h17": "blocked",
        "h17_target_selected": bool(h17.get("target_selected")),
        "h17_locked": bool(h17.get("locked")),
        "forbidden_hypotheses": list(v1.FORBIDDEN_HYPOTHESES),
    }


def verify_four_roles() -> dict:
    assigned = independent_assign()
    locked = dict(rules.ROLE_DIGESTS)
    computed = digest_roles(assigned)
    official = digest_roles(rules.assign_roles())
    exclusions = historical_exclusions(assigned)
    matches = computed == locked == official
    clean = exclusions["any_historical_hit"] is False
    if (
        "H17" not in v1.FORBIDDEN_HYPOTHESES
        or exclusions["h17"] != "blocked"
        or exclusions["h17_target_selected"]
        or exclusions["h17_locked"]
    ):
        raise RuntimeError("h17_must_remain_blocked")
    if lock.file_sha256(H16) != H16_SHA:
        raise RuntimeError("h16_scientific_ledger_mutated")
    status = "PASS" if matches and clean else "FAIL"
    return {
        "status": status,
        "hold_named": False,
        "locked_target": None,
        "scientific": False,
        "new_selection": False,
        "assignments": {role: list(key) for role, key in assigned.items()},
        "digests": computed,
        "locked_digests": locked,
        "official_rule_digests": official,
        "digests_match_locked": matches,
        "exclusions": exclusions,
        "historical_exclusion_clean": clean,
        "h17": "blocked",
        "cited_config_sha256": lock.LOCKED_CONFIG,
    }


def write_artifact() -> dict:
    payload = verify_four_roles()
    payload.update(
        {
            "collection": False,
            "scientific_ledger_preserved": [305.842, 3294.158],
            "claims_learning_to_learn": False,
            "is_agi": False,
        }
    )
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
