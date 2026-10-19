"""Navigation/preservation checks. No agent inference, simulator or checkpoints."""
import importlib.util
import json
from pathlib import Path
import shutil
import pytest

ROOT = Path(__file__).resolve().parents[1]


def checker():
    spec = importlib.util.spec_from_file_location('repository_checker', ROOT/'scripts/check_repository.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def small_tree(tmp_path):
    module = checker()
    record = json.loads((ROOT/'artifacts/seed_repository_refresh.json').read_text())
    names = set(module.REQUIRED + module.DOCUMENTS)
    # Copy only current entry points; mutation tests replace their links below.
    for name in names:
        target = tmp_path/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    # Narrow to an isolated copied file. Full preservation is tested at ROOT.
    import hashlib
    record['protected_sha256'] = {'src/nexus/seed/core.py': hashlib.sha256((ROOT/'src/nexus/seed/core.py').read_bytes()).hexdigest()}
    (tmp_path/'artifacts/seed_repository_refresh.json').write_text(json.dumps(record))
    return module


def test_current_navigation_and_all_preserved_files():
    result = checker().check()
    assert result['valid'] and result['local_links'] > 20
    assert result['preserved_files'] > 1000


@pytest.mark.parametrize('fault', ['link', 'escape', 'required', 'preserved', 'readme'])
def test_rejects_broken_navigation_or_history(tmp_path, fault):
    module = small_tree(tmp_path)
    # Avoid depending on unrelated linked historical files in mutation tests.
    for name in module.DOCUMENTS:
        (tmp_path/name).write_text('# Test document\n')
    if fault == 'link':
        (tmp_path/'README.md').write_text('[Missing](does-not-exist.md)')
    elif fault == 'escape':
        (tmp_path/'README.md').write_text('[Outside](../README.md)')
    elif fault == 'required':
        (tmp_path/'src/nexus/seed/lab.py').unlink()
    elif fault == 'preserved':
        (tmp_path/'src/nexus/seed/core.py').write_text('changed')
    else:
        (tmp_path/'docs/history/README_BEFORE_SEED_REFRESH.md').write_text('rewritten')
    with pytest.raises(ValueError):
        module.check(tmp_path)


def test_markdown_code_samples_are_not_link_targets():
    assert checker().links('```text\n[example](missing.md)\n```\n[Guide](docs/README.md)') == ['docs/README.md']


def test_private_seed_environment_is_ignored():
    import subprocess
    result = subprocess.run(['git', 'check-ignore', '--stdin'], cwd=ROOT,
                            input='.venv-seed/a\nruns/seed-sessions/private.json\n',
                            text=True, capture_output=True, check=True)
    assert result.stdout.splitlines() == ['.venv-seed/a', 'runs/seed-sessions/private.json']
