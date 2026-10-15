"""A small, source-fitted terminal readout. Existing networks stay frozen."""
from __future__ import annotations
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics

import numpy as np
import yaml

from nexus.world.planning_value import finite_array, sha
from nexus.world.receding_horizon import chunked_scores, _context_snapshot, _same_context
from nexus.world.long_continuation import paired_interval
from nexus.tasks.pendulum_family import pendulum_context_train, pendulum_context_development, pendulum_physics_key

CONFIG=Path('configs/terminal_value.yaml')
PROTOCOL=Path('docs/NEXUS_TERMINAL_VALUE_PROTOCOL.md')
OUTPUT=Path('artifacts/terminal_value.json')
FIT=Path('artifacts/terminal_value_source_fit.json')
NAMES=('zero','0','1','2','3','4')
CONFIG_SHA256='b426beef6da918c94c300fe8935b97c8b1640dadd03f1f9cedc17f3f8bd5b094'


def load_config():
    if sha(CONFIG)!=CONFIG_SHA256: raise ValueError('locked configuration drift')
    cfg=yaml.safe_load(CONFIG.read_text())
    if cfg['train_task_ids']!=[s.task_id for s in pendulum_context_train()] or cfg['eval_task_ids']!=[s.task_id for s in pendulum_context_development()]:
        raise ValueError('task registry drift')
    if cfg['train_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_train()] or cfg['eval_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_development()]:
        raise ValueError('physics registry drift')
    if sha(cfg['parent_capture'])!=cfg['parent_capture_sha256'] or sha('artifacts/control_replication_checkpoints/manifest.json')!=cfg['manifest_sha256']:
        raise ValueError('closed evidence/manifest changed')
    return cfg


def budget(cfg):
    source_support=8*128; source_prefix=8*4*16; source_tail=10*8*4*48
    eval_support=3*128; eval_common=10*3*2*3*64
    model_states=10*8*6*4*16+source_tail*256+10*3*2*6*2*256+10*3*2*3*63*256
    result=dict(source_support=source_support,source_prefix=source_prefix,source_tail=source_tail,
                eval_support=eval_support,eval_common=eval_common,model_states=model_states)
    if sum(v for k,v in result.items() if k!='model_states')!=cfg['env_cap'] or model_states!=cfg['model_cap']:
        raise ValueError('budget arithmetic drift')
    return result


def task_specs():
    return dict(source=[[s.task_id,*pendulum_physics_key(s)] for s in pendulum_context_train()],
                development=[[s.task_id,*pendulum_physics_key(s)] for s in pendulum_context_development()])


def continuation_seeds(cfg,role,task,state=0):
    if role=='source': base=cfg['train_tail_base']+64*task; n=48
    elif role=='evaluation': base=cfg['eval_continuation_base']+256*task+128*state; n=64
    else: raise ValueError('unknown role')
    return list(range(base,base+n))


def seed_groups(cfg):
    groups=[]
    for n,tag in ((8,'train'),(3,'eval')):
        groups.extend([{cfg[tag+'_support_env_base']+10*t for t in range(n)},
                       {cfg[tag+'_support_action_base']+t for t in range(n)}])
    groups.extend([{cfg['train_state_base']+t for t in range(8)}, {cfg['train_candidate_base']+t for t in range(8)},
        {cfg['eval_state_base']+10*t+j for t,j in itertools.product(range(3),range(2))},
        {cfg['eval_candidate_base']+10*t+j for t,j in itertools.product(range(3),range(2))},
        {x for t in range(8) for x in continuation_seeds(cfg,'source',t)},
        {x for t,j in itertools.product(range(3),range(2)) for x in continuation_seeds(cfg,'evaluation',t,j)}])
    return groups


def assert_seeds(cfg):
    from nexus.world.prediction_control_gap import diagnostic_seed_groups,load_prediction_config
    from nexus.world.receding_horizon import horizon_seed_groups,load_horizon_config
    from nexus.world.return_phase import phase_seed_groups,load_phase_config
    from nexus.world.late_control_gap_design import design_seed_groups
    from nexus.world.long_continuation import proposed_seeds,load_config as long_config
    from nexus.world.policy_switch import load_config as switch_config,seeds
    from nexus.world.planning_value import load_config as value_config,seed_groups as value_groups
    a,b=diagnostic_seed_groups(load_prediction_config()); blocked=set()
    for group in (a,b,horizon_seed_groups(load_horizon_config()),phase_seed_groups(load_phase_config()),design_seed_groups(),proposed_seeds(long_config())):
        for values in group.values(): blocked.update(values)
    prior=switch_config();blocked.update([prior['env_seed'],prior['planner_seed']])
    blocked.update(x for p in range(2) for slot in range(6) for x in seeds(prior,p,slot))
    for values in value_groups(value_config()): blocked.update(values)
    for values in seed_groups(cfg):
        if blocked & values: raise ValueError('closed or overlapping episode/RNG seed')
        blocked.update(values)


def support_hash(ds):
    h=hashlib.sha256()
    for name in ('obs','action','next_obs','reward','terminated','truncated','seed','episode_id'):
        block=np.ascontiguousarray(getattr(ds,name))
        h.update(f'{name}:{block.shape}:{block.dtype}:'.encode());h.update(block.tobytes())
    return h.hexdigest()


def polynomial_features(inputs):
    x=np.asarray(inputs,dtype=np.float64)
    if x.ndim!=2 or x.shape[1]!=11 or not np.isfinite(x).all(): raise ValueError('eleven finite observation/context coordinates required')
    i,j=np.triu_indices(11)
    with np.errstate(over='raise',invalid='raise'):
        return np.concatenate([x,x[:,i]*x[:,j]],axis=1)


class TerminalReadout:
    """78 coefficient ridge regression; normalization is fit on source rows only."""
    def __init__(self,mean,scale,weights):
        self.mean=finite_array(list(mean),(77,));self.scale=finite_array(list(scale),(77,));self.weights=finite_array(list(weights),(78,))
        if np.any(self.scale<=0): raise ValueError('invalid feature scale')
    @classmethod
    def fit(cls,inputs,targets,*,ridge=1.0):
        if ridge!=1.0: raise ValueError('locked regularization changed')
        features=polynomial_features(inputs);y=np.asarray(targets,dtype=np.float64)
        if len(features)==0 or y.shape!=(len(features),) or not np.isfinite(y).all(): raise ValueError('invalid source targets')
        mean=features.mean(axis=0);scale=features.std(axis=0);scale=np.where(scale<1e-8,1.,scale)
        x=np.column_stack([np.ones(len(features)),(features-mean)/scale])
        penalty=np.eye(78)*ridge;penalty[0,0]=0
        w=np.linalg.solve(x.T@x/len(x)+penalty,x.T@y/len(x))
        return cls(mean.tolist(),scale.tolist(),w.tolist())
    def predict(self,inputs):
        features=polynomial_features(inputs)
        out=np.column_stack([np.ones(len(features)),(features-self.mean)/self.scale])@self.weights
        if not np.isfinite(out).all(): raise ValueError('nonfinite terminal value')
        return out
    def state_dict(self):
        return dict(mean=self.mean.tolist(),scale=self.scale.tolist(),weights=self.weights.tolist())
    def digest(self):
        return hashlib.sha256(json.dumps(self.state_dict(),sort_keys=True,allow_nan=False).encode()).hexdigest()


def predicted_endpoints(model,obs,sequences):
    seq=np.asarray(sequences)
    if seq.ndim!=2 or seq.shape[1]!=16 or seq.shape[0] not in (4,16) or np.any((seq<0)|(seq>2)) or not np.issubdtype(seq.dtype,np.integer):
        raise ValueError('unregistered candidate array')
    snapshot=_context_snapshot(model);ends=[];survival=[]
    for start in range(0,len(seq),4):
        batch=seq[start:start+4];state=np.repeat(np.asarray(obs,dtype=np.float32).reshape(1,3),len(batch),axis=0)
        alive=np.ones(len(batch));model.begin_rollout(len(batch))
        for step in range(16):
            state,prob=model.step(state,batch[:,step]);state=np.asarray(state,dtype=np.float32)
            prob=np.asarray(prob,dtype=np.float64).reshape(len(batch))
            if state.shape!=(len(batch),3) or not np.isfinite(state).all() or not np.isfinite(prob).all(): raise ValueError('invalid predicted endpoint')
            alive*=1-np.clip(prob,0.,1.)
            _same_context(model,snapshot)
        ends.append(state.copy());survival.append(alive)
    return np.concatenate(ends),np.concatenate(survival)


def value_inputs(endpoints,model):
    context=_context_snapshot(model).detach().cpu().numpy().reshape(1,8)
    return np.concatenate([endpoints,np.repeat(context,len(endpoints),axis=0)],axis=1)


def score_conditions(model,obs,sequences,readout):
    base=chunked_scores(model,obs,sequences)
    endpoint,alive=predicted_endpoints(model,obs,sequences)
    values=readout.predict(value_inputs(endpoint,model))
    corrected=base+alive*values
    if not np.isfinite(corrected).all(): raise ValueError('nonfinite corrected scores')
    return dict(base=base.tolist(),corrected=corrected.tolist(),endpoint=endpoint.tolist(),survival=alive.tolist(),terminal=values.tolist(),inputs=value_inputs(endpoint,model).tolist())


def row_metrics(scores,action_returns,sequences):
    returns=finite_array(action_returns,(3,));seq=np.asarray(sequences)
    if set(scores)!=set(NAMES): raise ValueError('missing context condition')
    values={}
    for name,scored in scores.items():
        for kind in ('base','corrected'):
            vector=finite_array(scored[kind],(16,));index=int(np.argmax(vector));action=int(seq[index,0])
            values[(name,kind)]=float(returns[action])
    mean=lambda kind:statistics.mean(values[(str(s),kind)] for s in range(5))
    return dict(primary=mean('corrected')-mean('base'),student_value_vs_zero=mean('corrected')-values[('zero','base')],
        zero_value_vs_zero=values[('zero','corrected')]-values[('zero','base')],
        student_value_vs_zero_value=mean('corrected')-values[('zero','corrected')],
        corrected_student_regret=float(max(returns))-mean('corrected'),student_regret=float(max(returns))-mean('base'))


def summarize(rows,cfg):
    expected=set(itertools.product(cfg['decoders'],range(3),range(2)));seen={}
    for row in rows:
        key=tuple(row[k] for k in ('decoder','task','state'))
        if any(type(x) is not int for x in key) or key not in expected or key in seen: raise ValueError('invalid/duplicate planned cell')
        metrics=row['metrics']
        if set(metrics)!=set(('primary','student_value_vs_zero','zero_value_vs_zero','student_value_vs_zero_value','corrected_student_regret','student_regret')):
            raise ValueError('missing metric')
        finite_array(list(metrics.values()),(6,));seen[key]=row
    if set(seen)!=expected: raise ValueError('incomplete planned decoder/task/state grid')
    comparisons={}
    for metric in rows[0]['metrics']:
        vals=[statistics.mean(seen[(d,t,j)]['metrics'][metric] for t,j in itertools.product(range(3),range(2))) for d in cfg['decoders']]
        comparisons[metric]=dict(per_decoder=vals,interval=paired_interval(vals))
    ci=comparisons['primary']['interval'];label='local_first_action_inconclusive'
    if ci['mean']>=cfg['practical_margin'] and ci['lo']>0: label='local_first_action_gain'
    elif ci['hi']<0:label='local_first_action_harm'
    return dict(label=label,comparisons=comparisons)


def prepare():
    cfg=load_config();assert_seeds(cfg)
    return dict(status='awaiting_budget_approval',config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),
        tasks=task_specs(),counts=budget(cfg),env_steps=cfg['env_cap'],time_cap_s=cfg['time_cap_s'],
        estimate_minutes=[2,4],network_training_updates=0,readout_coefficients=780,
        history_encoder_rows=70400,new_environment_steps=0)
