import copy
import torch
import pytest
from nexus.seed.adaptive_state import AdaptiveState
from nexus.seed.structural_edits import propose,commit,parameters


def fixture():
    s=AdaptiveState();x=torch.zeros(62);x[0]=1
    s.anchors['reward']=[dict(x=x.tolist(),y=1.,ref=f'{i:064x}',key='new') for i in range(3)]
    g=torch.zeros(62);g[1]=1
    s.anchors['reward'].append(dict(x=g.tolist(),y=.0,ref='f'*64,key='old'))
    s.development['reward']=[dict(x=x.tolist(),y=1.,ref=f'{i+10:064x}',key='new') for i in range(2)]
    return s,x,g


def test_addition_has_exact_context_isolation_and_no_replacement():
    s,x,g=fixture();old=s.blocks['reward'].clone();random=torch.randn(20,62)
    before=s.predict('reward',random,'other').clone()
    p=propose(s,'reward','new','add_skill');assert p['allowed'];commit(s,p)
    assert torch.equal(old,s.blocks['reward']) and torch.equal(before,s.predict('reward',random,'other'))
    assert s.predict('reward',x,'new')>.9
    with pytest.raises(ValueError,match='scope_exists'):propose(s,'reward','new','add_skill')


def test_repair_keeps_scopes_and_merge_never_trains():
    s,x,g=fixture();commit(s,propose(s,'reward','new','add_skill'))
    skills=copy.deepcopy(s.skills);p=propose(s,'reward','new','repair')
    assert p['training_updates']==3 and p['parameters']['skills']==skills
    merge=propose(s,'reward','new','merge')
    assert merge['training_updates']==0 and merge['parameters']['skills']==[]
    before=s.predict('reward',x,'new');commit(s,merge)
    assert torch.allclose(before,s.predict('reward',x,'new'),atol=1e-6)
    assert s.predict('reward',g,'old')==0


def test_unsafe_merge_is_rejected_when_it_would_damage_other_knowledge():
    s,x,g=fixture();s.anchors['reward'][-1]['x']=x.tolist()
    commit(s,propose(s,'reward','new','add_skill'));p=propose(s,'reward','new','merge')
    assert not p['allowed'] and p['known_prediction_drift']>.9
    before=parameters(s)
    with pytest.raises(ValueError):commit(s,p)
    assert parameters(s)==before


@pytest.mark.parametrize('operation',['add_skill','repair','merge'])
def test_every_edit_can_be_reversed_without_refunding_work_or_erasing_evidence(operation):
    s,x,g=fixture()
    if operation=='merge':commit(s,propose(s,'reward','new','add_skill'))
    before=parameters(s);p=propose(s,'reward','new',operation);spent=s.work['structural_fits']
    commit(s,p);result=s.rollback()
    assert result['status']=='rolled_back' and parameters(s)==before and s.work['structural_fits']==spent
    assert len(s.anchors['reward'])==4


def test_stale_rollback_cannot_erase_a_subsequent_lesson():
    s,x,g=fixture();commit(s,propose(s,'reward','new','add_skill'))
    s.blocks['meaning'][0]=1
    with pytest.raises(ValueError,match='subsequent_learning'):s.rollback()


def test_repeated_review_is_idempotent_including_compute_and_undo_history():
    s,x,g=fixture();first=s.review('reward','new');before=s.snapshot()
    for _ in range(5):
        result=s.review('reward','new');assert result['cached_review']
    assert s.snapshot()==before
    assert first['adopted'] in ('repair','add_skill')


def test_legacy_state_loads_without_granting_undo_or_review_history():
    s=AdaptiveState();old=s.snapshot();old['schema']='seed_adaptive_state_v1';old.pop('reviews');old.pop('undo');old.pop('used_assessments')
    s.restore(old);assert s.reviews=={} and s.undo==[]
