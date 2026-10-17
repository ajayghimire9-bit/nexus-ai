"""Source-only H14 runner tests. No MountainCar env, no training."""
from __future__ import annotations
import inspect
import json
import time
from pathlib import Path
import numpy as np
import pytest
from nexus.world.data import TransitionDataset
from nexus.world import h14_candidate_reuse as lock
from nexus.world import h14_candidate_reuse_runner as runner


class DummyModel:
    def __init__(self, bias=0.0):
        self.bias = float(bias)
        self.calls = 0

    def copy_rms(self, rms):
        self.rms = rms

    def step(self, obs, action):
        self.calls += 1
        arr = np.asarray(obs, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr + self.bias, np.zeros(arr.shape[0], dtype=np.float64)


class MockEnv:
    def __init__(self, obs0=(0.1, 0.0), reward=-1.0, hidden=None, mismatch_hidden=False):
        self.obs0 = np.asarray(obs0, dtype=np.float32)
        self.obs = self.obs0.copy()
        self.reward = float(reward)
        self.hidden0 = np.asarray(hidden if hidden is not None else obs0, dtype=np.float64)
        self.state = self.hidden0.copy()
        self.unwrapped = self
        self.mismatch_hidden = mismatch_hidden
        self.resets = 0
        self.steps = 0

    def reset(self, seed=None):
        self.resets += 1
        self.obs = self.obs0.copy()
        self.state = self.hidden0.copy()
        if self.mismatch_hidden and self.resets > 1:
            self.state = self.hidden0 + 9.0
        return self.obs.copy(), {}

    def step(self, action):
        self.steps += 1
        self.obs = self.obs + 0.001 * (int(action) + 1)
        self.state = self.obs.astype(np.float64)
        return self.obs.copy(), self.reward, False, False, {}

    def close(self):
        pass


def fake_dataset(n, dim=2):
    return TransitionDataset(
        obs=np.zeros((n, dim), np.float32),
        action=np.zeros(n, np.int64),
        next_obs=np.zeros((n, dim), np.float32),
        reward=np.zeros(n, np.float32),
        terminated=np.zeros(n, np.bool_),
        truncated=np.zeros(n, np.bool_),
        task_id='toy',
        seed=np.zeros(n, np.int64),
        episode_id=np.zeros(n, np.int64),
        policy=np.array(['random'] * n),
        physics={'toy': 1.0},
    )


def fake_collect(spec, n_transitions, env_seeds, base_seed, mix=None):
    return fake_dataset(int(n_transitions))


def fake_train(train, val, **kwargs):
    return DummyModel(), {}


def fake_continue(*args, **kwargs):
    return None


def fake_rms(obs):
    return object()


def fast_score(model, obs, sequences, meter):
    meter.reserve_imagined(lock.N_CAND * lock.HORIZON)
    scores = np.arange(lock.N_CAND, dtype=np.float64) + float(getattr(model, 'bias', 0.0))
    first = np.repeat(np.asarray(obs, dtype=np.float64).reshape(1, -1), lock.N_CAND, axis=0)
    return scores, first


def cfg():
    return lock.load_config()


def test_lock_hashes_and_physics_are_unchanged():
    from nexus.world.planning_value import sha
    assert sha(lock.CONFIG) == lock.LOCKED_CONFIG
    assert sha(lock.PROTOCOL) == lock.LOCKED_PROTOCOL
    assert sha(lock.ALLOCATION) == '4155621de732cdc9b9a6cda3d478c3f6aab89693be6cb430ca10a350253cff51'
    assert lock.holdout_from_rule() == [lock.LOCKED_TARGET]
    assert lock.load_allocation()['authorized'] is False
    assert lock.load_allocation()['runs'] == 0


def test_four_conditions_share_l0_and_fixed_reuses_it():
    loaded = cfg()
    lib = loaded['library_base']
    redraw = loaded['redraw_base']
    matrices = []
    for mode in lock.MODES:
        for _arm in lock.ARMS:
            matrices.append(lock.recede_candidates(mode, lib, redraw, 3, 2, 0))
    assert all(np.array_equal(matrices[0], item) for item in matrices)
    first = matrices[0]
    for step in range(1, 16):
        assert np.array_equal(lock.recede_candidates('fixed', lib, redraw, 3, 2, step), first)
        fresh = lock.recede_candidates('redraw', lib, redraw, 3, 2, step)
        assert not np.array_equal(fresh, first)
        other_arm = lock.recede_candidates('redraw', lib, redraw, 3, 2, step)
        assert np.array_equal(fresh, other_arm)
        assert runner.candidate_seed_for(loaded, 3, 2, step, 'redraw') == lock.redraw_step_seed(redraw, 3, 2, step)


def test_first_index_argmax_and_did():
    seq = np.zeros((16, 16), dtype=np.int64)
    seq[0, 0] = 2
    seq[1, 0] = 1
    scores = np.ones(16)
    idx, action = lock.selected_first_action(seq, scores)
    assert idx == 0 and action == 2
    means = {('multitask', 'fixed'): 4.0, ('scratch', 'fixed'): 1.0,
             ('multitask', 'redraw'): 2.0, ('scratch', 'redraw'): 2.0}
    assert lock.difference_in_differences(means) == 3.0


def test_reset_obs_and_hidden_state_mismatch():
    env = MockEnv(obs0=(0.2, 0.0), hidden=(0.2, 0.0))
    recorded = runner.record_reset(env, 76100002)
    assert np.allclose(recorded['obs'], [0.2, 0.0])
    again = runner.assert_same_reset(env, 76100002, recorded)
    assert np.allclose(again, recorded['obs'])
    bad = MockEnv(obs0=(0.3, 0.0))
    with pytest.raises(RuntimeError, match='reset identity'):
        runner.assert_same_reset(bad, 1, recorded)
    hidden = MockEnv(obs0=(0.2, 0.0), hidden=(0.2, 0.0), mismatch_hidden=True)
    first = runner.record_reset(hidden, 7)
    with pytest.raises(RuntimeError, match='hidden-state'):
        runner.assert_same_reset(hidden, 7, first)


def test_real_reward_accumulation_and_open_loop_alignment():
    env = MockEnv(reward=-0.5)
    recorded = runner.record_reset(env, 76100000)
    loaded = cfg()
    l0 = lock.assert_shared_first_library(loaded['library_base'], 0, 0)
    meter = lock.PreflightMeter(dict(time_cap_s=30, env_cap=1024, model_cap=1))
    actual, traces = runner.realize_open_loop(
        env, 76100000, recorded, l0, meter, check_reward=False)
    assert actual.shape == (16,)
    assert np.allclose(actual, -8.0)
    assert traces[0] == [-0.5] * 16
    assert meter.env_steps == 256


def test_exact_resource_formulas_include_open_loop():
    counts = lock.budget(include_shared_open_loop=True, share_step0_scores=False)
    assert counts == dict(source_collection=15360, target_pool=1600, recede_control=2560,
                          shared_open_loop=10240, env_total=29760, imagined_total=655360,
                          time_cap_s=300, env_cap=29760, model_cap=655360)


def test_hard_cap_rejects_before_env_and_imagined_ops():
    env = MockEnv()
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=0, model_cap=15))
    with pytest.raises(RuntimeError, match='env-step cap would be exceeded'):
        runner.guarded_env_step(env, 1, meter)
    assert env.steps == 0
    assert meter.env_steps == 0
    assert meter.env_attempted == 1
    assert meter.env_interrupted == 1
    model = DummyModel()
    seq = lock.recede_candidates('fixed', 76200000, 76500000, 0, 0, 0)
    with pytest.raises(RuntimeError, match='imagined cap would be exceeded'):
        runner.score_library_guarded(model, np.zeros(2), seq, meter)
    assert model.calls == 0
    assert meter.model_states == 0
    assert meter.imagined_interrupted == 16


def test_imagined_batch_accounting_and_timeout():
    model = DummyModel()
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=10, model_cap=256))
    seq = lock.recede_candidates('fixed', 76200000, 76500000, 0, 0, 0)
    scores, first = runner.score_library_guarded(model, np.array([0.1, 0.0]), seq, meter)
    assert scores.shape == (16,)
    assert np.isfinite(scores).all()
    assert meter.model_states == 256
    assert model.calls == 16
    assert first.shape[0] == 16
    expired = runner.GuardedMeter(dict(time_cap_s=0.0, env_cap=10, model_cap=10))
    time.sleep(0.01)
    with pytest.raises(TimeoutError):
        expired.reserve_env(1)


def test_interrupted_env_step_stays_counted():
    class Boom(MockEnv):
        def step(self, action):
            raise RuntimeError('simulated interrupt')
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=4, model_cap=4))
    with pytest.raises(RuntimeError, match='simulated interrupt'):
        runner.guarded_env_step(Boom(), 0, meter)
    assert meter.env_steps == 1
    assert meter.env_interrupted == 1


def test_missing_duplicate_nonfinite_and_secondaries_cannot_relabel():
    good = [dict(state_index=k, returns={'multitask': {'fixed': 1.0, 'redraw': 0.0},
                                         'scratch': {'fixed': 0.0, 'redraw': 0.5}})
            for k in range(4)]
    cells = [dict(seed=s, states=good) for s in range(10)]
    out = lock.summarize(cells)
    assert out['label'] == 'h14_fixed_library_helps_multitask_relative'
    with pytest.raises(ValueError, match='incomplete or duplicated seed grid'):
        lock.summarize(cells[:9])
    with pytest.raises(ValueError, match='incomplete or duplicated seed grid'):
        lock.summarize(cells + [cells[0]])
    assert lock.classify_primary(0.0, -1.0, 1.0, 10) == 'h14_resampling_effect_not_established'
    assert lock.classify_primary(1.0, 0.5, 1.5, 10, complete=False) == 'incomplete'
    poisoned = dict(out)
    poisoned['groups'] = dict(out['groups'], secondaries={'multitask_minus_scratch_fixed': {'mean': 99.0}})
    assert lock.classify_primary(out['groups']['primary']['interval']['mean'],
                                 out['groups']['primary']['interval']['lo'],
                                 out['groups']['primary']['interval']['hi'], 10) == out['label']
    assert poisoned['label'] == out['label']


def test_planner_cannot_see_realized_returns():
    assert 'realized' not in inspect.signature(runner.score_library_guarded).parameters
    assert 'actual' not in inspect.signature(runner.score_library_guarded).parameters
    assert 'realized' not in inspect.signature(lock.score_library).parameters
    src = Path(runner.__file__).read_text(encoding='utf-8')
    assert 'later-state counterfactual' not in src


def test_controller_and_open_loop_traces_reconstruct():
    env = MockEnv(reward=-1.0)
    loaded = cfg()
    models = {'multitask': DummyModel(0.0), 'scratch': DummyModel(0.2)}
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=320, model_cap=16384))
    row = runner.evaluate_state(env, models, loaded, 0, 1, meter,
                                check_reward=False, score_fn=fast_score)
    assert set(row['returns']['multitask']) == {'fixed', 'redraw'}
    assert row['returns']['multitask']['fixed'] == -16.0
    assert len(row['open_loop']['actual']) == 16
    assert row['open_loop']['library_fingerprint'] == row['library_fingerprint']
    t0 = row['controllers']['multitask']['fixed']['traces'][0]
    t1 = row['controllers']['multitask']['redraw']['traces'][1]
    assert set(lock.TRACE_FIELDS) <= set(t0)
    assert t0['library_fingerprint'] == row['library_fingerprint']
    assert t1['library_fingerprint'] != t0['library_fingerprint']
    assert t0['candidate_seed'] == lock.shared_library_seed(loaded['library_base'], 0, 1)
    assert meter.env_steps == 320
    assert meter.model_states == 16384


def test_mock_grid_accounting_and_artifact_reconstruction(tmp_path):
    loaded = cfg()
    meter = runner.GuardedMeter(loaded)
    spec = object()
    priors = [object(), object(), object()]

    def train(cfg, spec, priors, seed, meter):
        return runner.train_seed_models(cfg, spec, priors, seed, meter,
                                        collect_fn=fake_collect, train_fn=fake_train,
                                        continue_fn=fake_continue, rms_fn=fake_rms)

    cells = runner.run_grid(loaded, meter, spec, priors, check_reward=False,
                            hooks=dict(train_seed_models=train, make_env=lambda spec: MockEnv(),
                                       score_fn=fast_score))
    assert meter.env_steps == 29760
    assert meter.model_states == 655360
    summary = runner.summarize_experiment(cells)
    assert summary['label'] == 'h14_resampling_effect_not_established'
    assert summary['groups']['primary']['metric'] == 'fixed_minus_redraw_relative_multitask_advantage'
    assert 'secondaries' in summary['groups']
    rebuilt = runner.summarize_experiment(json.loads(json.dumps(cells)))
    assert rebuilt['label'] == summary['label']
    assert rebuilt['groups']['primary']['per_seed'] == summary['groups']['primary']['per_seed']
    path = tmp_path / 'h14.json'
    payload = dict(complete=True, cells=cells, **summary)
    path.write_text(json.dumps(payload))
    loaded_payload = json.loads(path.read_text())
    assert runner.summarize_experiment(loaded_payload['cells'])['label'] == summary['label']


def test_unauthorized_execute_never_trains_or_builds_env():
    if lock.load_allocation().get('authorized') is True:
        pytest.skip('one-run allocation already flipped')
    runner.EVENTS.clear()
    with pytest.raises(PermissionError, match='fresh human approval'):
        runner.execute()
    with pytest.raises(PermissionError, match='fresh human approval'):
        runner.execute()
    assert 'authorized' not in runner.EVENTS
    assert 'make_task_env' not in runner.EVENTS
    assert not any(item.startswith('train:') for item in runner.EVENTS)
    assert not any(item.startswith('env:') for item in runner.EVENTS)
    assert not runner.OUTPUT.exists()
    assert lock.load_allocation()['authorized'] is False
    assert lock.load_allocation()['runs'] == 0
