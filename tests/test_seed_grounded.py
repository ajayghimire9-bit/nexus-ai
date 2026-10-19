"""Small authored engineering fixtures, not scientific controller trials."""
import copy
import hashlib
import json
from pathlib import Path
import pytest
torch=pytest.importorskip('torch')
from nexus.world.seed_rssm import SeedRSSM
from nexus.seed.core import Session,GRAMMAR,examples
from nexus.seed.grounded_world import observation,tensors,AuthoredWorld
from nexus.seed.grounded_agent import GroundedAgent
from nexus.seed.grounded_meta import OuterSeedMeta,RECIPES,program_truth
from nexus.seed.latent_planner import plan
from nexus.seed.grounded_audit import audit_episode,validate_config

torch.set_num_threads(1)


def model():
    torch.manual_seed(61)
    return SeedRSSM()


def test_all_modalities_and_shared_encoder_get_gradients():
    m=model();args=tensors([observation(o) for o in examples()[:4]])
    e=m.encode(*args);e.square().sum().backward()
    for module in (m.text,m.pixels,m.proprio,m.encoder):
        assert all(p.grad is not None and torch.isfinite(p.grad).all() and p.grad.norm()>0 for p in module.parameters())
    full=e.detach()
    assert all(not torch.equal(full,m.encode(*args,mask=tuple(j==i for j in range(3)))) for i in range(3))


def test_recurrent_state_stochastic_training_deterministic_inference_and_heads():
    m=model();h,z=m.initial();e=m.encode(*tensors([observation(examples()[0])]))
    a=m.observe(h,z,torch.tensor([0]),e,sample=False)
    b=m.observe(h,z,torch.tensor([0]),e,sample=False)
    assert torch.equal(a[0],b[0]) and torch.equal(a[1],b[1])
    assert not torch.equal(a[1],m.observe(h,z,torch.tensor([0]),e,sample=True)[1])
    assert not torch.equal(a[0],m.observe(h,z,torch.tensor([1]),e)[0])
    assert set(m.heads(*a[:2]))=={'state','latent','reward','done','value'}
    assert not h.any() and not z.any()


def test_learned_prototype_key_retrieval_has_gradients():
    m=model();e=torch.randn(2,32);p=torch.randn(3,32)
    memory,w=m.retrieve(e,p);memory.square().sum().backward()
    assert memory.shape==(2,16) and torch.allclose(w.sum(1),torch.ones(2))
    assert m.key.weight.grad.norm()>0 and m.query.weight.grad.norm()>0


def test_numeric_program_adapter_equivalent_to_existing_grammar():
    for p in GRAMMAR:
        for obj in examples():assert program_truth(p,obj)==p.matches(obj)


def test_existing_mpc_value_pruning_counts_and_does_not_mutate_state():
    m=model();h,z=m.initial();weights=copy.deepcopy(m.state_dict())
    a,info=plan(m,h,z,seed=17);again,other=plan(m,h,z,seed=17)
    assert a==again and info['candidate_scores']==other['candidate_scores']
    assert 0<=a<9 and info['value_pruned']==8
    assert m.work['transition_rows']==96 and m.work['transition_batches']==10
    assert not h.any() and not z.any()
    assert all(torch.equal(v,m.state_dict()[k]) for k,v in weights.items())


def test_outer_controller_training_feedback_only_and_no_runtime_executor():
    outer=OuterSeedMeta()
    with pytest.raises(ValueError):outer.propose(in_episode=True,remaining_s=1,remaining_steps=1)
    assert outer.propose(in_episode=False,remaining_s=0,remaining_steps=1) is None
    for i,r in enumerate(RECIPES):
        assert outer.propose(in_episode=False,remaining_s=1,remaining_steps=1)==r
        outer.reveal(r,dict(id=str(i),observed_training_loss=2-i),phase='training')
    assert outer.propose(in_episode=False,remaining_s=1,remaining_steps=1)==RECIPES[1]
    with pytest.raises(ValueError):outer.reveal(RECIPES[0],dict(id='eval',observed_training_loss=0),phase='evaluation')
    with pytest.raises(ValueError):outer.reveal(RECIPES[0],dict(id='0',observed_training_loss=0),phase='training')
    assert not hasattr(outer,'execute')


def test_model_roundtrip_hash_schema_finite_numeric(tmp_path):
    m=model();path=tmp_path/'model.json';sha=m.export(path,{'kind':'unit_fixture'})
    loaded,_=SeedRSSM.load(path,sha)
    args=tensors([observation(examples()[0])])
    assert torch.equal(m.encode(*args),loaded.encode(*args))
    assert all(not p.requires_grad for p in loaded.parameters())
    with pytest.raises(ValueError,match='hash'):SeedRSSM.load(path,'0'*64)
    d=json.loads(path.read_text());d['weights']['done.bias']=[True];bad=tmp_path/'bad.json';bad.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='numeric'):SeedRSSM.load(bad,hashlib.sha256(bad.read_bytes()).hexdigest())


def test_rejected_storage_is_not_reported_as_success_and_runtime_state_restores():
    m=model();s=Session();s.grounded_agent=GroundedAgent(m,'a'*64)
    before=copy.deepcopy(m.state_dict())
    out=s.request(dict(op='grounded',action='store',reference='o1',x=3,y=3,word='dax'))
    assert out['response_type']=='acted' and out['text']=='blocked'
    assert out['result']['result']['concept']['status']=='needs_evidence'
    assert out['resources']['grounded_model_work']['encoder_rows']>0
    assert out['state']['architecture']['learned_recurrent_memory'] is True
    restored=Session.restore(s.snapshot());assert restored.grounded_agent is None
    restored.grounded_agent=GroundedAgent(m,'a'*64);restored.grounded_agent.restore_state(restored)
    assert torch.equal(restored.grounded_agent.h,s.grounded_agent.h)
    assert torch.equal(restored.grounded_agent.z,s.grounded_agent.z)
    assert all(torch.equal(v,m.state_dict()[k]) for k,v in before.items())


def test_neural_induction_uses_bounded_proposals_and_cannot_keep_bad_program(monkeypatch):
    m=model();s=Session();agent=GroundedAgent(m,'a'*64)
    for o in examples():s.teach('dax',o,o['color']=='red')
    red=next(i for i,p in enumerate(GRAMMAR) if all(p.matches(o)==(o['color']=='red') for o in examples()))
    def propose(p,n):
        scores=torch.zeros(37);scores[red]=100;return scores
    monkeypatch.setattr(m,'propose',propose)
    result=agent.induce(s,'dax');assert result['status']=='adopted_development'
    assert agent.approved(s)['dax']['program_index']==red
    assert Session.restore(s.snapshot()).snapshot()==s.snapshot()
    s.teach('dax',examples()[0],False)
    assert not agent.approved(s)


def test_goal_cannot_be_reward_farmed_and_session_stop_blocks_neural_actions():
    s=Session();s.grounded_agent=GroundedAgent(model(),'a'*64)
    o=s.world[0]
    out=s.request(dict(op='grounded',action='decide',reference=o['id'],x=o['x'],y=o['y'],word='dax'))
    assert out['response_type']=='already_at_goal' and 'actual_reward' not in out['result']
    s.request(dict(op='stop'));h=s.grounded_agent.h.clone()
    assert s.request(dict(op='grounded',action='decide',reference='o1',x=3,y=3,word='dax'))['response_type']=='stopped'
    assert torch.equal(h,s.grounded_agent.h)


def test_unified_actions_and_reward_arithmetic():
    for action in range(9):
        w=AuthoredWorld(144);before=dict(w.obj);_,reward,done,info=w.step(action)
        e=dict(steps=[dict(action=action,reward=reward,done=done,before=before,after=dict(w.obj),goal=list(w.goal))],return_sum=reward)
        audit_episode(e,1)
        e['steps'][0]['reward']+=1
        with pytest.raises(ValueError,match='reward'):audit_episode(e,1)


def test_config_split_and_budget_rejection():
    c=json.loads((Path(__file__).resolve().parents[1]/'configs/seed_grounded_pilot.json').read_text());validate_config(c)
    for key,value in [('updates',121),('max_wall_s',181),('training_seeds',c['training_seeds'][:-1])]:
        bad=copy.deepcopy(c);bad[key]=value
        with pytest.raises(ValueError):validate_config(bad)
    bad=copy.deepcopy(c);bad['control_seeds'][0]=bad['training_seeds'][0]
    with pytest.raises(ValueError):validate_config(bad)


@pytest.mark.parametrize('action',[7,8])
def test_runtime_macro_boundary_semantics_match_training_world(monkeypatch,action):
    import nexus.seed.grounded_agent as module
    s=Session();s.world[0].update(x=5 if action==7 else 0,y=2)
    world=AuthoredWorld(4);world.obj=dict(s.world[0]);world.goal=(3,3)
    _,reward,done,_=world.step(action)
    s.grounded_agent=GroundedAgent(model(),'a'*64)
    monkeypatch.setattr(module,'plan',lambda *a,**k:(action,{}))
    out=s.request(dict(op='grounded',action='decide',reference='o1',x=3,y=3,word='dax'))
    assert s.world[0]==world.obj
    assert out['result']['actual_reward']==pytest.approx(reward)
    assert out['text']=='blocked' and out['result']['done']==done


def test_local_language_is_bounded_and_actual_trace_teacher_forcing_has_gradients():
    m=model();h,z=m.initial();memory=torch.zeros(1,16)
    logits=m.language_logits(h,z,memory,torch.tensor([[1,3,5]]))
    torch.nn.functional.cross_entropy(logits.reshape(-1,18),torch.tensor([3,5,2])).backward()
    assert m.language.weight_ih_l0.grad.norm()>0
    assert len(m.generate(h,z,memory).split())<=6


def test_query_prediction_loss_reaches_encoder_and_rssm():
    m=model();args=tensors([observation(o) for o in examples()[:2]])
    e=m.encode(*args);h,z=m.initial(2)
    h,z,_=m.observe(h,z,torch.tensor([0,1]),e,sample=True)
    h,z,_,_=m.transition(h,z,torch.tensor([1,2]),sample=True)
    m.heads(h,z)['state'].square().sum().backward()
    for module in (m.encoder,m.posterior,m.prior,m.recurrent,m.state_head):
        assert any(p.grad is not None and torch.isfinite(p.grad).all() and p.grad.norm()>0 for p in module.parameters())


def test_grounded_question_requires_actual_matching_feedback():
    s=Session();s.grounded_agent=GroundedAgent(model(),'a'*64)
    r=s.request(dict(op='grounded',action='ask',reference='o1',x=3,y=3,word='dax'))
    q=r['result']['question'];assert q['object']
    assert not any(e.kind=='seed_grounded_information' for e in s.journal.snapshot())
    s.request(dict(op='teach',word='dax',object=q['object'],positive=True))
    events=[e for e in s.journal.snapshot() if e.kind=='seed_grounded_information']
    assert len(events)==1
    feedback=json.loads(events[0].payload_json)
    assert feedback['task_reward']==0 and feedback['mixed_reward']==.05*feedback['information_gain']
    assert Session.restore(s.snapshot()).snapshot()==s.snapshot()


def test_complete_grid_rejects_missing_cells_and_nonfinite():
    from nexus.seed.grounded_audit import validate
    c=json.loads((Path(__file__).resolve().parents[1]/'configs/seed_grounded_pilot.json').read_text())
    def episodes(seeds):
        rows=[]
        for seed in seeds:
            w=AuthoredWorld(seed);before=dict(w.obj)
            # A recorded terminal transition from an adjacent state.
            w.goal=((w.obj['x']+1)%6,w.obj['y']);w.obj['x']=(w.goal[0]-1)%6
            if w.obj['x']==5:w.obj['x']=1;w.goal=(2,w.obj['y'])
            before=dict(w.obj);_,reward,done,info=w.step(1)
            rows.append(dict(seed=seed,return_sum=reward,steps=[dict(action=1,reward=reward,done=done,before=before,after=dict(w.obj),goal=list(w.goal))]))
        return rows
    source=episodes(c['training_seeds']);query=episodes(c['prediction_seeds']);control={m:episodes(c['control_seeds']) for m in c['methods']}
    row=dict(recipe='compact_tanh',frozen_evaluation=True,training=dict(losses=[dict(update=i,total=1.) for i in range(1,121)],encoder_gradient_norms=[1.]*120),prediction=dict(state_mae=1.,reward_mae=1.,done_bce=1.,trace_exact_accuracy=0.,modality_latent_mae=dict(text=1.,pixels=1.,proprioception=1.),observations=6,traces=[{}]*6),control=control)
    second=copy.deepcopy(row);second['recipe']='compact_relu'
    result=dict(config=c,source_episodes=source,prediction_episodes=query,models=[row,second],authored_world_steps=78,imagined_transitions=384,wall_s=1.)
    # 48 source + 6 queries + 2 recipes * 3 methods * 4 control steps.
    assert validate(result)['complete_grid']
    for mutate in [lambda r:r['models'].pop(),lambda r:r['source_episodes'].pop(),lambda r:r['models'][0]['control'].pop('random'),lambda r:r['models'][0]['control']['greedy'].pop(),lambda r:r['models'][0]['training']['losses'].pop(),lambda r:r['models'][0]['prediction'].update(state_mae=float('nan')),lambda r:r['models'][0]['prediction'].update(state_mae=True)]:
        bad=copy.deepcopy(result);mutate(bad)
        with pytest.raises(ValueError):validate(bad)


def test_invalid_grounded_requests_cannot_spend_model_work():
    s=Session();s.grounded_agent=GroundedAgent(model(),'a'*64)
    before=dict(s.grounded_agent.model.work)
    for key,value in [('action','shell'),('word',[]),('reference',None),('x',True)]:
        req=dict(op='grounded',action='decide',reference='o1',x=3,y=3,word='dax');req[key]=value
        assert s.request(req)['response_type']=='error'
    assert s.grounded_agent.model.work==before


def test_packaged_model_receipt_when_present():
    root=Path(__file__).resolve().parents[1];receipt=root/'artifacts/seed_grounded_pilot.json'
    # Before the committed single run, the ordinary architecture tests apply.
    # The explicit read-only audit CLI always fails on missing/incomplete output.
    if not receipt.exists():return
    from nexus.seed.grounded_audit import validate
    r=json.loads(receipt.read_text());assert r['declared_complete'] is True
    assert validate(r,root)['complete_grid']
    bad=copy.deepcopy(r);bad['execution_sha']='0'*40
    with pytest.raises(ValueError,match='provenance'):validate(bad,root)
