"""Independent source-only Evolution-2 readiness audit.

Not a scientific experiment. Does not train models, roll out environments,
select holdouts, or debit the scientific ledger.
"""
from __future__ import annotations
import ast
import hashlib
import inspect
import json
from pathlib import Path

from nexus.evolution1.toy_loop import ANCHORS, VARIANTS, features
from nexus.evolution2 import methods as e2m
from nexus.evolution2 import screen
from nexus.evolution2 import tasks
from nexus.evolution2.tasks import FAMILY_SPEC, hidden_score, make_task


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'artifacts' / 'research_session_h16_same_state_library_usage.json'
E2_FILES = (
    'src/nexus/evolution2/__init__.py',
    'src/nexus/evolution2/tasks.py',
    'src/nexus/evolution2/methods.py',
    'src/nexus/evolution2/screen.py',
    'tests/test_evolution2_cross_task_screen.py',
    'scripts/run_evolution2_cross_task_screen.py',
    'docs/NEXUS_EVOLUTION2_CROSS_TASK_SCREEN.md',
)


def _source(relpath):
    return (ROOT / relpath).read_text(encoding='utf-8')


def test_ledger_file_still_reports_the_closed_h16_totals():
    payload = json.loads(LEDGER.read_text(encoding='utf-8'))
    assert payload['ledger']['consumed_total_s'] == 305.842
    assert payload['remaining_session_allowance_s'] == 3294.158
    assert payload['consumed'] is True
    assert payload['experiment'] == 'h16_same_state_library'
    digest = hashlib.sha256(LEDGER.read_bytes()).hexdigest()
    assert digest == 'ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117'


def test_reported_e2_head_sources_still_declare_synthetic_only():
    labeled = (
        'src/nexus/evolution2/__init__.py',
        'src/nexus/evolution2/tasks.py',
        'src/nexus/evolution2/screen.py',
        'tests/test_evolution2_cross_task_screen.py',
        'scripts/run_evolution2_cross_task_screen.py',
        'docs/NEXUS_EVOLUTION2_CROSS_TASK_SCREEN.md',
    )
    for relpath in labeled:
        assert 'synthetic' in _source(relpath).lower()
    tasks_src = _source('src/nexus/evolution2/tasks.py')
    screen_src = _source('src/nexus/evolution2/screen.py')
    assert 'SCIENTIFIC = False' in tasks_src
    assert "MODE = 'synthetic_only'" in tasks_src
    assert 'real_env_steps=0' in screen_src
    assert 'scientific_ledger=False' in screen_src
    assert 'H17' in screen_src


def test_claimed_feedback_dependence_and_persistence_are_source_true():
    persist = e2m.PersistentAdaptive(seed=7)
    reset = e2m.ResetAdaptive(seed=7)
    first = make_task('successor_scale', 0)
    screen.propose_on_task(persist, first)
    screen.propose_on_task(reset, first)
    reset.reset_task()
    assert persist.learned_state()['weights'] != (0.0,) * 6
    assert persist.learned_state()['updates'] == 4
    assert reset.learned_state()['weights'] == (0.0,) * 6
    later = make_task('horizon_scale', 0).context
    assert persist.choose(tuple(VARIANTS), later) != reset.choose(tuple(VARIANTS), later)

    blind = e2m.PersistentAdaptive(seed=7)
    screen.propose_on_task(blind, first, apply_update=False)
    assert blind.learned_state()['weights'] == (0.0,) * 6


def test_authored_related_and_inverted_families_are_not_scientific_evidence():
    aligned = dict(
        train=(make_task('successor_scale', 0), make_task('successor_scale', 1)),
        development=(make_task('successor_dev', 0), make_task('successor_dev', 1)),
        shifted=(make_task('inverted_successor', 0), make_task('inverted_successor', 1)),
        holdout=(make_task('holdout_horizon', 0),),
    )
    report = screen.run_screen(seed=7, local_updates=False, split=aligned)
    assert report['scientific'] is False
    assert report['illustration_label'] == 'synthetic_illustration_not_a_result'
    assert report['persistent_minus_reset_dev_mean'] > 0
    persist_shift = sum(row['mean'] for row in report['shifted']['persistent_adaptive'])
    reset_shift = sum(row['mean'] for row in report['shifted']['reset_adaptive'])
    assert persist_shift < reset_shift
    assert report['cpu_memory']['scientific_ledger_used'] is False


def test_hidden_oracle_lives_in_the_proposer_feature_span():
    """Authored scores are linear in (S, B, h). That favors the linear SGD policy."""
    for family, spec in FAMILY_SPEC.items():
        task = make_task(family, 0)
        w0, ws, wb, wh = spec['hidden']
        offset = spec['offset']
        for variant in VARIANTS:
            s = float(variant.rule.value == 'successor')
            b = float(variant.generator.value == 'balanced_first_action')
            h = variant.horizon / 16.0
            expected = max(0.0, min(1.0, w0 + ws * s + wb * b + wh * h + offset))
            assert hidden_score(task, variant) == expected
            x = features(variant, task.context)
            assert x[0] == 1.0 and x[1] == s and x[2] == b and x[3] == h


def test_development_family_is_a_near_copy_of_one_training_family():
    train = FAMILY_SPEC['successor_scale']['hidden']
    dev = FAMILY_SPEC['successor_dev']['hidden']
    hold = FAMILY_SPEC['holdout_horizon']['hidden']
    horizon = FAMILY_SPEC['horizon_scale']['hidden']
    assert all(abs(a - b) <= 0.03 for a, b in zip(train, dev))
    assert all(abs(a - b) <= 0.03 for a, b in zip(horizon, hold))


def test_instance_offset_does_not_change_within_family_ranking():
    for family in FAMILY_SPEC:
        first = [hidden_score(make_task(family, 0), v) for v in VARIANTS]
        second = [hidden_score(make_task(family, 1), v) for v in VARIANTS]
        rank0 = sorted(range(len(VARIANTS)), key=lambda i: (-first[i], i))
        rank1 = sorted(range(len(VARIANTS)), key=lambda i: (-second[i], i))
        assert rank0 == rank1


def test_only_two_of_four_proposals_are_method_choices():
    assert tasks.PROPOSALS == 4
    assert tasks.SHARED_PROBES == 2
    persist = e2m.PersistentAdaptive(seed=7)
    rows = screen.propose_on_task(persist, make_task('balanced_scale', 0))
    assert [r.variant_id for r in rows[:2]] == [ANCHORS[0].fingerprint, ANCHORS[1].fingerprint]


def test_transfer_benefit_defaults_to_mean_while_future_protocol_names_best():
    assert screen.transfer_benefit.__defaults__ == ('mean',)
    proto = screen.future_protocol()
    assert proto['primary'] == 'mean_over_dev_instances(best_persistent - best_reset)'
    assert proto['authorized'] is False
    assert proto['n_proposed'] == 10
    assert screen.classify_transfer(0.2, 0.1, 0.3, 1) == 'e2_persistence_helps_transfer'


def test_random_eval_clone_is_the_training_object_and_evolution_is_first_available():
    methods = e2m.make_methods(seed=7)
    assert methods['random'].eval_clone(local_updates=False) is methods['random']
    assert methods['fixed'].eval_clone(local_updates=False) is methods['fixed']
    evo = e2m.EvolutionarySearch(seed=7)
    first = evo.choose(tuple(VARIANTS), make_task('horizon_scale', 0).context)
    assert first is VARIANTS[0]
    clone = evo.eval_clone(local_updates=False)
    assert clone.parent is None
    assert 'guarded' not in methods and 'memory' not in methods and 'retrieval' not in methods


def test_evolution2_screen_does_not_meter_or_isolate_like_evolution1():
    screen_src = ast.parse(_source('src/nexus/evolution2/screen.py'))
    names = {node.id for node in ast.walk(screen_src) if isinstance(node, ast.Name)}
    imported = set()
    for node in ast.walk(screen_src):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
            imported.update(alias.name for alias in node.names)
    assert 'ReservationLedger' not in names
    assert 'FixtureBroker' not in names
    assert 'DevelopmentGate' not in imported
    assert inspect.signature(screen.propose_on_task).parameters['apply_update'].default is True
    # Hidden family weights are ordinary importable Python, not process-isolated.
    assert all('hidden' in spec for spec in FAMILY_SPEC.values())
    assert hidden_score is not None
    view = json.dumps(make_task('successor_dev', 0).public_view())
    assert 'hidden' not in view
    assert '"role": "development"' in view


def test_default_screen_charges_forty_synthetic_lookups_and_twenty_four_train_updates():
    persist = e2m.PersistentAdaptive(seed=7)
    for task in tasks.default_split()['train']:
        screen.propose_on_task(persist, task)
    assert persist.learned_state()['updates'] == 24
    frozen = persist.freeze()
    report = screen.run_screen(seed=7)
    assert report['matched_lookups'] == 40
    assert report['frozen_updates'] == 24
    assert report['frozen_weights'] == list(frozen['weights'])
    eval_clone = persist.eval_clone(local_updates=False)
    assert eval_clone.learned_state()['weights'] == frozen['weights']


def test_audit_and_e2_modules_import_no_scientific_stack():
    for relpath in (
        'src/nexus/evolution2/__init__.py',
        'src/nexus/evolution2/tasks.py',
        'src/nexus/evolution2/methods.py',
        'src/nexus/evolution2/screen.py',
        'scripts/run_evolution2_cross_task_screen.py',
    ):
        tree = ast.parse(_source(relpath))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
        assert imported.isdisjoint({'gymnasium', 'torch', 'optuna', 'tensorboard'})
        assert '305.842' not in _source(relpath)
    proto = screen.future_protocol()
    assert proto['resource_caps']['scientific_ledger'] is False
    assert 'H17' in proto['blocked']
    assert proto['resource_caps']['real_env_steps'] == 0
