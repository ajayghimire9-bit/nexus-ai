"""Baseline-first workload preflight. No learned abstraction or runtime change.

Reuse the real-data adapter's vetted AST executor. This exact memoized solver
is a source-free baseline, NOT a simulated language-model response. A later
assistant comparison still requires the unchanged persistent runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations, product
import hashlib
import json
import random
import statistics
import time

from nexus.seed.real_data_evaluator_worker import evaluate_serialized_adapter_program


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True, order=True)
class Plan:
    key: int
    lhs: int
    rhs: int
    arithmetic: str
    aggregate: str
    placement: str

    def semantic_composition(self):
        return self.arithmetic, self.aggregate, self.placement

    def ast(self, columns, threshold):
        key = columns[self.key]
        lhs, rhs = columns[2 + self.lhs], columns[2 + self.rhs]
        ops = [dict(op='NormalizeTextField', field=key, ops=['strip', 'lower']),
               dict(op='ParseNumberField', field=lhs),
               dict(op='ParseNumberField', field=rhs),
               dict(op='ComputeDerivedField', target_field='derived',
                    lhs_field=lhs, rhs_field=rhs, arith_op=self.arithmetic)]
        filt = dict(op='FilterNumericThreshold', field='derived', cmp='ge', threshold=threshold)
        if self.placement == 'before':
            ops.append(filt)
        ops.extend([dict(op='GroupByField', key_field=key),
                    dict(op='AggregateGroups', key_field=key, aggregations=[
                        dict(out_col='derived', agg_fn=self.aggregate, src_col='derived')])])
        if self.placement == 'after':
            ops.append(filt)
        ops.extend([dict(op='OrderByFields', keys=[dict(field=key, direction='ASC')])])
        return ops


def execute(plan, columns, rows, threshold):
    result = evaluate_serialized_adapter_program(plan.ast(columns, threshold), rows)
    # Public output has stable names; source-role binding is not supplied.
    return [dict(group=row[columns[plan.key]], value=row['derived']) for row in result]


def grammar(config):
    return tuple(Plan(key, lhs, rhs, arith, agg, place)
                 for key, (lhs, rhs), arith, agg, place in product(
                     range(2), permutations(range(3), 2), config['arithmetic'],
                     config['aggregates'], config['placements'])
                 if (arith == 'sub' or lhs < rhs) and not (agg == 'max' and place == 'after'))


@dataclass(frozen=True)
class PublicTask:
    columns: tuple[str, ...]
    demonstration: tuple[dict, ...]
    demonstration_output: tuple[dict, ...]
    probes: tuple[tuple[dict, ...], ...]
    complete_specification: Plan | None = None


class TeachingOracle:
    """Only selected public probe answers. Final assessment has no API here."""
    def __init__(self, plan, public, threshold, limit):
        self._plan, self._public, self._threshold = plan, public, threshold
        self.limit, self.calls, self.selected = limit, 0, []

    def answer(self, index):
        if index in self.selected or self.calls >= self.limit:
            raise ValueError('duplicate_or_exhausted_question')
        if type(index) is not int or not 0 <= index < len(self._public.probes):
            raise ValueError('unregistered_probe')
        self.selected.append(index)
        self.calls += 1
        return execute(self._plan, self._public.columns,
                       self._public.probes[index], self._threshold)


def rows(rng, columns, count):
    return tuple({columns[0]: rng.choice([' A ', 'B', 'c']),
                  columns[1]: rng.choice(['x', ' Y ', 'z']),
                  **{c: str(rng.randrange(0, 16)) for c in columns[2:]}}
                 for _ in range(count))


def make_workload(config):
    """One draw, no resampling for ambiguity, difficulty or baseline failure.

    Eight source compositions and eight distinct new compositions are chosen
    before scoring. Controls include explicit specifications, renamed schemas,
    and exact repeats. All are development; no label is used to fit a learner.
    """
    rng = random.Random(config['seed'])
    compositions = [c for c in product(config['arithmetic'], config['aggregates'], config['placements'])
                    if not (c[1] == 'max' and c[2] == 'after')]
    rng.shuffle(compositions)
    tasks = []
    count = config['source_tasks'] + config['composition_tasks']
    for i, composition in enumerate(compositions[:count]):
        columns = tuple('f_' + ''.join(rng.choices('abcdefghjkmnpqrstuvwxyz', k=7)) for _ in range(5))
        if len(set(columns)) != 5:
            raise ValueError('schema_collision_no_resampling')
        lhs, rhs = rng.sample(range(3), 2)
        if composition[0] != 'sub':
            lhs, rhs = sorted((lhs, rhs))
        plan = Plan(rng.randrange(2), lhs, rhs, *composition)
        demo = rows(rng, columns, 2)
        public = PublicTask(columns, demo, tuple(execute(plan, columns, demo, config['threshold'])),
                            tuple(rows(rng, columns, config['probe_rows']) for _ in range(config['probe_batches'])))
        tasks.append(dict(id=f'task_{i:02}', cohort='source' if i < config['source_tasks'] else 'new_composition',
                          public=public, truth=plan,
                          assessment=rows(rng, columns, config['assessment_rows'])))
    # Controls are not counted as held-out compositions or headroom tasks.
    for i in range(config['control_pairs']):
        original = tasks[i]
        p = original['public']
        tasks.append(dict(original, id=f'explicit_{i}', cohort='explicit', public=PublicTask(
            p.columns, p.demonstration, p.demonstration_output, p.probes, original['truth'])))
        columns = tuple('renamed_' + str(i) + '_' + str(j) for j in range(5))
        rename = lambda batch: tuple(dict(zip(columns, (row[c] for c in p.columns))) for row in batch)
        tasks.append(dict(original, id=f'renamed_{i}', cohort='renamed', public=PublicTask(
            columns, rename(p.demonstration), p.demonstration_output, tuple(rename(b) for b in p.probes)),
            assessment=rename(original['assessment'])))
        tasks.append(dict(original, id=f'repeat_{i}', cohort='repeat'))
    return tasks


class ExactCachedBaseline:
    """Constraint filtering + exact expected version-space reduction.

    No forced flat search: compile explicit specs immediately, reuse identical
    resolved public problems, and memoize all predicted probe signatures. Query
    decisions use only predicted outcomes, never evaluator answers. Stop when
    no remaining query distinguishes survivors; do not expand the grammar.
    """
    def __init__(self, config):
        self.config = config
        t = time.perf_counter()
        self.plans = grammar(config)
        self.construction_s = time.perf_counter() - t
        self.predictions, self.solutions = {}, {}
        self.prefixes = {}
        self.executions = 0
        self.fragment_executions = 0

    def prediction(self, plan, public, batch):
        key = digest([plan.__dict__, public.columns, batch, self.config['threshold']])
        if key not in self.predictions:
            # Exact source-free prefix caching: common parsing, arithmetic and
            # grouping work is NOT re-executed just because plans differ later.
            ast = plan.ast(public.columns, self.config['threshold'])
            current, prefix, index = batch, [], 0
            batch_key = digest(batch)
            while index < len(ast):
                width = 2 if ast[index]['op'] == 'GroupByField' else 1
                chunk = ast[index:index+width]
                prefix.extend(chunk)
                fragment_key = digest([batch_key, prefix])
                if fragment_key not in self.prefixes:
                    self.prefixes[fragment_key] = evaluate_serialized_adapter_program(chunk, current)
                    self.fragment_executions += 1
                current = self.prefixes[fragment_key]
                index += width
            self.predictions[key] = [dict(group=row[public.columns[plan.key]], value=row['derived'])
                                     for row in current]
            self.executions += 1
        return self.predictions[key]

    def solve(self, public, oracle):
        t = time.perf_counter()
        before = self.executions
        fragments_before = self.fragment_executions
        key = digest([public.columns, public.demonstration, public.demonstration_output,
                      public.probes, public.complete_specification.__dict__ if public.complete_specification else None])
        cache_hit = key in self.solutions
        if public.complete_specification is not None:
            survivors = [public.complete_specification]
        elif cache_hit:
            survivors = [self.solutions[key]]
        else:
            survivors = [p for p in self.plans if self.prediction(p, public, public.demonstration)
                         == list(public.demonstration_output)]
        initial = len(survivors)
        locked = []
        while len(survivors) > 1 and oracle.calls < self.config['max_questions']:
            options = []
            for index, batch in enumerate(public.probes):
                if index in locked:
                    continue
                partitions = {}
                for plan in survivors:
                    sig = canonical(self.prediction(plan, public, batch))
                    partitions[sig] = partitions.get(sig, 0) + 1
                options.append((sum(n*n for n in partitions.values()), index, len(partitions)))
            if not options:
                break
            _, selected, parts = min(options)
            if parts == 1:
                break
            locked.append(selected)  # locked before the only answer access
            answer = oracle.answer(selected)
            survivors = [p for p in survivors if self.prediction(p, public, public.probes[selected]) == answer]
        chosen = min(survivors) if survivors else None
        discovery_s = time.perf_counter() - t
        t = time.perf_counter()
        valid = chosen is not None and execute(chosen, public.columns, public.demonstration,
                                              self.config['threshold']) == list(public.demonstration_output)
        validation_s = time.perf_counter() - t
        # Public-demo validation is not final-outcome validation or promotion.
        t = time.perf_counter()
        if valid and (len(survivors) == 1 or public.complete_specification is not None):
            self.solutions[key] = chosen
        retention_s = time.perf_counter() - t
        return chosen, dict(initial_survivors=initial, final_survivors=len(survivors),
                            questions=oracle.calls, locked_probes=locked, cache_hit=cache_hit,
                            candidate_executions=self.executions-before,
                            fragment_executions=self.fragment_executions-fragments_before,
                            validation_executions=int(chosen is not None),
                            discovery_s=discovery_s, validation_s=validation_s,
                            retention_s=retention_s, public_validation_passed=valid)


def run(config, emit):
    tasks = make_workload(config)
    baseline = ExactCachedBaseline(config)
    emit(dict(kind='construction', seconds=baseline.construction_s, catalogue_size=len(baseline.plans)))
    for task in tasks:
        public, truth = task['public'], task['truth']
        oracle = TeachingOracle(truth, public, config['threshold'], config['max_questions'])
        chosen, metrics = baseline.solve(public, oracle)
        # Query outcomes are accessed only after the plan and all probes are locked.
        t = time.perf_counter()
        output = execute(chosen, public.columns, task['assessment'], config['threshold']) if chosen else None
        execution_s = time.perf_counter() - t
        expected = execute(truth, public.columns, task['assessment'], config['threshold'])
        emit(dict(kind='task', id=task['id'], cohort=task['cohort'], columns=public.columns,
                  demonstration=public.demonstration, demonstration_output=public.demonstration_output,
                  probes=public.probes, assessment=task['assessment'], truth=truth.__dict__,
                  selected=chosen.__dict__ if chosen else None, output=output, expected=expected,
                  correct=output == expected, execution_s=execution_s, **metrics))
    emit(dict(kind='cache_accounting', prediction_entries=len(baseline.predictions),
              prediction_bytes=len(canonical(baseline.predictions).encode()),
              prefix_entries=len(baseline.prefixes), prefix_bytes=len(canonical(baseline.prefixes).encode()),
              solution_entries=len(baseline.solutions),
              solution_bytes=len(canonical({k: v.__dict__ for k, v in baseline.solutions.items()}).encode()),
              executions=baseline.executions, fragment_executions=baseline.fragment_executions,
              model_calls=0, neural_updates=0,
              environment_steps=0, learned_abstractions=0))


def summarize(records, config):
    tasks = [r for r in records if r.get('kind') == 'task']
    expected = {f'task_{i:02}' for i in range(config['source_tasks']+config['composition_tasks'])}
    expected |= {f'{c}_{i}' for c in ('explicit', 'renamed', 'repeat') for i in range(config['control_pairs'])}
    complete = len(tasks) == len(expected) and {r['id'] for r in tasks} == expected
    complete &= sum(r.get('kind') == 'construction' for r in records) == 1
    complete &= sum(r.get('kind') == 'cache_accounting' for r in records) == 1
    for row in tasks:
        for name in ('discovery_s', 'validation_s', 'retention_s', 'execution_s'):
            value = row.get(name)
            if type(value) not in (int, float) or not 0 <= value < float('inf'):
                complete = False
    if not complete:
        return dict(declared_complete=False, ready_for_learning_study=False,
                    verdict='INCOMPLETE', gates=dict(complete=False))
    novel = [r for r in tasks if r['cohort'] == 'new_composition']
    accuracy = sum(r['correct'] is True for r in novel)/len(novel) if novel else 0
    ambiguity = sum(r['initial_survivors'] > 1 for r in novel)/len(novel) if novel else 0
    median = statistics.median(r['discovery_s'] for r in novel) if novel else 0
    discovery = sum(r['discovery_s'] for r in novel)
    denominator = sum(sum(r[k] for k in ('discovery_s', 'validation_s', 'retention_s', 'execution_s')) for r in novel)
    fraction = discovery/denominator if denominator else 0
    distinct = len({tuple(r['truth'][k] for k in ('arithmetic', 'aggregate', 'placement')) for r in novel})
    s = config['screen']
    gates = dict(complete=bool(complete), accuracy=accuracy >= s['minimum_accuracy'],
                 ambiguity=ambiguity >= s['minimum_ambiguous_fraction'],
                 absolute_discovery=median >= s['minimum_median_discovery_s'],
                 discovery_fraction=fraction >= s['minimum_discovery_fraction'],
                 new_compositions=distinct >= s['minimum_new_compositions'])
    return dict(declared_complete=bool(complete), novel_accuracy=accuracy, ambiguous_fraction=ambiguity,
                median_discovery_s=median, discovery_fraction=fraction, new_compositions=distinct,
                gates=gates, symbolic_screen_passed=all(gates.values()),
                ready_for_learning_study=False,
                verdict='INCOMPLETE' if not complete else 'SYMBOLIC_PREFLIGHT_ONLY',
                required_next_gate='Unchanged persistent-model direct/tool baseline remains unmeasured on this workload')
