"""Source-only H15 confirmation runner tests. No MountainCar env, no training."""
from __future__ import annotations
import inspect
import json
import time
from pathlib import Path
import numpy as np
import pytest
from nexus.world.data import TransitionDataset
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h14_candidate_reuse_runner as h14_runner
from nexus.world import h15_candidate_reuse_confirm as lock
from nexus.world import h15_candidate_reuse_confirm_runner as runner


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


def test_runner_binds_h15_lock_not_h14_yaml():
    from nexus.world.planning_value import sha
    assert runner.lock is lock
    assert Path(lock.CONFIG).name == 'mcc_candidate_reuse_confirm.yaml'
    assert Path(h14.CONFIG).name == 'mcc_candidate_reuse.yaml'
    assert sha(lock.CONFIG) == lock.LOCKED_CONFIG
    assert sha(lock.PROTOCOL) == lock.LOCKED_PROTOCOL
    assert sha(lock.ALLOCATION) == '210f3a631a3081152f63e7a6b4d53bf98a2b8e157be52e515a7c7b5a53e39362'
    assert lock.holdout_from_rule() == [lock.LOCKED_TARGET] == [(0.004, 0.0021, 0.05)]
    assert lock.LOCKED_TARGET != h14.LOCKED_TARGET
    assert runner.OUTPUT != h14_runner.OUTPUT
    loaded = cfg()
    assert loaded['reset_base'] == 77_000_000
    assert loaded['holdout_rule'] == 'mcc_candidate_reuse_confirm_v1'
    rec = lock.load_allocation()
    assert rec['authorized'] is False
    assert rec['runs'] == 0


def test_four_conditions_share_l0_on_h15_bases():
    loaded = cfg()
    lib = loaded['library_base']
    redraw = loaded['redraw_base']
    assert lib == 77_200_000
    matrices = []
    for mode in lock.MODES:
        for _arm in lock.ARMS:
            matrices.append(h14.recede_candidates(mode, lib, redraw, 3, 2, 0))
    assert all(np.array_equal(matrices[0], item) for item in matrices)
    first = matrices[0]
    for step in range(1, 16):
        assert np.array_equal(h14.recede_candidates('fixed', lib, redraw, 3, 2, step), first)
        fresh = h14.recede_candidates('redraw', lib, redraw, 3, 2, step)
        assert not np.array_equal(fresh, first)
        assert np.array_equal(fresh, h14.recede_candidates('redraw', lib, redraw, 3, 2, step))
        assert runner.candidate_seed_for(loaded, 3, 2, step, 'redraw') == h14.redraw_step_seed(redraw, 3, 2, step)
    aliases = lock.redraw_alias_count(loaded)
    assert aliases == dict(intended=600, unique=450, aliased=150)


def test_h15_labels_and_secondaries_cannot_relabel():
    good = [dict(state_index=k, returns={'multitask': {'fixed': 1.0, 'redraw': 0.0},
                                         'scratch': {'fixed': 0.0, 'redraw': 0.5}})
            for k in range(4)]
    cells = [dict(seed=s, states=good) for s in range(10)]
    out = lock.summarize(cells)
    assert out['label'] == 'h15_fixed_library_helps_multitask_relative'
    assert 'h14' not in out['label']
    assert lock.classify_primary(0.178, -0.001, 0.348, 10) == (
        'h15_resampling_effect_not_established')
    poisoned = dict(out)
    poisoned['groups'] = dict(out['groups'], secondaries={'multitask_minus_scratch_fixed': {'mean': 99.0}})
    assert lock.classify_primary(out['groups']['primary']['interval']['mean'],
                                 out['groups']['primary']['interval']['lo'],
                                 out['groups']['primary']['interval']['hi'], 10) == out['label']
    assert poisoned['label'] == out['label']


def test_hard_cap_and_extra_collector_step():
    env = MockEnv()
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=0, model_cap=15))
    with pytest.raises(RuntimeError, match='env-step cap would be exceeded'):
        runner.guarded_env_step(env, 1, meter)
    assert env.steps == 0
    assert meter.env_attempted == 1
    assert meter.env_interrupted == 1
    collector = MockEnv()
    budget = runner.GuardedMeter(dict(time_cap_s=30, env_cap=8, model_cap=1))

    def extra_collect(spec, n_transitions, env_seeds, base_seed, mix=None):
        import nexus.world.data as data_mod
        built = data_mod.make_task_env(spec, seed=0)
        for _ in range(int(n_transitions) + 1):
            built.step(0)
        return fake_dataset(n_transitions)

    with pytest.raises(RuntimeError, match='collector would exceed reserved env steps'):
        runner.guarded_collect(extra_collect, object(), 4, (1,), 2, budget,
                               make_env_fn=lambda *a, **k: collector)
    assert collector.steps == 4
    assert budget.env_steps == 4


def test_planner_cannot_see_realized_returns():
    assert 'realized' not in inspect.signature(runner.score_library_guarded).parameters
    assert 'actual' not in inspect.signature(runner.score_library_guarded).parameters
    src = Path(runner.__file__).read_text(encoding='utf-8')
    assert 'Realized counterfactual returns are not arguments' in src


def test_controller_and_open_loop_on_h15_seeds():
    env = MockEnv(reward=-1.0)
    loaded = cfg()
    models = {'multitask': DummyModel(0.0), 'scratch': DummyModel(0.2)}
    meter = runner.GuardedMeter(dict(time_cap_s=30, env_cap=320, model_cap=16384))
    row = runner.evaluate_state(env, models, loaded, 0, 1, meter,
                                check_reward=False, score_fn=fast_score)
    assert row['state_seed'] == loaded['state_reset_base'] + 1
    assert row['returns']['multitask']['fixed'] == -16.0
    t0 = row['controllers']['multitask']['fixed']['traces'][0]
    t1 = row['controllers']['multitask']['redraw']['traces'][1]
    assert set(h14.TRACE_FIELDS) <= set(t0)
    assert t0['library_fingerprint'] == row['library_fingerprint']
    assert t1['library_fingerprint'] != t0['library_fingerprint']
    assert t0['candidate_seed'] == h14.shared_library_seed(loaded['library_base'], 0, 1)
    assert meter.env_steps == 320
    assert meter.model_states == 16384


def test_mock_grid_accounting_and_h15_reconstruction(tmp_path):
    loaded = cfg()
    meter = runner.GuardedMeter(loaded)

    def train(cfg, spec, priors, seed, meter):
        return runner.train_seed_models(cfg, spec, priors, seed, meter,
                                        collect_fn=fake_collect, train_fn=fake_train,
                                        continue_fn=fake_continue, rms_fn=fake_rms)

    cells = runner.run_grid(loaded, meter, object(), [object(), object(), object()],
                            check_reward=False,
                            hooks=dict(train_seed_models=train, make_env=lambda spec: MockEnv(),
                                       score_fn=fast_score))
    assert meter.env_steps == 29760
    assert meter.model_states == 655360
    summary = runner.summarize_experiment(cells)
    assert summary['label'] == 'h15_resampling_effect_not_established'
    assert not str(summary['label']).startswith('h14_')
    assert summary['groups']['primary']['metric'] == 'fixed_minus_redraw_relative_multitask_advantage'
    rebuilt = runner.summarize_experiment(json.loads(json.dumps(cells)))
    assert rebuilt['label'] == summary['label']
    path = tmp_path / 'h15.json'
    path.write_text(json.dumps(dict(complete=True, cells=cells, **summary)))
    loaded_payload = json.loads(path.read_text())
    assert runner.summarize_experiment(loaded_payload['cells'])['label'] == summary['label']


def test_partial_artifact_and_overwrite_refuse(tmp_path):
    existing = tmp_path / 'h15.json'
    existing.write_text('{"complete":false,"label":"incomplete"}')
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
    assert saved['label'] == 'incomplete'
    assert 'forced interrupt' in saved['failure']['message']


def test_unauthorized_execute_never_trains_or_builds_env():
    runner.EVENTS.clear()
    with pytest.raises(PermissionError, match='fresh human approval'):
        runner.execute()
    assert 'authorized' not in runner.EVENTS
    assert 'make_task_env' not in runner.EVENTS
    assert not any(item.startswith('train:') for item in runner.EVENTS)
    assert not runner.OUTPUT.exists()
    report = runner.prep()
    assert report['authorized'] is False
    assert report['runs'] == 0
    assert report['runner_implemented'] is True
    assert report['new_environment_steps'] == 0
    assert lock.load_allocation()['authorized'] is False
    assert lock.load_allocation()['runs'] == 0


def test_training_recipe_uses_h15_seed_bases():
    loaded = cfg()
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
        loaded, object(), [object(), object(), object()], 2, meter,
        collect_fn=collect, train_fn=train, continue_fn=cont, rms_fn=lambda obs: object())
    assert set(models) == {'multitask', 'scratch'}
    assert [row[1] for row in seen if row[0] == 'collect'] == [512, 512, 512, 128, 32]
    assert seen[0][2] == loaded['collect_source_base'] + 120 * 2
    assert ('train', 5 + 19 * 2, 15, (64, 64), 3, 1504, 32) in seen
    assert ('train', 5 + 19 * 2, 20, (64, 64), 3, 128, 32) in seen
    assert ('continue', 7 + 19 * 2, 20, 128, 32) in seen
