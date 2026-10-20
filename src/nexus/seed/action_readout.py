"""Small observed-state residual reward head. The parent RSSM stays frozen."""
import hashlib
import json
import math
from pathlib import Path
import torch
from torch import nn
from nexus.nn.factory import build_mlp


def features(model,h,z,proprio,memory=None):
    with torch.no_grad():
        h=h.expand(9,-1);z=z.expand(9,-1)
        mem=None if memory is None else memory.expand(9,-1)
        nh,nz,_,_=model.transition(h,z,torch.arange(9),mem)
        out=model.heads(nh,nz)
        x=torch.cat((proprio.expand(9,-1),torch.eye(9),out['state'],out['reward'][:,None]),1)
        return x.detach(),out['reward'].detach()


class ActionReadout(nn.Module):
    def __init__(self):
        super().__init__();trunk,width=build_mlp(34,(32,32),'tanh')
        self.net=nn.Sequential(trunk,nn.Linear(width,1));self.sha256=None;self.parent_hash=None

    def forward(self,x):return self.net(x).squeeze(-1)

    def rank(self,model,h,z,proprio,memory=None):
        with torch.no_grad():
            x,base=features(model,h,z,proprio,memory);scores=base+self(x)
        if not torch.isfinite(scores).all():raise ValueError('nonfinite_action_readout')
        action=int(scores.argmax())
        return action,dict(kind='learned_one_step_residual_reward_not_MPC',
            candidate_scores=scores.tolist(),frozen_reward_scores=base.tolist(),
            imagined_transitions=9,readout_sha256=self.sha256,parameter_count=sum(p.numel() for p in self.parameters()))

    def export(self,path,provenance):
        d=dict(schema='seed_action_readout_v1',architecture=dict(input=34,hidden=[32,32],activation='tanh',output=1),provenance=provenance,weights={k:v.detach().tolist() for k,v in self.state_dict().items()})
        with Path(path).open('x') as f:json.dump(d,f,allow_nan=False)
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    @classmethod
    def load(cls,path,sha,parent_hash):
        path=Path(path)
        if path.stat().st_size>200000:raise ValueError('readout_size_cap')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('readout_hash')
        d=json.loads(raw)
        if set(d)!={'schema','architecture','provenance','weights'} or d['schema']!='seed_action_readout_v1' or d['architecture']!=dict(input=34,hidden=[32,32],activation='tanh',output=1) or d['provenance']['parent_hash']!=parent_hash:raise ValueError('readout_parent_or_architecture')
        m=cls();expected=m.state_dict()
        def numeric(v):return all(numeric(x) for x in v) if type(v) is list else type(v) in (int,float) and math.isfinite(v)
        if set(d['weights'])!=set(expected) or not all(numeric(v) for v in d['weights'].values()):raise ValueError('readout_numeric_weights')
        state={k:torch.tensor(v) for k,v in d['weights'].items()}
        if any(v.shape!=expected[k].shape for k,v in state.items()):raise ValueError('readout_shape')
        m.load_state_dict(state);m.eval();m.sha256=sha;m.parent_hash=parent_hash
        for p in m.parameters():p.requires_grad_(False)
        return m


def fit(x,base,targets,*,seed,updates,check,progress=None):
    """Training tensors only: no query argument, evaluator, or environment access."""
    if any(t.requires_grad for t in (x,base,targets)):raise ValueError('detached_source_tensors_required')
    torch.manual_seed(seed);m=ActionReadout();opt=torch.optim.Adam(m.parameters(),lr=.003,weight_decay=.0001)
    g=torch.Generator().manual_seed(seed+67);losses=[]
    for i in range(updates):
        check();idx=torch.randint(len(x),(128,),generator=g)
        loss=(m(x[idx])+base[idx]-targets[idx]).square().mean()
        if not torch.isfinite(loss):raise ValueError('nonfinite_readout_training')
        opt.zero_grad();loss.backward();opt.step();losses.append(float(loss.detach()))
        if progress is not None:progress(i+1,losses[-1])
    m.eval()
    for p in m.parameters():p.requires_grad_(False)
    return m,losses
