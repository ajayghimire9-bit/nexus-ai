"""Small authored fixtures only. Never run the registered workload in pytest."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from nexus.seed.discovery_headroom import (
    Plan, PublicTask, TeachingOracle, ExactCachedBaseline, canonical, digest,
    execute, grammar, make_workload, summarize,
)

ROOT = Path(__file__).resolve().parents[1]


def config():
    return dict(arithmetic=['add', 'sub'], aggregates=['sum', 'max'],
                placements=['none', 'before', 'after'], threshold=10, max_questions=3)


def fixture():
    columns = ('name', 'other', 'x', 'y', 'z')
    demo = ({'name': ' A ', 'other': 'u', 'x': '8', 'y': '2', 'z': '3'},)
    probe = ({'name': 'b', 'other': 'v', 'x': '4', 'y': '9', 'z': '2'},
             {'name': 'b', 'other': 'u', 'x': '7', 'y': '1', 'z': '6'})
    plan = Plan(0, 0, 1, 'sub', 'sum', 'none')
    public = PublicTask(columns, demo, tuple(execute(plan, columns, demo, 10)), (probe,))
    return plan, public


def test_executor_known_composition_and_group_filter_order():
    plan, public = fixture()
    assert execute(plan, public.columns, public.demonstration, 10) == [dict(group='a', value=6.0)]
    assert execute(plan, public.columns, public.probes[0], 10) == [dict(group='b', value=1.0)]
    changed = Plan(0, 0, 1, 'add', 'sum', 'before')
    after = replace(changed, placement='after')
    assert execute(changed, public.columns, public.probes[0], 10) != execute(after, public.columns, public.probes[0], 10)


def test_no_forced_search_on_complete_specification_or_exact_repeat():
    c = config(); plan, public = fixture(); baseline = ExactCachedBaseline(c)
    explicit = replace(public, complete_specification=plan)
    for _ in range(2):
        oracle = TeachingOracle(plan, explicit, 10, 3)
        chosen, metrics = baseline.solve(explicit, oracle)
        assert chosen == plan
        assert metrics['candidate_executions'] == metrics['fragment_executions'] == oracle.calls == 0


def test_prefix_cache_matches_full_executor_and_avoids_repeat_work():
    c = config(); plan, public = fixture(); baseline = ExactCachedBaseline(c)
    for candidate in grammar(c):
        assert baseline.prediction(candidate, public, public.probes[0]) == execute(candidate, public.columns, public.probes[0], 10)
    count = baseline.fragment_executions
    for candidate in grammar(c):
        baseline.prediction(candidate, public, public.probes[0])
    assert baseline.fragment_executions == count
    assert count < sum(len(p.ast(public.columns, 10)) for p in grammar(c))


def test_choice_locked_before_answer_and_assessment_absent_from_solver():
    c = config(); plan, public = fixture(); decisions = []
    class RecordingOracle:
        calls = 0
        def answer(self, index):
            decisions.append(index)
            self.calls += 1
            return execute(plan, public.columns, public.probes[index], 10)
    solver = ExactCachedBaseline(c)
    _, metrics = solver.solve(public, RecordingOracle())
    assert decisions == metrics['locked_probes']
    assert not hasattr(public, 'assessment') and not hasattr(public, 'truth')
    # Changing private outcomes cannot enter the public feature/choice path.
    first = solver.solve(public, TeachingOracle(plan, public, 10, 3))[0]
    hidden_assessment = {'value': -1000000}
    hidden_assessment['value'] = 1e9
    second = ExactCachedBaseline(c).solve(public, TeachingOracle(plan, public, 10, 3))[0]
    assert first == second


def test_query_budget_and_duplicate_rejection():
    plan, public = fixture(); oracle = TeachingOracle(plan, public, 10, 1)
    oracle.answer(0)
    with pytest.raises(ValueError, match='exhausted'):
        oracle.answer(0)


def test_grammar_removes_known_equivalences_and_never_mutates_inputs():
    c = config(); plan, public = fixture(); original = deepcopy(public.demonstration)
    execute(plan, public.columns, public.demonstration, 10)
    assert public.demonstration == original
    assert all(p.lhs < p.rhs for p in grammar(c) if p.arithmetic == 'add')
    assert not any(p.aggregate == 'max' and p.placement == 'after' for p in grammar(c))
    assert len(grammar(c)) == len(set(grammar(c)))


def test_workload_structure_on_unregistered_tiny_fixture_only():
    c = dict(config(), seed=3, source_tasks=2, composition_tasks=2, control_pairs=1,
             probe_batches=2, probe_rows=3, assessment_rows=4)
    tasks = make_workload(c)
    source = {t['truth'].semantic_composition() for t in tasks if t['cohort'] == 'source'}
    target = {t['truth'].semantic_composition() for t in tasks if t['cohort'] == 'new_composition'}
    assert not source & target
    assert len(tasks) == 7
    assert digest(tasks[0]['assessment']) != digest(tasks[0]['public'].demonstration)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), True, '0.1', -1])
def test_required_timings_reject_nonfinite_or_non_numeric(value):
    c = dict(config(), source_tasks=0, composition_tasks=1, control_pairs=0,
             screen=dict(minimum_accuracy=.95, minimum_ambiguous_fraction=.5,
                         minimum_median_discovery_s=.01, minimum_discovery_fraction=.25,
                         minimum_new_compositions=1))
    row = dict(kind='task', id='task_00', cohort='new_composition', correct=True,
               initial_survivors=2, discovery_s=value, validation_s=0., retention_s=0., execution_s=0.,
               truth=dict(arithmetic='add', aggregate='sum', placement='none'))
    assert not summarize([dict(kind='construction'), dict(kind='cache_accounting'), row], c)['declared_complete']


def test_runtime_and_completed_study_unchanged():
    import hashlib
    c = json.loads((ROOT/'configs/seed_discovery_headroom.json').read_text())
    assert hashlib.sha256((ROOT/'src/nexus/seed/local_model_runtime.py').read_bytes()).hexdigest() == c['runtime_source_sha256']
    assert c['learning_comparison_authorized_by_this_config'] is False
    assert c['wall_s'] <= 60 and c['carried_used_s'] == 2186.632103455996


def test_probe_choice_does_not_read_unrevealed_answers():
    c = config(); _, public = fixture(); selected = []
    class StopAtAnswer:
        calls = 0
        def answer(self, index):
            selected.append(index)
            raise RuntimeError('choice_already_locked')
    for _hidden_answer in ([{'value': 0}], [{'value': 999}]):
        with pytest.raises(RuntimeError, match='already_locked'):
            ExactCachedBaseline(c).solve(public, StopAtAnswer())
    assert len(selected) == 2 and selected[0] == selected[1]


def test_missing_entire_task_and_duplicate_rejected_before_aggregation():
    c = dict(config(), source_tasks=1, composition_tasks=0, control_pairs=0)
    assert not summarize([dict(kind='construction'), dict(kind='cache_accounting')], c)['declared_complete']


def test_independent_reference_matches_known_execution_and_filter_placement():
    import importlib.util
    spec = importlib.util.spec_from_file_location('headroom_independent_test', ROOT/'scripts/verify_seed_discovery_headroom.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    _, public = fixture()
    for plan in grammar(config()):
        assert module.reference(plan.__dict__, public.columns, public.probes[0], 10) == execute(plan, public.columns, public.probes[0], 10)


def test_ambiguous_repeat_reuses_predictions_without_claiming_resolved_solution():
    c = config(); _, public = fixture()
    # No probes: ambiguity cannot be safely retained as a uniquely solved task.
    ambiguous = replace(public, probes=())
    oracle = TeachingOracle(Plan(0, 0, 1, 'sub', 'sum', 'none'), ambiguous, 10, 3)
    baseline = ExactCachedBaseline(c)
    _, first = baseline.solve(ambiguous, oracle)
    _, second = baseline.solve(ambiguous, oracle)
    assert first['final_survivors'] > 1 and second['final_survivors'] > 1
    assert second['candidate_executions'] == second['fragment_executions'] == 0
    assert not second['cache_hit']


@pytest.mark.parametrize('corruption', ['missing', 'duplicate', 'cohort', 'nonfinite', 'output', 'summary'])
def test_saved_preflight_rejection_without_reexecuting_workload(corruption):
    import importlib.util
    path = ROOT/'artifacts/seed_discovery_headroom_raw.jsonl'
    if not path.exists():
        # Pre-run tests have no registered outcomes; fixture tests above apply.
        return
    spec = importlib.util.spec_from_file_location('saved_headroom_test', ROOT/'scripts/verify_seed_discovery_headroom.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    records = [json.loads(s) for s in path.read_text().splitlines()]
    summary = json.loads((ROOT/'artifacts/seed_discovery_headroom.json').read_text())['summary']
    c = json.loads((ROOT/'configs/seed_discovery_headroom.json').read_text())
    task = next(r for r in records if r['kind'] == 'task')
    if corruption == 'missing': records.remove(task)
    if corruption == 'duplicate': records.append(task)
    if corruption == 'cohort': task['cohort'] = 'new_composition'
    if corruption == 'nonfinite': task['discovery_s'] = float('nan')
    if corruption == 'output': task['output'] = [{'fake': True}]
    if corruption == 'summary': summary['novel_accuracy'] = .5
    with pytest.raises(ValueError): module.verify(records, c, summary)
