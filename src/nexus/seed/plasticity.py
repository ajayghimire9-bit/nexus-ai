"""Small differentiable adaptation blocks, not a replacement world or memory.

Only actual labels may enter RuntimeAdapter. Meta-training assessments are an
explicit separate API. The precision solve is memory-sized (Woodbury).
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import torch
from torch import nn


def finite(t):
    if not torch.isfinite(t).all():
        raise ValueError('nonfinite_adaptation')
    return t


def correction(theta, x, y, anchors, diagonal, *, protection=9., damping=1., epsilon=.01):
    """Exact linear-head Jacobian; autograd remains connected to diagonal.

    Pj = Dj - DJ' (I/lambda + JDJ')^-1 JDj. No parameter-sized inverse.
    For nonlinear heads this function requires their explicit local Jacobian;
    the present implementation intentionally adapts linear residuals only.
    """
    if theta.ndim!=1 or x.shape!=theta.shape or diagonal.shape!=theta.shape or anchors.ndim!=2 or anchors.shape[1]!=len(theta):
        raise ValueError('adaptation_shapes')
    if len(theta)>128 or len(anchors)>16 or protection<0 or epsilon<0 or not 0<damping<=1:
        raise ValueError('adaptation_bounds')
    for t in (theta,x,anchors,diagonal,torch.as_tensor(y)):finite(t)
    if not (diagonal>0).all():raise ValueError('positive_plasticity_required')
    pj=diagonal*x
    if len(anchors) and protection:
        jd=anchors*diagonal
        a=torch.eye(len(anchors),dtype=x.dtype,device=x.device)/protection+jd@anchors.T
        pj=pj-diagonal*(anchors.T@torch.linalg.solve(a,jd@x))
    den=epsilon+x@pj
    if float(den.detach())<=0:raise ValueError('unusable_local_gradient')
    return finite(theta+damping*(y-x@theta)*pj/den)


class PlasticityController(nn.Module):
    """Context=(error magnitude, anchor count/16, novelty, task channel).

    This produces bounded positive diagonal settings, not arbitrary code edits.
    Labels of assessments never appear in the context vector.
    """
    def __init__(self,width=62):
        super().__init__()
        if type(width) is not int or not 1<=width<=128:raise ValueError('width')
        self.width=width;self.logits=nn.Linear(4,width)
        nn.init.zeros_(self.logits.weight);nn.init.zeros_(self.logits.bias)

    def forward(self,c):
        if c.shape!=(4,):raise ValueError('plasticity_context')
        return .05+1.95*torch.sigmoid(self.logits(finite(c)))

    def export(self,path,provenance):
        data=dict(schema='seed_plasticity_v1',width=self.width,provenance=provenance,
                  weights={k:v.detach().tolist() for k,v in self.state_dict().items()})
        with Path(path).open('x') as f:json.dump(data,f,allow_nan=False)
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    @classmethod
    def load(cls,path,sha):
        p=Path(path)
        if p.stat().st_size>150000:raise ValueError('controller_size')
        raw=p.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('controller_hash')
        d=json.loads(raw)
        if set(d)!={'schema','width','provenance','weights'} or d['schema']!='seed_plasticity_v1':raise ValueError('controller_schema')
        m=cls(d['width']);expected=m.state_dict()
        def numeric(v):return all(numeric(a) for a in v) if type(v) is list else type(v) in (int,float) and math.isfinite(v)
        if set(d['weights'])!=set(expected) or not all(numeric(v) for v in d['weights'].values()):raise ValueError('controller_weights')
        state={k:torch.tensor(v) for k,v in d['weights'].items()}
        if any(v.shape!=expected[k].shape for k,v in state.items()):raise ValueError('controller_shapes')
        m.load_state_dict(state);m.eval()
        for p in m.parameters():p.requires_grad_(False)
        return m


def context(theta,x,y,anchors,channel=0.):
    error=(y-x@theta).detach().abs().clamp(max=4)/4
    novelty=1. if not len(anchors) else float((anchors-x).square().mean(1).min().detach().clamp(max=1))
    return x.new_tensor([float(error),len(anchors)/16,novelty,channel])


@dataclass(frozen=True)
class TrainingLesson:
    support_x:torch.Tensor
    support_y:torch.Tensor
    query_x:torch.Tensor
    query_y:torch.Tensor
    old_x:torch.Tensor
    old_y:torch.Tensor


def learning_curve(controller,task,*,baseline=False,retention_weight=.5):
    """Meta-training task only. Query outcomes affect phi, never inner theta.

    Fixed replay SGD is the explicit comparator, with its own learning curve.
    It has no dependence on phi. Same teaching sequence and anchor information.
    """
    theta=task.old_x.new_zeros(controller.width)
    if len(task.old_x):theta=(task.old_x.T@torch.linalg.solve(task.old_x@task.old_x.T+1e-6*torch.eye(len(task.old_x)),task.old_y)).detach()
    start=theta.detach().clone();losses=[];forget=[]
    for x,y in zip(task.support_x,task.support_y):
        if baseline:
            grad=(x@theta-y)*x
            if len(task.old_x):grad=grad+task.old_x.T@(task.old_x@theta-task.old_y)/len(task.old_x)
            theta=theta-.2*grad
        else:
            d=controller(context(theta,x,y,task.old_x))
            theta=correction(theta,x,y,task.old_x,d)
        losses.append((task.query_x@theta-task.query_y).square().mean())
        forget.append(((task.old_x@theta-task.old_y).square().mean()-(task.old_x@start-task.old_y).square().mean()) if len(task.old_x) else theta.sum()*0)
    return torch.stack(losses).mean()+retention_weight*torch.stack(forget).mean(),theta,torch.stack(losses),torch.stack(forget)
