"""Source-only ranking runner guards. No environment collection or training."""
from __future__ import annotations
import inspect
import numpy as np
import pytest
from nexus.world import mcc_planning_ranking as m
from nexus.world import mcc_multitask_128 as h10
from nexus.world import mcc_multitask_128_confirm as h11
from nexus.world import xenv_transfer as rung1
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.rewards import mountaincar_step_reward


class ToyEnv:
    def __init__(self, obs, drift=False):
        self._obs = np.asarray(obs, dtype=np.float32)
        self.drift = drift
        self.resets = 0
        self.steps = 0

    def reset(self, seed=None):
        self.resets += 1
        if self.drift and self.resets > 1:
            return (self._obs + 1.0).copy(), {}
        return self._obs.copy(), {}

    def step(self, action):
        self.steps += 1
        nxt = self._obs.copy()
        reward = float(mountaincar_step_reward(self._obs, int(action), nxt).reshape(-1)[0])
        return nxt, reward, False, False, {}

    def close(self):
        pass


class ToyModel:
    def __init__(self, log=None):
        self.log = log if log is not None else []

    def begin_rollout(self, n):
        del n

    def step(self, obs, action):
        self.log.append('score')
        o = np.asarray(obs, dtype=np.float32)
        if o.ndim == 1:
            o = o.reshape(1, -1)
        return o.copy(), np.zeros(o.shape[0], dtype=np.float64)


class LoggingEnv(ToyEnv):
    def __init__(self, obs, log):
        super().__init__(obs)
        self.log = log

    def reset(self, seed=None):
        self.log.append('reset')
        return super().reset(seed=seed)

    def step(self, action):
        self.log.append('realize')
        return super().step(action)


def _tiny_meter(env_cap=100000, model_cap=100000):
    return rung1.Meter(dict(time_cap_s=30, env_cap=env_cap, model_cap=model_cap))


def _toy_cfg():
    cfg = m.load_config()
    return dict(closed_loop_step_base=cfg['closed_loop_step_base'])


def test_holdout_is_unused_and_not_chosen_from_h11_negative_seeds():
    cfg = m.load_config()
    hold = m.holdout_from_rule()
    assert hold == [(0.0027, 0.0015, 0.075)]
    assert hold[0] not in m.occupied_physics()
    assert hold[0] != h11.CLOSED_H10
    assert hold[0] != m.CLOSED_H11
    assert cfg['h10_negative_seeds_used'] is False
    assert cfg['full_episode_primary'] is False
    assert cfg['restore_method'] == 'reset_same_seed'
    assert cfg['n_states'] == 4 and cfg['n_candidates'] == 16
    assert cfg['source_physics'] == h10.load_config()['source_physics']
    assert cfg['pretrain_epochs'] == 15 and cfg['target_train'] == 128
    m.check_seeds(cfg)


def test_regret_is_nonnegative_and_separates_first_action():
    pred = np.array([1.0, 3.0, 0.5, 2.0])
    real = np.array([4.0, 1.0, 5.0, 0.0])
    seq = np.array([[0, 1], [1, 1], [2, 0], [1, 2]])
    assert m.sequence_regret(pred, real) == 4.0
    assert m.first_action_regret(pred, real, seq) == 4.0
    with pytest.raises(ValueError):
        m.sequence_regret([1.0], [1.0, 2.0])
    assert m.classify_primary(1.0, 0.1, 2.0, 10) == 'mcc_planning_ranking_multitask_better'
    assert m.classify_primary(-1.0, -2.0, -0.1, 10) == 'mcc_planning_ranking_scratch_better'
    assert m.classify_primary(1.0, -0.1, 2.0, 10) == 'mcc_planning_ranking_not_established'


def test_budget_counts_shared_ground_truth_and_blocks_collection():
    cfg = m.load_config()
    counts = m.budget(cfg)
    assert counts['ground_truth_open_loop'] == 10240
    assert counts['closed_loop_recede'] == 1280
    assert counts['source_collection'] + counts['target_pool'] == 16960
    assert cfg['env_cap'] == 28480 and cfg['model_cap'] == 348160
    assert cfg['time_cap_s'] == 300
    record = m.load_allocation()
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    if record.get('authorized') is True:
        assert record['runs'] == 1
        m.require_allocation(cfg)
        with pytest.raises(PermissionError, match='already authorized'):
            m.prep()
    else:
        assert record['runs'] == 0
        assert m.prep()['new_environment_steps'] == 0
        with pytest.raises(PermissionError, match='fresh human approval'):
            m.require_allocation(cfg)
        with pytest.raises(PermissionError):
            m.execute()
    assert m.LOCKED_CONFIG == sha(m.CONFIG)
    assert m.LOCKED_PROTOCOL == sha(m.PROTOCOL)
    assert 'actual' not in inspect.signature(m.score_candidates).parameters
    assert 'realized' not in inspect.signature(m.score_candidates).parameters
    assert 'model' not in inspect.signature(m.realize_open_loop).parameters


def test_reset_identity_and_failed_restore():
    env = ToyEnv(np.array([0.25, 0.0], dtype=np.float32))
    obs0 = m.record_reset(env, 7)
    again = m.assert_same_reset(env, 7, obs0)
    assert np.allclose(obs0, again)
    drifted = ToyEnv(np.array([0.25, 0.0], dtype=np.float32), drift=True)
    first = m.record_reset(drifted, 7)
    with pytest.raises(RuntimeError, match='reset identity failed'):
        m.assert_same_reset(drifted, 7, first)


def test_sequence_ties_use_first_index_and_differ_from_first_action():
    pred = np.array([2.0, 2.0, 0.0])
    real = np.array([1.0, 5.0, 0.0])
    seq = np.array([[1, 0], [0, 1], [2, 2]])
    assert int(np.argmax(pred)) == 0
    assert m.sequence_regret(pred, real) == 4.0
    assert m.first_action_regret(pred, real, seq) == 0.0
    pred2 = np.array([10.0, 9.0, 1.0, 0.0])
    real2 = np.array([0.0, 8.0, 7.0, 9.0])
    seq2 = np.array([[0, 1], [0, 2], [1, 0], [1, 1]])
    assert m.sequence_regret(pred2, real2) == 9.0
    assert m.first_action_regret(pred2, real2, seq2) == 1.0
    ranked = m.rank_shared_state({'multitask': pred2, 'scratch': pred2}, real2, seq2)
    assert 'closed_loop_return' not in ranked['multitask']
    assert ranked['multitask']['sequence_regret'] != ranked['multitask']['first_action_regret']


def test_closed_loop_is_not_the_primary_metric():
    cfg = m.load_config()
    cells = [dict(seed=i, sequence_regret={'scratch': 1.0, 'multitask': 1.0},
                  first_action_regret={'scratch': 4.0, 'multitask': 0.0},
                  closed_loop_return={'scratch': 100.0, 'multitask': -100.0})
             for i in range(10)]
    out = m.summarize(cells, cfg)
    assert out['label'] == 'mcc_planning_ranking_not_established'
    assert out['groups']['primary']['interval']['mean'] == 0.0
    assert out['groups']['primary']['metric'] == 'scratch_minus_multitask_sequence_regret'
    assert 'closed_loop' not in out['groups']['primary']
    assert m.classify_primary(1.0, 0.1, 2.0, 9) == 'incomplete'
    assert m.classify_primary(1.0, 0.1, 2.0, 10, False) == 'incomplete'
    with pytest.raises(ValueError, match='incomplete ranking seed grid'):
        m.summarize(cells[:9], cfg)


def test_meters_cannot_exceed_caps():
    env_meter = _tiny_meter(env_cap=2, model_cap=100)
    env_meter.env_step(); env_meter.env_step()
    with pytest.raises(RuntimeError, match='env-step cap reached'):
        env_meter.env_step()
    model = ToyModel()
    imagined = _tiny_meter(env_cap=100, model_cap=1)
    imagined.instrument(model)
    model.step(np.zeros(2, dtype=np.float32), 0)
    with pytest.raises(RuntimeError, match='imagined cap reached'):
        model.step(np.zeros(2, dtype=np.float32), 0)
    sequences = candidate_sequences(0, m.N_CAND, m.HORIZON, n_actions=m.N_ACTIONS)
    env = ToyEnv(np.array([0.1, 0.0], dtype=np.float32))
    obs0 = m.record_reset(env, 3)
    with pytest.raises(RuntimeError, match='env-step cap reached'):
        m.realize_open_loop(env, 3, obs0, sequences, _tiny_meter(env_cap=255, model_cap=100000))
    with pytest.raises(RuntimeError, match='imagined cap reached'):
        m.score_candidates(ToyModel(), obs0, sequences, _tiny_meter(env_cap=100000, model_cap=255))


def test_evaluate_state_scores_before_any_realized_return():
    log = []
    env = LoggingEnv(np.array([0.2, 0.0], dtype=np.float32), log)
    models = {'multitask': ToyModel(log), 'scratch': ToyModel(log)}
    sequences = candidate_sequences(1, m.N_CAND, m.HORIZON, n_actions=m.N_ACTIONS)
    row = m.evaluate_state(env, models, 11, sequences, _toy_cfg(), 0, 0, _tiny_meter())
    assert log.index('score') < log.index('realize')
    assert row['ranked']['multitask']['closed_loop_return'] is not None
    assert 'closed_loop_return' not in m.rank_shared_state(
        {'multitask': np.zeros(m.N_CAND), 'scratch': np.zeros(m.N_CAND)},
        np.zeros(m.N_CAND), sequences)['multitask']
    with pytest.raises(RuntimeError, match='reset identity failed'):
        m.evaluate_state(ToyEnv(np.array([0.2, 0.0], dtype=np.float32), drift=True),
                         models, 11, sequences, _toy_cfg(), 0, 0, _tiny_meter())
