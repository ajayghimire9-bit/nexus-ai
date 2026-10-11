from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import torch

from nexus.cl.metrics import hierarchical_bootstrap_ci, paired_seed_deltas, seed_level_ci
from nexus.cl.models import copy_encoder_into, copy_full_policy
from nexus.cl.protocol import CONFIRM_EVAL_SEED, HOLDOUT_EVAL_SEED, INDEPENDENT_SEED, VAL_SEED
from nexus.cl.selector import AdaptationSelector, RiskAwareSelector, Strategy
from nexus.cl.snapshot import capture_snapshot, eval_snapshot, retention_bundle
from nexus.cl.train import copy_obs_rms, eval_task, train_on_task
from nexus.cl.v062 import source_arch
from nexus.config import PPOConfig
from nexus.rl.ppo import PPOTrainer
from nexus.tasks.cartpole_family import confirmation_generation_rule, confirmation_targets, source_policy_task
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, CARTPOLE_PHYSICS_VERSION_LEGACY, TaskSpec, task_env_fns

FIXED_STRATEGIES: tuple[Strategy, ...] = (
    "scratch",
    "reuse",
    "full_finetune",
    "conservative_low_lr",
    "encoder_new_heads_finetune",
    "frozen_encoder_new_heads",
)
SOLVE_THRESHOLD = 475.0
LOW_LR = 3e-5
SOURCE_DROP_ABORT = 80.0
CURVE_POINTS = (0, 512, 2048, 4096, 8192)
NEW_HEADS = {"encoder_new_heads_finetune", "frozen_encoder_new_heads"}


def source_ppo_v064(seed: int, timesteps: int) -> PPOConfig:
    return PPOConfig(
        env_id="CartPole-v1",
        num_envs=4,
        num_steps=128,
        update_epochs=10,
        num_minibatches=4,
        learning_rate=2.5e-4,
        total_timesteps=timesteps,
        seed=seed,
        device="cpu",
        log_interval=100_000,
        normalize_obs=True,
        max_grad_norm=0.5,
    )


def make_v064_trainer(*, seed: int, timesteps: int, spec: TaskSpec, agent: Any | None = None) -> PPOTrainer:
    ppo = source_ppo_v064(seed, timesteps)
    return PPOTrainer(ppo, source_arch(), agent=agent, env_fns=task_env_fns(spec, ppo.num_envs, seed))


def _eval(agent: Any, spec: TaskSpec, *, episodes: int, seed: int, trainer: PPOTrainer, obs_rms: Any | None = None) -> float:
    return float(
        eval_task(
            agent,
            spec,
            episodes=episodes,
            seed=seed,
            device=trainer.device,
            obs_rms=trainer.obs_rms if obs_rms is None else obs_rms,
        )["mean_return"]
    )


def _set_backbone_trainable(agent: Any, flag: bool) -> None:
    if hasattr(agent, "backbone"):
        for p in agent.backbone.parameters():
            p.requires_grad = flag


def train_source_val_best(
    *,
    spec: TaskSpec,
    seeds: tuple[int, ...],
    budgets: tuple[int, ...],
    eval_episodes: int,
    checkpoint_dir: Path,
) -> dict[str, Any]:
    rows = []
    for seed in seeds:
        trainer = make_v064_trainer(seed=seed, timesteps=budgets[-1], spec=spec)
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
                    "solved_val": val_r >= SOLVE_THRESHOLD,
                    "solved_independent": ind_r >= SOLVE_THRESHOLD,
                }
            )
            if val_r > best_val:
                best_val = val_r
                best_ckpt = str(ckpt)
                best_steps = int(b)
        n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
        trainer.close()
        sel_ind = next(p["independent_return"] for p in curve if p["steps"] == best_steps)
        rows.append(
            {
                "seed": seed,
                "curve": curve,
                "n_params": n_params,
                "selected_checkpoint": best_ckpt,
                "selected_steps": best_steps,
                "selected_val": best_val,
                "selected_independent": sel_ind,
                "last_independent": curve[-1]["independent_return"],
                "solved_on_val": best_val >= SOLVE_THRESHOLD,
                "pretrain_steps": best_steps,
            }
        )
    selected = [r["selected_independent"] for r in rows]
    return {
        "task_id": spec.task_id,
        "per_seed": rows,
        "budgets": list(budgets),
        "val_seed": VAL_SEED,
        "independent_eval_seed": INDEPENDENT_SEED,
        "selection_uses_independent": False,
        "all_seeds_independent": seed_level_ci(selected),
        "solved_val_subgroup": seed_level_ci([r["selected_independent"] for r in rows if r["solved_on_val"]]),
        "n_solved_val": int(sum(1 for r in rows if r["solved_on_val"])),
        "n_params": rows[0]["n_params"] if rows else 0,
        "total_pretrain_steps": int(sum(r["pretrain_steps"] for r in rows)),
        "recipe": "64-64 shared, 4 envs, 128 steps, 10 epochs, lr 2.5e-4, val-best ckpt",
        "physics_version": CARTPOLE_PHYSICS_VERSION,
    }


def run_strategy(
    *,
    source: PPOTrainer,
    source_spec: TaskSpec,
    target: TaskSpec,
    seed: int,
    max_steps: int,
    eval_episodes: int,
    strategy: Strategy,
    final_eval_seed: int,
    curve_points: tuple[int, ...],
    rollback: bool,
) -> dict[str, Any]:
    trainer = make_v064_trainer(seed=seed + 17, timesteps=max(max_steps, 1), spec=target)
    source_snap = capture_snapshot(source)
    new_heads = strategy in NEW_HEADS
    if strategy == "scratch":
        copied = 0
    elif strategy in ("reuse", "full_finetune", "conservative_low_lr"):
        copied = copy_full_policy(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
    elif new_heads:
        copied = copy_encoder_into(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
    else:
        raise ValueError(strategy)

    lr = trainer.ppo.learning_rate
    if strategy == "conservative_low_lr":
        lr = LOW_LR
        trainer.ppo = replace(trainer.ppo, learning_rate=lr)
        trainer.optimizer = torch.optim.Adam(trainer.agent.parameters(), lr=lr, eps=1e-5)
    if strategy == "frozen_encoder_new_heads":
        _set_backbone_trainable(trainer.agent, False)
        trainer.optimizer = torch.optim.Adam(
            [p for p in trainer.agent.parameters() if p.requires_grad], lr=lr, eps=1e-5
        )

    pre_adapt = capture_snapshot(trainer)
    source_val_before = eval_snapshot(source, source_spec, source_snap, episodes=eval_episodes, seed=VAL_SEED, eval_fn=eval_task)
    curve = []
    rolled_back = False
    used = 0
    points = (0,) if strategy == "reuse" or max_steps <= 0 else tuple(p for p in curve_points if p <= max_steps)
    if 0 not in points:
        points = (0,) + points
    done = 0
    for b in points:
        extra = int(b) - done
        if extra > 0 and strategy != "reuse":
            train_on_task(trainer, target, timesteps=extra, seed=seed + 17)
            used += extra
            done = int(b)
            if rollback and not new_heads:
                src_now = _eval(trainer.agent, source_spec, episodes=eval_episodes, seed=VAL_SEED, trainer=trainer)
                if src_now < source_val_before - SOURCE_DROP_ABORT:
                    trainer.agent.load_state_dict(pre_adapt["state_dict"])
                    if trainer.obs_rms is not None and pre_adapt.get("obs_rms") is not None:
                        trainer.obs_rms.load_state_dict(pre_adapt["obs_rms"])
                    rolled_back = True
        tgt = _eval(trainer.agent, target, episodes=eval_episodes, seed=final_eval_seed, trainer=trainer)
        curve.append({"steps": b, "target_final": tgt, "rolled_back": rolled_back})

    retain = retention_bundle(
        trainer=trainer,
        source_spec=source_spec,
        source_snap=source_snap,
        adapted_is_new_heads=new_heads,
        episodes=eval_episodes,
        seed=INDEPENDENT_SEED,
        eval_fn=eval_task,
    )
    n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
    trainer.close()
    return {
        "strategy": strategy,
        "tensors_copied": copied,
        "curve": curve,
        "target_after": curve[-1]["target_final"],
        "target_at_0": curve[0]["target_final"],
        "steps_used": used,
        "rolled_back": rolled_back,
        "retention": retain,
        "n_params": n_params,
        "learning_rate": lr,
        "physics_version": CARTPOLE_PHYSICS_VERSION,
        "obs_rms_from_source": strategy != "scratch",
        "new_heads": new_heads,
    }


def _limits(steps: int, eval_episodes: int) -> dict[str, Any]:
    return {
        "val_seed": VAL_SEED,
        "independent_eval_seed": INDEPENDENT_SEED,
        "eval_episodes": eval_episodes,
        "max_target_steps": steps,
    }


def run_v064_benchmark(
    *,
    n_seeds: int = 10,
    source_budgets: tuple[int, ...] = (8_192, 32_768),
    transfer_steps: int = 8_192,
    eval_episodes: int = 8,
    curve_points: tuple[int, ...] = CURVE_POINTS,
    artifact_path: str | Path | None = "artifacts/v064_adaptation.json",
    checkpoint_dir: str | Path = "checkpoints/v064",
) -> dict[str, Any]:
    source_spec = source_policy_task()
    targets = confirmation_targets()
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
    limits = _limits(transfer_steps, eval_episodes)
    v063_sel = AdaptationSelector(max_target_steps=transfer_steps, limits=limits)
    risk_sel = RiskAwareSelector(max_target_steps=transfer_steps, limits=limits)
    per_seed: list[dict[str, Any]] = []
    for seed in seeds:
        src = make_v064_trainer(seed=seed, timesteps=1, spec=source_spec)
        src.load_training_state(source_report["per_seed"][seed]["selected_checkpoint"])
        source_val = _eval(src.agent, source_spec, episodes=eval_episodes, seed=VAL_SEED, trainer=src)
        by_target: dict[str, Any] = {}
        for target in targets:
            strategies = {}
            for name in FIXED_STRATEGIES:
                steps = 0 if name == "reuse" else transfer_steps
                strategies[name] = run_strategy(
                    source=src,
                    source_spec=source_spec,
                    target=target,
                    seed=seed,
                    max_steps=steps,
                    eval_episodes=eval_episodes,
                    strategy=name,
                    final_eval_seed=CONFIRM_EVAL_SEED,
                    curve_points=curve_points,
                    rollback=name in ("full_finetune", "conservative_low_lr"),
                )
            zs_val = _eval(src.agent, target, episodes=eval_episodes, seed=VAL_SEED, trainer=src)
            zs_stats = eval_task(
                src.agent, target, episodes=eval_episodes, seed=VAL_SEED, device=src.device, obs_rms=src.obs_rms
            )
            d_old = v063_sel.decide(zero_shot_val=zs_val, source_val=source_val, current_limits=limits)
            d_new = risk_sel.decide(
                zero_shot_val=zs_val,
                source_val=source_val,
                current_limits=limits,
                zero_shot_std=float(zs_stats["std_return"]),
                budget=transfer_steps,
            )
            by_target[target.task_id] = {
                "fixed": {k: {kk: vv for kk, vv in v.items() if kk != "retention"} | {"retention": v["retention"]} for k, v in strategies.items()},
                "v063_selector": {
                    **strategies[d_old.strategy],
                    "decision": {"strategy": d_old.strategy, "reason": d_old.reason, "used_confirm_eval": False},
                },
                "risk_selector": {
                    **strategies[d_new.strategy],
                    "decision": {"strategy": d_new.strategy, "reason": d_new.reason, "used_confirm_eval": False},
                },
                "zero_shot_val": zs_val,
            }
        src.close()
        per_seed.append(
            {
                "seed": seed,
                "source_val": source_val,
                "solved_on_val": source_report["per_seed"][seed]["solved_on_val"],
                "targets": by_target,
            }
        )

    def _matrix(strategy_key: str, field: str = "target_after") -> dict[int, dict[str, float]]:
        out: dict[int, dict[str, float]] = {}
        for p in per_seed:
            out[int(p["seed"])] = {}
            for tid, row in p["targets"].items():
                if strategy_key in ("v063_selector", "risk_selector"):
                    out[int(p["seed"])][tid] = {strategy_key: row[strategy_key][field]}
                else:
                    out[int(p["seed"])][tid] = {strategy_key: row["fixed"][strategy_key][field]}
        return out

    def _score_map(name: str) -> dict[int, dict[str, dict[str, float]]]:
        packed: dict[int, dict[str, dict[str, float]]] = {}
        for p in per_seed:
            packed[int(p["seed"])] = {}
            for tid, row in p["targets"].items():
                packed[int(p["seed"])][tid] = {
                    s: row["fixed"][s]["target_after"] for s in FIXED_STRATEGIES
                }
                packed[int(p["seed"])][tid]["v063_selector"] = row["v063_selector"]["target_after"]
                packed[int(p["seed"])][tid]["risk_selector"] = row["risk_selector"]["target_after"]
        return packed

    scores = _score_map("all")
    paired = {}
    for treat in ("risk_selector", "v063_selector", "reuse", "conservative_low_lr", "full_finetune"):
        for base in ("scratch", "reuse", "full_finetune", "conservative_low_lr"):
            if treat == base:
                continue
            paired[f"{treat}_minus_{base}"] = paired_seed_deltas(per_seed_task=scores, treatment=treat, baseline=base)

    def _seed_means(name: str, solved_only: bool = False) -> list[float]:
        vals = []
        for p in per_seed:
            if solved_only and not p["solved_on_val"]:
                continue
            xs = []
            for row in p["targets"].values():
                if name in ("v063_selector", "risk_selector"):
                    xs.append(row[name]["target_after"])
                else:
                    xs.append(row["fixed"][name]["target_after"])
            vals.append(float(sum(xs) / len(xs)))
        return vals

    summary_all = {s: seed_level_ci(_seed_means(s)) for s in (*FIXED_STRATEGIES, "v063_selector", "risk_selector")}
    summary_solved = {
        s: seed_level_ci(_seed_means(s, solved_only=True)) for s in (*FIXED_STRATEGIES, "v063_selector", "risk_selector")
    }
    risk_vs_cons = paired["risk_selector_minus_conservative_low_lr"]["across_seeds"]

    payload = {
        "protocol": {
            "family": "cartpole",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "legacy_physics_version": CARTPOLE_PHYSICS_VERSION_LEGACY,
            "legacy_artifacts": [
                "artifacts/v06_continual.json",
                "artifacts/v061_continual.json",
                "artifacts/v062_continual.json",
                "artifacts/v063_adaptation.json",
            ],
            "legacy_note": "V0.6–V0.6.3 CartPole variants did not recompute total_mass/polemass_length. Do not cite them as evidence on corrected physics.",
            "source_task": source_spec.task_id,
            "confirmation_targets": [t.task_id for t in targets],
            "confirmation_rule": confirmation_generation_rule(),
            "n_seeds": n_seeds,
            "replication_unit": "source_training_seed",
            "source_budgets": list(source_budgets),
            "transfer_steps": transfer_steps,
            "curve_points": list(curve_points),
            "eval_episodes": eval_episodes,
            "val_seed": VAL_SEED,
            "independent_eval_seed": INDEPENDENT_SEED,
            "confirm_eval_seed": CONFIRM_EVAL_SEED,
            "holdout_eval_seed_dev_only": HOLDOUT_EVAL_SEED,
            "selector_sees_confirm": False,
            "v07_compat": "OBSERVE → RECALL → PREDICT → PLAN → ACT → LEARN → VERIFY → STORE (V0.6.4 implements recall/adapt/verify only)",
        },
        "summary": {
            "all_seeds": summary_all,
            "solved_source_val_subgroup": summary_solved,
            "paired_seed_deltas": paired,
            "risk_selector_minus_conservative_bootstrap": hierarchical_bootstrap_ci(
                paired["risk_selector_minus_conservative_low_lr"]["per_seed_mean_delta"]
            ),
            "risk_equals_conservative": abs(float(risk_vs_cons.get("mean") or 0.0)) < 1e-9,
        },
        "source": source_report,
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "Corrected CartPole derived physics. Seed-level CIs. Not AGI.",
    }
    if artifact_path is not None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str))
    return payload
