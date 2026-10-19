"""Independent stdlib arithmetic/truth check; never imports Seed's learner."""
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def verify():
    raw=(ROOT/'configs/seed_s0_s1.json').read_bytes();c=json.loads(raw)
    p=json.loads((ROOT/'artifacts/seed_s0_s1_dev.json').read_text())
    if p['declared_complete'] is not True or p['config_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('complete_locked_capture_required')
    tasks={t['id']:t for t in c['semantic_tasks']}
    expected={(t,m) for t in tasks for m in c['methods']}
    keys=[(r['task_id'],r['method']) for r in p['rows']]
    if set(keys)!=expected or len(keys)!=len(expected):raise ValueError('independent_complete_grid')
    counts={m:0 for m in c['methods']};costs={};truth_checks=0;action_checks=0
    for r in p['rows']:
        target=tasks[r['task_id']]['literals']
        truth=lambda o:all((o[k]==v)!=neg for k,v,neg in target)
        if len(r['labels'])!=c['teacher_answer_budget'] or len(r['queries'])!=c['query_layouts_per_task']:raise ValueError('independent_label_query_grid')
        if r['costs']['teacher_answers']!=len(r['labels']):raise ValueError('independent_label_cost')
        for e in r['labels']:
            if type(e['positive']) is not bool or e['positive']!=truth(e['object']):raise ValueError('teacher_label_truth')
            truth_checks+=1
        for k,v in r['costs'].items():
            if type(v) is not int or v<0:raise ValueError('cost_type')
            costs[k]=costs.get(k,0)+v
        for q in r['queries']:
            if type(q['correct']) is not bool or not math.isfinite(q['wall_ms']):raise ValueError('query_metric_type')
            expected_ids=[o['id'] for o in q['objects'] if truth(o)]
            if q['expected']!=expected_ids or len(expected_ids)!=1:raise ValueError('query_truth')
            trace=q['response']['trace'];acted=q['response']['type']=='acted'
            correct=acted and all(t['object']==expected_ids[0] for t in trace)
            if correct!=q['correct'] or acted and len(trace)!=(1 if q['layout']==0 else 2):raise ValueError('recorded_action_truth')
            positions={o['id']:[o['x'],o['y']] for o in q['objects']}
            for t in trace:
                if t['before']!=positions[t['object']] or t['steps']!=1:raise ValueError('trace_before')
                dx,dy={'right':(1,0),'down':(0,1)}[t['direction']]
                after=[t['before'][0]+dx,t['before'][1]+dy]
                if t['after']!=after or any(not 0<=v<6 for v in after):raise ValueError('trace_after')
                positions[t['object']]=after;action_checks+=1
            counts[r['method']]+=correct
    if costs!=p['analysis']['costs'] or costs!=p['reserved_fixture_costs']:raise ValueError('independent_cost_arithmetic')
    for m in counts:
        if counts[m]!=p['analysis']['methods'][m]['correct']:raise ValueError('independent_accuracy')
    for k,v in p['previous_artifact_hashes'].items():
        if hashlib.sha256((ROOT/k).read_bytes()).hexdigest()!=v:raise ValueError('prior_artifact_changed')
    return dict(valid=True,correct_programs=counts,teacher_truth_checks=truth_checks,
                action_endpoint_checks=action_checks,costs=costs,
                previous_artifacts_preserved=len(p['previous_artifact_hashes']))


if __name__=='__main__':print(json.dumps(verify(),indent=2))
