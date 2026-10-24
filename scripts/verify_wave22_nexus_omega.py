#!/usr/bin/env python3
"""Standalone forensic & scientific verifier for Wave 22 (`NEXUS-OMEGA`)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BRANCH_NAME = 'cursor/seed-wave22-nexus-omega-wake-sleep-sinkhorn-world-engine'

PHASE1_FILES = (
    'src/nexus/seed/wave22_nexus_omega_engine.py',
    'scripts/run_wave22_nexus_omega_benchmark.py',
    'scripts/verify_wave22_nexus_omega.py',
    'tests/test_seed_wave22_nexus_omega.py',
)


def _canonical_payload_sha256(payload: dict[str, Any]) -> str:
    cloned = dict(payload)
    cloned.pop('payload_sha256', None)
    raw = json.dumps(cloned, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['git', *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _check_branch_reflog_no_amend() -> tuple[bool, list[str]]:
    """Verifies git reflog -n 50 has zero `commit (amend)`, `rebase`, or `reset` entries on Wave 22 branch."""
    proc = _run_git(['reflog', '-n', '50'])
    if proc.returncode != 0:
        return False, ['reflog_command_failed']

    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    branch_entries: list[str] = []
    for ln in lines:
        branch_entries.append(ln)
        if f'checkout: moving from' in ln and f'to {BRANCH_NAME}' in ln:
            break

    violations: list[str] = []
    for entry in branch_entries:
        lower = entry.lower()
        if 'commit (amend)' in lower or 'rebase' in lower or 'reset:' in lower:
            violations.append(entry)
    return (len(violations) == 0), violations


def verify_wave22(freeze_commit: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    bench_path = REPO_ROOT / 'artifacts' / 'seed_wave22_nexus_omega_benchmark.json'
    manifest_path = REPO_ROOT / 'artifacts' / 'seed_wave22_fresh_manifest.json'

    if not bench_path.is_file():
        raise FileNotFoundError(f'Missing benchmark artifact: {bench_path}')
    if not manifest_path.is_file():
        raise FileNotFoundError(f'Missing manifest artifact: {manifest_path}')

    bench = json.loads(bench_path.read_text(encoding='utf-8'))
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

    if bench.get('payload_sha256') != _canonical_payload_sha256(bench):
        errors.append('benchmark_payload_sha256_mismatch')
    if manifest.get('payload_sha256') != _canonical_payload_sha256(manifest):
        errors.append('manifest_payload_sha256_mismatch')

    # Check well-posedness report
    wp = bench.get('well_posedness_report', {})
    if not wp.get('valid', False) or wp.get('errors'):
        errors.append(f"well_posedness_invalid:{wp.get('errors')}")

    # Check reflog no-amend rule
    zero_amend_on_branch, reflog_violations = _check_branch_reflog_no_amend()
    if not zero_amend_on_branch:
        errors.append(f'git_reflog_history_rewrite_detected:{reflog_violations}')

    # Check two-commit physical separation
    fresh_absent_at_freeze = False
    phase1_zero_diff = False
    if freeze_commit:
        cat_proc = _run_git(
            ['cat-file', '-e', f'{freeze_commit}:src/nexus/seed/mechanism_wave22_fresh_assessment.py']
        )
        fresh_absent_at_freeze = cat_proc.returncode != 0
        if not fresh_absent_at_freeze:
            errors.append('fresh_assessment_existed_at_freeze_commit')

        diff_proc = _run_git(['diff', freeze_commit, 'HEAD', '--', *PHASE1_FILES])
        phase1_zero_diff = (diff_proc.returncode == 0) and (diff_proc.stdout.strip() == '')
        if not phase1_zero_diff:
            errors.append('phase1_files_modified_after_freeze_commit')

    # ------------------------------------------------------------------
    # Track 1 Verification (72 cells)
    # ------------------------------------------------------------------
    t1_rows = bench['track1_homomorphism']['rows']
    t1_sum = bench['track1_homomorphism']['summary']
    if len(t1_rows) != 72:
        errors.append(f'track1_expected_72_rows_got_{len(t1_rows)}')

    t1_omega = t1_sum['nexus_omega_sinkhorn_homomorphism']
    t1_bf = t1_sum['brute_force_factorial_baseline']
    t1_scratch = t1_sum['unaligned_scratch_enumerator']
    t1_rand = t1_sum['random_partial_mapping']

    if t1_omega['unique_private_correct'] != 15 or t1_omega['mapping_exact_matches'] != 15:
        errors.append(f"track1_sinkhorn_unique_incomplete:{t1_omega}")
    if t1_omega['ambiguous_correctly_declared'] != 3 or t1_omega['false_uniques'] != 0:
        errors.append(f"track1_sinkhorn_ambiguity_or_false_unique_failure:{t1_omega}")
    if t1_omega['commutator_disambiguation_count'] < 3:
        errors.append('track1_sinkhorn_missing_commutator_disambiguation')
    if t1_omega['gpu_forward_passes'] <= 0 or t1_omega['gpu_online_update_steps'] <= 0:
        errors.append('track1_sinkhorn_missing_mps_telemetry')
    if t1_omega['total_work'] > 0.25 * t1_bf['total_work']:
        errors.append(f"track1_sinkhorn_work_not_75pct_below_brute_force:{t1_omega['total_work']}_vs_{t1_bf['total_work']}")
    if t1_omega['total_work'] > 0.25 * t1_scratch['total_work']:
        errors.append(f"track1_sinkhorn_work_not_75pct_below_scratch:{t1_omega['total_work']}_vs_{t1_scratch['total_work']}")
    if t1_omega['private_correct'] <= t1_rand['private_correct']:
        errors.append('track1_sinkhorn_did_not_beat_random')

    # ------------------------------------------------------------------
    # Track 2 Verification (216 imperative cells + 9 repo cells)
    # ------------------------------------------------------------------
    t2_rows = bench['track2_imperative']['rows']
    t2_sum = bench['track2_imperative']['summary']
    repo_rows = bench['track2_imperative']['repo_repair_rows']
    repo_sum = bench['track2_imperative']['repo_repair_summary']

    if len(t2_rows) != 216:
        errors.append(f'track2_expected_216_rows_got_{len(t2_rows)}')
    if len(repo_rows) != 9 or repo_sum['all_contracts_passed_count'] != 9:
        errors.append(f'track2_repo_repair_failed:{repo_sum}')

    t2_omega = t2_sum['nexus_omega_full_wake_sleep']
    t2_wake = t2_sum['nexus_wake_only_no_dreaming']
    t2_blind = t2_sum['blind_ast_statement_enumerator']
    t2_macro = t2_sum['nexus_whole_function_macro_only']
    t2_notrace = t2_sum['nexus_imperative_without_trace_guidance']

    if t2_omega['private_correct'] != 36 or t2_omega['false_uniques'] != 0:
        errors.append(f"track2_omega_accuracy_or_false_unique_failure:{t2_omega}")
    if t2_omega['ambiguous_correctly_declared'] != 3:
        errors.append(f"track2_omega_ambiguity_failure:{t2_omega}")
    if t2_omega['dream_cycles_run'] < 3 or t2_omega['dreams_generated'] < 36 or t2_omega['dream_hit_count'] < 6:
        errors.append(f"track2_omega_dreaming_inactive:{t2_omega}")
    if t2_omega['cold_archive_reactivated_count'] < 3:
        errors.append(f"track2_omega_cold_archive_reactivation_missing:{t2_omega}")
    if not (
        t2_omega['total_work'] < t2_wake['total_work']
        and t2_omega['total_primitive_op_steps'] < t2_wake['total_primitive_op_steps']
    ):
        errors.append(
            f"track2_wake_sleep_did_not_beat_wake_only_ablation:{t2_omega['total_work']}_vs_{t2_wake['total_work']}"
        )
    if t2_omega['total_work'] > 0.40 * t2_blind['total_work']:
        errors.append('track2_omega_work_not_60pct_below_blind')
    if t2_omega['total_work'] > 0.40 * t2_macro['total_work']:
        errors.append('track2_omega_work_not_60pct_below_macro_only')
    if t2_omega['total_work'] >= t2_notrace['total_work']:
        errors.append('track2_omega_did_not_beat_without_trace_guidance')

    # ------------------------------------------------------------------
    # Track 3 Verification (72 dialogue cells on Real Metal GPU LLM)
    # ------------------------------------------------------------------
    t3_rows = bench['track3_epistemic_world_agent']['rows']
    t3_sum = bench['track3_epistemic_world_agent']['summary']
    if len(t3_rows) != 72:
        errors.append(f'track3_expected_72_rows_got_{len(t3_rows)}')

    for r in t3_rows:
        tel = r['llm_telemetry']
        if not tel.get('inference_ran') or int(tel.get('n_gpu_layers', 0)) != -1:
            errors.append(f"track3_missing_metal_gpu_inference:{r['dialogue_id']}:t{r['turn_index']}")
            break
        if not str(tel.get('model_sha256', '')).startswith('74a4da8c9fdbcd15'):
            errors.append('track3_unexpected_model_sha256')
            break

    t3_raw = t3_sum['standalone_pretrained_llm_mps']
    t3_omega = t3_sum['nexus_omega_epistemic_world_agent_mps']

    if t3_raw['hallucinated_claims'] < 9:
        errors.append(f"track3_raw_llm_insufficient_hallucinations:{t3_raw['hallucinated_claims']}")
    if (
        t3_omega['turn_correct'] != 36
        or t3_omega['hallucinated_claims'] != 0
        or t3_omega['false_premise_or_contradiction_complied'] != 0
        or t3_omega['premature_guess_on_ambiguous'] != 0
        or t3_omega['constraint_violated'] != 0
    ):
        errors.append(f'track3_omega_epistemic_failure:{t3_omega}')
    if t3_omega['cross_track_skills_reused'] < 6:
        errors.append(f"track3_omega_insufficient_cross_track_reuse:{t3_omega['cross_track_skills_reused']}")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'freeze_commit': freeze_commit,
        'zero_amend_on_branch': zero_amend_on_branch,
        'fresh_absent_at_freeze': fresh_absent_at_freeze,
        'phase1_zero_diff': phase1_zero_diff,
        'well_posedness_valid': wp.get('valid', False),
        'track1_cells': len(t1_rows),
        'track2_cells': len(t2_rows),
        'track2_repo_cells': len(repo_rows),
        'track3_cells': len(t3_rows),
        'track1_sinkhorn_summary': t1_omega,
        'track2_wake_sleep_summary': t2_omega,
        'track2_wake_only_ablation_summary': t2_wake,
        'track3_omega_summary': t3_omega,
        'track3_raw_llm_summary': t3_raw,
        'benchmark_payload_sha256': bench.get('payload_sha256'),
        'manifest_payload_sha256': manifest.get('payload_sha256'),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-commit', type=str, default=None, help='Commit 1 SHA for physical separation check')
    args = parser.parse_args()
    res = verify_wave22(freeze_commit=args.freeze_commit)
    print(json.dumps(res, indent=2))
    return 0 if res['valid'] else 1


if __name__ == '__main__':
    sys.exit(main())
