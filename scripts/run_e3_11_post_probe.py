"""One locked fresh-source post-probe study. --verify never calls models/envs."""
import argparse
from dataclasses import asdict,replace
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'configs/e3_11_post_probe.json'
PROTOCOL=ROOT/'docs/NEXUS_E3_11_POST_PROBE_PROTOCOL.md'
ALLOCATION=ROOT/'configs/e3_11_post_probe_allocation.json'
RESULT=ROOT/'artifacts/e3_11_post_probe.json'
USAGE=ROOT/'artifacts/e3_11_post_probe_usage.json'
VALIDATION=ROOT/'artifacts/e3_11_post_probe_validation.json'
PREDICTIONS=ROOT/'artifacts/e3_11_predecision.jsonl'
FROZEN=ROOT/'artifacts/e3_11_frozen_selector.json'
JOURNAL=ROOT/'artifacts/e3_11_resources.jsonl.gz'
ROLLOUT_PROFILE=False
CALIBRATION_PROFILE=False
HORIZON_PROFILE=False


def configure_horizon():
    global CONFIG,PROTOCOL,ALLOCATION,RESULT,USAGE,VALIDATION,JOURNAL,PREDICTIONS,HORIZON_PROFILE
    configure_calibration();HORIZON_PROFILE=True
    CONFIG=ROOT/'configs/e3_11d_horizon_calibration.json'
    PROTOCOL=ROOT/'docs/NEXUS_E3_11D_HORIZON_CALIBRATION_PROTOCOL.md'
    ALLOCATION=ROOT/'configs/e3_11d_horizon_calibration_allocation.json'
    RESULT=ROOT/'artifacts/e3_11d_horizon_calibration.json'
    USAGE=ROOT/'artifacts/e3_11d_horizon_usage.json'
    VALIDATION=ROOT/'artifacts/e3_11d_horizon_validation.json'
    JOURNAL=ROOT/'artifacts/e3_11d_horizon_resources.jsonl.gz'
    PREDICTIONS=ROOT/'artifacts/e3_11d_horizon_predecision.jsonl'


def configure_calibration():
    """Fresh E3.11B profile; original captures and preparation stay immutable."""
    global CONFIG,PROTOCOL,ALLOCATION,RESULT,USAGE,VALIDATION,JOURNAL,PREDICTIONS,ROLLOUT_PROFILE,CALIBRATION_PROFILE
    CALIBRATION_PROFILE=True;ROLLOUT_PROFILE=True
    CONFIG=ROOT/'configs/e3_11b_forecast_calibration_execution.json'
    PROTOCOL=ROOT/'docs/NEXUS_E3_11B_FORECAST_CALIBRATION_EXECUTION.md'
    ALLOCATION=ROOT/'configs/e3_11b_forecast_calibration_allocation.json'
    RESULT=ROOT/'artifacts/e3_11b_forecast_calibration.json'
    USAGE=ROOT/'artifacts/e3_11b_forecast_calibration_usage.json'
    VALIDATION=ROOT/'artifacts/e3_11b_forecast_calibration_validation.json'
    JOURNAL=ROOT/'artifacts/e3_11b_forecast_resources.jsonl.gz'
    PREDICTIONS=ROOT/'artifacts/e3_11b_forecast_predecision.jsonl'


def configure_rollout():
    global CONFIG,PROTOCOL,ALLOCATION,RESULT,USAGE,VALIDATION,JOURNAL,ROLLOUT_PROFILE
    ROLLOUT_PROFILE=True
    CONFIG=ROOT/'configs/e3_11a_rollout_headroom.json'
    PROTOCOL=ROOT/'docs/NEXUS_E3_11A_ROLLOUT_HEADROOM_PROTOCOL.md'
    ALLOCATION=ROOT/'configs/e3_11a_rollout_headroom_allocation.json'
    RESULT=ROOT/'artifacts/e3_11a_rollout_headroom.json'
    USAGE=ROOT/'artifacts/e3_11a_rollout_headroom_usage.json'
    VALIDATION=ROOT/'artifacts/e3_11a_rollout_headroom_validation.json'
    JOURNAL=ROOT/'artifacts/e3_11a_rollout_resources.jsonl.gz'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p):
    tmp=RESULT.with_suffix('.tmp');tmp.write_text(json.dumps(p,allow_nan=False,separators=(',',':'))+'\n');tmp.replace(RESULT)


def seed_audit(c,old):
    import numpy as np
    from nexus.evolution2.post_probe import registered_seeds
    from nexus.evolution2.full_policy_source import seed_collisions
    from nexus.evolution2.fit_clock import LOCKED_ARRAYS
    proposed=registered_seeds(c);collisions={}
    for n in old:
        hit=seed_collisions(json.loads((ROOT/n).read_text()),proposed)
        if hit:collisions[n]=sorted(hit)
    # Explicit source/config seed metadata too; this config is the new registration.
    for n in (ROOT/'configs').glob('*'):
        if n.suffix=='.json' and n not in (CONFIG,ALLOCATION):
            hit=seed_collisions(json.loads(n.read_text()),proposed)
            if hit:collisions[str(n.relative_to(ROOT))]=sorted(hit)
    for r in LOCKED_ARRAYS:
        if sha(ROOT/r['path'])!=r['sha256']:raise ValueError('source_array_provenance')
        with np.load(ROOT/r['path'],allow_pickle=False) as a:
            hit=set(a['env_seeds'].reshape(-1).tolist())&proposed
            if hit:collisions[r['path']]=sorted(hit)
    registry=json.loads((ROOT/'artifacts/h17_exclusion_registry_audit_validated.json').read_text())
    ranges=registry['conservative_seed_reservations']
    if collisions or any(lo<=s<=hi for s in proposed for lo,hi in ranges):raise ValueError('closed_or_reserved_seed_collision')
    return dict(requested_seed_count=len(proposed),collisions=collisions,registry_sha256=sha(ROOT/'artifacts/h17_exclusion_registry_audit_validated.json'),
        scope='Current artifact/config seed metadata, all original source arrays and conservative historical reservations; not unavailable external runs.')


def worker():
    use=json.loads(USAGE.read_text())
    if use['parent_pid']!=os.getppid() or os.environ.get('NEXUS_E311_PARENT')!=str(os.getppid()):raise ValueError('parent_launch_required')
    import numpy as np
    import torch
    from nexus.evolution1.resources import Work,Operation,Clock
    from nexus.evolution1.catalogue import digest
    from nexus.evolution2 import post_probe as h
    from nexus.evolution2.full_policy_source import DecisionJournal,task_spec,state_hash
    from nexus.evolution2.planner_evidence import planner_evidence,evidence_operations
    from nexus.evolution2.planner_adapter import iid_sequences
    from nexus.evolution2.staged_study import StagedStudy
    from nexus.world.dynamics import WorldModel
    from nexus.world.rewards import pendulum_step_reward,acrobot_step_reward
    from nexus.tasks.spec import make_task_env
    c=json.loads(CONFIG.read_text());p=json.loads(RESULT.read_text());torch.set_num_threads(1)
    cpu=time.process_time_ns();clock=lambda:Clock(time.process_time_ns()-cpu,int((time.perf_counter()-use['start_monotonic'])*1e9))
    p['seed_audit']=seed_audit(c,p['historical_json_sha256']);save(p)
    inventory=json.loads((ROOT/c['checkpoint_inventory']).read_text())['integrity']
    files=inventory['checkpoints']+inventory['source_arrays']
    if any(sha(ROOT/r['path'])!=r['sha256'] for r in files):raise ValueError('checkpoint_source_integrity')
    models={};initial={}
    for r in inventory['checkpoints']:
        wm=WorldModel.load(ROOT/r['path']);wm.net.eval()
        if wm.net.arch!='mlp' or tuple(wm.net.hidden)!=(64,64) or str(wm.device)!='cpu' or wm.kind!='residual' or wm.net.n_actions!=3:raise ValueError('frozen_source_mlp_profile')
        key=(r['family'],r['bundle']);models[key]=wm;initial[key]=state_hash(wm)
        p['models'].append({**r,'before':initial[key],'after':initial[key]})
    if set(models)!=set(itertools.product(c['families'],c['model_bundles'])):raise ValueError('checkpoint_grid')
    p['dependencies']=dict(python=sys.version,numpy=np.__version__,torch=torch.__version__)
    pending={};probe_records={};observed_calls=observed_forwards=0
    journal=DecisionJournal(JOURNAL,c['journal_chunk_decisions']);host=h.Host(c,clock,journal)

    def persist():
        p['resources']=host.resources();save(p)

    def probe(f,b,e,role):
        wm=models[f,b];host.bind(wm);s=h.seeds(c,f,e);task=f'{f}:{b}'
        env=make_task_env(task_spec(f),seed=s['env']);obs,_=env.reset(seed=s['env'])
        if state_hash(wm)!=initial[f,b]:raise ValueError('model_changed_before_probe')
        p['active_work']=dict(stage='probe',family=f,bundle=b,episode=e,upper=dict(real_steps=8,imagined_transitions=3592,model_calls=151,network_forwards=151));persist()
        support=[];actions=np.random.default_rng(s['probe']).integers(0,3,size=8).tolist()
        ops=[Operation(f'probe_{i}','environment',Work(real_steps=1)) for i in range(8)]
        ops.append(Operation('support','model',Work(imagined_transitions=8,model_calls=1,network_forwards=1)))
        dummy=np.zeros(task_spec(f).obs_dim,dtype=np.float32)
        for label in c['controllers']:ops.extend(h.planning_ops(label,dummy,'proposal_'+label+'_'))
        dummy_plans={label:np.zeros((16,16),dtype=np.int64) for label in c['controllers']}
        ops.extend(evidence_operations(dummy_plans,3))
        reward=pendulum_step_reward if f=='pendulum' else acrobot_step_reward
        def body(d):
            nonlocal obs
            for i,a in enumerate(actions):
                nxt,r,term,trunc,_=d.environment(f'probe_{i}',env,int(a))
                if term or trunc:raise ValueError('probe_early_end')
                published=reward(obs,int(a),nxt)
                if not np.isclose(float(published[0]),r,atol=1e-5,rtol=0):raise ValueError('probe_reward_timing')
                support.append(dict(task=task,episode=e,step=i,phase='support',observation=np.asarray(obs).tolist(),action=int(a),next_observation=np.asarray(nxt).tolist(),reward=float(r)))
                obs=nxt
            predicted,_=d.model('support',np.asarray([r['observation'] for r in support]),np.asarray(actions))
            std=np.sqrt(wm.obs_rms.var+wm.obs_rms.epsilon)
            mae=float(np.mean(np.abs(predicted-np.asarray([r['next_observation'] for r in support]))/std))
            proposals={label:d.action(label,f,obs,s['evidence'],'proposal_'+label+'_') for label in c['controllers']}
            tails=iid_sequences(s['evidence']+1,16,15,3)
            plans={label:np.column_stack((np.full(16,proposals[label]),tails)) for label in c['controllers']}
            evidence=planner_evidence(plans,obs,host.instrument,reward,n_actions=3,ledger=d.ledger,clock=clock,fingerprint=lambda:state_hash(wm))
            return dict(features=h.feature_vector(evidence,mae),evidence=evidence,support_prediction_mae=mae,proposed_actions=proposals)
        data,receipt=host.perform(ops,body,dict(stage='probe',role=role,family=f,bundle=b,episode=e))
        nonlocal observed_calls,observed_forwards
        observed_calls+=host.instrument.calls;observed_forwards+=host.instrument.network_forwards
        pending[f,b,e]=(env,np.asarray(obs).copy(),h.simulator_fingerprint(env))
        pair=dict(family=f,bundle=b,episode=e,role=role,phase=role,prefix=support,support_hash=digest(tuple(support)),
            restoration_hash=pending[f,b,e][2],features=data['features'],evidence=data['evidence'],
            proposed_actions=data['proposed_actions'],support_prediction_mae=data['support_prediction_mae'],probe_receipt=asdict(receipt),paths={},returns={})
        probe_records[f,b,e]=pair;p['pairs'].append(pair);p['active_work']=None;persist()
        return pair,receipt

    def continuation(f,b,e,label):
        nonlocal observed_calls,observed_forwards
        wm=models[f,b];host.bind(wm);pair=probe_records[f,b,e];original,obs,expected=pending[f,b,e]
        if e in c['evaluation_episodes'] and (not p.get('predecision_sha256') or sha(PREDICTIONS)!=p['predecision_sha256']):raise ValueError('all_choices_persisted_before_hidden_returns')
        env,restored=h.restore_copy(original)
        if restored!=expected:raise ValueError('restoration_changed')
        s=h.seeds(c,f,e);steps=[];total=Work();last_report=None
        p['active_work']=dict(stage='continuation',family=f,bundle=b,episode=e,controller=label,
            upper=dict(real_steps=192,imagined_transitions=294912,model_calls=12864,network_forwards=12864));persist()
        try:
            for tick in range(8,200):
                ops=h.planning_ops(label,obs,'')+(Operation('environment','environment',Work(real_steps=1)),)
                def body(d):
                    a=d.action(label,f,obs,s['planner']+tick,'')
                    nxt,r,term,trunc,_=d.environment('environment',env,a)
                    published=pendulum_step_reward(obs,a,nxt) if f=='pendulum' else acrobot_step_reward(obs,a,nxt)
                    if not np.isclose(float(published[0]),r,atol=1e-5,rtol=0):raise ValueError('reward_timing')
                    if term or bool(trunc)!=(tick==199):raise ValueError('episode_boundary')
                    return dict(tick=tick,obs=np.asarray(obs).tolist(),next_obs=np.asarray(nxt).tolist(),action=a,reward=float(r),terminated=bool(term),truncated=bool(trunc),planner_seed=s['planner']+tick)
                step,report=host.perform(ops,body,dict(stage='continuation',family=f,bundle=b,episode=e,controller=label,tick=tick,
                    predecision_sha256=p.get('predecision_sha256') if e in c['evaluation_episodes'] else None))
                steps.append(step);total=total.plus(report.physical_completed_reported);last_report=report
                obs=np.asarray(step['next_obs'],dtype=np.float32)
            # Summary of192 verified receipts, not another executed ledger.
            # Full per-call events remain in the lossless journal, once only.
            combined_report=replace(last_report,physical_reserved=total,physical_completed_reported=total,logical_charged=total,
                events=(),completed_keys=tuple(f'tick_{i}' for i in range(8,200)))
            pair['paths'][label]=dict(restored_hash=restored,steps=steps)
            pair['returns'][label]=sum(x['reward'] for x in steps)
            if state_hash(wm)!=initial[f,b]:raise ValueError('evaluation_updated_model')
            observed_calls+=host.instrument.calls;observed_forwards+=host.instrument.network_forwards
            p['active_work']=None;persist()
            return dict(evaluation_rewards=[x['reward'] for x in steps],support_hash=pair['support_hash'],
                metrics=dict(receipt_semantics='Sum of192 completed decision receipts; full events in journal')),combined_report
        finally:env.close()

    try:
        with journal:
            for f,b,e in sorted(h.grid(c,'training')):
                probe(f,b,e,'training')
                for label in c['controllers']:continuation(f,b,e,label)
                pending.pop((f,b,e))[0].close()
            study=StagedStudy(h.manifest(c,p['execution_sha']))
            training=[r for r in p['pairs'] if r['role']=='training']
            study.fit_source(training,lambda rows:h.ProbeSelector(rows,c),lambda selector:selector.fingerprint())
            selector=study.policy;p['selector_hash']=selector.fingerprint()
            frozen=dict(state=selector.state(),training_pairs=training,selector_hash=p['selector_hash'],execution_sha=p['execution_sha'],config_sha256=sha(CONFIG))
            with FROZEN.open('x') as handle:json.dump(frozen,handle,allow_nan=False)
            p['frozen_selector_sha256']=sha(FROZEN)
            with PREDICTIONS.open('x') as handle:
                for f,b,e in sorted(h.grid(c,'evaluation')):
                    pair,receipt=probe(f,b,e,'evaluation')
                    decision=selector.decide(f,b,pair['features']);decision.update(recipe_hash=selector.fingerprint(),family=f,bundle=b,episode=e,support_hash=pair['support_hash'])
                    pair['decision']=decision
                    study.adapt_support(f'{f}:{b}',pair['prefix'],lambda policy,rows:dict(decision=decision,features=pair['features']),receipt,episode=e)
                    handle.write(json.dumps(decision)+'\n');handle.flush();persist()
            p['predecision_sha256']=sha(PREDICTIONS);persist()
            def evaluate(case,policy,context):
                f,b=case['task'].split(':');return continuation(f,int(b),case['episode'],case['condition'])
            p['staged_study']=study.evaluate(evaluate)
            for value in pending.values():value[0].close()
            for r in p['models']:r['after']=state_hash(models[r['family'],r['bundle']])
            p['observed_model_calls']=observed_calls;p['observed_forwards']=observed_forwards
            p['resources']=host.resources();h.validate(p,c);p['analysis']=h.analyze(p['pairs'],c)
            if selector.fingerprint()!=p['selector_hash']:raise ValueError('post_evaluation_selector_changed')
            if any(sha(ROOT/r['path'])!=r['sha256'] for r in files):raise ValueError('frozen_files_changed')
            p['declared_complete']=True
    except BaseException as exc:
        p['failure']=f'{type(exc).__name__}: {exc}';raise
    finally:
        p['resources']=host.resources();p['journal_parts']=[dict(path=str(path.relative_to(ROOT)),sha256=sha(path)) for path in journal.paths]
        p['worker_cpu_s']=time.process_time();save(p)


def run():
    c=json.loads(CONFIG.read_text());a=json.loads(ALLOCATION.read_text())
    if a['authorized'] is not True or a['runs']!=1 or sha(CONFIG)!=a['config_sha256'] or sha(PROTOCOL)!=a['protocol_sha256']:raise ValueError('locked_allocation')
    if c['time_cap_s']>900 or c['real_cap']>100000:raise ValueError('standing_caps')
    if subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT).returncode:raise ValueError('clean_committed_implementation_required')
    for key in ('previous_validation','checkpoint_inventory'):
        if sha(ROOT/c[key])!=c[key+'_sha256']:raise ValueError('parent_provenance')
    ledger=json.loads((ROOT/c['previous_validation']).read_text())['session_ledger']
    if ledger['used_after_s']!=c['session_used_before_s'] or c['time_cap_s']>c['session_remaining_before_s']:raise ValueError('carried_session_allowance')
    if any(x.exists() for x in ((RESULT,) if ROLLOUT_PROFILE else (RESULT,FROZEN,PREDICTIONS))):raise ValueError('one_run_only')
    old={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'artifacts').rglob('*.json'))}
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();start=time.perf_counter()
    with USAGE.open('x') as handle:json.dump(dict(consumed=True,parent_pid=os.getpid(),start_monotonic=start,execution_sha=revision,allocation_sha256=sha(ALLOCATION)),handle)
    paths=['scripts/run_e3_11_post_probe.py','src/nexus/evolution2/post_probe.py','src/nexus/evolution2/staged_study.py','src/nexus/evolution2/planner_evidence.py','src/nexus/evolution2/full_policy_source.py','src/nexus/evolution2/generated_strategies.py','src/nexus/evolution2/planner_adapter.py','src/nexus/evolution1/resources.py','src/nexus/world/dynamics.py','src/nexus/world/rewards.py','src/nexus/tasks/spec.py','src/nexus/tasks/wrappers.py']
    if ROLLOUT_PROFILE:paths.append('src/nexus/evolution2/rollout_headroom.py')
    if CALIBRATION_PROFILE:paths.extend(['src/nexus/evolution2/calibration_execution.py','src/nexus/evolution2/forecast_calibration.py'])
    if HORIZON_PROFILE:paths.append('src/nexus/evolution2/horizon_calibration.py')
    save(dict(execution_sha=revision,config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),code_sha256={n:sha(ROOT/n) for n in paths},historical_json_sha256=old,declared_complete=False,pairs=[],models=[],active_work=None))
    env=dict(os.environ,NEXUS_E311_PARENT=str(os.getpid()),PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT/'.deps'),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
    error=None
    try:
        profile=['--horizon-calibration'] if HORIZON_PROFILE else (['--calibration'] if CALIBRATION_PROFILE else (['--rollout-audit'] if ROLLOUT_PROFILE else []))
        proc=subprocess.run([sys.executable,__file__,'--worker']+profile,env=env,cwd=ROOT,timeout=c['time_cap_s']-(time.perf_counter()-start),capture_output=True,text=True)
        if proc.returncode:error=proc.stderr[-4000:]
    except subprocess.TimeoutExpired:error='time_cap'
    wall=time.perf_counter()-start;p=json.loads(RESULT.read_text())
    if error or wall>c['time_cap_s']:p.update(declared_complete=False,failure=error or 'time_cap')
    preserved=all(sha(ROOT/n)==v for n,v in old.items())
    if not preserved:p.update(declared_complete=False,failure='historical_file_changed')
    p['historical_json_preserved']=len(old) if preserved else False;p['wall_s']=wall
    p['session_ledger']=dict(used_before_s=c['session_used_before_s'],used_after_s=c['session_used_before_s']+wall,remaining_after_s=c['session_remaining_before_s']-wall)
    save(p);print(json.dumps(dict(complete=p['declared_complete'],wall_s=wall,failure=p.get('failure'),label=p.get('analysis',{}).get('label'))))
    return int(not p['declared_complete'])


def verify():
    start=time.perf_counter();p=json.loads(RESULT.read_text());c=json.loads(CONFIG.read_text())
    from nexus.evolution2 import post_probe as h
    if not p['declared_complete'] or p['config_sha256']!=sha(CONFIG):raise ValueError('complete_locked_result')
    h.validate(p,c)
    if h.analyze(p['pairs'],c)!=p['analysis']:raise ValueError('analysis_replay')
    if sha(PREDICTIONS)!=p['predecision_sha256'] or sha(FROZEN)!=p['frozen_selector_sha256']:raise ValueError('frozen_choices')
    for n,v in p['historical_json_sha256'].items():
        if sha(ROOT/n)!=v:raise ValueError('historical_artifact_changed')
    # Verify executed work directly from lossless journal events, not cached returns.
    counts={k:0 for k in ('real_steps','imagined_transitions','model_calls','network_forwards')};records=0
    for part in p['journal_parts']:
        if sha(ROOT/part['path'])!=part['sha256']:raise ValueError('journal_hash')
        with gzip.open(ROOT/part['path'],'rt') as handle:
            for line in handle:
                records+=1;entry=json.loads(line);r=entry['report'];meta=entry['meta']
                if meta['stage']=='continuation' and meta['episode'] in c['evaluation_episodes'] and meta['predecision_sha256']!=p['predecision_sha256']:raise ValueError('choices_before_outcomes_provenance')
                if r['status']!='complete_execution':raise ValueError('journal_incomplete')
                events=[(e['kind'],json.loads(e['payload_json'])) for e in r['events']]
                reserved={e['operation']:e['physical'] for kind,e in events if kind=='reserved'}
                settled=[e['operation'] for kind,e in events if kind=='settled' and e['outcome']=='success']
                if len(settled)!=len(set(reserved)):raise ValueError('journal_settlement')
                for key in settled:
                    for name,cost in reserved[key].items():counts[name]+=cost
    if counts!=p['resources']['completed']:raise ValueError('journal_cost_accounting')
    frozen=json.loads(FROZEN.read_text())['state']
    from nexus.evolution1.catalogue import digest
    if digest(frozen)!=p['selector_hash']:raise ValueError('saved_selector_hash')
    import numpy as np
    from run_e3_10_metered_model import reward_replay
    for pair in p['pairs']:
        for forecast in pair['evidence'].values():
            if not np.allclose(reward_replay(dict(family=pair['family'],observation=pair['prefix'][-1]['next_observation']),forecast),forecast['scores'],rtol=0,atol=1e-8):raise ValueError('forecast_reward_replay')
        if pair['role']!='evaluation':continue
        key=f'{pair["family"]}:{pair["bundle"]}';model=frozen['models'][pair['family']]
        predicted=frozen['means'][key]+float((np.asarray(pair['features'])/model['scale'])@np.asarray(model['beta']))
        if abs(predicted-pair['decision']['estimated_advantage'])>1e-8:raise ValueError('frozen_prediction_replay')
        if pair['decision']['choices']['contextual_selector']!=('rank_blend' if predicted>0 else 'successor_anchor'):raise ValueError('predicted_choice_replay')
    for n,v in p['code_sha256'].items():
        raw=subprocess.check_output(['git','show',f'{p["execution_sha"]}:{n}'],cwd=ROOT)
        if hashlib.sha256(raw).hexdigest()!=v:raise ValueError('execution_code_provenance')
    elapsed=time.perf_counter()-start
    result=dict(valid=True,capture_sha256=sha(RESULT),journal_records=records,resources_verified=counts,model_inference=False,new_real_steps=0,new_imagined_transitions=0,wall_s=elapsed,
        session_ledger=dict(used_before_s=p['session_ledger']['used_after_s'],used_after_s=p['session_ledger']['used_after_s']+elapsed,remaining_after_s=p['session_ledger']['remaining_after_s']-elapsed))
    with VALIDATION.open('x') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps(result));return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);parser.add_argument('--verify',action='store_true');group=parser.add_mutually_exclusive_group();group.add_argument('--rollout-audit',action='store_true');group.add_argument('--calibration',action='store_true');group.add_argument('--horizon-calibration',action='store_true');args=parser.parse_args()
    if args.calibration or args.horizon_calibration:
        configure_horizon() if args.horizon_calibration else configure_calibration()
        from nexus.evolution2 import calibration_execution
        api=sys.modules[__name__]
        if args.worker:calibration_execution.worker(api)
        elif args.verify:raise SystemExit(calibration_execution.verify(api))
        else:
            calibration_execution.preflight(api)
            raise SystemExit(run())
    elif args.rollout_audit:
        configure_rollout()
        if args.worker or args.verify:
            from nexus.evolution2 import rollout_headroom
            api=sys.modules[__name__]
            if args.worker:rollout_headroom.worker(api)
            else:raise SystemExit(rollout_headroom.verify(api))
        else:raise SystemExit(run())
    elif args.worker:worker()
    else:raise SystemExit(verify() if args.verify else run())
