"""Toy public tables only. Never run a registered acquisition experiment."""
import copy
import inspect
import hashlib
import json
import itertools as it
from pathlib import Path
import numpy as np
import pytest
from nexus.evolution1.catalogue import digest
from nexus.seed import source_acquisition as a


def toy_table():
    return np.asarray([[bool((17*(i+1))&(1<<q)) for q in range(16)] for i in range(910)],bool)


def test_preanswer_interface_and_frozen_choices():
    table=toy_table();ids=np.arange(910);observed=[(0,True)];first=[]
    assert not {'answer','labels','query_outcomes','task_id'} & set(inspect.signature(a.features).parameters)
    f=a.features(table,ids,7,observed,7,a.meter())
    assert len(f)==10 and all(np.isfinite(f))
    model=dict(scale=[1.]*10,beta=[1.]+[0.]*9,static=[0.]*16,prior_weights=[1.]*910)
    before=digest(model);pool=list(range(8));query=list(range(8,16))
    for rule in (0,4,10):
        oracle=a.LabelOracle(table[rule,:8].tolist(),8)
        data=a.path('learned',table,model,pool,query,oracle.reveal,a.meter());first.append(data['steps'][0]['index'])
        assert len(oracle.revealed)==len(set(oracle.revealed))==8
        assert data['steps'][0]['scores']==[1.]*8
    assert len(set(first))==1 and digest(model)==before


def test_expected_risk_matches_explicit_hypothesis_average():
    table=toy_table()[:18];ids=np.arange(18);query=[8,9,10];weights=np.arange(1,19,dtype=float)
    p=table[:,query].mean(0);before=sum(weights[i]*np.mean((p-table[i,query])**2) for i in ids)/weights.sum()
    after=0.
    for i in ids:
        same=ids[table[:,2]==table[i,2]];pred=table[np.ix_(same,query)].mean(0)
        after+=weights[i]*np.mean((pred-table[i,query])**2)/weights.sum()
    assert a.expected_gain(table,ids,2,query,weights,a.meter())==pytest.approx(before-after,abs=1e-12)


def test_uniform_subset_equals_permutation_marginal():
    table=toy_table()[:8];pool=list(range(8));query=list(range(8,16));truth=table[2]
    actual=a.uniform_assessment(table,pool,query,truth[:8].tolist(),truth[8:].tolist(),a.meter())
    # Independent budget-one arithmetic; no hidden outputs enter a selector.
    losses=[]
    for q in pool:
        ids=np.flatnonzero(table[:,q]==truth[q]);p=table[np.ix_(ids,query)].mean(0)
        losses.append(float(np.mean((p-truth[query])**2)))
    assert actual['1']==pytest.approx(sum(losses)/8)


def test_source_scaling_and_target_outcomes_isolated():
    table=toy_table();groups=[0]*91+[1]*91+[2]*364+[3]*364
    source=[dict(role='source',task=40+i,answers=table[i].tolist()) for i in range(16)]
    one=a.fit_selector(source,table,groups,a.configuration(),a.meter())
    # There is no target/assessment argument or global target state to change.
    two=a.fit_selector(copy.deepcopy(source),table,groups,a.configuration(),a.meter())
    assert one==two and len(one['scale'])==len(one['beta'])==10
    bad=copy.deepcopy(source);bad[0]['role']='target'
    with pytest.raises(ValueError):a.fit_selector(bad,table,groups,a.configuration(),a.meter())


@pytest.fixture(scope='module')
def constructed_base():
    # Constructed truth tables, not the registered executable polynomials.
    table=toy_table();groups=[0]*91+[1]*91+[2]*364+[3]*364
    entries=[dict(answers=row.tolist(),group=g) for row,g in zip(table,groups)]
    c=a.configuration();assigned=a.assignment(c,entries);blocks=[]
    for i,family in enumerate(c['families']):
        source=[dict(role='source',task=task,answers=entries[index]['answers']) for task,index in zip(c['tasks']['train'][16*i:16*(i+1)],assigned[i]['source'])]
        fit_cost=a.meter();model=a.fit_selector(source,table,groups,c,fit_cost);rows=[]
        for task,index in zip(c['tasks']['target'][8*i:8*(i+1)],assigned[i]['target']):
            pool,query=a.split_inputs(task);answers=table[index,pool].tolist();methods={};costs={}
            for m in a.POLICIES:
                costs[m]=a.meter();methods[m]=a.path(m,table,model,pool,query,a.LabelOracle(answers,8).reveal,costs[m])
            rows.append(dict(task=task,pool=pool,query=query,support_answers=answers,methods=methods,costs=costs))
        lock=digest(rows)
        for row,index in zip(rows,assigned[i]['target']):
            labels=table[index,row['query']].tolist();row['query_answers']=labels
            row['metrics']={m:{str(b):float(np.mean((np.asarray(d['snapshots'][str(b)]['prediction'])-labels)**2)) for b in a.BUDGETS} for m,d in row['methods'].items()}
            row['uniform_cost']=a.meter();row['metrics']['uniform_expectation']=a.uniform_assessment(table,row['pool'],row['query'],row['support_answers'],labels,row['uniform_cost'])
            keep=a.risk(table,np.arange(len(table)),row['query'],labels,a.meter());row['metrics']['keep']={str(b):keep for b in a.BUDGETS}
        means={m:{str(b):sum(row['metrics'][m][str(b)] for row in rows)/8 for b in a.BUDGETS} for m in a.METHODS}
        blocks.append(dict(id=family,source=source,fit_cost=fit_cost,model=model,model_hash=digest(model),rows=rows,locked_choices_hash=lock,means=means))
    study=dict(config=c,declared_complete=True,blocks=blocks,assignment=assigned,catalogue_hash=digest(entries),catalogue_instructions=123,
        frozen_before=a.FROZEN,frozen_after=a.FROZEN,all_source_fits_frozen_before_targets=True,all_choices_locked_before_query_labels=True)
    study['seed_audit']=a.seed_audit(Path(__file__).resolve().parents[1],c);study['analysis']=a.summarize(blocks,c)
    resources=dict(real_steps=3072,source_labels=2048,target_support=512,target_query=512,updates=8,imagined_transitions=0,
        network_forwards=0,fitted_ridge_models=8,learned_coefficients=80,selector_training_cases=4608,program_instructions=123,cpu_s=.1,worker_wall_s=.1,
        cached_target_answer_exposures=3072,target_policy_paths=384,uniform_assessment_subsets=6848)
    return dict(study=study,resources=resources),c,entries


@pytest.fixture
def complete(constructed_base,monkeypatch):
    o,c,entries=copy.deepcopy(constructed_base);monkeypatch.setattr(a,'catalogue',lambda:(entries,123))
    return o,c,dict(real_steps=4000)


def test_complete_fixture_fixed_learner_and_task_separation(complete):
    o,c,caps=complete;a.validate_output(o,c,caps)
    used=[i for block in o['study']['assignment'] for ids in block.values() for i in ids]
    assert len(used)==len(set(used))==192
    for x in o['study']['blocks']:
        for row in x['rows']:
            assert not set(row['pool']) & set(row['query'])
            assert len({row['metrics'][m]['8'] for m in a.METHODS if m!='keep'})==1


@pytest.mark.parametrize('damage',['repetition','task','policy','budget','coefficient','scale','source','hidden_answer','score','checkpoint','nan'])
def test_fail_closed(complete,damage):
    o,c,caps=complete;s=o['study'];x=s['blocks'][0];row=x['rows'][0]
    if damage=='repetition':s['blocks'].pop()
    elif damage=='task':x['rows'].pop()
    elif damage=='policy':row['methods'].pop('learned')
    elif damage=='budget':row['metrics']['learned'].pop('2')
    elif damage=='coefficient':x['model']['beta'][0]+=.1
    elif damage=='scale':x['model']['scale'][1]*=2
    elif damage=='source':x['source'][0]['role']='target'
    elif damage=='hidden_answer':row['query_answers'][0]=not row['query_answers'][0]
    elif damage=='score':row['methods']['learned']['steps'][0]['scores'][0]+=.01
    elif damage=='checkpoint':s['frozen_after']={}
    else:o['resources']['cpu_s']=float('nan')
    with pytest.raises((ValueError,KeyError)):a.validate_output(o,c,caps)


def test_config_exact_and_catalogue_is_existing_interpreter():
    c=json.loads((Path(__file__).resolve().parents[1]/'configs/seed_source_acquisition.json').read_text());a.config_check(c)
    bad=copy.deepcopy(c);bad['ridge']=2
    with pytest.raises(ValueError):a.config_check(bad)
    assert 'programs.execute' in inspect.getsource(a.catalogue)


def test_public_catalogue_semantics_no_registered_task_sampling():
    entries,instructions=a.catalogue()
    assert len(entries)==910 and instructions==182000
    assert [sum(e['group']==g for e in entries) for g in range(4)]==[91,91,364,364]
    assert len({tuple(e['answers']) for e in entries})==910


def test_readonly_gui_requires_audited_hash_without_refitting(tmp_path,monkeypatch):
    folder=tmp_path/'artifacts';folder.mkdir()
    r=dict(config=a.configuration(),declared_complete=True,host_receipt=dict(wall_s=1.,peak_sampled_rss_mb=30),
        execution_sha='fixture',resources={},analysis={})
    raw=json.dumps(r).encode();(folder/'seed_source_acquisition.json').write_bytes(raw)
    audit=folder/'seed_source_acquisition_audit.json'
    with pytest.raises(FileNotFoundError):a.saved_replay(tmp_path)
    audit.write_text(json.dumps(dict(valid=True,raw_sha256='wrong')))
    with pytest.raises(ValueError,match='audit_required_or_hash'):a.saved_replay(tmp_path)
    audit.write_text(json.dumps(dict(valid=True,raw_sha256=hashlib.sha256(raw).hexdigest())))
    monkeypatch.setattr(a,'validate_output',lambda *args:pytest.fail('view triggered numeric refit'))
    assert a.saved_replay(tmp_path)['verification']=='saved_independent_audit_hash'
