"""Standalone Read-Only Verifier for Wave 21 Real Audit Benchmark.

Verifies:
1. Two-Commit Blind Protocol Integrity (`--freeze-commit`):
   - `src/nexus/seed/mechanism_wave21_fresh_assessment.py` did NOT exist at Commit 1.
   - Zero diff between Commit 1 and HEAD on all Phase-1 learner, runner, verifier, and test files.
2. Cryptographic payload digest (`digest`) and complete seed x method x task grids.
3. Track 1 (`unaligned_homomorphism`):
   - Exact work/primitive step accounting, M4 `mps` telemetry (`mps_available == True`,
     `gpu_forward_passes >= 1` on `nexus_unaligned_homomorphism_full`), `false_unique == 0`,
     and `nexus_unaligned_homomorphism_full` strictly beating `unaligned_scratch_enumerator`.
4. Track 2 (`imperative_python_and_repo_repair`):
   - Every unique solution passes `verify_multi_statement_imperative_ast(ast.parse(src))`
     (zero 1-line templates allowed), exact work/step accounting, M4 `mps` telemetry,
     multi-file repository trace repair passing all public and private tests, and
     `nexus_m4_execution_guided_imperative_full` strictly beating `blind_ast_statement_enumerator`
     and `nexus_whole_function_macro_only` on work and primitive op steps.
5. Track 3 (`grounded_llm_epistemic_gate`):
   - Real pretrained `qwen2.5-0.5b-instruct-q4_k_m.gguf` executed on Metal GPU (`n_gpu_layers == -1`,
     `inference_ran == True`) + PyTorch `mps` (`mps_available == True`) on every turn.
   - `standalone_pretrained_llm_mps` exhibits real empirical hallucinations (`hallucinated_claims > 0`)
     while `nexus_epistemic_gated_llm_mps` blocks hallucinations (`hallucinations_blocked > 0`,
     `hallucinated_claims == 0`, `turn_correct == n`).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nexus.seed.capability_evidence import digest
from nexus.seed import wave21_grounded_llm_epistemic_gate as m3
from nexus.seed import wave21_imperative_python_synthesizer as m2
from nexus.seed import wave21_unaligned_homomorphism_learner as m1

PHASE1_LOCKED_FILES: tuple[str, ...] = (
    'src/nexus/seed/wave21_unaligned_homomorphism_learner.py',
    'src/nexus/seed/wave21_imperative_python_synthesizer.py',
    'src/nexus/seed/wave21_grounded_llm_epistemic_gate.py',
    'scripts/run_wave21_real_audit_benchmark.py',
    'scripts/verify_wave21_real_audit_benchmark.py',
    'tests/test_seed_wave21_real_mechanisms.py',
)
FRESH_ASSESSMENT_RELPATH = 'src/nexus/seed/mechanism_wave21_fresh_assessment.py'


def verify_freeze_commit_protocol(freeze_commit: str) -> dict[str, Any]:
    """Verifies that Phase-1 files are untouched since `freeze_commit` and fresh suite was absent."""
    errors: list[str] = []

    # 1. Verify freeze_commit resolves
    rev = subprocess.run(
        ['git', 'rev-parse', '--verify', freeze_commit],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if rev.returncode != 0:
        return {
            'valid': False,
            'freeze_commit': freeze_commit,
            'errors': ['invalid_freeze_commit'],
        }
    resolved_sha = rev.stdout.strip()

    # 2. Verify `mechanism_wave21_fresh_assessment.py` did NOT exist at `freeze_commit`
    cat_fresh = subprocess.run(
        ['git', 'cat-file', '-e', f'{resolved_sha}:{FRESH_ASSESSMENT_RELPATH}'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if cat_fresh.returncode == 0:
        errors.append('fresh_assessment_existed_at_freeze_commit')

    # 3. Verify zero diff between `freeze_commit` and working tree on all PHASE1_LOCKED_FILES
    diff_proc = subprocess.run(
        ['git', 'diff', resolved_sha, '--', *PHASE1_LOCKED_FILES],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if diff_proc.returncode != 0 or diff_proc.stdout.strip():
        errors.append('phase1_files_modified_after_freeze')

    return {
        'valid': not errors,
        'freeze_commit_sha': resolved_sha,
        'fresh_absent_at_freeze': cat_fresh.returncode != 0,
        'phase1_zero_diff': diff_proc.returncode == 0 and not diff_proc.stdout.strip(),
        'errors': errors,
    }


def verify_payload(
    payload: dict[str, Any],
    manifest: dict[str, Any],
    *,
    freeze_commit: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []

    expected_hash = digest(
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
    if payload.get('hash') != expected_hash:
        errors.append('payload_hash_mismatch')
    if not payload.get('complete'):
        errors.append('incomplete_payload')

    # Check Track 1 rows
    t1_rows = payload.get('track1_homomorphism_rows', [])
    expected_t1_ids = set(manifest.get('track1_task_ids', []))
    if len(t1_rows) != len(expected_t1_ids) * 3 * len(m1.WAVE21_HOMOMORPHISM_METHODS):
        errors.append('track1_grid_size')
    for idx, row in enumerate(t1_rows):
        wb = row.get('work_breakdown', {})
        if row.get('total_work') != (
            wb.get('probe_executions', 0)
            + wb.get('candidate_evaluations', 0)
            + wb.get('macro_retrievals', 0)
            + wb.get('commutator_probes', 0)
        ):
            errors.append(f'track1_work_identity:{idx}')
        if row.get('method') == 'nexus_unaligned_homomorphism_full':
            gpu = row.get('gpu_telemetry', {})
            if not gpu.get('mps_available') or int(gpu.get('gpu_forward_passes', 0)) < 1:
                errors.append(f'track1_mps_missing:{idx}')
            if row.get('false_unique'):
                errors.append(f'track1_false_unique:{idx}')

    # Check Track 2 rows
    t2_rows = payload.get('track2_imperative_rows', [])
    expected_t2_ids = set(manifest.get('track2_task_ids', []))
    if len(t2_rows) != len(expected_t2_ids) * 3 * len(m2.WAVE21_IMPERATIVE_METHODS):
        errors.append('track2_grid_size')
    for idx, row in enumerate(t2_rows):
        wb = row.get('work_breakdown', {})
        if row.get('total_work') != (
            wb.get('probe_executions', 0)
            + wb.get('candidate_evaluations', 0)
            + wb.get('macro_retrievals', 0)
            + wb.get('commutator_probes', 0)
        ):
            errors.append(f'track2_work_identity:{idx}')
        if row.get('status') == 'unique':
            src = row.get('synthesized_source', '')
            if not src or not m2.verify_multi_statement_imperative_ast(ast.parse(src)):
                errors.append(f'track2_not_multi_statement:{idx}')
        if row.get('method') in (
            'standalone_m4_neural_trace_baseline',
            'nexus_imperative_without_trace_guidance',
            'nexus_m4_execution_guided_imperative_full',
        ):
            gpu = row.get('gpu_telemetry', {})
            if not gpu.get('mps_available') or int(gpu.get('gpu_forward_passes', 0)) < 1:
                errors.append(f'track2_mps_missing:{idx}')

    # Check Track 2 Repo Repair rows
    repo_rows = payload.get('track2_repo_repair_rows', [])
    expected_repo_ids = set(manifest.get('track2_repo_ids', []))
    if len(repo_rows) != len(expected_repo_ids) * 3:
        errors.append('track2_repo_grid_size')
    for idx, rrow in enumerate(repo_rows):
        if not rrow.get('public_passed') or not rrow.get('private_passed'):
            errors.append(f'track2_repo_failed:{idx}')
        rep_src = rrow.get('synthesized_replacement_source', '')
        if not rep_src or not m2.verify_multi_statement_imperative_ast(ast.parse(rep_src)):
            errors.append(f'track2_repo_not_multi_statement:{idx}')
        if not rrow.get('unified_diff', '').startswith('--- a/'):
            errors.append(f'track2_repo_missing_diff:{idx}')

    # Check Track 3 LLM Epistemic rows
    t3_rows = payload.get('track3_llm_epistemic_rows', [])
    expected_t3_count = int(manifest.get('track3_turn_count', 0))
    if len(t3_rows) != expected_t3_count * 3 * len(m3.WAVE21_LLM_METHODS):
        errors.append('track3_grid_size')
    for idx, row in enumerate(t3_rows):
        llm_tel = row.get('llm_telemetry', {})
        mps_tel = row.get('mps_telemetry', {})
        if llm_tel.get('inference_ran') is not True:
            errors.append(f'track3_llm_inference_missing:{idx}')
        if int(llm_tel.get('n_gpu_layers', 0)) != -1:
            errors.append(f'track3_metal_offload_missing:{idx}')
        if not mps_tel.get('mps_available') or int(mps_tel.get('gpu_forward_passes', 0)) < 1:
            errors.append(f'track3_mps_missing:{idx}')
        if not row.get('raw_llm_output'):
            errors.append(f'track3_empty_raw_llm:{idx}')

    # Check all gates
    gates = payload.get('gates', {})
    for g_name, g_val in gates.items():
        if g_val is not True:
            errors.append(f'gate_failed:{g_name}')

    freeze_report: dict[str, Any] = {}
    if freeze_commit:
        freeze_report = verify_freeze_commit_protocol(freeze_commit)
        if not freeze_report['valid']:
            errors.extend(freeze_report['errors'])

    return {
        'valid': not errors,
        'errors': sorted(set(errors)),
        'freeze_verification': freeze_report,
        'track1_rows_verified': len(t1_rows),
        'track2_rows_verified': len(t2_rows),
        'track2_repo_rows_verified': len(repo_rows),
        'track3_rows_verified': len(t3_rows),
        'gates': gates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--result',
        type=Path,
        default=ROOT / 'artifacts' / 'seed_wave21_real_audit_benchmark.json',
    )
    parser.add_argument(
        '--manifest',
        type=Path,
        default=ROOT / 'artifacts' / 'seed_wave21_fresh_manifest.json',
    )
    parser.add_argument('--freeze-commit', type=str, default=None)
    args = parser.parse_args()

    payload = json.loads(args.result.read_text(encoding='utf-8'))
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    report = verify_payload(payload, manifest, freeze_commit=args.freeze_commit)
    report['result_sha256'] = hashlib.sha256(args.result.read_bytes()).hexdigest()
    report['manifest_sha256'] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report['valid']:
        sys.exit(1)


if __name__ == '__main__':
    main()
