"""Authored source-only fixtures; never execute the registered audit in pytest."""
from copy import deepcopy
from dataclasses import replace

import pytest

from nexus.seed.discovery_headroom import Plan, execute
from nexus.seed.candidate_identifiability import (
    construct_probe, normal_form, observed_case, reconstruct_candidates, summarize,
)

COLUMNS = ('g', 'h', 'x', 'y', 'z')
CONFIG = dict(boundary_values=[0, 1, 5, 9, 10, 11, 15], maximum_probe_candidates=2048)


def test_real_difference_has_concrete_answer_free_counterexample_and_early_stop():
    a = Plan(0, 0, 1, 'add', 'sum', 'none')
    b = replace(a, placement='after')
    result = construct_probe((a, b), COLUMNS, 10, CONFIG)
    assert result['classification'] == 'MEANINGFULLY_DIFFERENT'
    assert result['examined'] == 1 and result['prediction_executions'] == 2
    assert result['worst_remaining'] == 1
    witness = result['witness']
    assert witness['predictions'][0] != witness['predictions'][1]
    for plan, output in zip(witness['representatives'], witness['predictions']):
        assert execute(Plan(**plan), COLUMNS, witness['rows'], 10) == output


def test_sound_equivalence_without_forced_probe_search():
    a = Plan(0, 0, 1, 'add', 'max', 'after')
    b = Plan(0, 1, 0, 'add', 'max', 'before')
    assert normal_form(a) == normal_form(b)
    result = construct_probe((a, b), COLUMNS, 10, CONFIG)
    assert result['classification'] == 'PROVEN_EQUIVALENT'
    assert result['prediction_executions'] == result['examined'] == 0
    for x in range(5):
        batch = ({'g': ' A ', 'h': 'b', 'x': str(x), 'y': '8', 'z': '0'},
                 {'g': 'a', 'h': 'c', 'x': '2', 'y': str(x), 'z': '1'})
        assert execute(a, COLUMNS, batch, 10) == execute(b, COLUMNS, batch, 10)


def test_no_witness_does_not_mean_equivalent():
    a = Plan(0, 0, 1, 'sub', 'sum', 'none')
    b = replace(a, rhs=2)
    result = construct_probe((a, b), COLUMNS, 10, dict(CONFIG, maximum_probe_candidates=0))
    assert result['classification'] == 'UNKNOWN' and result['witness'] is None


def test_group_aggregation_can_require_multiple_rows():
    a = Plan(0, 0, 1, 'add', 'mean_round2', 'none')
    b = replace(a, aggregate='max')
    result = construct_probe((a, b), COLUMNS, 10, CONFIG)
    assert result['classification'] == 'MEANINGFULLY_DIFFERENT'
    assert len(result['witness']['rows']) == 2
    assert result['worst_remaining'] == 1


def test_assessment_changes_cannot_affect_reconstructed_evidence_or_probes():
    a = Plan(0, 0, 1, 'add', 'sum', 'none')
    demo = [{'g': 'a', 'h': 'b', 'x': '0', 'y': '0', 'z': '0'}]
    row = dict(columns=COLUMNS, demonstration=demo,
               demonstration_output=execute(a, COLUMNS, demo, 10),
               probes=[demo], locked_probes=[], truth=a.__dict__, assessment=[{'secret': 123}], expected=[])
    changed = deepcopy(row); changed.update(assessment=[{'secret': -999}], expected=[{'invented': True}])
    first = observed_case(row, {'threshold': 10})
    second = observed_case(changed, {'threshold': 10})
    assert first == second
    config = dict(arithmetic=['add'], aggregates=['sum'], placements=['none', 'after'], threshold=10)
    candidates, _ = reconstruct_candidates(*first, config)
    a_result = construct_probe(candidates, COLUMNS, 10, CONFIG)
    b_result = construct_probe(tuple(reversed(candidates)), COLUMNS, 10, CONFIG)
    assert a_result['witness'] == b_result['witness']
    assert row['assessment'] == [{'secret': 123}]


@pytest.mark.parametrize('records', [[], [{'kind': 'case', 'id': 'a'}, {'kind': 'case', 'id': 'a'}]])
def test_missing_or_duplicate_grid_fails_closed(records):
    assert not summarize(records, dict(expected_ids=['a', 'b']))['declared_complete']


def test_readonly_audit_has_zero_collection_cap_and_carried_ledger():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root/'configs/seed_candidate_identifiability.json').read_text())
    assert config['real_steps'] == 0 and config['carried_used_s'] == 2188.632103455996
    assert len(config['primary_ids']) == 7 and len(config['expected_ids']) == 9


def test_independent_counterexample_arithmetic_and_canonical_rules():
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('independent_identifiability_test', root/'scripts/verify_seed_candidate_identifiability.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    plans = (Plan(0, 0, 1, 'add', 'sum', 'none'), Plan(0, 0, 1, 'add', 'sum', 'after'))
    result = construct_probe(plans, COLUMNS, 10, CONFIG)
    witness = result['witness']
    for plan, expected in zip(witness['representatives'], witness['predictions']):
        assert module.reference(plan, COLUMNS, witness['rows'], 10) == expected
        assert module.normalized(plan) == normal_form(Plan(**plan)).__dict__


def test_published_study_refuses_rerun_even_without_private_ledger():
    import importlib.util
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('closed_study_host_test', root/'scripts/run_seed_discovery_headroom.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    config = json.loads((root/'configs/seed_discovery_headroom.json').read_text())
    with pytest.raises(ValueError, match='published_attempt_is_closed'):
        module.host(config)
