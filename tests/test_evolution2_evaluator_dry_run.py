"""Development-only dry-run contracts. No Gymnasium collection."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution1.catalogue import catalogue
from nexus.evolution2 import evaluator_dry_run as run
from nexus.evolution2 import evaluator_readiness as ready
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_dry_run_covers_twelve_configs_without_gymnasium():
    imported = _imports(Path(run.__file__))
    assert "gymnasium" not in imported
    text = Path(run.__file__).read_text()
    assert "collect_transitions" not in text
    assert "make_task_env" not in text
    assert "train_world_model" not in text
    payload = run.run_dry_run()
    assert payload["n_planner_configs"] == 12
    assert payload["n_family_rows"] == 24
    assert payload["scientific"] is False
    assert payload["gymnasium"] is False
    assert payload["training"] is False
    assert payload["twenty_fit_measured"] is False
    assert payload["interruption"]["status"] == "incomplete_execution"
    assert payload["interruption"]["reason"] == "interrupted"
    assert "never_started" in payload["interruption"]["unresolved"]
    keys = {(row["family"], row["rule"], row["generator"], row["horizon"]) for row in payload["rows"]}
    assert len(keys) == 24
    pendulum = reviewed_binding("pendulum")
    assert run.decode_action(pendulum, 0) == -2.0
    assert run.decode_action(pendulum, 2) == 2.0
    with pytest.raises(RuntimeError, match="action_decode_failed"):
        run.decode_action(pendulum, 3)


def test_trusted_evaluator_owns_dry_run_scores():
    allowed = catalogue()
    produced = []

    def produce(variant):
        produced.append(variant)
        return 1.5

    evaluator = TrustedEvaluator(allowed, family="pendulum", bundle_id=0, produce_score=produce)
    first = evaluator.evaluate("persist", allowed[0])
    second = evaluator.evaluate("reset", allowed[0])
    assert first == second == 1.5
    assert produced == [allowed[0]]
    assert evaluator.physical == 1
    assert evaluator.cached == 1
    with pytest.raises(RuntimeError, match="score_substitution_forbidden"):
        evaluator.reveal("persist", allowed[0], 99.0)
    assert ready.SCIENTIFIC is False
