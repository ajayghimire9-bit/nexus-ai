"""Wave 21 Single-Shot Blind Benchmark Runner across all 3 Real Mechanisms.

Evaluates the unseen Phase-2 holdout suite (`src/nexus/seed/mechanism_wave21_fresh_assessment.py`,
which must not exist before Commit 1) across seeds (0, 1, 2) on:
1. Track 1 (`unaligned_homomorphism`):
   - `random_operator_mapping`
   - `hand_tagged_schema_baseline`
   - `unaligned_scratch_enumerator`
   - `nexus_unaligned_homomorphism_full`
2. Track 2 (`imperative_python_and_repo_repair`):
   - `standalone_m4_neural_trace_baseline`
   - `blind_ast_statement_enumerator`
   - `nexus_whole_function_macro_only`
   - `nexus_imperative_without_trace_guidance`
   - `nexus_m4_execution_guided_imperative_full`
   Plus multi-file repository runtime trace localization & multi-statement repair (`w21f_repo_*`).
3. Track 3 (`grounded_llm_epistemic_gate`):
   - `standalone_pretrained_llm_mps` (real Qwen2.5-0.5B-Instruct on Apple Silicon GPU)
   - `nexus_epistemic_gated_llm_mps` (Qwen2.5-0.5B-Instruct gated by NEXUS Symbolic & Execution Verifier)
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nexus.seed.capability_evidence import digest
from nexus.seed import wave21_grounded_llm_epistemic_gate as m3
from nexus.seed import wave21_imperative_python_synthesizer as m2
from nexus.seed import wave21_unaligned_homomorphism_learner as m1

SEEDS: tuple[int, ...] = (0, 1, 2)


def _serialize_homomorphism_row(res: m1.UnalignedHomomorphismResult) -> dict[str, Any]:
    return {
        'method': res.method,
        'task_id': res.task_id,
        'seed': res.seed,
        'status': res.status,
        'discovered_phi': dict(res.discovered_phi),
        'discovered_psi': dict(res.discovered_psi),
        'distortion': res.distortion,
        'commutator_disambiguation_used': res.commutator_disambiguation_used,
        'translated_program_ast': res.translated_program_ast,
        'mapping_exact_match': res.mapping_exact_match,
        'private_correct': res.private_correct,
        'false_unique': res.false_unique,
        'ambiguous_correctly_declared': res.ambiguous_correctly_declared,
        'total_work': res.total_work,
        'total_primitive_op_steps': res.total_primitive_op_steps,
        'work_breakdown': dict(res.work_breakdown),
        'gpu_telemetry': dict(res.gpu_telemetry),
    }


def run_benchmark(
    homomorphism_specs: list[dict[str, Any]],
    imperative_specs: list[dict[str, Any]],
    repo_specs: list[dict[str, Any]],
    dialogue_specs: list[dict[str, Any]],
    *,
    seeds: tuple[int, ...] = SEEDS,
) -> dict[str, Any]:
    t0 = time.perf_counter()

    # ------------------------------------------------------------------
    # Track 1: Unaligned Cross-Domain Homomorphism Discovery
    # ------------------------------------------------------------------
    track1_rows: list[dict[str, Any]] = []
    track1_totals: dict[str, dict[str, int]] = {}
    for method in m1.WAVE21_HOMOMORPHISM_METHODS:
        track1_totals[method] = {
            'n': 0,
            'private_correct': 0,
            'mapping_exact_match': 0,
            'false_unique': 0,
            'ambiguous_correctly_declared': 0,
            'commutator_disambiguation_used': 0,
            'total_work': 0,
            'total_primitive_op_steps': 0,
        }
        for seed in seeds:
            cached_fp = None
            align_cache: dict[tuple[str, str], dict[str, Any]] = {}
            for spec in homomorphism_specs:
                res, cached_fp = m1.solve_unaligned_cross_domain_task(
                    method,
                    spec,
                    seed,
                    cached_source_fp=cached_fp,
                    alignment_cache=align_cache,
                )
                row = _serialize_homomorphism_row(res)
                track1_rows.append(row)
                tot = track1_totals[method]
                tot['n'] += 1
                tot['private_correct'] += int(res.private_correct)
                tot['mapping_exact_match'] += int(res.mapping_exact_match)
                tot['false_unique'] += int(res.false_unique)
                tot['ambiguous_correctly_declared'] += int(res.ambiguous_correctly_declared)
                tot['commutator_disambiguation_used'] += int(res.commutator_disambiguation_used)
                tot['total_work'] += int(res.total_work)
                tot['total_primitive_op_steps'] += int(res.total_primitive_op_steps)

    # ------------------------------------------------------------------
    # Track 2: Execution-Guided Multi-Statement Imperative Synthesis & Repo Repair
    # ------------------------------------------------------------------
    track2_rows: list[dict[str, Any]] = []
    track2_totals: dict[str, dict[str, int]] = {}
    for method in m2.WAVE21_IMPERATIVE_METHODS:
        track2_totals[method] = {
            'n': 0,
            'private_correct': 0,
            'multi_statement_verified': 0,
            'helpers_invented': 0,
            'helpers_reused': 0,
            'cold_archive_reactivated': 0,
            'false_unique': 0,
            'ambiguous_correctly_declared': 0,
            'total_work': 0,
            'total_primitive_op_steps': 0,
        }
        for seed in seeds:
            scorer = m2.M4ExecutionTraceScorer(seed=seed)
            library = m2.ImperativeHelperLibrary()
            for spec in imperative_specs:
                res = m2.solve_imperative_python_task(
                    method, spec, seed, scorer=scorer, library=library
                )
                row = asdict(res)
                track2_rows.append(row)
                tot = track2_totals[method]
                tot['n'] += 1
                tot['private_correct'] += int(res.private_correct)
                tot['multi_statement_verified'] += int(res.is_multi_statement_verified)
                tot['cold_archive_reactivated'] += int(res.cold_archive_reactivated)
                tot['false_unique'] += int(res.false_unique)
                tot['ambiguous_correctly_declared'] += int(res.ambiguous_correctly_declared)
                tot['total_work'] += int(res.total_work)
                tot['total_primitive_op_steps'] += int(res.total_primitive_op_steps)
            track2_totals[method]['helpers_invented'] += int(library.helpers_invented)
            track2_totals[method]['helpers_reused'] += int(library.helpers_reused)

    repo_repair_rows: list[dict[str, Any]] = []
    repo_repair_totals = {
        'n': 0,
        'public_passed': 0,
        'private_passed': 0,
        'total_work': 0,
        'total_primitive_op_steps': 0,
    }
    for seed in seeds:
        for rspec in repo_specs:
            rres = m2.TraceDrivenRepoRepairEngine.localize_and_repair_repository(rspec, seed=seed)
            rrow = asdict(rres)
            rrow['seed'] = seed
            repo_repair_rows.append(rrow)
            repo_repair_totals['n'] += 1
            repo_repair_totals['public_passed'] += int(rres.public_passed)
            repo_repair_totals['private_passed'] += int(rres.private_passed)
            repo_repair_totals['total_work'] += int(rres.total_work)
            repo_repair_totals['total_primitive_op_steps'] += int(rres.total_primitive_op_steps)

    # ------------------------------------------------------------------
    # Track 3: Real Pretrained LLM on M4 GPU vs NEXUS Epistemic Gate
    # ------------------------------------------------------------------
    llm_turn_results, llm_runtime_meta = m3.run_grounded_llm_dialogue_suite(
        dialogue_specs, seeds=seeds, max_tokens=72
    )
    track3_rows = [asdict(r) for r in llm_turn_results]
    track3_totals: dict[str, dict[str, int]] = {}
    for method in m3.WAVE21_LLM_METHODS:
        track3_totals[method] = {
            'n': 0,
            'turn_correct': 0,
            'hallucinated_claims': 0,
            'hallucinations_blocked': 0,
            'false_premise_complied': 0,
            'premature_guess_on_ambiguous': 0,
            'constraint_violated': 0,
            'total_work': 0,
            'total_primitive_op_steps': 0,
        }
    for r in llm_turn_results:
        tot = track3_totals[r.method]
        tot['n'] += 1
        tot['turn_correct'] += int(r.turn_correct)
        tot['hallucinated_claims'] += int(r.hallucinated_claim)
        tot['hallucinations_blocked'] += int(r.hallucination_blocked)
        tot['false_premise_complied'] += int(r.false_premise_complied)
        tot['premature_guess_on_ambiguous'] += int(r.premature_guess_on_ambiguous)
        tot['constraint_violated'] += int(r.constraint_violated)
        tot['total_work'] += int(r.total_work)
        tot['total_primitive_op_steps'] += int(r.total_primitive_op_steps)

    # ------------------------------------------------------------------
    # Gate Summary
    # ------------------------------------------------------------------
    t1_full = track1_totals['nexus_unaligned_homomorphism_full']
    t1_scratch = track1_totals['unaligned_scratch_enumerator']
    t2_full = track2_totals['nexus_m4_execution_guided_imperative_full']
    t2_blind = track2_totals['blind_ast_statement_enumerator']
    t2_whole = track2_totals['nexus_whole_function_macro_only']
    t3_raw = track3_totals['standalone_pretrained_llm_mps']
    t3_gated = track3_totals['nexus_epistemic_gated_llm_mps']

    gates = {
        'track1_homomorphism_100pct_accuracy': t1_full['private_correct'] == t1_full['n'],
        'track1_homomorphism_zero_false_unique': t1_full['false_unique'] == 0,
        'track1_homomorphism_beats_scratch_work': t1_full['total_work'] < t1_scratch['total_work'],
        'track1_commutator_disambiguation_demonstrated': t1_full['commutator_disambiguation_used'] > 0,
        'track2_imperative_100pct_accuracy': t2_full['private_correct'] == t2_full['n'],
        'track2_imperative_zero_false_unique': t2_full['false_unique'] == 0,
        'track2_imperative_beats_blind_and_whole_work': (
            t2_full['total_work'] < t2_blind['total_work']
            and t2_full['total_work'] < t2_whole['total_work']
            and t2_full['total_primitive_op_steps'] < t2_whole['total_primitive_op_steps']
        ),
        'track2_repo_repair_100pct': repo_repair_totals['private_passed'] == repo_repair_totals['n'],
        'track3_real_llm_executed_on_metal_gpu': (
            bool(llm_runtime_meta.get('metal'))
            and int(llm_runtime_meta.get('n_gpu_layers', 0)) == -1
        ),
        'track3_standalone_llm_exhibits_real_hallucinations': t3_raw['hallucinated_claims'] > 0,
        'track3_epistemic_gate_blocks_hallucinations_to_zero': (
            t3_gated['hallucinated_claims'] == 0
            and t3_gated['hallucinations_blocked'] > 0
            and t3_gated['turn_correct'] == t3_gated['n']
        ),
    }

    payload: dict[str, Any] = {
        'kind': 'seed_wave21_real_audit_benchmark',
        'complete': True,
        'seeds': list(seeds),
        'wall_s': round(time.perf_counter() - t0, 4),
        'llm_runtime_metadata': llm_runtime_meta,
        'track1_homomorphism_rows': track1_rows,
        'track2_imperative_rows': track2_rows,
        'track2_repo_repair_rows': repo_repair_rows,
        'track3_llm_epistemic_rows': track3_rows,
        'totals': {
            'track1_homomorphism': track1_totals,
            'track2_imperative': track2_totals,
            'track2_repo_repair': repo_repair_totals,
            'track3_llm_epistemic': track3_totals,
        },
        'gates': gates,
    }
    payload['hash'] = digest(
        {
            k: payload[k]
            for k in (
                'kind',
                'track1_homomorphism_rows',
                'track2_imperative_rows',
                'track2_repo_repair_rows',
                'track3_llm_epistemic_rows',
                'totals',
                'gates',
            )
        }
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--out',
        type=Path,
        default=ROOT / 'artifacts' / 'seed_wave21_real_audit_benchmark.json',
    )
    parser.add_argument(
        '--manifest-out',
        type=Path,
        default=ROOT / 'artifacts' / 'seed_wave21_fresh_manifest.json',
    )
    args = parser.parse_args()

    from nexus.seed import mechanism_wave21_fresh_assessment as fresh

    hom_specs, imp_specs, repo_specs, dlg_specs = fresh.build_wave21_fresh_assessment_suite()
    manifest = fresh.export_wave21_fresh_manifest(hom_specs, imp_specs, repo_specs, dlg_specs)
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    payload = run_benchmark(hom_specs, imp_specs, repo_specs, dlg_specs, seeds=SEEDS)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'hash': payload['hash'], 'gates': payload['gates'], 'wall_s': payload['wall_s']}, indent=2))


if __name__ == '__main__':
    main()
