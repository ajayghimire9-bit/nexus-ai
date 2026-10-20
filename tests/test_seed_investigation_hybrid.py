"""Pure known-law fixtures, NOT fresh registered task generation."""
import copy
import json
from pathlib import Path
import statistics as st
import pytest
from nexus.seed import investigation_hybrid as h
from nexus.seed import investigation_transfer as b
from nexus.evolution1.catalogue import digest

ROOT=Path(__file__).resolve().parents[1]


def lib():return h.load_source(ROOT)['library']


@pytest.mark.parametrize('law',range(8))
def test_prefix_unchanged_and_search_only_after_abandon(law):
    library=lib();before=digest(library)
    fixed=h.adapt('tree_fixed',library,b.LabelOracle(list(b.TABLE[law]),8).reveal)
    hybrid=h.adapt('tree_greedy',library,b.LabelOracle(list(b.TABLE[law]),8).reveal)
    row=dict(methods=dict(tree_fixed=fixed,tree_greedy=hybrid))
    assert h.prefix_preserved(row,library)
    tree=library['tree'];history={};posterior=list(range(8));remaining=list(range(8))
    while tree['op']=='probe' and len(posterior)>1:
        costs=dict(tree_nodes=0,hypothesis_predictions=0,search_nodes=0)
        q=h.choose('tree_greedy',tuple(posterior),tuple(remaining),history,library,remaining,costs)
        assert q==tree['index'] and costs['greedy_calls']==costs['search_predictions']==0
        answer=b.TABLE[law][q];history[q]=answer;remaining.remove(q)
        posterior=[i for i in posterior if b.TABLE[i][q] is answer];tree=tree['branches'][int(answer)]
    assert digest(library)==before
    assert hybrid['snapshots']['8']['posterior']==[law]
    assert len(hybrid['steps'])<=4


def test_greedy_scoring_exact_and_all_lookups_charged():
    for mask in range(1,256):
        ids=tuple(i for i in range(8) if mask & (1<<i))
        costs=dict(tree_nodes=0,hypothesis_predictions=0,search_nodes=0)
        old=dict(costs)
        q=h.choose('greedy',ids,tuple(range(8)),{},lib(),[],costs)
        assert q==b.choose('greedy',ids,tuple(range(8)),{},lib(),[],old)
        assert costs['search_predictions']==costs['hypothesis_predictions']==len(ids)*8
        assert costs['greedy_calls']==1


def test_no_library_and_fixed_controls_reproduce_existing_choices():
    for method in ('fixed_order','no_library'):
        old=b.adapt(method,lib(),b.LabelOracle(list(b.TABLE[5]),8).reveal,27)
        new=h.adapt(method,lib(),b.LabelOracle(list(b.TABLE[5]),8).reveal,27)
        assert old['steps']==new['steps'] and old['snapshots']==new['snapshots']


def test_source_cost_not_free_or_new_training(monkeypatch):
    monkeypatch.setattr(b,'learn',lambda *a,**kw:pytest.fail('frozen tree refit'))
    source=h.load_source(ROOT)
    assert source['inherited_source']['labeled_observations']==256
    assert source['inherited_source']['source_split_comparisons']>512
    assert source['inherited_source']['new_source_fit'] is False
    assert digest(source['library'])==h.LIBRARY_SHA


def test_parent_hash_failure(tmp_path):
    p=tmp_path/h.PARENT;p.parent.mkdir();p.write_text('{}')
    with pytest.raises(ValueError,match='parent_artifact_hash'):h.load_source(tmp_path)


def test_reused_runner_never_refits_or_collects_source(tmp_path,monkeypatch):
    source=h.load_source(ROOT)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(b,'learn',lambda *a,**kw:pytest.fail('refit'))
    monkeypatch.setattr(b,'truth',lambda seed:0) # known authored fixture, not registered outcomes
    c=dict(schema='authored_test_fixture',tasks=dict(train=[],target=[7]),target_families=['temporal'],final_episodes=32,max_wall_s=60,max_authored_steps=100)
    out=b.run(dict(inputs=dict(study_config=c,repository=str(ROOT))),config_validator=lambda c:None,
        methods=h.METHODS,adapt_fn=h.adapt,analyze=lambda rows,c:dict(fixture=True),source_record=source)
    assert out['study']['declared_complete']
    assert out['resources']['real_steps']==40 and out['resources']['source_answers']==0
    assert out['resources']['source_fit_wall_s']==0
    assert out['study']['source_hash']==h.SOURCE_SHA
    assert out['study']['library_hash']==h.LIBRARY_SHA
    assert (tmp_path/'locked_target_choices.json').is_file()


def test_answer_boundary_and_fixed_configuration():
    library=lib();choices=[]
    for law in range(8):choices.append(h.adapt('tree_greedy',library,b.LabelOracle(list(b.TABLE[law]),8).reveal)['steps'][0]['question'])
    assert len(set(choices))==1
    c=h.configuration();assert h.config_check(c)['real_steps']==5000
    c['minimum_total_reduction']=0
    with pytest.raises(ValueError):h.config_check(c)


def grid():
    """Fabricated fixture grid using seed0 encodings, not registered outcomes."""
    source=h.load_source(ROOT);c=h.configuration();library=source['library']
    r=dict(config=c,source=source['source'],source_hash=h.SOURCE_SHA,library=library,library_hash=h.LIBRARY_SHA,
        inherited_source=source['inherited_source'],declared_complete=True,frozen_before_target=True,choices_locked_before_final=True,
        frozen_checkpoints_before=dict(b.FROZEN),frozen_checkpoints_after=dict(b.FROZEN),retention_before=[None]*32,retention_after=[None]*32,unchanged_library=True,rows=[])
    templates={m:h.adapt(m,library,b.LabelOracle(list(b.TABLE[0]),8).reveal,0) for m in h.METHODS}
    for i,seed in enumerate(c['tasks']['target']):
        family=c['target_families'][i//16];bind=b.binding(0,family)
        # Random control uses its prescribed seed; this is still a known-law fixture.
        methods=copy.deepcopy(templates);methods['no_library']=h.adapt('no_library',library,b.LabelOracle(list(b.TABLE[0]),8).reveal,seed+700)
        r['rows'].append(dict(task=seed,family=family,binding=bind,pool=[b.encode(bits,bind,0) for bits in b.BITS],support_bank_answers=list(b.TABLE[0]),methods=methods))
    r['choices_hash']=digest(r['rows'])
    for row in r['rows']:
        row['final']=[dict(id=f"final-{row['task']}-{j}",raw=b.encode(b.BITS[j%8],row['binding'],0),bits=list(b.BITS[j%8]),answer=b.TABLE[0][j%8]) for j in range(32)]
        row['data_hash']=digest(dict(binding=row['binding'],pool=row['pool'],final=row['final']))
        for d in row['methods'].values():
            d.update(predictions={},metrics={})
            for budget in b.BUDGETS:
                pred=[st.mean(b.hypotheses(f['bits'])[i] for i in d['snapshots'][str(budget)]['posterior']) for f in row['final']]
                d['predictions'][str(budget)]=pred
                d['metrics'][str(budget)]=dict(accuracy=st.mean((p>=.5)==f['answer'] for p,f in zip(pred,row['final'])),brier=st.mean((p-f['answer'])**2 for p,f in zip(pred,row['final'])))
    r['analysis']=h.summarize(r['rows'],c)
    work=dict(source_answers=0,target_pool_observations=256,target_answers=sum(len(d['steps']) for row in r['rows'] for d in row['methods'].values()),final_observations=1024,assessment_predictions=20480,real_steps=1280,updates=0,imagined_transitions=0,network_forwards=0,inherited_source=source['inherited_source'])
    return dict(study=r,resources=work),c,dict(real_steps=5000,updates=0,imagined_transitions=0)


def test_complete_grid():
    h.validate_output(*grid())


@pytest.mark.parametrize('damage',['task','method','budget','cost','library','source_cost','final','nan'])
def test_fail_closed(damage):
    o,c,cap=grid();r=o['study'];row=r['rows'][0];d=row['methods']['tree_greedy']
    if damage=='task':r['rows'].pop()
    elif damage=='method':row['methods'].pop('tree_fixed')
    elif damage=='budget':d['metrics'].pop('2')
    elif damage=='cost':d['costs']['search_predictions']+=1
    elif damage=='library':r['library_hash']='bad'
    elif damage=='source_cost':r['inherited_source']['labeled_observations']=0
    elif damage=='final':row['final'].pop()
    else:d['predictions']['1'][0]=float('nan')
    with pytest.raises((ValueError,KeyError)):h.validate_output(o,c,cap)
