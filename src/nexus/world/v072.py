"""V0.7.2: persistent MPC RNG, termination isolation, matched-horizon planning."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from nexus.cl.metrics import paired_seed_deltas, seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import source_policy_task
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION
from nexus.world.baselines import heuristic_cartpole, random_cartpole, run_episodes
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, collect_transitions
from nexus.world.ensemble import train_ensemble
from nexus.world.imagine import multi_step_errors
from nexus.world.linear import fit_ridge
from nexus.world.planning import InferenceCounter, MeanEnsemble, RandomShootingMPC, one_step_greedy
from nexus.world.protocol import COLLECT_TEST_SEED, COLLECT_TRAIN_SEED, COLLECT_VAL_SEED, CONTROL_EVAL_SEED
from nexus.world.terminate import TermOverride, TermMode, fit_temperature, term_metrics_for_mode
from nexus.world.train import one_step_errors, train_world_model

PLAN_BUDGET = 48
HORIZONS = (1, 3, 6, 10, 20)
TERM_MODES: tuple[TermMode, ...] = ("learned", "always_live", "calibrated", "geometric")


def _n_cand(horizon: int, budget: int = PLAN_BUDGET) -> int:
    return max(2, int(budget) // int(horizon))


def _logged_ds(spec: Any, row: dict[str, Any]) -> TransitionDataset:
    t = row["transitions"]
    n = int(t["obs"].shape[0])
    return TransitionDataset(
        obs=t["obs"],
        action=t["action"],
        next_obs=t["next_obs"],
        reward=np.ones(n, dtype=np.float32),
        terminated=t["terminated"],
        truncated=np.zeros(n, dtype=np.bool_),
        task_id=spec.task_id,
        seed=np.zeros(n, dtype=np.int64),
        episode_id=np.zeros(n, dtype=np.int64),
        policy=np.array(["mpc"] * n),
        physics=dict(spec.params),
        env_interactions=n,
    )


def _eval_mpc(
    spec: Any,
    planner: RandomShootingMPC,
    *,
    episodes: int,
    seed: int,
) -> dict[str, Any]:
    imagined: list[float] = []

    def _act(o: np.ndarray) -> int:
        a, meta = planner.act(o)
        imagined.append(float(meta["best_score"]))
        return a

    row = run_episodes(
        spec,
        act_fn=_act,
        episodes=episodes,
        seed=seed,
        on_episode_start=lambda ep, p=planner, s=seed: p.reset_episode(s + 1000 * ep),
    )
    row["imagined_mean_score"] = float(np.mean(imagined)) if imagined else None
    row["n_plan_decisions"] = len(imagined)
    return row


def run_v072_benchmark(
    *,
    n_model_seeds: int = 5,
    n_train: int = 1024,
    n_val: int = 256,
    n_test: int = 256,
    epochs: int = 20,
    paired_eval_seeds: int = 2,
    eval_episodes: int = 2,
    ensemble_members: int = 3,
    ensemble_epochs: int = 8,
    quick: bool = False,
    artifact_path: str | Path | None = "artifacts/v072_world_model.json",
    checkpoint_dir: str | Path = "checkpoints/v072",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    spec = source_policy_task()
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    per_seed: list[dict[str, Any]] = []
    objective: Any = "both"

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            spec,
            n_transitions=n_train,
            env_seeds=tuple(range(20 + 25 * mseed, 40 + 25 * mseed)),
            base_seed=COLLECT_TRAIN_SEED + 17 * mseed,
            mix=("random", "exploratory"),
        )
        val = collect_transitions(
            spec,
            n_transitions=n_val,
            env_seeds=tuple(range(500 + 10 * mseed, 508 + 10 * mseed)),
            base_seed=COLLECT_VAL_SEED + 17 * mseed,
            mix=("random", "exploratory"),
        )
        test = collect_transitions(
            spec,
            n_transitions=n_test,
            env_seeds=tuple(range(900 + 10 * mseed, 908 + 10 * mseed)),
            base_seed=COLLECT_TEST_SEED + 17 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val, test)
        residual, _ = train_world_model(train, val, kind="residual", epochs=epochs, seed=3 + 11 * mseed)
        ridge = fit_ridge(train, l2=1e-2, residual=True, n_actions=2)
        members, _ = train_ensemble(train, val, n_members=ensemble_members, kind="residual", epochs=ensemble_epochs, seed=9 + mseed)
        mean_ens = MeanEnsemble(members)
        temps = {"residual": fit_temperature(residual, val), "ridge": fit_temperature(ridge, val)}
        models = {"ridge": ridge, "residual": residual, "ensemble": mean_ens}

        term_table = {}
        for name, mod in (("ridge", ridge), ("residual", residual)):
            term_table[name] = {
                mode: term_metrics_for_mode(mod, test, mode, temperature=temps[name] if mode == "calibrated" else 1.0)
                for mode in TERM_MODES
            }

        control: dict[str, dict[str, list[float]]] = {}
        exploit: dict[str, Any] = {}
        inferences: dict[str, list[int]] = {}

        def _run(name: str, model: Any, *, horizon: int, mode: TermMode, penalty: float = 0.0, n_cand: int | None = None) -> None:
            temp = 1.0
            if mode == "calibrated":
                temp = float(temps["ridge"] if name == "ridge" else temps["residual"])
            wrapped = TermOverride(model, mode, temperature=temp)
            nc = _n_cand(horizon) if n_cand is None else int(n_cand)
            inf = InferenceCounter(wrapped)
            planner = RandomShootingMPC(
                model=wrapped,
                n_actions=2,
                horizon=horizon,
                n_candidates=nc,
                seed=0,
                uncertainty_penalty=penalty,
                ensemble=tuple(members) if penalty > 0 else None,
                inference=inf,
                objective=objective,
                enforce_time_budget=True,
            )
            rets = []
            env_n = 0
            onpol_mae = []
            imag = []
            real = []
            for i in range(paired_eval_seeds):
                es = CONTROL_EVAL_SEED + 19 * i
                inf.calls = 0
                inf.states = 0
                row = _eval_mpc(spec, planner, episodes=eval_episodes, seed=es)
                rets.append(float(row["mean_return"]))
                env_n += int(row["env_interactions"])
                ds = _logged_ds(spec, row)
                if len(ds):
                    onpol_mae.append(float(one_step_errors(wrapped, ds)["mae"]))
                imag.append(row["imagined_mean_score"])
                real.append(float(row["mean_return"]))
            key = f"{name}|{mode}|h{horizon}|p{penalty}|c{nc}"
            control.setdefault(key, {"returns": []})
            control[key]["returns"] = rets
            inferences[key] = [inf.states]
            exploit[key] = {
                "on_policy_mae": float(np.mean(onpol_mae)) if onpol_mae else None,
                "imagined_score": float(np.mean([x for x in imag if x is not None])) if imag else None,
                "realized_return": float(np.mean(real)),
                "eval_env_steps": env_n,
                "n_cand": nc,
                "horizon": horizon,
                "evals_per_decision": nc * horizon,
            }

        horizons = (1, 6) if quick else HORIZONS
        term_modes: tuple[TermMode, ...] = ("learned", "always_live") if quick else TERM_MODES
        for mode in term_modes:
            _run("ridge", ridge, horizon=6, mode=mode)
            _run("residual", residual, horizon=6, mode=mode)
        for h in horizons:
            for mode in ("learned", "always_live"):
                if h == 6 and mode in term_modes:
                    continue
                _run("ridge", ridge, horizon=h, mode=mode)
                _run("residual", residual, horizon=h, mode=mode)
            _run("ensemble", mean_ens, horizon=h, mode="always_live", penalty=0.0)
            if not quick:
                _run("ensemble", mean_ens, horizon=h, mode="always_live", penalty=2.0)
        # One-step greedy (same ranking terms, 2 model evals).
        g_rets_r, g_rets_d = [], []
        for i in range(paired_eval_seeds):
            es = CONTROL_EVAL_SEED + 19 * i
            g_rets_r.append(float(run_episodes(spec, act_fn=lambda o, m=ridge: one_step_greedy(m, o, 2), episodes=eval_episodes, seed=es)["mean_return"]))
            g_rets_d.append(float(run_episodes(spec, act_fn=lambda o, m=residual: one_step_greedy(m, o, 2), episodes=eval_episodes, seed=es)["mean_return"]))
        rnd, heu = [], []
        for i in range(paired_eval_seeds):
            es = CONTROL_EVAL_SEED + 19 * i
            rng = np.random.default_rng(es)
            rnd.append(float(run_episodes(spec, act_fn=lambda o, r=rng: random_cartpole(o, r), episodes=eval_episodes, seed=es)["mean_return"]))
            heu.append(float(run_episodes(spec, act_fn=heuristic_cartpole, episodes=eval_episodes, seed=es)["mean_return"]))

        test_mae = {"ridge": one_step_errors(ridge, test)["mae"], "residual": one_step_errors(residual, test)["mae"]}
        multi = {
            "ridge": multi_step_errors(ridge, test, HORIZONS),
            "residual": multi_step_errors(residual, test, HORIZONS),
        }
        per_seed.append(
            {
                "model_seed": mseed,
                "collect_seed": COLLECT_TRAIN_SEED + 17 * mseed,
                "init_seed": 3 + 11 * mseed,
                "test_mae": test_mae,
                "multi_step": multi,
                "term": term_table,
                "temps": temps,
                "control": {k: float(np.mean(v["returns"])) for k, v in control.items()},
                "control_per_eval": {k: v["returns"] for k, v in control.items()},
                "greedy": {"ridge": float(np.mean(g_rets_r)), "residual": float(np.mean(g_rets_d))},
                "greedy_per_eval": {"ridge": g_rets_r, "residual": g_rets_d},
                "random": float(np.mean(rnd)),
                "heuristic": float(np.mean(heu)),
                "exploit": exploit,
                "learning_env_steps": train.env_interactions + val.env_interactions,
                "test_collect_env_steps": test.env_interactions,
            }
        )
        print(f"v072 seed={mseed} ridge_mae={test_mae['ridge']:.5f} residual_mae={test_mae['residual']:.5f}", flush=True)

    def _ctrl(key: str) -> list[float]:
        return [float(p["control"][key]) for p in per_seed if key in p["control"]]

    # Summaries for the isolation keys.
    iso_keys = [k for k in per_seed[0]["control"] if "|h6|" in k]
    horizon_keys = [k for k in per_seed[0]["control"] if k.split("|")[0] in {"ridge", "residual", "ensemble"}]
    paired_iso: dict[int, dict[str, dict[str, float]]] = {}
    for p in per_seed:
        paired_iso[int(p["model_seed"])] = {
            "src": {
                "ridge_learned": p["control"].get("ridge|learned|h6|p0.0|c8", float("nan")),
                "ridge_live": p["control"].get("ridge|always_live|h6|p0.0|c8", float("nan")),
                "ridge_cal": p["control"].get("ridge|calibrated|h6|p0.0|c8", float("nan")),
                "ridge_geo": p["control"].get("ridge|geometric|h6|p0.0|c8", float("nan")),
                "res_learned": p["control"].get("residual|learned|h6|p0.0|c8", float("nan")),
                "res_live": p["control"].get("residual|always_live|h6|p0.0|c8", float("nan")),
                "ridge_greedy": p["greedy"]["ridge"],
                "res_greedy": p["greedy"]["residual"],
            }
        }

    def _horizon_means(model: str, mode: str) -> dict[str, Any]:
        out = {}
        for h in HORIZONS:
            nc = _n_cand(h)
            key = f"{model}|{mode}|h{h}|p0.0|c{nc}"
            if model == "ensemble" and mode == "always_live":
                key = f"ensemble|always_live|h{h}|p0.0|c{nc}"
            xs = _ctrl(key)
            out[str(h)] = {"returns": seed_level_ci(xs), "n_cand": nc, "evals_per_decision": nc * h}
        return out

    payload = {
        "protocol": {
            "code_version": "v0.7.2",
            "parent_commit": "b8d4bb0",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "persistent_rng": True,
            "episode_reset": True,
            "objective": "predicted_reward + theta ranking (matched to one_step_greedy)",
            "plan_eval_budget": PLAN_BUDGET,
            "horizons": list(HORIZONS),
            "n_model_seeds": n_model_seeds,
            "selection": "temperature on val Brier only; no test/control tuning",
            "geometric_oracle": "threshold on predicted state; not used as learned planner",
            "planner_uses_simulator": False,
            "is_agi": False,
        },
        "prediction": {
            "ridge_mae": seed_level_ci([p["test_mae"]["ridge"] for p in per_seed]),
            "residual_mae": seed_level_ci([p["test_mae"]["residual"] for p in per_seed]),
        },
        "termination_h6": {
            "ridge_learned": seed_level_ci(_ctrl("ridge|learned|h6|p0.0|c8")),
            "ridge_always_live": seed_level_ci(_ctrl("ridge|always_live|h6|p0.0|c8")),
            "ridge_calibrated": seed_level_ci(_ctrl("ridge|calibrated|h6|p0.0|c8")),
            "ridge_geometric": seed_level_ci(_ctrl("ridge|geometric|h6|p0.0|c8")),
            "residual_learned": seed_level_ci(_ctrl("residual|learned|h6|p0.0|c8")),
            "residual_always_live": seed_level_ci(_ctrl("residual|always_live|h6|p0.0|c8")),
            "residual_calibrated": seed_level_ci(_ctrl("residual|calibrated|h6|p0.0|c8")),
            "residual_geometric": seed_level_ci(_ctrl("residual|geometric|h6|p0.0|c8")),
        },
        "paired_termination": {
            "ridge_live_minus_learned": paired_seed_deltas(per_seed_task=paired_iso, treatment="ridge_live", baseline="ridge_learned"),
            "ridge_live_minus_greedy": paired_seed_deltas(per_seed_task=paired_iso, treatment="ridge_live", baseline="ridge_greedy"),
            "ridge_learned_minus_greedy": paired_seed_deltas(per_seed_task=paired_iso, treatment="ridge_learned", baseline="ridge_greedy"),
            "res_live_minus_learned": paired_seed_deltas(per_seed_task=paired_iso, treatment="res_live", baseline="res_learned"),
            "res_h6_minus_greedy": paired_seed_deltas(per_seed_task=paired_iso, treatment="res_learned", baseline="res_greedy"),
        },
        "greedy": {
            "ridge": seed_level_ci([p["greedy"]["ridge"] for p in per_seed]),
            "residual": seed_level_ci([p["greedy"]["residual"] for p in per_seed]),
            "random": seed_level_ci([p["random"] for p in per_seed]),
            "heuristic": seed_level_ci([p["heuristic"] for p in per_seed]),
        },
        "horizons": {
            "ridge_learned": _horizon_means("ridge", "learned"),
            "ridge_always_live": _horizon_means("ridge", "always_live"),
            "residual_learned": _horizon_means("residual", "learned"),
            "residual_always_live": _horizon_means("residual", "always_live"),
            "ensemble_always_live": _horizon_means("ensemble", "always_live"),
        },
        "term_metrics_test": {
            "ridge": {mode: seed_level_ci([p["term"]["ridge"][mode]["brier"] for p in per_seed]) for mode in TERM_MODES},
            "ridge_recall": {mode: seed_level_ci([p["term"]["ridge"][mode]["recall"] for p in per_seed]) for mode in TERM_MODES},
            "residual": {mode: seed_level_ci([p["term"]["residual"][mode]["brier"] for p in per_seed]) for mode in TERM_MODES},
        },
        "uncertainty": {
            "ens_zero_h6": seed_level_ci(_ctrl(f"ensemble|always_live|h6|p0.0|c{_n_cand(6)}")),
            "ens_pen_h6": seed_level_ci(_ctrl(f"ensemble|always_live|h6|p2.0|c{_n_cand(6)}")),
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.7.2 planning reliability. Geometric terminate is diagnostic. Not AGI.",
    }
    # uncertainty paired
    unc_map: dict[int, dict[str, dict[str, float]]] = {}
    zkey = f"ensemble|always_live|h6|p0.0|c{_n_cand(6)}"
    pkey = f"ensemble|always_live|h6|p2.0|c{_n_cand(6)}"
    for p in per_seed:
        unc_map[int(p["model_seed"])] = {"src": {"zero": p["control"].get(zkey, float("nan")), "pen": p["control"].get(pkey, float("nan"))}}
    payload["uncertainty"]["pen_minus_zero"] = paired_seed_deltas(per_seed_task=unc_map, treatment="pen", baseline="zero")
    payload["costs"] = {
        "mean_learning_env_steps": float(np.mean([p["learning_env_steps"] for p in per_seed])),
        "plan_eval_budget": PLAN_BUDGET,
        "n_model_seeds": n_model_seeds,
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    del iso_keys, horizon_keys
    return payload
