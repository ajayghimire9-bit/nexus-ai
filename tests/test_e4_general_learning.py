"""Source-only fixtures. Real-world smoke is an explicit separate script."""
from copy import deepcopy
from contextlib import closing
from dataclasses import replace
import io
import itertools
import json
from pathlib import Path
from types import SimpleNamespace

import gymnasium as gym
import numpy as np
import pytest
import torch

from nexus.evolution1.resources import Clock
from nexus.evolution2.post_probe import Host
from nexus.nn.bounds import architecture_cost, probe_architecture
from nexus.nn.expr import UNARY, ExprActivation, register_expr, validate_tree
from nexus.nn.spec import ArchitectureSpec
from nexus.tasks.benchmark import (FAMILIES, MeteredTaskEnv, evaluate_policy,
    expected_cells, ppo_binding, summarize_results, validate_results, validate_spec,
    validate_physics_splits, paired_comparison)
from nexus.tasks.learning_stream import begin_task, stream_binding

ROOT = Path(__file__).resolve().parents[1]


class FixtureEnv(gym.Env):
    def __init__(self, spec):
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, (spec.obs_dim,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(spec.n_actions)
        self.ticks = 0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.ticks = 0
        return self.np_random.normal(size=self.observation_space.shape).astype(np.float32), {}

    def step(self, action):
        self.ticks += 1
        return np.full(self.observation_space.shape, action, np.float32), 1., False, self.ticks == 2, {}


def host(cap=100, clock=lambda: Clock(1, 1)):
    return Host(dict(real_cap=cap, imagined_cap=0, model_call_cap=0,
                     network_forward_cap=0, time_cap_s=30), clock, io.BytesIO())


@pytest.mark.parametrize("family", FAMILIES)
def test_five_family_contract_and_same_ppo_algorithm(family):
    c = FAMILIES[family]
    spec = c.spec()
    assert validate_spec(spec) == c
    h = host()
    binding = ppo_binding(spec, h, seed=0, total_timesteps=128)
    assert binding["ppo"].learning_rate == 3e-4
    assert binding["architecture"].hidden_sizes == (64, 64)
    with MeteredTaskEnv(spec, h, factory=FixtureEnv) as env:
        a = evaluate_policy(env, lambda obs, rng, n: int(rng.integers(n)), seed=0, max_steps=4)
        b = evaluate_policy(env, lambda obs, rng, n: int(rng.integers(n)), seed=0, max_steps=4)
        assert a == b
        assert len(a["steps"]) == 2 and a["steps"][-1]["truncated"]
        assert a["raw_return"] == 2 and not a["collector_cutoff"]
        with pytest.raises(ValueError):
            env.step(0)
        env.reset()  # SAME seeded RNG supports vector autoreset.
        assert env.step(0)[1] == 1
    assert h.resources()["completed"]["real_steps"] == 5


def test_shared_budget_not_reset_by_reopening_world():
    h = host(1)
    for family in ("cartpole", "pendulum"):
        with MeteredTaskEnv(FAMILIES[family].spec(), h, factory=FixtureEnv) as env:
            env.reset(seed=0)
            if family == "cartpole":
                env.step(1)
            else:
                with pytest.raises(ValueError, match="global_pre_dispatch_cap"):
                    env.step(1)
    assert h.resources()["completed"]["real_steps"] == 1


@pytest.mark.parametrize("family", FAMILIES)
def test_existing_ppo_vector_api_autoresets_numpy_actions_and_network_shapes(family):
    from nexus.rl.actor_critic import ActorCritic
    c = FAMILIES[family]
    h = host()
    with closing(gym.vector.SyncVectorEnv([lambda: MeteredTaskEnv(c.spec(), h, factory=FixtureEnv)])) as envs:
        obs, _ = envs.reset(seed=0)
        for _ in range(5):
            # Existing PPO sends the same NumPy int64 action-vector interface.
            envs.step(np.array([0], dtype=np.int64))
        assert h.resources()["completed"]["real_steps"] == 4
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(0)
            agent = ActorCritic(c.obs_dim, envs.single_action_space, ArchitectureSpec((16, 16)))
            logp, value, entropy = agent.evaluate_actions(torch.as_tensor(obs), torch.zeros(1))
            assert logp.shape == value.shape == entropy.shape == (1,)
            (-logp.mean() + value.square().mean()).backward()
            assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in agent.parameters())


def test_deadline_precedes_dispatch_and_invalid_actions_not_charged():
    env = MeteredTaskEnv(FAMILIES["cartpole"].spec(), host(), factory=FixtureEnv)
    with pytest.raises(ValueError): env.reset()
    env.reset(seed=0)
    for invalid in (-1, 2, True, .5):
        with pytest.raises(ValueError): env.step(invalid)
    assert env.host.resources()["reserved"]["real_steps"] == 0
    env.host.clock = lambda: Clock(1, 31_000_000_000)
    with pytest.raises(Exception, match="ledger_stopped"):
        env.step(0)
    assert env.env.ticks == 0
    env.close()


def test_failure_consumes_registered_work():
    class Broken(FixtureEnv):
        def step(self, action): raise RuntimeError("broken")
    h = host()
    with MeteredTaskEnv(FAMILIES["cartpole"].spec(), h, factory=Broken) as env:
        env.reset(seed=0)
        with pytest.raises(RuntimeError): env.step(0)
    assert h.resources()["unknown_upper"]["real_steps"] == 1


def test_gym_numpy_reward_scalars_preserve_value_and_json_numeric_type():
    class NumpyReward(FixtureEnv):
        def step(self, action):
            obs, _, term, trunc, info = super().step(action)
            return obs, np.float64(-.125), term, trunc, info
    with MeteredTaskEnv(FAMILIES["pendulum"].spec(), host(), factory=NumpyReward) as env:
        env.reset(seed=0)
        result = env.step(np.int64(0))
        assert type(result[1]) is float and result[1] == -.125


def test_compatibility_checks_semantics_not_just_dimensions():
    mc, continuous = FAMILIES["mountaincar"], FAMILIES["mountaincar_continuous"]
    assert mc.obs_dim == continuous.obs_dim
    assert not mc.compatible(continuous, normalization_hash="abc", other_normalization_hash="abc")
    assert not mc.compatible(mc, normalization_hash="abc", other_normalization_hash="def")
    model = SimpleNamespace(net=SimpleNamespace(obs_dim=2, n_actions=3))
    mc.check_model(model, saved_contract_hash=mc.signature(), normalization_hash="abc", expected_normalization_hash="abc")
    with pytest.raises(ValueError):
        continuous.check_model(model, saved_contract_hash=mc.signature(), normalization_hash="abc", expected_normalization_hash="abc")
    assert mc.signature() != replace(mc, reward="other").signature()


def test_task_specs_cannot_silently_change_adapters_or_splits():
    c = FAMILIES["pendulum"]
    spec = c.spec()
    spec.params["g"] = 11
    assert c.spec().params["g"] == 10
    with pytest.raises(ValueError): c.spec(params={"obs_noise_std": 1})
    with pytest.raises(ValueError): c.spec(split="secret")
    with pytest.raises(ValueError): validate_spec(replace(spec, reward_scale=2))


def test_split_overlap_rejected_without_collecting_data():
    c = FAMILIES["cartpole"]
    a = c.spec("source", split="train")
    b = c.spec("other", split="development")
    with pytest.raises(ValueError): validate_physics_splits(dict(train=[a], development=[b]))
    # Algebraic fixture only; not a numerical research registration.
    with pytest.raises(ValueError): validate_physics_splits(dict(train=[a, a]))
    assert validate_physics_splits(dict(train=[a]))


def rows_and_manifest():
    c = json.loads((ROOT / "configs/e4_general_learning_benchmark.json").read_text())
    rows = [dict(zip(("family", "replicate", "method", "case"), cell),
                 metrics={name: 1 for name in c["required_metrics"]}) for cell in sorted(expected_cells(c))]
    return rows, c


@pytest.mark.parametrize("axis", ["family", "replicate", "method", "case"])
def test_missing_entire_planned_axis_rejected(axis):
    rows, c = rows_and_manifest()
    value = rows[0][axis]
    with pytest.raises(ValueError): validate_results([r for r in rows if r[axis] != value], c)


@pytest.mark.parametrize("value", [True, "1", float("nan"), float("inf"), None])
def test_invalid_metrics_rejected(value):
    rows, c = rows_and_manifest()
    rows[0]["metrics"]["raw_return"] = value
    with pytest.raises(ValueError): validate_results(rows, c)


def test_complete_results_and_family_specific_intervals():
    rows, c = rows_and_manifest()
    assert validate_results(rows, c)
    summary = summarize_results(rows, c)
    assert len(summary) == 5 * len(c["methods"]) * len(c["cases"])
    assert all(s["interval"]["n"] == 3 and s["interval"]["df"] == 2 for s in summary.values())
    with pytest.raises(ValueError): validate_results(rows + [deepcopy(rows[0])], c)
    contrast = paired_comparison(rows, c, family="pendulum", case="source", treatment="ppo_prior", baseline="ppo_scratch")
    assert contrast["per_seed"] == [0, 0, 0] and contrast["interval"]["df"] == 2


@pytest.mark.parametrize("control", ["persistent", "reset", "shuffled"])
def test_a_b_a_c_uses_same_taskstream_and_fresh_family_contexts(control):
    from nexus.evolution2.continual_state import TaskStream
    stream = stream_binding(control=control, schedule="fixed", seed=7, max_choices=4)
    assert type(stream) is TaskStream
    previous = None
    for i, (label, family) in enumerate(zip(("A", "B", "A", "C"), ("cartpole", "pendulum", "cartpole", "acrobot"))):
        context = begin_task(stream, FAMILIES[family].spec(label, split="train"))
        assert context.obs_dim == FAMILIES[family].obs_dim and context is not previous
        assert context.features()["total_observed"] == 0
        assert stream.choose_experiment() in TaskStream.ACTIONS
        stream.reveal(event=f"fixture_{i}", observed_return_gain=1., cpu_s=1., domain="synthetic_fixture")
        previous = context
    assert stream.remaining == 0 and stream.choose_experiment() == "stop"
    # Four fixture feedbacks are explicitly NOT environment learning evidence.
    assert len(stream.events) == 4


def test_softsign_opt_in_finite_gradient_and_legacy_sampler_unchanged():
    assert "softsign" not in UNARY
    expr = ("unary", "softsign", ("x",))
    name = register_expr(expr)
    x = torch.tensor([-1e6, -1., 0., 1., 1e6], requires_grad=True)
    result = ExprActivation(expr)(x)
    result.sum().backward()
    assert torch.isfinite(result).all() and torch.isfinite(x.grad).all()
    assert x.grad[2] > 0
    assert probe_architecture(4, ArchitectureSpec((16, 16), activation=name))["parameters"] == 356


@pytest.mark.parametrize("tree", [("x", "extra"), ("unary", "exec", ("x",)), ("binary", "add", ("x",)), ["x"]])
def test_malformed_expression_rejected_before_registration(tree):
    with pytest.raises(ValueError): register_expr(tree)


def test_expression_size_and_architecture_preallocation_caps():
    expr = ("x",)
    for _ in range(12): expr = ("unary", "softsign", expr)
    with pytest.raises(ValueError): validate_tree(expr)
    with pytest.raises(ValueError): architecture_cost(4, ArchitectureSpec((257,)))
    with pytest.raises(ValueError): architecture_cost(4, ArchitectureSpec((True,)))
    with pytest.raises(ValueError): architecture_cost(4, ArchitectureSpec((256, 256)), parameter_cap=10)


@pytest.mark.parametrize("residual,norm", list(itertools.product((False, True), repeat=2)))
def test_existing_residual_normalization_variants_numeric_bounds_and_rng(residual, norm):
    spec = ArchitectureSpec((16, 16), use_residual=residual, layer_norm=norm, dropout=.1)
    before = torch.random.get_rng_state().clone()
    a = probe_architecture(4, spec)
    assert torch.equal(before, torch.random.get_rng_state())
    assert a == probe_architecture(4, spec) and a["parameter_gradient_norm"] > 0
    assert a["dense_macs_per_row"] == 320


def test_saved_engineering_smoke_is_complete_without_new_environment_steps():
    path = ROOT / "artifacts/e4_foundation_smoke.json"
    if not path.exists():
        # Before first execution there must be no requirement to generate data
        # merely to run the source-only suite.
        return
    record = json.loads(path.read_text())
    config = json.loads((ROOT / "configs/e4_foundation_smoke.json").read_text())
    expected = set(itertools.product(config["families"], config["policies"]))
    ids = [(r["family"], r["policy"]) for r in record["paths"]]
    assert len(ids) == len(expected) and set(ids) == expected
    total = 0
    for row in record["paths"]:
        assert len(row["replays"]) == 2 and row["replays"][0] == row["replays"][1]
        for replay in row["replays"]:
            assert 1 <= len(replay["steps"]) <= 4
            assert replay["raw_return"] == sum(s["reward"] for s in replay["steps"])
            assert all(np.isfinite(s["observation"]).all() and np.isfinite(s["next_observation"]).all() for s in replay["steps"])
            total += len(replay["steps"])
    assert record["status"] == "complete" and record["scientific_claims"] is False
    assert record["resources"]["completed"] == dict(real_steps=total, imagined_transitions=0, model_calls=0, network_forwards=0)
    assert len(record["receipts"]) == total <= config["real_cap"]
    assert not any(record["resources"]["unknown_upper"].values())
