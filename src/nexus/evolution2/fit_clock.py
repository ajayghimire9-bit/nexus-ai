"""Disposable residual-MLP fit-clock lock. Source-only. Does not train."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution2 import execution_blockers as blockers
from nexus.evolution2 import source_persist_request as persist

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "docs" / "NEXUS_EVOLUTION2_FIT_CLOCK.md"
CONFIG = ROOT / "configs" / "evolution2_fit_clock.yaml"
ALLOCATION = ROOT / "configs" / "evolution2_fit_clock_allocation.json"
SOURCE = ROOT / "artifacts" / "evolution2_source_arrays"
TARGET = ROOT / "artifacts" / "evolution2_fit_clock_disposable"
RESULTS = ROOT / "artifacts" / "evolution2_fit_clock.json"

VERSION = "fit-clock-request"
DOES_NOT_REWRITE = ("v2", "v2-pilot", "n3-micro")
FAMILIES = persist.FAMILIES
N_FITS = 6
N_BUNDLES = 3
N_TRAIN = persist.N_TRAIN
N_VAL = persist.N_VAL
GRANTED_ENV_CAP = 0
GRANTED_TIME_CAP_S = 300
SCIENTIFIC_STATUS = "development_pilot_not_confirmation"
RECIPE = {
    "module": "nexus.world.train.train_world_model",
    "kind": "residual",
    "hidden": [64, 64],
    "epochs": 20,
    "batch_size": 128,
    "n_train": N_TRAIN,
    "n_val": N_VAL,
    "optimizer": "Adam",
    "lr": 0.001,
    "arch": "mlp",
}

LOCKED_CONFIG = "277d7ba628fcd4e528b27bf4407ed45f9e41ec9051bd9e26b4baef33c6df0ff0"
LOCKED_PROTOCOL = "3846f4ecb4161455f8954e6ae363f47d43b873031fd38ea68118e0683393fd52"
LOCKED_ALLOCATION = "79e535928ea7a067602ddb49dd0482e50e00af7dd4868186947cc95153231616"

LOCKED_ARRAYS = (
    {
        "family": "pendulum",
        "bundle": 0,
        "split": "train",
        "n": 1024,
        "path": "artifacts/evolution2_source_arrays/pendulum/bundle0_train.npz",
        "sha256": "c80901186c47247809a695c665525026994668dd96c396b68511412d50cc4a84",
    },
    {
        "family": "pendulum",
        "bundle": 0,
        "split": "val",
        "n": 256,
        "path": "artifacts/evolution2_source_arrays/pendulum/bundle0_val.npz",
        "sha256": "11745f3db32bc1c9841e24b316718c5a15337fd12cfd6439596ac8a56c3b847d",
    },
    {
        "family": "pendulum",
        "bundle": 1,
        "split": "train",
        "n": 1024,
        "path": "artifacts/evolution2_source_arrays/pendulum/bundle1_train.npz",
        "sha256": "6fbb1a6898ba292e068536ed3e8b656b3d2bf886d5948d45691abd6bbe3abd1a",
    },
    {
        "family": "pendulum",
        "bundle": 1,
        "split": "val",
        "n": 256,
        "path": "artifacts/evolution2_source_arrays/pendulum/bundle1_val.npz",
        "sha256": "d1a7eb68270ad1831c2c5262ac24fdc3f7f771e2b4fe4eafd910e9d5d006e4ed",
    },
    {
        "family": "pendulum",
        "bundle": 2,
        "split": "train",
        "n": 1024,
        "path": "artifacts/evolution2_source_arrays/pendulum/bundle2_train.npz",
        "sha256": "82464b7bbd807e83a3a8bd29da18333939d72f14d07f05cc14e57b6404a5c3f2",
    },
    {
        "family": "pendulum",
        "bundle": 2,
        "split": "val",
        "n": 256,
        "path": "artifacts/evolution2_source_arrays/pendulum/bundle2_val.npz",
        "sha256": "701a42ea78b9dabc0f6ef8d7841ef61f73ab29af0fb9c55d70febbca6d3e5b7a",
    },
    {
        "family": "acrobot",
        "bundle": 0,
        "split": "train",
        "n": 1024,
        "path": "artifacts/evolution2_source_arrays/acrobot/bundle0_train.npz",
        "sha256": "b904e52cb76398e279d2ed9d9b8c68a6250501f28cc65f3bb012b1330651a2ee",
    },
    {
        "family": "acrobot",
        "bundle": 0,
        "split": "val",
        "n": 256,
        "path": "artifacts/evolution2_source_arrays/acrobot/bundle0_val.npz",
        "sha256": "bbfdd62430e706485e95264cf7a79bde1ed82ce1185cf6154e788e52b1b8105e",
    },
    {
        "family": "acrobot",
        "bundle": 1,
        "split": "train",
        "n": 1024,
        "path": "artifacts/evolution2_source_arrays/acrobot/bundle1_train.npz",
        "sha256": "9a158288f0cbbb9cda9a7784f38eea7608398db0ac759f0bb8a0d48649451a71",
    },
    {
        "family": "acrobot",
        "bundle": 1,
        "split": "val",
        "n": 256,
        "path": "artifacts/evolution2_source_arrays/acrobot/bundle1_val.npz",
        "sha256": "45fd547868312ce4c7a5ce7786af3954198735fe16f966382801574d8d63421c",
    },
    {
        "family": "acrobot",
        "bundle": 2,
        "split": "train",
        "n": 1024,
        "path": "artifacts/evolution2_source_arrays/acrobot/bundle2_train.npz",
        "sha256": "f923bca054b0dd15f6e6195db3500d2e4c978a279cb58ca00b422471df73d070",
    },
    {
        "family": "acrobot",
        "bundle": 2,
        "split": "val",
        "n": 256,
        "path": "artifacts/evolution2_source_arrays/acrobot/bundle2_val.npz",
        "sha256": "4a6c5540b4db7e32154702eb5838260f6f459462326fb12864df110deb5631aa",
    },
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_scientific() -> None:
    raise RuntimeError(
        "Evolution-2 scientific dispatch remains blocked; this fit clock "
        "does not evaluate persist versus reset"
    )


def require_clock() -> None:
    raise RuntimeError(
        "fit clock unauthorized: authorized=false, env_cap!=0 or n_fits!=6, "
        "standing grant does not start training"
    )


def allocation_record() -> dict:
    return json.loads(ALLOCATION.read_text())


def clock_authorized(env_cap: int, n_fits: int) -> bool:
    record = allocation_record()
    return (
        record.get("authorized") is True
        and int(record.get("env_cap", -1)) == int(env_cap) == GRANTED_ENV_CAP
        and int(record.get("n_fits", -1)) == int(n_fits) == N_FITS
        and int(record.get("time_cap_s") or 0) == GRANTED_TIME_CAP_S
    )


def refuse_promotion(n_fits: int) -> None:
    if int(n_fits) != N_FITS:
        raise RuntimeError("n3_fit_clock_is_not_v2_confirmation")


def prior_hashes_frozen() -> bool:
    return (
        persist.prior_hashes_frozen()
        and persist.file_sha256(persist.CONFIG) == persist.LOCKED_CONFIG
        and persist.file_sha256(persist.ALLOCATION) == persist.LOCKED_ALLOCATION
    )


def planned_fits() -> list[dict]:
    rows = []
    for family in FAMILIES:
        for bundle in range(N_BUNDLES):
            rows.append(
                {
                    "family": family,
                    "bundle": bundle,
                    "path": f"artifacts/evolution2_fit_clock_disposable/{family}/bundle{bundle}.pt",
                }
            )
    return rows


def source_status() -> dict:
    rows = []
    for spec in LOCKED_ARRAYS:
        path = ROOT / spec["path"]
        digest = file_sha256(path) if path.is_file() else None
        rows.append(
            {
                **spec,
                "present": path.is_file(),
                "matches": bool(path.is_file() and digest == spec["sha256"]),
            }
        )
    return {
        "source_dir": "artifacts/evolution2_source_arrays",
        "n_files": len(rows),
        "all_match": all(row["matches"] for row in rows),
        "files": rows,
    }


def public_lock() -> dict:
    record = allocation_record()
    return {
        "version": VERSION,
        "authorized": bool(record.get("authorized")),
        "runs": int(record.get("runs") or 0),
        "hold_named": False,
        "collection": False,
        "fitting": False,
        "status": record.get("scientific_status") or "request_only_fit_unauthorized",
        "env_cap": int(record.get("env_cap") or 0),
        "time_cap_s": int(record.get("time_cap_s") or 0),
        "n_fits": int(record.get("n_fits") or 0),
        "config_sha256": LOCKED_CONFIG,
        "claims_learning_to_learn": False,
        "is_agi": False,
    }


def dispatch(env_cap: int, n_fits: int = N_FITS) -> None:
    refuse_promotion(n_fits)
    if int(env_cap) != GRANTED_ENV_CAP:
        raise RuntimeError("fit_clock_forbids_env_steps")
    if not clock_authorized(env_cap, n_fits):
        require_clock()
    runner = __import__("nexus.evolution2.fit_clock_run", fromlist=["run_clock"])
    runner.run_clock(int(env_cap), int(n_fits))


def write_artifact() -> dict:
    payload = {
        "scientific": False,
        "collection": False,
        "fitting": False,
        "status": public_lock()["status"],
        "recipe": dict(RECIPE),
        "source": source_status(),
        "planned_fits": planned_fits(),
        "blockers": [row["id"] for row in blockers.blocker_matrix()],
        "v2_n3_hashes_frozen": prior_hashes_frozen(),
        "ledger_debit_s": 0,
        "scientific_ledger_preserved": [305.842, 3294.158],
        "cited_config_sha256": LOCKED_CONFIG,
        "granted_env_cap": GRANTED_ENV_CAP,
        "granted_time_cap_s": GRANTED_TIME_CAP_S,
        "granted_n_fits": N_FITS,
        "next_action": (
            "Six disposable residual fits are granted at env_cap=0. Do not "
            "promote them to n=10 or v2 confirmation."
        ),
    }
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
