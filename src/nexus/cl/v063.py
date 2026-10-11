from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import torch

from nexus.cl.metrics import summarize_seeds
from nexus.cl.models import copy_encoder_into, copy_full_policy
from nexus.cl.protocol import HOLDOUT_EVAL_SEED, INDEPENDENT_SEED, VAL_SEED
from nexus.cl.selector import AdaptationSelector, Strategy
from nexus.cl.train import copy_obs_rms, eval_task, train_on_task
from nexus.cl.v062 import make_source_trainer
from nexus.rl.ppo import PPOTrainer
from nexus.tasks.cartpole_family import development_targets, final_test_targets, source_policy_task
from nexus.tasks.spec import TaskSpec

FIXED_STRATEGIES: tuple[Strategy, ...] = (
    "scratch",
    "reuse",
    "full_finetune",
    "encoder_new_heads_finetune",
    "frozen_encoder_new_heads",
    "conservative_low_lr",
)

SOLVE_THRESHOLD = 475.0
LOW_LR = 3e-5


def _set_backbone_trainable(agent: Any, flag: bool) -> None:
    if hasattr(agent, "backbone"):
        for p in agent.backbone.parameters():
            p.requires_grad = flag


def _eval(agent: Any, spec: TaskSpec, *, episodes: int, seed: int, trainer: PPOTrainer) -> float:
    return float(
        eval_task(
            agent, spec, episodes=episodes, seed=seed, device=trainer.device, obs_rms=trainer.obs_rms
        )["mean_return"]
    )


def train_source_val_best(
    *,
    spec: TaskSpec,
    seeds: tuple[int, ...],
    budgets: tuple[int, ...],
    eval_episodes: int,
    checkpoint_dir: Path,
) -> dict[str, Any]:
    """Train source; pick checkpoint by VAL return. Independent scores are logged, not selected on."""
    rows = []
    for seed in seeds:
        trainer = make_source_trainer(seed=seed, timesteps=budgets[-1], spec=spec)
        done = 0
        curve = []
        best_val = float("-inf")
        best_ckpt = ""
        best_steps = 0
        for b in budgets:
            extra = int(b) - done
            if extra > 0:
                train_on_task(trainer, spec, timesteps=extra, seed=seed)
                done = int(b)
            ckpt = checkpoint_dir / f"source_{spec.task_id}_s{seed}_t{b}.pt"
            trainer.save(ckpt)
            val_r = _eval(trainer.agent, spec, episodes=eval_episodes, seed=VAL_SEED, trainer=trainer)
            ind_r = _eval(trainer.agent, spec, episodes=eval_episodes, seed=INDEPENDENT_SEED, trainer=trainer)
            curve.append(
                {
                    "steps": b,
                    "val_return": val_r,
                    "independent_return": ind_r,
                    "checkpoint": str(ckpt),
                    "solved_independent": ind_r >= SOLVE_THRESHOLD,
                }
            )
            if val_r > best_val:
                best_val = val_r
                best_ckpt = str(ckpt)
                best_steps = int(b)
        last = curve[-1]
        n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
        trainer.close()
        rows.append(
            {
                "seed": seed,
                "curve": curve,
                "n_params": n_params,
                "selected_checkpoint": best_ckpt,
                "selected_steps": best_steps,
                "selected_val": best_val,
                "selected_independent": next(p["independent_return"] for p in curve if p["steps"] == best_steps),
                "last_independent": last["independent_return"],
                "collapsed": last["independent_return"] + 50.0 < max(p["independent_return"] for p in curve),
            }
        )
    selected = [r["selected_independent"] for r in rows]
    last_vals = [r["last_independent"] for r in rows]
    return {
        "task_id": spec.task_id,
        "per_seed": rows,
        "budgets": list(budgets),
        "val_seed": VAL_SEED,
        "independent_eval_seed": INDEPENDENT_SEED,
        "selection_uses_independent": False,
        "selected_independent": summarize_seeds([{"v": x} for x in selected], "v"),
        "last_checkpoint_independent": summarize_seeds([{"v": x} for x in last_vals], "v"),
        "n_solved_selected": int(sum(1 for x in selected if x >= SOLVE_THRESHOLD)),
        "n_params": rows[0]["n_params"] if rows else 0,
        "recipe": "shared 64-64, 4 envs, 128 steps, 4 epochs; val-best checkpoint",
    }


def run_strategy(
    *,
    source: PPOTrainer,
    source_spec: TaskSpec,
    target: TaskSpec,
    seed: int,
    steps: int,
    eval_episodes: int,
    strategy: Strategy,
    final_eval_seed: int,
) -> dict[str, Any]:
    trainer = make_source_trainer(seed=seed + 17, timesteps=max(steps, 1), spec=target)
    copied = 0
    retention_defined = strategy != "scratch"
    if strategy == "scratch":
        copied = 0
    elif strategy in ("reuse", "full_finetune", "conservative_low_lr"):
        copied = copy_full_policy(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
    elif strategy in ("encoder_new_heads_finetune", "frozen_encoder_new_heads"):
        copied = copy_encoder_into(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
    else:
        raise ValueError(strategy)

    lr = trainer.ppo.learning_rate
    if strategy == "conservative_low_lr":
        lr = LOW_LR
        trainer.ppo = replace(trainer.ppo, learning_rate=lr)
    if strategy == "frozen_encoder_new_heads":
        _set_backbone_trainable(trainer.agent, False)
        trainer.optimizer = torch.optim.Adam(
            [p for p in trainer.agent.parameters() if p.requires_grad], lr=lr, eps=1e-5
        )
    else:
        _set_backbone_trainable(trainer.agent, True)
        if strategy == "conservative_low_lr":
            trainer.optimizer = torch.optim.Adam(trainer.agent.parameters(), lr=lr, eps=1e-5)

    source_before = _eval(source.agent, source_spec, episodes=eval_episodes, seed=INDEPENDENT_SEED, trainer=source)
    target_before = _eval(trainer.agent, target, episodes=eval_episodes, seed=final_eval_seed, trainer=trainer)
    target_val_before = _eval(trainer.agent, target, episodes=eval_episodes, seed=VAL_SEED, trainer=trainer)

    used = 0
    if strategy not in ("reuse",) and steps > 0:
        train_on_task(trainer, target, timesteps=steps, seed=seed + 17)
        used = steps

    target_after = _eval(trainer.agent, target, episodes=eval_episodes, seed=final_eval_seed, trainer=trainer)
    source_after = _eval(trainer.agent, source_spec, episodes=eval_episodes, seed=INDEPENDENT_SEED, trainer=trainer)
    n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
    trainer.close()
    return {
        "strategy": strategy,
        "tensors_copied": copied,
        "retention_defined": retention_defined,
        "target_before": target_before,
        "target_after": target_after,
        "target_val_before": target_val_before,
        "source_before": source_before,
        "source_after": source_after,
        "source_delta": (source_after - source_before) if retention_defined else None,
        "target_delta": target_after - target_before,
        "steps_used": used,
        "n_params": n_params,
        "learning_rate": lr,
        "final_eval_seed": final_eval_seed,
        "val_seed": VAL_SEED,
    }


def _selector_limits(steps: int, eval_episodes: int) -> dict[str, Any]:
    return {
        "val_seed": VAL_SEED,
        "independent_eval_seed": INDEPENDENT_SEED,
        "eval_episodes": eval_episodes,
        "max_target_steps": steps,
    }


def run_v063_benchmark(
    *,
    n_seeds: int = 3,
    source_budgets: tuple[int, ...] = (8_192, 32_768),
    transfer_steps: int = 4_096,
    eval_episodes: int = 8,
    artifact_path: str | Path | None = "artifacts/v063_adaptation.json",
    checkpoint_dir: str | Path = "checkpoints/v063",
) -> dict[str, Any]:
    source_spec = source_policy_task()
    dev = development_targets()
    final = final_test_targets()
    ckpt_root = Path(checkpoint_dir)
    ckpt_root.mkdir(parents=True, exist_ok=True)
    seeds = tuple(range(n_seeds))
    t0 = time.perf_counter()
    source_report = train_source_val_best(
        spec=source_spec,
        seeds=seeds,
        budgets=source_budgets,
        eval_episodes=eval_episodes,
        checkpoint_dir=ckpt_root,
    )
    limits = _selector_limits(transfer_steps, eval_episodes)
    selector = AdaptationSelector(max_target_steps=transfer_steps, limits=limits)
    targets = tuple(dev) + tuple(final)
    per_seed: list[dict[str, Any]] = []
    for seed in seeds:
        src = make_source_trainer(seed=seed, timesteps=1, spec=source_spec)
        src.load_training_state(source_report["per_seed"][seed]["selected_checkpoint"])
        source_val = _eval(src.agent, source_spec, episodes=eval_episodes, seed=VAL_SEED, trainer=src)
        by_target: dict[str, Any] = {}
        for target in targets:
            split = target.train_split
            eval_seed = HOLDOUT_EVAL_SEED
            strategies: dict[str, Any] = {}
            for name in FIXED_STRATEGIES:
                steps = 0 if name == "reuse" else transfer_steps
                strategies[name] = run_strategy(
                    source=src,
                    source_spec=source_spec,
                    target=target,
                    seed=seed,
                    steps=steps,
                    eval_episodes=eval_episodes,
                    strategy=name,
                    final_eval_seed=eval_seed,
                )
            zs_val = float(strategies["reuse"]["target_val_before"])
            decision = selector.decide(
                zero_shot_val=zs_val,
                source_val=source_val,
                current_limits=limits,
            )
            chosen = dict(strategies[decision.strategy])
            chosen["decision"] = {
                "strategy": decision.strategy,
                "reason": decision.reason,
                "zero_shot_val": decision.zero_shot_val,
                "source_val": decision.source_val,
                "target_steps": decision.target_steps,
                "used_independent_or_holdout_for_decision": False,
            }
            by_target[target.task_id] = {
                "split": split,
                "fixed": strategies,
                "selector": chosen,
            }
        src.close()
        per_seed.append({"seed": seed, "source_val": source_val, "targets": by_target})

    def _collect(split: str, strategy: str, field: str) -> list[float]:
        out: list[float] = []
        ids = [t.task_id for t in (dev if split == "dev" else final)]
        for p in per_seed:
            for tid in ids:
                row = p["targets"][tid]["selector" if strategy == "selector" else "fixed"][strategy] if strategy != "selector" else p["targets"][tid]["selector"]
                val = row.get(field)
                if val is not None:
                    out.append(float(val))
        return out

    summary: dict[str, Any] = {"source": source_report["selected_independent"], "dev": {}, "test": {}}
    for split, label in (("dev", "dev"), ("test", "test")):
        block: dict[str, Any] = {}
        for name in (*FIXED_STRATEGIES, "selector"):
            after = _collect(split, name, "target_after")
            retain = _collect(split, name, "source_delta")
            block[name] = {
                "target_after": summarize_seeds([{"v": x} for x in after], "v") if after else {},
                "source_delta": summarize_seeds([{"v": x} for x in retain], "v") if retain else {},
            }
        summary[label] = block

    # Paired selector minus scratch / minus encoder on FINAL TEST only
    paired: dict[str, Any] = {}
    for vs in ("scratch", "encoder_new_heads_finetune", "reuse", "full_finetune", "conservative_low_lr"):
        deltas = []
        for p in per_seed:
            for t in final:
                sel = p["targets"][t.task_id]["selector"]["target_after"]
                base = p["targets"][t.task_id]["fixed"][vs]["target_after"]
                deltas.append(sel - base)
        paired[f"selector_minus_{vs}"] = summarize_seeds([{"v": d} for d in deltas], "v")
    summary["test_paired_selector"] = paired

    payload = {
        "protocol": {
            "family": "cartpole",
            "source_task": source_spec.task_id,
            "dev_targets": [t.task_id for t in dev],
            "final_test_targets": [t.task_id for t in final],
            "n_seeds": n_seeds,
            "source_budgets": list(source_budgets),
            "transfer_steps": transfer_steps,
            "eval_episodes": eval_episodes,
            "val_seed": VAL_SEED,
            "independent_eval_seed": INDEPENDENT_SEED,
            "final_eval_seed": HOLDOUT_EVAL_SEED,
            "selector_sees_independent": False,
            "selector_sees_final_test_returns": False,
            "selection_uses_independent": False,
            "checkpoint_selection": "max val return on source task",
            "not_acrobot": True,
        },
        "summary": summary,
        "source": source_report,
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "preserved_artifacts": [
            "artifacts/v06_continual.json",
            "artifacts/v061_continual.json",
            "artifacts/v062_continual.json",
        ],
        "caveat": "CartPole physics variants only. Selector thresholds frozen from V0.6.2. Not AGI.",
        "is_agi": False,
    }
    if artifact_path is not None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str))
    return payload
