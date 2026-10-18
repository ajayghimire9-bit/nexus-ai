"""Source-only fitting inventory and trusted-cache audit. No collection."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot
from nexus.evolution2 import residual_timing_probe as timing
from nexus.evolution2 import source_fitting_benchmark as m


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_source_fitting_is_unavailable_without_collection():
    status = m.source_data_status()
    assert status["status"] == "SOURCE_FITTING_UNAVAILABLE"
    assert status["found"] == []
    assert status["collection"] is False
    assert status["scientific"] is False
    assert status["ledger_debit_s"] == 0
    assert status["scientific_ledger_preserved"] == [305.842, 3294.158]
    assert status["recipe"]["module"] == "nexus.world.train.train_world_model"
    assert status["recipe"]["kind"] == "residual"
    assert status["recipe"]["n_train"] == 1024
    assert status["recipe"]["n_val"] == 256
    assert status["recipe"]["epochs"] == 20
    assert status["recipe"]["persists_transitions"] is False
    assert status["recipe"]["recipe_sha256"]
    with pytest.raises(RuntimeError, match="SOURCE_FITTING_UNAVAILABLE"):
        m.require_fitting_benchmark()


def test_checkpoint_provenance_is_read_only_and_hash_locked():
    rows = m.checkpoint_provenance()
    assert [row["id"] for row in rows] == [spec["id"] for spec in timing.REQUIRED_CHECKPOINTS]
    for row, spec in zip(rows, timing.REQUIRED_CHECKPOINTS, strict=True):
        assert row["expected_sha256"] == spec["sha256"]
        if row["present"]:
            assert row["matches"] is True


def test_combined_feasibility_does_not_invent_fitting_cost():
    report = m.combined_feasibility()
    assert report["fitting"] == "SOURCE_FITTING_UNAVAILABLE"
    assert report["source_fitting_s"] is None
    assert report["ten_bundle_two_family_expected_fitting_s"] is None
    assert report["v2_real_steps"] == 97600
    assert report["v2_imagined"] == 110592000
    assert report["pilot_real_steps"] == 57600
    assert report["pilot_imagined"] == 49152000
    assert report["v2_feasibility"] == "NO-GO"
    assert report["pilot_feasibility"] == "UNKNOWN"
    assert report["new_ledger_debit"] is False
    assert "SOURCE_FITTING_UNAVAILABLE" in report["blockers"]
    assert report["v2_conservative_planning_s"] > 600
    payload = m.write_artifact()
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["trusted_cache"] == "TrustedEvaluator"


def test_trusted_evaluator_owns_scores_and_separates_accounts():
    revealed = v2.anchors()
    produced = []

    def produce(variant):
        produced.append(variant)
        return 3.25

    evaluator = pilot.TrustedEvaluator(
        revealed, family="pendulum", bundle_id=0, produce_score=produce
    )
    first = evaluator.evaluate("persist", revealed[0], family="pendulum", bundle_id=0)
    second = evaluator.evaluate("reset", revealed[0], family="pendulum", bundle_id=0)
    assert first == second == 3.25
    assert produced == [revealed[0]]
    assert evaluator.physical == 1
    assert evaluator.cached == 1
    assert evaluator.charged == 2
    assert evaluator.training_feedback("persist")[revealed[0]] == 3.25
    assert evaluator.training_feedback("reset")[revealed[0]] == 3.25
    with pytest.raises(RuntimeError, match="score_substitution_forbidden"):
        evaluator.reveal("persist", revealed[0], 99.0)


def test_trusted_evaluator_blocks_forbidden_and_hidden_rows():
    revealed = v2.anchors()
    unused = next(variant for variant in v2.legal_mutants(revealed[0]) if variant not in revealed)
    evaluator = pilot.TrustedEvaluator(
        revealed, family="pendulum", bundle_id=0, produce_score=lambda _v: 1.0
    )
    evaluator.hide_development(revealed[1], 7.0)
    with pytest.raises(RuntimeError, match="unused_variant_not_revealed"):
        evaluator.evaluate("persist", unused)
    with pytest.raises(RuntimeError, match="hidden_development_outcome"):
        evaluator.evaluate("persist", revealed[1])
    assert revealed[1] not in evaluator.training_feedback("persist")
    assert evaluator._development[revealed[1]] == 7.0


def test_trusted_evaluator_blocks_cross_family_and_bundle_contamination():
    revealed = v2.anchors()
    pendulum = pilot.TrustedEvaluator(
        revealed, family="pendulum", bundle_id=0, produce_score=lambda _v: 1.0
    )
    acrobot = pilot.TrustedEvaluator(
        revealed, family="acrobot", bundle_id=1, produce_score=lambda _v: 2.0
    )
    pendulum.evaluate("persist", revealed[0])
    with pytest.raises(RuntimeError, match="cross_family_contamination"):
        pendulum.evaluate("reset", revealed[0], family="acrobot")
    with pytest.raises(RuntimeError, match="cross_bundle_contamination"):
        pendulum.evaluate("reset", revealed[0], bundle_id=1)
    other = acrobot.evaluate("persist", revealed[0], family="acrobot", bundle_id=1)
    assert other == 2.0
    assert pendulum.training_feedback("persist")[revealed[0]] == 1.0
    assert acrobot.training_feedback("persist")[revealed[0]] == 2.0


def test_inventory_and_pilot_stay_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "torch" not in imported
    assert "nexus.tasks.spec" not in imported
    assert "nexus.world.train" not in imported
    assert "nexus.evolution1.adapters" not in imported
    text = Path(m.__file__).read_text()
    assert "collect_transitions" not in text
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
