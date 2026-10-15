"""Held-out calibration of existing readouts; no fitting, no controller changes."""
from __future__ import annotations
import itertools
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

import numpy as np
import torch
import yaml

from nexus.world.planning_value import finite_array, sha
from nexus.world.terminal_value import (NAMES, TerminalReadout, predicted_endpoints, value_inputs,
    load_config as parent_config, seed_groups as parent_seeds)
from nexus.world.terminal_value_execution import (checked_id_grid, validate_capture,
    fingerprints, save)
from nexus.world.long_continuation_execution import ExecutionMeter
from nexus.world.long_continuation import continuation_trace, paired_interval
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.receding_horizon import rollout_actions, true_state, restore_state
from nexus.tasks.spec import make_task_env
from nexus.tasks.pendulum_family import pendulum_context_train, pendulum_context_development, pendulum_physics_key

CONFIG=Path('configs/terminal_value_calibration.yaml')
PROTOCOL=Path('docs/NEXUS_TERMINAL_VALUE_CALIBRATION_PROTOCOL.md')
OUTPUT=Path('artifacts/terminal_value_calibration.json')
APPROVAL=Path('configs/terminal_value_calibration_approval.json')
LOCK='0fea17504d5a5baea32d857947cd516ab14cef84df524d7f835594d71d7d6184'
PARENT=Path('artifacts/terminal_value.json')
FIT=Path('artifacts/terminal_value_source_fit.json')


def load_config():
    if sha(CONFIG)!=LOCK: raise ValueError('locked configuration drift')
    cfg=yaml.safe_load(CONFIG.read_text())
    specs=pendulum_context_train()+pendulum_context_development()
    expected=[dict(role='source' if i<8 else 'development',task_id=s.task_id,physics=list(pendulum_physics_key(s))) for i,s in enumerate(specs)]
    if cfg['tasks']!=expected: raise ValueError('registered task/physics drift')
    for path,digest in cfg['parents'].items():
        if sha(path)!=digest: raise ValueError('closed artifact/manifest drift')
    if LOCK not in PROTOCOL.read_text(): raise ValueError('missing protocol lock')
    return cfg


def tail_seeds(cfg,task):
    return list(range(cfg['tail_base']+64*task,cfg['tail_base']+64*task+48))


def check_seeds(cfg):
    from nexus.world.prediction_control_gap import diagnostic_seed_groups,load_prediction_config
    from nexus.world.receding_horizon import horizon_seed_groups,load_horizon_config
    from nexus.world.return_phase import phase_seed_groups,load_phase_config
    from nexus.world.late_control_gap_design import design_seed_groups
    from nexus.world.long_continuation import proposed_seeds,load_config as long_config
    from nexus.world.policy_switch import load_config as switch_config,seeds
    from nexus.world.planning_value import load_config as value_config,seed_groups as value_groups
    a,b=diagnostic_seed_groups(load_prediction_config());blocked=set()
    for group in (a,b,horizon_seed_groups(load_horizon_config()),phase_seed_groups(load_phase_config()),design_seed_groups(),proposed_seeds(long_config())):
        for values in group.values():blocked.update(values)
    prior=switch_config();blocked.update([prior['env_seed'],prior['planner_seed']])
    blocked.update(x for p in range(2) for slot in range(6) for x in seeds(prior,p,slot))
    for group in value_groups(value_config())+parent_seeds(parent_config()):blocked.update(group)
    groups=[{cfg['state_base']+t for t in range(11)}, {cfg['candidate_base']+t for t in range(11)},
            {s for t in range(11) for s in tail_seeds(cfg,t)}]
    for group in groups:
        if blocked & group:raise ValueError('closed/overlapping RNG seeds')
        blocked.update(group)


def budget(cfg):
    result=dict(prefix=11*4*16,tail=10*11*4*48,model_states=10*11*6*4*16+10*11*4*48*256)
    if result['prefix']+result['tail']!=cfg['env_cap'] or result['model_states']!=cfg['model_cap']:
        raise ValueError('budget mismatch')
    return result


def parent_evidence():
    cfg=parent_config();p=json.loads(PARENT.read_text());stage=json.loads(FIT.read_text())
    if p.get('complete') is not True: raise ValueError('incomplete parent experiment')
    validate_capture(p,cfg,stage)
    return p,stage


def saved_contexts(p,stage,d,t):
    """Exact recorded z, not newly inferred or fitted from query experience."""
    if t<8:
        row=next(r for r in stage['source_cells'] if r['decoder']==d and r['task']==t)
        inputs=row['inputs'];role='source';local=t
    else:
        local=t-8;role='evaluation'
        rows=[r for r in p['cells'] if r['decoder']==d and r['task']==local]
        inputs={name:rows[0]['scores'][name]['inputs'] for name in NAMES}
        for r in rows:
            for name in NAMES:
                if not np.array_equal(np.array(r['scores'][name]['inputs'])[:,3:],np.tile(inputs[name][0][3:],(16,1))):
                    raise ValueError('parent contexts vary within a task')
    check=next(r for r in p['frozen_checks'] if r['role']==role and r['decoder']==d and r['task']==local)
    contexts={}
    import hashlib
    for name in NAMES:
        x=finite_array(inputs[name],(4 if t<8 else 16,11));z=x[0,3:].astype(np.float32)
        if not np.all(x[:,3:]==x[0,3:]) or hashlib.sha256(z.tobytes()).hexdigest()!=check['before'][name][1]:
            raise ValueError('parent context fingerprint mismatch')
        contexts[name]=z
    return contexts,check['before']


def load_models(d,t,rep,confirmation,p,stage):
    from nexus.world.control_replication import _decoder_file,_student_rows
    from nexus.world.latent_control import _fresh_decoder,_install_encoder
    contexts,expected=saved_contexts(p,stage,d,t)
    students={str(i):r for i,r in enumerate(_student_rows(d,'broad',rep,confirmation))}
    models={}
    for name in NAMES:
        model,digest=_fresh_decoder(_decoder_file(d,rep),rep)
        if name!='zero': _install_encoder(model,students[name]['path'],rep,digest)
        model.z=torch.tensor(contexts[name],dtype=torch.float32)
        models[name]=model
    if fingerprints(models)!=expected: raise ValueError('loaded network/normalizer/context fingerprint drift')
    return models


def metrics(predictions,targets):
    y=finite_array(targets,(4,));result={}
    if set(predictions)!=set(NAMES): raise ValueError('missing context')
    for name in NAMES:
        row=predictions[name]
        if set(row)!=set(('imagined','actual','constant')):raise ValueError('missing prediction condition')
        result[name]={kind:float(np.sqrt(np.mean((finite_array(row[kind],(4,))-y)**2))) for kind in row}
    return result


def summarize(rows,cfg):
    index=checked_id_grid(rows,('decoder','task'),set(itertools.product(cfg['decoders'],range(11))))
    for r in index.values():
        rebuilt=metrics(r['predictions'],r['targets'])
        if set(r['metrics'])!=set(NAMES):raise ValueError('missing stored context metric')
        for name in NAMES:
            if set(r['metrics'][name])!={'imagined','actual','constant'}:raise ValueError('missing stored prediction metric')
            finite_array(list(r['metrics'][name].values()),(3,))
        if r['metrics']!=rebuilt:raise ValueError('metric/raw mismatch')
    summaries={}
    for role,tasks in [('source',range(8)),('development',range(8,11))]:
        vals={}
        for kind in ('imagined','actual','constant'):
            vals[kind]=[statistics.mean(index[d,t]['metrics'][str(s)][kind] for t,s in itertools.product(tasks,cfg['students'])) for d in cfg['decoders']]
        benefit=[a-b for a,b in zip(vals['constant'],vals['imagined'])]
        endpoint=[a-b for a,b in zip(vals['imagined'],vals['actual'])]
        fraction=(statistics.mean(benefit)/statistics.mean(vals['constant'])) if statistics.mean(vals['constant'])>0 else None
        by_task={}
        for t in tasks:
            per_context={name:{kind:[index[d,t]['metrics'][name][kind] for d in cfg['decoders']] for kind in ('imagined','actual','constant')} for name in NAMES}
            task_benefit=[statistics.mean(index[d,t]['metrics'][str(s)]['constant']-index[d,t]['metrics'][str(s)]['imagined'] for s in cfg['students']) for d in cfg['decoders']]
            by_task[cfg['tasks'][t]['task_id']]=dict(per_context=per_context,student_benefit=paired_interval(task_benefit))
        zero={kind:[statistics.mean(index[d,t]['metrics']['zero'][kind] for t in tasks) for d in cfg['decoders']] for kind in ('imagined','actual','constant')}
        summaries[role]=dict(per_decoder=vals,zero_context=zero,per_task=by_task,benefit=paired_interval(benefit),endpoint_difference=paired_interval(endpoint),fractional_reduction=fraction)
    dev=summaries['development']
    passed=dev['fractional_reduction'] is not None and dev['fractional_reduction']>=cfg['minimum_fraction'] and dev['benefit']['lo']>0
    return dict(label='held_out_calibration_screen_pass' if passed else 'held_out_calibration_not_established',summaries=summaries)


def validate(p,cfg,parent,stage):
    prefixes=checked_id_grid(p['prefixes'],('task',),{(t,) for t in range(11)})
    cells=checked_id_grid(p['cells'],('decoder','task'),set(itertools.product(cfg['decoders'],range(11))))
    for (t,),row in prefixes.items():
        if row['reset_seed']!=cfg['state_base']+t or not np.array_equal(row['sequences'],candidate_sequences(cfg['candidate_base']+t)[cfg['candidate_indices']]):raise ValueError('unpaired reset/candidates')
        obs=finite_array(row['obs'],(3,));state=finite_array(row['state'],(2,))
        if not np.allclose(obs,[np.cos(state[0]),np.sin(state[0]),state[1]],atol=1e-6):raise ValueError('observation/state mismatch')
        if row['restore_exact'] is not True or len(row['rollouts'])!=4: raise ValueError('missing restored prefix')
        for tr in row['rollouts']:
            finite_array(tr['rewards'],(16,));finite_array(tr['endpoint'],(2,));endpoint=finite_array(tr['endpoint_obs'],(3,))
            if not np.allclose(endpoint,[np.cos(tr['endpoint'][0]),np.sin(tr['endpoint'][0]),tr['endpoint'][1]],atol=1e-6):raise ValueError('wrong actual endpoint')
    for (d,t),row in cells.items():
        contexts,expected=saved_contexts(parent,stage,d,t)
        if row['before']!=expected or row['after']!=expected:raise ValueError('frozen fingerprint mismatch')
        readout=TerminalReadout(**stage['readouts'][str(d)]['state'])
        if row['readout_sha256']!=readout.digest():raise ValueError('readout changed')
        constant=float(np.mean([sum(tr['rewards']) for r in stage['source_cells'] if r['decoder']==d for tr in r['traces']]))
        if len(row['traces'])!=4 or set(row['inputs'])!=set(NAMES):raise ValueError('missing trace/context')
        targets=[]
        for tr in row['traces']:
            rewards=finite_array(tr['rewards'],(48,));targets.append(float(sum(rewards)))
            if len(tr['actions'])!=48 or len(tr['decisions'])!=48:raise ValueError('short trace')
            for k,(a,dec) in enumerate(zip(tr['actions'],tr['decisions'])):
                seed=tail_seeds(cfg,t)[k];idx=dec['selected_index']
                if type(a) is not int or type(idx) is not int or not 0<=idx<16 or dec['seed']!=seed or a!=int(candidate_sequences(seed)[idx,0]) or dec['original_step']!=16+k or dec['terminated'] is not False or dec['truncated'] is not False:raise ValueError('tail RNG/action/clock mismatch')
                finite_array([dec['predicted_score']],(1,))
        if not np.array_equal(finite_array(row['targets'],(4,)),targets):raise ValueError('wrong continuation label')
        for name in NAMES:
            if set(row['inputs'][name])!={'imagined','actual'}:raise ValueError('input condition mismatch')
            for kind in ('imagined','actual'):
                x=finite_array(row['inputs'][name][kind],(4,11))
                if not np.array_equal(x[:,3:],np.tile(contexts[name],(4,1))):raise ValueError('context drift')
                if kind=='actual' and not np.array_equal(x[:,:3],[tr['endpoint_obs'] for tr in prefixes[t,]['rollouts']]):raise ValueError('actual endpoint mismatch')
                if not np.array_equal(finite_array(row['predictions'][name][kind],(4,)),readout.predict(x)):raise ValueError('prediction changed')
            if not np.array_equal(finite_array(row['predictions'][name]['constant'],(4,)),[constant]*4):raise ValueError('baseline used query labels')
    for key,expected in [('config_sha256',sha(CONFIG)),('protocol_sha256',sha(PROTOCOL))]:
        if p[key]!=expected:raise ValueError('execution provenance drift')
    if p['parents']!=cfg['parents'] or p['counts']!=budget(cfg):raise ValueError('parent/count mismatch')
    if any(p[k]!=dict(verified=120,missing=0,mismatched=0) for k in ('checkpoint_before','checkpoint_after')):raise ValueError('missing checkpoint verification')
    finite_array([p['wall_clock_s']],(1,))
    if not 0<=p['wall_clock_s']<=cfg['time_cap_s']:raise ValueError('time cap exceeded')
    return summarize(p['cells'],cfg)


class CalibrationMeter(ExecutionMeter):
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='prefix'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('600-second calibration cap reached')


def prepare():
    cfg=load_config();check_seeds(cfg);parent_evidence()
    return dict(status='awaiting_budget_approval',config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),parents=cfg['parents'],
        counts=budget(cfg),new_environment_steps=0,network_updates=0,readout_fits=0,new_support_steps=0,
        estimated_minutes=[2,3],time_cap_s=cfg['time_cap_s'],source_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())


def require_approval(approved_hash,cfg):
    if approved_hash!=LOCK or not APPROVAL.is_file():raise PermissionError('new exact-config budget approval required; previous run approval is consumed')
    record=json.loads(APPROVAL.read_text())
    expected=dict(kind='human_approved_bounded_local_experiment',config_sha256=LOCK,time_cap_s=cfg['time_cap_s'],env_cap=cfg['env_cap'],model_cap=cfg['model_cap'],runs=1,further_experiments_authorized=False)
    if any(type(record.get(k)) is not type(v) or record[k]!=v for k,v in expected.items()):raise PermissionError('stale/mismatched approval')


def verify_inputs():
    cfg=load_config();parent,stage=parent_evidence()
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.control_replication import load_replication_config,_confirmation_artifact
    checks=verify_checkpoint_integrity();rep=load_replication_config();confirmation=_confirmation_artifact(rep)
    for d,t in itertools.product(cfg['decoders'],range(11)):
        load_models(d,t,rep,confirmation,parent,stage)
    return dict(checkpoints=checks,model_context_groups=110,readouts=10,new_environment_steps=0)


def execute(approved_hash=None):
    cfg=load_config();require_approval(approved_hash,cfg)
    if OUTPUT.exists():raise RuntimeError('refusing repeat/overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean implementation and approval first')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    check_seeds(cfg);parent,stage=parent_evidence()
    started=time.perf_counter();meter=CalibrationMeter(cfg)
    p=dict(complete=False,label='incomplete',implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_dirty=False,
        config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),approval_sha256=sha(APPROVAL),parents=cfg['parents'],prefixes=[],cells=[],counts=meter.counts)
    try:
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        from nexus.world.control_replication import load_replication_config,_confirmation_artifact
        import gymnasium
        p['dependencies']=dict(python=sys.version,numpy=np.__version__,torch=torch.__version__,gymnasium=gymnasium.__version__)
        p['checkpoint_before']=verify_checkpoint_integrity();rep=load_replication_config();confirmation=_confirmation_artifact(rep)
        specs=pendulum_context_train()+pendulum_context_development()
        for t,spec in enumerate(specs):
            env=make_task_env(spec)
            try:
                obs,_=env.reset(seed=cfg['state_base']+t);state=true_state(env);meter.instrument_env(env);meter.bucket='prefix'
                if not np.array_equal(restore_state(env,state),obs):raise RuntimeError('inexact restoration')
                sequences=candidate_sequences(cfg['candidate_base']+t)[cfg['candidate_indices']];rollouts=[]
                for actions in sequences:
                    trace=rollout_actions(env,state,actions)
                    rollouts.append(dict(rewards=trace['rewards'].tolist(),endpoint=true_state(env).tolist(),endpoint_obs=trace['next_obs'][-1].tolist()))
                p['prefixes'].append(dict(task=t,reset_seed=cfg['state_base']+t,obs=obs.tolist(),state=state.tolist(),restore_exact=True,sequences=sequences.tolist(),rollouts=rollouts))
            finally:env.close()
        for d in cfg['decoders']:
            readout=TerminalReadout(**stage['readouts'][str(d)]['state']);readout_hash=readout.digest()
            constant=float(np.mean([sum(tr['rewards']) for r in stage['source_cells'] if r['decoder']==d for tr in r['traces']]))
            for t,spec in enumerate(specs):
                models=load_models(d,t,rep,confirmation,parent,stage);before=fingerprints(models)
                for model in models.values():meter.instrument_model(model)
                prefix=p['prefixes'][t];seq=np.array(prefix['sequences'],dtype=np.int64);inputs={};predictions={}
                for name,model in models.items():
                    imagined=predicted_endpoints(model,prefix['obs'],seq)[0]
                    actual=np.array([r['endpoint_obs'] for r in prefix['rollouts']])
                    inputs[name]={k:value_inputs(x,model).tolist() for k,x in [('imagined',imagined),('actual',actual)]}
                    predictions[name]={k:readout.predict(x).tolist() for k,x in inputs[name].items()};predictions[name]['constant']=[constant]*4
                env=make_task_env(spec);env.reset(seed=cfg['state_base']+t);meter.instrument_env(env);meter.bucket='tail'
                try:
                    traces=[continuation_trace(env,models['zero'],r['endpoint'],tail_seeds(cfg,t),horizon=48,original_phase=16) for r in prefix['rollouts']]
                finally:env.close()
                targets=[float(sum(tr['rewards'])) for tr in traces];after=fingerprints(models)
                if before!=after or readout.digest()!=readout_hash:raise RuntimeError('frozen state changed')
                p['cells'].append(dict(decoder=d,task=t,before=before,after=after,readout_sha256=readout_hash,inputs=inputs,predictions=predictions,targets=targets,traces=traces,metrics=metrics(predictions,targets)))
            p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p)
            print(f'calibration decoder={d} seconds={p["wall_clock_s"]:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['wall_clock_s']=time.perf_counter()-started
        p.update(validate(p,cfg,parent,stage));meter.check();p['complete']=True
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p)
    return p
