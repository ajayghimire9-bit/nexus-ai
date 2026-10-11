from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

import torch

from nexus.cl.experiment import METHODS, _curriculum_compare, _eval_all, _run_method
from nexus.cl.metrics import cl_evaluation_metrics, summarize_seeds
from nexus.cl.models import copy_encoder_into, copy_full_policy
from nexus.cl.protocol import HOLDOUT_EVAL_SEED, INDEPENDENT_SEED, VAL_SEED
from nexus.cl.train import copy_obs_rms, eval_task, make_trainer, train_on_task
from nexus.config import ArchitectureConfig, PPOConfig
from nexus.rl.ppo import PPOTrainer
from nexus.tasks.cartpole_family import heldout_task, source_tasks
from nexus.tasks.spec import TaskSpec, task_env_fns

TransferMode = Literal[
    "scratch",
    "full_zero_shot",
    "encoder_new_heads_zero_shot",
    "full_finetune",
    "encoder_new_heads_finetune",
    "frozen_encoder_new_heads",
]


def source_arch() -> ArchitectureConfig:
    """Shared encoder so backbone copy is actually used in the forward pass."""
    return ArchitectureConfig(hidden_sizes=(64, 64), activation="tanh", shared_backbone=True)


def source_ppo(seed: int, timesteps: int) -> PPOConfig:
    """Stronger than the 2-epoch 32-unit CL smoke recipe; still cheaper than V0.4 250k."""
    return PPOConfig(
        env_id="CartPole-v1",
        num_envs=4,
        num_steps=128,
        update_epochs=4,
        num_minibatches=4,
        total_timesteps=timesteps,
        seed=seed,
        device="cpu",
        log_interval=50_000,
        normalize_obs=True,
    )


def make_source_trainer(*, seed: int, timesteps: int, spec: TaskSpec, agent: Any | None = None) -> PPOTrainer:
    ppo = source_ppo(seed, timesteps)
    return PPOTrainer(ppo, source_arch(), agent=agent, env_fns=task_env_fns(spec, ppo.num_envs, seed))


def _set_backbone_trainable(agent: Any, flag: bool) -> None:
    if hasattr(agent, "backbone"):
        for p in agent.backbone.parameters():
            p.requires_grad = flag


def source_learning_curve(
    *,
    spec: TaskSpec,
    seeds: tuple[int, ...],
    budgets: tuple[int, ...],
    eval_episodes: int,
    checkpoint_dir: Path,
) -> dict[str, Any]:
    rows = []
    for seed in seeds:
        trainer = make_source_trainer(seed=seed, timesteps=budgets[-1], spec=spec)
        done = 0
        curve = []
        for b in budgets:
            extra = int(b) - done
            if extra > 0:
                train_on_task(trainer, spec, timesteps=extra, seed=seed)
                done = int(b)
            ckpt = checkpoint_dir / f"source_{spec.task_id}_s{seed}_t{b}.pt"
            trainer.save(ckpt)
            ev = eval_task(
                trainer.agent,
                spec,
                episodes=eval_episodes,
                seed=INDEPENDENT_SEED,
                device=trainer.device,
                obs_rms=trainer.obs_rms,
            )
            curve.append({"steps": b, "independent_return": float(ev["mean_return"]), "checkpoint": str(ckpt)})
        n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
        trainer.close()
        rows.append({"seed": seed, "task_id": spec.task_id, "curve": curve, "n_params": n_params})
    by_budget = {}
    for b in budgets:
        vals = [next(p["independent_return"] for p in r["curve"] if p["steps"] == b) for r in rows]
        by_budget[str(b)] = summarize_seeds([{"v": x} for x in vals], "v")
    return {
        "task_id": spec.task_id,
        "by_budget": by_budget,
        "per_seed": rows,
        "budgets": list(budgets),
        "eval_seed": INDEPENDENT_SEED,
        "n_params": rows[0]["n_params"] if rows else 0,
        "recipe": "shared 64-64 tanh, 4 envs, 128 steps, 4 epochs, obs RMS",
    }


def _transfer_one(
    *,
    source: PPOTrainer,
    hold: TaskSpec,
    seed: int,
    steps: int,
    eval_episodes: int,
    mode: TransferMode,
    curve_points: tuple[int, ...],
) -> dict[str, Any]:
    trainer = make_source_trainer(seed=seed + 17, timesteps=max(steps, 1), spec=hold)
    copied = 0
    if mode == "scratch":
        copied = 0
    elif mode in ("full_zero_shot", "full_finetune"):
        copied = copy_full_policy(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
    elif mode in ("encoder_new_heads_zero_shot", "encoder_new_heads_finetune", "frozen_encoder_new_heads"):
        copied = copy_encoder_into(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
        if copied < 1:
            raise RuntimeError(f"{mode} copied 0 encoder tensors")
    else:
        raise ValueError(mode)

    if mode == "frozen_encoder_new_heads":
        _set_backbone_trainable(trainer.agent, False)
        trainer.optimizer = torch.optim.Adam(
            [p for p in trainer.agent.parameters() if p.requires_grad],
            lr=trainer.ppo.learning_rate,
            eps=1e-5,
        )
    else:
        _set_backbone_trainable(trainer.agent, True)

    curve = []
    zero = eval_task(
        trainer.agent,
        hold,
        episodes=eval_episodes,
        seed=HOLDOUT_EVAL_SEED,
        device=trainer.device,
        obs_rms=trainer.obs_rms,
    )
    curve.append({"steps": 0, "independent_return": float(zero["mean_return"]), "mode": mode})
    train_this = mode not in ("full_zero_shot", "encoder_new_heads_zero_shot")
    done = 0
    if train_this:
        for b in curve_points:
            extra = int(b) - done
            if extra > 0:
                train_on_task(trainer, hold, timesteps=extra, seed=seed + 17)
                done = int(b)
            ev = eval_task(
                trainer.agent,
                hold,
                episodes=eval_episodes,
                seed=HOLDOUT_EVAL_SEED,
                device=trainer.device,
                obs_rms=trainer.obs_rms,
            )
            curve.append({"steps": b, "independent_return": float(ev["mean_return"]), "mode": mode})
    n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
    trainable = int(sum(p.numel() for p in trainer.agent.parameters() if p.requires_grad))
    trainer.close()
    return {
        "mode": mode,
        "curve": curve,
        "n_params": n_params,
        "n_trainable": trainable,
        "tensors_copied": copied,
        "obs_rms_copied": mode != "scratch",
    }


def run_v062_benchmark(
    *,
    n_seeds: int = 3,
    source_budgets: tuple[int, ...] = (8_192, 32_768),
    transfer_steps: int = 8_192,
    cl_steps_per_task: int = 2_048,
    eval_episodes: int = 8,
    artifact_path: str | Path | None = "artifacts/v062_continual.json",
    checkpoint_dir: str | Path = "checkpoints/v062",
) -> dict[str, Any]:
    """Source curve first; transfer A–F; modest sequential CL with corrected metrics.

    Does not overwrite V0.6 / V0.6.1 artifacts. Does not scale every CL method to
    the source budget until a source specialist is shown to learn.
    """
    tasks = source_tasks()
    hold = heldout_task()
    source_spec = tasks[0]
    ckpt_root = Path(checkpoint_dir)
    ckpt_root.mkdir(parents=True, exist_ok=True)
    seeds = tuple(range(n_seeds))
    t0 = time.perf_counter()

    source = source_learning_curve(
        spec=source_spec,
        seeds=seeds,
        budgets=source_budgets,
        eval_episodes=eval_episodes,
        checkpoint_dir=ckpt_root,
    )

    transfer_modes: tuple[TransferMode, ...] = (
        "scratch",
        "full_zero_shot",
        "encoder_new_heads_zero_shot",
        "full_finetune",
        "encoder_new_heads_finetune",
        "frozen_encoder_new_heads",
    )
    per_seed: list[dict[str, Any]] = []
    for seed in seeds:
        src = make_source_trainer(seed=seed, timesteps=1, spec=source_spec)
        ckpt = ckpt_root / f"source_{source_spec.task_id}_s{seed}_t{source_budgets[-1]}.pt"
        src.load_training_state(ckpt)
        points = tuple(sorted({max(transfer_steps // 4, 256), transfer_steps}))
        transfer = {}
        for mode in transfer_modes:
            transfer[mode] = _transfer_one(
                source=src,
                hold=hold,
                seed=seed,
                steps=transfer_steps,
                eval_episodes=eval_episodes,
                mode=mode,
                curve_points=points if mode not in ("full_zero_shot", "encoder_new_heads_zero_shot") else (),
            )
        src.close()

        independent_after: dict[str, float] = {}
        method_rows: dict[str, Any] = {}
        for method in METHODS:
            row = _run_method(
                method,
                tasks,
                seed=seed,
                steps_per_task=cl_steps_per_task,
                eval_episodes=eval_episodes,
                eval_seed=INDEPENDENT_SEED,
                val_seed=VAL_SEED,
            )
            if method == "independent":
                independent_after = {t.task_id: row["eval_matrix"][t.task_id][t.task_id] for t in tasks}
            untrained = row.get("untrained") or {t.task_id: 0.0 for t in tasks}
            if method == "independent":
                metrics: dict[str, Any] = {
                    "average_return": float(sum(independent_after.values()) / max(len(independent_after), 1)),
                    "acc": float(sum(independent_after.values()) / max(len(independent_after), 1)),
                    "mean_forgetting": 0.0,
                    "mean_backward_transfer": 0.0,
                    "mean_zero_shot_forward_transfer": 0.0,
                    "mean_forward_adaptation": 0.0,
                    "note": "Independent specialists; sequential forgetting/BWT/FWT undefined.",
                }
            else:
                metrics = cl_evaluation_metrics(
                    matrix=row["eval_matrix"],
                    task_order=[t.task_id for t in tasks],
                    untrained=untrained,
                    independent=independent_after or None,
                )
            packed = {k: v for k, v in row.items() if k not in {"agent", "trainer"}}
            packed["transfer"] = metrics
            method_rows[method] = packed
            if row.get("trainer") is not None:
                row["trainer"].close()

        curriculum = _curriculum_compare(
            tasks,
            seed=seed,
            n_phases=3,
            steps_per_phase=cl_steps_per_task,
            eval_episodes=eval_episodes,
            eval_seed=INDEPENDENT_SEED,
            val_seed=VAL_SEED,
        )
        per_seed.append(
            {
                "seed": seed,
                "methods": method_rows,
                "heldout_transfer": transfer,
                "curriculum": curriculum,
            }
        )

    summary: dict[str, Any] = {
        "source": source["by_budget"],
        "methods": {},
        "heldout_transfer": {},
        "curriculum": {},
    }
    for method in METHODS:
        accs, forget, zs, adapt, bwt, steps = [], [], [], [], [], []
        for p in per_seed:
            tr = p["methods"][method]["transfer"]
            accs.append(float(tr.get("average_return") or tr.get("acc") or 0.0))
            forget.append(float(tr.get("mean_forgetting") or 0.0))
            zs.append(float(tr.get("mean_zero_shot_forward_transfer") or 0.0))
            adapt.append(float(tr.get("mean_forward_adaptation") or 0.0))
            bwt.append(float(tr.get("mean_backward_transfer") or 0.0))
            steps.append(p["methods"][method]["steps"])
        summary["methods"][method] = {
            "average_return": summarize_seeds([{"v": x} for x in accs], "v"),
            "mean_forgetting": summarize_seeds([{"v": x} for x in forget], "v"),
            "mean_zero_shot_forward_transfer": summarize_seeds([{"v": x} for x in zs], "v"),
            "mean_forward_adaptation": summarize_seeds([{"v": x} for x in adapt], "v"),
            "mean_backward_transfer": summarize_seeds([{"v": x} for x in bwt], "v"),
            "mean_steps": summarize_seeds([{"v": x} for x in steps], "v"),
            "n_params": per_seed[0]["methods"][method]["n_params"],
        }
    for mode in transfer_modes:
        zeros, finals = [], []
        for p in per_seed:
            curve = p["heldout_transfer"][mode]["curve"]
            zeros.append(curve[0]["independent_return"])
            finals.append(curve[-1]["independent_return"])
        summary["heldout_transfer"][mode] = {
            "at_0_steps": summarize_seeds([{"v": x} for x in zeros], "v"),
            "final": summarize_seeds([{"v": x} for x in finals], "v"),
            "tensors_copied": per_seed[0]["heldout_transfer"][mode]["tensors_copied"],
        }
    for mode in ("fixed", "random", "adaptive"):
        means = [p["curriculum"][mode]["mean_across_tasks"] for p in per_seed]
        summary["curriculum"][mode] = summarize_seeds([{"v": m} for m in means], "v")

    payload = {
        "protocol": {
            "family": "cartpole",
            "source_task": source_spec.task_id,
            "source_tasks": [t.task_id for t in tasks],
            "heldout_task": hold.task_id,
            "n_seeds": n_seeds,
            "source_budgets": list(source_budgets),
            "transfer_steps": transfer_steps,
            "cl_steps_per_task": cl_steps_per_task,
            "eval_episodes": eval_episodes,
            "val_seed": VAL_SEED,
            "independent_eval_seed": INDEPENDENT_SEED,
            "holdout_eval_seed": HOLDOUT_EVAL_SEED,
            "curriculum_sees_independent": False,
            "obs_rms_copied_on_transfer": True,
            "ewc": "per-task diagonal empirical Fisher of log π; snapshots not overwritten",
            "forward_transfer": "zero-shot vs untrained; adaptation vs matched independent",
            "not_acrobot": True,
        },
        "summary": summary,
        "source_curve": source,
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "preserved_artifacts": ["artifacts/v06_continual.json", "artifacts/v061_continual.json"],
        "caveat": (
            "V0.6.2 corrected EWC/metrics/transfer protocol. "
            "Positive transfer requires beating scratch/independent on held-out eval. "
            "Not AGI."
        ),
        "is_agi": False,
    }
    if artifact_path is not None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str))
    return payload
