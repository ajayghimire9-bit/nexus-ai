"""Saved-trial reconstruction, no model calls or benchmark result-builder import."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

METHODS = ('tools_retrieval', 'ordinary_cache', 'nexus_capsules')


def parse_records(raw):
    records=[]
    for i,line in enumerate(raw.splitlines()):
        try:records.append(json.loads(line))
        except ValueError:records.append(dict(kind='invalid_record',line=i,bytes=len(line)))
    return records


def paired(values):
    if len(values) != 4 or any(type(x) not in (float, int) or not math.isfinite(x) for x in values):
        raise ValueError('four finite paired file-block differences required')
    mean = statistics.mean(values)
    half = 3.182446305 * statistics.stdev(values) / 2
    rng = random.Random(90213)
    boot = sorted(statistics.mean(rng.choices(values, k=4)) for _ in range(10000))
    return dict(mean=mean, median=statistics.median(values), t95=[mean-half, mean+half],
                bootstrap95=[boot[249], boot[9749]], independent_blocks=4,
                identical_differences_warning=len(set(values)) == 1)


def reconstruct(records, config):
    trials = [r for r in records if r['kind'] == 'trial']
    expected = {(rep, m, phase, c['id']) for rep in range(config['cold_repetitions'])
                for m in METHODS for phase in ('cold', 'warm') for c in config['cases']}
    found = set()
    for row in trials:
        if type(row['repeat']) is not int:raise ValueError('integer repetition required')
        cell = (row['repeat'], row['method'], row['phase'], row['task_id'])
        if cell in found or cell not in expected:
            raise ValueError('duplicate/unplanned trial')
        found.add(cell)
        result = row['result']
        if type(row['correct']) is not bool:
            raise ValueError('boolean correctness required')
        for value in [result['workflow_s'], row['cold_startup_s'], row['amortized_startup_s']] + list(result['stages'].values()):
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('finite measured durations required')
        for count in result['counters'].values():
            if type(count) is not int or count < 0:
                raise ValueError('integer executed counters required')
        t = result['telemetry']
        if t['application_cache_hit'] and (t['inference_ran'] is not False or t['generated_tokens'] != 0 or t['input_tokens'] != 0):
            raise ValueError('application cache charged stale inference')
        for k in ('input_tokens', 'generated_tokens', 'prompt_cache_tokens'):
            if t[k] is not None and (type(t[k]) is not int or t[k] < 0):
                raise ValueError('token count must be integer or explicitly unavailable')
    startups=[r for r in records if r['kind']=='startup']
    starts={(r['repeat'],r['method']) for r in startups}
    planned_starts={(r,m) for r in range(config['cold_repetitions']) for m in METHODS}
    if len(starts)!=len(startups) or not starts<=planned_starts:raise ValueError('duplicate/unplanned startup')
    for r in startups:
        if r['metadata']['model_sha256']!=config['model_sha256']:raise ValueError('wrong model hash')
    integrations=[r for r in records if r['kind']=='live_integration']
    complete = (found == expected and starts==planned_starts and len(integrations)==1 and
                integrations[0]['passed'] is True and
                not any(r['kind'] in ('invalid_record','configuration_failure') for r in records))
    summary = {}
    for method in METHODS:
        rows = [r for r in trials if r['method'] == method]
        if not rows:
            continue
        telemetry = [r['result']['telemetry'] for r in rows]
        summary[method] = dict(trials=len(rows), correct=sum(r['correct'] for r in rows),
            accuracy=statistics.mean(r['correct'] for r in rows),
            failures=sum(r['result']['status'] == 'failure' for r in rows),
            mean_workflow_s=statistics.mean(r['result']['workflow_s'] for r in rows),
            mean_user_visible_s=statistics.mean(r['result']['workflow_s'] + r['cold_startup_s'] for r in rows),
            mean_total_amortized_s=statistics.mean(r['result']['workflow_s'] + r['amortized_startup_s'] for r in rows),
            cold_mean_s=(statistics.mean(r['result']['workflow_s'] for r in rows if r['phase']=='cold')
                         if any(r['phase']=='cold' for r in rows) else None),
            warm_mean_s=(statistics.mean(r['result']['workflow_s'] for r in rows if r['phase']=='warm')
                         if any(r['phase']=='warm' for r in rows) else None),
            confirmed_model_calls=sum(t['inference_ran'] is True for t in telemetry),
            unknown_model_call_outcomes=sum(t['inference_ran'] is None for t in telemetry),
            application_cache_hits=sum(t['application_cache_hit'] for t in telemetry),
            input_tokens_known_sum=sum(t['input_tokens'] for t in telemetry if t['input_tokens'] is not None),
            generated_tokens_known_sum=sum(t['generated_tokens'] for t in telemetry if t['generated_tokens'] is not None),
            unavailable_token_requests=sum(t['input_tokens'] is None or t['generated_tokens'] is None for t in telemetry),
            candidate_executions=sum(r['result']['counters']['candidate_executions'] for r in rows),
            questions=sum(r['result']['counters']['questions'] for r in rows),
            abstractions=sum(r['result']['counters']['abstractions'] for r in rows),
            capsule_hits=sum(r['result']['counters']['capsule_hit'] for r in rows),
            maximum_library_bytes=max(r['result']['library_bytes'] for r in rows))
    contrasts = {}
    files = [f['id'] for f in config['files']]
    if complete:
        cells = {(r['repeat'], r['method'], r['phase'], r['task_id']): r for r in trials}
        for baseline in METHODS[:2]:
            timing, accuracy = [], []
            for file in files:
                task_ids = [c['id'] for c in config['cases'] if c['file'] == file]
                diffs, gains = [], []
                for rep in range(config['cold_repetitions']):
                    for phase in ('cold', 'warm'):
                        for task in task_ids:
                            b, c = cells[(rep,baseline,phase,task)], cells[(rep,'nexus_capsules',phase,task)]
                            diffs.append((b['result']['workflow_s']+b['amortized_startup_s']) -
                                         (c['result']['workflow_s']+c['amortized_startup_s']))
                            gains.append(int(c['correct'])-int(b['correct']))
                timing.append(statistics.mean(diffs)); accuracy.append(statistics.mean(gains))
            contrasts[baseline] = dict(baseline_minus_nexus_latency_s=paired(timing),
                                       nexus_minus_baseline_correctness=paired(accuracy))
    passed = complete and summary['nexus_capsules']['accuracy'] >= config['success_rule']['minimum_task_accuracy'] and all(
        summary['nexus_capsules']['accuracy'] >= summary[b]['accuracy'] and
        summary['nexus_capsules']['mean_total_amortized_s'] <= .95*summary[b]['mean_total_amortized_s'] and
        contrasts[b]['baseline_minus_nexus_latency_s']['t95'][0] > 0 for b in METHODS[:2])
    # Retrospective cumulative break-even over the registered sequence; this is
    # descriptive and not extrapolated from a favorable one-off timing sample.
    break_even = {}
    if complete:
        for b in METHODS[:2]:
            points = []
            for i in range(len(config['cases'])):
                ids = {c['id'] for c in config['cases'][:i+1]}
                def total(m):
                    return sum(r['result']['workflow_s']+r['amortized_startup_s'] for r in trials
                               if r['method']==m and r['phase']=='cold' and r['task_id'] in ids)
                points.append(total(b)-total('nexus_capsules'))
            first = next((i+1 for i in range(len(points)) if all(x > 0 for x in points[i:])), None)
            break_even[b] = dict(first_sustained_task_count=first, cumulative_savings_s=points,
                                 label='descriptive measured sequence, not established reuse threshold')
    causal=[]
    if found==expected:
        indexed={(r['repeat'],r['method'],r['phase'],r['task_id']):r for r in trials}
        for rep in range(config['cold_repetitions']):
            for m in METHODS:
                for phase in ('cold','warm'):
                    one=indexed[(rep,m,phase,'repeat_1')]['result'];two=indexed[(rep,m,phase,'same_file_different_instruction')]['result']
                    causal.append(one['status']=='executed' and two['status']=='executed' and
                                  one['program']!=two['program'] and one['output']!=two['output'])
    return dict(declared_complete=complete, missing_trials=len(expected-found), expected_trials=len(expected),
                methods=summary, paired_file_block_contrasts=contrasts, passed=bool(passed),
                same_file_instruction_change_fraction=statistics.mean(causal) if causal else None,
                invalid_raw_records=sum(r['kind']=='invalid_record' for r in records),
                break_even=break_even, verdict=('PASS_DEVELOPMENT_SCREEN' if passed else
                           'FAIL_DEVELOPMENT_SCREEN' if complete else 'INCOMPLETE'),
                statistical_scope='four authored file blocks; repeated timings are not independent task/model replications')


def verify_outputs(records, config, directory):
    """Independent reference calculation from saved CSV, never model inference."""
    import csv
    from nexus.seed.real_data_evaluator_worker import evaluate_serialized_adapter_program
    cases = {c['id']: c for c in config['cases']}
    for trial in (r for r in records if r['kind']=='trial'):
        case = cases[trial['task_id']]
        path = Path(directory)/(case['file']+'.csv')
        if hashlib.sha256(path.read_bytes()).hexdigest() != trial['input_file_sha256']:
            raise ValueError('input hash mismatch')
        with path.open(newline='') as f:
            reader = csv.DictReader(f); names=reader.fieldnames; rows=list(reader)
        goal=case['expected']; output=None; status=goal['op']
        if status in ('rows','sum'):
            k,v=names; parsed=[]
            for r in rows:
                try: n=float(r[v])
                except ValueError: continue
                if goal['min'] is None or n>=goal['min']:parsed.append({k:r[k].strip().lower(),v:n})
            if status=='sum':
                groups={}
                for r in parsed:groups[r[k]]=groups.get(r[k],0)+r[v]
                output=[{k:x,'total':round(y,2)} for x,y in groups.items()]; order='total'
            else:output=parsed;order=v
            output.sort(key=lambda r:r[k]);output.sort(key=lambda r:r[order],reverse=goal['order']=='desc')
            status='executed'
        correct=trial['result']['status']==status and trial['result']['output']==output
        if correct != trial['correct']:raise ValueError('forged correctness')
        if trial['result']['status']=='executed':
            executed=evaluate_serialized_adapter_program(trial['result']['program'],rows)
            if executed!=trial['result']['output']:raise ValueError('saved program/output mismatch')


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('artifact',type=Path);args=p.parse_args()
    artifact=json.loads(args.artifact.read_text()); root=Path(__file__).resolve().parents[1]
    config_path=artifact['registration'].get('config_path','configs/seed_assistant_benchmark_v2.json')
    if config_path not in ('configs/seed_assistant_benchmark_v2.json','configs/seed_assistant_benchmark_v2_1.json'):
        raise ValueError('unregistered configuration path')
    content=(root/config_path).read_bytes();config=json.loads(content)
    if hashlib.sha256(content).hexdigest()!=artifact['registration']['config_sha256']:
        raise ValueError('configuration hash mismatch')
    raw=(args.artifact.parent/artifact['raw_file']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=artifact['raw_sha256']:raise ValueError('raw digest mismatch')
    records=parse_records(raw)
    verify_outputs(records,config,args.artifact.parent/artifact['inputs_directory'])
    summary=reconstruct(records,config)
    if artifact['resources']['stop_reason'] or artifact['resources']['worker_returncode']!=0:
        summary['declared_complete']=False;summary['passed']=False;summary['verdict']='INCOMPLETE'
    if artifact['summary']!=summary:raise ValueError('summary mismatch')
    print(json.dumps(dict(valid=True,summary=summary),indent=2))


if __name__=='__main__':main()
