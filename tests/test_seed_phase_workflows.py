"""Authored workflow engineering fixtures; no scientific efficacy assertions."""
import copy
import uuid
import pytest
from nexus.evolution1.catalogue import digest
from nexus.seed.core import Session
from nexus.seed.foundation import library,programs,curriculum,runtime
from nexus.seed.storage import save,load


def fragment():return dict(op='count',value=programs.pipeline(['sort','unique']))


def tasks(prefix,offsets,values):
    return [dict(task=prefix+str(i),program=dict(op='add',left=fragment(),right=programs.literal(n)),examples=[dict(input=x,output=len(set(x))+n)]) for i,(n,x) in enumerate(zip(offsets,values))]


def source():return tasks('source',[0,1,2],[[3,1,3],[4,1,4],[5,1,5]])
def checks():return tasks('check',[10,11],[[8,2,8,1],[9,3,9,1]])
def call(s,op,**args):return runtime.request(s,dict(op='foundation_'+op,args=args))['result']


def test_expression_discovery_real_execution_storage_and_rejection():
    proposals=library.expression_propose(source());candidate=next(c for c in proposals if c['id']==digest(fragment()))
    result=library.expression_assess(candidate,source(),checks())
    assert result['accepted'] and candidate['stored_node_savings']==2
    assert result['macro_instructions']>=result['original_instructions'] # no fabricated CPU saving
    bad=checks();bad[0]['examples'][0]['output']=-1
    assert not library.expression_assess(candidate,source(),bad)['accepted']


def test_closure_and_literal_data_preserved():
    t=dict(op='let',name='y',value=programs.variable(),body=dict(op='add',left=programs.variable('y'),right=programs.variable('x')))
    assert library.free_names(t)=={'x'}
    assert library.free_names(t['body'])=={'x','y'}
    literal=programs.literal({'op':'var','name':'untrusted'})
    assert library.free_names(literal)==set() and library.expression_nodes(literal)==1


def test_conditional_abstraction_not_a_list_operation_window():
    small=dict(op='count',value=programs.variable())
    part=dict(op='if',condition=dict(op='lt',left=small,right=programs.literal(2)),then=small,**{'else':programs.literal(2)})
    def rows(prefix,values):
        return [dict(task=prefix+str(i),program=dict(op='add',left=part,right=programs.literal(i)),examples=[dict(input=x,output=min(len(x),2)+i)]) for i,x in enumerate(values)]
    source=rows('source',[[1],[2,3],[1,2,3]]);checks=rows('check',[[7,8,9,10],[5,6,7,8,9]])
    candidate=next(x for x in library.expression_propose(source) if x['id']==digest(part))
    assert library.expression_assess(candidate,source,checks)['accepted']


def test_promotion_persistence_rollback_and_repeated_review(tmp_path):
    s=Session();proposal=call(s,'expression_propose',programs=source());candidate=next(x for x in proposal['candidates'] if x['id']==digest(fragment()))
    reviewed=call(s,'expression_review',proposal=proposal['ref'],candidate=candidate['id'],checks=checks())
    assert reviewed['accepted']
    tree=dict(op='call',name=candidate['name'],value=programs.variable())
    assert call(s,'execute',program=tree,inputs={'x':[3,1,3]})['value']==2
    before=s.snapshot();one=call(s,'workbench');two=call(s,'workbench');assert one==two and s.snapshot()==before
    receipt=save(tmp_path,'a'*32,s);restored=load(tmp_path,'a'*32,receipt['hash'])
    assert call(restored,'execute',program=tree,inputs={'x':[5,4,5]})['value']==2
    with pytest.raises(ValueError):call(s,'expression_review',proposal=proposal['ref'],candidate=candidate['id'],checks=checks())
    with pytest.raises(ValueError):call(s,'expression_propose',programs=checks())
    call(s,'expression_rollback',name=candidate['name'],target=None)
    with pytest.raises(ValueError):call(s,'execute',program=tree,inputs={'x':[1]})
    call(s,'expression_rollback',name=candidate['name'],target=reviewed['ref'])
    assert call(s,'execute',program=tree,inputs={'x':[1]})['value']==1


def test_forged_acceptance_rejected():
    s=Session();p=runtime.build(s,'expression_propose',dict(programs=source()));s.event(runtime.KIND,p)
    ref=s.journal.snapshot()[-1].fingerprint;candidate=p['result'][0]
    bad=checks();bad[0]['examples'][0]['output']=-1
    record=runtime.build(s,'expression_review',dict(proposal=ref,candidate=candidate['id'],checks=bad))
    assert not record['result']['accepted'];record['result']['accepted']=True
    with pytest.raises(ValueError):runtime.validate_event(record,s)


def test_generated_curriculum_is_bounded_source_only_and_persistent(tmp_path):
    s=Session();issued=call(s,'curriculum_issue',seed=4,count=4)
    assert {t['family'] for t in issued['tasks']}=={'coding','reasoning','language','world'}
    for task in issued['tasks']:
        result=call(s,'curriculum_submit',task=task['id'],answer=task['expected']);assert result['correct'] and result['role']=='source'
    with pytest.raises(ValueError):call(s,'curriculum_submit',task=issued['tasks'][0]['id'],answer=None)
    history=[dict(family=f,reward=0 if f=='reasoning' else 1) for f in ('coding','reasoning','language','world')]
    assert curriculum.generate(history,0)[0]['family']=='reasoning'
    assert curriculum.generate(history,0)==curriculum.generate(history,0)
    receipt=save(tmp_path,'b'*32,s);other=load(tmp_path,'b'*32,receipt['hash'])
    assert call(other,'inspect')['curriculum_progress']==call(s,'inspect')['curriculum_progress']


def test_pure_tools_refuse_external_or_recursive_capabilities():
    s=Session();assert call(s,'tool',name='execute',arguments=dict(program=programs.literal(7),inputs={}))['value']==7
    for name in ('shell','python','network','tool','grant','train'):
        with pytest.raises(ValueError):call(s,'tool',name=name,arguments={})


def test_all_seven_phase_views_share_existing_state():
    s=Session();before=s.snapshot();result=call(s,'workbench')
    assert [p['phase'] for p in result['phases']]==list(range(1,8))
    assert not result['automatic_scientific_execution'] and s.snapshot()==before
