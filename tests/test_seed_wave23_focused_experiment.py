"""Pre-freeze unit and integration tests for Wave 23 focused experiment on Apple Silicon M4 GPU."""
from __future__ import annotations

from nexus.seed.wave23_focused_meta_learning_and_witness_engine import (
    AuthoritativeTemplateStore,
    ElementaryProgramAST,
    ElementarySandboxExecutor,
    InterventionalMappingAcquisitionEngine,
    M4ElementaryStepProposer,
    NeuralTelemetry,
    SymbolicKANResidualInducer,
    WAVE23_TRACK1_METHODS,
    WAVE23_TRACK2_METHODS,
    WAVE23_TRACK3_METHODS,
    Wave23WorkCounter,
    build_bounded_elementary_catalog,
    build_wave23_Tracks_suite,
    derive_public_scalar_alignments,
    run_three_state_witness_search,
    run_wave23_llm_dialogue_suite,
    solve_wave23_elementary_task,
    verify_no_compound_loop_boxes,
)


def test_witness_pair_ambiguity_and_rejection_of_v_minus_2_on_audited_example() -> None:
    """Verifies requirement (a):
    - `v - 2 if v > 2 else v` is rejected on `[4, 6, 3] -> [2, 3]` (maps 6 -> 4 != 3).
    - `g_1` (`v // 2 if v > 2 else v`) and `g_2` (`v - 3 if v > 4 else 2`) both fit
      `[2, -3, 1] -> [2]` and `[4, 6, 3] -> [2, 3]` and disagree on `[2, 8, -4, 6]`
      (`[2, 4, 3]` vs `[2, 5, 3]`), triggering `AMBIGUOUS_WITNESS_FOUND` with probe `[8]`.
    - Only reaches `UNIQUE_IN_BOUNDED_SPACE` after `[8] -> [4]` is added AND the remaining
      bounded space is completely checked (whereas a tight budget returns `UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED`).
    """
    counter = Wave23WorkCounter()
    prog_bad = ElementaryProgramAST(
        pre_pass='NONE',
        filter_expr='v > 0 and v % 2 == 0',
        map_expr='v - 2 if v > 2 else v',
        reduce_kind='APPEND_ID',
    )
    prog_g1 = ElementaryProgramAST(
        pre_pass='NONE',
        filter_expr='v > 0 and v % 2 == 0',
        map_expr='v // 2 if v > 2 else v',
        reduce_kind='APPEND_ID',
    )
    prog_g2 = ElementaryProgramAST(
        pre_pass='NONE',
        filter_expr='v > 0 and v % 2 == 0',
        map_expr='v - 3 if v > 4 else 2',
        reduce_kind='APPEND_ID',
    )

    # 1. `v - 2 if v > 2 else v` is rejected on `[4, 6, 3] -> [2, 3]`
    assert ElementarySandboxExecutor.execute(prog_bad, [4, 6, 3], counter) == [2, 4]
    assert ElementarySandboxExecutor.execute(prog_bad, [4, 6, 3], counter) != [2, 3]

    # 2. Both g1 and g2 fit `[2, -3, 1] -> [2]` and `[4, 6, 3] -> [2, 3]`, and disagree on `[2, 8, -4, 6]`
    public_two = [([2, -3, 1], [2]), ([4, 6, 3], [2, 3])]
    for x_ex, y_ex in public_two:
        assert ElementarySandboxExecutor.execute(prog_g1, x_ex, counter) == y_ex
        assert ElementarySandboxExecutor.execute(prog_g2, x_ex, counter) == y_ex
    assert ElementarySandboxExecutor.execute(prog_g1, [2, 8, -4, 6], counter) == [2, 4, 3]
    assert ElementarySandboxExecutor.execute(prog_g2, [2, 8, -4, 6], counter) == [2, 5, 3]

    catalog = build_bounded_elementary_catalog(include_conditional_repairs=True)
    rep_amb = run_three_state_witness_search(
        catalog,
        public_two,
        [2, 8, -4, 6],
        counter,
        max_candidate_budget=1200,
    )
    assert rep_amb.status == 'AMBIGUOUS_WITNESS_FOUND'
    assert rep_amb.primary_program == prog_g1
    assert rep_amb.witness_program == prog_g2
    assert rep_amb.primary_query_prediction == [2, 4, 3]
    assert rep_amb.witness_query_prediction == [2, 5, 3]
    assert rep_amb.distinguishing_probe_input == [8]

    # 3. After adding `[8] -> [4]`, if budget expires before exhausting `catalog`, status is `UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED`
    public_three = [([2, -3, 1], [2]), ([4, 6, 3], [2, 3]), ([8], [4])]
    # Put g1 first so it is found immediately, then cap budget at 25 (< len(catalog))
    ordered_with_g1_first = [prog_g1] + [p for p in catalog if p != prog_g1]
    rep_budget_exhausted = run_three_state_witness_search(
        ordered_with_g1_first,
        public_three,
        [2, 8, -4, 6],
        counter,
        max_candidate_budget=25,
    )
    assert rep_budget_exhausted.status == 'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED'
    assert rep_budget_exhausted.bounded_space_exhausted is False

    # 4. Only after `[8] -> [4]` AND complete checking of the remaining bounded space does it reach `UNIQUE_IN_BOUNDED_SPACE`
    rep_unique = run_three_state_witness_search(
        catalog,
        public_three,
        [2, 8, -4, 6],
        counter,
        max_candidate_budget=1200,
    )
    assert rep_unique.status == 'UNIQUE_IN_BOUNDED_SPACE'
    assert rep_unique.bounded_space_exhausted is True
    assert rep_unique.primary_program == prog_g1
    assert rep_unique.primary_query_prediction == [2, 4, 3]


def test_public_alignment_derivation_and_symkan_faithful_export_mps() -> None:
    """Verifies requirement (b):
    Public candidate-filter alignment A(F, O) derives scalar pairs (v_m, u_m) purely from
    public list examples (x_i, y_i) without any oracle, and SymbolicKANResidualInducer
    induces expressions on MPS with `faithful_export=True`.
    """
    counter = Wave23WorkCounter()
    telemetry = NeuralTelemetry()
    public_examples = [([2, -3, 1], [2]), ([4, 6, 3], [2, 3]), ([8], [4])]

    alignments = derive_public_scalar_alignments(public_examples, counter)
    assert len(alignments) >= 1
    pos_even_id = [
        a
        for a in alignments
        if a.filter_expr == 'v > 0 and v % 2 == 0' and a.ordering == 'APPEND_ID'
    ]
    assert len(pos_even_id) == 1
    assert pos_even_id[0].scalar_pairs == [(2, 2), (4, 2), (6, 3), (8, 4)]

    expr_str, kan_rep = SymbolicKANResidualInducer.induce_from_alignment_mps(
        pos_even_id[0], counter, telemetry
    )
    assert expr_str == 'v // 2 if v > 2 else v'
    assert kan_rep.attempted is True
    assert kan_rep.faithful_export is True
    assert kan_rep.hardened_kan_predictions == [2, 2, 3, 4]
    assert kan_rep.exported_ast_predictions == [2, 2, 3, 4]
    assert telemetry.mps_available is True
    assert telemetry.gpu_forward_passes >= 1


def test_all_witness_states_failure_states_and_public_vs_private_mapping_separation() -> None:
    """Verifies requirement (c):
    - All 3 witness states (`AMBIGUOUS_WITNESS_FOUND`, `UNIQUE_IN_BOUNDED_SPACE`, `UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED`)
    - All 3 failure states (`VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS`, `NO_PROGRAM_IN_BOUNDED_GRAMMAR`, `NO_PROGRAM_WITHIN_BUDGET`)
    - `verify_no_compound_loop_boxes` (`<= 7` inner statements, zero compound loop boxes)
    - 3-to-5-step Public Validation vs. Private Assessment mapping separation (`UNIQUE_VALIDATED_MAPPING`, `AMBIGUOUS_VALIDATED_MAPPINGS`, `NO_VALIDATED_MAPPING`)
    - Equal-tool LLM baseline vs. witness-gated agent on Metal GPU.
    """
    t1_tasks, t2_tasks, t3_turns = build_wave23_Tracks_suite()
    assert len(t1_tasks) == 8
    assert len(t2_tasks) == 14
    assert len(t3_turns) == 10

    # Verify `NO_PROGRAM_WITHIN_BUDGET` when 0 programs fit within a tight budget
    c = Wave23WorkCounter()
    cat = build_bounded_elementary_catalog()
    rep_no_prog_budget = run_three_state_witness_search(
        cat,
        [([1, 2, 3], [111, -222, 333, 444])],
        [1, 2, 3],
        c,
        max_candidate_budget=15,
    )
    assert rep_no_prog_budget.status == 'NO_PROGRAM_WITHIN_BUDGET'
    assert rep_no_prog_budget.bounded_space_exhausted is False

    # Verify Track 1 Public Validation vs Private Assessment across both methods
    for method in WAVE23_TRACK1_METHODS:
        cache = {}
        rows1 = [
            InterventionalMappingAcquisitionEngine.evaluate_mapping_and_transfer(
                method, task, 0, validated_cache=cache
            )
            for task in t1_tasks
        ]
        assert all(r.private_assessment_correct for r in rows1)
        verdicts = [r.mapping_verdict for r in rows1]
        assert verdicts.count('UNIQUE_VALIDATED_MAPPING') == 6
        assert verdicts.count('AMBIGUOUS_VALIDATED_MAPPINGS') == 1
        assert verdicts.count('NO_VALIDATED_MAPPING') == 1

    # Verify Track 2 across all 5 methods on seed 0
    for method in WAVE23_TRACK2_METHODS:
        store = AuthoritativeTemplateStore()
        proposer = M4ElementaryStepProposer(seed=0)
        rows2 = [
            solve_wave23_elementary_task(method, task, 0, store=store, proposer=proposer)
            for task in t2_tasks
        ]
        assert all(r.private_correct for r in rows2)
        assert all(r.no_compound_boxes_verified for r in rows2)
        assert all(r.statement_count <= 7 for r in rows2)
        for r in rows2:
            if r.synthesized_source:
                assert verify_no_compound_loop_boxes(r.synthesized_source)
        statuses = {r.witness_status for r in rows2}
        assert 'UNIQUE_IN_BOUNDED_SPACE' in statuses
        assert 'AMBIGUOUS_WITNESS_FOUND' in statuses
        assert 'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED' in statuses
        assert 'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS' in statuses
        assert 'NO_PROGRAM_IN_BOUNDED_GRAMMAR' in statuses

    # Verify Track 3 on Metal GPU (seed 0)
    rows3, meta = run_wave23_llm_dialogue_suite(t3_turns[:4], seeds=(0,))
    assert meta.get('n_gpu_layers') == -1
    nexus_rows = [r for r in rows3 if r.method == 'nexus_witness_gated_agent_mps']
    tool_rows = [r for r in rows3 if r.method == 'tool_equipped_llm_with_skill_cache_mps']
    assert all(r.turn_correct for r in nexus_rows)
    assert any(r.premature_commit_on_ambiguous for r in tool_rows)
