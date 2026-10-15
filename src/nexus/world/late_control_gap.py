"""Locked late-state intervention. No model fitting or controller changes."""
from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.spec import make_task_env
from nexus.world.context_pilot import prefix_hash
from nexus.world.control_replication import _collect_named, _confirmation_artifact, assert_fresh_physics, load_replication_config
from nexus.world.latent_generalization import decoder_digest, load_generalization_config
from nexus.world.late_control_gap_design import load_design_config, assert_design_seeds, episode_seed, state_seed, common_continuation_seed
from nexus.world.prediction_control_gap import candidate_sequences, load_prediction_config, verify_provenance
from nexus.world.receding_horizon import (_models_for_task, _context_snapshot, _same_context, _reward_ok,
    restore_state, run_live_episode, evaluate_state)
from nexus.world.planning import mpc_for_model

PROTOCOL=Path('docs/NEXUS_LATE_CONTROL_GAP_RESULTS.md')
OUTPUT=Path('artifacts/late_control_gap.json')
METRICS=('primary','policy','regret','reward_error','agreement','student_return','zero_return')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_ready():
    cfg=load_design_config()
    assert_design_seeds(cfg)
    text=PROTOCOL.read_text()
    if '<!-- execution-lock: late_control_v2_equal_visitors -->' not in text:
        raise RuntimeError('execution protocol must be saved before collection')
    for path,key in [('return_phase_decomposition','return_phase_artifact_sha256'),
                     ('receding_horizon_diagnostic','receding_artifact_sha256'),
                     ('prediction_control_gap','prediction_artifact_sha256')]:
        if sha(f'artifacts/{path}.json') != cfg[key]:
            raise RuntimeError(f'closed artifact changed: {path}')
    return cfg


def network_hash(model):
    h=hashlib.sha256(decoder_digest(model).encode())
    weights={**{'net.'+k:v for k,v in model.net.state_dict().items()},
             **{'encoder.'+k:v for k,v in model.encoder.state_dict().items()}}
    for key,value in sorted(weights.items()):
        a=value.detach().cpu().contiguous().numpy()
        h.update(key.encode()); h.update(str(a.dtype).encode()); h.update(str(a.shape).encode()); h.update(a.tobytes())
    return h.hexdigest()


def validate_grid(rows):
    expected=set(itertools.product(range(10),range(4),(16,50,100,150),('student','zero'),range(5)))
    seen=set()
    for row in rows:
        key=tuple(row[k] for k in ('decoder','task','phase','visitor','student'))
        if key not in expected or key in seen: raise ValueError(f'invalid/duplicate cell {key}')
        seen.add(key)
        for field in METRICS:
            value=row.get(field)
            if type(value) not in (float,int) or not np.isfinite(value):
                raise ValueError(f'invalid metric {key} {field}')
    if seen!=expected: raise ValueError(f'incomplete locked grid: {len(seen)}/{len(expected)}')


def aggregate(rows,metric,**filters):
    chosen=[r for r in rows if all(r[k]==v for k,v in filters.items())]
    values=[]
    for d in range(10):
        tasks=[]
        for t in sorted({r['task'] for r in chosen}):
            phases=[]
            for p in sorted({r['phase'] for r in chosen}):
                visitors=[]
                for v in sorted({r['visitor'] for r in chosen}):
                    cells=[r[metric] for r in chosen if (r['decoder'],r['task'],r['phase'],r['visitor'])==(d,t,p,v)]
                    if len(cells)!=5: raise ValueError('each visitor needs five paired student comparisons')
                    visitors.append(float(np.mean(cells)))
                phases.append(float(np.mean(visitors)))
            tasks.append(float(np.mean(phases)))
        values.append(float(np.mean(tasks)))
    return {'per_decoder':values,'interval':seed_level_ci(values)}


def decision(mean,lo,hi,complete):
    if not complete or not all(np.isfinite(x) for x in (mean,lo,hi)): return 'incomplete'
    if hi>=0: return 'action_quality_not_separated'
    if mean>-1: return 'below_practical_threshold'
    return 'same_state_action_worse'


def policy_return(env,model,state,seeds):
    """Full policy at all 16 steps; shared seed stream, state paths may diverge."""
    snapshot=_context_snapshot(model)
    obs=restore_state(env,state)
    total=0.
    planner=mpc_for_model(model,seed=seeds[0],enforce_time_budget=False)
    for k,seed in enumerate(seeds):
        planner.reset_episode(int(seed))
        action,info=planner.act(obs)
        if info['n_scored']!=16: raise RuntimeError('candidate budget changed')
        nxt,reward,term,trunc,_=env.step(int(action))
        _reward_ok(obs,action,nxt,reward)
        total+=float(reward); obs=np.asarray(nxt,dtype=np.float32)
        _same_context(model,snapshot)
        if (term or trunc) and k!=15: raise RuntimeError('short continuation')
    return total


class Meter:
    def __init__(self,deadline):
        self.deadline=deadline
        self.counts={'support':0,'live':0,'open_loop_and_common':0,'policy':0,'model_states':0}
        self.bucket='support'

    def check(self):
        if time.perf_counter()>=self.deadline: raise TimeoutError('registered 1800s cap reached')

    def instrument_env(self,env):
        original=env.step
        def step(action):
            self.check()
            result=original(action)
            self.counts[self.bucket]+=1
            return result
        env.step=step

    def instrument_model(self,model):
        original=model.step
        def step(obs,actions):
            self.check()
            result=original(obs,actions)
            self.counts['model_states']+=int(np.asarray(actions).size)
            return result
        model.step=step


def _save(payload):
    OUTPUT.parent.mkdir(exist_ok=True)
    temporary=OUTPUT.with_suffix('.partial.tmp')
    temporary.write_text(dumps_strict(payload))
    temporary.replace(OUTPUT)


def run():
    cfg=assert_ready()
    if OUTPUT.exists(): raise RuntimeError('refuse to overwrite existing run; no automatic rerun')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():
        raise RuntimeError('commit protocol and implementation before evaluation')
    for path in (PROTOCOL,Path(__file__).relative_to(Path.cwd()),Path('scripts/run_late_control_gap.py')):
        subprocess.run(['git','cat-file','-e',f'{revision}:{path}'],check=True)
    started=time.perf_counter(); meter=Meter(started+cfg['time_limit_s'])
    payload={'protocol_id':'late_control_v2_equal_visitors','starting_sha':'2dc746b07a8bc61bd784e664cc3cd0a46b1a5cf1',
        'implementation_sha':revision,'source_dirty':False,'config_sha256':sha('configs/late_control_gap_design.yaml'),
        'protocol_sha256':sha(PROTOCOL),'diagnostic_complete':False,'primary_decision':'incomplete',
        'cells':[],'states':[],'episodes':[],'counts':meter.counts,'frozen_checks':[],
        'time_limit_s':cfg['time_limit_s'],'control_claim':False,'is_learning_to_learn':False}
    try:
        provenance=verify_provenance(load_prediction_config())
        payload['provenance']=provenance
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        payload['checkpoint_integrity']=verify_checkpoint_integrity()
        rep=load_replication_config(); confirmation=_confirmation_artifact(rep)
        specs=list(assert_fresh_physics(rep))
        from nexus.tasks.pendulum_family import pendulum_physics_key
        payload['tasks']=[{'task':s.task_id,'physics':list(pendulum_physics_key(s))} for s in specs]
        import sys, gymnasium, importlib.metadata
        payload['dependencies']={'python':sys.version,'numpy':np.__version__,'torch':torch.__version__,
            'gymnasium':gymnasium.__version__,'pytest':importlib.metadata.version('pytest')}
        payload['registered_seeds']={k:cfg[k] for k in ('eval_env0','planner_seed_base','candidate_seed_base','common_continuation_base','policy_continuation_base')}
        forbidden=set(load_generalization_config()['forbidden_task_ids'])
        supports=[]
        for t,spec in enumerate(specs):
            meter.check()
            support=_collect_named(spec,128,rep['fresh_support_env0']+10*t,rep['fresh_support_base']+t,forbidden)
            if prefix_hash(support,128)!=cfg['fresh_support_hashes'][t]: raise RuntimeError('support hash mismatch')
            supports.append(support); meter.counts['support']+=128
        payload['support_hashes']=cfg['fresh_support_hashes']
        fingerprints={int(row['seed']):row['decoder_digest'] for row in provenance['decoder_fingerprints']}
        for d in range(10):
            for t,spec in enumerate(specs):
                meter.check()
                models=_models_for_task(d,rep,cfg,confirmation,supports[t],fingerprints[d])
                before={str(k):network_hash(m) for k,m in models.items()}
                contexts={k:_context_snapshot(m) for k,m in models.items()}
                for model in models.values(): meter.instrument_model(model)
                env=make_task_env(spec); env.reset(seed=episode_seed(cfg,'env',t,0)); meter.instrument_env(env)
                episodes=[]
                try:
                    meter.bucket='live'
                    for slot in range(6):
                        name='zero' if slot==5 else slot
                        ep=run_live_episode(env,models[name],reset_seed=episode_seed(cfg,'env',t,slot),
                            planner_seed=episode_seed(cfg,'planner',t,slot),phases=cfg['late_steps'],max_steps=200)
                        if not all(c['reproduced'] for c in ep['phases']): raise RuntimeError('live decision failed replay')
                        episodes.append(ep)
                        payload['episodes'].append({'decoder':d,'task':t,'slot':slot,'reset_seed':episode_seed(cfg,'env',t,slot),
                            'planner_seed':episode_seed(cfg,'planner',t,slot),'return':ep['return'],'rewards':ep['rewards']})
                    for pi,phase in enumerate(cfg['late_steps']):
                        for slot,ep in enumerate(episodes):
                            meter.check()
                            capture=next(c for c in ep['phases'] if c['step']==phase)
                            if not np.array_equal(restore_state(env,capture['state']),capture['obs']): raise RuntimeError('restore mismatch')
                            students=list(range(5)) if slot==5 else [slot]
                            named={s:models[s] for s in students}; named['zero']=models['zero']
                            seq=candidate_sequences(state_seed(cfg,'candidate',t,pi,slot),16,16,3)
                            common=[common_continuation_seed(cfg,t,pi,slot,k) for k in range(16)]
                            meter.bucket='open_loop_and_common'
                            evaluated=evaluate_state(env,state=capture['state'],obs=capture['obs'],sequences=seq,
                                models=named,zero_model=models['zero'],continuation_seeds=common)
                            policy_seeds=[state_seed(cfg,'policy',t,pi,slot)+k for k in range(16)]
                            meter.bucket='policy'
                            full={k:policy_return(env,m,capture['state'],policy_seeds) for k,m in named.items()}
                            z=evaluated['zero']
                            for s in students:
                                a=evaluated[s]
                                row=dict(decoder=d,task=t,phase=phase,visitor='zero' if slot==5 else 'student',student=s,
                                    primary=float(a['continuation_return']-z['continuation_return']),
                                    policy=float(full[s]-full['zero']),regret=float(z['regret']-a['regret']),
                                    reward_error=float(z['reward_mae']-a['reward_mae']),
                                    agreement=float(a['first_action']==z['first_action']),
                                    student_return=float(a['continuation_return']),zero_return=float(z['continuation_return']))
                                if abs(row['regret']-(a['sequence_return']-z['sequence_return']))>1e-10: raise RuntimeError('regret identity failed')
                                payload['cells'].append(row)
                            payload['states'].append(dict(decoder=d,task=t,phase=phase,slot=slot,
                                capture=capture,candidate_seed=state_seed(cfg,'candidate',t,pi,slot),
                                sequences=seq,common_seeds=common,policy_seeds=policy_seeds,
                                evaluated={str(k):v for k,v in evaluated.items()},policy_returns={str(k):v for k,v in full.items()}))
                    for k,m in models.items():
                        _same_context(m,contexts[k])
                        if network_hash(m)!=before[str(k)]: raise RuntimeError('network or normalization changed')
                    payload['frozen_checks'].append({'decoder':d,'task':t,'before':before,'after':{str(k):network_hash(m) for k,m in models.items()}})
                finally: env.close()
                payload['wall_clock_s']=time.perf_counter()-started
                _save(payload)
                print(f'finished decoder={d} task={t} states={len(payload["states"])} elapsed={payload["wall_clock_s"]:.1f}s',flush=True)
        validate_grid(payload['cells'])
        if len(payload['states'])!=960 or len(payload['episodes'])!=240 or len(payload['frozen_checks'])!=40:
            raise RuntimeError('incomplete execution integrity grid')
        payload['comparisons']={k:aggregate(payload['cells'],k) for k in METRICS}
        payload['by_task']={spec.task_id:aggregate(payload['cells'],'primary',task=t) for t,spec in enumerate(specs)}
        payload['by_visitor']={v:aggregate(payload['cells'],'primary',visitor=v) for v in ('student','zero')}
        payload['by_phase']={str(p):aggregate(payload['cells'],'primary',phase=p) for p in cfg['late_steps']}
        ci=payload['comparisons']['primary']['interval']
        payload['diagnostic_complete']=True
        payload['primary_decision']=decision(ci['mean'],ci['lo'],ci['hi'],True)
    except Exception as exc:
        payload['failure']={'type':type(exc).__name__,'message':str(exc)}
        print(f'INCOMPLETE: {type(exc).__name__}: {exc}',flush=True)
    payload['wall_clock_s']=time.perf_counter()-started
    payload['total_env_steps']=sum(v for k,v in meter.counts.items() if k!='model_states')
    payload['artifact_notes']={'student_seeds_not_decoder_replications':True,'equal_visitor_weights':True,
        'full_policy_secondary':True,'not_a_causal_explanation_of_184_step_gap':True}
    _save(payload)
    print(payload['primary_decision'],payload.get('comparisons',{}).get('primary'),flush=True)
    return payload
