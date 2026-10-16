"""Action-conditioned first-action Q with explicit action×observation interactions.

The locked 81-coefficient additive protocol is not modified and is not executed here.
Collection is blocked until a fresh human allocation is committed.
"""
from __future__ import annotations
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import time
import numpy as np
import yaml
from nexus.world import first_action_value as linear_q
from nexus.world import capacity_matched_q as poly_q
from nexus.world import visited_commitment as visited
from nexus.world import source_scalar_calibration as scalar
from nexus.world.planning_value import sha, finite_array
from nexus.world.long_continuation import paired_interval
from nexus.world.terminal_value import NAMES, TerminalReadout, score_conditions
from nexus.world.terminal_value_execution import checked_id_grid, fingerprints, save
from nexus.world.commitment_value import continue_locked, total, validate_endpoint, validate_trace
from nexus.world.prediction_control_gap import candidate_sequences

CONFIG=Path('configs/action_conditioned_q.yaml')
PROTOCOL=Path('docs/NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md')
ALLOCATION=Path('configs/action_conditioned_q_allocation.json')
FIT=Path('artifacts/action_conditioned_q_fit.json')
OUTPUT=Path('artifacts/action_conditioned_q.json')
FEASIBILITY=Path('artifacts/action_conditioned_q_feasibility.json')
USAGE=Path('artifacts/research_session_first_action_value_usage.json')
ALLOWED_RIDGE=(0.1,1.0,10.0)
ELIGIBLE=('action_obs','action_obs_z','action_obs_action_z')
FAMILIES={
    'additive':dict(n_features=6,uses_z=False,action_obs=False,action_z=False,state_dependent=False),
    'action_obs':dict(n_features=15,uses_z=False,action_obs=True,action_z=False,state_dependent=True),
    'action_obs_z':dict(n_features=23,uses_z=True,action_obs=True,action_z=False,state_dependent=True),
    'action_obs_action_z':dict(n_features=47,uses_z=True,action_obs=True,action_z=True,state_dependent=True),
}
FIELDS=('h16_first','sequence_first','additive_first','conditioned_first','gain_vs_h16','gain_vs_additive',
        'gain_vs_sequence','additive_vs_h16','sequence_vs_h16','h16_regret','additive_regret','conditioned_regret',
        'sequence_regret','q_rmse','additive_rmse','conditioned_h16_agree','conditioned_additive_agree','conditioned_sequence_agree')


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),source_tasks=8,source_states=2,eval_tasks=3,visitors=2,
                phase=50,horizon=16,n_candidates=16,total_steps=64,family='action_obs',additive_family='additive',
                ridge=0.1,n_features=15,n_weights=16,additive_n_features=6,additive_n_weights=7,practical_margin=1.0,
                time_cap_s=240,env_cap=45240,model_cap=11612160,source_state_base=6000000,source_future_base=6010000,
                reset_base=6100000,collection_base=6110000,candidate_base=6300000,future_base=6400000)
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked action-conditioned design/budget changed')
    if FAMILIES[cfg['family']]['n_features']!=cfg['n_features'] or cfg['n_weights']!=cfg['n_features']+1:
        raise ValueError('registered family width mismatch')
    if not FAMILIES[cfg['family']]['state_dependent']:raise ValueError('registered family cannot rank actions by state')
    from nexus.tasks.pendulum_family import pendulum_context_train,pendulum_context_development,pendulum_physics_key
    if cfg['source_task_ids']!=[s.task_id for s in pendulum_context_train()]:raise ValueError('source physics changed')
    if cfg['eval_task_ids']!=[s.task_id for s in pendulum_context_development()]:raise ValueError('development physics changed')
    if cfg['source_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_train()]:raise ValueError('source physics values changed')
    if cfg['eval_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_development()]:raise ValueError('eval physics values changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg);check_seeds(cfg)
    return cfg


def source_state_seed(cfg,t,k):return cfg['source_state_base']+10*t+k
def source_future_seeds(cfg,t,k):
    base=cfg['source_future_base']+256*t+64*k
    return list(range(base,base+64))
def reset_seed(cfg,d,t):return cfg['reset_base']+100*d+t
def collection_seeds(cfg,d,t):return list(range(cfg['collection_base']+10000*d+100*t,cfg['collection_base']+10000*d+100*t+50))
def candidate_seed(cfg,d,t,v):return cfg['candidate_base']+100*d+10*t+v
def future_seeds(cfg,d,t,v):return list(range(cfg['future_base']+10000*d+1000*t+100*v,cfg['future_base']+10000*d+1000*t+100*v+64))
def visitor_student(d,t):return (d+t)%5


def seed_groups(cfg):
    k_states=cfg['source_states']
    return [
        {source_state_seed(cfg,t,k) for t,k in itertools.product(range(8),range(k_states))},
        {s for t,k in itertools.product(range(8),range(k_states)) for s in source_future_seeds(cfg,t,k)},
        {reset_seed(cfg,d,t) for d,t in itertools.product(range(10),range(3))},
        {s for d,t in itertools.product(range(10),range(3)) for s in collection_seeds(cfg,d,t)},
        {candidate_seed(cfg,d,t,v) for d,t,v in itertools.product(range(10),range(3),range(2))},
        {s for d,t,v in itertools.product(range(10),range(3),range(2)) for s in future_seeds(cfg,d,t,v)},
    ]


def check_seeds(cfg):
    visited.check_seeds(visited.load_config());scalar.load_config()
    linear_q.check_seeds(linear_q.load_config());poly_q.check_seeds(poly_q.load_config())
    blocked=set().union(*scalar.seed_sets(visited.load_config()),*scalar.seed_sets(scalar.load_config()),
                        *poly_q.seed_groups(linear_q.load_config()),*poly_q.seed_groups(poly_q.load_config()))
    groups=seed_groups(cfg)
    if [len(g) for g in groups]!=[16,1024,30,1500,60,3840]:raise ValueError('duplicate registered seeds')
    for group in groups:
        if group & blocked or min(group)<6000000:raise ValueError('closed or overlapping seeds')
        blocked.update(group)


def budget(cfg):
    k=cfg['source_states']
    counts=dict(source_labels=15360*k,collection=3000,first_common=11520,model_states=3870720*k+3870720)
    if sum(v for k_,v in counts.items() if k_!='model_states')!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:
        raise ValueError('action-conditioned resource allocation mismatch')
    return counts


def _vector(value,n):
    arr=np.asarray(value,dtype=np.float64).reshape(-1)
    if arr.shape!=(n,) or not np.isfinite(arr).all():raise ValueError('finite observation/context vector required')
    return arr


def features(family,obs,z,actions):
    spec=FAMILIES[family];obs=_vector(obs,3);act=np.asarray(actions,dtype=np.int64).reshape(-1)
    if act.size==0 or np.any((act<0)|(act>2)):raise ValueError('discrete first actions required')
    onehot=np.eye(3,dtype=np.float64)[act];obs_rep=np.repeat(obs.reshape(1,3),len(act),axis=0)
    parts=[obs_rep]
    if spec['uses_z']:
        z=_vector(z,8);z_rep=np.repeat(z.reshape(1,8),len(act),axis=0);parts.append(z_rep)
    parts.append(onehot)
    if spec['action_obs']:parts.append((obs_rep[:,None,:]*onehot[:,:,None]).reshape(len(act),9))
    if spec['action_z']:parts.append((z_rep[:,None,:]*onehot[:,:,None]).reshape(len(act),24))
    out=np.concatenate(parts,axis=1)
    if out.shape!=(len(act),spec['n_features']):raise ValueError('feature width drift')
    return out


class RidgeQ:
    """Ridge Q with a family-specific feature width. Intercept is unpenalized."""
    def __init__(self,mean,scale,weights):
        n=len(mean)
        self.mean=finite_array(list(mean),(n,));self.scale=finite_array(list(scale),(n,));self.weights=finite_array(list(weights),(n+1,))
        if np.any(self.scale<=0):raise ValueError('invalid Q feature scale')
    @classmethod
    def fit(cls,inputs,targets,*,ridge):
        if ridge not in ALLOWED_RIDGE:raise ValueError('Q regularization not in the source-only grid')
        x=np.asarray(inputs,dtype=np.float64);y=np.asarray(targets,dtype=np.float64)
        if x.ndim!=2 or y.shape!=(len(x),) or not np.isfinite(x).all() or not np.isfinite(y).all() or len(x)==0:
            raise ValueError('invalid Q source arrays')
        mean=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale<1e-8,1.,scale)
        phi=np.column_stack([np.ones(len(x)),(x-mean)/scale]);penalty=np.eye(x.shape[1]+1)*ridge;penalty[0,0]=0
        weights=np.linalg.solve(phi.T@phi/len(x)+penalty,phi.T@y/len(x))
        return cls(mean.tolist(),scale.tolist(),weights.tolist())
    def predict(self,inputs):
        x=np.asarray(inputs,dtype=np.float64)
        if x.ndim!=2 or x.shape[1]!=len(self.mean):raise ValueError('Q feature width mismatch')
        out=np.column_stack([np.ones(len(x)),(x-self.mean)/self.scale])@self.weights
        if not np.isfinite(out).all():raise ValueError('nonfinite action value')
        return out
    def state_dict(self):
        return dict(mean=self.mean.tolist(),scale=self.scale.tolist(),weights=self.weights.tolist())
    def digest(self):
        return hashlib.sha256(json.dumps(self.state_dict(),sort_keys=True,allow_nan=False).encode()).hexdigest()


def preferred_actions(readout,family,observations,z=None):
    chosen=[]
    for obs in observations:
        q=readout.predict(features(family,obs,z,[0,1,2]))
        chosen.append(int(np.argmax(q)))
    return chosen


def ranking_is_state_dependent(readout,family,z=None):
    plus=np.array([0.8,0.0,0.0]);minus=np.array([-0.8,0.0,0.0])
    return preferred_actions(readout,family,[plus,minus],z)[0]!=preferred_actions(readout,family,[plus,minus],z)[1]


def design_diagnostics(family,feature_matrix,targets,ridge=1.0):
    x=np.asarray(feature_matrix,dtype=np.float64);y=np.asarray(targets,dtype=np.float64)
    spec=FAMILIES[family]
    if x.ndim!=2 or x.shape[1]!=spec['n_features'] or y.shape!=(len(x),):raise ValueError('diagnostic width mismatch')
    mean=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale<1e-8,1.,scale)
    phi=np.column_stack([np.ones(len(x)),(x-mean)/scale]);penalty=np.eye(x.shape[1]+1)*ridge;penalty[0,0]=0
    return dict(family=family,n_rows=int(len(x)),n_features=spec['n_features'],n_weights=spec['n_features']+1,ridge=ridge,
                feature_rank=int(np.linalg.matrix_rank(x,tol=1e-8)),augmented_rank=int(np.linalg.matrix_rank(phi,tol=1e-8)),
                gram_condition=float(np.linalg.cond(phi.T@phi/len(x)+penalty)),
                state_dependent=spec['state_dependent'],uses_context=spec['uses_z'],
                unique_targets=int(len({(round(v,8)) for v in y})))


def unique_source_examples(decoder,cells):
    selected=[r for r in cells if r['decoder']==decoder]
    rows=checked_id_grid(selected,('decoder','task'),{(decoder,t) for t in range(8)})
    examples=[]
    for t in range(8):
        obs=rows[(decoder,t)]['obs'];y=finite_array(rows[(decoder,t)]['returns'],(3,))
        for a in range(3):
            examples.append(dict(task=int(t),obs=obs,action=a,y=float(y[a])))
    return examples


def stack_examples(family,examples,contexts=None):
    xs=[];ys=[]
    for e in examples:
        if FAMILIES[family]['uses_z']:
            if contexts is None:raise ValueError('context-using family needs frozen z')
            for name in NAMES:
                xs.append(features(family,e['obs'],contexts[e['task']][name],[e['action']])[0]);ys.append(e['y'])
        else:
            xs.append(features(family,e['obs'],None,[e['action']])[0]);ys.append(e['y'])
    return np.asarray(xs,dtype=np.float64),np.asarray(ys,dtype=np.float64)


def leave_one_task_out(examples,family,ridge,contexts=None):
    tasks=sorted({e['task'] for e in examples});hits=[];rmses=[]
    for hold in tasks:
        train=[e for e in examples if e['task']!=hold];test=[e for e in examples if e['task']==hold]
        x,y=stack_examples(family,train,contexts);model=RidgeQ.fit(x,y,ridge=ridge)
        hold_obs=test[0]['obs'];y_true=np.array([e['y'] for e in sorted(test,key=lambda row:row['action'])])
        if FAMILIES[family]['uses_z']:
            preds=[model.predict(features(family,hold_obs,contexts[hold][name],[0,1,2])) for name in NAMES]
            q=np.mean(preds,axis=0)
        else:
            q=model.predict(features(family,hold_obs,None,[0,1,2]))
        rmses.append(float(np.sqrt(np.mean((q-y_true)**2))))
        hits.append(float(int(np.argmax(q))==int(np.argmax(y_true))))
    return dict(action_id=float(np.mean(hits)),rmse=float(np.mean(rmses)),n_held_out_tasks=len(tasks),n_weights=FAMILIES[family]['n_features']+1)


def select_registered_family(table):
    best=None
    for family in ELIGIBLE:
        for ridge in ALLOWED_RIDGE:
            row=table[family][str(ridge)]
            key=(row['action_id'],-row['n_weights'],-row['rmse'])
            if best is None or key>best[0]:best=(key,family,ridge)
    family,ridge=best[1],best[2];row=table[family][str(ridge)]
    return dict(family=family,ridge=ridge,action_id=row['action_id'],rmse=row['rmse'],n_weights=row['n_weights'])


def score_q(readout,family,obs,z,sequences):
    seq=np.asarray(sequences,dtype=np.int64)
    if seq.shape!=(16,16):raise ValueError('aligned scoring requires the locked candidate set')
    q=readout.predict(features(family,obs,z,seq[:,0]))
    index=int(np.argmax(q));return dict(values=q.tolist(),selected=index,first_action=int(seq[index,0]))


def row_metrics(scores,sequences,first_returns,conditioned,additive,obs,family,additive_family):
    first=finite_array(first_returns,(3,));seq=np.asarray(sequences,dtype=np.int64);out={}
    if set(scores)!=set(NAMES):raise ValueError('missing scoring context')
    for name,s in scores.items():
        h16_i,h16_a=linear_q.choose_first(s['base'],seq);seq_i,seq_a=linear_q.choose_first(s['corrected'],seq)
        z=finite_array(s['inputs'],(16,11))[0,3:]
        cond=score_q(conditioned,family,obs,z if FAMILIES[family]['uses_z'] else None,seq)
        add=score_q(additive,additive_family,obs,z if FAMILIES[additive_family]['uses_z'] else None,seq)
        q_cond=conditioned.predict(features(family,obs,z if FAMILIES[family]['uses_z'] else None,[0,1,2]))
        q_add=additive.predict(features(additive_family,obs,z if FAMILIES[additive_family]['uses_z'] else None,[0,1,2]))
        m=dict(h16_first=float(first[h16_a]),sequence_first=float(first[seq_a]),additive_first=float(first[add['first_action']]),
               conditioned_first=float(first[cond['first_action']]))
        m.update(gain_vs_h16=m['conditioned_first']-m['h16_first'],gain_vs_additive=m['conditioned_first']-m['additive_first'],
                 gain_vs_sequence=m['conditioned_first']-m['sequence_first'],additive_vs_h16=m['additive_first']-m['h16_first'],
                 sequence_vs_h16=m['sequence_first']-m['h16_first'],h16_regret=float(max(first))-m['h16_first'],
                 additive_regret=float(max(first))-m['additive_first'],conditioned_regret=float(max(first))-m['conditioned_first'],
                 sequence_regret=float(max(first))-m['sequence_first'],
                 q_rmse=float(np.sqrt(np.mean((q_cond-first)**2))),additive_rmse=float(np.sqrt(np.mean((q_add-first)**2))),
                 conditioned_h16_agree=float(cond['first_action']==h16_a),conditioned_additive_agree=float(cond['first_action']==add['first_action']),
                 conditioned_sequence_agree=float(cond['first_action']==seq_a))
        if set(m)!=set(FIELDS):raise ValueError('metric schema drift')
        finite_array([m[k] for k in FIELDS],(len(FIELDS),));out[name]=m
    return out


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task','state'),set(itertools.product(range(10),range(3),range(2))))
    for row in cells.values():
        if set(row['metrics'])!=set(NAMES):raise ValueError('missing scoring context')
        for metrics in row['metrics'].values():
            if set(metrics)!=set(FIELDS):raise ValueError('missing first-action metric')
            finite_array([metrics[k] for k in FIELDS],(len(FIELDS),))
    definitions=[('pooled',range(3),range(2),[str(s) for s in range(5)]),('zero_context',range(3),range(2),['zero'])]
    definitions+=[(f'task_{t}',[t],range(2),[str(s) for s in range(5)]) for t in range(3)]
    definitions+=[(name,range(3),[v],[str(s) for s in range(5)]) for v,name in enumerate(('student_visitor','zero_visitor'))]
    groups={}
    for name,tasks,visitors,students in definitions:
        groups[name]={}
        for metric in FIELDS:
            values=[statistics.mean(cells[d,t,v]['metrics'][s][metric] for t,v,s in itertools.product(tasks,visitors,students)) for d in range(10)]
            groups[name][metric]=dict(per_decoder=values,interval=paired_interval(values))
    primary=groups['pooled']['gain_vs_h16']['interval'];label='action_conditioned_gain_not_established'
    if primary['mean']>=cfg['practical_margin'] and primary['lo']>0:label='action_conditioned_gain'
    elif primary['hi']<0:label='action_conditioned_harm'
    return dict(label=label,groups=groups)


def classify_primary(mean,lo,hi,n,threshold=1.0,complete=True):
    if not complete or int(n)!=10:return 'incomplete'
    if hi<0:return 'action_conditioned_harm'
    if mean>=threshold and lo>0:return 'action_conditioned_gain'
    return 'action_conditioned_gain_not_established'


def source_training_arrays(decoder,cells,family,contexts=None):
    selected=[r for r in cells if r['decoder']==decoder]
    keys=set((decoder,r['task'],r['state']) for r in selected)
    rows=checked_id_grid(selected,('decoder','task','state'),keys)
    examples=[]
    for (d,t,k),row in sorted(rows.items()):
        y=finite_array(row['returns'],(3,))
        for a in range(3):
            examples.append(dict(task=t,obs=row['obs'],action=a,y=float(y[a])))
    return stack_examples(family,examples,contexts)


def historical_source_cells():
    raw=json.loads(linear_q.OUTPUT.read_text())
    return [dict(decoder=r['decoder'],task=r['task'],obs=r['obs'],returns=r['returns']) for r in raw['source_cells']]


def source_cross_task_table(cells,context_by_decoder=None):
    table={family:{str(ridge):dict(action_id=[],rmse=[]) for ridge in ALLOWED_RIDGE} for family in FAMILIES}
    for d in range(10):
        examples=unique_source_examples(d,cells)
        if len(examples)!=24:raise ValueError('historical unique source labels are not 24')
        contexts=None if context_by_decoder is None else context_by_decoder[d]
        for family in FAMILIES:
            if FAMILIES[family]['uses_z'] and contexts is None:continue
            for ridge in ALLOWED_RIDGE:
                row=leave_one_task_out(examples,family,ridge,contexts)
                table[family][str(ridge)]['action_id'].append(row['action_id'])
                table[family][str(ridge)]['rmse'].append(row['rmse'])
    summary={}
    for family,by_ridge in table.items():
        summary[family]={}
        for ridge,stats in by_ridge.items():
            if not stats['action_id']:continue
            summary[family][ridge]=dict(action_id=float(np.mean(stats['action_id'])),rmse=float(np.mean(stats['rmse'])),
                                        n_weights=FAMILIES[family]['n_features']+1,n_decoders=len(stats['action_id']),
                                        action_id_per_decoder=stats['action_id'],rmse_per_decoder=stats['rmse'])
    return summary


class Meter(visited.Meter):
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='source_labels'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('action-conditioned-q execution cap reached')


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),time_cap_s=240,env_cap=45240,model_cap=11612160).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('action-conditioned allocation drift')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before collection')
    usage=json.loads(Path(record['previous_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def require_fit(cfg):
    stage=json.loads(FIT.read_text())
    if stage.get('complete') is not True or stage['config_sha256']!=sha(CONFIG) or stage['protocol_sha256']!=sha(PROTOCOL):
        raise ValueError('stale/missing source Q fit')
    return stage


def verify_inputs():
    cfg=load_config();parent,stage=visited.prior.parent_evidence()
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.control_replication import load_replication_config,_confirmation_artifact
    checks=verify_checkpoint_integrity();rep=load_replication_config();confirmation=_confirmation_artifact(rep)
    for d,t in itertools.product(cfg['decoders'],range(3)):visited.prior.load_models(d,t+8,rep,confirmation,parent,stage)
    if set(stage['readouts'])!={str(d) for d in cfg['decoders']}:raise ValueError('missing frozen sequence-value readout')
    return dict(checkpoints=checks,model_context_groups=30,sequence_readouts=10,new_environment_steps=0)


def _synthetic_interaction_data(n=48):
    rng=np.random.default_rng(0);examples=[]
    for i in range(n):
        obs=rng.normal(size=3);obs[0]=0.6 if i%2==0 else -0.6
        for a in range(3):
            y=10.0*obs[0] if a==0 else (-10.0*obs[0] if a==1 else 0.0)
            examples.append(dict(task=i%8,obs=obs.tolist(),action=a,y=y))
    return examples


def feasibility():
    cfg=load_config();load_allocation()
    syn=_synthetic_interaction_data()
    x_add,y_add=stack_examples('additive',syn)
    x_int,y_int=stack_examples('action_obs',syn)
    add=RidgeQ.fit(x_add,y_add,ridge=1.0);cond=RidgeQ.fit(x_int,y_int,ridge=1.0)
    synthetic=dict(additive_state_dependent=ranking_is_state_dependent(add,'additive'),
                   action_obs_state_dependent=ranking_is_state_dependent(cond,'action_obs'),
                   additive_preferred=preferred_actions(add,'additive',[np.array([0.8,0,0]),np.array([-0.8,0,0])]),
                   action_obs_preferred=preferred_actions(cond,'action_obs',[np.array([0.8,0,0]),np.array([-0.8,0,0])]))
    if synthetic['action_obs_state_dependent'] is not True or synthetic['additive_state_dependent'] is not False:
        raise ValueError('synthetic ranking check failed')
    cells=historical_source_cells()
    parent,stage=visited.prior.parent_evidence()
    context_by_decoder={}
    for d in range(10):
        context_by_decoder[d]={}
        for t in range(8):
            z,_=visited.prior.saved_contexts(parent,stage,d,t)
            context_by_decoder[d][t]={name:np.asarray(value,dtype=np.float64) for name,value in z.items()}
    cv=source_cross_task_table(cells,context_by_decoder)
    chosen=select_registered_family(cv)
    if chosen['family']!=cfg['family'] or chosen['ridge']!=cfg['ridge']:
        note='source CV preferred a different eligible family/ridge; the yaml lock is the registered object and was not silently retuned after this report'
    else:
        note='source CV selected the registered family and ridge'
    unique_x,unique_y=stack_examples('action_obs',unique_source_examples(0,cells))
    report=dict(complete=True,config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                new_environment_steps=0,new_imagined_transitions=0,authorized=False,
                remaining_session_allowance_s=json.loads(USAGE.read_text())['remaining_session_allowance_s'],
                historical_unique_labels_per_decoder=24,proposed_unique_labels_per_decoder=8*cfg['source_states']*3,
                repeated_contexts_not_independent_targets=True,action_times_context_not_identified_by_labels=True,
                synthetic=synthetic,cross_task_source_cv=cv,selected=chosen,registered_family=cfg['family'],
                registered_ridge=cfg['ridge'],selection_note=note,
                action_obs_diagnostics=design_diagnostics('action_obs',unique_x,unique_y,ridge=cfg['ridge']),
                development_outcomes_used=False,confirmation_used=False)
    save(FEASIBILITY,report);return report


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists() or FIT.exists():raise RuntimeError('refusing repeat/overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    started=time.perf_counter();meter=Meter(cfg);parent,seq_stage=visited.prior.parent_evidence()
    p=dict(complete=False,label='incomplete',source_cells=[],cells=[],counts=meter.counts,
           implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_dirty=False,
           config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),parents=cfg['parents'])
    try:
        import sys,torch,gymnasium
        from nexus.tasks.spec import make_task_env
        from nexus.tasks.pendulum_family import pendulum_context_train,pendulum_context_development
        from nexus.world.control_replication import load_replication_config,_confirmation_artifact
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        from nexus.world.receding_horizon import true_state
        from nexus.world.long_continuation_execution import restore_at_phase
        p['dependencies']=dict(python=sys.version,numpy=np.__version__,torch=torch.__version__,gymnasium=gymnasium.__version__)
        p['input_verification']=verify_inputs();p['checkpoint_before']=p['input_verification']['checkpoints']
        rep=load_replication_config();confirmation=_confirmation_artifact(rep)
        source_specs=list(pendulum_context_train());eval_specs=list(pendulum_context_development())
        for t,spec in enumerate(source_specs):
            for k in range(cfg['source_states']):
                env=make_task_env(spec);obs,_=env.reset(seed=source_state_seed(cfg,t,k));state=true_state(env)
                if not np.array_equal(restore_at_phase(env,state,0),obs):raise ValueError('source restoration failed')
                env.close()
                for d in cfg['decoders']:
                    models=visited.prior.load_models(d,t,rep,confirmation,parent,seq_stage)
                    for model in models.values():meter.instrument_model(model)
                    before=fingerprints(models);env=make_task_env(spec);env.reset(seed=source_state_seed(cfg,t,k));meter.instrument_env(env)
                    try:
                        meter.bucket='source_labels';seeds=source_future_seeds(cfg,t,k)
                        traces=[continue_locked(env,models['zero'],state,seeds,first_action=a,phase=0) for a in range(3)]
                    finally:env.close()
                    if fingerprints(models)!=before:raise RuntimeError('source collection changed frozen models')
                    p['source_cells'].append(dict(decoder=d,task=t,state=k,task_id=spec.task_id,reset_seed=source_state_seed(cfg,t,k),
                        obs=np.asarray(obs,dtype=np.float32).tolist(),true_state=state.tolist(),
                        returns=[total(tr['rewards'],64) for tr in traces],traces=traces,before=before,after=fingerprints(models)))
                print(f'source task={t} state={k} seconds={time.perf_counter()-started:.1f}',flush=True)
        fit=dict(complete=False,config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),implementation_sha=p['implementation_sha'],
                 family=cfg['family'],additive_family=cfg['additive_family'],ridge=cfg['ridge'],readouts={})
        expected_rows=8*cfg['source_states']*3
        for d in cfg['decoders']:
            x_c,y_c=source_training_arrays(d,p['source_cells'],cfg['family'])
            x_a,y_a=source_training_arrays(d,p['source_cells'],cfg['additive_family'])
            if len(x_c)!=expected_rows or len(x_a)!=expected_rows:raise ValueError('unique source row count changed')
            cond=RidgeQ.fit(x_c,y_c,ridge=cfg['ridge']);add=RidgeQ.fit(x_a,y_a,ridge=cfg['ridge'])
            fit['readouts'][str(d)]=dict(
                conditioned=dict(state=cond.state_dict(),sha256=cond.digest(),rows=expected_rows,
                    fit_rmse=float(np.sqrt(np.mean((cond.predict(x_c)-y_c)**2))),diagnostics=design_diagnostics(cfg['family'],x_c,y_c,cfg['ridge'])),
                additive=dict(state=add.state_dict(),sha256=add.digest(),rows=expected_rows,
                    fit_rmse=float(np.sqrt(np.mean((add.predict(x_a)-y_a)**2))),diagnostics=design_diagnostics(cfg['additive_family'],x_a,y_a,cfg['ridge'])))
        fit['complete']=True;fit['wall_clock_s']=time.perf_counter()-started;save(FIT,fit)
        fit=json.loads(FIT.read_text())
        conditioned={d:RidgeQ(**fit['readouts'][str(d)]['conditioned']['state']) for d in cfg['decoders']}
        additive={d:RidgeQ(**fit['readouts'][str(d)]['additive']['state']) for d in cfg['decoders']}
        p['fit_sha256']=sha(FIT)
        for d in cfg['decoders']:
            sequence=TerminalReadout(**seq_stage['readouts'][str(d)]['state'])
            for t,spec in enumerate(eval_specs):
                models=visited.prior.load_models(d,t+8,rep,confirmation,parent,seq_stage)
                for model in models.values():meter.instrument_model(model)
                for v in range(2):
                    before=fingerprints(models);env=make_task_env(spec);env.reset(seed=reset_seed(cfg,d,t));meter.instrument_env(env)
                    try:
                        visitor=str(visitor_student(d,t)) if v==0 else 'zero';meter.bucket='collection'
                        live=visited.collect(env,models[visitor],collection_seeds(cfg,d,t))
                        state=true_state(env);obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32)
                        if not np.array_equal(restore_at_phase(env,state,50),obs):raise ValueError('exact restoration failed')
                        seq=candidate_sequences(candidate_seed(cfg,d,t,v))
                        scores={name:score_conditions(model,obs,seq,sequence) for name,model in models.items()}
                        meter.bucket='first_common';seeds=future_seeds(cfg,d,t,v)
                        first=[continue_locked(env,models['zero'],state,seeds,first_action=a,phase=50) for a in range(3)]
                    finally:env.close()
                    after=fingerprints(models)
                    if before!=after:raise RuntimeError('frozen model/context drift')
                    metrics=row_metrics(scores,seq,[total(tr['rewards'],64) for tr in first],conditioned[d],additive[d],obs,cfg['family'],cfg['additive_family'])
                    p['cells'].append(dict(decoder=d,task=t,state=v,visitor='student' if v==0 else 'zero',visitor_model=visitor,
                        reset_seed=reset_seed(cfg,d,t),collection=live,live_replay_matched=True,true_state=state.tolist(),
                        obs=obs.tolist(),restore_exact=True,sequences=seq.tolist(),first_traces=first,scores=scores,
                        before=before,after=after,sequence_readout_sha256=sequence.digest(),
                        conditioned_sha256=conditioned[d].digest(),additive_sha256=additive[d].digest(),metrics=metrics))
                print(f'eval decoder={d} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['wall_clock_s']=time.perf_counter()-started
        p.update(validate(p,cfg,parent,seq_stage,fit));meter.check();p['complete']=True
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def validate(p,cfg,parent,seq_stage,fit=None):
    if fit is None:fit=require_fit(cfg)
    if p.get('fit_sha256')!=sha(FIT):raise ValueError('source Q fit changed after evaluation boundary')
    source=checked_id_grid(p['source_cells'],('decoder','task','state'),set(itertools.product(range(10),range(8),range(cfg['source_states']))))
    for (d,t,k),row in source.items():
        _,expected=visited.prior.saved_contexts(parent,seq_stage,d,t)
        if row['before']!=expected or row['after']!=expected:raise ValueError('source frozen fingerprints changed')
        if row['reset_seed']!=source_state_seed(cfg,t,k) or len(row['traces'])!=3:raise ValueError('source seed/label grid changed')
        validate_endpoint(row['true_state'],row['obs']);seeds=source_future_seeds(cfg,t,k)
        for a,tr in enumerate(row['traces']):
            validate_trace(tr,seeds,0,a)
            if not math.isclose(row['returns'][a],total(tr['rewards'],64),abs_tol=1e-8):raise ValueError('source return accounting changed')
    expected_rows=8*cfg['source_states']*3
    for d in range(10):
        x_c,y_c=source_training_arrays(d,p['source_cells'],cfg['family'])
        x_a,y_a=source_training_arrays(d,p['source_cells'],cfg['additive_family'])
        cond=RidgeQ(**fit['readouts'][str(d)]['conditioned']['state']);add=RidgeQ(**fit['readouts'][str(d)]['additive']['state'])
        if cond.digest()!=fit['readouts'][str(d)]['conditioned']['sha256'] or add.digest()!=fit['readouts'][str(d)]['additive']['sha256']:
            raise ValueError('Q checksum mismatch')
        if RidgeQ.fit(x_c,y_c,ridge=cfg['ridge']).digest()!=cond.digest() or RidgeQ.fit(x_a,y_a,ridge=cfg['ridge']).digest()!=add.digest():
            raise ValueError('Q was not fitted from locked source labels')
        if len(x_c)!=expected_rows:raise ValueError('unique source row count changed')
    cells=checked_id_grid(p['cells'],('decoder','task','state'),set(itertools.product(range(10),range(3),range(2))))
    for (d,t,v),row in cells.items():
        _,expected=visited.prior.saved_contexts(parent,seq_stage,d,t+8)
        if row['before']!=expected or row['after']!=expected:raise ValueError('eval frozen fingerprints changed')
        if row['visitor']!=('student' if v==0 else 'zero') or row['visitor_model']!=(str(visitor_student(d,t)) if v==0 else 'zero') or row['reset_seed']!=reset_seed(cfg,d,t):
            raise ValueError('visitor assignment changed')
        live=row['collection']
        if len(live)!=50 or row['live_replay_matched'] is not True:raise ValueError('missing live trajectory/replay')
        previous=None
        for step_i,r in enumerate(live):
            validate_endpoint(r['true_state'],r['obs'])
            if previous is not None and r['obs']!=previous:raise ValueError('discontinuous live trajectory')
            previous=r['next_obs']
            if r['step']!=step_i or r['seed']!=collection_seeds(cfg,d,t)[step_i]:raise ValueError('live seed mismatch')
        validate_endpoint(row['true_state'],row['obs'])
        if row['obs']!=previous or row['restore_exact'] is not True:raise ValueError('visited state not collection endpoint')
        seq=candidate_sequences(candidate_seed(cfg,d,t,v))
        if not np.array_equal(row['sequences'],seq) or len(row['first_traces'])!=3:raise ValueError('candidate/first-action grid mismatch')
        seeds=future_seeds(cfg,d,t,v)
        for a,tr in enumerate(row['first_traces']):validate_trace(tr,seeds,50,a)
        sequence=TerminalReadout(**seq_stage['readouts'][str(d)]['state'])
        cond=RidgeQ(**fit['readouts'][str(d)]['conditioned']['state']);add=RidgeQ(**fit['readouts'][str(d)]['additive']['state'])
        if row['sequence_readout_sha256']!=sequence.digest() or row['conditioned_sha256']!=cond.digest() or row['additive_sha256']!=add.digest():
            raise ValueError('readout identity changed')
        rebuilt=row_metrics(row['scores'],seq,[total(tr['rewards'],64) for tr in row['first_traces']],cond,add,row['obs'],cfg['family'],cfg['additive_family'])
        if rebuilt!=row['metrics']:raise ValueError('raw first-action metrics mismatch')
    if p['counts']!=budget(cfg) or p['config_sha256']!=sha(CONFIG) or p['protocol_sha256']!=sha(PROTOCOL) or p['parents']!=cfg['parents'] or p['source_dirty'] is not False:
        raise ValueError('accounting/provenance mismatch')
    for key in ('checkpoint_before','checkpoint_after'):
        if p[key]!=dict(verified=120,missing=0,mismatched=0):raise ValueError('missing binary audit')
    if p.get('input_verification')!=dict(checkpoints=dict(verified=120,missing=0,mismatched=0),model_context_groups=30,sequence_readouts=10,new_environment_steps=0):
        raise ValueError('missing before-collection verification')
    for key,length in (('implementation_sha',40),('allocation_sha256',64),('fit_sha256',64)):
        digest=p.get(key)
        if not isinstance(digest,str) or len(digest)!=length or any(c not in '0123456789abcdef' for c in digest):raise ValueError('missing execution/fit provenance')
    if not 0<p['wall_clock_s']<=cfg['time_cap_s']:raise ValueError('time exceeded')
    result=summarize(p['cells'],cfg)
    if classify_primary(result['groups']['pooled']['gain_vs_h16']['interval']['mean'],result['groups']['pooled']['gain_vs_h16']['interval']['lo'],result['groups']['pooled']['gain_vs_h16']['interval']['hi'],10,cfg['practical_margin'],True)!=result['label']:
        raise ValueError('primary label rule drift')
    return result


def audit():
    cfg=load_config();p=json.loads(OUTPUT.read_text());parent,stage=visited.prior.parent_evidence();fit=require_fit(cfg)
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid action-conditioned evaluation')
    rebuilt=validate(p,cfg,parent,stage,fit)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),fit_sha256=sha(FIT),groups=p['groups'])
