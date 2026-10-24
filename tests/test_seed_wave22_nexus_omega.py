"""Pre-freeze unit & integration tests for Wave 22 (`NEXUS-OMEGA`) on Apple Silicon M4 GPU."""
from __future__ import annotations

import copy

from nexus.seed.wave22_nexus_omega_engine import (
    WAVE22_HOMOMORPHISM_METHODS,
    WAVE22_IMPERATIVE_METHODS,
    WakeSleepCodeEvolver,
    build_pre_freeze_wave22_dev_suite,
    run_wave22_llm_epistemic_suite,
    solve_wave22_homomorphism_task,
    solve_wave22_imperative_task,
    validate_wave22_suite_well_posedness,
)


def test_sinkhorn_partial_homomorphism_with_distractors_mps() -> None:
    hom_dev, _, _, _, _ = build_pre_freeze_wave22_dev_suite()
    src_env = hom_dev[0]['source_env']
    tgt_env = hom_dev[0]['target_env']
    assert len(src_env.operators) == 6
    assert len(tgt_env.operators) == 9  # 6 true + 3 distractors
    assert len(src_env.guards) == 2
    assert len(tgt_env.guards) == 3     # 2 true + 1 distractor

    by_method = {}
    for method in WAVE22_HOMOMORPHISM_METHODS:
        cache = {}
        rows = [solve_wave22_homomorphism_task(method, spec, 0, alignment_cache=cache) for spec in hom_dev]
        by_method[method] = rows

    sinkhorn_rows = by_method['nexus_omega_sinkhorn_homomorphism']
    assert all(r.private_correct for r in sinkhorn_rows)
    assert all(r.mapping_exact_match for r in sinkhorn_rows)
    assert any(r.commutator_disambiguation_used for r in sinkhorn_rows)
    assert all(r.gpu_telemetry['mps_available'] is True for r in sinkhorn_rows)
    assert sum(r.gpu_telemetry['gpu_forward_passes'] for r in sinkhorn_rows) > 30

    sinkhorn_work = sum(r.total_work for r in sinkhorn_rows)
    bf_work = sum(r.total_work for r in by_method['brute_force_factorial_baseline'])
    scratch_work = sum(r.total_work for r in by_method['unaligned_scratch_enumerator'])
    assert sinkhorn_work < 0.35 * bf_work
    assert sinkhorn_work < 0.15 * scratch_work


def test_wake_sleep_dreaming_beats_wake_only_and_baselines_mps() -> None:
    _, imp_dev, _, _, _ = build_pre_freeze_wave22_dev_suite()

    by_method = {}
    evolvers = {}
    for method in WAVE22_IMPERATIVE_METHODS:
        ev = WakeSleepCodeEvolver(seed=0)
        rows = [solve_wave22_imperative_task(method, spec, 0, evolver=ev) for spec in imp_dev]
        by_method[method] = rows
        evolvers[method] = ev

    omega_rows = by_method['nexus_omega_full_wake_sleep']
    wake_rows = by_method['nexus_wake_only_no_dreaming']
    blind_rows = by_method['blind_ast_statement_enumerator']
    omega_ev = evolvers['nexus_omega_full_wake_sleep']

    assert all(r.private_correct for r in omega_rows)
    assert all(r.is_multi_statement_verified for r in omega_rows)
    assert omega_ev.dream_cycles_run == 1
    assert omega_ev.dreams_generated == 12
    assert sum(1 for r in omega_rows if r.dream_hit) >= 2

    omega_work = sum(r.total_work for r in omega_rows)
    wake_work = sum(r.total_work for r in wake_rows)
    blind_work = sum(r.total_work for r in blind_rows)
    omega_ops = sum(r.total_primitive_op_steps for r in omega_rows)
    wake_ops = sum(r.total_primitive_op_steps for r in wake_rows)

    assert omega_work < wake_work
    assert omega_ops < wake_ops
    assert omega_work < 0.10 * blind_work


def test_epistemic_world_compiler_and_zero_survivor_contradiction_trap_mps() -> None:
    hom_dev, imp_dev, _, dlg_dev, track1_ctx = build_pre_freeze_wave22_dev_suite()
    ev = WakeSleepCodeEvolver(seed=0)
    for spec in imp_dev:
        solve_wave22_imperative_task('nexus_omega_full_wake_sleep', spec, 0, evolver=ev)

    rows, meta = run_wave22_llm_epistemic_suite(
        dlg_dev,
        seeds=(0,),
        track1_context=track1_ctx,
        track2_helpers=ev.library.active_helpers,
    )
    assert str(meta.get('model_sha256', '')).startswith('74a4da8c9fdbcd15')

    raw_rows = [r for r in rows if r.method == 'standalone_pretrained_llm_mps']
    omega_rows = [r for r in rows if r.method == 'nexus_omega_epistemic_world_agent_mps']

    # Verify Theorem 1 fixes the Wave 21 0-survivor contradiction trap
    contradiction_row = next(
        r for r in omega_rows if r.dialogue_id == 'dev_w22_dlg_wave21_contradiction_regression'
    )
    assert contradiction_row.surviving_hypothesis_count == 0
    assert contradiction_row.decision_status == 'REFUSE_CONTRADICTION_OR_FALSE_PREMISE'
    assert contradiction_row.turn_correct is True

    assert all(r.turn_correct for r in omega_rows)
    assert sum(1 for r in omega_rows if r.hallucinated_claim) == 0
    assert sum(1 for r in omega_rows if r.cross_track_skill_reused) >= 1
    assert sum(1 for r in raw_rows if r.hallucinated_claim) >= 2


def test_well_posedness_validator_catches_ill_posed_and_passes_valid() -> None:
    hom_dev, imp_dev, repo_dev, dlg_dev, track1_ctx = build_pre_freeze_wave22_dev_suite()
    ev = WakeSleepCodeEvolver(seed=0)
    for spec in imp_dev:
        solve_wave22_imperative_task('nexus_omega_full_wake_sleep', spec, 0, evolver=ev)

    valid_report = validate_wave22_suite_well_posedness(
        hom_dev,
        imp_dev,
        repo_dev,
        dlg_dev,
        track1_context=track1_ctx,
        track2_helpers=ev.library.active_helpers,
    )
    assert valid_report['valid'] is True
    assert valid_report['errors'] == []

    # Inject a contradictory public example into a unique imperative task and verify validator flags it
    corrupted_imp = copy.deepcopy(imp_dev)
    corrupted_imp[0]['public'] = [([2, -3, 1], [2]), ([4, 6, 3], [2, 3])]
    bad_report = validate_wave22_suite_well_posedness(
        hom_dev,
        corrupted_imp,
        repo_dev,
        dlg_dev,
        track1_context=track1_ctx,
        track2_helpers=ev.library.active_helpers,
    )
    assert bad_report['valid'] is False
    assert any('imp_unique_zero_survivors' in err for err in bad_report['errors'])


def test_repo_repair_and_benchmark_runner_imports() -> None:
    import importlib.util
    from pathlib import Path
    from nexus.seed.wave21_imperative_python_synthesizer import TraceDrivenRepoRepairEngine

    _, _, repo_dev, _, _ = build_pre_freeze_wave22_dev_suite()
    r_res = TraceDrivenRepoRepairEngine.localize_and_repair_repository(repo_dev[0], seed=0)
    assert r_res.public_passed is True
    assert r_res.private_passed is True
    assert 'def unique_frequency_squares' in r_res.synthesized_replacement_source

    repo_root = Path(__file__).resolve().parents[1]
    for script_rel in ('scripts/run_wave22_nexus_omega_benchmark.py', 'scripts/verify_wave22_nexus_omega.py'):
        spec = importlib.util.spec_from_file_location('mod_check', repo_root / script_rel)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

