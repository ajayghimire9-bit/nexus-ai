"""Adversarial source-only H15 readiness audit. No MountainCar env."""
from __future__ import annotations
import inspect
import json
import time
from pathlib import Path
import numpy as np
import pytest
from nexus.cl.metrics import seed_level_ci
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h15_candidate_reuse_confirm as lock
from nexus.world import h15_candidate_reuse_confirm_runner as runner
from nexus.world.data import TransitionDataset, collect_transitions


def fake_dataset(n, dim=2):
    return TransitionDataset(
        obs=np.zeros((n, dim), np.float32), action=np.zeros(n, np.int64),
        next_obs=np.zeros((n, dim), np.float32), reward=np.zeros(n, np.float32),
        terminated=np.zeros(n, np.bool_), truncated=np.zeros(n, np.bool_),
        task_id='toy', seed=np.zeros(n, np.int64), episode_id=np.zeros(n, np.int64),
        policy=np.array(['random'] * n), physics={'toy': 1.0},
    )


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
        self.obs = self.obs + 0.001
        self.state = self.obs.astype(np.float64)
        return self.obs.copy(), self.reward, False, False, {}

    def close(self):
        pass


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


class NanModel(DummyModel):
    def step(self, obs, action):
        arr = np.asarray(obs, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr * np.nan, np.zeros(arr.shape[0], dtype=np.float64)


class ToySpec:
    task_id = 'toy'
    n_actions = 3
    params = {'toy': 1.0}


def test_frozen_hashes_physics_and_77m_streams():
    from nexus.world.planning_value import sha
    assert sha(lock.CONFIG) == 'bc263e69e3a57ae3bcb4c27616f0c4736deaf123dab6c0c3cb49311b3804c193'
    assert sha(lock.PROTOCOL) == '4e5f7a5d0f55c6f183d1c78046597a99f5dfd8f788546a1d91c8270dad0116af'
    assert sha(lock.ALLOCATION) == '210f3a631a3081152f63e7a6b4d53bf98a2b8e157be52e515a7c7b5a53e39362'
    assert lock.holdout_from_rule() == [(0.004, 0.0021, 0.05)]
    assert lock.HOLD_RULE == 'mcc_candidate_reuse_confirm_v1'
    cfg = lock.load_config()
    streams, used = lock.seed_streams(cfg)
    assert min(used) == 77_000_000
    assert cfg['redraw_base'] == 77_500_000
    assert len(streams['redraw']) == 450
    for seed in range(10):
        for state in range(4):
            local = [cfg['redraw_base'] + 1000 * seed + 10 * state + step for step in range(1, 16)]
            assert len(set(local)) == 15
    rec = lock.load_allocation()
    assert rec['authorized'] is False
    assert rec['runs'] == 0
    _parent, h14_used = h14.seed_streams(h14.load_config())
    assert used & h14_used == set()


def test_actual_l0_matrices_match_across_four_h15_conditions():
    cfg = lock.load_config()
    for seed in range(10):
        for state in range(4):
            matrices = [h14.recede_candidates(mode, cfg['library_base'], cfg['redraw_base'],
                                              seed, state, 0)
                        for mode in lock.MODES for _arm in lock.ARMS]
            assert all(np.array_equal(matrices[0], item) for item in matrices)
            expected = candidate_sequences(
                h14.shared_library_seed(cfg['library_base'], seed, state), 16, 16, n_actions=3)
            assert np.array_equal(matrices[0], expected)
            later = h14.recede_candidates('redraw', cfg['library_base'], cfg['redraw_base'],
                                          seed, state, 1)
            registered = candidate_sequences(
                h14.redraw_step_seed(cfg['redraw_base'], seed, state, 1), 16, 16, n_actions=3)
            assert np.array_equal(later, registered)
            assert not np.array_equal(later, matrices[0])
            assert np.array_equal(
                h14.recede_candidates('fixed', cfg['library_base'], cfg['redraw_base'], seed, state, 7),
                matrices[0])
            other_arm = h14.recede_candidates('redraw', cfg['library_base'], cfg['redraw_base'],
                                              seed, state, 1)
            assert np.array_equal(later, other_arm)


def test_production_collector_uses_guarded_make_task_env():
    src = inspect.getsource(collect_transitions)
    assert 'make_task_env' in src
    env = MockEnv()
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=8, model_cap=1))
    ds = runner.guarded_collect(collect_transitions, ToySpec(), 4, (1,), 2, meter,
                                make_env_fn=lambda *a, **k: env)
    assert len(ds) == 4
    assert env.steps == 4
    assert meter.env_steps == 4


def test_short_collection_and_extra_inner_step_fail_closed():
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=8, model_cap=1))

    def short(spec, n_transitions, env_seeds, base_seed, mix=None):
        return fake_dataset(int(n_transitions) - 1)

    with pytest.raises(ValueError, match='collection length drifted'):
        runner.guarded_collect(short, object(), 4, (1,), 2, meter)
    env = MockEnv()

    def extra(spec, n_transitions, env_seeds, base_seed, mix=None):
        import nexus.world.data as data_mod
        built = data_mod.make_task_env(spec, seed=0)
        for _ in range(int(n_transitions) + 1):
            built.step(0)
        return fake_dataset(n_transitions)

    with pytest.raises(RuntimeError, match='collector would exceed reserved env steps'):
        runner.guarded_collect(extra, object(), 4, (1,), 2, meter,
                               make_env_fn=lambda *a, **k: env)
    assert env.steps == 4


def test_timeout_during_collection_and_control():
    meter = runner.GuardedMeter(dict(time_cap_s=0.05, env_cap=8, model_cap=1))

    def collect(spec, n_transitions, env_seeds, base_seed, mix=None):
        time.sleep(0.06)
        import nexus.world.data as data_mod
        env = data_mod.make_task_env(spec, seed=0)
        env.step(0)
        return fake_dataset(n_transitions)

    with pytest.raises(TimeoutError):
        runner.guarded_collect(collect, object(), 4, (1,), 2, meter,
                               make_env_fn=lambda *a, **k: MockEnv())
    expired = runner.GuardedMeter(dict(time_cap_s=0.0, env_cap=64, model_cap=8192))
    time.sleep(0.01)
    env = MockEnv()
    recorded = runner.record_reset(env, 77100000)
    with pytest.raises(TimeoutError):
        runner.recede_controller(
            env, DummyModel(), recorded, lock.load_config(), 0, 0, 'fixed', 'multitask',
            expired, check_reward=False,
            score_fn=lambda model, obs, sequences, meter: (np.arange(16, dtype=np.float64), None))
    assert env.steps == 0


def test_nonfinite_score_scoring_exception_and_library_mismatch():
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=10, model_cap=4096))
    seq = h14.recede_candidates('fixed', 77200000, 77500000, 0, 0, 0)
    with pytest.raises(RuntimeError, match='nonfinite|dropped'):
        runner.score_library_guarded(NanModel(), np.array([0.1, 0.0]), seq, meter)
    env = MockEnv()
    recorded = runner.record_reset(env, 77100000)
    cfg = lock.load_config()

    def boom_score(model, obs, sequences, meter):
        raise RuntimeError('score boom')

    with pytest.raises(RuntimeError, match='score boom'):
        runner.recede_controller(
            env, DummyModel(), recorded, cfg, 0, 0, 'fixed', 'multitask', meter,
            check_reward=False, score_fn=boom_score)
    l0 = h14.assert_shared_first_library(cfg['library_base'], 1, 1)
    wrong = h14.recede_candidates('redraw', cfg['library_base'], cfg['redraw_base'], 1, 1, 3)
    assert not np.array_equal(l0, wrong)


def test_reset_hidden_state_and_exact_cap_plus_one():
    env = MockEnv(obs0=(0.2, 0.0), hidden=(0.2, 0.0))
    recorded = runner.record_reset(env, 77100002)
    assert np.allclose(runner.assert_same_reset(env, 77100002, recorded), recorded['obs'])
    hidden = MockEnv(obs0=(0.2, 0.0), hidden=(0.2, 0.0), mismatch_hidden=True)
    first = runner.record_reset(hidden, 7)
    with pytest.raises(RuntimeError, match='hidden-state'):
        runner.assert_same_reset(hidden, 7, first)
    counts = lock.budget(include_shared_open_loop=True, share_step0_scores=False)
    assert counts['env_total'] == 29760
    assert counts['imagined_total'] == 655360
    cap = runner.GuardedMeter(dict(time_cap_s=30, env_cap=1, model_cap=256))
    cap.reserve_env(1)
    with pytest.raises(RuntimeError, match='env-step cap would be exceeded'):
        cap.reserve_env(1)
    imag = runner.GuardedMeter(dict(time_cap_s=30, env_cap=1, model_cap=256))
    imag.reserve_imagined(256)
    with pytest.raises(RuntimeError, match='imagined cap would be exceeded'):
        imag.reserve_imagined(1)


def test_primary_labels_boundaries_missing_mode_and_no_h14_pool():
    def cells_from_means(means):
        states = [dict(state_index=k, returns={
            'multitask': {'fixed': means[0], 'redraw': means[2]},
            'scratch': {'fixed': means[1], 'redraw': means[3]}}) for k in range(4)]
        return [dict(seed=s, states=states) for s in range(10)]

    positive = lock.summarize(cells_from_means((2.0, 0.0, 0.0, 0.0)))
    assert positive['label'] == 'h15_fixed_library_helps_multitask_relative'
    assert positive['groups']['primary']['interval']['n'] == 10
    assert positive['groups']['primary']['interval']['df'] == 9
    rebuilt = seed_level_ci([2.0] * 10)
    assert rebuilt['df'] == 9 and rebuilt['lo'] > 0
    negative = lock.summarize(cells_from_means((0.0, 0.0, 2.0, 0.0)))
    assert negative['label'] == 'h15_redraw_helps_multitask_relative'
    zero = lock.summarize(cells_from_means((1.0, 1.0, 1.0, 1.0)))
    assert zero['label'] == 'h15_resampling_effect_not_established'
    assert lock.classify_primary(0.4, 0.0, 0.8, 10) == 'h15_resampling_effect_not_established'
    assert lock.classify_primary(-0.4, -0.8, 0.0, 10) == 'h15_resampling_effect_not_established'
    assert lock.classify_primary(1.0, 0.5, 1.5, 10, complete=False) == 'incomplete'
    with pytest.raises(ValueError, match='incomplete or duplicated'):
        lock.summarize(cells_from_means((1, 0, 0, 0)) + [dict(seed=0, states=[])])
    with pytest.raises(ValueError, match='missing arm/mode'):
        h14.difference_in_differences({('multitask', 'fixed'): 1.0, ('scratch', 'fixed'): 0.0,
                                       ('multitask', 'redraw'): 0.0})
    nan_states = [dict(state_index=k, returns={
        'multitask': {'fixed': float('nan'), 'redraw': 0.0},
        'scratch': {'fixed': 0.0, 'redraw': 0.0}}) for k in range(4)]
    with pytest.raises(ValueError, match='nonfinite'):
        h14.mean_seed_returns(nan_states)
    positive['groups']['secondaries'] = {'multitask_minus_scratch_fixed': {'mean': -99.0}}
    assert lock.classify_primary(2.0, positive['groups']['primary']['interval']['lo'],
                                 positive['groups']['primary']['interval']['hi'], 10) == (
        'h15_fixed_library_helps_multitask_relative')
    assert not str(positive['label']).startswith('h14_')


def test_training_recipe_and_planner_blindness():
    cfg = lock.load_config()
    seen = []

    def collect(spec, n_transitions, env_seeds, base_seed, mix=None):
        seen.append(('collect', n_transitions, env_seeds[0], base_seed))
        return fake_dataset(n_transitions)

    def train(train_ds, val_ds, **kwargs):
        seen.append(('train', kwargs['seed'], kwargs['epochs'], kwargs['hidden'],
                     kwargs['n_actions'], kwargs['lr'], kwargs['kind'], len(train_ds), len(val_ds)))
        return DummyModel(), {}

    def cont(model, train_ds, val_ds, **kwargs):
        seen.append(('continue', kwargs['seed'], kwargs['epochs'], kwargs['lr'], len(train_ds), len(val_ds)))

    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=2000, model_cap=1))
    models = runner.train_seed_models(
        cfg, object(), [object(), object(), object()], 2, meter,
        collect_fn=collect, train_fn=train, continue_fn=cont, rms_fn=lambda obs: object())
    assert set(models) == {'multitask', 'scratch'}
    assert [row[1] for row in seen if row[0] == 'collect'] == [512, 512, 512, 128, 32]
    assert seen[0][2] == cfg['collect_source_base'] + 120 * 2
    assert ('train', 5 + 19 * 2, 15, (64, 64), 3, 0.001, 'residual', 1504, 32) in seen
    assert ('train', 5 + 19 * 2, 20, (64, 64), 3, 0.001, 'residual', 128, 32) in seen
    assert ('continue', 7 + 19 * 2, 20, 0.001, 128, 32) in seen
    assert 'realized' not in inspect.signature(runner.score_library_guarded).parameters
    assert 'actual' not in inspect.signature(runner.score_library_guarded).parameters


def test_incomplete_and_overwrite_never_succeed(tmp_path):
    existing = tmp_path / 'h15.json'
    existing.write_text('{"complete":true,"label":"h15_fixed_library_helps_multitask_relative"}')
    before = existing.read_text()

    def require(cfg):
        return None

    with pytest.raises(RuntimeError, match='refusing H15 overwrite'):
        runner.execute(hooks=dict(require_allocation=require, output=str(existing),
                                  skip_git_guards=True))
    assert existing.read_text() == before
    dest = tmp_path / 'partial.json'

    def boom_train(cfg, spec, priors, seed, meter):
        raise RuntimeError('forced interrupt')

    payload = runner.execute(hooks=dict(
        require_allocation=require, output=str(dest), skip_git_guards=True,
        spec=object(), priors=[object(), object(), object()],
        train_seed_models=boom_train, skip_reward_check=True))
    assert payload['complete'] is False
    assert payload['label'] == 'incomplete'
    saved = json.loads(dest.read_text())
    assert saved['complete'] is False
    assert saved['label'] == 'incomplete'
    assert 'forced interrupt' in saved['failure']['message']


def test_unauthorized_execute_fails_before_construction():
    runner.EVENTS.clear()
    with pytest.raises(PermissionError, match='fresh human approval'):
        runner.execute()
    assert runner.EVENTS[:2] == ['load_config', 'require_allocation']
    assert 'authorized' not in runner.EVENTS
    assert 'make_task_env' not in runner.EVENTS
    assert not any(item.startswith('train:') for item in runner.EVENTS)
    assert lock.load_allocation()['authorized'] is False
    assert lock.load_allocation()['runs'] == 0
    assert not Path('artifacts/h15_candidate_reuse_confirm.json').exists()
    src = Path('scripts/run_h15_candidate_reuse_confirm.py').read_text(encoding='utf-8')
    assert 'if args.execute' in src
    assert 'runner.execute()' in src
