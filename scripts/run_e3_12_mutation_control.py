"""One-run real source-control binding; --verify uses saved data only."""
import argparse
from dataclasses import asdict,replace
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'configs/e3_12_mutation_control.json'
PROTOCOL=ROOT/'docs/NEXUS_E3_12_MUTATION_CONTROL_PROTOCOL.md'
ALLOCATION=ROOT/'configs/e3_12_mutation_control_allocation.json'
RESULT=ROOT/'artifacts/e3_12_mutation_control.json'
USAGE=ROOT/'artifacts/e3_12_mutation_usage.json'
VALIDATION=ROOT/'artifacts/e3_12_mutation_validation.json'
JOURNAL=ROOT/'artifacts/e3_12_mutation_resources.jsonl.gz'
OPERATOR_PROFILE=False
PARTIAL_PROFILE=False


def configure_operator():
    """Separate balanced-panel study; original one-run outputs stay immutable."""
    global CONFIG,PROTOCOL,ALLOCATION,RESULT,USAGE,VALIDATION,JOURNAL,OPERATOR_PROFILE,PARTIAL_PROFILE
    OPERATOR_PROFILE=True;PARTIAL_PROFILE=False
    CONFIG=ROOT/'configs/e3_12b_operator_headroom.json'
    PROTOCOL=ROOT/'docs/NEXUS_E3_12B_OPERATOR_HEADROOM_PROTOCOL.md'
    ALLOCATION=ROOT/'configs/e3_12b_operator_headroom_allocation.json'
    RESULT=ROOT/'artifacts/e3_12b_operator_headroom.json'
    USAGE=ROOT/'artifacts/e3_12b_operator_usage.json'
    VALIDATION=ROOT/'artifacts/e3_12b_operator_validation.json'
    JOURNAL=ROOT/'artifacts/e3_12b_operator_resources.jsonl.gz'


def configure_partial():
    global CONFIG,PROTOCOL,ALLOCATION,RESULT,USAGE,VALIDATION,JOURNAL,PARTIAL_PROFILE
    configure_operator();PARTIAL_PROFILE=True
    CONFIG=ROOT/'configs/e3_12c_partial_feedback.json'
    PROTOCOL=ROOT/'docs/NEXUS_E3_12C_PARTIAL_FEEDBACK_PROTOCOL.md'
    ALLOCATION=ROOT/'configs/e3_12c_partial_feedback_allocation.json'
    RESULT=ROOT/'artifacts/e3_12c_partial_feedback.json'
    USAGE=ROOT/'artifacts/e3_12c_partial_usage.json'
    VALIDATION=ROOT/'artifacts/e3_12c_partial_validation.json'
    JOURNAL=ROOT/'artifacts/e3_12c_partial_resources.jsonl.gz'


def study_module():
    if PARTIAL_PROFILE:
        from nexus.evolution2 import partial_feedback
        return partial_feedback
    if OPERATOR_PROFILE:
        from nexus.evolution2 import operator_headroom
        return operator_headroom
    from nexus.evolution2 import mutation_control
    return mutation_control


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,data):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(data,allow_nan=False,separators=(',',':'))+'\n');tmp.replace(p)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def preflight(c):
    from nexus.evolution2.mutation_control import requested_seeds
    import run_e3_11_post_probe as previous
    previous.CONFIG=CONFIG;previous.ALLOCATION=ALLOCATION
    old={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'artifacts').rglob('*.json')}
    audit=previous.seed_audit(c,old,requested_seeds(c))
    if sha(ROOT/c['checkpoint_inventory'])!=c['checkpoint_inventory_sha256']:raise ValueError('inventory_hash')
    inventory=read(ROOT/c['checkpoint_inventory'])['integrity']
    if any(sha(ROOT/r['path'])!=r['sha256'] for r in inventory['checkpoints']+inventory['source_arrays']):raise ValueError('frozen_input_provenance')
    return old,audit,inventory


def worker():
    use=read(USAGE)
    if os.getppid()!=use['parent_pid'] or os.environ.get('NEXUS_MUTATION_PARENT')!=str(os.getppid()):raise ValueError('metered_parent_required')
    import numpy as np
    import torch
    from nexus.world.dynamics import WorldModel,DynamicsMLP
    from nexus.evolution1.resources import Clock,Operation,Work
    from nexus.evolution1.catalogue import digest
    from nexus.evolution2 import post_probe as hostapi
    study=study_module()
    from nexus.evolution2.full_policy_source import DecisionJournal,controllers,operation_plan,state_hash,task_spec
    from nexus.evolution2.generated_strategies import StrategyGenerator
    from nexus.evolution2.measured_mutation import observe_measured_pair
    from nexus.tasks.spec import make_task_env
    torch.set_num_threads(1);cpu=time.process_time_ns();c=read(CONFIG);p=read(RESULT)
    inventory=read(ROOT/c['checkpoint_inventory'])['integrity']
    clock=lambda:Clock(time.process_time_ns()-cpu,int((time.perf_counter()-use['start_monotonic'])*1e9))
    journal=DecisionJournal(JOURNAL,1000);host=hostapi.Host(c,clock,journal)
    def persist():p['resources']=host.resources();write(RESULT,p)
    try:
        with journal:
            for item in inventory['checkpoints']:
                f,b=item['family'],item['bundle'];wm=WorldModel.load(ROOT/item['path'])
                if type(wm.net) is not DynamicsMLP or str(wm.device)!='cpu' or wm.kind!='residual' or tuple(wm.net.hidden)!=(64,64):raise ValueError('frozen_cpu_model_profile')
                wm.net.eval();before=state_hash(wm);host.bind(wm)
                generators={m:StrategyGenerator(c['proposal_seed'],adaptive=m=='learned',mutation_credit=True) for m in study.METHODS}
                for e in c['training_episodes']+c['evaluation_episodes']:
                    role='training' if e in c['training_episodes'] else 'evaluation'
                    reset,planner=study.seed_pair(c,f,b,e);env=make_task_env(task_spec(f),seed=reset);obs,_=env.reset(seed=reset)
                    parent=controllers()['successor_anchor'];partner=controllers()['flat_anchor'].left
                    row=dict(family=f,bundle=b,episode=e,role=role,initial_observation=np.asarray(obs).tolist(),
                        restored_hash=hostapi.simulator_fingerprint(env),before={m:g.mutation_probabilities() for m,g in generators.items()},strategies={},paths={})
                    protocol=dict(phase=role,pair_id=f'{f}:{b}:{e}',context_hash=digest(row['initial_observation']),reset_seed=reset,
                        planner_seed=planner,horizon=200,planning_cap=1536,checkpoint_sha256=item['sha256'],reward_sha256=p['reward_sha256'])
                    row['protocol']=protocol;p['rows'].append(row)
                    children=(study.operators() if OPERATOR_PROFILE else
                        {m:g.paired_child(parent,partner,study.proposal_uniform(c,f,b,e)) for m,g in generators.items()})
                    if PARTIAL_PROFILE and role=='training':
                        row['training_operator']=study.training_operator(c,f,b,e)
                        children={row['training_operator']:children[row['training_operator']]}
                    if OPERATOR_PROFILE and role=='evaluation':
                        row['decision']=study.decide(p['rows'][:-1],c,f,b,generators['learned'])
                    row['strategies']={m:s.payload() for m,s in children.items()}
                    strategies=dict(parent=parent,**children)
                    if role=='evaluation' and not OPERATOR_PROFILE:strategies['fixed_blend']=controllers()['rank_blend']
                    receipts={}
                    try:
                        for name,strategy in strategies.items():
                            copy,restored=hostapi.restore_copy(env);current=np.asarray(obs).copy();start=time.process_time();total=Work()
                            path=dict(steps=[],restored_hash=restored,return_value=0.)
                            row['paths'][name]=path;p['active_work']=dict(family=f,bundle=b,episode=e,condition=name,tick=0);persist()
                            try:
                                for tick in range(200):
                                    if time.perf_counter()-use['start_monotonic']>=c['time_cap_s']:raise TimeoutError('experiment_cap')
                                    p['active_work']['tick']=tick
                                    ops=operation_plan(strategy,current,3)
                                    def body(d):
                                        action=d.action_strategy(strategy,f,current,planner+tick,'')
                                        nxt,r,term,trunc,_=d.environment('environment',copy,action)
                                        return action,nxt,r,term,trunc
                                    value,receipt=host.perform(ops,body,dict(family=f,bundle=b,episode=e,role=role,condition=name,tick=tick))
                                    action,nxt,r,term,trunc=value;total=total.plus(receipt.physical_completed_reported)
                                    step=dict(tick=tick,obs=current.tolist(),next_obs=np.asarray(nxt).tolist(),action=int(action),reward=float(r),terminated=bool(term),truncated=bool(trunc),planner_seed=planner+tick)
                                    study.check_real_step(step,current.tolist(),tick,planner+tick,f);path['steps'].append(step);current=np.asarray(nxt)
                                    if tick%50==49:persist()
                                path['cpu_s']=time.process_time()-start;path['return']=sum(x['reward'] for x in path['steps']);path.pop('return_value')
                                # Aggregate a completed path for bridge validation only.
                                # Physical calls are counted solely in the per-decision journal.
                                receipts[name]=replace(receipt,physical_reserved=total,physical_completed_reported=total,logical_charged=total,events=())
                            finally:copy.close()
                        if role=='training':
                            updates=([(kind,generators['learned']) for kind in children] if OPERATOR_PROFILE else list(generators.items()))
                            for m,g in updates:
                                feedback_protocol=(dict(protocol,pair_id=protocol['pair_id']+':'+m) if OPERATOR_PROFILE else protocol)
                                paths={}
                                for label,strategy in [('parent',parent),('child',children[m])]:
                                    path=row['paths']['parent' if label=='parent' else m]
                                    paths[label]=dict(**feedback_protocol,strategy=strategy.fingerprint,rewards=[s['reward'] for s in path['steps']],cpu_s=path['cpu_s'])
                                observe_measured_pair(g,parent,children[m],paths,dict(parent=receipts['parent'],child=receipts[m]),feedback_protocol,return_scale=c['return_scale'])
                        row['after']={m:g.mutation_probabilities() for m,g in generators.items()};p['active_work']=None;persist()
                    finally:env.close()
                p['final_policies'][f'{f}:{b}']={m:g.mutation_probabilities() for m,g in generators.items()}
                p['learning_journals'][f'{f}:{b}']={m:[asdict(x) for x in g.journal.snapshot()] for m,g in generators.items()}
                p['models'].append(dict(family=f,bundle=b,before=before,after=state_hash(wm),
                    parameter_count=sum(x.numel() for x in wm.net.parameters()),checkpoint_sha256=item['sha256']))
                for k,v in [('model_calls',host.instrument.calls),('network_forwards',host.instrument.network_forwards),('imagined_transitions',host.instrument.rows)]:p['observed'][k]+=v
                persist()
        study.validate(p,c);p['analysis']=study.analyze(p['rows'],c);p['declared_complete']=True;p['status']='complete_valid'
    except BaseException as error:
        p['status']='incomplete_or_invalid';p['error']=repr(error);raise
    finally:
        p['cpu_s']=(time.process_time_ns()-cpu)/1e9;p['max_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        p['journals']=[dict(path=str(x.relative_to(ROOT)),sha256=sha(x)) for x in journal.paths]
        import gymnasium
        p['dependencies']=dict(python=sys.version,numpy=np.__version__,torch=torch.__version__,gymnasium=gymnasium.__version__);persist()


def run():
    c=read(CONFIG);a=read(ALLOCATION)
    if a['config_sha256']!=sha(CONFIG) or a['protocol_sha256']!=sha(PROTOCOL) or a['authorized'] is not True or a['runs']!=1 or a['automatic_retry'] is not False:raise ValueError('locked_one_run_allocation')
    if c['time_cap_s']>min(900,a['session_remaining_before_s']) or c['real_cap']>100000:raise ValueError('standing_caps')
    if any(c[k]!=a[k] for k in ('time_cap_s','real_cap','imagined_cap','model_call_cap','network_forward_cap')):raise ValueError('allocation_caps')
    if git('status','--porcelain','--untracked-files=no'):raise ValueError('clean_committed_implementation_required')
    if any(p.exists() for p in (RESULT,USAGE,VALIDATION)) or list(JOURNAL.parent.glob(JOURNAL.name.replace('.jsonl.gz','*'))):raise ValueError('one_run_consumed')
    old,audit,inventory=preflight(c);start=time.perf_counter()
    use=dict(start_monotonic=start,parent_pid=os.getpid(),source_commit=git('rev-parse','HEAD'),config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION))
    with USAGE.open('x') as f:f.write(json.dumps(use)+'\n')
    write(RESULT,dict(status='started',declared_complete=False,provenance=use,historical_json_sha256=old,seed_audit=audit,
        rows=[],models=[],final_policies={},learning_journals={},observed=dict(model_calls=0,network_forwards=0,imagined_transitions=0),
        inputs=inventory['checkpoints']+inventory['source_arrays'],reward_sha256=sha(ROOT/'src/nexus/world/rewards.py')))
    env={**os.environ,'NEXUS_MUTATION_PARENT':str(os.getpid()),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','VECLIB_MAXIMUM_THREADS':'1'}
    profile=['--partial-feedback'] if PARTIAL_PROFILE else ['--operator-headroom'] if OPERATOR_PROFILE else []
    child=subprocess.Popen([sys.executable,__file__,'--worker',*profile],cwd=ROOT,env=env)
    try:code=child.wait(timeout=c['time_cap_s'])
    except subprocess.TimeoutExpired:child.kill();child.wait();code=-9
    p=read(RESULT);p['wall_s']=time.perf_counter()-start;p['exit_code']=code
    p['historical_preserved']=all(sha(ROOT/n)==h for n,h in old.items())
    p['inputs_preserved']=all(sha(ROOT/r['path'])==r['sha256'] for r in p['inputs'])
    if code or not p['historical_preserved'] or not p['inputs_preserved']:
        p['status']='incomplete_or_invalid';p['declared_complete']=False
        # A killed worker may not flush its last per-call receipt. Do not report
        # the last persisted counters as an exact final physical measurement.
        complete=p.get('resources',{}).get('completed',{})
        p['unreported_work_upper']={key:max(0,c[cap]-complete.get(key,0)) for key,cap in
            [('real_steps','real_cap'),('imagined_transitions','imagined_cap'),('model_calls','model_call_cap'),('network_forwards','network_forward_cap')]}
    p['session_used_after_s']=a['session_used_before_s']+p['wall_s'];p['session_remaining_after_s']=3600-p['session_used_after_s'];write(RESULT,p)
    print(json.dumps({k:p.get(k) for k in ('status','wall_s','resources','analysis','error')}))
    if code:raise SystemExit(1)


def verify():
    study=study_module()
    start=time.perf_counter();p=read(RESULT);c=read(CONFIG)
    if not p['declared_complete'] or p['status']!='complete_valid':raise ValueError('execution_not_complete')
    if sha(CONFIG)!=p['provenance']['config_sha256'] or sha(PROTOCOL)!=p['provenance']['protocol_sha256']:raise ValueError('locked_provenance')
    study.validate(p,c)
    if study.analyze(p['rows'],c)!=p['analysis']:raise ValueError('analysis_replay')
    if any(sha(ROOT/n)!=h for n,h in p['historical_json_sha256'].items()) or any(sha(ROOT/r['path'])!=r['sha256'] for r in p['inputs']):raise ValueError('preservation')
    total=dict(real_steps=0,imagined_transitions=0,model_calls=0,network_forwards=0);count=0
    for item in p['journals']:
        path=ROOT/item['path']
        if sha(path)!=item['sha256']:raise ValueError('journal_hash')
        with gzip.open(path,'rt') as stream:
            for line in stream:
                row=json.loads(line);r=row['report'];count+=1
                if r['status']!='complete_execution' or any(r['physical_unknown_upper_bound'].values()):raise ValueError('journal_complete')
                for key in total:total[key]+=r['physical_completed_reported'][key]
    if total!=p['resources']['completed'] or count!=c['real_cap']:raise ValueError('journal_sum')
    elapsed=time.perf_counter()-start
    result=dict(valid=True,result_sha256=sha(RESULT),journal_decisions=count,resources=total,verification_s=elapsed,
        session_used_after_s=p['session_used_after_s']+elapsed,session_remaining_after_s=p['session_remaining_after_s']-elapsed,
        historical_json_preserved=len(p['historical_json_sha256']),source_commit=p['provenance']['source_commit'])
    if VALIDATION.exists():raise ValueError('verification_record_exists')
    write(VALIDATION,result);print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');parser.add_argument('--verify',action='store_true');parser.add_argument('--preflight',action='store_true');profiles=parser.add_mutually_exclusive_group();profiles.add_argument('--operator-headroom',action='store_true');profiles.add_argument('--partial-feedback',action='store_true');args=parser.parse_args()
    if args.operator_headroom:configure_operator()
    if args.partial_feedback:configure_partial()
    if args.worker:worker()
    elif args.verify:verify()
    elif args.preflight:print(json.dumps(preflight(read(CONFIG))[1]))
    else:run()
