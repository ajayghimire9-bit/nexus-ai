"""V0.7.1: val-only selection, multi-seed world models, absorbing MPC."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

from nexus.cl.metrics import paired_seed_deltas, seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.cl.train import eval_task, make_trainer, train_on_task
from nexus.cl.v064 import make_v064_trainer
from nexus.tasks.cartpole_family import source_policy_task
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, make_task_env
from nexus.world.baselines import heuristic_cartpole, random_cartpole, run_episodes
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.ensemble import disagreement_and_error, train_ensemble
from nexus.world.experiment import _finetune, v07_transfer_task
from nexus.world.imagine import multi_step_errors, persistence_errors
from nexus.world.linear import fit_ridge
from nexus.world.planning import InferenceCounter, MeanEnsemble, RandomShootingMPC, one_step_greedy
from nexus.world.protocol import COLLECT_TEST_SEED, COLLECT_TRAIN_SEED, COLLECT_VAL_SEED, CONTROL_EVAL_SEED, PPO_TRAIN_SEED, TRANSFER_COLLECT_SEED, TRANSFER_EVAL_SEED
from nexus.world.select import select_winner
from nexus.world.term_metrics import termination_report
from nexus.world.train import one_step_errors, train_world_model


def _logged_ds(spec: Any, row: dict[str, Any], task_id: str) -> TransitionDataset:
    t = row["transitions"]
    n = int(t["obs"].shape[0])
    return TransitionDataset(
        obs=t["obs"],
        action=t["action"],
        next_obs=t["next_obs"],
        reward=np.ones(n, dtype=np.float32),
        terminated=t["terminated"],
        truncated=np.zeros(n, dtype=np.bool_),
        task_id=task_id,
        seed=np.zeros(n, dtype=np.int64),
        episode_id=np.zeros(n, dtype=np.int64),
        policy=np.array(["controller"] * n),
        physics=dict(spec.params),
        env_interactions=n,
    )


def _action_rank(model: Any, spec: Any, obs: np.ndarray, *, max_n: int = 64) -> dict[str, Any]:
    env = make_task_env(spec, seed=0)
    n = min(int(max_n), int(obs.shape[0]))
    ok = 0
    steps = 0
    for i in range(n):
        o = np.asarray(obs[i], dtype=np.float32).reshape(-1)
        p0 = np.asarray(model.step(o, 0)[0]).reshape(-1)
        p1 = np.asarray(model.step(o, 1)[0]).reshape(-1)
        pred = 0 if abs(float(p0[2])) <= abs(float(p1[2])) else 1
        th = []
        for a in (0, 1):
            env.reset()
            env.unwrapped.state = np.array(o, dtype=np.float64)
            nxt, _, _, _, _ = env.step(int(a))
            steps += 1
            th.append(abs(float(np.asarray(nxt, dtype=np.float32).reshape(-1)[2])))
        true = 0 if th[0] <= th[1] else 1
        ok += int(pred == true)
    env.close()
    return {"accuracy": float(ok / max(n, 1)), "n": n, "oracle_env_steps": steps}


def _eval_controller(spec: Any, act: Callable[[np.ndarray], int], *, episodes: int, seed: int) -> dict[str, Any]:
    return run_episodes(spec, act_fn=act, episodes=episodes, seed=seed)


def run_v071_benchmark(
    *,
    n_model_seeds: int = 10,
    n_train: int = 2048,
    n_val: int = 512,
    n_test: int = 512,
    epochs: int = 25,
    mpc_candidates: int = 32,
    mpc_horizon: int = 8,
    paired_eval_seeds: int = 3,
    eval_episodes: int = 4,
    ensemble_members: int = 3,
    ensemble_epochs: int = 8,
    transfer_n: int = 256,
    ppo_short_seeds: int = 5,
    ppo_strong_seeds: int = 3,
    ppo_strong_steps: int = 16_384,
    dagger_episodes: int = 4,
    artifact_path: str | Path | None = "artifacts/v071_world_model.json",
    checkpoint_dir: str | Path = "checkpoints/v071",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    spec = source_policy_task()
    tgt = v07_transfer_task()
    ckpt = Path(checkpoint_dir)
    ckpt.mkdir(parents=True, exist_ok=True)
    horizons = (1, 5, 10, 20)
    frozen_kind: str | None = None
    per_seed: list[dict[str, Any]] = []
    analysis_oracle_steps = 0

    for mseed in range(n_model_seeds):
        train_ds = collect_transitions(
            spec,
            n_transitions=n_train,
            env_seeds=tuple(range(20 + 30 * mseed, 40 + 30 * mseed)),
            base_seed=COLLECT_TRAIN_SEED + 1009 * mseed,
            mix=("random", "exploratory"),
        )
        val_ds = collect_transitions(
            spec,
            n_transitions=n_val,
            env_seeds=tuple(range(400 + 20 * mseed, 410 + 20 * mseed)),
            base_seed=COLLECT_VAL_SEED + 1009 * mseed,
            mix=("random", "exploratory"),
        )
        test_ds = collect_transitions(
            spec,
            n_transitions=n_test,
            env_seeds=tuple(range(800 + 20 * mseed, 810 + 20 * mseed)),
            base_seed=COLLECT_TEST_SEED + 1009 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train_ds, val_ds, test_ds)
        residual, rlog = train_world_model(train_ds, val_ds, kind="residual", epochs=epochs, seed=7 + 13 * mseed)
        direct, dlog = train_world_model(train_ds, val_ds, kind="direct", epochs=epochs, seed=7 + 13 * mseed)
        ridge = fit_ridge(train_ds, l2=1e-2, residual=True, n_actions=2)
        models = {"residual": residual, "direct": direct, "ridge": ridge}
        kind, val_mae = select_winner(models, val_ds)
        if frozen_kind is None:
            frozen_kind = kind
        planner_kind = frozen_kind
        planner: Any = residual
        if planner_kind == "direct":
            planner = direct
        elif planner_kind == "ridge":
            planner = ridge
        if mseed == 0:
            residual.save(ckpt / "frozen_residual.pt")
        test_err = {name: one_step_errors(mod, test_ds) for name, mod in models.items()}
        persist = persistence_errors(test_ds)
        multi = {name: multi_step_errors(mod, test_ds, horizons) for name, mod in models.items()}
        members, ens_log = train_ensemble(
            train_ds, val_ds, n_members=ensemble_members, kind=planner_kind if planner_kind != "ridge" else "residual", epochs=ensemble_epochs, seed=11 + mseed
        )
        ens_cal = disagreement_and_error(members, test_ds)
        p_term, y = planner.step(test_ds.obs, test_ds.action)[1], test_ds.terminated
        term = termination_report(p_term, y)

        mean_ens = MeanEnsemble(members)
        inf_mpc = InferenceCounter(planner)
        inf_matched = InferenceCounter(planner)
        inf_ens0 = InferenceCounter(mean_ens)
        inf_ensp = InferenceCounter(mean_ens)
        mpc = RandomShootingMPC(model=planner, n_actions=2, horizon=mpc_horizon, n_candidates=mpc_candidates, seed=0, inference=inf_mpc, objective="predicted_reward")
        mpc_matched = RandomShootingMPC(
            model=planner,
            n_actions=2,
            horizon=mpc_horizon,
            n_candidates=mpc_candidates * max(ensemble_members, 1),
            seed=0,
            inference=inf_matched,
            objective="predicted_reward",
        )
        mpc_ens0 = RandomShootingMPC(
            model=mean_ens, n_actions=2, horizon=mpc_horizon, n_candidates=mpc_candidates, seed=0, inference=inf_ens0, ensemble=tuple(members), uncertainty_penalty=0.0
        )
        mpc_ensp = RandomShootingMPC(
            model=mean_ens, n_actions=2, horizon=mpc_horizon, n_candidates=mpc_candidates, seed=0, inference=inf_ensp, ensemble=tuple(members), uncertainty_penalty=2.0
        )

        ctrl: dict[str, list[float]] = {
            k: [] for k in ("random", "heuristic", "greedy", "mpc", "mpc_matched", "ens_zero", "ens_pen", "residual_greedy", "residual_mpc")
        }
        ctrl_env = {k: 0 for k in ctrl}
        plan_ms: dict[str, list[float]] = {k: [] for k in ("mpc", "mpc_matched", "ens_zero", "ens_pen")}
        for i in range(paired_eval_seeds):
            es = CONTROL_EVAL_SEED + 17 * i
            rng = np.random.default_rng(es)

            def _g(o: np.ndarray, p=planner) -> int:
                return one_step_greedy(p, o, 2)

            res_mpc = RandomShootingMPC(model=residual, n_actions=2, horizon=mpc_horizon, n_candidates=mpc_candidates, seed=0, objective="predicted_reward")

            def _rg(o: np.ndarray, p=residual) -> int:
                return one_step_greedy(p, o, 2)

            rows = {
                "random": _eval_controller(spec, lambda o, r=rng: random_cartpole(o, r), episodes=eval_episodes, seed=es),
                "heuristic": _eval_controller(spec, heuristic_cartpole, episodes=eval_episodes, seed=es),
                "greedy": _eval_controller(spec, _g, episodes=eval_episodes, seed=es),
                "mpc": _eval_controller(spec, lambda o, p=mpc, k="mpc": _plan(p, o, plan_ms, k), episodes=eval_episodes, seed=es),
                "mpc_matched": _eval_controller(spec, lambda o, p=mpc_matched, k="mpc_matched": _plan(p, o, plan_ms, k), episodes=eval_episodes, seed=es),
                "ens_zero": _eval_controller(spec, lambda o, p=mpc_ens0, k="ens_zero": _plan(p, o, plan_ms, k), episodes=eval_episodes, seed=es),
                "ens_pen": _eval_controller(spec, lambda o, p=mpc_ensp, k="ens_pen": _plan(p, o, plan_ms, k), episodes=eval_episodes, seed=es),
                "residual_greedy": _eval_controller(spec, _rg, episodes=eval_episodes, seed=es),
                "residual_mpc": _eval_controller(spec, lambda o, p=res_mpc: p.act(o)[0], episodes=eval_episodes, seed=es),
            }
            for k, row in rows.items():
                ctrl[k].append(float(row["mean_return"]))
                ctrl_env[k] += int(row["env_interactions"])

        rank = _action_rank(planner, spec, test_ds.obs, max_n=48)
        analysis_oracle_steps += int(rank["oracle_env_steps"])
        print(f"v071 model_seed={mseed} val_mae={val_mae} planner={planner_kind}", flush=True)
        per_seed.append(
            {
                "model_seed": mseed,
                "collect_train_seed": COLLECT_TRAIN_SEED + 1009 * mseed,
                "init_seed": 7 + 13 * mseed,
                "val_mae": val_mae,
                "selected_on_val": kind,
                "frozen_planner_kind": planner_kind,
                "test_mae": {k: v["mae"] for k, v in test_err.items()},
                "test_mae_per_dim": {k: v["mae_per_dim"] for k, v in test_err.items()},
                "persistence_mae": persist["mae"],
                "multi_step": multi,
                "term": term,
                "ensemble_cal": ens_cal,
                "control": {k: float(np.mean(v)) for k, v in ctrl.items()},
                "control_per_eval_seed": ctrl,
                "control_eval_env_steps": ctrl_env,
                "plan_ms_mean": {k: float(np.mean(v)) if v else None for k, v in plan_ms.items()},
                "inferences": {
                    "mpc_states": inf_mpc.states,
                    "mpc_matched_states": inf_matched.states,
                    "ens_zero_states": inf_ens0.states,
                    "ens_pen_states": inf_ensp.states,
                },
                "action_rank": rank,
                "learning_env_steps": train_ds.env_interactions + val_ds.env_interactions,
                "test_collect_env_steps": test_ds.env_interactions,
                "train_n": len(train_ds),
                "val_log": {"residual": rlog["best_val"], "direct": dlog["best_val"]},
            }
        )

    assert frozen_kind is not None
    # PPO at matched learning budget and a stronger frozen recipe.
    learn_budget = n_train + n_val
    ppo_short = []
    ppo_short_steps = 0
    for i in range(ppo_short_seeds):
        tr = make_trainer(seed=PPO_TRAIN_SEED + i, timesteps=learn_budget, spec=spec)
        phase = train_on_task(tr, spec, timesteps=learn_budget, seed=PPO_TRAIN_SEED + i)
        ppo_short_steps += int(phase.get("timesteps", learn_budget))
        ret = eval_task(tr.agent, spec, episodes=eval_episodes, seed=CONTROL_EVAL_SEED + 17 * (i % max(paired_eval_seeds, 1)), device=tr.device, obs_rms=tr.obs_rms)
        ppo_short.append(float(ret["mean_return"]))
        tr.close()
    ppo_strong: list[float] = []
    strong_sum = 0
    for i in range(ppo_strong_seeds):
        tr = make_v064_trainer(seed=PPO_TRAIN_SEED + 50 + i, timesteps=ppo_strong_steps, spec=spec)
        phase = train_on_task(tr, spec, timesteps=ppo_strong_steps, seed=PPO_TRAIN_SEED + 50 + i)
        strong_sum += int(phase.get("timesteps", ppo_strong_steps))
        ret = eval_task(tr.agent, spec, episodes=eval_episodes, seed=CONTROL_EVAL_SEED, device=tr.device, obs_rms=tr.obs_rms)
        ppo_strong.append(float(ret["mean_return"]))
        tr.close()

    # Transfer / prediction-vs-control using frozen seed-0 residual (val-selected kind).
    src = WorldModel.load(ckpt / "frozen_residual.pt") if (ckpt / "frozen_residual.pt").exists() else residual
    tgt_rand = collect_transitions(tgt, n_transitions=n_test, env_seeds=tuple(range(300, 308)), base_seed=TRANSFER_COLLECT_SEED, mix=("random", "exploratory"))
    tgt_tr = collect_transitions(tgt, n_transitions=transfer_n, env_seeds=tuple(range(320, 326)), base_seed=TRANSFER_COLLECT_SEED + 1, mix=("random", "exploratory"))
    tgt_va = collect_transitions(tgt, n_transitions=max(transfer_n // 2, 64), env_seeds=tuple(range(340, 344)), base_seed=TRANSFER_COLLECT_SEED + 2, policy="random")
    scratch, _ = train_world_model(tgt_tr, tgt_va, kind="residual", epochs=max(epochs // 2, 6), seed=21)
    ft_wm = WorldModel.create(spec.obs_dim, spec.n_actions, kind="residual", seed=24)
    ft_wm.net.load_state_dict(src.net.state_dict())
    ft_wm.copy_rms(src.obs_rms)
    ft, _ = _finetune(ft_wm, tgt_tr, tgt_va, epochs=max(epochs // 2, 6), seed=24)
    pred_rand = {"source": one_step_errors(src, tgt_rand), "finetune": one_step_errors(ft, tgt_rand), "scratch": one_step_errors(scratch, tgt_rand)}

    def _mpc_row(model: Any, eval_i: int) -> dict[str, Any]:
        planner = RandomShootingMPC(model=model, n_actions=2, horizon=mpc_horizon, n_candidates=mpc_candidates, seed=0, objective="predicted_reward")
        return _eval_controller(tgt, lambda o, p=planner: p.act(o)[0], episodes=eval_episodes, seed=TRANSFER_EVAL_SEED + eval_i)

    src_ctrl = [_mpc_row(src, i) for i in range(min(paired_eval_seeds, 3))]
    ft_ctrl = [_mpc_row(ft, i) for i in range(min(paired_eval_seeds, 3))]
    src_onpol = _logged_ds(tgt, src_ctrl[0], tgt.task_id)
    ft_onpol = _logged_ds(tgt, ft_ctrl[0], tgt.task_id)
    onpol_mae = {
        "source_on_source_mpc_states": one_step_errors(src, src_onpol) if len(src_onpol) else None,
        "finetune_on_source_mpc_states": one_step_errors(ft, src_onpol) if len(src_onpol) else None,
        "source_on_finetune_mpc_states": one_step_errors(src, ft_onpol) if len(ft_onpol) else None,
        "finetune_on_finetune_mpc_states": one_step_errors(ft, ft_onpol) if len(ft_onpol) else None,
    }
    src_rank = _action_rank(src, tgt, tgt_rand.obs, max_n=48)
    ft_rank = _action_rank(ft, tgt, tgt_rand.obs, max_n=48)
    analysis_oracle_steps += src_rank["oracle_env_steps"] + ft_rank["oracle_env_steps"]
    src_multi = multi_step_errors(src, tgt_rand, horizons)
    ft_multi = multi_step_errors(ft, tgt_rand, horizons)
    src_term = termination_report(src.step(tgt_rand.obs, tgt_rand.action)[1], tgt_rand.terminated)
    ft_term = termination_report(ft.step(tgt_rand.obs, tgt_rand.action)[1], tgt_rand.terminated)

    # Extra on-policy data: collect from source MPC on target (counted), mix, finetune, re-eval on held-out eval seeds.
    dagger_row = _eval_controller(
        tgt,
        lambda o, p=RandomShootingMPC(model=src, n_actions=2, horizon=mpc_horizon, n_candidates=mpc_candidates, seed=1): p.act(o)[0],
        episodes=dagger_episodes,
        seed=TRANSFER_COLLECT_SEED + 50,
    )
    dag_ds = _logged_ds(tgt, dagger_row, tgt.task_id)
    mixed_obs = np.concatenate([tgt_tr.obs, dag_ds.obs], axis=0) if len(dag_ds) else tgt_tr.obs
    mixed = TransitionDataset(
        obs=mixed_obs,
        action=np.concatenate([tgt_tr.action, dag_ds.action]) if len(dag_ds) else tgt_tr.action,
        next_obs=np.concatenate([tgt_tr.next_obs, dag_ds.next_obs]) if len(dag_ds) else tgt_tr.next_obs,
        reward=np.concatenate([tgt_tr.reward, dag_ds.reward]) if len(dag_ds) else tgt_tr.reward,
        terminated=np.concatenate([tgt_tr.terminated, dag_ds.terminated]) if len(dag_ds) else tgt_tr.terminated,
        truncated=np.concatenate([tgt_tr.truncated, dag_ds.truncated]) if len(dag_ds) else tgt_tr.truncated,
        task_id=tgt.task_id,
        seed=np.concatenate([tgt_tr.seed, dag_ds.seed]) if len(dag_ds) else tgt_tr.seed,
        episode_id=np.concatenate([tgt_tr.episode_id, dag_ds.episode_id]) if len(dag_ds) else tgt_tr.episode_id,
        policy=np.concatenate([tgt_tr.policy, dag_ds.policy]) if len(dag_ds) else tgt_tr.policy,
        physics=dict(tgt.params),
        env_interactions=tgt_tr.env_interactions + dag_ds.env_interactions,
    )
    dag_wm = WorldModel.create(spec.obs_dim, spec.n_actions, kind="residual", seed=30)
    dag_wm.net.load_state_dict(src.net.state_dict())
    dag_wm.copy_rms(src.obs_rms)
    dag_ft, _ = _finetune(dag_wm, mixed, tgt_va, epochs=max(epochs // 2, 6), seed=30)
    dag_ctrl = [_mpc_row(dag_ft, i) for i in range(min(paired_eval_seeds, 3))]

    def _means(key: str) -> list[float]:
        return [float(p["control"][key]) for p in per_seed]

    def _mae(name: str) -> list[float]:
        return [float(p["test_mae"][name]) for p in per_seed]

    control_table = {k: seed_level_ci(_means(k)) for k in per_seed[0]["control"]}
    paired_ctrl: dict[int, dict[str, dict[str, float]]] = {
        int(p["model_seed"]): {
            "src": {
                "mpc": p["control"]["mpc"],
                "greedy": p["control"]["greedy"],
                "ens_pen": p["control"]["ens_pen"],
                "ens_zero": p["control"]["ens_zero"],
                "mpc_matched": p["control"]["mpc_matched"],
                "heuristic": p["control"]["heuristic"],
                "random": p["control"]["random"],
                "residual_mpc": p["control"]["residual_mpc"],
                "residual_greedy": p["control"]["residual_greedy"],
            }
        }
        for p in per_seed
    }
    payload = {
        "protocol": {
            "code_version": "v0.7.1",
            "parent_commit": "5c14294",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "selection": "validation MAE only; planner kind frozen from model seed 0",
            "residual_controllers": "diagnostic only; not used to pick kind",
            "frozen_planner_kind": frozen_kind,
            "n_model_seeds": n_model_seeds,
            "n_train": n_train,
            "n_val": n_val,
            "n_test": n_test,
            "mpc_candidates": mpc_candidates,
            "mpc_horizon": mpc_horizon,
            "objective": "predicted_reward with absorbing survival",
            "time_budget_enforced": True,
            "planner_uses_simulator": False,
            "is_agi": False,
        },
        "prediction": {
            "persistence": seed_level_ci([p["persistence_mae"] for p in per_seed]),
            "ridge": seed_level_ci(_mae("ridge")),
            "direct": seed_level_ci(_mae("direct")),
            "residual": seed_level_ci(_mae("residual")),
            "per_seed_test_mae": [{k: p["test_mae"][k] for k in p["test_mae"]} | {"seed": p["model_seed"]} for p in per_seed],
        },
        "control": control_table,
        "paired_control": {
            "mpc_minus_greedy": paired_seed_deltas(per_seed_task=paired_ctrl, treatment="mpc", baseline="greedy"),
            "ens_pen_minus_mpc": paired_seed_deltas(per_seed_task=paired_ctrl, treatment="ens_pen", baseline="mpc"),
            "ens_pen_minus_ens_zero": paired_seed_deltas(per_seed_task=paired_ctrl, treatment="ens_pen", baseline="ens_zero"),
            "mpc_minus_matched": paired_seed_deltas(per_seed_task=paired_ctrl, treatment="mpc_matched", baseline="mpc"),
            "mpc_minus_random": paired_seed_deltas(per_seed_task=paired_ctrl, treatment="mpc", baseline="random"),
            "residual_mpc_minus_residual_greedy": paired_seed_deltas(per_seed_task=paired_ctrl, treatment="residual_mpc", baseline="residual_greedy"),
            "residual_mpc_minus_random": paired_seed_deltas(per_seed_task=paired_ctrl, treatment="residual_mpc", baseline="random"),
        },
        "diagnostic_note": "residual_* controllers are not used for architecture selection; they diagnose planning when the val-MAE winner is a linear model.",
        "ppo": {
            "short_matched_learn_budget": {"steps_per_seed": learn_budget, "returns": seed_level_ci(ppo_short), "train_env_steps_sum": ppo_short_steps},
            "strong_v064": {"steps_per_seed": ppo_strong_steps, "returns": seed_level_ci(ppo_strong), "train_env_steps_sum": strong_sum},
        },
        "costs": {
            "mean_learning_env_steps": float(np.mean([p["learning_env_steps"] for p in per_seed])),
            "mean_test_collect_env_steps": float(np.mean([p["test_collect_env_steps"] for p in per_seed])),
            "mean_control_eval_env_steps": {k: float(np.mean([p["control_eval_env_steps"][k] for p in per_seed])) for k in per_seed[0]["control_eval_env_steps"]},
            "mean_inferences": {k: float(np.mean([p["inferences"][k] for p in per_seed])) for k in per_seed[0]["inferences"]},
            "mean_plan_ms": {k: float(np.mean([p["plan_ms_mean"][k] for p in per_seed if p["plan_ms_mean"][k] is not None])) for k in ("mpc", "mpc_matched", "ens_zero", "ens_pen")},
            "analysis_oracle_env_steps": analysis_oracle_steps,
            "dagger_env_steps": int(dagger_row["env_interactions"]),
            "transfer_collect": tgt_rand.env_interactions + tgt_tr.env_interactions + tgt_va.env_interactions,
        },
        "termination": {
            "mean_brier": seed_level_ci([p["term"]["brier"] for p in per_seed]),
            "mean_prevalence": seed_level_ci([p["term"]["prevalence"] for p in per_seed]),
            "mean_recall": seed_level_ci([p["term"]["recall"] for p in per_seed]),
            "always_nonterminal_brier": seed_level_ci([p["term"]["always_nonterminal_brier"] for p in per_seed]),
        },
        "ensemble_corr": seed_level_ci([p["ensemble_cal"]["error_vs_std_corr"] for p in per_seed]),
        "action_rank": seed_level_ci([p["action_rank"]["accuracy"] for p in per_seed]),
        "transfer": {
            "random_policy_mae": pred_rand,
            "on_policy_mae": onpol_mae,
            "multi_step": {"source": src_multi, "finetune": ft_multi},
            "term": {"source": src_term, "finetune": ft_term},
            "action_rank": {"source": src_rank, "finetune": ft_rank},
            "mpc_returns": {
                "source": seed_level_ci([float(r["mean_return"]) for r in src_ctrl]),
                "finetune": seed_level_ci([float(r["mean_return"]) for r in ft_ctrl]),
                "dagger_finetune": seed_level_ci([float(r["mean_return"]) for r in dag_ctrl]),
            },
            "note": "Transfer control seeds are held out from adaptation. DAgger mix uses extra counted MPC env steps.",
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.7.1 planning validation. Not AGI. Not V0.6.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload


def _plan(planner: RandomShootingMPC, obs: np.ndarray, store: dict[str, list[float]], key: str) -> int:
    a, meta = planner.act(obs)
    store[key].append(float(meta["plan_ms"]))
    return a
