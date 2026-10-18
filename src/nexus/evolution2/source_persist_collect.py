"""Authorized 7680-step source persist. Family defaults only. No model training."""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from nexus.evolution2 import source_persist_plan as plan
from nexus.evolution2 import source_persist_request as lock
from nexus.tasks.acrobot_family import acrobot_default, acrobot_physics_key
from nexus.tasks.pendulum_family import pendulum_default, pendulum_physics_key
from nexus.world.data import assert_disjoint_seeds, collect_transitions

USAGE = lock.ROOT / "artifacts" / "research_session_e2_source_persist_7680_usage.json"
MANIFEST = lock.ROOT / "artifacts" / "evolution2_source_persist_7680.json"


def source_spec(family: str):
    if family == "pendulum":
        spec = pendulum_default()
        key = pendulum_physics_key(spec)
    elif family == "acrobot":
        spec = acrobot_default()
        key = acrobot_physics_key(spec)
    else:
        raise RuntimeError("unknown_family")
    if spec.task_id != plan.ALLOWED_TASK_IDS[family]:
        raise RuntimeError("unexpected_task_id")
    plan.refuse_closed_physics(family, key)
    return spec, key


def _arrays(ds, *, family: str, bundle: int, split: str, key) -> dict:
    return {
        "obs": np.asarray(ds.obs, dtype=np.float32),
        "action": np.asarray(ds.action, dtype=np.int64),
        "next_obs": np.asarray(ds.next_obs, dtype=np.float32),
        "terminated": np.asarray(ds.terminated, dtype=np.bool_),
        "env_seeds": np.asarray(ds.seed, dtype=np.int64),
        "family": np.asarray(family),
        "bundle": np.asarray(bundle),
        "split": np.asarray(split),
        "task_id": np.asarray(ds.task_id),
        "physics": np.asarray(key, dtype=np.float64),
    }


def run_persist(env_cap: int) -> dict:
    env_cap = int(env_cap)
    if not lock.persist_authorized(env_cap):
        lock.require_persist()
    if env_cap != lock.N3_SOURCE_STEPS:
        raise RuntimeError("only_7680_is_granted")
    plan.scientific_status(env_cap)
    record = lock.allocation_record()
    time_cap = float(record.get("time_cap_s") or 0)
    plan.refuse_duplicate_or_partial()
    started = time.perf_counter()
    cpu0 = time.process_time()
    charged = 0
    files = []
    grouped: dict[tuple[str, int], list] = {}
    for row in plan.seed_schedule(3):
        grouped.setdefault((row["family"], row["bundle"]), []).append(row)
    try:
        for (family, bundle), splits in grouped.items():
            spec, key = source_spec(family)
            datasets = {}
            for row in splits:
                if time_cap and time.perf_counter() - started >= time_cap:
                    raise RuntimeError("time_cap")
                if charged + int(row["n"]) > env_cap:
                    raise RuntimeError("env_cap")
                ds = collect_transitions(
                    spec,
                    n_transitions=int(row["n"]),
                    env_seeds=tuple(row["env_seeds"]),
                    base_seed=int(row["base_seed"]),
                    policy="random",
                )
                if int(ds.env_interactions) != int(row["n"]):
                    raise RuntimeError("interaction_mismatch")
                charged += int(ds.env_interactions)
                datasets[row["split"]] = ds
                digest = plan.atomic_write_npz(
                    lock.ROOT / row["path"],
                    _arrays(ds, family=family, bundle=bundle, split=row["split"], key=key),
                )
                files.append({**row, "sha256": digest, "physics": list(key)})
            assert_disjoint_seeds(datasets["train"], datasets["val"])
    except Exception:
        raise
    wall = time.perf_counter() - started
    cpu = time.process_time() - cpu0
    payload = {
        "scientific": False,
        "scientific_status": plan.SCIENTIFIC_STATUS,
        "collection": True,
        "env_steps": charged,
        "env_cap": env_cap,
        "time_cap_s": time_cap,
        "wall_s": wall,
        "cpu_s": cpu,
        "n_files": len(files),
        "files": files,
        "config_sha256": lock.LOCKED_CONFIG,
        "allocation_sha256": lock.file_sha256(lock.ALLOCATION),
        "hold_named": False,
        "models_trained": 0,
        "v2_confirmation": False,
        "claims_learning_to_learn": False,
        "is_agi": False,
        "scientific_ledger_preserved": [305.842, 3294.158],
    }
    usage = {
        "session_id": record.get("session_id"),
        "env_steps": charged,
        "wall_s": wall,
        "cpu_s": cpu,
        "h16_scientific_ledger_untouched": True,
        "consumed_total_s": wall,
    }
    plan.write_manifest(MANIFEST, payload)
    plan.write_manifest(USAGE, usage)
    return payload
