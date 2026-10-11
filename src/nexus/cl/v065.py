from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import torch

from nexus.cl.checkpoint_stop import save_adapt_checkpoint, stop_at_checkpoint
from nexus.cl.linucb_strategy import ARMS, StrategyLinUCB
from nexus.cl.metrics import paired_seed_deltas, seed_level_ci
from nexus.cl.models import copy_encoder_into, copy_full_policy
from nexus.cl.protocol import CONFIRM_EVAL_SEED_V065, INDEPENDENT_SEED, VAL_SEED
from nexus.cl.selector import RiskAwareSelector
from nexus.cl.serialize import dumps_strict
from nexus.cl.snapshot import capture_snapshot, retention_bundle
from nexus.cl.train import copy_obs_rms, eval_task, train_on_task
from nexus.cl.v064 import LOW_LR, SOLVE_THRESHOLD, _eval, _set_backbone_trainable, make_v064_trainer, train_source_val_best
from nexus.rl.ppo import PPOTrainer
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v065_confirmation_rule,
    v065_confirmation_targets,
    v065_development_targets,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, CARTPOLE_PHYSICS_VERSION_LEGACY, TaskSpec

Ablation = Literal[
    "A_random_encoder_fresh_rms",
    "B_random_encoder_source_rms",
    "C_pretrained_encoder_fresh_rms",
    "D_pretrained_encoder_source_rms",
    "E_full_policy_source_rms",
    "F_frozen_encoder_source_rms",
]

ABLATIONS: tuple[Ablation, ...] = (
    "A_random_encoder_fresh_rms",
    "B_random_encoder_source_rms",
    "C_pretrained_encoder_fresh_rms",
    "D_pretrained_encoder_source_rms",
    "E_full_policy_source_rms",
    "F_frozen_encoder_source_rms",
)

SOURCE_DROP = 80.0


def _rms_shift(src: PPOTrainer, dst: PPOTrainer) -> float:
    if src.obs_rms is None or dst.obs_rms is None:
        return 0.0
    return float(abs(src.obs_rms.mean - dst.obs_rms.mean).mean())


def apply_ablation(trainer: PPOTrainer, source: PPOTrainer, name: Ablation) -> dict[str, Any]:
    copied_enc = 0
    copied_full = 0
    rms = "fresh"
    frozen = False
    if name == "A_random_encoder_fresh_rms":
        pass
    elif name == "B_random_encoder_source_rms":
        copy_obs_rms(trainer, source)
        rms = "source"
    elif name == "C_pretrained_encoder_fresh_rms":
        copied_enc = copy_encoder_into(trainer.agent, source.agent)
        rms = "fresh"
    elif name == "D_pretrained_encoder_source_rms":
        copied_enc = copy_encoder_into(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
        rms = "source"
    elif name == "E_full_policy_source_rms":
        copied_full = copy_full_policy(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
        rms = "source"
    elif name == "F_frozen_encoder_source_rms":
        copied_enc = copy_encoder_into(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
        _set_backbone_trainable(trainer.agent, False)
        trainer.optimizer = torch.optim.Adam(
            [p for p in trainer.agent.parameters() if p.requires_grad],
            lr=trainer.ppo.learning_rate,
            eps=1e-5,
        )
        frozen = True
        rms = "source"
    else:
        raise ValueError(name)
    return {
        "copied_encoder_tensors": copied_enc,
        "copied_full_tensors": copied_full,
        "rms": rms,
        "frozen_encoder": frozen,
        "pretrained_encoder": copied_enc > 0 or copied_full > 0,
    }


def run_ablation(
    *,
    source: PPOTrainer,
    source_spec: TaskSpec,
    target: TaskSpec,
    seed: int,
    steps: int,
    eval_episodes: int,
    name: Ablation,
    final_eval_seed: int,
    halt_on_source_drop: bool = False,
) -> dict[str, Any]:
    trainer = make_v064_trainer(seed=seed + 19, timesteps=max(steps, 1), spec=target)
    meta = apply_ablation(trainer, source, name)
    ckpt = Path("checkpoints/v065") / f"pre_{name}_s{seed}_{target.task_id}.pt"
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    save_adapt_checkpoint(trainer, ckpt)
    source_snap = capture_snapshot(source)
    source_val0 = _eval(source.agent, source_spec, episodes=eval_episodes, seed=VAL_SEED, trainer=source)
    stopped = False
    used = 0
    if steps > 0:
        train_on_task(trainer, target, timesteps=steps, seed=seed + 19)
        used = steps
        if halt_on_source_drop and name in ("E_full_policy_source_rms",):
            now = _eval(trainer.agent, source_spec, episodes=eval_episodes, seed=VAL_SEED, trainer=trainer)
            if now < source_val0 - SOURCE_DROP:
                stop_at_checkpoint(trainer, ckpt)
                stopped = True
    target_ret = _eval(trainer.agent, target, episodes=eval_episodes, seed=final_eval_seed, trainer=trainer)
    new_heads = name not in ("E_full_policy_source_rms",)
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
        "ablation": name,
        **meta,
        "target_after": target_ret,
        "steps_used": used,
        "stopped_at_checkpoint": stopped,
        "retention": retain,
        "n_params": n_params,
        "physics_version": CARTPOLE_PHYSICS_VERSION,
    }


def run_named_strategy(
    *,
    source: PPOTrainer,
    target: TaskSpec,
    seed: int,
    steps: int,
    eval_episodes: int,
    strategy: str,
    final_eval_seed: int,
) -> dict[str, Any]:
    mapping: dict[str, Ablation] = {
        "scratch": "A_random_encoder_fresh_rms",
        "encoder_new_heads_finetune": "D_pretrained_encoder_source_rms",
        "frozen_encoder_new_heads": "F_frozen_encoder_source_rms",
        "reuse": "E_full_policy_source_rms",
        "conservative_low_lr": "E_full_policy_source_rms",
    }
    abl = mapping[strategy]
    trainer = make_v064_trainer(seed=seed + 23, timesteps=max(steps, 1), spec=target)
    apply_ablation(trainer, source, abl)
    if strategy == "conservative_low_lr":
        trainer.ppo = replace(trainer.ppo, learning_rate=LOW_LR)
        trainer.optimizer = torch.optim.Adam(trainer.agent.parameters(), lr=LOW_LR, eps=1e-5)
    used = 0
    if strategy != "reuse" and steps > 0:
        train_on_task(trainer, target, timesteps=steps, seed=seed + 23)
        used = steps
    ret = _eval(trainer.agent, target, episodes=eval_episodes, seed=final_eval_seed, trainer=trainer)
    val = _eval(trainer.agent, target, episodes=eval_episodes, seed=VAL_SEED, trainer=trainer)
    trainer.close()
    return {"strategy": strategy, "target_after": ret, "target_val": val, "steps_used": used}


def _limits(steps: int, eval_episodes: int) -> dict[str, Any]:
    return {
        "val_seed": VAL_SEED,
        "independent_eval_seed": INDEPENDENT_SEED,
        "eval_episodes": eval_episodes,
        "max_target_steps": steps,
    }


def run_v065_benchmark(
    *,
    n_seeds: int = 10,
    source_budgets: tuple[int, ...] = (8_192, 32_768),
    transfer_steps: int = 2_048,
    probe_steps: int = 256,
    eval_episodes: int = 8,
    artifact_path: str | Path | None = "artifacts/v065_transfer.json",
    checkpoint_dir: str | Path = "checkpoints/v065",
) -> dict[str, Any]:
    source_spec = source_policy_task()
    confirm = v065_confirmation_targets()
    develop = v065_development_targets()
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

    bandit = StrategyLinUCB()
    # Fit LinUCB on development using val returns only (never confirm seed 75000).
    fit_log = []
    fit_seeds = seeds[: min(3, len(seeds))]
    for seed in fit_seeds:
        src = make_v064_trainer(seed=seed, timesteps=1, spec=source_spec)
        src.load_training_state(source_report["per_seed"][seed]["selected_checkpoint"])
        source_val = _eval(src.agent, source_spec, episodes=eval_episodes, seed=VAL_SEED, trainer=src)
        for target in develop[:1]:
            zs = eval_task(src.agent, target, episodes=eval_episodes, seed=VAL_SEED, device=src.device, obs_rms=src.obs_rms)
            x = bandit.features(
                source_val=source_val,
                zero_shot_val=float(zs["mean_return"]),
                zero_shot_std=float(zs["std_return"]),
                rms_shift=0.0,
                budget_frac=1.0,
            )
            for arm in ARMS:
                row = run_named_strategy(
                    source=src,
                    target=target,
                    seed=seed,
                    steps=0 if arm == "reuse" else min(512, transfer_steps),
                    eval_episodes=eval_episodes,
                    strategy=arm,
                    final_eval_seed=VAL_SEED,
                )
                bandit.update(arm, x, row["target_val"] / 500.0)
                fit_log.append({"seed": seed, "task": target.task_id, "arm": arm, "val": row["target_val"]})
        src.close()

    limits = _limits(transfer_steps, eval_episodes)
    heuristic = RiskAwareSelector(max_target_steps=transfer_steps, limits=limits)
    per_seed: list[dict[str, Any]] = []
    for seed in seeds:
        src = make_v064_trainer(seed=seed, timesteps=1, spec=source_spec)
        src.load_training_state(source_report["per_seed"][seed]["selected_checkpoint"])
        source_val = _eval(src.agent, source_spec, episodes=eval_episodes, seed=VAL_SEED, trainer=src)
        weak_ckpt = source_report["per_seed"][seed]["curve"][0]["checkpoint"]
        src_weak = make_v064_trainer(seed=seed, timesteps=1, spec=source_spec)
        src_weak.load_training_state(weak_ckpt)
        by_target: dict[str, Any] = {}
        for target in confirm:
            ablations = {}
            for name in ABLATIONS:
                ablations[name] = run_ablation(
                    source=src,
                    source_spec=source_spec,
                    target=target,
                    seed=seed,
                    steps=transfer_steps,
                    eval_episodes=eval_episodes,
                    name=name,
                    final_eval_seed=CONFIRM_EVAL_SEED_V065,
                    halt_on_source_drop=True,
                )
            weak_d = run_ablation(
                source=src_weak,
                source_spec=source_spec,
                target=target,
                seed=seed,
                steps=transfer_steps,
                eval_episodes=eval_episodes,
                name="D_pretrained_encoder_source_rms",
                final_eval_seed=CONFIRM_EVAL_SEED_V065,
            )
            zs = eval_task(src.agent, target, episodes=eval_episodes, seed=VAL_SEED, device=src.device, obs_rms=src.obs_rms)
            x = bandit.features(
                source_val=source_val,
                zero_shot_val=float(zs["mean_return"]),
                zero_shot_std=float(zs["std_return"]),
                rms_shift=0.0,
                budget_frac=1.0,
            )
            learned_arm = bandit.choose(x)
            heur = heuristic.decide(
                zero_shot_val=float(zs["mean_return"]),
                source_val=source_val,
                current_limits=limits,
                zero_shot_std=float(zs["std_return"]),
                budget=transfer_steps,
            )
            learned_run = run_named_strategy(
                source=src,
                target=target,
                seed=seed,
                steps=0 if learned_arm == "reuse" else transfer_steps,
                eval_episodes=eval_episodes,
                strategy=learned_arm,
                final_eval_seed=CONFIRM_EVAL_SEED_V065,
            )
            heur_run = run_named_strategy(
                source=src,
                target=target,
                seed=seed,
                steps=heur.target_steps,
                eval_episodes=eval_episodes,
                strategy=heur.strategy,
                final_eval_seed=CONFIRM_EVAL_SEED_V065,
            )
            # Probe: two 256-step trials on val, remaining budget on winner. Counted in steps.
            probe_budget = min(probe_steps, transfer_steps // 4)
            remaining = transfer_steps
            p1 = run_named_strategy(
                source=src, target=target, seed=seed, steps=probe_budget, eval_episodes=eval_episodes,
                strategy="conservative_low_lr", final_eval_seed=VAL_SEED,
            )
            p2 = run_named_strategy(
                source=src, target=target, seed=seed, steps=probe_budget, eval_episodes=eval_episodes,
                strategy="encoder_new_heads_finetune", final_eval_seed=VAL_SEED,
            )
            remaining -= 2 * probe_budget
            winner = "encoder_new_heads_finetune" if p2["target_val"] >= p1["target_val"] else "conservative_low_lr"
            probed = run_named_strategy(
                source=src, target=target, seed=seed, steps=max(remaining, 0), eval_episodes=eval_episodes,
                strategy=winner, final_eval_seed=CONFIRM_EVAL_SEED_V065,
            )
            probed["steps_used"] = 2 * probe_budget + probed["steps_used"]
            probed["probe_winner"] = winner
            probed["used_confirm_for_probe"] = False
            by_target[target.task_id] = {
                "ablations": ablations,
                "weak_source_D": weak_d,
                "learned_selector": {
                    **learned_run,
                    "decision": {"strategy": learned_arm, "used_confirm": False},
                },
                "heuristic_selector": {
                    **heur_run,
                    "decision": {"strategy": heur.strategy, "reason": heur.reason, "used_confirm": False},
                },
                "probe_selector": probed,
            }
        # Continual: confirm_0 then confirm_1, naive sequential vs frozen original snapshot eval.
        seq = confirm[:2]
        naive = make_v064_trainer(seed=seed + 31, timesteps=transfer_steps * 2, spec=seq[0])
        copy_full_policy(naive.agent, src.agent)
        copy_obs_rms(naive, src)
        after = {}
        for spec in seq:
            train_on_task(naive, spec, timesteps=transfer_steps, seed=seed + 31)
            after[spec.task_id] = {
                "adapted": _eval(naive.agent, spec, episodes=eval_episodes, seed=CONFIRM_EVAL_SEED_V065, trainer=naive),
            }
        after[seq[0].task_id]["after_second"] = _eval(
            naive.agent, seq[0], episodes=eval_episodes, seed=CONFIRM_EVAL_SEED_V065, trainer=naive
        )
        preserved = _eval(src.agent, seq[0], episodes=eval_episodes, seed=CONFIRM_EVAL_SEED_V065, trainer=src)
        naive.close()
        src_weak.close()
        src.close()
        per_seed.append(
            {
                "seed": seed,
                "source_val": source_val,
                "solved_on_val": source_report["per_seed"][seed]["solved_on_val"],
                "targets": by_target,
                "continual": {
                    "naive_after": after,
                    "immutable_source_on_first_target": preserved,
                    "memory_note": "immutable source checkpoint is a separate copy, not in-weight memory",
                    "n_params": source_report["n_params"],
                },
            }
        )

    def _seed_means(abl: str) -> list[float]:
        out = []
        for p in per_seed:
            xs = [p["targets"][t.task_id]["ablations"][abl]["target_after"] for t in confirm]
            out.append(float(sum(xs) / len(xs)))
        return out

    scores: dict[int, dict[str, dict[str, float]]] = {}
    for p in per_seed:
        scores[int(p["seed"])] = {}
        for t in confirm:
            row = p["targets"][t.task_id]
            scores[int(p["seed"])][t.task_id] = {a: row["ablations"][a]["target_after"] for a in ABLATIONS}
            scores[int(p["seed"])][t.task_id]["learned_selector"] = row["learned_selector"]["target_after"]
            scores[int(p["seed"])][t.task_id]["heuristic_selector"] = row["heuristic_selector"]["target_after"]
            scores[int(p["seed"])][t.task_id]["probe_selector"] = row["probe_selector"]["target_after"]
            scores[int(p["seed"])][t.task_id]["weak_D"] = row["weak_source_D"]["target_after"]

    paired = {
        "D_minus_A": paired_seed_deltas(per_seed_task=scores, treatment="D_pretrained_encoder_source_rms", baseline="A_random_encoder_fresh_rms"),
        "D_minus_B": paired_seed_deltas(per_seed_task=scores, treatment="D_pretrained_encoder_source_rms", baseline="B_random_encoder_source_rms"),
        "D_minus_C": paired_seed_deltas(per_seed_task=scores, treatment="D_pretrained_encoder_source_rms", baseline="C_pretrained_encoder_fresh_rms"),
        "C_minus_A": paired_seed_deltas(per_seed_task=scores, treatment="C_pretrained_encoder_fresh_rms", baseline="A_random_encoder_fresh_rms"),
        "B_minus_A": paired_seed_deltas(per_seed_task=scores, treatment="B_random_encoder_source_rms", baseline="A_random_encoder_fresh_rms"),
        "learned_minus_D": paired_seed_deltas(per_seed_task=scores, treatment="learned_selector", baseline="D_pretrained_encoder_source_rms"),
        "learned_minus_heuristic": paired_seed_deltas(per_seed_task=scores, treatment="learned_selector", baseline="heuristic_selector"),
        "probe_minus_D": paired_seed_deltas(per_seed_task=scores, treatment="probe_selector", baseline="D_pretrained_encoder_source_rms"),
        "valbest_D_minus_weak_D": paired_seed_deltas(per_seed_task=scores, treatment="D_pretrained_encoder_source_rms", baseline="weak_D"),
    }
    encoder_beyond_rms = paired["D_minus_B"]["across_seeds"]
    encoder_beyond_init = paired["C_minus_A"]["across_seeds"]

    payload = {
        "protocol": {
            "family": "cartpole",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "legacy_physics_version": CARTPOLE_PHYSICS_VERSION_LEGACY,
            "preserved_artifacts": [
                "artifacts/v06_continual.json",
                "artifacts/v061_continual.json",
                "artifacts/v062_continual.json",
                "artifacts/v063_adaptation.json",
                "artifacts/v064_adaptation.json",
            ],
            "source_task": source_spec.task_id,
            "development_targets": [t.task_id for t in develop],
            "confirmation_targets": [t.task_id for t in confirm],
            "confirmation_rule": v065_confirmation_rule(),
            "n_seeds": n_seeds,
            "replication_unit": "source_training_seed",
            "source_budgets": list(source_budgets),
            "transfer_steps": transfer_steps,
            "probe_steps_each": probe_steps,
            "eval_episodes": eval_episodes,
            "val_seed": VAL_SEED,
            "independent_eval_seed": INDEPENDENT_SEED,
            "confirm_eval_seed": CONFIRM_EVAL_SEED_V065,
            "selector_fit_uses_confirm": False,
            "learned_selector": "disjoint LinUCB, fit on development val only",
            "v07_compat": "RECALL / LEARN / VERIFY only",
        },
        "summary": {
            "ablations": {a: seed_level_ci(_seed_means(a)) for a in ABLATIONS},
            "learned_selector": seed_level_ci(
                [float(sum(p["targets"][t.task_id]["learned_selector"]["target_after"] for t in confirm) / 3) for p in per_seed]
            ),
            "heuristic_selector": seed_level_ci(
                [float(sum(p["targets"][t.task_id]["heuristic_selector"]["target_after"] for t in confirm) / 3) for p in per_seed]
            ),
            "probe_selector": seed_level_ci(
                [float(sum(p["targets"][t.task_id]["probe_selector"]["target_after"] for t in confirm) / 3) for p in per_seed]
            ),
            "paired_seed_deltas": paired,
            "encoder_weights_beyond_source_rms": encoder_beyond_rms,
            "encoder_weights_beyond_random_init": encoder_beyond_init,
            "normalization_only": paired["B_minus_A"]["across_seeds"],
        },
        "source": source_report,
        "linucb": bandit.state_dict(),
        "selector_fit_log": fit_log,
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "Causal ablations on corrected CartPole physics. Not AGI.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
