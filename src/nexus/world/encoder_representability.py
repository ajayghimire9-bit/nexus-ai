"""Can the existing mean-pooling encoder reproduce the saved teacher codes?

Training labels are the eight meta-training vectors already stored per decoder.
A second support fit is a consistency check. It is not a new label.
Development query error is not a selection criterion. Confirmation physics are not collected.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml
from torch import nn

from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import pendulum_context_train
from nexus.world.amortized_latent import amortized_seed_groups, decoder_digest, load_amortized_config
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_model import CONTEXT_DIM, ENCODER_HIDDEN
from nexus.world.context_optimization import _sha256
from nexus.world.context_pilot import _collect, prefix_hash
from nexus.world.data import TransitionDataset
from nexus.world.direct_latent import fit_from_support, lock_network, vector_hash
from nexus.world.frozen_dynamics import load_context_checkpoint, planned_env_seeds
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/encoder_representability.yaml")
PROTOCOL_PATH = Path("docs/NEXUS_ENCODER_REPRESENTABILITY.md")
TEACHER_LR = 0.1
TEACHER_UPDATES = 256


def load_representability_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("representability config must be a mapping")
    expected = _locked_config()
    if cfg != expected:
        missing = sorted(set(expected) - set(cfg))
        extra = sorted(set(cfg) - set(expected))
        drifted = sorted(key for key in expected if key in cfg and cfg[key] != expected[key])
        raise ValueError(f"representability config drifted; missing={missing} extra={extra} drifted={drifted}")
    if 0.001 not in [float(v) for v in cfg["learning_rates"]]:
        raise ValueError("the previous learning rate 0.001 is missing")
    if int(cfg["max_steps"]) != 2000 or int(cfg["log_steps"][-1]) != int(cfg["max_steps"]):
        raise ValueError("the step budget is not closed at the final log step")
    if int(cfg["encoder_hidden"]) != ENCODER_HIDDEN or int(cfg["context_dim"]) != CONTEXT_DIM:
        raise ValueError("encoder capacity drifted")
    if int(cfg["n_parameters"]) != 584:
        raise ValueError("parameter count drifted")
    return cfg


def _locked_config() -> dict[str, Any]:
    return {
        "protocol_id": "encoder_representability_v1",
        "starting_sha": "e657935e60074964069a9075fa46696fd1cf9312",
        "teacher_artifact": "artifacts/amortized_latent_dev.json",
        "teacher_artifact_sha256": "cd120f53ffdd1efbaaff8b632faad01b251e3b4e4afccd201af28c267ac1162f",
        "prior_selection": "artifacts/direct_latent_selection.json",
        "prior_selection_sha256": "ef99a31fd1c50ee27e4de35dff6c810397a22ab267622d1b4aa938cf4ffb5c5f",
        "forbidden_confirm_hash": "87b83c41be34aa1a",
        "amort_confirm_hash": "d1fa621351d286cf",
        "is_agi": False,
        "is_learning_to_learn": False,
        "control_sweep": False,
        "confirmation_evaluated": False,
        "h_represent": (
            "The existing 584-parameter mean-pooling encoder can reproduce the eight saved "
            "meta-training teacher latents on the support that defined them."
        ),
        "n_decoder_seeds": 3,
        "n_tasks": 8,
        "support_budget": 128,
        "encoder_hidden": 32,
        "context_dim": 8,
        "n_parameters": 584,
        "teacher_learning_rate": 0.1,
        "teacher_updates": 256,
        "learning_rates": [0.001, 0.01, 0.1],
        "max_steps": 2000,
        "log_steps": [0, 1, 100, 400, 1000, 2000],
        "mean_l2_threshold": 0.25,
        "max_l2_threshold": 0.5,
        "equivalence_l2": 0.5,
        "equivalence_relative_gap": 0.1,
        "equivalence_fraction": 0.5,
        "grad_vanish_norm": "1e-8",
        "meta_support_env0": 72000,
        "meta_support_base": 255000,
        "consistency_env0": 90000,
        "consistency_base": 261000,
        "time_limit_s": 600,
        "meta_task_ids": [f"pendulum_ctx_tr{i}" for i in range(8)],
        "forbidden_task_ids": [f"pendulum_ctx_c{i}" for i in range(4)] + [f"pendulum_amort_c{i}" for i in range(4)],
        "parent_checkpoints": [
            {"seed": 0, "path": "artifacts/frozen_dynamics_checkpoints/seed0_history_u1000.pt", "sha256": "83e90a9b187cdffe5e39d794ce86abf65ef891fde011daf8e55b7eee1f348959", "global_vector_sha256": "d40d71a3e5c0e62ef158e08ec82617f10a8f6fcfeaac436744c9e9958b31f8ba"},
            {"seed": 1, "path": "artifacts/frozen_dynamics_checkpoints/seed1_history_u1000.pt", "sha256": "cd5400070a69238ce8e35ca036c57448b18664f7ce1e8600ac5a3aab2983ef3e", "global_vector_sha256": "4705c19a62e0547267705e1b10aeb4f06c1a62058ab077534b24a8f2cc4fdb33"},
            {"seed": 2, "path": "artifacts/frozen_dynamics_checkpoints/seed2_history_u1000.pt", "sha256": "254b097c5dbd3df02c463913c60392928aaed0584c6c29245e060ed25113b6fd", "global_vector_sha256": "9910f28a645a7a4d8a714cf0523f6c8a9c7b58b7dd71103e96a511583be31218"},
        ],
    }


def _fmt_rate(value: float) -> str:
    return f"{float(value):.3f}".rstrip("0").rstrip(".")


def assert_protocol_frozen(protocol_path: str | Path, cfg: dict[str, Any]) -> None:
    path = Path(protocol_path)
    if not path.is_file():
        raise RuntimeError("representability is blocked until the protocol document is saved")
    text = path.read_text()
    start = text.find("<!-- protocol-lock")
    end = text.find("-->", start)
    if start < 0 or end < 0:
        raise RuntimeError("representability is blocked because the protocol lock block is missing")
    locked: dict[str, str] = {}
    for line in text[start:end].splitlines():
        if ":" not in line or line.strip().startswith("<!--"):
            continue
        key, value = line.split(":", 1)
        locked[key.strip()] = value.strip()
    required = {
        "teacher_artifact_sha256": str(cfg["teacher_artifact_sha256"]),
        "forbidden_confirm_hash": str(cfg["forbidden_confirm_hash"]),
        "amort_confirm_hash": str(cfg["amort_confirm_hash"]),
        "teacher_lr": f"{float(cfg['teacher_learning_rate']):.1f}",
        "teacher_updates": str(int(cfg["teacher_updates"])),
        "learning_rates": ",".join(_fmt_rate(v) for v in cfg["learning_rates"]),
        "max_steps": str(int(cfg["max_steps"])),
        "mean_l2_threshold": f"{float(cfg['mean_l2_threshold']):.2f}",
        "max_l2_threshold": f"{float(cfg['max_l2_threshold']):.1f}",
        "equivalence_l2": f"{float(cfg['equivalence_l2']):.1f}",
        "equivalence_relative_gap": f"{float(cfg['equivalence_relative_gap']):.1f}",
        "grad_vanish_norm": str(cfg["grad_vanish_norm"]),
        "consistency_env0": str(int(cfg["consistency_env0"])),
        "meta_support_env0": str(int(cfg["meta_support_env0"])),
        "n_parameters": str(int(cfg["n_parameters"])),
    }
    for key, value in required.items():
        if locked.get(key) != value:
            raise RuntimeError(f"representability is blocked because protocol {key}={locked.get(key)!r} is not {value!r}")


def assert_saved_targets(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(cfg["teacher_artifact"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != cfg["teacher_artifact_sha256"]:
        raise RuntimeError("saved teacher artifact hash mismatch")
    payload = json.loads(path.read_text())
    rows = [row for row in payload["teachers"] if row["split"] == "meta"]
    expected_tasks = list(cfg["meta_task_ids"])
    if len(rows) != int(cfg["n_decoder_seeds"]) * len(expected_tasks):
        raise RuntimeError("saved meta-training teachers are incomplete")
    for decoder in range(int(cfg["n_decoder_seeds"])):
        got = [row["task"] for row in rows if int(row["decoder"]) == decoder]
        if got != expected_tasks:
            raise RuntimeError(f"decoder {decoder} teacher tasks drifted")
        parent = cfg["parent_checkpoints"][decoder]
        for row in rows:
            if int(row["decoder"]) != decoder:
                continue
            if row["checkpoint_sha256"] != parent["sha256"]:
                raise RuntimeError("saved teacher checkpoint hash drifted")
            vector = torch.tensor(row["vector"], dtype=torch.float32)
            if vector_hash(vector) != row["vector_sha256"]:
                raise RuntimeError(f"saved teacher vector hash mismatch for {row['task']}")
    forbidden = set(cfg["forbidden_task_ids"])
    if forbidden & {row["task"] for row in rows}:
        raise RuntimeError("a reserved confirmation task is among the training labels")
    return rows


def representability_seed_groups(cfg: dict[str, Any]) -> dict[str, set[int]]:
    groups = amortized_seed_groups(load_amortized_config())
    seeds: set[int] = set()
    for i in range(len(cfg["meta_task_ids"])):
        seeds |= planned_env_seeds(int(cfg["support_budget"]), int(cfg["consistency_env0"]) + 10 * i)
    groups["represent_consistency"] = seeds
    return groups


def assert_seeds_disjoint(cfg: dict[str, Any]) -> None:
    named = representability_seed_groups(cfg)
    keys = list(named)
    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            overlap = named[left] & named[right]
            if overlap:
                raise ValueError(f"collect seeds overlap between {left} and {right}: {sorted(overlap)[:8]}")


def assert_checkpoint_hashes(cfg: dict[str, Any]) -> None:
    for row in cfg["parent_checkpoints"]:
        if _sha256(Path(row["path"])) != row["sha256"]:
            raise RuntimeError(f"checkpoint hash mismatch for {row['path']}")
    selection_path = Path(cfg["prior_selection"])
    if hashlib.sha256(selection_path.read_bytes()).hexdigest() != cfg["prior_selection_sha256"]:
        raise RuntimeError("global-vector artifact hash mismatch")


def distances(preds: list[torch.Tensor], targets: list[torch.Tensor]) -> list[float]:
    return [float(torch.linalg.vector_norm(pred.detach() - target.detach()).item()) for pred, target in zip(preds, targets)]


def output_rms(vectors: list[torch.Tensor]) -> float:
    stacked = torch.stack([vector.detach().float() for vector in vectors])
    centered = stacked - stacked.mean(dim=0)
    return float(torch.sqrt((centered * centered).mean()).item())


def constant_code(targets: list[torch.Tensor]) -> torch.Tensor:
    return torch.stack([target.detach().float() for target in targets]).mean(dim=0)


def decoder_passes(mean_l2: float, max_l2: float, constant_l2: float, cfg: dict[str, Any]) -> bool:
    return bool(
        np.isfinite(mean_l2)
        and np.isfinite(max_l2)
        and np.isfinite(constant_l2)
        and float(mean_l2) <= float(cfg["mean_l2_threshold"])
        and float(max_l2) <= float(cfg["max_l2_threshold"])
        and float(mean_l2) < float(constant_l2)
    )


def trajectory_complete(steps: list[int], required: list[int]) -> bool:
    return set(int(step) for step in steps) == set(int(step) for step in required)


def _relative_gap(foreign: float, native: float) -> float:
    return abs(float(foreign) - float(native)) / max(abs(float(native)), 1e-8)


def pair_is_equivalent(l2: float, gap_saved_support: float, gap_new_support: float, cfg: dict[str, Any]) -> bool:
    return bool(
        float(l2) > float(cfg["equivalence_l2"])
        and float(gap_saved_support) < float(cfg["equivalence_relative_gap"])
        and float(gap_new_support) < float(cfg["equivalence_relative_gap"])
    )


def decoder_is_ambiguous(median_l2: float, n_far: int, n_equivalent: int, cfg: dict[str, Any]) -> bool:
    if not np.isfinite(median_l2) or float(median_l2) <= float(cfg["equivalence_l2"]) or int(n_far) <= 0:
        return False
    return (float(n_equivalent) / float(n_far)) >= float(cfg["equivalence_fraction"])


def choose_learning_rate(summary: dict[float, float]) -> float:
    """Lowest mean training distance at the final step. Ties prefer the lower rate."""
    if not summary:
        raise ValueError("no learning-rate scores")
    ranked = sorted((float(distance), float(rate)) for rate, distance in summary.items())
    return float(ranked[0][1])


def recommend(representable: bool, ambiguous: bool, grad_norm: float | None, cfg: dict[str, Any]) -> str:
    if ambiguous:
        return "null_space"
    if representable:
        return "generalization"
    vanish = float(cfg["grad_vanish_norm"])
    if grad_norm is not None and np.isfinite(grad_norm) and float(grad_norm) < vanish:
        return "optimizer"
    return "attention_pool"


def _support_loss(model: Any, ds: TransitionDataset, vector: torch.Tensor) -> float:
    with torch.no_grad():
        value = model.query_loss(ds.obs, ds.action, ds.next_obs, ds.terminated, vector.detach())
    if not torch.isfinite(value):
        raise RuntimeError("support loss was nonfinite")
    return float(value.item())


def _encode_batch(model: Any, supports: list[TransitionDataset], teachers: list[torch.Tensor]) -> tuple[torch.Tensor, list[torch.Tensor], list[float]]:
    losses = []
    vectors = []
    dists = []
    for support, teacher in zip(supports, teachers):
        z = model.encode(support.obs, support.action, support.next_obs, differentiable=True)
        losses.append(nn.functional.mse_loss(z, teacher.detach()))
        vectors.append(z)
        dists.append(float(torch.linalg.vector_norm(z.detach() - teacher.detach()).item()))
    return torch.stack(losses).mean(), vectors, dists


def train_encoder(
    model: Any,
    supports: list[TransitionDataset],
    teachers: list[torch.Tensor],
    tasks: list[str],
    *,
    lr: float,
    steps: int,
    log_steps: list[int],
    init_state: dict[str, torch.Tensor],
    decoder_before: str,
) -> list[dict[str, Any]]:
    """Full-batch distillation for a fixed step budget. The decoder is not a parameter."""
    if int(model.encoder.hidden) != ENCODER_HIDDEN or int(model.encoder.z_dim) != CONTEXT_DIM:
        raise RuntimeError("refusing to train an encoder whose capacity differs from the existing history encoder")
    if int(sum(param.numel() for param in model.encoder.parameters())) != 584:
        raise RuntimeError("encoder parameter count is not 584")
    model.encoder.load_state_dict(init_state)
    for param in model.encoder.parameters():
        param.requires_grad_(True)
    for param in model.net.parameters():
        param.requires_grad_(False)
    opt = torch.optim.Adam(model.encoder.parameters(), lr=float(lr))
    wanted = {int(step) for step in log_steps}
    logs: list[dict[str, Any]] = []

    def snapshot(step: int, dists: list[float], vectors: list[torch.Tensor], loss: float, grad_norm: float | None) -> None:
        logs.append({
            "step": int(step),
            "mean_l2": float(np.mean(dists)),
            "max_l2": float(np.max(dists)),
            "mean_mse": float(loss),
            "grad_norm": grad_norm,
            "output_rms": output_rms(vectors),
            "per_task": [{"task": task, "l2": float(dist)} for task, dist in zip(tasks, dists)],
        })

    with torch.no_grad():
        initial, vectors, dists = _encode_batch(model, supports, teachers)
    if 0 in wanted:
        snapshot(0, dists, vectors, float(initial.item()), None)
    for step in range(1, int(steps) + 1):
        opt.zero_grad(set_to_none=True)
        loss, _vectors, _dists = _encode_batch(model, supports, teachers)
        if not torch.isfinite(loss.detach()):
            raise RuntimeError("representability training produced a nonfinite loss; refusing to continue")
        loss.backward()
        grads = []
        for param in model.encoder.parameters():
            if param.grad is None or not torch.isfinite(param.grad).all():
                raise RuntimeError("encoder gradient was missing or nonfinite; refusing to continue")
            grads.append(param.grad.detach().reshape(-1))
        for name, param in model.net.named_parameters():
            if param.grad is not None:
                raise RuntimeError(f"decoder parameter {name} received a gradient")
        grad_norm = float(torch.cat(grads).norm().item())
        opt.step()
        if decoder_digest(model) != decoder_before:
            raise RuntimeError("encoder training changed the decoder or normalization")
        if step in wanted:
            with torch.no_grad():
                after, vectors, dists = _encode_batch(model, supports, teachers)
            snapshot(step, dists, vectors, float(after.item()), grad_norm)
    if not trajectory_complete([row["step"] for row in logs], list(log_steps)):
        raise RuntimeError("training trajectory is missing a locked log step")
    return logs


def _collect_checked(spec: Any, n: int, env0: int, base: int, forbidden: set[str]) -> TransitionDataset:
    if spec.task_id in forbidden:
        raise RuntimeError(f"refusing to collect reserved task {spec.task_id}")
    ds = _collect(spec, n, env0=env0, base=base)
    expected = planned_env_seeds(n, env0)
    if {int(seed) for seed in np.unique(ds.seed)} != expected:
        raise RuntimeError(f"collect seeds drifted for {spec.task_id}")
    return ds


def run_encoder_representability(
    *,
    protocol_path: str | Path = PROTOCOL_PATH,
    out_path: str | Path = "artifacts/encoder_representability.json",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = load_representability_config()
    assert_protocol_frozen(protocol_path, cfg)
    assert_checkpoint_hashes(cfg)
    assert_seeds_disjoint(cfg)
    saved_rows = assert_saved_targets(cfg)
    specs = pendulum_context_train()
    if [spec.task_id for spec in specs] != list(cfg["meta_task_ids"]):
        raise RuntimeError("meta-training task ids drifted")
    forbidden = set(cfg["forbidden_task_ids"])
    budget = int(cfg["support_budget"])
    supports = [
        _collect_checked(spec, budget, int(cfg["meta_support_env0"]) + 10 * i, int(cfg["meta_support_base"]) + i, forbidden)
        for i, spec in enumerate(specs)
    ]
    for i, spec in enumerate(specs):
        saved_hashes = {row["support_hash"] for row in saved_rows if row["task"] == spec.task_id}
        if saved_hashes != {prefix_hash(supports[i], budget)}:
            raise RuntimeError(f"recollected support hash mismatch for {spec.task_id}")
    consistency_supports = [
        _collect_checked(spec, budget, int(cfg["consistency_env0"]) + 10 * i, int(cfg["consistency_base"]) + i, forbidden)
        for i, spec in enumerate(specs)
    ]
    selection = json.loads(Path(cfg["prior_selection"]).read_text())["selection_record"]
    if float(selection["chosen_lr"]) != TEACHER_LR or int(selection["chosen_updates"]) != TEACHER_UPDATES:
        raise RuntimeError("the stored teacher rule does not match the locked procedure")
    runs: list[dict[str, Any]] = []
    consistency: list[dict[str, Any]] = []
    resources = {"encoder_optimizer_steps": 0, "consistency_optimizer_steps": 0, "support_env": 0, "consistency_env": 0}
    resources["support_env"] = int(sum(ds.env_interactions for ds in supports))
    resources["consistency_env"] = int(sum(ds.env_interactions for ds in consistency_supports))
    deadline = t0 + float(cfg["time_limit_s"])
    for decoder in range(int(cfg["n_decoder_seeds"])):
        if time.perf_counter() > deadline:
            raise RuntimeError("representability exceeded the time cap")
        parent = cfg["parent_checkpoints"][decoder]
        model = load_context_checkpoint(Path(parent["path"]))
        lock_network(model)
        digest = decoder_digest(model)
        init_state = {key: value.detach().cpu().clone() for key, value in model.encoder.state_dict().items()}
        global_z = torch.tensor(selection["global_vectors"][str(decoder)], dtype=torch.float32)
        if vector_hash(global_z) != parent["global_vector_sha256"]:
            raise RuntimeError(f"global vector hash mismatch for decoder {decoder}")
        teachers = [torch.tensor(row["vector"], dtype=torch.float32) for row in saved_rows if int(row["decoder"]) == decoder]
        if [vector_hash(vector) for vector in teachers] != [row["vector_sha256"] for row in saved_rows if int(row["decoder"]) == decoder]:
            raise RuntimeError("training targets do not match the saved teacher hashes")
        const = constant_code(teachers)
        const_dists = distances([const for _task in teachers], teachers)
        for task_index, spec in enumerate(specs):
            fitted = fit_from_support(
                model, consistency_supports[task_index], global_z,
                lr=TEACHER_LR, updates=TEACHER_UPDATES, snapshot_at=(TEACHER_UPDATES,),
            )
            resources["consistency_optimizer_steps"] += TEACHER_UPDATES
            if decoder_digest(model) != digest:
                raise RuntimeError("consistency fit changed the decoder")
            other = fitted["snapshots"][TEACHER_UPDATES]
            saved = teachers[task_index]
            l2 = float(torch.linalg.vector_norm(saved - other).item())
            cosine = float(torch.nn.functional.cosine_similarity(saved.reshape(1, -1), other.reshape(1, -1)).item())
            loss_saved_on_saved = _support_loss(model, supports[task_index], saved)
            loss_other_on_saved = _support_loss(model, supports[task_index], other)
            loss_saved_on_new = _support_loss(model, consistency_supports[task_index], saved)
            loss_other_on_new = _support_loss(model, consistency_supports[task_index], other)
            gap_saved = _relative_gap(loss_other_on_saved, loss_saved_on_saved)
            gap_new = _relative_gap(loss_saved_on_new, loss_other_on_new)
            consistency.append({
                "decoder": decoder,
                "task": spec.task_id,
                "l2": l2,
                "cosine": cosine,
                "saved_vector_sha256": vector_hash(saved),
                "consistency_vector_sha256": vector_hash(other),
                "used_as_training_label": False,
                "loss_saved_on_saved_support": loss_saved_on_saved,
                "loss_consistency_on_saved_support": loss_other_on_saved,
                "loss_saved_on_new_support": loss_saved_on_new,
                "loss_consistency_on_new_support": loss_other_on_new,
                "gap_saved_support": gap_saved,
                "gap_new_support": gap_new,
                "far": bool(l2 > float(cfg["equivalence_l2"])),
                "prediction_equivalent": pair_is_equivalent(l2, gap_saved, gap_new, cfg),
            })
        rates = [float(value) for value in cfg["learning_rates"]]
        for lr in rates:
            logs = train_encoder(
                model, supports, teachers, list(cfg["meta_task_ids"]),
                lr=lr, steps=int(cfg["max_steps"]), log_steps=list(cfg["log_steps"]),
                init_state=init_state, decoder_before=digest,
            )
            resources["encoder_optimizer_steps"] += int(cfg["max_steps"])
            final = logs[-1]
            runs.append({
                "decoder": decoder,
                "learning_rate": lr,
                "trajectory": logs,
                "final_mean_l2": final["mean_l2"],
                "final_max_l2": final["max_l2"],
                "final_grad_norm": final["grad_norm"],
                "final_output_rms": final["output_rms"],
                "teacher_output_rms": output_rms(teachers),
                "constant_mean_l2": float(np.mean(const_dists)),
                "constant_max_l2": float(np.max(const_dists)),
                "passes": decoder_passes(final["mean_l2"], final["max_l2"], float(np.mean(const_dists)), cfg),
            })
            print(f"representability decoder={decoder} lr={lr} mean_l2={final['mean_l2']:.4f}", flush=True)
    by_rate: dict[float, list[dict[str, Any]]] = {}
    for row in runs:
        by_rate.setdefault(float(row["learning_rate"]), []).append(row)
    rate_mean = {rate: float(np.mean([row["final_mean_l2"] for row in rows])) for rate, rows in by_rate.items()}
    chosen = choose_learning_rate(rate_mean)
    chosen_rows = by_rate[chosen]
    complete = all(trajectory_complete([point["step"] for point in row["trajectory"]], list(cfg["log_steps"])) for row in runs)
    complete = complete and all(len(rows) == int(cfg["n_decoder_seeds"]) for rows in by_rate.values())
    representable = bool(complete and all(row["passes"] for row in chosen_rows))
    ambiguous_decoders = []
    for decoder in range(int(cfg["n_decoder_seeds"])):
        pairs = [row for row in consistency if int(row["decoder"]) == decoder]
        median_l2 = float(np.median([row["l2"] for row in pairs]))
        n_far = sum(1 for row in pairs if row["far"])
        n_equivalent = sum(1 for row in pairs if row["prediction_equivalent"])
        if decoder_is_ambiguous(median_l2, n_far, n_equivalent, cfg):
            ambiguous_decoders.append(decoder)
    chosen_grad = float(max(row["final_grad_norm"] for row in chosen_rows))
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    clean = not bool(source_status.get("source_dirty", True))
    decision = recommend(representable, bool(ambiguous_decoders), chosen_grad, cfg)
    payload = {
        "protocol_id": cfg["protocol_id"],
        "hypothesis": cfg["h_represent"],
        "implementation_sha": sha if clean else None,
        "source_dirty": not clean,
        "git": head,
        "decision_recorded": bool(clean and complete),
        "threshold_met": bool(representable),
        "representable": bool(representable and clean),
        "chosen_learning_rate": chosen,
        "rate_mean_l2": {str(rate): value for rate, value in rate_mean.items()},
        "threshold": {"mean_l2": float(cfg["mean_l2_threshold"]), "max_l2": float(cfg["max_l2_threshold"])},
        "ambiguous_decoders": ambiguous_decoders,
        "recommendation": decision if clean and complete else None,
        "runs": runs,
        "consistency": consistency,
        "encoder_parameter_count": 584,
        "resources": resources,
        "confirmation_evaluated": False,
        "control_evaluated": False,
        "is_agi": False,
        "is_learning_to_learn": False,
        "declared_complete": bool(complete),
        "wall_clock_s": time.perf_counter() - t0,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(dumps_strict(payload))
    return payload
