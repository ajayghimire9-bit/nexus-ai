"""Bounded factorial policy intervention. Frozen controllers, no learning."""
from __future__ import annotations
import hashlib
import itertools
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from nexus.cl.serialize import json_sanitize
from nexus.world.long_continuation import continuation_trace,split_rewards,paired_interval,proposed_seeds,load_config as long_config
from nexus.world.long_continuation_execution import ExecutionMeter,frozen_hash,context_hash,restore_at_phase
from nexus.world.receding_horizon import run_live_episode,_models_for_task,_context_snapshot,_same_context,true_state

CONFIG=Path('configs/policy_switch.yaml')
PROTOCOL=Path('docs/NEXUS_POLICY_SWITCH.md')
OUTPUT=Path('artifacts/policy_switch.json')
SCHEDULES=('SS','SZ','ZS','ZZ')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    if cfg['decoders']!=list(range(10)) or cfg['students']!=list(range(5)) or cfg['phases']!=[50,100]: raise ValueError('fixed grid drift')
    if (cfg['prefix_steps'],cfg['suffix_steps'],cfg['horizon'],cfg['candidates'])!=(16,48,16,16): raise ValueError('controller or schedule drift')
    if cfg['task']!=['pendulum_ctrl_rp2',9.1,3.1,1.05] or cfg['source_task_index']!=2: raise ValueError('task drift')
    if (cfg['env_cap'],cfg['model_cap'],cfg['time_cap_s'])!=(52268,13378560,600): raise ValueError('budget drift')
    if sha(cfg['parent_artifact'])!=cfg['parent_sha256']: raise ValueError('closed parent changed')
    if sha('artifacts/control_replication_checkpoints/manifest.json')!=cfg['manifest_sha256']: raise ValueError('manifest changed')
    return cfg


def seeds(cfg,phase_index,slot):
    base=cfg['switch_seed_base']+phase_index*1024+slot*128
    return list(range(base,base+64))


def assert_seeds(cfg):
    from nexus.world.prediction_control_gap import diagnostic_seed_groups,load_prediction_config
    from nexus.world.receding_horizon import horizon_seed_groups,load_horizon_config
    from nexus.world.return_phase import phase_seed_groups,load_phase_config
    from nexus.world.late_control_gap_design import design_seed_groups
    a,b=diagnostic_seed_groups(load_prediction_config()); blocked=set()
    for group in (a,b,horizon_seed_groups(load_horizon_config()),phase_seed_groups(load_phase_config()),design_seed_groups(),proposed_seeds(long_config())):
        for values in group.values(): blocked.update(values)
    groups=[{cfg['env_seed']},{cfg['planner_seed']},{x for pi in range(2) for slot in range(6) for x in seeds(cfg,pi,slot)}]
    if len(groups[-1])!=768: raise ValueError('seed collision')
    for group in groups:
        if blocked & group: raise ValueError('closed or overlapping seed')
        blocked.update(group)


class SwitchMeter(ExecutionMeter):
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s']; self.env_cap=cfg['env_cap']; self.model_cap=cfg['model_cap']
        self.counts={'support':0,'harvest':0,'switch':0,'model_states':0}; self.bucket='harvest'
    def check(self):
        if time.perf_counter()>=self.deadline: raise TimeoutError('600-second policy-switch cap reached')


def switch_trace(env,student,zero,state,rng,phase,schedule):
    if schedule not in SCHEDULES: raise ValueError('unknown schedule')
    models={'S':student,'Z':zero}
    a=continuation_trace(env,models[schedule[0]],state,rng[:16],horizon=16,original_phase=phase)
    middle=true_state(env)
    b=continuation_trace(env,models[schedule[1]],middle,rng[16:],horizon=48,original_phase=phase+16)
    rewards=a['rewards']+b['rewards']
    return {'schedule':schedule,'middle_state':middle.tolist(),'rewards':rewards,
            'actions':a['actions']+b['actions'],'decisions':a['decisions']+b['decisions'],**split_rewards(rewards)}


def contrasts(traces):
    for k in SCHEDULES:
        values=split_rewards(traces[k]['rewards'])
        for w in ('early','late','total'):
            if not math.isclose(values[w],traces[k][w],abs_tol=1e-9): raise ValueError('trace reward mismatch')
    for left,right in (('SS','SZ'),('ZS','ZZ')):
        if traces[left]['rewards'][:16]!=traces[right]['rewards'][:16] or traces[left]['actions'][:16]!=traces[right]['actions'][:16]:
            raise ValueError('nonidentical shared prefix')
        if traces[left]['middle_state']!=traces[right]['middle_state']: raise ValueError('prefix endpoint mismatch')
    ss,sz,zs,zz=[traces[k]['late'] for k in SCHEDULES]
    result={'suffix':ss-sz,'inheritance':sz-zz,'overall':ss-zz,'zero_prefix_suffix':zs-zz,'interaction':(ss-sz)-(zs-zz)}
    if not math.isclose(result['suffix']+result['inheritance'],result['overall'],abs_tol=1e-8): raise ValueError('decomposition mismatch')
    return result


def validate_and_summarize(payload,cfg):
    expected=set(itertools.product(cfg['decoders'],cfg['phases'],('student','zero'),cfg['students']))
    rows={}
    for row in payload['cells']:
        if any(type(row.get(k)) is not int for k in ('decoder','phase','student')): raise ValueError('invalid identifier type')
        key=tuple(row[k] for k in ('decoder','phase','visitor','student'))
        if key not in expected or key in rows: raise ValueError('invalid/duplicate cell')
        for k in ('suffix','inheritance','overall','zero_prefix_suffix','interaction'):
            if type(row.get(k)) not in (int,float) or not math.isfinite(row[k]): raise ValueError('invalid metric')
        rows[key]=row
    if set(rows)!=expected: raise ValueError('missing planned cells')
    rawexpected=set(itertools.product(cfg['decoders'],cfg['phases'],range(6))); rawseen=set()
    for record in payload['states']:
        d,p,slot=(record[k] for k in ('decoder','phase','slot')); key=(d,p,slot)
        if key not in rawexpected or key in rawseen: raise ValueError('invalid raw state grid')
        rawseen.add(key)
        if not record['capture']['reproduced'] or not record['restore_exact']: raise ValueError('replay/restoration failed')
        students=cfg['students'] if slot==5 else [slot]
        expectednames={'ZZ',*(str(s) for s in students)}
        if set(record['traces'])!=expectednames: raise ValueError('missing raw schedule conditions')
        rng=seeds(cfg,cfg['phases'].index(p),slot)
        for s in students:
            tr={**record['traces'][str(s)],'ZZ':record['traces']['ZZ']}
            if set(tr)!=set(SCHEDULES): raise ValueError('missing factorial condition')
            for name,trace in tr.items():
                if trace['schedule']!=name or len(trace['actions'])!=64 or len(trace['decisions'])!=64: raise ValueError('invalid trace')
                if any(type(a) is not int or a not in (0,1,2) for a in trace['actions']): raise ValueError('invalid action')
                if len(trace['rewards'])!=64 or any(type(x) not in (int,float) or not math.isfinite(x) for x in trace['rewards']): raise ValueError('invalid raw reward')
                if [r['seed'] for r in trace['decisions']]!=rng: raise ValueError('unpaired switch RNG')
                if [r['original_step'] for r in trace['decisions']]!=list(range(p,p+64)): raise ValueError('lost episode clock')
                if any(r['terminated'] or r['truncated'] for r in trace['decisions']): raise ValueError('unexpected episode end')
            rebuilt=contrasts(tr)
            row=rows[(d,p,'zero' if slot==5 else 'student',s)]
            if any(not math.isclose(value,row[k],abs_tol=1e-9) for k,value in rebuilt.items()): raise ValueError('raw/summary mismatch')
    if rawseen!=rawexpected: raise ValueError('raw state grid missing')
    episodes=payload['episodes']
    if len(episodes)!=60 or {tuple(r[k] for k in ('decoder','slot')) for r in episodes}!=set(itertools.product(cfg['decoders'],range(6))):
        raise ValueError('missing harvest episodes')
    if any(r['reset_seed']!=cfg['env_seed'] or r['planner_seed']!=cfg['planner_seed'] or r['stop_reason']!='diagnostic_cut' or len(r['rewards'])!=101 or not all(math.isfinite(x) for x in r['rewards']) for r in episodes):
        raise ValueError('unpaired or invalid harvest episodes')
    checks=payload['frozen_checks']
    expected_models={'zero',*(str(s) for s in cfg['students'])}
    if any(set(r[k])!=expected_models for r in checks for k in ('before','after')): raise ValueError('missing frozen model check')
    if [r['decoder'] for r in checks]!=cfg['decoders'] or any(r['before']!=r['after'] for r in checks): raise ValueError('frozen/context integrity failure')
    if payload['counts']!={'support':128,'harvest':6060,'switch':46080,'model_states':cfg['model_cap']}: raise ValueError('resource mismatch')
    if type(payload.get('wall_clock_s')) not in (int,float) or not math.isfinite(payload['wall_clock_s']) or payload['wall_clock_s']>cfg['time_cap_s']: raise ValueError('timeout or invalid duration')
    summary={}
    for metric in ('suffix','inheritance','overall','zero_prefix_suffix','interaction'):
        values=[]
        for d in cfg['decoders']:
            phases=[]
            for p in cfg['phases']:
                phases.append(statistics.mean(statistics.mean(rows[(d,p,v,s)][metric] for s in cfg['students']) for v in ('student','zero')))
            values.append(float(statistics.mean(phases)))
        summary[metric]={'per_decoder':values,'interval':paired_interval(values)}
    ci=summary['suffix']['interval']
    label='suffix_unseparated'
    if ci['hi']<0: label='continued_student_suffix_worse' if ci['mean']<=-cfg['practical_margin'] else 'suffix_below_margin'
    elif ci['lo']>0: label='student_suffix_favors_student'
    return {'label':label,'comparisons':summary,'valid':True}


def save(payload):
    tmp=OUTPUT.with_suffix('.tmp');tmp.write_text(json.dumps(json_sanitize(payload),separators=(',',':'),allow_nan=False)+'\n');tmp.replace(OUTPUT)


def execute():
    cfg=load_config();assert_seeds(cfg)
    if OUTPUT.exists(): raise RuntimeError('refusing to repeat/overwrite a recorded run')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip(): raise RuntimeError('commit clean implementation first')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    meter=SwitchMeter(cfg);started=time.perf_counter()
    payload={'implementation_sha':revision,'config_sha256':sha(CONFIG),'protocol_sha256':sha(PROTOCOL),
        'parent_sha256':cfg['parent_sha256'],'manifest_sha256':cfg['manifest_sha256'],
        'source_dirty':False,'complete':False,'label':'incomplete','states':[],'cells':[],'episodes':[],
        'frozen_checks':[],'counts':meter.counts}
    try:
        from nexus.world.control_replication import load_replication_config,_confirmation_artifact,assert_fresh_physics,_collect_named
        from nexus.world.prediction_control_gap import verify_provenance,load_prediction_config
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        from nexus.world.context_pilot import prefix_hash
        from nexus.world.latent_generalization import load_generalization_config
        from nexus.tasks.spec import make_task_env
        from nexus.tasks.pendulum_family import pendulum_physics_key
        import gymnasium
        payload['dependencies']={'python':sys.version,'torch':torch.__version__,'numpy':np.__version__,'gymnasium':gymnasium.__version__}
        payload['checkpoint_before']=verify_checkpoint_integrity(); prov=verify_provenance(load_prediction_config());payload['provenance']=prov
        rep=load_replication_config();confirm=_confirmation_artifact(rep);spec=list(assert_fresh_physics(rep))[2]
        if [spec.task_id,*pendulum_physics_key(spec)]!=cfg['task']: raise ValueError('physics mismatch')
        support=_collect_named(spec,128,rep['fresh_support_env0']+20,rep['fresh_support_base']+2,set(load_generalization_config()['forbidden_task_ids']))
        parent=json.loads(Path(cfg['parent_artifact']).read_text())
        if len(support)!=128 or prefix_hash(support,128)!=parent['support_hashes'][2]: raise ValueError('support drift')
        meter.counts['support']=128;payload['support_hash']=parent['support_hashes'][2]
        fingerprints={int(r['seed']):r['decoder_digest'] for r in prov['decoder_fingerprints']}
        for d in cfg['decoders']:
            meter.check();models=_models_for_task(d,rep,{'n_student_seeds':5,'student_kind':'broad','support_budget':128},confirm,support,fingerprints[d])
            before={str(k):(frozen_hash(m),context_hash(m)) for k,m in models.items()}
            snapshots={k:_context_snapshot(m) for k,m in models.items()}
            for m in models.values(): meter.instrument_model(m)
            env=make_task_env(spec);env.reset(seed=cfg['env_seed']);meter.instrument_env(env)
            episodes=[]
            try:
                meter.bucket='harvest'
                for slot in range(6):
                    name='zero' if slot==5 else slot
                    ep=run_live_episode(env,models[name],reset_seed=cfg['env_seed'],planner_seed=cfg['planner_seed'],phases=cfg['phases'],max_steps=101)
                    if not all(r['reproduced'] for r in ep['phases']): raise RuntimeError('live replay failed')
                    episodes.append(ep);payload['episodes'].append({'decoder':d,'slot':slot,'reset_seed':cfg['env_seed'],'planner_seed':cfg['planner_seed'],'stop_reason':'diagnostic_cut','rewards':ep['rewards']})
                meter.bucket='switch'
                for pi,p in enumerate(cfg['phases']):
                    for slot,ep in enumerate(episodes):
                        meter.check();capture=next(r for r in ep['phases'] if r['step']==p)
                        if not np.array_equal(restore_at_phase(env,capture['state'],p),capture['obs']): raise ValueError('restore mismatch')
                        rng=seeds(cfg,pi,slot);students=cfg['students'] if slot==5 else [slot]
                        traces={'ZZ':switch_trace(env,models['zero'],models['zero'],capture['state'],rng,p,'ZZ')}
                        for s in students:
                            group={k:switch_trace(env,models[s],models['zero'],capture['state'],rng,p,k) for k in ('SS','SZ','ZS')}
                            values=contrasts({**group,'ZZ':traces['ZZ']})
                            traces[str(s)]=group;payload['cells'].append({'decoder':d,'phase':p,'visitor':'zero' if slot==5 else 'student','student':s,**values})
                        payload['states'].append({'decoder':d,'phase':p,'slot':slot,'capture':capture,'restore_exact':True,'traces':traces})
                for k,m in models.items(): _same_context(m,snapshots[k])
                after={str(k):(frozen_hash(m),context_hash(m)) for k,m in models.items()}
                if before!=after: raise RuntimeError('network/context changed')
                payload['frozen_checks'].append({'decoder':d,'before':before,'after':after})
            finally: env.close()
            payload['wall_clock_s']=time.perf_counter()-started;save(payload)
            print(f'policy switch decoder={d} states={len(payload["states"])} seconds={payload["wall_clock_s"]:.1f}',flush=True)
        payload['checkpoint_after']=verify_checkpoint_integrity();payload['wall_clock_s']=time.perf_counter()-started
        result=validate_and_summarize(payload,cfg);payload.update(result);payload['complete']=True
    except Exception as exc:
        payload['failure']={'type':type(exc).__name__,'message':str(exc)};print('INCOMPLETE',payload['failure'],flush=True)
    payload['wall_clock_s']=time.perf_counter()-started;save(payload)
    print(payload['label'],payload.get('comparisons',{}).get('suffix'),flush=True)
    return payload
