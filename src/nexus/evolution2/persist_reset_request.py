"""Persist-versus-reset request. Source-only. Does not collect or evaluate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution2 import fit_clock as clock
from nexus.evolution2 import pendulum_acrobot_holdout_review as review
from nexus.evolution2 import pendulum_acrobot_protocol_n3_micro as n3
from nexus.evolution2 import source_persist_request as persist

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_PERSIST_RESET_REQUEST.md"
CONFIG = ROOT / "configs" / "evolution2_persist_reset_request.yaml"
ALLOCATION = ROOT / "configs" / "evolution2_persist_reset_allocation.json"
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_request.json"

VERSION = "persist-reset-request"
DOES_NOT_REWRITE = ("v2", "v2-pilot", "n3-micro")
METHODS = ("persist", "reset", "random", "evolution")
METHOD_MODULES = {
    "persist": "evolution2.methods.PersistentAdaptive",
    "reset": "evolution2.methods.ResetAdaptive",
    "random": "evolution2.methods.StatelessWrapper/RandomProposer",
    "evolution": "evolution2.methods.EvolutionarySearch",
}
N_BUNDLES = 3
CI_DF = 2
PRIMARY = "persist_minus_reset"
LOCKED_CONFIG = "8e90b74ad3f406509051025160799c13d9a28bbb7e16c11a77808653bb43827e"
LOCKED_PROTOCOL = "2c0d54cfd61215dddcda2e21fc71b36856b1871b5ba4f8817daecceb609174c9"
LOCKED_ALLOCATION = "ecb6b8c69932d8fe2bfc4c29870e9cf0ee4474a048338898c258d3689879da8f"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_named_holdout() -> None:
    review.require_named_holdout()


def require_scientific() -> None:
    raise RuntimeError(
        "persist-versus-reset unauthorized: authorized=false, env_cap=0, "
        "holdout unnamed, continue is not approval"
    )


def allocation_record() -> dict:
    return json.loads(ALLOCATION.read_text())


def persist_reset_authorized(env_cap: int) -> bool:
    record = allocation_record()
    return (
        record.get("authorized") is True
        and bool(record.get("hold_named"))
        and int(record.get("env_cap", 0)) == int(env_cap)
        and int(env_cap) > 0
    )


def dispatch(env_cap: int) -> None:
    require_named_holdout()
    if not persist_reset_authorized(env_cap):
        require_scientific()
    raise RuntimeError("persist_versus_reset_not_implemented_while_unauthorized")


def prior_hashes_frozen() -> bool:
    return (
        n3.prior_hashes_frozen()
        and persist.file_sha256(persist.CONFIG) == persist.LOCKED_CONFIG
        and clock.file_sha256(clock.CONFIG) == clock.LOCKED_CONFIG
        and n3.file_sha256(n3.CONFIG) == n3.LOCKED_CONFIG
    )


def public_lock() -> dict:
    record = allocation_record()
    return {
        "version": VERSION,
        "authorized": bool(record.get("authorized")),
        "runs": int(record.get("runs") or 0),
        "hold_named": False,
        "collection": False,
        "status": record.get("scientific_status") or "request_only_unauthorized",
        "env_cap": int(record.get("env_cap") or 0),
        "n_bundles": N_BUNDLES,
        "df": CI_DF,
        "methods": list(METHODS),
        "primary_comparison": PRIMARY,
        "twenty_fit_measured": False,
        "config_sha256": LOCKED_CONFIG,
        "claims_learning_to_learn": False,
        "is_agi": False,
    }


def worksheet() -> dict:
    return {
        "version": VERSION,
        "does_not_rewrite": list(DOES_NOT_REWRITE),
        "n_bundles": N_BUNDLES,
        "df": CI_DF,
        "methods": list(METHODS),
        "method_modules": dict(METHOD_MODULES),
        "primary_comparison": PRIMARY,
        "equal_budget": True,
        "bonferroni_t_crit": n3.BONFERRONI_T_CRIT_DF2,
        "practical_margin": n3.PRACTICAL_MARGIN,
        "hold_named": False,
        "locked_target": None,
        "occupied_defaults_are_not_holdout": True,
        "disposable_weights_are_not_confirmation": True,
        "source_fits": "six_fit_clock_cost_prior_only",
        "six_fit_wall_s": 1.215,
        "twenty_fit_measured": False,
        "authorized_env_cap": 0,
        "authorized_time_cap_s": 0,
        "collection": False,
    }


def write_artifact() -> dict:
    payload = {
        "scientific": False,
        "collection": False,
        "status": public_lock()["status"],
        "worksheet": worksheet(),
        "lock": public_lock(),
        "v2_n3_hashes_frozen": prior_hashes_frozen(),
        "holdout_review": review.VERDICT,
        "ledger_debit_s": 0,
        "scientific_ledger_preserved": [305.842, 3294.158],
        "cited_config_sha256": LOCKED_CONFIG,
        "next_action": (
            "Do not collect. A later approval must cite 8e90b74a, name a "
            "four-role unused holdout, and set env_cap. continue is not approval."
        ),
    }
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
