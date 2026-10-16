"""Fail-closed resume of the incomplete action-conditioned Q grid.

The original incomplete capture and fit files are read-only. Collection of the
single missing cell is blocked until a fresh human allocation is committed.
"""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import time
import numpy as np
import yaml
from nexus.world import action_conditioned_q as q
from nexus.world.planning_value import sha, finite_array
from nexus.world.terminal_value import NAMES, TerminalReadout, score_conditions
from nexus.world.terminal_value_execution import checked_id_grid, fingerprints, save
from nexus.world.commitment_value import continue_locked, total, validate_endpoint, validate_trace
from nexus.world.prediction_control_gap import candidate_sequences

CONFIG=Path('configs/action_conditioned_q_resume.yaml')
PROTOCOL=Path('docs/NEXUS_ACTION_CONDITIONED_Q_RESUME_PROTOCOL.md')
ALLOCATION=Path('configs/action_conditioned_q_resume_allocation.json')
PARENT_OUTPUT=q.OUTPUT
PARENT_FIT=q.FIT
CELL_OUTPUT=Path('artifacts/action_conditioned_q_resume_cell.json')
COMPLETED=Path('artifacts/action_conditioned_q_completed.json')
FEASIBILITY=Path('artifacts/action_conditioned_q_resume_feasibility.json')
MISSING=(9,2,1)
PRESENT_DIGEST='6e8bff7dd117ab396811165d690d6c9f7a45d5959b4b1dd3db8aedaaca423e5a'
EXPECTED_PRESENT=set(itertools.product(range(10),range(3),range(2)))-{MISSING}
REQUIRED_CELL=('decoder','task','state','visitor','visitor_model','reset_seed','collection','live_replay_matched',
               'true_state','obs','restore_exact','sequences','first_traces','scores','before','after',
               'sequence_readout_sha256','conditioned_sha256','additive_sha256','metrics')


def load_resume_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(missing_decoder=9,missing_task=2,missing_state=1,missing_visitor='zero',
                present_digest=PRESENT_DIGEST,
                time_cap_s=60,env_cap=242,model_cap=64512,
                parent_output='artifacts/action_conditioned_q.json',parent_fit='artifacts/action_conditioned_q_fit.json',
                starting_sha='36a9753ba1afcf49b50802bfe0fd7d85625629c0')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked resume design/budget changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('frozen incomplete capture or parent protocol changed')
    if (cfg['missing_decoder'],cfg['missing_task'],cfg['missing_state'])!=MISSING:raise ValueError('missing cell identity changed')
    parent=q.load_config();budget(cfg)
    return cfg,parent


def budget(cfg):
    counts=dict(collection=50,first_common=192,model_states=64512)
    if sum(v for k,v in counts.items() if k!='model_states')!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:
        raise ValueError('resume resource allocation mismatch')
    return counts


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),time_cap_s=60,env_cap=242,model_cap=64512).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('resume allocation drift')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before collecting the missing cell')
    usage=json.loads(Path(record['previous_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('resume session allowance exhausted')
    exhausted=json.loads(Path(record['previous_exhausted_session_record']).read_text())
    if sha(record['previous_exhausted_session_record'])!=record['previous_exhausted_session_sha256']:
        raise ValueError('exhausted 3600-second ledger changed')
    if float(exhausted['remaining_session_allowance_s'])>=cfg['time_cap_s']:
        raise ValueError('resume must not treat the exhausted standing ledger as remaining budget')


def load_parent():
    raw=json.loads(PARENT_OUTPUT.read_text());fit=json.loads(PARENT_FIT.read_text())
    if sha(PARENT_OUTPUT)!='6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680':
        raise ValueError('incomplete capture hash changed')
    if sha(PARENT_FIT)!='2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae':
        raise ValueError('frozen Q fit hash changed')
    if raw.get('complete') is not False or raw.get('label')!='incomplete':raise ValueError('parent is not the incomplete capture')
    if fit.get('complete') is not True or fit.get('family')!='action_obs':raise ValueError('parent fit is not the frozen action_obs readout')
    return raw,fit


def present_keys(cells):
    return {(c['decoder'],c['task'],c['state']) for c in cells}


def freeze_cells(cells):
    payload=[{k:row[k] for k in REQUIRED_CELL} for row in cells]
    return hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def inspect_fits(raw,fit,cfg):
    expected_rows=8*cfg['source_states']*3
    rebuilt={}
    for d in range(10):
        x_c,y_c=q.source_training_arrays(d,raw['source_cells'],cfg['family'])
        x_a,y_a=q.source_training_arrays(d,raw['source_cells'],cfg['additive_family'])
        if len(x_c)!=expected_rows:raise ValueError('unique source row count changed')
        cond=q.RidgeQ.fit(x_c,y_c,ridge=cfg['ridge']);add=q.RidgeQ.fit(x_a,y_a,ridge=cfg['ridge'])
        saved_c=fit['readouts'][str(d)]['conditioned'];saved_a=fit['readouts'][str(d)]['additive']
        if cond.digest()!=saved_c['sha256'] or add.digest()!=saved_a['sha256']:
            raise ValueError('rebuilt Q does not match frozen fit')
        if q.RidgeQ(**saved_c['state']).digest()!=cond.digest() or q.RidgeQ(**saved_a['state']).digest()!=add.digest():
            raise ValueError('frozen Q state is not the rebuilt readout')
        rebuilt[d]=dict(conditioned=cond.digest(),additive=add.digest(),rows=expected_rows,
                        conditioned_rmse=float(np.sqrt(np.mean((cond.predict(x_c)-y_c)**2))),
                        additive_rmse=float(np.sqrt(np.mean((add.predict(x_a)-y_a)**2))))
    return rebuilt


def inspect_source(raw,cfg,parent,seq_stage):
    source=checked_id_grid(raw['source_cells'],('decoder','task','state'),set(itertools.product(range(10),range(8),range(cfg['source_states']))))
    for (d,t,k),row in source.items():
        _,expected=q.visited.prior.saved_contexts(parent,seq_stage,d,t)
        if row['before']!=expected or row['after']!=expected:raise ValueError('source frozen fingerprints changed')
        if row['reset_seed']!=q.source_state_seed(cfg,t,k) or len(row['traces'])!=3:raise ValueError('source seed/label grid changed')
        validate_endpoint(row['true_state'],row['obs']);seeds=q.source_future_seeds(cfg,t,k)
        for a,tr in enumerate(row['traces']):
            validate_trace(tr,seeds,0,a)
            if not math.isclose(row['returns'][a],total(tr['rewards'],64),abs_tol=1e-8):raise ValueError('source return accounting changed')
    return 160


def inspect_eval_cell(row,cfg,parent,seq_stage,fit):
    d,t,v=row['decoder'],row['task'],row['state']
    if any(k not in row for k in REQUIRED_CELL):raise ValueError('evaluation cell missing required raw fields')
    _,expected=q.visited.prior.saved_contexts(parent,seq_stage,d,t+8)
    if row['before']!=expected or row['after']!=expected:raise ValueError('eval frozen fingerprints changed')
    if row['visitor']!=('student' if v==0 else 'zero') or row['visitor_model']!=(str(q.visitor_student(d,t)) if v==0 else 'zero') or row['reset_seed']!=q.reset_seed(cfg,d,t):
        raise ValueError('visitor assignment changed')
    live=row['collection']
    if len(live)!=50 or row['live_replay_matched'] is not True:raise ValueError('missing live trajectory/replay')
    previous=None
    for step_i,r in enumerate(live):
        validate_endpoint(r['true_state'],r['obs'])
        if previous is not None and r['obs']!=previous:raise ValueError('discontinuous live trajectory')
        previous=r['next_obs']
        if r['step']!=step_i or r['seed']!=q.collection_seeds(cfg,d,t)[step_i]:raise ValueError('live seed mismatch')
        if type(r['action']) is not int or r['action'] not in (0,1,2):raise ValueError('live action missing')
        if type(r['reward']) not in (int,float) or not math.isfinite(r['reward']):raise ValueError('live reward missing')
    validate_endpoint(row['true_state'],row['obs'])
    if row['obs']!=previous or row['restore_exact'] is not True:raise ValueError('visited state not collection endpoint')
    seq=candidate_sequences(q.candidate_seed(cfg,d,t,v))
    if not np.array_equal(row['sequences'],seq) or len(row['first_traces'])!=3:raise ValueError('candidate/first-action grid mismatch')
    seeds=q.future_seeds(cfg,d,t,v)
    for a,tr in enumerate(row['first_traces']):
        validate_trace(tr,seeds,50,a)
        finite_array(tr['rewards'],(64,));finite_array(tr['actions'],(64,))
    sequence=TerminalReadout(**seq_stage['readouts'][str(d)]['state'])
    cond=q.RidgeQ(**fit['readouts'][str(d)]['conditioned']['state']);add=q.RidgeQ(**fit['readouts'][str(d)]['additive']['state'])
    if row['sequence_readout_sha256']!=sequence.digest() or row['conditioned_sha256']!=cond.digest() or row['additive_sha256']!=add.digest():
        raise ValueError('readout identity changed')
    rebuilt=q.row_metrics(row['scores'],seq,[total(tr['rewards'],64) for tr in row['first_traces']],cond,add,row['obs'],cfg['family'],cfg['additive_family'])
    if rebuilt!=row['metrics']:raise ValueError('raw first-action metrics mismatch')
    return True


def inspect_present_cells(raw,cfg,parent,seq_stage,fit):
    keys=present_keys(raw['cells'])
    if keys!=EXPECTED_PRESENT:raise ValueError('present evaluation grid is not the locked 59-cell set')
    if MISSING in keys:raise ValueError('missing cell is already present')
    digest=freeze_cells(raw['cells'])
    if digest!=PRESENT_DIGEST:raise ValueError('frozen 59-cell digest changed')
    for row in raw['cells']:
        inspect_eval_cell(row,cfg,parent,seq_stage,fit)
    sibling=next(r for r in raw['cells'] if (r['decoder'],r['task'],r['state'])==(9,2,0))
    if sibling['visitor']!='student' or sibling['reset_seed']!=q.reset_seed(cfg,9,2):
        raise ValueError('sibling student cell does not share the locked reset seed')
    if [step['seed'] for step in sibling['collection']]!=q.collection_seeds(cfg,9,2):
        raise ValueError('sibling collection seeds drifted from the visitor-independent lock')
    if q.candidate_seed(cfg,9,2,0)==q.candidate_seed(cfg,9,2,1):raise ValueError('candidate seeds must differ by visitor')
    if q.future_seeds(cfg,9,2,0)==q.future_seeds(cfg,9,2,1):raise ValueError('continuation seeds must differ by visitor')
    return dict(n=59,cell_digest=freeze_cells(raw['cells']),sibling_reset=sibling['reset_seed'],
                missing_reset=q.reset_seed(cfg,9,2),missing_collection=q.collection_seeds(cfg,9,2)[:3],
                missing_candidate=q.candidate_seed(cfg,9,2,1),missing_future0=q.future_seeds(cfg,9,2,1)[0],
                visitor_model='zero',independent_of_sibling_candidates=True)


def accept_only_missing_cell(cell):
    if (cell.get('decoder'),cell.get('task'),cell.get('state'))!=MISSING:raise ValueError('resume cell is not the locked missing cell')
    if cell.get('visitor')!='zero' or cell.get('visitor_model')!='zero':raise ValueError('resume visitor is not zero')
    return True


def assemble(parent_raw,new_cell,fit,cfg,resume_meta):
    accept_only_missing_cell(new_cell)
    if resume_meta.get('present_digest')!=PRESENT_DIGEST or freeze_cells(parent_raw['cells'])!=PRESENT_DIGEST:
        raise ValueError('completed 59-cell set was replaced')
    cells=copy.deepcopy(parent_raw['cells'])+[copy.deepcopy(new_cell)]
    if present_keys(cells)!=set(itertools.product(range(10),range(3),range(2))):raise ValueError('assembled grid is not the locked 60 cells')
    if any((c['decoder'],c['task'],c['state'])==MISSING for c in parent_raw['cells']):raise ValueError('parent already contained the missing cell')
    payload=copy.deepcopy(parent_raw)
    payload['cells']=cells
    payload['parent_raw_sha256']=sha(PARENT_OUTPUT)
    payload['parent_fit_sha256']=sha(PARENT_FIT)
    payload['resume']=resume_meta
    payload['counts']=q.budget(cfg)
    payload['parent_counts']=copy.deepcopy(parent_raw.get('counts'))
    payload['resume_counts']=budget(resume_meta['resume_cfg'])
    payload['complete']=False
    payload['label']='incomplete'
    payload.pop('failure',None)
    payload.pop('groups',None)
    return payload


class Meter(q.Meter):
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='collection'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('action-conditioned-q resume cap reached')


def inspect_parent():
    resume_cfg,cfg=load_resume_config();load_allocation()
    before_out,before_fit=sha(PARENT_OUTPUT),sha(PARENT_FIT)
    raw,fit=load_parent();parent,seq_stage=q.visited.prior.parent_evidence()
    rebuilt=inspect_fits(raw,fit,cfg)
    n_source=inspect_source(raw,cfg,parent,seq_stage)
    present=inspect_present_cells(raw,cfg,parent,seq_stage,fit)
    if sha(PARENT_OUTPUT)!=before_out or sha(PARENT_FIT)!=before_fit:raise RuntimeError('inspect mutated frozen parent artifacts')
    reconstruction=dict(possible=True,reason='missing zero-visitor cell is independently seeded; 59 cells and ten Q fits rebuild from raw source/eval traces',
                        caution='resume must abort if the new cell fails fingerprint, replay or metric reconstruction; do not patch')
    report=dict(complete=True,new_environment_steps=0,new_imagined_transitions=0,authorized=False,
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                parent_output_sha256=before_out,parent_fit_sha256=before_fit,
                n_source_cells=n_source,n_eval_cells=present['n'],missing={'decoder':9,'task':2,'state':1,'visitor':'zero'},
                present_digest=present['cell_digest'],fits=rebuilt,present=present,reconstruction=reconstruction,
                original_protocol_unmodified=sha('docs/NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md')=='76c06fd1de355d7176f7165b6e2dc1cfceb0729b67ea5cac244e595207bfa597',
                development_outcomes_used_for_tuning=False)
    save(FEASIBILITY,report);return report


def collect_missing_cell(cfg,resume_cfg,fit,meter,parent,seq_stage,rep,confirmation):
    d,t,v=MISSING
    spec=list(__import__('nexus.tasks.pendulum_family',fromlist=['pendulum_context_development']).pendulum_context_development())[t]
    from nexus.tasks.spec import make_task_env
    from nexus.world.receding_horizon import true_state
    from nexus.world.long_continuation_execution import restore_at_phase
    sequence=TerminalReadout(**seq_stage['readouts'][str(d)]['state'])
    cond=q.RidgeQ(**fit['readouts'][str(d)]['conditioned']['state']);add=q.RidgeQ(**fit['readouts'][str(d)]['additive']['state'])
    models=q.visited.prior.load_models(d,t+8,rep,confirmation,parent,seq_stage)
    for model in models.values():meter.instrument_model(model)
    before=fingerprints(models);env=make_task_env(spec);env.reset(seed=q.reset_seed(cfg,d,t));meter.instrument_env(env)
    try:
        visitor='zero';meter.bucket='collection'
        live=q.visited.collect(env,models[visitor],q.collection_seeds(cfg,d,t))
        state=true_state(env);obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32)
        if not np.array_equal(restore_at_phase(env,state,50),obs):raise ValueError('exact restoration failed')
        seq=candidate_sequences(q.candidate_seed(cfg,d,t,v))
        scores={name:score_conditions(model,obs,seq,sequence) for name,model in models.items()}
        meter.bucket='first_common';seeds=q.future_seeds(cfg,d,t,v)
        first=[continue_locked(env,models['zero'],state,seeds,first_action=a,phase=50) for a in range(3)]
    finally:env.close()
    after=fingerprints(models)
    if before!=after:raise RuntimeError('frozen model/context drift')
    cell=dict(decoder=d,task=t,state=v,visitor='zero',visitor_model='zero',reset_seed=q.reset_seed(cfg,d,t),
              collection=live,live_replay_matched=True,true_state=state.tolist(),obs=obs.tolist(),restore_exact=True,
              sequences=seq.tolist(),first_traces=first,scores=scores,before=before,after=after,
              sequence_readout_sha256=sequence.digest(),conditioned_sha256=cond.digest(),additive_sha256=add.digest(),
              metrics=q.row_metrics(scores,seq,[total(tr['rewards'],64) for tr in first],cond,add,obs,cfg['family'],cfg['additive_family']))
    accept_only_missing_cell(cell);inspect_eval_cell(cell,cfg,parent,seq_stage,fit)
    return cell


def validate_completed(payload,cfg,parent,seq_stage,fit,resume_cfg):
    if sha(PARENT_OUTPUT)!=payload['parent_raw_sha256'] or sha(PARENT_FIT)!=payload['parent_fit_sha256']:
        raise ValueError('completed artifact does not point at the frozen incomplete capture')
    kept=[c for c in payload['cells'] if (c['decoder'],c['task'],c['state'])!=MISSING]
    if freeze_cells(kept)!=PRESENT_DIGEST:raise ValueError('completed 59-cell set was replaced')
    inspect_source(payload,cfg,parent,seq_stage);inspect_fits(payload,fit,cfg)
    cells=checked_id_grid(payload['cells'],('decoder','task','state'),set(itertools.product(range(10),range(3),range(2))))
    for row in cells.values():inspect_eval_cell(row,cfg,parent,seq_stage,fit)
    if payload['counts']!=q.budget(cfg):raise ValueError('completed scientific counts are not the locked full-grid budget')
    if payload['resume_counts']!=budget(resume_cfg):raise ValueError('resume interaction counts drifted')
    if payload.get('checkpoint_after')!=dict(verified=120,missing=0,mismatched=0):raise ValueError('missing resume binary audit')
    if not 0<payload['resume']['wall_clock_s']<=resume_cfg['time_cap_s']:raise ValueError('resume time exceeded')
    result=q.summarize(payload['cells'],cfg)
    if q.classify_primary(result['groups']['pooled']['gain_vs_h16']['interval']['mean'],result['groups']['pooled']['gain_vs_h16']['interval']['lo'],result['groups']['pooled']['gain_vs_h16']['interval']['hi'],10,cfg['practical_margin'],True)!=result['label']:
        raise ValueError('primary label rule drift')
    return result


def verify_before_collection():
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    resume_cfg,cfg=load_resume_config();raw,fit=load_parent()
    if subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='':raise RuntimeError('missing implementation revision')
    checkpoints=verify_checkpoint_integrity()
    parent,seq_stage=q.visited.prior.parent_evidence()
    present=inspect_present_cells(raw,cfg,parent,seq_stage,fit)
    rebuilt=inspect_fits(raw,fit,cfg);inspect_source(raw,cfg,parent,seq_stage)
    if present['cell_digest']!=PRESENT_DIGEST:raise ValueError('frozen 59-cell digest changed')
    if sha(PARENT_OUTPUT)!='6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680' or sha(PARENT_FIT)!='2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae':
        raise RuntimeError('verification mutated frozen parent artifacts')
    return dict(resume_cfg=resume_cfg,cfg=cfg,raw=raw,fit=fit,parent=parent,seq_stage=seq_stage,present=present,
                checkpoints=checkpoints,fits=rebuilt,implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                protocol_sha256=sha(PROTOCOL),config_sha256=sha(CONFIG),
                parent_output_sha256=sha(PARENT_OUTPUT),parent_fit_sha256=sha(PARENT_FIT))


def execute():
    resume_cfg,cfg=load_resume_config();require_allocation(resume_cfg)
    if CELL_OUTPUT.exists() or COMPLETED.exists():raise RuntimeError('refusing resume overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean resume protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',resume_cfg['starting_sha'],'HEAD'],check=True)
    verified=verify_before_collection();raw,fit,parent,seq_stage,present=verified['raw'],verified['fit'],verified['parent'],verified['seq_stage'],verified['present']
    payload=dict(complete=False,label='incomplete')
    started=time.perf_counter();meter=Meter(resume_cfg)
    try:
        from nexus.world.control_replication import load_replication_config,_confirmation_artifact
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        rep=load_replication_config();confirmation=_confirmation_artifact(rep)
        cell=collect_missing_cell(cfg,resume_cfg,fit,meter,parent,seq_stage,rep,confirmation)
        collection_s=time.perf_counter()-started;meter.check()
        save(CELL_OUTPUT,dict(cell=cell,counts=meter.counts,parent_raw_sha256=sha(PARENT_OUTPUT),parent_fit_sha256=sha(PARENT_FIT)))
        if sha(PARENT_OUTPUT)!='6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680' or sha(PARENT_FIT)!='2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae':
            raise RuntimeError('resume collection mutated frozen parent artifacts')
        meta=dict(present_digest=present['cell_digest'],wall_clock_s=collection_s,
                  implementation_sha=verified['implementation_sha'],
                  config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                  resume_cfg={'time_cap_s':60,'env_cap':242,'model_cap':64512})
        assembled=assemble(raw,cell,fit,cfg,meta)
        assembled['resume_counts']=dict(meter.counts)
        assembled['checkpoint_before']=verified['checkpoints']
        assembled['checkpoint_after']=verify_checkpoint_integrity()
        assembled['input_verification']=dict(checkpoints=verified['checkpoints'],n_source_cells=160,n_eval_cells=59,
                                             present_digest=PRESENT_DIGEST,implementation_sha=verified['implementation_sha'],
                                             new_environment_steps=0)
        assembled['resume']=meta
        result=validate_completed(assembled,cfg,parent,seq_stage,fit,resume_cfg)
        assembled.update(result);assembled['complete']=True
        payload=assembled
    except Exception as exc:
        payload=dict(complete=False,label='incomplete',failure=dict(type=type(exc).__name__,message=str(exc)),
                     parent_raw_sha256=sha(PARENT_OUTPUT),wall_clock_s=time.perf_counter()-started)
        print('INCOMPLETE',payload['failure'],flush=True)
    payload['wall_clock_s']=payload.get('resume',{}).get('wall_clock_s',time.perf_counter()-started) if payload.get('complete') is True else time.perf_counter()-started
    if payload.get('complete') is True:save(COMPLETED,payload)
    else:save(CELL_OUTPUT.with_name('action_conditioned_q_resume_incomplete.json'),payload)
    return payload


def audit():
    resume_cfg,cfg=load_resume_config();raw,fit=load_parent();parent,seq_stage=q.visited.prior.parent_evidence()
    completed=json.loads(COMPLETED.read_text())
    if completed.get('complete') is not True:raise RuntimeError('incomplete/invalid resumed evaluation')
    rebuilt=validate_completed(completed,cfg,parent,seq_stage,fit,resume_cfg)
    if completed['label']!=rebuilt['label']:raise ValueError('saved label differs')
    if completed['groups']!=rebuilt['groups']:raise ValueError('saved decoder intervals differ from independent reconstruction')
    kept=[c for c in completed['cells'] if (c['decoder'],c['task'],c['state'])!=MISSING]
    if freeze_cells(kept)!=PRESENT_DIGEST:raise ValueError('completed artifact replaced a saved cell')
    if sha(PARENT_OUTPUT)!='6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680' or sha(PARENT_FIT)!='2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae':
        raise ValueError('parent capture changed after resume')
    return dict(audit_passed=True,label=completed['label'],raw_sha256=sha(COMPLETED),parent_raw_sha256=sha(PARENT_OUTPUT),
                parent_fit_sha256=sha(PARENT_FIT),present_digest=PRESENT_DIGEST,groups=completed['groups'])
