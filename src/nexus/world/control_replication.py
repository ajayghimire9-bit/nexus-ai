"""Independent decoder replications of the H=16 context controller.

The statistical unit is one trained decoder. Five student seeds, tasks, and
episodes are averaged inside that decoder. The original three history
checkpoints can be re-scored on new episodes, and they are not new seeds.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import (
    PENDULUM_MAX_STEPS,
    pendulum_context_train,
    pendulum_control_replication,
    pendulum_latent_confirmation,
    pendulum_physics_key,
)
from nexus.tasks.spec import make_task_env
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_model import ContextWorldModel, context_optimizer, make_context_schedule, run_context_updates
from nexus.world.context_optimization import _sha256
from nexus.world.context_pilot import _collect, _fit_rms, _split_hash, prefix_hash
from nexus.world.data import TransitionDataset, concat_datasets
from nexus.world.direct_latent import fit_latent, lock_network, vector_hash
from nexus.world.frozen_dynamics import (
    freeze_shared_dynamics,
    fresh_audit_seeds,
    history_optimizer,
    load_context_checkpoint,
    load_frozen_config,
    load_mlp_checkpoint,
    planned_env_seeds,
    run_history_updates,
    source_split_seeds,
)
from nexus.world.latent_generalization import (
    STUDENT_LR,
    TEACHER_LR,
    TEACHER_UPDATES,
    _collect_checked,
    _fit_teacher,
    assert_checkpoint_hashes,
    decoder_digest,
    load_generalization_config,
    train_pairs,
)
from nexus.world.latent_control import (
    _fresh_decoder,
    _install_encoder,
    control_env_seeds,
    load_control_config,
    verify_student_checkpoints,
)
from nexus.world.latent_generalization_confirmation import (
    _occupied_physics,
    assert_confirmation_physics,
    confirmation_seed_groups,
    load_confirmation_config,
)
from nexus.world.planning import InferenceCounter, mpc_for_model
from nexus.world.protocol import V089C_SOURCE_COLLECT_SEED, V089C_TRAIN_SEED
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/control_replication.yaml")
PROTOCOL_PATH = Path("docs/NEXUS_CONTROL_REPLICATION.md")
CHECKPOINT_DIR = Path("artifacts/control_replication_checkpoints")
MANIFEST_PATH = CHECKPOINT_DIR / "manifest.json"
ORIGINAL_SEEDS = (0, 1, 2)
NEW_SEEDS = (3, 4, 5, 6, 7, 8, 9)
TARGET_DECODERS = 10
PRIMARY_CONTROLS = ("zero", "encoder")
SHARED_LABELS = ("zero", "global", "encoder", "teacher")
STUDENT_LABELS = ("student", "baseline")
PROTECTED_CHECKPOINT_DIRS = (
    "frozen_dynamics_checkpoints",
    "context_optimization_checkpoints",
    "latent_generalization_confirmation_checkpoints",
)


def load_replication_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("replication config must be a mapping")
    expected = _locked_config()
    if cfg != expected:
        missing = sorted(set(expected) - set(cfg))
        extra = sorted(set(cfg) - set(expected))
        drifted = sorted(key for key in expected if key in cfg and cfg[key] != expected[key])
        raise ValueError(f"replication config drifted; missing={missing} extra={extra} drifted={drifted}")
    if int(cfg["target_decoders"]) != TARGET_DECODERS:
        raise ValueError("the registered decoder count drifted")
    if list(cfg["original_seeds"]) != list(ORIGINAL_SEEDS) or list(cfg["new_seeds"]) != list(NEW_SEEDS):
        raise ValueError("original and new decoder seeds drifted")
    if float(cfg["minimum_effect"]) != 25 or int(cfg["horizon"]) != 16 or int(cfg["n_candidates"]) != 16:
        raise ValueError("control recipe drifted")
    return cfg


def _locked_config() -> dict[str, Any]:
    gen = load_generalization_config()
    conf = load_confirmation_config()
    control = load_control_config()
    frozen = load_frozen_config()
    fresh = pendulum_control_replication()
    return {
        "protocol_id": "control_replication_v1",
        "starting_sha": "5889c3c4fabec814fb83b07607139adfea0b9639",
        "is_agi": False,
        "is_learning_to_learn": False,
        "retune_on_return": False,
        "h_replication": (
            "Across ten independently trained decoders, the 584-parameter student raises H=16 "
            "return by at least 25 points above zero context and above the frozen encoder, on "
            "new episodes of the previous physics and on a disjoint physics set."
        ),
        "target_decoders": TARGET_DECODERS,
        "original_seeds": list(ORIGINAL_SEEDS),
        "new_seeds": list(NEW_SEEDS),
        "horizon": 16,
        "n_candidates": 16,
        "chunk_size": 4,
        "enforce_time_budget": False,
        "episodes": 4,
        "support_budget": 128,
        "n_student_seeds": 5,
        "student_learning_rate": STUDENT_LR,
        "student_epochs": 200,
        "teacher_learning_rate": TEACHER_LR,
        "teacher_updates": TEACHER_UPDATES,
        "global_learning_rate": 0.01,
        "global_updates": 300,
        "context_updates": int(frozen["prior_context_updates"]),
        "history_updates": 1000,
        "context_lr": float(frozen["lr"]),
        "batch": int(frozen["batch"]),
        "empty_prob": float(frozen["empty_prob"]),
        "source_per_task": int(frozen["source_per_task"]),
        "n_source_tasks": 8,
        "n_parameters": 584,
        "n_decoder_parameters": 3748,
        "minimum_effect": 25,
        "catastrophic_return": -1500,
        "primary_unit": "decoder",
        "time_limit_s": 9000,
        "previous_control_eval_env0": int(control["control_eval_env0"]),
        "replication_eval_env0": 120000,
        "fresh_support_env0": 124000,
        "fresh_support_base": 280000,
        "fresh_eval_env0": 126000,
        "confirm_support_env0": int(conf["confirm_support_env0"]),
        "confirm_support_base": int(conf["confirm_support_base"]),
        "confirm_split_hash": str(conf["confirm_split_hash"]),
        "fresh_split_hash": _split_hash(fresh),
        "fresh_task_ids": [spec.task_id for spec in fresh],
        "fresh_physics": [list(pendulum_physics_key(spec)) for spec in fresh],
        "replication_task_ids": list(conf["confirm_task_ids"]),
        "replication_physics": [list(row) for row in conf["confirm_physics"]],
        "broad_h0_env0": int(gen["broad_h0_env0"]),
        "broad_h0_base": int(gen["broad_h0_base"]),
        "broad_h1_env0": int(gen["broad_h1_env0"]),
        "broad_h1_base": int(gen["broad_h1_base"]),
        "baseline_support_env0": int(gen["baseline_support_env0"]),
        "baseline_support_base": int(gen["baseline_support_base"]),
        "development_artifact": "artifacts/latent_generalization_dev.json",
        "development_artifact_sha256": "c8438e09c383fc669b3b9f4cad275725d7daa9f49d2616083f256cefa1f24aba",
        "confirmation_artifact": str(control["confirmation_artifact"]),
        "confirmation_artifact_sha256": str(control["confirmation_artifact_sha256"]),
        "control_artifact": "artifacts/latent_control.json",
        "control_artifact_sha256": "ce04ce90f368a6d0ecd45b42cce881e045619fd642bfe39d13c8c32216c5e9b4",
        "parent_checkpoints": list(gen["parent_checkpoints"]),
        "mlp_checkpoints": list(control["mlp_checkpoints"]),
    }


def assert_protocol_frozen(protocol_path: str | Path, cfg: dict[str, Any]) -> None:
    path = Path(protocol_path)
    if not path.is_file():
        raise RuntimeError("replication is blocked until the protocol document is saved")
    text = path.read_text()
    start = text.find("<!-- protocol-lock")
    end = text.find("-->", start)
    if start < 0 or end < 0:
        raise RuntimeError("replication is blocked because the protocol lock block is missing")
    locked: dict[str, str] = {}
    for line in text[start:end].splitlines():
        if ":" not in line or line.strip().startswith("<!--"):
            continue
        key, value = line.split(":", 1)
        locked[key.strip()] = value.strip()
    required = {
        "target_decoders": str(int(cfg["target_decoders"])),
        "original_seeds": ",".join(str(int(seed)) for seed in cfg["original_seeds"]),
        "new_seeds": ",".join(str(int(seed)) for seed in cfg["new_seeds"]),
        "horizon": str(int(cfg["horizon"])),
        "n_candidates": str(int(cfg["n_candidates"])),
        "episodes": str(int(cfg["episodes"])),
        "support_budget": str(int(cfg["support_budget"])),
        "student_lr": f"{float(cfg['student_learning_rate']):.2f}",
        "student_epochs": str(int(cfg["student_epochs"])),
        "teacher_lr": f"{float(cfg['teacher_learning_rate']):.1f}",
        "teacher_updates": str(int(cfg["teacher_updates"])),
        "minimum_effect": str(int(cfg["minimum_effect"])),
        "catastrophic_return": str(int(cfg["catastrophic_return"])),
        "replication_eval_env0": str(int(cfg["replication_eval_env0"])),
        "fresh_eval_env0": str(int(cfg["fresh_eval_env0"])),
        "fresh_support_env0": str(int(cfg["fresh_support_env0"])),
        "fresh_split_hash": str(cfg["fresh_split_hash"]),
        "confirm_split_hash": str(cfg["confirm_split_hash"]),
        "primary_unit": str(cfg["primary_unit"]),
        "time_limit_s": str(int(cfg["time_limit_s"])),
        "n_parameters": str(int(cfg["n_parameters"])),
        "n_decoder_parameters": str(int(cfg["n_decoder_parameters"])),
        "context_updates": str(int(cfg["context_updates"])),
        "history_updates": str(int(cfg["history_updates"])),
    }
    for key, value in required.items():
        if locked.get(key) != value:
            raise RuntimeError(f"replication is blocked because protocol {key}={locked.get(key)!r} is not {value!r}")


def cohort(seed: int) -> str:
    if int(seed) in ORIGINAL_SEEDS:
        return "original"
    if int(seed) in NEW_SEEDS:
        return "new"
    raise ValueError(f"decoder seed {seed} is outside the registered replication")


def source_env0(seed: int, task_index: int) -> int:
    return 1000 + 100 * int(seed) + 10 * int(task_index)


def source_base(seed: int, task_index: int) -> int:
    return int(V089C_SOURCE_COLLECT_SEED) + 50 * int(seed) + 9 * int(task_index)


def model_init_seed(seed: int) -> int:
    return int(V089C_TRAIN_SEED) + 17 * int(seed)


def schedule_seed(seed: int) -> int:
    return int(V089C_TRAIN_SEED) + 31 * int(seed)


def student_rng_seed(decoder: int, student: int) -> int:
    return 30_000 + int(decoder) * 100 + int(student)


def episode_seeds(env0: int, n_tasks: int, episodes: int) -> set[int]:
    seeds: set[int] = set()
    for index in range(int(n_tasks)):
        base = int(env0) + 10 * index
        for episode in range(int(episodes)):
            seeds.add(base + episode)
    return seeds


def replication_seed_groups(cfg: dict[str, Any]) -> dict[str, set[int]]:
    groups = confirmation_seed_groups(load_confirmation_config())
    groups["previous_control"] = control_env_seeds(load_control_config())
    frozen = load_frozen_config()
    for name, seeds in source_split_seeds(frozen).items():
        groups[f"source_{name}"] = seeds
    for name, seeds in fresh_audit_seeds(frozen).items():
        groups[f"frozen_{name}"] = seeds
    new_train: set[int] = set()
    for seed in cfg["new_seeds"]:
        for task_index in range(int(cfg["n_source_tasks"])):
            new_train |= planned_env_seeds(int(cfg["source_per_task"]), source_env0(int(seed), task_index))
    groups["new_decoder_train"] = new_train
    groups["replication_eval"] = episode_seeds(int(cfg["replication_eval_env0"]), len(cfg["replication_task_ids"]), int(cfg["episodes"]))
    groups["fresh_eval"] = episode_seeds(int(cfg["fresh_eval_env0"]), len(cfg["fresh_task_ids"]), int(cfg["episodes"]))
    fresh_support: set[int] = set()
    for index in range(len(cfg["fresh_task_ids"])):
        fresh_support |= planned_env_seeds(int(cfg["support_budget"]), int(cfg["fresh_support_env0"]) + 10 * index)
    groups["fresh_support"] = fresh_support
    return groups


def assert_replication_seeds(cfg: dict[str, Any]) -> None:
    """New collect and episode seeds must miss every earlier split. Prior splits are not re-checked."""
    if int(cfg["previous_control_eval_env0"]) != 110000:
        raise ValueError("the closed control seed block drifted")
    named = replication_seed_groups(cfg)
    fresh_names = ("new_decoder_train", "replication_eval", "fresh_eval", "fresh_support")
    occupied: set[int] = set()
    for name, seeds in named.items():
        if name not in fresh_names:
            occupied |= seeds
    for name in fresh_names:
        overlap = named[name] & occupied
        if overlap:
            raise ValueError(f"{name} overlaps an earlier collect: {sorted(overlap)[:8]}")
    for i, left in enumerate(fresh_names):
        for right in fresh_names[i + 1 :]:
            overlap = named[left] & named[right]
            if overlap:
                raise ValueError(f"collect seeds overlap between {left} and {right}: {sorted(overlap)[:8]}")
    if named["replication_eval"] & named["previous_control"] or named["fresh_eval"] & named["previous_control"]:
        raise ValueError("replication reused a previous control episode seed")


def assert_fresh_physics(cfg: dict[str, Any]) -> tuple[Any, ...]:
    specs = pendulum_control_replication()
    if _split_hash(specs) != cfg["fresh_split_hash"]:
        raise RuntimeError("fresh physics hash drifted")
    if [spec.task_id for spec in specs] != list(cfg["fresh_task_ids"]):
        raise RuntimeError("fresh task ids drifted")
    if [list(pendulum_physics_key(spec)) for spec in specs] != cfg["fresh_physics"]:
        raise RuntimeError("fresh physics values drifted")
    occupied = {pendulum_physics_key(spec) for spec in _occupied_physics()}
    occupied |= {pendulum_physics_key(spec) for spec in pendulum_latent_confirmation()}
    fresh = [pendulum_physics_key(spec) for spec in specs]
    replication = [pendulum_physics_key(spec) for spec in pendulum_latent_confirmation()]
    if len(fresh) != len(set(fresh)) or occupied.intersection(fresh) or set(fresh) & set(replication):
        raise RuntimeError("fresh physics collide with a previous Pendulum split")
    return specs


def assert_writable_checkpoint(path: str | Path) -> Path:
    target = Path(path)
    for name in PROTECTED_CHECKPOINT_DIRS:
        if name in target.parts:
            raise RuntimeError(f"refusing to write a prior checkpoint: {target}")
    return target


def _weights_equal(left: Any, right: Any) -> float:
    worst = 0.0
    for name, src, dst in (
        ("encoder", left.encoder.state_dict(), right.encoder.state_dict()),
        ("net", left.net.state_dict(), right.net.state_dict()),
    ):
        if src.keys() != dst.keys():
            raise RuntimeError(f"{name} keys differ")
        for key in src:
            gap = float((src[key].detach() - dst[key].detach()).abs().max().item())
            worst = max(worst, gap)
    for key in ("mean", "var", "count"):
        gap = float(np.max(np.abs(np.asarray(left.obs_rms.state_dict()[key]) - np.asarray(right.obs_rms.state_dict()[key]))))
        worst = max(worst, gap)
    return worst


def train_history_decoder(seed: int, cfg: dict[str, Any]) -> tuple[ContextWorldModel, torch.Tensor, list[str]]:
    """Joint context training, then encoder and FiLM updates, then the locked global fit."""
    if int(cfg["context_updates"]) != 3000 or int(cfg["history_updates"]) != 1000:
        raise RuntimeError("decoder update budget drifted from the history checkpoints")
    if float(cfg["context_lr"]) != 0.001 or int(cfg["batch"]) != 64 or float(cfg["empty_prob"]) != 0.2:
        raise RuntimeError("decoder optimizer recipe drifted")
    specs = pendulum_context_train()
    if len(specs) != int(cfg["n_source_tasks"]):
        raise RuntimeError("source task count drifted")
    tasks = [
        _collect(spec, int(cfg["source_per_task"]), env0=source_env0(seed, index), base=source_base(seed, index))
        for index, spec in enumerate(specs)
    ]
    hashes = [prefix_hash(ds, len(ds)) for ds in tasks]
    rms = _fit_rms(tasks)
    schedule = make_context_schedule(
        tasks,
        updates=int(cfg["context_updates"]),
        seed=schedule_seed(seed),
        batch=int(cfg["batch"]),
        empty_prob=float(cfg["empty_prob"]),
    )
    model = ContextWorldModel.create(3, 3, seed=model_init_seed(seed))
    model.copy_rms(rms)
    opt = context_optimizer(model, lr=float(cfg["context_lr"]))
    run_context_updates(model, opt, tasks, schedule, support_mode="fixed")
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    staging = CHECKPOINT_DIR / f".seed{int(seed)}_context_staging.pt"
    assert_writable_checkpoint(staging)
    torch.save({"encoder": model.encoder.state_dict(), "net": model.net.state_dict(), "obs_rms": rms.state_dict()}, staging)
    loaded = load_context_checkpoint(staging)
    staging.unlink(missing_ok=True)
    history = loaded.clone_trainable()
    freeze_shared_dynamics(history)
    rows = make_context_schedule(
        tasks,
        updates=int(cfg["history_updates"]),
        seed=schedule_seed(seed),
        batch=int(cfg["batch"]),
        empty_prob=float(cfg["empty_prob"]),
    )
    run_history_updates(history, history_optimizer(history, lr=float(cfg["context_lr"])), tasks, rows)
    lock_network(history)
    for param in list(history.encoder.parameters()) + list(history.net.parameters()):
        param.grad = None
    pooled = concat_datasets(*tasks, task_id="context_source_pool")
    fitted = fit_latent(
        history,
        pooled.obs,
        pooled.action,
        pooled.next_obs,
        pooled.terminated,
        torch.zeros(history.context_dim()),
        lr=float(cfg["global_learning_rate"]),
        updates=int(cfg["global_updates"]),
        snapshot_at=(int(cfg["global_updates"]),),
    )
    return history, fitted["final"].detach().clone(), hashes


def verify_original_recipe(cfg: dict[str, Any], seeds: list[int] | None = None) -> list[dict[str, Any]]:
    """Retrain the original seeds in memory and compare them with the saved checkpoints."""
    parents = {int(row["seed"]): row for row in cfg["parent_checkpoints"]}
    reports = []
    for seed in ORIGINAL_SEEDS if seeds is None else seeds:
        trained, global_z, hashes = train_history_decoder(int(seed), cfg)
        expected = load_context_checkpoint(Path(parents[int(seed)]["path"]))
        gap = _weights_equal(trained, expected)
        if gap != 0.0:
            raise RuntimeError(f"decoder recipe did not reproduce seed {seed}; max abs diff {gap}")
        if vector_hash(global_z) != parents[int(seed)]["global_vector_sha256"]:
            raise RuntimeError(f"global latent recipe did not reproduce seed {seed}")
        reports.append({"seed": int(seed), "cohort": "original", "weight_gap": gap, "train_hashes": hashes, "reproduced": True})
        print(f"replication recipe reproduced original decoder {seed}", flush=True)
    return reports


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        return {"decoders": {}}
    payload = yaml.safe_load(MANIFEST_PATH.read_text()) if MANIFEST_PATH.suffix == ".yaml" else __import__("json").loads(MANIFEST_PATH.read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get("decoders"), dict):
        raise RuntimeError("checkpoint manifest is unreadable; refusing to overwrite new checkpoints")
    return payload


def _write_manifest(manifest: dict[str, Any]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(dumps_strict(manifest))


def _require_hash(path: Path, expected: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    got = _sha256(path)
    if got != expected:
        raise RuntimeError(f"checkpoint hash mismatch for {path}; refusing to replace it")


def save_new_decoder(seed: int, model: ContextWorldModel, global_z: torch.Tensor, train_hashes: list[str]) -> dict[str, Any]:
    model_path = assert_writable_checkpoint(CHECKPOINT_DIR / f"d{int(seed)}_history_u1000.pt")
    global_path = assert_writable_checkpoint(CHECKPOINT_DIR / f"d{int(seed)}_global.pt")
    manifest = _load_manifest()
    row = manifest["decoders"].get(str(int(seed)))
    if model_path.is_file() or global_path.is_file():
        if not row:
            raise RuntimeError(f"decoder {seed} files exist without a manifest; refusing to overwrite them")
        _require_hash(model_path, row["model_sha256"])
        _require_hash(global_path, row["global_sha256"])
        return row
    torch.save(
        {
            "encoder": {key: value.detach().cpu().clone() for key, value in model.encoder.state_dict().items()},
            "net": {key: value.detach().cpu().clone() for key, value in model.net.state_dict().items()},
            "obs_rms": model.obs_rms.state_dict(),
            "seed": int(seed),
            "cohort": "new",
            "kind": "history",
            "updates": 1000,
            "parent_updates": 3000,
        },
        model_path,
    )
    torch.save({"vector": global_z.detach().cpu().clone(), "vector_sha256": vector_hash(global_z)}, global_path)
    saved = {
        "seed": int(seed),
        "cohort": "new",
        "model_path": str(model_path),
        "model_sha256": _sha256(model_path),
        "global_path": str(global_path),
        "global_sha256": _sha256(global_path),
        "global_vector_sha256": vector_hash(global_z),
        "train_hashes": train_hashes,
        "students": {},
    }
    manifest["decoders"][str(int(seed))] = saved
    _write_manifest(manifest)
    return saved


def _encoder_path(seed: int, student: int, kind: str) -> Path:
    return assert_writable_checkpoint(CHECKPOINT_DIR / f"d{int(seed)}_s{int(student)}_{kind}_e200.pt")


def save_student(seed: int, student: int, kind: str, state: dict[str, torch.Tensor]) -> dict[str, Any]:
    path = _encoder_path(seed, student, kind)
    manifest = _load_manifest()
    row = manifest["decoders"].setdefault(str(int(seed)), {"students": {}})
    students = row.setdefault("students", {})
    slot = students.get(f"{int(student)}:{kind}")
    if path.is_file():
        if not slot:
            raise RuntimeError(f"{path} exists without a manifest hash; refusing to overwrite it")
        _require_hash(path, slot["sha256"])
        return slot
    torch.save({key: value.detach().cpu().clone() for key, value in state.items()}, path)
    blob = torch.load(path, map_location="cpu", weights_only=False)
    count = int(sum(tensor.numel() for tensor in blob.values()))
    if count != 584:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"student checkpoint has {count} parameters")
    slot = {"seed": int(seed), "student": int(student), "kind": kind, "epoch": 200, "path": str(path), "sha256": _sha256(path), "parameters": count}
    students[f"{int(student)}:{kind}"] = slot
    _write_manifest(manifest)
    return slot


def train_new_students(seed: int, cfg: dict[str, Any], broad: list[TransitionDataset], baseline: list[TransitionDataset]) -> list[dict[str, Any]]:
    row = _load_manifest()["decoders"][str(int(seed))]
    model, digest = _fresh_decoder(row["model_path"], cfg)
    global_blob = torch.load(row["global_path"], map_location="cpu", weights_only=False)
    global_z = global_blob["vector"]
    if vector_hash(global_z) != row["global_vector_sha256"]:
        raise RuntimeError(f"stored global vector hash mismatch for decoder {seed}")
    init_state = {key: value.detach().cpu().clone() for key, value in model.encoder.state_dict().items()}
    broad_teachers = []
    for support in broad:
        vector = _fit_teacher(model, support, global_z)
        if decoder_digest(model) != digest:
            raise RuntimeError("teacher fit changed the new decoder")
        broad_teachers.append(vector.detach().clone())
    baseline_teachers = []
    for support in baseline:
        vector = _fit_teacher(model, support, global_z)
        if decoder_digest(model) != digest:
            raise RuntimeError("baseline teacher fit changed the new decoder")
        baseline_teachers.append(vector.detach().clone())
    written = []
    for student in range(int(cfg["n_student_seeds"])):
        rng_seed = student_rng_seed(seed, student)
        broad_snaps, _l2, _grad = train_pairs(
            model,
            broad,
            broad_teachers,
            epochs=int(cfg["student_epochs"]),
            checkpoints=[int(cfg["student_epochs"])],
            lr=float(cfg["student_learning_rate"]),
            seed=rng_seed,
            init_state=init_state,
            decoder_before=digest,
            budget=int(cfg["support_budget"]),
        )
        base_snaps, _l2, _grad = train_pairs(
            model,
            baseline,
            baseline_teachers,
            epochs=int(cfg["student_epochs"]),
            checkpoints=[int(cfg["student_epochs"])],
            lr=float(cfg["student_learning_rate"]),
            seed=rng_seed,
            init_state=init_state,
            decoder_before=digest,
            budget=int(cfg["support_budget"]),
        )
        written.append(save_student(seed, student, "broad", broad_snaps[int(cfg["student_epochs"])]))
        written.append(save_student(seed, student, "baseline", base_snaps[int(cfg["student_epochs"])]))
        print(f"replication trained decoder {seed} student {student}", flush=True)
    return written


def _matching(records: list[dict[str, Any]], **filters: Any) -> list[dict[str, Any]]:
    out = []
    for row in records:
        if all(row.get(key) == value for key, value in filters.items()):
            out.append(row)
    return out


def decoder_level_deltas(records: list[dict[str, Any]], control: str, split: str, decoders: list[int]) -> list[float]:
    """One paired difference per decoder. Student seeds are inside the mean."""
    deltas = []
    for decoder in decoders:
        student = _matching(records, split=split, decoder=int(decoder), label="student")
        ctrl = _matching(records, split=split, decoder=int(decoder), label=control)
        if not student or not ctrl:
            deltas.append(float("nan"))
            continue
        deltas.append(float(np.mean([row["mean_return"] for row in student]) - np.mean([row["mean_return"] for row in ctrl])))
    return deltas


def replication_gate(
    zero_deltas: list[float],
    encoder_deltas: list[float],
    minimum_effect: float,
    required_n: int,
) -> tuple[bool, dict[str, Any]]:
    """Pass only at the pre-registered decoder count. A shorter sample cannot pass."""
    report: dict[str, Any] = {}
    ok = len(zero_deltas) == int(required_n) and len(encoder_deltas) == int(required_n)
    for name, values in (("zero", zero_deltas), ("encoder", encoder_deltas)):
        finite = len(values) == int(required_n) and all(np.isfinite(value) for value in values)
        interval = seed_level_ci([float(value) for value in values]) if finite else {
            "n": len(values),
            "mean": None,
            "lo": None,
            "hi": None,
            "se": None,
            "interval": "student_t_95",
        }
        passed = bool(
            finite
            and float(interval["mean"]) >= float(minimum_effect)
            and float(interval["lo"]) > 0.0
        )
        stronger = bool(finite and float(interval["lo"]) > float(minimum_effect))
        report[name] = {
            "per_decoder": [None if not np.isfinite(value) else float(value) for value in values],
            "interval": interval,
            "pass": passed,
            "lower_bound_exceeds_margin": stronger,
            "sign": "student_minus_control",
        }
        ok = ok and passed
    return ok, report


def variance_split(records: list[dict[str, Any]], split: str, decoders: list[int]) -> dict[str, Any]:
    """Decoder SD of paired means versus the RMS of within-decoder episode SDs."""
    decoder_means = []
    within = []
    for decoder in decoders:
        episode_deltas = []
        tasks = sorted({row["task"] for row in records if row.get("split") == split and row.get("decoder") == int(decoder)})
        for task in tasks:
            students = _matching(records, split=split, decoder=int(decoder), label="student", task=task)
            zeros = _matching(records, split=split, decoder=int(decoder), label="zero", task=task)
            if not students or len(zeros) != 1:
                continue
            zero_returns = zeros[0]["returns"]
            for episode in range(len(zero_returns)):
                stacked = [float(row["returns"][episode]) for row in students if episode < len(row["returns"])]
                if len(stacked) != len(students):
                    continue
                episode_deltas.append(float(np.mean(stacked) - float(zero_returns[episode])))
        if not episode_deltas:
            continue
        decoder_means.append(float(np.mean(episode_deltas)))
        if len(episode_deltas) >= 2:
            within.append(float(np.std(episode_deltas, ddof=1)))
    decoder_sd = float(np.std(decoder_means, ddof=1)) if len(decoder_means) >= 2 else None
    episode_sd = float(np.sqrt(np.mean(np.square(within)))) if within else None
    dominates = None
    if decoder_sd is not None and episode_sd is not None:
        if abs(decoder_sd - episode_sd) <= 1e-9:
            dominates = "tied"
        elif decoder_sd > episode_sd:
            dominates = "decoder"
        else:
            dominates = "episode"
    return {
        "split": split,
        "n_decoders": len(decoder_means),
        "decoder_sd": decoder_sd,
        "episode_sd": episode_sd,
        "dominates": dominates,
        "note": "Episode residuals share a decoder. They are not additional model replications.",
    }


def _rank(values: list[float]) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(array.size, dtype=np.float64)
    cursor = 0
    while cursor < array.size:
        stop = cursor
        while stop + 1 < array.size and array[order[stop + 1]] == array[order[cursor]]:
            stop += 1
        average = 0.5 * (cursor + stop)
        for index in range(cursor, stop + 1):
            ranks[order[index]] = average
        cursor = stop + 1
    return ranks


def _spearman(left: list[float], right: list[float]) -> float:
    ranked_left = _rank(left)
    ranked_right = _rank(right)
    if float(np.std(ranked_left)) == 0.0 or float(np.std(ranked_right)) == 0.0:
        return 1.0 if np.allclose(ranked_left, ranked_right) else 0.0
    return float(np.corrcoef(ranked_left, ranked_right)[0, 1])


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        return None
    if float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _mean_field(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows if row.get(key) is not None and np.isfinite(row[key])]
    return float(np.mean(values)) if values else float("nan")


def prediction_deltas(records: list[dict[str, Any]], split: str, decoders: list[int]) -> list[float]:
    """Positive means the student has lower visited angular-velocity error than zero."""
    deltas = []
    for decoder in decoders:
        student = _matching(records, split=split, decoder=int(decoder), label="student")
        zero = _matching(records, split=split, decoder=int(decoder), label="zero")
        if not student or not zero:
            deltas.append(float("nan"))
            continue
        deltas.append(_mean_field(zero, "visited_angvel_mae") - _mean_field(student, "visited_angvel_mae"))
    return deltas


def action_diagnostics(records: list[dict[str, Any]], split: str, decoders: list[int]) -> dict[str, Any]:
    first_rates = []
    path_rates = []
    rank_gaps = []
    short_gaps = []
    for decoder in decoders:
        tasks = sorted({row["task"] for row in _matching(records, split=split, decoder=int(decoder), label="zero")})
        decoder_first = []
        decoder_path = []
        decoder_rank = []
        decoder_short = []
        for task in tasks:
            zeros = _matching(records, split=split, decoder=int(decoder), label="zero", task=task)
            students = _matching(records, split=split, decoder=int(decoder), label="student", task=task)
            if len(zeros) != 1 or not students:
                continue
            zero = zeros[0]
            for student in students:
                first = [
                    float(int(left) == int(right))
                    for left, right in zip(student["first_actions"], zero["first_actions"])
                ]
                decoder_first.extend(first)
                code_s = str(student.get("action_code") or "")
                code_z = str(zero.get("action_code") or "")
                if code_s and len(code_s) == len(code_z):
                    decoder_path.append(float(np.mean([left == right for left, right in zip(code_s, code_z)])))
                scores = [
                    _spearman(left, right)
                    for left, right in zip(student.get("first_scores") or [], zero.get("first_scores") or [])
                    if len(left) == len(right) and len(left) > 1
                ]
                if scores:
                    decoder_rank.append(float(1.0 - np.mean(scores)))
            decoder_short.append(_mean_field(students, "short_horizon_return") - float(zero["short_horizon_return"]))
        if decoder_first:
            first_rates.append(float(np.mean(decoder_first)))
        if decoder_path:
            path_rates.append(float(np.mean(decoder_path)))
        if decoder_rank:
            rank_gaps.append(float(np.mean(decoder_rank)))
        if decoder_short:
            short_gaps.append(float(np.mean(decoder_short)))
    return {
        "split": split,
        "first_action_agreement": float(np.mean(first_rates)) if first_rates else None,
        "path_action_agreement": float(np.mean(path_rates)) if path_rates else None,
        "path_agreement_is_same_state": False,
        "first_decision_rank_disagreement": float(np.mean(rank_gaps)) if rank_gaps else None,
        "short_horizon_student_minus_zero": float(np.mean(short_gaps)) if short_gaps else None,
        "n_decoders": len(first_rates),
    }


def recommend_replication(
    *,
    complete: bool,
    replication_pass: bool,
    fresh_pass: bool,
    prediction_pass: bool,
) -> str:
    if not complete:
        return "incomplete"
    if replication_pass and fresh_pass:
        return "cross_task_adaptation_efficiency"
    if replication_pass and not fresh_pass:
        return "negative_transfer"
    if prediction_pass:
        return "planner_sensitivity"
    return "uncertain"


def _evaluate_mpc(spec: Any, model: Any, eval_seed: int, episodes: int, catastrophic_at: float) -> dict[str, Any]:
    counter = InferenceCounter(model)
    planner = mpc_for_model(model, seed=0, inference=counter, enforce_time_budget=False)
    if int(planner.horizon) != 16 or int(planner.n_candidates) != 16 or int(planner.chunk_size) != 4 or planner.enforce_time_budget:
        raise RuntimeError("planner recipe is not the locked H=16, 16-candidate pendulum controller")
    env = make_task_env(spec, seed=int(eval_seed))
    returns: list[float] = []
    first_actions: list[int] = []
    first_scores: list[list[float]] = []
    codes: list[str] = []
    short_values: list[float] = []
    obs_all: list[np.ndarray] = []
    act_all: list[int] = []
    next_all: list[np.ndarray] = []
    plan_ms: list[float] = []
    predicted: list[float] = []
    interactions = 0
    try:
        for episode in range(int(episodes)):
            planner.reset_episode(int(eval_seed) + 1000 * int(episode))
            obs, _info = env.reset(seed=int(eval_seed) + int(episode))
            total = 0.0
            rewards: list[float] = []
            actions: list[int] = []
            first = True
            steps = 0
            done = False
            while not done and steps < PENDULUM_MAX_STEPS:
                current = np.asarray(obs, dtype=np.float32).reshape(-1)
                action, meta = planner.act(current)
                if int(meta["n_scored"]) != 16 or len(meta["candidate_scores"]) != 16:
                    raise RuntimeError("a controller did not score 16 candidate sequences")
                nxt, reward, terminated, truncated, _info = env.step(int(action))
                if first:
                    first_actions.append(int(action))
                    first_scores.append([float(value) for value in meta["candidate_scores"]])
                    first = False
                actions.append(int(action))
                rewards.append(float(reward))
                obs_all.append(current)
                act_all.append(int(action))
                next_all.append(np.asarray(nxt, dtype=np.float32).reshape(-1))
                plan_ms.append(float(meta["plan_ms"]))
                predicted.append(float(meta["best_score"]))
                obs = nxt
                total += float(reward)
                steps += 1
                interactions += 1
                done = bool(terminated or truncated)
            returns.append(total)
            codes.append("".join(str(action) for action in actions))
            reward_array = np.asarray(rewards, dtype=np.float64)
            windows = [float(reward_array[start : start + 16].sum()) for start in range(reward_array.size)]
            short_values.append(float(np.mean(windows)) if windows else float("nan"))
    finally:
        env.close()
    if obs_all:
        pred, _term = model.step(np.stack(obs_all), np.asarray(act_all, dtype=np.int64))
        error = np.asarray(pred, dtype=np.float64) - np.stack(next_all)
        visited_mae = float(np.mean(np.abs(error)))
        visited_angvel = float(np.mean(np.abs(error[:, 2])))
    else:
        visited_mae = float("nan")
        visited_angvel = float("nan")
    catastrophic = [bool(value <= float(catastrophic_at)) for value in returns]
    return {
        "mean_return": float(np.mean(returns)) if returns else float("nan"),
        "returns": returns,
        "catastrophic_rate": float(np.mean(catastrophic)) if catastrophic else float("nan"),
        "env_interactions": int(interactions),
        "mean_plan_ms": float(np.mean(plan_ms)) if plan_ms else float("nan"),
        "mean_predicted_score": float(np.mean(predicted)) if predicted else float("nan"),
        "short_horizon_return": float(np.mean(short_values)) if short_values else float("nan"),
        "visited_mae": visited_mae,
        "visited_angvel_mae": visited_angvel,
        "first_actions": first_actions,
        "first_scores": first_scores,
        "action_code": "".join(codes),
        "model_states": int(counter.states),
        "n_decisions": int(sum(len(code) for code in codes)),
        "eval_seed": int(eval_seed),
    }


def _expected_keys(cfg: dict[str, Any], split: str, tasks: list[str], decoders: list[int]) -> set[tuple[Any, ...]]:
    keys = set()
    for decoder in decoders:
        for task in tasks:
            for student in range(int(cfg["n_student_seeds"])):
                for label in STUDENT_LABELS:
                    keys.add((split, int(decoder), student, task, label))
            for label in SHARED_LABELS:
                keys.add((split, int(decoder), None, task, label))
    for row in cfg["mlp_checkpoints"]:
        for task in tasks:
            keys.add((split, None, None, task, f"mlp{int(row['seed'])}"))
    return keys


def _have_keys(records: list[dict[str, Any]]) -> set[tuple[Any, ...]]:
    keys = set()
    for row in records:
        label = row["label"] if row["label"] != "mlp" else f"mlp{int(row.get('mlp_seed'))}"
        keys.add((row["split"], row.get("decoder"), row.get("student"), row["task"], label))
    return keys


def _cell_done(records: list[dict[str, Any]], split: str, decoder: int | None, student: int | None, task: str, label: str) -> bool:
    key_label = label if label != "mlp" else label
    return any(
        row["split"] == split
        and row.get("decoder") == decoder
        and row.get("student") == student
        and row["task"] == task
        and row["label"] == key_label
        for row in records
    )


def _collect_named(spec: Any, n: int, env0: int, base: int, forbidden: set[str]) -> TransitionDataset:
    return _collect_checked(spec, n, env0, base, forbidden)


def _support_bundle(cfg: dict[str, Any], forbidden: set[str]) -> dict[str, Any]:
    gen = load_generalization_config()
    budget = int(cfg["support_budget"])
    dev = __import__("json").loads(Path(cfg["development_artifact"]).read_text())
    if hashlib.sha256(Path(cfg["development_artifact"]).read_bytes()).hexdigest() != cfg["development_artifact_sha256"]:
        raise RuntimeError("development artifact hash mismatch")
    train_ids = list(gen["train_task_ids"])
    from nexus.tasks.pendulum_family import pendulum_latent_train

    train_specs = pendulum_latent_train()
    if [spec.task_id for spec in train_specs] != train_ids:
        raise RuntimeError("twelve-task training ids drifted")
    broad: list[TransitionDataset] = []
    for env0, base in (
        (int(cfg["broad_h0_env0"]), int(cfg["broad_h0_base"])),
        (int(cfg["broad_h1_env0"]), int(cfg["broad_h1_base"])),
    ):
        for index, spec in enumerate(train_specs):
            support = _collect_named(spec, budget, env0 + 10 * index, base + index, forbidden)
            stored = next(
                row["support_hash"]
                for row in dev["pair_rows"]
                if row["role"] == "train" and int(row["decoder"]) == 0 and row["task"] == spec.task_id and int(row["support_index"]) == (0 if env0 == int(cfg["broad_h0_env0"]) else 1)
            )
            if prefix_hash(support, budget) != stored:
                raise RuntimeError(f"twelve-task support hash drifted for {spec.task_id}")
            broad.append(support)
    baseline_specs = pendulum_context_train()
    baseline = []
    saved = __import__("json").loads(Path(gen["teacher_artifact"]).read_text())
    for index, spec in enumerate(baseline_specs):
        support = _collect_named(spec, budget, int(cfg["baseline_support_env0"]) + 10 * index, int(cfg["baseline_support_base"]) + index, forbidden)
        stored = next(row["support_hash"] for row in saved["teachers"] if row["split"] == "meta" and int(row["decoder"]) == 0 and row["task"] == spec.task_id)
        if prefix_hash(support, budget) != stored:
            raise RuntimeError(f"baseline support hash drifted for {spec.task_id}")
        baseline.append(support)
    return {"broad": broad, "baseline": baseline, "interactions": int(sum(ds.env_interactions for ds in broad + baseline))}


def _confirmation_artifact(cfg: dict[str, Any]) -> dict[str, Any]:
    path = Path(cfg["confirmation_artifact"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != cfg["confirmation_artifact_sha256"]:
        raise RuntimeError("confirmation artifact hash mismatch")
    return __import__("json").loads(path.read_text())


def _student_rows(seed: int, kind: str, cfg: dict[str, Any], confirmation: dict[str, Any]) -> list[dict[str, Any]]:
    if int(seed) in ORIGINAL_SEEDS:
        rows = [row for row in confirmation["checkpoints"] if row["kind"] == kind and int(row["epoch"]) == 200 and int(row["decoder"]) == int(seed)]
        rows.sort(key=lambda row: int(row["student"]))
        if len(rows) != int(cfg["n_student_seeds"]):
            raise RuntimeError(f"original {kind} checkpoints for decoder {seed} are incomplete")
        for row in rows:
            _require_hash(Path(row["path"]), row["sha256"])
        return rows
    manifest = _load_manifest()["decoders"][str(int(seed))]
    rows = []
    for student in range(int(cfg["n_student_seeds"])):
        slot = manifest["students"][f"{int(student)}:{kind}"]
        _require_hash(Path(slot["path"]), slot["sha256"])
        rows.append(slot)
    return rows


def _global_vector(seed: int, cfg: dict[str, Any], selection: dict[str, Any]) -> torch.Tensor:
    if int(seed) in ORIGINAL_SEEDS:
        parents = {int(row["seed"]): row for row in cfg["parent_checkpoints"]}
        vector = torch.tensor(selection["global_vectors"][str(int(seed))], dtype=torch.float32)
        if vector_hash(vector) != parents[int(seed)]["global_vector_sha256"]:
            raise RuntimeError(f"original global vector hash mismatch for decoder {seed}")
        return vector
    row = _load_manifest()["decoders"][str(int(seed))]
    blob = torch.load(row["global_path"], map_location="cpu", weights_only=False)
    vector = blob["vector"].detach().clone().float()
    if vector_hash(vector) != row["global_vector_sha256"] or _sha256(Path(row["global_path"])) != row["global_sha256"]:
        raise RuntimeError(f"new global vector hash mismatch for decoder {seed}")
    return vector


def _decoder_file(seed: int, cfg: dict[str, Any]) -> str:
    if int(seed) in ORIGINAL_SEEDS:
        parents = {int(row["seed"]): row for row in cfg["parent_checkpoints"]}
        path = Path(parents[int(seed)]["path"])
        if _sha256(path) != parents[int(seed)]["sha256"]:
            raise RuntimeError(f"original decoder hash mismatch for {path}")
        return str(path)
    row = _load_manifest()["decoders"][str(int(seed))]
    _require_hash(Path(row["model_path"]), row["model_sha256"])
    return str(row["model_path"])


def _run_label(
    records: list[dict[str, Any]],
    *,
    split: str,
    decoder: int | None,
    student: int | None,
    task: str,
    label: str,
    spec: Any,
    model: Any,
    eval_seed: int,
    cfg: dict[str, Any],
    mlp_seed: int | None = None,
    infer_seconds: float = 0.0,
) -> None:
    if any(
        row["split"] == split
        and row.get("decoder") == decoder
        and row.get("student") == student
        and row["task"] == task
        and row["label"] == label
        and row.get("mlp_seed") == mlp_seed
        for row in records
    ):
        return
    outcome = _evaluate_mpc(spec, model, eval_seed, int(cfg["episodes"]), float(cfg["catastrophic_return"]))
    records.append(
        {
            "split": split,
            "decoder": decoder,
            "cohort": None if decoder is None else cohort(int(decoder)),
            "student": student,
            "mlp_seed": mlp_seed,
            "task": task,
            "label": label,
            "infer_seconds": float(infer_seconds),
            **outcome,
        }
    )
    print(
        f"replication split={split} decoder={decoder} student={student} task={task} label={label} return={outcome['mean_return']:.1f}",
        flush=True,
    )


def _evaluate_decoder(
    records: list[dict[str, Any]],
    *,
    seed: int,
    split: str,
    specs: list[Any],
    supports: list[TransitionDataset],
    cfg: dict[str, Any],
    confirmation: dict[str, Any],
    selection: dict[str, Any],
    deadline: float,
    teacher_seconds: list[float],
    infer_seconds: list[float],
) -> bool:
    """Return False when the time cap stops the grid."""
    path = _decoder_file(seed, cfg)
    model, digest = _fresh_decoder(path, cfg)
    global_z = _global_vector(seed, cfg, selection)
    teachers = []
    for support in supports:
        if time.perf_counter() > deadline:
            return False
        started = time.perf_counter()
        vector = _fit_teacher(model, support, global_z)
        teacher_seconds.append(time.perf_counter() - started)
        if decoder_digest(model) != digest:
            raise RuntimeError("teacher fit changed the decoder during control")
        if split == "replication" and int(seed) in ORIGINAL_SEEDS:
            expected_hash = next(
                row["vector_sha256"]
                for row in confirmation["teacher_bindings"]
                if int(row["decoder"]) == int(seed) and row["task"] == specs[len(teachers)].task_id
            )
            if vector_hash(vector) != expected_hash:
                raise RuntimeError(f"teacher latent for decoder {seed} does not match the confirmation fit")
        teachers.append(vector.detach().clone())
    broad = _student_rows(seed, "broad", cfg, confirmation)
    baseline = _student_rows(seed, "baseline", cfg, confirmation)
    env0 = int(cfg["replication_eval_env0"] if split == "replication" else cfg["fresh_eval_env0"])
    for task_index, spec in enumerate(specs):
        if time.perf_counter() > deadline:
            return False
        eval_seed = env0 + 10 * task_index
        shared = {"zero": torch.zeros(8), "global": global_z.detach().clone(), "teacher": teachers[task_index]}
        for label, vector in shared.items():
            if _cell_done(records, split, seed, None, spec.task_id, label):
                continue
            probe, probe_digest = _fresh_decoder(path, cfg)
            if probe_digest != digest:
                raise RuntimeError("decoder digest drifted before control")
            probe.z = vector.detach().clone()
            _run_label(
                records, split=split, decoder=seed, student=None, task=spec.task_id, label=label,
                spec=spec, model=probe, eval_seed=eval_seed, cfg=cfg,
            )
        if not _cell_done(records, split, seed, None, spec.task_id, "encoder"):
            probe, _probe_digest = _fresh_decoder(path, cfg)
            started = time.perf_counter()
            probe.set_context_from_dataset(supports[task_index], budget=int(cfg["support_budget"]))
            elapsed = time.perf_counter() - started
            infer_seconds.append(elapsed)
            _run_label(
                records, split=split, decoder=seed, student=None, task=spec.task_id, label="encoder",
                spec=spec, model=probe, eval_seed=eval_seed, cfg=cfg, infer_seconds=elapsed,
            )
        for student in range(int(cfg["n_student_seeds"])):
            for label, rows in (("student", broad), ("baseline", baseline)):
                if _cell_done(records, split, seed, student, spec.task_id, label):
                    continue
                if time.perf_counter() > deadline:
                    return False
                probe, _probe_digest = _fresh_decoder(path, cfg)
                slot = next(row for row in rows if int(row["student"]) == student)
                _install_encoder(probe, slot["path"], cfg, digest)
                started = time.perf_counter()
                probe.set_context_from_dataset(supports[task_index], budget=int(cfg["support_budget"]))
                elapsed = time.perf_counter() - started
                infer_seconds.append(elapsed)
                _run_label(
                    records, split=split, decoder=seed, student=student, task=spec.task_id, label=label,
                    spec=spec, model=probe, eval_seed=eval_seed, cfg=cfg, infer_seconds=elapsed,
                )
    return True


def _strip_bulky(records: list[dict[str, Any]]) -> None:
    for row in records:
        row.pop("action_code", None)
        row.pop("first_scores", None)


def _mean_label(records: list[dict[str, Any]], split: str, label: str) -> float:
    rows = _matching(records, split=split, label=label)
    return float(np.mean([row["mean_return"] for row in rows])) if rows else float("nan")


def _task_rows(records: list[dict[str, Any]], split: str, tasks: list[str], physics: list[list[float]]) -> list[dict[str, Any]]:
    rows = []
    for task, values in zip(tasks, physics):
        item: dict[str, Any] = {"split": split, "task": task, "physics": list(values)}
        for label in ("student", "baseline", *SHARED_LABELS, "mlp"):
            matched = [row for row in records if row["split"] == split and row["task"] == task and row["label"] == label]
            item[label] = float(np.mean([row["mean_return"] for row in matched])) if matched else None
        rows.append(item)
    return rows


def _per_decoder(records: list[dict[str, Any]], split: str, decoders: list[int]) -> list[dict[str, Any]]:
    rows = []
    for decoder in decoders:
        item: dict[str, Any] = {"split": split, "decoder": int(decoder), "cohort": cohort(int(decoder))}
        for label in ("student", "baseline", *SHARED_LABELS):
            matched = _matching(records, split=split, decoder=int(decoder), label=label)
            item[label] = float(np.mean([row["mean_return"] for row in matched])) if matched else None
        rows.append(item)
    return rows


def _bars(path: Path, replication: list[float], fresh: list[float]) -> None:
    labels = ["student", "zero", "encoder", "global", "teacher", "baseline", "mlp"]
    width, height, pad = 760, 360, 48
    finite = [float(value) for value in replication + fresh if np.isfinite(value)]
    lo = min(finite) if finite else -1.0
    hi = max(finite) if finite else 0.0
    if hi - lo < 1.0:
        hi = lo + 1.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="48" y="24" font-size="14">Replication episodes</text>',
        '<text x="400" y="24" font-size="14">Fresh physics</text>',
    ]
    for panel, values, origin in ((0, replication, pad), (1, fresh, width / 2)):
        bar_w = (width / 2 - pad) / max(len(labels), 1)
        for index, (label, value) in enumerate(zip(labels, values)):
            if not np.isfinite(value):
                continue
            top = 40 + (height - 80) * (hi - float(value)) / (hi - lo)
            bottom = height - 36
            x = origin + index * bar_w + 4
            color = "#1f4e79" if panel == 0 else "#0f6b4c"
            parts.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bar_w - 10:.1f}" height="{max(bottom - top, 1):.1f}" fill="{color}"/>')
            parts.append(f'<text x="{x:.1f}" y="{height - 16}" font-size="10">{label}</text>')
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts))


def _read_partial(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    payload = __import__("json").loads(path.read_text())
    if isinstance(payload, dict) and payload.get("protocol_id") == "control_replication_v1":
        return list(payload.get("raw_records") or [])
    return []


def run_control_replication(
    *,
    protocol_path: str | Path = PROTOCOL_PATH,
    out_path: str | Path = "artifacts/control_replication.json",
    plot_path: str | Path = "artifacts/control_replication.svg",
    verify_original: bool = True,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = load_replication_config()
    assert_protocol_frozen(protocol_path, cfg)
    assert_confirmation_physics(load_confirmation_config())
    assert_fresh_physics(cfg)
    assert_replication_seeds(cfg)
    assert_checkpoint_hashes(load_generalization_config())
    for row in cfg["mlp_checkpoints"]:
        if _sha256(Path(row["path"])) != row["sha256"]:
            raise RuntimeError(f"MLP reference hash mismatch for {row['path']}")
    if hashlib.sha256(Path(cfg["control_artifact"]).read_bytes()).hexdigest() != cfg["control_artifact_sha256"]:
        raise RuntimeError("previous control artifact hash mismatch")
    confirmation = _confirmation_artifact(cfg)
    try:
        verify_student_checkpoints(confirmation, {"n_decoder_seeds": 3, "n_student_seeds": int(cfg["n_student_seeds"]), "n_parameters": 584})
    except FileNotFoundError:
        from nexus.world.latent_control import reproduce_missing_checkpoints

        reproduce_missing_checkpoints(confirmation, load_control_config())
        verify_student_checkpoints(confirmation, {"n_decoder_seeds": 3, "n_student_seeds": int(cfg["n_student_seeds"]), "n_parameters": 584})
    selection = __import__("json").loads(Path(load_generalization_config()["prior_selection"]).read_text())["selection_record"]
    deadline = t0 + float(cfg["time_limit_s"])
    recipe_reports: list[dict[str, Any]] = []
    if verify_original:
        recipe_reports = verify_original_recipe(cfg)
    trained = []
    source_interactions = 0
    for seed in cfg["new_seeds"]:
        if time.perf_counter() > deadline:
            break
        manifest = _load_manifest()["decoders"].get(str(int(seed)))
        students_ready = bool(manifest) and all(
            f"{student}:{kind}" in manifest.get("students", {})
            for student in range(int(cfg["n_student_seeds"]))
            for kind in ("broad", "baseline")
        )
        if manifest and students_ready:
            _require_hash(Path(manifest["model_path"]), manifest["model_sha256"])
            trained.append(int(seed))
            print(f"replication reusing new decoder {seed}", flush=True)
            continue
        if manifest and not students_ready:
            _require_hash(Path(manifest["model_path"]), manifest["model_sha256"])
            model_ready = True
        else:
            model_ready = False
        if not model_ready:
            model, global_z, hashes = train_history_decoder(int(seed), cfg)
            source_interactions += int(cfg["source_per_task"]) * int(cfg["n_source_tasks"])
            save_new_decoder(int(seed), model, global_z, hashes)
            print(f"replication trained new decoder {seed}", flush=True)
        forbidden = set(load_generalization_config()["forbidden_task_ids"])
        bundle = _support_bundle(cfg, forbidden)
        train_new_students(int(seed), cfg, bundle["broad"], bundle["baseline"])
        trained.append(int(seed))
    destination = Path(out_path)
    records = _read_partial(destination)
    forbidden = set(load_generalization_config()["forbidden_task_ids"])
    bundle = _support_bundle(cfg, forbidden)
    replication_specs = list(pendulum_latent_confirmation())
    fresh_specs = list(assert_fresh_physics(cfg))
    budget = int(cfg["support_budget"])
    replication_supports = []
    for index, spec in enumerate(replication_specs):
        support = _collect_named(spec, budget, int(cfg["confirm_support_env0"]) + 10 * index, int(cfg["confirm_support_base"]) + index, forbidden)
        expected = {row["support_hash"] for row in confirmation["teacher_bindings"] if row["task"] == spec.task_id}
        if expected != {prefix_hash(support, budget)}:
            raise RuntimeError(f"replication support for {spec.task_id} is not the previous confirmation support")
        replication_supports.append(support)
    fresh_supports = [
        _collect_named(spec, budget, int(cfg["fresh_support_env0"]) + 10 * index, int(cfg["fresh_support_base"]) + index, forbidden)
        for index, spec in enumerate(fresh_specs)
    ]
    teacher_seconds: list[float] = []
    infer_seconds: list[float] = []
    available = [int(seed) for seed in ORIGINAL_SEEDS if int(seed) in cfg["original_seeds"]] + trained
    timed_out = False

    def flush_records() -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(dumps_strict({
            "protocol_id": "control_replication_v1",
            "declared_complete": False,
            "raw_records": records,
        }))
    for split, specs, supports in (
        ("replication", replication_specs, replication_supports),
        ("fresh", fresh_specs, fresh_supports),
    ):
        for seed in available:
            if time.perf_counter() > deadline:
                timed_out = True
                break
            finished = _evaluate_decoder(
                records, seed=int(seed), split=split, specs=specs, supports=supports, cfg=cfg,
                confirmation=confirmation, selection=selection, deadline=deadline,
                teacher_seconds=teacher_seconds, infer_seconds=infer_seconds,
            )
            flush_records()
            if not finished:
                timed_out = True
                break
        if timed_out:
            break
        for row in cfg["mlp_checkpoints"]:
            if time.perf_counter() > deadline:
                timed_out = True
                break
            mlp = load_mlp_checkpoint(Path(row["path"]), tuple(row["hidden"]))
            env0 = int(cfg["replication_eval_env0"] if split == "replication" else cfg["fresh_eval_env0"])
            for task_index, spec in enumerate(specs):
                if any(item["split"] == split and item["label"] == "mlp" and item.get("mlp_seed") == int(row["seed"]) and item["task"] == spec.task_id for item in records):
                    continue
                _run_label(
                    records, split=split, decoder=None, student=None, task=spec.task_id, label="mlp",
                    spec=spec, model=mlp, eval_seed=env0 + 10 * task_index, cfg=cfg, mlp_seed=int(row["seed"]),
                )
            flush_records()
    needed = _expected_keys(cfg, "replication", list(cfg["replication_task_ids"]), list(ORIGINAL_SEEDS) + list(NEW_SEEDS))
    needed |= _expected_keys(cfg, "fresh", list(cfg["fresh_task_ids"]), list(ORIGINAL_SEEDS) + list(NEW_SEEDS))
    missing = sorted(str(key) for key in (needed - _have_keys(records)))
    complete = not missing and not timed_out and len(available) == TARGET_DECODERS
    decoders = [int(seed) for seed in list(ORIGINAL_SEEDS) + list(NEW_SEEDS)]
    finished_decoders = [seed for seed in decoders if all((("replication", seed, None, task, "zero") in _have_keys(records)) for task in cfg["replication_task_ids"])]
    paired = {
        split: {
            name: decoder_level_deltas(records, name, split, decoders)
            for name in (*PRIMARY_CONTROLS, "global", "teacher", "baseline")
        }
        for split in ("replication", "fresh")
    }
    gates = {}
    passed = {}
    for split in ("replication", "fresh"):
        ok, report = replication_gate(paired[split]["zero"], paired[split]["encoder"], float(cfg["minimum_effect"]), TARGET_DECODERS)
        gates[split] = report
        for name in ("global", "teacher", "baseline"):
            values = paired[split][name]
            finite = len(values) == TARGET_DECODERS and all(np.isfinite(value) for value in values)
            report[name] = {
                "per_decoder": [None if not np.isfinite(value) else float(value) for value in values],
                "interval": seed_level_ci([float(value) for value in values]) if finite else {"n": len(values), "mean": None, "lo": None, "hi": None},
                "sign": "student_minus_control",
            }
        passed[split] = bool(ok and complete)
    pred = {split: prediction_deltas(records, split, decoders) for split in ("replication", "fresh")}
    pred_ok = {}
    pred_report = {}
    for split in ("replication", "fresh"):
        finite = len(pred[split]) == TARGET_DECODERS and all(np.isfinite(value) for value in pred[split])
        interval = seed_level_ci([float(value) for value in pred[split]]) if finite else {"n": len(pred[split]), "mean": None, "lo": None, "hi": None}
        pred_ok[split] = bool(finite and float(interval["mean"]) > 0.0 and float(interval["lo"]) > 0.0)
        pred_report[split] = {"per_decoder": pred[split], "interval": interval, "pass": pred_ok[split], "sign": "zero_minus_student_visited_angvel"}
    diagnostics = {split: action_diagnostics(records, split, finished_decoders) for split in ("replication", "fresh")}
    correlations = {}
    for split in ("replication", "fresh"):
        correlations[split] = {
            "pearson_prediction_improvement_vs_return_improvement": _pearson(
                [float(value) for value in pred[split]],
                [float(value) for value in paired[split]["zero"]],
            ),
            "n": TARGET_DECODERS,
            "interpretation": "Correlation across decoders is not evidence that prediction error causes the return difference.",
        }
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    clean = not bool(source_status.get("source_dirty", True))
    decision = bool(clean and complete)
    recommendation = recommend_replication(
        complete=decision,
        replication_pass=bool(passed["replication"]),
        fresh_pass=bool(passed["fresh"]),
        prediction_pass=bool(pred_ok["replication"]),
    ) if clean else None
    manifest = _load_manifest()
    sample_path = cfg["parent_checkpoints"][0]["path"]
    sample, _digest = _fresh_decoder(sample_path, cfg)
    means = {
        split: {label: _mean_label(records, split, label) for label in ("student", "baseline", *SHARED_LABELS, "mlp")}
        for split in ("replication", "fresh")
    }
    plot = Path(plot_path)
    _bars(
        plot,
        [means["replication"][label] for label in ("student", "zero", "encoder", "global", "teacher", "baseline", "mlp")],
        [means["fresh"][label] for label in ("student", "zero", "encoder", "global", "teacher", "baseline", "mlp")],
    )
    payload = {
        "protocol_id": cfg["protocol_id"],
        "hypothesis": cfg["h_replication"],
        "implementation_sha": sha if clean else None,
        "source_dirty": not clean,
        "git": head,
        "decision_recorded": decision,
        "statistical_objective": "ten independent decoders",
        "objective_met": bool(complete),
        "exploratory": not bool(complete),
        "gate_pass": bool(passed["replication"] and passed["fresh"] and decision),
        "replication_gate_pass": bool(passed["replication"]),
        "fresh_gate_pass": bool(passed["fresh"]),
        "previous_point_estimate_positive": bool(
            np.isfinite(means["replication"]["student"]) and np.isfinite(means["replication"]["zero"]) and means["replication"]["student"] > means["replication"]["zero"]
        ),
        "minimum_effect": float(cfg["minimum_effect"]),
        "primary_unit": "decoder after averaging its student seeds, tasks, and episodes",
        "independent_decoder_count": len(available),
        "target_decoders": TARGET_DECODERS,
        "original_seeds": list(ORIGINAL_SEEDS),
        "new_seeds_trained": trained,
        "recipe_reproduced_original": recipe_reports,
        "means": means,
        "paired_student_minus_control": gates,
        "prediction_visited_angvel": pred_report,
        "prediction_return_correlation": correlations,
        "action_diagnostics": diagnostics,
        "variance": {split: variance_split(records, split, finished_decoders) for split in ("replication", "fresh")},
        "per_decoder": _per_decoder(records, "replication", decoders) + _per_decoder(records, "fresh", decoders),
        "per_task": _task_rows(records, "replication", list(cfg["replication_task_ids"]), cfg["replication_physics"])
        + _task_rows(records, "fresh", list(cfg["fresh_task_ids"]), cfg["fresh_physics"]),
        "latency": {
            "mean_plan_ms": float(np.mean([row["mean_plan_ms"] for row in records])) if records else None,
            "encoder_infer_seconds_mean": float(np.mean(infer_seconds)) if infer_seconds else None,
            "teacher_fit_seconds_mean": float(np.mean(teacher_seconds)) if teacher_seconds else None,
        },
        "resources": {
            "encoder_parameters": 584,
            "decoder_parameters": 3748,
            "encoder_bytes": int(sum(param.detach().nbytes for param in sample.encoder.parameters())),
            "decoder_bytes": int(sum(param.detach().nbytes for param in sample.net.parameters())),
            "new_decoder_source_transitions": int(source_interactions),
            "student_support_env_interactions": int(bundle["interactions"]),
            "control_env_interactions": int(sum(row["env_interactions"] for row in records)),
            "imagined_model_states": int(sum(row["model_states"] for row in records)),
            "time_limit_s": int(cfg["time_limit_s"]),
            "timed_out": bool(timed_out),
        },
        "checkpoint_manifest": manifest,
        "schema_failures": missing[:40],
        "n_missing_cells": len(missing),
        "declared_complete": bool(complete),
        "control_evaluated": bool(records),
        "is_agi": False,
        "is_learning_to_learn": False,
        "recommendation": recommendation,
        "plot": str(plot),
        "wall_clock_s": time.perf_counter() - t0,
        "raw_records": records,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dumps_strict(payload))
    return payload
