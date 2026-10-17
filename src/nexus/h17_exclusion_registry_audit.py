"""Read committed configuration metadata, never outcomes or neural modules.

An inventory is not a target selector or proof of a globally complete closed
registry. Coverage is the fetched local/remote ref snapshot, not lost branches.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

import yaml

from nexus.h16_selection_mechanism_diagnosis import number, require, verify_provenance


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    out = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        require(key not in out, f'duplicate configuration key: {key}')
        out[key] = loader.construct_object(value_node, deep=True)
    return out


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def parse_config(text):
    data = yaml.load(text, Loader=UniqueLoader)
    require(type(data) is dict, 'configuration must be a mapping')
    return data


def physics_key(row):
    require(type(row) in (list, tuple) and len(row) == 3, 'physics tuple shape')
    values = tuple(number(v) for v in row)
    require(all(v > 0 for v in values), 'nonpositive physics')
    # Preserve exact decimal inputs. Do not round a new collision into existence.
    return values


def plausible_mcc(row):
    return (type(row) in (list, tuple) and len(row) == 3 and
            all(type(x) in (int, float) for x in row) and
            0.0001 <= row[0] <= 0.01 and 0.0001 <= row[1] <= 0.01 and
            0.01 <= row[2] <= 0.2)


def config_metadata(path, data):
    """Known MCC rows vs conservative ambiguous cross-family exclusions."""
    known = (data.get('source_family') == 'mountaincar_continuous' or
             data.get('target_family') == 'mountaincar_continuous' or
             Path(path).name.startswith(('mcc_', 'mountaincar_continuous_')))
    evidence, bases = [], []

    def visit(mapping, prefix=''):
        for key, value in mapping.items():
            require(type(key) is str, 'non-string config key')
            field = prefix+key
            if type(value) is dict:
                visit(value, field+'.')
            elif key.endswith('_base') and type(value) is int:
                require(0 <= value < 2**32, 'invalid seed base')
                bases.append(dict(field=field, base=value))
            elif key in ('source_physics', 'target_physics', 'eval_physics') and value is not None:
                if known:
                    require(type(value) is list and value, 'missing/malformed MCC physics list')
                    for row in value:
                        evidence.append(dict(field=field, physics=list(physics_key(row)), classification='explicit_mcc'))
                elif type(value) is list:
                    for row in value:
                        if plausible_mcc(row):
                            evidence.append(dict(field=field, physics=list(physics_key(row)), classification='ambiguous_conservative'))
    visit(data)
    return dict(physics=evidence, seed_bases=bases)


def family_metadata(text):
    """Literal committed task rows and keyword defaults, not function calls."""
    tree = ast.parse(text)
    rows = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'rows' for t in node.targets):
            literal = ast.literal_eval(node.value)
            rows.update(physics_key(row) for row in literal)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '_mcc':
            kw = {k.arg:k.value for k in node.keywords}
            if {'gravity','power','max_speed'} <= set(kw):
                try:
                    values = [ast.literal_eval(kw[k]) for k in ('gravity','power','max_speed')]
                except (ValueError, TypeError):
                    continue  # row-index expressions accounted for by literal rows
                rows.add(physics_key(values))
    require(rows, 'MCC task source contains no literal physics')
    return sorted(rows)


def merge_ranges(ranges):
    merged = []
    for low, high in sorted(ranges):
        require(type(low) is int and type(high) is int and 0 <= low <= high < 2**32, 'invalid seed range')
        if merged and low <= merged[-1][1]+1:
            merged[-1][1] = max(merged[-1][1], high)
        else:
            merged.append([low,high])
    return merged


def inventory(root):
    root = Path(root)
    parent = verify_provenance(root)
    git = lambda *args: subprocess.check_output(['git', *args], cwd=root)
    refs = []
    for line in git('for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads', 'refs/remotes').decode().splitlines():
        name, commit = line.split()
        if not name.endswith('/HEAD'):
            refs.append(dict(name=name, commit=commit))
    require(refs, 'no references to audit')
    commits = sorted({r['commit'] for r in refs})
    blobs = {}
    family_path = 'src/nexus/tasks/mountaincar_continuous_family.py'
    for commit in commits:
        for entry in git('ls-tree', '-r', commit, '--', 'configs', family_path).decode().splitlines():
            meta, path = entry.split('\t',1)
            _mode, kind, blob = meta.split()
            if kind != 'blob' or not (path == family_path or path.endswith(('.json','.yaml','.yml'))):
                continue
            blobs.setdefault((path,blob), set()).add(commit)
    inputs, candidates, bases, issues = [], {}, [], []
    def add(key, evidence):
        candidates.setdefault(tuple(key), []).append(evidence)
    for (path, blob), owners in sorted(blobs.items()):
        raw = git('cat-file', 'blob', blob)
        descriptor = dict(path=path, git_blob=blob, sha256=hashlib.sha256(raw).hexdigest(), commits=sorted(owners))
        inputs.append(descriptor)
        try:
            if path == family_path:
                for row in family_metadata(raw.decode()):
                    add(row, dict(path=path,git_blob=blob,field='literal_task_source',classification='explicit_mcc'))
            else:
                data = config_metadata(path, parse_config(raw.decode()))
                for item in data['physics']:
                    add(item['physics'],dict(path=path,git_blob=blob,field=item['field'],classification=item['classification']))
                bases.extend(dict(path=path,git_blob=blob,**item) for item in data['seed_bases'])
        except (ValueError, TypeError, SyntaxError, yaml.YAMLError, UnicodeError) as error:
            issues.append(dict(path=path,git_blob=blob,error=str(error)))
    # Keep the previously reviewed historical exclusion list as additive evidence.
    legacy_path = root/'artifacts/h16_same_state_library_feasibility.json'
    legacy = json.loads(legacy_path.read_text())
    for row in legacy['closed_mcc_physics']:
        add(physics_key(row),dict(path=str(legacy_path.relative_to(root)),field='closed_mcc_physics',classification='historical_inventory'))
    ranges = merge_ranges([(0,999999)] + [(b['base'],min(2**32-1,b['base']+999999)) for b in bases])
    excluded = [dict(physics=list(k), evidence=v) for k,v in sorted(candidates.items())]
    ambiguous = [r['physics'] for r in excluded if not any(e['classification'] in ('explicit_mcc','historical_inventory') for e in r['evidence'])]
    return dict(status='metadata_inventory_only_not_a_lock', target_selected=False,
                locked=False, authorized=False, source_revision=git('rev-parse','HEAD').decode().strip(),
                source_dirty=bool(git('status','--porcelain').strip()),
                ref_snapshot=refs, unique_commits=len(commits), inputs=inputs,
                input_config_blob_count=sum(r['path'] != family_path for r in inputs),
                legacy_inventory_sha256=hashlib.sha256(legacy_path.read_bytes()).hexdigest(),
                excluded_physics=excluded, ambiguous_only_exclusions=ambiguous,
                seed_base_evidence=bases, conservative_seed_reservations=ranges,
                reservation_policy='exclude_0_to_999999_and_each_config_base_plus_999999_inclusive',
                parsing_issues=issues, snapshot_parsed_without_issues=not issues,
                globally_complete_closed_registry=False,
                limitations=['No deleted/unfetched branch or removed historical config coverage guarantee.',
                             'One-million seed windows are conservative metadata reservations, not exact historical RNG enumeration.',
                             'Ambiguous family physics are excluded conservatively, not asserted to be used MCC tasks.',
                             'Manual/implicit physics or seed generation outside configurations requires separate review.'],
                new_environment_steps=0,new_imagined_transitions=0,model_inference_calls=0,training_updates=0,
                ledger_used_s=parent['ledger_used_s'],ledger_remaining_s=parent['ledger_remaining_s'])
