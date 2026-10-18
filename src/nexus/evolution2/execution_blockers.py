"""Evolution-2 execution-blocker matrix. Read-only. No collection."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from nexus.evolution2 import nofit_inventory as nofit
from nexus.evolution2 import pendulum_acrobot_protocol_n3_micro as n3
from nexus.evolution2 import residual_timing_probe as timing
from nexus.evolution2 import source_fitting_benchmark as fitting

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_execution_blockers.json"

STATUS = "E2_SCIENTIFIC_DISPATCH_BLOCKED"
TRANSITION_TOKENS = ("transition", "dataset", "next_obs", "train", "val")


def require_scientific() -> None:
    raise RuntimeError(
        "Evolution-2 scientific dispatch is blocked: source fitting "
        "unavailable, checkpoint payloads are weights only, holdout unnamed"
    )


def payload_audit() -> list[dict]:
    rows = []
    seen: set[str] = set()
    specs = list(n3.bound_files()) + list(timing.checkpoint_status())
    for spec in specs:
        path = spec["path"]
        if path in seen:
            continue
        seen.add(path)
        file_path = ROOT / path
        zip_file = bool(file_path.is_file() and zipfile.is_zipfile(file_path))
        names = zipfile.ZipFile(file_path).namelist() if zip_file else []
        hits = [name for name in names if any(token in name.lower() for token in TRANSITION_TOKENS)]
        rows.append(
            {
                "id": spec["id"],
                "path": path,
                "present": file_path.is_file(),
                "zip": zip_file,
                "members": len(names),
                "bytes": file_path.stat().st_size if file_path.is_file() else 0,
                "transition_members": hits,
                "weights_only": zip_file and not hits,
            }
        )
    return rows


def blocker_matrix() -> list[dict]:
    infer = timing.feasibility_from_measured()
    sheets = nofit.nofit_worksheets()
    payloads = payload_audit()
    return [
        {
            "id": "SOURCE_FITTING_UNAVAILABLE",
            "status": fitting.STATUS,
            "blocks": ["v2", "v2-pilot"],
        },
        {
            "id": "WEIGHTS_ONLY_PAYLOAD",
            "status": "confirmed" if all(row["weights_only"] for row in payloads) else "failed",
            "blocks": ["source_fit_from_checkpoint"],
        },
        {
            "id": "NO_FIT_TEN_BUNDLE_UNAVAILABLE",
            "status": nofit.STATUS,
            "blocks": ["v2", "v2-pilot"],
        },
        {
            "id": "N3_NOT_READY_RECIPE_MISMATCH",
            "status": n3.public_lock()["status"],
            "blocks": ["n3-micro"],
        },
        {
            "id": "HOLDOUT_UNNAMED",
            "status": "unnamed",
            "blocks": ["v2", "v2-pilot", "n3-micro"],
        },
        {
            "id": "TWELVE_ARM_DISPATCH_BLOCKED",
            "status": "blocked",
            "blocks": ["scientific_dispatch"],
        },
        {
            "id": "FULL_V2_NO_GO",
            "status": infer.get("v2_feasibility"),
            "blocks": ["v2"],
        },
        {
            "id": "V2_PILOT_NOFIT_BLOCKED",
            "status": sheets["pilot_nofit_feasibility"],
            "blocks": ["v2-pilot"],
        },
        {
            "id": "SCIENTIFIC_DISPATCH_UNAUTHORIZED",
            "status": "unauthorized",
            "blocks": ["v2", "v2-pilot", "n3-micro"],
        },
        {
            "id": "H17_BLOCKED",
            "status": "blocked",
            "blocks": ["h17"],
        },
    ]


def write_artifact() -> dict:
    payloads = payload_audit()
    payload = {
        "scientific": False,
        "collection": False,
        "modifies_checkpoints": False,
        "status": STATUS,
        "payloads": payloads,
        "weights_only": all(row["weights_only"] for row in payloads),
        "blockers": blocker_matrix(),
        "v2_hashes_frozen": n3.prior_hashes_frozen(),
        "n3_hashes_frozen": (
            n3.file_sha256(n3.CONFIG) == n3.LOCKED_CONFIG
            and n3.file_sha256(n3.PROTOCOL) == n3.LOCKED_PROTOCOL
            and n3.file_sha256(n3.ALLOCATION) == n3.LOCKED_ALLOCATION
        ),
        "ledger_debit_s": 0,
        "scientific_ledger_preserved": [305.842, 3294.158],
        "next_action": (
            "Do not open another worksheet shrink. Do not collect replacements. "
            "Evolution-2 stays blocked until a separate authorization persists "
            "matched Pendulum/Acrobot source train/val arrays."
        ),
        "claims_learning_to_learn": False,
        "is_agi": False,
    }
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
