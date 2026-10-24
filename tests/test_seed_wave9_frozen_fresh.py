"""Pytest suite for Wave-9 frozen-fresh comparison and self-adaptive learner."""

from __future__ import annotations

from pathlib import Path

from nexus.seed.mechanism_wave9_fresh_holdout import (
    FROZEN_BF66447_METHODS,
    OPENED_IDS,
    TASK_ORDERS_BY_SEED,
    WAVE9_COMPARISON_METHODS,
    WAVE9_FRESH_HOLDOUT_TASKS,
    run_wave9_frozen_fresh,
)
from nexus.seed.wave9_learned_abstraction_meta_control import (
    WAVE9_SELF_ADAPTIVE_METHOD,
)
from scripts.verify_wave9_frozen_fresh_comparison import (
    FROZEN_DECONFOUNDED_LEARNER_SHA256,
    audit_learner_ast,
    sha256_file,
    verify_wave9_artifact,
)


def test_frozen_learner_sha256_and_ast_audits() -> None:
    root = Path(__file__).resolve().parents[1]
    frozen_path = root / "src" / "nexus" / "seed" / "deconfounded_equal_capability.py"
    adaptive_path = (
        root / "src" / "nexus" / "seed" / "wave9_learned_abstraction_meta_control.py"
    )
    assert sha256_file(frozen_path) == FROZEN_DECONFOUNDED_LEARNER_SHA256

    frozen_audit = audit_learner_ast(frozen_path)
    adaptive_audit = audit_learner_ast(adaptive_path)
    assert frozen_audit["ast_clean"] is True, f"Frozen AST violations: {frozen_audit}"
    assert (
        adaptive_audit["ast_clean"] is True
    ), f"Adaptive AST violations: {adaptive_audit}"
    assert adaptive_audit["solve_unfamiliar_task_args"] == [
        "self",
        "env",
        "public_budget",
    ]


def test_wave9_task_ids_disjoint_and_seed_orders_distinct() -> None:
    task_ids = [t["task_id"] for t in WAVE9_FRESH_HOLDOUT_TASKS]
    assert len(task_ids) == 14
    assert not (set(task_ids) & set(OPENED_IDS))
    unique_orders = {tuple(v) for v in TASK_ORDERS_BY_SEED.values()}
    assert len(unique_orders) == 3
    assert len(FROZEN_BF66447_METHODS) == 4
    assert len(WAVE9_COMPARISON_METHODS) == 5


def test_wave9_suite_and_reconstructing_verifier(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    frozen_path = root / "src" / "nexus" / "seed" / "deconfounded_equal_capability.py"
    adaptive_path = (
        root / "src" / "nexus" / "seed" / "wave9_learned_abstraction_meta_control.py"
    )
    payload = run_wave9_frozen_fresh(tmp_path)
    artifact_path = tmp_path / "seed_wave9_frozen_fresh_and_adaptive.json"
    assert artifact_path.exists()

    verification = verify_wave9_artifact(artifact_path, frozen_path, adaptive_path)
    assert verification["valid"] is True, f"Verifier failed: {verification}"
    assert verification["rows_verified"] == 210
    assert verification["frozen_learner_sha256_verified"] is True

    suite = payload["totals"]["suite"]
    for method in WAVE9_COMPARISON_METHODS:
        assert suite[method]["mapping_correct"] == 42
        assert suite[method]["private_correct"] == 42
        assert suite[method]["false_analogy_lock"] == 0
        assert suite[method]["false_unique"] == 0

    assert suite[WAVE9_SELF_ADAPTIVE_METHOD]["cold_archive_reactivated"] >= 2
