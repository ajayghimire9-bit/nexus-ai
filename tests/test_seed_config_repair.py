"""Small authored fixtures; no registered manifest run or neural inference."""
import ast
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from nexus.seed.config_repair_baseline import Baseline, PublicTask, contract_from_public_tests, fixture, evaluate, summarize
from nexus.seed.config_repair_worker import compile_project


def toy(**kwargs):
    return dict(id='unit_fixture_not_registered', key='budget', default=9,
                parser='or', core='ternary', caller='if', cohort='primary', **kwargs)


def test_real_multifile_patch_changes_actions_preserves_unrelated_code():
    task, private = fixture(toy())
    original = evaluate(task.files, task.tests)
    assert not all(r['passed'] for r in original['results'])
    patched = Baseline().solve(task)
    assert any(r['calls'] for r in patched['original_public']['results'])
    assert patched['public_passed'] and len({e['path'] for e in patched['edits']}) == 3
    assert all(r['passed'] for r in evaluate(patched['files'], private)['results'])
    def legacy(source): return ast.dump(next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'legacy_fallback'))
    assert legacy(task.files['cfgparse.py']) == legacy(patched['files']['cfgparse.py'])


def test_exact_cache_uses_full_request_source_and_public_tests():
    task, _ = fixture(toy())
    baseline = Baseline(); first = baseline.solve(task); second = baseline.solve(task)
    assert not first['cache_hit'] and second['cache_hit']
    assert second['tools']['candidate_plans'] == second['tools']['project_subprocesses'] == 0
    assert not baseline.solve(replace(task, request=task.request+' Please verify.'))['cache_hit']


def test_assessment_inaccessible_to_solver_and_input_immutable():
    task, private = fixture(toy()); original = deepcopy(task.files)
    first = Baseline().solve(task)
    for case in private: case['expected'] = -123
    second = Baseline().solve(task)
    assert first['files'] == second['files'] and task.files == original
    assert not hasattr(task, 'assessment')


@pytest.mark.parametrize('parser', ['get_default', 'subscript'])
def test_missing_versus_null_ast_fixes(parser):
    spec = toy(); spec['parser'] = parser; spec['core'] = 'floor'; spec['caller'] = 'or'
    task, private = fixture(spec)
    result = Baseline().solve(task)
    assert all(r['passed'] for r in evaluate(result['files'], private)['results'])


def test_unsupported_contract_abstains_not_fake_model_output():
    task, _ = fixture(toy())
    with pytest.raises(ValueError, match='abstain'):
        contract_from_public_tests(replace(task, tests=[]))


@pytest.mark.parametrize('source', ['import os\ndef read(x):\n return x\n',
                                  'def read(x):\n return open("/tmp/unsafe")\n',
                                  'def read(x):\n while True:\n  pass\n'])
def test_worker_rejects_unsupported_effects_or_loops(source):
    task, _ = fixture(toy()); files = dict(task.files, **{'cfgparse.py': source})
    with pytest.raises(ValueError): compile_project(files)


def test_missing_grid_is_not_a_negative_scientific_result():
    config = dict(tasks=[dict(id='a')])
    assert summarize([], config)['verdict'] == 'INCOMPLETE'


def test_manifest_is_fixed_and_contains_easy_multifile_and_cache_controls():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root/'configs/seed_config_repair_baseline.json').read_text())
    assert len(config['tasks']) == len({t['id'] for t in config['tasks']}) == 12
    assert sum(t['cohort'] == 'primary' for t in config['tasks']) == 8
    assert config['carried_used_s'] == 2190.632103455996 and config['real_steps'] == 0


def test_recorded_worker_overhead_and_execution_times_are_distinct():
    task, _ = fixture(toy())
    report = evaluate(task.files, task.tests)
    assert report['wall_s'] >= report['internal_s'] > 0
    assert abs(report['process_overhead_residual_s'] - (report['wall_s']-report['internal_s'])) < 1e-12


def test_independent_verifier_on_unregistered_toy_end_to_end():
    import importlib.util
    from nexus.seed.config_repair_baseline import digest
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('config_repair_verifier_test', root/'scripts/verify_seed_config_repair.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    recipe = toy(); task, final = fixture(recipe); baseline = Baseline()
    outcome = baseline.solve(task); assessed = evaluate(outcome['files'], final)
    row = dict(kind='task', id=recipe['id'], cohort='primary', public=task.__dict__,
               locked_patch_sha256=digest(outcome['files']), assessment_cases=final,
               assessment=assessed, final_passed=all(r['passed'] for r in assessed['results']), **outcome)
    config = dict(tasks=[recipe], screen=dict(minimum_accuracy=.9, minimum_discovery_s=.01, minimum_discovery_fraction=.25))
    records = [row, dict(kind='cache', entries=len(baseline.cache), serialized_bytes=len(json.dumps(baseline.cache).encode()),
                         model_calls=0, training_updates=0, new_environment_steps=0, learned_abstractions=0)]
    summary = summarize(records, config)
    assert module.verify(records, config, summary, replay=False)['valid']
    broken = deepcopy(records); broken[0]['assessment']['results'][0]['actual'] = -999
    with pytest.raises(ValueError, match='forged'):
        module.verify(broken, config, summary, replay=False)


@pytest.mark.parametrize('corruption', ['missing', 'patch', 'cache', 'timing', 'summary', 'retention'])
def test_saved_repair_artifact_rejects_corruption(corruption):
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    path = root/'artifacts/seed_config_repair_baseline_raw.jsonl'
    if not path.exists(): return  # Not available before the one registered run.
    spec = importlib.util.spec_from_file_location('saved_repair_test', root/'scripts/verify_seed_config_repair.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    records = [json.loads(s) for s in path.read_text().splitlines()]
    config = json.loads((root/'configs/seed_config_repair_baseline.json').read_text())
    summary = json.loads((root/'artifacts/seed_config_repair_baseline.json').read_text())['summary']
    row = next(r for r in records if r['kind'] == 'task')
    if corruption == 'missing': records.remove(row)
    if corruption == 'patch': row['files']['app.py'] += '\n# changed\n'
    if corruption == 'cache': next(r for r in records if r.get('cache_hit'))['public_receipt_sha256'] = 'forged'
    if corruption == 'timing': row['stages']['patch_construction_s'] = float('nan')
    if corruption == 'summary': summary['median_discovery_s'] += 1
    if corruption == 'retention': row['assessment_cases'][-2]['expected'] = -999
    with pytest.raises(ValueError): module.verify(records, config, summary, replay=False)
