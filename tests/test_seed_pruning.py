"""Source/provenance-only cleanup checks; no models, worlds or training."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def branch_tool():
    spec = importlib.util.spec_from_file_location('seed_branches', ROOT/'scripts/audit_seed_branches.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('branch,local,remote,occupied,ancestor,expected', [
    ('main', 'a', 'a', set(), True, 'protected'),
    ('codex/seed-repository-pruning', 'a', None, set(), True, 'protected'),
    ('research', 'a', 'a', {'research'}, True, 'occupied_worktree'),
    ('research', 'a', 'b', set(), True, 'different_local_github_tips'),
    ('research', 'a', 'a', set(), False, 'not_merged_into_reviewed_main'),
    ('research', 'a', 'a', set(), True, None),
    ('local-only', 'a', None, set(), True, None),
    ('remote-only', None, 'a', set(), True, None),
])
def test_retirement_requires_matching_redundant_unoccupied_tip(branch, local, remote, occupied, ancestor, expected):
    assert branch_tool().reason(branch, local, remote, occupied, ancestor) == expected


def test_only_remote_peeled_exact_tip_is_a_verified_backup():
    m = branch_tool()
    plan = {'eligible': [{'branch': 'old', 'sha': 'commit', 'backup_tag': 'archive/old'}]}
    for tags in ({}, {'refs/tags/archive/old': 'commit'}, {'refs/tags/archive/old^{}': 'wrong'}):
        with pytest.raises(ValueError, match='missing_or_wrong_remote_backup'):
            m.verify_backups(plan, tags)
    assert m.verify_backups(plan, {'refs/tags/archive/old^{}': 'commit'})


def test_shared_numeric_validation_preserves_scalar_contract_without_neural_imports():
    # In a fresh stdlib-only interpreter the four evidence readers stay light.
    code = '''
import sys
sys.path.insert(0, sys.argv[1])
from nexus.seed.grounded_audit import finite
from nexus.seed.contract_audit import finite as a
from nexus.seed.readout_audit import finite as b
from nexus.seed.learning_validation_audit import numeric as c
from nexus.seed.nonlinear_learning_audit import numeric as d
assert all(f is finite for f in (a,b,c,d))
for v in (0, -3, 1.5): assert finite(v)
for v in (True, False, '1', None, [], {}, float('nan'), float('inf'), -float('inf')): assert not finite(v)
assert not any(n in sys.modules for n in ('torch','numpy','gymnasium'))
'''
    subprocess.run([sys.executable, '-I', '-S', '-c', code, str(ROOT/'src')], check=True)


def test_retirement_receipt_covers_original_inventory_and_exact_tips_offline():
    # Repository-only checks work in a fresh clone without local worktrees,
    # checkpoint binaries or a live GitHub connection.
    raw = (ROOT/'artifacts/seed_branch_cleanup_plan.json').read_bytes()
    plan = json.loads(raw)
    receipt = json.loads((ROOT/'artifacts/seed_branch_cleanup_receipt.json').read_text())
    assert receipt['plan_sha256'] == hashlib.sha256(raw).hexdigest()
    names = [r['branch'] for r in plan['eligible']]
    assert len(names) == len(set(names)) == receipt['local_retired']
    assert len({r['backup_tag'] for r in plan['eligible']}) == receipt['durable_exact_tip_backups']
    assert sum(r['github_sha'] is not None for r in plan['eligible']) == receipt['github_retired']
    for row in plan['eligible']:
        assert row['local_sha'] == row['sha']
        assert row['github_sha'] in (None, row['sha'])
        assert row['branch'] not in receipt['remaining_local']
        assert row['branch'] not in receipt['remaining_github']
    for row in plan['retained']:
        if row['local_sha']:
            assert receipt['remaining_local'][row['branch']] == row['local_sha']
        if row['github_sha']:
            assert receipt['remaining_github'][row['branch']] == row['github_sha']
    assert receipt['main_modified'] is False and receipt['worktrees_removed'] == 0


def test_all_previous_artifacts_and_cleanup_source_hashes_match_offline():
    receipt = json.loads((ROOT/'artifacts/seed_branch_cleanup_receipt.json').read_text())
    for path, expected in receipt['preserved_artifact_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected, path
    changes = json.loads((ROOT/'artifacts/seed_pruning_changes.json').read_text())
    assert len(changes['changes']) == 5
    for path, hashes in changes['changes'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == hashes['after'], path
