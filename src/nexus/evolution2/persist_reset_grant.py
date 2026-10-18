"""One-run persist-versus-reset science grant. Does not rewrite frozen hashes."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from nexus.evolution2 import persist_reset_approval as gate
from nexus.evolution2 import persist_reset_budget as budget
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_roles as roles
from nexus.evolution2.pendulum_acrobot_instance_rules import ROLE_DIGESTS, ROLE_ORDER
from nexus.evolution2.pendulum_acrobot_protocol import FORBIDDEN_HYPOTHESES, digest, physics_key

ROOT = Path(__file__).resolve().parents[3]
GRANT = ROOT / "configs" / "evolution2_persist_reset_science_grant.json"
H16 = roles.H16
H16_SHA = roles.H16_SHA
REQUIRED_COMMIT = "170dec7bcab2aa2074d46357315f033c8f7127dc"
REQUIRED_ENV_CAP = 17_280
REQUIRED_TIME_CAP_S = 900
HUMAN_APPROVAL = """I explicitly approve ONE bounded Evolution-2 n=3 persist-versus-reset scientific experiment.
Config SHA256: 8e90b74ad3f406509051025160799c13d9a28bbb7e16c11a77808653bb43827e
env_cap=17280
time_cap_s=900
acrobot_development=(0.8, 0.7, 1.15)
acrobot_source=(0.85, 1.3, 0.85)
pendulum_source=(7.5, 1.35, 1.4)
pendulum_development=(12.5, 1.15, 0.65)
"""
APPROVED_ROLES = {
    "acrobot_development": (0.8, 0.7, 1.15),
    "acrobot_source": (0.85, 1.3, 0.85),
    "pendulum_source": (7.5, 1.35, 1.4),
    "pendulum_development": (12.5, 1.15, 0.65),
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_commit() -> str:
    out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
    return out.decode().strip()


def verify_roles(named: dict | None = None) -> dict:
    report = roles.verify_four_roles()
    if report["status"] != "PASS":
        raise RuntimeError("four_role_integrity_failed")
    assigned = roles.independent_assign()
    for role in ROLE_ORDER:
        if physics_key(assigned[role]) != physics_key(APPROVED_ROLES[role]):
            raise RuntimeError(f"approved_role_mismatch_{role}")
        if digest(assigned[role]) != ROLE_DIGESTS[role]:
            raise RuntimeError(f"approved_digest_mismatch_{role}")
        if named is not None and role in named:
            value = named[role]
            got = value if isinstance(value, str) and len(value) == 64 else digest(physics_key(value))
            if got != ROLE_DIGESTS[role]:
                raise RuntimeError(f"named_digest_mismatch_{role}")
    if report["historical_exclusion_clean"] is not True:
        raise RuntimeError("historical_exclusion_hit")
    if "H17" not in FORBIDDEN_HYPOTHESES:
        raise RuntimeError("h17_must_remain_blocked")
    return report


def verify_frozen_hashes() -> dict:
    checks = {
        "config": file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG,
        "protocol": file_sha256(lock.PROTOCOL) == lock.LOCKED_PROTOCOL,
        "allocation": file_sha256(lock.ALLOCATION) == lock.LOCKED_ALLOCATION,
        "h16": file_sha256(H16) == H16_SHA,
        "cited_config": lock.LOCKED_CONFIG
        == "8e90b74ad3f406509051025160799c13d9a28bbb7e16c11a77808653bb43827e",
    }
    if not all(checks.values()):
        raise RuntimeError("frozen_hash_integrity_failed:" + ",".join(k for k, ok in checks.items() if not ok))
    return checks


def verify_approval(text: str) -> dict:
    parsed = gate.parse_approval(text)
    if parsed["status"] != "COMPLETE_TEXT_ONLY" or not parsed["four_role_valid"]:
        raise RuntimeError("persist_versus_reset_approval_insufficient:" + ",".join(parsed["missing"]))
    if parsed["env_cap"] != REQUIRED_ENV_CAP:
        raise RuntimeError("env_cap_must_be_17280")
    if parsed["occupied_default_named"]:
        raise RuntimeError("occupied_default_is_not_a_holdout")
    verify_roles(gate.extract_named_roles(text))
    return parsed


def integrity_preflight(approval_text: str) -> dict:
    commit = source_commit()
    hashes = verify_frozen_hashes()
    parsed = verify_approval(approval_text)
    role_report = verify_roles(gate.extract_named_roles(approval_text))
    record = lock.allocation_record()
    if record.get("authorized") is True or int(record.get("env_cap") or 0) != 0:
        raise RuntimeError("frozen_allocation_must_stay_unauthorized")
    if budget.FRESH_TOTAL_STEPS != REQUIRED_ENV_CAP:
        raise RuntimeError("fresh_budget_rewritten")
    return {
        "status": "PASS",
        "source_commit_at_check": commit,
        "required_source_commit": REQUIRED_COMMIT,
        "hashes": hashes,
        "parsed": {
            "status": parsed["status"],
            "four_role_valid": parsed["four_role_valid"],
            "env_cap": parsed["env_cap"],
        },
        "roles": {
            "status": role_report["status"],
            "digests": role_report["digests"],
            "assignments": role_report["assignments"],
            "historical_exclusion_clean": role_report["historical_exclusion_clean"],
        },
        "h17": "blocked",
        "frozen_allocation_unauthorized": True,
    }


def grant_record() -> dict:
    if not GRANT.is_file():
        raise RuntimeError("science_grant_missing")
    return json.loads(GRANT.read_text())


def grant_unused() -> bool:
    if not GRANT.is_file():
        return False
    record = grant_record()
    return (
        record.get("authorized") is True
        and record.get("consumed") is False
        and int(record.get("runs") or 0) == 0
        and int(record.get("env_cap") or 0) == REQUIRED_ENV_CAP
    )


def write_grant(approval_text: str, *, source_commit_sha: str) -> dict:
    if GRANT.is_file():
        existing = grant_record()
        if existing.get("consumed") is True or int(existing.get("runs") or 0) > 0:
            raise RuntimeError("science_grant_already_consumed")
        return existing
    preflight = integrity_preflight(approval_text)
    if source_commit_sha != REQUIRED_COMMIT:
        raise RuntimeError("grant_must_cite_required_source_commit")
    payload = {
        "authorized": True,
        "consumed": False,
        "closed": False,
        "runs": 0,
        "max_runs": 1,
        "automatic_retries": False,
        "env_cap": REQUIRED_ENV_CAP,
        "time_cap_s": REQUIRED_TIME_CAP_S,
        "n_bundles": 3,
        "methods": ["persist", "reset", "random", "evolution"],
        "primary_comparison": "persist_minus_reset",
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "source_commit": source_commit_sha,
        "roles": {role: list(APPROVED_ROLES[role]) for role in ROLE_ORDER},
        "role_digests": dict(ROLE_DIGESTS),
        "hold_named": True,
        "h17": "blocked",
        "n10_forbidden": True,
        "occupied_default_credit": 0,
        "does_not_rewrite": [
            "configs/evolution2_persist_reset_request.yaml",
            "configs/evolution2_persist_reset_allocation.json",
            "docs/NEXUS_EVOLUTION2_PERSIST_RESET_REQUEST.md",
        ],
        "frozen_hashes": preflight["hashes"],
        "scientific_ledger_before": [305.842, 3294.158],
        "authority": (
            "Human 2026-10-18 one-run n=3 persist-versus-reset grant. "
            "Does not rewrite frozen request hashes."
        ),
        "claims_learning_to_learn": False,
        "is_agi": False,
    }
    GRANT.write_text(json.dumps(payload, indent=2) + "\n")
    if file_sha256(lock.CONFIG) != lock.LOCKED_CONFIG:
        raise RuntimeError("grant_rewrote_frozen_config")
    if file_sha256(lock.ALLOCATION) != lock.LOCKED_ALLOCATION:
        raise RuntimeError("grant_rewrote_frozen_allocation")
    return payload


def consume_grant() -> dict:
    record = grant_record()
    if record.get("authorized") is not True:
        raise RuntimeError("science_grant_unauthorized")
    if record.get("consumed") is True or int(record.get("runs") or 0) != 0:
        raise RuntimeError("science_grant_already_consumed")
    if int(record.get("env_cap") or 0) != REQUIRED_ENV_CAP:
        raise RuntimeError("science_grant_env_cap_mismatch")
    record["consumed"] = True
    record["runs"] = 1
    GRANT.write_text(json.dumps(record, indent=2) + "\n")
    if file_sha256(lock.CONFIG) != lock.LOCKED_CONFIG:
        raise RuntimeError("consume_rewrote_frozen_config")
    if file_sha256(lock.ALLOCATION) != lock.LOCKED_ALLOCATION:
        raise RuntimeError("consume_rewrote_frozen_allocation")
    return record


def require_unused_grant(env_cap: int, approval_text: str) -> dict:
    if int(env_cap) == 7680:
        raise RuntimeError("occupied_default_persist_not_fresh_physics")
    if int(env_cap) != REQUIRED_ENV_CAP:
        raise RuntimeError("env_cap_must_be_17280")
    if not grant_unused():
        lock.require_named_holdout()
    verify_approval(approval_text)
    record = grant_record()
    if record.get("source_commit") != REQUIRED_COMMIT:
        raise RuntimeError("grant_source_commit_mismatch")
    return record
