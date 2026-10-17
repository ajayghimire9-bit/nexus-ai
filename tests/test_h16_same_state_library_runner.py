"""Source-only H16 runner tests. No MountainCar env, no training."""
from __future__ import annotations
import inspect
import json
import time
from pathlib import Path
import numpy as np
import pytest
from nexus.world.data import TransitionDataset
from nexus.world.planning_value import sha
from nexus.world import h16_same_state_library as lock
from nexus.world import h16_same_state_library_runner as runner
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h15_candidate_reuse_confirm as h15


class DummyModel:
    def __init__(self, bias=0.0):
        self.bias = float(bias)
        self.calls = 0
        self.seen_realized = False

    def copy_rms(self, rms):
        self.rms = rms

    def step(self, obs, action):
        self.calls += 1
        arr = np.asarray(obs, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr + self.bias, np.zeros(arr.shape[0], dtype=np.float64)


class MockEnv:
    def __init__(self, reward=-0.25, terminate_after=None, drift_state=False,
                 drift_elapsed=False, drift_reward=False):
        self.reward = float(reward)
        self.terminate_after = terminate_after
        self.drift_state = drift_state
        self.drift_elapsed = drift_elapsed
        self.drift_reward = drift_reward
        self.resets = 0
        self.steps = 0
        self._elapsed_steps = 0
        self.state = np.zeros(2, dtype=np.float32)
        self.unwrapped = self
        self.wrapper_names = list(lock.REQUIRED_WRAPPERS)
        self._seed = 0

    def reset(self, seed=None):
        self.resets += 1
        self._seed = int(seed or 0)
        rng = np.random.default_rng(self._seed)
        self.state = rng.normal(size=2).astype(np.float32)
        if self.drift_state and self.resets > 1:
            self.state = self.state + np.float32(0.5)
        self._elapsed_steps = 2 if self.drift_elapsed and self.resets > 1 else 0
        self.steps = 0
        return self.state.copy(), {}

    def step(self, action):
        if self.steps >= 100 and self.terminate_after is None:
            pass
        self.steps += 1
        self._elapsed_steps += 1 if not self.drift_elapsed else 2
        self.state = (self.state + np.float32(0.01 * (int(action) + 1))).astype(np.float32)
        terminated = self.terminate_after is not None and self.steps >= int(self.terminate_after)
        reward = self.reward + (0.3 if self.drift_reward and self.resets > 1 else 0.0)
        return self.state.copy(), float(reward), bool(terminated), False, {}

    def close(self):
        pass


def fake_dataset(n, dim=2):
    return TransitionDataset(
        obs=np.zeros((n, dim), np.float32), action=np.zeros(n, np.int64),
        next_obs=np.zeros((n, dim), np.float32), reward=np.zeros(n, np.float32),
        terminated=np.zeros(n, np.bool_), truncated=np.zeros(n, np.bool_),
        task_id='toy', seed=np.zeros(n, np.int64), episode_id=np.zeros(n, np.int64),
        policy=np.array(['random'] * n), physics={'toy': 1.0})


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
    return np.arange(lock.N_CAND, dtype=np.float64) + float(getattr(model, 'bias', 0.0))


def train_hook(cfg, spec, priors, seed, meter):
    return runner.train_seed_models(cfg, spec, priors, seed, meter,
                                    collect_fn=fake_collect, train_fn=fake_train,
                                    continue_fn=fake_continue, rms_fn=fake_rms)


def test_frozen_lock_hashes_and_unauthorized_execute():
    assert sha(lock.CONFIG) == lock.LOCKED_CONFIG
    assert sha(lock.PROTOCOL) == lock.LOCKED_PROTOCOL
    assert lock.LOCKED_TARGET == (0.0015, 0.0014, 0.055)
    rec = lock.load_allocation()
    if rec.get('authorized') is False:
        assert sha(lock.ALLOCATION) == '02d4680d308ad17384ecd148ce48b7e319cffa4710be8304165ebc847d7474fd'
        assert rec['runs'] == 0
        runner.EVENTS.clear()
        with pytest.raises(PermissionError, match='fresh human approval'):
            runner.execute()
        assert 'authorized' not in runner.EVENTS
        assert 'make_task_env' not in runner.EVENTS
        assert not any(item.startswith('train:') for item in runner.EVENTS)
    else:
        assert rec['authorized'] is True and rec['runs'] == 1
        assert rec.get('one_run_usage_record')
    assert not runner.OUTPUT.exists()


def test_l0_redraw_identity_and_seed_disjointness():
    cfg = lock.load_config()
    streams, used = lock.seed_streams(cfg)
    assert len(streams['redraw']) == 80
    assert min(used) >= 78_000_000
    h14_used = h14.seed_streams(__import__('yaml').safe_load(h14.CONFIG.read_text()))[1]
    h15_used = h15.seed_streams(__import__('yaml').safe_load(h15.CONFIG.read_text()))[1]
    assert used & h14_used == set()
    assert used & h15_used == set()
    l0_a, mat_a = lock.library_for('l0', cfg['library_base'], cfg['redraw_base'], 2, 1, 8)
    l0_b, mat_b = lock.library_for('l0', cfg['library_base'], cfg['redraw_base'], 2, 1, 12)
    assert l0_a == l0_b and np.array_equal(mat_a, mat_b)
    red8 = lock.library_for('redraw', cfg['library_base'], cfg['redraw_base'], 2, 1, 8)[1]
    red12 = lock.library_for('redraw', cfg['library_base'], cfg['redraw_base'], 2, 1, 12)[1]
    assert not np.array_equal(mat_a, red8)
    assert not np.array_equal(red8, red12)


def test_reference_and_exact_replay():
    cfg = lock.load_config()
    env = MockEnv()
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1))
    ref = runner.record_reference(env, cfg, 0, 1, meter, check_reward=False)
    assert set(ref['snapshots']) == {8, 12}
    assert ref['snapshots'][8]['elapsed_steps'] == 8
    assert ref['snapshots'][12]['elapsed_steps'] == 12
    assert meter.env_steps == 12
    replayed = runner.replay_to_later(env, ref, 8, meter, check_reward=False)
    assert replayed['elapsed_steps'] == 8
    assert np.array_equal(replayed['later_obs'], ref['snapshots'][8]['later_obs'])
    assert np.array_equal(replayed['later_state'], ref['snapshots'][8]['later_state'])


def test_restoration_failures():
    cfg = lock.load_config()
    drifted = MockEnv(drift_state=True)
    ref = runner.record_reference(drifted, cfg, 1, 0,
                                  runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1)),
                                  check_reward=False)
    with pytest.raises(RuntimeError, match='reset_obs|reset_state|later_state|later_obs'):
        runner.replay_to_later(drifted, ref, 8,
                               runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1)),
                               check_reward=False)
    clean = runner.record_reference(MockEnv(), cfg, 1, 0,
                                    runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1)),
                                    check_reward=False)
    with pytest.raises(RuntimeError, match='elapsed_steps'):
        runner.replay_to_later(MockEnv(drift_elapsed=True), clean, 8,
                               runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1)),
                               check_reward=False)
    rewarded = MockEnv(drift_reward=True)
    ref_r = runner.record_reference(rewarded, cfg, 2, 0,
                                    runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1)),
                                    check_reward=False)
    with pytest.raises(RuntimeError, match='prefix reward'):
        runner.replay_to_later(rewarded, ref_r, 8,
                               runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1)),
                               check_reward=False)
    with pytest.raises(RuntimeError, match='reference prefix ended'):
        runner.record_reference(MockEnv(terminate_after=3), cfg, 0, 0,
                                runner.GuardedMeter(dict(time_cap_s=30, env_cap=16, model_cap=1)),
                                check_reward=False)


def test_score_before_truth_shared_returns_and_algebra():
    cfg = lock.load_config()
    models = {'multitask': DummyModel(0.0), 'scratch': DummyModel(1.0)}
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=4000, model_cap=2048))
    group = runner.evaluate_reset_group(
        MockEnv(), models, cfg, 0, 0, meter, check_reward=False, score_fn=fast_score)
    assert len(group['later_states']) == 2
    row = group['later_states'][0]
    l0 = row['libraries']['l0']
    assert l0['selected']['multitask']['index'] == 15
    assert len(l0['realized']) == 16
    assert l0['oracle'] == pytest.approx(max(l0['realized']))
    lock.oracle_cancels_in_arm_gap(l0['realized'], l0['predicted_scores']['multitask'],
                                   l0['predicted_scores']['scratch'])
    seq = np.zeros((16, 16), dtype=np.int64)
    seq[0, 0] = 2
    scores = np.ones(16)
    assert lock.selected_index(scores) == 0
    assert 'realized' not in inspect.signature(runner.score_library_guarded).parameters


def test_seed_level_aggregation_and_incomplete_grids():
    cells = []
    for seed in range(10):
        later = [dict(state_index=k, later_t=t, s_mt_l0=-1.0 + 0.02 * seed,
                      s_sc_l0=-1.2, s_mt_redraw=-1.3, s_sc_redraw=-1.25,
                      libraries={'l0': _lib(), 'redraw': _lib()})
                 for k in range(4) for t in (8, 12)]
        cells.append(dict(seed=seed, later_states=later))
    out = runner.summarize_experiment(cells)
    assert out['label'] == 'h16_l0_helps_multitask_relative_same_state'
    assert out['groups']['primary']['interval']['df'] == 9
    assert 'secondaries' in out['groups']
    assert lock.classify_primary(out['groups']['primary']['interval']['mean'],
                                 out['groups']['primary']['interval']['lo'],
                                 out['groups']['primary']['interval']['hi'], 10) == out['label']
    with pytest.raises(ValueError, match='incomplete or duplicated seed'):
        lock.mean_seed_cells(cells[:9])
    with pytest.raises(ValueError, match='incomplete or duplicated seed'):
        lock.mean_seed_cells(cells + [cells[0]])


def _lib():
    realized = np.linspace(-2.0, -0.5, 16).tolist()
    scores = list(reversed(realized))
    seq = np.zeros((16, 16), dtype=np.int64).tolist()
    return dict(oracle=-0.5, realized=realized, sequences=seq,
                predicted_scores={'multitask': scores, 'scratch': scores},
                regret={'multitask': 0.0, 'scratch': 0.0})


def test_exact_budget_and_cap_plus_one():
    cfg = lock.load_config()
    meter = runner.GuardedMeter(cfg)
    cells = runner.run_grid(cfg, meter, object(), [object(), object(), object()],
                            check_reward=False, check_wrappers=False,
                            hooks=dict(train_seed_models=train_hook, make_env=lambda spec: MockEnv(),
                                       score_fn=fast_score, skip_wrapper_check=True))
    assert meter.env_steps == 84000
    assert meter.model_states == 81920
    assert len(cells) == 10
    assert len(cells[0]['later_states']) == 8
    env = MockEnv()
    blocked = runner.GuardedMeter(dict(time_cap_s=30, env_cap=0, model_cap=1))
    with pytest.raises(RuntimeError, match='env-step cap would be exceeded'):
        runner.guarded_env_step(env, 1, blocked)
    assert env.steps == 0
    assert blocked.env_attempted == 1
    assert blocked.env_interrupted == 1


def test_collector_overrun_timeout_overwrite_and_incomplete(tmp_path):
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=4, model_cap=4))
    created = []

    def make_env(*args, **kwargs):
        env = MockEnv()
        created.append(env)
        return env

    def over_collect(spec, n_transitions, env_seeds, base_seed, mix=None):
        import nexus.tasks.spec as spec_mod
        env = spec_mod.make_task_env(spec)
        for _ in range(int(n_transitions) + 1):
            env.step(0)
        return fake_dataset(n_transitions)

    with pytest.raises(RuntimeError, match='collector would exceed'):
        runner.guarded_collect(over_collect, object(), 2, (1,), 2, meter, make_env_fn=make_env)
    assert created[0].steps == 2
    expired = runner.GuardedMeter(dict(time_cap_s=0.0, env_cap=10, model_cap=10))
    time.sleep(0.01)
    with pytest.raises(TimeoutError):
        expired.reserve_env(1)
    existing = tmp_path / 'exists.json'
    existing.write_text('{}')
    with pytest.raises(RuntimeError, match='overwrite'):
        runner.execute(hooks=dict(require_allocation=lambda cfg: None, output=existing,
                                  skip_git_guards=True))
    out = tmp_path / 'partial.json'

    def boom(*args, **kwargs):
        raise RuntimeError('simulated interrupt')

    payload = runner.execute(hooks=dict(
        require_allocation=lambda cfg: None, output=out, skip_git_guards=True,
        train_seed_models=boom, make_env=lambda spec: MockEnv(),
        priors=[object(), object(), object()], spec=object(),
        skip_reward_check=True, skip_wrapper_check=True))
    assert payload['complete'] is False
    assert payload['label'] == 'incomplete'
    assert payload['failure']['type'] == 'RuntimeError'
    saved = json.loads(out.read_text())
    assert saved['complete'] is False
    assert saved['counts']['events']
