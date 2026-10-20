"""Same-state authored action diagnostic. Reuses the frozen RSSM/world adapter."""
import copy
import hashlib
import json
import math
import random
import numpy as np
import torch
from .grounded_world import AuthoredWorld,tensors


def hash_file(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def registered_world(seed,index):
    w=AuthoredWorld(seed);r=random.Random(seed+401)
    if index%2:
        w.obj.update(x=r.randrange(1,5),y=r.randrange(1,5))
    else:
        side=(index//2)%4;v=r.randrange(6)
        w.obj.update(x=(0 if side==0 else 5 if side==1 else v),
                     y=(0 if side==2 else 5 if side==3 else v))
    if (w.obj['x'],w.obj['y'])==w.goal:w.goal=((w.goal[0]+1)%6,w.goal[1])
    return w


def outcomes(world,charge):
    before=copy.deepcopy(world.__dict__);rows=[]
    for action in range(9):
        other=copy.deepcopy(world);charge()
        obs,reward,done,info=other.step(action)
        rows.append(dict(action=action,reward=reward,done=done,proprio=obs['proprio'].tolist(),
                         after=dict(other.obj),flags=list(other.flags),trace=info['trace']))
    if world.__dict__!=before:raise ValueError('same_state_mutated')
    return rows


def predict(model,world):
    """Only current observations enter; no outcomes or future sensors allowed."""
    with torch.no_grad():
        encoded=model.encode(*tensors([world.observe()]));h,z=model.initial()
        h,z,_=model.observe(h,z,torch.zeros(1,dtype=torch.long),encoded)
        nh,nz,_,_=model.transition(h.repeat(9,1),z.repeat(9,1),torch.arange(9))
        out=model.heads(nh,nz)
        return {k:out[k].tolist() for k in ('state','reward','value','done')}


def rank_metrics(predicted,actual):
    p=np.asarray(predicted);y=np.asarray(actual)
    if p.shape!=(9,) or y.shape!=(9,) or not np.isfinite(p).all() or not np.isfinite(y).all():raise ValueError('finite_nine_action_scores')
    choice=int(p.argmax());pairs=[(i,j) for i in range(9) for j in range(i) if abs(y[i]-y[j])>1e-8]
    accuracy=sum(1. if (p[i]-p[j])*(y[i]-y[j])>0 else .5 if p[i]==p[j] else 0. for i,j in pairs)/len(pairs) if pairs else 1.
    return dict(selected=choice,regret=float(y.max()-y[choice]),optimal=bool(y.max()-y[choice]<1e-8),
        pairwise_accuracy=accuracy,score_range=float(np.ptp(p)),reward_mae=float(np.abs(p-y).mean()),
        uniform_expected_regret=float(y.max()-y.mean()))


def finite(v):return type(v) in (int,float) and math.isfinite(v)


def validate_diagnostic(r):
    c=r['config'];expected=list(range(c['state_seed_start'],c['state_seed_start']+c['states']))
    if [s['seed'] for s in r['states']]!=expected:raise ValueError('complete_state_grid')
    if r['authored_steps']!=c['states']*9 or r['authored_steps']>c['max_authored_steps']:raise ValueError('interaction_count')
    for row in r['states']:
        if [o['action'] for o in row['outcomes']]!=list(range(9)):raise ValueError('complete_action_grid')
        if set(row['models'])!=set(c['model_recipes']):raise ValueError('complete_model_grid')
        for m in row['models'].values():
            for name in ('reward','reward_plus_value'):
                if set(m['metrics'][name])!={'selected','regret','optimal','pairwise_accuracy','score_range','reward_mae','uniform_expected_regret'}:raise ValueError('metric_grid')
                if any(not finite(v) for k,v in m['metrics'][name].items() if k!='optimal'):raise ValueError('finite_metrics')
            if any(not finite(v) for v in m['prediction']['reward']):raise ValueError('finite_prediction')
    if not all(r['frozen'].values()):raise ValueError('changed_frozen_model')
    return True
