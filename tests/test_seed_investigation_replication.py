"""Constructed truth-table fixtures only; never execute registered collections."""
import copy
import json
import math
from pathlib import Path
import statistics as st
import pytest
from nexus.evolution1.catalogue import digest
from nexus.seed import investigation_replication as r, investigation_hybrid as h, investigation_transfer as b
from test_seed_investigation_hybrid import grid


def fixture():
    c=r.configuration();prototype,_,_=grid();records=[]
    for i,identifier in enumerate(c['replications']):
        sub=r.subconfig(c,i);out=copy.deepcopy(prototype);s=out['study'];s['config']=sub;s.pop('inherited_source',None)
        a=s['source'][:16];z=s['source'][16:];source=a[i:]+a[:i]+z[i:]+z[:i]
        for seed,row in zip(sub['tasks']['train'],source):row['task']=seed
        s['source']=source;s['source_hash']=digest(source)
        s['library']['source_episodes']=[f'source-{x}' for x in sub['tasks']['train']];s['library_hash']=digest(s['library'])
        rows=[]
        for j,seed in enumerate(sub['tasks']['target']):
            family=sub['target_family_by_task'][str(seed)];binding=b.binding(0,family);law=j%8
            rows.append(dict(task=seed,family=family,binding=binding,pool=[b.encode(bits,binding,0) for bits in b.BITS],support_bank_answers=list(b.TABLE[law]),methods={m:h.adapt(m,s['library'],b.LabelOracle(list(b.TABLE[law]),8).reveal,seed+700) for m in h.METHODS}))
        s['choices_hash']=digest(rows)
        for j,row in enumerate(rows):
            law=j%8;row['final']=[dict(id=f"final-{row['task']}-{k}",raw=b.encode(b.BITS[k%8],row['binding'],0),bits=list(b.BITS[k%8]),answer=b.TABLE[law][k%8]) for k in range(32)]
            row['data_hash']=digest(dict(binding=row['binding'],pool=row['pool'],final=row['final']))
            for d in row['methods'].values():
                d.update(metrics={},predictions={})
                for budget in b.BUDGETS:
                    p=[st.mean(b.hypotheses(f['bits'])[a] for a in d['snapshots'][str(budget)]['posterior']) for f in row['final']]
                    d['predictions'][str(budget)]=p;d['metrics'][str(budget)]=dict(accuracy=st.mean((v>=.5)==f['answer'] for v,f in zip(p,row['final'])),brier=st.mean((v-f['answer'])**2 for v,f in zip(p,row['final'])))
        s['rows']=rows;s['analysis']=r.tree_summary(s)
        out['resources'].update(source_answers=256,real_steps=1536,target_answers=sum(len(d['steps']) for row in rows for d in row['methods'].values()),tree_nodes=sum(d['costs']['tree_nodes'] for row in rows for d in row['methods'].values()),hypothesis_predictions=sum(d['costs']['hypothesis_predictions'] for row in rows for d in row['methods'].values()),search_nodes=0,cached_retention_reads=180)
        records.append(dict(id=identifier,**out))
    study=dict(config=c,declared_complete=True,replications=records,analysis=r.summarize(records,c))
    work={k:sum(x['resources'][k] for x in records) for k in ('real_steps','source_answers','target_pool_observations','target_answers','final_observations','assessment_predictions','tree_nodes','hypothesis_predictions','search_nodes','cached_retention_reads')}
    work.update(updates=0,imagined_transitions=0,network_forwards=0)
    return dict(study=study,resources=work),c,dict(real_steps=5000,updates=0,imagined_transitions=0)


def test_full_fixture_and_tree_units():
    o,c,cap=fixture();r.validate_output(o,c,cap)
    assert o['resources']['real_steps']==4608
    assert o['study']['analysis']['question_savings']['greedy']['n']==3
    assert o['study']['analysis']['question_savings']['greedy']['df']==2


def test_balanced_hidden_assignment_and_separation():
    c=r.configuration()
    for i in range(3):
        d=r.subconfig(c,i)
        assert set(d['tasks']['train']).isdisjoint(d['tasks']['target'])
        assert all(list(d['target_laws'].values()).count(law)==4 for law in range(8))
        for family in c['target_families']:
            assert all(sum(d['target_laws'][key]==law and value==family for key,value in d['target_family_by_task'].items())==2 for law in range(8))


def test_independent_interval_numeric():
    p=r.interval([1,2,3]);assert p['mean']==2
    assert p['low']==pytest.approx(2-4.30265272991/math.sqrt(3))
    with pytest.raises(ValueError):r.interval([1,2])


@pytest.mark.parametrize('damage',['tree','task','condition','budget','cost','copy_source','balance','resource'])
def test_complete_grid_failures(damage):
    o,c,cap=fixture();s=o['study'];x=s['replications'][0]
    if damage=='tree':s['replications'].pop()
    elif damage=='task':x['study']['rows'].pop()
    elif damage=='condition':x['study']['rows'][0]['methods'].pop('greedy')
    elif damage=='budget':x['study']['rows'][0]['methods']['tree_greedy']['metrics'].pop('2')
    elif damage=='cost':x['study']['rows'][0]['methods']['tree_greedy']['costs']['search_predictions']+=1
    elif damage=='copy_source':s['replications'][1]['study']['source']=copy.deepcopy(x['study']['source'])
    elif damage=='balance':x['study']['rows'][0]['support_bank_answers']=list(b.TABLE[7])
    else:o['resources']['real_steps']=4000
    with pytest.raises((ValueError,KeyError)):r.validate_output(o,c,cap)
