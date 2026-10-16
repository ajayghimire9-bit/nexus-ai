"""No scalar is fit to the real research data in these synthetic tests."""
import copy
import itertools
import json
import subprocess
import numpy as np
import pytest
from nexus.world import source_scalar_calibration as m
from test_commitment_value import master_capture
from test_visited_commitment import visited_capture


def cells(slope):
    return [dict(decoder=d,task=t,targets=(np.arange(4)*slope+10).tolist(),predictions={str(s):dict(imagined=list(range(4))) for s in range(5)}) for d,t in itertools.product(range(10),range(8))]


@pytest.mark.parametrize('slope,beta',[(.25,.25),(2.,1.),(-1.,0.),(0.,0.)])
def test_closed_form_recovery_and_registered_bounds(slope,beta):
    result=m.source_terms(cells(slope));assert result['beta']==beta
    assert result['source_examples']==1600 and len(result['groups'])==400


def test_degenerate_predictor_has_defined_zero_scalar():
    rows=cells(1.)
    for row in rows:
        for r in row['predictions'].values():r['imagined']=[2.]*4
    result=m.source_terms(rows);assert result['degenerate'] is True and result['beta']==0.


def test_development_or_query_outcomes_cannot_affect_scalar():
    rows=cells(.5);expected=m.source_terms(rows)
    rows.extend([dict(decoder=d,task=t,targets=['forbidden'],predictions=None) for d,t in itertools.product(range(10),range(8,11))])
    assert m.source_terms(rows)==expected


def test_missing_source_task_or_invalid_outcome_rejected():
    rows=cells(1.);rows.pop()
    with pytest.raises(ValueError):m.source_terms(rows)
    rows=cells(1.);rows[0]['targets'][0]=False
    with pytest.raises(ValueError):m.source_terms(rows)


def test_scalar_limits_and_pure_score_interface():
    s=dict(base=np.arange(16,dtype=float).tolist(),survival=[.9]*16,terminal=np.arange(16,dtype=float).tolist())
    assert np.allclose(m.calibrated_score(s,1.,-20.),np.arange(16)*1.9)
    assert np.allclose(m.calibrated_score(s,0.,-20.),np.arange(16)-18.)
    before=m.calibrated_score(s,.25,-20.)
    unrelated_outcomes=[1e20]*16
    assert np.array_equal(before,m.calibrated_score(s,.25,-20.)) and unrelated_outcomes[0]==1e20
    with pytest.raises(ValueError):m.calibrated_score(s,2.,0.)


def test_new_seeds_budget_and_missing_fit_block_before_environment(monkeypatch,tmp_path):
    cfg=m.load_config();assert m.visited.budget(cfg)['model_states']==15667200
    monkeypatch.setattr(m,'FIT',tmp_path/'missing.json')
    def forbidden(*args,**kwargs):raise AssertionError('no evaluation without committed fit')
    monkeypatch.setattr(m.visited,'execute',forbidden)
    with pytest.raises((FileNotFoundError,PermissionError)):m.execute()


def test_custom_runner_cannot_skip_protocol_preflight():
    with pytest.raises(PermissionError,match='preflight'):m.visited.execute(configuration={'time_cap_s':1})


def test_synthetic_aggregation_and_equal_visitor_weights():
    cfg=m.load_config();rows=[]
    for d,t,v in itertools.product(range(10),range(3),range(2)):
        metrics={name:{k:0. for k in m.FIELDS} for name in m.visited.prior.NAMES}
        for r in metrics.values():r.update(gain_vs_base=20. if v==0 else -10.,gain_vs_uncalibrated=10.)
        rows.append(dict(decoder=d,task=t,state=v,metrics=metrics))
    result=m.summarize(rows,cfg)
    assert result['groups']['pooled']['gain_vs_base']['interval']['mean']==5.
    assert result['groups']['pooled']['gain_vs_base']['interval']['n']==10
    assert result['label']=='source_scalar_selection_gain'
    for corruption in ('decoder','visitor','context','metric'):
        bad=copy.deepcopy(rows)
        if corruption=='decoder':bad=[r for r in bad if r['decoder']!=9]
        elif corruption=='visitor':bad=[r for r in bad if r['state']!=1]
        elif corruption=='context':del bad[0]['metrics']['4']
        else:bad[0]['metrics']['zero']['gain_vs_base']=False
        with pytest.raises((ValueError,KeyError)):m.summarize(bad,cfg)


def test_all_source_fit_manifest_fields_must_be_committed(monkeypatch,tmp_path):
    cfg=m.load_config();path=tmp_path/'fit.json';terms=m.source_terms(cells(.5))
    fit=dict(terms,complete=True,source_dirty=False,config_sha256=m.sha(m.CONFIG),protocol_sha256=m.sha(m.PROTOCOL),source_sha256=m.sha('artifacts/terminal_value_calibration.json'),proof_sha256=m.sha('artifacts/terminal_value_calibration_validation.json'),wall_clock_s=1.,implementation_sha=cfg['starting_sha'])
    path.write_text(json.dumps(fit));monkeypatch.setattr(m,'FIT',path);monkeypatch.setattr(m,'source_terms',lambda rows:terms)
    assert m.require_fit(cfg,committed=False)['beta']==.5
    monkeypatch.setattr(subprocess,'check_output',lambda *args,**kwargs:'different or absent committed content')
    with pytest.raises(ValueError,match='commit immutable'):m.require_fit(cfg)


def test_closed_visitor_rng_sets_are_not_reused():
    cfg=m.load_config();old=m.visited.load_config()
    assert not set().union(*m.seed_sets(cfg)) & set().union(*m.seed_sets(old))


def test_raw_cell_beta_one_exactly_recovers_original_correction(visited_capture):
    p,_,_,_=visited_capture;result=m.row_metrics(p['cells'][0],1.,-100.)
    for metrics in result.values():
        assert metrics['gain_vs_uncalibrated']==0.
        assert metrics['block_calibrated']==metrics['block_uncalibrated']
        assert metrics['first_calibrated']==metrics['first_uncalibrated']
        assert metrics['centered_error_benefit']==0.
