"""Fresh-task comparison over SAME frozen Seed core and local update rule.

All query outcomes live in evaluator records. Inner updates accept only a
teaching row and permitted anchors. No new generic learner/memory framework.
"""
import copy
from dataclasses import dataclass
import hashlib
import json
import math
import random
import torch
from .adaptive_state import reward_features
from .grounded_world import AuthoredWorld,observation,tensors
from .state_contract import Belief
from .plasticity import correction,context

METHODS=('learned','fixed','replay','none')
LEARNING_METHODS=METHODS+('neutral',)
WORK={}


def count(name,n=1):WORK[name]=WORK.get(name,0)+int(n)


@dataclass(frozen=True)
class LessonTask:
    support_x:torch.Tensor
    support_y:torch.Tensor
    query_x:torch.Tensor
    query_y:torch.Tensor
    old_x:torch.Tensor
    old_y:torch.Tensor
    retention_x:torch.Tensor
    retention_y:torch.Tensor


def scale_features(rows):
    # Fitted on fresh TRAIN teaching rows only,never query labels/observations.
    return rows.square().mean(0).sqrt().clamp(min=.01)*math.sqrt(rows.shape[1])


def initial(task):
    count('old_anchor_initial_solves')
    x,y=task.old_x,task.old_y
    return x.T@torch.linalg.solve(x@x.T+.01*torch.eye(len(x)),y)


def update(theta,x,y,anchors,old_y,seen_x,seen_y,controller,method,channel=0.):
    count('calls_'+method)
    if method=='none':return theta
    if method=='replay':
        count('replay_prediction_examples',len(anchors)+len(seen_x))
        # Full permitted replay batch; lr <= .5 / trace(H) ensures descent for
        # this linear squared-error objective regardless of feature scaling.
        bx=torch.cat((anchors,seen_x));by=torch.cat((old_y,seen_y))
        step=.5/bx.square().sum(1).mean().clamp(min=1e-6)
        return theta-step*(bx.T@(bx@theta-by)/len(bx))
    if method not in ('learned','fixed','neutral'):raise ValueError('learning_method')
    count('protected_current_examples');count('protected_anchor_examples',len(anchors))
    count('protected_solves',bool(len(anchors)))
    d=controller(context(theta,x,y,anchors,channel))[:len(theta)] if method=='learned' else torch.full_like(theta,1.025 if method=='neutral' else 1.)
    return correction(theta,x,y,anchors,d)


def curve(task,controller,method,check=lambda:None):
    theta=initial(task);start=theta.detach().clone();rows=[];snapshots={}
    for i,(x,y) in enumerate(zip(task.support_x,task.support_y)):
        check()
        # Same old anchor information across all methods; prefix replay is
        # additionally available to SGD. Extra work is reported explicitly.
        theta=update(theta,x,y,task.old_x,task.old_y,task.support_x[:i+1],task.support_y[:i+1],controller,method)
        if i+1 in (1,2,4,8):
            error=(task.query_x@theta-task.query_y).square().mean()
            forgetting=(task.retention_x@theta-task.retention_y).square().mean()-(task.retention_x@start-task.retention_y).square().mean()
            rows.append((i+1,error,forgetting));snapshots[i+1]=theta.detach().clone()
    return rows,snapshots


def frozen_scores(model,obs,belief=None,previous=0,token=0):
    b=belief if belief is not None else Belief(model)
    with torch.no_grad():
        inputs=tensors([obs]);b.observe(model.encode(*inputs),torch.tensor([previous]),token)
        count('posterior_prior_rows')
        x=reward_features(b.h,b.z,inputs[2])
        nh,nz,_,_=model.transition(b.h.expand(9,-1),b.z.expand(9,-1),torch.arange(9),b.memory.expand(9,-1))
        count('imagined_rows',9)
        base=model.heads(nh,nz)['reward']
    return x,base


def world_at(seed,goal,index):
    w=AuthoredWorld(seed);w.information_reward=False;w.goal=tuple(goal)
    # Four near-goal and four arbitrary teaching starts. Sampling does not
    # inspect returns. The task still has boundary and nonmovement actions.
    if index%2==0:
        dx,dy=((-1,0),(1,0),(0,-1),(0,1))[(index//2)%4]
        w.obj.update(x=max(0,min(5,goal[0]+dx)),y=max(0,min(5,goal[1]+dy)))
    if (w.obj['x'],w.obj['y'])==w.goal:w.obj['x']=(w.obj['x']+1)%6
    return w


def collect_task(model,seed,charge,check):
    rng=random.Random(seed);goal=(rng.randrange(6),rng.randrange(6));old_goal=((goal[0]+3)%6,(goal[1]+2)%6)
    records={};arrays={}
    for name,n,target,offset in [('support',8,goal,100),('old',4,old_goal,200),('query',3,goal,300),('retention',3,old_goal,400)]:
        xs=[];ys=[];raw=[]
        for i in range(n):
            check();w=world_at(seed+offset+i,target,i);x,base=frozen_scores(model,w.observe())
            if name in ('query','retention'):
                actual=[]
                for a in range(9):
                    clone=copy.deepcopy(w);charge(name);_,reward,_,_=clone.step(a);actual.append(reward)
                xs.extend(x);ys.extend((torch.tensor(actual)-base).tolist())
                raw.append(dict(seed=seed+offset+i,before=dict(w.obj),goal=list(target),actual=actual,base=base.tolist()))
            else:
                a=(i+seed)%9;before=dict(w.obj);charge(name);_,reward,done,_=w.step(a)
                xs.append(x[a]);ys.append(reward-float(base[a]))
                raw.append(dict(seed=seed+offset+i,before=before,goal=list(target),action=a,reward=reward,done=done,base=float(base[a])))
        arrays[name]=(torch.stack(xs),torch.tensor(ys));records[name]=raw
    task=LessonTask(*arrays['support'],*arrays['query'],*arrays['old'],*arrays['retention'])
    return task,dict(seed=seed,goal=list(goal),records=records,record_sha256=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest())


def scaled(task,scale):
    return LessonTask(task.support_x/scale,task.support_y,task.query_x/scale,task.query_y,
                      task.old_x/scale,task.old_y,task.retention_x/scale,task.retention_y)


def rollout(model,seed,goal,theta,scale,charge,check,max_steps=12,grid=False):
    w=world_at(seed,goal,1);b=Belief(model);previous=0;records=[];total=0.;success=False
    for t in range(max_steps):
        check();before=dict(w.obj)
        if grid:
            dx=w.goal[0]-w.obj['x'];dy=w.goal[1]-w.obj['y']
            a=(1 if dx>0 else 0) if dx else (3 if dy>0 else 2);scores=None
        else:
            x,base=frozen_scores(model,w.observe(),b,previous,t);scores=base+(x/scale)@theta;a=int(scores.argmax())
        charge('control');_,reward,done,_=w.step(a);total+=reward;previous=a
        records.append(dict(step=t,action=a,reward=reward,done=done,before=before,after=dict(w.obj),scores=None if scores is None else scores.tolist()))
        if done:success=True;break
    return dict(seed=seed,goal=list(goal),return_sum=total,success=success,steps=records)
