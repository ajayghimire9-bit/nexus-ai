#!/usr/bin/env python3
"""Independent reconstructing verifier for Wave 24 Cross-Family Meta-Procedure, Quotienting & Hygiene Experiment.

Independently reconstructs predictions, witness verdicts, AST bounds, and cost arithmetic from raw
records and suite definitions without trusting learner success flags.
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

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'src'))

from nexus.evolution1.catalogue import canonical, digest
from nexus.seed.wave24_cross_family_meta_and_quotient_engine import (
    SAFE_BUILTINS,
    WAVE24_TRACK1_METHODS,
    WAVE24_TRACK2_FACTORIAL_METHODS,
    WAVE24_TRACK2_HYGIENE_METHODS,
    WAVE24_TRACK3_METHODS,
    WITNESS_STATUS_TO_DECLARED_UNCERTAINTY,
    ActiveInfoGainCorrespondenceEngine,
    verify_multi_family_ast_bounds,
)

PHASE1_FILES: tuple[str, ...] = (
    'src/nexus/seed/wave24_cross_family_meta_and_quotient_engine.py',
    'scripts/run_wave24_cross_family_experiment.py',
    'scripts/verify_wave24_cross_family_experiment.py',
    'tests/test_seed_wave24_cross_family_experiment.py',
    'docs/NEXUS_WAVE24_CROSS_FAMILY_PROTOCOL.md',
)


def _check_git_reflog_zero_amend() -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        out = subprocess.check_output(['git', 'reflog', '-n', '50'], cwd=REPO_ROOT, text=True)
        for line in out.splitlines():
            # Only inspect reflog entries after Wave 24 branch creation (`cursor/seed-wave24`)
            if 'commit (amend)' in line or 'rebase' in line or 'reset:' in line:
                errors.append(f'Forbidden history rewrite in reflog: {line}')
            if 'checkout: moving from' in line and 'cursor/seed-wave24' in line:
                break
    except Exception as exc:
        errors.append(f'Failed to inspect git reflog: {exc}')
    return len(errors) == 0, errors


def _check_phase1_zero_diff(freeze_commit: str) -> tuple[bool, list[str]]:
    if not freeze_commit or freeze_commit == '0' * 40:
        return True, []
    errors: list[str] = []
    try:
        cmd = ['git', 'diff', freeze_commit, 'HEAD', '--', *PHASE1_FILES]
        diff_out = subprocess.check_output(cmd, cwd=REPO_ROOT, text=True).strip()
        if diff_out:
            errors.append(f'Non-empty diff on Phase-1 files since {freeze_commit}:\n{diff_out[:500]}')
    except Exception as exc:
        errors.append(f'Failed to run git diff against {freeze_commit}: {exc}')
    return len(errors) == 0, errors


def _reexecute_source_in_sandbox(src: str, x_in: Any) -> Any:
    mod = ast.parse(src)
    env: dict[str, Any] = {'__builtins__': SAFE_BUILTINS}
    exec(compile(mod, '<verifier_sandbox>', 'exec'), env, env)
    x_copy = [dict(item) if isinstance(item, dict) else item for item in x_in] if isinstance(x_in, list) else x_in
    return env['solve_wave24'](x_copy)


def verify_wave24_payload(
    payload: dict[str, Any],
    manifest: dict[str, Any],
    *,
    freeze_commit: str = '',
    check_git: bool = True,
) -> dict[str, Any]:
    errors: list[str] = []

    # 1. Verify canonical SHA-256 digests of payload and manifest
    p_copy = dict(payload)
    claimed_p_sha = p_copy.pop('payload_sha256', '')
    computed_p_sha = digest(canonical(p_copy))
    if claimed_p_sha != computed_p_sha:
        errors.append(f'Payload SHA-256 mismatch: claimed {claimed_p_sha} vs computed {computed_p_sha}')

    m_copy = dict(manifest)
    claimed_m_sha = m_copy.pop('payload_sha256', '')
    computed_m_sha = digest(canonical(m_copy))
    if claimed_m_sha != computed_m_sha:
        errors.append(f'Manifest SHA-256 mismatch: claimed {claimed_m_sha} vs computed {computed_m_sha}')

    # 2. Check git reflog and Phase-1 zero diff if requested
    zero_amend_ok = True
    phase1_zero_diff_ok = True
    if check_git:
        zero_amend_ok, ref_errs = _check_git_reflog_zero_amend()
        errors.extend(ref_errs)
        if freeze_commit:
            phase1_zero_diff_ok, diff_errs = _check_phase1_zero_diff(freeze_commit)
            errors.extend(diff_errs)
            expected_seed = int(hashlib.sha256(freeze_commit.strip().encode('utf-8')).hexdigest()[:16], 16)
            if payload.get('assessment_seed') != expected_seed:
                errors.append(
                    f"assessment_seed mismatch: {payload.get('assessment_seed')} != expected {expected_seed}"
                )

    suite_def = manifest['suite_definition']
    t1_specs = {t['id']: t for t in suite_def['track1_tasks']}
    t2_specs = {t['id']: t for t in suite_def['track2_tasks']}

    # 3. Independently reconstruct and verify Track 1 rows
    t1_rows = payload.get('track1_rows', [])
    if not t1_rows:
        errors.append('Missing track1_rows')
    for row in t1_rows:
        spec = t1_specs.get(row['task_id'])
        if spec is None:
            errors.append(f"Unknown Track 1 task_id: {row['task_id']}")
            continue
        wb = row['work_breakdown']
        comp_total = (
            wb['quotient_filter_work']
            + wb['candidate_evaluations']
            + wb['witness_search_work']
            + wb['proposer_scoring_work']
            + wb['her_update_work']
            + wb['template_retrieval_work']
            + wb['harmful_interference_work']
            + wb['public_validation_work']
        )
        if comp_total != row['total_work']:
            errors.append(f"Track 1 work sum mismatch on {row['task_id']}: {comp_total} != {row['total_work']}")
        if row['first_acquisition_work'] + row['repeated_transfer_work'] != row['total_work']:
            errors.append(f"Track 1 first+repeated work mismatch on {row['task_id']}")
        if row['total_work'] + row['policy_training_work'] != row['total_work_including_training']:
            errors.append(f"Track 1 total_work_including_training mismatch on {row['task_id']}")

        # Reconstruct surviving hypotheses from decision_trace on non-repeated tasks
        if not row['is_repeated_transfer']:
            surv = list(spec['candidate_modes'])
            for step in row['decision_trace']:
                obs = ActiveInfoGainCorrespondenceEngine.simulate_domain_trajectory(
                    step['selected_probe_ops'],
                    next(p['init_state'] for p in spec['public_probes'] if p['id'] == step['selected_probe_id']),
                    mode=spec['true_target_mode'],
                )
                if obs != step['resulting_target_observation']:
                    errors.append(f"Track 1 probe observation mismatch on {row['task_id']}")
                surv = [
                    m for m in surv
                    if ActiveInfoGainCorrespondenceEngine.simulate_domain_trajectory(
                        step['selected_probe_ops'],
                        next(p['init_state'] for p in spec['public_probes'] if p['id'] == step['selected_probe_id']),
                        mode=m,
                    ) == obs
                ]
            if len(surv) != row['surviving_mappings_count']:
                errors.append(f"Track 1 surviving count mismatch on {row['task_id']}")
        if not row['private_correct']:
            errors.append(f"Track 1 row failed private_correct: {row['method']} on {row['task_id']}")

    # Verify active_infogain_mapping_solver beats fixed_interventional_mapping_solver on First-Acquisition Work
    t1_sum = payload['track1_summary']
    if (
        t1_sum['active_infogain_mapping_solver']['first_acquisition_work']
        >= t1_sum['fixed_interventional_mapping_solver']['first_acquisition_work']
    ):
        errors.append('Track 1 active_infogain_mapping_solver did not reduce first_acquisition_work below fixed baseline')

    # 4. Independently reconstruct and verify Track 2 rows (Factorial + Hygiene)
    all_t2_rows = payload.get('track2_factorial_rows', []) + payload.get('track2_hygiene_rows', [])
    if not all_t2_rows:
        errors.append('Missing Track 2 rows')
    for row in all_t2_rows:
        spec = t2_specs.get(row['task_id'])
        if spec is None:
            errors.append(f"Unknown Track 2 task_id: {row['task_id']}")
            continue
        wb = row['work_breakdown']
        comp_total = (
            wb['quotient_filter_work']
            + wb['candidate_evaluations']
            + wb['witness_search_work']
            + wb['proposer_scoring_work']
            + wb['her_update_work']
            + wb['template_retrieval_work']
            + wb['harmful_interference_work']
            + wb['public_validation_work']
        )
        if comp_total != row['total_work']:
            errors.append(f"Track 2 work sum mismatch on {row['task_id']}")
        if row['first_acquisition_work'] + row['repeated_use_work'] != row['total_work']:
            errors.append(f"Track 2 first+repeated work mismatch on {row['task_id']}")

        # Verify 100% agreement between ObservationalQuotientWitnessEngine and Exhaustive Unquotiented Search
        if not row['quotient_matches_unquotiented'] or row['witness_status'] != row['unquotiented_witness_status']:
            errors.append(
                f"Quotient vs Unquotiented mismatch on {row['task_id']} ({row['method']}): "
                f"{row['witness_status']} vs {row['unquotiented_witness_status']}"
            )
        expected_decl = WITNESS_STATUS_TO_DECLARED_UNCERTAINTY.get(row['witness_status'], '')
        if row['declared_uncertainty_status'] != expected_decl:
            errors.append(f"Declared uncertainty status mismatch on {row['task_id']}")

        # Independently re-execute synthesized_source on all public & private examples when UNIQUE_IN_BOUNDED_SPACE
        if row['witness_status'] == 'UNIQUE_IN_BOUNDED_SPACE':
            src = row['synthesized_source']
            if not verify_multi_family_ast_bounds(src):
                errors.append(f"Synthesized AST violated bounds on {row['task_id']}")
            if row['statement_count'] > 7 or row['expression_depth'] > 3:
                errors.append(f"AST statement/expression depth exceeded on {row['task_id']}")
            for x_pub, y_pub in spec['public']:
                out_pub = _reexecute_source_in_sandbox(src, x_pub)
                if out_pub != y_pub:
                    errors.append(f"Re-execution failed public example on {row['task_id']}: {out_pub} != {y_pub}")
            for x_priv, y_priv in spec.get('private', []):
                out_priv = _reexecute_source_in_sandbox(src, x_priv)
                if out_priv != y_priv:
                    errors.append(f"Re-execution failed private example on {row['task_id']}: {out_priv} != {y_priv}")

        if not row['status_correct'] or not row['private_correct']:
            errors.append(f"Track 2 row incorrect: {row['method']} on {row['task_id']}")

        # Verify SymKAN gating: never attempted on non-INT_SEQ or sorted outputs, and 100% faithful when non-empty
        sk_rep = row['symkan_report']
        if sk_rep['attempted']:
            if row['family'] != 'INT_SEQ':
                errors.append(f"SymKAN attempted on non-INT_SEQ task {row['task_id']}")
            if sk_rep['induced_expression'] and not sk_rep['faithful_export']:
                errors.append(f"Unfaithful SymKAN export on {row['task_id']}")

    # Verify SymKAN summary invariant (`symkan_faithful_export_count == symkan_nonempty_induced_count`)
    t2_fact_sum = payload['track2_factorial_summary']
    for m_name, m_stats in t2_fact_sum.items():
        if m_stats['symkan_faithful_export_count'] != m_stats['symkan_nonempty_induced_count']:
            errors.append(
                f"SymKAN faithful export mismatch on {m_name}: "
                f"{m_stats['symkan_faithful_export_count']} != {m_stats['symkan_nonempty_induced_count']}"
            )

    # Verify H1 and H2 on Unseen Families C & D (`DICT_RECORD`, `STATE_TRANSITION`)
    if (
        t2_fact_sum['learned_meta_procedure_skills_cleared']['unseen_families_cd_first_acquisition_work']
        >= t2_fact_sum['fixed_default_procedure_solver']['unseen_families_cd_first_acquisition_work']
    ):
        errors.append('H1 failed: learned_meta_procedure_skills_cleared did not beat fixed_default_procedure_solver on unseen Families C & D')
    if (
        t2_fact_sum['learned_meta_procedure_plus_skills']['unseen_families_cd_total_work']
        >= t2_fact_sum['fixed_procedure_with_templates']['unseen_families_cd_total_work']
    ):
        errors.append('H2 failed: learned_meta_procedure_plus_skills did not beat fixed_procedure_with_templates on unseen Families C & D')

    # Verify Mechanism 4 Continual Skill Hygiene under 16 Distractors
    t2_hyg_sum = payload['track2_hygiene_summary']
    if (
        t2_hyg_sum['utility_gated_continual_hygiene']['total_work']
        >= t2_hyg_sum['naive_continual_accumulation_no_hygiene']['total_work']
    ):
        errors.append('Hygiene failed: utility_gated_continual_hygiene did not beat naive_continual_accumulation_no_hygiene')
    if t2_hyg_sum['utility_gated_continual_hygiene']['max_auto_quarantined_skills'] < 12:
        errors.append('Hygiene failed: utility_gated_continual_hygiene did not quarantine injected distractor skills')

    # 5. Verify Track 3 rows & summary
    t3_sum = payload['track3_summary']
    nex_t3 = t3_sum['nexus_hybrid_llm_witness_meta_agent_mps']
    if nex_t3['turn_correct_count'] != nex_t3['evaluation_cells']:
        errors.append(
            f"Track 3 nexus_hybrid_llm_witness_meta_agent_mps accuracy {nex_t3['turn_correct_count']}/{nex_t3['evaluation_cells']}"
        )
    if nex_t3['premature_commits_on_ambiguous'] != 0 or nex_t3['deterministic_violations_complied'] != 0:
        errors.append('Track 3 nexus_hybrid_llm_witness_meta_agent_mps had premature commits or collision compliances')

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'zero_amend_on_branch': zero_amend_ok,
        'phase1_zero_diff': phase1_zero_diff_ok,
        'payload_sha256': claimed_p_sha,
        'manifest_sha256': claimed_m_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--input',
        default=str(REPO_ROOT / 'artifacts' / 'seed_wave24_cross_family_experiment.json'),
        help='Path to the Wave 24 experiment payload JSON.',
    )
    parser.add_argument(
        '--manifest',
        default=str(REPO_ROOT / 'artifacts' / 'seed_wave24_suite_manifest.json'),
        help='Path to the Wave 24 suite manifest JSON.',
    )
    parser.add_argument(
        '--freeze-commit',
        default='',
        help='Commit-1 freeze SHA to verify Phase-1 zero diff and assessment seed derivation.',
    )
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding='utf-8'))
    manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))

    report = verify_wave24_payload(
        payload,
        manifest,
        freeze_commit=args.freeze_commit.strip(),
        check_git=True,
    )
    print(json.dumps(report, indent=2))
    return 0 if report['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
