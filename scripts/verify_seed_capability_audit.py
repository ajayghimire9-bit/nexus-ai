"""Independent saved-event arithmetic/reference audit; no model inference.

Controller replay verifies completeness; a separate elementary interpreter checks
outputs. Neither authenticates a maliciously replaced whole execution log.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nexus.seed.capability_evidence import (digest, make_task, catalogue, train_public, parameters,
    EventMeter, SharedLedger)
from nexus.seed.combined_investigation_engine import EqualizedInvestigationEngineV2, EqualizedControllerConfig


def reference(ops, values):
    out = list(values)
    for op in ops:
        if op == 'reverse': out = out[::-1]
        elif op == 'increment': out = [v+1 for v in out]
        elif op == 'double': out = [2*v for v in out]
        elif op == 'abs_val': out = [abs(v) for v in out]
        elif op == 'filter_even': out = [v for v in out if v%2 == 0]
        elif op == 'unique_stable': out = list(dict.fromkeys(out))
        else: raise ValueError('unknown_opcode')
    return out


def paired(values):
    if len(values) < 2: return dict(mean=statistics.mean(values), interval=None, n=len(values))
    mean = statistics.mean(values)
    if len(values) != 3: raise ValueError('locked_three_seed_analysis')
    half = 4.302652729911275*statistics.stdev(values)/math.sqrt(3)
    return dict(mean=mean, interval=[mean-half, mean+half], n=3, values=values)


def verify_records(records, config, summary=None):
    if len(set(config['seeds'])) != len(config['seeds']) or len(set(config['methods'])) != len(config['methods']):
        raise ValueError('duplicate_locked_grid')
    events = [r for r in records if r.get('kind')=='execution']
    previous = '0'*64
    for i, event in enumerate(events, 1):
        obj = dict(event)
        claimed = obj.pop('hash')
        if claimed != digest(obj) or event['index'] != i or event['previous'] != previous:
            raise ValueError('event_chain')
        if type(event['elapsed_s']) not in (int,float) or not math.isfinite(event['elapsed_s']) or event['elapsed_s'] < 0:
            raise ValueError('invalid_time')
        previous = claimed
    if not events: raise ValueError('missing_events')
    manifest = [r for r in records if r.get('kind')=='audit_manifest']
    if len(manifest)!=1 or manifest[0]['config_hash']!=digest(config): raise ValueError('config_manifest')
    expected = {(s,m,i) for s in config['seeds'] for m in config['methods'] for i in range(config['assessment_tasks'])}
    episodes = [r for r in records if r.get('kind')=='episode']
    keys = [(r['seed'],r['method'],r['task']) for r in episodes]
    if len(keys)!=len(set(keys)) or set(keys)!=expected: raise ValueError('episode_grid')
    locks = [r for r in records if r.get('kind')=='choice']
    if len(locks)!=len(episodes) or len({r['scope'] for r in locks})!=len(locks): raise ValueError('choice_grid')
    if any(not row['frozen_capsules'] for row in locks): raise ValueError('capsule_mutation')
    # No target, assessment or answer-derived candidate payload in learner locks.
    for row in locks:
        if set(row)!={'kind','scope','selected','selected_ops','policy_hash','capsule_hash','frozen_capsules'}:
            raise ValueError('private_or_unexpected_choice_field')
    all_by_scope = {}
    for j, row in enumerate(records): all_by_scope.setdefault(row.get('scope'), []).append((j,row))
    pool = {cid:ops for cid, ops, _ in catalogue(config)}
    metrics = {}
    raw_seed = {}
    primitive_invocations = 0
    # Independently reconstruct every task outcome and cost from individual events.
    for episode in episodes:
        seed, method, i = episode['seed'], episode['method'], episode['task']
        scope = f'{seed}:{method}:{i}'
        if episode['scope'] != scope: raise ValueError('scope_alias')
        task, target, rows = make_task(config, seed, 'assessment', i)
        seq = all_by_scope[scope]
        lock_index, lock = next((j,r) for j,r in seq if r['kind']=='choice')
        refs = [(j,r) for j,r in seq if r.get('operation')=='assessment_reference']
        actual = [(j,r) for j,r in seq if r.get('operation')=='assessment_candidate']
        if len(refs)!=3 or len(actual)!=3 or any(j<lock_index for j,_ in refs+actual): raise ValueError('assessment_order_or_count')
        if lock['selected'] not in pool or list(pool[lock['selected']])!=lock['selected_ops']: raise ValueError('selection')
        if [r['argument'] for _,r in refs] != rows or [r['argument'] for _,r in actual]!=rows: raise ValueError('assessment_inputs')
        for _, event in seq:
            if event.get('operation') in ('support_check','probe_construction','assessment_candidate'):
                if event['identity'] not in pool or event['output']!=reference(pool[event['identity']],event['argument']):
                    raise ValueError('candidate_output')
                primitive_invocations += len(pool[event['identity']])
            if event.get('operation') in ('oracle','assessment_reference'):
                if event['output']!=reference(target,event['argument']): raise ValueError('oracle_output')
            if event.get('operation')=='oracle' and event['argument'] not in task.probe_pool_inputs:
                raise ValueError('assessment_leak_into_question')
        correct = all(r['output']==reference(target,r['argument']) for _,r in actual)
        calls = Counter(r['operation'] for _,r in seq if r['kind']=='execution')
        metrics.setdefault(method, dict(correct=0,tasks=0,operations=Counter(),candidate_calls=0))
        metric = metrics[method]
        metric['correct']+=correct; metric['tasks']+=1; metric['operations'].update(calls)
        cost = calls['support_check']+calls['probe_construction']
        metric['candidate_calls']+=cost
        raw_seed.setdefault((method,seed),dict(correct=0,calls=0))
        raw_seed[method,seed]['correct']+=correct; raw_seed[method,seed]['calls']+=cost
    for row in metrics.values(): row['operations']=dict(row['operations'])
    if summary is not None and summary['methods']!=metrics: raise ValueError('summary_tamper')
    states = [r for r in records if r.get('kind')=='learned_state']
    if len(states)!=len(config['seeds']) or {r['seed'] for r in states}!=set(config['seeds']): raise ValueError('state_grid')
    # Replay public-only training and controller events to detect omitted calls.
    replay = []
    meter = EventMeter(replay.append)
    for seed in config['seeds']:
        source = [make_task(config,seed,'source',i,meter) for i in range(config['source_tasks'])]
        answers = {t.task_id:lambda x, ops=ops:reference(ops,x) for t,ops,_ in source}
        learned = train_public([t for t,_,_ in source], answers, meter, seed, config)
        expected_state = dict(weights=learned[0],frequencies=learned[1],probe_credit=learned[2],capsules=[asdict(c) for c in learned[3]])
        saved = next(r for r in states if r['seed']==seed)
        if saved['state']!=expected_state or saved['state_hash']!=digest(expected_state) or not saved['restart_equal']:
            raise ValueError('source_feedback_or_state')
        for i in range(config['assessment_tasks']):
            task, target, _ = make_task(config,seed,'assessment',i,meter)
            for method in config['methods']:
                scope = f'{seed}:{method}:{i}'
                engine = EqualizedInvestigationEngineV2(ledger_factory=lambda:SharedLedger(meter,scope), strict_controller_bounds=True)
                params, mode = parameters(method,learned,task,seed)
                engine.set_strategy_params(params)
                keep = method in ('learned','cache','prior_reset')
                if keep: engine.knowledge.skills.capsules={c.capsule_id:deepcopy(c) for c in learned[3]}
                class Answers:
                    def request_answer(_,tid,x):
                        if tid!=task.task_id: raise ValueError('task_mismatch')
                        return reference(target,x)
                out = engine.investigate_v2(task,Answers(),EqualizedControllerConfig(**config['controller']),mode,allow_compositional_capsules=keep)
                saved_lock = next(r for r in locks if r['scope']==scope)
                if (saved_lock['selected']!=out['selected_candidate_id'] or saved_lock['policy_hash']!=digest(asdict(params))
                    or saved_lock['capsule_hash']!=engine.knowledge.skills.state_hash()): raise ValueError('choice_replay')
    def semantic(row):
        return {k:v for k,v in row.items() if k not in ('index','hash','previous','elapsed_s')}
    counted = {'support_reference','support_check','probe_construction','oracle','source_validation','source_validation_oracle'}
    if [semantic(r) for r in events if r['operation'] in counted] != [semantic(r) for r in replay]:
        raise ValueError('omitted_or_changed_execution')
    ids = [r['id'] for r in records if r.get('kind')=='capability']
    expected_ids = {r['id'] for r in config['coding']+config['chat']}|{'json','sqlite','restart','live_model','z3','sympy'}
    if len(ids)!=len(set(ids)) or set(ids)!=expected_ids: raise ValueError('capability_grid')
    # Tool success comes from actual per-case evidence, not "solved" counters.
    for spec in config['coding']:
        scope='coding:'+spec['id']
        scoped=[e for e in events if e['scope']==scope]
        agents=[e for e in scoped if e['operation']=='agent']
        finals=[e for e in scoped if e['operation']=='assessment_worker']
        if len(agents)!=1 or len(finals)!=1: raise ValueError('coding_grid')
        agent, final=agents[0]['output'], finals[0]
        if final['argument']!=dict(language=spec['language'],files=agent['final_files'],cases=spec['assessment']):
            raise ValueError('coding_private_assessment_binding')
        out=final['output']
        if isinstance(out,dict) and out.get('status') not in ('blocked_missing_runtime','rejected'):
            results=out.get('results',[])
            if len(results)!=len(spec['assessment']): raise ValueError('missing_private_test')
            for case,row in zip(spec['assessment'],results):
                if row.get('passed')!=(row.get('actual')==case['expected'] and not row.get('error')):
                    raise ValueError('forged_case_outcome')
        expected_cases=[dict(kind='worker_case',scope=scope,index=j,result=row,execution_hash=e['hash'])
                        for e in scoped if e['operation']=='worker' and isinstance(e['output'],dict)
                        for j,row in enumerate(e['output'].get('results',[]))]
        if [r for r in records if r.get('kind')=='worker_case' and r['scope']==scope]!=expected_cases:
            raise ValueError('worker_case_trace_missing_or_duplicated')
        if [r['record'] for r in records if r.get('kind')=='tool_trace' and r['scope']==scope]!=agent['tool_calls']:
            raise ValueError('tool_trace_missing_or_changed')
    required = [m for m in ('fixed_infogain','boundary_first','cost_aware','frequency','cache')
                if metrics[m]['correct']>=metrics['learned']['correct']]
    strongest = min(required, key=lambda m:metrics[m]['candidate_calls']) if required else None
    difference = paired([(raw_seed[strongest,s]['calls']-raw_seed['learned',s]['calls'])/config['assessment_tasks']
                         for s in config['seeds']]) if strongest else None
    screen = bool(strongest and metrics['learned']['candidate_calls']<=.95*metrics[strongest]['candidate_calls']
                  and difference['interval'][0]>0)
    training = Counter(e['operation'] for e in events if ':train:' in e['scope'])
    train_cost = sum(training[k] for k in ('support_check','probe_construction','source_validation'))
    saving = difference['mean'] if difference else 0
    return dict(valid=True, methods=metrics, primary_comparator=strongest, paired_calls_saved=difference,
                practical_screen_passed=screen, source_training_calls=train_cost,
                break_even_tasks_per_trained_policy=(train_cost/len(config['seeds'])/saving if saving>0 else None),
                additional_trusted_log_primitive_invocations=primitive_invocations,
                source_operations=dict(training), all_operations=dict(Counter(e['operation'] for e in events)),
                seed_metrics=[dict(method=m,seed=s,**row) for (m,s),row in raw_seed.items()],
                learning_to_learn_established=False, confirmation=False,
                trust_boundary='instrumented-log consistency plus deterministic replay; not execution attestation')


def main():
    config = json.loads((ROOT/'configs/seed_capability_audit.json').read_text())
    path = ROOT/'artifacts/seed_capability_audit.json'
    payload = json.loads(path.read_text())
    raw = ROOT/'artifacts/seed_capability_audit_raw.jsonl'
    import hashlib
    if hashlib.sha256(raw.read_bytes()).hexdigest()!=payload['raw_sha256']: raise ValueError('raw_hash')
    records=[json.loads(line) for line in raw.read_text().splitlines()]
    audit = verify_records(records,config,payload['summary'])
    audit['source_sha'] = payload['registration']['source_sha']
    audit['raw_sha256'] = payload['raw_sha256']
    output=ROOT/'artifacts/seed_capability_audit_verified.json'
    with output.open('x') as f: json.dump(audit,f,indent=2,allow_nan=False)
    print(json.dumps(audit,indent=2))


if __name__=='__main__': main()
