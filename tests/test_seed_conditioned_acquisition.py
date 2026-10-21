"""Known synthetic arrays only. No registered study execution from tests."""
import copy
import hashlib
import inspect
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.seed import conditioned_acquisition as q,source_acquisition as a
from nexus.evolution1.catalogue import digest


def table():return np.asarray([[bool((17*(i+1))&(1<<x)) for x in range(16)] for i in range(910)],bool)


def test_public_query_features_and_blind_capacity():
    assert not {'answer','labels','task','outcomes','parameters'}&set(inspect.signature(q.extra_features).parameters)
    c=q.meter()
    assert q.extra_features('conditioned',0,[0,1,3,15],c)==[.4375,.328125,0.]
    assert c['query_distance_operations']==4
    assert q.extra_features('blind_capacity',7,[1],c)==q.extra_features('blind_capacity',7,[15],c)
    assert q.extra_features('conditioned',0,[1],c)!=q.extra_features('conditioned',0,[15],c)


def test_fit_is_source_only_with_matched_cases_and_fixed_models():
    t=table();groups=[0]*91+[1]*91+[2]*364+[3]*364
    source=[dict(role='source',task=100+i,answers=t[i].tolist()) for i in range(8)]
    c=q.configuration();first=q.fit(source,t,groups,c,q.meter())
    c['tasks']['target']=[999];second=q.fit(copy.deepcopy(source),t,groups,c,q.meter())
    assert first==second and len(first['base']['cases'])==288
    assert {k:len(m['beta']) for k,m in first['models'].items()}=={'blind':10,'blind_capacity':13,'conditioned':13}
    assert set(inspect.signature(q.fit).parameters)=={'source','table','groups','c','cost'}
    bad=copy.deepcopy(source);bad[0]['role']='target'
    with pytest.raises(ValueError,match='source_only'):q.fit(bad,t,groups,c,q.meter())
    pool=list(range(8));query=list(range(8,16));before=digest(first)
    for method in q.POLICIES:
        starts=[]
        for index in (1,3):
            oracle=a.LabelOracle(t[index,:8].tolist(),8)
            path=q.path(method,t,first,pool,query,oracle.reveal,q.meter())
            assert len(oracle.revealed)==8 and len(set(oracle.revealed))==8
            starts.append(path['steps'][0]['scores'])
        assert starts[0]==starts[1]
    assert digest(first)==before


def test_fresh_registration_uses_no_old_scores():
    entries=[dict(group=g) for g,size in enumerate([91,91,364,364]) for _ in range(size)]
    c=q.configuration();new,old=q.assignment(c,entries)
    used=[x for b in new for ids in b.values() for x in ids]
    assert len(used)==len(set(used))==128 and len(old)==192 and not set(used)&set(old)
    assert q.assignment(c,entries)==(new,old)
    for block in new:
        for role in ('source','target'):
            assert [sum(entries[i]['group']==g for i in block[role]) for g in range(4)]==[1,1,3,3]


@pytest.fixture(scope='module')
def synthetic_complete():
    # Full known-array integration fixture; never call q.run or the host.
    t=table();groups=[0]*91+[1]*91+[2]*364+[3]*364;entries=[dict(answers=row.tolist(),group=g) for row,g in zip(t,groups)]
    c=q.configuration();assigned,excluded=q.assignment(c,entries);blocks=[]
    for i,family in enumerate(c['families']):
        source=[dict(role='source',task=task,answers=t[index].tolist()) for task,index in zip(c['tasks']['train'][8*i:8*(i+1)],assigned[i]['source'])]
        cost=q.meter();model=q.fit(source,t,groups,c,cost);rows=[]
        for task,index in zip(c['tasks']['target'][8*i:8*(i+1)],assigned[i]['target']):
            pool,query=a.split_inputs(task);answers=t[index,pool].tolist();paths={};costs={}
            for method in q.POLICIES:
                costs[method]=q.meter();paths[method]=q.path(method,t,model,pool,query,a.LabelOracle(answers,8).reveal,costs[method])
            rows.append(dict(task=task,pool=pool,query=query,support_answers=answers,methods=paths,costs=costs))
        lock=digest(rows)
        for row,index in zip(rows,assigned[i]['target']):
            labels=t[index,row['query']].tolist();row['query_answers']=labels
            row['metrics']={m:{str(b):float(np.mean((np.asarray(p['snapshots'][str(b)]['prediction'])-labels)**2)) for b in a.BUDGETS} for m,p in row['methods'].items()}
            row['uniform_cost']=q.meter();row['metrics']['uniform_expectation']=a.uniform_assessment(t,row['pool'],row['query'],row['support_answers'],labels,row['uniform_cost'])
            row['metrics']['keep']={str(b):a.risk(t,np.arange(910),row['query'],labels,a.meter()) for b in a.BUDGETS}
        means={m:{str(b):sum(x['metrics'][m][str(b)] for x in rows)/8 for b in a.BUDGETS} for m in q.METHODS}
        blocks.append(dict(id=family,source=source,model=model,model_hash=digest(model),fit_cost=cost,rows=rows,means=means,locked_choices_hash=lock))
    root=Path(__file__).resolve().parents[1]
    names=set(json.loads((root/'artifacts/seed_source_acquisition.json').read_text())['seed_audit']['config_hashes'])|{'seed_source_acquisition.json','seed_query_context.json'}
    study=dict(config=c,declared_complete=True,blocks=blocks,assignment=assigned,excluded_historical_programs=excluded,
        catalogue_hash=digest(entries),catalogue_instructions=123,source_fits_frozen_before_targets=True,all_choices_locked_before_query_labels=True,
        frozen_before=a.FROZEN,frozen_after=a.FROZEN,seed_audit=a.seed_audit(root,c,names=names),analysis=q.analyze(blocks,c))
    resources=dict(real_steps=2048,source_labels=1024,target_support=512,target_query=512,updates=24,imagined_transitions=0,network_forwards=0,
        cached_target_answer_exposures=4096,target_policy_paths=512,program_instructions=123,selector_training_cases=2304,learned_coefficients=288,
        uniform_assessment_subsets=6848,cpu_s=.1,worker_wall_s=.1)
    return dict(study=study,resources=resources),entries


def test_full_synthetic_integration(synthetic_complete,monkeypatch):
    output,entries=synthetic_complete;monkeypatch.setattr(a,'catalogue',lambda:(entries,123))
    q.validate_output(copy.deepcopy(output),q.configuration(),dict(real_steps=2500))


@pytest.mark.parametrize('damage',['repetition','source_task','target_task','method','budget','nan','inf','bool','string','beta','normalizer','hidden_query','score','retention','checkpoint'])
def test_incomplete_invalid_and_leaking_results_rejected(synthetic_complete,monkeypatch,damage):
    output,entries=synthetic_complete;o=copy.deepcopy(output);s=o['study'];b=s['blocks'][0];row=b['rows'][0]
    monkeypatch.setattr(a,'catalogue',lambda:(entries,123))
    if damage=='repetition':s['blocks'].pop()
    elif damage=='source_task':b['source'].pop()
    elif damage=='target_task':b['rows'].pop()
    elif damage=='method':row['methods'].pop('conditioned')
    elif damage=='budget':row['metrics']['conditioned'].pop('2')
    elif damage in ('nan','inf','bool','string'):row['metrics']['conditioned']['1']={'nan':float('nan'),'inf':float('inf'),'bool':True,'string':'0.2'}[damage]
    elif damage=='beta':b['model']['models']['conditioned']['beta'][0]+=.01
    elif damage=='normalizer':b['model']['models']['conditioned']['scale'][0]*=2
    elif damage=='hidden_query':row['query_answers'][0]=not row['query_answers'][0]
    elif damage=='score':row['methods']['conditioned']['steps'][0]['scores'][0]+=.1
    elif damage=='retention':row['methods']['conditioned']['steps'][0]['posterior']=[0]
    else:s['frozen_after']={}
    with pytest.raises((ValueError,KeyError)):q.validate_output(o,q.configuration(),dict(real_steps=2500))


def test_config_and_readonly_receipt(tmp_path):
    root=Path(__file__).resolve().parents[1]
    assert json.loads((root/'configs/seed_conditioned_acquisition.json').read_text())==q.configuration()
    c=q.configuration();c['ridge']=10
    with pytest.raises(ValueError):q.config_check(c)
    (tmp_path/'artifacts').mkdir();(tmp_path/'artifacts/seed_conditioned_acquisition.json').write_text('{}')
    (tmp_path/'artifacts/seed_conditioned_acquisition_audit.json').write_text('{"valid":true,"raw_sha256":"wrong"}')
    with pytest.raises(ValueError,match='receipt'):q.saved_replay(tmp_path)


def test_independent_reference_math_and_catalogue_order():
    import importlib.util
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('conditioned_reference',root/'scripts/verify_seed_conditioned_acquisition.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    expected,instructions=module.reference_table();entries,count=a.catalogue()
    assert count==instructions==182000 and np.array_equal(expected,np.asarray([e['answers'] for e in entries]))
    assert [e['group'] for e in entries]==[0,1]*91+[2,3]*364
    t=table()[:25];weights=np.arange(1,26,dtype=float)
    for x in (0,3,7):
        assert module.weighted_gain(t,x,list(range(8,16)),weights)==pytest.approx(a.expected_gain(t,np.arange(25),x,list(range(8,16)),weights,a.meter()),abs=1e-12)
