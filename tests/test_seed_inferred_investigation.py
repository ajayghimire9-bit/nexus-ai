"""Known fixture tables only. Never collect registered family outcomes."""
import copy
import json
import math
from pathlib import Path
import random
import pytest
from nexus.evolution1.catalogue import digest
from nexus.seed import inferred_investigation as n, investigation_transfer as b, compiled_greedy as cg


def traces(table=None):
    table=table or b.TABLE
    return [dict(role='source',episode=f'fixture-{i}',answers=list(table[i%8]),hypothesis=i%8) for i in range(32)]


def test_source_only_model_and_exact_custom_compilation(monkeypatch):
    table=[list(reversed(row)) for row in reversed(b.TABLE)]
    source=traces(table)
    monkeypatch.setattr(n,'evaluator_table',lambda *a:pytest.fail('hidden outcomes accessed'))
    fitted=n.fit_procedures(source);before=digest(fitted)
    assert fitted['model']['table']==table
    assert fitted['policy']['grammar_sha256']==digest(table)
    assert fitted['model']['work']==dict(response_reads=256,consistency_checks=192,class_label_reads=32)
    for law in range(8):
        a=n.adapt('compiled_greedy',fitted,b.LabelOracle(table[law],8).reveal)
        z=n.adapt('greedy',fitted,b.LabelOracle(table[law],8).reveal)
        assert cg.decision(a)==cg.decision(z)
    assert digest(fitted)==before


@pytest.mark.parametrize('damage',['role','missing_class','noise','duplicate_episode','numeric_answer','class_id'])
def test_invalid_source_rejected(damage):
    s=traces()
    if damage=='role':s[0]['role']='target'
    elif damage=='missing_class':s=[row for row in s if row['hypothesis']!=7]
    elif damage=='noise':s[8]['answers'][0]=not s[8]['answers'][0]
    elif damage=='duplicate_episode':s[1]['episode']=s[0]['episode']
    elif damage=='numeric_answer':s[0]['answers'][0]=1
    else:s[0]['hypothesis']=False
    with pytest.raises(ValueError):n.fit_procedures(s)


def test_hidden_answers_and_final_labels_cannot_change_learner():
    fitted=n.fit_procedures(traces());before=digest(fitted);firsts=[]
    for law in range(8):
        data=n.adapt('tree_greedy',fitted,b.LabelOracle(b.TABLE[law],8).reveal)
        firsts.append(data['steps'][0]['question'])
        final=[dict(query=j,answer=False) for j in range(8)]
        changed=[dict(query=j,answer=True) for j in range(8)]
        assert n.score(copy.deepcopy(data),final,fitted['model']['table'])['steps']==n.score(copy.deepcopy(data),changed,fitted['model']['table'])['steps']
    assert len(set(firsts))==1 and before==digest(fitted)
    with pytest.raises(TypeError):n.fit_procedures(traces(),target_labels=[0])


def test_compiler_rejects_bad_shapes_and_duplicate_classes():
    for table in [[],[[False]*8]*8,[[True]*7 for _ in range(8)]]:
        with pytest.raises(ValueError):cg.compile_table(table)
    with pytest.raises(ValueError,match='matching_choice_function'):
        b.adapt('greedy',{},b.LabelOracle(b.TABLE[0],8).reveal,table=b.TABLE)


def test_interval_is_family_level_not_target_level():
    values=list(range(8));p=n.interval(values)
    assert p['mean']==3.5 and p['n']==8 and p['df']==7
    half=2.364624251*math.sqrt(sum((x-3.5)**2 for x in values)/7)/math.sqrt(8)
    assert p['low']==pytest.approx(3.5-half)
    with pytest.raises(ValueError):n.interval([1]*256)


@pytest.fixture
def complete(monkeypatch):
    c=n.configuration();blocks=[];tables={}
    # Rotate supplied fixture rows/queries. These are not the registered random tables.
    for i,family in enumerate(c['families']):
        tables[family]=[list(b.TABLE[(j+i)%8][i:]+b.TABLE[(j+i)%8][:i]) for j in range(8)]
    monkeypatch.setattr(n,'evaluator_table',lambda seed:copy.deepcopy(tables[seed]))
    monkeypatch.setattr(n,'source_classes',lambda seed:list(range(8))*4)
    for i,family in enumerate(c['families']):
        table=tables[family];source=[]
        for j,seed in enumerate(c['tasks']['train'][32*i:32*(i+1)]):
            source.append(dict(role='source',episode=f'source-{seed}',answers=table[j%8],hypothesis=j%8))
        fitted=n.fit_procedures(source);rows=[]
        for j,seed in enumerate(c['tasks']['target'][32*i:32*(i+1)]):
            answers=table[j%8];methods={m:n.adapt(m,fitted,b.LabelOracle(answers,8).reveal,seed+700) for m in n.METHODS}
            rows.append(dict(task=seed,support_answers=answers,methods=methods))
        lock=digest(rows)
        for j,row in enumerate(rows):
            rng=random.Random(row['task']+200000);final=[]
            for k in range(32):
                q=rng.randrange(8);final.append(dict(id=f"final-{row['task']}-{k}",query=q,answer=table[j%8][q]))
            row['final']=final;row['final_hash']=digest(final)
            for data in row['methods'].values():n.score(data,final,table)
        block=dict(id=family,source=source,source_hash=digest(source),fitted=fitted,fitted_hash=digest(fitted),rows=rows,
            locked_choices_hash=lock,evaluator_table=table)
        block['means']=n.family_summary(block);blocks.append(block)
    r=dict(config=c,blocks=blocks,declared_complete=True,all_sources_frozen_before_targets=True,
        all_choices_locked_before_final=True,frozen_before=b.FROZEN,frozen_after=b.FROZEN)
    root=Path(__file__).resolve().parents[1]
    historical=json.loads((root/'artifacts/seed_inferred_investigation.json').read_text())['seed_audit']['config_hashes']
    r['seed_audit']=n.seed_audit(root,c,names=historical)
    r['analysis']=n.summarize(blocks,c)
    work=dict(real_steps=12544,source_responses=2048,source_annotations=256,target_support=2048,final_observations=8192,
        assessment_predictions=163840,updates=0,imagined_transitions=0,network_forwards=0,source_model_fits=8,source_tree_fits=8,
        cached_answer_exposures=sum(len(d['steps']) for x in blocks for row in x['rows'] for d in row['methods'].values()),cpu_s=.1,worker_wall_s=.1)
    return dict(study=r,resources=work),c,dict(real_steps=13000)


def test_complete_fixture_and_annotation_accounting(complete):
    o,c,caps=complete;n.validate_output(o,c,caps)
    assert o['resources']['real_steps']==sum(o['resources'][k] for k in ('source_responses','source_annotations','target_support','final_observations'))
    assert o['study']['analysis']['source_model_recovery']


@pytest.mark.parametrize('damage',['family','task','method','budget','cost','source','hidden','freeze','score','resource','nan','hash'])
def test_grid_and_leakage_fail_closed(complete,damage):
    o,c,caps=complete;r=o['study'];x=r['blocks'][0];row=x['rows'][0]
    if damage=='family':r['blocks'].pop()
    elif damage=='task':x['rows'].pop()
    elif damage=='method':row['methods'].pop('greedy')
    elif damage=='budget':row['methods']['tree_greedy']['snapshots'].pop('2')
    elif damage=='cost':row['methods']['compiled_greedy']['costs']['tree_nodes']+=1
    elif damage=='source':x['source'][0]['role']='target'
    elif damage=='hidden':x['fitted']['model']['table'][0][0]=not x['fitted']['model']['table'][0][0]
    elif damage=='freeze':r['all_choices_locked_before_final']=False
    elif damage=='score':row['final'][0]['answer']=not row['final'][0]['answer']
    elif damage=='resource':o['resources']['source_annotations']=0
    elif damage=='nan':x['fitted']['fit_wall_s']['tree']=float('nan')
    else:r['frozen_after']={}
    with pytest.raises((ValueError,KeyError)):n.validate_output(o,c,caps)


def test_exact_config_and_disjoint_registrations():
    root=Path(__file__).resolve().parents[1];c=n.configuration()
    assert json.loads((root/'configs/seed_inferred_investigation.json').read_text())==c
    assert not set(c['tasks']['train']).intersection(c['tasks']['target'])
    bad=copy.deepcopy(c);bad['max_authored_steps']=14000
    with pytest.raises(ValueError):n.config_check(bad)


def test_yaml_and_implicit_offset_exact_collision(tmp_path):
    folder=tmp_path/'configs';folder.mkdir();p=folder/'old.yaml'
    p.write_text('reset_base: 1_743_200_700\n')
    with pytest.raises(ValueError,match='existing_config_identifier'):n.seed_audit(tmp_path,n.configuration())
    p.write_text('reset_base: 42\n')
    assert n.seed_audit(tmp_path,n.configuration())['config_files']==1
