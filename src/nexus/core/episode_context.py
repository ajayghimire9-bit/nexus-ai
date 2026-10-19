"""Episode-local observed evidence; independent of persistent source memory."""
from collections import deque
import numpy as np


class EpisodeContext:
    def __init__(self,obs_dim,n_actions,*,window=32,source_context=()):
        if any(type(v) is not int or v<=0 for v in (obs_dim,n_actions,window)) or window>128:raise ValueError('context_dimensions')
        self.obs_dim=obs_dim;self.n_actions=n_actions;self.window=window
        self.source_context=tuple(float(v) for v in source_context)
        if not np.isfinite(self.source_context).all():raise ValueError('finite_source_context')
        self._rows=deque(maxlen=window);self.reset_episode()

    def _obs(self,value):
        out=np.asarray(value,dtype=float)
        if out.shape!=(self.obs_dim,) or not np.isfinite(out).all():raise ValueError('finite_observation')
        return out.copy()

    def reset_episode(self,episode_id=None,initial_observation=None):
        self.episode_id=episode_id;self.steps=0;self._rows.clear();self._prediction=None
        self._last=None if initial_observation is None else self._obs(initial_observation)

    def predict_before_action(self,predicted_next):
        if self._prediction is not None:raise ValueError('prediction_already_registered')
        self._prediction=self._obs(predicted_next)

    def observe(self,observation,action,next_observation,reward,*,step=None,episode_id=None):
        if step is not None and (type(step) is not int or step!=self.steps):raise ValueError('chronological_prefix_only')
        if episode_id is not None and episode_id!=self.episode_id:raise ValueError('episode_identity')
        if type(action) is not int or not 0<=action<self.n_actions or type(reward) not in (int,float) or not np.isfinite(reward):raise ValueError('observed_transition_schema')
        obs=self._obs(observation);nxt=self._obs(next_observation)
        if self._last is not None and not np.allclose(obs,self._last,atol=1e-7,rtol=0):raise ValueError('transition_discontinuity')
        error=None if self._prediction is None else float(np.mean(np.abs(nxt-self._prediction)))
        self._rows.append((tuple(obs),action,tuple(nxt),float(reward),error));self.steps+=1;self._last=nxt;self._prediction=None

    def features(self):
        count=len(self._rows);delta=np.zeros(self.obs_dim);history=np.zeros(self.obs_dim);actions=np.zeros(self.n_actions)
        conditional=np.zeros((self.n_actions,self.obs_dim));rewards=[];errors=[]
        for obs,action,nxt,reward,error in self._rows:
            d=np.asarray(nxt)-obs;delta+=np.abs(d);history+=obs;actions[action]+=1;conditional[action]+=d;rewards.append(reward)
            if error is not None:errors.append(error)
        if count:delta/=count;history/=count
        conditional/=np.maximum(actions,1)[:,None]
        return dict(source_context=self.source_context,episode_id=self.episode_id,total_observed=self.steps,
            rolling_observed=count,mean_abs_delta=delta.tolist(),mean_observation=history.tolist(),
            action_counts=actions.astype(int).tolist(),action_conditioned_delta=conditional.tolist(),
            reward_mean=float(np.mean(rewards)) if rewards else 0.,reward_std=float(np.std(rewards)) if rewards else 0.,
            prediction_error_mean=float(np.mean(errors)) if errors else 0.,prediction_error_count=len(errors))


def from_cached_prefix(rows,*,decision_step,obs_dim,n_actions,episode_id,source_context=()):
    if type(decision_step) is not int or decision_step<0 or len(rows)!=decision_step:raise ValueError('exact_predecision_prefix_required')
    context=EpisodeContext(obs_dim,n_actions,source_context=source_context)
    context.reset_episode(episode_id)
    for i,row in enumerate(rows):
        if row['step']!=i or row['episode_id']!=episode_id:raise ValueError('prefix_identity')
        context.observe(row['observation'],row['action'],row['next_observation'],row['reward'],step=i,episode_id=episode_id)
    return context
