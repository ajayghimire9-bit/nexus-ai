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
    'docs/seed/GROUNDED_QUICKSTART.md', 'docs/NEXUS_SEED_GROUNDED_PROTOCOL.md',
    'docs/NEXUS_SEED_GROUNDED_RESULTS.md',
    'docs/seed/CONTRACT_QUICKSTART.md','docs/NEXUS_SEED_CONTRACT_RESULTS.md',
    'docs/seed/ADAPTIVE_QUICKSTART.md','docs/NEXUS_SEED_MEMORY_AWARE_PROTOCOL.md',
    'docs/NEXUS_SEED_MEMORY_AWARE_RESULTS.md',
    'docs/NEXUS_SEED_LEARNING_VALIDATION_PROTOCOL.md','docs/NEXUS_SEED_LEARNING_VALIDATION_RESULTS.md',
    'docs/NEXUS_SEED_SURPRISE_READOUT_PROTOCOL.md','docs/NEXUS_SEED_SURPRISE_READOUT_RESULTS.md',
    'AGENTS.md','docs/MASTER_CONTEXT.md','docs/NEXUS_CANONICAL_CURRENT_STATE.md',
    'docs/NEXUS_CODE_REUSE_MAP.md','docs/NEXUS_FULL_RESEARCH_REGISTRY.md',
    'docs/NEXUS_SEED_FOCUS_CLEANUP.md','docs/history/seed-focus-2026-10-20/README.md',
    'docs/NEXUS_SEED_SPATIAL_TRANSFER_PROTOCOL.md','docs/NEXUS_SEED_SPATIAL_TRANSFER_RESULTS.md',
    'docs/NEXUS_SEED_READOUT_LEARNING_PROPOSAL.md',
    'docs/NEXUS_EXPERIMENTAL_MODE.md',
    'docs/NEXUS_SEED_NONLINEAR_LEARNING_PROTOCOL.md',
    'docs/NEXUS_SEED_NONLINEAR_LEARNING_RESULTS.md',
    'docs/NEXUS_SEED_BRANCH_CLEANUP.md',
    'docs/NEXUS_SEED_UPDATE_DIAGNOSIS_PROTOCOL.md',
    'docs/NEXUS_SEED_UPDATE_DIAGNOSIS_RESULTS.md',
    'docs/NEXUS_SEED_BOUNDED_CORRECTION_PROTOCOL.md',
    'docs/NEXUS_SEED_BOUNDED_CORRECTION_RESULTS.md',
    'docs/NEXUS_SEED_UPDATE_GATE_PROTOCOL.md',
    'docs/NEXUS_SEED_PREFIX_CONSISTENCY_PROTOCOL.md',
    'docs/NEXUS_SEED_SEQUENTIAL_CONSISTENCY_PROTOCOL.md',
    'docs/NEXUS_SEED_LEARNING_CHOICE_PROTOCOL.md',
    'docs/NEXUS_SHARED_LEARNING_LABS.md',
    'docs/NEXUS_SEED_CONVERSATION_WORKSPACE.md',
    'docs/NEXUS_SEED_FOUNDATION.md','docs/NEXUS_SEED_PHASE1_7_WORKBENCH.md',
    'docs/NEXUS_SEED_INVESTIGATION_REPLICATION_PROTOCOL.md','docs/NEXUS_SEED_INVESTIGATION_REPLICATION_RESULTS.md',
    'docs/NEXUS_SEED_INVESTIGATION_HYBRID_PROTOCOL.md','docs/NEXUS_SEED_INVESTIGATION_HYBRID_RESULTS.md',
    'docs/NEXUS_SEED_INVESTIGATION_TRANSFER_PROTOCOL.md','docs/NEXUS_SEED_INVESTIGATION_TRANSFER_RESULTS.md',
    'docs/NEXUS_SEED_EXECUTABLE_WORLD.md','docs/NEXUS_SEED_EXECUTABLE_WORLD_PROTOCOL.md',
    'docs/NEXUS_SEED_EXECUTABLE_WORLD_RESULTS.md',
    'docs/NEXUS_SEED_QUESTION_SELECTION_PROTOCOL.md',
    'docs/NEXUS_SEED_QUESTION_SELECTION_RESULTS.md',
    'docs/NEXUS_SEED_QUESTION_HEADROOM_PROTOCOL.md',
    'docs/NEXUS_SEED_QUESTION_HEADROOM_RESULTS.md',
    'docs/NEXUS_SEED_QUERY_REPLICATION_PROTOCOL.md',
    'docs/NEXUS_SEED_QUERY_REPLICATION_RESULTS.md',
    'docs/NEXUS_SEED_ANSWER_FREE_UTILITY_PROTOCOL.md',
    'docs/NEXUS_SEED_ANSWER_FREE_UTILITY_RESULTS.md',
    'docs/NEXUS_SEED_QUESTION_UTILITY_PROTOCOL.md',
    'docs/NEXUS_SEED_QUESTION_UTILITY_RESULTS.md',
    'docs/NEXUS_SEED_LEARNING_CHOICE_RESULTS.md',
    'docs/NEXUS_SEED_SEQUENTIAL_CONSISTENCY_RESULTS.md',
    'docs/NEXUS_SEED_PREFIX_CONSISTENCY_RESULTS.md',
    'docs/NEXUS_SEED_UPDATE_GATE_RESULTS.md',
    'docs/NEXUS_SEED_CUMULATIVE_LEARNING_PROTOCOL.md',
    'docs/NEXUS_SEED_CUMULATIVE_LEARNING_RESULTS.md',
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
    for change_path in (root/'artifacts/seed_hybrid_code_changes.json',root/'artifacts/seed_action_code_changes.json',root/'artifacts/seed_contract_code_changes.json',root/'artifacts/seed_contract_document_changes.json',root/'artifacts/seed_plasticity_code_changes.json',root/'artifacts/seed_plasticity_document_changes.json',root/'artifacts/seed_validation_code_changes.json',root/'artifacts/seed_validation_document_changes.json',root/'artifacts/seed_readout_changes.json',root/'artifacts/seed_focus_changes.json',root/'artifacts/seed_transfer_changes.json',root/'artifacts/seed_experimental_changes.json',root/'artifacts/seed_nonlinear_changes.json',root/'artifacts/seed_update_diagnosis_changes.json',root/'artifacts/seed_bounded_changes.json',root/'artifacts/seed_cumulative_changes.json',root/'artifacts/seed_update_gate_changes.json',root/'artifacts/seed_prefix_consistency_changes.json',root/'artifacts/seed_sequential_consistency_changes.json',root/'artifacts/seed_learning_choice_changes.json',root/'artifacts/seed_shared_labs_changes.json',root/'artifacts/seed_question_selection_changes.json',root/'artifacts/seed_question_headroom_changes.json',root/'artifacts/seed_query_replication_changes.json',root/'artifacts/seed_question_utility_changes.json',root/'artifacts/seed_answer_free_utility_changes.json',root/'artifacts/seed_conversation_changes.json',root/'artifacts/seed_structure_changes.json',root/'artifacts/seed_structure_results_changes.json',root/'artifacts/seed_foundation_changes.json',root/'artifacts/seed_investigation_changes.json',root/'artifacts/seed_investigation_results_changes.json',root/'artifacts/seed_hybrid_investigation_changes.json',root/'artifacts/seed_hybrid_investigation_results_changes.json',root/'artifacts/seed_replication_workbench_changes.json',root/'artifacts/seed_replication_workbench_results_changes.json'):
        if not change_path.exists():continue
        change=json.loads(change_path.read_text())
        baseline=hashlib.sha256((root/'artifacts/seed_repository_refresh.json').read_bytes()).hexdigest()
        if change.get('schema')!='seed_explicit_code_evolution_v1' or change.get('baseline_manifest_sha256')!=baseline or type(change.get('changes')) is not dict:
            raise ValueError('invalid_code_evolution_record')
        for name,row in change['changes'].items():
            if name not in protected or set(row)!={'before','after'} or row['before']!=overrides.get(name,protected[name]) or type(row['after']) is not str or not re.fullmatch('[0-9a-f]{64}',row['after']):
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
