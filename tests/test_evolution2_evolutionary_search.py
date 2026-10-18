"""Population-4 / tournament-2 evolutionary baseline. Synthetic only."""
from __future__ import annotations

import inspect

import pytest

from nexus.evolution1.catalogue import Variant
from nexus.evolution1.toy_loop import ANCHORS, TrainingFeedback, VARIANTS
from nexus.evolution2 import methods as m
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import screen
from nexus.evolution2.tasks import make_task


def test_cold_start_still_returns_first_available_without_feedback():
    evo = m.EvolutionarySearch(seed=7)
    first = evo.choose(tuple(VARIANTS), make_task("horizon_scale", 0).context)
    assert first is VARIANTS[0]
    assert evo.population_size == 4
    assert evo.tournament_size == 2
    assert v2.existing_evolution_implements_population_tournament() is True


def test_population_is_capped_and_resets_across_tasks():
    evo = m.EvolutionarySearch(seed=7)
    task = make_task("horizon_scale", 0)
    rows = screen.propose_on_task(evo, task)
    assert len(rows) == 4
    assert {r.variant_id for r in rows[:2]} == {ANCHORS[0].fingerprint, ANCHORS[1].fingerprint}
    assert len({r.variant_id for r in rows}) == 4
    assert len(evo.population) == 4
    assert evo.learned_state()["population"] == 4
    evo.reset_task()
    assert evo.population == []
    assert evo.parent is None


def test_tournament_parent_changes_later_choices_and_forbids_crossover():
    evo = m.EvolutionarySearch(seed=3)
    task = make_task("successor_scale", 0)
    screen.propose_on_task(evo, task)
    available = [v for v in VARIANTS if v not in [row[1] for row in evo.population]]
    chosen = evo.choose(tuple(available), task.context)
    assert chosen in available
    parent = evo.parent
    changed = (
        int(chosen.rule is not parent.rule)
        + int(chosen.generator is not parent.generator)
        + int(chosen.horizon != parent.horizon)
    )
    assert changed == 1


def test_unsuccessful_mutation_does_not_silently_return_unrelated_available():
    evo = m.EvolutionarySearch(seed=0)
    parent = VARIANTS[0]
    evo.population = [(1.0, parent)]
    evo.parent = parent
    evo.best_score = 1.0
    illegal = [
        v
        for v in VARIANTS
        if (
            int(v.rule is not parent.rule)
            + int(v.generator is not parent.generator)
            + int(v.horizon != parent.horizon)
        )
        != 1
    ]
    with pytest.raises(m.MethodError, match="no_legal_mutant_in_available"):
        evo.choose(tuple(illegal), make_task("horizon_scale", 0).context)


def test_mutation_search_fallback_stays_inside_legal_available():
    evo = m.EvolutionarySearch(seed=1)
    parent = VARIANTS[0]
    evo.population = [(1.0, parent)]
    evo.parent = parent
    legal = [
        v
        for v in VARIANTS
        if (
            int(v.rule is not parent.rule)
            + int(v.generator is not parent.generator)
            + int(v.horizon != parent.horizon)
        )
        == 1
    ]
    chosen = evo.choose(tuple(legal), make_task("horizon_scale", 0).context)
    assert chosen in legal
    assert chosen is not parent
    with pytest.raises(m.MethodError, match="crossover"):
        evo._crossover()


def test_feedback_is_training_only_and_hidden_scores_are_not_arguments():
    evo = m.EvolutionarySearch(seed=7)
    params = inspect.signature(evo.update).parameters
    assert "oracle" not in params and "hidden" not in params
    task = make_task("horizon_scale", 0)
    rows = screen.propose_on_task(evo, task)
    with pytest.raises(m.MethodError, match="permitted_training_feedback_only"):
        evo.update({"score": 1.0}, task.context)
    replay = TrainingFeedback(rows[0].variant_id, 0.0, False, rows[0].event_id)
    with pytest.raises(m.MethodError, match="replayed"):
        evo.update(replay, task.context)
    assert inspect.signature(evo.choose).parameters.keys() == {"available", "context"}


def test_synthetic_screen_label_is_unchanged():
    report = screen.run_screen(seed=7, local_updates=False)
    assert report["illustration_label"] == "synthetic_illustration_not_a_result"
    assert report["mode"] == "synthetic_only"
    assert report["scientific"] is False
