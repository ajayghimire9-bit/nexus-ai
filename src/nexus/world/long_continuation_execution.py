"""One approved, locked longer-continuation run. No training or retuning."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

from nexus.cl.serialize import json_sanitize
from nexus.world.long_continuation import (CONFIG,load_config,digest,budget,assert_unused_seeds,
    require_budget_approval,state_seed,continuation_trace,split_rewards,
    validate_result_grid,summarize_result_grid,paired_interval)
from nexus.world.late_control_gap import network_hash
from nexus.world.receding_horizon import (restore_state,run_live_episode,chunked_scores,
    _models_for_task,_context_snapshot,_same_context)

OUTPUT=Path('artifacts/long_continuation.json')
PROTOCOL=Path('docs/NEXUS_LONG_CONTINUATION_PROTOCOL.md')
APPROVAL=Path('configs/long_continuation_approval.json')
LOCK='764afda08f1f614bc4e0151bf8ca203fd78caa043d6443a85467692599198918'


def context_hash(model):
    return hashlib.sha256(model.z.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


def frozen_hash(model):
    # Include exact normalization serialization, beyond the legacy decoder fingerprint.
    h=hashlib.sha256(network_hash(model).encode())
    h.update(json.dumps(json_sanitize(model.obs_rms.state_dict()),sort_keys=True,allow_nan=False).encode())
    return h.hexdigest()


def restore_at_phase(env,state,phase):
    if type(phase) is not int or not 0<=phase<=100: raise ValueError('unregistered episode phase')
    obs=restore_state(env,state)
    cursor=env
    while cursor is not None:
        if '_elapsed_steps' in vars(cursor): cursor._elapsed_steps=phase
        cursor=getattr(cursor,'env',None)
    return obs


class ExecutionMeter:
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s']
        self.plan=budget(cfg); self.env_cap=self.plan['env_steps']; self.model_cap=self.plan['model_states']
        self.counts={k:0 for k in ('support','harvest','common','full_policy','model_states')}
        self.bucket='harvest'

    def check(self):
        if time.perf_counter()>=self.deadline: raise TimeoutError('approved 1800-second cap reached')

    def instrument_env(self,env):
        original=env.step
        def step(action):
            self.check()
            if sum(v for k,v in self.counts.items() if k!='model_states')>=self.env_cap:
                raise RuntimeError('approved environment-interaction cap reached')
            out=original(action); self.counts[self.bucket]+=1
            return out
        env.step=step

    def instrument_model(self,model):
        original=model.step
        def step(obs,actions):
            self.check(); n=int(np.asarray(actions).size)
            if self.counts['model_states']+n>self.model_cap: raise RuntimeError('approved model-state cap reached')
            out=original(obs,actions); self.counts['model_states']+=n
            return out
        model.step=step


def save(payload):
    tmp=OUTPUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(json_sanitize(payload),separators=(',',':'),allow_nan=False)+'\n')
    tmp.replace(OUTPUT)


def validate_execution(payload,cfg):
    indexed=validate_result_grid(payload['cells'],cfg)
    expected=set(itertools.product(cfg['decoders'],range(4),cfg['phases'],range(6)))
    seen=set(); reconstructed={}
    for state in payload['states']:
        key=tuple(state[k] for k in ('decoder','task','phase','slot'))
        if key not in expected or key in seen: raise ValueError('raw state grid incomplete/duplicated')
        seen.add(key)
        d,t,p,slot=key
        from nexus.world.prediction_control_gap import candidate_sequences
        pi=cfg['phases'].index(p)
        expected_seed=state_seed(cfg,'candidate',t,pi,slot)
        if state['candidate_seed']!=expected_seed or not np.array_equal(state['sequences'],candidate_sequences(expected_seed,16,16,3)):
            raise ValueError('shared candidates or candidate seed drifted')
        if not state['capture']['reproduced'] or not state['restore_exact']:
            raise ValueError('restoration or live replay failed')
        students=cfg['students'] if slot==5 else [slot]
        named={str(s) for s in students}|{'zero'}
        if set(state['selected'])!=named: raise ValueError('missing shared candidate score condition')
        for selection in state['selected'].values():
            scores=np.asarray(selection['scores'],dtype=np.float64)
            if scores.shape!=(16,) or not np.isfinite(scores).all(): raise ValueError('invalid stored candidate scores')
            best=int(np.argmax(scores))
            if selection['index']!=best or selection['action']!=int(state['sequences'][best][0]):
                raise ValueError('chosen action does not match shared candidate ranking')
        if set(state['full'])!=named or len(state['common'])!=3:
            raise ValueError('missing continuation condition')
        for action,trace in enumerate(state['common']):
            if trace['actions'][0]!=action: raise ValueError('common continuation first-action mismatch')
        for trace in list(state['full'].values())+state['common']:
            values=split_rewards(trace['rewards'])
            if len(trace['actions'])!=64 or len(trace['decisions'])!=64:
                raise ValueError('short action/decision trace')
            if any(type(a) is not int or a not in (0,1,2) for a in trace['actions']):
                raise ValueError('invalid action')
            if [r['original_step'] for r in trace['decisions']]!=list(range(p,p+64)):
                raise ValueError('original episode clock lost')
            if any((r['selected_index'] is not None and (type(r['selected_index']) is not int or not 0<=r['selected_index']<16))
                   or (r['predicted_score'] is not None and not math.isfinite(r['predicted_score'])) for r in trace['decisions']):
                raise ValueError('invalid planner decision metadata')
            if any(r['terminated'] or r['truncated'] for r in trace['decisions']):
                raise ValueError('unexpected episode end')
            for w in ('early','late','total'):
                if not math.isclose(values[w],trace[w],abs_tol=1e-9): raise ValueError('raw reward sum mismatch')
        pi=cfg['phases'].index(p)
        for kind,traces in [('policy',state['full'].values()),('common',state['common'])]:
            seeds=[state_seed(cfg,kind,t,pi,slot)+k for k in range(64)]
            if any([r['seed'] for r in tr['decisions']]!=seeds for tr in traces):
                raise ValueError('unpaired continuation randomness')
        for student in students:
            rowkey=(d,t,p,'zero' if slot==5 else 'student',student)
            rec={}
            for policy in ('full','common'):
                if policy=='full':
                    a=state['full'][str(student)]; z=state['full']['zero']
                else:
                    a=state['common'][state['selected'][str(student)]['action']]
                    z=state['common'][state['selected']['zero']['action']]
                for w in ('early','late','total'):
                    rec[policy+'_'+w]=a[w]-z[w]
            for metric,value in rec.items():
                if not math.isclose(value,indexed[rowkey][metric],abs_tol=1e-9):
                    raise ValueError('raw trace / paired cell mismatch')
            reconstructed[rowkey]=rec
    if seen!=expected or set(reconstructed)!=set(indexed): raise ValueError('incomplete raw grid')
    episode_expected=set(itertools.product(cfg['decoders'],range(4),range(6)))
    episodes=set()
    for row in payload['episodes']:
        key=tuple(row[k] for k in ('decoder','task','slot'))
        if key not in episode_expected or key in episodes: raise ValueError('harvest episode grid invalid')
        episodes.add(key)
        if row['reset_seed']!=cfg['env_seed_base']+row['task']*100 or row['planner_seed']!=cfg['planner_seed_base']+row['task']*100:
            raise ValueError('live episodes not paired')
        if len(row['rewards'])!=101 or not all(math.isfinite(x) for x in row['rewards']) or row['stop_reason']!='diagnostic_cut':
            raise ValueError('invalid harvest metadata')
    if episodes!=episode_expected: raise ValueError('missing harvest episode')
    checks=payload['frozen_checks']
    if {(r['decoder'],r['task']) for r in checks}!=set(itertools.product(cfg['decoders'],range(4))) or len(checks)!=40:
        raise ValueError('frozen-check grid invalid')
    expected_models={'zero',*(str(s) for s in cfg['students'])}
    if any(set(r[k])!=expected_models for r in checks for k in ('before','after','contexts_before','contexts_after')):
        raise ValueError('missing model in frozen/context checks')
    if any(r['before']!=r['after'] or r['contexts_before']!=r['contexts_after'] for r in checks):
        raise ValueError('weights, normalization or context changed')
    plan=budget(cfg)
    if payload['counts']!={**plan['env_by_bucket'],'model_states':plan['model_states']}:
        raise ValueError('exact resource accounting mismatch')
    if payload.get('wall_clock_s',float('inf'))>cfg['time_cap_s']: raise ValueError('execution exceeded cap')
    return {'raw_states':len(seen),'paired_cells':len(indexed),'episodes':len(episodes),
            'all_reward_traces_verified':True,'frozen_checks':40}


def sensitivity(rows,cfg):
    report={}
    for axis,values in [('task',range(4)),('visitor',('student','zero')),('phase',cfg['phases'])]:
        report[axis]={}
        for value in values:
            subset=[r for r in rows if r[axis]==value]
            bydecoder=[float(np.mean([r['full_late'] for r in subset if r['decoder']==d])) for d in cfg['decoders']]
            report[axis][str(value)]={'per_decoder':bydecoder,'interval':paired_interval(bydecoder)}
    report['leave_one_task_out']={}
    for task in range(4):
        subset=[r for r in rows if r['task']!=task]
        values=[float(np.mean([r['full_late'] for r in subset if r['decoder']==d])) for d in cfg['decoders']]
        report['leave_one_task_out'][str(task)]={'per_decoder':values,'interval':paired_interval(values)}
    return report


def execute(approved_config_sha256=None):
    require_budget_approval(approved_config_sha256)
    if approved_config_sha256!=LOCK: raise PermissionError('approved configuration changed')
    approval=json.loads(APPROVAL.read_text())
    if approval['config_sha256']!=LOCK or approval['scope']!='one_locked_local_run':
        raise PermissionError('missing recorded human approval')
    if OUTPUT.exists(): raise RuntimeError('refusing to overwrite or repeat a recorded run')
    cfg=load_config(); assert_unused_seeds(cfg)
    if digest(CONFIG)!=LOCK: raise RuntimeError('approved protocol changed')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():
        raise RuntimeError('commit clean implementation before collection')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    started=time.perf_counter(); meter=ExecutionMeter(cfg)
    payload={'protocol_id':cfg['protocol_id'],'implementation_sha':revision,'source_dirty':False,
        'config_sha256':LOCK,'protocol_sha256':digest(PROTOCOL),'approval_sha256':digest(APPROVAL),
        'parent_sha256':cfg['parent_sha256'],'manifest_sha256':cfg['manifest_sha256'],
        'diagnostic_complete':False,'primary_label':'incomplete','cells':[],'states':[],
        'episodes':[],'frozen_checks':[],'counts':meter.counts,'budget':budget(cfg)}
    try:
        from nexus.world.prediction_control_gap import verify_provenance,load_prediction_config,candidate_sequences
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        from nexus.world.control_replication import (load_replication_config,_confirmation_artifact,assert_fresh_physics,_collect_named)
        from nexus.world.latent_generalization import load_generalization_config
        from nexus.world.context_pilot import prefix_hash
        from nexus.tasks.spec import make_task_env
        from nexus.tasks.pendulum_family import pendulum_physics_key
        import gymnasium
        payload['dependencies']={'python':sys.version,'torch':torch.__version__,'numpy':np.__version__,'gymnasium':gymnasium.__version__}
        payload['checkpoint_audit_before']=verify_checkpoint_integrity()
        provenance=verify_provenance(load_prediction_config()); payload['provenance']=provenance
        rep=load_replication_config(); confirmation=_confirmation_artifact(rep)
        specs=list(assert_fresh_physics(rep))
        if [[s.task_id,*pendulum_physics_key(s)] for s in specs]!=cfg['tasks']: raise RuntimeError('task physics drift')
        payload['tasks']=cfg['tasks']
        parent=json.loads(Path(cfg['parent_artifact']).read_text())
        forbidden=set(load_generalization_config()['forbidden_task_ids']); supports=[]
        for t,spec in enumerate(specs):
            meter.check()
            support=_collect_named(spec,128,rep['fresh_support_env0']+10*t,rep['fresh_support_base']+t,forbidden)
            if len(support)!=128 or prefix_hash(support,128)!=parent['support_hashes'][t]: raise RuntimeError('closed support changed')
            meter.counts['support']+=128; supports.append(support)
        payload['support_hashes']=parent['support_hashes']
        fingerprints={int(r['seed']):r['decoder_digest'] for r in provenance['decoder_fingerprints']}
        model_cfg={'n_student_seeds':5,'student_kind':'broad','support_budget':128}
        for d in cfg['decoders']:
            for t,spec in enumerate(specs):
                meter.check()
                models=_models_for_task(d,rep,model_cfg,confirmation,supports[t],fingerprints[d])
                hashes={str(k):frozen_hash(m) for k,m in models.items()}
                context_hashes={str(k):context_hash(m) for k,m in models.items()}
                contexts={k:_context_snapshot(m) for k,m in models.items()}
                for m in models.values(): meter.instrument_model(m)
                env=make_task_env(spec); env.reset(seed=cfg['env_seed_base']+t*100); meter.instrument_env(env)
                episodes=[]
                try:
                    meter.bucket='harvest'
                    for slot in range(6):
                        name='zero' if slot==5 else slot
                        episode=run_live_episode(env,models[name],reset_seed=cfg['env_seed_base']+t*100,
                            planner_seed=cfg['planner_seed_base']+t*100,phases=cfg['phases'],max_steps=cfg['harvest_steps'])
                        if not all(c['reproduced'] for c in episode['phases']): raise RuntimeError('live replay failed')
                        episodes.append(episode)
                        payload['episodes'].append({'decoder':d,'task':t,'slot':slot,
                            'reset_seed':cfg['env_seed_base']+t*100,'planner_seed':cfg['planner_seed_base']+t*100,
                            'rewards':episode['rewards'],'stop_reason':'diagnostic_cut'})
                    for pi,phase in enumerate(cfg['phases']):
                        for slot,episode in enumerate(episodes):
                            meter.check()
                            capture=next(c for c in episode['phases'] if c['step']==phase)
                            if not np.array_equal(restore_at_phase(env,capture['state'],phase),capture['obs']): raise RuntimeError('restore mismatch')
                            students=cfg['students'] if slot==5 else [slot]
                            named={str(s):models[s] for s in students}; named['zero']=models['zero']
                            sequences=candidate_sequences(state_seed(cfg,'candidate',t,pi,slot),16,16,3)
                            selected={}
                            for name,model in named.items():
                                scores=chunked_scores(model,capture['obs'],sequences)
                                if not np.isfinite(scores).all(): raise RuntimeError('nonfinite candidate score')
                                best=int(np.argmax(scores))
                                selected[name]={'action':int(sequences[best,0]),'index':best,'scores':scores.tolist()}
                            common_seeds=[state_seed(cfg,'common',t,pi,slot)+k for k in range(64)]
                            policy_seeds=[state_seed(cfg,'policy',t,pi,slot)+k for k in range(64)]
                            meter.bucket='common'
                            common=[continuation_trace(env,models['zero'],capture['state'],common_seeds,
                                first_action=action,original_phase=phase) for action in range(3)]
                            meter.bucket='full_policy'
                            full={name:continuation_trace(env,m,capture['state'],policy_seeds,original_phase=phase) for name,m in named.items()}
                            for s in students:
                                row={'decoder':d,'task':t,'phase':phase,'visitor':'zero' if slot==5 else 'student','student':s}
                                for policy in ('full','common'):
                                    a=full[str(s)] if policy=='full' else common[selected[str(s)]['action']]
                                    z=full['zero'] if policy=='full' else common[selected['zero']['action']]
                                    for w in ('early','late','total'): row[policy+'_'+w]=float(a[w]-z[w])
                                payload['cells'].append(row)
                            payload['states'].append({'decoder':d,'task':t,'phase':phase,'slot':slot,
                                'capture':capture,'restore_exact':True,'sequences':sequences,
                                'candidate_seed':state_seed(cfg,'candidate',t,pi,slot),'selected':selected,'common':common,'full':full})
                    for k,m in models.items():
                        _same_context(m,contexts[k])
                        if frozen_hash(m)!=hashes[str(k)]: raise RuntimeError('frozen model changed')
                    payload['frozen_checks'].append({'decoder':d,'task':t,'before':hashes,
                        'after':{str(k):frozen_hash(m) for k,m in models.items()},'contexts_before':context_hashes,
                        'contexts_after':{str(k):context_hash(m) for k,m in models.items()}})
                finally: env.close()
                payload['wall_clock_s']=time.perf_counter()-started
                save(payload)
                print(f'long continuation decoder={d} task={t} states={len(payload["states"])} seconds={payload["wall_clock_s"]:.1f}',flush=True)
        payload['checkpoint_audit_after']=verify_checkpoint_integrity()
        payload['wall_clock_s']=time.perf_counter()-started
        payload['integrity']=validate_execution(payload,cfg)
        result=summarize_result_grid(payload['cells'],cfg)
        payload['primary_label']=result['primary_label']; payload['comparisons']=result['comparisons']
        payload['sensitivity']=sensitivity(payload['cells'],cfg)
        payload['diagnostic_complete']=True
    except Exception as exc:
        payload['failure']={'type':type(exc).__name__,'message':str(exc)}
        print(f'INCOMPLETE {type(exc).__name__}: {exc}',flush=True)
    payload['wall_clock_s']=time.perf_counter()-started
    payload['total_env_steps']=sum(v for k,v in meter.counts.items() if k!='model_states')
    save(payload)
    print(payload['primary_label'],payload.get('comparisons',{}).get('full_late'),flush=True)
    return payload
