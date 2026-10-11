"""Reproducible CartPole transition collection. Splits are seed-disjoint."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

import numpy as np

from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec, make_task_env

PolicyName = Literal["random", "exploratory"]


def random_action(obs: np.ndarray, rng: np.random.Generator, n_actions: int) -> int:
    del obs
    return int(rng.integers(0, n_actions))


def exploratory_action(obs: np.ndarray, rng: np.random.Generator, n_actions: int) -> int:
    """Mix of random and a weak angle heuristic. Not the evaluation controller."""
    if rng.random() < 0.35:
        return random_action(obs, rng, n_actions)
    return 1 if float(obs[2] + 0.3 * obs[3]) > 0.0 else 0


POLICIES: dict[str, Callable[[np.ndarray, np.random.Generator, int], int]] = {
    "random": random_action,
    "exploratory": exploratory_action,
}


@dataclass
class TransitionDataset:
    obs: np.ndarray
    action: np.ndarray
    next_obs: np.ndarray
    reward: np.ndarray
    terminated: np.ndarray
    truncated: np.ndarray
    task_id: str
    seed: np.ndarray
    episode_id: np.ndarray
    policy: np.ndarray
    physics: dict[str, float]
    physics_version: str = CARTPOLE_PHYSICS_VERSION
    env_interactions: int = 0
    notes: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return int(self.obs.shape[0])

    def slice(self, idx: np.ndarray) -> "TransitionDataset":
        return TransitionDataset(
            obs=self.obs[idx],
            action=self.action[idx],
            next_obs=self.next_obs[idx],
            reward=self.reward[idx],
            terminated=self.terminated[idx],
            truncated=self.truncated[idx],
            task_id=self.task_id,
            seed=self.seed[idx],
            episode_id=self.episode_id[idx],
            policy=self.policy[idx],
            physics=dict(self.physics),
            physics_version=self.physics_version,
            env_interactions=int(idx.size),
            notes=dict(self.notes),
        )


def collect_transitions(
    spec: TaskSpec,
    *,
    n_transitions: int,
    env_seeds: tuple[int, ...] | list[int],
    base_seed: int,
    policy: PolicyName = "random",
    mix: tuple[PolicyName, ...] | None = None,
) -> TransitionDataset:
    """Collect exactly ``n_transitions`` env steps. Seeds cycle; episodes do not leak across calls."""
    names = mix if mix is not None else (policy,)
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
    rng = np.random.default_rng(base_seed)
    while interactions < n_transitions:
        env_seed = int(env_seeds[seed_i % len(env_seeds)]) + 1000 * (episode_id // max(len(env_seeds), 1))
        seed_i += 1
        env = make_task_env(spec, seed=env_seed)
        obs, _ = env.reset(seed=env_seed)
        done = False
        pol_name = names[episode_id % len(names)]
        fn = POLICIES[pol_name]
        while not done and interactions < n_transitions:
            o = np.asarray(obs, dtype=np.float32).reshape(-1)
            a = int(fn(o, rng, spec.n_actions))
            nxt, rew, terminated, truncated, _ = env.step(a)
            obs_l.append(o)
            act_l.append(a)
            next_l.append(np.asarray(nxt, dtype=np.float32).reshape(-1))
            rew_l.append(float(rew))
            term_l.append(bool(terminated))
            trunc_l.append(bool(truncated))
            seed_l.append(int(env_seed))
            ep_l.append(int(episode_id))
            pol_l.append(pol_name)
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
        notes={"base_seed": base_seed, "n_episodes": episode_id, "policies": list(names)},
    )


def assert_disjoint_seeds(*datasets: TransitionDataset) -> None:
    seen: set[int] = set()
    for ds in datasets:
        seeds = set(int(s) for s in np.unique(ds.seed))
        if seen.intersection(seeds):
            raise ValueError(f"overlapping collect seeds: {seen.intersection(seeds)}")
        seen.update(seeds)


def episodes_from(ds: TransitionDataset) -> list[dict[str, np.ndarray]]:
    out = []
    for eid in np.unique(ds.episode_id):
        m = ds.episode_id == eid
        out.append(
            {
                "obs": ds.obs[m],
                "action": ds.action[m],
                "next_obs": ds.next_obs[m],
                "terminated": ds.terminated[m],
                "truncated": ds.truncated[m],
                "reward": ds.reward[m],
            }
        )
    return out
