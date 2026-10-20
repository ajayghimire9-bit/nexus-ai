import copy
import random
import pytest
import torch
from nexus.seed.surprise import SurpriseGate,AssessmentLedger
from nexus.seed.hidden_residual import HiddenResidual
from nexus.seed.adaptive_state import AdaptiveState
from nexus.seed.grounded_meta import OuterSeedMeta
from nexus.seed.action_readout import features,fit
from nexus.seed.state_contract import Belief
from nexus.seed.grounded_world import AuthoredWorld,tensors
from nexus.world.seed_rssm import SeedRSSM


def test_surprise_uses_fixed_actual_error_and_never_edits():
    g=SurpriseGate([1.,1.],development_hash='a'*64)
    assert not g.observe(actual_reward=1.,predicted_reward=1.,receipt_id='1',phase='actual_experience')['investigate']
    r=g.observe(actual_reward=5.,predicted_reward=0.,receipt_id='2',phase='actual_experience')
    assert r['investigate'] and not r['modified'] and g.scale==1
    with pytest.raises(ValueError):g.observe(actual_reward=5.,predicted_reward=0.,receipt_id='2',phase='actual_experience')
    with pytest.raises(ValueError):g.observe(actual_reward=5.,predicted_reward=0.,receipt_id='3',phase='hypothetical')


def test_assessment_is_consumed_even_on_rejection_and_final_is_inaccessible():
    l=AssessmentLedger();token=l.reserve(['a','b'],phase='fresh_development')
    assert not l.assess(token,keep_loss=1,candidate_loss=2,forgetting=0,cost=1)['accept']
    with pytest.raises(ValueError):l.reserve(['a'],phase='fresh_development')
    with pytest.raises(ValueError):l.assess(token,keep_loss=1,candidate_loss=0,forgetting=0,cost=1)
    with pytest.raises(ValueError):l.reserve(['final'],phase='final_audit')
    t=l.reserve(['c'],phase='fresh_development')
    assert not l.assess(t,keep_loss=1,candidate_loss=.1,forgetting=.5,cost=1)['accept']


def test_repeated_review_cannot_reopen_assessment_after_another_lesson():
    s=AdaptiveState();x=torch.zeros(62);x[0]=1
    for i in range(8):s.update('reward',x,1.,f'{i:064x}',key='task')
    s.review('reward','task');assert len(s.used_assessments)==2
    spent=s.work['structural_fits'];s.blocks['reward'][1]=.1
    r=s.review('reward','task');assert r['fresh_required'] and s.work['structural_fits']==spent
    restored=AdaptiveState();restored.restore(s.snapshot());assert restored.used_assessments==s.used_assessments


def test_legacy_development_is_conservatively_retired():
    s=AdaptiveState();x=torch.zeros(62)
    for i in range(4):s.update('reward',x,1.,f'{i:064x}')
    p=s.snapshot();p['schema']='seed_adaptive_state_v2';p.pop('used_assessments')
    restored=AdaptiveState();restored.restore(p)
    assert restored.used_assessments==[f'{3:064x}']


def test_rank_four_is_256_parameters_without_recurrent_writeback():
    torch.manual_seed(45);a=HiddenResidual();h=torch.randn(8,32);before=h.clone()
    assert sum(p.numel() for p in a.parameters())==256 and torch.equal(a(h),h)
    opt=torch.optim.Adam(a.parameters(),lr=.01);initial=float((a(h)-2*h).square().mean().detach())
    for _ in range(10):
        loss=(a(h)-2*h).square().mean();opt.zero_grad();loss.backward();opt.step()
    assert a.U.grad.norm()>0 and a.V.grad.norm()>0 and float(loss.detach())<initial and torch.equal(h,before)


def test_readout_uses_current_posterior_memory_without_changing_it():
    torch.manual_seed(46);m=SeedRSSM();w=AuthoredWorld(47);args=tensors([w.observe()]);b=Belief(m)
    with torch.no_grad():b.observe(m.encode(*args),torch.tensor([0]),0)
    h,z=b.h.clone(),b.z.clone();weights=copy.deepcopy(m.state_dict())
    x,base=features(m,b.h,b.z,args[2],b.memory)
    y=base+x[:,0]*x[:,12];head,_=fit(x,base,y,seed=48,updates=10,check=lambda:None)
    head.rank(m,b.h,b.z,args[2],b.memory)
    assert torch.equal(h,b.h) and torch.equal(z,b.z)
    assert all(torch.equal(v,m.state_dict()[k]) for k,v in weights.items())


def test_edit_credit_is_future_gain_not_acceptance_and_rejections_are_charged():
    m=OuterSeedMeta();rng=random.Random(1);choices=[]
    for i in range(4):
        action=m.choose_edit(rng);choices.append(action)
        receipt=dict(id=str(i),future_error_before=1.,future_error_after=0. if action=='merge' else 1.,forgetting=0.,cost=2.,accepted=False)
        m.reveal_edit(action,receipt,phase='source_training')
    assert set(choices)=={'keep','repair','add_skill','merge'} and m.choose_edit(rng,explore=False)=='merge'
    assert m.controller.predicted_kind_value((),'edit/keep')<0
    with pytest.raises(ValueError):m.reveal_edit('keep',receipt,phase='audit')


def test_resource_upper_bounds():
    import json
    from pathlib import Path
    c=json.loads((Path(__file__).resolve().parents[1]/'configs/seed_surprise_readout.json').read_text())
    states=sum(c[k]['states'] for k in ('source','development','audit'));episodes=8*4
    assert states*9+episodes*20*7<=c['max_authored_steps']
    assert states*9+episodes*20*(4*9+48)<=c['max_imagined_transitions']


def test_manifest_cannot_be_skipped(tmp_path):
    from nexus.seed.readout_validation import require_manifest
    with pytest.raises(ValueError,match='saved_manifest'):require_manifest({},tmp_path)


def test_credit_audit_uses_real_fits_and_no_heldout_updates():
    from nexus.seed.edit_credit_audit import evaluate
    torch.manual_seed(49);x=torch.randn(360,34);base=torch.zeros(360);y=x[:,0]*.2
    r=evaluate(x,base,y,lambda:None)
    assert r['real_new_collection']==0 and r['heldout_feedback_updates']==0
    for p in r['policies'].values():
        assert p['source_journal_entries']==32 and len(p['rows'])==40
        assert all(v['cost']>0 for v in p['rows'])
    assert set(v['action'] for v in r['policies']['adaptive']['rows'][:4])=={'keep','repair','add_skill','merge'}


@pytest.mark.parametrize('missing',['seed','state','task','method','score','episode','nonfinite'])
def test_complete_grid_is_built_from_locked_configuration(missing):
    from nexus.seed.readout_validation import validate
    from nexus.seed.action_ranking import rank_metrics
    c=dict(readout_seeds=[1],updates=1,source=dict(start=1,states=1),development=dict(start=2,states=1),audit=dict(start=3,states=1),control_task_seeds=list(range(10,18)),control_episodes_per_task=1,control_steps=1,methods=['frozen','readout_1'],max_authored_steps=100,max_imagined_transitions=100,max_wall_s=10)
    r=dict(config=c,models=[dict(seed=1,losses=[.1])],source=[dict(seed=1,actual=[0.]*9)],development=[dict(seed=2,actual=[0.]*9)],audit=[dict(seed=3,actual=[0.]*9,scores={m:[0.]*9 for m in c['methods']},metrics={m:rank_metrics([0.]*9,[0.]*9) for m in c['methods']})],control={},frozen_core=True,frozen_bank=True,authored_steps=43,imagined_transitions=0,wall_s=1.)
    e=dict(steps=[dict(action=1,reward=1.18,done=True,before=dict(x=0,y=0),after=dict(x=1,y=0),goal=[1,0])],return_sum=1.18)
    for task in c['control_task_seeds']:r['control'][str(task)]={m:[dict(copy.deepcopy(e),seed=task+100)] for m in c['methods']}
    assert validate(r,c)
    if missing=='seed':r['models']=[]
    elif missing=='state':r['audit']=[]
    elif missing=='task':r['control'].pop('10')
    elif missing=='method':r['control']['10'].pop('frozen')
    elif missing=='score':r['audit'][0]['scores']['frozen'].pop()
    elif missing=='episode':r['control']['10']['frozen']=[]
    else:r['audit'][0]['actual'][0]=float('nan')
    with pytest.raises(ValueError):validate(r,c)
