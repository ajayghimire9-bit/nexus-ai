"""Locked persist-versus-reset resource budget. Source-only. Not science.

Does not grant 7680. Does not collect. Occupied-default persist is not credit.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution2 import persist_reset_readiness as ready
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.pendulum_acrobot_protocol_v2 import IMAGINED_CAP_PER_DECISION

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_budget.json"
USAGE = ROOT / "artifacts" / "research_session_e2_persist_reset_budget_usage.json"
H16 = ready.H16
H16_SHA = ready.H16_SHA

SCREEN_DECISIONS_UPPER = ready.SCREEN_STEPS
IMAGINED_SCREEN_UPPER = SCREEN_DECISIONS_UPPER * IMAGINED_CAP_PER_DECISION
FRESH_TOTAL_STEPS = ready.FRESH_TOTAL_STEPS
FRESH_SOURCE_STEPS = ready.FRESH_SOURCE_STEPS
N_FITS = 6
STANDING_TIME_CAP_S = 900
STANDING_ENV_CAP = 100_000
AUTHORIZED_ENV_CAP = 0
AUTHORIZED_TIME_CAP_S = 0


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resource_budget() -> dict:
    steps = ready.step_worksheet()
    if steps["fresh_total_environment_steps"] != 17_280:
        raise RuntimeError("fresh_total_rewritten")
    if IMAGINED_SCREEN_UPPER != 14_745_600:
        raise RuntimeError("imagined_upper_mismatch")
    return {
        "scientific": False,
        "authorized_env_cap": AUTHORIZED_ENV_CAP,
        "authorized_time_cap_s": AUTHORIZED_TIME_CAP_S,
        "do_not_grant_7680": True,
        "real_environment": {
            "fresh_source": FRESH_SOURCE_STEPS,
            "revealed": ready.REVEALED_STEPS,
            "development": ready.DEVELOPMENT_STEPS,
            "screen": ready.SCREEN_STEPS,
            "fresh_total": FRESH_TOTAL_STEPS,
            "confirmation": 0,
            "occupied_default_credit": 0,
        },
        "imagined": {
            "cap_per_decision": IMAGINED_CAP_PER_DECISION,
            "screen_decisions_upper": SCREEN_DECISIONS_UPPER,
            "screen_upper_bound": IMAGINED_SCREEN_UPPER,
            "source_fitting": 0,
            "assumption": "receding_decide_every_real_screen_step",
        },
        "fits": {
            "n3_required": N_FITS,
            "v2_twenty": 20,
            "twenty_measured": False,
            "reuse_e29_defaults": False,
        },
        "standing": {
            "time_cap_s": STANDING_TIME_CAP_S,
            "env_cap": STANDING_ENV_CAP,
            "fresh_total_fits_standing_env": FRESH_TOTAL_STEPS <= STANDING_ENV_CAP,
            "v2_wall_clock_risk": "likely_incomplete_budget_under_900s",
        },
        "rejected_grants": {
            "7680": "occupied_default_reuse_or_source_only",
            "9600": "screen_without_fresh_residuals",
            "25600": "v2_n10_source",
        },
        "justification": steps["justification"],
    }


def refuse_premature_7680(env_cap: int) -> None:
    if int(env_cap) == 7680:
        raise RuntimeError("do_not_grant_7680_before_full_17280_fresh_budget")
    ready.refuse_source_reuse(int(env_cap))


def write_artifact(clock: dict | None = None, path: dict | None = None) -> dict:
    payload = {
        "scientific": False,
        "collection": False,
        "fitting": False,
        "enabled_dispatch": False,
        "granted_7680": False,
        "budget": resource_budget(),
        "bonferroni": ready.bonferroni_lock(),
        "clock": clock,
        "execution_path": path,
        "readiness": ready.scientific_readiness(0),
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "h16_scientific_ledger_untouched": file_sha256(H16) == H16_SHA,
        "scientific_ledger_preserved": [305.842, 3294.158],
        "claims_learning_to_learn": False,
        "is_agi": False,
        "next_action": (
            "Do not grant 7680. Do not collect. A later persist-versus-reset "
            "approval must cite 8e90b74a, name a four-role unused holdout, "
            "and set env_cap=17280. continue is not that approval."
        ),
    }
    RESULTS.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return payload
