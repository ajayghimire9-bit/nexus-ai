"""Saved-candidate equivalence and answer-free witness construction.

Reuses discovery_headroom.Plan, grammar, and the existing vetted AST executor.
Nothing here updates the persistent runtime, library, or historical benchmark.
"""
from dataclasses import replace
from itertools import product, islice
import hashlib
import json
from pathlib import Path
import statistics
import time

from nexus.seed.discovery_headroom import Plan, canonical, execute, grammar


def normal_form(plan):
    """Only algebraically justified rules, not finite-sample equivalences."""
    if plan.arithmetic in ('add', 'mul') and plan.lhs > plan.rhs:
        plan = replace(plan, lhs=plan.rhs, rhs=plan.lhs)
    if plan.aggregate == 'max' and plan.placement == 'after':
        plan = replace(plan, placement='before')
    return plan


def probe_inputs(columns, values):
    """Small legal inputs exposing boundaries and group aggregation effects.

    No target identity, true plan, answer, or assessment enters this iterator.
    Singleton probes come first; then equal-row, zero-mixed, one-mixed and
    different-group pairs. Enumeration stops as soon as full separation occurs.
    """
    def row(vector, second_group=False):
        return {columns[0]: 'b' if second_group else 'a', columns[1]: 'y' if second_group else 'x',
                **{c: str(v) for c, v in zip(columns[2:], vector)}}
    for vector in product(values, repeat=3):
        yield (row(vector),)
    for pattern in ('equal', 'zero', 'one', 'other_group'):
        for vector in product(values, repeat=3):
            second = vector if pattern in ('equal', 'other_group') else (0, 0, 0) if pattern == 'zero' else (1, 1, 1)
            yield (row(vector), row(second, pattern == 'other_group'))


def construct_probe(candidates, columns, threshold, config):
    started = time.perf_counter()
    representatives = tuple(sorted(set(normal_form(p) for p in candidates)))
    evaluations = 0; best = None; examined = 0
    if len(representatives) == 1:
        return dict(classification='PROVEN_EQUIVALENT', canonical_classes=1, witness=None,
                    examined=0, prediction_executions=0, worst_remaining=1,
                    elapsed_s=time.perf_counter()-started)
    for batch in islice(probe_inputs(columns, config['boundary_values']), config['maximum_probe_candidates']):
        outputs = [execute(plan, columns, batch, threshold) for plan in representatives]
        evaluations += len(representatives); examined += 1
        partitions = {}
        for index, output in enumerate(outputs):
            partitions.setdefault(canonical(output), []).append(index)
        sizes = [len(p) for p in partitions.values()]
        score = (max(sizes), sum(n*n for n in sizes))
        if len(partitions) > 1 and (best is None or score < best[0]):
            best = (score, dict(rows=batch, predictions=outputs,
                               representatives=[p.__dict__ for p in representatives],
                               partition_sizes=sizes))
        if len(partitions) == len(representatives):
            break
    return dict(classification='MEANINGFULLY_DIFFERENT' if best else 'UNKNOWN',
                canonical_classes=len(representatives), witness=best[1] if best else None,
                examined=examined, prediction_executions=evaluations,
                worst_remaining=best[0][0] if best else len(representatives),
                elapsed_s=time.perf_counter()-started)


def observed_case(record, source_config):
    """Recover only responses to ALREADY ASKED probes from the frozen record.

    The original raw format omitted explicit answer bodies. Its saved truth
    program reconstructs just those responses, in an evaluator-side bridge.
    No new probe is answered and no final assessment rows/outcomes are read.
    The witness constructor never receives this record or its truth program.
    """
    columns = tuple(record['columns'])
    observations = [(record['demonstration'], record['demonstration_output'])]
    for index in record['locked_probes']:
        batch = record['probes'][index]
        observations.append((batch, execute(Plan(**record['truth']), columns, batch, source_config['threshold'])))
    return columns, observations


def reconstruct_candidates(columns, observations, source_config):
    candidates = grammar(source_config); executions = 0
    for batch, output in observations:
        survivors = []
        for plan in candidates:
            executions += 1
            if execute(plan, columns, batch, source_config['threshold']) == list(output):
                survivors.append(plan)
        candidates = tuple(survivors)
    return candidates, executions


def run(config, emit):
    root = Path(__file__).resolve().parents[3]
    for path, expected in config['inputs'].items():
        if hashlib.sha256((root/path).read_bytes()).hexdigest() != expected:
            raise ValueError('frozen_input_mismatch:'+path)
    source_config = json.loads((root/'configs/seed_discovery_headroom.json').read_text())
    records = [json.loads(s) for s in (root/'artifacts/seed_discovery_headroom_raw.jsonl').read_text().splitlines()]
    selected = [r for r in records if r.get('kind') == 'task' and r['final_survivors'] > 1]
    if len(selected) != len(config['expected_ids']) or {r['id'] for r in selected} != set(config['expected_ids']):
        raise ValueError('frozen_unresolved_grid_mismatch')
    for record in selected:
        t = time.perf_counter()
        columns, observations = observed_case(record, source_config)
        candidates, reconstructions = reconstruct_candidates(columns, observations, source_config)
        if len(candidates) != record['final_survivors']:
            raise ValueError('candidate_reconstruction_mismatch')
        reconstruction_s = time.perf_counter()-t
        result = construct_probe(candidates, columns, source_config['threshold'], config)
        emit(dict(kind='case', id=record['id'], primary=record['id'] in config['primary_ids'],
                  columns=columns, candidates=[p.__dict__ for p in candidates],
                  original_remaining=len(candidates), reconstruction_executions=reconstructions,
                  saved_answer_reconstructions=len(observations)-1, reconstruction_s=reconstruction_s,
                  recorded_discovery_s=record['discovery_s'],
                  hypothetical_combined_discovery_s=record['discovery_s']+result['elapsed_s'],
                  new_answers=0, assessment_access=False, **result))


def summarize(records, config):
    rows = [r for r in records if r.get('kind') == 'case']
    complete = len(rows) == len(config['expected_ids']) and {r['id'] for r in rows} == set(config['expected_ids'])
    for row in rows:
        complete &= row.get('classification') in ('PROVEN_EQUIVALENT', 'MEANINGFULLY_DIFFERENT', 'UNKNOWN')
        for name in ('elapsed_s', 'reconstruction_s', 'recorded_discovery_s', 'hypothetical_combined_discovery_s'):
            value = row.get(name)
            complete &= type(value) in (int, float) and 0 <= value < float('inf')
    if not complete:
        return dict(declared_complete=False, verdict='INCOMPLETE', ready_for_learning_study=False)
    primary = [r for r in rows if r['id'] in config['primary_ids']]
    counts = {label: sum(r['classification'] == label for r in primary)
              for label in ('PROVEN_EQUIVALENT', 'MEANINGFULLY_DIFFERENT', 'UNKNOWN')}
    median = statistics.median(r['hypothetical_combined_discovery_s'] for r in primary)
    cheap = all(r['worst_remaining'] == 1 for r in primary) and median < config['cheap_resolution_s']
    if counts['UNKNOWN']:
        action = 'INCONCLUSIVE_COVERAGE'
    elif cheap:
        action = 'PREPARE_DIFFERENT_PRACTICAL_TASK_FAMILY'
    elif counts['PROVEN_EQUIVALENT'] > len(primary)/2:
        action = 'IMPROVE_CANONICALIZATION'
    else:
        action = 'IMPROVE_PROBE_CONSTRUCTION'
    return dict(declared_complete=True, primary_cases=len(primary), descriptive_cases=len(rows),
                classification_counts=counts, median_probe_construction_s=statistics.median(r['elapsed_s'] for r in primary),
                median_hypothetical_combined_discovery_s=median, cheap_resolution=cheap,
                new_answers=sum(r['new_answers'] for r in rows),
                predicted_remaining_before=sum(r['original_remaining'] for r in primary)/len(primary),
                predicted_worst_remaining_after=sum(r['worst_remaining'] for r in primary)/len(primary),
                verdict=action, ready_for_learning_study=False)
