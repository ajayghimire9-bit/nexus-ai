"""Pytest suite for Wave-8 deconfounded equal-capability mechanism and verifier."""

from __future__ import annotations

from pathlib import Path

from nexus.seed.deconfounded_equal_capability import (
    EQUAL_CAPABILITY_METHODS,
    EqualCapabilityLearner,
    execute_serialized_program_ast,
    universal_catalog_manifest,
)
from nexus.seed.mechanism_wave8_deconfounded import (
    OPENED_IDS,
    SPLIT_DELAYED,
    SPLIT_L1,
    SPLIT_L2,
    SPLIT_OOG,
    TASK_ORDERS_BY_SEED,
    WAVE8_DECONFOUNDED_TASKS,
    run_wave8_deconfounded,
)
from scripts.verify_wave8_deconfounded_equal_capability import (
    audit_learner_ast,
    verify_artifact,
)


def test_learner_ast_is_strictly_label_blind() -> None:
    root = Path(__file__).resolve().parents[1]
    learner_path = root / "src" / "nexus" / "seed" / "deconfounded_equal_capability.py"
    audit = audit_learner_ast(learner_path)
    assert audit["ast_clean"] is True, f"AST violations: {audit['violations']}"
    assert audit["solve_unfamiliar_task_args"] == ["self", "env", "public_budget"]
    assert audit["has_usage_age_prune"] is True


def test_task_ids_disjoint_and_seed_orders_distinct() -> None:
    task_ids = [t["task_id"] for t in WAVE8_DECONFOUNDED_TASKS]
    assert len(task_ids) == 14
    assert not (set(task_ids) & set(OPENED_IDS))
    unique_orders = {tuple(v) for v in TASK_ORDERS_BY_SEED.values()}
    assert len(unique_orders) == 3


def test_deconfounded_suite_and_reconstructing_verifier(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    learner_path = root / "src" / "nexus" / "seed" / "deconfounded_equal_capability.py"
    payload = run_wave8_deconfounded(tmp_path)
    artifact_path = tmp_path / "seed_wave8_deconfounded_equal_capability.json"
    assert artifact_path.exists()

    verification = verify_artifact(artifact_path, learner_path)
    assert verification["valid"] is True, f"Verifier failed: {verification}"
    assert verification["rows_verified"] == 252

    suite = payload["totals"]["suite"]
    # All 6 methods must achieve 42/42 mapping_correct and 42/42 private_correct under equal capability
    for method in EQUAL_CAPABILITY_METHODS:
        assert suite[method]["mapping_correct"] == 42
        assert suite[method]["private_correct"] == 42
        assert suite[method]["false_analogy_lock"] == 0
        assert suite[method]["false_unique"] == 0

    # Schema-using methods must record non-zero schema_distill_cost in raw rows
    for method in (
        "persistent_nexus_hierarchy_disabled",
        "persistent_nexus_gate_disabled",
        "persistent_nexus_pruning_disabled",
        "persistent_nexus_full",
    ):
        assert suite[method]["schema_distill_cost"] == 36
        assert suite[method]["role_probe_cost"] == 168

    # Both L1 sub-predicate reuse and complete L2 skill reuse occur
    assert suite["persistent_nexus_full"]["l1_sub_predicate_reused"] > 0
    assert suite["persistent_nexus_full"]["l2_full_skill_reused"] == 3
    assert suite["ordinary_persistent_memoization"]["memoized_program_reused"] == 3

    # Prerequisite gate reduces OOG work vs gate_disabled
    oog = payload["totals"]["oog"]
    assert (
        oog["persistent_nexus_full"]["total_work"]
        < oog["persistent_nexus_gate_disabled"]["total_work"]
    )

    # Honest pruning tradeoff: on Seed 0 delayed post-prune task, pruning_disabled beats full
    seed0_delayed = payload["seed_blocks"][0]["delayed"]
    assert (
        seed0_delayed["persistent_nexus_pruning_disabled"]["codegen_plus_synthesis"]
        < seed0_delayed["persistent_nexus_full"]["codegen_plus_synthesis"]
    )

    # Re-execute a sample L2 program AST directly
    sample_ast = {
        "domain_kind": "sequence",
        "kind": "macro_skill",
        "predicate_id": "palindrome_pred",
        "then_transform_id": "rotate_bang_tf",
        "else_transform_id": "identity",
        "macro_skill_id": "palindromic_rotate_bang",
    }
    assert execute_serialized_program_ast(sample_ast, ("r", "a", "r")) == (
        "a",
        "r",
        "r",
        "!",
    )
    assert execute_serialized_program_ast(sample_ast, ("a", "b")) == ("a", "b")
    assert len(universal_catalog_manifest()["extension_transforms"]) == 4
