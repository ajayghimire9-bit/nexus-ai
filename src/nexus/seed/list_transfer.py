"""Gated new-domain adapter; same update rule,not a new learner or environment."""
import random
import torch
from .learning_benchmark import LessonTask,curve


def authorize(gates):
    if set(gates)!={'learning','actions'} or not all(v is True for v in gates.values()):raise ValueError('object_world_success_required_before_transfer')


def task(seed):
    rng=random.Random(seed);permutation=rng.choice([(2,1,0),(1,2,0),(2,0,1)])
    inputs=[[rng.uniform(-1,1) for _ in range(3)] for _ in range(16)]
    x=torch.zeros(16,62);x[:,:3]=torch.tensor(inputs);x[:,-1]=1
    y=torch.tensor([[v[i] for i in permutation] for v in inputs])
    # One zero anchor is a real known zero-list behavior,not a hidden task id.
    old=torch.zeros(1,62);old[:,-1]=1
    lessons=[LessonTask(x[:8],y[:8,j],x[8:],y[8:,j],old,torch.zeros(1),old,torch.zeros(1)) for j in range(3)]
    return lessons,dict(seed=seed,permutation=list(permutation),support_inputs=inputs[:8],query_inputs=inputs[8:])


def evaluate(controllers,seeds,gates,check):
    authorize(gates);result=[]
    for seed in seeds:
        lessons,raw=task(seed);rows=[]
        for ci,c in enumerate(controllers):
            for method in ('learned','fixed','replay','none'):
                curves=[curve(t,c,method,check)[0] for t in lessons]
                rows.append(dict(controller=ci,method=method,curve=[dict(budget=k,mse=sum(float(c[j][1]) for c in curves)/3) for j,k in enumerate((1,2,4,8))]))
        result.append(dict(raw,rows=rows))
    return result
