"""Read-only checks for the consolidation inventory. No scientific work."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'artifacts' / 'research_session_h16_same_state_library_usage.json'


def test_inventory_script_is_read_only_and_has_no_scientific_stack():
    source = (ROOT / 'scripts' / 'nexus_branch_inventory.py').read_text()
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split('.')[0])
    assert imported.isdisjoint({'torch', 'gymnasium', 'numpy', 'optuna'})
    assert 'git checkout' not in source and 'push --force' not in source
    assert 'git branch -D' not in source


def test_generated_inventory_forbids_cleanup_actions():
    payload = json.loads((ROOT / 'artifacts' / 'nexus_branch_inventory.json').read_text())
    assert payload['scientific'] is False
    assert payload['cleanup_policy']['delete_now'] is False
    assert payload['cleanup_policy']['merge_main'] is False
    assert len(payload['head']) == 40
    assert payload['main'].startswith('d36b49f')
    assert payload['counts']['branches'] >= 100
    assert payload['counts']['delete'] == 0


def test_registry_and_ledger_are_unchanged_by_this_audit():
    registry = json.loads((ROOT / 'artifacts' / 'nexus_research_registry.json').read_text())
    assert registry['h17'] == 'blocked'
    assert registry['scientific'] is False
    payload = json.loads(LEDGER.read_text())
    assert payload['ledger']['consumed_total_s'] == 305.842
    assert payload['remaining_session_allowance_s'] == 3294.158
    digest = hashlib.sha256(LEDGER.read_bytes()).hexdigest()
    assert digest == 'ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117'
