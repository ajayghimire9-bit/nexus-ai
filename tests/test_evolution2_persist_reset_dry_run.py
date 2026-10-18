"""Development-only persist-versus-reset dry-run. Not a scientific experiment."""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from nexus.evolution1.catalogue import catalogue
from nexus.evolution2 import persist_reset_dry_run as run
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.methods import EvolutionarySearch, make_methods
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator
from nexus.evolution2.planner_adapter import twelve_arm_scientific_dispatch
from nexus.evolution2.tasks import HOLDOUT_FAMILY, PROPOSALS, hidden_score, make_task


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_dispatch_remains_an_unimplemented_scientific_stub():
    text = Path(lock.__file__).read_text()
    assert "persist_versus_reset_not_implemented_while_unauthorized" in text
    assert "run_development_dry_run" not in text
    imported = _imports(Path(lock.__file__))
    assert "nexus.evolution2.persist_reset_dry_run" not in imported
    source = inspect.getsource(lock.dispatch)
    assert "require_named_holdout" in source
    assert "run_development_dry_run" not in source
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(7680)
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.require_named_holdout()


def test_bonferroni_five_versus_three_is_intentional_conservatism():
    sheet = lock.worksheet()
    assert sheet["bonferroni_comparisons_locked"] == 5
    assert sheet["listed_controls"] == 3
    assert sheet["bonferroni_conservatism"] == lock.BONFERRONI_NOTE
    assert sheet["science_runner"] == "unimplemented_stub"
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
    assert lock.file_sha256(lock.PROTOCOL) == lock.LOCKED_PROTOCOL
    assert lock.file_sha256(lock.ALLOCATION) == lock.LOCKED_ALLOCATION


def test_development_dry_run_exercises_four_methods_with_equal_budget():
    payload = run.run_development_dry_run(seed=7)
    assert payload["dry_run"] == "PASS"
    assert payload["all_four_methods_exercised"] is True
    assert payload["methods_exercised"] == ["persist", "reset", "random", "evolution"]
    assert payload["equal_budget"] is True
    assert payload["leakage_audit"] == "PASS"
    assert set(payload["lookups_per_method"].values()) == {4 * PROPOSALS}
    assert payload["persist_cross_task"]["weights_changed"] is True
    assert payload["persist_cross_task"]["updates"] == 3 * PROPOSALS
    assert payload["reset_genuine"]["after_reset_zero_weights"] is True
    assert payload["reset_genuine"]["after_reset_updates"] == [0, 0, 0]
    assert payload["random_independent"] is True
    assert payload["evolution_legal"] is True
    assert payload["crossover_illegal"] is True
    assert payload["hidden_feedback_isolated"] is True
    assert payload["holdout_consumed"] is False
    assert payload["evaluator_physical"] == 48
    assert payload["evaluator_cached"] == 64
    assert payload["ledger"]["status"] == "complete_execution"
    assert payload["ledger"]["physical"]["model_calls"] == 48
    assert payload["ledger"]["logical"]["imagined_transitions"] == 112
    assert payload["ledger"]["physical"]["imagined_transitions"] == 48
    assert payload["interruption"]["status"] == "incomplete_execution"
    assert payload["interruption"]["reason"] == "interrupted"
    assert "never-started" in payload["interruption"]["unresolved"]
    assert payload["twelve_arm_dispatch"] == "PASS"
    assert payload["twelve_arm_scientific"] == "BLOCKED"
    assert payload["scientific_execution"] == "BLOCKED"
    assert payload["scientific"] is False
    assert payload["gymnasium"] is False
    assert payload["h16_scientific_ledger_untouched"] is True
    assert payload["scientific_ledger_preserved"] == [305.842, 3294.158]
    assert payload["cited_config_sha256"] == lock.LOCKED_CONFIG


def test_dry_run_does_not_use_historical_holdout_gate_or_gymnasium():
    imported = _imports(Path(run.__file__))
    assert "gymnasium" not in imported
    text = Path(run.__file__).read_text()
    assert "require_named_holdout()" not in text
    assert "lock.require_named_holdout" not in text
    assert "review.require_named_holdout" not in text
    assert "collect_transitions" not in text
    assert "make_task_env" not in text
    assert "train_world_model" not in text
    assert "from nexus.world.train" not in text
    split = run.development_split()
    used = split["train"] + split["development"]
    assert HOLDOUT_FAMILY not in {task.family for task in used}
    run.development_fixtures_are_not_a_holdout(used)
    for task in used:
        view = task.public_view()
        assert "hidden" not in view
        dumped = str(view)
        assert "0.36" not in dumped


def test_hidden_score_substitution_and_crossover_stay_illegal():
    task = make_task("successor_scale", 0)
    evaluator = TrustedEvaluator(
        catalogue(),
        family=task.family,
        bundle_id=task.instance,
        produce_score=lambda variant: hidden_score(task, variant),
    )
    first = evaluator.evaluate("persist", catalogue()[0], family=task.family, bundle_id=0)
    second = evaluator.evaluate("reset", catalogue()[0], family=task.family, bundle_id=0)
    assert first == second
    assert evaluator.physical == 1
    assert evaluator.cached == 1
    with pytest.raises(RuntimeError, match="score_substitution_forbidden"):
        evaluator.reveal("persist", catalogue()[0], 0.99)
    evo = EvolutionarySearch(seed=7)
    with pytest.raises(Exception, match="crossover_is_illegal"):
        evo._crossover()


def test_random_states_and_checkpoint_identity_are_independent():
    ctx = make_task("successor_scale", 0).context
    assert run.random_choice_sequence(7, ctx) != run.random_choice_sequence(11, ctx)
    assert run.random_choice_sequence(7, ctx) == run.random_choice_sequence(7, ctx)
    identity = run.checkpoint_identity()
    assert set(identity) == {"pendulum", "acrobot"}
    methods = make_methods(7)
    assert set(methods) >= set(run.METHOD_KEYS.values())
    scientific = twelve_arm_scientific_dispatch()
    assert scientific["status"] == "BLOCKED"
    assert scientific["development_binding"] == "PASS"
    assert lock.allocation_record()["authorized"] is False
