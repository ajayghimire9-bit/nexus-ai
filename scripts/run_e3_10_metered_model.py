"""One-run, parent-timeboxed engineering inference check; no environment calls."""
import argparse
from dataclasses import asdict
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'configs/e3_10_metered_model.json'
PROTOCOL=ROOT/'docs/NEXUS_E3_10_METERED_MODEL_PROTOCOL.md'
ALLOCATION=ROOT/'configs/e3_10_metered_model_allocation.json'
RESULT=ROOT/'artifacts/e3_10_metered_model.json'
USAGE=ROOT/'artifacts/e3_10_metered_model_usage.json'
VALIDATION=ROOT/'artifacts/e3_10_metered_model_validation.json'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(p):
    temporary=RESULT.with_suffix('.tmp')
    temporary.write_text(json.dumps(p,indent=2,allow_nan=False)+'\n')
    temporary.replace(RESULT)


def expected(c):
    if c['families']!=['pendulum','acrobot'] or c['model_bundles']!=[0,1] or c['observation_indices']!=[0,1]:raise ValueError('locked_model_observation_axes')
    if c['candidates']!=16 or c['horizon']!=16 or c['candidate_sets']!=['incumbent','challenger']:raise ValueError('locked_candidate_profile')
    return set(itertools.product(c['families'],c['model_bundles'],c['observation_indices']))


def reward_replay(row,forecast):
    import numpy as np
    from nexus.world.rewards import pendulum_step_reward,acrobot_step_reward
    reward=pendulum_step_reward if row['family']=='pendulum' else acrobot_step_reward
    actions=np.asarray(forecast['actions'],dtype=np.int64)
    state=np.repeat(np.asarray(row['observation'],dtype=np.float32)[None,:],len(actions),axis=0)
    survival=np.ones(len(actions));scores=np.zeros(len(actions))
    for t,(nxt,prob) in enumerate(zip(forecast['states'],forecast['termination_estimates'])):
        nxt=np.asarray(nxt,dtype=np.float32);prob=np.asarray(prob,dtype=np.float64)
        scores+=survival*reward(state,actions[:,t],nxt)
        survival*=1-prob;state=nxt
    return scores


def validate(p,c):
    import numpy as np
    grid=expected(c);keys=[(r['family'],r['bundle'],r['observation_index']) for r in p['rows']]
    if len(keys)!=len(grid) or set(keys)!=grid:raise ValueError('complete_model_observation_grid')
    totals={k:0 for k in ('real_steps','imagined_transitions','model_calls','network_forwards')}
    for row in p['rows']:
        if set(row['evidence'])!=set(c['candidate_sets']) or set(row['reference'])!=set(c['candidate_sets']):raise ValueError('complete_condition_grid')
        for name in c['candidate_sets']:
            a=row['evidence'][name];b=row['reference'][name]
            actions=np.asarray(a['actions']);states=np.asarray(a['states']);probs=np.asarray(a['termination_estimates'])
            d=3 if row['family']=='pendulum' else 6
            if actions.shape!=(16,16) or states.shape!=(16,16,d) or probs.shape!=(16,16):raise ValueError('complete_forecast_shapes')
            if actions.dtype.kind not in 'iu' or np.any(actions<0) or np.any(actions>=3):raise ValueError('discrete_candidate_actions')
            for values in (states,probs,a['scores'],b['scores']):
                if np.asarray(values).dtype.kind not in 'if' or not np.isfinite(values).all():raise ValueError('finite_numeric_forecasts')
            if np.any(probs<0) or np.any(probs>1):raise ValueError('termination_probability')
            if a['actions']!=b['actions'] or a['states']!=b['states'] or a['termination_estimates']!=b['termination_estimates']:raise ValueError('exact_forecast_equality')
            if not np.allclose(a['scores'],b['scores'],rtol=c['score_rtol'],atol=c['score_atol']):raise ValueError('scores_differ')
            if a['selected_candidate']!=b['selected_candidate'] or a['selected_candidate']!=int(np.argmax(a['scores'])):raise ValueError('selection_differ')
            if list(np.argsort(a['scores'],kind='stable'))!=list(np.argsort(b['scores'],kind='stable')):raise ValueError('ranking_differ')
            if not np.allclose(reward_replay(row,a),a['scores'],rtol=0,atol=c['score_atol']):raise ValueError('reward_timing_or_survival')
        report=row['receipt']
        if report['status']!='complete_execution' or any(report['physical_unknown_upper_bound'].values()):raise ValueError('complete_resource_receipt')
        if row['fingerprint_before']!=row['fingerprint_after']:raise ValueError('frozen_model_changed')
        work=report['physical_completed_reported']
        if work!=dict(real_steps=0,imagined_transitions=1024,model_calls=64,network_forwards=64):raise ValueError('cell_resource_grid')
        if row['observed']!=dict(model_calls=64,imagined_transitions=1024,network_forwards=64,denied_forwards=0):raise ValueError('observed_hook_counts')
        keys={f'{path}_{name}_{t}' for path in ('evidence','reference') for name in c['candidate_sets'] for t in range(16)}
        if len(report['completed_keys'])!=64 or set(report['completed_keys'])!=keys:raise ValueError('complete_operation_receipt')
        for k in totals:totals[k]+=work[k]
    if totals!=dict(real_steps=0,imagined_transitions=8192,model_calls=512,network_forwards=512):raise ValueError('aggregate_resources')
    readiness=json.loads((ROOT/c['source_readiness_path']).read_text())
    if sha(ROOT/c['source_readiness_path'])!=c['source_readiness_sha256']:raise ValueError('pinned_readiness_provenance')
    files=readiness['integrity']['checkpoints']+readiness['integrity']['source_arrays']
    paths={r['path']:r['sha256'] for r in files}
    if len(p['files_after'])!=len(paths) or {r['path']:r['sha256'] for r in p['files_after']}!=paths or any(r['matches'] is not True for r in p['files_after']):raise ValueError('frozen_files_changed')
    return totals


def worker():
    # Internal child entry, not a second independently authorized launcher.
    use=json.loads(USAGE.read_text())
    if os.environ.get('NEXUS_E310_PARENT')!=str(os.getppid()) or use['parent_pid']!=os.getppid():raise ValueError('parent_launch_required')
    c=json.loads(CONFIG.read_text());p=json.loads(RESULT.read_text())
    import numpy as np
    import torch
    from nexus.evolution1.resources import Work,Operation,Clock,Limits,ReservationLedger
    from nexus.evolution2.planner_adapter import score_open_loop,iid_sequences
    from nexus.evolution2.planner_evidence import planner_evidence,evidence_operations,ForwardCheckedStep
    from nexus.evolution2.full_policy_source import state_hash
    from nexus.world.dynamics import WorldModel,DynamicsMLP
    from nexus.world.rewards import pendulum_step_reward,acrobot_step_reward
    torch.set_num_threads(1)
    cpu=time.process_time_ns()
    clock=lambda:Clock(time.process_time_ns()-cpu,int((time.perf_counter()-use['start_monotonic'])*1e9))
    readiness=json.loads((ROOT/c['source_readiness_path']).read_text())
    files=readiness['integrity']['checkpoints']+readiness['integrity']['source_arrays']
    if any(sha(ROOT/r['path'])!=r['sha256'] for r in files):raise ValueError('frozen_file_integrity')
    checkpoint_rows=readiness['integrity']['checkpoints']
    if {(r['family'],r['bundle']) for r in checkpoint_rows}!=set(itertools.product(c['families'],c['model_bundles'])) or len(checkpoint_rows)!=4:raise ValueError('checkpoint_grid')
    p['dependencies']=dict(python=platform.python_version(),numpy=np.__version__,torch=torch.__version__)
    p['model_loads']=[]
    for index,r in enumerate(checkpoint_rows):
        load_start=time.perf_counter()
        wm=WorldModel.load(ROOT/r['path'])
        p['model_loads'].append(dict(family=r['family'],bundle=r['bundle'],wall_s=time.perf_counter()-load_start))
        if type(wm) is not WorldModel or type(wm.net) is not DynamicsMLP or wm.net.arch!='mlp' or wm.kind!='residual' or wm.device.type!='cpu' or getattr(wm,'uses_simulator',False):raise ValueError('vetted_cpu_residual_mlp_only')
        wm.net.eval();before=state_hash(wm)
        source=next(s for s in readiness['integrity']['source_arrays'] if s['family']==r['family'] and s['bundle']==r['bundle'] and '_train.npz' in s['path'])
        with np.load(ROOT/source['path'],allow_pickle=False) as data:
            observations=np.asarray(data['obs'][:2],dtype=np.float32).copy()
        if observations.shape!=(2,wm.net.obs_dim):raise ValueError('source_observation_schema')
        reward=pendulum_step_reward if r['family']=='pendulum' else acrobot_step_reward
        for observation_index in c['observation_indices']:
            cell_start=time.perf_counter();cell_cpu=time.process_time()
            obs=observations[observation_index]
            plans={name:iid_sequences(c['candidate_seed']+index*100+observation_index*2+j,16,16,3) for j,name in enumerate(c['candidate_sets'])}
            ops=evidence_operations(plans,3)
            ops+=tuple(Operation(op.key.replace('evidence_','reference_',1),'model',op.cost) for op in ops)
            work=Work(imagined_transitions=1024,model_calls=64,network_forwards=64)
            ledger=ReservationLedger(ops,Limits(work,work,int(c['time_cap_s']*1e9),int(c['time_cap_s']*1e9)))
            instrument=ForwardCheckedStep(wm)
            p['active_cell']=dict(family=r['family'],bundle=r['bundle'],observation_index=observation_index,unknown_upper=asdict(work));save(p)
            try:
                evidence=planner_evidence(plans,obs,instrument,reward,n_actions=3,ledger=ledger,clock=clock,fingerprint=lambda:state_hash(wm))
                reference={}
                for name,actions in plans.items():
                    states=[];terms=[]
                    class Direct:
                        def step(self,o,a):
                            ticket=ledger.reserve(f'reference_{name}_{len(states)}',clock())
                            try:
                                nxt,prob=instrument.step_reserved(o,a,ticket)
                                states.append(nxt.copy().tolist());terms.append(prob.copy().tolist())
                            except BaseException:
                                ledger.settle(ticket,'failed',clock());raise
                            ledger.settle(ticket,'success',clock());return nxt,prob
                    scores=score_open_loop(Direct(),obs,actions,reward)
                    reference[name]=dict(actions=actions.tolist(),states=states,termination_estimates=terms,scores=scores.tolist(),selected_candidate=int(np.argmax(scores)))
                row=dict(family=r['family'],bundle=r['bundle'],observation_index=observation_index,
                    observation=obs.tolist(),checkpoint_sha256=r['sha256'],source_sha256=source['sha256'],
                    parameter_count=sum(t.numel() for t in wm.net.parameters()),
                    evidence=evidence,reference=reference,fingerprint_before=before,fingerprint_after=state_hash(wm),
                    observed=dict(model_calls=instrument.calls,imagined_transitions=instrument.rows,
                        network_forwards=instrument.network_forwards,denied_forwards=instrument.denied_forwards))
            except BaseException:
                p['failed_receipt']=asdict(ledger.close(clock()));p['active_cell']=None;save(p);raise
            row['receipt']=asdict(ledger.close(clock()));row['wall_s']=time.perf_counter()-cell_start;row['cpu_s']=time.process_time()-cell_cpu
            p['rows'].append(row);p['active_cell']=None;save(p)
    p['files_after']=[dict(path=r['path'],sha256=r['sha256'],matches=sha(ROOT/r['path'])==r['sha256']) for r in files]
    p['resources']=validate(p,c);p['declared_complete']=True
    import resource
    p['worker_process_cpu_s']=time.process_time()
    p['worker_peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
    p['outcome']='metered_inference_equivalence_verified';save(p)


def run():
    c=json.loads(CONFIG.read_text());a=json.loads(ALLOCATION.read_text());expected(c)
    if not a['authorized'] or a['runs']!=1 or a['config_sha256']!=sha(CONFIG) or a['protocol_sha256']!=sha(PROTOCOL):raise ValueError('exact_allocation')
    if c['time_cap_s']!=30 or c['imagined_cap']!=8192 or c['real_cap']!=0 or c['model_call_cap']!=512 or c['network_forward_cap']!=512:raise ValueError('locked_caps')
    if sha(ROOT/c['source_readiness_path'])!=c['source_readiness_sha256']:raise ValueError('readiness_hash')
    prior=json.loads((ROOT/c['source_readiness_path']).read_text())['session_ledger']
    if prior['used_s']!=c['session_used_before_s'] or c['time_cap_s']>c['session_remaining_before_s']:raise ValueError('carried_session_budget')
    if subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT).returncode:raise ValueError('clean_tracked_implementation_required')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if RESULT.exists():raise ValueError('result_already_exists')
    old={str(x.relative_to(ROOT)):sha(x) for x in sorted((ROOT/'artifacts').rglob('*.json'))}
    start=time.perf_counter()
    with USAGE.open('x') as handle:json.dump(dict(consumed=True,automatic_retry=False,parent_pid=os.getpid(),start_monotonic=start,execution_sha=revision,allocation_sha256=sha(ALLOCATION)),handle)
    paths=['scripts/run_e3_10_metered_model.py','src/nexus/evolution2/planner_evidence.py','src/nexus/world/dynamics.py','src/nexus/world/planning.py','src/nexus/world/rewards.py','src/nexus/evolution2/planner_adapter.py','src/nexus/evolution1/resources.py']
    save(dict(kind='engineering_inference_check',execution_sha=revision,config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),
        code_sha256={x:sha(ROOT/x) for x in paths},declared_complete=False,outcome='incomplete',rows=[],active_cell=None,
        historical_json_sha256=old,scope=c['scope']))
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',
        PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT/'.deps'),PYTHONDONTWRITEBYTECODE='1',NEXUS_E310_PARENT=str(os.getpid()))
    error=None
    try:
        proc=subprocess.run([sys.executable,__file__,'--worker'],cwd=ROOT,env=env,
            timeout=max(.001,c['time_cap_s']-(time.perf_counter()-start)),capture_output=True,text=True)
        if proc.returncode:error='worker_failed: '+proc.stderr[-4000:]
    except subprocess.TimeoutExpired:error='execution_time_cap'
    elapsed=time.perf_counter()-start;p=json.loads(RESULT.read_text())
    if error or elapsed>c['time_cap_s']:
        p['declared_complete']=False;p['outcome']='incomplete_time_cap' if error=='execution_time_cap' or elapsed>c['time_cap_s'] else 'invalid_execution';p['error']=error
    preserved=all(sha(ROOT/n)==h for n,h in old.items())
    if not preserved:p.update(declared_complete=False,outcome='invalid_historical_preservation')
    p['historical_json_preserved']=len(old) if preserved else False
    p['wall_s']=elapsed
    p['session_ledger']=dict(used_before_s=c['session_used_before_s'],used_after_s=c['session_used_before_s']+elapsed,
        remaining_after_s=c['session_remaining_before_s']-elapsed)
    save(p);print(json.dumps(dict(complete=p['declared_complete'],outcome=p['outcome'],wall_s=elapsed)))
    return int(not p['declared_complete'])


def verify():
    start=time.perf_counter();p=json.loads(RESULT.read_text());c=json.loads(CONFIG.read_text())
    if not p['declared_complete'] or p['config_sha256']!=sha(CONFIG):raise ValueError('completed_locked_capture_required')
    totals=validate(p,c)
    if not all(sha(ROOT/n)==h for n,h in p['historical_json_sha256'].items()):raise ValueError('historical_preservation')
    for n,h in p['code_sha256'].items():
        raw=subprocess.check_output(['git','show',f'{p["execution_sha"]}:{n}'],cwd=ROOT)
        if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('execution_source_provenance')
    elapsed=time.perf_counter()-start
    result=dict(valid=True,capture_sha256=sha(RESULT),resources_verified=totals,model_inference=False,
        new_real_steps=0,new_imagined_transitions=0,wall_s=elapsed,
        session_ledger=dict(used_before_s=p['session_ledger']['used_after_s'],used_after_s=p['session_ledger']['used_after_s']+elapsed,
            remaining_after_s=p['session_ledger']['remaining_after_s']-elapsed))
    with VALIDATION.open('x') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps(result));return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--verify',action='store_true',help='Saved forecast/reward/resource replay only, no inference.')
    args=parser.parse_args()
    if args.worker:worker()
    else:raise SystemExit(verify() if args.verify else run())
