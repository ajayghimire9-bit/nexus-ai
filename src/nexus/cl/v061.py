from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import torch

from nexus.cl.experiment import METHODS, _curriculum_compare, _eval_all, _run_method
from nexus.cl.metrics import continual_metrics, summarize_seeds
from nexus.cl.models import copy_encoder_into
from nexus.cl.protocol import HOLDOUT_EVAL_SEED, INDEPENDENT_SEED, VAL_SEED
from nexus.cl.train import eval_task, make_trainer, train_on_task
from nexus.tasks.cartpole_family import heldout_task, source_tasks
from nexus.tasks.spec import TaskSpec


def _set_backbone_trainable(agent: Any, flag: bool) -> None:
    if hasattr(agent, "backbone"):
        for p in agent.backbone.parameters():
            p.requires_grad = flag


def specialist_learning_curves(
    *,
    seeds: tuple[int, ...],
    budgets: tuple[int, ...],
    eval_episodes: int,
    checkpoint_dir: Path,
) -> dict[str, Any]:
    tasks = source_tasks()
    rows = []
    for seed in seeds:
        for spec in tasks:
            trainer = make_trainer(seed=seed, timesteps=budgets[-1], spec=spec)
            done = 0
            curve = []
            for b in budgets:
                extra = int(b) - done
                if extra > 0:
                    train_on_task(trainer, spec, timesteps=extra, seed=seed)
                    done = int(b)
                ckpt = checkpoint_dir / f"specialist_{spec.task_id}_s{seed}_t{b}.pt"
                trainer.save(ckpt)
                ev = eval_task(
                    trainer.agent,
                    spec,
                    episodes=eval_episodes,
                    seed=INDEPENDENT_SEED,
                    device=trainer.device,
                    obs_rms=trainer.obs_rms,
                )
                curve.append({"steps": b, "independent_return": float(ev["mean_return"])})
            n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
            trainer.close()
            rows.append({"seed": seed, "task_id": spec.task_id, "curve": curve, "n_params": n_params})
    by_task: dict[str, Any] = {}
    for spec in tasks:
        for b in budgets:
            vals = [
                next(p["independent_return"] for p in r["curve"] if p["steps"] == b)
                for r in rows
                if r["task_id"] == spec.task_id
            ]
            by_task.setdefault(spec.task_id, {})[str(b)] = summarize_seeds([{"v": x} for x in vals], "v")
    return {"by_task": by_task, "per_seed": rows, "budgets": list(budgets), "eval_seed": INDEPENDENT_SEED}


def _transfer_variant(
    *,
    source: Any,
    hold: TaskSpec,
    seed: int,
    steps: int,
    eval_episodes: int,
    mode: str,
    curve_points: tuple[int, ...],
) -> dict[str, Any]:
    trainer = make_trainer(seed=seed + 17, timesteps=max(steps, 1), spec=hold)
    if mode != "scratch":
        copy_encoder_into(trainer.agent, source.agent)
    if mode == "frozen_encoder":
        _set_backbone_trainable(trainer.agent, False)
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
    done = 0
    for b in curve_points:
        if b <= 0:
            continue
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
    return {"mode": mode, "curve": curve, "n_params": n_params, "n_trainable": trainable}


def run_v061_benchmark(
    *,
    n_seeds: int = 3,
    steps_per_task: int = 8192,
    specialist_budgets: tuple[int, ...] = (2048, 8192, 16384),
    eval_episodes: int = 8,
    artifact_path: str | Path | None = "artifacts/v061_continual.json",
    checkpoint_dir: str | Path = "checkpoints/v061",
) -> dict[str, Any]:
    tasks = source_tasks()
    hold = heldout_task()
    ckpt_root = Path(checkpoint_dir)
    ckpt_root.mkdir(parents=True, exist_ok=True)
    seeds = tuple(range(n_seeds))
    t0 = time.perf_counter()
    specialists = specialist_learning_curves(
        seeds=seeds,
        budgets=specialist_budgets,
        eval_episodes=eval_episodes,
        checkpoint_dir=ckpt_root,
    )
    per_seed: list[dict[str, Any]] = []
    for seed in seeds:
        independent_scratch = {}
        method_rows: dict[str, Any] = {}
        naive_trainer = None
        for method in METHODS:
            row = _run_method(
                method,
                tasks,
                seed=seed,
                steps_per_task=steps_per_task,
                eval_episodes=eval_episodes,
                eval_seed=INDEPENDENT_SEED,
                val_seed=VAL_SEED,
            )
            if method == "independent":
                independent_scratch = {t.task_id: row["eval_matrix"][t.task_id][t.task_id] for t in tasks}
            if method == "naive":
                naive_trainer = row.get("trainer")
            if method == "independent":
                metrics = {
                    "acc": float(sum(independent_scratch.values()) / max(len(independent_scratch), 1)),
                    "mean_forgetting": 0.0,
                    "mean_forward_transfer": 0.0,
                    "mean_backward_transfer": 0.0,
                    "note": "Independent specialists; forgetting/FWT/BWT undefined.",
                }
            else:
                metrics = continual_metrics(
                    matrix=row["eval_matrix"],
                    task_order=[t.task_id for t in tasks],
                    scratch=independent_scratch or {t.task_id: 0.0 for t in tasks},
                )
            packed = {k: v for k, v in row.items() if k not in {"agent", "trainer"}}
            packed["transfer"] = metrics
            method_rows[method] = packed
            if method != "naive" and row.get("trainer") is not None:
                row["trainer"].close()
        transfer = {}
        if naive_trainer is not None:
            points = tuple(sorted({steps_per_task // 4, steps_per_task}))
            for mode in ("zero_shot", "frozen_encoder", "finetune_encoder", "scratch"):
                if mode == "zero_shot":
                    transfer[mode] = _transfer_variant(
                        source=naive_trainer,
                        hold=hold,
                        seed=seed,
                        steps=0,
                        eval_episodes=eval_episodes,
                        mode="frozen_encoder",
                        curve_points=(),
                    )
                    transfer[mode]["mode"] = "zero_shot"
                else:
                    transfer[mode] = _transfer_variant(
                        source=naive_trainer,
                        hold=hold,
                        seed=seed,
                        steps=steps_per_task,
                        eval_episodes=eval_episodes,
                        mode=mode if mode != "finetune_encoder" else "finetune",
                        curve_points=points,
                    )
            naive_trainer.close()
        curriculum = _curriculum_compare(
            tasks,
            seed=seed,
            n_phases=3,
            steps_per_phase=steps_per_task,
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

    summary: dict[str, Any] = {"methods": {}, "heldout_transfer": {}, "curriculum": {}, "specialists": specialists["by_task"]}
    for method in METHODS:
        accs, forget, fwt, bwt, steps = [], [], [], [], []
        for p in per_seed:
            tr = p["methods"][method]["transfer"]
            accs.append(float(tr.get("acc") or sum(p["methods"][method]["final_eval"].values()) / 3))
            forget.append(float(tr.get("mean_forgetting") or 0.0))
            fwt.append(float(tr.get("mean_forward_transfer") or 0.0))
            bwt.append(float(tr.get("mean_backward_transfer") or 0.0))
            steps.append(p["methods"][method]["steps"])
        summary["methods"][method] = {
            "acc": summarize_seeds([{"v": x} for x in accs], "v"),
            "mean_forgetting": summarize_seeds([{"v": x} for x in forget], "v"),
            "mean_forward_transfer": summarize_seeds([{"v": x} for x in fwt], "v"),
            "mean_backward_transfer": summarize_seeds([{"v": x} for x in bwt], "v"),
            "mean_steps": summarize_seeds([{"v": x} for x in steps], "v"),
            "n_params": per_seed[0]["methods"][method]["n_params"],
        }
    for mode in ("zero_shot", "frozen_encoder", "finetune_encoder", "scratch"):
        finals = []
        zeros = []
        for p in per_seed:
            curve = p["heldout_transfer"][mode]["curve"]
            zeros.append(curve[0]["independent_return"])
            finals.append(curve[-1]["independent_return"])
        summary["heldout_transfer"][mode] = {
            "zero_or_start": summarize_seeds([{"v": x} for x in zeros], "v"),
            "final": summarize_seeds([{"v": x} for x in finals], "v"),
        }
    for mode in ("fixed", "random", "adaptive"):
        means = [p["curriculum"][mode]["mean_across_tasks"] for p in per_seed]
        summary["curriculum"][mode] = summarize_seeds([{"v": m} for m in means], "v")

    payload = {
        "protocol": {
            "family": "cartpole",
            "source_tasks": [t.task_id for t in tasks],
            "heldout_task": hold.task_id,
            "n_seeds": n_seeds,
            "steps_per_task": steps_per_task,
            "specialist_budgets": list(specialist_budgets),
            "eval_episodes": eval_episodes,
            "val_seed": VAL_SEED,
            "independent_eval_seed": INDEPENDENT_SEED,
            "holdout_eval_seed": HOLDOUT_EVAL_SEED,
            "curriculum_sees_independent": False,
            "not_acrobot": True,
        },
        "summary": summary,
        "specialist_curves": specialists,
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "v06_artifact_preserved": "artifacts/v06_continual.json",
        "caveat": (
            "V0.6.1 CartPole-variant CL/transfer study. "
            "Do not treat a win as AGI. V0.6 artifacts are unchanged."
        ),
        "is_agi": False,
    }
    if artifact_path is not None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str))
    return payload
