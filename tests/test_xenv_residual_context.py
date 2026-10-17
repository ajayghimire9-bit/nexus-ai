"""Offline rung-4 guards: residual context, isolation, no leakage, gates."""
from __future__ import annotations
from types import SimpleNamespace
import numpy as np
import pytest
import torch
from nexus.world import xenv_residual_context as m
from nexus.world.planning_value import sha


def _toy(n, dim, n_actions, seed=0):
    rng = np.random.default_rng(seed)
    obs = rng.normal(size=(n, dim)).astype(np.float32)
    act = rng.integers(0, n_actions, size=n).astype(np.int64)
    nxt = obs + 0.01 * (act - 1).reshape(-1, 1).astype(np.float32)
    return SimpleNamespace(obs=obs, action=act, next_obs=nxt,
                           terminated=np.zeros(n, dtype=bool))


def _net(seed=5):
    return m.XEnvResidualContextNet({'cartpole': (4, 2), 'acrobot': (6, 3),
                                      'mountaincar': (2, 3), 'mcc': (2, 3)},
                                     context_dim=8, seed=seed)


def test_locked_configuration_budget_and_seeds():
    cfg = m.load_config()
    assert cfg['reset_base'] == 66000000 and cfg['residual_pad'] == 6
    assert cfg['holdout_rule'] == 'mcc_xenv_v5'
    counts = m.budget(cfg)
    assert counts['prior_collection'] + counts['target_pool'] + \
        counts['evaluation_episodes'] == cfg['env_cap'] == 44000
    m.check_seeds(cfg)


def test_holdout_rejects_closed_rungs():
    hold = m.holdout_from_rule()
    assert hold == [(0.0019, 0.0013, 0.065)]
    assert (0.0027, 0.0009, 0.05) in m.occupied_physics()
    assert (0.0025, 0.0015, 0.09) in m.occupied_physics()
    spec = m.target_spec(hold[0])
    assert spec.task_id == 'mcc_xenv5_t0'


def test_residual_changes_inferred_context_and_encoder_shape():
    net = _net()
    assert net.ctx_enc[0].weight.shape == (8, 70)
    obs = np.zeros((8, 2), np.float32)
    act = np.zeros(8, np.int64)
    z0 = net.infer_context('mcc', obs, act, obs)
    z1 = net.infer_context('mcc', obs, act, obs + 0.2)
    assert z0.shape == (1, 8) and not torch.equal(z0, z1)


def test_support_may_read_next_obs_but_not_val_fields():
    class Guarded:
        def __init__(self, ds):
            self._ds = ds
        def __getattr__(self, key):
            if key not in ('obs', 'action', 'next_obs'):
                raise AssertionError(f'context inference touched {key}')
            return getattr(self._ds, key)
    obs, act, nxt = m.support_arrays(Guarded(_toy(16, 2, 3)), 8)
    assert obs.shape == (8, 2) and nxt.shape == (8, 2)


def test_pretrain_moves_encoder_and_survives_multiple_batches():
    net = _net()
    from nexus.world.xenv_transfer import fit_rms
    data = {'cartpole': (_toy(200, 4, 2, 1), fit_rms(_toy(200, 4, 2, 1).obs))}
    before = net.ctx_enc[0].weight.detach().clone()
    m.pretrain_contextual(net, data, 64, epochs=1, lr=1e-3, seed=3, batch_size=64)
    assert not torch.equal(before, net.ctx_enc[0].weight)


def test_zero_film_identity_and_matched_arms():
    a, b = _net(11), _net(11)
    assert a.n_parameters() == b.n_parameters()
    z = a.frozen_context('mcc', np.ones((8, 2), np.float32), np.zeros(8, np.int64),
                         np.zeros((8, 2), np.float32))
    a.set_context('mcc', z)
    o1, _ = a('mcc', torch.zeros(3, 2), torch.tensor([0, 1, 2]))
    a.set_context('mcc', z + 1)
    o2, _ = a('mcc', torch.zeros(3, 2), torch.tensor([0, 1, 2]))
    assert torch.equal(o1, o2)


def test_allocation_binds_the_authorized_one_run_record():
    cfg = m.load_config()
    record = m.load_allocation()
    assert record['authorized'] is True and record['runs'] == 1
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    m.require_allocation(cfg)
    with pytest.raises(PermissionError, match='already authorized'):
        m.prep()
