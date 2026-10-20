"""Small authored contract fixtures, not the registered experiment or success gate."""
import copy
import json
from pathlib import Path
import pytest
from nexus.evolution1.catalogue import digest
from nexus.seed.core import Session
from nexus.seed.structure.state import State, observe
from nexus.seed.structure.features import evaluate, grammar, validate
from nexus.seed.structure.learning import Example, induce, conflicts, fit_table, predict_table
from nexus.seed.structure.mechanisms import execute, plan, run_skill
from nexus.seed.structure.investigation import learn, run
from nexus.seed.structure.runtime import request, inspect


def raw(codes, flag=False, time=None, name='object'):
    return dict(entities=[dict(id=name,type='item',attributes=dict(flag=flag,ready=None))],relations=[],
        events=[dict(code=c,entity=name,time=i) for i,c in enumerate(codes)],time=len(codes) if time is None else time,source='sensor')


def example(i, codes, answer, role='source'):
    s=observe(State(episode=f'{role}-{i}'),raw(codes))
    return Example(s.episode,s,0,answer)


def toy_data(role):
    return [example(i,[0] if i%2 else [1],bool(i%2),role) for i in range(8)]


def mechanism(**changes):
    p=dict(id='ready',entity_type='item',precondition=None,
        effects=[dict(op='set',attribute='ready',value=True,type='boolean')],origin='supplied',
        evidence=[],known_failures=[],uncertainty=0.)
    p.update(changes);return p


def test_provenance_unknowns_clock_identity_and_inspection():
    s=observe(State(),raw([1]));before=s.wire()
    with pytest.raises(ValueError):observe(s,raw([0]))
    with pytest.raises(ValueError):observe(State(),dict(raw([0]),hidden_state=True))
    assert evaluate(dict(op='attribute',name='ready'),s) is None
    assert s.wire()==before
    remembered=observe(s,dict(entities=[],relations=[],events=[],time=10,source='sensor'))
    assert not remembered.current and remembered.remembered['object']['observed_at']==1
    assert evaluate(dict(op='exists',code=1),remembered) is None
    altered=raw([1]);altered['entities'][0]['attributes']['flag']='secret'
    with pytest.raises(ValueError):observe(State(),altered)


def test_history_truncation_and_unknown_not_false():
    s=State()
    for i in range(33):
        x=raw([]);x['time']=i;x['events']=[dict(code=0 if i==0 else 1,entity='object',time=i)]
        s=observe(s,x)
    assert s.truncated and len(s.events)==32
    assert evaluate(dict(op='exists',code=0),s) is None
    assert evaluate(dict(op='exists',code=1),s) is True
    assert evaluate(dict(op='after',first=0,second=1),s) is False


def test_feature_types_order_and_renaming():
    s=observe(State(),raw([0,1,0],name='newname'))
    assert evaluate(dict(op='after',first=0,second=1),s,'newname')
    assert not evaluate(dict(op='after',first=1,second=0),s,'newname')
    assert len(grammar())==90
    for p in [dict(op='exists',code=True),dict(op='python',code=0),dict(op='and',terms=[dict(op='and',terms=[dict(op='exists',code=0)]*2)]*2)]:
        with pytest.raises(ValueError):validate(p)


def test_recurrent_conflicts_source_only_and_one_candidate_validation():
    train,validation=toy_data('source'),toy_data('validation')
    assert conflicts(train)
    record=induce(train,validation)
    assert record['accepted'] and record['validation_candidates']==1
    assert record['candidates_evaluated']==90
    assert record==induce(train,validation)
    with pytest.raises(ValueError,match='overlap'):induce(train,train)
    with pytest.raises(ValueError,match='candidate_cap'):induce(train,validation,candidates=grammar()*2)
    # Contradictory validation rejects, does not search another validation winner.
    bad=[Example(x.episode,x.state,x.action,not x.outcome) for x in validation]
    rejected=induce(train,bad)
    assert not rejected['accepted'] and rejected['feature'] is None and rejected['validation_candidates']==1
    assert not conflicts(train[:2])


def test_unseen_context_uncertainty_and_disabled_feature_ablation():
    train=toy_data('source');p=dict(op='exists',code=0)
    fixed,model=fit_table(train,[]),fit_table(train,[p])
    assert predict_table(fixed,train[0],[])==predict_table(fixed,train[1],[])==.5
    assert predict_table(model,train[0],[p])!=predict_table(model,train[1],[p])
    unknown=example(50,[2],False);unknown=Example(unknown.episode,unknown.state,1,False)
    assert predict_table(model,unknown,[p])==.5


def test_atomic_typed_mechanisms_no_hidden_calls_and_bounded_plan():
    state=observe(State(),raw([0]));before=state.wire();meter={}
    out=execute(mechanism(),state,'object',meter)
    assert out['state'].current[0]['attributes']['ready'] is True
    assert state.wire()==before and meter==dict(retrieval_tests=1,instructions=1)
    result=plan(state,[mechanism()],'object',dict(op='attribute',name='ready'))
    assert result['status']=='planned' and result['path']==['ready'] and result['hypothetical']
    assert plan(state,[mechanism()],'object',dict(op='attribute',name='ready'),timeout=0)['status']=='timeout'
    with pytest.raises(ValueError):plan(state,[mechanism()]*17,'object',dict(op='attribute',name='ready'))
    bad=mechanism(effects=[dict(op='add',attribute='ready',value=1,type='number')])
    assert execute(bad,state,'object',{})['status']=='unknown'
    assert execute(mechanism(precondition=dict(op='exists',code=3)),state,'object',{})['status']=='failed_precondition'
    assert run_skill(dict(schema='list',ops=['reverse']),[1,2])==[2,1]


def test_investigation_learning_branches_probe_cost_and_no_target_feedback():
    traces=[dict(role='source',episode=str(i),answers=[bool(i%2),bool((i//2)%2)],hypothesis=i%2) for i in range(8)]
    program=learn(traces);before=digest(program);calls=[]
    result=run(program,lambda i:(calls.append(i) or True))
    assert calls==[0] and result['hypothesis']==1 and result['real_probes']==1
    assert digest(program)==before and run(program,lambda _:True,budget=0)['status']=='budget_stop'
    altered=copy.deepcopy(traces);altered[0]['role']='final'
    with pytest.raises(ValueError):learn(altered)
    shuffled=[dict(r,hypothesis=int(r['answers'][1])) for r in traces]
    assert learn(shuffled)['tree']['index']==1


def test_same_session_optional_runtime_persistence_and_baseline_unchanged(tmp_path):
    from nexus.seed.storage import save,load
    from nexus.seed.lab import SeedWorkspace
    w=SeedWorkspace(tmp_path);sid=w.dispatch(dict(session_id=None,request=dict(op='new')))['session_id']
    call=lambda **r:w.dispatch(dict(session_id=sid,request=r))['response']
    baseline=w.sessions[sid].snapshot();assert call(op='structure_inspect')['features']==[]
    assert w.sessions[sid].snapshot()==baseline
    call(op='structure_reset',episode='first')
    call(op='structure_observe',observation=raw([0]))
    call(op='structure_install',mechanism=mechanism())
    assert call(op='structure_plan',binding='object',goal=dict(op='attribute',name='ready'))['path']==['ready']
    # Planning/inspection don't execute graph effects or the real authored world.
    before=w.sessions[sid].snapshot();call(op='structure_predict',action=0);call(op='structure_inspect')
    assert w.sessions[sid].snapshot()==before
    receipt=save(tmp_path,sid,w.sessions[sid]);restored=load(tmp_path,sid,receipt['hash'])
    assert inspect(restored)==inspect(w.sessions[sid]) and restored.world==Session().world
    call(op='chat_send',text='Hello',id='a'*32)
    assert w.sessions[sid].counts['sandbox_actions']==0


def test_review_rollback_preserves_evidence_and_consumes_validation():
    s=Session();ids={'source':[],'source_validation':[]}
    for role in ids:
        for i in range(8):
            request(s,dict(op='structure_reset',episode=f'{role}-{i}'))
            request(s,dict(op='structure_observe',observation=raw([i%2])))
            eid=f'{role}-{i}';ids[role].append(eid)
            request(s,dict(op='structure_example',id=eid,action=0,outcome=bool(i%2),role=role))
    request(s,dict(op='structure_review',train=ids['source'],validation=ids['source_validation']))
    assert len(inspect(s)['features'])==1
    restored=Session.restore(s.snapshot());assert inspect(restored)==inspect(s)
    request(s,dict(op='structure_rollback'))
    assert inspect(s)['features']==[] and len(inspect(s)['evidence'])==16
    with pytest.raises(ValueError):request(s,dict(op='structure_review',train=ids['source'],validation=ids['source_validation']))
    assert inspect(Session.restore(s.snapshot()))==inspect(s)


def test_neural_residual_is_separate_bounded_and_round_trips():
    import torch
    from nexus.seed.structure.neural import NumericResidual
    torch.set_num_threads(1);model=NumericResidual(2,1.,seed=7)
    x=torch.tensor([[1.,0.],[0.,1.],[1.,1.],[-1.,0.]])
    model.fit(x,torch.tensor([.4,.2,.6,-.4]),steps=4)
    prediction=model.predict(x);assert torch.isfinite(prediction).all() and prediction.abs().max()<=1
    assert any(p.grad is not None and p.grad.abs().sum()>0 for p in model.model.parameters())
    restored=NumericResidual.load(model.checkpoint())
    assert torch.equal(restored.predict(x),prediction)


def test_numeric_mechanism_uses_observed_attributes_and_persists_separately():
    from nexus.seed.structure.neural import NumericResidual
    s=Session();checkpoint=NumericResidual(1,seed=9).checkpoint()
    request(s,dict(op='structure_install_numeric',id='numeric',checkpoint=checkpoint,evidence=['source-fixture']))
    x=raw([]);x['entities'][0]['attributes'].update(value=.2,score=None)
    request(s,dict(op='structure_observe',observation=x));before=s.snapshot()
    result=request(s,dict(op='structure_predict_numeric',id='numeric',binding='object',inputs=['value'],output='score',supplied_prediction=0.))
    assert result['hypothetical'] and abs(result['residual'])<=1
    assert s.snapshot()==before and inspect(Session.restore(before))==inspect(s)
    with pytest.raises(ValueError,match='bernoulli'):request(s,dict(op='structure_predict_numeric',id='numeric',binding='object',inputs=['value'],output='flag',supplied_prediction=0.))


def test_observation_metadata_cannot_change_features_or_fitted_parameters():
    train=toy_data('source');changed=copy.deepcopy(train)
    for x in changed:
        x.state.episode='private-task';x.state.provenance=[dict(answer='secret')]
        for e in x.state.events:e['source']='different'
    assert fit_table(train,grammar()[:2])==fit_table(changed,grammar()[:2])


def test_induction_persists_and_reuses_source_learned_investigation():
    s=Session();ids=[]
    for i in range(8):
        request(s,dict(op='structure_reset',episode=f'source-{i}'))
        request(s,dict(op='structure_observe',observation=raw([i%2])))
        ids.append(f'example-{i}')
        request(s,dict(op='structure_example',id=ids[-1],action=0,outcome=bool(i%2),role='source'))
    probes=[dict(op='exists',code=0),dict(op='exists',code=1)]
    request(s,dict(op='structure_learn_investigation',source_ids=ids,probes=probes))
    library=inspect(s)['library_sha256']
    request(s,dict(op='structure_reset',episode='target-support'))
    assert inspect(s)['state']['events']==[]
    request(s,dict(op='structure_observe',observation=raw([1])))
    request(s,dict(op='structure_investigate',index=0,budget=3))
    current=inspect(s);performed=current['investigations_performed'][-1]['result']
    assert performed['hypothesis']==1 and performed['observed_history_reads']==1 and performed['real_probes']==0
    assert all(not x['real'] for x in performed['transcript'])
    assert current['library_sha256']==library
    assert inspect(Session.restore(s.snapshot()))==current


def test_repeated_reviews_do_not_claim_adding_the_same_feature_is_progress():
    train=toy_data('source');validation=toy_data('validation')
    first=induce(train,validation);new_validation=toy_data('new-validation')
    second=induce(train,new_validation,baseline_features=[first['feature']])
    assert not second['accepted'] and second['before']==second['after']==0


def complete_fixture():
    from nexus.seed.structure.study import summary,KINDS,METHODS
    c=json.loads((Path(__file__).resolve().parents[1]/'configs/seed_executable_world.json').read_text())
    rows=[];manifest=[]
    for j,seed in enumerate(c['tasks']['train']):
        data={role:[dict(episode=f'{role}-{seed}-{i}',action=0,flag=False,outcome=False,codes=[0,1]) for i in range(n)] for role,n in [('source',96),('validation',48),('final',96)]}
        change=dict(accepted=False,forgetting=0.)
        fitted=dict(fixed=[],induced=[],replay=[],all_history=dict(scale=[1.]*364,beta=[0.]*364))
        checkpoint={'gru.weight_ih_l0':[[0.]*8 for _ in range(96)],'gru.weight_hh_l0':[[0.]*32 for _ in range(96)],
            'gru.bias_ih_l0':[0.]*96,'gru.bias_hh_l0':[0.]*96,'head.weight':[[0.]*32],'head.bias':[0.]}
        rows.append(dict(seed=seed,kind=KINDS[j//4],data=data,change=change,feature=[],fitted=fitted,
            metrics={m:dict(brier=.25,accuracy=0.) for m in METHODS},predictions={m:[.5]*96 for m in METHODS},gru_checkpoint=checkpoint))
        manifest.append(dict(task=seed,feature=[],change_sha256=digest(change),fitted_sha256=digest(fitted),
            source_sha256=digest(data['source']),validation_sha256=digest(data['validation']),gru_sha256=digest(checkpoint)))
    r=dict(declared_complete=True,config=c,rows=rows,frozen_before_final=True,frozen_manifest=manifest,frozen_manifest_sha256=digest(manifest),analysis=summary(rows,c))
    resources=dict(real_steps=11520,imagined_transitions=0,updates=3200)
    return dict(study=r,resources=resources),c,dict(real_steps=34560,imagined_transitions=0,updates=3200)


@pytest.mark.parametrize('mutation',['task','method','episode','checkpoint','nan','inf','bool','numeric_string','manifest','held_label'])
def test_exact_grid_and_frozen_record_rejection(mutation):
    from nexus.seed.structure.study import validate_output
    out,c,caps=complete_fixture();validate_output(out,c,caps)
    row=out['study']['rows'][0]
    if mutation=='task':out['study']['rows'].pop()
    elif mutation=='method':row['predictions'].pop('gru32')
    elif mutation=='episode':row['data']['final'].pop()
    elif mutation=='checkpoint':row.pop('gru_checkpoint')
    elif mutation in ('nan','inf','bool','numeric_string'):row['predictions']['fixed'][0]={'nan':float('nan'),'inf':float('inf'),'bool':True,'numeric_string':'.5'}[mutation]
    elif mutation=='manifest':out['study']['frozen_manifest'].pop()
    elif mutation=='held_label':row['data']['final'][0]['outcome']=True
    with pytest.raises((ValueError,KeyError)):validate_output(out,c,caps)


def test_eval_grid_validator_rejects_missing_and_nonfinite_before_outcomes():
    from nexus.seed.structure.study import config_check, validate_output
    c=json.loads((Path(__file__).resolve().parents[1]/'configs/seed_executable_world.json').read_text())
    config_check(c)
    incomplete=dict(study=dict(declared_complete=True,config=c,rows=[]))
    with pytest.raises(ValueError,match='complete_task_grid'):validate_output(incomplete,c,{})
    wrong=copy.deepcopy(c);wrong['gru_lr']=.1
    with pytest.raises(ValueError):config_check(wrong)


def test_recurrent_baseline_has_compatible_source_training_and_exact_step_accounting():
    import torch
    from nexus.seed.structure.study import fit_recurrent,sequence
    torch.set_num_threads(1);rows=toy_data('source');c=dict(gru_lr=.01,gru_updates=2)
    work=dict(updates=0,training_examples=0)
    model,_=fit_recurrent(rows,777,c,lambda:None,work)
    assert work==dict(updates=2,training_examples=16)
    weights={k:v.clone() for k,v in model.state_dict().items()}
    x,index=sequence(rows)
    with torch.no_grad():h,_=model['gru'](x);pred=model['head'](h[torch.arange(len(rows)),index])
    assert torch.isfinite(pred).all()
    assert all(torch.equal(v,weights[k]) for k,v in model.state_dict().items())
    again,_=fit_recurrent(rows,777,c,lambda:None)
    assert all(torch.equal(v,again.state_dict()[k]) for k,v in weights.items())
