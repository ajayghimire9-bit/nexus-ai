"""Explicitly approved source fitting followed by locked development evaluation."""
from __future__ import annotations
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import torch

from nexus.cl.serialize import json_sanitize
from nexus.tasks.spec import make_task_env
from nexus.tasks.pendulum_family import pendulum_context_train,pendulum_context_development
from nexus.world.terminal_value import (CONFIG,PROTOCOL,OUTPUT,FIT,NAMES,load_config,budget,assert_seeds,
    continuation_seeds,support_hash,TerminalReadout,predicted_endpoints,value_inputs,score_conditions,row_metrics,summarize,polynomial_features)
from nexus.world.planning_value import sha,finite_array
from nexus.world.long_continuation_execution import ExecutionMeter,frozen_hash,context_hash
from nexus.world.long_continuation import continuation_trace
from nexus.world.receding_horizon import _models_for_task,rollout_actions,true_state,restore_state
from nexus.world.prediction_control_gap import candidate_sequences


def save(path,payload):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(json_sanitize(payload),separators=(',',':'),allow_nan=False)+'\n');tmp.replace(path)


class TerminalMeter(ExecutionMeter):
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='source_prefix'
    def check(self):
        if time.perf_counter()>=self.deadline: raise TimeoutError('600-second terminal-value cap reached')


def fingerprints(models):
    return {str(k):[frozen_hash(m),context_hash(m)] for k,m in models.items()}


def approved_config(approved_config_sha256):
    cfg=load_config()
    if approved_config_sha256 is None or approved_config_sha256!=sha(CONFIG):
        raise PermissionError('explicit approval of this exact terminal-value budget/configuration required')
    assert_seeds(cfg);budget(cfg)
    return cfg


def checked_id_grid(rows,fields,expected):
    seen={}
    for row in rows:
        key=tuple(row[k] for k in fields)
        if any(type(x) is not int for x in key) or key not in expected or key in seen: raise ValueError('invalid/duplicate planned cell')
        seen[key]=row
    if set(seen)!=expected: raise ValueError('incomplete planned grid')
    return seen


def source_training_arrays(decoder,cells,cfg):
    selected=[r for r in cells if r['decoder']==decoder]
    rows=checked_id_grid(selected,('decoder','task'),{(decoder,t) for t in range(8)})
    features=[];labels=[]
    for t in range(8):
        row=rows[(decoder,t)]
        if row.get('role')!='source' or row.get('task_id')!=cfg['train_task_ids'][t]:
            raise ValueError('only registered source tasks can fit the readout')
        if set(row['inputs'])!=set(NAMES) or len(row['traces'])!=4:raise ValueError('missing source condition/target')
        targets=[float(sum(finite_array(tr['rewards'],(48,)))) for tr in row['traces']]
        for name in NAMES:
            features.extend(finite_array(row['inputs'][name],(4,11)).tolist());labels.extend(targets)
    return np.array(features),np.array(labels)


def validate_fit(stage,cfg):
    if stage.get('complete') is not True or stage['config_sha256']!=sha(CONFIG): raise ValueError('missing/stale source-fitting stage')
    expected=set(itertools.product(cfg['decoders'],range(8)))
    rows=checked_id_grid(stage['source_cells'],('decoder','task'),expected)
    if set(stage['readouts'])!={str(d) for d in cfg['decoders']}: raise ValueError('missing readout seed')
    for row in rows.values():
        if set(row['inputs'])!=set(NAMES) or len(row['traces'])!=4: raise ValueError('missing source context/target')
        for features in row['inputs'].values(): finite_array(features,(4,11))
        for trace in row['traces']: finite_array(trace['rewards'],(48,))
    for name,record in stage['readouts'].items():
        model=TerminalReadout(**record['state'])
        if model.digest()!=record['sha256'] or record['rows']!=192: raise ValueError('readout checksum/row mismatch')
        finite_array([record['fit_rmse']],(1,))
        features,targets=source_training_arrays(int(name),stage['source_cells'],cfg)
        phi=polynomial_features(features);mean=phi.mean(axis=0);scale=phi.std(axis=0);scale=np.where(scale<1e-8,1.,scale)
        if not np.array_equal(mean,model.mean) or not np.array_equal(scale,model.scale):raise ValueError('normalization was not fitted on source rows')
        x=np.column_stack([np.ones(len(phi)),(phi-mean)/scale]);penalty=model.weights.copy();penalty[0]=0
        residual=x.T@(x@model.weights-targets)/len(x)+penalty
        if not np.allclose(residual,0,atol=1e-7,rtol=0):raise ValueError('readout does not solve the locked source objective')
        rmse=float(np.sqrt(np.mean((model.predict(features)-targets)**2)))
        if not math.isclose(record['fit_rmse'],rmse,abs_tol=1e-8):raise ValueError('source error mismatch')
    return rows


def require_fit_stage(cfg):
    if not FIT.is_file(): raise RuntimeError('development collection blocked until saved source fitting is complete')
    stage=json.loads(FIT.read_text());validate_fit(stage,cfg)
    return stage


def validate_capture(p,cfg,stage):
    source_rows=validate_fit(stage,cfg)
    if p['fit_sha256']!=sha(FIT): raise ValueError('source fitting changed after evaluation boundary')
    prefixes=checked_id_grid(p['prefixes'],('task',),{(t,) for t in range(8)})
    for (t,),row in prefixes.items():
        expected=candidate_sequences(cfg['train_candidate_base']+t)[cfg['train_candidate_indices']]
        if not np.array_equal(row['sequences'],expected) or len(row['rollouts'])!=4: raise ValueError('source candidate drift')
        finite_array(row['obs'],(3,));finite_array(row['state'],(2,))
        for tr in row['rollouts']: finite_array(tr['rewards'],(16,));finite_array(tr['endpoint'],(2,))
    if len(p['supports'])!=11: raise ValueError('missing support histories')
    supports={}
    for row in p['supports']:
        key=(row['role'],row['task'])
        if key in supports or type(row['task']) is not int or row['rows']!=128 or not isinstance(row['sha256'],str) or len(row['sha256'])!=64 or any(c not in '0123456789abcdef' for c in row['sha256']):
            raise ValueError('invalid support provenance')
        supports[key]=row
    if set(supports)!={*itertools.product(('source',),range(8)),*itertools.product(('evaluation',),range(3))}: raise ValueError('invalid support grid')
    checks={}
    for row in p['frozen_checks']:
        key=(row['role'],row['decoder'],row['task'])
        if any(type(row[k]) is not int for k in ('decoder','task')) or key in checks or set(row['before'])!=set(NAMES) or row['before']!=row['after']: raise ValueError('changed/missing frozen model/context')
        checks[key]=row
    if set(checks)!={*itertools.product(('source',),cfg['decoders'],range(8)),*itertools.product(('evaluation',),cfg['decoders'],range(3))}: raise ValueError('incomplete frozen checks')
    rows=checked_id_grid(p['cells'],('decoder','task','state'),set(itertools.product(cfg['decoders'],range(3),range(2))))
    def validate_trace(tr,seeds,phase,forced=None):
        n=len(seeds);finite_array(tr['rewards'],(n,))
        if len(tr['actions'])!=n or len(tr['decisions'])!=n: raise ValueError('truncated trace')
        for k,(a,dec) in enumerate(zip(tr['actions'],tr['decisions'])):
            if type(a) is not int or a not in (0,1,2) or dec['seed']!=seeds[k] or dec['original_step']!=phase+k or dec['terminated'] is not False or dec['truncated'] is not False: raise ValueError('reward/action/clock/RNG mismatch')
            idx=dec['selected_index']
            if k==0 and forced is not None:
                if a!=forced or idx is not None: raise ValueError('forced first action mismatch')
            else:
                if type(idx) is not int or not 0<=idx<16 or a!=int(candidate_sequences(seeds[k])[idx,0]): raise ValueError('candidate RNG/action mismatch')
                finite_array([dec['predicted_score']],(1,))
    for (d,t),r in source_rows.items():
        for tr in r['traces']:validate_trace(tr,continuation_seeds(cfg,'source',t),16)
    for (d,t,j),row in rows.items():
        seq=candidate_sequences(cfg['eval_candidate_base']+10*t+j)
        if not np.array_equal(seq,row['sequences']) or row['reset_seed']!=cfg['eval_state_base']+10*t+j or not row['restore_exact']:
            raise ValueError('unpaired development reset/candidates')
        finite_array(row['obs'],(3,));state=finite_array(row['true_state'],(2,))
        if not np.allclose(row['obs'],[np.cos(state[0]),np.sin(state[0]),state[1]],atol=1e-6):raise ValueError('state/observation mismatch')
        if len(row['traces'])!=3 or set(row['scores'])!=set(NAMES): raise ValueError('missing counterfactual or context')
        returns=[];readout=TerminalReadout(**stage['readouts'][str(d)]['state'])
        for action,tr in enumerate(row['traces']):
            validate_trace(tr,continuation_seeds(cfg,'evaluation',t,j),0,action);returns.append(float(sum(tr['rewards'])))
        for name,scored in row['scores'].items():
            base=finite_array(scored['base'],(16,));corrected=finite_array(scored['corrected'],(16,));alive=finite_array(scored['survival'],(16,))
            inputs=finite_array(scored['inputs'],(16,11));end=finite_array(scored['endpoint'],(16,3));values=finite_array(scored['terminal'],(16,))
            if not np.array_equal(inputs[:,:3],end) or not np.all(inputs[:,3:]==inputs[0,3:]) or np.any((alive<0)|(alive>1)):
                raise ValueError('endpoint/context/survival mismatch')
            ctx=hashlib.sha256(np.asarray(inputs[0,3:],dtype=np.float32).tobytes()).hexdigest()
            if ctx!=checks[('evaluation',d,t)]['before'][name][1]:raise ValueError('incorrect installed context')
            if not np.allclose(values,readout.predict(inputs),atol=1e-9,rtol=0) or not np.allclose(corrected,base+alive*values,atol=1e-9,rtol=0): raise ValueError('terminal score changed')
        rebuilt=row_metrics(row['scores'],returns,seq)
        if set(row['metrics'])!=set(rebuilt) or any(not math.isclose(row['metrics'][k],v,abs_tol=1e-8) for k,v in rebuilt.items()): raise ValueError('raw/summary mismatch')
    if p['counts']!=budget(cfg) or type(p['wall_clock_s']) not in (int,float) or not math.isfinite(p['wall_clock_s']) or not 0<=p['wall_clock_s']<=cfg['time_cap_s']: raise ValueError('resource/timeout failure')
    if any(p.get(k)!=dict(verified=120,missing=0,mismatched=0) for k in ('checkpoint_before','checkpoint_after')): raise ValueError('checkpoint audit missing')
    return summarize(p['cells'],cfg)


def collect_support(spec,role,t,cfg,meter):
    from nexus.world.control_replication import _collect_named
    from nexus.world.latent_generalization import load_generalization_config
    tag='train' if role=='source' else 'eval'
    meter.check()
    ds=_collect_named(spec,128,cfg[tag+'_support_env_base']+10*t,cfg[tag+'_support_action_base']+t,set(load_generalization_config()['forbidden_task_ids']))
    if len(ds)!=128:raise ValueError('short support')
    meter.counts['source_support' if role=='source' else 'eval_support']+=len(ds)
    return ds,dict(role=role,task=t,rows=len(ds),sha256=support_hash(ds))


def execute(approved_config_sha256=None):
    cfg=approved_config(approved_config_sha256)
    if OUTPUT.exists() or FIT.exists():raise RuntimeError('refusing repeat/overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean implementation first')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    started=time.perf_counter();meter=TerminalMeter(cfg)
    p=dict(complete=False,label='incomplete',source_dirty=False,implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),parent_sha256=cfg['parent_capture_sha256'],manifest_sha256=cfg['manifest_sha256'],
        prefixes=[],supports=[],source_cells=[],cells=[],frozen_checks=[],counts=meter.counts)
    try:
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        from nexus.world.prediction_control_gap import verify_provenance,load_prediction_config
        from nexus.world.control_replication import load_replication_config,_confirmation_artifact
        import gymnasium
        p['dependencies']=dict(python=sys.version,numpy=np.__version__,torch=torch.__version__,gymnasium=gymnasium.__version__)
        p['checkpoint_before']=verify_checkpoint_integrity();prov=verify_provenance(load_prediction_config());p['provenance']=prov
        rep=load_replication_config();confirmation=_confirmation_artifact(rep);digests={r['seed']:r['decoder_digest'] for r in prov['decoder_fingerprints']}
        source_support=[]
        for t,spec in enumerate(pendulum_context_train()):
            ds,metadata=collect_support(spec,'source',t,cfg,meter);source_support.append(ds);p['supports'].append(metadata)
            env=make_task_env(spec);obs,_=env.reset(seed=cfg['train_state_base']+t);meter.instrument_env(env);meter.bucket='source_prefix'
            try:
                state=true_state(env);seq=candidate_sequences(cfg['train_candidate_base']+t)[cfg['train_candidate_indices']];rolls=[]
                for actions in seq:
                    trace=rollout_actions(env,state,actions);rolls.append(dict(rewards=trace['rewards'].tolist(),endpoint=true_state(env).tolist()))
                p['prefixes'].append(dict(task=t,obs=obs.tolist(),state=state.tolist(),sequences=seq.tolist(),rollouts=rolls))
            finally:env.close()
        readouts={}
        for d in cfg['decoders']:
            for t,spec in enumerate(pendulum_context_train()):
                models={str(k):m for k,m in _models_for_task(d,rep,dict(n_student_seeds=5,student_kind='broad',support_budget=128),confirmation,source_support[t],digests[d]).items()}
                before=fingerprints(models)
                for m in models.values():meter.instrument_model(m)
                prefix=p['prefixes'][t];seq=np.array(prefix['sequences'],dtype=np.int64)
                inputs={name:value_inputs(predicted_endpoints(m,prefix['obs'],seq)[0],m).tolist() for name,m in models.items()}
                env=make_task_env(spec);env.reset(seed=cfg['train_state_base']+t);meter.instrument_env(env);meter.bucket='source_tail'
                try:
                    traces=[continuation_trace(env,models['zero'],r['endpoint'],continuation_seeds(cfg,'source',t),horizon=48,original_phase=16) for r in prefix['rollouts']]
                finally:env.close()
                p['source_cells'].append(dict(role='source',task_id=spec.task_id,decoder=d,task=t,inputs=inputs,traces=traces))
                after=fingerprints(models)
                if before!=after:raise RuntimeError('source network/context changed')
                p['frozen_checks'].append(dict(role='source',decoder=d,task=t,before=before,after=after))
            features,labels=source_training_arrays(d,p['source_cells'],cfg)
            readout=TerminalReadout.fit(features,labels,ridge=cfg['ridge'])
            readouts[str(d)]=dict(state=readout.state_dict(),sha256=readout.digest(),rows=len(features),fit_rmse=float(np.sqrt(np.mean((readout.predict(features)-labels)**2))))
            p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p)
            print(f'terminal source decoder={d} seconds={p["wall_clock_s"]:.1f}',flush=True)
        stage=dict(complete=True,config_sha256=sha(CONFIG),implementation_sha=p['implementation_sha'],readouts=readouts,source_cells=p['source_cells'],supports=p['supports'])
        validate_fit(stage,cfg);save(FIT,stage)
        stage=require_fit_stage(cfg);p['fit_sha256']=sha(FIT)
        # No development support or query environment has been collected before this boundary.
        eval_support=[]
        for t,spec in enumerate(pendulum_context_development()):
            ds,metadata=collect_support(spec,'evaluation',t,cfg,meter);eval_support.append(ds);p['supports'].append(metadata)
        for d in cfg['decoders']:
            readout=TerminalReadout(**stage['readouts'][str(d)]['state']);readout_hash=readout.digest()
            for t,spec in enumerate(pendulum_context_development()):
                models={str(k):m for k,m in _models_for_task(d,rep,dict(n_student_seeds=5,student_kind='broad',support_budget=128),confirmation,eval_support[t],digests[d]).items()}
                before=fingerprints(models)
                for m in models.values():meter.instrument_model(m)
                env=make_task_env(spec);env.reset(seed=cfg['eval_state_base']+10*t);meter.instrument_env(env);meter.bucket='eval_common'
                try:
                    for j in range(2):
                        reset_seed=cfg['eval_state_base']+10*t+j;obs,_=env.reset(seed=reset_seed);state=true_state(env)
                        seq=candidate_sequences(cfg['eval_candidate_base']+10*t+j)
                        scores={name:score_conditions(m,obs,seq,readout) for name,m in models.items()}
                        if not np.array_equal(restore_state(env,state),obs):raise RuntimeError('restoration failed')
                        traces=[continuation_trace(env,models['zero'],state,continuation_seeds(cfg,'evaluation',t,j),first_action=action,horizon=64) for action in range(3)]
                        metrics=row_metrics(scores,[sum(tr['rewards']) for tr in traces],seq)
                        p['cells'].append(dict(decoder=d,task=t,state=j,reset_seed=reset_seed,true_state=state.tolist(),obs=obs.tolist(),restore_exact=True,sequences=seq.tolist(),scores=scores,traces=traces,metrics=metrics))
                finally:env.close()
                after=fingerprints(models)
                if before!=after or readout.digest()!=readout_hash:raise RuntimeError('evaluation updated model/context/readout')
                p['frozen_checks'].append(dict(role='evaluation',decoder=d,task=t,before=before,after=after))
            p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p)
            print(f'terminal development decoder={d} seconds={p["wall_clock_s"]:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['wall_clock_s']=time.perf_counter()-started
        p.update(validate_capture(p,cfg,stage));meter.check();p['complete']=True
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p)
    return p
