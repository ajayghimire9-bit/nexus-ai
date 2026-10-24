"""Frozen standalone AST/dual-cost/coverage/evidence replay verifier."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.capability_evidence import digest
from nexus.seed.wave14_piecewise_archive_learner import (
    WORK_KEYS,PRIMITIVE_KEYS,OpCounter,eval_expr_ast,expr_ast_from_dict,execute_wave14_program_ast,WAVE14_METHODS)
from scripts.run_wave16_peeled_archive_assessment import FROZEN_PATHS,HOLDOUT,freeze_sha,evaluate_gates


def totals(rows):
    """Independently reconstruct saved summaries rather than import runner sums."""
    result={}
    fields=('mapping_correct','private_correct','false_unique','cold_archive_reactivated',
            'ambiguous_correctly_declared','total_work','total_primitive_op_steps')
    for method in WAVE14_METHODS:
        block=[r for r in rows if r['method']==method]
        result[method]={'n':len(block)}
        for field in fields:result[method][field]=sum(int(r[field]) for r in block)
    return result


def verify_payload(payload):
    errors=[];rows=payload['assessment'];manifest=payload['task_manifest']
    if len({r['id'] for r in manifest})!=len(manifest):errors.append('duplicate_task_manifest')
    expected={(seed,method,t['id']) for seed in payload['seeds'] for method in WAVE14_METHODS for t in manifest}
    actual=[(r['source_seed'],r['method'],r['task_id']) for r in rows]
    if len(actual)!=len(set(actual)) or set(actual)!=expected:errors.append('incomplete_grid')
    if payload['methods']!=list(WAVE14_METHODS):errors.append('method_grid')
    if len(payload['seeds'])!=len(set(payload['seeds'])):errors.append('duplicate_seeds')
    if payload['seeds']!=[0,1,2] or len(manifest)!=18:errors.append('locked_grid')
    for row in rows:
        if any(type(row.get(k)) is not int or row[k]<0 for k in WORK_KEYS+PRIMITIVE_KEYS):errors.append('cost_schema')
        if sum(row[k] for k in WORK_KEYS)!=row['total_work']:errors.append('work_identity')
        if sum(row[k] for k in PRIMITIVE_KEYS)!=row['total_primitive_op_steps']:errors.append('primitive_identity')
        if row['private_before_lock']:errors.append('private_before_lock')
        if row['status']=='unique':
            if len(row['private_evaluations'])!=4:errors.append('private_grid')
            ok=True
            for obs in row['public_observations']:
                if list(execute_wave14_program_ast(row['program_ast'],obs['input']))!=obs['observed_output']:errors.append('public_replay')
            for obs in row['private_evaluations']:
                pred=list(execute_wave14_program_ast(row['program_ast'],obs['input']))
                if pred!=obs['predicted_output']:errors.append('private_replay')
                ok=ok and pred==obs['ground_truth_output']
            if ok!=row['private_correct']:errors.append('outcome_flag')
        diag=row['support_gate']
        if 'index_hash_probes' in diag:
            expected_archive=diag['archive_public_evals']+diag['index_build_evals']+diag['index_hash_probes']
            if expected_archive!=row['archive_lookup_evals']:errors.append('archive_work_identity')
            if diag['index_build_primitive_steps']>row['archive_primitive_op_steps']:errors.append('archive_primitive_accounting')
        if diag.get('aborted_before_piecewise'):
            if diag['piecewise_evaluations'] or diag['piecewise_primitive_steps']:errors.append('abort_cost')
        initial=diag.get('initial_pairs',[]);strict={i for i,(x,y) in enumerate(initial) if x!=y};covers=[]
        for item in diag.get('evaluated_partial_transforms',[]):
            node=expr_ast_from_dict(item['ast'])
            mask={i for i in strict if list(eval_expr_ast(node,initial[i][0]))==initial[i][1]}
            if mask!=set(item['coverage']):errors.append('coverage_replay')
            covers.append(mask)
        if diag.get('gate1') is not None:
            snapshot=[set(m) for m in diag['gate_coverage_snapshot']]
            if any(m not in covers for m in snapshot):errors.append('gate_snapshot')
            gate1=any(len(m)>=2 for m in snapshot)
            gate2=any(len(a)>=2 and len(strict-a)>=1 and a|b==strict for a in snapshot for b in snapshot)
            if gate1!=diag['gate1'] or gate2!=diag['gate2']:errors.append('support_gate')
    if totals(rows)!=payload['totals']['suite']:errors.append('suite_totals')
    for split in {r['split'] for r in rows}:
        if totals([r for r in rows if r['split']==split])!=payload['totals'].get(split):errors.append('split_totals')
    if evaluate_gates(rows)!=payload['gates']:errors.append('scientific_gate_arithmetic')
    if digest({k:payload[k] for k in ('kind','assessment','totals','gates')})!=payload['hash']:errors.append('payload_hash')
    if payload['usage']['model_calls']!=0 or payload['usage']['frozen_debit_s']!=0:errors.append('track_b_execution')
    return dict(valid=not errors,errors=errors,replayed_rows=len(rows),scientific_gates_passed=payload['gates']['passed'])


def main():
    path=ROOT/'artifacts/seed_wave16_peeled_archive_enumerator.json'
    payload=json.loads(path.read_text());report=verify_payload(payload)
    from nexus.seed.mechanism_wave16_fresh_assessment import fresh_cases
    expected_manifest=[dict(id=c[0],split=c[2],gold=c[4]) for c in fresh_cases()]
    report['locked_manifest']=expected_manifest==payload['task_manifest']
    report['holdout_hash_match']=hashlib.sha256((ROOT/HOLDOUT).read_bytes()).hexdigest()==payload['registration']['holdout_sha256']
    freeze=freeze_sha();names=subprocess.check_output(['git','ls-tree','-r','--name-only',freeze],cwd=ROOT,text=True).splitlines()
    report['commit1_blindness']=HOLDOUT not in names
    report['phase1_zero_diff']=not bool(subprocess.check_output(['git','diff',freeze,'--',*FROZEN_PATHS],cwd=ROOT))
    report['hashes_match']=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in payload['registration']['phase1_hashes'].items())
    report['runtime_unchanged']=hashlib.sha256((ROOT/'src/nexus/seed/local_model_runtime.py').read_bytes()).hexdigest()==payload['registration']['runtime_sha256']
    tree=ast.parse((ROOT/FROZEN_PATHS[0]).read_text())
    report['lambda_count']=sum(isinstance(node,ast.Lambda) for node in ast.walk(tree))
    report['valid']=report['valid'] and report['locked_manifest'] and report['holdout_hash_match'] and report['commit1_blindness'] and report['phase1_zero_diff'] and report['hashes_match'] and report['runtime_unchanged'] and report['lambda_count']==0
    with (ROOT/'artifacts/seed_wave16_verification.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))
    return 0 if report['valid'] and report['scientific_gates_passed'] else 1


if __name__=='__main__':raise SystemExit(main())


