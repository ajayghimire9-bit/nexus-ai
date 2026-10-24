#!/usr/bin/env python3
"""Benchmark runner for Wave 22 (`NEXUS-OMEGA`) across all 3 tracks on Apple Silicon M4 GPU."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from nexus.seed.wave21_imperative_python_synthesizer import TraceDrivenRepoRepairEngine
from nexus.seed.wave22_nexus_omega_engine import (
    WAVE22_HOMOMORPHISM_METHODS,
    WAVE22_IMPERATIVE_METHODS,
    WAVE22_LLM_METHODS,
    WakeSleepCodeEvolver,
    run_wave22_llm_epistemic_suite,
    solve_wave22_homomorphism_task,
    solve_wave22_imperative_task,
    validate_wave22_suite_well_posedness,
)

SEEDS = (0, 1, 2)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_payload_sha256(payload: dict[str, Any]) -> str:
    cloned = dict(payload)
    cloned.pop('payload_sha256', None)
    raw = json.dumps(cloned, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def run_wave22_benchmark() -> dict[str, Any]:
    from nexus.seed.mechanism_wave22_fresh_assessment import (
        WAVE22_FRESH_MANIFEST,
        build_wave22_fresh_assessment_suite,
    )

    t0 = time.perf_counter()
    hom_specs, imp_specs, repo_specs, dlg_specs, track1_seed_ctx = build_wave22_fresh_assessment_suite()

    # Pre-warm a single Wake-Sleep curriculum pass to collect the learned helper library for well-posedness validation
    pre_evolver = WakeSleepCodeEvolver(seed=0)
    for spec in imp_specs:
        solve_wave22_imperative_task('nexus_omega_full_wake_sleep', spec, 0, evolver=pre_evolver)

    well_posedness = validate_wave22_suite_well_posedness(
        hom_specs,
        imp_specs,
        repo_specs,
        dlg_specs,
        track1_context=track1_seed_ctx,
        track2_helpers=pre_evolver.library.active_helpers,
    )
    if not well_posedness['valid']:
        raise RuntimeError(f"Wave 22 fixture well-posedness check failed: {well_posedness['errors']}")

    # ------------------------------------------------------------------
    # Track 1: Partial Homomorphism Discovery with Distractors (72 cells)
    # ------------------------------------------------------------------
    track1_rows: list[dict[str, Any]] = []
    discovered_track1_context = dict(track1_seed_ctx)
    for seed in SEEDS:
        for method in WAVE22_HOMOMORPHISM_METHODS:
            alignment_cache: dict[tuple[str, str], dict[str, Any]] = {}
            for spec in hom_specs:
                res = solve_wave22_homomorphism_task(
                    method, spec, seed, alignment_cache=alignment_cache
                )
                track1_rows.append(asdict(res))
                if (
                    method == 'nexus_omega_sinkhorn_homomorphism'
                    and seed == 0
                    and res.discovered_phi
                    and res.discovered_psi
                ):
                    discovered_track1_context['phi'] = dict(res.discovered_phi)
                    discovered_track1_context['psi'] = dict(res.discovered_psi)

    track1_summary: dict[str, dict[str, Any]] = {}
    for method in WAVE22_HOMOMORPHISM_METHODS:
        m_rows = [r for r in track1_rows if r['method'] == method]
        unique_rows = [r for r in m_rows if not r['task_id'].endswith('_ambiguous')]
        ambig_rows = [r for r in m_rows if r['task_id'].endswith('_ambiguous')]
        track1_summary[method] = {
            'cells': len(m_rows),
            'private_correct': sum(1 for r in m_rows if r['private_correct']),
            'private_accuracy': round(sum(1 for r in m_rows if r['private_correct']) / len(m_rows), 4),
            'unique_private_correct': sum(1 for r in unique_rows if r['private_correct']),
            'unique_cells': len(unique_rows),
            'mapping_exact_matches': sum(1 for r in unique_rows if r['mapping_exact_match']),
            'false_uniques': sum(1 for r in m_rows if r['false_unique']),
            'ambiguous_correctly_declared': sum(1 for r in ambig_rows if r['ambiguous_correctly_declared']),
            'ambiguous_cells': len(ambig_rows),
            'commutator_disambiguation_count': sum(1 for r in m_rows if r['commutator_disambiguation_used']),
            'total_work': sum(int(r['total_work']) for r in m_rows),
            'total_primitive_op_steps': sum(int(r['total_primitive_op_steps']) for r in m_rows),
            'gpu_forward_passes': sum(int(r['gpu_telemetry']['gpu_forward_passes']) for r in m_rows),
            'gpu_online_update_steps': sum(int(r['gpu_telemetry']['gpu_online_update_steps']) for r in m_rows),
            'gpu_wall_ms': round(sum(float(r['gpu_telemetry']['gpu_wall_ms']) for r in m_rows), 3),
        }

    # ------------------------------------------------------------------
    # Track 2: Open-Ended Wake-Sleep Imperative Synthesis + Repo Repair
    # ------------------------------------------------------------------
    track2_rows: list[dict[str, Any]] = []
    track2_evolver_stats: dict[str, dict[str, int]] = {
        m: {'dream_cycles_run': 0, 'dreams_generated': 0, 'dream_hits': 0, 'helpers_learned': 0}
        for m in WAVE22_IMPERATIVE_METHODS
    }
    consolidated_track2_helpers = {}

    for seed in SEEDS:
        for method in WAVE22_IMPERATIVE_METHODS:
            evolver = WakeSleepCodeEvolver(seed=seed)
            for spec in imp_specs:
                res = solve_wave22_imperative_task(method, spec, seed, evolver=evolver)
                track2_rows.append(asdict(res))
            track2_evolver_stats[method]['dream_cycles_run'] += evolver.dream_cycles_run
            track2_evolver_stats[method]['dreams_generated'] += evolver.dreams_generated
            track2_evolver_stats[method]['dream_hits'] += evolver.dream_hits
            track2_evolver_stats[method]['helpers_learned'] += len(evolver.library.active_helpers) + len(
                evolver.library.cold_archive
            )
            if method == 'nexus_omega_full_wake_sleep' and seed == 0:
                consolidated_track2_helpers = dict(evolver.library.active_helpers)
                for h_k, h_v in evolver.library.cold_archive.items():
                    consolidated_track2_helpers.setdefault(h_k, h_v)

    track2_summary: dict[str, dict[str, Any]] = {}
    for method in WAVE22_IMPERATIVE_METHODS:
        m_rows = [r for r in track2_rows if r['method'] == method]
        ambig_rows = [r for r in m_rows if r['task_id'].endswith('_ambiguous')]
        track2_summary[method] = {
            'cells': len(m_rows),
            'private_correct': sum(1 for r in m_rows if r['private_correct']),
            'private_accuracy': round(sum(1 for r in m_rows if r['private_correct']) / len(m_rows), 4),
            'multi_statement_verified': sum(1 for r in m_rows if r['is_multi_statement_verified']),
            'helper_used_count': sum(1 for r in m_rows if r['helper_used']),
            'dream_hit_count': sum(1 for r in m_rows if r['dream_hit']),
            'cold_archive_reactivated_count': sum(1 for r in m_rows if r['cold_archive_reactivated']),
            'false_uniques': sum(1 for r in m_rows if r['false_unique']),
            'ambiguous_correctly_declared': sum(1 for r in ambig_rows if r['ambiguous_correctly_declared']),
            'ambiguous_cells': len(ambig_rows),
            'total_work': sum(int(r['total_work']) for r in m_rows),
            'total_primitive_op_steps': sum(int(r['total_primitive_op_steps']) for r in m_rows),
            'dream_cycles_run': track2_evolver_stats[method]['dream_cycles_run'],
            'dreams_generated': track2_evolver_stats[method]['dreams_generated'],
            'helpers_learned': track2_evolver_stats[method]['helpers_learned'],
            'gpu_forward_passes': sum(int(r['gpu_telemetry']['gpu_forward_passes']) for r in m_rows),
            'gpu_online_update_steps': sum(int(r['gpu_telemetry']['gpu_online_update_steps']) for r in m_rows),
        }

    repo_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        for rspec in repo_specs:
            r_res = TraceDrivenRepoRepairEngine.localize_and_repair_repository(rspec, seed=seed)
            row_dict = asdict(r_res)
            row_dict['all_contracts_passed'] = bool(r_res.public_passed and r_res.private_passed)
            repo_rows.append(row_dict)

    repo_summary = {
        'cells': len(repo_rows),
        'all_contracts_passed_count': sum(1 for r in repo_rows if r['all_contracts_passed']),
        'total_work': sum(int(r['total_work']) for r in repo_rows),
        'total_primitive_op_steps': sum(int(r['total_primitive_op_steps']) for r in repo_rows),
    }

    # ------------------------------------------------------------------
    # Track 3: Grounded Pretrained LLM + Epistemic World Compiler (72 cells)
    # ------------------------------------------------------------------
    dlg_results, llm_runtime_meta = run_wave22_llm_epistemic_suite(
        dlg_specs,
        seeds=SEEDS,
        track1_context=discovered_track1_context,
        track2_helpers=consolidated_track2_helpers,
    )
    track3_rows = [asdict(r) for r in dlg_results]

    track3_summary: dict[str, dict[str, Any]] = {}
    for method in WAVE22_LLM_METHODS:
        m_rows = [r for r in track3_rows if r['method'] == method]
        track3_summary[method] = {
            'cells': len(m_rows),
            'turn_correct': sum(1 for r in m_rows if r['turn_correct']),
            'turn_accuracy': round(sum(1 for r in m_rows if r['turn_correct']) / len(m_rows), 4),
            'hallucinated_claims': sum(1 for r in m_rows if r['hallucinated_claim']),
            'hallucinations_blocked': sum(1 for r in m_rows if r['hallucination_blocked']),
            'false_premise_or_contradiction_complied': sum(
                1 for r in m_rows if r['false_premise_or_contradiction_complied']
            ),
            'premature_guess_on_ambiguous': sum(1 for r in m_rows if r['premature_guess_on_ambiguous']),
            'constraint_violated': sum(1 for r in m_rows if r['constraint_violated']),
            'cross_track_skills_reused': sum(1 for r in m_rows if r['cross_track_skill_reused']),
            'total_work': sum(int(r['total_work']) for r in m_rows),
            'total_primitive_op_steps': sum(int(r['total_primitive_op_steps']) for r in m_rows),
        }

    fresh_path = SRC_ROOT / 'nexus' / 'seed' / 'mechanism_wave22_fresh_assessment.py'
    engine_path = SRC_ROOT / 'nexus' / 'seed' / 'wave22_nexus_omega_engine.py'

    payload: dict[str, Any] = {
        'wave': 'wave22_nexus_omega_wake_sleep_sinkhorn_world_engine',
        'seeds': list(SEEDS),
        'well_posedness_report': well_posedness,
        'file_hashes': {
            'wave22_nexus_omega_engine.py': _sha256_file(engine_path),
            'mechanism_wave22_fresh_assessment.py': _sha256_file(fresh_path),
        },
        'llm_runtime_metadata': llm_runtime_meta,
        'track1_homomorphism': {
            'summary': track1_summary,
            'rows': track1_rows,
        },
        'track2_imperative': {
            'summary': track2_summary,
            'rows': track2_rows,
            'repo_repair_summary': repo_summary,
            'repo_repair_rows': repo_rows,
        },
        'track3_epistemic_world_agent': {
            'summary': track3_summary,
            'rows': track3_rows,
        },
        'wall_seconds': round(time.perf_counter() - t0, 3),
    }
    payload['payload_sha256'] = _canonical_payload_sha256(payload)

    artifacts_dir = REPO_ROOT / 'artifacts'
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    bench_out = artifacts_dir / 'seed_wave22_nexus_omega_benchmark.json'
    manifest_out = artifacts_dir / 'seed_wave22_fresh_manifest.json'

    bench_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    manifest_payload = dict(WAVE22_FRESH_MANIFEST)
    manifest_payload['fresh_assessment_sha256'] = _sha256_file(fresh_path)
    manifest_payload['well_posedness_report'] = well_posedness
    manifest_payload['payload_sha256'] = _canonical_payload_sha256(manifest_payload)
    manifest_out.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    return payload


if __name__ == '__main__':
    report = run_wave22_benchmark()
    t1 = report['track1_homomorphism']['summary']['nexus_omega_sinkhorn_homomorphism']
    t2 = report['track2_imperative']['summary']['nexus_omega_full_wake_sleep']
    t2_wake = report['track2_imperative']['summary']['nexus_wake_only_no_dreaming']
    t3 = report['track3_epistemic_world_agent']['summary']['nexus_omega_epistemic_world_agent_mps']
    print(
        json.dumps(
            {
                'well_posedness_valid': report['well_posedness_report']['valid'],
                'track1_sinkhorn': t1,
                'track2_wake_sleep': t2,
                'track2_wake_only_ablation': t2_wake,
                'track3_omega_agent': t3,
                'payload_sha256': report['payload_sha256'],
            },
            indent=2,
        )
    )
