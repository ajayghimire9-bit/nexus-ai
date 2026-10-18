"""Source-array persist request. Source-only. Does not collect."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution2 import execution_blockers as blockers
from nexus.evolution2 import pendulum_acrobot_protocol_n3_micro as n3
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_SOURCE_PERSIST_REQUEST.md"
CONFIG = ROOT / "configs" / "evolution2_source_persist_request.yaml"
ALLOCATION = ROOT / "configs" / "evolution2_source_persist_allocation.json"
TARGET = ROOT / "artifacts" / "evolution2_source_arrays"
RESULTS = ROOT / "artifacts" / "evolution2_source_persist_request.json"

VERSION = "source-persist-request"
DOES_NOT_REWRITE = ("v2", "v2-pilot", "n3-micro")
FAMILIES = ("pendulum", "acrobot")
REQUIRED_KEYS = ("obs", "action", "next_obs", "terminated", "env_seeds")
N_TRAIN = v2.SOURCE_TRAIN_STEPS
N_VAL = v2.SOURCE_VAL_STEPS
V2_SOURCE_STEPS = v2.N_BUNDLES * 2 * (N_TRAIN + N_VAL)
N3_SOURCE_STEPS = n3.N_BUNDLES * 2 * (N_TRAIN + N_VAL)

LOCKED_CONFIG = "325cd42b99bd4ff03d7a993bda71272933bd9ed0644103cd55274ab2303a9c76"
LOCKED_PROTOCOL = "3ffb544dfcc75b294bb093bd3ad23175ce9312832e014bc5b1fd8600eed5f1a9"
LOCKED_ALLOCATION = "be122e8fff80c3f26c426a083a75534653bc3d82ec8ea68f0ed0a302a85830ac"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_persist() -> None:
    raise RuntimeError(
        "source persist unauthorized: authorized=false, env_cap=0, "
        "standing grant does not start collection"
    )


def require_scientific() -> None:
    raise RuntimeError(
        "Evolution-2 scientific dispatch remains blocked; this request "
        "does not collect or evaluate"
    )


def prior_hashes_frozen() -> bool:
    return (
        n3.prior_hashes_frozen()
        and n3.file_sha256(n3.CONFIG) == n3.LOCKED_CONFIG
        and n3.file_sha256(n3.PROTOCOL) == n3.LOCKED_PROTOCOL
        and n3.file_sha256(n3.ALLOCATION) == n3.LOCKED_ALLOCATION
    )


def planned_files(n_bundles: int) -> list[str]:
    rows = []
    for family in FAMILIES:
        for bundle in range(int(n_bundles)):
            for split in ("train", "val"):
                rows.append(f"artifacts/evolution2_source_arrays/{family}/bundle{bundle}_{split}.npz")
    return rows


def target_status() -> dict:
    present = sorted(
        str(path.relative_to(ROOT))
        for path in TARGET.rglob("*.npz")
        if path.is_file()
    ) if TARGET.exists() else []
    return {
        "target_dir": "artifacts/evolution2_source_arrays",
        "exists": TARGET.exists(),
        "found": present,
        "empty": present == [],
    }


def worksheet() -> dict:
    return {
        "version": VERSION,
        "does_not_rewrite": list(DOES_NOT_REWRITE),
        "n_train": N_TRAIN,
        "n_val": N_VAL,
        "required_keys": list(REQUIRED_KEYS),
        "v2_source_steps": V2_SOURCE_STEPS,
        "n3_source_steps": N3_SOURCE_STEPS,
        "v2_files": len(planned_files(v2.N_BUNDLES)),
        "n3_files": len(planned_files(n3.N_BUNDLES)),
        "authorized_env_cap": 0,
        "authorized_time_cap_s": 0,
        "collection": False,
    }


def public_lock() -> dict:
    return {
        "version": VERSION,
        "authorized": False,
        "runs": 0,
        "hold_named": False,
        "collection": False,
        "status": "request_only_unauthorized",
        "claims_learning_to_learn": False,
        "is_agi": False,
    }


def allocation_record() -> dict:
    return json.loads(ALLOCATION.read_text())


def write_artifact() -> dict:
    payload = {
        "scientific": False,
        "collection": False,
        "status": "request_only_unauthorized",
        "target": target_status(),
        "worksheet": worksheet(),
        "blockers": [row["id"] for row in blockers.blocker_matrix()],
        "v2_n3_hashes_frozen": prior_hashes_frozen(),
        "ledger_debit_s": 0,
        "scientific_ledger_preserved": [305.842, 3294.158],
        "next_action": (
            "Human approval must cite this configuration hash and set "
            "env_cap to 7680 or 25600. Do not collect before that record."
        ),
    }
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
