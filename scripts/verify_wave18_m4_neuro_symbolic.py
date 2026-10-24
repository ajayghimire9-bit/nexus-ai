"""Read-only Wave18 saved-result verification. Never executes a learner.

Reuses the trusted Wave17 independent verifier with task-local dependency
injection. An uncertified neural decoder may make incorrect predictions; those
are scored failures, not permission to fabricate consistency or invalidate an
otherwise honestly recorded comparison.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import sys
from types import FunctionType

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.capability_evidence import digest
from nexus.seed import wave18_m4_gpu_neuro_symbolic_learner as wave
from scripts.verify_wave17_exact_cache_enumerator import verify_payload as old_verify


def verify_payload(payload, manifest):
    """Expected seeds/methods/tasks come from locked inputs, never result rows."""
    errors=[];rows=payload.get('assessment',[])
    expected=set(itertools.product((0,1,2),wave.METHODS,[s['id'] for s in manifest]))
    keys=[(r.get('source_seed'),r.get('method'),r.get('task_id')) for r in rows]
    if len(manifest)!=18 or len({s['id'] for s in manifest})!=18:
        errors.append('locked_task_manifest')
    if len(keys)!=324 or set(keys)!=expected:
        errors.append('incomplete_grid')
    if payload.get('methods')!=list(wave.METHODS) or payload.get('seeds')!=[0,1,2]:
        errors.append('locked_axes')
    if not payload.get('complete'):
        errors.append('incomplete_execution')
    calculated=digest({k:payload[k] for k in ('kind','assessment','totals','gates')})
    if payload.get('hash')!=calculated:
        errors.append('payload_hash')
    certified=copy.deepcopy(payload)
    certified['methods']=list(wave.METHODS[1:])
    certified['assessment']=[r for r in rows if r.get('method')!=wave.METHODS[0]]
    for table in certified.get('totals',{}).values():
        table.pop(wave.METHODS[0],None)
    certified['hash']=digest({k:certified[k] for k in ('kind','assessment','totals','gates')})
    namespace=dict(old_verify.__globals__)
    namespace.update(WAVE14_METHODS=wave.METHODS[1:],WORK_KEYS=wave.WORK_KEYS)
    verify=FunctionType(old_verify.__code__,namespace,old_verify.__name__,
                        old_verify.__defaults__,old_verify.__closure__)
    replay=verify(certified,manifest)
    errors.extend(replay['errors'])
    specs={s['id']:s for s in manifest}
    baseline_totals={k:0 for k in ('mapping_correct','private_correct','false_unique',
        'cold_archive_reactivated','ambiguous_correctly_declared','total_work',
        'total_primitive_op_steps','n')}
    for index,row in enumerate(rows):
        label=str(index)
        gpu=row.get('gpu',{})
        if row.get('total_work')!=sum(row.get(k,0) for k in wave.WORK_KEYS):
            errors.append('work_identity:'+label)
        if row.get('total_primitive_op_steps')!=sum(row.get(k,0) for k in wave.PRIMITIVE_KEYS):
            errors.append('primitive_identity:'+label)
        neural=row.get('method') in (wave.METHODS[0],wave.METHODS[-2],wave.METHODS[-1])
        if neural and (gpu.get('gpu_device')!='mps' or gpu.get('mps_available') is not True):
            errors.append('mps_required:'+label)
        for k in ('gpu_forward_passes','gpu_encoder_calls','gpu_online_update_steps','head_expansions'):
            if type(gpu.get(k)) is not int or gpu[k]<0:
                errors.append('invalid_gpu_counter:'+label+':'+k)
        if neural and gpu.get('gpu_forward_passes',0)<1:
            errors.append('missing_neural_forward:'+label)
        if neural and row.get('method')!=wave.METHODS[0]:
            if gpu.get('gpu_online_update_steps')!=(3 if row.get('status')=='unique' else 0):
                errors.append('online_update_rule:'+label)
        if row.get('method')!=wave.METHODS[0]:
            continue
        spec=specs.get(row.get('task_id'))
        if spec is None:
            continue
        correct=row.get('status')==spec['gold']
        part=spec['seeds'].get(row.get('source_seed'),spec['seeds'].get(str(row.get('source_seed'))))
        if row.get('private_before_lock') is not False:
            errors.append('baseline_private_boundary:'+label)
        if row.get('status')=='unique':
            saved=row.get('private_evaluations',[])
            if len(saved)!=len(part['private']):
                errors.append('baseline_private_count:'+label)
            for (x,y),obs in zip(part['private'],saved):
                prediction=wave.eval_program(row['program_ast'],x)
                if wave.exact.canonical_input(obs['input'])!=wave.exact.canonical_input(x):
                    errors.append('baseline_private_input:'+label)
                if prediction!=wave.exact.canonical_input(obs['predicted_output']):
                    errors.append('baseline_prediction_replay:'+label)
                if wave.exact.canonical_input(y)!=wave.exact.canonical_input(obs['ground_truth_output']):
                    errors.append('baseline_private_target:'+label)
                correct=correct and prediction==wave.exact.canonical_input(y)
        if correct!=row.get('private_correct'):
            errors.append('baseline_accuracy:'+label)
        if row.get('false_unique')!=(row.get('status')=='unique' and not correct):
            errors.append('baseline_false_unique:'+label)
        for k in baseline_totals:
            baseline_totals[k]+=1 if k=='n' else int(row[k])
    if baseline_totals!=payload.get('totals',{}).get('suite',{}).get(wave.METHODS[0]):
        errors.append('baseline_totals')
    return dict(valid=not errors,errors=sorted(set(errors)),replayed_rows=len(rows),
                baseline_totals=baseline_totals,certified_totals=replay['totals'])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    args=parser.parse_args()
    payload=json.loads(args.result.read_text());registered=json.loads(args.manifest.read_text())
    manifest=registered['specs'] if isinstance(registered,dict) else registered
    result=verify_payload(payload,manifest)
    result['result_sha256']=hashlib.sha256(args.result.read_bytes()).hexdigest()
    result['manifest_sha256']=hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    print(json.dumps(result,indent=2))
    return 0 if result['valid'] else 1


if __name__=='__main__':
    raise SystemExit(main())
