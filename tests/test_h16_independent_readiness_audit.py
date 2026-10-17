"""Adversarial source-only H16 readiness audit. No MountainCar env."""
from __future__ import annotations
import inspect
import json
import time
from pathlib import Path
import numpy as np
import pytest
from nexus.cl.metrics import seed_level_ci
from nexus.world.data import TransitionDataset, collect_transitions
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h15_candidate_reuse_confirm as h15
from nexus.world import h16_same_state_library as lock
from nexus.world import h16_same_state_library_runner as runner


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


class MockEnv:
    def __init__(self, reward=-0.25, terminate_after=None, drift_state=False,
                 drift_elapsed=False, drift_reward=False, hidden_offset=0.0):
        self.reward = float(reward)
        self.terminate_after = terminate_after
        self.drift_state = drift_state
        self.drift_elapsed = drift_elapsed
        self.drift_reward = drift_reward
        self.hidden_offset = float(hidden_offset)
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
            self.state = self.state + np.float32(self.hidden_offset or 0.5)
        self._elapsed_steps = 2 if self.drift_elapsed and self.resets > 1 else 0
        self.steps = 0
        return self.state.copy(), {}

    def step(self, action):
        self.steps += 1
        self._elapsed_steps += 1 if not self.drift_elapsed else 2
        self.state = (self.state + np.float32(0.01 * (int(action) + 1))).astype(np.float32)
        terminated = self.terminate_after is not None and self.steps >= int(self.terminate_after)
        reward = self.reward + (0.3 if self.drift_reward and self.resets > 1 else 0.0)
        return self.state.copy(), float(reward), bool(terminated), False, {}

    def close(self):
        pass


class ToySpec:
    task_id = 'toy'
    n_actions = 3
    params = {'toy': 1.0}


def fake_dataset(n, dim=2):
    return TransitionDataset(
        obs=np.zeros((n, dim), np.float32), action=np.zeros(n, np.int64),
        next_obs=np.zeros((n, dim), np.float32), reward=np.zeros(n, np.float32),
        terminated=np.zeros(n, np.bool_), truncated=np.zeros(n, np.bool_),
        task_id='toy', seed=np.zeros(n, np.int64), episode_id=np.zeros(n, np.int64),
        policy=np.array(['random'] * n), physics={'toy': 1.0},
    )


def later_row(seed, values):
    later = []
    for k in range(4):
        for t in (8, 12):
            later.append(dict(
                seed=seed, state_index=k, later_t=t,
                s_mt_l0=values[0], s_sc_l0=values[1],
                s_mt_redraw=values[2], s_sc_redraw=values[3],
            ))
    return dict(seed=seed, later_states=later)


def test_frozen_hashes_closed_parents_and_unauthorized_allocation():
    assert sha(lock.CONFIG) == 'e71b0053331afa39db5b368510c8524d23e454fb490a2bde57e72ac39f32834c'
    assert sha(lock.PROTOCOL) == 'f757e8a8e1f08d0b5abeb7cffa84071a79e1c5e93ded89b6817fe25e8f7fcea7'
    assert sha(lock.ALLOCATION) == '02d4680d308ad17384ecd148ce48b7e319cffa4710be8304165ebc847d7474fd'
    rec = lock.load_allocation()
    assert rec['authorized'] is False and rec['runs'] == 0
    assert lock.LOCKED_TARGET == (0.0015, 0.0014, 0.055)
    assert lock.holdout_from_rule() == [lock.LOCKED_TARGET]
    assert lock.HOLD_RULE == 'mcc_same_state_library_v1'
    cfg = lock.load_config()
    assert cfg['env_cap'] == 84000 and cfg['model_cap'] == 81920 and cfg['time_cap_s'] == 300
    assert cfg['restore_method'] == 'reset_plus_action_prefix'
    assert cfg['direct_state_mutation'] is False
    lock.assert_parents_frozen()
    h14_alloc = json.loads(h14.ALLOCATION.read_text())
    h15_alloc = json.loads(h15.ALLOCATION.read_text())
    assert h14_alloc['authorized'] is True and int(h14_alloc['runs']) == 1
    assert h15_alloc['authorized'] is True and int(h15_alloc['runs']) == 1
    assert h15_alloc.get('consumed') is True
    prep = lock.prep()
    assert prep['session_ledger'] == {'used_s': 303.777, 'remaining_s': 3296.223, 'unchanged': True}
    assert runner.prep()['authorized'] is False
    assert runner.prep()['runner_implemented'] is True


def test_unauthorized_cli_and_lock_execute_fail_before_construction():
    runner.EVENTS.clear()
    with pytest.raises(PermissionError, match='fresh human approval'):
        runner.execute()
    assert runner.EVENTS[:2] == ['load_config', 'require_allocation']
    assert 'authorized' not in runner.EVENTS
    assert 'make_task_env' not in runner.EVENTS
    assert not any(item.startswith('train:') for item in runner.EVENTS)
    assert not runner.OUTPUT.exists()
    with pytest.raises(PermissionError, match='fresh human approval'):
        lock.execute()
    src = Path('scripts/run_h16_same_state_library.py').read_text(encoding='utf-8')
    assert 'if args.execute' in src
    assert 'runner.execute()' in src
    assert '.state =' not in Path('src/nexus/world/h16_same_state_library_runner.py').read_text()
    assert inspect.getsource(runner.replay_to_later).count('env.reset') == 1
    assert 'env.unwrapped.state =' not in inspect.getsource(runner.replay_to_later)


def test_actual_l0_and_80_unique_redraw_matrices():
    cfg = lock.load_config()
    l0_seen = {}
    redraw_fps = set()
    redraw_seeds = set()
    for seed in range(10):
        for state in range(4):
            sid8, mat8 = lock.library_for('l0', cfg['library_base'], cfg['redraw_base'], seed, state, 8)
            sid12, mat12 = lock.library_for('l0', cfg['library_base'], cfg['redraw_base'], seed, state, 12)
            expected = candidate_sequences(cfg['library_base'] + 10 * seed + state, 16, 16, n_actions=3)
            assert sid8 == sid12 == cfg['library_base'] + 10 * seed + state
            assert np.array_equal(mat8, mat12)
            assert np.array_equal(mat8, expected)
            assert mat8.shape == (16, 16)
            l0_seen[(seed, state)] = lock.library_fingerprint(mat8)
            for later_t in (8, 12):
                rid, red = lock.library_for(
                    'redraw', cfg['library_base'], cfg['redraw_base'], seed, state, later_t)
                assert rid == cfg['redraw_base'] + 10_000 * seed + 100 * state + later_t
                assert np.array_equal(red, candidate_sequences(rid, 16, 16, n_actions=3))
                assert not np.array_equal(red, mat8)
                redraw_seeds.add(rid)
                redraw_fps.add(lock.library_fingerprint(red))
    assert len(l0_seen) == 40
    assert len(redraw_seeds) == 80
    assert len(redraw_fps) == 80
    import yaml
    streams, used = lock.seed_streams(cfg)
    assert len(streams['redraw']) == 80
    assert min(used) >= 78_000_000
    h14_used = h14.seed_streams(yaml.safe_load(h14.CONFIG.read_text()))[1]
    h15_used = h15.seed_streams(yaml.safe_load(h15.CONFIG.read_text()))[1]
    assert used & h14_used == set()
    assert used & h15_used == set()


def test_restoration_repeated_replay_and_gymnasium_contracts():
    cfg = lock.load_config()
    env = MockEnv()
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=200, model_cap=1))
    ref = runner.record_reference(env, cfg, 3, 2, meter, check_reward=False)
    assert set(ref['snapshots']) == {8, 12}
    first = runner.replay_to_later(env, ref, 8, meter, check_reward=False)
    for _ in range(5):
        again = runner.replay_to_later(env, ref, 8, meter, check_reward=False)
        assert np.array_equal(again['later_obs'], first['later_obs'])
        assert np.array_equal(again['later_state'], first['later_state'])
        assert again['elapsed_steps'] == 8
    drifted = MockEnv(drift_state=True, hidden_offset=0.75)
    bad = runner.record_reference(drifted, cfg, 1, 0,
                                  runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1)),
                                  check_reward=False)
    before_charge = runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1))
    with pytest.raises(RuntimeError, match='reset_obs|reset_state|later_state|later_obs'):
        runner.replay_to_later(drifted, bad, 8, before_charge, check_reward=False)
    assert before_charge.env_attempted == 0
    rewarded = MockEnv(drift_reward=True)
    ref_r = runner.record_reference(rewarded, cfg, 2, 0,
                                    runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1)),
                                    check_reward=False)
    charged = runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1))
    with pytest.raises(RuntimeError, match='prefix reward'):
        runner.replay_to_later(rewarded, ref_r, 8, charged, check_reward=False)
    assert charged.env_attempted >= 1
    assert charged.env_interrupted >= 1 or charged.env_steps >= 1
    import gymnasium
    from gymnasium.wrappers import TimeLimit
    from gymnasium.envs.classic_control.continuous_mountain_car import Continuous_MountainCarEnv
    tl_src = inspect.getsource(TimeLimit)
    assert 'self._elapsed_steps = 0' in tl_src
    assert 'self._elapsed_steps += 1' in tl_src
    assert 'super().reset(seed=seed)' in inspect.getsource(Continuous_MountainCarEnv.reset)
    assert gymnasium.__version__
    names = ('MountainCarDenseRewardWrapper', 'DiscreteTorqueWrapper',
             'ContinuousMountainCarGravityPatch', 'TimeLimit', 'OrderEnforcing',
             'PassiveEnvChecker', 'Continuous_MountainCarEnv')
    assert lock.wrapper_stack_ok(names)
    assert not lock.wrapper_stack_ok(names[:-2] + ('ObservationNoiseWrapper',))
    assert not lock.wrapper_stack_ok([n for n in names if n != 'TimeLimit'])


def test_score_before_truth_adversarial_oracle_and_shared_g():
    cfg = lock.load_config()
    order = []
    env = MockEnv()

    def adversarial_score(model, obs, sequences, meter):
        order.append(('score', int(getattr(model, 'bias', 0.0)), env.steps))
        meter.reserve_imagined(lock.N_CAND * lock.HORIZON)
        # Predicted ranking prefers index 0. Oracle constructed below prefers 15.
        return np.array([10.0] + [-1.0] * 15, dtype=np.float64) + float(getattr(model, 'bias', 0.0))

    models = {'multitask': DummyModel(0.0), 'scratch': DummyModel(3.0)}
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=4000, model_cap=2048))
    group = runner.evaluate_reset_group(
        env, models, cfg, 0, 0, meter, check_reward=False, score_fn=adversarial_score)
    assert order[0][0] == 'score'
    row = group['later_states'][0]
    l0 = row['libraries']['l0']
    assert l0['selected']['multitask']['index'] == 0
    assert l0['selected']['scratch']['index'] == 0
    assert l0['selected_return']['multitask'] == pytest.approx(l0['realized'][0])
    assert l0['oracle'] == pytest.approx(max(l0['realized']))
    disagree_g = np.linspace(-2.0, 3.0, 16)
    disagree_p = np.array([5.0] + [-1.0] * 15, dtype=np.float64)
    assert lock.selected_index(disagree_p) == 0
    assert int(np.argmax(disagree_g)) == 15
    assert lock.selected_return(disagree_g, disagree_p) == pytest.approx(disagree_g[0])
    lock.oracle_cancels_in_arm_gap(
        l0['realized'], l0['predicted_scores']['multitask'], l0['predicted_scores']['scratch'])
    assert inspect.signature(runner.score_library_guarded).parameters.keys() == {
        'model', 'obs', 'sequences', 'meter'}
    with pytest.raises(TypeError):
        runner.score_library_guarded(
            DummyModel(), np.zeros(2, dtype=np.float32),
            np.zeros((16, 16), dtype=np.int64), meter, realized=[1])
    prod_meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=1, model_cap=256))
    env_before = env.steps
    scores = runner.score_library_guarded(
        DummyModel(0.1), np.array([0.2, 0.0], dtype=np.float32),
        lock.library_for('l0', cfg['library_base'], cfg['redraw_base'], 0, 0, 8)[1],
        prod_meter)
    assert scores.shape == (16,) and np.isfinite(scores).all()
    assert prod_meter.model_states == 256
    assert env.steps == env_before
    nan_meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=1, model_cap=4096))
    with pytest.raises(RuntimeError, match='nonfinite|dropped'):
        runner.score_library_guarded(
            NanModel(), np.array([0.1, 0.0], dtype=np.float32),
            lock.library_for('l0', cfg['library_base'], cfg['redraw_base'], 0, 0, 8)[1],
            nan_meter)


def test_ties_algebra_and_selected_index_frozen_after_realization():
    realized = np.linspace(-2.0, -0.5, 16)
    tied = np.ones(16)
    assert lock.selected_index(tied) == 0
    scores_mt = np.zeros(16); scores_mt[3] = 1.0
    scores_sc = np.zeros(16); scores_sc[15] = 1.0
    s_mt = lock.selected_return(realized, scores_mt)
    s_sc = lock.selected_return(realized, scores_sc)
    o = lock.oracle_return(realized)
    r_mt = lock.within_library_regret(realized, scores_mt)
    r_sc = lock.within_library_regret(realized, scores_sc)
    assert s_mt == pytest.approx(o - r_mt)
    assert s_sc == pytest.approx(o - r_sc)
    assert (s_mt - s_sc) == pytest.approx(r_sc - r_mt)
    lock.oracle_cancels_in_arm_gap(realized, scores_mt, scores_sc)
    cfg = lock.load_config()
    captured = {}

    def score_fn(model, obs, sequences, meter):
        meter.reserve_imagined(lock.N_CAND * lock.HORIZON)
        pred = np.arange(16, dtype=np.float64) + float(getattr(model, 'bias', 0.0))
        captured.setdefault('pred', pred.copy())
        return pred

    group = runner.evaluate_reset_group(
        MockEnv(), {'multitask': DummyModel(0.0), 'scratch': DummyModel(1.0)},
        cfg, 1, 1, runner.GuardedMeter(dict(time_cap_s=30, env_cap=4000, model_cap=2048)),
        check_reward=False, score_fn=score_fn)
    l0 = group['later_states'][0]['libraries']['l0']
    assert l0['selected']['multitask']['index'] == 15
    assert lock.selected_index(l0['predicted_scores']['multitask']) == 15


def test_seed_level_labels_boundaries_and_secondaries_cannot_relabel():
    def grid(values):
        return [later_row(s, values) for s in range(10)]

    positive = lock.mean_seed_cells(grid((-1.0, -1.4, -1.3, -1.25)))
    assert positive['label'] == 'h16_l0_helps_multitask_relative_same_state'
    assert positive['interval']['n'] == 10 and positive['interval']['df'] == 9
    rebuilt = seed_level_ci(positive['per_seed'])
    assert rebuilt['df'] == 9 and rebuilt['lo'] > 0
    negative = lock.mean_seed_cells(grid((-1.4, -1.0, -1.0, -1.4)))
    assert negative['label'] == 'h16_redraw_helps_multitask_relative_same_state'
    zero = lock.mean_seed_cells(grid((-1.0, -1.0, -1.0, -1.0)))
    assert zero['label'] == 'h16_same_state_library_effect_not_established'
    assert lock.classify_primary(0.4, 0.0, 0.8, 10) == 'h16_same_state_library_effect_not_established'
    assert lock.classify_primary(-0.4, -0.8, 0.0, 10) == 'h16_same_state_library_effect_not_established'
    assert lock.classify_primary(1.0, 0.5, 1.5, 10, complete=False) == 'incomplete'
    with pytest.raises(ValueError, match='incomplete or duplicated'):
        lock.mean_seed_cells(grid((-1, -2, -3, -4))[:9])
    with pytest.raises(ValueError, match='incomplete or duplicated'):
        lock.mean_seed_cells(grid((-1, -2, -3, -4)) + [later_row(0, (-1, -2, -3, -4))])
    broken = grid((-1.0, -1.4, -1.3, -1.25))
    broken[0]['later_states'] = broken[0]['later_states'][:7]
    with pytest.raises(ValueError, match='incomplete or duplicated later-state'):
        lock.mean_seed_cells(broken)
    nan_grid = grid((-1.0, -1.4, -1.3, -1.25))
    nan_grid[2]['later_states'][0]['s_mt_l0'] = float('nan')
    with pytest.raises(ValueError, match='nonfinite'):
        lock.mean_seed_cells(nan_grid)
    summarized = runner.summarize_experiment(
        [dict(seed=s, later_states=[dict(
            state_index=k, later_t=t, s_mt_l0=-1.0, s_sc_l0=-1.4,
            s_mt_redraw=-1.3, s_sc_redraw=-1.25,
            libraries={'l0': dict(oracle=-0.5, realized=list(np.linspace(-2, -0.5, 16)),
                                  sequences=np.zeros((16, 16), np.int64).tolist(),
                                  predicted_scores={'multitask': list(range(16)),
                                                    'scratch': list(range(16))},
                                  regret={'multitask': 0.1, 'scratch': 0.2}),
                       'redraw': dict(oracle=-0.8, realized=list(np.linspace(-2, -0.8, 16)),
                                      sequences=np.zeros((16, 16), np.int64).tolist(),
                                      predicted_scores={'multitask': list(range(16)),
                                                        'scratch': list(range(16))},
                                      regret={'multitask': 0.1, 'scratch': 0.2})})
            for k in range(4) for t in (8, 12)]) for s in range(10)])
    summarized['groups']['secondaries']['oracle_opportunity_l0_minus_redraw'] = {'mean': 99.0}
    assert lock.classify_primary(
        summarized['groups']['primary']['interval']['mean'],
        summarized['groups']['primary']['interval']['lo'],
        summarized['groups']['primary']['interval']['hi'], 10) == summarized['label']
    assert not str(summarized['label']).startswith('h14_')
    assert not str(summarized['label']).startswith('h15_')


def test_training_recipe_matches_frozen_h10():
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
        seen.append(('continue', kwargs['seed'], kwargs['epochs'], kwargs['lr'],
                     len(train_ds), len(val_ds)))

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
    assert cfg['source_train'] == 512 and cfg['target_train'] == 128 and cfg['target_val'] == 32
    assert cfg['pretrain_epochs'] == 15 and cfg['train_epochs'] == 20
    assert cfg['hidden'] == [64, 64]


def test_independent_budget_and_cap_plus_one():
    counts = lock.budget()
    assert counts == {
        'source_collection': 15360, 'target_pool': 1600, 'reference_prefix': 480,
        'prefix_replay': 25600, 'shared_candidate_realizations': 40960,
        'env_total': 84000, 'imagined_total': 81920, 'time_cap_s': 300,
        'env_cap': 84000, 'model_cap': 81920,
    }
    assert 15360 + 1600 + 480 + 25600 + 40960 == 84000
    assert 80 * 2 * 2 * 16 * 16 == 81920
    env = MockEnv()
    blocked = runner.GuardedMeter(dict(time_cap_s=30, env_cap=0, model_cap=1))
    with pytest.raises(RuntimeError, match='env-step cap would be exceeded'):
        runner.guarded_env_step(env, 1, blocked)
    assert env.steps == 0
    assert blocked.env_attempted == 1 and blocked.env_interrupted == 1
    imag = runner.GuardedMeter(dict(time_cap_s=30, env_cap=1, model_cap=256))
    imag.reserve_imagined(256)
    with pytest.raises(RuntimeError, match='imagined cap would be exceeded'):
        imag.reserve_imagined(1)
    assert imag.imagined_attempted == 257
    assert imag.imagined_interrupted == 1


def test_collector_short_extra_and_production_factory():
    src = inspect.getsource(collect_transitions)
    assert 'make_task_env' in src
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
    prod = MockEnv()
    counted = runner.GuardedMeter(dict(time_cap_s=30, env_cap=8, model_cap=1))
    ds = runner.guarded_collect(collect_transitions, ToySpec(), 4, (1,), 2, counted,
                                make_env_fn=lambda *a, **k: prod)
    assert len(ds) == 4
    assert prod.steps == 4
    assert counted.env_steps == 4


def test_timeouts_scoring_exception_incomplete_and_overwrite(tmp_path):
    cfg = lock.load_config()
    expired = runner.GuardedMeter(dict(time_cap_s=0.0, env_cap=64, model_cap=8192))
    time.sleep(0.01)
    env = MockEnv()
    with pytest.raises(TimeoutError):
        runner.record_reference(env, cfg, 0, 0, expired, check_reward=False)
    assert env.steps == 0
    live = runner.GuardedMeter(dict(time_cap_s=30, env_cap=64, model_cap=1))
    ref = runner.record_reference(MockEnv(), cfg, 0, 1, live, check_reward=False)
    late = runner.GuardedMeter(dict(time_cap_s=0.0, env_cap=64, model_cap=1))
    time.sleep(0.01)
    with pytest.raises(TimeoutError):
        runner.realize_candidates(
            MockEnv(), ref, 8, lock.library_for('l0', cfg['library_base'], cfg['redraw_base'], 0, 1, 8)[1],
            late, check_reward=False)

    def boom_score(model, obs, sequences, meter):
        raise RuntimeError('score boom')

    with pytest.raises(RuntimeError, match='score boom'):
        runner.evaluate_reset_group(
            MockEnv(), {'multitask': DummyModel(), 'scratch': DummyModel()},
            cfg, 0, 0, runner.GuardedMeter(dict(time_cap_s=30, env_cap=4000, model_cap=2048)),
            check_reward=False, score_fn=boom_score)
    existing = tmp_path / 'h16.json'
    existing.write_text('{"complete":true,"label":"h16_l0_helps_multitask_relative_same_state"}')
    before = existing.read_text()
    with pytest.raises(RuntimeError, match='overwrite'):
        runner.execute(hooks=dict(require_allocation=lambda cfg: None, output=str(existing),
                                  skip_git_guards=True))
    assert existing.read_text() == before
    dest = tmp_path / 'partial.json'
    payload = runner.execute(hooks=dict(
        require_allocation=lambda cfg: None, output=str(dest), skip_git_guards=True,
        spec=object(), priors=[object(), object(), object()],
        train_seed_models=lambda *a, **k: (_ for _ in ()).throw(RuntimeError('forced interrupt')),
        skip_reward_check=True, skip_wrapper_check=True))
    assert payload['complete'] is False
    assert payload['label'] == 'incomplete'
    saved = json.loads(dest.read_text())
    assert saved['complete'] is False and saved['label'] == 'incomplete'
    assert 'forced interrupt' in saved['failure']['message']
    assert saved['counts']['events']
