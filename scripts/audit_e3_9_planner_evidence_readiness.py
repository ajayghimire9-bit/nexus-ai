"""Hash/AST/arithmetic audit. Never imports models or constructs environments."""
import argparse
import ast
import hashlib
import itertools
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'configs/e3_9_planner_evidence_readiness.json'
OUTPUT = ROOT/'artifacts/e3_9_planner_evidence_readiness.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def budget(c):
    """Declared worst-case arithmetic, not a resource meter or allocation."""
    if any(type(v) is not int or v<1 for k,v in c.items() if k!='evidence_frequency'):
        raise ValueError('positive_integer_budget_counts')
    if c['evidence_frequency']!='per_remaining_decision_upper_bound':
        raise ValueError('explicit_evidence_frequency')
    if c['probe_steps']+c['remaining_steps']!=200:raise ValueError('episode_budget')
    pairs=c['model_count']*(c['training_episodes_per_model']+c['evaluation_episodes_per_model'])
    decisions=pairs*c['conditions']*c['remaining_steps']
    extra=c['evidence_sets']*c['evidence_candidates']*c['evidence_horizon']
    return dict(shared_probe_interactions=pairs*c['probe_steps'],
        remaining_evaluation_interactions=decisions,
        total_real_interactions=pairs*c['probe_steps']+decisions,
        controller_imagined_upper=decisions*c['planning_imagined_per_decision'],
        evidence_imagined_upper=decisions*extra,
        combined_imagined_upper=decisions*(c['planning_imagined_per_decision']+extra),
        per_case_controller_imagined=c['remaining_steps']*c['planning_imagined_per_decision'],
        per_case_combined_imagined=c['remaining_steps']*(c['planning_imagined_per_decision']+extra),
        evidence_model_calls_upper=decisions*c['evidence_sets']*c['evidence_horizon'],
        evidence_network_forwards_upper_if_one_per_call=decisions*c['evidence_sets']*c['evidence_horizon'],
        allocation=False,registered=False,
        note='Illustration only; candidate proposal generation beyond the controller cap is additional. No wall-time estimate is inferred.')


def inventory(root,c):
    for key in ('fit_manifest','source_inventory','draft_manifest'):
        if sha(root/c[key])!=c[key+'_sha256']:raise ValueError('pinned_'+key+'_mismatch')
    families=c['families'];bundles=c['model_bundles'];splits=c['source_splits']
    if families!=['pendulum','acrobot'] or bundles!=[0,1] or splits!=['train','val']:
        raise ValueError('locked_inventory_axes')
    fits=json.loads((root/c['fit_manifest']).read_text())['fits']
    selected=[r for r in fits if r['family'] in families and r['bundle'] in bundles]
    ids=[(r['family'],r['bundle']) for r in selected]
    if len(ids)!=4 or set(ids)!=set(itertools.product(families,bundles)):
        raise ValueError('checkpoint_grid')
    tree=ast.parse((root/c['source_inventory']).read_text())
    constants=[ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='LOCKED_ARRAYS' for t in n.targets)]
    if len(constants)!=1:raise ValueError('source_inventory_literal')
    arrays=[r for r in constants[0] if r['family'] in families and r['bundle'] in bundles]
    ids=[(r['family'],r['bundle'],r['split']) for r in arrays]
    expected=set(itertools.product(families,bundles,splits))
    if len(ids)!=len(expected) or set(ids)!=expected:raise ValueError('source_array_grid')
    def check(rows):
        out=[]
        for r in rows:
            path=root/r['path']
            if not path.resolve().is_relative_to(root.resolve()):raise ValueError('repository_path_only')
            actual=sha(path) if path.is_file() else None
            out.append({k:r[k] for k in ('family','bundle','path','sha256')} |
                dict(actual_sha256=actual,present=path.is_file(),matches=actual==r['sha256']))
        return out
    checkpoints=check(selected);sources=check(arrays)
    return dict(checkpoints=checkpoints,source_arrays=sources,
        all_files_match=all(r['matches'] for r in checkpoints+sources),
        checkpoint_contents_loaded=False,source_arrays_deserialized=False)


def audit(root,c):
    files=inventory(root,c);draft=json.loads((root/c['draft_manifest']).read_text())
    blocks=['production_metered_host_not_bound','fresh_task_seed_grid_not_registered',
        'experiment_protocol_and_allocation_not_frozen','evidence_frequency_and_comparator_compute_not_locked',
        'fresh_feedback_fit_evaluation_split_and_analysis_not_locked']
    if not files['all_files_match']:blocks.insert(0,'checkpoint_or_source_file_missing_or_mismatched')
    if draft['registered'] is not False or draft['authorized'] is not False or draft['cases']:
        raise ValueError('unexpected_draft_registration')
    return dict(kind=c['kind'],verdict='BLOCKED_FRESH_STUDY_NOT_READY',
        integrity=files,blockers=blocks,budget_illustration=budget(c['budget_illustration']),
        scientific_execution=False,model_inference=False,model_training=False,
        new_real_steps=0,new_imagined_transitions=0,
        session_ledger=dict(used_s=c['session_used_s'],remaining_s=c['session_remaining_s'],unchanged=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--require-checkpoints',action='store_true',help='Exit nonzero on missing/wrong files; never skip requested integrity verification.')
    args=parser.parse_args();c=json.loads(CONFIG.read_text())
    old={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'artifacts').rglob('*.json'))}
    result=audit(ROOT,c)
    if any(sha(ROOT/p)!=h for p,h in old.items()):raise ValueError('historical_artifact_changed')
    result.update(execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        config_sha256=sha(CONFIG),script_sha256=sha(Path(__file__)),
        historical_json_sha256=old,historical_json_preserved=len(old))
    with args.output.open('x') as handle:json.dump(result,handle,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps(dict(verdict=result['verdict'],all_files_match=result['integrity']['all_files_match'],
        checkpoints=len(result['integrity']['checkpoints']),source_arrays=len(result['integrity']['source_arrays']))))
    return int(args.require_checkpoints and not result['integrity']['all_files_match'])


if __name__=='__main__':raise SystemExit(main())
