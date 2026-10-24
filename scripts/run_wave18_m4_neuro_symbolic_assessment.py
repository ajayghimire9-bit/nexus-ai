"""Owner-approved vetted MPS worker and bounded supervisor.

Contains no fresh rules. The owner explicitly permits this runner before the
freeze; fresh definitions and results remain prohibited until afterward.
Reuses E1 Journal/write_new and the frozen public evaluator, not a new framework.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from types import FunctionType, SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.experimental import write_new
from nexus.evolution1.fixtures import Journal
from nexus.seed.capability_evidence import digest
from nexus.seed import wave18_m4_gpu_neuro_symbolic_learner as wave
from scripts import run_wave17_exact_cache_assessment as previous

SUBJECT='Pre-assessment code freeze for Wave 18 M4-GPU neuro-symbolic canonical evolution'
PROTOCOL='docs/NEXUS_WAVE18_M4_NEURO_SYMBOLIC_PROTOCOL.md'
HOLDOUT='src/nexus/seed/mechanism_wave18_fresh_assessment.py'
OUTPUT='artifacts/seed_wave18_m4_neuro_symbolic.json'
FROZEN_PATHS=('src/nexus/seed/wave18_m4_gpu_neuro_symbolic_learner.py',
    'scripts/run_wave18_m4_neuro_symbolic_assessment.py',
    'scripts/verify_wave18_m4_neuro_symbolic.py','tests/test_seed_wave18_m4_neuro_symbolic.py')
BASE_FROZEN_USED=3128.309460455996
PRIOR_SYMBOLIC_CPU=188.041673
SESSION_CAP=3600.
OWNER_APPROVAL=dict(device='mps',wall_s=200,cpu_s=200,memory_mb=1024,
    real_steps=0,assessment_attempts=1,session_increase=False,
    provenance='Owner approved the exact limits in the Wave18 clarification reply.')


def totals(rows):
    return {method:{**{k:sum(int(r[k]) for r in rows if r['method']==method) for k in (
        'mapping_correct','private_correct','false_unique','cold_archive_reactivated',
        'ambiguous_correctly_declared','total_work','total_primitive_op_steps')},
        'n':sum(r['method']==method for r in rows)} for method in wave.METHODS}


def evaluate_gates(rows):
    table=totals(rows);full=table[wave.METHODS[-1]];failures=[]
    if len(rows)!=324 or any(table[m]['n']!=54 for m in wave.METHODS):
        failures.append('incomplete_grid')
    if full['private_correct']!=54:failures.append('full_accuracy')
    if full['false_unique']:failures.append('false_unique_full')
    if full['ambiguous_correctly_declared']!=3:failures.append('ambiguity_full')
    if full['cold_archive_reactivated']<3:failures.append('cold_reactivation_full')
    for row in rows:
        if row['method']==wave.METHODS[0]:continue
        diag=row['support_gate']
        if diag.get('cached_coverage_mask_errors',0):failures.append('mask_error')
        if row['gold_status']=='abstain' and (row['status']!='abstain' or
                diag.get('piecewise_evaluations',0) or diag.get('piecewise_primitive_steps',0)):
            failures.append('oog:'+row['method'])
    for method in wave.METHODS[:-1]:
        if table[method]['private_correct']==54:
            for metric in ('total_work','total_primitive_op_steps'):
                if full[metric]>=table[method][metric]:failures.append(metric+':'+method)
    return dict(passed=not failures,failures=sorted(set(failures)),
        neural_only_failed=table[wave.METHODS[0]]['private_correct']<54,
        neural_only_claim='limited_top16_ablation_not_a_representative_LLM')


def assess_specs(specs, emit=None):
    """Reuse the frozen evaluator body with explicit local method/row adapters."""
    ordinal=[0]
    def factory(method):
        index=ordinal[0];ordinal[0]+=1
        if method!=wave.METHODS[index%len(wave.METHODS)]:
            raise ValueError('unexpected_evaluator_construction_order')
        return LearnerAdapter(method,index//len(wave.METHODS))
    namespace=dict(previous.assess_specs.__globals__)
    namespace.update(WAVE14_METHODS=wave.METHODS,TypedEqualCapabilityLearner=factory,
                     report_to_row=unwrap_row,totals=totals,evaluate_gates=evaluate_gates)
    evaluate=FunctionType(previous.assess_specs.__code__,namespace,previous.assess_specs.__name__,
        previous.assess_specs.__defaults__,previous.assess_specs.__closure__)
    payload=evaluate(specs,development=True,emit=emit)
    payload['kind']='seed_wave18_m4_neuro_symbolic'
    payload['hash']=digest({k:payload[k] for k in ('kind','assessment','totals','gates')})
    return payload


class LearnerAdapter:
    def __init__(self, method, seed):
        self.learner=wave.Wave18Learner(method,seed)
        self.last_diagnostics={}

    def solve_unfamiliar_task(self, env, public_budget):
        row=self.learner.solve_unfamiliar_task(env,public_budget)
        self.last_diagnostics=self.learner.last_diagnostics
        return SimpleNamespace(**row,_row=row)


def unwrap_row(report):
    return dict(report._row)


def check_freeze():
    lines=subprocess.check_output(['git','log','--format=%H%x09%s'],cwd=ROOT,text=True).splitlines()
    matches=[line.split('\t')[0] for line in lines if line.split('\t',1)[1]==SUBJECT]
    if len(matches)!=1:raise ValueError('one_passing_physical_freeze_required')
    freeze=matches[0]
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',freeze],cwd=ROOT,text=True).splitlines()
    exception=FROZEN_PATHS[1]
    if any('wave18' in p and 'assessment' in p and p!=exception for p in paths):
        raise ValueError('fresh_definition_present_before_freeze')
    if 'docs/NEXUS_WAVE18_M4_NEURO_SYMBOLIC_RESULTS.md' in paths:
        raise ValueError('results_before_freeze')
    protocol=subprocess.check_output(['git','show',freeze+':'+PROTOCOL],cwd=ROOT)
    if b'NOT FROZEN' in protocol or (ROOT/PROTOCOL).read_bytes()!=protocol:
        raise ValueError('protocol_not_locked_or_changed')
    if subprocess.check_output(['git','diff',freeze,'--',*FROZEN_PATHS],cwd=ROOT):
        raise ValueError('phase1_changed')
    for path in FROZEN_PATHS:
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest().encode() not in protocol:
            raise ValueError('frozen_hash:'+path)
    if hashlib.sha256((ROOT/'src/nexus/seed/local_model_runtime.py').read_bytes()).hexdigest()!=previous.RUNTIME_HASH:
        raise ValueError('track_b_runtime_changed')
    return freeze,protocol


def consumed_wave18_wall():
    consumed=0.
    for receipt in (ROOT/'artifacts').glob('seed_wave18_*_process.json'):
        data=json.loads(receipt.read_text())
        consumed+=float(data['charged_wall_s'])
    # Unsettled reservations remain fully charged across crashes/retries.
    for reserved in (ROOT/'artifacts').glob('seed_wave18_*_reservation.json'):
        corresponding=reserved.with_name(reserved.name.replace('_reservation.json','_process.json'))
        if not corresponding.exists():consumed+=float(json.loads(reserved.read_text())['wall_cap_s'])
    return consumed


def supervise(kind, source_revision=1):
    if kind not in ('smoke','source_gate','fresh'):raise ValueError('vetted_worker_required')
    if type(source_revision) is not int or not 1<=source_revision<=8:
        raise ValueError('bounded_source_revision')
    if kind=='fresh' and source_revision!=1:raise ValueError('fresh_cannot_retry')
    if kind=='fresh':check_freeze()
    remaining=SESSION_CAP-BASE_FROZEN_USED-PRIOR_SYMBOLIC_CPU-consumed_wave18_wall()
    cap=min(OWNER_APPROVAL['wall_s'],remaining)
    if cap<1:raise ValueError('session_exhausted')
    paths=ROOT/'artifacts';stem='seed_wave18_'+kind+('_r'+str(source_revision) if source_revision!=1 else '')
    reservation=paths/(stem+'_reservation.json');receipt=paths/(stem+'_process.json')
    if reservation.exists() or receipt.exists():raise ValueError('existing_attempt_no_automatic_retry')
    journal=Journal()
    reserved=dict(kind=kind,source_revision=source_revision,owner_approval=OWNER_APPROVAL,wall_cap_s=cap,cpu_cap_s=min(200,cap),
        memory_policy='sampled_rss_30ms_and_bounded_MPS_allocator_not_kernel_isolation',
        gpu_allocator_cap_bytes=256*1024*1024,carried_frozen_used_s=BASE_FROZEN_USED,
        prior_symbolic_cpu_s=PRIOR_SYMBOLIC_CPU,prior_wave18_charged_wall_s=consumed_wave18_wall(),
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        phase1_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FROZEN_PATHS})
    journal.append('reserved',reserved);write_new(reservation,reserved)
    env=dict(os.environ);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
        PYTHONDONTWRITEBYTECODE='1',PYTORCH_ENABLE_MPS_FALLBACK='0',
        NEXUS_WAVE18_CPU_CAP_S=str(min(200,cap)),
        NEXUS_WAVE18_SOURCE_ROWS=str(paths/(stem+'_rows.jsonl')),
        PYTHONPATH=str(ROOT)+os.pathsep+str(ROOT/'src')+os.pathsep+os.environ.get('PYTHONPATH',''))
    start=time.perf_counter();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    reason=None;peak_rss_mb=0.;proc=None
    try:
        with (paths/(stem+'_stdout.txt')).open('x') as out,(paths/(stem+'_stderr.txt')).open('x') as err:
            proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',kind],
                cwd=ROOT,env=env,stdout=out,stderr=err,start_new_session=True)
            while proc.poll() is None:
                sample=subprocess.run(['ps','-o','rss=','-p',str(proc.pid)],capture_output=True,text=True,timeout=.2)
                if sample.stdout.strip():peak_rss_mb=max(peak_rss_mb,float(sample.stdout.strip())/1024)
                if time.perf_counter()-start>=cap or peak_rss_mb>OWNER_APPROVAL['memory_mb']:
                    reason='wall_cap' if time.perf_counter()-start>=cap else 'memory_cap'
                    os.killpg(proc.pid,signal.SIGKILL);break
                time.sleep(.03)
            proc.wait()
    except BaseException:
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        raise
    finally:
        elapsed=time.perf_counter()-start;after=resource.getrusage(resource.RUSAGE_CHILDREN)
        settled=dict(kind=kind,returncode=proc.returncode if proc else None,reason=reason,
            charged_wall_s=elapsed,wall_cap_s=cap,peak_sampled_rss_mb=peak_rss_mb,
            cpu_user_s=after.ru_utime-before.ru_utime,cpu_system_s=after.ru_stime-before.ru_stime,
            track_b_calls=0,track_b_debit_s=0,simulator_steps=0)
        journal.append('settled',settled);settled['journal']=[asdict(e) for e in journal.snapshot()]
        write_new(receipt,settled)
    print(json.dumps(settled,indent=2))
    return 0 if proc and proc.returncode==0 and reason is None else 1


def worker(kind):
    cpu=float(os.environ['NEXUS_WAVE18_CPU_CAP_S']);hard=max(1,math.ceil(cpu))
    resource.setrlimit(resource.RLIMIT_CPU,(max(1,hard-2),hard))
    torch,_=wave.require_mps()
    torch.mps.set_per_process_memory_fraction(min(1.,256*1024*1024/torch.mps.recommended_max_memory()))
    if kind in ('smoke','source_gate'):
        import pytest
        expression='mps and not complete_source' if kind=='smoke' else 'complete_source_gate_mps'
        return pytest.main(['-o','addopts=','-q','-s','tests/test_seed_wave18_m4_neuro_symbolic.py',
                            '-k',expression,'--tb=short'])
    freeze,protocol=check_freeze()
    marker=ROOT/'artifacts/seed_wave18_fresh_attempt.json'
    registration=dict(freeze_sha=freeze,protocol_sha256=hashlib.sha256(protocol).hexdigest(),
        holdout_sha256=hashlib.sha256((ROOT/HOLDOUT).read_bytes()).hexdigest(),
        phase1_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FROZEN_PATHS},
        owner_approval=OWNER_APPROVAL)
    write_new(marker,registration)
    from nexus.seed.mechanism_wave18_fresh_assessment import fresh_specs
    specs=fresh_specs()
    if any(not s['id'].startswith('w18f_') for s in specs):raise ValueError('fresh_namespace')
    with (ROOT/'artifacts/seed_wave18_registered_fixtures.json').open('x') as stream:
        json.dump(specs,stream,indent=2)
    with (ROOT/'artifacts/seed_wave18_fresh_rows.jsonl').open('x') as stream:
        def emit(row):
            stream.write(json.dumps(row,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
        payload=assess_specs(specs,emit)
    payload.update(complete=True,registration=registration)
    with (ROOT/OUTPUT).open('x') as stream:json.dump(payload,stream,indent=2)
    print(json.dumps(dict(complete=True,gates=payload['gates'],totals=payload['totals']['suite']),indent=2))
    return 0 if payload['gates']['passed'] else 1


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-smoke',action='store_true')
    parser.add_argument('--source-gate',action='store_true')
    parser.add_argument('--source-revision',type=int,default=1)
    parser.add_argument('--worker',choices=('smoke','source_gate','fresh'))
    args=parser.parse_args()
    if args.worker:return worker(args.worker)
    return supervise('smoke' if args.source_smoke else 'source_gate' if args.source_gate else 'fresh',args.source_revision)


if __name__=='__main__':raise SystemExit(main())
