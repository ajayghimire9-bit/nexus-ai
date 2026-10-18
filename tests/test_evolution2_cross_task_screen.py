"""Source-only Evolution-2 synthetic contracts. Not a scientific experiment."""
from __future__ import annotations
import inspect
import json
from nexus.evolution1.catalogue import digest
from nexus.evolution1.toy_loop import ANCHORS, AdaptiveProposer, TrainingFeedback, VARIANTS
from nexus.evolution2 import methods as m
from nexus.evolution2 import screen
from nexus.evolution2 import tasks
from nexus.evolution2.tasks import hidden_score, make_task, oracle_best, oracle_table


def test_scores_are_synthetic_and_independent_of_proposal_order():
    task = make_task('successor_scale', 0)
    table = oracle_table(task)
    assert all(0.0 <= s <= 1.0 for s in table.values())
    assert len(table) == 12
    first = [hidden_score(task, v) for v in VARIANTS]
    second = [hidden_score(task, v) for v in reversed(VARIANTS)]
    assert first == list(reversed(second))
    raw = json.dumps(table)
    assert '0.178' not in raw and '0.230' not in raw
    assert 'h16' not in raw and 'H16' not in str(tasks.FAMILY_SPEC)


def test_oracle_is_not_an_update_argument():
    for cls in (AdaptiveProposer, m.PersistentAdaptive, m.ResetAdaptive, m.EvolutionarySearch):
        params = inspect.signature(cls.update).parameters
        assert 'oracle' not in params and 'table' not in params and 'hidden' not in params
    assert 'oracle' not in inspect.signature(screen.propose_on_task).parameters


def test_default_split_reserves_holdout():
    split = tasks.default_split()
    used = [t.family for t in split['train'] + split['development'] + split['shifted']]
    assert tasks.HOLDOUT_FAMILY not in used
    assert {t.family for t in split['train']} == set(tasks.TRAIN_FAMILIES)
    assert {t.role for t in split['development']} == {'development'}
    assert {t.role for t in split['shifted']} == {'shifted'}
    assert split['holdout'][0].family == tasks.HOLDOUT_FAMILY
    assert all(t.scientific is False and t.mode == 'synthetic_only' for role in split
               for t in split[role])


def test_persistence_changes_later_task_proposals():
    persist = m.PersistentAdaptive(seed=7)
    reset = m.ResetAdaptive(seed=7)
    first = make_task('successor_scale', 0)
    screen.propose_on_task(persist, first)
    screen.propose_on_task(reset, first)
    reset.reset_task()
    assert reset.learned_state()['weights'] == (0.0,) * 6
    assert persist.learned_state()['weights'] != (0.0,) * 6
    later_ctx = make_task('horizon_scale', 0).context
    available = tuple(VARIANTS)
    assert persist.choose(available, later_ctx) != reset.choose(available, later_ctx)
    assert persist.learned_state()['updates'] == 4
    assert reset.learned_state()['updates'] == 0


def test_withheld_training_feedback_prevents_persistent_transfer():
    persist = m.PersistentAdaptive(seed=7)
    reset = m.ResetAdaptive(seed=7)
    task = make_task('successor_scale', 0)
    screen.propose_on_task(persist, task, apply_update=False)
    screen.propose_on_task(reset, task, apply_update=False)
    assert persist.learned_state()['weights'] == (0.0,) * 6
    later = make_task('successor_scale', 1)
    persist_ids = [r.variant_id for r in screen.propose_on_task(persist, later, apply_update=False)]
    reset_ids = [r.variant_id for r in screen.propose_on_task(reset, later, apply_update=False)]
    assert persist_ids == reset_ids


def test_eval_does_not_mutate_frozen_global_weights():
    report = screen.run_screen(seed=7, local_updates=True)
    persist = m.PersistentAdaptive(seed=7)
    for task in tasks.default_split()['train']:
        screen.propose_on_task(persist, task)
    frozen = persist.freeze()
    assert report['frozen_weights'] == list(frozen['weights'])
    assert persist.learned_state()['weights'] == frozen['weights']
    assert report['scientific'] is False
    assert report['illustration_label'] == 'synthetic_illustration_not_a_result'


def test_matched_budgets_and_public_information():
    report = screen.run_screen(seed=7)
    names = ('random', 'fixed', 'reset_adaptive', 'persistent_adaptive', 'evolutionary')
    for phase in ('train', 'development', 'shifted'):
        counts = {name: [row['n_proposals'] for row in report[phase][name]] for name in names}
        assert all(c == counts['persistent_adaptive'] for c in counts.values())
        assert all(n == tasks.PROPOSALS for row in counts.values() for n in row)
    assert report['matched_lookups'] == 40
    assert report['cpu_memory']['scientific_ledger_used'] is False


def test_synthetic_transfer_helps_on_related_family_and_hurts_when_shifted():
    aligned = dict(
        train=(make_task('successor_scale', 0), make_task('successor_scale', 1)),
        development=(make_task('successor_dev', 0), make_task('successor_dev', 1)),
        shifted=(make_task('inverted_successor', 0), make_task('inverted_successor', 1)),
        holdout=(make_task('holdout_horizon', 0),),
    )
    frozen = screen.run_screen(seed=7, local_updates=False, split=aligned)
    persist_ids = [row['variants'] for row in frozen['development']['persistent_adaptive']]
    reset_ids = [row['variants'] for row in frozen['development']['reset_adaptive']]
    assert persist_ids != reset_ids
    assert frozen['persistent_minus_reset_dev_mean'] > 0
    persist_shift = [row['mean'] for row in frozen['shifted']['persistent_adaptive']]
    reset_shift = [row['mean'] for row in frozen['shifted']['reset_adaptive']]
    assert sum(persist_shift) < sum(reset_shift)
    mixed = screen.run_screen(seed=7, local_updates=False)
    assert mixed['illustration_label'] == 'synthetic_illustration_not_a_result'
    assert mixed['mode'] == 'synthetic_only'


def test_evolutionary_uses_equal_budget_and_does_not_see_oracle():
    evo = m.EvolutionarySearch(seed=7)
    task = make_task('horizon_scale', 0)
    rows = screen.propose_on_task(evo, task)
    assert len(rows) == 4
    assert {r.variant_id for r in rows[:2]} == {ANCHORS[0].fingerprint, ANCHORS[1].fingerprint}
    assert inspect.signature(evo.choose).parameters.keys() == {'available', 'context'}


def test_future_protocol_is_unauthorized_and_h17_stays_blocked():
    proto = screen.future_protocol()
    assert proto['authorized'] is False and proto['locked'] is False and proto['executed'] is False
    assert proto['untouched_holdout_family'] == tasks.HOLDOUT_FAMILY
    assert 'H17' in proto['blocked']
    assert proto['resource_caps']['real_env_steps'] == 0
    assert proto['resource_caps']['scientific_ledger'] is False
    assert screen.classify_transfer(0.2, 0.1, 0.3, 10) == 'e2_persistence_helps_transfer'
    assert screen.classify_transfer(-0.2, -0.3, -0.1, 10) == 'e2_persistence_hurts_transfer'
    assert screen.classify_transfer(0.2, -0.1, 0.3, 10) == 'e2_transfer_not_established'
    assert screen.classify_transfer(0.2, 0.1, 0.3, 10, complete=False) == 'incomplete'


def test_public_view_omits_hidden_weights():
    task = make_task('balanced_scale', 1)
    view = task.public_view()
    dumped = json.dumps(view)
    assert 'hidden' not in dumped
    assert '0.60' not in dumped
    assert view['scientific'] is False
    best_id, best = oracle_best(task)
    persist = m.PersistentAdaptive(seed=7)
    chosen = persist.choose(tuple(VARIANTS), task.context)
    assert chosen.fingerprint != best_id or persist.learned_state()['updates'] == 0
    assert best >= hidden_score(task, chosen)
