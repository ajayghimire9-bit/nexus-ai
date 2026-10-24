"""Pre-freeze Unit Tests for Wave 21 Real Mechanisms (Modules 1, 2, and 3)."""
from __future__ import annotations

import ast
import pytest

from nexus.seed import wave21_grounded_llm_epistemic_gate as m3
from nexus.seed import wave21_imperative_python_synthesizer as m2
from nexus.seed import wave21_unaligned_homomorphism_learner as m1


def test_module1_rejects_non_anonymous_target_names() -> None:
    bad_env = m1.AnonymousDomainEnvironment(
        domain_id='bad_target',
        probe_states=(1, 2),
        operators={'GUARD_PARITY_TRANSFORM': lambda x: x},
        guards={'anon_guard_0': lambda x: True},
        is_anonymous_target=True,
    )
    with pytest.raises(ValueError, match='violates anonymous naming'):
        bad_env.validate()


def test_module1_unaligned_homomorphism_discovery_and_efficiency() -> None:
    suite = m1.build_pre_freeze_homomorphism_dev_suite()
    totals: dict[str, dict[str, int]] = {}
    for method in m1.WAVE21_HOMOMORPHISM_METHODS:
        fp = None
        cache: dict[tuple[str, str], dict] = {}
        corr = 0
        work = 0
        exact_phi = 0
        comm_used = 0
        for spec in suite:
            res, fp = m1.solve_unaligned_cross_domain_task(
                method, spec, 0, cached_source_fp=fp, alignment_cache=cache
            )
            corr += int(res.private_correct)
            work += res.total_work
            exact_phi += int(res.mapping_exact_match)
            comm_used += int(res.commutator_disambiguation_used)
            if method == 'nexus_unaligned_homomorphism_full':
                assert res.gpu_telemetry['mps_available'] is True
                assert res.gpu_telemetry['gpu_forward_passes'] >= 1
                assert res.false_unique is False
        totals[method] = {
            'correct': corr,
            'work': work,
            'exact_phi': exact_phi,
            'comm_used': comm_used,
        }

    full = totals['nexus_unaligned_homomorphism_full']
    scratch = totals['unaligned_scratch_enumerator']
    hand = totals['hand_tagged_schema_baseline']
    rand = totals['random_operator_mapping']

    assert full['correct'] == len(suite)
    assert full['exact_phi'] == len(suite)
    assert full['comm_used'] >= 1
    assert full['work'] < scratch['work']
    assert full['work'] < hand['work']
    assert full['correct'] > rand['correct']


def test_module2_rejects_one_line_templates_and_verifies_multi_statement() -> None:
    one_liner = ast.parse('def solve(x):\n    return [v * v for v in x if v > 0]\n')
    assert m2.verify_multi_statement_imperative_ast(one_liner) is False

    multi_stmt = ast.parse(
        'def solve(x):\n'
        '    acc = []\n'
        '    for item in x:\n'
        '        if item > 0:\n'
        '            acc.append(item * item)\n'
        '    return acc\n'
    )
    assert m2.verify_multi_statement_imperative_ast(multi_stmt) is True


def test_module2_execution_guided_imperative_synthesis_and_repo_repair() -> None:
    tasks, repos = m2.build_pre_freeze_imperative_dev_suite()
    totals: dict[str, dict[str, int]] = {}
    for method in m2.WAVE21_IMPERATIVE_METHODS:
        scorer = m2.M4ExecutionTraceScorer(seed=0)
        lib = m2.ImperativeHelperLibrary()
        corr = 0
        work = 0
        steps = 0
        for spec in tasks:
            res = m2.solve_imperative_python_task(method, spec, 0, scorer=scorer, library=lib)
            corr += int(res.private_correct)
            work += res.total_work
            steps += res.total_primitive_op_steps
            if res.status == 'unique':
                assert res.is_multi_statement_verified is True
                assert res.statement_count >= 3
        totals[method] = {
            'correct': corr,
            'work': work,
            'steps': steps,
            'helpers_invented': lib.helpers_invented,
        }

    full = totals['nexus_m4_execution_guided_imperative_full']
    blind = totals['blind_ast_statement_enumerator']
    whole = totals['nexus_whole_function_macro_only']
    no_trace = totals['nexus_imperative_without_trace_guidance']

    assert full['correct'] == len(tasks)
    assert full['helpers_invented'] >= 1
    assert full['work'] < blind['work']
    assert full['work'] < whole['work']
    assert full['work'] < no_trace['work']
    assert full['steps'] < whole['steps']

    for rspec in repos:
        rres = m2.TraceDrivenRepoRepairEngine.localize_and_repair_repository(rspec, seed=0)
        assert rres.localized_file == 'pkg/reducer.py'
        assert rres.localized_function == 'unique_frequency_squares'
        assert rres.public_passed is True
        assert rres.private_passed is True
        assert m2.verify_multi_statement_imperative_ast(ast.parse(rres.synthesized_replacement_source))


def test_module3_real_pretrained_llm_mps_vs_epistemic_gate() -> None:
    dev_turns = m3.build_pre_freeze_llm_epistemic_dev_suite()
    results, meta = m3.run_grounded_llm_dialogue_suite(dev_turns, seeds=(0,))

    assert meta['metal'] is True
    assert int(meta['n_gpu_layers']) == -1
    assert meta['model_file'] == 'qwen2.5-0.5b-instruct-q4_k_m.gguf'

    raw_rows = [r for r in results if r.method == 'standalone_pretrained_llm_mps']
    gated_rows = [r for r in results if r.method == 'nexus_epistemic_gated_llm_mps']

    assert len(raw_rows) == 4
    assert len(gated_rows) == 4

    assert sum(int(r.hallucinated_claim) for r in raw_rows) >= 2
    assert all(r.turn_correct for r in gated_rows)
    assert all(not r.hallucinated_claim for r in gated_rows)
    assert sum(int(r.hallucination_blocked) for r in gated_rows) >= 2
    assert all(r.llm_telemetry['inference_ran'] is True for r in gated_rows)
    assert all(r.mps_telemetry['mps_available'] is True for r in gated_rows)
