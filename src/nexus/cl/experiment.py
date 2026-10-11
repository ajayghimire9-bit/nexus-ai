from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

import torch

from nexus.cl.curriculum import CurriculumSelector, assert_frozen_eval_rules, fixed_order, random_order
from nexus.cl.metrics import summarize_seeds, transfer_metrics
from nexus.cl.models import MultiHeadActorCritic, copy_encoder_into
from nexus.cl.regularizers import EWCPenalty, ReplayBuffer
from nexus.cl.train import _arch, _ppo, eval_task, make_trainer, train_on_task
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.actor_critic import ActorCritic
from nexus.rl.ppo import spec_from_arch_config
from nexus.tasks.cartpole_family import heldout_task, source_tasks
from nexus.tasks.spec import TaskSpec, task_env_fns

INDEPENDENT_EVAL_SEED = 70_000
METHODS = ("independent", "naive", "replay", "ewc", "multihead")


def _eval_all(trainer: Any, tasks: tuple[TaskSpec, ...], *, episodes: int, seed: int) -> dict[str, dict[str, float]]:
    out = {}
    for spec in tasks:
        agent = trainer.agent
        if isinstance(agent, MultiHeadActorCritic) and spec.task_id in agent.task_ids:
            agent.set_task(spec.task_id)
        out[spec.task_id] = eval_task(
            agent, spec, episodes=episodes, seed=seed, device=trainer.device, obs_rms=trainer.obs_rms
        )
    return out


def _run_method(
    method: str,
    tasks: tuple[TaskSpec, ...],
    *,
    seed: int,
    steps_per_task: int,
    eval_episodes: int,
    eval_seed: int,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    n_params = 0
    peak: dict[str, float] = {}
    matrix: dict[str, dict[str, float]] = {}
    steps_used = 0
    traces: list[dict[str, Any]] = []
    replay = ReplayBuffer(capacity=2048)
    ewc = EWCPenalty(lam=8.0)

    if method == "independent":
        trainers = {}
        for spec in tasks:
            tr = make_trainer(seed=seed, timesteps=steps_per_task, spec=spec)
            phase = train_on_task(tr, spec, timesteps=steps_per_task, seed=seed)
            steps_used += int(phase["timesteps"])
            n_params = int(sum(p.numel() for p in tr.agent.parameters()))
            scores = _eval_all(tr, tasks, episodes=eval_episodes, seed=eval_seed)
            matrix[spec.task_id] = {k: float(v["mean_return"]) for k, v in scores.items()}
            peak[spec.task_id] = float(scores[spec.task_id]["mean_return"])
            traces.append({"trained": spec.task_id, "eval": matrix[spec.task_id], "steps": steps_used})
            trainers[spec.task_id] = tr
        specialist = {t.task_id: float(matrix[t.task_id][t.task_id]) for t in tasks}
        for spec in tasks:
            trainers[spec.task_id].close()
        wall = time.perf_counter() - t0
        return {
            "method": method,
            "seed": seed,
            "eval_matrix": matrix,
            "peak": peak,
            "steps": steps_used,
            "n_params": n_params,
            "wall_clock_s": wall,
            "final_eval": specialist,
            "trace": traces,
            "agent": None,
            "last_trainer_closed": True,
        }

    first = tasks[0]
    if method == "multihead":
        ids = tuple(t.task_id for t in tasks)
        probe = make_trainer(seed=seed, timesteps=steps_per_task, spec=first)
        space = probe.envs.single_action_space
        obs_dim = probe.obs_dim
        spec_nn = spec_from_arch_config(_arch())
        agent = MultiHeadActorCritic(obs_dim, space, spec_nn, ids)
        probe.close()
        trainer = make_trainer(seed=seed, timesteps=steps_per_task, spec=first, agent=agent)
        trainer.agent.set_task(first.task_id)  # type: ignore[union-attr]
    else:
        trainer = make_trainer(seed=seed, timesteps=steps_per_task, spec=first)

    trainer.aux_loss_fn = None
    for spec in tasks:
        if method == "multihead":
            trainer.agent.set_task(spec.task_id)  # type: ignore[union-attr]
        if method == "replay":
            trainer.replay_buffer = replay
            buf = replay

            def _aux(agent: Any, _buf: ReplayBuffer = buf) -> torch.Tensor:
                return 0.4 * _buf.bc_loss(agent)

            trainer.aux_loss_fn = _aux
        elif method == "ewc":
            pen = ewc

            def _aux(agent: Any, _pen: EWCPenalty = pen) -> torch.Tensor:
                return _pen.loss(agent)

            trainer.aux_loss_fn = _aux
        else:
            trainer.aux_loss_fn = None
        start_steps = int(trainer._timesteps_done)
        phase = train_on_task(trainer, spec, timesteps=steps_per_task, seed=seed)
        delta = int(phase["timesteps"]) - start_steps
        steps_used += max(delta, 0)
        n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
        obs_t = trainer._obs_tensor_no_update(trainer._raw_obs)
        with torch.no_grad():
            act, _, _, _ = trainer.agent(obs_t)
        if method == "ewc":
            ewc.consolidate(trainer.agent, obs_t.detach(), act.detach())
        scores = _eval_all(trainer, tasks, episodes=eval_episodes, seed=eval_seed)
        matrix[spec.task_id] = {k: float(v["mean_return"]) for k, v in scores.items()}
        peak[spec.task_id] = max(peak.get(spec.task_id, float("-inf")), float(scores[spec.task_id]["mean_return"]))
        traces.append({"trained": spec.task_id, "eval": matrix[spec.task_id], "steps": steps_used})

    final = {k: float(v) for k, v in matrix[tasks[-1].task_id].items()}
    wall = time.perf_counter() - t0
    payload = {
        "method": method,
        "seed": seed,
        "eval_matrix": matrix,
        "peak": peak,
        "steps": steps_used,
        "n_params": n_params,
        "wall_clock_s": wall,
        "final_eval": final,
        "trace": traces,
        "agent": trainer.agent,
        "trainer": trainer,
    }
    return payload


def _encoder_transfer(
    source_trainer: Any,
    holdout: TaskSpec,
    *,
    seed: int,
    steps: int,
    eval_episodes: int,
    eval_seed: int,
) -> dict[str, Any]:
    scratch = make_trainer(seed=seed + 17, timesteps=steps, spec=holdout)
    scratch_phase = train_on_task(scratch, holdout, timesteps=steps, seed=seed + 17)
    scratch_eval = eval_task(
        scratch.agent, holdout, episodes=eval_episodes, seed=eval_seed, device=scratch.device, obs_rms=scratch.obs_rms
    )
    transferred = make_trainer(seed=seed + 17, timesteps=steps, spec=holdout)
    copy_encoder_into(transferred.agent, source_trainer.agent)
    for p in transferred.agent.backbone.parameters():
        p.requires_grad = False
    # architecture reuse already implied; this is weight transfer of the encoder only
    tr_phase = train_on_task(transferred, holdout, timesteps=steps, seed=seed + 17)
    tr_eval = eval_task(
        transferred.agent,
        holdout,
        episodes=eval_episodes,
        seed=eval_seed,
        device=transferred.device,
        obs_rms=transferred.obs_rms,
    )
    n_src = int(sum(p.numel() for p in source_trainer.agent.parameters()))
    scratch.close()
    transferred.close()
    return {
        "heldout_task": holdout.task_id,
        "from_scratch": {
            "mean_return": float(scratch_eval["mean_return"]),
            "steps": int(scratch_phase["timesteps"]),
        },
        "encoder_weight_transfer": {
            "mean_return": float(tr_eval["mean_return"]),
            "steps": int(tr_phase["timesteps"]),
            "frozen_backbone": True,
        },
        "architecture_reuse_only": "from_scratch uses the same MLP spec without copied weights",
        "n_params_source": n_src,
        "delta_vs_scratch": float(tr_eval["mean_return"]) - float(scratch_eval["mean_return"]),
    }


def _curriculum_compare(
    tasks: tuple[TaskSpec, ...],
    *,
    seed: int,
    n_phases: int,
    steps_per_phase: int,
    eval_episodes: int,
    eval_seed: int,
) -> dict[str, Any]:
    limits = {
        "independent_eval_seed": eval_seed,
        "eval_episodes": eval_episodes,
        "max_timesteps_per_task": steps_per_phase,
    }
    rng_sel = random.Random(seed + 99)
    selector = CurriculumSelector(tasks)
    modes = ("fixed", "random", "adaptive")
    results: dict[str, Any] = {}
    for mode in modes:
        spec0 = tasks[0]
        trainer = make_trainer(seed=seed, timesteps=steps_per_phase, spec=spec0)
        order: list[str] = []
        for phase in range(n_phases):
            current = {
                "independent_eval_seed": eval_seed,
                "eval_episodes": eval_episodes,
                "max_timesteps_per_task": steps_per_phase,
            }
            assert_frozen_eval_rules(limits, current)
            if mode == "fixed":
                chosen = fixed_order(tasks, phase)
            elif mode == "random":
                chosen = random_order(tasks, rng_sel)
            else:
                if phase == 0:
                    chosen = tasks[0]
                else:
                    chosen = selector.select(rng_sel)
            order.append(chosen.task_id)
            train_on_task(trainer, chosen, timesteps=steps_per_phase, seed=seed + phase)
            scores = _eval_all(trainer, tasks, episodes=eval_episodes, seed=eval_seed)
            if mode == "adaptive":
                for spec in tasks:
                    selector.observe(spec.task_id, scores[spec.task_id]["mean_return"], scores[spec.task_id]["std_return"])
        final = _eval_all(trainer, tasks, episodes=eval_episodes, seed=eval_seed)
        trainer.close()
        results[mode] = {
            "order": order,
            "final": {k: float(v["mean_return"]) for k, v in final.items()},
            "mean_across_tasks": float(sum(v["mean_return"] for v in final.values()) / len(final)),
        }
    return results


def run_continual_benchmark(
    *,
    n_seeds: int = 3,
    steps_per_task: int = 2048,
    eval_episodes: int = 8,
    artifact_path: str | Path | None = "artifacts/v06_continual.json",
) -> dict[str, Any]:
    tasks = source_tasks()
    hold = heldout_task()
    assert all(tasks[0].compatible_with(t) for t in tasks)
    assert hold.compatible_with(tasks[0])
    per_seed: list[dict[str, Any]] = []
    for seed in range(n_seeds):
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
                eval_seed=INDEPENDENT_EVAL_SEED,
            )
            if method == "independent":
                independent_scratch = {t.task_id: row["eval_matrix"][t.task_id][t.task_id] for t in tasks}
            if method == "naive":
                naive_trainer = row.get("trainer")
            if method == "independent":
                metrics = {
                    "forgetting": {t.task_id: 0.0 for t in tasks},
                    "mean_forgetting": 0.0,
                    "forward_transfer": {},
                    "backward_transfer": {},
                    "note": "Independent specialists are not a sequential run; forgetting is undefined.",
                }
            else:
                metrics = transfer_metrics(
                    peak_during_task=row["peak"],
                    final_matrix={k: v for k, v in row["eval_matrix"].items()},
                    independent=independent_scratch or {t.task_id: 0.0 for t in tasks},
                )
            packed = {k: v for k, v in row.items() if k not in {"agent", "trainer"}}
            packed["transfer"] = metrics
            method_rows[method] = packed
            if method != "naive" and row.get("trainer") is not None:
                row["trainer"].close()
        transfer = None
        if naive_trainer is not None:
            transfer = _encoder_transfer(
                naive_trainer,
                hold,
                seed=seed,
                steps=steps_per_task,
                eval_episodes=eval_episodes,
                eval_seed=INDEPENDENT_EVAL_SEED + 500,
            )
            naive_trainer.close()
        curriculum = _curriculum_compare(
            tasks,
            seed=seed,
            n_phases=3,
            steps_per_phase=steps_per_task,
            eval_episodes=eval_episodes,
            eval_seed=INDEPENDENT_EVAL_SEED,
        )
        per_seed.append(
            {
                "seed": seed,
                "methods": method_rows,
                "encoder_transfer": transfer,
                "curriculum": curriculum,
            }
        )

    summary: dict[str, Any] = {"methods": {}, "encoder_transfer": {}, "curriculum": {}}
    for method in METHODS:
        finals = []
        forget = []
        steps = []
        for p in per_seed:
            fe = p["methods"][method]["final_eval"]
            finals.append(sum(fe.values()) / max(len(fe), 1))
            forget.append(p["methods"][method]["transfer"]["mean_forgetting"])
            steps.append(p["methods"][method]["steps"])
        summary["methods"][method] = {
            "mean_final_return_across_tasks": summarize_seeds(
                [{"v": f} for f in finals], "v"
            ),
            "mean_forgetting": summarize_seeds([{"v": f} for f in forget], "v"),
            "mean_steps": summarize_seeds([{"v": s} for s in steps], "v"),
        }
    deltas = [
        float((p["encoder_transfer"] or {}).get("delta_vs_scratch", 0.0)) for p in per_seed if p.get("encoder_transfer")
    ]
    summary["encoder_transfer"] = {
        "delta_vs_scratch": summarize_seeds([{"v": d} for d in deltas], "v"),
        "heldout_task": hold.task_id,
        "note": "Positive delta is encoder weight transfer beating matched-step from-scratch on held-out cartpole_lowg.",
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
            "eval_episodes": eval_episodes,
            "independent_eval_seed": INDEPENDENT_EVAL_SEED,
            "not_acrobot": True,
            "compatible_semantics": "obs_dim=4 discrete_n=2 CartPole physics variants only",
        },
        "summary": summary,
        "per_seed": per_seed,
        "caveat": (
            "Small CartPole-variant continual-learning study. "
            "Do not treat a win as AGI or as transfer to Acrobot. "
            "V0.5.2 research-controller results are unchanged."
        ),
        "is_meta_rl": False,
        "is_agi": False,
    }
    if artifact_path is not None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str))
    return payload
