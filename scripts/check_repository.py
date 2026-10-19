"""Stdlib-only Seed documentation/layout and preserved-file verification.

No import of the agent, environments, neural libraries or experiment runners.
Checks local paths, not external websites or Markdown fragment IDs. Historical
verbatim snapshots are deliberately excluded from current-navigation link checks.
"""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (
    'README.md', 'CONTRIBUTING.md', 'SECURITY.md', 'docs/README.md',
    'docs/seed/QUICKSTART.md', 'docs/seed/ARCHITECTURE.md',
    'docs/history/README.md', 'docs/NEXUS_REPOSITORY_STRUCTURE.md',
    'docs/NEXUS_SEED_CHARTER.md', 'docs/NEXUS_SEED_ROADMAP.md',
    'docs/NEXUS_SEED_STATUS.md', 'docs/NEXUS_SEED_RESULTS.md',
)
REQUIRED = (
    'AGENTS.md', 'pyproject.toml', 'Makefile', '.gitignore',
    '.github/PULL_REQUEST_TEMPLATE.md', 'docs/automation/seed-checks.yml.example',
    '.github/ISSUE_TEMPLATE/bug.yml', '.github/ISSUE_TEMPLATE/research.yml',
    'docs/assets/nexus-seed.svg', 'docs/history/README_BEFORE_SEED_REFRESH.md',
    'src/nexus/seed/core.py', 'src/nexus/seed/storage.py', 'src/nexus/seed/lab.py',
    'scripts/run_learning_lab.py', 'scripts/verify_seed_comparison.py',
    'web/learning-lab/seed.html', 'artifacts/seed_s0_s1_dev.json',
    'artifacts/seed_repository_refresh.json',
)


def links(text):
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    return (re.findall(r'\[[^\]\n]*\]\(([^\s)]+)\)', text) +
            re.findall(r'(?:href|src)="([^"]+)"', text))


def check(root=ROOT):
    root = Path(root).resolve()
    for name in DOCUMENTS + REQUIRED:
        if not (root/name).is_file():
            raise ValueError('missing_repository_file: '+name)
    count = 0
    for name in DOCUMENTS:
        for target in links((root/name).read_text()):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = (root/name).parent/unquote(parsed.path)
            resolved = path.resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                raise ValueError('broken_local_link: '+name+' -> '+target)
            count += 1
    record = json.loads((root/'artifacts/seed_repository_refresh.json').read_text())
    protected = record['protected_sha256']
    if type(protected) is not dict or not protected:
        raise ValueError('preservation_manifest_required')
    # A new, committed engineering task can evolve runtime code without
    # retroactively rewriting the historical preservation receipt.
    overrides={}
    change_path=root/'artifacts/seed_hybrid_code_changes.json'
    if change_path.exists():
        change=json.loads(change_path.read_text())
        baseline=hashlib.sha256((root/'artifacts/seed_repository_refresh.json').read_bytes()).hexdigest()
        if change.get('schema')!='seed_explicit_code_evolution_v1' or change.get('baseline_manifest_sha256')!=baseline or type(change.get('changes')) is not dict:
            raise ValueError('invalid_code_evolution_record')
        for name,row in change['changes'].items():
            if name not in protected or set(row)!={'before','after'} or row['before']!=protected[name] or type(row['after']) is not str or not re.fullmatch('[0-9a-f]{64}',row['after']):
                raise ValueError('unlisted_or_unanchored_code_change')
            overrides[name]=row['after']
    for name, expected in protected.items():
        path = (root/name).resolve()
        if (not path.is_relative_to(root) or not path.is_file() or
                hashlib.sha256(path.read_bytes()).hexdigest() != overrides.get(name,expected)):
            raise ValueError('preserved_file_changed: '+name)
    archived = (root/'docs/history/README_BEFORE_SEED_REFRESH.md').read_bytes()
    if hashlib.sha256(archived).hexdigest() != record['previous_readme_sha256']:
        raise ValueError('historical_readme_changed')
    return dict(valid=True,active_documents=len(DOCUMENTS),local_links=count,
                preserved_files=len(protected)-len(overrides),explicit_code_changes=len(overrides),
                external_links_checked=False,fragment_ids_checked=False,
                scientific_execution=False,checkpoint_files_required=False)


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
