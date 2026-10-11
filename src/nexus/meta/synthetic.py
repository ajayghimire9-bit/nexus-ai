from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from nexus.meta.controller import FrozenLinUCBController, LinUCBController


def _ci95(xs: np.ndarray) -> tuple[float, float, float]:
    mean = float(xs.mean())
    if len(xs) < 2:
        return mean, mean, mean
    std = float(xs.std(ddof=1))
    half = 1.96 * std / math.sqrt(len(xs))
    return mean, mean - half, mean + half


class LinearBanditEnv:
    """Known-optimal linear contextual bandit. Reward[a] = x · theta[a] + noise."""

    def __init__(self, n_arms: int, dim: int, seed: int) -> None:
        rng = np.random.default_rng(seed)
        self.n_arms = n_arms
        self.dim = dim
        self.theta = rng.normal(size=(n_arms, dim))
        # Make arm 0 uniquely best on the first half-space of x[0].
        self.theta[0] *= 0.1
        self.theta[0, 0] = 3.0
        self.theta[1:, 0] = -1.0
        self.rng = rng

    def context(self, shift: float = 0.0, scale: float = 1.0) -> np.ndarray:
        x = self.rng.uniform(-1.0, 1.0, size=self.dim) * scale
        x[0] = x[0] + shift
        return x

    def reward(self, x: np.ndarray, arm: int, noise_std: float = 0.1) -> float:
        return float(x @ self.theta[arm] + self.rng.normal() * noise_std)

    def optimal_arm(self, x: np.ndarray) -> int:
        return int(np.argmax(self.theta @ x))


def _select(name: str, ctrl: Any, x: np.ndarray, rng: np.random.Generator, epsilon: float) -> int:
    if name == "random":
        return int(rng.integers(0, ctrl.n_arms))
    if name == "epsilon_greedy":
        if rng.random() < epsilon:
            return int(rng.integers(0, ctrl.n_arms))
        scores = ctrl._ucb(x)
        return int(np.argmax(scores))
    scores = ctrl._ucb(x)
    return int(np.argmax(scores))


def run_synthetic_bandit(
    *,
    n_seeds: int = 20,
    horizon: int = 200,
    n_arms: int = 4,
    dim: int = 8,
    epsilon: float = 0.1,
    alpha: float = 0.5,
    noise_std: float = 0.1,
    artifact_path: str | Path | None = "artifacts/v051_synthetic_bandit.json",
) -> dict[str, Any]:
    """LinUCB vs frozen/random/ε-greedy on a bandit with a known optimal policy."""
    names = ("random", "epsilon_greedy", "linucb", "linucb_frozen")
    per_seed: list[dict[str, Any]] = []
    for seed in range(n_seeds):
        env = LinearBanditEnv(n_arms, dim, seed=10_000 + seed)
        ctrls: dict[str, Any] = {
            "random": LinUCBController(alpha=alpha, n_arms=n_arms),
            "epsilon_greedy": LinUCBController(alpha=alpha, n_arms=n_arms),
            "linucb": LinUCBController(alpha=alpha, n_arms=n_arms),
            "linucb_frozen": FrozenLinUCBController(alpha=alpha, n_arms=n_arms),
        }
        rngs = {n: np.random.default_rng(50_000 + seed * 17 + i) for i, n in enumerate(names)}
        rows: dict[str, dict[str, Any]] = {}
        for name in names:
            ctrl = ctrls[name]
            regrets = np.zeros(horizon)
            opt_hits = np.zeros(horizon)
            freq = np.zeros(n_arms)
            cum = 0.0
            for t in range(horizon):
                x = env.context()
                opt = env.optimal_arm(x)
                arm = _select(name, ctrl, x, rngs[name], epsilon)
                r = env.reward(x, arm, noise_std=noise_std)
                r_opt = float(x @ env.theta[opt])
                inst = r_opt - float(x @ env.theta[arm])
                cum += inst
                regrets[t] = cum
                opt_hits[t] = float(arm == opt)
                freq[arm] += 1
                if name in {"linucb", "epsilon_greedy"}:
                    ctrl.A[arm] += np.outer(x, x)
                    ctrl.b[arm] += r * x
            rows[name] = {
                "final_regret": float(regrets[-1]),
                "last50_opt_rate": float(opt_hits[-50:].mean()),
                "opt_curve": opt_hits.tolist(),
                "regret_curve": regrets.tolist(),
                "action_freq": (freq / horizon).tolist(),
            }
        per_seed.append({"seed": seed, "methods": rows})

    summary = []
    for name in names:
        regret = np.asarray([p["methods"][name]["final_regret"] for p in per_seed], dtype=np.float64)
        opt50 = np.asarray([p["methods"][name]["last50_opt_rate"] for p in per_seed], dtype=np.float64)
        curves = np.asarray([p["methods"][name]["regret_curve"] for p in per_seed], dtype=np.float64)
        optc = np.asarray([p["methods"][name]["opt_curve"] for p in per_seed], dtype=np.float64)
        rm, rlo, rhi = _ci95(regret)
        om, olo, ohi = _ci95(opt50)
        mean_regret_t = curves.mean(axis=0)
        mean_opt_t = optc.mean(axis=0)
        freqs = np.asarray([p["methods"][name]["action_freq"] for p in per_seed], dtype=np.float64)
        summary.append(
            {
                "method": name,
                "n_seeds": n_seeds,
                "horizon": horizon,
                "mean_final_regret": rm,
                "ci95_final_regret": [rlo, rhi],
                "mean_last50_opt_rate": om,
                "ci95_last50_opt_rate": [olo, ohi],
                "mean_regret_curve": mean_regret_t.tolist(),
                "mean_opt_curve": mean_opt_t.tolist(),
                "mean_action_freq": freqs.mean(axis=0).tolist(),
            }
        )

    # Generalization: train LinUCB on train contexts, evaluate greedy accuracy on shifted contexts.
    gen_rows = []
    for seed in range(n_seeds):
        env = LinearBanditEnv(n_arms, dim, seed=20_000 + seed)
        ctrl = LinUCBController(alpha=alpha, n_arms=n_arms)
        frozen = FrozenLinUCBController(alpha=alpha, n_arms=n_arms)
        for _ in range(horizon):
            x = env.context()
            arm = int(np.argmax(ctrl._ucb(x)))
            r = env.reward(x, arm, noise_std=noise_std)
            ctrl.A[arm] += np.outer(x, x)
            ctrl.b[arm] += r * x
        n_eval = 200
        hits = {"linucb": 0, "linucb_frozen": 0, "random": 0}
        rng = np.random.default_rng(30_000 + seed)
        for _ in range(n_eval):
            x = env.context(shift=1.5, scale=1.2)
            opt = env.optimal_arm(x)
            hits["linucb"] += int(int(np.argmax(ctrl._ucb(x))) == opt)
            hits["linucb_frozen"] += int(int(np.argmax(frozen._ucb(x))) == opt)
            hits["random"] += int(int(rng.integers(0, n_arms)) == opt)
        gen_rows.append({k: v / n_eval for k, v in hits.items()})
    gen_summary = {
        k: {
            "mean": float(np.mean([g[k] for g in gen_rows])),
            "ci95": list(_ci95(np.asarray([g[k] for g in gen_rows], dtype=np.float64))[1:]),
        }
        for k in ("linucb", "linucb_frozen", "random")
    }

    payload = {
        "task": "synthetic_linear_contextual_bandit",
        "n_seeds": n_seeds,
        "horizon": horizon,
        "n_arms": n_arms,
        "dim": dim,
        "summary": summary,
        "generalization_shifted_context": gen_summary,
        "per_seed": [{"seed": p["seed"], "final_regret": {m: p["methods"][m]["final_regret"] for m in names}, "last50_opt_rate": {m: p["methods"][m]["last50_opt_rate"] for m in names}} for p in per_seed],
        "is_meta_rl": False,
        "caveat": "Synthetic bandit with known optimal arm. Success here does not imply PPO meta-controller improvement.",
    }
    if artifact_path is not None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
    return payload
