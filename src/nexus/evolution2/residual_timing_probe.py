"""Residual-MLP timing-probe contracts. Source-only. No env collection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_RESIDUAL_TIMING_PROBE.md"
CONFIG = ROOT / "configs" / "evolution2_residual_timing_probe.yaml"
ALLOCATION = ROOT / "configs" / "evolution2_residual_timing_probe_allocation.json"
RESULTS = ROOT / "artifacts" / "evolution2_residual_timing_probe.json"

VERSION = "residual-timing-probe-v1"
HOLD_NAMED = False
LOCKED_TARGET = None
AUTHORIZED_TIME_CAP_S = 60
AUTHORIZED_ENV_CAP = 0
AUTHORIZED_IMAGINED_CAP = 200_000
SESSION_LEDGER_USED_S = 305.842
SESSION_LEDGER_REMAINING_S = 3294.158
HISTORICAL_SECONDS_PER_IMAGINED = 68.146 / 12_324_000
V2_IMAGINED = 110_592_000
PILOT_IMAGINED = 49_152_000

REQUIRED_CHECKPOINTS = (
    {
        "id": "pendulum_frozen_decoder",
        "family": "pendulum",
        "path": "artifacts/frozen_dynamics_checkpoints/seed0_history_u1000.pt",
        "sha256": "83e90a9b187cdffe5e39d794ce86abf65ef891fde011daf8e55b7eee1f348959",
    },
    {
        "id": "pendulum_residual_mlp",
        "family": "pendulum",
        "path": "artifacts/context_optimization_checkpoints/seed0_mlp_u1000.pt",
        "sha256": "4f4db2ca0ade8d2e19cb37971cf7343959edcdc17befe73e1aa9169e19c21cc2",
    },
    {
        "id": "acrobot_lookahead_seed0",
        "family": "acrobot",
        "path": "checkpoints/acrobot_lookahead_h16/seed0.pt",
        "sha256": "bcd7fbb61231c314d83cf96d73e49e29f19d9dd10e299bc69b7fe3811ca05c2f",
    },
)

LOCKED_CONFIG = "b3b4ad6e316485a3bda3e8950e3fae3f87ddd645c353972a06e03fca8241f2ef"
LOCKED_PROTOCOL = "feeb1cc4962ad33a9a0d5389e528287e8c642a7ad4b624c171e229731631d19c"
LOCKED_ALLOCATION = "23608a22dca192965d6f977f11073a4aebe3d96a5914ebf284e09f348eb979ac"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_scientific() -> None:
    raise RuntimeError(
        "v2/v2-pilot collection remains unauthorized; this probe times "
        "existing residual MLPs only"
    )


def require_named_holdout() -> None:
    raise RuntimeError("holdout remains unnamed")


def checkpoint_status() -> list[dict]:
    rows = []
    for spec in REQUIRED_CHECKPOINTS:
        path = ROOT / spec["path"]
        present = path.is_file()
        digest = file_sha256(path) if present else None
        rows.append(
            {
                "id": spec["id"],
                "family": spec["family"],
                "path": spec["path"],
                "expected_sha256": spec["sha256"],
                "present": present,
                "matches": bool(present and digest == spec["sha256"]),
            }
        )
    return rows


def all_checkpoints_verified() -> bool:
    return all(row["matches"] for row in checkpoint_status())


def require_probe() -> None:
    record = allocation_record()
    if record.get("authorized") is not True:
        raise RuntimeError("timing probe unauthorized")
    if int(record.get("env_cap", -1)) != 0:
        raise RuntimeError("timing probe forbids env steps")
    if not all_checkpoints_verified():
        raise RuntimeError("timing probe checkpoints missing or mismatched")


def extrapolate(seconds_per_imagined: float) -> dict[str, float]:
    return {
        "historical_s": HISTORICAL_SECONDS_PER_IMAGINED,
        "measured_s": float(seconds_per_imagined),
        "v2_historical_s": HISTORICAL_SECONDS_PER_IMAGINED * V2_IMAGINED,
        "v2_measured_s": float(seconds_per_imagined) * V2_IMAGINED,
        "pilot_historical_s": HISTORICAL_SECONDS_PER_IMAGINED * PILOT_IMAGINED,
        "pilot_measured_s": float(seconds_per_imagined) * PILOT_IMAGINED,
    }


def allocation_record() -> dict:
    return json.loads(ALLOCATION.read_text())


def public_lock() -> dict:
    return {
        "version": VERSION,
        "authorized": True,
        "runs": 0,
        "hold_named": HOLD_NAMED,
        "locked_target": LOCKED_TARGET,
        "authorized_time_cap_s": AUTHORIZED_TIME_CAP_S,
        "authorized_env_cap": AUTHORIZED_ENV_CAP,
        "authorized_imagined_cap": AUTHORIZED_IMAGINED_CAP,
        "collection": False,
        "modifies_checkpoints": False,
        "claims_learning_to_learn": False,
        "is_agi": False,
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
