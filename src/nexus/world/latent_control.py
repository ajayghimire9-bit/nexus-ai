"""Does the confirmed encoder improve H=16 pendulum control?

The planner, decoder, and epoch-200 encoder stay frozen. Returns on the four
confirmation physics are the measurement. They are not a new physics confirmation,
and they are not used to retune the latent rule.
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
from nexus.tasks.pendulum_family import PENDULUM_MAX_STEPS, pendulum_latent_confirmation
from nexus.world.baselines import run_episodes
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_optimization import _sha256
from nexus.world.context_pilot import prefix_hash
from nexus.world.direct_latent import lock_network, vector_hash
from nexus.world.frozen_dynamics import load_context_checkpoint, load_mlp_checkpoint
from nexus.world.latent_generalization import (
    _collect_checked,
    _fit_teacher,
    assert_checkpoint_hashes,
    decoder_digest,
    load_generalization_config,
    run_latent_generalization,
)
from nexus.world.latent_generalization_confirmation import (
    assert_confirmation_physics,
    load_confirmation_config,
    save_student_checkpoints,
)
from nexus.world.planning import InferenceCounter, mpc_for_model
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/latent_control.yaml")
PROTOCOL_PATH = Path("docs/NEXUS_LATENT_CONTROL.md")
PRIMARY_CONTROLS = ("zero", "encoder")
SHARED_LABELS = ("zero", "global", "encoder", "teacher")
STUDENT_LABELS = ("student", "baseline")


def load_control_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("control config must be a mapping")
    expected = _locked_config()
    if cfg != expected:
        missing = sorted(set(expected) - set(cfg))
        extra = sorted(set(cfg) - set(expected))
        drifted = sorted(key for key in expected if key in cfg and cfg[key] != expected[key])
        raise ValueError(f"control config drifted; missing={missing} extra={extra} drifted={drifted}")
    if int(cfg["horizon"]) != 16 or int(cfg["n_candidates"]) != 16:
        raise ValueError("planner recipe drifted")
    if float(cfg["minimum_effect"]) != 25:
        raise ValueError("minimum return effect drifted")
    return cfg


def _locked_config() -> dict[str, Any]:
    gen = load_generalization_config()
    conf = load_confirmation_config()
    return {
        "protocol_id": "latent_context_control_v1",
        "starting_sha": "24d9b38fb05d294ac4475613694cbb4153344ef3",
        "confirmation_artifact": "artifacts/latent_generalization_confirmation.json",
        "confirmation_artifact_sha256": "18ef526655e8d0ce9d49fe5b67f4af17997c08bff564f256354e48e1086c04fa",
        "confirm_split_hash": "baa655fcb94e61bc",
        "is_agi": False,
        "is_learning_to_learn": False,
        "retune_on_return": False,
        "h_control": (
            "The epoch-200 student context raises H=16 MPC return by at least 25 points above "
            "zero context and above the frozen encoder on the four confirmation physics."
        ),
        "horizon": 16,
        "n_candidates": 16,
        "chunk_size": 4,
        "enforce_time_budget": False,
        "support_budget": 128,
        "episodes": 4,
        "confirmation_epoch": 200,
        "n_decoder_seeds": 3,
        "n_student_seeds": 5,
        "n_parameters": 584,
        "n_decoder_parameters": 3748,
        "minimum_effect": 25,
        "catastrophic_return": -1500,
        "control_eval_env0": 110000,
        "confirm_support_env0": int(conf["confirm_support_env0"]),
        "confirm_support_base": int(conf["confirm_support_base"]),
        "confirm_task_ids": list(conf["confirm_task_ids"]),
        "confirm_physics": [list(row) for row in conf["confirm_physics"]],
        "primary_unit": "decoder",
        "time_limit_s": 1800,
        "parent_checkpoints": list(gen["parent_checkpoints"]),
        "mlp_checkpoints": [
            {"seed": 0, "path": "artifacts/context_optimization_checkpoints/seed0_mlp_u1000.pt", "sha256": "4f4db2ca0ade8d2e19cb37971cf7343959edcdc17befe73e1aa9169e19c21cc2", "hidden": [64, 64]},
            {"seed": 1, "path": "artifacts/context_optimization_checkpoints/seed1_mlp_u1000.pt", "sha256": "eb72c8c9f41d6e53a123e9f9b9aa86ce0540117e33a97c5617c164ff4456526f", "hidden": [64, 64]},
            {"seed": 2, "path": "artifacts/context_optimization_checkpoints/seed2_mlp_u1000.pt", "sha256": "58dc9209c1435543b33cb48878785a30705bc9909090510631e40f7e95b466a1", "hidden": [64, 64]},
        ],
    }


def assert_protocol_frozen(protocol_path: str | Path, cfg: dict[str, Any]) -> None:
    path = Path(protocol_path)
    if not path.is_file():
        raise RuntimeError("control is blocked until the protocol document is saved")
    text = path.read_text()
    start = text.find("<!-- protocol-lock")
    end = text.find("-->", start)
    if start < 0 or end < 0:
        raise RuntimeError("control is blocked because the protocol lock block is missing")
    locked: dict[str, str] = {}
    for line in text[start:end].splitlines():
        if ":" not in line or line.strip().startswith("<!--"):
            continue
        key, value = line.split(":", 1)
        locked[key.strip()] = value.strip()
    required = {
        "confirm_split_hash": str(cfg["confirm_split_hash"]),
        "confirmation_artifact_sha256": str(cfg["confirmation_artifact_sha256"]),
        "horizon": str(int(cfg["horizon"])),
        "n_candidates": str(int(cfg["n_candidates"])),
        "support_budget": str(int(cfg["support_budget"])),
        "episodes": str(int(cfg["episodes"])),
        "confirmation_epoch": str(int(cfg["confirmation_epoch"])),
        "n_decoder_seeds": str(int(cfg["n_decoder_seeds"])),
        "n_student_seeds": str(int(cfg["n_student_seeds"])),
        "n_parameters": str(int(cfg["n_parameters"])),
        "n_decoder_parameters": str(int(cfg["n_decoder_parameters"])),
        "minimum_effect": str(int(cfg["minimum_effect"])),
        "catastrophic_return": str(int(cfg["catastrophic_return"])),
        "control_eval_env0": str(int(cfg["control_eval_env0"])),
        "primary_unit": str(cfg["primary_unit"]),
    }
    for key, value in required.items():
        if locked.get(key) != value:
            raise RuntimeError(f"control is blocked because protocol {key}={locked.get(key)!r} is not {value!r}")


def control_env_seeds(cfg: dict[str, Any]) -> set[int]:
    seeds: set[int] = set()
    for index in range(len(cfg["confirm_task_ids"])):
        base = int(cfg["control_eval_env0"]) + 10 * index
        for episode in range(int(cfg["episodes"])):
            seeds.add(base + episode)
    return seeds


def assert_control_seeds(cfg: dict[str, Any]) -> None:
    from nexus.world.latent_generalization_confirmation import confirmation_seed_groups

    occupied = confirmation_seed_groups(load_confirmation_config())
    fresh = control_env_seeds(cfg)
    for name, seeds in occupied.items():
        overlap = fresh & seeds
        if overlap:
            raise ValueError(f"control seeds overlap {name}: {sorted(overlap)[:8]}")
    if len(fresh) != len(cfg["confirm_task_ids"]) * int(cfg["episodes"]):
        raise ValueError("control episode seeds are not one seed per episode")


def _checkpoint_rows(artifact: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    rows = [row for row in artifact["checkpoints"] if row["kind"] == kind and int(row["epoch"]) == 200]
    rows.sort(key=lambda row: (int(row["decoder"]), int(row["student"])))
    return rows


def verify_student_checkpoints(artifact: dict[str, Any], cfg: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Check the saved epoch-200 encoders. A hash miss does not overwrite the file."""
    grouped = {}
    for kind in ("broad", "baseline"):
        rows = _checkpoint_rows(artifact, kind)
        expected = int(cfg["n_decoder_seeds"]) * int(cfg["n_student_seeds"])
        if len(rows) != expected:
            raise RuntimeError(f"{kind} checkpoint count is {len(rows)}, not {expected}")
        for row in rows:
            path = Path(row["path"])
            if not path.is_file():
                raise FileNotFoundError(path)
            digest = _sha256(path)
            if digest != row["sha256"]:
                raise RuntimeError(f"checkpoint hash mismatch for {path}; refusing to replace it")
            blob = torch.load(path, map_location="cpu", weights_only=False)
            count = int(sum(tensor.numel() for tensor in blob.values()))
            if count != int(cfg["n_parameters"]):
                raise RuntimeError(f"{path} does not contain {cfg['n_parameters']} encoder parameters")
        grouped[kind] = rows
    return grouped


def reproduce_missing_checkpoints(artifact: dict[str, Any], cfg: dict[str, Any]) -> None:
    """Retrain only when a recorded file is absent. The new file must match the recorded hash."""
    missing = [row for row in artifact["checkpoints"] if not Path(row["path"]).is_file()]
    if not missing:
        return
    sink: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        run_latent_generalization(out_path=Path(tmp) / "dev.json", plot_path=Path(tmp) / "dev.svg", sink=sink)
    written = save_student_checkpoints(sink["snapshots"])
    by_path = {row["path"]: row["sha256"] for row in written}
    for row in artifact["checkpoints"]:
        if by_path.get(row["path"]) != row["sha256"]:
            raise RuntimeError(f"reproduced checkpoint {row['path']} does not match the recorded hash")
    verify_student_checkpoints(artifact, cfg)


def _install_encoder(model: Any, path: str | Path, cfg: dict[str, Any], digest: str) -> Any:
    blob = torch.load(path, map_location="cpu", weights_only=False)
    model.encoder.load_state_dict(blob)
    lock_network(model)
    if int(sum(param.numel() for param in model.encoder.parameters())) != int(cfg["n_parameters"]):
        raise RuntimeError("encoder parameter count changed while loading a student")
    if int(sum(param.numel() for param in model.net.parameters())) != int(cfg["n_decoder_parameters"]):
        raise RuntimeError("decoder parameter count changed while loading a student")
    if decoder_digest(model) != digest:
        raise RuntimeError("loading a student encoder changed the decoder")
    return model


def _fresh_decoder(path: str | Path, cfg: dict[str, Any]) -> tuple[Any, str]:
    model = load_context_checkpoint(Path(path))
    lock_network(model)
    if int(sum(param.numel() for param in model.net.parameters())) != int(cfg["n_decoder_parameters"]):
        raise RuntimeError("frozen decoder parameter count drifted")
    if int(sum(param.numel() for param in model.encoder.parameters())) != int(cfg["n_parameters"]):
        raise RuntimeError("frozen encoder parameter count drifted")
    return model, decoder_digest(model)


def control_gate(zero_deltas: list[float], encoder_deltas: list[float], minimum_effect: float) -> tuple[bool, dict[str, Any]]:
    """Positive means the student return is higher. The interval is across decoders."""
    report: dict[str, Any] = {}
    ok = True
    for name, values in (("zero", zero_deltas), ("encoder", encoder_deltas)):
        interval = seed_level_ci([float(v) for v in values])
        passed = bool(float(interval["mean"]) >= float(minimum_effect) and float(interval["lo"]) > 0.0)
        report[name] = {"per_decoder": [float(v) for v in values], "interval": interval, "pass": passed, "sign": "student_minus_control"}
        ok = ok and passed
    return ok, report


def recommend_control(
    gate: bool,
    zero_deltas: list[float],
    encoder_deltas: list[float],
    teacher_deltas: list[float],
    minimum_effect: float,
) -> str:
    """Locked reading of the returns. The same episodes are not reused for a retune."""
    if gate:
        return "independent_control_confirmation"
    zero = seed_level_ci(zero_deltas)
    encoder = seed_level_ci(encoder_deltas)
    teacher = seed_level_ci(teacher_deltas)
    crosses = float(zero["lo"]) <= 0.0 <= float(zero["hi"]) or float(encoder["lo"]) <= 0.0 <= float(encoder["hi"])
    if (float(zero["mean"]) > 0.0 or float(encoder["mean"]) > 0.0) and crosses:
        return "inconclusive"
    signed = float(zero["lo"]) > 0.0 and float(encoder["lo"]) > 0.0
    if signed and (float(zero["mean"]) < float(minimum_effect) or float(encoder["mean"]) < float(minimum_effect)):
        return "below_minimum_effect"
    teacher_pass = float(teacher["mean"]) >= float(minimum_effect) and float(teacher["lo"]) > 0.0
    if teacher_pass:
        return "latent_mismatch"
    if float(zero["mean"]) <= 0.0 and float(teacher["mean"]) <= 0.0:
        return "planning_mechanism"
    return "prediction_control_gap"


def _mean_return(records: list[dict[str, Any]], label: str, decoder: int | None = None, task: str | None = None) -> float:
    values = [
        float(row["mean_return"])
        for row in records
        if row["label"] == label and (decoder is None or row.get("decoder") == decoder) and (task is None or row["task"] == task)
    ]
    return float(np.mean(values)) if values else float("nan")


def decoder_return_deltas(records: list[dict[str, Any]], control: str, cfg: dict[str, Any]) -> list[float]:
    return [
        _mean_return(records, "student", decoder) - _mean_return(records, control, decoder)
        for decoder in range(int(cfg["n_decoder_seeds"]))
    ]


def _evaluate_mpc(spec: Any, model: Any, eval_seed: int, episodes: int, catastrophic_at: float) -> dict[str, Any]:
    counter = InferenceCounter(model)
    planner = mpc_for_model(model, seed=0, inference=counter, enforce_time_budget=False)
    if int(planner.horizon) != 16 or int(planner.n_candidates) != 16 or planner.enforce_time_budget:
        raise RuntimeError("planner recipe is not the locked H=16, 16-candidate pendulum controller")
    plan_ms: list[float] = []
    predicted: list[float] = []
    actions: list[int] = []
    first_actions: list[int] = []
    awaiting_first = {"value": False}

    def act(obs: np.ndarray) -> int:
        action, meta = planner.act(obs)
        if int(meta["n_scored"]) != 16:
            raise RuntimeError("a controller scored fewer than 16 candidate sequences")
        if awaiting_first["value"]:
            first_actions.append(int(action))
            awaiting_first["value"] = False
        plan_ms.append(float(meta["plan_ms"]))
        predicted.append(float(meta["best_score"]))
        actions.append(int(action))
        return int(action)

    def start(episode: int, planner=planner, seed=eval_seed) -> None:
        planner.reset_episode(int(seed) + 1000 * int(episode))
        awaiting_first["value"] = True

    row = run_episodes(
        spec,
        act_fn=act,
        episodes=int(episodes),
        seed=int(eval_seed),
        max_steps=PENDULUM_MAX_STEPS,
        on_episode_start=start,
    )
    returns = [float(value) for value in row["returns"]]
    catastrophic = [bool(value <= float(catastrophic_at)) for value in returns]
    return {
        "mean_return": float(row["mean_return"]),
        "returns": returns,
        "catastrophic_rate": float(np.mean(catastrophic)) if catastrophic else float("nan"),
        "catastrophic_episodes": int(sum(catastrophic)),
        "env_interactions": int(row["env_interactions"]),
        "mean_plan_ms": float(np.mean(plan_ms)) if plan_ms else float("nan"),
        "mean_predicted_score": float(np.mean(predicted)) if predicted else float("nan"),
        "first_actions": first_actions,
        "model_states": int(counter.states),
        "n_decisions": len(actions),
        "eval_seed": int(eval_seed),
    }


def _completeness(records: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for decoder in range(int(cfg["n_decoder_seeds"])):
        for task in cfg["confirm_task_ids"]:
            for student in range(int(cfg["n_student_seeds"])):
                for label in STUDENT_LABELS:
                    if not any(row["decoder"] == decoder and row["task"] == task and row.get("student") == student and row["label"] == label for row in records):
                        failures.append(f"missing decoder={decoder} student={student} task={task} label={label}")
            for label in SHARED_LABELS:
                if not any(row["decoder"] == decoder and row["task"] == task and row.get("student") is None and row["label"] == label for row in records):
                    failures.append(f"missing decoder={decoder} task={task} label={label}")
    for seed in range(len(cfg["mlp_checkpoints"])):
        for task in cfg["confirm_task_ids"]:
            if not any(row["label"] == "mlp" and row.get("mlp_seed") == seed and row["task"] == task for row in records):
                failures.append(f"missing mlp seed={seed} task={task}")
    return {"declared_complete": not failures, "failures": failures}


def _task_table(records: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for task, physics in zip(cfg["confirm_task_ids"], cfg["confirm_physics"]):
        item = {"task": task, "physics": list(physics)}
        for label in ("student", "baseline", *SHARED_LABELS):
            item[label] = _mean_return(records, label, task=task)
        item["student_above_zero"] = bool(item["student"] > item["zero"])
        item["student_above_encoder"] = bool(item["student"] > item["encoder"])
        item["student_above_global"] = bool(item["student"] > item["global"])
        item["teacher_above_zero"] = bool(item["teacher"] > item["zero"])
        rows.append(item)
    return rows


def _bars(path: Path, labels: list[str], values: list[float]) -> None:
    width, height, pad = 720, 320, 56
    finite = [float(value) for value in values if np.isfinite(value)]
    lo = min(finite) if finite else -1.0
    hi = max(finite) if finite else 0.0
    if hi - lo < 1.0:
        hi = lo + 1.0
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">', '<rect width="100%" height="100%" fill="white"/>']
    bar_w = (width - 2 * pad) / max(len(labels), 1)
    for index, (label, value) in enumerate(zip(labels, values)):
        if not np.isfinite(value):
            continue
        top = pad + (height - 2 * pad) * (hi - float(value)) / (hi - lo)
        bottom = height - pad
        x = pad + index * bar_w + 8
        parts.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bar_w - 16:.1f}" height="{max(bottom - top, 1):.1f}" fill="#1f4e79"/>')
        parts.append(f'<text x="{x:.1f}" y="{height - 16}" font-size="11">{label}</text>')
        parts.append(f'<text x="{x:.1f}" y="{max(top - 4, 12):.1f}" font-size="11">{float(value):.0f}</text>')
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts))


def run_latent_control(
    *,
    protocol_path: str | Path = PROTOCOL_PATH,
    out_path: str | Path = "artifacts/latent_control.json",
    plot_path: str | Path = "artifacts/latent_control.svg",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = load_control_config()
    assert_protocol_frozen(protocol_path, cfg)
    conf = load_confirmation_config()
    assert_confirmation_physics(conf)
    if cfg["confirm_task_ids"] != conf["confirm_task_ids"] or cfg["confirm_physics"] != [list(row) for row in conf["confirm_physics"]]:
        raise RuntimeError("control physics drifted from the confirmation split")
    assert_control_seeds(cfg)
    gen = load_generalization_config()
    assert_checkpoint_hashes(gen)
    for row in cfg["mlp_checkpoints"]:
        if _sha256(Path(row["path"])) != row["sha256"]:
            raise RuntimeError(f"MLP reference hash mismatch for {row['path']}")
    artifact_path = Path(cfg["confirmation_artifact"])
    if hashlib.sha256(artifact_path.read_bytes()).hexdigest() != cfg["confirmation_artifact_sha256"]:
        raise RuntimeError("confirmation artifact hash mismatch; control stays closed")
    artifact = json.loads(artifact_path.read_text())
    try:
        checkpoints = verify_student_checkpoints(artifact, cfg)
    except FileNotFoundError:
        reproduce_missing_checkpoints(artifact, cfg)
        checkpoints = verify_student_checkpoints(artifact, cfg)
    deadline = t0 + float(cfg["time_limit_s"])
    specs = pendulum_latent_confirmation()
    forbidden = set(gen["forbidden_task_ids"])
    budget = int(cfg["support_budget"])
    supports = []
    for index, spec in enumerate(specs):
        support = _collect_checked(spec, budget, int(cfg["confirm_support_env0"]) + 10 * index, int(cfg["confirm_support_base"]) + index, forbidden)
        digest = prefix_hash(support, budget)
        expected = {row["support_hash"] for row in artifact["teacher_bindings"] if row["task"] == spec.task_id}
        if expected != {digest}:
            raise RuntimeError(f"support for {spec.task_id} is not the confirmation support; control stays closed")
        supports.append(support)
    selection = json.loads(Path(gen["prior_selection"]).read_text())["selection_record"]
    records: list[dict[str, Any]] = []
    teacher_seconds = []
    infer_seconds = []
    support_interactions = int(sum(ds.env_interactions for ds in supports))
    for decoder, parent in enumerate(cfg["parent_checkpoints"]):
        if time.perf_counter() > deadline:
            raise RuntimeError("control exceeded the time cap before the grid was complete")
        model, digest = _fresh_decoder(parent["path"], cfg)
        global_z = torch.tensor(selection["global_vectors"][str(decoder)], dtype=torch.float32)
        if vector_hash(global_z) != parent["global_vector_sha256"]:
            raise RuntimeError(f"global vector hash mismatch for decoder {decoder}")
        teachers = []
        for task_index, support in enumerate(supports):
            started = time.perf_counter()
            vector = _fit_teacher(model, support, global_z)
            teacher_seconds.append(time.perf_counter() - started)
            if decoder_digest(model) != digest:
                raise RuntimeError("teacher fit changed the decoder")
            expected_hash = next(row["vector_sha256"] for row in artifact["teacher_bindings"] if int(row["decoder"]) == decoder and row["task"] == specs[task_index].task_id)
            if vector_hash(vector) != expected_hash:
                raise RuntimeError(f"teacher latent for {specs[task_index].task_id} does not match the confirmation fit")
            teachers.append(vector.detach().clone())
        broad = [row for row in checkpoints["broad"] if int(row["decoder"]) == decoder]
        baseline = [row for row in checkpoints["baseline"] if int(row["decoder"]) == decoder]
        for task_index, spec in enumerate(specs):
            eval_seed = int(cfg["control_eval_env0"]) + 10 * task_index
            shared = {
                "zero": torch.zeros(8),
                "global": global_z.detach().clone(),
                "teacher": teachers[task_index],
            }
            for label, vector in shared.items():
                probe, probe_digest = _fresh_decoder(parent["path"], cfg)
                if probe_digest != digest:
                    raise RuntimeError("decoder digest drifted before control")
                probe.z = vector.detach().clone()
                outcome = _evaluate_mpc(spec, probe, eval_seed, int(cfg["episodes"]), float(cfg["catastrophic_return"]))
                records.append({"decoder": decoder, "student": None, "task": spec.task_id, "label": label, "infer_seconds": 0.0, **outcome})
                print(f"control decoder={decoder} task={spec.task_id} label={label} return={outcome['mean_return']:.1f}", flush=True)
            probe, _ = _fresh_decoder(parent["path"], cfg)
            started = time.perf_counter()
            probe.set_context_from_dataset(supports[task_index], budget=budget)
            infer_seconds.append(time.perf_counter() - started)
            outcome = _evaluate_mpc(spec, probe, eval_seed, int(cfg["episodes"]), float(cfg["catastrophic_return"]))
            records.append({"decoder": decoder, "student": None, "task": spec.task_id, "label": "encoder", "infer_seconds": infer_seconds[-1], **outcome})
            print(f"control decoder={decoder} task={spec.task_id} label=encoder return={outcome['mean_return']:.1f}", flush=True)
            for student in range(int(cfg["n_student_seeds"])):
                for label, rows in (("student", broad), ("baseline", baseline)):
                    probe, _ = _fresh_decoder(parent["path"], cfg)
                    path = next(row["path"] for row in rows if int(row["student"]) == student)
                    _install_encoder(probe, path, cfg, digest)
                    started = time.perf_counter()
                    probe.set_context_from_dataset(supports[task_index], budget=budget)
                    elapsed = time.perf_counter() - started
                    infer_seconds.append(elapsed)
                    outcome = _evaluate_mpc(spec, probe, eval_seed, int(cfg["episodes"]), float(cfg["catastrophic_return"]))
                    records.append({"decoder": decoder, "student": student, "task": spec.task_id, "label": label, "infer_seconds": elapsed, **outcome})
                    print(f"control decoder={decoder} student={student} task={spec.task_id} label={label} return={outcome['mean_return']:.1f}", flush=True)
    mlp_parameters = None
    for row in cfg["mlp_checkpoints"]:
        mlp = load_mlp_checkpoint(Path(row["path"]), tuple(row["hidden"]))
        mlp_parameters = int(sum(param.numel() for param in mlp.net.parameters()))
        for task_index, spec in enumerate(specs):
            eval_seed = int(cfg["control_eval_env0"]) + 10 * task_index
            outcome = _evaluate_mpc(spec, mlp, eval_seed, int(cfg["episodes"]), float(cfg["catastrophic_return"]))
            records.append({"decoder": None, "student": None, "mlp_seed": int(row["seed"]), "task": spec.task_id, "label": "mlp", "infer_seconds": 0.0, **outcome})
            print(f"control mlp={row['seed']} task={spec.task_id} return={outcome['mean_return']:.1f}", flush=True)
    completeness = _completeness(records, cfg)
    paired = {name: decoder_return_deltas(records, name, cfg) for name in (*PRIMARY_CONTROLS, "global", "teacher", "baseline")}
    gate_ok, gate_report = control_gate(paired["zero"], paired["encoder"], float(cfg["minimum_effect"]))
    tasks = _task_table(records, cfg)
    gains = sum(1 for row in tasks if row["student_above_zero"])
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    clean = not bool(source_status.get("source_dirty", True))
    decision = bool(clean and completeness["declared_complete"])
    passed = bool(gate_ok and decision)
    recommendation = recommend_control(passed, paired["zero"], paired["encoder"], paired["teacher"], float(cfg["minimum_effect"])) if decision else None
    sample, _ = _fresh_decoder(cfg["parent_checkpoints"][0]["path"], cfg)
    means = {label: _mean_return(records, label) for label in ("student", "baseline", *SHARED_LABELS, "mlp")}
    payload = {
        "protocol_id": cfg["protocol_id"],
        "hypothesis": cfg["h_control"],
        "implementation_sha": sha if clean else None,
        "source_dirty": not clean,
        "git": head,
        "decision_recorded": decision,
        "gate_pass": passed,
        "inconclusive": bool(recommendation == "inconclusive"),
        "minimum_effect": float(cfg["minimum_effect"]),
        "primary_unit": "decoder after averaging its five student seeds, four tasks, and four episodes",
        "means": means,
        "paired_student_minus_control": gate_report | {
            name: {"per_decoder": paired[name], "interval": seed_level_ci(paired[name]), "sign": "student_minus_control"}
            for name in ("global", "teacher", "baseline")
        },
        "per_decoder": [
            {"decoder": decoder, **{label: _mean_return(records, label, decoder) for label in ("student", "baseline", *SHARED_LABELS)}}
            for decoder in range(int(cfg["n_decoder_seeds"]))
        ],
        "per_task": tasks,
        "gains_across_tasks": int(gains),
        "gains_concentrated": bool(gains < 3),
        "catastrophic_rate": {
            label: float(np.mean([row["catastrophic_rate"] for row in records if row["label"] == label]))
            for label in ("student", "baseline", *SHARED_LABELS, "mlp")
        },
        "latency": {
            "mean_plan_ms": float(np.mean([row["mean_plan_ms"] for row in records])),
            "encoder_infer_seconds_mean": float(np.mean(infer_seconds)) if infer_seconds else None,
            "teacher_fit_seconds_mean": float(np.mean(teacher_seconds)) if teacher_seconds else None,
        },
        "resources": {
            "encoder_parameters": int(cfg["n_parameters"]),
            "decoder_parameters": int(cfg["n_decoder_parameters"]),
            "mlp_parameters": mlp_parameters,
            "encoder_bytes": int(sum(param.detach().nbytes for param in sample.encoder.parameters())),
            "decoder_bytes": int(sum(param.detach().nbytes for param in sample.net.parameters())),
            "support_env_interactions": support_interactions,
            "control_env_interactions": int(sum(row["env_interactions"] for row in records)),
            "imagined_model_states": int(sum(row["model_states"] for row in records)),
        },
        "checkpoints_verified": True,
        "schema_failures": completeness["failures"],
        "declared_complete": bool(completeness["declared_complete"]),
        "raw_records": records,
        "control_evaluated": True,
        "is_agi": False,
        "is_learning_to_learn": False,
        "recommendation": recommendation,
        "wall_clock_s": time.perf_counter() - t0,
    }
    labels = ["student", "teacher", "baseline", "mlp", "encoder", "zero", "global"]
    _bars(Path(plot_path), labels, [means[label] for label in labels])
    payload["plot"] = str(plot_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(dumps_strict(payload))
    return payload
