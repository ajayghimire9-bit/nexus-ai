#!/usr/bin/env python3
"""Read-only NEXUS branch inventory. Does not checkout, delete, or merge."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAMILIES = (
    ('h17', re.compile(r'h17', re.I)),
    ('h16', re.compile(r'h16|same-state-library', re.I)),
    ('h15', re.compile(r'h15')),
    ('h14', re.compile(r'h14')),
    ('h12_h13', re.compile(r'h12|h13|planning-ranking', re.I)),
    ('h8_h11_mcc', re.compile(r'mcc-multitask|mcc-native|mcc-residual|h10|h11', re.I)),
    ('evolution2', re.compile(r'evolution2', re.I)),
    ('evolution1', re.compile(r'evolution1', re.I)),
    ('v0', re.compile(r'(^|/)v0|/v0[5-9]|v08', re.I)),
    ('xenv', re.compile(r'xenv', re.I)),
    ('lookahead_families', re.compile(
        r'lookahead|acrobot|mountaincar|cartpole-h3|pendulum-compute|compute-matched', re.I)),
    ('latent_context', re.compile(r'latent|context-adapt|amortized|encoder|direct-latent', re.I)),
    ('planning_value', re.compile(
        r'horizon|receding|commitment|terminal-value|action-conditioned|first-action|policy-switch|late-control|long-continuation|decision-aware', re.I)),
    ('meta_cl', re.compile(r'meta-learning|continual|v06', re.I)),
    ('governance', re.compile(r'standing-research|autonomous-research|research-evidence', re.I)),
)


def _run(args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def _heads(remote=None):
    if remote:
        text = _run(['git', 'ls-remote', '--heads', remote])
        rows = []
        for line in text.splitlines():
            if not line.strip():
                continue
            sha, ref = line.split('\t', 1)
            rows.append((ref.split('refs/heads/', 1)[-1], sha))
        return rows
    text = _run(['git', 'for-each-ref', '--format=%(refname:short) %(objectname) %(subject)', 'refs/heads'])
    rows = []
    for line in text.splitlines():
        name, sha, subject = line.split(' ', 2)
        rows.append((name, sha, subject))
    return rows


def _subject(sha):
    return _run(['git', 'log', '-1', '--format=%s', sha])


def classify(name):
    for family, pattern in FAMILIES:
        if pattern.search(name):
            return family
    return 'other'


def role(name):
    if re.search(r'execute|results', name, re.I):
        return 'results'
    if re.search(r'readiness|audit|diagnosis|synthesis|feasibility', name, re.I):
        return 'review'
    if re.search(r'protocol-lock|protocol$', name, re.I):
        return 'lock'
    if re.search(r'runner', name, re.I):
        return 'runner'
    if re.search(r'main$', name):
        return 'mainline'
    return 'topic'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT / 'artifacts' / 'nexus_branch_inventory.json'))
    args = parser.parse_args()
    local = []
    for name, sha, subject in _heads():
        local.append({
            'name': name, 'sha': sha, 'subject': subject,
            'family': classify(name), 'role': role(name), 'presence': ['local'],
        })
    by_name = {row['name']: row for row in local}
    for remote in ('origin', 'github'):
        try:
            remote_rows = _heads(remote)
        except subprocess.CalledProcessError:
            continue
        for name, sha in remote_rows:
            if name in by_name:
                if remote not in by_name[name]['presence']:
                    by_name[name]['presence'].append(remote)
                by_name[name].setdefault('remote_sha', {})[remote] = sha
            else:
                by_name[name] = {
                    'name': name, 'sha': sha, 'subject': _subject(sha),
                    'family': classify(name), 'role': role(name),
                    'presence': [remote], 'remote_sha': {remote: sha},
                }
    rows = sorted(by_name.values(), key=lambda r: (r['family'], r['name']))
    sha_groups = defaultdict(list)
    for row in rows:
        sha_groups[row['sha']].append(row['name'])
    duplicates = {sha: names for sha, names in sha_groups.items() if len(names) > 1}
    head = _run(['git', 'rev-parse', 'HEAD'])
    main_sha = by_name.get('main', {}).get('sha')
    payload = {
        'mode': 'read_only_inventory',
        'scientific': False,
        'head': head,
        'main': main_sha,
        'counts': {
            'branches': len(rows),
            'families': {family: sum(1 for r in rows if r['family'] == family) for family, _ in FAMILIES + (('other', None),)},
            'shared_tips': len(duplicates),
        },
        'duplicate_tips': duplicates,
        'branches': rows,
        'cleanup_policy': {
            'delete_now': False,
            'rewrite_history': False,
            'merge_main': False,
            'requires_human_approval': [
                'delete_or_archive_remote_branches',
                'merge_to_main',
                'retag_or_rewrite',
                'scientific_execution',
            ],
        },
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + '\n')
    print(f'INVENTORY {len(rows)} branches -> {path}')
    print(json.dumps(payload['counts'], indent=2))


if __name__ == '__main__':
    main()
