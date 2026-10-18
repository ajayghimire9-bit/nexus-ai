"""Read-only/temporary-source fixtures; no reviewed module is imported or run."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/audit_evolution1_adapters.py'
spec = importlib.util.spec_from_file_location('evolution1_source_audit', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_exact_committed_inventory_matches_repository():
    report = audit.verify_manifest(ROOT, audit.load_manifest(audit.MANIFEST))
    assert len(report['sources']) == len(audit.SOURCES) == 15


@pytest.mark.parametrize('mutation', ['missing_file', 'missing_symbol', 'duplicate_file',
    'wrong_hash', 'extra_path', 'false_as_zero', 'numeric_string', 'claimed_ready'])
def test_altered_or_incomplete_grid_fails(mutation):
    payload = copy.deepcopy(audit.source_snapshot(ROOT))
    rows = payload['sources']
    if mutation == 'missing_file': rows.pop()
    elif mutation == 'missing_symbol': rows[0]['symbols'].pop(next(iter(rows[0]['symbols'])))
    elif mutation == 'duplicate_file': rows.append(copy.deepcopy(rows[0]))
    elif mutation == 'wrong_hash': rows[0]['sha256'] = '0'*64
    elif mutation == 'extra_path': rows[0]['path'] = '../../unreviewed.py'
    elif mutation == 'false_as_zero': payload['execution_authorized'] = 0
    elif mutation == 'numeric_string': payload['real_interactions'] = '0'
    elif mutation == 'claimed_ready': payload['status'] = 'ready'
    with pytest.raises(audit.ReviewMismatch): audit.verify_manifest(ROOT, payload)


def test_source_bytes_change_invalidates_hash_even_if_ast_unchanged(tmp_path):
    original = audit.source_snapshot(ROOT)
    for relative in audit.SOURCES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    changed = tmp_path / next(iter(audit.SOURCES))
    changed.write_text(changed.read_text() + '\n# changed review evidence\n')
    with pytest.raises(audit.ReviewMismatch): audit.verify_manifest(tmp_path, original)
    changed.unlink()
    with pytest.raises(audit.ReviewMismatch): audit.source_snapshot(tmp_path)


def test_missing_or_duplicated_definition_cannot_be_certified():
    for source in ('def other(): pass', 'def f(): pass\ndef f(): pass'):
        with pytest.raises(audit.ReviewMismatch): audit.definition(ast.parse(source), 'f')


@pytest.mark.parametrize('text', ['{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}'])
def test_manifest_json_rejects_nonfinite_and_duplicate_keys(tmp_path,text):
    path = tmp_path / 'bad.json'; path.write_text(text)
    with pytest.raises(audit.ReviewMismatch): audit.load_manifest(path)


def test_check_does_not_import_scientific_stack_or_create_execution_entrypoint():
    code = f'''import runpy, sys
sys.argv = [{str(SCRIPT)!r}, '--check']
runpy.run_path({str(SCRIPT)!r}, run_name='__main__')
assert not any(n in sys.modules for n in ('numpy','torch','gymnasium','nexus.world','nexus.tasks'))
'''
    result = subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,check=True)
    assert '15 files; runtime remains blocked' in result.stdout
    denied = subprocess.run([sys.executable,'-B',str(SCRIPT),'--execute'],capture_output=True,text=True)
    assert denied.returncode != 0


def test_audit_script_has_only_stdlib_imports_and_no_source_execution():
    tree = ast.parse(SCRIPT.read_text())
    allowed = {'__future__','argparse','ast','hashlib','json','pathlib'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): assert all(n.name in allowed for n in node.names)
        if isinstance(node,ast.ImportFrom): assert node.module in allowed
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
            assert node.func.id not in {'exec','eval','compile','__import__'}
