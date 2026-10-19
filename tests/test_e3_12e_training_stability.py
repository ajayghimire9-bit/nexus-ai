"""Authored fixtures test extraction/statistics; no query outcomes decoded."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from nexus.evolution2 import selection_stability as audit

ROOT=Path(__file__).resolve().parents[1]


def example():
    c=dict(families=['pendulum','acrobot'],model_bundles=[0,1],training_episodes=list(range(8)),proposal_seed=73512,return_scale=100.,training_schedule={})
    rows=[]
    for f in c['families']:
        for b in c['model_bundles']:
            c['training_schedule'][f'{f}:{b}']=['switch']*4+['rank_blend']*4
            for e in range(12):
                if e>=8:
                    rows.append(dict(paths={'__QUERY_SECRET__':True},role='evaluation'));continue
                kind='switch' if e<4 else 'rank_blend';parent=0. if e<4 else -100.
                # Child on easier resets looks good absolutely, yet loses paired.
                child=parent-10. if kind=='switch' else parent+10.
                def path(value):return dict(steps=[dict(reward=value/200) for _ in range(200)],cpu_s=1.,return_value=value)
                paths={'parent':path(parent),kind:path(child)}
                for p in paths.values():p['return']=p.pop('return_value')
                q=dict(phase='training',pair_id=f'{f}:{b}:{e}',context_hash='f'*64,reset_seed=100+e,planner_seed=200+e)
                rows.append(dict(paths=paths,role='training',family=f,bundle=b,episode=e,training_operator=kind,protocol=q))
    return json.dumps(dict(rows=rows,analysis={'__QUERY_SECRET__':'unused'})),c


def test_projection_never_decodes_queries_even_when_role_is_last(monkeypatch):
    text,c=example();real=audit.json.loads
    def guarded(raw,*args,**kwargs):
        if '__QUERY_SECRET__' in raw:raise AssertionError('query_outcome_decoding')
        return real(raw,*args,**kwargs)
    monkeypatch.setattr(audit.json,'loads',guarded)
    projection=audit.project_training(text,c)
    assert projection['query_outcomes_decoded']==0 and len(projection['rows'])==32
    altered=text.replace('__QUERY_SECRET__','CHANGED_CLOSED_OUTCOMES')
    assert audit.project_training(altered,c)['training_rows_sha256']==projection['training_rows_sha256']


def test_known_decomposition_sign_reversal_and_dependent_deletions():
    text,c=example();p=audit.project_training(text,c);result=audit.analyze(p,c)
    assert len(result['models'])==4
    for m in result['models']:
        f=m['full'];assert f['raw_advantages']['switch']==40 and f['paired_advantages']['switch']==-10 and f['reset_offsets']['switch']==50
        assert f['choices']['raw_parent']=='switch' and f['choices']['paired_guard']=='rank_blend'
        assert set(m['raw_paired_sign_disagreements'])=={'switch','rank_blend'}
        assert len(m['deletions']['leave_one_reset_out'])==8 and len(m['deletions']['balanced_leave_pair_out'])==16
        assert m['balanced_partition_count']==70
        for row in m['deletions']['balanced_leave_pair_out']:assert row['counts']=={'switch':3,'rank_blend':3}
    assert audit.analyze(p,c)==result


@pytest.mark.parametrize('fault',['model','reset','arm','reward','nan','cpu','identity','schedule'])
def test_projection_rejects_incomplete_or_invalid_training(fault):
    text,c=example();p=json.loads(text);r=p['rows'][0]
    if fault=='model':p['rows']=[x for x in p['rows'] if x.get('bundle')!=1]
    elif fault=='reset':p['rows'].pop(0)
    elif fault=='arm':del r['paths']['parent']
    elif fault=='reward':r['paths']['parent']['return']+=1
    elif fault=='nan':r['paths']['parent']['return']=float('nan')
    elif fault=='cpu':r['paths']['parent']['cpu_s']=True
    elif fault=='identity':r['episode']=False
    else:r['training_operator']='rank_blend'
    with pytest.raises(ValueError):audit.project_training(json.dumps(p),c)


def test_single_extreme_training_reset_can_change_a_choice():
    text,c=example();p=audit.project_training(text,c)
    for r in p['rows']:
        k=r['training_operator'];r['paths']['parent']['return']=0.;r['paths'][k]['return']=-1.
        if r['episode']==0:r['paths'][k]['return']=100.
    result=audit.analyze(p,c)
    assert all(m['choice_flip_counts']['leave_one_reset_out']['raw_parent']==1 for m in result['models'])


def test_scope_allocation_and_inputs_are_exact():
    c=json.loads((ROOT/'configs/e3_12e_training_stability.json').read_text());a=json.loads((ROOT/'configs/e3_12e_training_stability_allocation.json').read_text())
    for kind,path in [('config','configs/e3_12e_training_stability.json'),('protocol','docs/NEXUS_E3_12E_TRAINING_STABILITY_PROTOCOL.md')]:assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==a[kind+'_sha256']
    assert c['env_cap']==c['imagined_cap']==c['neural_inference_cap']==c['ridge_fit_cap']==0
    assert a['runs']==1 and a['automatic_retry'] is False and a['session_used_before_s']==1806.2957189570038
