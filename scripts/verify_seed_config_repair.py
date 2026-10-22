"""Independently verify saved manifest coverage, repairs, costs and exact caches.

Replay saved patched source in bounded CPython workers; no new tasks, policies,
model inference, fitting or result replacement. Default is read-only.
"""
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nexus.seed.config_repair_baseline import evaluate


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def verify(records, config, summary, replay=True):
    rows = [r for r in records if r.get('kind') == 'task']
    expected = {t['id']: t for t in config['tasks']}
    if len(rows) != len(expected) or {r['id']: r['cohort'] for r in rows} != {k:v['cohort'] for k,v in expected.items()}:
        raise ValueError('missing_duplicate_or_wrong_task')
    caches = [r for r in records if r.get('kind') == 'cache']
    if len(caches) != 1: raise ValueError('missing_cache_accounting')
    receipts = {}; reconstructed_cache = {}; public_runs = 0; assessment_runs = 0; project_calls = 0
    for row in rows:
        if 'failure' in row: raise ValueError('invalid_or_incomplete_execution')
        spec = expected[row['id']]; key, default = spec['key'], spec['default']
        if row['contract'] != dict(key=key, default=default): raise ValueError('wrong_contract')
        public = row['public']
        if digest(row['files']) != row['locked_patch_sha256']: raise ValueError('unlocked_patch')
        cache_key = digest([public['request'], public['files'], public['tests'], row['contract']])
        if row['cache_key'] != cache_key: raise ValueError('wrong_cache_key')
        if type(row['cache_hit']) is not bool: raise ValueError('invalid_cache_flag')
        if any(type(v) is not int for v in row['tools'].values()): raise ValueError('invalid_tool_count')
        if row['cache_hit']:
            if cache_key not in receipts or row['public_receipt_sha256'] != receipts[cache_key]: raise ValueError('unearned_validation_cache_hit')
            if row['tools'] != dict(project_subprocesses=0, candidate_plans=0): raise ValueError('reused_work_counted_twice')
        else:
            for name in ('original_public', 'patched_public'):
                if len(row[name]['results']) != len(public['tests']): raise ValueError('missing_public_test')
            if all(r['passed'] for r in row['original_public']['results']): raise ValueError('fixture_was_not_broken')
            passed = all(r['passed'] for r in row['patched_public']['results'])
            if row['public_passed'] != passed: raise ValueError('wrong_public_summary')
            receipt = digest([row['files'], public['tests'], row['patched_public']['results']])
            if row['public_receipt_sha256'] != receipt: raise ValueError('wrong_validation_receipt')
            if passed:
                receipts[cache_key] = receipt
                reconstructed_cache[cache_key] = dict(files=row['files'], edits=row['edits'], receipt=receipt)
            if row['tools'] != dict(project_subprocesses=2, candidate_plans=1): raise ValueError('wrong_tool_counts')
            public_runs += 2; project_calls += 2*len(public['tests'])
        cases = row['assessment_cases']; results = row['assessment']['results']
        if len(cases) != 14 or len(results) != 14: raise ValueError('missing_final_or_retention_case')
        for case, result in zip(cases, results):
            entry = case['entry']; value = case['input']
            if entry in ('app.run', 'cfgparse.read'):
                raw = value.get(key)
                expected_value = default if raw is None else int(raw)
            elif entry == 'engine.consume': expected_value = default if value is None else value
            elif entry == 'cfgparse.legacy_fallback': expected_value = value or default
            else: raise ValueError('unregistered_final_entry')
            if case['expected'] != expected_value: raise ValueError('wrong_evaluator_reference')
            passed = result.get('trace') is None and type(result['actual']) is type(expected_value) and result['actual'] == expected_value
            if type(result['passed']) is not bool or result['passed'] != passed: raise ValueError('forged_test_result')
        if row['final_passed'] != all(r['passed'] for r in results): raise ValueError('forged_task_result')
        if replay:
            actual = evaluate(row['files'], cases)['results']
            if [(r['actual'],r['passed']) for r in actual] != [(r['actual'],r['passed']) for r in results]:
                raise ValueError('saved_patch_does_not_reproduce')
        assessment_runs += 1; project_calls += len(cases)
        for field, value in row['stages'].items():
            if type(value) not in (int, float) or not 0 <= value < float('inf'): raise ValueError('invalid_stage')
        for report in [row['assessment']] + ([] if row['cache_hit'] else [row['original_public'], row['patched_public']]):
            for field in ('wall_s', 'compilation_s', 'tests_s', 'internal_s', 'process_overhead_residual_s'):
                value = report[field]
                if type(value) not in (int,float) or not 0 <= value < float('inf'): raise ValueError('invalid_timing')
            if abs(report['process_overhead_residual_s']-max(0,report['wall_s']-report['internal_s'])) > 1e-12:
                raise ValueError('overhead_arithmetic')
    if caches[0]['entries'] != len(reconstructed_cache) or caches[0]['serialized_bytes'] != len(json.dumps(reconstructed_cache).encode()):
        raise ValueError('wrong_cache_storage_accounting')
    if any(type(caches[0][k]) is not int or caches[0][k] != 0 for k in ('model_calls','training_updates','new_environment_steps','learned_abstractions')):
        raise ValueError('wrong_execution_scope')
    primary = [r for r in rows if r['cohort'] == 'primary']
    discoveries = [sum(r['stages'][k] for k in ('source_index_search_s','fault_localization_s','patch_construction_s')) for r in primary]
    accuracy = sum(r['final_passed'] for r in primary)/len(primary)
    median = statistics.median(discoveries); fraction = sum(discoveries)/sum(r['wall_s'] for r in primary)
    s = config['screen']; passed = accuracy >= s['minimum_accuracy'] and median >= s['minimum_discovery_s'] and fraction >= s['minimum_discovery_fraction']
    expected_summary = dict(declared_complete=True, primary_tasks=len(primary), total_tasks=len(rows), primary_accuracy=accuracy,
        all_final_passed=sum(r['final_passed'] for r in rows), median_discovery_s=median,
        discovery_fraction_of_repair_wall=fraction, practical_headroom_passed=passed,
        cache_hits=sum(r['cache_hit'] for r in rows), model_calls=0,
        verdict='PREPARE_SEPARATE_LEARNING_COMPARISON' if passed else 'NO_PRACTICAL_DISCOVERY_HEADROOM', ready_for_learning_study=False)
    if summary != expected_summary: raise ValueError('summary_arithmetic')
    return dict(valid=True, summary=expected_summary, public_project_processes=public_runs,
                final_project_processes=assessment_runs, measured_project_function_calls=project_calls,
                saved_patch_replay_processes=len(rows) if replay else 0, neural_calls=0)


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__); p.add_argument('--save-audit', action='store_true'); args = p.parse_args()
    config_path = ROOT/'configs/seed_config_repair_baseline.json'
    config = json.loads(config_path.read_text())
    result = json.loads((ROOT/'artifacts/seed_config_repair_baseline.json').read_text())
    raw = (ROOT/'artifacts/seed_config_repair_baseline_raw.jsonl').read_bytes()
    for path, expected in [(config_path, result['registration']['config_sha256']),
                          (ROOT/'docs/NEXUS_SEED_CONFIG_REPAIR_PROTOCOL.md', result['registration']['protocol_sha256']),
                          (ROOT/'src/nexus/seed/local_model_runtime.py', result['registration']['runtime_source_sha256'])]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected: raise ValueError('provenance_hash')
    if hashlib.sha256(raw).hexdigest() != result['raw_sha256']: raise ValueError('raw_hash')
    audit = verify([json.loads(s) for s in raw.splitlines()], config, result['summary'])
    if args.save_audit:
        from nexus.seed.experimental import Sandbox
        events = Sandbox(ROOT).events()
        new = [e for e in events if json.loads(e.payload_json).get('run_id') == config['id'] or e.kind == 'grant' and json.loads(e.payload_json).get('id') == config['id']]
        prior = new[0].sequence-1
        ledger = dict(previous_anchor=events[prior].fingerprint, prior_sequence=prior, count=len(new),
                      accounted_balance_before_reconciliation_s=result['registration']['carried_used_s'],
                      events=[asdict(e) for e in new], head=new[-1].fingerprint)
        previous = json.loads((ROOT/'artifacts/seed_candidate_identifiability_audit.json').read_text())['ledger']['head']
        if ledger['previous_anchor'] != previous: raise ValueError('ledger_anchor')
        spec = importlib.util.spec_from_file_location('existing_ledger_verifier', ROOT/'scripts/analyze_seed_assistant_benchmark_v2.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        ledger['reconstructed_used_s'] = module.verify_ledger(ledger)
        if ledger['reconstructed_used_s'] != result['resources']['session_used_s']: raise ValueError('ledger_balance')
        audit.update(ledger=ledger, execution_sha=result['registration']['source_sha'], raw_sha256=result['raw_sha256'])
        with (ROOT/'artifacts/seed_config_repair_baseline_audit.json').open('x') as f:
            json.dump(audit,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(audit,indent=2,sort_keys=True))
