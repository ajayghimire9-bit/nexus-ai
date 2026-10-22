"""Independent saved-data arithmetic/output audit; no model or outcome collection."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]


def reference(plan, columns, rows, threshold):
    groups = {}
    for row in rows:
        key = str(row[columns[plan['key']]]).strip().lower()
        a, b = float(row[columns[2+plan['lhs']]]), float(row[columns[2+plan['rhs']]])
        value = round({'add': lambda: a+b, 'sub': lambda: a-b, 'mul': lambda: a*b}[plan['arithmetic']](), 2)
        if plan['placement'] == 'before' and value < threshold:
            continue
        groups.setdefault(key, []).append(value)
    result = []
    for key, values in sorted(groups.items()):
        value = round({'sum': lambda: sum(values), 'mean_round2': lambda: sum(values)/len(values),
                       'max': lambda: max(values)}[plan['aggregate']](), 2)
        if plan['placement'] == 'after' and value < threshold:
            continue
        result.append(dict(group=key, value=value))
    return result


def verify(records, config, summary):
    expected = {f'task_{i:02}': 'source' if i < config['source_tasks'] else 'new_composition'
                for i in range(config['source_tasks']+config['composition_tasks'])}
    expected.update({f'{cohort}_{i}': cohort for cohort in ('explicit', 'renamed', 'repeat')
                     for i in range(config['control_pairs'])})
    tasks = [r for r in records if r.get('kind') == 'task']
    if len(tasks) != len(expected) or {r['id']: r['cohort'] for r in tasks} != expected:
        raise ValueError('missing_duplicate_or_wrong_cohort')
    if sum(r.get('kind') == 'construction' for r in records) != 1 or sum(r.get('kind') == 'cache_accounting' for r in records) != 1:
        raise ValueError('missing_accounting')
    for row in tasks:
        for field in ('discovery_s', 'validation_s', 'retention_s', 'execution_s'):
            value = row.get(field)
            if type(value) not in (int, float) or not 0 <= value < float('inf'):
                raise ValueError('invalid_timing')
        for field in ('questions', 'candidate_executions', 'fragment_executions', 'validation_executions',
                      'initial_survivors', 'final_survivors'):
            if type(row.get(field)) is not int or row[field] < 0:
                raise ValueError('invalid_count')
        if len(row['locked_probes']) != row['questions'] or len(set(row['locked_probes'])) != row['questions'] or row['questions'] > config['max_questions']:
            raise ValueError('question_budget_or_lock')
        if any(type(i) is not int or not 0 <= i < config['probe_batches'] for i in row['locked_probes']):
            raise ValueError('invalid_probe')
        if reference(row['truth'], row['columns'], row['assessment'], config['threshold']) != row['expected']:
            raise ValueError('wrong_reference')
        if reference(row['truth'], row['columns'], row['demonstration'], config['threshold']) != row['demonstration_output']:
            raise ValueError('wrong_demonstration')
        output = reference(row['selected'], row['columns'], row['assessment'], config['threshold']) if row['selected'] else None
        if output != row['output'] or type(row['correct']) is not bool or row['correct'] != (output == row['expected']):
            raise ValueError('forged_output_or_correctness')
        if row['cohort'] in ('explicit', 'repeat') and (row['candidate_executions'] or row['questions']):
            raise ValueError('artificial_search_in_control')
    accounting = next(r for r in records if r['kind'] == 'cache_accounting')
    if accounting['executions'] != sum(r['candidate_executions'] for r in tasks):
        raise ValueError('cached_executions_counted_again')
    if accounting['fragment_executions'] != sum(r['fragment_executions'] for r in tasks):
        raise ValueError('fragment_accounting')
    source = {tuple(r['truth'][k] for k in ('arithmetic', 'aggregate', 'placement')) for r in tasks if r['cohort'] == 'source'}
    novel = [r for r in tasks if r['cohort'] == 'new_composition']
    target = {tuple(r['truth'][k] for k in ('arithmetic', 'aggregate', 'placement')) for r in novel}
    if source & target:
        raise ValueError('repeated_composition_not_novel')
    accuracy = sum(r['correct'] for r in novel)/len(novel)
    ambiguity = sum(r['initial_survivors'] > 1 for r in novel)/len(novel)
    median = statistics.median(r['discovery_s'] for r in novel)
    fraction = sum(r['discovery_s'] for r in novel)/sum(sum(r[k] for k in ('discovery_s', 'validation_s', 'retention_s', 'execution_s')) for r in novel)
    for field, value in dict(novel_accuracy=accuracy, ambiguous_fraction=ambiguity, median_discovery_s=median,
                             discovery_fraction=fraction, new_compositions=len(target)).items():
        if summary.get(field) != value:
            raise ValueError('wrong_summary_'+field)
    s = config['screen']
    gates = dict(complete=True, accuracy=accuracy >= s['minimum_accuracy'], ambiguity=ambiguity >= s['minimum_ambiguous_fraction'],
                 absolute_discovery=median >= s['minimum_median_discovery_s'], discovery_fraction=fraction >= s['minimum_discovery_fraction'],
                 new_compositions=len(target) >= s['minimum_new_compositions'])
    if summary['gates'] != gates or summary['symbolic_screen_passed'] != all(gates.values()) or summary['ready_for_learning_study'] is not False:
        raise ValueError('wrong_gate_or_promotion')
    return dict(valid=True, tasks=len(tasks), questions=sum(r['questions'] for r in tasks),
                authored_response_events=2*len(tasks)+sum(r['questions'] for r in tasks),
                outputs_independently_recomputed=True, neural_calls=0,
                cohorts={cohort: dict(n=sum(r['cohort'] == cohort for r in tasks),
                            correct=sum(r['correct'] for r in tasks if r['cohort'] == cohort),
                            questions=sum(r['questions'] for r in tasks if r['cohort'] == cohort)) for cohort in set(expected.values())})


if __name__ == '__main__':
    result = json.loads((ROOT/'artifacts/seed_discovery_headroom.json').read_text())
    raw = (ROOT/'artifacts/seed_discovery_headroom_raw.jsonl').read_bytes()
    config_bytes = (ROOT/'configs/seed_discovery_headroom.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != result['raw_sha256'] or hashlib.sha256(config_bytes).hexdigest() != result['registration']['config_sha256']:
        raise ValueError('provenance_hash_mismatch')
    for path, field in [('docs/NEXUS_SEED_DISCOVERY_HEADROOM_PROTOCOL.md', 'protocol_sha256'),
                        ('src/nexus/seed/local_model_runtime.py', 'runtime_source_sha256')]:
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != result['registration'][field]:
            raise ValueError('frozen_source_mismatch')
    print(json.dumps(verify([json.loads(line) for line in raw.splitlines()], json.loads(config_bytes), result['summary']), indent=2, sort_keys=True))
