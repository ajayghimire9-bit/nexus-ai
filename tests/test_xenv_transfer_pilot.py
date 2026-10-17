"""Offline xenv transfer pilot guards. No environment collection here."""
from __future__ import annotations
from types import SimpleNamespace
import json
from pathlib import Path
import numpy as np
import pytest
import torch
from nexus.world import xenv_transfer as m
from nexus.world.planning_value import sha


def _toy(n, dim, n_actions, seed=0):
    rng = np.random.default_rng(seed)
    obs = rng.normal(size=(n, dim)).astype(np.float32)
    act = rng.integers(0, n_actions, size=n).astype(np.int64)
    nxt = obs + 0.01 * (act - 1).reshape(-1, 1).astype(np.float32)
    return SimpleNamespace(obs=obs, action=act, next_obs=nxt,
                           terminated=np.zeros(n, dtype=bool))


def test_locked_configuration_budget_and_seeds():
    cfg = m.load_config()
    assert cfg['target_budgets'] == [128, 1024] and cfg['n_model_seeds'] == 10
    assert cfg['reset_base'] == 63000000 and cfg['collect_target_base'] == 63300000
    counts = m.budget(cfg)
    assert counts == dict(prior_collection=19200, target_pool=12800,
        evaluation_episodes=12000, imagined=3072000, time_cap_s=600)
    assert counts['prior_collection'] + counts['target_pool'] + \
        counts['evaluation_episodes'] == cfg['env_cap'] == 44000
    m.check_seeds(cfg)


def test_holdout_rule_rejects_all_occupied_physics():
    cfg = m.load_config()
    hold = m.holdout_from_rule()
    assert hold == [(0.0025, 0.0015, 0.09)]
    assert hold[0] not in m.occupied_physics()
    assert hold == [tuple(cfg['target_physics'][0])]
    spec = m.target_spec(hold[0])
    assert spec.task_id == 'mcc_xenv_t0' and spec.obs_dim == 2 and spec.n_actions == 3


def test_xenvnet_family_scoping_and_deterministic_construction():
    fam = {'cartpole': (4, 2), 'acrobot': (6, 3), 'mcc': (2, 3)}
    a, b = m.XEnvNet(fam, seed=5), m.XEnvNet(fam, seed=5)
    sa = {k: v.clone() for k, v in a.state_dict().items()}
    a.load_state_dict(b.state_dict())
    assert all(torch.equal(v, sa[k]) for k, v in a.state_dict().items())
    obs = torch.zeros(3, 2)
    pred, logit = a('mcc', obs, torch.tensor([0, 1, 2]))
    assert pred.shape == (3, 2) and logit.shape == (3, 1)
    pred4, _l = a('cartpole', torch.zeros(3, 4), torch.tensor([0, 1, 0]))
    assert pred4.shape == (3, 4)
    rms = m.fit_rms(_toy(16, 2, 3).obs)
    model = m.XEnvModel(a, 'mcc', 2, 3, rms)
    nxt, p = model.step(np.zeros((3, 2), np.float32), np.array([0, 1, 2]))
    assert nxt.shape == (3, 2) and p.shape == (3,)
    assert np.isfinite(nxt).all() and ((p >= 0) & (p <= 1)).all()


def test_pretrain_moves_shared_and_prior_heads_not_target_heads():
    fam = {'cartpole': (4, 2), 'mcc': (2, 3)}
    before = m.XEnvNet(fam, seed=7)
    after = m.XEnvNet(fam, seed=7)
    before.load_state_dict(after.state_dict())
    data = {'cartpole': (_toy(64, 4, 2, 1), m.fit_rms(_toy(64, 4, 2, 1).obs))}
    m.pretrain_shared(after, data, epochs=2, lr=1e-3, seed=3)
    sd0, sd1 = before.state_dict(), after.state_dict()
    assert not torch.equal(sd0['shared.weight'], sd1['shared.weight'])
    assert not torch.equal(sd0['in_heads.cartpole.weight'], sd1['in_heads.cartpole.weight'])
    for key in ('in_heads.mcc.weight', 'state_heads.mcc.weight', 'term_heads.mcc.weight'):
        assert torch.equal(sd0[key], sd1[key]), key


def test_finetune_target_updates_target_and_shared_and_reduces_loss():
    fam = {'mcc': (2, 3)}
    net = m.XEnvNet(fam, seed=11)
    tr, vl = _toy(128, 2, 3, 2), _toy(32, 2, 3, 3)
    rms = m.fit_rms(tr.obs)
    sd0 = {k: v.clone() for k, v in net.state_dict().items()}
    log = m.finetune_target(net, 'mcc', tr, vl, rms, epochs=8, lr=1e-3, seed=4)
    sd1 = net.state_dict()
    assert not torch.equal(sd0['shared.weight'], sd1['shared.weight'])
    assert not torch.equal(sd0['state_heads.mcc.weight'], sd1['state_heads.mcc.weight'])
    assert log['epochs'] == 8 and np.isfinite(log['best_val'])
    model = m.XEnvModel(net, 'mcc', 2, 3, rms)
    assert m.prediction_mae(model, vl) >= 0.0


def test_allocation_binds_the_authorized_one_run_record():
    cfg = m.load_config()
    record = m.load_allocation()
    assert record['authorized'] is True and record['runs'] == 1
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    assert record['protocol_sha256'] == sha(m.PROTOCOL) == m.LOCKED_PROTOCOL
    m.require_allocation(cfg)
    with pytest.raises(PermissionError, match='already authorized'):
        m.prep()
