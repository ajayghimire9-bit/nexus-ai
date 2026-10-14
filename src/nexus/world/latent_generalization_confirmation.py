"""Confirmation for the twelve-task mean-pooling encoder.

Retrain the locked student, match the development artifact, and only then
score a newly registered Pendulum split. The epoch, learning rate, support
budget, and teacher rule stay at the development values. This is a prediction
check. It does not run control.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import (
    pendulum_amortized_confirmation,
    pendulum_confirmation_targets,
    pendulum_context_confirmation,
    pendulum_context_development,
    pendulum_context_train,
    pendulum_default,
    pendulum_development,
    pendulum_latent_confirmation,
    pendulum_latent_train,
    pendulum_latent_validation,
    pendulum_meta_confirm,
    pendulum_meta_train,
    pendulum_meta_val,
    pendulum_physics_key,
    pendulum_source,
    pendulum_transfer_confirmation,
    pendulum_transfer_development,
    pendulum_transfer_sequence,
)
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_diagnosis import complete_episodes
from nexus.world.context_optimization import _sha256
from nexus.world.context_pilot import _split_hash, prefix_hash
from nexus.world.direct_latent import assert_support_query_separated, lock_network, vector_hash
from nexus.world.frozen_dynamics import load_context_checkpoint, planned_env_seeds
from nexus.world.latent_generalization import (
    _collect_checked,
    _fit_teacher,
    _infer,
    _mean_angvel,
    _metric_summary,
    _per_decoder,
    _score_heldout,
    _student_seed_means,
    assert_checkpoint_hashes,
    baseline_label,
    broad_label,
    combined_seed,
    decoder_digest,
    generalization_seed_groups,
    load_generalization_config,
    run_latent_generalization,
)
from nexus.world.result_checks import schema_completeness
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/latent_generalization_confirmation.yaml")
PROTOCOL_PATH = Path("docs/NEXUS_LATENT_GENERALIZATION_CONFIRMATION.md")
REFERENCE_PATH = Path("artifacts/latent_generalization_dev.json")
CHECKPOINT_DIR = Path("artifacts/latent_generalization_confirmation_checkpoints")
PRIMARY_CONTROLS = ("zero", "encoder", "global")


def load_confirmation_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("confirmation config must be a mapping")
    expected = _locked_config()
    if cfg != expected:
        missing = sorted(set(expected) - set(cfg))
        extra = sorted(set(cfg) - set(expected))
        drifted = sorted(key for key in expected if key in cfg and cfg[key] != expected[key])
        raise ValueError(f"confirmation config drifted; missing={missing} extra={extra} drifted={drifted}")
    if int(cfg["confirmation_epoch"]) != 200 or float(cfg["student_learning_rate"]) != 0.01:
        raise ValueError("confirmation training rule drifted")
    if float(cfg["minimum_effect"]) != 0.01:
        raise ValueError("minimum effect drifted")
    return cfg


def _locked_config() -> dict[str, Any]:
    gen = load_generalization_config()
    rows = [[5.1, 0.88, 0.96], [15.8, 0.92, 1.04], [10.4, 2.45, 0.58], [11.4, 0.48, 1.82]]
    return {
        "protocol_id": "latent_generalization_confirmation_v1",
        "starting_sha": "5299ddc956f6f9cea73c5281a15445260b0b7adf",
        "development_artifact": "artifacts/latent_generalization_dev.json",
        "development_artifact_sha256": "c8438e09c383fc669b3b9f4cad275725d7daa9f49d2616083f256cefa1f24aba",
        "forbidden_confirm_hash": "87b83c41be34aa1a",
        "amort_confirm_hash": "d1fa621351d286cf",
        "confirm_split_hash": "baa655fcb94e61bc",
        "is_agi": False,
        "is_learning_to_learn": False,
        "control_sweep": False,
        "h_confirm": (
            "The 584-parameter encoder trained on the twelve source physics lowers confirmation "
            "angular-velocity error at least 0.01 below zero context, the frozen encoder, and the global vector."
        ),
        "n_decoder_seeds": int(gen["n_decoder_seeds"]),
        "n_student_seeds": int(gen["n_student_seeds"]),
        "support_budget": int(gen["support_budget"]),
        "query_episodes": int(gen["query_episodes"]),
        "query_transitions": int(gen["query_transitions"]),
        "confirmation_epoch": 200,
        "student_learning_rate": 0.01,
        "teacher_learning_rate": 0.1,
        "teacher_updates": 256,
        "encoder_hidden": 32,
        "context_dim": 8,
        "n_parameters": 584,
        "minimum_effect": 0.01,
        "repro_atol": 0.0001,
        "recovery_min_relative": 0.05,
        "history_fail_l2": 0.5,
        "angular_velocity_index": 2,
        "horizons": [3, 8, 16],
        "rollout_starts": list(gen["rollout_starts"]),
        "confirm_support_env0": 102000,
        "confirm_support_base": 268000,
        "confirm_query_env0": 103000,
        "confirm_query_base": 269000,
        "expected_teacher_steps": 30720,
        "expected_student_steps": 96000,
        "time_limit_s": 2400,
        "confirm_physics": rows,
        "confirm_task_ids": [f"pendulum_lat_cf{i}" for i in range(4)],
        "primary_unit": "decoder",
        "parent_checkpoints": list(gen["parent_checkpoints"]),
    }


def assert_protocol_frozen(protocol_path: str | Path, cfg: dict[str, Any]) -> None:
    path = Path(protocol_path)
    if not path.is_file():
        raise RuntimeError("confirmation is blocked until the protocol document is saved")
    text = path.read_text()
    start = text.find("<!-- protocol-lock")
    end = text.find("-->", start)
    if start < 0 or end < 0:
        raise RuntimeError("confirmation is blocked because the protocol lock block is missing")
    locked: dict[str, str] = {}
    for line in text[start:end].splitlines():
        if ":" not in line or line.strip().startswith("<!--"):
            continue
        key, value = line.split(":", 1)
        locked[key.strip()] = value.strip()
    required = {
        "confirm_split_hash": str(cfg["confirm_split_hash"]),
        "forbidden_confirm_hash": str(cfg["forbidden_confirm_hash"]),
        "amort_confirm_hash": str(cfg["amort_confirm_hash"]),
        "development_artifact_sha256": str(cfg["development_artifact_sha256"]),
        "teacher_lr": f"{float(cfg['teacher_learning_rate']):.1f}",
        "teacher_updates": str(int(cfg["teacher_updates"])),
        "student_lr": f"{float(cfg['student_learning_rate']):.2f}",
        "confirmation_epoch": str(int(cfg["confirmation_epoch"])),
        "n_student_seeds": str(int(cfg["n_student_seeds"])),
        "n_decoder_seeds": str(int(cfg["n_decoder_seeds"])),
        "support_budget": str(int(cfg["support_budget"])),
        "minimum_effect": f"{float(cfg['minimum_effect']):.2f}",
        "repro_atol": f"{float(cfg['repro_atol']):.4f}",
        "n_parameters": str(int(cfg["n_parameters"])),
        "confirm_support_env0": str(int(cfg["confirm_support_env0"])),
        "confirm_query_env0": str(int(cfg["confirm_query_env0"])),
        "primary_unit": str(cfg["primary_unit"]),
    }
    for key, value in required.items():
        if locked.get(key) != value:
            raise RuntimeError(f"confirmation is blocked because protocol {key}={locked.get(key)!r} is not {value!r}")


def _occupied_physics() -> list[Any]:
    specs: list[Any] = [
        pendulum_default(),
        pendulum_development(),
        pendulum_source(),
        pendulum_transfer_development(),
        *pendulum_confirmation_targets(),
        *pendulum_transfer_confirmation(),
        *pendulum_transfer_sequence(),
        *pendulum_meta_train(),
        *pendulum_meta_val(),
        *pendulum_meta_confirm(),
        *pendulum_context_train(),
        *pendulum_context_development(),
        *pendulum_context_confirmation(),
        *pendulum_amortized_confirmation(),
        *pendulum_latent_train(),
        *pendulum_latent_validation(),
    ]
    return specs


def assert_confirmation_physics(cfg: dict[str, Any]) -> tuple[Any, ...]:
    specs = pendulum_latent_confirmation()
    if _split_hash(specs) != cfg["confirm_split_hash"]:
        raise RuntimeError("confirmation physics hash drifted")
    if [spec.task_id for spec in specs] != list(cfg["confirm_task_ids"]):
        raise RuntimeError("confirmation task ids drifted")
    if [list(pendulum_physics_key(spec)) for spec in specs] != cfg["confirm_physics"]:
        raise RuntimeError("confirmation physics values drifted")
    if _split_hash(pendulum_context_confirmation()) != cfg["forbidden_confirm_hash"]:
        raise RuntimeError("the direct-latent confirmation split changed")
    if _split_hash(pendulum_amortized_confirmation()) != cfg["amort_confirm_hash"]:
        raise RuntimeError("the amortized confirmation split changed")
    occupied = {pendulum_physics_key(spec) for spec in _occupied_physics()}
    fresh = [pendulum_physics_key(spec) for spec in specs]
    if len(fresh) != len(set(fresh)) or occupied.intersection(fresh):
        raise RuntimeError("confirmation physics collide with a previous Pendulum split")
    reserved = {spec.task_id for spec in (*pendulum_context_confirmation(), *pendulum_amortized_confirmation())}
    if reserved & {spec.task_id for spec in specs}:
        raise RuntimeError("confirmation reused a reserved task id")
    return specs


def confirmation_seed_groups(cfg: dict[str, Any]) -> dict[str, set[int]]:
    groups = generalization_seed_groups(load_generalization_config())
    n_tasks = len(cfg["confirm_task_ids"])
    for name, n, env0 in (
        ("confirm_support", int(cfg["support_budget"]), int(cfg["confirm_support_env0"])),
        ("confirm_query", int(cfg["query_transitions"]), int(cfg["confirm_query_env0"])),
    ):
        seeds: set[int] = set()
        for index in range(n_tasks):
            seeds |= planned_env_seeds(n, env0 + 10 * index)
        groups[name] = seeds
    return groups


def assert_confirmation_seeds(cfg: dict[str, Any]) -> None:
    named = confirmation_seed_groups(cfg)
    keys = list(named)
    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            overlap = named[left] & named[right]
            if overlap:
                raise ValueError(f"collect seeds overlap between {left} and {right}: {sorted(overlap)[:8]}")


def confirm_schema(cfg: dict[str, Any]) -> dict[str, Any]:
    epoch = int(cfg["confirmation_epoch"])
    labels = [broad_label(epoch), baseline_label(epoch), "zero", "global", "encoder", "teacher"]
    n_student = int(cfg["n_student_seeds"])
    return {
        "seed_ids": [combined_seed(d, s, n_student) for d in range(int(cfg["n_decoder_seeds"])) for s in range(n_student)],
        "task_ids": list(cfg["confirm_task_ids"]),
        "labels": labels,
        "conditions_by_label": {label: [label] for label in labels},
        "metrics": ["mae", "rmse", "angvel_mae"],
        "horizons": ["3", "8", "16"],
        "per_dim": 3,
    }


def decoder_deltas(records: list[dict[str, Any]], student_label: str, control: str, cfg: dict[str, Any]) -> list[float]:
    """One number per frozen decoder. Student seeds are averaged inside the decoder."""
    n_student = int(cfg["n_student_seeds"])
    out = []
    for decoder in range(int(cfg["n_decoder_seeds"])):
        ids = [combined_seed(decoder, student, n_student) for student in range(n_student)]
        out.append(_mean_angvel(records, control, ids) - _mean_angvel(records, student_label, ids))
    return out


def confirmation_gate(deltas: dict[str, list[float]], minimum_effect: float) -> tuple[bool, dict[str, Any]]:
    """Pass only when each primary control loses by at least the locked margin.

    The interval is the Student-t interval across the three decoders. A lower
    bound of 0 fails. Five student seeds inside one decoder are not five replications.
    """
    report: dict[str, Any] = {}
    ok = True
    for name in PRIMARY_CONTROLS:
        values = [float(v) for v in deltas[name]]
        if len(values) != 3 or any(not np.isfinite(v) for v in values):
            report[name] = {"pass": False}
            ok = False
            continue
        interval = seed_level_ci(values)
        passed = bool(float(interval["mean"]) >= float(minimum_effect) and float(interval["lo"]) > 0.0)
        report[name] = {"per_decoder": values, "interval": interval, "pass": passed}
        ok = ok and passed
    return ok, report


def recovery_fraction(global_mean: float, student_mean: float, teacher_mean: float, min_relative: float) -> float | None:
    denom = float(global_mean) - float(teacher_mean)
    if not np.isfinite(denom) or denom < float(min_relative) * float(global_mean):
        return None
    return (float(global_mean) - float(student_mean)) / denom


def recommend_confirmation(
    gate: bool,
    teacher_worse_fraction: float,
    zero_deltas: list[float],
    history_l2: float,
    confirm_l2: float,
) -> str:
    """Locked diagnosis. A failure does not retune this confirmation split."""
    if gate:
        return "mpc_return_pilot"
    if float(teacher_worse_fraction) >= 0.5:
        return "teacher_failure"
    signs = [float(value) > 0.0 for value in zero_deltas]
    if any(signs) and not all(signs):
        return "decoder_variability"
    if float(history_l2) > 0.5 and float(confirm_l2) > 0.5:
        return "support_history_uncertainty"
    return "task_shift"


def _binding_rows(rows: list[dict[str, Any]], role: str) -> list[tuple[Any, ...]]:
    bound = []
    for row in rows:
        if row.get("role") != role:
            continue
        bound.append((
            int(row["decoder"]),
            str(row["task"]),
            None if row.get("support_index") is None else int(row["support_index"]),
            str(row.get("support_hash")),
            str(row.get("vector_sha256")),
        ))
    return sorted(bound)


def assert_reproduction(reproduced: dict[str, Any], reference: dict[str, Any], cfg: dict[str, Any]) -> dict[str, float]:
    """Reject a retraining that does not match the development artifact.

    Hash bindings must match exactly. Scalar scores must match within the
    locked absolute tolerance. This function does not collect new physics.
    """
    atol = float(cfg["repro_atol"])
    if int(reproduced.get("chosen_epoch") or -1) != int(cfg["confirmation_epoch"]):
        raise RuntimeError("reproduced development selection is not epoch 200; confirmation stays closed")
    if reproduced["resources"]["teacher_optimizer_steps"] != int(cfg["expected_teacher_steps"]):
        raise RuntimeError("reproduced teacher step count drifted")
    if reproduced["resources"]["student_optimizer_steps"] != int(cfg["expected_student_steps"]):
        raise RuntimeError("reproduced student step count drifted")
    deltas: dict[str, float] = {}
    for key in ("student", "zero", "encoder", "global", "teacher", "baseline"):
        delta = abs(float(reproduced["means"][key]) - float(reference["means"][key]))
        deltas[key] = delta
        if delta > atol:
            raise RuntimeError(f"reproduced development {key} differs by {delta}; confirmation stays closed")
    for epoch in ("40", "100", "200"):
        delta = abs(float(reproduced["dev_checkpoint_angvel"][epoch]) - float(reference["dev_checkpoint_angvel"][epoch]))
        deltas[f"epoch_{epoch}"] = delta
        if delta > atol:
            raise RuntimeError(f"reproduced epoch {epoch} differs by {delta}; confirmation stays closed")
    for key in ("train_latent_l2", "history_latent_l2", "teacher_pair_median_l2"):
        delta = abs(float(reproduced[key]) - float(reference[key]))
        deltas[key] = delta
        if delta > atol:
            raise RuntimeError(f"reproduced {key} differs by {delta}; confirmation stays closed")
    for role in ("train", "history"):
        if _binding_rows(reproduced["pair_rows"], role) != _binding_rows(reference["pair_rows"], role):
            raise RuntimeError(f"reproduced {role} teacher bindings do not match the development artifact")
    return deltas


def save_student_checkpoints(snapshots: dict[Any, Any], directory: str | Path = CHECKPOINT_DIR) -> list[dict[str, Any]]:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for decoder, students in sorted(snapshots.items()):
        for student, states in sorted(students.items()):
            for kind in ("broad", "baseline"):
                state = states[(kind, 200)]
                count = int(sum(tensor.numel() for tensor in state.values()))
                if count != 584:
                    raise RuntimeError("refusing to save an encoder whose parameter count is not 584")
                path = root / f"d{int(decoder)}_s{int(student)}_{kind}_e200.pt"
                torch.save({key: value.detach().cpu() for key, value in state.items()}, path)
                rows.append({
                    "decoder": int(decoder),
                    "student": int(student),
                    "kind": kind,
                    "epoch": 200,
                    "path": str(path),
                    "sha256": _sha256(path),
                    "n_parameters": count,
                })
    if len(rows) != 30:
        raise RuntimeError("student checkpoint set is incomplete")
    return rows


def _task_rows(records: list[dict[str, Any]], label: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    specs = {spec.task_id: pendulum_physics_key(spec) for spec in pendulum_latent_confirmation()}
    rows = []
    for task in cfg["confirm_task_ids"]:
        task_records = [row for row in records if row["task"] == task]
        student = _mean_angvel(task_records, label)
        zero = _mean_angvel(task_records, "zero")
        encoder = _mean_angvel(task_records, "encoder")
        global_mean = _mean_angvel(task_records, "global")
        teacher = _mean_angvel(task_records, "teacher")
        rows.append({
            "task": task,
            "physics": list(specs[task]),
            "student": student,
            "zero": zero,
            "encoder": encoder,
            "global": global_mean,
            "teacher": teacher,
            "baseline": _mean_angvel(task_records, baseline_label(int(cfg["confirmation_epoch"]))),
            "teacher_worse_than_zero": bool(teacher > zero),
            "student_below_zero": bool(student < zero),
            "student_below_encoder": bool(student < encoder),
            "student_below_global": bool(student < global_mean),
        })
    return rows


def _bars(path: Path, labels: list[str], values: list[float]) -> None:
    width, height, pad = 640, 320, 48
    finite = [value for value in values if np.isfinite(value)]
    hi = max(finite) if finite else 1.0
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">', '<rect width="100%" height="100%" fill="white"/>']
    bar_w = (width - 2 * pad) / max(len(labels), 1)
    for index, (label, value) in enumerate(zip(labels, values)):
        if not np.isfinite(value):
            continue
        h = (height - 2 * pad) * (value / hi)
        x = pad + index * bar_w + 8
        y = height - pad - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 16:.1f}" height="{h:.1f}" fill="#1f4e79"/>')
        parts.append(f'<text x="{x:.1f}" y="{height - 18}" font-size="11">{label}</text>')
        parts.append(f'<text x="{x:.1f}" y="{y - 4:.1f}" font-size="11">{value:.3f}</text>')
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts))


def run_latent_generalization_confirmation(
    *,
    protocol_path: str | Path = PROTOCOL_PATH,
    out_path: str | Path = "artifacts/latent_generalization_confirmation.json",
    plot_path: str | Path = "artifacts/latent_generalization_confirmation.svg",
    checkpoint_dir: str | Path = CHECKPOINT_DIR,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = load_confirmation_config()
    assert_protocol_frozen(protocol_path, cfg)
    assert_confirmation_physics(cfg)
    assert_confirmation_seeds(cfg)
    gen = load_generalization_config()
    assert_checkpoint_hashes(gen)
    reference_path = Path(cfg["development_artifact"])
    if hashlib.sha256(reference_path.read_bytes()).hexdigest() != cfg["development_artifact_sha256"]:
        raise RuntimeError("development artifact hash mismatch; confirmation stays closed")
    reference = json.loads(reference_path.read_text())
    forbidden = set(gen["forbidden_task_ids"])
    if forbidden & set(cfg["confirm_task_ids"]):
        raise RuntimeError("confirmation task ids include a reserved split")

    sink: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        reproduced = run_latent_generalization(
            out_path=Path(tmp) / "reproduced_dev.json",
            plot_path=Path(tmp) / "reproduced_dev.svg",
            sink=sink,
        )
        deltas = assert_reproduction(reproduced, reference, cfg)
    reloaded = []
    for row in cfg["parent_checkpoints"]:
        model = load_context_checkpoint(Path(row["path"]))
        lock_network(model)
        reloaded.append(decoder_digest(model))
    if list(sink.get("decoder_digests") or []) != reloaded:
        raise RuntimeError("decoder digest changed during reproduction; confirmation stays closed")
    checkpoints = save_student_checkpoints(sink["snapshots"], checkpoint_dir)

    specs = pendulum_latent_confirmation()
    budget = int(cfg["support_budget"])
    epoch = int(cfg["confirmation_epoch"])
    horizons = [int(h) for h in cfg["horizons"]]
    angvel_index = int(cfg["angular_velocity_index"])
    supports = []
    queries = []
    for index, spec in enumerate(specs):
        supports.append(_collect_checked(spec, budget, int(cfg["confirm_support_env0"]) + 10 * index, int(cfg["confirm_support_base"]) + index, forbidden))
        raw = _collect_checked(spec, int(cfg["query_transitions"]), int(cfg["confirm_query_env0"]) + 10 * index, int(cfg["confirm_query_base"]) + index, forbidden)
        done = complete_episodes(raw, 16)
        if len(np.unique(done.episode_id)) != int(cfg["query_episodes"]):
            raise RuntimeError(f"{spec.task_id} did not yield the locked confirmation episode count")
        queries.append(done)
    assert_support_query_separated(*zip(supports, queries))

    selection = json.loads(Path(gen["prior_selection"]).read_text())["selection_record"]
    teachers: dict[int, list[torch.Tensor]] = {}
    globals_by_decoder: dict[int, torch.Tensor] = {}
    teacher_seconds = []
    teacher_rows = []
    for decoder, parent in enumerate(cfg["parent_checkpoints"]):
        model = load_context_checkpoint(Path(parent["path"]))
        if decoder_digest(model) != sink["decoder_digests"][decoder]:
            raise RuntimeError("confirmation teacher fit saw a changed decoder")
        global_z = torch.tensor(selection["global_vectors"][str(decoder)], dtype=torch.float32)
        if vector_hash(global_z) != parent["global_vector_sha256"]:
            raise RuntimeError(f"global vector hash mismatch for decoder {decoder}")
        started = time.perf_counter()
        fitted = []
        for task_index, support in enumerate(supports):
            vector = _fit_teacher(model, support, global_z)
            fitted.append(vector)
            teacher_rows.append({
                "decoder": decoder,
                "task": specs[task_index].task_id,
                "support_hash": prefix_hash(support, budget),
                "vector_sha256": vector_hash(vector),
            })
        teacher_seconds.append(time.perf_counter() - started)
        teachers[decoder] = fitted
        globals_by_decoder[decoder] = global_z.detach().clone()

    probe = load_context_checkpoint(Path(cfg["parent_checkpoints"][0]["path"]))
    sample = sink["snapshots"][0][0][("broad", 200)]
    student_infer_seconds = []
    for _repeat in range(5):
        started = time.perf_counter()
        _infer(probe, sample, supports[0], budget)
        student_infer_seconds.append(time.perf_counter() - started)
    infer_started = time.perf_counter()
    records = _score_heldout(
        cfg, sink["snapshots"], specs, supports, queries, teachers, globals_by_decoder, epoch, horizons, angvel_index, budget,
    )
    infer_seconds = time.perf_counter() - infer_started
    schema = confirm_schema(cfg)
    completeness = schema_completeness(
        records,
        seed_ids=list(schema["seed_ids"]),
        task_ids=list(schema["task_ids"]),
        labels=list(schema["labels"]),
        conditions_by_label={key: list(value) for key, value in schema["conditions_by_label"].items()},
        metrics=tuple(schema["metrics"]),
        horizons=tuple(schema["horizons"]),
        per_dim=int(schema["per_dim"]),
    )
    label = broad_label(epoch)
    paired = {name: decoder_deltas(records, label, name, cfg) for name in (*PRIMARY_CONTROLS, "teacher", baseline_label(epoch))}
    gate_ok, gate_report = confirmation_gate({name: paired[name] for name in PRIMARY_CONTROLS}, float(cfg["minimum_effect"]))
    tasks = _task_rows(records, label, cfg)
    teacher_worse = [row["task"] for row in tasks if row["teacher_worse_than_zero"]]
    task_failures = [row["task"] for row in tasks if not (row["student_below_zero"] and row["student_below_encoder"] and row["student_below_global"])]
    means = {name: _mean_angvel(records, name if name != "student" else label) for name in ("student", *PRIMARY_CONTROLS, "teacher")}
    means["student"] = _mean_angvel(records, label)
    means["baseline"] = _mean_angvel(records, baseline_label(epoch))
    summary = {name: _metric_summary(records, name if name != "student" else label) for name in ("student", "baseline", *PRIMARY_CONTROLS, "teacher")}
    summary["student"] = _metric_summary(records, label)
    summary["baseline"] = _metric_summary(records, baseline_label(epoch))
    confirm_l2 = float(summary["student"].get("latent_l2") or float("nan"))
    fraction = len(teacher_worse) / max(len(tasks), 1)
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    clean = not bool(source_status.get("source_dirty", True))
    decision = bool(clean and completeness["declared_complete"])
    passed = bool(gate_ok and decision)
    history_l2 = float(reproduced["history_latent_l2"])
    recommendation = recommend_confirmation(passed, fraction, paired["zero"], history_l2, confirm_l2) if decision else None
    payload = {
        "protocol_id": cfg["protocol_id"],
        "hypothesis": cfg["h_confirm"],
        "implementation_sha": sha if clean else None,
        "source_dirty": not clean,
        "git": head,
        "decision_recorded": decision,
        "gate_pass": passed,
        "minimum_effect": float(cfg["minimum_effect"]),
        "primary_unit": "decoder after averaging its five student seeds and the confirmation tasks",
        "confirmation_epoch": epoch,
        "means": means,
        "paired_control_minus_student": gate_report | {
            "teacher": {"per_decoder": paired["teacher"], "interval": seed_level_ci(paired["teacher"])},
            "baseline": {"per_decoder": paired["baseline"], "interval": seed_level_ci(paired["baseline"])},
        },
        "secondary_student_seed_interval": seed_level_ci(_student_seed_means(records, label, cfg)),
        "secondary_student_seed_note": "This interval averages decoders inside each student seed. It is not the primary replication unit.",
        "metric_summary": summary,
        "per_decoder": _per_decoder(records, label, cfg),
        "per_task": tasks,
        "task_failures": task_failures,
        "teacher_worse_than_zero": teacher_worse,
        "recovery_fraction": recovery_fraction(means["global"], means["student"], means["teacher"], float(cfg["recovery_min_relative"])),
        "reproduction": {
            "matched": True,
            "absolute_deltas": deltas,
            "development_means": reproduced["means"],
            "train_latent_l2": reproduced["train_latent_l2"],
            "history_latent_l2": history_l2,
            "teacher_pair_median_l2": reproduced["teacher_pair_median_l2"],
            "decoder_digests": list(sink["decoder_digests"]),
            "teacher_optimizer_steps": reproduced["resources"]["teacher_optimizer_steps"],
            "student_optimizer_steps": reproduced["resources"]["student_optimizer_steps"],
        },
        "checkpoints": checkpoints,
        "teacher_bindings": teacher_rows,
        "schema": schema,
        "raw_records": records,
        "completeness": completeness,
        "declared_complete": bool(completeness["declared_complete"]),
        "resources": {
            "confirm_support_env": int(sum(ds.env_interactions for ds in supports)),
            "confirm_query_env": int(sum(ds.env_interactions for ds in queries)),
            "confirm_teacher_optimizer_steps": int(cfg["teacher_updates"]) * len(specs) * int(cfg["n_decoder_seeds"]),
            "teacher_fit_seconds_per_decoder": teacher_seconds,
            "teacher_fit_seconds_mean": float(np.mean(teacher_seconds) / len(specs)),
            "student_infer_seconds_mean": float(np.mean(student_infer_seconds)),
            "student_score_seconds": infer_seconds,
            "reproduction_resources": reproduced["resources"],
        },
        "confirmation_evaluated": True,
        "control_evaluated": False,
        "is_agi": False,
        "is_learning_to_learn": False,
        "recommendation": recommendation,
        "wall_clock_s": time.perf_counter() - t0,
    }
    _bars(Path(plot_path), ["student", "teacher", "global", "zero", "baseline", "encoder"], [means[name] for name in ("student", "teacher", "global", "zero", "baseline", "encoder")])
    payload["plot"] = str(plot_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(dumps_strict(payload))
    return payload
