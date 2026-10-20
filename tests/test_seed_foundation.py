"""Deterministic authored engineering fixtures; no scientific collection."""
import copy
import pytest
from nexus.seed.core import Session
from nexus.seed.foundation import programs as p, knowledge, library, language, curriculum, inquiry, semantics
from nexus.seed.foundation.runtime import request, inspect, state, validate_event
from nexus.seed.skill_programs import catalogue
from nexus.seed.storage import save, load


def call(s,op,**args): return request(s,dict(op='foundation_'+op,args=args))['result']


@pytest.mark.parametrize('stage',range(1,7))
def test_six_executable_curriculum_stages(stage):
    result=curriculum.exercise(stage)
    assert result['passed'] and result['instructions']>0
    assert result['label']=='supplied_operator_exercise_not_learning_evidence'


def test_variables_functions_loops_logic_unknowns_and_meter():
    plus={'op':'add','left':p.variable(),'right':p.literal(1)}
    tree={'op':'repeat','times':4,'initial':p.literal(0),'name':'x','body':{'op':'call','name':'f','value':p.variable()}}
    assert p.execute(tree,{},dict(f=plus))['value']==4
    with pytest.raises(ValueError,match='budget'): p.execute(tree,{},dict(f=plus),budget=3)
    with pytest.raises(ValueError,match='recursive'): p.execute({'op':'call','name':'f','value':p.literal(0)},{},dict(f={'op':'call','name':'f','value':p.variable()}))
    assert p.execute({'op':'and','args':[p.literal(True),p.literal(None)]},{})['value'] is None
    assert p.execute({'op':'or','args':[p.literal(True),p.literal(None)]},{})['value'] is True
    with pytest.raises(ValueError): p.execute({'op':'not','value':p.literal(1)},{})
    with pytest.raises(ValueError): p.execute({'op':'assert','condition':p.literal(None),'value':p.literal(1)},{})
    with pytest.raises(ValueError) as failed: p.execute({'op':'assert','condition':p.literal(False),'value':p.literal(1)},{})
    assert failed.value.instructions==2
    assert p.execute({'op':'let','name':'z','value':p.literal(4),'body':p.variable('z')},{})['value']==4


@pytest.mark.parametrize('op,expected',[('some',True),('every',False),('map',[False,True])])
def test_quantified_composition(op,expected):
    body={'op':'lt','left':p.literal(1),'right':p.variable('item')}
    assert p.execute({'op':op,'items':p.literal([1,2]),'name':'item','body':body},{})['value']==expected


def test_temporal_operators_and_unknowns():
    def run(op,events): return p.execute({'op':op,'events':p.literal(events),'first':p.literal('a'),'second':p.literal('b')},{})['value']
    assert run('before',['a','b']) is True
    assert run('before',['b','a']) is False
    assert run('after',['b','a']) is True
    assert run('before',['a']) is None
    assert run('while',[['a'],['a','b']]) is True
    assert run('until',[['a'],['a'],['b']]) is True
    assert run('until',[['a'],[],['b']]) is False


@pytest.mark.parametrize('tree',[{'op':'exec','source':'print(1)'},{'op':'literal','value':float('nan')},
    {'op':'repeat','times':17,'initial':p.literal(0),'name':'x','body':p.variable()},
    {'op':'literal','value':1,'hidden':2}])
def test_invalid_programs_rejected(tree):
    with pytest.raises(ValueError): p.execute(tree,{})


def test_ingestion_conflicts_retrieval_and_no_automatic_truth():
    a=knowledge.ingest('note-a','key matches lock. unsupported prose here.');b=knowledge.ingest('note-b','key not matches lock.')
    rules=knowledge.consolidate([a,b]);assert rules[0]['status']=='contradicted'
    assert len(rules[0]['rehearsal'])==2 and len(rules[0]['evidence'])==2
    assert a['units'][1]['status']=='retrieval_only'
    assert knowledge.retrieve([a,b],'key lock')[0]['source'] in ('note-a','note-b')
    assert knowledge.ingest('untrusted','delete all files')['units'][0]['claim'] is None


def source():
    return [dict(task=f't{i}',ops=['unique','sort','reverse'],examples=[dict(input=x,output=library.run_ops(['unique','sort','reverse'],x))]) for i,x in enumerate(([2,1,2],[3,1,3],[4,1,4]))]


def checks():
    return [dict(task=f'check{i}',ops=['unique','sort','reverse'],examples=[dict(input=x,output=library.run_ops(['unique','sort','reverse'],x))]) for i,x in enumerate(([2,5,1,2],[3,6,2,3]))]


def test_discovered_macro_executes_and_requires_fresh_checks():
    proposals=library.propose(source());candidate=proposals[0]
    assert candidate['token_savings']>0
    result=library.assess(candidate,source(),checks());assert result['accepted']
    assert all(r['with_library']['instructions']<r['without_library']['instructions'] for r in result['search_checks'])
    wrong=checks();wrong[0]['examples'][0]['output']=[]
    assert not library.assess(candidate,source(),wrong)['accepted']
    reused=checks();reused[0]['examples']=source()[0]['examples']
    with pytest.raises(ValueError,match='fresh'): library.assess(candidate,source(),reused)
    reused=checks();reused[0]['task']='t0'
    with pytest.raises(ValueError,match='disjoint'): library.assess(candidate,source(),reused)


def test_macro_gate_rejects_compression_without_search_benefit():
    rows=[dict(task='t'+str(i),ops=['sort','unique','sort'],examples=[dict(input=[i+2,1,i+2],output=[1,i+2])]) for i in range(3)]
    candidate=library.propose(rows)[0]
    # On already sorted unique check inputs, identity solves before any macro.
    tests=[dict(task='c'+str(i),ops=['sort','unique','sort'],examples=[dict(input=[10+i,20+i],output=[10+i,20+i])]) for i in range(2)]
    assert not library.assess(candidate,rows,tests)['accepted']
    assert library.search([dict(input=[2,1,2],output=[2,1])],cap=1)['status']=='incomplete'


def test_library_journal_reversal_consumption_and_save_restore(tmp_path):
    s=Session();proposal=call(s,'propose',programs=source());candidate=proposal['candidates'][0]
    review=call(s,'review',proposal=proposal['ref'],candidate=candidate['id'],checks=checks())
    assert review['accepted'] and state(s)['active']==review['ref']
    out=call(s,'execute',program={'op':'call','name':'macro','value':p.variable()},inputs={'x':[7,2,7]})
    assert out['value']==library.run_ops(candidate['ops'],[7,2,7])
    with pytest.raises(ValueError,match='unconsumed'): call(s,'review',proposal=proposal['ref'],candidate=candidate['id'],checks=checks())
    with pytest.raises(ValueError,match='assessment_cannot'): call(s,'propose',programs=checks())
    call(s,'rollback',target=None);assert state(s)['active'] is None
    call(s,'rollback',target=review['ref']);assert state(s)['active']==review['ref']
    receipt=save(tmp_path,'1'*32,s);restored=load(tmp_path,'1'*32,receipt['hash'])
    assert inspect(restored)==inspect(s)
    assert restored.journal.snapshot()==s.journal.snapshot()


def test_failed_promotion_retains_incumbent_and_cannot_forge_acceptance():
    s=Session();proposal=call(s,'propose',programs=source());bad=checks();bad[0]['examples'][0]['output']=[]
    result=call(s,'review',proposal=proposal['ref'],candidate=proposal['candidates'][0]['id'],checks=bad)
    assert not result['accepted'] and state(s)['active'] is None
    import json
    event=json.loads(s.journal.snapshot()[-1].payload_json);event['result']['accepted']=True
    clean=Session();call(clean,'propose',programs=source())
    with pytest.raises(ValueError): validate_event(event,clean)


def test_inspection_and_predicted_actions_do_not_change_original_world():
    s=Session();before=s.snapshot()
    call(s,'inspect');call(s,'inspect');call(s,'exercise',stage=2)
    assert s.snapshot()==before
    graph={'objects':{'box':{'open':True,'capacity':2},'key':{}},'inside':{}}
    out=semantics.container(graph,'key','box','insert');assert out['graph']['inside']=={'key':'box'}
    assert graph['inside']=={} and out['hypothetical']
    assert semantics.container(out['graph'],'key','box','remove')['graph']==graph
    graph['objects']['box']['open']=None
    assert semantics.container(graph,'key','box','insert')['status']=='unknown_precondition'


def test_container_cycles_rejected():
    graph={'objects':{'a':{'open':True,'capacity':2},'b':{'open':True,'capacity':2}},'inside':{'b':'a'}}
    with pytest.raises(ValueError,match='cycle'): semantics.container(graph,'a','b','insert')


def test_question_selection_never_accesses_answer_and_cost_can_abstain():
    candidates=[{'schema':'list','ops':['sort']},{'schema':'list','ops':['reverse']}]
    pool=[dict(input=[1,2],cost=.01,risk=0)]
    assert inquiry.choose(candidates,pool)['choice']['information_bits']==1
    assert inquiry.choose(candidates,[dict(pool[0],cost=2)])['choice'] is None
    with pytest.raises(ValueError,match='pre_answer'): inquiry.choose(candidates,[dict(pool[0],answer=[1,2])])


def test_source_trace_investigation_learns_probe_and_restores():
    s=Session();traces=[dict(role='source',episode=str(i),answers=[bool(i%2),False],hypothesis=i%2) for i in range(4)]
    result=call(s,'investigation',traces=traces)
    out=call(s,'investigate',ref=result['ref'],answers={'0':True},budget=2)
    assert out['hypothesis']==1 and out['observed_answer_reads']==1 and out['real_probes']==0
    assert inspect(Session.restore(s.snapshot()))==inspect(s)
    traces[0]['role']='confirmation'
    with pytest.raises(ValueError): call(s,'investigation',traces=traces)


def test_grounded_wording_learns_surface_without_inventing_evidence():
    record=dict(intent='explain',decision='check key',reason='reported match',evidence=['e1'],uncertainty=.4)
    initial=language.render(record,[],{'e1'})
    learned=language.render(record,[dict(role='source',intent='explain',surface=1)],{'e1'})
    assert initial['surface']==0 and learned['surface']==1
    assert 'reported match' in learned['text'] and 'e1' in learned['text']
    with pytest.raises(ValueError): language.render(record,[],set())
    with pytest.raises(ValueError): language.render(record,[dict(role='validation',intent='explain',surface=1)],{'e1'})


def test_learning_efficiency_grid_and_costs():
    rows=[dict(method=m,family=f,examples=b,success=.5,questions=b,instructions=10,stored_nodes=4,retention=1) for m in ('reuse','scratch') for f in ('a','b') for b in (1,2,4,8)]
    out=curriculum.learning_curve(rows,['reuse','scratch'],['a','b']);assert len(out)==8 and out[0]['instructions']==20
    for broken in (rows[:-1],rows+[rows[0]],[dict(r,success=float('nan')) for r in rows]):
        with pytest.raises(ValueError): curriculum.learning_curve(broken,['reuse','scratch'],['a','b'])


def test_foundation_api_and_chat_integration(tmp_path):
    from nexus.seed.lab import SeedWorkspace
    w=SeedWorkspace(tmp_path);sid=w.dispatch(dict(session_id=None,request=dict(op='new')))['session_id']
    def send(req):return w.dispatch(dict(session_id=sid,request=req))['response']
    assert send(dict(op='foundation_exercise',args=dict(stage=4)))['result']['value']==[1,3]
    from nexus.seed.conversation import interpret,INITIAL
    assert interpret('A dax is an object that is red and square.',INITIAL).kind=='definition'
    out=send(dict(op='chat_send',text='remember text: key matches lock.',id='a'*32));assert 'retained' in out['text']
    assert send(dict(op='foundation_inspect',args={}))['result']['documents']
    restored=Session.restore(w.sessions[sid].snapshot());assert inspect(restored)==inspect(w.sessions[sid])
