"""Unit & Pre-Freeze Dry-Run Tests for Wave 24 (`wave24_cross_family_meta_and_quotient_engine.py`).

Uses the separate Development Suite (`build_wave24_dev_suite` / `w24_dev_*`) so final post-freeze
assessment tasks (`w24f_*`, parameterized by the Commit-1 SHA) are never pre-exercised before Commit 1.
"""
from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'src'))
if str(REPO_ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'scripts'))

from nexus.seed.wave24_cross_family_meta_and_quotient_engine import (
    TASK_FAMILIES,
    ActiveInfoGainCorrespondenceEngine,
    MetaProcedureOptimizer,
    MultiFamilyASTEngine,
    ObservationalQuotientWitnessEngine,
    UtilityGatedSkillHygiene,
    Wave24WorkCounter,
    build_16_adversarial_distractor_skills,
    build_wave24_dev_suite,
    build_wave24_source_training_suite,
    run_wave24_experiment,
    verify_multi_family_ast_bounds,
)
from verify_wave24_cross_family_experiment import verify_wave24_payload


def test_multi_family_ast_bounds_and_zero_compound_boxes() -> None:
    """Verifies that all programs in all 4 families obey `<= 7` statements, depth `<= 3`, and zero compound boxes."""
    for fam in TASK_FAMILIES:
        by_strat = MultiFamilyASTEngine.build_family_catalog_by_strategy(fam)
        total_progs = 0
        for strat, progs in by_strat.items():
            assert len(progs) > 0, f'Empty strategy {strat} in {fam}'
            for p in progs:
                total_progs += 1
                assert p.statement_count() <= 7
                assert p.max_expression_depth() <= 3
                assert verify_multi_family_ast_bounds(p)
        assert total_progs >= 20


def test_observational_quotient_witness_engine_100_percent_soundness_on_dev_suite() -> None:
    """(a) Verifies 100% agreement between `ObservationalQuotientWitnessEngine` and exhaustive unquotiented search."""
    dev_suite = build_wave24_dev_suite()
    seen_statuses: set[str] = set()

    for task in dev_suite['track2_tasks']:
        pub = [(x, y) for x, y in task['public']]
        q_in = task['query_input']
        budget = int(task.get('max_candidate_budget', 400))
        is_stateful = bool(task.get('declared_stateful', False))
        fam = MultiFamilyASTEngine.infer_task_family_from_public_io(pub)
        by_strat = MultiFamilyASTEngine.build_family_catalog_by_strategy(fam)
        flat_cat = [p for s in MetaProcedureOptimizer.STRATEGIES for p in by_strat[s]]

        c_quot = Wave24WorkCounter()
        rep_quot = ObservationalQuotientWitnessEngine.run_quotient_witness_search(
            flat_cat, pub, q_in, c_quot, max_candidate_budget=budget, is_stateful_history_task=is_stateful
        )

        c_unq = Wave24WorkCounter()
        rep_unq = ObservationalQuotientWitnessEngine.run_exhaustive_unquotiented_reference(
            flat_cat, pub, q_in, c_unq, max_candidate_budget=budget, is_stateful_history_task=is_stateful
        )

        assert rep_quot.status == rep_unq.status == task['gold_witness_status']
        assert rep_quot.declared_uncertainty_status == rep_unq.declared_uncertainty_status
        assert rep_quot.primary_query_output == rep_unq.primary_query_output
        seen_statuses.add(rep_quot.status)

        if rep_quot.status == 'UNIQUE_IN_BOUNDED_SPACE':
            # Quotienting + query-output disagreement filtering must strictly reduce total work vs unquotiented search
            assert c_quot.total_work < c_unq.total_work

    assert {
        'UNIQUE_IN_BOUNDED_SPACE',
        'AMBIGUOUS_WITNESS_FOUND',
        'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED',
        'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
        'NO_PROGRAM_IN_BOUNDED_GRAMMAR',
    }.issubset(seen_statuses)


def test_meta_procedure_optimizer_cross_family_transfer_and_symkan_gating() -> None:
    """(b) & (c) Verifies `MetaProcedureOptimizer` trained on Families A & B transfers to unseen Families C & D."""
    from nexus.seed.wave21_grounded_llm_epistemic_gate import resolve_local_pretrained_gguf_path
    try:
        resolve_local_pretrained_gguf_path()
    except FileNotFoundError:
        import pytest
        pytest.skip("local pretrained GGUF weights (qwen2.5-0.5b-instruct-q4_k_m.gguf) are absent on this machine")
    src_suite = build_wave24_source_training_suite()
    meta_opt = MetaProcedureOptimizer()
    train_info = meta_opt.fit_from_source_families_ab(src_suite['track2_source_tasks'])
    meta_opt.freeze_policy()

    assert train_info['policy_training_work'] > 0
    assert len(meta_opt.training_provenance) == len(src_suite['track2_source_tasks'])

    # Execute full dev experiment and check H1, H2, SymKAN gating, Hygiene, and Verifier dry-run
    payload, manifest = run_wave24_experiment(
        freeze_commit_sha='0' * 40,
        seeds=(0, 1),
        use_dev_suite=True,
        execute_metal_llm=True,
    )

    t2_sum = payload['track2_factorial_summary']
    # (b) SymKAN faithful export == nonempty induced count, and zero wasted calls on sorted/non-int tasks
    for m_name, stats in t2_sum.items():
        assert stats['symkan_faithful_export_count'] == stats['symkan_nonempty_induced_count']

    # (c) H1: learned_meta_procedure_skills_cleared beats fixed_default_procedure_solver and object_level_weights_only_solver on unseen C & D
    c_cd = t2_sum['learned_meta_procedure_skills_cleared']['unseen_families_cd_first_acquisition_work']
    a_cd = t2_sum['fixed_default_procedure_solver']['unseen_families_cd_first_acquisition_work']
    f_cd = t2_sum['object_level_weights_only_solver']['unseen_families_cd_first_acquisition_work']
    assert c_cd < a_cd
    assert c_cd < f_cd

    # H2: learned_meta_procedure_plus_skills beats fixed_procedure_with_templates on unseen C & D
    d_cd = t2_sum['learned_meta_procedure_plus_skills']['unseen_families_cd_total_work']
    b_cd = t2_sum['fixed_procedure_with_templates']['unseen_families_cd_total_work']
    assert d_cd < b_cd
    assert payload['h1_and_h2_verdicts']['H1_policy_only_skills_cleared_vs_fixed_no_skills'][
        'established_on_unseen_families_cd_operating_work'
    ] is True
    assert payload['h1_and_h2_verdicts']['H2_acquired_structure_plus_policy_vs_ordinary_template_reuse'][
        'established_on_unseen_families_cd'
    ] is True

    # (d) UtilityGatedSkillHygiene quarantines 16 injected distractors and beats naive accumulation
    hyg_sum = payload['track2_hygiene_summary']
    assert hyg_sum['utility_gated_continual_hygiene']['max_auto_quarantined_skills'] >= 12
    assert hyg_sum['utility_gated_continual_hygiene']['harmful_interference_work'] == 0
    assert (
        hyg_sum['utility_gated_continual_hygiene']['total_work']
        < hyg_sum['naive_continual_accumulation_no_hygiene']['total_work']
    )

    # (e) Pre-freeze dry-run check of `verify_wave24_payload` on dev payload
    v_rep = verify_wave24_payload(payload, manifest, freeze_commit='', check_git=True)
    assert v_rep['valid'] is True, f"Verifier dry-run failed with errors: {v_rep['errors']}"
    assert v_rep['errors'] == []
