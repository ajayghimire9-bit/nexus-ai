"""H17 source-only coverage review. No physics/seed selection or execution.

Scanners identify evidence, not prove absence of implicit registrations.
Fail closed if bound/completeness evidence has not been reconciled.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

import yaml

from nexus.h16_selection_mechanism_diagnosis import load_json, require, verify_provenance
from nexus.h17_exclusion_registry_audit import config_metadata, parse_config, plausible_mcc
from nexus.h17_protocol_readiness import CONFIG, seed_keys, validate_draft

BASE = '4a86031542229dbe738067c1d34532a553b1d69a'
REGISTRY = 'artifacts/h17_exclusion_registry_audit_validated.json'
REGISTRY_SHA = 'd823e9fd703076b543edeb74fc2c069282f92b9b7816cf6513bd0f01b6c9ef32'
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
TRIPLE = re.compile(r'[\[(]\s*('+NUMBER+r')\s*,\s*('+NUMBER+r')\s*,\s*('+NUMBER+r')\s*[\])]')


def contains(ranges, value):
    return any(lo <= value <= hi for lo,hi in ranges)


def literal_source_evidence(text):
    """Literal physics hints and dynamic RNG-registry functions, never eval."""
    tree = ast.parse(text)
    physics, blocks, unresolved = [], [], []
    for node in ast.walk(tree):
        if isinstance(node,(ast.List,ast.Tuple)) and len(node.elts) == 3:
            try:
                value = ast.literal_eval(node)
            except (ValueError,TypeError):
                pass
            else:
                if plausible_mcc(value):
                    physics.append(dict(line=node.lineno,physics=list(value)))
        if isinstance(node,ast.Assign):
            names = [t.id for t in node.targets if isinstance(t,ast.Name)]
            if any('BLOCK' in name or 'SEED' in name or name.endswith('_base') for name in names):
                for item in ast.walk(node.value):
                    if isinstance(item,ast.Constant) and type(item.value) is int and 1000000 <= item.value < 2**32:
                        blocks.append(dict(line=item.lineno,value=item.value,assignment=names))
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in ('seed_groups','seed_streams','check_seeds'):
            # The old million-wide base windows were not checked against these
            # functions' actual generated sets or maximum offsets.
            unresolved.append(dict(line=node.lineno,function=node.name,
                                   body_sha256=hashlib.sha256(ast.dump(node).encode()).hexdigest()))
    return dict(physics=physics,seed_block_literals=blocks,seed_registry_functions=unresolved)


def document_evidence(text):
    """Only metadata tuples/seed reservations; never performance comparisons."""
    rows, manual = [], []
    for i,line in enumerate(text.splitlines(),1):
        for match in TRIPLE.finditer(line):
            row = [float(x) for x in match.groups()]
            if plausible_mcc(row):
                rows.append(dict(line=i,physics=row))
        if re.search(r'(seed|block|reserv|manual|uncommitted)',line,re.I):
            # Preserve evidence text: an open '+' is not a bounded interval.
            if re.search(r'\d[\d,_]{5,}\+?',line):
                manual.append(dict(line=i,text=line.strip()[:400]))
    return dict(physics=rows,manual_seed_lines=manual)


def artifact_metadata(data):
    """Read registration fields only; do not traverse raw/cell result metrics."""
    rows = []
    wrappers = {'provenance','config','configuration','metadata','tasks','splits','models','checkpoints','manifest'}
    fields = {'target_physics','source_physics','eval_physics','closed_mcc_physics','physics'}
    def visit(value,prefix=''):
        if type(value) is list:
            for i,item in enumerate(value):
                if type(item) in (dict,list): visit(item,prefix+f'[{i}].')
        elif type(value) is dict:
            for key,item in value.items():
                if key in fields:
                    candidates = [item] if plausible_mcc(item) else item if type(item) is list else []
                    for row in candidates:
                        if plausible_mcc(row): rows.append(dict(field=prefix+key,physics=list(row)))
                elif key in wrappers:
                    visit(item,prefix+key+'.')
    visit(data)
    return rows


def coverage_verdict(*, provenance_ok, new_physics, parse_issues,
                     unresolved_seed_functions, unversioned_manual_files,
                     closure_attested=False):
    if not provenance_ok:
        return 'BLOCKED_PROVENANCE_MISMATCH'
    if new_physics or parse_issues or unresolved_seed_functions or unversioned_manual_files or not closure_attested:
        return 'BLOCKED_INCOMPLETE_EXCLUSION_COVERAGE'
    return 'READY_FOR_SEPARATE_TARGET_SEED_REGISTRATION'


def review(root):
    root = Path(root)
    parent = verify_provenance(root)
    raw = (root/REGISTRY).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == REGISTRY_SHA, 'validated registry provenance mismatch')
    old = json.loads(raw)
    excluded = {tuple(row['physics']) for row in old['excluded_physics']}
    budget = validate_draft(load_json(root/CONFIG))
    git = lambda *args: subprocess.check_output(['git',*args],cwd=root)
    git('merge-base','--is-ancestor',BASE,'HEAD')
    require(git('rev-parse','--is-shallow-repository').strip() == b'false', 'shallow history cannot establish coverage')
    commits = git('rev-list','--all').decode().splitlines()
    objects = {}
    for commit in commits:
        for line in git('ls-tree','-r',commit,'--','configs','src','scripts','docs','artifacts','README.md','AGENTS.md').decode().splitlines():
            meta,path = line.split('\t',1)
            _mode,kind,blob = meta.split()
            if kind == 'blob' and path.endswith(('.json','.yaml','.yml','.py','.md')):
                objects.setdefault((path,blob),commit)
    old_inputs = {(r['path'],r['git_blob']) for r in old['inputs']}
    descriptors, config_new, physics, blocks, unresolved, issues, manual_lines = [], [], [], [], [], [], []
    counts = dict(config=0,python=0,document=0,artifact_indexed=0,artifact_metadata_read=0)
    for (path,blob),commit in sorted(objects.items()):
        category = ('config' if path.startswith('configs/') else 'python' if path.endswith('.py') else
                    'artifact_indexed' if path.startswith('artifacts/') else 'document')
        counts[category] += 1
        descriptor = dict(path=path,git_blob=blob,reachable_commit=commit)
        descriptors.append(descriptor)
        # Index all JSON result/manifests; extract only MCC-specific metadata
        # or named manifests, without interpreting any performance fields.
        read_artifact = category == 'artifact_indexed' and (
            Path(path).name.startswith(('mcc_','xenv_','h14_','h15_','h16_','mountaincar_continuous_')) or
            'manifest' in path.lower() or 'provenance' in path.lower())
        if category == 'artifact_indexed' and not read_artifact:
            continue
        data = git('cat-file','blob',blob)
        descriptor['sha256'] = hashlib.sha256(data).hexdigest()
        try:
            if category == 'config':
                rows = config_metadata(path,parse_config(data.decode()))
                if (path,blob) not in old_inputs: config_new.append(dict(path=path,git_blob=blob))
                for row in rows['physics']: physics.append(dict(path=path,git_blob=blob,**row))
                blocks.extend(dict(path=path,git_blob=blob,value=r['base'],field=r['field']) for r in rows['seed_bases'])
            elif category == 'python':
                text = data.decode()
                if not re.search(r'mcc|mountaincar_continuous|MountainCarContinuous',text):
                    continue
                rows = literal_source_evidence(text)
                physics.extend(dict(path=path,git_blob=blob,**r) for r in rows['physics'])
                blocks.extend(dict(path=path,git_blob=blob,**r) for r in rows['seed_block_literals'])
                unresolved.extend(dict(path=path,git_blob=blob,**r) for r in rows['seed_registry_functions'])
            elif category == 'document':
                text = data.decode()
                if not re.search(r'mcc|mountaincar_continuous|MountainCarContinuous',text,re.I):
                    continue
                rows = document_evidence(text)
                physics.extend(dict(path=path,git_blob=blob,**r) for r in rows['physics'])
                manual_lines.extend(dict(path=path,git_blob=blob,**r) for r in rows['manual_seed_lines'])
            else:
                counts['artifact_metadata_read'] += 1
                physics.extend(dict(path=path,git_blob=blob,**r) for r in artifact_metadata(json.loads(data)))
        except (ValueError,TypeError,SyntaxError,UnicodeError,yaml.YAMLError) as error:
            issues.append(dict(path=path,git_blob=blob,error=str(error)))
    # Named active worktrees: capture only reservation metadata, never modify.
    manual_files, worktree_status = [], []
    worktrees = [line[9:] for line in git('worktree','list','--porcelain').decode().splitlines() if line.startswith('worktree ')]
    for folder in worktrees:
        status = subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=folder).decode()
        worktree_status.append(dict(path=folder,status_porcelain=status))
        for line in status.splitlines():
            path = line[3:]
            if 'xenv_context_adaptation' not in path.lower() or not path.endswith(('.yaml','.json','.md','.py')):
                continue
            file = Path(folder)/path
            if not file.is_file(): continue
            data = file.read_bytes()
            row = dict(worktree=folder,path=path,sha256=hashlib.sha256(data).hexdigest(),status=line[:2])
            if path.endswith('.yaml'):
                row['metadata'] = config_metadata(path,parse_config(data.decode()))
            manual_files.append(row)
    novel = sorted({tuple(r['physics']) for r in physics} - excluded)
    uncovered_blocks = [r for r in blocks if not contains(old['conservative_seed_reservations'],r['value'])]
    verdict = coverage_verdict(provenance_ok=True,new_physics=novel,parse_issues=issues,
                               unresolved_seed_functions=unresolved,unversioned_manual_files=manual_files)
    return dict(verdict=verdict,base_sha=BASE,source_revision=git('rev-parse','HEAD').decode().strip(),
                registry_sha256=REGISTRY_SHA,reachable_commits=len(commits),counts=counts,
                all_reachable_inputs=descriptors,historical_configs_absent_from_previous_tip_inventory=config_new,
                existing_exclusions_preserved=[list(k) for k in sorted(excluded)],
                literal_or_metadata_physics_not_in_registry=[list(k) for k in novel],
                physics_evidence=physics,seed_evidence=blocks,uncovered_seed_literals=uncovered_blocks,
                unresolved_seed_registry_functions=unresolved,manual_reservation_lines=manual_lines,
                unversioned_manual_files=manual_files,parsing_issues=issues,
                worktree_status=worktree_status,
                symbolic_seed_keys=len(seed_keys()),numerical_registration_safe=False,
                proposed_budget=budget,proposed_cap_s=300,
                blockers=['Historical seed-function range bounds have not been certified against the old conservative windows.',
                          'The named uncommitted Cline reservation has no portable committed snapshot/owner closure record.',
                          'Artifact indexing/metadata extraction and literal scans do not certify implicit registrations outside recognized fields.'],
                ledger_used_s=parent['ledger_used_s'],ledger_remaining_s=parent['ledger_remaining_s'],
                new_environment_steps=0,new_imagined_transitions=0,model_inference_calls=0,training_updates=0,
                target_selected=False,numerical_seeds_registered=False,locked=False,authorized=False)
