"""One preregistered authored-fixture benchmark, not an environment study."""
import argparse
from dataclasses import asdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import signal
import subprocess
import time
from nexus.evolution2.learning_cycle import LearningCycle,FixtureHost,METHODS
from nexus.evolution1.fixtures import Event,verify_journal

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'configs/bounded_learning_cycle.json'
PROTOCOL=ROOT/'docs/NEXUS_BOUNDED_LEARNING_CYCLE_PROTOCOL.md'
RESULT=ROOT/'artifacts/bounded_learning_cycle.json'
USAGE=ROOT/'artifacts/bounded_learning_cycle_usage.json'
ALLOCATION=ROOT/'configs/bounded_learning_cycle_allocation.json'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def settings():
    c=json.loads(CONFIG.read_text())
    fixed=dict(version='bounded_learning_cycle_fixture_v1',seeds=list(range(7,19)),methods=list(METHODS),
        training_tasks=['A','B','A','C'],transfer_tasks=['D','E','F'],steps_per_task=4,host_call_cap=256,
        time_cap_s=60,minimum_utility_gain=.02,maximum_forgetting=.05)
    if any(c.get(k)!=v for k,v in fixed.items()):raise ValueError('locked_fixture_configuration')
    return c


def metrics(row):
    train=row['training'];transfer=row['transfer']
    return dict(transfer_proposal=statistics.mean(r['after'] for r in transfer['probes']),
        return_A=train['probes'][2]['after'],forgetting=train['probes'][0]['retained_A']-train['probes'][1]['retained_A'],
        improvement_per_unit=train['gain']/max(1,train['declared_training_cost_units']),
        deployed_transfer=statistics.mean(r['deployed_gain'] for r in transfer['probes']))


def validate(p,c):
    expected=set(itertools.product(c['seeds'],c['methods']));ids=[(r['seed'],r['method']) for r in p['rows']]
    if len(ids)!=len(expected) or set(ids)!=expected:raise ValueError('complete_locked_fixture_grid')
    for row in p['rows']:
        for split,tasks in [('training',c['training_tasks']),('transfer',c['transfer_tasks'])]:
            value=row[split]
            if type(value['fixture_calls']) is not int or type(value['declared_training_cost_units']) is not int:raise ValueError('integer_fixture_accounting')
            if [r['task'] for r in value['probes']]!=tasks or not 0<=value['fixture_calls']<=c['host_call_cap']:raise ValueError('complete_task_stream')
            if len(value['trace'])>len(tasks)*4 or value['declared_training_cost_units']!=2*len(value['trace']):raise ValueError('matched_bounded_attempts')
            events=tuple(Event(**r) for r in value['journal'])
            if not verify_journal(events):raise ValueError('immutable_attempt_journal')
            start=value['journal_start_event']
            if type(start) is not int or not 0<=start<len(events):raise ValueError('journal_segment')
            segment=events[start:];attempts=[json.loads(e.payload_json) for e in segment if e.kind=='training_attempt']
            if [json.loads(e.payload_json)['task'] for e in segment if e.kind=='task_started']!=tasks or len(attempts)!=len(value['trace']):raise ValueError('complete_logged_task_attempts')
            from nexus.evolution1.catalogue import digest
            for attempt,trace in zip(attempts,value['trace']):
                if attempt['task']!=trace['task'] or attempt['action']!=trace['action'] or digest(attempt['child'])!=trace['child'] or digest(attempt['parent'])!=trace['parent']:raise ValueError('lineage_replay')
                gain=attempt['child_utility']-attempt['parent_utility']
                if gain!=trace['gain'] or trace['effective_gain']!=(0. if trace['action']=='gather_evidence' else gain):raise ValueError('feedback_replay')
            if value['gain']!=sum(r['effective_gain'] for r in value['trace']):raise ValueError('gain_accounting')
            for r in value['probes']:
                if any(type(r[k]) not in (int,float) or not math.isfinite(r[k]) for k in ('before','after','retained_A','deployed_gain')):raise ValueError('finite_fixture_metrics')
            for r in value['trace']:
                if any(type(r[k]) not in (int,float) or not math.isfinite(r[k]) for k in ('gain','effective_gain')):raise ValueError('finite_fixture_feedback')
            if any(type(value[k]) is not int or value[k]!=0 for k in ('new_real_steps','model_inference')):raise ValueError('fixture_only')
    return True


def analyze(p,c):
    validate(p,c);lookup={(r['seed'],r['method']):metrics(r) for r in p['rows']}
    def contrast(a,b,metric):
        x=[lookup[s,a][metric]-lookup[s,b][metric] for s in c['seeds']];m=statistics.mean(x);half=2.2009851601*statistics.stdev(x)/math.sqrt(len(x))
        return dict(mean=m,ci95=[m-half,m+half],per_seed=x,unit='12 authored fixture banks, not pretrained models')
    pairs=dict(mutation=contrast('generation_only','random_generation','transfer_proposal'),
        memory=contrast('unified','reset_memory','return_A'),scheduler_random=contrast('unified','random_schedule','improvement_per_unit'),
        scheduler_fixed=contrast('unified','fixed_schedule','improvement_per_unit'),rule_fixed=contrast('unified','fixed_update','transfer_proposal'),
        rule_random=contrast('unified','random_update','transfer_proposal'),cycle=contrast('unified','fixed_generation','deployed_transfer'),
        feedback_shuffled=contrast('unified','shuffled_feedback','transfer_proposal'))
    passed=lambda name:pairs[name]['mean']>=c['minimum_utility_gain'] and pairs[name]['ci95'][0]>0
    forgetting=statistics.mean(lookup[s,'unified']['forgetting'] for s in c['seeds'])
    screens=dict(E3_12=passed('mutation'),E3_13=passed('memory') and forgetting<=c['maximum_forgetting'],
        E3_14=passed('scheduler_random') and passed('scheduler_fixed'),E4_0=passed('rule_fixed') and passed('rule_random'),E4_1=passed('cycle'))
    return dict(kind='authored_fixture_results_only',contrasts=pairs,fixture_screens=screens,unified_mean_forgetting=forgetting,
        real_environment_capabilities_established=False,warning='Descriptor utilities are authored; these are not controller returns or proof of learning-to-learn.')


def save(p):
    temp=RESULT.with_suffix('.tmp');temp.write_text(json.dumps(p,allow_nan=False,separators=(',',':'))+'\n');temp.replace(RESULT)


def run():
    c=settings()
    grant=json.loads(ALLOCATION.read_text())
    if grant.get('authorized') is not True or grant.get('runs')!=1 or grant.get('config_sha256')!=sha(CONFIG) or grant.get('protocol_sha256')!=sha(PROTOCOL) or grant.get('time_cap_s')!=c['time_cap_s']:raise ValueError('locked_fixture_allocation')
    if RESULT.exists() or USAGE.exists():raise ValueError('fixture_run_already_consumed')
    if subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT).returncode:raise ValueError('committed_protocol_required')
    prior=json.loads((ROOT/c['previous_validation']).read_text())['session_ledger']
    if prior['used_after_s']!=c['session_used_before_s'] or c['time_cap_s']>c['session_remaining_before_s']:raise ValueError('carried_budget')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    old={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'artifacts').rglob('*.json')}
    code=['scripts/run_bounded_learning_cycle.py','src/nexus/evolution2/learning_cycle.py','src/nexus/evolution2/generated_strategies.py','src/nexus/evolution2/continual_state.py','src/nexus/evolution1/toy_loop.py','src/nexus/evolution1/promotion.py','src/nexus/evolution1/fixtures.py','src/nexus/meta/controller.py']
    p=dict(execution_sha=revision,code_sha256={n:sha(ROOT/n) for n in code},allocation_sha256=sha(ALLOCATION),config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),rows=[],declared_complete=False,
        historical_json_sha256=old,scientific=False,new_real_steps=0,new_imagined_transitions=0,neural_inference=0)
    with USAGE.open('x') as f:json.dump(dict(consumed=True,config_sha256=sha(CONFIG),execution_sha=revision),f)
    start=time.perf_counter();cpu=time.process_time();save(p)
    def timeout(*unused):raise TimeoutError('fixture_time_cap')
    previous_handler=signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,c['time_cap_s'])
    try:
        for seed,method in itertools.product(c['seeds'],c['methods']):
            if time.perf_counter()-start>=c['time_cap_s']:raise TimeoutError('fixture_time_cap')
            row_start=time.perf_counter();row_cpu=time.process_time()
            cycle=LearningCycle(seed,method);training=cycle.run(FixtureHost(seed,c['host_call_cap']))
            transfer_cycle=cycle.transfer_copy();transfer=transfer_cycle.run(FixtureHost(seed,c['host_call_cap']),tasks=('D','E','F'))
            p['rows'].append(dict(seed=seed,method=method,selected_rule=transfer_cycle.selected_rule,training=training,transfer=transfer,
                measured_wall_s=time.perf_counter()-row_start,measured_cpu_s=time.process_time()-row_cpu));save(p)
        p['analysis']=analyze(p,c);p['declared_complete']=True
    except BaseException as exc:p['failure']=f'{type(exc).__name__}: {exc}';raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous_handler)
        elapsed=time.perf_counter()-start;p['wall_s']=elapsed;p['cpu_s']=time.process_time()-cpu
        if elapsed>c['time_cap_s']:p['declared_complete']=False;p['failure']='fixture_time_cap'
        p['historical_json_preserved']=all(sha(ROOT/n)==v for n,v in old.items())
        p['session_ledger']=dict(used_before_s=c['session_used_before_s'],used_after_s=c['session_used_before_s']+elapsed,remaining_after_s=c['session_remaining_before_s']-elapsed)
        if not p['historical_json_preserved']:p['declared_complete']=False;p['failure']='historical_file_changed'
        save(p)
    print(json.dumps(dict(complete=p['declared_complete'],wall_s=p['wall_s'],analysis=p.get('analysis'))))


def verify():
    start=time.perf_counter()
    p=json.loads(RESULT.read_text());c=settings()
    if not p['declared_complete'] or p['config_sha256']!=sha(CONFIG) or p['protocol_sha256']!=sha(PROTOCOL):raise ValueError('complete_locked_capture_required')
    if analyze(p,c)!=p['analysis']:raise ValueError('fixture_analysis_replay')
    if any(sha(ROOT/n)!=v for n,v in p['historical_json_sha256'].items()):raise ValueError('history_changed')
    for n,value in p['code_sha256'].items():
        raw=subprocess.check_output(['git','show',f'{p["execution_sha"]}:{n}'],cwd=ROOT)
        if hashlib.sha256(raw).hexdigest()!=value:raise ValueError('execution_source_hash')
    elapsed=time.perf_counter()-start;prior=p['session_ledger']
    result=dict(valid=True,kind='fixture_only',rows=len(p['rows']),capture_sha256=sha(RESULT),real_steps=0,model_inference=0,
        wall_s=elapsed,session_ledger=dict(used_before_s=prior['used_after_s'],used_after_s=prior['used_after_s']+elapsed,remaining_after_s=prior['remaining_after_s']-elapsed))
    with (ROOT/'artifacts/bounded_learning_cycle_validation.json').open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    verify() if args.verify else run()
