"""Synthetic fixtures only; never call the registered scientific runner."""
import copy
import inspect
import json
import math
import statistics as st
from pathlib import Path
import pytest
from nexus.evolution1.catalogue import digest
from nexus.seed import investigation_transfer as it

ROOT=Path(__file__).resolve().parents[1]


def library():
    return it.learn([dict(role='source',episode=str(h),answers=list(it.TABLE[h]),hypothesis=h) for h in range(8)],max_depth=3,max_nodes=15)


@pytest.mark.parametrize('family',['attributes','thresholds','temporal','spatial'])
def test_public_bindings_independent_of_hidden_law(family):
    b=it.binding(7,family)
    for bits in it.BITS:assert it.decode(it.encode(bits,b,4),b)==bits


def test_pre_answer_boundary_and_freeze():
    lib=library();before=digest(lib);calls=[]
    def reveal(q):
        calls.append(q);return it.TABLE[3][q]
    result=it.adapt('learned',lib,reveal)
    assert calls==[s['question'] for s in result['steps']]
    assert digest(lib)==before
    assert set(inspect.signature(it.choose).parameters)=={'method','posterior','remaining','history','library','random_order','costs'}
    # Unrevealed truth and final labels cannot enter the pure choice function.
    initial=[]
    for h in range(8):
        initial.append(it.adapt('learned',lib,lambda q:it.TABLE[h][q])['steps'][0]['question'])
    assert len(set(initial))==1


@pytest.mark.parametrize('method',it.METHODS)
def test_budget_unique_questions_and_identification(method):
    for h in range(8):
        oracle=it.LabelOracle(list(it.TABLE[h]),8)
        d=it.adapt(method,library(),oracle.reveal,4)
        assert d['snapshots']['8']['posterior']==[h]
        assert len(d['steps'])<=8
        assert d['snapshots']['1']['questions']==1
        assert d['costs']['search_nodes']<=8*4096
        assert d==it.adapt(method,library(),it.LabelOracle(list(it.TABLE[h]),8).reveal,4)


def fixture():
    """Exact grid with fabricated known fixture answers, NOT registered outcomes."""
    c=json.loads((ROOT/'configs/seed_investigation_transfer.json').read_text());lib=library()
    r=dict(config=c,declared_complete=True,frozen_before_target=True,choices_locked_before_final=True,library=lib,library_hash=digest(lib),unchanged_library=True,retention_before=[None]*32,retention_after=[None]*32,source=[],rows=[])
    r.update(frozen_checkpoints_before=dict(it.FROZEN),frozen_checkpoints_after=dict(it.FROZEN))
    for i,seed in enumerate(c['tasks']['train']):
        family=c['source_families'][i//16];b=it.binding(0,family)
        episodes=[dict(id=f'source-{seed}-{q}',bits=list(bits),raw=it.encode(bits,b,0),answer=it.TABLE[0][q]) for q,bits in enumerate(it.BITS)]
        r['source'].append(dict(task=seed,family=family,binding=b,episodes=episodes))
    r['source_hash']=digest(r['source'])
    template={m:it.adapt(m,lib,it.LabelOracle(list(it.TABLE[0]),8).reveal,0) for m in it.METHODS}
    for i,seed in enumerate(c['tasks']['target']):
        family=c['target_families'][i//16];b=it.binding(0,family)
        r['rows'].append(dict(task=seed,family=family,binding=b,pool=[it.encode(bits,b,0) for bits in it.BITS],support_bank_answers=list(it.TABLE[0]),methods=copy.deepcopy(template)))
    r['choices_hash']=digest(r['rows'])
    for row in r['rows']:
        row['final']=[dict(id=f"final-{row['task']}-{j}",raw=it.encode(it.BITS[j%8],row['binding'],0),bits=list(it.BITS[j%8]),answer=it.TABLE[0][j%8]) for j in range(32)]
        row['data_hash']=digest(dict(binding=row['binding'],pool=row['pool'],final=row['final']))
        for d in row['methods'].values():
            d['predictions']={};d['metrics']={}
            for b in it.BUDGETS:
                pred=[st.mean(it.hypotheses(f['bits'])[h] for h in d['snapshots'][str(b)]['posterior']) for f in row['final']]
                d['predictions'][str(b)]=pred
                d['metrics'][str(b)]=dict(accuracy=st.mean((p>=.5)==f['answer'] for p,f in zip(pred,row['final'])),brier=st.mean((p-f['answer'])**2 for p,f in zip(pred,row['final'])))
    r['analysis']=it.analysis(r['rows'],c)
    work=dict(source_answers=256,target_pool_observations=256,target_answers=sum(len(d['steps']) for row in r['rows'] for d in row['methods'].values()),final_observations=1024,assessment_predictions=20480,real_steps=1536,updates=0,imagined_transitions=0,network_forwards=0)
    return dict(study=r,resources=work),c,dict(real_steps=5000,updates=0,imagined_transitions=0)


def test_complete_fixture_and_independent_interval():
    o,c,cap=fixture();it.validate_output(o,c,cap)
    xs=list(range(32));p=it.paired(xs)
    variance=sum((x-15.5)**2 for x in xs)/31
    assert p['low']==pytest.approx(15.5-2.039513*math.sqrt(variance/32))
    assert o['study']['analysis']['means']['learned']['questions']==len(o['study']['rows'][0]['methods']['learned']['steps'])


@pytest.mark.parametrize('damage',['task','source','method','budget','episode','nan','hash','freeze','resource','posterior','answer','checkpoint'])
def test_missing_or_corrupt_cells_fail_closed(damage):
    o,c,cap=fixture();r=o['study'];row=r['rows'][0];d=row['methods']['learned']
    if damage=='task':r['rows'].pop()
    elif damage=='source':r['source'].pop()
    elif damage=='method':row['methods'].pop('greedy')
    elif damage=='budget':d['metrics'].pop('2')
    elif damage=='episode':row['final'].pop()
    elif damage=='nan':d['predictions']['1'][0]=float('nan')
    elif damage=='hash':r['library_hash']='bad'
    elif damage=='freeze':r['choices_locked_before_final']=False
    elif damage=='resource':o['resources']['real_steps']+=1
    elif damage=='posterior':d['snapshots']['1']['posterior']=[0]
    elif damage=='checkpoint':r['frozen_checkpoints_after']={}
    else:row['support_bank_answers'][0]=not row['support_bank_answers'][0]
    with pytest.raises((ValueError,KeyError)):it.validate_output(o,c,cap)


def test_target_labels_never_refit_library(monkeypatch):
    lib=library();before=digest(lib)
    monkeypatch.setattr(it,'learn',lambda *a,**kw:pytest.fail('target refitting'))
    for h in range(8):it.adapt('learned',lib,it.LabelOracle(list(it.TABLE[h]),8).reveal)
    assert digest(lib)==before


def test_config_cannot_expand_cap_or_reuse_tasks():
    _,c,_=fixture();c['max_wall_s']=61
    with pytest.raises(ValueError):it.config_check(c)


def test_oracle_rejects_extra_or_repeated_answers():
    oracle=it.LabelOracle([True,False],1)
    oracle.reveal(0)
    with pytest.raises(ValueError):oracle.reveal(0)
    with pytest.raises(ValueError):oracle.reveal(1)
