import copy
import json
from pathlib import Path
import pytest
from nexus.seed.spatial_transfer import world,identity,validate,closed_initials
from nexus.seed.action_ranking import rank_metrics


@pytest.mark.parametrize('group',['corner_goal','opposite_corners','boundary_reversal','cross_diagonal'])
def test_registered_sampling_is_deterministic_and_has_no_outcome_access(group):
    a=world(19,group,set());b=world(19,group,set())
    assert a.__dict__==b.__dict__ and a.steps==0 and a.information_reward is False
    old=identity(a.obj,a.goal);other=world(19,group,{old})
    assert identity(other.obj,other.goal)!=old
    if group=='opposite_corners':assert abs(a.obj['x']-a.goal[0])+abs(a.obj['y']-a.goal[1])==10
    if group=='cross_diagonal':assert (a.goal[0]-a.obj['x'])*(a.goal[1]-a.obj['y'])==-1


def fixture():
    c=dict(groups=['g'],ranking_seed_start=1,ranking_states_per_group=1,control_seed_start=100,streams=8,episodes_per_stream=1,episode_steps=1,head_seeds=[1],methods=['frozen','readout_1'],max_authored_steps=100,max_imagined_transitions=1000,max_wall_s=10)
    s=dict(seed=1,before=dict(x=5,y=5,color='red',shape='square',size='small'),goal=[4,5],actual=[0.]*9,scores={m:[0.]*9 for m in c['methods']},metrics={m:rank_metrics([0.]*9,[0.]*9) for m in c['methods']})
    r=dict(config=c,ranking={'g':[s]},control={'g':{}},closed_initials=[],authored_steps=25,imagined_transitions=153,frozen_core=True,frozen_bank=True,frozen_readouts=True,wall_s=1.)
    for i in range(8):
        before=dict(x=i%4,y=i//4,color='red',shape='square',size='small');after=dict(before,x=before['x']+1)
        e=dict(seed=100+i*100,steps=[dict(action=1,reward=1.18,done=True,before=before,after=after,goal=[after['x'],after['y']])],return_sum=1.18,success=True)
        r['control']['g'][str(i)]={m:[copy.deepcopy(e)] for m in c['methods']}
    return r,c


@pytest.mark.parametrize('fault',['group','stream','method','episode','score','pair','closed','weights','count'])
def test_exact_locked_grid_and_frozen_integrity(fault):
    r,c=fixture();assert validate(r,c)
    if fault=='group':r['ranking']={}
    elif fault=='stream':r['control']['g'].pop('0')
    elif fault=='method':r['control']['g']['0'].pop('frozen')
    elif fault=='episode':r['control']['g']['0']['frozen']=[]
    elif fault=='score':r['ranking']['g'][0]['scores']['frozen'][0]=float('inf')
    elif fault=='pair':r['control']['g']['0']['frozen'][0]['seed']+=1
    elif fault=='closed':r['closed_initials']=[list(identity(r['ranking']['g'][0]['before'],r['ranking']['g'][0]['goal']))]
    elif fault=='weights':r['frozen_core']=False
    else:r['imagined_transitions']+=1
    with pytest.raises(ValueError):validate(r,c)


def test_resource_bound_and_closed_parent_checkpoint_rule():
    root=Path(__file__).resolve().parents[1];c=json.loads((root/'configs/seed_spatial_transfer.json').read_text())
    assert 4*32*9+4*8*2*7*20<=c['max_authored_steps']
    assert 4*32*9+4*8*2*20*(4*9+48)<=c['max_imagined_transitions']
    assert c['max_wall_s']<=c['carried_remaining_s'] and c['head_seeds']==[6301,6302,6303]
