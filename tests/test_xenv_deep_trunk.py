"""Offline deep-trunk guards. No environment collection here."""
from __future__ import annotations
from types import SimpleNamespace
import numpy as np
import pytest
import torch
from nexus.world import xenv_deep_trunk as m
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
    assert cfg['reset_base'] == 63500000 and cfg['collect_target_base'] == 63800000
    counts = m.budget(cfg)
    assert counts['prior_collection'] + counts['target_pool'] + \
        counts['evaluation_episodes'] == cfg['env_cap'] == 44000
    assert counts['imagined'] == cfg['model_cap'] == 3072000
    m.check_seeds(cfg)


def test_holdout_rule_rejects_all_occupied_physics():
    cfg = m.load_config()
    hold = m.holdout_from_rule()
    assert hold == [(0.0028, 0.0013, 0.065)]
    assert hold[0] not in m.occupied_physics()
    assert (0.0025, 0.0015, 0.09) in m.occupied_physics()  # rung 1 rejected
    assert hold == [tuple(cfg['target_physics'][0])]
    spec = m.target_spec(hold[0])
    assert spec.task_id == 'mcc_xenv2_t0' and spec.obs_dim == 2


def test_deep_net_family_scoping_and_deterministic_construction():
    fam = {'cartpole': (4, 2), 'mcc': (2, 3)}
    a, b = m.XEnvDeepNet(fam, seed=5), m.XEnvDeepNet(fam, seed=5)
    sa = {k: v.clone() for k, v in a.state_dict().items()}
    a.load_state_dict(b.state_dict())
    assert all(torch.equal(v, sa[k]) for k, v in a.state_dict().items())
    pred, logit = a('mcc', torch.zeros(3, 2), torch.tensor([0, 1, 2]))
    assert pred.shape == (3, 2) and logit.shape == (3, 1)
    pred4, _l = a('cartpole', torch.zeros(3, 4), torch.tensor([0, 1, 0]))
    assert pred4.shape == (3, 4)


def test_pretrain_moves_both_shared_layers_not_target_heads():
    fam = {'cartpole': (4, 2), 'mcc': (2, 3)}
    before = m.XEnvDeepNet(fam, seed=7)
    after = m.XEnvDeepNet(fam, seed=7)
    before.load_state_dict(after.state_dict())
    from nexus.world.xenv_transfer import fit_rms, pretrain_shared
    data = {'cartpole': (_toy(64, 4, 2, 1), fit_rms(_toy(64, 4, 2, 1).obs))}
    pretrain_shared(after, data, epochs=2, lr=1e-3, seed=3)
    sd0, sd1 = before.state_dict(), after.state_dict()
    assert not torch.equal(sd0['shared1.weight'], sd1['shared1.weight'])
    assert not torch.equal(sd0['shared2.weight'], sd1['shared2.weight'])
    assert not torch.equal(sd0['in_proj.cartpole.weight'], sd1['in_proj.cartpole.weight'])
    for key in ('in_proj.mcc.weight', 'state_heads.mcc.weight', 'term_heads.mcc.weight'):
        assert torch.equal(sd0[key], sd1[key]), key


def test_allocation_binds_the_authorized_one_run_record():
    cfg = m.load_config()
    record = m.load_allocation()
    assert record['authorized'] is True and record['runs'] == 1
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    assert record['protocol_sha256'] == sha(m.PROTOCOL) == m.LOCKED_PROTOCOL
    m.require_allocation(cfg)
    with pytest.raises(PermissionError, match='already authorized'):
        m.prep()


def test_recorded_deep_trunk_result_passes_the_independent_audit():
    import json
    from pathlib import Path
    p = json.loads(m.OUTPUT.read_text())
    assert p['complete'] is True and p['label'] == 'xenv_deep_trunk_not_established'
    audit = m.audit_results()
    assert audit['audit_passed'] is True and audit['label'] == p['label']
    assert audit['raw_sha256'] == sha(m.OUTPUT)
    assert int(audit['new_environment_steps']) == 44000
    primary = p['groups']['primary']['interval']
    assert primary['n'] == 10 and primary['lo'] < 0 < primary['hi']
    for b in ('128', '1024'):
        pb = p['groups']['per_budget_return_gain'][b]
        assert pb['lo'] < 0 < pb['hi']
    usage = json.loads(Path('artifacts/research_session_xenv_deep_trunk_usage.json').read_text())
    assert usage['status'] == 'complete' and int(usage['retries']) == 0
    assert usage['raw_sha256'] == sha(m.OUTPUT) and usage['label'] == p['label']
    assert float(usage['remaining_session_allowance_s']) == 3414.313
