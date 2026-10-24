"""Shared bounded evaluator. Fresh definitions are imported only after freeze.

The required runner is the owner's carried exception to the filename exclusion;
it contains no fresh assessment rules, tokens, examples or target ASTs.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.capability_evidence import digest
from nexus.seed.wave17_exact_cache_boundary_learner import (
    TypedEqualCapabilityLearner,canonical_input,eval_program,validate_task_fixture_semantics,
    WAVE14_METHODS,WORK_KEYS,PRIMITIVE_KEYS,PUBLIC_BUDGET,report_to_row)

FROZEN_PATHS=('src/nexus/seed/wave17_exact_cache_boundary_learner.py',
    'scripts/run_wave17_exact_cache_assessment.py','scripts/verify_wave17_exact_cache_enumerator.py',
    'tests/test_seed_wave17_boundary_and_cache_invariance.py')
HOLDOUT='src/nexus/seed/mechanism_wave17_fresh_assessment.py'
PROTOCOL='docs/NEXUS_WAVE17_EXACT_CACHE_BOUNDARY_PROTOCOL.md'
SUBJECT='Pre-assessment code freeze for Wave 17 exact interpreter cache and boundary invariance'
RUNTIME_HASH='5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781'
OUTPUT='artifacts/seed_wave17_exact_cache_enumerator.json'
SEEDS=(0,1,2)


class PublicWorld:
    """Observation-only capability. Private rows live solely in the evaluator."""
    __slots__=('_public','extra_public_slots','reads','locked')
    def __init__(self,part):
        public=[(x,canonical_input(y)) for x,y in part['public']]
        if len(public)<8:raise ValueError('insufficient_public_rows')
        slots=['alpha','beta','gamma','delta','epsilon']
        slots+=['bank_%03d'%i for i in range(len(public)-5)]
        confirm_count=part.get('confirm_count',2)
        for i in range(confirm_count):slots[-confirm_count+i]='confirm_%03d'%i
        self._public=dict(zip(slots,public));self.reads=[];self.locked=False
        self.extra_public_slots={s:x for s,(x,y) in self._public.items() if s not in slots[:5]}

    def public_read(self,slot):
        if self.locked:raise RuntimeError('public_after_lock')
        x,y=self._public[slot];self.reads.append(slot)
        return dict(payload=x,result=y,slot=slot,echo=x,stamp=len(self.reads),tick=len(self.reads))

    def lock(self):self.locked=True


def totals(rows):
    table={}
    for method in WAVE14_METHODS:
        subset=[r for r in rows if r['method']==method]
        table[method]={key:sum(int(r[key]) for r in subset) for key in (
            'mapping_correct','private_correct','false_unique','cold_archive_reactivated',
            'ambiguous_correctly_declared','total_work','total_primitive_op_steps')}
        table[method]['n']=len(subset)
    return table


def evaluate_gates(rows):
    t=totals(rows);full=t['nexus_typed_full'];errors=[]
    if full['n']!=54 or full['private_correct']!=54:errors.append('full_accuracy')
    if full['cold_archive_reactivated']<3:errors.append('cold_reactivation')
    if full['ambiguous_correctly_declared']!=3:errors.append('ambiguity')
    if any(r['false_unique'] for r in rows):errors.append('false_unique')
    for row in rows:
        diag=row['support_gate']
        if diag.get('cached_coverage_mask_errors',0):errors.append('coverage_mask')
        if row['gold_status']=='abstain' and (diag['piecewise_evaluations'] or row['status']!='abstain'):
            errors.append('oog:'+row['method'])
    for method in WAVE14_METHODS:
        if method=='nexus_typed_full':continue
        for metric in ('total_work','total_primitive_op_steps'):
            if full[metric]>=t[method][metric]:errors.append(metric+':'+method)
    return dict(passed=not errors,failures=sorted(set(errors)))


def assess_specs(specs,development=False,emit=None):
    identifiers=[s['id'] for s in specs]
    if len(identifiers)!=18 or len(set(identifiers))!=18:raise ValueError('expected_18_distinct_tasks')
    validation={s['id']:validate_task_fixture_semantics(s) for s in specs}
    if not all(v['valid'] for v in validation.values()):raise ValueError('invalid_fixture:'+json.dumps(validation))
    rows=[]
    for seed in SEEDS:
        for method in WAVE14_METHODS:
            learner=TypedEqualCapabilityLearner(method)
            for arrival,spec in enumerate(specs):
                part=spec['seeds'].get(seed,spec['seeds'].get(str(seed)))
                world=PublicWorld(part)
                report=learner.solve_unfamiliar_task(world,PUBLIC_BUDGET)
                world.lock();private=[];correct=report.status==spec['gold']
                if report.status=='unique':
                    for x,y in part['private']:
                        predicted=eval_program(report.program_ast,x)
                        private.append(dict(input=canonical_input(x),predicted_output=predicted,ground_truth_output=canonical_input(y)))
                        correct=correct and predicted==canonical_input(y)
                row=report_to_row(report)
                row.update(task_id=spec['id'],split=spec['split'],source_seed=seed,arrival_index=arrival,
                    gold_status=spec['gold'],mapping_correct=report.status==spec['gold'],private_correct=bool(correct),
                    false_unique=report.status=='unique' and not correct,
                    ambiguous_correctly_declared=spec['gold']=='ambiguous' and report.status=='ambiguous',
                    private_before_lock=False,private_evaluations=private,
                    public_read_slots=world.reads,support_gate=learner.last_diagnostics)
                rows.append(row)
                if emit:emit(row)
    payload=dict(kind='seed_wave17_exact_cache_enumerator',development=development,
        methods=list(WAVE14_METHODS),seeds=list(SEEDS),public_budget=PUBLIC_BUDGET,
        task_manifest=[dict(id=s['id'],split=s['split'],gold=s['gold']) for s in specs],
        fixture_validation=validation,assessment=rows,totals=dict(suite=totals(rows)),gates=evaluate_gates(rows))
    for split in sorted({s['split'] for s in specs}):
        payload['totals'][split]=totals([r for r in rows if r['split']==split])
    payload['hash']=digest({k:payload[k] for k in ('kind','assessment','totals','gates')})
    return payload


def freeze_sha():
    lines=subprocess.check_output(['git','log','--format=%H%x09%s'],cwd=ROOT,text=True).splitlines()
    return next(line.split('\t')[0] for line in lines if line.split('\t',1)[1]==SUBJECT)


def check_freeze():
    freeze=freeze_sha()
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',freeze],cwd=ROOT,text=True).splitlines()
    exceptions={'scripts/run_wave17_exact_cache_assessment.py'}
    if any('wave17' in p and 'assessment' in p and p not in exceptions for p in paths):raise ValueError('assessment_definitions_before_freeze')
    if 'docs/NEXUS_WAVE17_EXACT_CACHE_BOUNDARY_RESULTS.md' in paths:raise ValueError('results_present_before_freeze')
    if subprocess.check_output(['git','diff',freeze,'--',*FROZEN_PATHS],cwd=ROOT):raise ValueError('phase1_code_changed')
    protocol=subprocess.check_output(['git','show',freeze+':'+PROTOCOL],cwd=ROOT)
    if (ROOT/PROTOCOL).read_bytes()!=protocol:raise ValueError('protocol_changed')
    for p in FROZEN_PATHS:
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest().encode() not in protocol:raise ValueError('frozen_hash:'+p)
    runtime=hashlib.sha256((ROOT/'src/nexus/seed/local_model_runtime.py').read_bytes()).hexdigest()
    if runtime!=RUNTIME_HASH:raise ValueError('track_b_runtime_changed')
    return freeze,protocol


def main():
    freeze,protocol=check_freeze()
    marker=ROOT/'artifacts/seed_wave17_attempt.json';output=ROOT/OUTPUT
    if marker.exists() or output.exists():raise ValueError('closed_attempt_no_retry')
    registration=dict(freeze_sha=freeze,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        holdout_sha256=hashlib.sha256((ROOT/HOLDOUT).read_bytes()).hexdigest(),
        protocol_sha256=hashlib.sha256(protocol).hexdigest(),
        phase1_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FROZEN_PATHS},
        runtime_sha256=RUNTIME_HASH,track_b_model_calls=0,track_b_debit_s=0,
        wall_cap_s=200,cpu_cap_s=200,carried_frozen_cpu_used_s=3128.309460455996,
        carried_frozen_cpu_remaining_s=471.690539544004,prior_symbolic_cpu_s=13.264430)
    with marker.open('x') as f:json.dump(registration,f,indent=2)
    resource.setrlimit(resource.RLIMIT_CPU,(195,200))
    def timeout(signum,frame):raise TimeoutError('wave17_wall_cap')
    signal.signal(signal.SIGXCPU,timeout)
    signal.signal(signal.SIGALRM,timeout);signal.alarm(200)
    wall=time.perf_counter();cpu=time.process_time()
    try:
        from nexus.seed.mechanism_wave17_fresh_assessment import fresh_specs
        specs=fresh_specs()
        if any(not s['id'].startswith('w17f_') for s in specs):raise ValueError('incorrect_fresh_namespace')
        with (ROOT/'artifacts/seed_wave17_rows.jsonl').open('x') as stream:
            def emit(row):
                stream.write(json.dumps(row,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
            payload=assess_specs(specs,emit=emit)
        payload.update(complete=True,registration=registration)
    except Exception as exc:
        payload=dict(complete=False,status='INCOMPLETE_OR_INVALID',registration=registration,
            error=type(exc).__name__+':'+str(exc),automatic_retry_permitted=False)
    finally:signal.alarm(0)
    payload['usage']=dict(cpu_s=time.process_time()-cpu,wall_s=time.perf_counter()-wall,
        peak_rss_native=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        python=sys.version,platform=platform.platform(),model_calls=0,simulator_steps=0,
        frozen_debit_s=0,neural_training_updates=0)
    with output.open('x') as f:json.dump(payload,f,indent=2)
    print(json.dumps(dict(complete=payload['complete'],gates=payload.get('gates'),usage=payload['usage']),indent=2))
    return 0 if payload.get('complete') and payload['gates']['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
