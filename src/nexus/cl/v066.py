from __future__ import annotations

import random
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import numpy as np
import torch

from nexus.cl.checkpoint_stop import save_adapt_checkpoint
from nexus.cl.experiment import _run_method
from nexus.cl.linucb_strategy import StrategyLinUCB
from nexus.cl.metrics import cl_evaluation_metrics, paired_seed_deltas, seed_level_ci
from nexus.cl.models import copy_encoder_into, copy_full_policy
from nexus.cl.protocol import CONFIRM_EVAL_SEED_V066, INDEPENDENT_SEED, VAL_SEED
from nexus.cl.selector import RiskAwareSelector
from nexus.cl.serialize import dumps_strict
from nexus.cl.train import copy_obs_rms, eval_task, train_on_task
from nexus.cl.v062 import source_arch
from nexus.cl.v064 import LOW_LR, _eval, _set_backbone_trainable, source_ppo_v064, train_source_val_best
from nexus.cl.v065 import apply_ablation
from nexus.rl.ppo import PPOTrainer
from nexus.rl.running_stats import RunningMeanStd
from nexus.tasks.cartpole_family import (
    source_policy_task,
    source_tasks,
    v066_confirmation_rule,
    v066_confirmation_targets,
    v066_development_targets,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, CARTPOLE_PHYSICS_VERSION_LEGACY, TaskSpec, make_task_env, task_env_fns

NormMethod = Literal[
    "A_fresh_random",
    "B_source_rms_random",
    "C_encoder_fresh_rms",
    "D_encoder_source_rms",
    "E_full_policy",
    "F_target_calibrated_rms",
    "G_multisource_rms",
    "H_no_obs_norm",
    "B_frozen_source_rms",
]

NORM_METHODS: tuple[NormMethod, ...] = (
    "A_fresh_random",
    "B_source_rms_random",
    "C_encoder_fresh_rms",
    "D_encoder_source_rms",
    "E_full_policy",
    "F_target_calibrated_rms",
    "G_multisource_rms",
    "H_no_obs_norm",
    "B_frozen_source_rms",
)

SELECTOR_ARMS = (
    "rms_only",
    "conservative_low_lr",
    "encoder_new_heads_finetune",
    "scratch",
    "reuse",
)


def make_v066_trainer(
    *,
    seed: int,
    timesteps: int,
    spec: TaskSpec,
    normalize_obs: bool = True,
    freeze_obs_rms: bool = False,
    learning_rate: float | None = None,
) -> PPOTrainer:
    ppo = source_ppo_v064(seed, timesteps)
    ppo = replace(ppo, normalize_obs=normalize_obs)
    if learning_rate is not None:
        ppo = replace(ppo, learning_rate=learning_rate)
    trainer = PPOTrainer(ppo, source_arch(), env_fns=task_env_fns(spec, ppo.num_envs, seed))
    trainer.freeze_obs_rms = freeze_obs_rms
    return trainer


def collect_obs_rms(spec: TaskSpec, *, n_steps: int, seed: int) -> tuple[RunningMeanStd, int]:
    env = make_task_env(spec, seed=seed)
    rms = RunningMeanStd((spec.obs_dim,))
    obs, _ = env.reset(seed=seed)
    for _ in range(n_steps):
        rms.update(np.asarray(obs, dtype=np.float32).reshape(1, -1))
        obs, _, term, trunc, _ = env.step(int(env.action_space.sample()))
        if term or trunc:
            obs, _ = env.reset()
    env.close()
    return rms, n_steps


def rms_mean_shift(a: RunningMeanStd | None, b: RunningMeanStd | None) -> float:
    if a is None or b is None:
        return 0.0
    return float(np.abs(a.mean - b.mean).mean())


def apply_norm_method(
    trainer: PPOTrainer,
    source: PPOTrainer,
    target: TaskSpec,
    name: NormMethod,
    *,
    calib_seed: int,
    calib_steps: int,
) -> dict[str, Any]:
    extra_obs = 0
    frozen = False
    if name == "A_fresh_random":
        pass
    elif name == "B_source_rms_random":
        copy_obs_rms(trainer, source)
    elif name == "B_frozen_source_rms":
        copy_obs_rms(trainer, source)
        trainer.freeze_obs_rms = True
        frozen = True
    elif name == "C_encoder_fresh_rms":
        copy_encoder_into(trainer.agent, source.agent)
    elif name == "D_encoder_source_rms":
        copy_encoder_into(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
    elif name == "E_full_policy":
        copy_full_policy(trainer.agent, source.agent)
        copy_obs_rms(trainer, source)
    elif name == "F_target_calibrated_rms":
        rms, n = collect_obs_rms(target, n_steps=calib_steps, seed=calib_seed)
        extra_obs = n
        if trainer.obs_rms is None:
            trainer.obs_rms = RunningMeanStd((trainer.obs_dim,))
        trainer.obs_rms.load_state_dict(rms.state_dict())
    elif name == "G_multisource_rms":
        acc = None
        n_tot = 0
        for spec in source_tasks():
            rms, n = collect_obs_rms(spec, n_steps=max(calib_steps // 3, 32), seed=calib_seed)
            extra_obs += n
            n_tot += n
            if acc is None:
                acc = rms
            else:
                acc.mean = (acc.mean * acc.count + rms.mean * rms.count) / (acc.count + rms.count)
                acc.var = (acc.var * acc.count + rms.var * rms.count) / (acc.count + rms.count)
                acc.count = acc.count + rms.count
        if trainer.obs_rms is not None and acc is not None:
            trainer.obs_rms.load_state_dict(acc.state_dict())
    elif name == "H_no_obs_norm":
        trainer.obs_rms = None
        trainer.ppo = replace(trainer.ppo, normalize_obs=False)
    else:
        raise ValueError(name)
    return {"method": name, "extra_obs_steps": extra_obs, "frozen_rms": frozen}


def run_norm_method(
    *,
    source: PPOTrainer,
    target: TaskSpec,
    seed: int,
    steps: int,
    eval_episodes: int,
    name: NormMethod,
    final_eval_seed: int,
    calib_steps: int,
) -> dict[str, Any]:
    normalize = name != "H_no_obs_norm"
    trainer = make_v066_trainer(seed=seed + 41, timesteps=max(steps, 1), spec=target, normalize_obs=normalize)
    meta = apply_norm_method(trainer, source, target, name, calib_seed=seed + 900, calib_steps=calib_steps)
    used = 0
    if steps > 0:
        train_on_task(trainer, target, timesteps=steps, seed=seed + 41)
        used = steps
    ret = _eval(trainer.agent, target, episodes=eval_episodes, seed=final_eval_seed, trainer=trainer)
    n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
    trainer.close()
    return {
        **meta,
        "target_after": ret,
        "train_steps": used,
        "accounted_steps": used + int(meta["extra_obs_steps"]),
        "n_params": n_params,
    }


def _start_arm(
    source: PPOTrainer,
    target: TaskSpec,
    seed: int,
    arm: str,
    *,
    timesteps: int,
) -> PPOTrainer:
    trainer = make_v066_trainer(seed=seed + 43, timesteps=max(timesteps, 1), spec=target)
    if arm == "rms_only":
        apply_ablation(trainer, source, "B_random_encoder_source_rms")
    elif arm == "scratch":
        apply_ablation(trainer, source, "A_random_encoder_fresh_rms")
    elif arm == "encoder_new_heads_finetune":
        apply_ablation(trainer, source, "D_pretrained_encoder_source_rms")
    elif arm in ("reuse", "conservative_low_lr"):
        apply_ablation(trainer, source, "E_full_policy_source_rms")
        if arm == "conservative_low_lr":
            trainer.ppo = replace(trainer.ppo, learning_rate=LOW_LR)
            trainer.optimizer = torch.optim.Adam(trainer.agent.parameters(), lr=LOW_LR, eps=1e-5)
    else:
        raise ValueError(arm)
    return trainer


def probe_and_continue(
    *,
    source: PPOTrainer,
    target: TaskSpec,
    seed: int,
    probe_steps: int,
    total_steps: int,
    eval_episodes: int,
    ckpt_dir: Path,
    candidates: tuple[str, ...] = ("rms_only", "conservative_low_lr"),
) -> dict[str, Any]:
    """Train candidates for probe_steps, pick winner on VAL, resume that checkpoint."""
    probe_rows = []
    for arm in candidates:
        tr = _start_arm(source, target, seed, arm, timesteps=total_steps)
        if probe_steps > 0 and arm != "reuse":
            train_on_task(tr, target, timesteps=probe_steps, seed=seed + 43)
        ckpt = ckpt_dir / f"probe_{arm}_s{seed}_{target.task_id}.pt"
        save_adapt_checkpoint(tr, ckpt)
        val = _eval(tr.agent, target, episodes=eval_episodes, seed=VAL_SEED, trainer=tr)
        probe_rows.append({"arm": arm, "val": val, "checkpoint": str(ckpt), "probe_steps": 0 if arm == "reuse" else probe_steps})
        tr.close()
    winner = max(probe_rows, key=lambda r: r["val"])
    remaining = max(int(total_steps) - int(probe_steps) * len(candidates), 0)
    win_tr = make_v066_trainer(seed=seed + 43, timesteps=max(total_steps, 1), spec=target)
    win_tr.load_training_state(winner["checkpoint"])
    resumed = True
    if remaining > 0 and winner["arm"] != "reuse":
        train_on_task(win_tr, target, timesteps=remaining, seed=seed + 43)
    final = _eval(win_tr.agent, target, episodes=eval_episodes, seed=CONFIRM_EVAL_SEED_V066, trainer=win_tr)
    win_tr.close()
    accounted = int(probe_steps) * len(candidates) + remaining
    return {
        "strategy": "probe_and_continue",
        "winner": winner["arm"],
        "probe_vals": {r["arm"]: r["val"] for r in probe_rows},
        "resumed_from_probe_checkpoint": resumed,
        "restarted_from_scratch_after_probe": False,
        "target_after": final,
        "steps_used": accounted,
        "probe_steps_total": int(probe_steps) * len(candidates),
        "resume_steps": remaining,
        "used_confirm_for_selection": False,
        "val_episodes": eval_episodes * len(candidates),
    }


def run_arm(
    *,
    source: PPOTrainer,
    target: TaskSpec,
    seed: int,
    arm: str,
    steps: int,
    eval_episodes: int,
    eval_seed: int,
) -> dict[str, Any]:
    tr = _start_arm(source, target, seed, arm, timesteps=max(steps, 1))
    used = 0
    if arm != "reuse" and steps > 0:
        train_on_task(tr, target, timesteps=steps, seed=seed + 43)
        used = steps
    ret = _eval(tr.agent, target, episodes=eval_episodes, seed=eval_seed, trainer=tr)
    val = _eval(tr.agent, target, episodes=eval_episodes, seed=VAL_SEED, trainer=tr)
    tr.close()
    return {"strategy": arm, "target_after": ret, "target_val": val, "steps_used": used}


def _context(source: PPOTrainer, target: TaskSpec, source_val: float, eval_episodes: int, budget_frac: float, calib_seed: int) -> tuple[np.ndarray, float, int]:
    zs = eval_task(source.agent, target, episodes=eval_episodes, seed=VAL_SEED, device=source.device, obs_rms=source.obs_rms)
    tgt_rms, n = collect_obs_rms(target, n_steps=64, seed=calib_seed)
    shift = rms_mean_shift(source.obs_rms, tgt_rms)
    ucb = StrategyLinUCB()
    x = ucb.features(
        source_val=source_val,
        zero_shot_val=float(zs["mean_return"]),
        zero_shot_std=float(zs["std_return"]),
        rms_shift=shift,
        budget_frac=budget_frac,
    )
    return x, shift, n


def run_v066_benchmark(
    *,
    n_seeds: int = 10,
    source_budgets: tuple[int, ...] = (8_192, 32_768),
    transfer_steps: int = 1_024,
    probe_steps: int = 256,
    calib_steps: int = 128,
    eval_episodes: int = 8,
    fit_seed_count: int = 4,
    artifact_path: str | Path | None = "artifacts/v066_transfer.json",
    checkpoint_dir: str | Path = "checkpoints/v066",
) -> dict[str, Any]:
    source_spec = source_policy_task()
    confirm = v066_confirmation_targets()
    develop = v066_development_targets()
    ckpt_root = Path(checkpoint_dir)
    ckpt_root.mkdir(parents=True, exist_ok=True)
    seeds = tuple(range(n_seeds))
    fit_seeds = seeds[:fit_seed_count]
    test_seeds = seeds[fit_seed_count:] or seeds
    t0 = time.perf_counter()
    source_report = train_source_val_best(
        spec=source_spec,
        seeds=seeds,
        budgets=source_budgets,
        eval_episodes=eval_episodes,
        checkpoint_dir=ckpt_root,
    )

    bandit = StrategyLinUCB(arms=SELECTOR_ARMS)
    fit_log: list[dict[str, Any]] = []
    # Supervised-style fit: run each arm on development, update LinUCB from VAL reward.
    # This is batched outcome learning, not online bandit during confirmation.
    for seed in fit_seeds:
        src = make_v066_trainer(seed=seed, timesteps=1, spec=source_spec)
        src.load_training_state(source_report["per_seed"][seed]["selected_checkpoint"])
        source_val = _eval(src.agent, source_spec, episodes=eval_episodes, seed=VAL_SEED, trainer=src)
        target = develop[0]
        x, shift, extra = _context(src, target, source_val, eval_episodes, 1.0, seed + 700)
        for arm in SELECTOR_ARMS:
            row = run_arm(
                source=src,
                target=target,
                seed=seed,
                arm=arm,
                steps=min(256, transfer_steps),
                eval_episodes=eval_episodes,
                eval_seed=VAL_SEED,
            )
            bandit.update(arm, x, row["target_val"] / 500.0)
            fit_log.append({"seed": seed, "arm": arm, "val": row["target_val"], "rms_shift": shift, "extra_obs": extra})
        src.close()

    limits = {
        "val_seed": VAL_SEED,
        "independent_eval_seed": INDEPENDENT_SEED,
        "eval_episodes": eval_episodes,
        "max_target_steps": transfer_steps,
    }
    heuristic = RiskAwareSelector(max_target_steps=transfer_steps, limits=limits)
    rng = random.Random(66)
    per_seed: list[dict[str, Any]] = []
    eval_seeds = test_seeds
    for seed in seeds:
        src = make_v066_trainer(seed=seed, timesteps=1, spec=source_spec)
        src.load_training_state(source_report["per_seed"][seed]["selected_checkpoint"])
        source_val = _eval(src.agent, source_spec, episodes=eval_episodes, seed=VAL_SEED, trainer=src)
        by_target: dict[str, Any] = {}
        for target in confirm:
            norms = {
                name: run_norm_method(
                    source=src,
                    target=target,
                    seed=seed,
                    steps=transfer_steps,
                    eval_episodes=eval_episodes,
                    name=name,
                    final_eval_seed=CONFIRM_EVAL_SEED_V066,
                    calib_steps=calib_steps,
                )
                for name in NORM_METHODS
            }
            x, shift, extra = _context(src, target, source_val, eval_episodes, 1.0, seed + 800)
            learned_arm = bandit.choose(x)
            heur = heuristic.decide(
                zero_shot_val=_eval(src.agent, target, episodes=eval_episodes, seed=VAL_SEED, trainer=src),
                source_val=source_val,
                current_limits=limits,
            )
            rand_arm = rng.choice(list(SELECTOR_ARMS))
            selectors = {}
            if seed in eval_seeds:
                selectors["learned"] = {
                    **run_arm(source=src, target=target, seed=seed, arm=learned_arm, steps=transfer_steps, eval_episodes=eval_episodes, eval_seed=CONFIRM_EVAL_SEED_V066),
                    "decision": learned_arm,
                    "fit_seed": False,
                    "rms_shift": shift,
                    "context_obs_steps": extra,
                }
                heur_arm = "rms_only" if heur.strategy == "encoder_new_heads_finetune" else heur.strategy
                selectors["heuristic"] = {
                    **run_arm(
                        source=src,
                        target=target,
                        seed=seed,
                        arm=heur_arm,
                        steps=0 if heur_arm == "reuse" else transfer_steps,
                        eval_episodes=eval_episodes,
                        eval_seed=CONFIRM_EVAL_SEED_V066,
                    ),
                    "v064_heuristic_raw": heur.strategy,
                    "mapped_arm": heur_arm,
                    "fit_seed": False,
                }
                selectors["random"] = run_arm(source=src, target=target, seed=seed, arm=rand_arm, steps=transfer_steps, eval_episodes=eval_episodes, eval_seed=CONFIRM_EVAL_SEED_V066)
                selectors["probe_and_continue"] = probe_and_continue(
                    source=src,
                    target=target,
                    seed=seed,
                    probe_steps=probe_steps,
                    total_steps=transfer_steps,
                    eval_episodes=eval_episodes,
                    ckpt_dir=ckpt_root,
                )
            by_target[target.task_id] = {"norm": norms, "selectors": selectors, "rms_shift": shift, "selector_evaluated": seed in eval_seeds}
        continual = None
        if seed in eval_seeds:
            seq = develop[:3]
            cl_rows = {}
            for method in ("naive", "replay", "ewc", "multihead"):
                row = _run_method(
                    method,
                    seq,
                    seed=seed,
                    steps_per_task=transfer_steps,
                    eval_episodes=eval_episodes,
                    eval_seed=CONFIRM_EVAL_SEED_V066,
                    val_seed=VAL_SEED,
                )
                if row.get("trainer") is not None:
                    row["trainer"].close()
                untrained = row.get("untrained") or {t.task_id: 0.0 for t in seq}
                metrics = cl_evaluation_metrics(
                    matrix=row["eval_matrix"],
                    task_order=[t.task_id for t in seq],
                    untrained=untrained,
                )
                packed = {k: v for k, v in row.items() if k not in {"agent", "trainer"}}
                packed["cl_metrics"] = metrics
                packed["replay_bytes"] = None if method != "replay" else 2048 * 3 * 4 * 5
                cl_rows[method] = packed
            snap_a = {}
            src_eval = {t.task_id: _eval(src.agent, t, episodes=eval_episodes, seed=CONFIRM_EVAL_SEED_V066, trainer=src) for t in seq}
            snap_a["immutable_source"] = src_eval
            snap_a["note"] = "separate checkpoint, not in-network memory"
            cl_rows["snapshot_retrieval"] = snap_a
            rms_seq = make_v066_trainer(seed=seed + 51, timesteps=transfer_steps * 3, spec=seq[0])
            copy_obs_rms(rms_seq, src)
            seq_mat: dict[str, dict[str, float]] = {}
            for spec in seq:
                train_on_task(rms_seq, spec, timesteps=transfer_steps, seed=seed + 51)
                seq_mat[spec.task_id] = {
                    t.task_id: _eval(rms_seq.agent, t, episodes=eval_episodes, seed=CONFIRM_EVAL_SEED_V066, trainer=rms_seq)
                    for t in seq
                }
            rms_seq.close()
            cl_rows["rms_aware_naive"] = {"eval_matrix": seq_mat, "cl_metrics": cl_evaluation_metrics(matrix=seq_mat, task_order=[t.task_id for t in seq], untrained={t.task_id: 0.0 for t in seq})}
            continual = cl_rows
        src.close()
        per_seed.append(
            {
                "seed": seed,
                "source_val": source_val,
                "fit_split": seed in fit_seeds,
                "test_split": seed in eval_seeds,
                "targets": by_target,
                "continual": continual,
            }
        )

    test_rows = [p for p in per_seed if p["test_split"]]

    def _means(method: str) -> list[float]:
        out = []
        for p in per_seed:
            xs = [p["targets"][t.task_id]["norm"][method]["target_after"] for t in confirm]
            out.append(float(sum(xs) / len(xs)))
        return out

    def _sel_means(key: str) -> list[float]:
        out = []
        for p in test_rows:
            xs = [p["targets"][t.task_id]["selectors"][key]["target_after"] for t in confirm]
            out.append(float(sum(xs) / len(xs)))
        return out

    scores: dict[int, dict[str, dict[str, float]]] = {}
    for p in per_seed:
        scores[int(p["seed"])] = {}
        for t in confirm:
            scores[int(p["seed"])][t.task_id] = {m: p["targets"][t.task_id]["norm"][m]["target_after"] for m in NORM_METHODS}
    sel_scores: dict[int, dict[str, dict[str, float]]] = {}
    for p in test_rows:
        sel_scores[int(p["seed"])] = {}
        for t in confirm:
            sel_scores[int(p["seed"])][t.task_id] = {k: p["targets"][t.task_id]["selectors"][k]["target_after"] for k in p["targets"][t.task_id]["selectors"]}
            sel_scores[int(p["seed"])][t.task_id]["B_source_rms_random"] = p["targets"][t.task_id]["norm"]["B_source_rms_random"]["target_after"]
            sel_scores[int(p["seed"])][t.task_id]["E_full_policy"] = p["targets"][t.task_id]["norm"]["E_full_policy"]["target_after"]

    # Small PPO stabilization: lower LR, predefined cap, 3 seeds, keep failures.
    stab = []
    for seed in (0, 1, 2):
        tr = make_v066_trainer(seed=seed + 100, timesteps=16_384, spec=source_spec, learning_rate=1e-4)
        train_on_task(tr, source_spec, timesteps=16_384, seed=seed + 100)
        val = _eval(tr.agent, source_spec, episodes=eval_episodes, seed=VAL_SEED, trainer=tr)
        ind = _eval(tr.agent, source_spec, episodes=eval_episodes, seed=INDEPENDENT_SEED, trainer=tr)
        stab.append({"seed": seed, "val": val, "independent": ind, "solved_val": val >= 475, "cap": 16384, "lr": 1e-4})
        tr.close()

    payload = {
        "protocol": {
            "family": "cartpole",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "legacy_physics": CARTPOLE_PHYSICS_VERSION_LEGACY,
            "preserved_artifacts": [
                "artifacts/v06_continual.json",
                "artifacts/v061_continual.json",
                "artifacts/v062_continual.json",
                "artifacts/v063_adaptation.json",
                "artifacts/v064_adaptation.json",
                "artifacts/v065_transfer.json",
            ],
            "n_seeds": n_seeds,
            "fit_seeds": list(fit_seeds),
            "test_seeds": list(test_seeds),
            "replication_unit": "source_training_seed",
            "selector_fit": "batched LinUCB updates from development VAL outcomes; not online confirmation bandit",
            "confirm_eval_seed": CONFIRM_EVAL_SEED_V066,
            "val_seed": VAL_SEED,
            "development_targets": [t.task_id for t in develop],
            "confirmation_targets": [t.task_id for t in confirm],
            "confirmation_rule": v066_confirmation_rule(),
            "transfer_steps": transfer_steps,
            "probe_continues_from_checkpoint": True,
            "code_version": "v0.6.6",
            "parent_commit": "e73e071",
            "v07_not_implemented": True,
        },
        "summary": {
            "normalization": {m: seed_level_ci(_means(m)) for m in NORM_METHODS},
            "paired_norm": {
                "B_minus_A": paired_seed_deltas(per_seed_task=scores, treatment="B_source_rms_random", baseline="A_fresh_random"),
                "D_minus_B": paired_seed_deltas(per_seed_task=scores, treatment="D_encoder_source_rms", baseline="B_source_rms_random"),
                "F_minus_A": paired_seed_deltas(per_seed_task=scores, treatment="F_target_calibrated_rms", baseline="A_fresh_random"),
                "G_minus_B": paired_seed_deltas(per_seed_task=scores, treatment="G_multisource_rms", baseline="B_source_rms_random"),
                "Bfrozen_minus_B": paired_seed_deltas(per_seed_task=scores, treatment="B_frozen_source_rms", baseline="B_source_rms_random"),
                "H_minus_A": paired_seed_deltas(per_seed_task=scores, treatment="H_no_obs_norm", baseline="A_fresh_random"),
            },
            "selectors_heldout_seeds": {k: seed_level_ci(_sel_means(k)) for k in ("learned", "heuristic", "random", "probe_and_continue") if test_rows},
            "paired_selectors": {
                "learned_minus_B": paired_seed_deltas(per_seed_task=sel_scores, treatment="learned", baseline="B_source_rms_random") if sel_scores else {},
                "probe_minus_B": paired_seed_deltas(per_seed_task=sel_scores, treatment="probe_and_continue", baseline="B_source_rms_random") if sel_scores else {},
                "learned_minus_heuristic": paired_seed_deltas(per_seed_task=sel_scores, treatment="learned", baseline="heuristic") if sel_scores else {},
            },
            "stabilization_lr1e4_16k": {
                "independent": seed_level_ci([r["independent"] for r in stab]),
                "n_solved_val": int(sum(1 for r in stab if r["solved_val"])),
                "failure_rate": float(sum(1 for r in stab if not r["solved_val"]) / max(len(stab), 1)),
            },
        },
        "source": source_report,
        "linucb": bandit.state_dict(),
        "selector_fit_log": fit_log,
        "stabilization": stab,
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.6.6 finalization. Probe resumes checkpoints. Not V0.7. Not AGI.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
