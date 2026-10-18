"""Locked 7680-step persist plan. No Gymnasium collection."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from nexus.evolution2 import pendulum_acrobot_protocol as v1
from nexus.evolution2 import source_persist_request as lock

ALLOWED_PHYSICS = {
    "pendulum": (10.0, 1.0, 1.0),
    "acrobot": (1.0, 1.0, 1.0),
}
ALLOWED_TASK_IDS = {
    "pendulum": "pendulum_default",
    "acrobot": "acrobot_default",
}
SEEDS_PER_SPLIT = 8
SCIENTIFIC_STATUS = "development_pilot_not_confirmation"


def physics_key(values) -> tuple[float, float, float]:
    return v1.physics_key(values)


def refuse_promotion_to_v2(env_cap: int) -> None:
    if int(env_cap) == lock.N3_SOURCE_STEPS:
        raise RuntimeError("n3_pilot_is_not_v2_confirmation")


def scientific_status(env_cap: int) -> str:
    if int(env_cap) != lock.N3_SOURCE_STEPS:
        raise RuntimeError("env_cap_must_be_7680_or_25600")
    return SCIENTIFIC_STATUS


def refuse_closed_physics(family: str, key) -> None:
    row = physics_key(key)
    allowed = ALLOWED_PHYSICS[family]
    if row != allowed:
        raise RuntimeError("closed_or_unlisted_physics")
    occupied = v1.occupied_pendulum() if family == "pendulum" else v1.occupied_acrobot()
    if row in occupied and row != allowed:
        raise RuntimeError("closed_or_unlisted_physics")


def seed_block(*, family: str, bundle: int, split: str) -> tuple[int, ...]:
    family_code = 0 if family == "pendulum" else 1
    split_code = 0 if split == "train" else 1
    start = 30_000 + 10_000 * family_code + 5_000 * split_code + 200 * int(bundle)
    return tuple(start + i for i in range(SEEDS_PER_SPLIT))


def base_seed(*, family: str, bundle: int, split: str) -> int:
    family_code = 0 if family == "pendulum" else 1
    split_code = 0 if split == "train" else 1
    return 17 + 23 * int(bundle) + 100 * family_code + 3 * split_code


def seed_schedule(n_bundles: int = 3) -> list[dict]:
    rows = []
    seen: set[int] = set()
    for family in lock.FAMILIES:
        for bundle in range(int(n_bundles)):
            for split in ("train", "val"):
                seeds = seed_block(family=family, bundle=bundle, split=split)
                if seen.intersection(seeds):
                    raise RuntimeError("train_val_seed_overlap")
                seen.update(seeds)
                rows.append(
                    {
                        "family": family,
                        "bundle": bundle,
                        "split": split,
                        "n": lock.N_TRAIN if split == "train" else lock.N_VAL,
                        "env_seeds": list(seeds),
                        "base_seed": base_seed(family=family, bundle=bundle, split=split),
                        "path": f"artifacts/evolution2_source_arrays/{family}/bundle{bundle}_{split}.npz",
                    }
                )
    return rows


def refuse_duplicate_or_partial(root: Path | None = None) -> None:
    base = root or lock.ROOT
    target = base / "artifacts" / "evolution2_source_arrays"
    if not target.exists():
        return
    leftovers = [p for p in target.rglob("*") if p.is_file()]
    if leftovers:
        raise RuntimeError("duplicate_or_partial_persist")


def atomic_write_npz(path: Path, arrays: dict[str, np.ndarray]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".partial.npz")
    if tmp.exists():
        tmp.unlink()
    missing = [key for key in lock.REQUIRED_KEYS if key not in arrays]
    if missing:
        raise RuntimeError(f"missing_required_keys:{missing}")
    np.savez_compressed(tmp, **arrays)
    os.replace(tmp, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(tmp, path)
