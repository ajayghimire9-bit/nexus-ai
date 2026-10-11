"""V0.7 world-model benchmark. Simulator is an eval oracle, not the planner."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.cl.train import eval_task, make_trainer, train_on_task
from nexus.tasks.cartpole_family import source_policy_task
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec
from nexus.world.baselines import heuristic_cartpole, random_cartpole, run_episodes
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, collect_transitions
from nexus.world.ensemble import disagreement_and_error, train_ensemble
from nexus.world.imagine import action_sensitivity, imagine_actions, multi_step_errors, persistence_errors
from nexus.world.planning import RandomShootingMPC, one_step_greedy
from nexus.world.protocol import (
    COLLECT_TEST_SEED,
    COLLECT_TRAIN_SEED,
    COLLECT_VAL_SEED,
    CONTROL_EVAL_SEED,
    PPO_TRAIN_SEED,
    TRANSFER_COLLECT_SEED,
    TRANSFER_EVAL_SEED,
)
from nexus.world.train import one_step_errors, train_world_model


def v07_transfer_task() -> TaskSpec:
    """Held-out physics. Not a V0.6 confirmation task."""
    return TaskSpec(
        task_id="cartpole_v07_transfer",
        family="cartpole",
        gym_id="CartPole-v1",
        obs_dim=4,
        n_actions=2,
        params={"gravity": 11.0, "length": 0.45, "masspole": 0.15},
        notes="V0.7 transfer physics; corrected derived mass terms.",
    )


def _replay_real(spec: TaskSpec, obs0_seed: int, actions: np.ndarray) -> np.ndarray:
    from nexus.tasks.spec import make_task_env

    env = make_task_env(spec, seed=obs0_seed)
    obs, _ = env.reset(seed=obs0_seed)
    # Walk until we match starting from a fresh reset; caller should pass a seed whose reset is obs0.
    states = []
    for a in actions:
        obs, _, term, trunc, _ = env.step(int(a))
        states.append(np.asarray(obs, dtype=np.float32).reshape(-1))
        if term or trunc:
            break
    env.close()
    return np.stack(states, axis=0) if states else np.zeros((0, spec.obs_dim), dtype=np.float32)


def run_v07_benchmark(
    *,
    n_train: int = 4096,
    n_val: int = 1024,
    n_test: int = 1024,
    epochs: int = 40,
    mpc_candidates: int = 48,
    mpc_horizon: int = 10,
    control_seeds: int = 5,
    eval_episodes: int = 8,
    ensemble_members: int = 3,
    ensemble_epochs: int = 20,
    transfer_n: int = 256,
    ppo_seeds: int = 5,
    artifact_path: str | Path | None = "artifacts/v07_world_model.json",
    checkpoint_dir: str | Path = "checkpoints/v07",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    spec = source_policy_task()
    ckpt = Path(checkpoint_dir)
    ckpt.mkdir(parents=True, exist_ok=True)

    train_ds = collect_transitions(
        spec,
        n_transitions=n_train,
        env_seeds=tuple(range(20)),
        base_seed=COLLECT_TRAIN_SEED,
        mix=("random", "exploratory"),
    )
    val_ds = collect_transitions(
        spec,
        n_transitions=n_val,
        env_seeds=tuple(range(100, 110)),
        base_seed=COLLECT_VAL_SEED,
        mix=("random", "exploratory"),
    )
    test_ds = collect_transitions(
        spec,
        n_transitions=n_test,
        env_seeds=tuple(range(200, 210)),
        base_seed=COLLECT_TEST_SEED,
        mix=("random", "exploratory"),
    )
    assert_disjoint_seeds(train_ds, val_ds, test_ds)
    collect_cost = train_ds.env_interactions + val_ds.env_interactions + test_ds.env_interactions

    residual, residual_log = train_world_model(train_ds, val_ds, kind="residual", epochs=epochs, seed=7)
    direct, direct_log = train_world_model(train_ds, val_ds, kind="direct", epochs=epochs, seed=7)
    residual.save(ckpt / "residual.pt")
    loaded = type(residual).load(ckpt / "residual.pt")
    reload_mae = one_step_errors(loaded, test_ds)["mae"]

    res_err = one_step_errors(residual, test_ds)
    dir_err = one_step_errors(direct, test_ds)
    persist = persistence_errors(test_ds)
    winner_kind = "residual" if res_err["mae"] <= dir_err["mae"] else "direct"
    winner = residual if winner_kind == "residual" else direct
    winner.save(ckpt / "winner.pt")

    horizons = (1, 5, 10, 20)
    multi = multi_step_errors(winner, test_ds, horizons)
    persist_h = {str(h): None for h in horizons}
    # persistence multi-step: predicted state stays at s0
    from nexus.world.data import episodes_from

    for h in horizons:
        maes = []
        for ep in episodes_from(test_ds):
            if ep["obs"].shape[0] < h:
                continue
            pred = np.repeat(ep["obs"][0][None, :], h, axis=0)
            maes.append(float(np.mean(np.abs(pred - ep["next_obs"][:h]))))
        persist_h[str(h)] = float(np.mean(maes)) if maes else None

    sens = action_sensitivity(winner, test_ds.obs[0], spec.n_actions)
    # Compare imagination to a fresh simulator replay of the first long-enough test episode.
    oracle = None
    for ep in episodes_from(test_ds):
        if ep["obs"].shape[0] >= 10:
            imag = imagine_actions(winner, ep["obs"][0], ep["action"][:10])
            # Re-simulate from a dedicated eval seed, not from the collected episode (episode start != that seed reset).
            # Use the recorded true next_obs as the oracle trajectory (already collected; no extra privileged train input).
            oracle = {
                "mae_vs_recorded": float(np.mean(np.abs(imag["states"] - ep["next_obs"][:10]))),
                "n": 10,
                "note": "recorded test trajectory is the oracle; actions were collected independently of the model",
            }
            break

    members, ens_log = train_ensemble(
        train_ds, val_ds, n_members=ensemble_members, kind=winner_kind, epochs=ensemble_epochs, seed=11
    )
    ens_cal = disagreement_and_error(members, test_ds)

    mpc = RandomShootingMPC(model=winner, n_actions=spec.n_actions, horizon=mpc_horizon, n_candidates=mpc_candidates, seed=0)
    mpc_unc = RandomShootingMPC(
        model=winner,
        n_actions=spec.n_actions,
        horizon=mpc_horizon,
        n_candidates=mpc_candidates,
        seed=0,
        ensemble=tuple(members),
        uncertainty_penalty=2.0,
    )

    control_rows: dict[str, list[float]] = {
        "random": [],
        "heuristic": [],
        "one_step_model": [],
        "mpc": [],
        "mpc_uncertainty": [],
        "ppo": [],
    }
    control_cost: dict[str, int] = {k: 0 for k in control_rows}
    plan_ms: list[float] = []
    ppo_train_steps = 0

    for i in range(control_seeds):
        eval_seed = CONTROL_EVAL_SEED + 17 * i
        rng = np.random.default_rng(eval_seed)
        rnd = run_episodes(spec, act_fn=lambda o, r=rng: random_cartpole(o, r), episodes=eval_episodes, seed=eval_seed)
        heu = run_episodes(spec, act_fn=heuristic_cartpole, episodes=eval_episodes, seed=eval_seed)

        def _greedy(o: np.ndarray) -> int:
            return one_step_greedy(winner, o, spec.n_actions)

        greedy = run_episodes(spec, act_fn=_greedy, episodes=eval_episodes, seed=eval_seed)

        def _mpc_act(o: np.ndarray) -> int:
            a, meta = mpc.act(o)
            plan_ms.append(float(meta["plan_ms"]))
            return a

        planned = run_episodes(spec, act_fn=_mpc_act, episodes=eval_episodes, seed=eval_seed)

        def _unc(o: np.ndarray) -> int:
            a, _ = mpc_unc.act(o)
            return a

        unc = run_episodes(spec, act_fn=_unc, episodes=eval_episodes, seed=eval_seed)

        trainer = make_trainer(seed=PPO_TRAIN_SEED + i, timesteps=n_train, spec=spec)
        phase = train_on_task(trainer, spec, timesteps=n_train, seed=PPO_TRAIN_SEED + i)
        ppo_ret = eval_task(
            trainer.agent,
            spec,
            episodes=eval_episodes,
            seed=eval_seed,
            device=trainer.device,
            obs_rms=trainer.obs_rms,
        )
        ppo_train_steps += int(phase.get("timesteps", n_train))
        trainer.close()

        control_rows["random"].append(float(rnd["mean_return"]))
        control_rows["heuristic"].append(float(heu["mean_return"]))
        control_rows["one_step_model"].append(float(greedy["mean_return"]))
        control_rows["mpc"].append(float(planned["mean_return"]))
        control_rows["mpc_uncertainty"].append(float(unc["mean_return"]))
        control_rows["ppo"].append(float(ppo_ret["mean_return"]))
        control_cost["random"] += int(rnd["env_interactions"])
        control_cost["heuristic"] += int(heu["env_interactions"])
        control_cost["one_step_model"] += int(greedy["env_interactions"])
        control_cost["mpc"] += int(planned["env_interactions"])
        control_cost["mpc_uncertainty"] += int(unc["env_interactions"])

    # Transfer
    tgt = v07_transfer_task()
    src_pred_tgt = collect_transitions(
        tgt, n_transitions=n_test, env_seeds=tuple(range(300, 310)), base_seed=TRANSFER_COLLECT_SEED, mix=("random", "exploratory")
    )
    source_on_target = one_step_errors(winner, src_pred_tgt)
    tgt_train = collect_transitions(
        tgt, n_transitions=transfer_n, env_seeds=tuple(range(320, 328)), base_seed=TRANSFER_COLLECT_SEED + 1, mix=("random", "exploratory")
    )
    tgt_val = collect_transitions(
        tgt, n_transitions=max(transfer_n // 2, 64), env_seeds=tuple(range(340, 346)), base_seed=TRANSFER_COLLECT_SEED + 2, mix=("random",)
    )
    scratch, _ = train_world_model(tgt_train, tgt_val, kind=winner_kind, epochs=max(epochs // 2, 8), seed=21)
    from nexus.world.dynamics import WorldModel

    ft_wm = WorldModel.create(spec.obs_dim, spec.n_actions, kind=winner_kind, seed=24)
    ft_wm.net.load_state_dict(winner.net.state_dict())
    ft_wm.copy_rms(winner.obs_rms)
    ft_true, _ = _finetune(ft_wm, tgt_train, tgt_val, epochs=max(epochs // 2, 8), seed=24)
    rms_trained, _ = train_world_model(
        tgt_train,
        tgt_val,
        kind=winner_kind,
        epochs=max(epochs // 2, 8),
        seed=25,
        obs_rms=winner.obs_rms,
        freeze_rms=True,
    )

    transfer_pred = {
        "source_zero_shot": source_on_target,
        "scratch_target": one_step_errors(scratch, src_pred_tgt),
        "finetune_source_weights": one_step_errors(ft_true, src_pred_tgt),
        "source_rms_random_weights": one_step_errors(rms_trained, src_pred_tgt),
        "target_collect_interactions": tgt_train.env_interactions + tgt_val.env_interactions + src_pred_tgt.env_interactions,
    }

    def _tgt_mpc(model: Any) -> list[float]:
        scores = []
        planner = RandomShootingMPC(model=model, n_actions=2, horizon=mpc_horizon, n_candidates=mpc_candidates, seed=3)
        for i in range(min(control_seeds, 3)):
            row = run_episodes(
                tgt,
                act_fn=lambda o, p=planner: p.act(o)[0],
                episodes=max(eval_episodes // 2, 4),
                seed=TRANSFER_EVAL_SEED + i,
            )
            scores.append(float(row["mean_return"]))
        return scores

    transfer_ctrl = {
        "source_mpc": seed_level_ci(_tgt_mpc(winner)),
        "finetune_mpc": seed_level_ci(_tgt_mpc(ft_true)),
        "scratch_mpc": seed_level_ci(_tgt_mpc(scratch)),
        "rms_mpc": seed_level_ci(_tgt_mpc(rms_trained)),
    }

    payload = {
        "protocol": {
            "code_version": "v0.7.0",
            "parent_commit": "c38b54e",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "task": spec.task_id,
            "transfer_task": tgt.task_id,
            "transfer_params": dict(tgt.params),
            "collect_seeds": {
                "train_base": COLLECT_TRAIN_SEED,
                "val_base": COLLECT_VAL_SEED,
                "test_base": COLLECT_TEST_SEED,
            },
            "control_eval_seed": CONTROL_EVAL_SEED,
            "n_train": n_train,
            "n_val": n_val,
            "n_test": n_test,
            "mpc_candidates": mpc_candidates,
            "mpc_horizon": mpc_horizon,
            "winner_kind": winner_kind,
            "planner_uses_simulator": False,
            "is_agi": False,
        },
        "collection": {
            "train": len(train_ds),
            "val": len(val_ds),
            "test": len(test_ds),
            "env_interactions": collect_cost,
            "disjoint_seeds": True,
        },
        "prediction": {
            "persistence": persist,
            "residual": {"one_step": res_err, "val": residual_log["best_val"]},
            "direct": {"one_step": dir_err, "val": direct_log["best_val"]},
            "winner": winner_kind,
            "reload_test_mae": reload_mae,
            "multi_step": multi,
            "persistence_multi_step_mae": persist_h,
            "action_sensitivity": sens,
            "oracle_check": oracle,
        },
        "ensemble": {**ens_log, "calibration": ens_cal},
        "control": {
            k: {"returns": seed_level_ci(v), "eval_env_interactions": control_cost.get(k, 0)}
            for k, v in control_rows.items()
        },
        "costs": {
            "model_collect_env_steps": collect_cost,
            "ppo_train_env_steps_sum": ppo_train_steps,
            "ppo_matched_collect_n_train": n_train,
            "mean_plan_ms": float(np.mean(plan_ms)) if plan_ms else None,
            "n_plan_calls": len(plan_ms),
        },
        "transfer": {"prediction": transfer_pred, "control": transfer_ctrl},
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "CartPole world model. Not AGI. Simulator used only as eval oracle.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload


def _finetune(wm: Any, train: TransitionDataset, val: TransitionDataset, *, epochs: int, seed: int) -> tuple[Any, dict[str, Any]]:
    """Continue Adam from current weights on target data, keeping current RMS."""
    rng = np.random.default_rng(seed)
    opt = torch.optim.Adam(wm.net.parameters(), lr=5e-4)
    loss_fn = torch.nn.MSELoss()
    bce = torch.nn.BCEWithLogitsLoss()
    best = 1e18
    best_state = {k: v.detach().cpu().clone() for k, v in wm.net.state_dict().items()}
    history = []
    for epoch in range(epochs):
        wm.net.train()
        idx = rng.permutation(len(train))
        for i in range(0, len(train), 64):
            sl = idx[i : i + 64]
            obs = torch.as_tensor(wm.normalize(train.obs[sl]))
            nxt = torch.as_tensor(wm.normalize(train.next_obs[sl]))
            act = torch.as_tensor(train.action[sl], dtype=torch.int64)
            term = torch.as_tensor(train.terminated[sl].astype(np.float32))
            pred, logit = wm.net(obs, act)
            target = nxt - obs if wm.kind == "residual" else nxt
            loss = loss_fn(pred, target) + 0.25 * bce(logit, term)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        wm.net.eval()
        with torch.no_grad():
            obs = torch.as_tensor(wm.normalize(val.obs))
            nxt = torch.as_tensor(wm.normalize(val.next_obs))
            act = torch.as_tensor(val.action, dtype=torch.int64)
            pred, logit = wm.net(obs, act)
            target = nxt - obs if wm.kind == "residual" else nxt
            v = float(loss_fn(pred, target).item())
        history.append(v)
        if v < best:
            best = v
            best_state = {k: t.detach().cpu().clone() for k, t in wm.net.state_dict().items()}
    wm.net.load_state_dict(best_state)
    wm.net.eval()
    return wm, {"best_val": best, "history": history}
