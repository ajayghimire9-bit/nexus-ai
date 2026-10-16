"""Deterministic engineering tests only: no training or environment episodes."""
from copy import deepcopy

import numpy as np
import pytest
import torch

from nexus.world import acrobot_lookahead, bellman_backup_control, mountaincar_lookahead
from nexus.world.context_model import ContextWorldModel
from nexus.world.dynamics import WorldModel
from nexus.world.planning import RandomShootingMPC
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.successor_search import DIMS, REWARDS, PreparedSuccessorSearch


class Toy:
    batch_independent = True

    def __init__(self, dim, *, tied=False):
        self.dim = dim
        self.calls = []
        self.begins = []
        self.tied = tied

    def begin_rollout(self, n):
        self.begins.append(n)

    def step(self, obs, actions):
        obs = np.asarray(obs, dtype=np.float32).reshape(-1, self.dim)
        actions = np.asarray(actions)
        self.calls.append((obs.copy(), actions.copy()))
        nxt = obs.copy()
        if not self.tied:
            nxt[:, -1] += (actions.astype(np.float32) - 1) * np.float32(.025)
            nxt[:, 0] += nxt[:, -1] * np.float32(.01)
        p = np.zeros(len(obs)) if self.tied else .03 + .04 * actions
        return nxt, p


def original(model, obs, seq, family):
    if family == "pendulum":
        return bellman_backup_control.lookahead_first_action(model, obs, seq)
    module = acrobot_lookahead if family == "acrobot" else mountaincar_lookahead
    return module.lookahead_first_action(module.make_planner(model), obs, seq)


@pytest.mark.parametrize("family", DIMS)
@pytest.mark.parametrize("seed", [0, 27, 91])
def test_original_q_rankings_and_action_are_bitwise_equal_on_rowwise_toy(family, seed):
    seq = candidate_sequences(seed, 16, 16, 3)
    obs = np.linspace(-.2, .3, DIMS[family], dtype=np.float32)
    serial, batched = Toy(DIMS[family]), Toy(DIMS[family])
    expected = original(serial, obs, seq, family)
    result = PreparedSuccessorSearch(seq, family=family).score(batched, obs)
    assert np.array_equal(expected[1], result.q)
    assert np.array_equal(np.argsort(expected[1], kind="stable"), np.argsort(result.q, kind="stable"))
    assert expected[0] == result.action
    assert len(serial.calls) == 51 and len(batched.calls) == 17
    assert sum(len(a) for _, a in serial.calls) == sum(len(a) for _, a in batched.calls) == 771
    assert [len(a) for _, a in batched.calls] == [3] + [48] * 16
    assert batched.begins == [48]
    for t, (_, a) in enumerate(batched.calls[1:]):
        assert np.array_equal(a.reshape(3, 16), np.tile(seq[:, t], (3, 1)))
    if family == "pendulum":
        assert np.array_equal(expected[2], result.successors[result.action])


@pytest.mark.parametrize("family", DIMS)
def test_every_tail_candidate_and_reward_timing_matches_original_score_batch(family):
    seq = candidate_sequences(77, 16, 16, 3)
    model = Toy(DIMS[family])
    obs = np.linspace(.1, .4, DIMS[family], dtype=np.float32)
    result = PreparedSuccessorSearch(seq, family=family).score(model, obs)
    for a in range(3):
        ref = Toy(DIMS[family])
        nxt, p = ref.step(obs.reshape(1, -1), np.array([a]))
        planner = RandomShootingMPC(ref, 3, horizon=16, n_candidates=16,
                                    step_reward=REWARDS[family], enforce_time_budget=False)
        scores = planner._score_batch(nxt, seq)
        assert np.array_equal(scores, result.tail_scores[a])
        reward = float(REWARDS[family](obs, a, nxt)[0])
        assert result.immediate_rewards[a] == reward
        outer = 1. if family == "pendulum" else 1. - p[0]
        assert result.outer_survival[a] == outer
        assert result.q[a] == reward + outer * max(scores)


@pytest.mark.parametrize("family", DIMS)
def test_duplicate_candidates_ties_and_caller_mutation(family):
    seq = np.zeros((16, 16), dtype=np.int64)
    prepared = PreparedSuccessorSearch(seq, family=family)
    seq[:] = 2
    exposed = prepared.sequences
    exposed[:] = 1
    assert np.array_equal(prepared.sequences, np.zeros((16, 16)))
    obs = np.zeros(DIMS[family], dtype=np.float32)
    obs[0] = 1.
    result = prepared.score(Toy(DIMS[family], tied=True), obs)
    expected = original(Toy(DIMS[family], tied=True), obs, prepared.sequences, family)
    assert result.action == expected[0]
    assert np.array_equal(result.q, expected[1])
    assert np.all(result.tail_scores == result.tail_scores[:, :1])
    if family != "pendulum":
        assert result.action == 0  # all three actions exactly tied


def snapshot(model):
    modules = [model.net] + ([model.encoder] if hasattr(model, "encoder") else [])
    params = [p.detach().clone() for module in modules for p in module.parameters()]
    return params, deepcopy(model.obs_rms.state_dict()), getattr(model, "z", None)


@pytest.mark.parametrize("family", DIMS)
@pytest.mark.parametrize("seed", [0, 11])
def test_real_neural_code_without_training_is_equivalent_and_immutable(family, seed):
    torch.set_num_threads(1)
    if family == "pendulum":
        model = ContextWorldModel.create(3, 3, seed=seed)
        model.z = torch.linspace(-.2, .2, 8)
        model.encoder.eval()
    else:
        model = WorldModel.create(DIMS[family], 3, seed=seed)
    model.net.eval()
    before = snapshot(model)
    obs = np.linspace(.1, .4, DIMS[family], dtype=np.float32)
    seq = candidate_sequences(7 + seed, 16, 16, 3)
    expected = original(model, obs, seq, family)
    result = PreparedSuccessorSearch(seq, family=family).score(model, obs)
    np.testing.assert_allclose(result.q, expected[1], atol=2e-4, rtol=2e-5)
    assert result.action == expected[0]
    after = snapshot(model)
    assert all(torch.equal(a, b) for a, b in zip(before[0], after[0]))
    for k in before[1]:
        assert np.array_equal(before[1][k], after[1][k])
    if before[2] is not None:
        assert torch.equal(before[2], after[2])
    assert all(p.grad is None for p in model.net.parameters())


@pytest.mark.parametrize("bad", [np.zeros((15, 16), int), np.zeros((16, 15), int),
                                  np.zeros((16, 16), float), np.zeros((16, 16), bool),
                                  np.full((16, 16), 3), np.full((16, 16), -1)])
def test_bad_candidates_rejected(bad):
    with pytest.raises(ValueError):
        PreparedSuccessorSearch(bad, family="mountaincar")


def test_gru_unknown_models_nonfinite_and_context_mutation_rejected():
    prepared = PreparedSuccessorSearch(np.zeros((16, 16), int), family="mountaincar")
    model = WorldModel.create(2, 3, arch="gru")
    with pytest.raises(TypeError):
        prepared.score(model, np.zeros(2))
    unknown = Toy(2)
    unknown.batch_independent = False
    with pytest.raises(TypeError):
        prepared.score(unknown, np.zeros(2))
    with pytest.raises(ValueError):
        prepared.score(Toy(2), np.array([np.nan, 0.]))
    class Mutates(Toy):
        def __init__(self):
            super().__init__(2)
            self.z = torch.zeros(8)
        def step(self, o, a):
            self.z += 1
            return super().step(o, a)
    with pytest.raises(RuntimeError, match="context changed"):
        prepared.score(Mutates(), np.zeros(2))
    class Invalid(Toy):
        def step(self, o, a):
            nxt, p = super().step(o, a)
            p[0] = np.inf
            return nxt, p
    with pytest.raises(ValueError, match="finite"):
        prepared.score(Invalid(2), np.zeros(2))


def test_scoring_never_draws_randomness_or_changes_planner_rng():
    planner = mountaincar_lookahead.make_planner(Toy(2))
    state = deepcopy(planner._rng.bit_generator.state)
    seq = candidate_sequences(31, 16, 16, 3)
    prepared = PreparedSuccessorSearch(seq, family="mountaincar")
    a = prepared.score(planner.model, np.array([-.5, .01], dtype=np.float32))
    b = prepared.score(planner.model, np.array([-.5, .01], dtype=np.float32))
    assert planner._rng.bit_generator.state == state
    assert np.array_equal(a.q, b.q) and a.action == b.action


@pytest.mark.parametrize("family", DIMS)
def test_termination_clipping_and_outer_backup_semantics(family):
    class OutsideProbability(Toy):
        def step(self, obs, actions):
            nxt, _ = super().step(obs, actions)
            return nxt, np.where(np.asarray(actions) == 0, -.4, 1.7)
    seq = candidate_sequences(54, 16, 16, 3)
    obs = np.linspace(.1, .3, DIMS[family], dtype=np.float32)
    expected = original(OutsideProbability(DIMS[family]), obs, seq, family)
    result = PreparedSuccessorSearch(seq, family=family).score(OutsideProbability(DIMS[family]), obs)
    assert np.array_equal(result.q, expected[1])
    if family != "pendulum":
        assert np.array_equal(result.outer_survival, [1., 0., 0.])
        assert np.array_equal(result.q[1:], result.immediate_rewards[1:])
    else:
        assert np.array_equal(result.outer_survival, [1., 1., 1.])
