"""Pure arithmetic and authored-world PPO integration; zero scientific steps."""
from contextlib import closing
from copy import deepcopy
from dataclasses import asdict
import gzip
import io
import importlib.util
import json
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
import pytest
import torch
from gymnasium.vector import AutoresetMode

from nexus.config import PPOConfig, ArchitectureConfig
from nexus.evolution1.resources import Clock
from nexus.evolution2.post_probe import Host
from nexus.rl.ppo import PPOTrainer, _bootstrap_from_final_obs
from nexus.tasks.benchmark import FAMILIES, expected_cells
from nexus.tasks.ppo_benchmark import (bounds, validate_config, all_seeds, job_seeds,
    RecordedTaskEnv, PolicyCounters, collect_update, parameter_hash, validate_complete, analyze)

ROOT = Path(__file__).resolve().parents[1]


def config():
    return json.loads((ROOT / "configs/e4_ppo_benchmark.json").read_text())


class Toy(gym.Env):
    metadata = {}
    def __init__(self, spec):
        self.observation_space = gym.spaces.Box(-100, 100, (spec.obs_dim,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(spec.n_actions)
        self.ticks = 0
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.ticks = 0
        return np.zeros(self.observation_space.shape, np.float32), {}
    def step(self, action):
        self.ticks += 1
        return np.full(self.observation_space.shape, self.ticks, np.float32), float(1 + action), False, self.ticks == 2, {}


def toy_trainer(seed=1):
    journal = io.BytesIO()
    c = config()
    host = Host(c, lambda: Clock(1, 1), io.BytesIO())
    spec = FAMILIES["cartpole"].spec("fixture")
    def factory():
        return RecordedTaskEnv(spec, host, journal, dict(role="authored_fixture"), factory=Toy)
    cfg = PPOConfig(num_envs=1, num_steps=8, total_timesteps=8, update_epochs=1, num_minibatches=2, seed=seed)
    trainer = PPOTrainer(cfg, ArchitectureConfig(hidden_sizes=(8,)), env_fns=[factory], autoreset_mode=AutoresetMode.SAME_STEP)
    return trainer, host, journal


def test_exact_bound_and_no_training_evaluation_seed_overlap():
    c = config()
    assert validate_config(c)
    assert bounds(c) == dict(training_real=61440, evaluation_real_upper=23400, real_upper=84840,
        optimizer_steps=7680, policy_trunk_calls_upper=199800, policy_trunk_rows_upper=437880)
    assert len(all_seeds(c)) == 90
    for f in c["families"]:
        for r in c["replicates"]:
            s = job_seeds(c, f, r)
            assert s["train_reset"] not in s["evaluation"] and s["model"] not in s["evaluation"]


@pytest.mark.parametrize("key,value", [("real_cap", 84841), ("time_cap_s", 301),
    ("training_interactions", 4097), ("autoreset", "NextStep"), ("evaluation_episodes", 1)])
def test_locked_recipe_rejects_substitution(key, value):
    c = config(); c[key] = value
    with pytest.raises(ValueError): validate_config(c)


def test_default_source_physics_cannot_silently_be_changed():
    c = config(); c["tasks"]["pendulum"]["params"]["g"] = 99
    with pytest.raises(ValueError): validate_config(c)
    c = config(); c["ppo"]["learning_rate"] *= 2
    with pytest.raises(ValueError): validate_config(c)


def test_same_step_ppo_updates_on_exact_real_rows_and_reproduces_seed():
    hashes = []
    for _ in range(2):
        trainer, host, journal = toy_trainer()
        counters = PolicyCounters(config())
        handles = counters.attach(trainer.agent, trainer.optimizer)
        try:
            before = parameter_hash(trainer.agent)
            row = collect_update(trainer, trainer.envs.envs[0], before_steps=0)
            after = parameter_hash(trainer.agent)
            assert before != after and row["real_steps"] == 8
            assert host.resources()["completed"]["real_steps"] == 8
            assert trainer._timesteps_done == 8 and counters.counts["optimizer_steps"] == 2
            events = [json.loads(x) for x in journal.getvalue().splitlines()]
            transitions = [e for e in events if e["kind"] == "transition"]
            assert len(transitions) == 8 and sum(e["truncated"] for e in transitions) == 4
            assert all(e["next_observation"] == [2.] * 4 for e in transitions if e["truncated"])
            hashes.append(after)
        finally:
            for h in handles: h.remove()
            trainer.close()
    assert hashes[0] == hashes[1]


def test_same_step_timeout_uses_final_observation_not_reset_value():
    fake = type("Trainer", (), {"_obs_tensor_no_update": staticmethod(torch.as_tensor),
        "agent": type("Agent", (), {"value": staticmethod(lambda x: x[:, 0])})()})()
    v = _bootstrap_from_final_obs(torch.tensor([0.]), {"final_obs": [np.array([7., 0.])]},
        np.array([True]), np.array([False]), np.array([False]), fake)
    assert v.tolist() == [7.]
    term = _bootstrap_from_final_obs(torch.tensor([0.]), {"final_obs": [np.array([7., 0.])]},
        np.array([True]), np.array([True]), np.array([False]), fake)
    assert term.tolist() == [0.]


def complete_fixture():
    c = config()
    p = dict(rows=[], models=[], resources=dict(completed=dict(real_steps=0, imagined_transitions=0, model_calls=0, network_forwards=0),
        unknown_upper=dict(real_steps=0, imagined_transitions=0, model_calls=0, network_forwards=0)),
        policy_compute=dict(counts=dict(optimizer_steps=7680)))
    for family in c["families"]:
        for replicate in c["replicates"]:
            s = job_seeds(c, family, replicate)
            p["models"].append(dict(family=family, replicate=replicate, history=[dict(policy_loss=0., value_loss=0., entropy=1., clipfrac=0.) for _ in range(32)],
                training_real_steps=4096, optimizer_steps=512, initial_hash=f"{family}-{replicate}", fitted_hash="fit", after_evaluation_hash="fit", checkpoint_sha256="a" * 64))
            for method in c["methods"]:
                reward = 50. if method == "ppo_scratch" else 0.
                p["rows"].append(dict(family=family, replicate=replicate, method=method, case=c["cases"][0],
                    episodes=[dict(reset_seed=seed, raw_return=reward, length=2, initial_observation=[0.] * FAMILIES[family].obs_dim, terminated=False, truncated=True) for seed in s["evaluation"]],
                    metrics=dict(raw_return=reward, real_steps=4, imagined_transitions=0, model_calls=0, network_forwards=0, wall_s=1., cpu_s=1.)))
    p["resources"]["completed"]["real_steps"] = 61440 + len(p["rows"]) * 4
    return p, c


def test_seed_level_intervals_do_not_count_episodes_or_families_as_units():
    p, c = complete_fixture()
    assert validate_complete(p, c)
    a = analyze(p, c)
    for family in c["families"]:
        ci = a["families"][family]["contrasts"]["random"]["interval"]
        assert ci["mean"] == 50. and ci["n"] == 3 and ci["df"] == 2
    assert a["label"] == "five_family_scratch_pilot_screen_passed"
    for row in p["rows"]:
        if row["method"] == "ppo_scratch":
            row["metrics"]["raw_return"] = -10
            for e in row["episodes"]: e["raw_return"] = -10
    assert analyze(p, c)["label"] == "five_family_scratch_learning_not_established"


@pytest.mark.parametrize("axis", ["family", "replicate", "method"])
def test_missing_entire_planned_axis_rejected(axis):
    p, c = complete_fixture()
    value = p["rows"][0][axis]
    p["rows"] = [r for r in p["rows"] if r[axis] != value]
    with pytest.raises(ValueError): validate_complete(p, c)


@pytest.mark.parametrize("value", [True, "1", float("nan"), float("inf")])
def test_nonfinite_or_untyped_raw_results_rejected(value):
    p, c = complete_fixture(); p["rows"][0]["episodes"][0]["raw_return"] = value
    with pytest.raises(ValueError): validate_complete(p, c)


def test_frozen_eval_missing_model_and_shortened_episode_list_rejected():
    p, c = complete_fixture(); p["models"][0]["after_evaluation_hash"] = "changed"
    with pytest.raises(ValueError): validate_complete(p, c)
    p, c = complete_fixture(); p["models"].pop()
    with pytest.raises(ValueError): validate_complete(p, c)
    p, c = complete_fixture(); p["rows"][0]["episodes"].pop()
    with pytest.raises(ValueError): validate_complete(p, c)


def test_evaluation_does_not_update_network_and_pairs_initial_states(monkeypatch):
    from nexus.tasks import ppo_benchmark as m
    trainer, host, journal = toy_trainer()
    original = m.RecordedTaskEnv
    monkeypatch.setattr(m, "RecordedTaskEnv", lambda spec, h, j, i: original(spec, h, j, i, factory=Toy))
    try:
        before = parameter_hash(trainer.agent)
        results = [m.evaluate(config(), trainer.agent, FAMILIES["cartpole"].spec(), host, journal, dict(role="fixture"),
            reset_seed=10, policy_seed=20, method=method) for method in config()["methods"]]
        assert parameter_hash(trainer.agent) == before
        assert len({tuple(r["initial_observation"]) for r in results}) == 1
        assert all(r["length"] == 2 and r["truncated"] for r in results)
    finally:
        trainer.close()


def test_hook_budget_rejects_before_neural_execution():
    trainer, _, _ = toy_trainer()
    counter = PolicyCounters(config())
    counter.upper["policy_trunk_calls_upper"] = 0
    handles = counter.attach(trainer.agent)
    try:
        with pytest.raises(ValueError, match="policy_forward_cap"):
            trainer.agent(torch.zeros(1, 4))
        assert counter.counts["trunk_calls"] == 0 and counter.counts["policy_head_calls"] == 0
    finally:
        for h in handles: h.remove()
        trainer.close()


def test_independent_journal_audit_rejects_changed_episode_return(tmp_path, monkeypatch):
    from nexus.tasks import ppo_benchmark as m
    resources, transitions = io.BytesIO(), io.BytesIO()
    h = Host(config(), lambda: Clock(1, 1), resources)
    original = m.RecordedTaskEnv
    monkeypatch.setattr(m, "RecordedTaskEnv", lambda spec, host, j, i: original(spec, host, j, i, factory=Toy))
    identity = dict(role="evaluation", family="cartpole", replicate="learner_0", method="fixed", evaluation_episode=0)
    result = m.evaluate(config(), None, FAMILIES["cartpole"].spec(split="development"), h, transitions,
        identity, reset_seed=10, policy_seed=20, method="fixed")
    paths = []
    for prefix, data in (("resources", resources), ("transitions", transitions)):
        path = tmp_path / f"e4_ppo_{prefix}.jsonl.gz"
        with gzip.open(path, "wb") as stream: stream.write(data.getvalue())
        paths.append(dict(path=path.name))
    p = dict(journals=paths, models=[], resources=h.resources(), rows=[dict(family="cartpole", replicate="learner_0", method="fixed", episodes=[{**result, "raw_return": 999.}])])
    with pytest.raises(ValueError, match="independent_raw_return_mismatch"):
        m.audit_journals(p, tmp_path, deadline=time.perf_counter() + 10)


def entry_fixture(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("e4_pilot_entry", ROOT / "scripts/run_e4_ppo_benchmark.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    c = config()
    for attr, relative in dict(ROOT=".", CONFIG="config.json", PROTOCOL="protocol.md", RESULT="result.json", USAGE="usage.json", LOCAL="local_run").items():
        monkeypatch.setattr(m, attr, tmp_path / relative)
    m.CONFIG.write_text(json.dumps(c)); m.PROTOCOL.write_text("authored gate fixture, no run")
    names = ["scripts/run_e4_ppo_benchmark.py", "src/nexus/tasks/ppo_benchmark.py", "src/nexus/rl/ppo.py", "src/nexus/tasks/benchmark.py", "src/nexus/evolution2/post_probe.py"]
    for name in names:
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("source fixture")
    allocation = dict(authorized=True, runs=1, config_sha256=m.file_hash(m.CONFIG), protocol_sha256=m.file_hash(m.PROTOCOL),
        real_cap=84840, time_cap_s=300, session_remaining_before_s=1000,
        source_sha256={name:m.file_hash(tmp_path / name) for name in names}, frozen_preservation=[],
        historical_snapshot=dict(count=0, sorted_hash_map_sha256="fixture"))
    monkeypatch.setattr(m, "historical_snapshot", lambda *args: allocation["historical_snapshot"])
    monkeypatch.setattr(m, "RecordedTaskEnv", lambda *args: pytest.fail("preflight must not construct worlds"))
    return m, c, allocation


def test_consumed_allocation_rejected_before_environment_construction(tmp_path, monkeypatch):
    m, c, allocation = entry_fixture(tmp_path, monkeypatch)
    m.USAGE.write_text('{"consumed":true}')
    with pytest.raises(FileExistsError, match="one_run_already_started"):
        m.preflight(c, allocation)


def test_missing_or_stale_protocol_and_source_rejected(tmp_path, monkeypatch):
    m, c, allocation = entry_fixture(tmp_path, monkeypatch)
    allocation["authorized"] = False
    with pytest.raises(ValueError): m.preflight(c, allocation)
    allocation["authorized"] = True
    m.PROTOCOL.write_text("changed")
    with pytest.raises(ValueError): m.preflight(c, allocation)
    allocation["protocol_sha256"] = m.file_hash(m.PROTOCOL)
    (tmp_path / "src/nexus/rl/ppo.py").write_text("unregistered changed source")
    with pytest.raises(ValueError, match="locked_source_changed"):
        m.preflight(c, allocation)
