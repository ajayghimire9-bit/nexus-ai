"""Synthetic arrays only; never launch a scientific audit from ordinary tests."""
import copy
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.seed import query_context as q,source_acquisition as a


def toy():
    # Two independent bits; each query duplicates a different candidate.
    return np.asarray([[False,False,False,False],[False,True,False,True],
        [True,False,True,False],[True,True,True,True]],bool)


def model():return dict(scale=[1.]*10,beta=[0.]*10)


def test_query_omission_produces_provable_choice_conflict():
    table=toy();cost=a.meter();cost['covariance_multiply_adds']=0
    r=q.context(table,np.arange(4),[0,1],[2,3],[],model(),cost,1e-10)
    assert r['optimal_sets']==[[0],[1]] and r['incompatible']
    assert r['alias_gap']==pytest.approx(.125)
    assert r['expected_regret']['learned']==pytest.approx(.125)
    c=a.meter();c['covariance_multiply_adds']=0
    swapped=q.context(table,np.arange(4),[0,1],[3,2],[],model(),c,1e-10)
    assert r['feature_hash']==swapped['feature_hash'] and r['choices']==swapped['choices']


def test_covariance_matches_branch_enumeration_and_direct_squared_error():
    table=toy();ids=np.arange(4);cost=a.meter();cost['covariance_multiply_adds']=0
    gains=q.gain_matrix(table,ids,[0,1],[2,3],cost)
    for i,x in enumerate([0,1]):
        for j,y in enumerate([2,3]):
            expected=a.expected_gain(table,ids,x,[y],np.ones(4),a.meter())
            before=np.mean((table[:,y]-.5)**2)
            after=sum(np.mean((table[table[:,x]==answer,y]-table[table[:,x]==answer,y].mean())**2)*.5 for answer in [False,True])
            assert gains[i,j]==pytest.approx(expected,abs=1e-12)
            assert gains[i,j]==pytest.approx(before-after,abs=1e-12)


def test_constant_candidate_and_input_separation():
    table=np.zeros((4,4),bool);c=a.meter();c['covariance_multiply_adds']=0
    assert np.array_equal(q.gain_matrix(table,np.arange(4),[0],[1],c),[[0.]])
    with pytest.raises(ValueError,match='disjoint'):q.context(table,np.arange(4),[0,1],[1,2],[],model(),c,1e-10)


def test_hidden_targets_never_enter_projection():
    r=dict(blocks=[dict(id=7,source=[dict(task=1,answers=[True]*16)],model=model(),rows=[dict(query_answers=[True])])])
    before=q.project_source(r);r['blocks'][0]['rows']=[dict(query_answers=[False],support_answers=[False])]
    assert q.project_source(r)==before
    assert set(before[0])=={'id','source','model'}


def test_unobserved_outcomes_not_context_arguments_and_frozen_model():
    import inspect
    assert not {'answers','labels','task','target'}&set(inspect.signature(q.context).parameters)
    m=model();before=copy.deepcopy(m);c=a.meter();c['covariance_multiply_adds']=0
    q.context(toy(),np.arange(4),[0,1],[2,3],[],m,c,1e-10)
    assert m==before


def test_actual_source_replay_ignores_unobserved_source_answers(monkeypatch):
    import random
    table=np.tile(toy(),(1,4))
    monkeypatch.setattr(a,'catalogue',lambda:([dict(answers=row.tolist()) for row in table],0))
    monkeypatch.setattr(a,'split_inputs',lambda task:(list(range(8)),list(range(8,16))))
    task=10;order=list(range(8));random.Random(task+700).shuffle(order)
    source=dict(task=task,answers=table[0].tolist())
    pack=[dict(id=1,source=[source],model=model())]
    c=q.configuration();c['prefixes']=[0,1]
    before=q.calculate(pack,c)
    # Only the first prefix label is permitted. Every other candidate answer
    # and all source query labels change; fixed model and permitted prefix stay.
    for x in range(16):
        if x!=order[0]:source['answers'][x]=not source['answers'][x]
    assert q.calculate(pack,c)==before


def cell_fixture():
    task=q.configuration()['tasks']['source'][0];pool,queries=a.split_inputs(task)
    pack=[dict(id=1,source=[dict(task=task)])];c=dict(prefixes=[0],families=[1],source_tasks_per_block=1,tasks={'source':[task]})
    row=dict(block=1,task=task,prefix=0,candidates=pool,queries=queries,gains=[[0.]*8 for _ in pool],alias_gap=0.,expected_regret={'learned':0.})
    return [row],c,pack


@pytest.mark.parametrize('kind',['task','prefix','query','candidate','cell','duplicate','nan','inf','bool','string'])
def test_raw_grid_failures(kind):
    rows,c,pack=cell_fixture()
    if kind=='task':rows=[]
    elif kind=='prefix':rows[0]['prefix']=2
    elif kind=='query':rows[0]['queries'].pop()
    elif kind=='candidate':rows[0]['candidates'].pop()
    elif kind=='cell':rows[0]['gains'][0].pop()
    elif kind=='duplicate':rows.append(copy.deepcopy(rows[0]))
    else:rows[0]['gains'][0][0]={'nan':float('nan'),'inf':float('inf'),'bool':True,'string':'0'}[kind]
    with pytest.raises(ValueError):q.validate_cells(rows,c,pack)


def test_expected_grid_cannot_shrink_with_missing_source_projection():
    rows,c,pack=cell_fixture()
    with pytest.raises(ValueError,match='complete_context_grid'):q.validate_cells([],c,[])


def test_configuration_and_hash_checks(tmp_path):
    root=Path(__file__).resolve().parents[1]
    assert json.loads((root/'configs/seed_query_context.json').read_text())==q.configuration()
    c=q.configuration();c['max_outer_updates']=1
    with pytest.raises(ValueError):q.config_check(c)
    (tmp_path/'artifacts').mkdir();(tmp_path/'artifacts/seed_source_acquisition.json').write_text('{}')
    with pytest.raises(ValueError,match='parent_hash'):q.source_pack(tmp_path)


def test_readonly_view_requires_matching_audit_receipt(tmp_path):
    (tmp_path/'artifacts').mkdir();(tmp_path/'artifacts/seed_query_context.json').write_text('{}')
    (tmp_path/'artifacts/seed_query_context_audit.json').write_text('{"valid":true,"raw_sha256":"wrong"}')
    with pytest.raises(ValueError,match='receipt'):q.saved_replay(tmp_path)


def test_summary_counts_and_means_independently():
    rows=[]
    for block in range(8):
        for task in range(16):
            for prefix in (0,1,2,4):
                gap=(block+1)*.001
                rows.append(dict(block=block,prefix=prefix,incompatible=True,alias_gap=gap,
                    expected_regret=dict(learned=gap*2,variance=gap*3,original_order=gap*4,best_query_blind=gap,query_aware=0.)))
    s=q.summarize(rows,q.configuration())
    assert s['contexts']==512 and s['paired_query_contexts']==4096 and s['incompatible']==512
    assert s['material_gap_contexts']==512 and s['verdict']=='query_information_missing'
    assert s['mean_alias_gap']==pytest.approx(.0045)
    assert s['expected_regret']['learned']==pytest.approx(.009)
    assert all(v['incompatible']==64 for v in s['per_block'])
