"""Approval-text gate for persist-versus-reset. Source-only. Not science.

Vague authorization is not enough. A later message must cite the locked
config hash, name a four-role unused holdout, and set env_cap=17280.
Does not flip yaml flags, collect, or name a holdout.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from nexus.evolution2 import persist_reset_budget as budget
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import pendulum_acrobot_holdout_review as review

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_approval.json"

REQUIRED_HASH = lock.LOCKED_CONFIG
REQUIRED_ENV_CAP = budget.FRESH_TOTAL_STEPS
VAGUE = (
    "continue",
    "i authorised you",
    "i authorized you",
    "i authorised u",
    "i authorized u",
    "i approved everything",
    "i authorised everything",
    "i authorized everything",
    "i authrosed you",
)


def _norm(text: str) -> str:
    return " ".join(str(text).lower().split())


def parse_approval(text: str) -> dict:
    raw = str(text)
    norm = _norm(raw)
    hash_hit = REQUIRED_HASH in raw or REQUIRED_HASH[:8] in raw
    cap_hits = [int(x) for x in re.findall(r"env_cap\s*[=:]\s*(\d+)", norm)]
    env_cap = cap_hits[-1] if cap_hits else None
    hold_named = bool(
        re.search(r"holdout|pendulum_source|acrobot_source|four-role|four role", norm)
    ) and not any(
        phrase in norm
        for phrase in (
            "do not name a holdout",
            "holdout unnamed",
            "without naming",
        )
    )
    occupied = "(10,1,1)" in raw.replace(" ", "") or "(1,1,1)" in raw.replace(" ", "")
    if occupied:
        hold_named = False
    vague = any(phrase in norm for phrase in VAGUE)
    missing = []
    if not hash_hit:
        missing.append("config_hash_8e90b74a")
    if not hold_named:
        missing.append("named_four_role_unused_holdout")
    if env_cap != REQUIRED_ENV_CAP:
        missing.append("env_cap_17280")
    if env_cap == 7680:
        missing.append("rejected_7680_reuse")
    status = "INSUFFICIENT" if missing else "COMPLETE_TEXT_ONLY"
    return {
        "status": status,
        "authorized": False,
        "scientific": False,
        "collection": False,
        "hash_cited": hash_hit,
        "hold_named": False,
        "env_cap": env_cap,
        "required_env_cap": REQUIRED_ENV_CAP,
        "vague_authorization": vague,
        "occupied_default_named": occupied,
        "missing": missing,
        "holdout_review": review.VERDICT,
        "yaml_unchanged": lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG,
        "allocation_unchanged": lock.file_sha256(lock.ALLOCATION) == lock.LOCKED_ALLOCATION,
        "note": (
            "Text completeness is not authorization. Allocation stays "
            "unauthorized until a later recorded grant flips no frozen hashes "
            "here. This parser does not name a holdout."
        ),
    }


def refuse_vague_authorization(text: str) -> None:
    parsed = parse_approval(text)
    if parsed["occupied_default_named"]:
        raise RuntimeError("occupied_default_is_not_a_holdout")
    if parsed["status"] != "COMPLETE_TEXT_ONLY":
        raise RuntimeError(
            "persist_versus_reset_approval_insufficient:" + ",".join(parsed["missing"])
        )
    raise RuntimeError("persist_versus_reset_allocation_still_unauthorized")


def write_artifact(text: str) -> dict:
    parsed = parse_approval(text)
    payload = {
        "scientific": False,
        "collection": False,
        "granted_7680": False,
        "message": text,
        "parsed": parsed,
        "budget_fresh_total": REQUIRED_ENV_CAP,
        "cited_config_sha256": REQUIRED_HASH,
        "scientific_ledger_preserved": [305.842, 3294.158],
        "claims_learning_to_learn": False,
        "is_agi": False,
        "next_action": (
            "Reply with the config hash 8e90b74ad3f406509051025160799c13d9a28bbb7e16c11a77808653bb43827e, "
            "a named unused four-role holdout, and env_cap=17280. "
            "continue / i authorised you is not approval."
        ),
    }
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
