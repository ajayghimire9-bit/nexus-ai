"""Adversarial source-only H14 readiness audit. No MountainCar env."""
from __future__ import annotations
import json
import time
from pathlib import Path
import numpy as np
import pytest
from nexus.cl.metrics import seed_level_ci
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world import h14_candidate_reuse as lock
from nexus.world import h14_candidate_reuse_runner as runner
from nexus.world.data import TransitionDataset


def fake_dataset(n, dim=2):
    return TransitionDataset(
        obs=np.zeros((n, dim), np.float32), action=np.zeros(n, np.int64),
        next_obs=np.zeros((n, dim), np.float32), reward=np.zeros(n, np.float32),
        terminated=np.zeros(n, np.bool_), truncated=np.zeros(n, np.bool_),
        task_id='toy', seed=np.zeros(n, np.int64), episode_id=np.zeros(n, np.int64),
        policy=np.array(['random'] * n), physics={'toy': 1.0},
    )


class MockEnv:
    def __init__(self, obs0=(0.1, 0.0), reward=-1.0):
        self.obs0 = np.asarray(obs0, dtype=np.float32)
        self.obs = self.obs0.copy()
        self.state = self.obs0.astype(np.float64).copy()
        self.unwrapped = self
        self.reward = float(reward)
        self.steps = 0

    def reset(self, seed=None):
        self.obs = self.obs0.copy()
        self.state = self.obs0.astype(np.float64).copy()
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

    def copy_rms(self, rms):
        self.rms = rms

    def step(self, obs, action):
        arr = np.asarray(obs, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr + self.bias, np.zeros(arr.shape[0], dtype=np.float64)


def test_locked_hashes_physics_and_76m_streams():
    from nexus.world.planning_value import sha
    assert sha(lock.CONFIG) == 'df155e89b8a4810bdbf04cfc121e93de7c9900235a440057dd66f7128459f81a'
    assert sha(lock.PROTOCOL) == '1005e12568f3457f32638f9c7a08b0c29c7090785bf1085d097054224a012c1b'
    assert sha(lock.ALLOCATION) == '4155621de732cdc9b9a6cda3d478c3f6aab89693be6cb430ca10a350253cff51'
    assert lock.holdout_from_rule() == [(0.0023, 0.0019, 0.065)]
    cfg = lock.load_config()
    streams, used = lock.seed_streams(cfg)
    assert min(used) == 76000000
    assert cfg['redraw_base'] == 76500000
    # Locked formula 1000s+10k+t aliases across states of one seed (450 unique, 600 slots).
    assert len(streams['redraw']) == 450
    for seed in range(10):
        for state in range(4):
            local = [cfg['redraw_base'] + 1000 * seed + 10 * state + step for step in range(1, 16)]
            assert len(set(local)) == 15
    rec = lock.load_allocation()
    assert rec['authorized'] is False and rec['runs'] == 0


def test_actual_l0_matrices_match_across_four_conditions():
    cfg = lock.load_config()
    for seed in range(10):
        for state in range(4):
            matrices = [lock.recede_candidates(mode, cfg['library_base'], cfg['redraw_base'],
                                               seed, state, 0)
                        for mode in lock.MODES for _arm in lock.ARMS]
            assert all(np.array_equal(matrices[0], item) for item in matrices)
            expected = candidate_sequences(
                lock.shared_library_seed(cfg['library_base'], seed, state), 16, 16, n_actions=3)
            assert np.array_equal(matrices[0], expected)
            later = lock.recede_candidates('redraw', cfg['library_base'], cfg['redraw_base'],
                                           seed, state, 1)
            registered = candidate_sequences(
                lock.redraw_step_seed(cfg['redraw_base'], seed, state, 1), 16, 16, n_actions=3)
            assert np.array_equal(later, registered)
            assert not np.array_equal(later, matrices[0])
            assert np.array_equal(
                lock.recede_candidates('fixed', cfg['library_base'], cfg['redraw_base'], seed, state, 7),
                matrices[0])


def test_first_decision_fixed_and_redraw_match_under_deterministic_model():
    cfg = lock.load_config()
    env = MockEnv()
    model = DummyModel(0.0)
    recorded = runner.record_reset(env, int(cfg['state_reset_base']))
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=8192))

    def score(model, obs, sequences, meter):
        meter.reserve_imagined(256)
        return np.arange(16, dtype=np.float64), None

    fixed, fixed_tr = runner.recede_controller(
        env, model, recorded, cfg, 0, 0, 'fixed', 'multitask', meter,
        check_reward=False, score_fn=score)
    redraw, redraw_tr = runner.recede_controller(
        env, model, recorded, cfg, 0, 0, 'redraw', 'scratch', meter,
        check_reward=False, score_fn=score)
    assert fixed_tr[0]['library_fingerprint'] == redraw_tr[0]['library_fingerprint']
    assert fixed_tr[0]['executed_action'] == redraw_tr[0]['executed_action']
    assert fixed_tr[1]['library_fingerprint'] != redraw_tr[1]['library_fingerprint']
    assert fixed == redraw == -16.0


def test_training_recipe_seeds_target_size_and_source_count():
    cfg = lock.load_config()
    seen = []

    def collect(spec, n_transitions, env_seeds, base_seed, mix=None):
        seen.append(('collect', n_transitions, env_seeds[0], base_seed))
        return fake_dataset(n_transitions)

    def train(train_ds, val_ds, **kwargs):
        seen.append(('train', kwargs['seed'], kwargs['epochs'], kwargs['hidden'],
                     kwargs['n_actions'], len(train_ds), len(val_ds)))
        return DummyModel(), {}

    def cont(model, train_ds, val_ds, **kwargs):
        seen.append(('continue', kwargs['seed'], kwargs['epochs'], len(train_ds), len(val_ds)))

    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=2000, model_cap=1))
    models = runner.train_seed_models(
        cfg, object(), [object(), object(), object()], 2, meter,
        collect_fn=collect, train_fn=train, continue_fn=cont, rms_fn=lambda obs: object())
    assert set(models) == {'multitask', 'scratch'}
    assert [row[1] for row in seen if row[0] == 'collect'] == [512, 512, 512, 128, 32]
    assert ('train', 5 + 19 * 2, 15, (64, 64), 3, 1504, 32) in seen
    assert ('train', 5 + 19 * 2, 20, (64, 64), 3, 128, 32) in seen
    assert ('continue', 7 + 19 * 2, 20, 128, 32) in seen
    with pytest.raises(ValueError, match='source count'):
        runner.train_seed_models(cfg, object(), [object()], 0, meter,
                                 collect_fn=collect, train_fn=train, continue_fn=cont,
                                 rms_fn=lambda obs: object())


def test_primary_ci_df9_boundaries_and_secondaries_cannot_relabel():
    def cells_from_means(means):
        states = [dict(state_index=k, returns={
            'multitask': {'fixed': means[0], 'redraw': means[2]},
            'scratch': {'fixed': means[1], 'redraw': means[3]}}) for k in range(4)]
        return [dict(seed=s, states=states) for s in range(10)]

    positive = lock.summarize(cells_from_means((2.0, 0.0, 0.0, 0.0)))
    assert positive['label'] == 'h14_fixed_library_helps_multitask_relative'
    assert positive['groups']['primary']['interval']['n'] == 10
    assert positive['groups']['primary']['interval']['df'] == 9
    rebuilt = seed_level_ci([2.0] * 10)
    assert rebuilt['df'] == 9 and rebuilt['lo'] > 0
    negative = lock.summarize(cells_from_means((0.0, 0.0, 2.0, 0.0)))
    assert negative['label'] == 'h14_redraw_helps_multitask_relative'
    zero = lock.summarize(cells_from_means((1.0, 1.0, 1.0, 1.0)))
    assert zero['label'] == 'h14_resampling_effect_not_established'
    assert lock.classify_primary(0.4, 0.0, 0.8, 10) == 'h14_resampling_effect_not_established'
    assert lock.classify_primary(-0.4, -0.8, 0.0, 10) == 'h14_resampling_effect_not_established'
    assert lock.classify_primary(1.0, 0.5, 1.5, 10, complete=False) == 'incomplete'
    with pytest.raises(ValueError, match='incomplete or duplicated'):
        lock.summarize(cells_from_means((1, 0, 0, 0)) + [dict(seed=0, states=[])])
    nan_states = [dict(state_index=k, returns={
        'multitask': {'fixed': float('nan'), 'redraw': 0.0},
        'scratch': {'fixed': 0.0, 'redraw': 0.0}}) for k in range(4)]
    with pytest.raises(ValueError, match='nonfinite'):
        lock.mean_seed_returns(nan_states)
    positive['groups']['secondaries'] = {'multitask_minus_scratch_fixed': {'mean': -99.0}}
    assert lock.classify_primary(2.0, positive['groups']['primary']['interval']['lo'],
                                 positive['groups']['primary']['interval']['hi'], 10) == (
        'h14_fixed_library_helps_multitask_relative')


def test_extra_collector_step_is_rejected_before_it_runs():
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=8, model_cap=1))
    env = MockEnv()

    def extra_collect(spec, n_transitions, env_seeds, base_seed, mix=None):
        import nexus.world.data as data_mod
        built = data_mod.make_task_env(spec, seed=0)
        for _ in range(int(n_transitions) + 1):
            built.step(0)
        return fake_dataset(n_transitions)

    with pytest.raises(RuntimeError, match='collector would exceed reserved env steps'):
        runner.guarded_collect(extra_collect, object(), 4, (1,), 2, meter,
                               make_env_fn=lambda *a, **k: env)
    assert env.steps == 4
    assert meter.env_steps == 4


def test_imagined_batch_larger_than_remaining_budget():
    model = DummyModel()
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=1, model_cap=15))
    seq = lock.recede_candidates('fixed', 76200000, 76500000, 0, 0, 0)
    with pytest.raises(RuntimeError, match='imagined cap would be exceeded'):
        runner.score_library_guarded(model, np.zeros(2), seq, meter)
    assert meter.model_states == 0


def test_timeout_during_collection_is_incomplete():
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
    assert meter.env_steps == 4


def test_failed_reset_missing_trace_and_wrong_library_are_rejected():
    env = MockEnv(obs0=(0.4, 0.0))
    recorded = {'obs': np.array([0.1, 0.0], dtype=np.float32), 'state': np.array([0.1, 0.0])}
    with pytest.raises(RuntimeError, match='reset identity'):
        runner.assert_same_reset(env, 1, recorded)
    with pytest.raises(ValueError, match='missing trace'):
        lock.controller_trace(seed=0, state_index=0)
    cfg = lock.load_config()
    l0 = lock.assert_shared_first_library(cfg['library_base'], 1, 1)
    wrong = lock.recede_candidates('redraw', cfg['library_base'], cfg['redraw_base'], 1, 1, 3)
    assert not np.array_equal(l0, wrong)


def test_partial_artifact_and_overwrite_refuse(tmp_path):
    existing = tmp_path / 'h14.json'
    existing.write_text('{"complete":false,"label":"incomplete"}')
    before = existing.read_text()

    def require(cfg):
        return None

    with pytest.raises(RuntimeError, match='refusing H14 overwrite'):
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
    assert saved['label'] == 'incomplete'
    assert saved['complete'] is False
    assert 'forced interrupt' in saved['failure']['message']


def test_unauthorized_execute_still_fails_before_construction():
    runner.EVENTS.clear()
    with pytest.raises(PermissionError):
        runner.execute()
    assert 'authorized' not in runner.EVENTS
    assert 'make_task_env' not in runner.EVENTS
    assert lock.load_allocation()['authorized'] is False
    assert lock.load_allocation()['runs'] == 0
    assert not Path('artifacts/h14_candidate_reuse.json').exists()
