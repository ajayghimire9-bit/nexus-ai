"""Read-only local/GitHub branch retirement plan. Never deletes or fetches refs.

Commit ancestry proves redundancy, not lack of scientific importance. Every
eligible branch still needs a verified remote exact-tip archive before removal.
Other remotes, worktrees and ignored files are deliberately outside this tool.
"""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = 'ad8b65c155f20a71a82f1ee51bcde9e1fd353492'
PREFIX = 'archive/seed-cleanup/2026-10-20/'


def reason(branch, local, github, occupied, ancestor):
    if branch in ('main', 'master', 'codex/seed-repository-pruning'):
        return 'protected'
    if branch in occupied:
        return 'occupied_worktree'
    if local is not None and github is not None and local != github:
        return 'different_local_github_tips'
    if not ancestor:
        return 'not_merged_into_reviewed_main'
    return None


def verify_backups(plan, remote_tags):
    """Require peeled GitHub commit IDs, not merely local tags or tag objects."""
    for row in plan['eligible']:
        if remote_tags.get('refs/tags/'+row['backup_tag']+'^{}') != row['sha']:
            raise ValueError('missing_or_wrong_remote_backup: '+row['branch'])
    return True


def audit(root=ROOT):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    github = {ref.removeprefix('refs/heads/'): sha for sha, ref in
              (line.split() for line in git('ls-remote', '--heads', 'github').splitlines())}
    local = {ref.removeprefix('refs/heads/'): sha for ref, sha in
             (line.split() for line in git('for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads').splitlines())}
    if github.get('main') != BASE or local.get('main') != BASE:
        raise ValueError('main_advanced_reaudit_required')
    occupied = {line.removeprefix('branch refs/heads/') for line in
                git('worktree', 'list', '--porcelain').splitlines() if line.startswith('branch refs/heads/')}
    eligible, retained = [], []
    for branch in sorted(set(local) | set(github)):
        sha = github.get(branch, local.get(branch))
        check = subprocess.run(['git', 'merge-base', '--is-ancestor', sha, BASE], cwd=root, capture_output=True)
        why = reason(branch, local.get(branch), github.get(branch), occupied, check.returncode == 0)
        row = dict(branch=branch, sha=sha, local_sha=local.get(branch), github_sha=github.get(branch))
        if why:
            retained.append(dict(row, reason=why))
        else:
            eligible.append(dict(row, backup_tag=PREFIX+branch))
    return dict(schema='seed_branch_retirement_plan_v1', base=BASE,
                eligible=eligible, retained=retained,
                local_count=len(local), github_count=len(github),
                other_remotes_modified=False, scientific_execution=False)


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
