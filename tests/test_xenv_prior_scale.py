"""Offline 2x prior-scale guards. No environment collection here."""
from __future__ import annotations
import pytest
from nexus.world import xenv_prior_scale as m
from nexus.world.planning_value import sha
from nexus.world import xenv_transfer as rung1


def test_locked_2x_budget_uses_rung1_net_and_rejects_closed_physics():
    cfg = m.load_config()
    assert cfg['prior_train'] == 1024 and cfg['prior_val'] == 256
    assert cfg['env_cap'] == 63200 and cfg['reset_base'] == 67000000
    counts = m.budget(cfg)
    assert counts['prior_collection'] == 38400
    assert counts['prior_collection'] + counts['target_pool'] + \
        counts['evaluation_episodes'] == 63200
    hold = m.holdout_from_rule()
    assert hold == [(0.0022, 0.0019, 0.08)]
    assert hold[0] not in m.occupied_physics()
    for closed in m.CLOSED_TARGETS:
        assert closed in m.occupied_physics()
    spec = m.target_spec(hold[0])
    assert spec.task_id == 'mcc_xenv6_t0'
    m.check_seeds(cfg)


def test_uses_closed_rung1_architecture():
    net = rung1.XEnvNet({'cartpole': (4, 2), 'mcc': (2, 3)}, seed=5)
    assert hasattr(net, 'shared') and not hasattr(net, 'film')
    import torch
    pred, logit = net('mcc', torch.zeros(3, 2), torch.tensor([0, 1, 2]))
    assert pred.shape == (3, 2) and logit.shape == (3, 1)


def test_allocation_binds_the_authorized_one_run_record():
    cfg = m.load_config()
    record = m.load_allocation()
    assert record['authorized'] is True and record['runs'] == 1
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    assert record['env_cap'] == 63200
    m.require_allocation(cfg)
    with pytest.raises(PermissionError, match='already authorized'):
        m.prep()


def test_recorded_prior_scale_result_passes_the_independent_audit():
    import json
    from pathlib import Path
    p = json.loads(m.OUTPUT.read_text())
    assert p['complete'] is True and p['label'] == 'xenv_prior_scale_not_established'
    audit = m.audit_results()
    assert audit['audit_passed'] is True and audit['raw_sha256'] == sha(m.OUTPUT)
    assert int(audit['new_environment_steps']) == 63200
    primary = p['groups']['primary']['interval']
    assert primary['n'] == 10 and primary['lo'] < 0 < primary['hi']
    usage = json.loads(Path('artifacts/research_session_xenv_prior_scale_usage.json').read_text())
    assert usage['status'] == 'complete' and usage['label'] == p['label']
    assert float(usage['remaining_session_allowance_s']) == 3359.478
