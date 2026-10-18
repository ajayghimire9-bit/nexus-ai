"""Authorized six-fit residual clock. Reuses persisted arrays. No collection."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np

from nexus.evolution2 import fit_clock as lock
from nexus.evolution2 import source_persist_plan as plan
from nexus.world.data import CARTPOLE_PHYSICS_VERSION, TransitionDataset
from nexus.world.train import train_world_model

USAGE = lock.ROOT / "artifacts" / "research_session_e2_fit_clock_usage.json"
MANIFEST = lock.ROOT / "artifacts" / "evolution2_fit_clock_run.json"


def refuse_duplicate() -> None:
    if lock.TARGET.exists() and any(lock.TARGET.rglob("*.pt")):
        raise RuntimeError("duplicate_or_partial_fit_clock")
    if any(lock.TARGET.rglob("*.partial.pt")):
        raise RuntimeError("duplicate_or_partial_fit_clock")


def dataset_from_npz(path: Path, *, family: str, expected_n: int) -> TransitionDataset:
    data = np.load(path)
    for key in ("obs", "action", "next_obs", "terminated", "env_seeds"):
        if key not in data.files:
            raise RuntimeError("missing_array_key")
    n = int(data["obs"].shape[0])
    if n != int(expected_n):
        raise RuntimeError("array_length_mismatch")
    physics = tuple(float(x) for x in np.asarray(data["physics"]).reshape(-1))
    plan.refuse_closed_physics(family, physics)
    raw_task = np.asarray(data["task_id"])
    task_id = str(raw_task.item() if raw_task.shape == () else raw_task.reshape(-1)[0])
    if task_id != plan.ALLOWED_TASK_IDS[family]:
        raise RuntimeError("unexpected_task_id")
    return TransitionDataset(
        obs=np.asarray(data["obs"], dtype=np.float32),
        action=np.asarray(data["action"], dtype=np.int64),
        next_obs=np.asarray(data["next_obs"], dtype=np.float32),
        reward=np.zeros(n, dtype=np.float32),
        terminated=np.asarray(data["terminated"], dtype=np.bool_),
        truncated=np.zeros(n, dtype=np.bool_),
        task_id=task_id,
        seed=np.asarray(data["env_seeds"], dtype=np.int64),
        episode_id=np.zeros(n, dtype=np.int64),
        policy=np.asarray(["random"] * n),
        physics={"g": physics[0], "m": physics[1], "l": physics[2]}
        if family == "pendulum"
        else {"link1": physics[0], "link2": physics[1], "mass": physics[2]},
        physics_version=CARTPOLE_PHYSICS_VERSION,
        env_interactions=0,
        notes={"source": "evolution2_source_arrays", "disposable_fit_clock": True},
    )


def atomic_save(model, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".partial.pt")
    if tmp.exists():
        tmp.unlink()
    model.save(tmp)
    os.replace(tmp, path)
    return lock.file_sha256(path)


def run_clock(env_cap: int, n_fits: int) -> dict:
    env_cap = int(env_cap)
    n_fits = int(n_fits)
    if not lock.clock_authorized(env_cap, n_fits):
        lock.require_clock()
    if env_cap != lock.GRANTED_ENV_CAP:
        raise RuntimeError("fit_clock_forbids_env_steps")
    lock.refuse_promotion(n_fits)
    source = lock.source_status()
    if not source["all_match"]:
        raise RuntimeError("source_array_hash_mismatch")
    refuse_duplicate()
    record = lock.allocation_record()
    time_cap = float(record.get("time_cap_s") or 0)
    started = time.perf_counter()
    cpu0 = time.process_time()
    fits = []
    recipe = lock.RECIPE
    grouped: dict[tuple[str, int], dict[str, dict]] = {}
    for row in lock.LOCKED_ARRAYS:
        grouped.setdefault((row["family"], int(row["bundle"])), {})[row["split"]] = row
    if len(grouped) != n_fits:
        raise RuntimeError("fit_count_mismatch")
    try:
        for (family, bundle), splits in grouped.items():
            if time_cap and time.perf_counter() - started >= time_cap:
                raise RuntimeError("time_cap")
            train = dataset_from_npz(
                lock.ROOT / splits["train"]["path"],
                family=family,
                expected_n=int(splits["train"]["n"]),
            )
            val = dataset_from_npz(
                lock.ROOT / splits["val"]["path"],
                family=family,
                expected_n=int(splits["val"]["n"]),
            )
            seed = 1000 + 10 * (0 if family == "pendulum" else 1) + int(bundle)
            model, metrics = train_world_model(
                train,
                val,
                kind=recipe["kind"],
                epochs=int(recipe["epochs"]),
                batch_size=int(recipe["batch_size"]),
                lr=float(recipe["lr"]),
                seed=seed,
                hidden=tuple(recipe["hidden"]),
                arch=recipe["arch"],
            )
            dest = lock.ROOT / f"artifacts/evolution2_fit_clock_disposable/{family}/bundle{bundle}.pt"
            digest = atomic_save(model, dest)
            fits.append(
                {
                    "family": family,
                    "bundle": bundle,
                    "seed": seed,
                    "path": str(dest.relative_to(lock.ROOT)),
                    "sha256": digest,
                    "best_val": metrics["best_val"],
                    "train_n": metrics["train_n"],
                    "val_n": metrics["val_n"],
                    "disposable": True,
                }
            )
    except Exception:
        raise
    wall = time.perf_counter() - started
    cpu = time.process_time() - cpu0
    payload = {
        "scientific": False,
        "scientific_status": lock.SCIENTIFIC_STATUS,
        "collection": False,
        "fitting": True,
        "env_steps": 0,
        "env_cap": env_cap,
        "time_cap_s": time_cap,
        "wall_s": wall,
        "cpu_s": cpu,
        "n_fits": len(fits),
        "fits": fits,
        "recipe": dict(recipe),
        "config_sha256": lock.LOCKED_CONFIG,
        "allocation_sha256": lock.file_sha256(lock.ALLOCATION),
        "hold_named": False,
        "v2_confirmation": False,
        "claims_learning_to_learn": False,
        "is_agi": False,
        "scientific_ledger_preserved": [305.842, 3294.158],
    }
    usage = {
        "session_id": record.get("session_id"),
        "env_steps": 0,
        "wall_s": wall,
        "cpu_s": cpu,
        "n_fits": len(fits),
        "h16_scientific_ledger_untouched": True,
        "consumed_total_s": wall,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n")
    USAGE.write_text(json.dumps(usage, indent=2) + "\n")
    return payload
