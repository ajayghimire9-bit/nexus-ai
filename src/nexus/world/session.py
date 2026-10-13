"""Persistent live environment loop. Reset only on term/trunc or scheduled task change."""

from __future__ import annotations

from typing import Any

import numpy as np

from nexus.tasks.spec import TaskSpec, make_task_env
from nexus.world.belief import BeliefEstimator, BeliefStepModel, IdentityBelief
from nexus.world.data import TransitionDataset
from nexus.world.planning import mpc_for_model


class PersistentSession:
    """One live env across observe → predict → act → detect. Chunks do not reset the env."""

    def __init__(
        self,
        spec: TaskSpec,
        wm: Any,
        *,
        env_seed: int,
        plan_seed: int,
        est: BeliefEstimator | None = None,
    ) -> None:
        self.spec = spec
        self.wm = wm
        self.env_seed = int(env_seed)
        self.plan_seed = int(plan_seed)
        self.est: BeliefEstimator = est if est is not None else IdentityBelief()
        self.planner = mpc_for_model(BeliefStepModel(wm), seed=0)
        self.env = make_task_env(spec, seed=self.env_seed)
        self.obs, _ = self.env.reset(seed=self.env_seed)
        self.est.reset()
        self.planner.reset_episode(self.plan_seed)
        self.prev_a: int | None = None
        self.episode_id = 0
        self.n_resets = 1
        self.n_scheduled_switches = 0
        self.n_term_resets = 0
        self.interactions = 0
        self.closed = False

    def set_model(self, wm: Any) -> None:
        """Swap the deployed model without resetting the live episode or planner RNG."""
        self.wm = wm
        self.planner.model = BeliefStepModel(wm)

    def close(self) -> None:
        if not self.closed:
            self.env.close()
            self.closed = True

    def _start_episode(self, *, scheduled: bool) -> None:
        if not self.closed:
            self.env.close()
        seed = int(self.env_seed) + 1000 * int(self.episode_id + 1)
        self.episode_id += 1
        self.env = make_task_env(self.spec, seed=seed)
        self.closed = False
        self.obs, _ = self.env.reset(seed=seed)
        self.est.reset()
        self.prev_a = None
        self.planner.reset_episode(int(self.plan_seed) + 1000 * int(self.episode_id))
        self.n_resets += 1
        if scheduled:
            self.n_scheduled_switches += 1
        else:
            self.n_term_resets += 1

    def switch_task(self, spec: TaskSpec, *, env_seed: int) -> None:
        """Explicit task transition. The only non-term/trunc reset besides the first start."""
        self.spec = spec
        self.env_seed = int(env_seed)
        self._start_episode(scheduled=True)

    def step(self) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("session closed")
        o = np.asarray(self.obs, dtype=np.float32).reshape(-1)
        b = self.est.observe(o, self.prev_a)
        a, _ = self.planner.act(b)
        nxt, rew, terminated, truncated, _ = self.env.step(int(a))
        nxt_a = np.asarray(nxt, dtype=np.float32).reshape(-1)
        rec = {
            "obs": o,
            "action": int(a),
            "next_obs": nxt_a,
            "reward": float(rew),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "seed": int(self.env_seed) + 1000 * int(self.episode_id),
            "episode_id": int(self.episode_id),
            "prev_action": self.prev_a,
        }
        self.interactions += 1
        self.prev_a = int(a)
        done = bool(terminated or truncated)
        if done:
            self._start_episode(scheduled=False)
        else:
            self.obs = nxt
        return rec

    def collect(self, n: int) -> TransitionDataset:
        n = int(n)
        if n <= 0:
            z = np.zeros((0, self.spec.obs_dim), dtype=np.float32)
            return TransitionDataset(
                obs=z,
                action=np.zeros((0,), dtype=np.int64),
                next_obs=z.copy(),
                reward=np.zeros((0,), dtype=np.float32),
                terminated=np.zeros((0,), dtype=np.bool_),
                truncated=np.zeros((0,), dtype=np.bool_),
                task_id=self.spec.task_id,
                seed=np.zeros((0,), dtype=np.int64),
                episode_id=np.zeros((0,), dtype=np.int64),
                policy=np.array([], dtype=object),
                physics=dict(self.spec.params),
                env_interactions=0,
            )
        recs = [self.step() for _ in range(n)]
        return TransitionDataset(
            obs=np.stack([r["obs"] for r in recs], axis=0),
            action=np.asarray([r["action"] for r in recs], dtype=np.int64),
            next_obs=np.stack([r["next_obs"] for r in recs], axis=0),
            reward=np.asarray([r["reward"] for r in recs], dtype=np.float32),
            terminated=np.asarray([r["terminated"] for r in recs], dtype=np.bool_),
            truncated=np.asarray([r["truncated"] for r in recs], dtype=np.bool_),
            task_id=self.spec.task_id,
            seed=np.asarray([r["seed"] for r in recs], dtype=np.int64),
            episode_id=np.asarray([r["episode_id"] for r in recs], dtype=np.int64),
            policy=np.asarray(["persistent_mpc"] * n, dtype=object),
            physics=dict(self.spec.params),
            env_interactions=n,
            notes={"n_resets": self.n_resets, "episode_id": self.episode_id},
        )
