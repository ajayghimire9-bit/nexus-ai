"""Tests for Wave-10 atomic self-evolving operators and cost-ordered meta-control."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_wave10_atomic_self_evolving import (
    FROZEN_DECONFOUNDED_LEARNER_SHA256,
    FROZEN_WAVE9_LEARNER_SHA256,
    audit_learner_ast,
    sha256_file,
    verify_wave10_artifact,
)
from nexus.seed.mechanism_wave10_atomic_evolution import (
    OPENED_IDS,
    TASK_ORDERS_BY_SEED,
    WAVE10_ATOMIC_TASKS,
)
from nexus.seed.wave10_atomic_self_evolving_learner import (
    AtomicSelfEvolvingLibrary,
    atomic_catalog_manifest,
    execute_wave10_program_ast,
    synthesize_wave10_atomic,
)


def test_wave10_ast_audit_and_frozen_sha256() -> None:
    root = Path(__file__).resolve().parents[1]
    w8_path = root / "src" / "nexus" / "seed" / "deconfounded_equal_capability.py"
    w9_path = (
        root / "src" / "nexus" / "seed" / "wave9_learned_abstraction_meta_control.py"
    )
    w10_path = (
        root / "src" / "nexus" / "seed" / "wave10_atomic_self_evolving_learner.py"
    )

    assert sha256_file(w8_path) == FROZEN_DECONFOUNDED_LEARNER_SHA256
    assert sha256_file(w9_path) == FROZEN_WAVE9_LEARNER_SHA256

    ast_audit = audit_learner_ast(w10_path)
    assert ast_audit["ast_clean"] is True
    assert ast_audit["solve_unfamiliar_task_args"] == ["self", "env", "public_budget"]
    assert ast_audit["has_usage_age_prune"] is True

    # Verify task IDs are strictly disjoint from OPENED_IDS and orders are distinct
    task_ids = {t["task_id"] for t in WAVE10_ATOMIC_TASKS}
    assert len(task_ids) == 16
    assert task_ids.isdisjoint(OPENED_IDS)
    unique_orders = {tuple(v) for v in TASK_ORDERS_BY_SEED.values()}
    assert len(unique_orders) == 3


def test_wave10_synthetic_public_only_tiers() -> None:
    manifest = atomic_catalog_manifest()
    assert len(manifest["atomic_base_predicates"]) == 7
    assert len(manifest["atomic_base_transforms"]) == 7

    lib = AtomicSelfEvolvingLibrary()

    # Synthetic public-only check 1: base depth-1 task solved in Tier 0
    core_even = [
        ((), ("m",)),
        (("a",), ("a",)),
        (("a", "b"), ("a", "b", "m")),
        (("b",), ("b",)),
    ]
    all_even = core_even + [(("c", "d", "e", "f"), ("c", "d", "e", "f", "m"))]
    res_t0 = synthesize_wave10_atomic(core_even, all_even, lib)
    assert res_t0.abstained is False
    assert res_t0.gate_evals == 0
    assert res_t0.micro_codegen_evals == 0
    assert res_t0.compression_evals == 0
    assert execute_wave10_program_ast(res_t0.program_ast.to_dict(), ("x", "y")) == (
        "x",
        "y",
        "m",
    )

    # Synthetic public-only check 2: multi-node predicate task solved in Tier 3a -> evolved
    core_ge3 = [
        ((), ()),
        (("a",), ("a",)),
        (("a", "b", "c"), ("a", "b", "c", "z")),
        (("a", "b"), ("a", "b")),
    ]
    all_ge3 = core_ge3 + [(("p", "q", "r", "s"), ("p", "q", "r", "s", "z"))]
    res_t3a = synthesize_wave10_atomic(core_ge3, all_ge3, lib)
    assert res_t3a.abstained is False
    assert "ast_len_ge_3" in res_t3a.invented_l1
    assert "ast_len_ge_3" in lib.operators

    # Synthetic public-only check 3: age out ast_len_ge_3 via 2 base tasks -> cold_archive
    synthesize_wave10_atomic(core_even, all_even, lib)
    synthesize_wave10_atomic(core_even, all_even, lib)
    assert "ast_len_ge_3" not in lib.operators
    assert "ast_len_ge_3" in lib.cold_archive

    # Synthetic public-only check 4: Tier-2 pre-synthesis cold archive reactivation
    core_ge3_q = [
        ((), ()),
        (("a",), ("a",)),
        (("a", "b", "c"), ("a", "b", "c", "q")),
        (("a", "b"), ("a", "b")),
    ]
    all_ge3_q = core_ge3_q + [(("p", "q", "r", "s"), ("p", "q", "r", "s", "q"))]
    res_t2 = synthesize_wave10_atomic(core_ge3_q, all_ge3_q, lib)
    assert res_t2.cold_archive_reactivated is True
    assert res_t2.micro_codegen_evals == 0
    assert "ast_len_ge_3" in lib.operators

    # Synthetic public-only check 5: Tier-3b transform evolution + Tier-1 recombination + Tier-3d scratch
    core_even_rot = [
        ((), ("!",)),
        (("a",), ("a",)),
        (("a", "b"), ("b", "a", "!")),
        (("b",), ("b",)),
    ]
    all_even_rot = core_even_rot + [(("m", "n", "p", "q"), ("n", "p", "q", "m", "!"))]
    res_t3b = synthesize_wave10_atomic(core_even_rot, all_even_rot, lib)
    assert "ast_rotate_left_bang" in res_t3b.invented_l2

    core_pal_z = [
        ((), ("z",)),
        (("a",), ("a", "z")),
        (("r", "a", "r"), ("r", "a", "r", "z")),
        (("a", "b"), ("a", "b")),
    ]
    all_pal_z = core_pal_z + [(("k", "o", "k"), ("k", "o", "k", "z"))]
    res_pal = synthesize_wave10_atomic(core_pal_z, all_pal_z, lib)
    assert "ast_eq_reverse" in res_pal.invented_l1

    core_pal_rot = [
        (("a",), ("a", "!")),
        (("b", "b"), ("b", "b", "!")),
        (("r", "a", "r"), ("a", "r", "r", "!")),
        (("a", "b"), ("a", "b")),
    ]
    all_pal_rot = core_pal_rot + [(("a", "b", "c", "a"), ("a", "b", "c", "a"))]
    res_t1_deep = synthesize_wave10_atomic(core_pal_rot, all_pal_rot, lib)
    assert res_t1_deep.micro_codegen_evals == 0
    assert (
        res_t1_deep.program_ast.macro_skill_id
        == "macro_ast_eq_reverse_ast_rotate_left_bang"
    )

    scratch_lib = AtomicSelfEvolvingLibrary(
        use_predicate_evolution=False,
        use_transform_evolution=False,
        use_pruning=False,
        use_cold_archive=False,
        use_pre_synthesis_archive=False,
        use_base_first_beam=True,
        use_event_triggered_mdl=True,
        use_memoization=False,
        use_schemas=False,
    )
    res_t3d = synthesize_wave10_atomic(core_pal_rot, all_pal_rot, scratch_lib)
    assert res_t3d.abstained is False
    assert res_t3d.micro_codegen_evals > 0


def test_wave10_artifact_verification_when_present() -> None:
    root = Path(__file__).resolve().parents[1]
    artifact_path = (
        root / "artifacts" / "seed_wave10_atomic_self_evolving_operators.json"
    )
    if not artifact_path.exists():
        pytest.skip("Wave-10 artifact not yet generated (pre-Commit-1 check).")
    w8_path = root / "src" / "nexus" / "seed" / "deconfounded_equal_capability.py"
    w9_path = (
        root / "src" / "nexus" / "seed" / "wave9_learned_abstraction_meta_control.py"
    )
    w10_path = (
        root / "src" / "nexus" / "seed" / "wave10_atomic_self_evolving_learner.py"
    )
    res = verify_wave10_artifact(artifact_path, w8_path, w9_path, w10_path)
    assert res["valid"] is True
    assert res["rows_verified"] == 288
    assert res["gates"]["passed"] is True
