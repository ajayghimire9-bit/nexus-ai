"""Lookahead versus frozen H=16 transfer on a new holdout. Collection unauthorized.

Successor value remains frozen open-loop H=16 score from s'. This is not a
learned or Bellman-consistent receding-policy value. Closed confirmation
splits are not reused. Reserved amortized confirmation is not consumed.
"""
from __future__ import annotations
import hashlib
import inspect
import itertools
import json
import subprocess
from pathlib import Path
import numpy as np
import yaml
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import (
    pendulum_amortized_confirmation,
    pendulum_confirmation_targets,
    pendulum_context_confirmation,
    pendulum_context_development,
    pendulum_context_train,
    pendulum_control_replication,
    pendulum_default,
    pendulum_development,
    pendulum_latent_confirmation,
    pendulum_latent_train,
    pendulum_latent_validation,
    pendulum_lookahead_transfer_holdout,
    pendulum_meta_confirm,
    pendulum_meta_train,
    pendulum_meta_val,
    pendulum_physics_key,
    pendulum_source,
    pendulum_transfer_confirmation,
    pendulum_transfer_development,
    pendulum_transfer_sequence,
)
from nexus.world import bellman_backup_control as bbc
from nexus.world import late_episode_decision_trajectory as late
from nexus.world.long_continuation import paired_interval
from nexus.world.planning_value import sha, finite_array
from nexus.world.terminal_value_execution import checked_id_grid, save

CONFIG=Path('configs/lookahead_transfer_confirmation.yaml')
PROTOCOL=Path('docs/NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_PROTOCOL.md')
ALLOCATION=Path('configs/lookahead_transfer_confirmation_allocation.json')
AUDIT=Path('docs/NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_PREP.md')
OUTPUT=Path('artifacts/lookahead_transfer_confirmation.json')
HOLD_RULE='lookahead_transfer_holdout_v1'
HOLD_SPLIT='73844661addfa11b'
LOCKED_CONFIG='385285edca761d60c1759bf8ef951c2682794e7b3d6066e9223aad5236c9cae8'
LOCKED_PROTOCOL='5c2e0d7300e497c65c0564990aa2a86ab4d08e79979c40d8ce7d2ea51735c942'
PRIMARY='return_gain'
FIELDS=bbc.FIELDS


def occupied_physics():
    rows=[]
    for fn in (
        pendulum_default,pendulum_development,pendulum_source,pendulum_transfer_development,
        pendulum_confirmation_targets,pendulum_transfer_confirmation,pendulum_transfer_sequence,
        pendulum_meta_train,pendulum_meta_val,pendulum_meta_confirm,pendulum_context_train,
        pendulum_context_development,pendulum_context_confirmation,pendulum_amortized_confirmation,
        pendulum_latent_train,pendulum_latent_confirmation,pendulum_control_replication,
        pendulum_latent_validation,
    ):
        specs=fn();
        if not isinstance(specs,(tuple,list)): specs=(specs,)
        for spec in specs: rows.append((fn.__name__,spec.task_id,pendulum_physics_key(spec)))
    keys={row[2] for row in rows}
    return keys,rows


def holdout_from_rule(n=3,rule=HOLD_RULE):
    occupied,_rows=occupied_physics()
    gs=[round(x*0.1,1) for x in range(30,191)]
    ms=[round(x*0.05,2) for x in range(4,65)]
    ls=[round(x*0.05,2) for x in range(10,41)]
    chosen=[];counter=0
    while len(chosen)<int(n):
        digest=hashlib.sha256(f'{rule}:{counter}'.encode()).digest()
        idx=int.from_bytes(digest[:8],'big')
        key=(float(gs[idx%len(gs)]),float(ms[(idx//len(gs))%len(ms)]),float(ls[(idx//(len(gs)*len(ms)))%len(ls)]))
        if key not in occupied and key not in chosen: chosen.append(key)
        counter+=1
    return chosen


def split_hash(specs):
    payload=[[s.task_id,list(pendulum_physics_key(s))] for s in specs]
    return hashlib.sha256(dumps_strict(payload).encode()).hexdigest()[:16]


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),eval_tasks=3,visitors=2,
                candidate_horizon=16,n_candidates=16,n_actions=3,episode_steps=200,phase=0,
                practical_margin=25.0,time_cap_s=180,env_cap=27840,model_cap=12324000,
                training_updates=0,support_budget=128,reset_base=14000000,step_seed_base=14100000,
                support_seed_base=14200000,paired_shared_candidates=True,new_network=False,
                three_action_counterfactuals=False,compute_matched_control=False,
                holdout_rule=HOLD_RULE,holdout_split_hash=HOLD_SPLIT,
                starting_sha='961e935cdf2a72c4221c640bd9ead1b2928cfac7',
                reserved_uncollected_amortized_hash='d1fa621351d286cf',
                historically_exposed_latent_confirm_hash='baa655fcb94e61bc',
                historically_exposed_control_replication_hash='053e8efca60fb4ac',
                historically_exposed_context_confirm_hash='87b83c41be34aa1a')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked transfer design/budget changed')
    specs=pendulum_lookahead_transfer_holdout()
    if cfg['eval_task_ids']!=[s.task_id for s in specs]: raise ValueError('holdout task ids changed')
    if cfg['eval_physics']!=[list(pendulum_physics_key(s)) for s in specs]: raise ValueError('holdout physics changed')
    if split_hash(specs)!=HOLD_SPLIT: raise ValueError('holdout split hash drifted')
    if holdout_from_rule()!=[tuple(row) for row in cfg['eval_physics']]:
        raise ValueError('holdout rule does not reproduce locked physics')
    occupied,_rows=occupied_physics()
    for row in cfg['eval_physics']:
        if tuple(row) in occupied: raise ValueError('holdout collides with a registered split')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    if sha(CONFIG)!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
    if sha(PROTOCOL)!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
    budget(cfg);check_seeds(cfg);assert_controller_identity()
    return cfg


def reset_seed(cfg,d,t): return cfg['reset_base']+100*d+t
def step_seed(cfg,d,t,step): return cfg['step_seed_base']+1000*d+200*t+step
def support_seed(cfg,d,t): return cfg['support_seed_base']+100*d+t
def visitor_student(d,t): return late.visitor_student(d,t)


def seed_groups(cfg):
    resets={reset_seed(cfg,d,t) for d in range(10) for t in range(3)}
    steps={step_seed(cfg,d,t,s) for d in range(10) for t in range(3) for s in range(200)}
    supports={support_seed(cfg,d,t) for d in range(10) for t in range(3)}
    return [resets,steps,supports]


def check_seeds(cfg):
    groups=seed_groups(cfg)
    if [len(g) for g in groups]!=[30,6000,30]: raise ValueError('duplicate transfer seeds')
    used=set().union(*groups)
    blocked=set().union(*late.seed_groups(late.load_config()),*bbc.seed_groups(bbc.load_config()))
    if used & blocked: raise ValueError('transfer seeds collide with development lookahead or late-episode seeds')
    if min(used)<14000000: raise ValueError('seed block drifted below 14000000')


def budget(cfg):
    control=10*3*2*200*2
    support=10*3*int(cfg['support_budget'])
    imagined=10*3*2*200*(16*16+3+3*16*16)
    if control+support!=cfg['env_cap'] or imagined!=cfg['model_cap']:
        raise ValueError('transfer resource allocation mismatch')
    if int(cfg['training_updates'])!=0: raise ValueError('training is not part of this protocol')
    return dict(episode=control+support,control=control,support=support,model_states=imagined,
                time_cap_s=180,training_updates=0,lookahead_imagined_per_step=771,h16_imagined_per_step=256)


def assert_controller_identity():
    for name in ('h16_first_action','lookahead_first_action','shared_candidates'):
        if not callable(getattr(bbc,name)): raise ValueError(f'frozen controller {name} missing')
    look=inspect.getsource(bbc.lookahead_first_action)
    h16=inspect.getsource(bbc.h16_first_action)
    if 'receding-policy Q' not in look: raise ValueError('lookahead docstring drifted')
    if 'for a in range(3)' not in look: raise ValueError('lookahead no longer backups three first actions')
    if 'int(sequences[idx,0])' not in h16: raise ValueError('H=16 no longer executes seq[argmax,0]')


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=180,env_cap=27840,model_cap=12324000,training_updates=0).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('transfer allocation drift')
    if record.get('holdout_split_hash')!=HOLD_SPLIT: raise ValueError('allocation holdout hash drifted')
    if record.get('config_sha256')!=LOCKED_CONFIG or record.get('config_sha256')!=sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256')!=LOCKED_PROTOCOL or record.get('protocol_sha256')!=sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before transfer collection')
    if sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')
    if sha(PROTOCOL)!=record.get('protocol_sha256'):
        raise PermissionError('allocation does not bind this protocol hash')
    if sha('artifacts/research_session_first_action_value_usage.json')!=record.get('previous_exhausted_session_sha256'):
        raise PermissionError('exhausted 3600-second ledger was modified')
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'lookahead_transfer_established'
    if mean<=-margin and hi<0: return 'lookahead_transfer_harm_established'
    return 'lookahead_transfer_not_established'


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task'),set(itertools.product(range(10),range(3))))
    for row in cells.values():
        if set(row['metrics'])!=set(FIELDS): raise ValueError('missing transfer metric')
        finite_array([row['metrics'][k] for k in FIELDS],(len(FIELDS),))
        if not np.isclose(row['metrics']['return_gain'],
                          0.5*(row['metrics']['student_gain']+row['metrics']['zero_gain']),atol=1e-8):
            raise ValueError('return_gain identity mismatch')
    groups={}
    for metric in FIELDS:
        values=[float(np.mean([cells[d,t]['metrics'][metric] for t in range(3)])) for d in range(10)]
        groups[metric]=dict(per_decoder=values,interval=paired_interval(values))
    student_zero_h16=[float(np.mean([cells[d,t]['metrics']['return_h16_student']-cells[d,t]['metrics']['return_h16_zero'] for t in range(3)])) for d in range(10)]
    student_zero_look=[float(np.mean([cells[d,t]['metrics']['return_lookahead_student']-cells[d,t]['metrics']['return_lookahead_zero'] for t in range(3)])) for d in range(10)]
    groups['student_minus_zero_h16']=dict(per_decoder=student_zero_h16,interval=paired_interval(student_zero_h16))
    groups['student_minus_zero_lookahead']=dict(per_decoder=student_zero_look,interval=paired_interval(student_zero_look))
    primary=groups[PRIMARY]['interval']
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,True,cfg['practical_margin'])
    return dict(label=label,groups=groups)


def eligibility_audit():
    occupied,rows=occupied_physics()
    hold=holdout_from_rule()
    specs=pendulum_lookahead_transfer_holdout()
    return dict(
        n_registered_physics=len(occupied),
        historically_exposed={
            'latent_confirmation_baa655fcb94e61bc':'used for H=16 student-versus-zero control and later mechanism studies; not pristine',
            'control_replication_053e8efca60fb4ac':'used for negative-transfer H=16 control and later 200-step studies; not pristine',
            'context_confirmation_87b83c41be34aa1a':'used for direct-latent prediction confirmation; not 200-step lookahead; not pristine',
            'amortized_confirmation_d1fa621351d286cf':'registered and unpublished as outcomes; reserved for a failed-gate encoder confirm; uncollected but not generated for this question',
        },
        genuinely_uncollected_reserved=['d1fa621351d286cf'],
        selected_holdout=[list(k) for k in hold],
        selected_task_ids=[s.task_id for s in specs],
        split_hash=split_hash(specs),
        holdout_collides_registered=any(k in occupied for k in hold),
        reused_closed_confirmation_outcomes=False,
        confirmation_outcomes_read=False,
    )


def load_visitor_models(d,rep,confirmation):
    from nexus.world.terminal_value import NAMES
    from nexus.world.control_replication import _decoder_file,_student_rows
    from nexus.world.latent_control import _fresh_decoder,_install_encoder
    students={str(i):r for i,r in enumerate(_student_rows(d,'broad',rep,confirmation))}
    models={}
    for name in NAMES:
        model,_digest=_fresh_decoder(_decoder_file(d,rep),rep)
        if name!='zero': _install_encoder(model,students[name]['path'],rep,_digest)
        model.clear_context()
        models[name]=model
    return models


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing transfer overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    from nexus.tasks.spec import make_task_env
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.control_replication import load_replication_config,_confirmation_artifact
    from nexus.world.receding_horizon import true_state,restore_state
    from nexus.world.terminal_value_execution import fingerprints
    from nexus.world.data import collect_transitions
    import time
    started=time.perf_counter();meter=bbc.Meter(cfg)
    p=dict(complete=False,label='incomplete',cells=[],counts=meter.counts,
           implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
           parents=cfg['parents'],confirmation_physics_reused=False,training_updates=0,
           successor_value='frozen_open_loop_h16_score',new_network=False,
           compute_matched_control=False,holdout_split_hash=HOLD_SPLIT)
    try:
        if p['config_sha256']!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
        if p['protocol_sha256']!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
        p['checkpoint_before']=verify_checkpoint_integrity()
        rep=load_replication_config();confirmation=_confirmation_artifact(rep)
        specs=list(pendulum_lookahead_transfer_holdout())
        for d,t in itertools.product(cfg['decoders'],range(3)):
            models=load_visitor_models(d,rep,confirmation)
            for model in models.values():meter.instrument_model(model)
            spec=specs[t]
            support=collect_transitions(spec,n_transitions=int(cfg['support_budget']),
                                        env_seeds=(support_seed(cfg,d,t),),base_seed=support_seed(cfg,d,t),
                                        policy='random')
            meter.counts['episode']+=int(cfg['support_budget']);meter.check()
            if meter.counts['episode']>meter.env_cap:raise TimeoutError('env cap reached')
            student=models[str(visitor_student(d,t))];zero=models['zero']
            student.set_context_from_dataset(support,budget=int(cfg['support_budget']))
            if int(zero.z.abs().sum().item())!=0: raise RuntimeError('zero-context visitor is not cleared')
            env=make_task_env(spec);obs,_=env.reset(seed=reset_seed(cfg,d,t));meter.instrument_env(env)
            try:
                start=true_state(env);before=fingerprints({'student':student,'zero':zero})
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start)
                student_h16=bbc._rollout(env,student,cfg,d,t,'h16')
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start)
                zero_h16=bbc._rollout(env,zero,cfg,d,t,'h16')
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start)
                student_look=bbc._rollout(env,student,cfg,d,t,'lookahead')
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start)
                zero_look=bbc._rollout(env,zero,cfg,d,t,'lookahead')
                after=fingerprints({'student':student,'zero':zero})
                if before!=after:raise RuntimeError('frozen model/context drift during control')
                seeds=student_h16['seeds']
                if zero_h16['seeds']!=seeds or student_look['seeds']!=seeds or zero_look['seeds']!=seeds:
                    raise ValueError('step seeds were not shared')
                metrics=bbc.cell_metrics(student_h16,zero_h16,student_look,zero_look)
                p['cells'].append(dict(decoder=d,task=t,reset_seed=reset_seed(cfg,d,t),
                                       support_seed=support_seed(cfg,d,t),visitor_student=visitor_student(d,t),
                                       true_state=start.tolist(),student_h16=student_h16,zero_h16=zero_h16,
                                       student_lookahead=student_look,zero_lookahead=zero_look,metrics=metrics,
                                       n_steps_student_h16=len(student_h16['actions']),
                                       n_steps_zero_h16=len(zero_h16['actions']),
                                       n_steps_student_lookahead=len(student_look['actions']),
                                       n_steps_zero_lookahead=len(zero_look['actions'])))
            finally:env.close()
            print(f'decoder={d} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['counts']=dict(meter.counts)
        if int(p['counts']['episode'])!=27840:raise ValueError('env step count drifted')
        if int(p['counts']['model_states'])!=12324000:raise ValueError('imagined count drifted')
        summary=summarize(p['cells'],cfg);p.update(summary);meter.check()
        p['complete']=len(p['cells'])==30
        p['n_episodes']=120
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
        p['complete']=False;p['label']='incomplete'
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def prep():
    cfg=load_config();record=load_allocation()
    if record.get('authorized') is True or int(record.get('runs',0))!=0:
        raise PermissionError('prep refuses an already authorized allocation')
    counts=budget(cfg)
    report=dict(
        complete=True,authorized=False,runs=0,new_environment_steps=0,new_imagined_transitions=0,
        training_updates=0,confirmation_outcomes_read=False,starting_sha=cfg['starting_sha'],
        config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
        controller=dict(h16='bbc.h16_first_action',lookahead='bbc.lookahead_first_action',
                        candidates='candidate_sequences(seed,16,16)',horizon=16,n_candidates=16,
                        n_actions=3,reward='published_pendulum',successor='frozen_open_loop_h16_score',
                        new_network=False,compute_matched_control=False,
                        lookahead_imagined_per_step=771,h16_imagined_per_step=256),
        eligibility=eligibility_audit(),proposed_budget=counts,
        primary=PRIMARY,practical_margin=25.0,labels=('lookahead_transfer_established',
            'lookahead_transfer_harm_established','lookahead_transfer_not_established','incomplete'),
        secondary_cannot_upgrade=('student_gain','zero_gain','student_minus_zero_h16','student_minus_zero_lookahead'),
        note='No environment collection. Closed confirmation outcomes were not read.',
    )
    return report
