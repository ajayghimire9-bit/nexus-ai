import copy
import pytest
import numpy as np
torch=pytest.importorskip('torch')
from nexus.seed.action_ranking import registered_world,outcomes,predict,rank_metrics
from nexus.world.seed_rssm import SeedRSSM


def test_shared_state_restoration_and_exact_accounting():
    w=registered_world(913,0);before=copy.deepcopy(w.__dict__);n=[]
    rows=outcomes(w,lambda:n.append(1))
    assert len(n)==9 and w.__dict__==before
    for r in rows:
        c=copy.deepcopy(w);o,reward,done,_=c.step(r['action'])
        assert reward==r['reward'] and done==r['done'] and o['proprio'].tolist()==r['proprio']


def test_registration_boundary_groups_and_reproduction():
    for i in range(8):
        a=registered_world(800+i,i);b=registered_world(800+i,i)
        assert a.__dict__==b.__dict__ and (a.obj['x'],a.obj['y'])!=a.goal
        assert (a.obj['x'] in (0,5) or a.obj['y'] in (0,5))==(i%2==0)


def test_rank_metrics_are_tie_aware_and_reject_nonfinite():
    y=[0.,1.,1.,-1.,0.,0.,0.,0.,0.]
    m=rank_metrics(y,y);assert m['regret']==0 and m['optimal'] and m['pairwise_accuracy']==1
    assert rank_metrics([0.]*9,y)['pairwise_accuracy']==.5
    for bad in ([0.]*8,[float('nan')]*9):
        with pytest.raises(ValueError):rank_metrics(bad,y)


def test_prediction_has_no_query_argument_and_keeps_network_and_world_fixed():
    torch.manual_seed(3);m=SeedRSSM();before=copy.deepcopy(m.state_dict());w=registered_world(913,1)
    first=predict(m,w);again=predict(m,w)
    assert first==again and len(first['reward'])==9
    assert all(torch.equal(v,m.state_dict()[k]) for k,v in before.items())
    assert m.work['transition_rows']==20  # observation prior + nine alternatives, twice
