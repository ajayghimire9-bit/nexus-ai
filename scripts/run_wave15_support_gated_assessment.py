"""Freezeable shared evaluator; fresh task definitions are imported only in main."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import platform

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.capability_evidence import digest
from nexus.seed.wave15_support_gated_piecewise_learner import TypedEqualCapabilityLearner
from nexus.seed.wave14_piecewise_archive_learner import (
    WAVE14_METHODS,report_to_row,execute_wave14_program_ast,WORK_KEYS,PRIMITIVE_KEYS)

FROZEN_PATHS=(
    'src/nexus/seed/wave15_support_gated_piecewise_learner.py',
    'scripts/run_wave15_support_gated_assessment.py',
    'scripts/verify_wave15_support_gated_enumerator.py',
    'tests/test_seed_wave15_support_gated.py')
HOLDOUT='src/nexus/seed/mechanism_wave15_fresh_assessment.py'
SUBJECT='Pre-assessment code freeze for Wave 15 pre-piecewise residual support abort'
PROTOCOL='docs/NEXUS_WAVE15_SUPPORT_GATED_PIECEWISE_PROTOCOL.md'


def totals(rows):
    out={}
    for method in WAVE14_METHODS:
        subset=[r for r in rows if r['method']==method]
        out[method]=dict(n=len(subset),mapping_correct=sum(r['mapping_correct'] for r in subset),
            private_correct=sum(r['private_correct'] for r in subset),
            false_unique=sum(r['false_unique'] for r in subset),
            cold_archive_reactivated=sum(r['cold_archive_reactivated'] for r in subset),
            ambiguous_correctly_declared=sum(r['ambiguous_correctly_declared'] for r in subset),
            total_work=sum(r['total_work'] for r in subset),
            total_primitive_op_steps=sum(r['total_primitive_op_steps'] for r in subset))
    return out


def evaluate_gates(rows):
    suite=totals(rows);full=suite['nexus_typed_full'];failures=[]
    if full['mapping_correct']!=full['n'] or full['private_correct']!=full['n']:failures.append('full_accuracy')
    if any(r['false_unique'] for r in rows):failures.append('false_unique')
    for method in WAVE14_METHODS:
        if method=='nexus_typed_full':continue
        for metric in ('total_work','total_primitive_op_steps'):
            if full[metric]>=suite[method][metric]:failures.append(metric+':'+method)
    for seed in sorted({r['source_seed'] for r in rows}):
        block=[r for r in rows if r['source_seed']==seed]
        f=[r for r in block if r['method']=='nexus_typed_full']
        if not any(r['cold_archive_reactivated'] for r in f):failures.append('archive:'+str(seed))
        for r in block:
            if r['gold_status']=='abstain' and (r['status']!='abstain' or r['support_gate']['piecewise_evaluations']!=0
                    or r['support_gate']['piecewise_primitive_steps']!=0):failures.append('oog:'+r['method'])
        if any(r['gold_status']=='ambiguous' and r['status']!='ambiguous' for r in f):failures.append('ambiguous:'+str(seed))
    return dict(passed=not failures,failures=failures)


def assess_cases(cases,world_factory,seeds=(0,1,2),development=False,emit=None):
    rows=[];start=time.perf_counter()
    for seed in seeds:
        for method in WAVE14_METHODS:
            learner=TypedEqualCapabilityLearner(method)
            for arrival,(identifier,fn,split,pal,gold) in enumerate(cases):
                env=world_factory(fn,seed,pal=pal,ambiguous=gold=='ambiguous')
                report=learner.solve_unfamiliar_task(env,10)
                private_before=env.private_opened
                env.lock();private=[]
                private_ok=report.status==gold
                if report.status=='unique':
                    for slot in ('alpha','beta','gamma','delta'):
                        obs=env.private_read(slot);pred=execute_wave14_program_ast(report.program_ast,obs['payload'])
                        private.append(dict(input=list(obs['payload']),predicted_output=list(pred),ground_truth_output=list(obs['result'])))
                        private_ok=private_ok and pred==obs['result']
                row=report_to_row(report)
                diag=getattr(learner,'last_diagnostics',dict(piecewise_evaluations=0,piecewise_primitive_steps=0))
                if report.status=='ambiguous' and not report.public_observations:diag=dict(piecewise_evaluations=0,piecewise_primitive_steps=0)
                row.update(source_seed=seed,arrival_index=arrival,task_id=identifier,split=split,gold_status=gold,
                    mapping_correct=report.status==gold,private_correct=bool(private_ok),
                    false_unique=report.status=='unique' and not private_ok,
                    ambiguous_correctly_declared=gold=='ambiguous' and report.status=='ambiguous',
                    private_before_lock=private_before,private_evaluations=private,support_gate=diag)
                rows.append(row)
                if emit:emit(row)
    table=dict(suite=totals(rows))
    for split in sorted({r['split'] for r in rows}):table[split]=totals([r for r in rows if r['split']==split])
    payload=dict(kind='seed_wave15_support_gated_enumerator',development=development,
        methods=list(WAVE14_METHODS),seeds=list(seeds),task_manifest=[dict(id=c[0],split=c[2],gold=c[4]) for c in cases],
        assessment=rows,totals=table,gates=evaluate_gates(rows),
        usage=dict(model_calls=0,frozen_debit_s=0,elapsed_s=time.perf_counter()-start))
    payload['hash']=digest({k:payload[k] for k in ('kind','assessment','totals','gates')})
    return payload


def freeze_sha():
    log=subprocess.check_output(['git','log','--format=%H%x09%s'],cwd=ROOT,text=True)
    return next(line.split('\t')[0] for line in log.splitlines() if line.split('\t',1)[1]==SUBJECT)


def main():
    freeze=freeze_sha()
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',freeze],cwd=ROOT,text=True).splitlines()
    if any('wave15' in n and ('fresh_assessment' in n or n.startswith('artifacts/seed_wave15')) for n in names):
        raise ValueError('holdout_or_results_present_at_freeze')
    if subprocess.check_output(['git','diff',freeze,'--',*FROZEN_PATHS],cwd=ROOT):raise ValueError('phase1_code_changed')
    frozen_protocol=subprocess.check_output(['git','show',freeze+':'+PROTOCOL],cwd=ROOT)
    if (ROOT/PROTOCOL).read_bytes()!=frozen_protocol:raise ValueError('protocol_changed')
    for name in FROZEN_PATHS:
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().encode() not in frozen_protocol:
            raise ValueError('protocol_hash_mismatch:'+name)
    output=ROOT/'artifacts/seed_wave15_support_gated_enumerator.json'
    marker=ROOT/'artifacts/seed_wave15_attempt.json'
    registration=dict(freeze_sha=freeze,holdout_sha256=hashlib.sha256((ROOT/HOLDOUT).read_bytes()).hexdigest(),
        phase1_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FROZEN_PATHS},
        protocol_sha256=hashlib.sha256(frozen_protocol).hexdigest(),
        historical_runtime_sha256='5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781',
        runtime_sha256=hashlib.sha256((ROOT/'src/nexus/seed/local_model_runtime.py').read_bytes()).hexdigest(),
        track_b_model_calls=0,track_b_debit_s=0,wall_cap_s=120,cpu_cap_s=120,
        carried_frozen_cpu_used_s=3128.309460455996,carried_frozen_cpu_remaining_s=471.690539544004)
    if registration['runtime_sha256']!=registration['historical_runtime_sha256']:raise ValueError('historical_runtime_changed')
    if output.exists() or marker.exists():raise ValueError('closed_attempt_no_retry')
    with marker.open('x') as f:json.dump(registration,f,indent=2)
    resource.setrlimit(resource.RLIMIT_CPU,(120,120))
    def timeout(_signum,_frame):raise TimeoutError('wave15_wall_cap')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(120)
    start_wall=time.perf_counter();start_cpu=time.process_time()
    try:
        from nexus.seed.mechanism_wave15_fresh_assessment import fresh_cases,FreshWorld
        cases=fresh_cases()
        if len(cases)!=18 or len({c[0] for c in cases})!=18 or any(not c[0].startswith('w15f_') for c in cases):raise ValueError('invalid_registered_grid')
        with (ROOT/'artifacts/seed_wave15_rows.jsonl').open('x') as f:
            def emit(row):f.write(json.dumps(row,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
            payload=assess_cases(cases,FreshWorld,emit=emit)
    except Exception as exc:
        partial=dict(complete=False,status='INCOMPLETE_OR_INVALID',error=type(exc).__name__+':'+str(exc),
            registration=registration,wall_s=time.perf_counter()-start_wall,cpu_s=time.process_time()-start_cpu,
            raw_rows='artifacts/seed_wave15_rows.jsonl',automatic_retry_permitted=False)
        with output.open('x') as f:json.dump(partial,f,indent=2)
        raise
    finally:signal.alarm(0)
    payload['complete']=True
    payload['usage'].update(cpu_s=time.process_time()-start_cpu,wall_s=time.perf_counter()-start_wall,
        peak_rss_native=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,platform=platform.platform(),
        python=sys.version,simulator_steps=0,neural_training_updates=0)
    payload['registration']=registration
    with output.open('x') as f:json.dump(payload,f,indent=2)
    print(json.dumps(dict(gates=payload['gates'],suite=payload['totals']['suite'],usage=payload['usage']),indent=2))
    return 0 if payload['gates']['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
