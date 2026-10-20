import copy
import hashlib
import json
from pathlib import Path
import pytest
torch=pytest.importorskip('torch')
from nexus.seed.action_readout import ActionReadout,features,fit
from nexus.seed.action_ranking import registered_world,rank_metrics
from nexus.seed.grounded_world import tensors
from nexus.seed.grounded_agent import GroundedAgent
from nexus.seed.core import Session
from nexus.world.seed_rssm import SeedRSSM
torch.set_num_threads(1)


def test_residual_head_learns_and_reproduces_without_query_access():
    torch.manual_seed(15);x=torch.randn(64,34);y=x[:,0]*.2;base=torch.zeros(64)
    a,la=fit(x,base,y,seed=3,updates=80,check=lambda:None)
    b,lb=fit(x,base,y,seed=3,updates=80,check=lambda:None)
    assert la==lb and la[-1]<la[0]/5
    assert all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items())
    with pytest.raises(TypeError):fit(x,base,y,seed=3,updates=1,check=lambda:None,query_outcomes=y)
    with pytest.raises(ValueError):fit(x.requires_grad_(),base,y,seed=3,updates=1,check=lambda:None)


def test_frozen_features_only_use_current_sensor_and_do_not_update_parent():
    torch.manual_seed(41);m=SeedRSSM();before=copy.deepcopy(m.state_dict());w=registered_world(718,0)
    args=tensors([w.observe()]);h,z=m.initial()
    x,base=features(m,h,z,args[2]);assert x.shape==(9,34) and not x.requires_grad
    a=ActionReadout();loss=(a(x)+base).square().mean();loss.backward()
    assert any(p.grad is not None and p.grad.norm()>0 for p in a.parameters())
    assert all(p.grad is None for p in m.parameters())
    assert all(torch.equal(v,m.state_dict()[k]) for k,v in before.items())
    w.step(0)  # hidden outcomes cannot enter already constructed feature tensors
    again,_=features(m,h,z,args[2]);assert torch.equal(x,again)


def test_parent_bound_roundtrip_and_rejection(tmp_path):
    a=ActionReadout();path=tmp_path/'a.json';sha=a.export(path,dict(parent_hash='a'*64))
    b=ActionReadout.load(path,sha,'a'*64);x=torch.randn(9,34)
    assert torch.equal(a(x),b(x))
    for sh,parent in [('0'*64,'a'*64),(sha,'b'*64)]:
        with pytest.raises(ValueError):ActionReadout.load(path,sh,parent)
    d=json.loads(path.read_text());d['weights'][next(iter(d['weights']))]=[True];path2=tmp_path/'bad.json';path2.write_text(json.dumps(d))
    with pytest.raises(ValueError):ActionReadout.load(path2,hashlib.sha256(path2.read_bytes()).hexdigest(),'a'*64)


def test_gui_choice_is_owner_enabled_logged_and_evaluation_frozen(tmp_path):
    m=SeedRSSM();a=ActionReadout();path=tmp_path/'a.json';sha=a.export(path,dict(parent_hash='a'*64));a=ActionReadout.load(path,sha,'a'*64)
    s=Session();s.grounded_agent=GroundedAgent(m,'a'*64,a);before=copy.deepcopy(a.state_dict())
    out=s.request(dict(op='grounded',action='ranked_decide',reference='o1',x=3,y=3,word='dax'))
    assert out['result']['planning']['imagined_transitions']==9
    assert out['result']['planning']['kind']=='learned_one_step_residual_reward_not_MPC'
    assert Session.restore(s.snapshot()).snapshot()==s.snapshot()
    assert all(torch.equal(v,a.state_dict()[k]) for k,v in before.items())
    s.request(dict(op='stop'));assert s.request(dict(op='grounded',action='ranked_decide',reference='o1',x=3,y=3,word='dax'))['response_type']=='stopped'
    with pytest.raises(ValueError):GroundedAgent(m,'b'*64,a)
    other=Session();other.grounded_agent=GroundedAgent(m,'a'*64)
    assert other.request(dict(op='grounded',action='ranked_decide',reference='o1',x=3,y=3,word='dax'))['response_type']=='error'


def fixture_result(root):
    from nexus.seed.action_ranking import hash_file
    c=dict(model_recipes=['m'],readout_seeds=[1],updates=1,training_states=1,training_seed_start=901,audit_states=1,audit_seed_start=902,control_episodes=1,control_seed_start=903,control_steps=1,methods=['greedy'],max_wall_s=10,max_authored_steps=19,max_imagined_transitions=18)
    (root/'configs').mkdir();(root/'artifacts').mkdir();cfg=root/'configs/seed_action_readout.json';cfg.write_text(json.dumps(c));ch=hash_file(cfg)
    source=[dict(seed=901,outcomes=[dict(action=i,reward=0.) for i in range(9)])];sh=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
    provenance=dict(parent_hash='a'*64,source_sha256=sh,config_sha256=ch,execution_sha='b'*40,seed=1)
    head=root/'artifacts/head.json';head.write_text(json.dumps(dict(provenance=provenance)))
    h=dict(seed=1,checkpoint='artifacts/head.json',sha256=hash_file(head),losses=[.1])
    models=[dict(recipe='m',parent_hash='a'*64,heads=[h])]
    manifest=dict(config_sha256=ch,source_sha256=sh,execution_sha='b'*40,models=[dict(recipe='m',parent_hash='a'*64,heads=[{k:h[k] for k in ('seed','checkpoint','sha256')}])])
    p=root/'artifacts/seed_action_readout_manifest.json';p.write_text(json.dumps(manifest))
    scores={k:[0.]*9 for k in ('frozen_reward','source_mean','calibrated_1')}
    audit=[dict(seed=902,outcomes=copy.deepcopy(source[0]['outcomes']),models=dict(m=dict(scores=scores,metrics={k:rank_metrics(v,[0.]*9) for k,v in scores.items()})))]
    e=dict(seed=903,return_sum=1.18,steps=[dict(action=1,reward=1.18,done=True,before=dict(x=0,y=0),after=dict(x=1,y=0),goal=[1,0])])
    return dict(config=c,config_sha256=ch,source_sha256=sh,execution_sha='b'*40,manifest_sha256=hash_file(p),models=models,source=source,audit=audit,control=dict(m=dict(greedy=[e])),frozen=dict(m=True),wall_s=1.,authored_steps=19,imagined_transitions=18)


@pytest.mark.parametrize('kind',['parent','seed','state','action','condition','episode','nonfinite','manifest'])
def test_exact_grid_and_manifest_fail_closed(tmp_path,kind):
    from nexus.seed.readout_audit import validate,require_manifest
    r=fixture_result(tmp_path);assert validate(r,tmp_path)['complete']
    bad=copy.deepcopy(r)
    if kind=='parent':bad['models']=[]
    elif kind=='seed':bad['models'][0]['heads']=[]
    elif kind=='state':bad['audit']=[]
    elif kind=='action':bad['audit'][0]['outcomes'].pop()
    elif kind=='condition':bad['audit'][0]['models']['m']['scores'].pop('source_mean')
    elif kind=='episode':bad['control']['m']['greedy']=[]
    elif kind=='nonfinite':bad['audit'][0]['models']['m']['scores']['source_mean'][0]=float('nan')
    else:
        (tmp_path/'artifacts/seed_action_readout_manifest.json').unlink()
        with pytest.raises(ValueError):require_manifest(r,tmp_path)
    with pytest.raises(ValueError):validate(bad,tmp_path)
