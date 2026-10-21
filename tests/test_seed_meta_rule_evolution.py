"""Tests for the Combined Wake-Sleep-Dream-Evolution Architecture & Meta-Rule Evolution v1."""
import copy
import random
import pytest

from nexus.seed import meta_rule_evolution as mre


def test_immutable_kernel_and_dsl_bounds() -> None:
    cfg = mre.configuration()
    assert mre.config_check(cfg)["real_steps"] == 3072
    kernel = mre.ImmutableTrustedKernel(cfg)
    sig_before = kernel.kernel_signature()
    assert kernel.verify_integrity() is True

    starters = mre.make_starter_rules()
    assert len(starters) == 5
    for r in starters:
        assert 10 <= len(r["instructions"]) <= 30
        assert r["instructions"][-1] == "STOP"

    rng = random.Random(1751000001)
    pop = mre.build_initial_population(1751000001, 32)
    assert len(pop) == 32
    for r in pop:
        assert 10 <= len(r["instructions"]) <= 30
        mut = mre.mutate_learning_rule(r, rng, "test_mut")
        assert 10 <= len(mut["instructions"]) <= 30
        assert mut["instructions"][-1] == "STOP"

    assert kernel.kernel_signature() == sig_before


def test_wake_zorp_capsule_and_four_grammars() -> None:
    for g in mre.GRAMMAR_FAMILIES:
        pool = mre.build_grammar_hypothesis_pool(g)
        assert pool["stored_whole_program_fingerprints"] == 0
        assert len(pool["primitives"]) == 6
        assert len(pool["primitive_models"]) == 6

    s0 = mre.run_single_seed_evolution(0, 1751000001, mre.configuration())
    zcap = s0["zorp_capsule"]
    assert zcap is not None
    assert "zorp" in zcap["names"]
    assert zcap["selected_composition"] == ["even", "decrement", "reverse", "unique"]
    assert set(zcap) == {
        "names",
        "type",
        "remaining_hypotheses",
        "selected_composition",
        "preconditions",
        "predicted_effects",
        "evidence",
        "counterexamples",
        "tests",
        "provenance",
    }
    assert zcap["provenance"]["constructed_from_primitives"] is True
    assert zcap["provenance"]["whole_program_fingerprint_lookup"] is False


def test_dream_admissibility_and_sleep_compression() -> None:
    cfg = mre.configuration()
    s0 = mre.run_single_seed_evolution(0, cfg["seeds"][0], cfg)
    dream = s0["dream_report"]
    assert dream["rejected_inadmissible_foils"] == 2
    assert dream["archive_cycle_rate"] == 0.0
    assert dream["mean_selected_regret"] > 0.0
    for item in dream["selected_high_regret_tasks"]:
        assert all(item["admissibility_checks"].values())

    sleep = s0["sleep_report"]
    assert sleep["mdl_reduction"] >= 1.0
    assert sleep["old_capsule_test_pass_rate"] == 1.0
    assert sleep["distilled_policy"]["neural_decides_truth"] is False
    assert len(sleep["accepted_macros"]) >= 1


def test_full_study_passes_all_nine_gates() -> None:
    res = mre.run_study()
    eval_block = res["study"]["evaluation"]
    assert eval_block["verdict"] == "PASS_META_RULE_EVOLUTION_V1"
    assert eval_block["overall_pass"] is True
    for g_name, g_val in eval_block["gates"].items():
        assert g_val is True, f"Gate failed: {g_name}"


def test_saved_replay_and_independent_verifier() -> None:
    replay = mre.saved_replay()
    assert replay["id"] == "seed-meta-rule-evolution-1"
    assert replay["status"] == "complete_development"
    assert replay["meta_rule_evolution"]["verdict"] == "PASS_META_RULE_EVOLUTION_V1"
    assert replay["meta_rule_evolution"]["overall_pass"] is True

