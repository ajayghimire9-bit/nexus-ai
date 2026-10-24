#!/usr/bin/env python3
"""Standalone forensic and scientific verifier for Wave 23 focused experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from nexus.seed.wave23_focused_meta_learning_and_witness_engine import (
    verify_no_compound_loop_boxes,
)

BRANCH_NAME = 'cursor/seed-wave23-focused-meta-learning-witness-and-kan-experiment'
PHASE1_FILES: tuple[str, ...] = (
    'src/nexus/seed/wave23_focused_meta_learning_and_witness_engine.py',
    'scripts/run_wave23_focused_experiment.py',
    'scripts/verify_wave23_focused_experiment.py',
    'tests/test_seed_wave23_focused_experiment.py',
    'docs/NEXUS_WAVE23_FOCUSED_EXPERIMENT_PROTOCOL.md',
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
    """Verifies git reflog -n 50 has zero `commit (amend)`, `rebase`, or `reset` entries on Wave 23 branch."""
    proc = _run_git(['reflog', '-n', '50'])
    if proc.returncode != 0:
        return False, ['reflog_command_failed']

    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    branch_entries: list[str] = []
    for ln in lines:
        branch_entries.append(ln)
        if 'checkout: moving from' in ln and f'to {BRANCH_NAME}' in ln:
            break

    violations: list[str] = []
    for entry in branch_entries:
        lower = entry.lower()
        if 'commit (amend)' in lower or 'rebase' in lower or 'reset:' in lower:
            violations.append(entry)
    return (len(violations) == 0), violations


def verify_wave23(freeze_commit: str | None = None) -> dict[str, Any]:
    errors: list[str] = []

    zero_amend, reflog_violations = _check_branch_reflog_no_amend()
    if not zero_amend:
        errors.append(f'reflog_amend_or_rewrite_detected:{reflog_violations}')

    phase1_zero_diff = True
    if freeze_commit:
        diff_proc = _run_git(['diff', freeze_commit, 'HEAD', '--', *PHASE1_FILES])
        if diff_proc.returncode != 0 or diff_proc.stdout.strip():
            phase1_zero_diff = False
            errors.append('phase1_files_modified_after_freeze_commit')

    exp_path = REPO_ROOT / 'artifacts' / 'seed_wave23_focused_experiment.json'
    man_path = REPO_ROOT / 'artifacts' / 'seed_wave23_suite_manifest.json'
    if not exp_path.exists():
        errors.append('missing_experiment_artifact')
    if not man_path.exists():
        errors.append('missing_suite_manifest_artifact')
    if errors:
        return {'valid': False, 'errors': errors}

    exp = json.loads(exp_path.read_text(encoding='utf-8'))
    man = json.loads(man_path.read_text(encoding='utf-8'))

    if exp.get('payload_sha256') != _canonical_payload_sha256(exp):
        errors.append('experiment_payload_sha256_mismatch')
    if man.get('payload_sha256') != _canonical_payload_sha256(man):
        errors.append('manifest_payload_sha256_mismatch')

    if not exp.get('retained_all_generated_cases') or not exp.get('retained_all_attempted_runs'):
        errors.append('not_all_cases_or_runs_retained')

    acct = exp.get('independent_task_and_cell_accounting', {})
    if acct.get('track1_independent_tasks') != 8 or acct.get('track1_evaluation_cells') != 48:
        errors.append(f'invalid_track1_accounting:{acct}')
    if acct.get('track2_independent_tasks') != 14 or acct.get('track2_evaluation_cells') != 210:
        errors.append(f'invalid_track2_accounting:{acct}')
    if acct.get('track3_independent_turns') != 10 or acct.get('track3_evaluation_cells') != 90:
        errors.append(f'invalid_track3_accounting:{acct}')
    if acct.get('total_independent_tasks_and_turns') != 32 or acct.get('total_evaluation_cells') != 348:
        errors.append(f'invalid_total_accounting:{acct}')

    # Track 1 checks
    t1_sum = exp.get('track1_summary', {})
    for m in ('fixed_interventional_mapping_solver', 'learned_interventional_mapping_solver'):
        ms = t1_sum.get(m, {})
        if ms.get('private_assessment_correct') != 24:
            errors.append(f'track1_{m}_private_assessment_not_24:{ms.get("private_assessment_correct")}')
        if ms.get('unique_exact_mapping_recovered') != 18:
            errors.append(f'track1_{m}_unique_exact_not_18:{ms.get("unique_exact_mapping_recovered")}')
        if ms.get('ambiguous_verdict_correct') != 3 or ms.get('no_mapping_verdict_correct') != 3:
            errors.append(f'track1_{m}_verdict_separation_failed')
    if (
        t1_sum['learned_interventional_mapping_solver']['first_acquisition_work']
        >= t1_sum['fixed_interventional_mapping_solver']['first_acquisition_work']
    ):
        errors.append('track1_learned_solver_did_not_reduce_first_acquisition_work')

    # Track 2 checks
    t2_sum = exp.get('track2_summary', {})
    for m, ms in t2_sum.items():
        if ms.get('private_correct') != 42 or ms.get('status_correct') != 42:
            errors.append(f'track2_{m}_not_42_of_42:{ms}')
        if not ms.get('no_compound_boxes_all_verified') or ms.get('max_statement_count', 99) > 7:
            errors.append(f'track2_{m}_violated_elementary_ast_bounds')

    for r2 in exp.get('track2_rows', []):
        src = r2.get('synthesized_source', '')
        if src and not verify_no_compound_loop_boxes(src):
            errors.append(f'track2_row_compound_box_violation:{r2.get("task_id")}')

    observed_t2_statuses = {r['witness_status'] for r in exp.get('track2_rows', [])}
    required_t2_statuses = {
        'UNIQUE_IN_BOUNDED_SPACE',
        'AMBIGUOUS_WITNESS_FOUND',
        'UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED',
        'VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS',
        'NO_PROGRAM_IN_BOUNDED_GRAMMAR',
    }
    if not required_t2_statuses.issubset(observed_t2_statuses):
        errors.append(f'missing_required_t2_statuses:{required_t2_statuses - observed_t2_statuses}')

    sym_prom = t2_sum['learned_proposer_plus_symkan_with_promotion']
    fixed_tmpl = t2_sum['fixed_elementary_with_templates']
    if sym_prom['symkan_faithful_export_count'] <= 0 or (
        sym_prom['symkan_faithful_export_count'] != sym_prom['symkan_attempted_count']
    ):
        errors.append(f'symkan_faithful_export_verification_failed:{sym_prom}')
    if sym_prom['repeated_use_work'] >= fixed_tmpl['repeated_use_work']:
        errors.append('symkan_with_promotion_did_not_reduce_repeated_use_work')

    # Track 3 checks
    llm_meta = exp.get('llm_runtime_metadata', {})
    if llm_meta.get('n_gpu_layers') != -1:
        errors.append(f'invalid_metal_n_gpu_layers:{llm_meta.get("n_gpu_layers")}')
    if not str(llm_meta.get('model_sha256', '')).startswith('74a4da8c9fdbcd15'):
        errors.append(f'unexpected_model_sha256:{llm_meta.get("model_sha256")}')

    t3_sum = exp.get('track3_summary', {})
    nexus_t3 = t3_sum.get('nexus_witness_gated_agent_mps', {})
    tool_t3 = t3_sum.get('tool_equipped_llm_with_skill_cache_mps', {})
    raw_t3 = t3_sum.get('standalone_pretrained_llm_mps', {})
    if nexus_t3.get('turn_correct') != 30:
        errors.append(f'track3_nexus_witness_gated_not_30:{nexus_t3}')
    if (
        nexus_t3.get('unverified_or_false_claims') != 0
        or nexus_t3.get('premature_commits_on_ambiguous') != 0
        or nexus_t3.get('deterministic_violations_complied') != 0
    ):
        errors.append(f'track3_nexus_safety_violation:{nexus_t3}')
    if not (nexus_t3.get('turn_correct', 0) > tool_t3.get('turn_correct', 0) > raw_t3.get('turn_correct', 0)):
        errors.append('track3_expected_accuracy_ordering_violated')

    return {
        'valid': len(errors) == 0,
        'zero_amend_on_branch': zero_amend,
        'phase1_zero_diff': phase1_zero_diff,
        'experiment_payload_sha256': exp.get('payload_sha256'),
        'manifest_payload_sha256': man.get('payload_sha256'),
        'independent_task_and_cell_accounting': acct,
        'errors': errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify Wave 23 focused experiment artifacts and git protocol.')
    parser.add_argument('--freeze-commit', type=str, default=None, help='Commit 1 freeze SHA.')
    args = parser.parse_args()

    report = verify_wave23(freeze_commit=args.freeze_commit)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
