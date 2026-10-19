"""Seed adapter/subclass of existing RandomShootingMPC, not a new planner stack."""
import numpy as np
import torch
from nexus.world.planning import RandomShootingMPC,InferenceCounter


class RSSMStepAdapter:
    uses_simulator=False
    def __init__(self,model,memory=None):
        self.model=model;self.memory=memory;self.last_reward=None
    def begin_rollout(self,n):pass  # State is explicit in each candidate row.
    def step(self,state,action):
        s=torch.as_tensor(np.asarray(state),dtype=torch.float32)
        if s.ndim==1:s=s.unsqueeze(0)
        a=torch.as_tensor(action,dtype=torch.long).expand(len(s))
        memory=None if self.memory is None else self.memory.expand(len(s),-1)
        with torch.no_grad():
            h,z,_,_=self.model.transition(s[:,:32],s[:,32:],a,memory)
            out=self.model.heads(h,z)
            self.last_reward=out['reward'].numpy().copy()
            self.last_value=out['value'].numpy().copy()
            return torch.cat((h,z),-1).numpy(),torch.sigmoid(out['done']).numpy()


class SeedLatentPlanner(RandomShootingMPC):
    def _score_batch(self,obs,seqs):
        n=len(seqs);start=np.repeat(np.asarray(obs).reshape(1,-1),n,0)
        # Learned value prunes half the candidates after a shared one-step probe.
        self.inference.step(start,seqs[:,0])
        estimate=self.model.last_reward+.9*self.model.last_value
        keep=np.argsort(-estimate,kind='stable')[:max(1,n//2)]
        scores=np.full(n,-np.inf);scores[keep]=super()._score_batch(obs,seqs[keep])
        return scores


def plan(model,h,z,memory=None,seed=0):
    adapter=RSSMStepAdapter(model,memory);counter=InferenceCounter(adapter)
    planner=SeedLatentPlanner(model=adapter,n_actions=9,horizon=4,n_candidates=16,
        seed=seed,chunk_size=16,enforce_time_budget=False,inference=counter,
        step_reward=lambda s,a,n:adapter.last_reward)
    action,info=planner.act(torch.cat((h,z),-1)[0].detach().numpy())
    # Nonfinite masked scores are internal pruning sentinels, not JSON metrics.
    info['candidate_scores']=[float(s) if np.isfinite(s) else None for s in info['candidate_scores']]
    info['value_pruned']=8
    return action,info
