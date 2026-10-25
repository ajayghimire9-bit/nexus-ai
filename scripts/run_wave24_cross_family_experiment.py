#!/usr/bin/env python3
"""Single-shot runner for Wave 24 Cross-Family Meta-Procedure, Quotienting & Interference Immunity Experiment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'src'))

from nexus.seed.wave24_cross_family_meta_and_quotient_engine import run_wave24_experiment


def _resolve_git_head() -> str:
    try:
        out = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO_ROOT, text=True).strip()
        return out
    except Exception:
        return '0' * 40


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--freeze-commit',
        default='',
        help='Commit-1 freeze SHA used to deterministically seed the post-freeze assessment generator.',
    )
    parser.add_argument(
        '--output',
        default=str(REPO_ROOT / 'artifacts' / 'seed_wave24_cross_family_experiment.json'),
        help='Path to write the Wave 24 experiment payload JSON.',
    )
    parser.add_argument(
        '--manifest-output',
        default=str(REPO_ROOT / 'artifacts' / 'seed_wave24_suite_manifest.json'),
        help='Path to write the Wave 24 suite manifest JSON.',
    )
    parser.add_argument(
        '--dev-suite',
        action='store_true',
        help='Run on the separate development suite (`w24_dev_*`) instead of the post-freeze assessment suite.',
    )
    args = parser.parse_args()

    freeze_sha = args.freeze_commit.strip() or _resolve_git_head()
    payload, manifest = run_wave24_experiment(
        freeze_commit_sha=freeze_sha,
        seeds=(0, 1, 2),
        use_dev_suite=bool(args.dev_suite),
        execute_metal_llm=True,
    )

    out_path = Path(args.output)
    manifest_path = Path(args.manifest_output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    print(
        json.dumps(
            {
                'status': 'ok',
                'freeze_commit_sha': freeze_sha,
                'assessment_seed': payload['assessment_seed'],
                'payload_sha256': payload['payload_sha256'],
                'manifest_sha256': manifest['payload_sha256'],
                'h1_established_on_unseen_cd': payload['h1_and_h2_verdicts'][
                    'H1_policy_only_skills_cleared_vs_fixed_no_skills'
                ]['established_on_unseen_families_cd_operating_work'],
                'h2_established_on_unseen_cd': payload['h1_and_h2_verdicts'][
                    'H2_acquired_structure_plus_policy_vs_ordinary_template_reuse'
                ]['established_on_unseen_families_cd'],
            },
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
