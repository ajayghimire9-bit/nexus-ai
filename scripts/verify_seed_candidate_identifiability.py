"""Independent saved-evidence reconstruction and counterexample arithmetic."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nexus.seed.discovery_headroom import grammar


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


reference = load_script('independent_data_reference', 'scripts/verify_seed_discovery_headroom.py').reference


def normalized(plan):
    plan = dict(plan)
    if plan['arithmetic'] in ('add', 'mul'):
        plan['lhs'], plan['rhs'] = sorted((plan['lhs'], plan['rhs']))
    if plan['aggregate'] == 'max' and plan['placement'] == 'after': plan['placement'] = 'before'
    return plan


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def verify(rows, config, source, source_config, summary):
    rows = [r for r in rows if r.get('kind') == 'case']
    if len(rows) != len(config['expected_ids']) or {r['id'] for r in rows} != set(config['expected_ids']):
        raise ValueError('missing_duplicate_case')
    source = {r['id']: r for r in source if r.get('kind') == 'task'}
    for row in rows:
        for field in ('original_remaining', 'canonical_classes', 'examined', 'prediction_executions',
                      'worst_remaining', 'reconstruction_executions', 'saved_answer_reconstructions', 'new_answers'):
            if type(row.get(field)) is not int or row[field] < 0: raise ValueError('invalid_count')
        if type(row.get('primary')) is not bool: raise ValueError('invalid_unit_flag')
        original = source[row['id']]; columns = original['columns']
        observations = [(original['demonstration'], original['demonstration_output'])]
        for index in original['locked_probes']:
            batch = original['probes'][index]
            observations.append((batch, reference(original['truth'], columns, batch, source_config['threshold'])))
        plans = [p.__dict__ for p in grammar(source_config)]; executions = 0
        for batch, expected in observations:
            executions += len(plans)
            plans = [p for p in plans if reference(p, columns, batch, source_config['threshold']) == expected]
        if plans != row['candidates'] or len(plans) != original['final_survivors'] or row['reconstruction_executions'] != executions:
            raise ValueError('wrong_reconstructed_candidates')
        if row['columns'] != columns or row['primary'] != (row['id'] in config['primary_ids']):
            raise ValueError('wrong_schema_or_unit')
        if row['new_answers'] != 0 or row['assessment_access'] is not False or row['saved_answer_reconstructions'] != len(observations)-1:
            raise ValueError('data_boundary')
        for field in ('elapsed_s', 'reconstruction_s', 'recorded_discovery_s', 'hypothetical_combined_discovery_s'):
            if type(row[field]) not in (int, float) or not 0 <= row[field] < float('inf'):
                raise ValueError('nonfinite_timing')
        if row['recorded_discovery_s'] != original['discovery_s'] or row['hypothetical_combined_discovery_s'] != row['recorded_discovery_s']+row['elapsed_s']:
            raise ValueError('cost_arithmetic')
        classes = {encode(normalized(p)) for p in plans}
        if row['canonical_classes'] != len(classes): raise ValueError('wrong_canonical_count')
        label, witness = row['classification'], row['witness']
        if label == 'PROVEN_EQUIVALENT':
            if len(classes) != 1 or witness is not None or row['prediction_executions'] != 0 or row['worst_remaining'] != 1:
                raise ValueError('unjustified_equivalence')
        elif label == 'MEANINGFULLY_DIFFERENT':
            if not witness or {encode(p) for p in witness['representatives']} != classes:
                raise ValueError('wrong_witness_candidates')
            if not 1 <= len(witness['rows']) <= 2: raise ValueError('invalid_probe_rows')
            for sample in witness['rows']:
                if set(sample) != set(columns) or any(not 0 <= float(sample[c]) <= 15 for c in columns[2:]):
                    raise ValueError('out_of_domain_witness')
            predictions = [reference(p, columns, witness['rows'], source_config['threshold']) for p in witness['representatives']]
            partitions = list(Counter(encode(p) for p in predictions).values())
            if predictions != witness['predictions'] or partitions != witness['partition_sizes'] or len(partitions) < 2:
                raise ValueError('not_a_counterexample')
            if row['worst_remaining'] != max(partitions): raise ValueError('wrong_partition_bound')
        elif label != 'UNKNOWN' or witness is not None or row['worst_remaining'] != len(classes):
            raise ValueError('invalid_classification')
        if type(row['examined']) is not int or not 0 <= row['examined'] <= config['maximum_probe_candidates']:
            raise ValueError('probe_budget')
        if row['prediction_executions'] != row['examined']*len(classes): raise ValueError('prediction_accounting')
    primary = [r for r in rows if r['id'] in config['primary_ids']]
    counts = {label: sum(r['classification'] == label for r in primary)
              for label in ('PROVEN_EQUIVALENT', 'MEANINGFULLY_DIFFERENT', 'UNKNOWN')}
    median = statistics.median(r['hypothetical_combined_discovery_s'] for r in primary)
    cheap = all(r['worst_remaining'] == 1 for r in primary) and median < config['cheap_resolution_s']
    action = ('INCONCLUSIVE_COVERAGE' if counts['UNKNOWN'] else 'PREPARE_DIFFERENT_PRACTICAL_TASK_FAMILY' if cheap
              else 'IMPROVE_CANONICALIZATION' if counts['PROVEN_EQUIVALENT'] > len(primary)/2 else 'IMPROVE_PROBE_CONSTRUCTION')
    expected_summary = dict(declared_complete=True, primary_cases=len(primary), descriptive_cases=len(rows),
        classification_counts=counts, median_probe_construction_s=statistics.median(r['elapsed_s'] for r in primary),
        median_hypothetical_combined_discovery_s=median, cheap_resolution=cheap, new_answers=0,
        predicted_remaining_before=sum(r['original_remaining'] for r in primary)/len(primary),
        predicted_worst_remaining_after=sum(r['worst_remaining'] for r in primary)/len(primary),
        verdict=action, ready_for_learning_study=False)
    if summary != expected_summary: raise ValueError('incorrect_summary')
    return dict(valid=True, cases=len(rows), primary_requests=len(primary), summary=expected_summary,
                reconstruction_executions=sum(r['reconstruction_executions'] for r in rows),
                new_probe_prediction_executions=sum(r['prediction_executions'] for r in rows),
                new_teacher_answers=0, final_assessments_scored=0)


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__); p.add_argument('--save-audit', action='store_true'); args = p.parse_args()
    config_path = ROOT/'configs/seed_candidate_identifiability.json'
    config = json.loads(config_path.read_text())
    result = json.loads((ROOT/'artifacts/seed_candidate_identifiability.json').read_text())
    raw = (ROOT/'artifacts/seed_candidate_identifiability_raw.jsonl').read_bytes()
    for path, expected in config['inputs'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != expected: raise ValueError('input_hash_mismatch')
    for path, expected in [(config_path, result['registration']['config_sha256']),
                           (ROOT/'docs/NEXUS_SEED_CANDIDATE_IDENTIFIABILITY_PROTOCOL.md', result['registration']['protocol_sha256']),
                           (ROOT/'src/nexus/seed/local_model_runtime.py', result['registration']['runtime_source_sha256'])]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected: raise ValueError('provenance_mismatch')
    if hashlib.sha256(raw).hexdigest() != result['raw_sha256']: raise ValueError('raw_hash_mismatch')
    source = [json.loads(s) for s in (ROOT/'artifacts/seed_discovery_headroom_raw.jsonl').read_text().splitlines()]
    source_config = json.loads((ROOT/'configs/seed_discovery_headroom.json').read_text())
    audit = verify([json.loads(s) for s in raw.splitlines()], config, source, source_config, result['summary'])
    if args.save_audit:
        from nexus.seed.experimental import Sandbox
        events = Sandbox(ROOT).events()
        new = [e for e in events if json.loads(e.payload_json).get('run_id') == config['id'] or
               e.kind == 'grant' and json.loads(e.payload_json).get('id') == config['id']]
        prior = new[0].sequence-1
        ledger = dict(previous_anchor=events[prior].fingerprint, prior_sequence=prior, count=len(new),
                      accounted_balance_before_reconciliation_s=result['registration']['carried_used_s'],
                      events=[asdict(e) for e in new], head=new[-1].fingerprint)
        previous = json.loads((ROOT/'artifacts/seed_discovery_headroom_audit.json').read_text())['ledger']['head']
        if ledger['previous_anchor'] != previous: raise ValueError('ledger_not_anchored_to_previous_study')
        verifier = load_script('existing_e1_accounting', 'scripts/analyze_seed_assistant_benchmark_v2.py')
        ledger['reconstructed_used_s'] = verifier.verify_ledger(ledger)
        if ledger['reconstructed_used_s'] != result['resources']['session_used_s']: raise ValueError('ledger_balance')
        audit.update(ledger=ledger, execution_sha=result['registration']['source_sha'], raw_sha256=result['raw_sha256'])
        with (ROOT/'artifacts/seed_candidate_identifiability_audit.json').open('x') as f:
            json.dump(audit, f, indent=2, sort_keys=True); f.write('\n')
    print(json.dumps(audit, indent=2, sort_keys=True))
