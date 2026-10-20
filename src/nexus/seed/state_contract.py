"""One posterior per observed time index; inspection never advances a belief."""
import torch


def world_memory(model,encoded):
    bank=getattr(model,'world_memory_bank',None)
    if bank is None:return torch.zeros(len(encoded),16,device=encoded.device)
    return model.retrieve(encoded,bank.to(encoded.device))[0]


class Belief:
    def __init__(self,model,batch=1):
        self.model=model;self.h,self.z=model.initial(batch);self.token=None
        self.encoded=None;self.memory=None;self.distribution=None

    def observe(self,encoded,previous_action,token,*,sample=False):
        if type(token) is not int or token<0 or self.token is None and token!=0:raise ValueError('valid_observation_index_required')
        if token==self.token:
            if not torch.equal(encoded,self.encoded):raise ValueError('changed_observation_reuses_time_index')
            return self.h,self.z,self.distribution
        if self.token is not None and token!=self.token+1:raise ValueError('nonconsecutive_observation_index')
        self.memory=world_memory(self.model,encoded)
        self.h,self.z,self.distribution=self.model.observe(self.h,self.z,previous_action,encoded,self.memory,sample=sample)
        self.token=token;self.encoded=encoded
        return self.h,self.z,self.distribution

    def clone(self):
        other=Belief(self.model,len(self.h));other.h=self.h.clone();other.z=self.z.clone();other.token=self.token
        other.encoded=None if self.encoded is None else self.encoded.clone()
        other.memory=None if self.memory is None else self.memory.clone()
        other.distribution=self.distribution
        return other


def value_targets(steps,start,length=4,horizon=3,gamma=.9):
    """V3 of the observed current state under the recorded behavior policy.

    Mask truncated suffixes rather than silently treating them as terminal.
    """
    values=[];valid=[]
    for t in range(start,start+length):
        tail=steps[t:t+horizon];total=0.
        for j,s in enumerate(tail):
            total+=gamma**j*s['reward']
            if s['done']:break
        values.append(total);valid.append(len(tail)==horizon or any(s['done'] for s in tail))
    return values,valid
