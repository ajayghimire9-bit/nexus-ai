"""Shared five-family bindings, not a new learner, planner or resource meter.

TaskSpec/wrappers own dynamics; PPOTrainer owns learning; Host and its
ReservationLedger own reservations. Opening a real world is always explicit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import itertools
import json
import math
import time

import gymnasium as gym
import numpy as np

from nexus.config import ArchitectureConfig, PPOConfig
from nexus.evolution1.resources import Clock, Operation, Work
from nexus.tasks.spec import TaskSpec, make_task_env


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class FamilyContract:
    family: str
    gym_id: str
    observation_fields: tuple[str, ...]
    action_values: tuple[float, ...]
    action_semantics: str
    reward: str
    termination: str
    max_episode_steps: int
    default_params: tuple[tuple[str, float], ...] = ()

    @property
    def obs_dim(self):
        return len(self.observation_fields)

    def spec(self, task_id=None, split="engineering_fixture", params=None):
        if split not in {"train", "validation", "development", "confirmation", "engineering_fixture"}:
            raise ValueError("explicit_split_required")
        settings = dict(self.default_params)
        for key, value in (params or {}).items():
            if key not in settings or type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
                raise ValueError("unsupported_physics_parameter")
            settings[key] = value
        return TaskSpec(task_id or self.family, self.family, self.gym_id,
                        self.obs_dim, len(self.action_values), settings, train_split=split)

    def signature(self):
        # Physics/split intentionally excluded: same interface is not evidence
        # that weights transfer, or that training and evaluation are disjoint.
        payload = asdict(self)
        payload.pop("default_params")
        return fingerprint(payload)

    def compatible(self, other, *, normalization_hash, other_normalization_hash):
        return (self.signature() == other.signature()
                and bool(normalization_hash) and normalization_hash == other_normalization_hash)

    def check_model(self, model, *, saved_contract_hash, normalization_hash, expected_normalization_hash):
        if (saved_contract_hash != self.signature()
                or not normalization_hash or normalization_hash != expected_normalization_hash
                or model.net.obs_dim != self.obs_dim
                or model.net.n_actions != len(self.action_values)):
            raise ValueError("model_schema_action_reward_or_normalization_mismatch")


FAMILIES = {
    "cartpole": FamilyContract("cartpole", "CartPole-v1", ("x", "x_dot", "theta", "theta_dot"),
        (0., 1.), "native discrete left/right force", "native +1 per step, including failure step",
        "native failure; TimeLimit truncation distinct", 500,
        (("gravity", 9.8), ("masspole", .1), ("masscart", 1.), ("length", .5))),
    "mountaincar": FamilyContract("mountaincar", "MountainCar-v0", ("position", "velocity"),
        (0., 1., 2.), "native discrete left/neutral/right", "sin(3 * successor_position)",
        "goal termination suppressed by existing dense wrapper; timeout retained", 200,
        (("force", .001), ("gravity", .0025))),
    "mountaincar_continuous": FamilyContract("mountaincar_continuous", "MountainCarContinuous-v0",
        ("position", "velocity"), (-1., 0., 1.), "discrete index -> continuous force via existing torque wrapper",
        "sin(3 * successor_position)", "goal termination suppressed by existing dense wrapper; timeout retained", 200,
        (("power", .0015), ("gravity", .0025))),
    "pendulum": FamilyContract("pendulum", "Pendulum-v1", ("cos_theta", "sin_theta", "theta_dot"),
        (-2., 0., 2.), "discrete index -> torque via existing wrapper",
        "native -(theta^2 + .1*theta_dot^2 + .001*torque^2), pre-transition state",
        "native nonterminal; TimeLimit truncation", 200, (("g", 10.), ("m", 1.), ("l", 1.))),
    "acrobot": FamilyContract("acrobot", "Acrobot-v1", ("cos1", "sin1", "cos2", "sin2", "dot1", "dot2"),
        (0., 1., 2.), "native discrete torque indices (-1,0,+1)",
        "-successor_cos1 - (successor_cos1*cos2 - successor_sin1*sin2)",
        "goal termination suppressed by existing dense wrapper; timeout retained", 200,
        (("LINK_MASS_1", 1.), ("LINK_MASS_2", 1.), ("LINK_LENGTH_1", 1.))),
}


def validate_spec(spec):
    contract = FAMILIES[spec.family]
    expected = contract.spec(spec.task_id, spec.train_split, spec.params)
    if spec != expected:
        raise ValueError("task_spec_outside_reviewed_contract")
    return contract


def validate_physics_splits(groups):
    """For physics-disjoint designs only; reset-shift reuses physics explicitly.

    This checks supplied registrations, not historical exclusion completeness.
    Historical registry review remains mandatory before choosing new physics.
    """
    seen, identities = set(), set()
    for split, specs in groups.items():
        if not specs:
            raise ValueError("empty_registered_split")
        for spec in specs:
            validate_spec(spec)
            physics = (spec.family, spec.gym_id, tuple(sorted((k, float(v)) for k, v in spec.params.items())))
            if spec.train_split != split or physics in seen or spec.task_id in identities:
                raise ValueError("physics_or_task_identity_overlap")
            seen.add(physics)
            identities.add(spec.task_id)
    return True


class MeteredTaskEnv(gym.Wrapper):
    """Thin dispatch over SAME Host, shared across all roles and environments.

    Injected factory is for source-only fixtures. Scientific callers must not
    replace the trusted factory. Invalid step results consume reserved work.
    """
    def __init__(self, spec, host, *, factory=make_task_env):
        self.contract = validate_spec(spec)
        self.host = host
        self.task_spec = spec
        self.ready = False
        self.seeded = False
        super().__init__(factory(spec))
        if (not isinstance(self.observation_space, gym.spaces.Box)
                or self.observation_space.shape != (spec.obs_dim,)
                or not isinstance(self.action_space, gym.spaces.Discrete)
                or self.action_space.n != spec.n_actions):
            self.close()
            raise ValueError("actual_spaces_disagree_with_contract")

    def _observation(self, obs):
        if np.asarray(obs).shape != (self.task_spec.obs_dim,) or not np.isfinite(obs).all():
            raise ValueError("finite_observation_shape")

    def reset(self, *, seed=None, options=None):
        if seed is None and self.seeded:
            pass  # Gym vector autoreset continues the explicitly seeded RNG.
        elif type(seed) is not int or seed < 0:
            raise ValueError("explicit_reset_seed_required")
        self.ready = False
        obs, info = self.env.reset(seed=seed, options=options)
        self._observation(obs)
        if seed is not None:
            self.action_space.seed(seed)
        self.seeded = True
        self.ready = True
        return obs, info

    def step(self, action):
        if not self.ready or (type(action) is not int and not isinstance(action, np.integer)) or not self.action_space.contains(action):
            raise ValueError("reset_required_or_invalid_action")
        action = int(action)  # SyncVectorEnv supplies NumPy integer scalars.
        key = "task_step"  # each Host.perform creates its own existing ledger
        def execute(dispatch):
            result = dispatch.environment(key, self.env, action)
            obs, reward, terminated, truncated, _ = result
            self._observation(obs)
            if (type(reward) not in (float, int) and not isinstance(reward, np.floating)) or not math.isfinite(reward):
                raise ValueError("finite_reward_required")
            if type(terminated) is not bool or type(truncated) is not bool:
                raise ValueError("boolean_episode_flags")
            return obs, float(reward), terminated, truncated, result[4]
        try:
            result, _ = self.host.perform((Operation(key, "environment", Work(real_steps=1)),), execute,
                dict(task=self.task_spec.task_id, split=self.task_spec.train_split, family=self.task_spec.family))
        except BaseException:
            self.ready = False
            raise
        self.ready = not (result[2] or result[3])
        return result


def ppo_binding(spec, host, *, seed, total_timesteps):
    """Constructor kwargs for SAME PPOTrainer, no construction or training here.

    All five families use the same algorithm/hyperparameters and independent
    shape-appropriate weights. Host must include all collection/evaluation.
    """
    validate_spec(spec)
    if type(seed) is not int or seed < 0 or type(total_timesteps) is not int or total_timesteps < 1:
        raise ValueError("explicit_training_recipe_required")
    def open_env():
        env = MeteredTaskEnv(spec, host)
        env.reset(seed=seed)
        return env
    return dict(ppo=PPOConfig(env_id=spec.gym_id, num_envs=1, total_timesteps=total_timesteps,
                             seed=seed, device="cpu"),
                architecture=ArchitectureConfig(), env_fns=[open_env])


def evaluate_policy(env, policy, *, seed, max_steps):
    """Explicit bounded trajectory; native terminated and truncated remain separate."""
    if type(max_steps) is not int or not 1 <= max_steps <= env.contract.max_episode_steps:
        raise ValueError("bounded_episode_required")
    obs, _ = env.reset(seed=seed)
    rng = np.random.default_rng(seed)
    rows = []
    for tick in range(max_steps):
        action = policy(obs.copy(), rng, env.action_space.n)
        nxt, reward, terminated, truncated, _ = env.step(action)
        rows.append(dict(tick=tick, observation=obs.tolist(), action=action,
            next_observation=nxt.tolist(), reward=reward, terminated=terminated, truncated=truncated))
        obs = nxt
        if terminated or truncated:
            break
    return dict(steps=rows, raw_return=sum(r["reward"] for r in rows),
                collector_cutoff=not (rows[-1]["terminated"] or rows[-1]["truncated"]))


def expected_cells(manifest):
    axes = ("families", "replicates", "methods", "cases")
    for axis in axes:
        values = manifest[axis]
        if not values or any(type(v) is not str for v in values) or len(values) != len(set(values)):
            raise ValueError("invalid_locked_axis")
    if set(manifest["families"]) != set(FAMILIES):
        raise ValueError("five_reviewed_families_required")
    return set(itertools.product(*(manifest[a] for a in axes)))


def validate_results(rows, manifest):
    """Expected grid comes only from locked manifest, never produced results."""
    ids = [(r["family"], r["replicate"], r["method"], r["case"]) for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != expected_cells(manifest):
        raise ValueError("incomplete_or_duplicate_result_grid")
    for row in rows:
        for name in manifest["required_metrics"]:
            value = row["metrics"].get(name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("missing_or_nonfinite_numeric_metric")
        for name in ("real_steps", "imagined_transitions", "model_calls", "network_forwards"):
            value = row["metrics"][name]
            if type(value) is not int or value < 0:
                raise ValueError("nonnegative_integer_resource_count")
        if row["metrics"]["wall_s"] < 0 or row["metrics"]["cpu_s"] < 0:
            raise ValueError("nonnegative_elapsed_time")
    return True


def summarize_results(rows, manifest):
    from nexus.cl.metrics import seed_level_ci
    validate_results(rows, manifest)
    out = {}
    for family, method, case in itertools.product(manifest["families"], manifest["methods"], manifest["cases"]):
        values = [r["metrics"]["raw_return"] for r in rows
                  if (r["family"], r["method"], r["case"]) == (family, method, case)]
        interval = seed_level_ci(values) if len(values) > 1 else dict(n=1, mean=values[0], lo=None, hi=None)
        out[f"{family}/{method}/{case}"] = dict(raw_units=True, interval=interval,
            replication_unit="independently_initialized_learner_seed", normalization=None)
    return out  # Deliberately no across-family raw-return average.


def paired_comparison(rows, manifest, *, family, case, treatment, baseline):
    from nexus.cl.metrics import seed_level_ci
    validate_results(rows, manifest)
    if family not in manifest["families"] or case not in manifest["cases"] or treatment == baseline or any(m not in manifest["methods"] for m in (treatment, baseline)):
        raise ValueError("registered_paired_comparison_required")
    lookup = {(r["replicate"], r["method"]): r["metrics"]["raw_return"] for r in rows if r["family"] == family and r["case"] == case}
    deltas = [lookup[(seed, treatment)] - lookup[(seed, baseline)] for seed in manifest["replicates"]]
    return dict(per_seed=deltas, interval=seed_level_ci(deltas) if len(deltas) > 1 else None,
                unit="independently_initialized_learner_seed", family=family, case=case)
