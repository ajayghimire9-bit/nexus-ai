"""Capacity-matched first-action Q using sequence-value polynomial features.

World models, encoders and the frozen 78-coefficient V stay unchanged.
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
from nexus.world import visited_commitment as visited
from nexus.world import source_scalar_calibration as scalar
from nexus.world.planning_value import sha, finite_array
from nexus.world.long_continuation import paired_interval
from nexus.world.terminal_value import NAMES, TerminalReadout, polynomial_features, score_conditions
from nexus.world.terminal_value_execution import checked_id_grid, fingerprints, save
from nexus.world.commitment_value import continue_locked, total, validate_endpoint, validate_trace
from nexus.world.prediction_control_gap import candidate_sequences

CONFIG=Path('configs/capacity_matched_q.yaml')
PROTOCOL=Path('docs/NEXUS_CAPACITY_MATCHED_Q_PROTOCOL.md')
ALLOCATION=Path('configs/capacity_matched_q_allocation.json')
FIT=Path('artifacts/capacity_matched_q_fit.json')
OUTPUT=Path('artifacts/capacity_matched_q.json')
FEASIBILITY=Path('artifacts/capacity_matched_q_feasibility.json')
USAGE=Path('artifacts/research_session_first_action_value_usage.json')
FIELDS=linear_q.FIELDS


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),source_tasks=8,eval_tasks=3,visitors=2,phase=50,
                horizon=16,n_candidates=16,total_steps=64,ridge=1.0,n_poly=77,n_action=3,n_features=80,n_weights=81,
                practical_margin=1.0,time_cap_s=150,env_cap=29880,model_cap=7741440,
                source_state_base=5000000,source_future_base=5010000,reset_base=5100000,
                collection_base=5110000,candidate_base=5300000,future_base=5400000)
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked capacity-matched design/budget changed')
    from nexus.tasks.pendulum_family import pendulum_context_train,pendulum_context_development,pendulum_physics_key
    if cfg['source_task_ids']!=[s.task_id for s in pendulum_context_train()]:raise ValueError('source physics changed')
    if cfg['eval_task_ids']!=[s.task_id for s in pendulum_context_development()]:raise ValueError('development physics changed')
    if cfg['source_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_train()]:raise ValueError('source physics values changed')
    if cfg['eval_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_development()]:raise ValueError('eval physics values changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg);check_seeds(cfg)
    return cfg


def source_state_seed(cfg,t):return cfg['source_state_base']+t
def source_future_seeds(cfg,t):return list(range(cfg['source_future_base']+64*t,cfg['source_future_base']+64*t+64))
def reset_seed(cfg,d,t):return cfg['reset_base']+100*d+t
def collection_seeds(cfg,d,t):return list(range(cfg['collection_base']+10000*d+100*t,cfg['collection_base']+10000*d+100*t+50))
def candidate_seed(cfg,d,t,v):return cfg['candidate_base']+100*d+10*t+v
def future_seeds(cfg,d,t,v):return list(range(cfg['future_base']+10000*d+1000*t+100*v,cfg['future_base']+10000*d+1000*t+100*v+64))
def visitor_student(d,t):return (d+t)%5


def seed_groups(cfg):
    return [
        {source_state_seed(cfg,t) for t in range(8)},
        {s for t in range(8) for s in source_future_seeds(cfg,t)},
        {reset_seed(cfg,d,t) for d,t in itertools.product(range(10),range(3))},
        {s for d,t in itertools.product(range(10),range(3)) for s in collection_seeds(cfg,d,t)},
        {candidate_seed(cfg,d,t,v) for d,t,v in itertools.product(range(10),range(3),range(2))},
        {s for d,t,v in itertools.product(range(10),range(3),range(2)) for s in future_seeds(cfg,d,t,v)},
    ]


def check_seeds(cfg):
    visited.check_seeds(visited.load_config());scalar.load_config();linear_q.check_seeds(linear_q.load_config())
    blocked=set().union(*scalar.seed_sets(visited.load_config()),*scalar.seed_sets(scalar.load_config()),*seed_groups(linear_q.load_config()))
    groups=seed_groups(cfg)
    if [len(g) for g in groups]!=[8,512,30,1500,60,3840]:raise ValueError('duplicate registered seeds')
    for group in groups:
        if group & blocked or min(group)<5000000:raise ValueError('closed or overlapping seeds')
        blocked.update(group)


def budget(cfg):
    counts=dict(source_labels=15360,collection=3000,first_common=11520,model_states=7741440)
    if sum(v for k,v in counts.items() if k!='model_states')!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:
        raise ValueError('capacity-matched resource allocation mismatch')
    return counts


def _vector(value,n):
    arr=np.asarray(value,dtype=np.float64).reshape(-1)
    if arr.shape!=(n,) or not np.isfinite(arr).all():raise ValueError('finite observation/context vector required')
    return arr


def q_features(obs,z,actions):
    """77 sequence-value polynomial coordinates plus three action indicators."""
    obs=_vector(obs,3);z=_vector(z,8);act=np.asarray(actions,dtype=np.int64).reshape(-1)
    if act.size==0 or np.any((act<0)|(act>2)):raise ValueError('discrete first actions required')
    obs_z=np.concatenate([np.repeat(obs.reshape(1,3),len(act),axis=0),np.repeat(z.reshape(1,8),len(act),axis=0)],axis=1)
    poly=polynomial_features(obs_z)
    if poly.shape!=(len(act),77):raise ValueError('sequence-value polynomial rank changed')
    return np.concatenate([poly,np.eye(3,dtype=np.float64)[act]],axis=1)


class PolynomialActionValueReadout:
    """81-coefficient ridge Q: 77 V-polynomial coordinates, 3 action dummies, intercept."""
    def __init__(self,mean,scale,weights):
        self.mean=finite_array(list(mean),(80,));self.scale=finite_array(list(scale),(80,));self.weights=finite_array(list(weights),(81,))
        if np.any(self.scale<=0):raise ValueError('invalid Q feature scale')
    @classmethod
    def fit(cls,inputs,targets,*,ridge=1.0):
        if ridge!=1.0:raise ValueError('locked Q regularization changed')
        x=np.asarray(inputs,dtype=np.float64);y=np.asarray(targets,dtype=np.float64)
        if x.ndim!=2 or x.shape[1]!=80 or y.shape!=(len(x),) or not np.isfinite(x).all() or not np.isfinite(y).all() or len(x)==0:
            raise ValueError('invalid Q source arrays')
        mean=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale<1e-8,1.,scale)
        phi=np.column_stack([np.ones(len(x)),(x-mean)/scale]);penalty=np.eye(81)*ridge;penalty[0,0]=0
        weights=np.linalg.solve(phi.T@phi/len(x)+penalty,phi.T@y/len(x))
        return cls(mean.tolist(),scale.tolist(),weights.tolist())
    def predict(self,inputs):
        x=np.asarray(inputs,dtype=np.float64)
        if x.ndim!=2 or x.shape[1]!=80:raise ValueError('Q expected eighty features')
        out=np.column_stack([np.ones(len(x)),(x-self.mean)/self.scale])@self.weights
        if not np.isfinite(out).all():raise ValueError('nonfinite action value')
        return out
    def state_dict(self):
        return dict(mean=self.mean.tolist(),scale=self.scale.tolist(),weights=self.weights.tolist())
    def digest(self):
        return hashlib.sha256(json.dumps(self.state_dict(),sort_keys=True,allow_nan=False).encode()).hexdigest()


def design_diagnostics(features,targets,ridge=1.0):
    x=np.asarray(features,dtype=np.float64);y=np.asarray(targets,dtype=np.float64)
    if x.ndim!=2 or x.shape[1]!=80 or y.shape!=(len(x),):raise ValueError('diagnostic arrays must be 80-feature Q rows')
    if len(x)!=144:raise ValueError('source Q rows are not 144')
    y_block=y.reshape(8,6,3)
    if not np.allclose(y_block,y_block[:,:1,:],rtol=0,atol=1e-8):raise ValueError('repeated context rows are not identical labels')
    mean=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale<1e-8,1.,scale)
    phi=np.column_stack([np.ones(len(x)),(x-mean)/scale]);penalty=np.eye(81)*ridge;penalty[0,0]=0
    gram=phi.T@phi/len(x)+penalty
    dummy_sum=x[:,77:].sum(axis=1)
    dummy=PolynomialActionValueReadout(mean.tolist(),scale.tolist(),np.concatenate([[0.0],np.ones(80)]).tolist())
    action_offsets=[]
    for obs,z in ((np.zeros(3),np.zeros(8)),(np.array([0.2,-0.1,0.3]),np.linspace(-0.4,0.4,8))):
        q=dummy.predict(q_features(obs,z,[0,1,2]))
        action_offsets.append((q-q[0]).tolist())
    return dict(n_rows=144,n_unique_labels=24,n_unique_observations=8,n_unique_obs_context=48,n_features=80,n_weights=81,ridge=ridge,
                feature_rank=int(np.linalg.matrix_rank(x,tol=1e-8)),augmented_rank=int(np.linalg.matrix_rank(phi,tol=1e-8)),
                gram_condition=float(np.linalg.cond(gram)),action_dummies_sum_to_one=bool(np.allclose(dummy_sum,1.0)),
                unregularized_intercept_collinear_with_actions=True,state_independent_action_ranking=True,
                additive_action_offsets_independent_of_state=bool(np.allclose(action_offsets[0],action_offsets[1])),
                repeated_context_rows_not_independent=True)


def score_aligned(readout,obs,z,sequences):
    seq=np.asarray(sequences,dtype=np.int64)
    if seq.shape!=(16,16):raise ValueError('aligned scoring requires the locked candidate set')
    q=readout.predict(q_features(obs,z,seq[:,0]))
    index=int(np.argmax(q));return dict(values=q.tolist(),selected=index,first_action=int(seq[index,0]))


def choose_first(scores,sequences):
    return linear_q.choose_first(scores,sequences)


def row_metrics(scores,sequences,first_returns,readouts_q,obs):
    first=finite_array(first_returns,(3,));seq=np.asarray(sequences,dtype=np.int64);out={}
    if set(scores)!=set(NAMES) or set(readouts_q)!=set(NAMES):raise ValueError('missing scoring context')
    for name,s in scores.items():
        h16_i,h16_a=choose_first(s['base'],seq);seq_i,seq_a=choose_first(s['corrected'],seq)
        aligned=score_aligned(readouts_q[name],obs,finite_array(s['inputs'],(16,11))[0,3:],seq)
        q_pred=readouts_q[name].predict(q_features(obs,finite_array(s['inputs'],(16,11))[0,3:],[0,1,2]))
        m=dict(h16_first=float(first[h16_a]),sequence_first=float(first[seq_a]),aligned_first=float(first[aligned['first_action']]))
        m.update(gain_vs_h16=m['aligned_first']-m['h16_first'],gain_vs_sequence=m['aligned_first']-m['sequence_first'],sequence_vs_h16=m['sequence_first']-m['h16_first'],
                 h16_regret=float(max(first))-m['h16_first'],sequence_regret=float(max(first))-m['sequence_first'],aligned_regret=float(max(first))-m['aligned_first'],
                 q_rmse=float(np.sqrt(np.mean((q_pred-first)**2))),aligned_h16_agree=float(aligned['first_action']==h16_a),aligned_sequence_agree=float(aligned['first_action']==seq_a))
        if set(m)!=set(FIELDS):raise ValueError('metric schema drift')
        finite_array([m[k] for k in FIELDS],(len(FIELDS),));out[name]=m
    return out


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task','state'),set(itertools.product(range(10),range(3),range(2))))
    for row in cells.values():
        if set(row['metrics'])!=set(NAMES):raise ValueError('missing scoring context')
        for m in row['metrics'].values():
            if set(m)!=set(FIELDS):raise ValueError('missing first-action metric')
            finite_array([m[k] for k in FIELDS],(len(FIELDS),))
    definitions=[('pooled',range(3),range(2),[str(s) for s in range(5)]),('zero_context',range(3),range(2),['zero'])]
    definitions+=[(f'task_{t}',[t],range(2),[str(s) for s in range(5)]) for t in range(3)]
    definitions+=[(name,range(3),[v],[str(s) for s in range(5)]) for v,name in enumerate(('student_visitor','zero_visitor'))]
    groups={}
    for name,tasks,visitors,students in definitions:
        groups[name]={}
        for metric in FIELDS:
            values=[statistics.mean(cells[d,t,v]['metrics'][s][metric] for t,v,s in itertools.product(tasks,visitors,students)) for d in range(10)]
            groups[name][metric]=dict(per_decoder=values,interval=paired_interval(values))
    primary=groups['pooled']['gain_vs_h16']['interval'];label='aligned_first_action_gain_not_established'
    if primary['mean']>=cfg['practical_margin'] and primary['lo']>0:label='aligned_first_action_gain'
    elif primary['hi']<0:label='aligned_first_action_harm'
    return dict(label=label,groups=groups)


def classify_primary(mean,lo,hi,n,threshold=1.0,complete=True):
    return linear_q.classify_primary(mean,lo,hi,n,threshold,complete)


def source_training_arrays(decoder,cells,context_by_task):
    selected=[r for r in cells if r['decoder']==decoder]
    rows=checked_id_grid(selected,('decoder','task'),{(decoder,t) for t in range(8)})
    features=[];labels=[]
    for t in range(8):
        row=rows[(decoder,t)]
        if len(row['returns'])!=3 or len(row['obs'])!=3:raise ValueError('source action labels missing')
        y=finite_array(row['returns'],(3,))
        for name in NAMES:
            z=_vector(context_by_task[t][name],8)
            features.extend(q_features(row['obs'],z,[0,1,2]).tolist());labels.extend(y.tolist())
    return np.asarray(features,dtype=np.float64),np.asarray(labels,dtype=np.float64)


def validate_fit(stage,cfg,source_cells,context_by_decoder):
    if stage.get('complete') is not True:raise ValueError('incomplete Q fit')
    if set(stage['readouts'])!={str(d) for d in range(10)}:raise ValueError('missing Q readout')
    checked_id_grid(source_cells,('decoder','task'),set(itertools.product(range(10),range(8))))
    for d in range(10):
        features,targets=source_training_arrays(d,source_cells,context_by_decoder[d])
        if len(features)!=144:raise ValueError('source Q rows are not 144')
        model=PolynomialActionValueReadout(**stage['readouts'][str(d)]['state'])
        if model.digest()!=stage['readouts'][str(d)]['sha256'] or stage['readouts'][str(d)]['rows']!=144:raise ValueError('Q checksum/row mismatch')
        rebuilt=PolynomialActionValueReadout.fit(features,targets,ridge=cfg['ridge'])
        if rebuilt.digest()!=model.digest():raise ValueError('Q was not fitted from locked source labels')
        rmse=float(np.sqrt(np.mean((model.predict(features)-targets)**2)))
        if not math.isclose(stage['readouts'][str(d)]['fit_rmse'],rmse,abs_tol=1e-8):raise ValueError('source Q RMSE mismatch')
        expected=design_diagnostics(features,targets,ridge=cfg['ridge'])
        saved=stage['readouts'][str(d)].get('diagnostics')
        if saved is None:raise ValueError('missing source identifiability diagnostics')
        for key in ('n_unique_labels','n_weights','state_independent_action_ranking','repeated_context_rows_not_independent'):
            if saved[key]!=expected[key]:raise ValueError('identifiability diagnostic mismatch')
        if abs(saved['gram_condition']-expected['gram_condition'])>1e-6:raise ValueError('Gram condition mismatch')
    return True


class Meter(visited.Meter):
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='source_labels'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('capacity-matched-q execution cap reached')


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),time_cap_s=150,env_cap=29880,model_cap=7741440).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('capacity-matched allocation drift')
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


def historical_source_probe(decoder=0):
    """Rank/conditioning on closed source observations only. Development cells are not used."""
    raw=json.loads(linear_q.OUTPUT.read_text())
    parent,stage=visited.prior.parent_evidence()
    source=[r for r in raw['source_cells'] if r['decoder']==decoder]
    contexts={}
    for t in range(8):
        z,_=visited.prior.saved_contexts(parent,stage,decoder,t)
        contexts[t]={name:np.asarray(value,dtype=np.float64) for name,value in z.items()}
    features,targets=source_training_arrays(decoder,source,contexts)
    return design_diagnostics(features,targets,ridge=1.0)


def feasibility():
    cfg=load_config();load_allocation()
    rng=np.random.default_rng(0)
    cells=[];context_by_task={}
    for t in range(8):
        obs=rng.normal(size=3).tolist();returns=rng.normal(size=3).tolist()
        cells.append(dict(decoder=0,task=t,obs=obs,returns=returns))
        context_by_task[t]={name:rng.normal(size=8).tolist() for name in NAMES}
    synthetic_x,synthetic_y=source_training_arrays(0,cells,context_by_task)
    synthetic=design_diagnostics(synthetic_x,synthetic_y,ridge=cfg['ridge'])
    historical=historical_source_probe(0)
    obs=np.array([0.2,-0.1,0.05]);z=np.linspace(-0.3,0.4,8)
    poly=polynomial_features(np.concatenate([obs,z]).reshape(1,11))
    q=q_features(obs,z,[0,1,2])
    if not np.allclose(q[:,:77],np.repeat(poly,3,axis=0)) or not np.array_equal(q[:,77:],np.eye(3)):
        raise ValueError('capacity-matched features drifted from sequence-value polynomial')
    dummy=PolynomialActionValueReadout.fit(synthetic_x,synthetic_y,ridge=1.0)
    ranks=[]
    for test_obs,test_z in ((obs,z),(np.zeros(3),np.zeros(8)),(np.ones(3)*0.4,np.linspace(0.1,0.2,8))):
        ranks.append(int(np.argmax(dummy.predict(q_features(test_obs,test_z,[0,1,2])))))
    report=dict(complete=True,config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                new_environment_steps=0,new_imagined_transitions=0,authorized=False,
                remaining_session_allowance_s=json.loads(USAGE.read_text())['remaining_session_allowance_s'],
                polynomial_coordinates=77,action_indicators=3,n_weights=81,ridge=1.0,
                synthetic=synthetic,historical_source_decoder0=historical,
                additive_argmax_constant_across_states=len(set(ranks))==1,
                development_outcomes_used=False,confirmation_used=False,linear_q_weights_used=False)
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
        context_table={d:{} for d in cfg['decoders']}
        for t,spec in enumerate(source_specs):
            env=make_task_env(spec);obs,_=env.reset(seed=source_state_seed(cfg,t));state=true_state(env)
            if not np.array_equal(restore_at_phase(env,state,0),obs):raise ValueError('source restoration failed')
            env.close()
            for d in cfg['decoders']:
                models=visited.prior.load_models(d,t,rep,confirmation,parent,seq_stage)
                for m in models.values():meter.instrument_model(m)
                context_table[d][t]={name:np.asarray(models[name].z.detach().cpu().numpy(),dtype=np.float64) for name in NAMES}
                before=fingerprints(models);env=make_task_env(spec);env.reset(seed=source_state_seed(cfg,t));meter.instrument_env(env)
                try:
                    meter.bucket='source_labels';seeds=source_future_seeds(cfg,t)
                    traces=[continue_locked(env,models['zero'],state,seeds,first_action=a,phase=0) for a in range(3)]
                finally:env.close()
                if fingerprints(models)!=before:raise RuntimeError('source collection changed frozen models')
                returns=[total(tr['rewards'],64) for tr in traces]
                p['source_cells'].append(dict(decoder=d,task=t,task_id=spec.task_id,reset_seed=source_state_seed(cfg,t),
                    obs=np.asarray(obs,dtype=np.float32).tolist(),true_state=state.tolist(),returns=returns,traces=traces,before=before,after=fingerprints(models)))
            print(f'source task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        readouts={};fit=dict(complete=False,config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),implementation_sha=p['implementation_sha'],readouts={},rows_per_decoder=144)
        for d in cfg['decoders']:
            features,targets=source_training_arrays(d,p['source_cells'],context_table[d])
            model=PolynomialActionValueReadout.fit(features,targets,ridge=cfg['ridge']);pred=model.predict(features)
            fit['readouts'][str(d)]=dict(state=model.state_dict(),sha256=model.digest(),rows=144,
                fit_rmse=float(np.sqrt(np.mean((pred-targets)**2))),diagnostics=design_diagnostics(features,targets,ridge=cfg['ridge']))
            readouts[d]=model
        fit['complete']=True;fit['wall_clock_s']=time.perf_counter()-started;save(FIT,fit)
        validate_fit(fit,cfg,p['source_cells'],context_table)
        fit=json.loads(FIT.read_text());readouts={d:PolynomialActionValueReadout(**fit['readouts'][str(d)]['state']) for d in cfg['decoders']}
        p['fit_sha256']=sha(FIT);p['q_readout_sha256']={str(d):readouts[d].digest() for d in cfg['decoders']}
        for d in cfg['decoders']:
            sequence=TerminalReadout(**seq_stage['readouts'][str(d)]['state'])
            for t,spec in enumerate(eval_specs):
                models=visited.prior.load_models(d,t+8,rep,confirmation,parent,seq_stage)
                for m in models.values():meter.instrument_model(m)
                for v in range(2):
                    before=fingerprints(models);env=make_task_env(spec);env.reset(seed=reset_seed(cfg,d,t));meter.instrument_env(env)
                    try:
                        visitor=str(visitor_student(d,t)) if v==0 else 'zero';meter.bucket='collection'
                        live=visited.collect(env,models[visitor],collection_seeds(cfg,d,t))
                        state=true_state(env);obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32)
                        if not np.array_equal(restore_at_phase(env,state,50),obs):raise ValueError('exact restoration failed')
                        seq=candidate_sequences(candidate_seed(cfg,d,t,v))
                        scores={name:score_conditions(m,obs,seq,sequence) for name,m in models.items()}
                        meter.bucket='first_common';seeds=future_seeds(cfg,d,t,v)
                        first=[continue_locked(env,models['zero'],state,seeds,first_action=a,phase=50) for a in range(3)]
                    finally:env.close()
                    after=fingerprints(models)
                    if before!=after:raise RuntimeError('frozen model/context drift')
                    q_models={name:readouts[d] for name in NAMES}
                    metrics=row_metrics(scores,seq,[total(tr['rewards'],64) for tr in first],q_models,obs)
                    p['cells'].append(dict(decoder=d,task=t,state=v,visitor='student' if v==0 else 'zero',visitor_model=visitor,
                        reset_seed=reset_seed(cfg,d,t),collection=live,live_replay_matched=True,true_state=state.tolist(),
                        obs=obs.tolist(),restore_exact=True,sequences=seq.tolist(),first_traces=first,scores=scores,
                        before=before,after=after,sequence_readout_sha256=sequence.digest(),q_readout_sha256=readouts[d].digest(),metrics=metrics))
                print(f'eval decoder={d} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['wall_clock_s']=time.perf_counter()-started
        p.update(validate(p,cfg,parent,seq_stage,fit));meter.check();p['complete']=True
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def validate(p,cfg,parent,seq_stage,fit=None):
    if fit is None:fit=require_fit(cfg)
    if p.get('fit_sha256')!=sha(FIT):raise ValueError('source Q fit changed after evaluation boundary')
    source=checked_id_grid(p['source_cells'],('decoder','task'),set(itertools.product(range(10),range(8))))
    for (d,t),row in source.items():
        _,expected=visited.prior.saved_contexts(parent,seq_stage,d,t)
        if row['before']!=expected or row['after']!=expected:raise ValueError('source frozen fingerprints changed')
        if row['reset_seed']!=source_state_seed(cfg,t) or len(row['traces'])!=3:raise ValueError('source seed/label grid changed')
        validate_endpoint(row['true_state'],row['obs']);seeds=source_future_seeds(cfg,t)
        for a,tr in enumerate(row['traces']):
            validate_trace(tr,seeds,0,a)
            if not math.isclose(row['returns'][a],total(tr['rewards'],64),abs_tol=1e-8):raise ValueError('source return accounting changed')
    context_table={}
    for d in range(10):
        context_table[d]={}
        for t in range(8):
            contexts,_=visited.prior.saved_contexts(parent,seq_stage,d,t)
            context_table[d][t]={name:np.asarray(z,dtype=np.float64) for name,z in contexts.items()}
    validate_fit(fit,cfg,p['source_cells'],context_table)
    cells=checked_id_grid(p['cells'],('decoder','task','state'),set(itertools.product(range(10),range(3),range(2))))
    for (d,t,v),row in cells.items():
        _,expected=visited.prior.saved_contexts(parent,seq_stage,d,t+8)
        if row['before']!=expected or row['after']!=expected:raise ValueError('eval frozen fingerprints changed')
        if row['visitor']!=('student' if v==0 else 'zero') or row['visitor_model']!=(str(visitor_student(d,t)) if v==0 else 'zero') or row['reset_seed']!=reset_seed(cfg,d,t):
            raise ValueError('visitor assignment changed')
        live=row['collection']
        if len(live)!=50 or row['live_replay_matched'] is not True:raise ValueError('missing live trajectory/replay')
        previous=None
        for k,r in enumerate(live):
            validate_endpoint(r['true_state'],r['obs'])
            if previous is not None and r['obs']!=previous:raise ValueError('discontinuous live trajectory')
            previous=r['next_obs']
            if r['step']!=k or r['seed']!=collection_seeds(cfg,d,t)[k]:raise ValueError('live seed mismatch')
        validate_endpoint(row['true_state'],row['obs'])
        if row['obs']!=previous or row['restore_exact'] is not True:raise ValueError('visited state not collection endpoint')
        seq=candidate_sequences(candidate_seed(cfg,d,t,v))
        if not np.array_equal(row['sequences'],seq) or len(row['first_traces'])!=3:raise ValueError('candidate/first-action grid mismatch')
        seeds=future_seeds(cfg,d,t,v)
        for a,tr in enumerate(row['first_traces']):validate_trace(tr,seeds,50,a)
        sequence=TerminalReadout(**seq_stage['readouts'][str(d)]['state']);q=PolynomialActionValueReadout(**fit['readouts'][str(d)]['state'])
        if row['sequence_readout_sha256']!=sequence.digest() or row['q_readout_sha256']!=q.digest():raise ValueError('readout identity changed')
        q_models={name:q for name in NAMES}
        rebuilt=row_metrics(row['scores'],seq,[total(tr['rewards'],64) for tr in row['first_traces']],q_models,row['obs'])
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
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid capacity-matched evaluation')
    rebuilt=validate(p,cfg,parent,stage,fit)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),fit_sha256=sha(FIT),groups=p['groups'])
