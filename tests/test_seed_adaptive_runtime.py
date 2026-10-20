import copy
import json
import torch
import pytest
from nexus.world.seed_rssm import SeedRSSM
from nexus.seed.core import Session,examples
from nexus.seed.grounded_agent import GroundedAgent
from nexus.seed.adaptive_state import AdaptiveState,meaning_features
from nexus.seed.plasticity import PlasticityController
from nexus.seed.lab import SeedWorkspace


def agent():
    torch.manual_seed(53);m=SeedRSSM();m.eval()
    for p in m.parameters():p.requires_grad_(False)
    s=Session();s.grounded_agent=GroundedAgent(m,'a'*64,adaptive=AdaptiveState(),controller_hash='b'*64)
    return s


def request(s,action):return s.request(dict(op='grounded',action=action,reference='o1',x=5,y=5,word='dax'))


def test_actual_action_updates_only_small_block_and_inspection_is_readonly():
    s=agent();a=s.grounded_agent;old={k:v.clone() for k,v in a.model.state_dict().items()}
    out=request(s,'adaptive_decide');assert out['result']['result']['adaptation']['updated']
    assert not torch.count_nonzero(a.adaptive.blocks['meaning'])
    assert torch.count_nonzero(a.adaptive.blocks['reward'])
    before=a.adaptive.snapshot();h=a.h.clone();z=a.z.clone()
    for action in ('observe','speak'):
        request(s,action);s.request(dict(op='inspect'))
    assert before==a.adaptive.snapshot() and torch.equal(a.h,h) and torch.equal(a.z,z)
    assert all(torch.equal(old[k],v) for k,v in a.model.state_dict().items())


def test_actual_teaching_routes_meaning_and_restart_preserves_learned_state(tmp_path):
    s=agent();a=s.grounded_agent
    for i in range(5):s.teach('dax',examples()[i],i%2==0)
    assert torch.count_nonzero(a.adaptive.blocks['meaning']) and not torch.count_nonzero(a.adaptive.blocks['reward'])
    from nexus.seed.storage import save,load
    record=save(tmp_path,'a'*32,s);restored=load(tmp_path,'a'*32,record['hash'])
    assert restored.grounded_agent is None # data never grants runtime authority
    workspace=SeedWorkspace(tmp_path,grounded_model=a.model,grounded_hash='a'*64,
        plasticity_controller=a.adaptive.controller,plasticity_hash='b'*64)
    workspace.attach_grounded(restored)
    assert restored.grounded_agent.adaptive.snapshot()==a.adaptive.snapshot()


def test_no_online_update_from_correction_or_hypothetical_answers():
    s=agent();o=examples()[0];ref=s.teach('dax',o,True);count=s.grounded_agent.adaptive.steps
    s.teach('dax',o,False,ref)
    assert s.grounded_agent.adaptive.steps==count
    assert not torch.count_nonzero(s.grounded_agent.adaptive.blocks['meaning'])
    # Contradictory correction does not train another stale label. It requires
    # explicit replay/rebuild before learning its replacement.
    for i in range(1,4):s.teach('dax',examples()[i],False)
    before=copy.deepcopy(s.evidence);steps=s.grounded_agent.adaptive.steps
    request(s,'adaptive_ask')
    assert s.evidence==before and s.grounded_agent.adaptive.steps==steps+1 # actual ask-action reward only


def test_saved_hypothetical_feedback_and_tampered_parameters_rejected():
    from nexus.evolution1.catalogue import digest
    s=agent();request(s,'adaptive_decide');wire=s.snapshot()
    event=next(e for e in wire['data']['events'] if e['kind']=='seed_adaptive_state')
    p=json.loads(event['payload_json']);p['state']['blocks']['reward'][0]=float('inf')
    from nexus.seed.grounded_records import validate_record
    with pytest.raises(ValueError):validate_record('seed_adaptive_state',p,s)
    p=json.loads(event['payload_json']);p['source_ref']='f'*64
    with pytest.raises(ValueError):validate_record('seed_adaptive_state',p,s)


def test_owner_optin_stop_and_independent_session_weights(tmp_path):
    m=SeedRSSM();c=PlasticityController()
    w=SeedWorkspace(tmp_path,grounded_model=m,grounded_hash='a'*64,plasticity_controller=c,plasticity_hash='b'*64)
    first=w.dispatch(dict(session_id=None,request=dict(op='new')))['session_id']
    second=w.dispatch(dict(session_id=None,request=dict(op='new')))['session_id']
    request(w.sessions[first],'adaptive_decide')
    assert not w.sessions[second].grounded_agent.adaptive.steps
    w.sessions[first].request(dict(op='stop'));steps=w.sessions[first].grounded_agent.adaptive.steps
    assert request(w.sessions[first],'adaptive_decide')['response_type']=='stopped'
    assert w.sessions[first].grounded_agent.adaptive.steps==steps
    s=Session();s.grounded_agent=GroundedAgent(m,'a'*64)
    with pytest.raises(ValueError):s.grounded_agent.request(s,'adaptive_decide','o1',5,5,'dax')


def test_scoped_skill_changes_predictions_and_merge_is_executable():
    a=AdaptiveState();x=torch.zeros(62);x[0]=1
    # Independent synthetic protocol fixture: retained old context wants0,
    # new scoped context wants1. No simulator or hidden evaluator involved.
    for i in range(6):
        row=dict(x=x.tolist(),y=1.,ref=f'{i:064x}',key='new')
        a.anchors['reward'].append(row)
    a.anchors['reward'].append(dict(x=x.tolist(),y=0.,ref='a'*64,key='old'))
    a.development['reward']=[dict(x=x.tolist(),y=1.,ref=f'{20+i:064x}',key='new') for i in range(2)]
    report=a.review('reward','new');assert report['adopted']=='add_skill'
    assert a.predict('reward',x,'new')>.9 and a.predict('reward',x,'old')==0
    # The first batch consumed these labels. A later decision cannot reopen them.
    report=a.review('reward','new');assert report['fresh_required']


def test_actual_feedback_automatically_triggers_bounded_structural_decision():
    a=AdaptiveState();x=torch.zeros(62);x[0]=1
    receipts=[a.learn('reward',x,0.,f'{i:064x}',key='known') for i in range(24)]
    reviews=[r['automatic_structural_review'] for r in receipts if 'automatic_structural_review' in r]
    assert len(reviews)==3 and all(r['adopted']=='keep' for r in reviews)
    before=a.work['structural_fits']
    assert a.learn('reward',x,0.,'f'*64,key='known')['status']=='lesson_cap'
    assert a.work['structural_fits']==before
