import copy
import json
from pathlib import Path
import pytest
torch=pytest.importorskip('torch')
from nexus.world.seed_rssm import SeedRSSM
from nexus.seed.state_contract import Belief,value_targets,world_memory
from nexus.seed.grounded_world import observation,tensors
from nexus.seed.core import Session
from nexus.seed.grounded_agent import GroundedAgent


def test_belief_duplicate_observation_is_noop_but_blocked_action_advances_once():
    torch.manual_seed(44);m=SeedRSSM();b=Belief(m);e=torch.randn(1,32)
    h,z,_=b.observe(e,torch.tensor([0]),0);calls=m.work['transition_rows']
    assert torch.equal(h,b.observe(e,torch.tensor([0]),0)[0]) and m.work['transition_rows']==calls
    with pytest.raises(ValueError):b.observe(e+1,torch.tensor([0]),0)
    with pytest.raises(ValueError):Belief(m).observe(e,torch.tensor([0]),2)
    b.observe(e,torch.tensor([0]),1)
    assert b.token==1 and m.work['transition_rows']==calls+1 and not torch.equal(h,b.h)


def test_inspect_observe_and_speak_do_not_commit_internal_state_before_or_after_action():
    s=Session();s.grounded_agent=GroundedAgent(SeedRSSM(),'a'*64)
    def stable():return (s.grounded_agent.h.clone(),s.grounded_agent.z.clone(),copy.deepcopy(s.world),copy.deepcopy(s.evidence),s.grounded_agent._belief.token,copy.deepcopy(s.grounded_agent.context))
    for stage in range(2):
        before=stable()
        for _ in range(3):
            s.request(dict(op='inspect'))
            for action in ('observe','speak'):s.request(dict(op='grounded',action=action,reference='o1',x=3,y=3,word='dax'))
        after=stable()
        assert torch.equal(before[0],after[0]) and torch.equal(before[1],after[1]) and before[2:]==after[2:]
        if stage==0:s.request(dict(op='grounded',action='ask',reference='o1',x=3,y=3,word='dax'))


def test_gui_and_control_contract_produce_identical_posteriors(monkeypatch):
    import nexus.seed.grounded_agent as module
    torch.manual_seed(4);m=SeedRSSM();m.semantics='aligned_v1';m.world_memory_bank=torch.randn(32,32)
    s=Session();s.grounded_agent=GroundedAgent(m,'a'*64);obj=copy.deepcopy(s.world[0]);b=Belief(m)
    with torch.no_grad():b.observe(m.encode(*tensors([observation(obj,(3,3))])),torch.tensor([0]),0)
    monkeypatch.setattr(module,'plan',lambda *a,**k:(1,{}))
    s.request(dict(op='grounded',action='decide',reference='o1',x=3,y=3,word='dax'))
    with torch.no_grad():b.observe(m.encode(*tensors([observation(s.world[0],(3,3))])),torch.tensor([1]),1)
    assert torch.equal(b.h,s.grounded_agent.h) and torch.equal(b.z,s.grounded_agent.z)
    assert s.grounded_agent._belief.token==1


def test_current_state_fixed_horizon_value_targets_mask_truncation_and_stop_at_terminal():
    steps=[dict(reward=float(i),done=False) for i in range(1,6)]
    v,mask=value_targets(steps,0)
    assert v[0]==pytest.approx(1+.9*2+.81*3) and mask==[True,True,True,False]
    steps[1]['done']=True
    assert value_targets(steps,0)[0][0]==pytest.approx(1+.9*2)
    short=[dict(reward=2.,done=True)]
    assert value_targets(short,0,length=1)==([2.],[True])


def test_aligned_bank_roundtrip_fixed_inputs_without_parameter_growth(tmp_path):
    m=SeedRSSM();count=sum(p.numel() for p in m.parameters());m.semantics='aligned_v1';m.world_memory_bank=torch.randn(32,32)
    p=tmp_path/'m.json';sha=m.export(p,{'unit_fixture':True});n,_=SeedRSSM.load(p,sha)
    assert n.semantics=='aligned_v1' and torch.equal(n.world_memory_bank,m.world_memory_bank)
    assert sum(p.numel() for p in n.parameters())==count
    e=torch.randn(2,32);assert torch.equal(world_memory(m,e),world_memory(n,e))
    b=Belief(n);before=n.world_memory_bank.clone();b.observe(e[:1],torch.tensor([0]),0)
    assert torch.equal(before,n.world_memory_bank)


def test_pruning_off_preserves_candidates_but_accounts_more_model_states():
    from nexus.seed.latent_planner import plan
    m=SeedRSSM();h,z=m.initial();plan(m,h,z,seed=14,prune=True);first=m.work['transition_rows']
    _,info=plan(m,h,z,seed=14,prune=False)
    assert first==48 and m.work['transition_rows']-first==64 and info['value_pruned']==0


def test_capability_boundaries_and_equal_concept_search_budgets():
    from nexus.seed.capability_audit import language_audit,concept_audit
    l=language_audit();assert l['total']==24 and l['exact']==8
    rows=concept_audit(SeedRSSM(),85410001)
    for r in rows:
        assert not set(r['support_indices'])&set(r['query_indices'])
        assert all(v['candidates_tested']<=8 for k,v in r['conditions'].items() if k!='symbolic_full_reference')


def audit_fixture():
    import hashlib
    c=dict(recipes=['m'],model_seeds=[1],conditions=['legacy'],updates=1,training_seed_start=1,training_episodes=1,source_steps=1,ranking_seed_start=2,ranking_states=1,control_seed_start=3,control_episodes=1,control_steps=1,max_authored_steps=20,max_imagined_transitions=200,max_wall_s=10)
    ep=dict(seed=1,return_sum=1.18,steps=[dict(action=1,reward=1.18,done=True,before=dict(x=0,y=0),after=dict(x=1,y=0),goal=[1,0])])
    concept=dict(support_indices=list(range(8)),query_indices=list(range(8,14)),conditions={k:dict(candidates_tested=0,query_correct=0,query_total=6) for k in ('neural','symbolic_equal_cap','symbolic_full_reference')})
    model=dict(identity='m_1_legacy',condition='legacy',training=dict(updates=1,losses=[dict(update=1,total=.1)]),concepts=[dict(concept,task=i) for i in range(37)])
    metric=dict(selected=0,regret=0.,optimal=True,pairwise_accuracy=1.,score_range=0.,reward_mae=0.,uniform_expected_regret=0.)
    e=copy.deepcopy(ep);e['seed']=3
    r=dict(config=c,models=[model],source=[ep],ranking=[dict(seed=2,outcomes=[dict(action=i,reward=0.,proprio=[0.]*12) for i in range(9)],models={'m_1_legacy':dict(reward=metric,pixels_non_goal_mae=.1,structured_non_goal_mae=.1)})],control={'m_1_legacy':dict(pruned=[e],unpruned=[e])},references=dict(random=[e],greedy=[e]),language=dict(rows=[dict(exact=False)]*24,total=24,exact=0),frozen={'m_1_legacy':True},historical_artifacts_unchanged=True,authored_steps=14,imagined_transitions=139,optimizer_updates=1,wall_s=1.)
    r['source_sha256']=hashlib.sha256(json.dumps(r['source'],sort_keys=True).encode()).hexdigest()
    return r


@pytest.mark.parametrize('fault',['model','seed','ranking','action','prune','reference','metric','nan','frozen'])
def test_contract_study_rejects_incomplete_and_invalid_results(fault):
    from nexus.seed.contract_audit import validate
    r=audit_fixture();assert validate(r)['complete']
    if fault=='model':r['models']=[]
    elif fault=='seed':r['config']['model_seeds']=[1,2]
    elif fault=='ranking':r['ranking']=[]
    elif fault=='action':r['ranking'][0]['outcomes'].pop()
    elif fault=='prune':r['control']['m_1_legacy'].pop('pruned')
    elif fault=='reference':r['references'].pop('random')
    elif fault=='metric':r['ranking'][0]['models']['m_1_legacy'].pop('pixels_non_goal_mae')
    elif fault=='nan':r['ranking'][0]['models']['m_1_legacy']['reward']['regret']=float('nan')
    else:r['frozen']['m_1_legacy']=False
    with pytest.raises(ValueError):validate(r)


def test_explicit_local_checkpoint_audit_fails_instead_of_skipping(tmp_path):
    from nexus.seed.contract_audit import verify_files
    r=dict(models=[dict(checkpoint='runs/missing.json',sha256='a'*64)])
    assert verify_files(r,tmp_path,local_checkpoints=False)
    with pytest.raises(ValueError,match='required_local_checkpoint'):verify_files(r,tmp_path,local_checkpoints=True)
