"""V0.8 adaptive world models. Inference never reads the simulator or privileged physics."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np
import torch
from torch import nn

from nexus.cl.metrics import paired_seed_deltas, seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v08_confirmation_targets,
    v08_development_target,
    v08_sequence_tasks,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec, make_task_env
from nexus.world.baselines import heuristic_cartpole, run_episodes
from nexus.world.data import (
    TransitionDataset,
    assert_disjoint_seeds,
    collect_transitions,
    concat_datasets,
    split_by_episodes,
)
from nexus.world.dynamics import WorldModel
from nexus.world.ensemble import train_ensemble
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL, FROZEN_OBJECTIVE, FROZEN_PRIMARY_HORIZON
from nexus.world.imagine import multi_step_errors
from nexus.world.memory import PredictiveMemory, checkpoint_nbytes, probe_mae
from nexus.world.planning import InferenceCounter, RandomShootingMPC
from nexus.world.protocol import (
    V08_CONFIRM_EVAL_SEED,
    V08_DETECT_COLLECT_SEED,
    V08_DEV_EVAL_SEED,
    V08_EXPLORE_COLLECT_SEED,
    V08_SEQUENCE_EVAL_SEED,
    V08_SOURCE_COLLECT_SEED,
    V08_TARGET_COLLECT_SEED,
)
from nexus.world.train import one_step_errors, train_world_model
from nexus.world.v072 import _eval_mpc

MethodName = Literal["frozen", "finetune", "scratch", "replay", "adapter"]
METHODS: tuple[MethodName, ...] = ("frozen", "finetune", "scratch", "replay", "adapter")


def _stable_int(text: str, mod: int) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % int(mod)


def per_transition_mae(model: Any, obs: np.ndarray, action: np.ndarray, next_obs: np.ndarray) -> np.ndarray:
    pred, _ = model.step(obs, action)
    return np.mean(np.abs(pred - next_obs), axis=-1)


class ResidualChangeDetector:
    """Page–Hinkley + windowed z-score on one-step MAE. No physics parameters."""

    def __init__(self, *, window: int = 32, z_thresh: float = 3.0, ph_delta_scale: float = 0.5, ph_lambda_scale: float = 4.0) -> None:
        self.window = int(window)
        self.z_thresh = float(z_thresh)
        self.ph_delta_scale = float(ph_delta_scale)
        self.ph_lambda_scale = float(ph_lambda_scale)
        self.source_mean = 0.0
        self.source_std = 1.0
        self._ph = 0.0
        self._ph_min = 0.0
        self._buf: list[float] = []
        self.fitted = False
        self.uses_privileged_physics = False

    def fit(self, errors: np.ndarray) -> None:
        arr = np.asarray(errors, dtype=np.float64).reshape(-1)
        self.source_mean = float(arr.mean()) if arr.size else 0.0
        self.source_std = float(arr.std(ddof=1)) if arr.size > 1 else 1e-6
        self.source_std = max(self.source_std, 1e-8)
        self._ph = 0.0
        self._ph_min = 0.0
        self._buf = []
        self.fitted = True

    def update(self, error: float) -> dict[str, Any]:
        x = float(error)
        self._buf.append(x)
        if len(self._buf) > 4096:
            self._buf = self._buf[-2048:]
        delta = self.ph_delta_scale * self.source_std
        lam = self.ph_lambda_scale * self.source_std
        self._ph += x - self.source_mean - delta
        self._ph_min = min(self._ph_min, self._ph)
        ph_stat = self._ph - self._ph_min
        ph_alarm = bool(ph_stat > lam)
        w = self._buf[-self.window :]
        z = 0.0
        z_alarm = False
        if len(w) >= self.window:
            se = self.source_std / np.sqrt(len(w))
            z = float((float(np.mean(w)) - self.source_mean) / max(se, 1e-12))
            z_alarm = bool(z > self.z_thresh)
        return {
            "error": x,
            "ph_stat": float(ph_stat),
            "ph_alarm": ph_alarm,
            "z": z,
            "z_alarm": z_alarm,
            "alarm": bool(ph_alarm or z_alarm),
            "uses_privileged_physics": False,
        }

    def scan(self, errors: np.ndarray) -> dict[str, Any]:
        self._ph = 0.0
        self._ph_min = 0.0
        self._buf = []
        flags = [self.update(float(e)) for e in np.asarray(errors, dtype=np.float64).reshape(-1)]
        first = next((i for i, r in enumerate(flags) if r["alarm"]), None)
        return {
            "n": len(flags),
            "n_alarm": int(sum(1 for r in flags if r["alarm"])),
            "first_alarm": first,
            "ph_alarm_frac": float(np.mean([r["ph_alarm"] for r in flags])) if flags else 0.0,
            "z_alarm_frac": float(np.mean([r["z_alarm"] for r in flags])) if flags else 0.0,
            "uses_privileged_physics": False,
        }


class WindowThresholdDetector:
    """Alarm if rolling mean MAE exceeds source_mean + k * source_std. Residuals only."""

    def __init__(self, *, window: int = 32, k: float = 3.0) -> None:
        self.window = int(window)
        self.k = float(k)
        self.source_mean = 0.0
        self.source_std = 1.0
        self.threshold = 1.0
        self._buf: list[float] = []
        self.uses_privileged_physics = False

    def fit(self, errors: np.ndarray) -> None:
        arr = np.asarray(errors, dtype=np.float64).reshape(-1)
        self.source_mean = float(arr.mean()) if arr.size else 0.0
        self.source_std = max(float(arr.std(ddof=1)) if arr.size > 1 else 1e-6, 1e-8)
        self.threshold = self.source_mean + self.k * self.source_std
        self._buf = []

    def update(self, error: float) -> dict[str, Any]:
        self._buf.append(float(error))
        w = self._buf[-self.window :]
        mean = float(np.mean(w))
        alarm = bool(len(w) >= self.window and mean > self.threshold)
        return {
            "error": float(error),
            "window_mean": mean,
            "threshold": self.threshold,
            "alarm": alarm,
            "uses_privileged_physics": False,
        }

    def scan(self, errors: np.ndarray) -> dict[str, Any]:
        self._buf = []
        flags = [self.update(float(e)) for e in np.asarray(errors, dtype=np.float64).reshape(-1)]
        first = next((i for i, r in enumerate(flags) if r["alarm"]), None)
        return {
            "n": len(flags),
            "n_alarm": int(sum(1 for r in flags if r["alarm"])),
            "first_alarm": first,
            "alarm_frac": float(np.mean([r["alarm"] for r in flags])) if flags else 0.0,
            "detection_delay": first,
            "missed": first is None,
            "uses_privileged_physics": False,
        }


class AdditiveAdapter(nn.Module):
    """Target-specific residual in normalized next-state. Source trunk is frozen."""

    def __init__(self, obs_dim: int, n_actions: int, hidden: int = 32) -> None:
        super().__init__()
        self.n_actions = n_actions
        self.net = nn.Sequential(nn.Linear(obs_dim + n_actions, hidden), nn.Tanh(), nn.Linear(hidden, obs_dim))
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self, obs_norm: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        oh = torch.nn.functional.one_hot(action.long(), num_classes=self.n_actions).float()
        return self.net(torch.cat([obs_norm, oh], dim=-1))


@dataclass
class AdaptedWorldModel:
    base: WorldModel
    adapter: AdditiveAdapter
    uses_simulator: bool = False
    uses_privileged_physics: bool = False

    @property
    def kind(self) -> str:
        return self.base.kind

    @property
    def net(self) -> nn.Module:
        return self.base.net

    @property
    def obs_rms(self) -> Any:
        return self.base.obs_rms

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        o = np.asarray(obs, dtype=np.float32).reshape(-1, self.base.net.obs_dim)
        a = np.asarray(action, dtype=np.int64).reshape(-1)
        if a.size == 1 and o.shape[0] > 1:
            a = np.full(o.shape[0], int(a.flat[0]), dtype=np.int64)
        self.base.net.eval()
        self.adapter.eval()
        with torch.no_grad():
            obs_n = torch.as_tensor(self.base.normalize(o))
            act_t = torch.as_tensor(a)
            pred, logit = self.base.net(obs_n, act_t)
            next_n = obs_n + pred if self.base.kind == "residual" else pred
            next_n = next_n + self.adapter(obs_n, act_t)
            p = torch.sigmoid(logit)
        nxt = self.base.unnormalize(next_n.cpu().numpy()).reshape(o.shape)
        return nxt, p.cpu().numpy().reshape(-1)


def collect_with_actor(
    spec: TaskSpec,
    *,
    n_transitions: int,
    env_seeds: tuple[int, ...] | list[int],
    base_seed: int,
    actor: Callable[[np.ndarray], int],
    policy_name: str = "custom",
    on_episode_start: Callable[[int], None] | None = None,
) -> TransitionDataset:
    obs_l: list[np.ndarray] = []
    act_l: list[int] = []
    next_l: list[np.ndarray] = []
    rew_l: list[float] = []
    term_l: list[bool] = []
    trunc_l: list[bool] = []
    seed_l: list[int] = []
    ep_l: list[int] = []
    pol_l: list[str] = []
    interactions = 0
    episode_id = 0
    seed_i = 0
    while interactions < n_transitions:
        env_seed = int(env_seeds[seed_i % len(env_seeds)]) + 1000 * (episode_id // max(len(env_seeds), 1))
        seed_i += 1
        env = make_task_env(spec, seed=env_seed)
        if on_episode_start is not None:
            on_episode_start(episode_id)
        obs, _ = env.reset(seed=env_seed)
        done = False
        while not done and interactions < n_transitions:
            o = np.asarray(obs, dtype=np.float32).reshape(-1)
            a = int(actor(o))
            nxt, rew, terminated, truncated, _ = env.step(a)
            obs_l.append(o)
            act_l.append(a)
            next_l.append(np.asarray(nxt, dtype=np.float32).reshape(-1))
            rew_l.append(float(rew))
            term_l.append(bool(terminated))
            trunc_l.append(bool(truncated))
            seed_l.append(int(env_seed))
            ep_l.append(int(episode_id))
            pol_l.append(policy_name)
            interactions += 1
            done = bool(terminated or truncated)
            obs = nxt
        env.close()
        episode_id += 1
    return TransitionDataset(
        obs=np.stack(obs_l, axis=0),
        action=np.asarray(act_l, dtype=np.int64),
        next_obs=np.stack(next_l, axis=0),
        reward=np.asarray(rew_l, dtype=np.float32),
        terminated=np.asarray(term_l, dtype=np.bool_),
        truncated=np.asarray(trunc_l, dtype=np.bool_),
        task_id=spec.task_id,
        seed=np.asarray(seed_l, dtype=np.int64),
        episode_id=np.asarray(ep_l, dtype=np.int64),
        policy=np.asarray(pol_l),
        physics=dict(spec.params),
        env_interactions=interactions,
        notes={"n_episodes": episode_id, "policy": policy_name, "base_seed": base_seed},
    )


def split_train_val(ds: TransitionDataset, *, rng: np.random.Generator, val_frac: float = 0.25) -> tuple[TransitionDataset, TransitionDataset]:
    """Transition-shuffled split used by V0.8. Prefer ``split_by_episodes`` for new work."""
    n = len(ds)
    if n < 8:
        return ds, ds
    n_val = max(4, int(round(n * val_frac)))
    n_val = min(n_val, n - 4) if n > 8 else max(1, n // 4)
    idx = rng.permutation(n)
    return ds.slice(idx[n_val:]), ds.slice(idx[:n_val])


def split_train_val_episodes(ds: TransitionDataset, *, rng: np.random.Generator, val_frac: float = 0.25) -> tuple[TransitionDataset, TransitionDataset]:
    return split_by_episodes(ds, val_frac=val_frac, rng=rng)


def finetune_world_model(wm: WorldModel, train: TransitionDataset, val: TransitionDataset, *, epochs: int, seed: int, lr: float = 5e-4) -> tuple[WorldModel, dict[str, Any]]:
    if len(val) == 0:
        val = train
    out = wm.clone()
    rng = np.random.default_rng(seed)
    opt = torch.optim.Adam(out.net.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    bce = nn.BCEWithLogitsLoss()
    best = 1e18
    best_state = {k: v.detach().cpu().clone() for k, v in out.net.state_dict().items()}
    history: list[float] = []
    for _epoch in range(int(epochs)):
        out.net.train()
        idx = rng.permutation(len(train))
        for i in range(0, len(train), 64):
            sl = idx[i : i + 64]
            obs = torch.as_tensor(out.normalize(train.obs[sl]))
            nxt = torch.as_tensor(out.normalize(train.next_obs[sl]))
            act = torch.as_tensor(train.action[sl], dtype=torch.int64)
            term = torch.as_tensor(train.terminated[sl].astype(np.float32))
            pred, logit = out.net(obs, act)
            target = nxt - obs if out.kind == "residual" else nxt
            loss = loss_fn(pred, target) + 0.25 * bce(logit, term)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(out.net.parameters(), 1.0)
            opt.step()
        out.net.eval()
        with torch.no_grad():
            obs = torch.as_tensor(out.normalize(val.obs))
            nxt = torch.as_tensor(out.normalize(val.next_obs))
            act = torch.as_tensor(val.action, dtype=torch.int64)
            pred, logit = out.net(obs, act)
            target = nxt - obs if out.kind == "residual" else nxt
            v = float(loss_fn(pred, target).item())
        history.append(v)
        if v < best:
            best = v
            best_state = {k: t.detach().cpu().clone() for k, t in out.net.state_dict().items()}
    out.net.load_state_dict(best_state)
    out.net.eval()
    return out, {"best_val": best, "history": history}


def train_adapter(base: WorldModel, train: TransitionDataset, val: TransitionDataset, *, epochs: int, seed: int) -> tuple[AdaptedWorldModel, dict[str, Any]]:
    adapter = AdditiveAdapter(base.net.obs_dim, base.net.n_actions)
    opt = torch.optim.Adam(adapter.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    rng = np.random.default_rng(seed)
    best = 1e18
    best_state = {k: v.detach().cpu().clone() for k, v in adapter.state_dict().items()}
    base.net.eval()
    for p in base.net.parameters():
        p.requires_grad_(False)
    for _epoch in range(int(epochs)):
        adapter.train()
        idx = rng.permutation(len(train))
        for i in range(0, len(train), 64):
            sl = idx[i : i + 64]
            obs_n = torch.as_tensor(base.normalize(train.obs[sl]))
            nxt_n = torch.as_tensor(base.normalize(train.next_obs[sl]))
            act = torch.as_tensor(train.action[sl], dtype=torch.int64)
            with torch.no_grad():
                pred, _logit = base.net(obs_n, act)
                next_base = obs_n + pred if base.kind == "residual" else pred
            pred_n = next_base + adapter(obs_n, act)
            loss = loss_fn(pred_n, nxt_n)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        adapter.eval()
        with torch.no_grad():
            obs_n = torch.as_tensor(base.normalize(val.obs))
            nxt_n = torch.as_tensor(base.normalize(val.next_obs))
            act = torch.as_tensor(val.action, dtype=torch.int64)
            pred, _ = base.net(obs_n, act)
            next_base = obs_n + pred if base.kind == "residual" else pred
            v = float(loss_fn(next_base + adapter(obs_n, act), nxt_n).item())
        if v < best:
            best = v
            best_state = {k: t.detach().cpu().clone() for k, t in adapter.state_dict().items()}
    adapter.load_state_dict(best_state)
    adapter.eval()
    return AdaptedWorldModel(base=base, adapter=adapter), {"best_val": best}


def plan_h3(spec: TaskSpec, model: Any, *, seed: int, episodes: int) -> dict[str, Any]:
    inf = InferenceCounter(model)
    planner = RandomShootingMPC(
        model=model,
        n_actions=2,
        horizon=FROZEN_PRIMARY_HORIZON,
        n_candidates=FROZEN_CANDIDATES[FROZEN_PRIMARY_HORIZON],
        seed=0,
        inference=inf,
        objective=FROZEN_OBJECTIVE,  # type: ignore[arg-type]
    )
    row = _eval_mpc(spec, planner, episodes=episodes, seed=seed)
    h_row = run_episodes(spec, act_fn=heuristic_cartpole, episodes=episodes, seed=seed)
    rets = [float(x) for x in row.get("returns", [])]
    fail_rate = float(np.mean([r < 500.0 for r in rets])) if rets else None
    onpol = None
    tr = row.get("transitions")
    if tr is not None and len(tr["obs"]):
        pred, _ = model.step(tr["obs"], tr["action"])
        onpol = float(np.mean(np.abs(pred - tr["next_obs"])))
    return {
        "mean_return": float(row["mean_return"]),
        "returns": rets,
        "fail_rate": fail_rate,
        "on_policy_mae": onpol,
        "env_interactions": int(row["env_interactions"]),
        "model_states": int(inf.states),
        "heuristic_return": float(h_row["mean_return"]),
        "heuristic_env_interactions": int(h_row["env_interactions"]),
        "used_simulator": False,
        "used_privileged_physics": False,
    }


def _metrics(model: Any, ds: TransitionDataset) -> dict[str, Any]:
    one = one_step_errors(model, ds)
    multi = multi_step_errors(model, ds, (1, 3, 8))
    return {"one_step": one, "multi_step": multi}


def adapt_method(
    method: MethodName,
    source: WorldModel,
    source_replay: TransitionDataset,
    target: TransitionDataset,
    *,
    epochs: int,
    seed: int,
    episode_disjoint: bool = False,
) -> tuple[Any, dict[str, Any]]:
    if method == "frozen" or len(target) == 0:
        return source, {"method": "frozen", "train_n": 0, "val_n": 0}
    rng = np.random.default_rng(seed)
    tr, va = split_train_val_episodes(target, rng=rng) if episode_disjoint else split_train_val(target, rng=rng)
    if len(va) == 0:
        va = tr
    if method == "finetune":
        wm, log = finetune_world_model(source, tr, va, epochs=epochs, seed=seed)
        return wm, {"method": method, "train_n": len(tr), "val_n": len(va), **log}
    if method == "scratch":
        wm, log = train_world_model(tr, va, kind=FROZEN_KIND, epochs=epochs, seed=seed, hidden=(64, 64))  # type: ignore[arg-type]
        return wm, {"method": method, "train_n": len(tr), "val_n": len(va), **log}
    if method == "replay":
        n_src = min(len(source_replay), len(tr))
        src_idx = rng.choice(len(source_replay), size=n_src, replace=False) if n_src else np.zeros(0, dtype=np.int64)
        mix = concat_datasets(source_replay.slice(src_idx), tr, task_id="replay_mix") if n_src else tr
        wm, log = finetune_world_model(source, mix, va, epochs=epochs, seed=seed)
        return wm, {"method": method, "train_n": len(mix), "val_n": len(va), "source_replay_n": int(n_src), **log}
    adapted, log = train_adapter(source, tr, va, epochs=epochs, seed=seed)
    return adapted, {"method": method, "train_n": len(tr), "val_n": len(va), **log}


def uncertainty_actor(members: list[WorldModel], rng: np.random.Generator, *, epsilon: float = 0.1) -> Callable[[np.ndarray], int]:
    def act(obs: np.ndarray) -> int:
        if rng.random() < epsilon:
            return int(rng.integers(0, 2))
        o = np.asarray(obs, dtype=np.float32).reshape(-1)
        best_a, best_d = 0, -1.0
        for a in range(2):
            preds = [m.step(o, a)[0].reshape(-1) for m in members]
            d = float(np.std(np.stack(preds, axis=0), axis=0).mean())
            if d > best_d:
                best_d, best_a = d, a
        return int(best_a)

    return act


def run_v08_benchmark(
    *,
    n_model_seeds: int = 5,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    adapt_epochs: int = 12,
    budgets: tuple[int, ...] = (0, 64, 128, 256, 512),
    eval_episodes: int = 1,
    detect_n: int = 128,
    probe_n: int = 32,
    artifact_path: str | Path | None = "artifacts/v08_adaptation.json",
    checkpoint_dir: str | Path = "checkpoints/v08",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    if quick:
        n_train, n_val, epochs, adapt_epochs = 64, 32, 1, 1
        budgets = (0, 32)
        detect_n, probe_n, eval_episodes = 32, 16, 1
        n_model_seeds = min(n_model_seeds, 1)
    source_spec = source_policy_task()
    seq_a, seq_b, seq_c = v08_sequence_tasks()
    dev = v08_development_target()
    confirms = v08_confirmation_targets()
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    per_seed: list[dict[str, Any]] = []

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source_spec,
            n_transitions=n_train,
            env_seeds=tuple(range(20 + 30 * mseed, 40 + 30 * mseed)),
            base_seed=V08_SOURCE_COLLECT_SEED + 29 * mseed,
            mix=("random", "exploratory"),
        )
        val = collect_transitions(
            source_spec,
            n_transitions=n_val,
            env_seeds=tuple(range(400 + 10 * mseed, 408 + 10 * mseed)),
            base_seed=V08_SOURCE_COLLECT_SEED + 1000 + 29 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        source, slog = train_world_model(train, val, kind=FROZEN_KIND, epochs=epochs, seed=7 + 13 * mseed)  # type: ignore[arg-type]
        src_mae = per_transition_mae(source, val.obs, val.action, val.next_obs)
        detector = ResidualChangeDetector()
        detector.fit(src_mae)

        def _detect_stream(spec: TaskSpec, extra: int) -> dict[str, Any]:
            ds = collect_transitions(
                spec,
                n_transitions=detect_n,
                env_seeds=tuple(range(800 + extra + 5 * mseed, 808 + extra + 5 * mseed)),
                base_seed=V08_DETECT_COLLECT_SEED + extra + 17 * mseed,
                mix=("random", "exploratory"),
            )
            err = per_transition_mae(source, ds.obs, ds.action, ds.next_obs)
            scan = detector.scan(err)
            scan["mean_mae"] = float(err.mean())
            scan["task_id"] = spec.task_id
            scan["env_interactions"] = ds.env_interactions
            scan["physics_in_detector"] = False
            return scan

        detection = {
            "source_holdout": _detect_stream(source_spec, 0),
            "seq_b": _detect_stream(seq_b, 50),
            "seq_c": _detect_stream(seq_c, 90),
            "dev": _detect_stream(dev, 130),
        }

        def _collect_target(spec: TaskSpec, n: int, tag: int) -> TransitionDataset:
            if n <= 0:
                return collect_transitions(spec, n_transitions=1, env_seeds=(1,), base_seed=1).slice(np.zeros(0, dtype=np.int64))
            return collect_transitions(
                spec,
                n_transitions=n,
                env_seeds=tuple(range(50 + tag + 8 * mseed, 58 + tag + 8 * mseed)),
                base_seed=V08_TARGET_COLLECT_SEED + tag + 41 * mseed,
                mix=("random", "exploratory"),
            )

        # Matched-budget adaptation on development task (selection split).
        max_b = max(budgets)
        dev_pool = _collect_target(dev, max_b, 200)
        dev_hold = collect_transitions(
            dev,
            n_transitions=max(64, n_val if not quick else 32),
            env_seeds=tuple(range(900 + 8 * mseed, 908 + 8 * mseed)),
            base_seed=V08_TARGET_COLLECT_SEED + 500 + 41 * mseed,
            mix=("random", "exploratory"),
        )
        rng_dev = np.random.default_rng(11 + mseed)
        order = rng_dev.permutation(len(dev_pool)) if len(dev_pool) else np.zeros(0, dtype=np.int64)
        dev_grid: dict[str, Any] = {}
        selected: dict[str, str] = {}
        for b in budgets:
            prefix = dev_pool.slice(order[:b]) if b and len(dev_pool) else dev_pool.slice(np.zeros(0, dtype=np.int64))
            by_m: dict[str, Any] = {}
            best_m, best_mae = "frozen", 1e18
            for method in METHODS:
                model, log = adapt_method(method, source, train, prefix, epochs=adapt_epochs, seed=21 + 3 * mseed)
                pred = _metrics(model, dev_hold)
                plan = plan_h3(dev, model, seed=V08_DEV_EVAL_SEED, episodes=eval_episodes)
                mae = float(pred["one_step"]["mae"])
                by_m[method] = {
                    "log": {k: v for k, v in log.items() if k != "history"},
                    "prediction": pred,
                    "planning": plan,
                    "target_interactions": int(prefix.env_interactions) if b else 0,
                    "checkpoint_nbytes": checkpoint_nbytes(source) if method != "adapter" else checkpoint_nbytes(source) + 4 * 32 * (4 + 2),
                }
                if mae < best_mae:
                    best_mae, best_m = mae, method
            selected[str(b)] = best_m
            dev_grid[str(b)] = {"methods": by_m, "selected_by_val_mae": best_m}

        # Confirmation: all methods, never used to retune. Independent eval seed.
        confirm_rows: dict[str, Any] = {}
        for spec in confirms:
            pool = _collect_target(spec, max_b, 300 + _stable_int(spec.task_id, 50))
            hold = collect_transitions(
                spec,
                n_transitions=max(64, n_val if not quick else 32),
                env_seeds=tuple(range(1100 + 9 * mseed, 1108 + 9 * mseed)),
                base_seed=V08_TARGET_COLLECT_SEED + 800 + 17 * mseed + _stable_int(spec.task_id, 13),
                mix=("random", "exploratory"),
            )
            rng_c = np.random.default_rng(33 + mseed + _stable_int(spec.task_id, 7))
            cord = rng_c.permutation(len(pool)) if len(pool) else np.zeros(0, dtype=np.int64)
            by_b: dict[str, Any] = {}
            for b in budgets:
                prefix = pool.slice(cord[:b]) if b and len(pool) else pool.slice(np.zeros(0, dtype=np.int64))
                by_m = {}
                for method in METHODS:
                    model, log = adapt_method(method, source, train, prefix, epochs=adapt_epochs, seed=51 + mseed)
                    by_m[method] = {
                        "log": {k: v for k, v in log.items() if k != "history"},
                        "prediction": _metrics(model, hold),
                        "planning": plan_h3(spec, model, seed=V08_CONFIRM_EVAL_SEED, episodes=eval_episodes),
                        "target_interactions": int(prefix.env_interactions) if b else 0,
                    }
                by_b[str(b)] = by_m
            confirm_rows[spec.task_id] = {"physics": dict(spec.params), "by_budget": by_b, "split": spec.train_split}

        # Continual A→B→C→A with budget 128 (or max available).
        seq_budget = 32 if quick else (128 if 128 in budgets else budgets[-1])
        memory = PredictiveMemory(max_entries=8, replay_cap=n_train + 2 * seq_budget)
        shared = source.clone()
        seq_specs = (seq_a, seq_b, seq_c, seq_a)
        seq_names = ("A", "B", "C", "A_return")
        seq_log: list[dict[str, Any]] = []
        forgetting: dict[str, Any] = {}
        hold_a = val
        hold_b = collect_transitions(
            seq_b,
            n_transitions=max(48, n_val if not quick else 24),
            env_seeds=tuple(range(1200 + 6 * mseed, 1206 + 6 * mseed)),
            base_seed=V08_SEQUENCE_EVAL_SEED + 11 * mseed,
            mix=("random", "exploratory"),
        )
        hold_c = collect_transitions(
            seq_c,
            n_transitions=max(48, n_val if not quick else 24),
            env_seeds=tuple(range(1250 + 6 * mseed, 1256 + 6 * mseed)),
            base_seed=V08_SEQUENCE_EVAL_SEED + 200 + 11 * mseed,
            mix=("random", "exploratory"),
        )
        holds = {"A": hold_a, "B": hold_b, "C": hold_c, "A_return": hold_a}
        for ti, (sp, name) in enumerate(zip(seq_specs, seq_names)):
            tgt = _collect_target(sp, seq_budget, 400 + 10 * ti)
            probe = tgt.slice(np.arange(min(probe_n, len(tgt)))) if len(tgt) else tgt
            retrieved, ret_meta = memory.retrieve(probe) if memory.entries else (None, {"n_candidates": 0, "used_task_id": False})
            naive, _nlog = adapt_method("finetune", shared, train, tgt, epochs=adapt_epochs, seed=70 + ti + mseed)
            from_src, _flog = adapt_method("finetune", source, train, tgt, epochs=adapt_epochs, seed=80 + ti + mseed)
            if retrieved is not None:
                from_mem, _mlog = adapt_method("finetune", retrieved, train, tgt, epochs=adapt_epochs, seed=90 + ti + mseed)
            else:
                from_mem, _mlog = source, {"method": "frozen"}
            shared = naive
            memory.store(naive, probe, stats={"stage": name}, replay=tgt, label=name)
            eval_sp = seq_a if name == "A_return" else sp
            hold = holds[name]
            seq_log.append(
                {
                    "stage": name,
                    "task_id": sp.task_id,
                    "target_interactions": tgt.env_interactions,
                    "retrieval": ret_meta,
                    "naive_shared": {
                        "prediction": _metrics(naive, hold),
                        "planning": plan_h3(eval_sp, naive, seed=V08_SEQUENCE_EVAL_SEED, episodes=eval_episodes),
                    },
                    "from_source": {
                        "prediction": _metrics(from_src, hold),
                        "planning": plan_h3(eval_sp, from_src, seed=V08_SEQUENCE_EVAL_SEED, episodes=eval_episodes),
                    },
                    "from_retrieved": {
                        "prediction": _metrics(from_mem, hold),
                        "planning": plan_h3(eval_sp, from_mem, seed=V08_SEQUENCE_EVAL_SEED, episodes=eval_episodes),
                    },
                    "memory_bytes": memory.bytes_used(),
                    "memory_entries": len(memory.entries),
                }
            )
            if name in ("B", "C", "A_return"):
                forgetting[name] = {
                    "mae_on_A": float(one_step_errors(naive, hold_a)["mae"]),
                    "snapshot_A_mae": float(one_step_errors(source, hold_a)["mae"]),
                    "retrieved_on_A": float(one_step_errors(retrieved, hold_a)["mae"]) if retrieved is not None else None,
                }

        # Exploration: matched 128 (or seq_budget) target steps, random vs disagreement.
        members, _elog = train_ensemble(train, val, n_members=3, kind=FROZEN_KIND, epochs=max(1, epochs // 2), seed=9 + mseed)
        n_ex = seq_budget
        rand_ds = collect_transitions(
            seq_b,
            n_transitions=n_ex,
            env_seeds=tuple(range(1300 + 6 * mseed, 1308 + 6 * mseed)),
            base_seed=V08_EXPLORE_COLLECT_SEED + 19 * mseed,
            mix=("random",),
        )
        rng_u = np.random.default_rng(V08_EXPLORE_COLLECT_SEED + 7 * mseed)
        unc_ds = collect_with_actor(
            seq_b,
            n_transitions=n_ex,
            env_seeds=tuple(range(1400 + 6 * mseed, 1408 + 6 * mseed)),
            base_seed=V08_EXPLORE_COLLECT_SEED + 100 + 19 * mseed,
            actor=uncertainty_actor(members, rng_u, epsilon=0.15),
            policy_name="uncertainty",
        )
        rand_m, _ = adapt_method("finetune", source, train, rand_ds, epochs=adapt_epochs, seed=101 + mseed)
        unc_m, _ = adapt_method("finetune", source, train, unc_ds, epochs=adapt_epochs, seed=101 + mseed)
        explore = {
            "n_target": n_ex,
            "random": {
                "env_interactions": rand_ds.env_interactions,
                "prediction": _metrics(rand_m, hold_b),
                "planning": plan_h3(seq_b, rand_m, seed=V08_SEQUENCE_EVAL_SEED + 3, episodes=eval_episodes),
            },
            "uncertainty": {
                "env_interactions": unc_ds.env_interactions,
                "prediction": _metrics(unc_m, hold_b),
                "planning": plan_h3(seq_b, unc_m, seed=V08_SEQUENCE_EVAL_SEED + 3, episodes=eval_episodes),
            },
            "matched_budget": rand_ds.env_interactions == unc_ds.env_interactions,
        }

        src_plan = plan_h3(source_spec, source, seed=V08_DEV_EVAL_SEED, episodes=eval_episodes)
        per_seed.append(
            {
                "model_seed": mseed,
                "source_val_loss": slog["best_val"],
                "source_one_step": one_step_errors(source, val),
                "source_planning": src_plan,
                "learning_env_steps": train.env_interactions + val.env_interactions,
                "source_checkpoint_nbytes": checkpoint_nbytes(source),
                "detection": detection,
                "dev_grid": dev_grid,
                "selected_by_budget": selected,
                "confirmation": confirm_rows,
                "continual": seq_log,
                "forgetting": forgetting,
                "explore": explore,
                "memory_retrieval_inferences": memory.retrieval_inferences,
                "memory_bytes": memory.bytes_used(),
            }
        )
        print(f"v08 seed={mseed} selected_128={selected.get('128', selected.get('32'))}", flush=True)

    def _confirm_mae(budget: int, method: str) -> list[float]:
        out = []
        for p in per_seed:
            xs = []
            for tid, row in p["confirmation"].items():
                xs.append(float(row["by_budget"][str(budget)][method]["prediction"]["one_step"]["mae"]))
            out.append(float(np.mean(xs)))
        return out

    def _confirm_ret(budget: int, method: str) -> list[float]:
        out = []
        for p in per_seed:
            xs = []
            for tid, row in p["confirmation"].items():
                xs.append(float(row["by_budget"][str(budget)][method]["planning"]["mean_return"]))
            out.append(float(np.mean(xs)))
        return out

    confirm_ids = [t.task_id for t in confirms]
    report_budgets = [b for b in budgets]
    confirm_summary: dict[str, Any] = {}
    for b in report_budgets:
        confirm_summary[str(b)] = {
            "mae": {m: seed_level_ci(_confirm_mae(b, m)) for m in METHODS},
            "plan_return": {m: seed_level_ci(_confirm_ret(b, m)) for m in METHODS},
        }

    paired_at: dict[str, Any] = {}
    for b in report_budgets:
        per_seed_task: dict[int, dict[str, dict[str, float]]] = {}
        for p in per_seed:
            inner: dict[str, dict[str, float]] = {}
            # mean across confirm tasks stored as one dummy task for pairing methods
            inner["confirm"] = {
                m: float(np.mean([p["confirmation"][tid]["by_budget"][str(b)][m]["planning"]["mean_return"] for tid in confirm_ids]))
                for m in METHODS
            }
            per_seed_task[int(p["model_seed"])] = inner
        paired_at[str(b)] = {
            "finetune_minus_frozen": paired_seed_deltas(per_seed_task=per_seed_task, treatment="finetune", baseline="frozen"),
            "scratch_minus_frozen": paired_seed_deltas(per_seed_task=per_seed_task, treatment="scratch", baseline="frozen"),
            "replay_minus_frozen": paired_seed_deltas(per_seed_task=per_seed_task, treatment="replay", baseline="frozen"),
            "adapter_minus_frozen": paired_seed_deltas(per_seed_task=per_seed_task, treatment="adapter", baseline="frozen"),
        }

    detect_fpr = seed_level_ci([float(p["detection"]["source_holdout"]["ph_alarm_frac"]) for p in per_seed])
    detect_tpr_b = seed_level_ci([float(p["detection"]["seq_b"]["ph_alarm_frac"]) for p in per_seed])

    payload = {
        "protocol": {
            "code_version": "v0.8",
            "parent_commit": "25f4bf9",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "frozen_v07_kind": FROZEN_KIND,
            "frozen_horizon": FROZEN_PRIMARY_HORIZON,
            "n_train": n_train,
            "n_val": n_val,
            "epochs": epochs,
            "adapt_epochs": adapt_epochs,
            "budgets": list(budgets),
            "n_model_seeds": n_model_seeds,
            "confirm_eval_seed": V08_CONFIRM_EVAL_SEED,
            "dev_eval_seed": V08_DEV_EVAL_SEED,
            "selection_split": "dev_v08",
            "retuned_on_confirmation": False,
            "planner_uses_simulator": False,
            "inference_uses_privileged_physics": False,
            "v07_preserved": True,
            "is_agi": False,
            "quick": quick,
        },
        "tasks": {
            "source": dict(source_spec.params),
            "sequence": [dict(s.params) | {"task_id": s.task_id} for s in (seq_a, seq_b, seq_c)],
            "development": dict(dev.params) | {"task_id": dev.task_id},
            "confirmation": [dict(t.params) | {"task_id": t.task_id} for t in confirms],
        },
        "detection": {"source_ph_alarm_frac": detect_fpr, "shift_B_ph_alarm_frac": detect_tpr_b},
        "confirmation_summary": confirm_summary,
        "confirmation_by_task": {
            tid: {
                str(b): {
                    m: {
                        "mae": seed_level_ci(
                            [float(p["confirmation"][tid]["by_budget"][str(b)][m]["prediction"]["one_step"]["mae"]) for p in per_seed]
                        ),
                        "plan_return": seed_level_ci(
                            [float(p["confirmation"][tid]["by_budget"][str(b)][m]["planning"]["mean_return"]) for p in per_seed]
                        ),
                    }
                    for m in METHODS
                }
                for b in report_budgets
            }
            for tid in confirm_ids
        },
        "paired_planning_vs_frozen": paired_at,
        "dev_selection": {str(p["model_seed"]): p["selected_by_budget"] for p in per_seed},
        "continual_return_to_A": {
            "naive_mae_on_A": seed_level_ci([float(p["forgetting"]["A_return"]["mae_on_A"]) for p in per_seed]),
            "snapshot_mae_on_A": seed_level_ci([float(p["forgetting"]["A_return"]["snapshot_A_mae"]) for p in per_seed]),
        },
        "explore": {
            "random_mae": seed_level_ci([float(p["explore"]["random"]["prediction"]["one_step"]["mae"]) for p in per_seed]),
            "uncertainty_mae": seed_level_ci([float(p["explore"]["uncertainty"]["prediction"]["one_step"]["mae"]) for p in per_seed]),
            "random_return": seed_level_ci([float(p["explore"]["random"]["planning"]["mean_return"]) for p in per_seed]),
            "uncertainty_return": seed_level_ci([float(p["explore"]["uncertainty"]["planning"]["mean_return"]) for p in per_seed]),
        },
        "costs": {
            "mean_source_env_steps": float(np.mean([p["learning_env_steps"] for p in per_seed])),
            "mean_memory_bytes": float(np.mean([p["memory_bytes"] for p in per_seed])),
            "mean_retrieval_inferences": float(np.mean([p["memory_retrieval_inferences"] for p in per_seed])),
            "mean_source_checkpoint_nbytes": float(np.mean([p["source_checkpoint_nbytes"] for p in per_seed])),
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.8 CartPole physics family only. Not AGI. Positive adaptation is not assumed.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
