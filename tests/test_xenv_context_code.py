"""Offline rung-3 guards: context mechanics, isolation, no leakage, gates."""
from __future__ import annotations
from types import SimpleNamespace
import numpy as np
import pytest
import torch
from nexus.world import xenv_context_code as m
from nexus.world.planning_value import sha


def _toy(n, dim, n_actions, seed=0):
    rng = np.random.default_rng(seed)
    obs = rng.normal(size=(n, dim)).astype(np.float32)
    act = rng.integers(0, n_actions, size=n).astype(np.int64)
    nxt = obs + 0.01 * (act - 1).reshape(-1, 1).astype(np.float32)
    return SimpleNamespace(obs=obs, action=act, next_obs=nxt,
                           terminated=np.zeros(n, dtype=bool))


def _net(seed=5):
    return m.XEnvContextCodeNet({'cartpole': (4, 2), 'acrobot': (6, 3),
                                  'mountaincar': (2, 3), 'mcc': (2, 3)},
                                 context_dim=8, seed=seed)


def test_locked_configuration_budget_and_seeds():
    cfg = m.load_config()
    assert cfg['target_budgets'] == [128, 1024] and cfg['n_model_seeds'] == 10
    assert cfg['reset_base'] == 65000000 and cfg['collect_target_base'] == 65300000
    assert cfg['context_dim'] == 8 and cfg['context_support'] == 64
    counts = m.budget(cfg)
    assert counts['prior_collection'] + counts['target_pool'] + \
        counts['evaluation_episodes'] == cfg['env_cap'] == 44000
    assert counts['imagined'] == cfg['model_cap'] == 3072000
    m.check_seeds(cfg)


def test_holdout_rule_rejects_all_occupied_physics():
    cfg = m.load_config()
    hold = m.holdout_from_rule()
    assert hold == [(0.0027, 0.0009, 0.05)]
    assert hold[0] not in m.occupied_physics()
    assert (0.0025, 0.0015, 0.09) in m.occupied_physics()
    assert (0.0028, 0.0013, 0.065) in m.occupied_physics()
    assert (0.0034, 0.001, 0.055) in m.occupied_physics()
    assert hold == [tuple(cfg['target_physics'][0])]
    spec = m.target_spec(hold[0])
    assert spec.task_id == 'mcc_xenv4_t0' and spec.obs_dim == 2


def test_film_context_dimensions_and_gradient_flow():
    net = _net()
    assert net.film.weight.shape == (128, 8) and net.ctx_enc[0].weight.shape == (8, 64)
    z = net.frozen_context('mcc', np.zeros((4, 2), np.float32), np.zeros(4, np.int64))
    assert z.shape == (1, 8) and float(z.norm()) > 0
    net.set_context('mcc', z)
    obs = torch.zeros(3, 2)
    pred, logit = net('mcc', obs, torch.tensor([0, 1, 2]))
    assert pred.shape == (3, 2) and logit.shape == (3, 1)
    loss = pred.pow(2).sum() + logit.pow(2).sum()
    loss.backward()
    assert net.film.weight.grad is not None and net.film.weight.grad.abs().sum() > 0
    assert net.ctx_enc[0].weight.grad is None


def test_contextual_pretraining_trains_the_encoder_through_conditioning():
    net = _net()
    from nexus.world.xenv_transfer import fit_rms
    data = {'cartpole': (_toy(64, 4, 2, 1), fit_rms(_toy(64, 4, 2, 1).obs))}
    before = net.ctx_enc[0].weight.detach().clone()
    film_before = net.film.weight.detach().clone()
    m.pretrain_contextual(net, data, 64, epochs=2, lr=1e-3, seed=3)
    assert not torch.equal(before, net.ctx_enc[0].weight)
    assert not torch.equal(film_before, net.film.weight)


def test_pretrain_survives_multiple_batches_without_double_backward():
    net = _net()
    from nexus.world.xenv_transfer import fit_rms
    data = {'cartpole': (_toy(200, 4, 2, 1), fit_rms(_toy(200, 4, 2, 1).obs))}
    m.pretrain_contextual(net, data, 64, epochs=1, lr=1e-3, seed=3, batch_size=64)


def test_identical_architecture_between_arms():
    a, b = _net(11), _net(11)
    sa = {k: v.clone() for k, v in a.state_dict().items()}
    a.load_state_dict(b.state_dict())
    assert all(torch.equal(v, sa[k]) for k, v in a.state_dict().items())
    assert a.n_parameters() == b.n_parameters()


def test_zero_initialized_film_is_identity_at_construction():
    net = _net()
    z1 = net.frozen_context('mcc', np.ones((8, 2), np.float32), np.zeros(8, np.int64))
    net.set_context('mcc', z1)
    o1, _l1 = net('mcc', torch.zeros(3, 2), torch.tensor([0, 1, 2]))
    z2 = net.frozen_context('mcc', -np.ones((8, 2), np.float32), np.ones(8, np.int64))
    net.set_context('mcc', z2)
    o2, _l2 = net('mcc', torch.zeros(3, 2), torch.tensor([0, 1, 2]))
    assert torch.equal(o1, o2)


def test_context_inference_is_support_only_and_isolated():
    net = _net()

    class Guarded:
        def __init__(self, ds):
            self._ds = ds

        def __getattr__(self, key):
            if key not in ('obs', 'action'):
                raise AssertionError(f'context inference touched {key}')
            return getattr(self._ds, key)
    ds = Guarded(_toy(16, 2, 3))
    obs, act = m.support_arrays(ds, 8)
    assert obs.shape == (8, 2) and act.shape == (8,)
    z = net.frozen_context('mcc', obs, act)
    assert z.shape == (1, 8)
    z2 = net.frozen_context('mcc', obs, act)
    assert torch.equal(z, z2)
    z3 = net.frozen_context('mcc', -obs, act)
    assert not torch.equal(z, z3)


def test_context_diagnostics_flag_identification_not_adaptation():
    net = _net()
    from nexus.world.xenv_transfer import fit_rms
    src = {n: (fit_rms(_toy(32, d, a, i).obs).normalize(_toy(32, d, a, i).obs),
               _toy(32, d, a, i).action)
           for i, (n, d, a) in enumerate((('cartpole', 4, 2), ('acrobot', 6, 3)))}
    tgt = (fit_rms(_toy(8, 2, 3, 9).obs).normalize(_toy(8, 2, 3, 9).obs),
           _toy(8, 2, 3, 9).action)
    d = m.context_diagnostics(net, src, tgt)
    assert d['nearest_source_distance'] > 0 and d['mean_inter_source_distance'] > 0
    assert d['nearest_source_ratio'] is not None


def test_classify_primary_requires_interval_and_completeness():
    assert m.classify_primary(10.0, 1.0, 20.0, 10) == 'xenv_context_code_beats_scratch'
    assert m.classify_primary(-10.0, -20.0, -1.0, 10) == 'xenv_context_code_harm_established'
    assert m.classify_primary(10.0, -1.0, 20.0, 10) == 'xenv_context_code_not_established'
    assert m.classify_primary(10.0, 1.0, 20.0, 9) == 'incomplete'
    assert m.classify_primary(10.0, 1.0, 20.0, 10, complete=False) == 'incomplete'


def test_support_encoder_cannot_see_transition_residual():
    net = _net()
    sig = net.infer_context.__func__.__code__.co_varnames
    assert 'support_obs' in sig and 'support_action' in sig
    assert 'next_obs' not in sig and 'residual' not in sig
    class Probe:
        def __init__(self, ds):
            self._ds = ds
        def __getattr__(self, key):
            if key in ('next_obs', 'terminated', 'reward'):
                raise AssertionError(f'support context touched {key}')
            if key not in ('obs', 'action'):
                raise AssertionError(f'context inference touched {key}')
            return getattr(self._ds, key)
    ds = Probe(_toy(16, 2, 3))
    obs, act = m.support_arrays(ds, 8)
    z = net.infer_context('mcc', obs, act)
    assert z.shape == (1, 8)


def test_epoch_recipe_is_135_loops_not_the_label_10():
    cfg = m.load_config()
    assert cfg['pretrain_epochs'] == 15
    assert cfg['finetune_epochs'] == 20
    assert cfg['reference_epochs'] == 20
    assert cfg['training_epochs_budget'] == 10
    n_b = len(cfg['target_budgets'])
    xenv = cfg['pretrain_epochs'] + n_b * cfg['finetune_epochs']
    scratch = n_b * cfg['finetune_epochs']
    reference = n_b * cfg['reference_epochs']
    assert (xenv, scratch, reference, xenv + scratch + reference) == (55, 40, 40, 135)
    counts = m.budget(cfg)
    assert 'epochs' not in counts and 'updates' not in counts


def test_post_finetune_diagnostic_target_code_is_not_the_frozen_z():
    net = _net()
    support = (np.ones((8, 2), np.float32), np.zeros(8, np.int64))
    z_used = net.frozen_context('mcc', *support)
    net.set_context('mcc', z_used)
    with torch.no_grad():
        net.in_proj['mcc'].weight.add_(0.5)
    z_after = net.frozen_context('mcc', *support)
    assert not torch.equal(z_used, z_after)
    assert torch.equal(net.contexts['mcc'], z_used.reshape(-1, 8))


def test_parent_hashes_and_locked_provenance():
    cfg = m.load_config()
    for path, digest in cfg['parents'].items():
        assert sha(path) == digest, path
    assert sha(m.CONFIG) == m.LOCKED_CONFIG
    assert sha(m.PROTOCOL) == m.LOCKED_PROTOCOL


def test_allocation_binds_the_authorized_one_run_record():
    cfg = m.load_config()
    record = m.load_allocation()
    assert record['authorized'] is True and record['runs'] == 1
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    assert record['protocol_sha256'] == sha(m.PROTOCOL) == m.LOCKED_PROTOCOL
    m.require_allocation(cfg)
    with pytest.raises(PermissionError, match='already authorized'):
        m.prep()
