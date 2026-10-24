"""Independent saved arithmetic and exact-interpreter replay; no learner run."""
from __future__ import annotations
import itertools
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.capability_evidence import digest
from nexus.seed.wave17_exact_cache_boundary_learner import (
    eval_expr_ast,eval_program,expr_ast_from_dict,canonical_input,WORK_KEYS,
    PRIMITIVE_KEYS,WAVE14_METHODS,PUBLIC_BUDGET,validate_task_fixture_semantics)


def verify_payload(payload,expected_manifest):
    errors=[];rows=payload.get('assessment',[])
    methods=list(WAVE14_METHODS);seeds=[0,1,2]
    manifest=[dict(id=s['id'],split=s['split'],gold=s.get('gold',s.get('gold_status'))) for s in expected_manifest]
    if len(manifest)!=18 or len({s['id'] for s in manifest})!=18:errors.append('expected_manifest')
    if payload.get('methods')!=methods or payload.get('seeds')!=seeds:errors.append('locked_axes')
    if payload.get('task_manifest')!=manifest:errors.append('manifest_mismatch')
    expected=set(itertools.product(seeds,methods,[s['id'] for s in manifest]))
    keys=[(r.get('source_seed'),r.get('method'),r.get('task_id')) for r in rows]
    if set(keys)!=expected or len(keys)!=len(expected):errors.append('incomplete_grid')
    specs={s['id']:s for s in expected_manifest}
    for spec in expected_manifest:
        if 'seeds' in spec and not validate_task_fixture_semantics(spec)['valid']:errors.append('fixture:'+spec['id'])
    for i,row in enumerate(rows):
        label=str(i)
        for k in WORK_KEYS+PRIMITIVE_KEYS:
            if type(row.get(k)) is not int or row[k]<0:errors.append('cost_type:'+label+':'+k)
        if any(type(row.get(k)) is not int for k in WORK_KEYS+PRIMITIVE_KEYS):continue
        if row['total_work']!=sum(row[k] for k in WORK_KEYS):errors.append('work:'+label)
        if row['total_primitive_op_steps']!=sum(row[k] for k in PRIMITIVE_KEYS):errors.append('primitive:'+label)
        if len(row.get('public_read_slots',[]))>PUBLIC_BUDGET:errors.append('public_budget:'+label)
        if len(set(row.get('public_read_slots',[])))!=len(row.get('public_read_slots',[])):errors.append('duplicate_probe:'+label)
        if row.get('private_before_lock') is not False:errors.append('private_boundary:'+label)
        spec=specs.get(row.get('task_id'))
        if not spec:continue
        if row.get('gold_status')!=spec['gold']:errors.append('gold:'+label)
        private_ok=row.get('status')==spec['gold']
        if row.get('status')=='unique':
            for obs in row.get('public_observations',[]):
                if eval_program(row['program_ast'],obs['input'])!=canonical_input(obs['observed_output']):errors.append('public_replay:'+label)
            part=spec.get('seeds',{}).get(row['source_seed'],spec.get('seeds',{}).get(str(row['source_seed'])))
            if part is not None and len(row['private_evaluations'])!=len(part['private']):errors.append('private_count:'+label)
            for obs in row.get('private_evaluations',[]):
                actual=eval_program(row['program_ast'],obs['input'])
                if actual!=canonical_input(obs['predicted_output']):errors.append('private_replay:'+label)
                private_ok=private_ok and actual==canonical_input(obs['ground_truth_output'])
            if part is not None:
                for (x,y),obs in zip(part['private'],row['private_evaluations']):
                    if canonical_input(x)!=canonical_input(obs['input']) or canonical_input(y)!=canonical_input(obs['ground_truth_output']):errors.append('fixture_private:'+label)
        if bool(private_ok)!=row.get('private_correct'):errors.append('scoring:'+label)
        if row.get('mapping_correct')!=(row.get('status')==spec['gold']):errors.append('status_scoring:'+label)
        if row.get('false_unique')!=(row.get('status')=='unique' and not private_ok):errors.append('false_unique_scoring:'+label)
        diag=row.get('support_gate',{})
        cold=set(diag.get('cold_before',[]));used=set(row.get('used_operators',[]))
        receipts=set(diag.get('cold_used',[]))
        if receipts!=cold&used or bool(receipts)!=bool(row.get('cold_archive_reactivated')):
            errors.append('cold_receipt:'+label)
        if not receipts<=set(diag.get('active_after',[])):errors.append('cold_not_active:'+label)
        if diag.get('cached_coverage_mask_errors',0):errors.append('mask_error_counter:'+label)
        pairs=diag.get('coverage_pairs',[])
        strict={j for j,(x,y) in enumerate(pairs) if canonical_input(x)!=canonical_input(y)}
        for record in diag.get('evaluated_partial_transforms',[]):
            node=expr_ast_from_dict(record['ast'])
            cov={j for j,(x,y) in enumerate(pairs) if j in strict and eval_expr_ast(node,x)==canonical_input(y)}
            if cov!=set(record['coverage']):errors.append('coverage_replay:'+label)
        if spec['gold']=='abstain' and (diag.get('piecewise_evaluations') or diag.get('piecewise_primitive_steps')):errors.append('oog_piecewise:'+label)
    independently_summed={}
    for method in methods:
        rs=[r for r in rows if r.get('method')==method]
        independently_summed[method]={k:sum(int(r[k]) for r in rs) for k in (
            'mapping_correct','private_correct','false_unique','cold_archive_reactivated',
            'ambiguous_correctly_declared','total_work','total_primitive_op_steps')}
        independently_summed[method]['n']=len(rs)
    if independently_summed!=payload.get('totals',{}).get('suite'):errors.append('summary_arithmetic')
    for split in sorted({s['split'] for s in manifest}):
        for method in methods:
            block=[r for r in rows if r.get('method')==method and r.get('split')==split]
            saved=payload.get('totals',{}).get(split,{}).get(method,{})
            for k in independently_summed[method]:
                calculated=len(block) if k=='n' else sum(int(r[k]) for r in block)
                if saved.get(k)!=calculated:errors.append('split_arithmetic:'+split+':'+method+':'+k)
    calculated=digest({k:payload[k] for k in ('kind','assessment','totals','gates')})
    if payload.get('hash')!=calculated:errors.append('payload_hash')
    return dict(valid=not errors,errors=errors,replayed_rows=len(rows),totals=independently_summed)


def main():
    from scripts.run_wave17_exact_cache_assessment import check_freeze,OUTPUT
    from nexus.seed.mechanism_wave17_fresh_assessment import fresh_specs
    freeze,_=check_freeze();payload=json.loads((ROOT/OUTPUT).read_text())
    if not payload.get('complete'):
        result=dict(valid=False,errors=['incomplete_execution'],freeze_sha=freeze)
    else:
        result=verify_payload(payload,fresh_specs());result['freeze_sha']=freeze
    output=ROOT/'artifacts/seed_wave17_independent_audit.json'
    with output.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
    return 0 if result['valid'] else 1


if __name__=='__main__':raise SystemExit(main())
