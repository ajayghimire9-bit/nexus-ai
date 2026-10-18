"""Bound historical seed expressions as data; never import experiment modules.

This deliberately narrow interpreter rejects unsupported syntax. Its certificates
cover registry expressions, not a claim that every RNG call uses a registry.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

from nexus.h16_selection_mechanism_diagnosis import require, verify_provenance
from nexus.h17_exclusion_coverage_review import (
    REGISTRY, REGISTRY_SHA, artifact_metadata, contains,
)
from nexus.h17_exclusion_registry_audit import parse_config
from nexus.h17_protocol_readiness import CONFIG, validate_draft

PARENT = 'artifacts/h17_exclusion_coverage_review_validated.json'
PARENT_SHA = '0d3fe10e12fb5117c3d8c06ae7a8f54e5aba8faccae2f5ab1084882b85b25b1c'
FUNCTIONS = {'seed_groups', 'seed_streams', 'check_seeds'}
LIMIT = 1000000


class Unsupported(ValueError):
    pass


class Arithmetic:
    """Integer arithmetic/comprehensions only, with a shared operation cap."""

    def __init__(self, text):
        self.tree = ast.parse(text)
        self.functions = {n.name:n for n in self.tree.body if isinstance(n, ast.FunctionDef)}
        self.constants = {}
        self.operations = 0
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name): self.constants[target.id] = value

    def expression(self, node, env, depth=0):
        self.operations += 1
        if self.operations > LIMIT or depth > 20:
            raise Unsupported('arithmetic resource bound exceeded')
        def e(n): return self.expression(n, env, depth+1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, str): return node.value
        if isinstance(node, ast.Name):
            if node.id in env: return env[node.id]
            if node.id in self.constants: return self.constants[node.id]
        if isinstance(node, ast.Subscript): return e(node.value)[e(node.slice)]
        if isinstance(node, (ast.Tuple, ast.List)): return tuple(e(n) for n in node.elts)
        if isinstance(node, ast.Dict): return {e(k):e(v) for k,v in zip(node.keys,node.values)}
        if isinstance(node, ast.BinOp):
            left, right = e(node.left), e(node.right)
            if isinstance(node.op, ast.BitOr) and type(left) is set and type(right) is set: return left | right
            if type(left) is int and type(right) is int:
                if isinstance(node.op, ast.Add): return left+right
                if isinstance(node.op, ast.Sub): return left-right
                if isinstance(node.op, ast.Mult): return left*right
        if isinstance(node, ast.SetComp):
            result = set()
            def walk(i, scope):
                if i == len(node.generators):
                    value = self.expression(node.elt, scope, depth+1)
                    if type(value) is not int: raise Unsupported('seed is not an integer')
                    result.add(value)
                    return
                gen = node.generators[i]
                if gen.ifs or gen.is_async or not isinstance(gen.target, ast.Name):
                    raise Unsupported('filtered/complex comprehension')
                for value in self.expression(gen.iter, scope, depth+1):
                    walk(i+1, dict(scope, **{gen.target.id:value}))
            walk(0, env)
            return result
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            args = [e(n) for n in node.args]
            if name == 'range' and all(type(v) is int for v in args):
                r = range(*args)
                if len(r) > 10000: raise Unsupported('range bound exceeded')
                return r
            if name == 'int' and len(args) == 1 and type(args[0]) is int: return args[0]
            if name == 'set' and not args: return set()
            # Inline only a local arithmetic return. Never execute a function.
            fn = self.functions.get(name)
            if fn and len(args) == len(fn.args.args):
                returns = [n for n in fn.body if isinstance(n, ast.Return)]
                if len(returns) == 1 and all(isinstance(n,(ast.If,ast.Return,ast.Expr)) for n in fn.body):
                    return self.expression(returns[0].value, dict(zip((a.arg for a in fn.args.args),args)), depth+1)
        raise Unsupported('unsupported expression: '+ast.dump(node)[:180])

    def registry(self, name, cfg):
        """Extract own streams only. Imported blocked-set checks are not run."""
        fn = self.functions[name]
        env = {'cfg':cfg}
        if name == 'check_seeds':
            relevant = [n for n in fn.body if isinstance(n,(ast.Assign,ast.AugAssign))
                        and isinstance(n.targets[0] if isinstance(n,ast.Assign) else n.target,ast.Name)
                        and (n.targets[0] if isinstance(n,ast.Assign) else n.target).id == 'used']
        else:
            relevant = [n for n in fn.body if isinstance(n,(ast.Assign,ast.Return))]
        out = None
        for node in relevant:
            if isinstance(node,ast.Return):
                out = env['streams'] if 'streams' in env else self.expression(node.value,env)
                break
            if isinstance(node,ast.Assign):
                if len(node.targets) != 1 or not isinstance(node.targets[0],ast.Name):
                    raise Unsupported('complex registry assignment')
                target = node.targets[0].id
                # stream union is only bookkeeping after the streams dict.
                if target == 'used' and 'streams' in env: continue
                env[target] = self.expression(node.value,env)
            else:
                if not isinstance(node.op,ast.BitOr): raise Unsupported('unexpected update')
                env[node.target.id] |= self.expression(node.value,env)
        if 'streams' in env: out = env['streams']
        if name == 'check_seeds': out = env.get('used')
        def flatten(value):
            if isinstance(value,dict): return set().union(*(flatten(v) for v in value.values()))
            if isinstance(value,tuple): return set().union(*(flatten(v) for v in value))
            if type(value) is set and all(type(v) is int for v in value): return value
            raise Unsupported('no self-contained own-seed expression')
        return flatten(out)


def _config_path(tree):
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CONFIG' for t in node.targets):
            value = node.value
            if isinstance(value,ast.Call) and isinstance(value.func,ast.Name) and value.func.id=='Path' and len(value.args)==1:
                path = ast.literal_eval(value.args[0])
                if type(path) is str and path.startswith('configs/'): return path
    raise Unsupported('literal configuration path unavailable')


def certify(text, cfg, ranges, function):
    engine = Arithmetic(text)
    values = engine.registry(function,cfg)
    require(bool(values),'empty registry cannot certify a reservation')
    outside = sorted(v for v in values if not contains(ranges,v))
    digest = hashlib.sha256(json.dumps(sorted(values),separators=(',',':')).encode()).hexdigest()
    return dict(count=len(values),minimum=min(values),maximum=max(values),seed_set_sha256=digest,
                outside_reservations=outside,operations=engine.operations)


def review(root):
    root = Path(root)
    ledger = verify_provenance(root)
    def checked(path, digest):
        raw = (root/path).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==digest,'parent hash mismatch: '+path)
        return json.loads(raw)
    parent = checked(PARENT,PARENT_SHA)
    old = checked(REGISTRY,REGISTRY_SHA)
    excluded = {tuple(r['physics']) for r in old['excluded_physics']}
    git = lambda *args: subprocess.check_output(['git',*args],cwd=root)
    certificates, failures, metadata, issues = [], [], [], []
    # Bind source and config to the same historical commit, never pair arbitrary
    # current configs with historical formulas.
    for row in parent['all_reachable_inputs']:
        path, blob, commit = row['path'],row['git_blob'],row['reachable_commit']
        if path.endswith('.py'):
            text = git('cat-file','blob',blob).decode()
            tree = ast.parse(text)
            names = {n.name for n in tree.body if isinstance(n,ast.FunctionDef)} & FUNCTIONS
            for name in sorted(names):
                record = dict(path=path,git_blob=blob,commit=commit,function=name)
                try:
                    cfgpath = _config_path(tree)
                    raw = git('show',commit+':'+cfgpath)
                    cfg = parse_config(raw.decode())
                    record.update(config_path=cfgpath,config_sha256=hashlib.sha256(raw).hexdigest())
                    record.update(certify(text,cfg,old['conservative_seed_reservations'],name))
                    certificates.append(record)
                except (Unsupported,ValueError,KeyError,TypeError,subprocess.CalledProcessError) as error:
                    failures.append(dict(**record,error=str(error)))
        elif path.startswith('artifacts/') and path.endswith('.json'):
            raw = git('cat-file','blob',blob)
            try:
                data = json.loads(raw)
                rows = artifact_metadata(data)
                # Record root schema even when no recognized physics field is
                # present. This is NOT a completeness attestation for that file.
                metadata.append(dict(path=path,git_blob=blob,sha256=hashlib.sha256(raw).hexdigest(),
                                     root_keys=sorted(data) if type(data) is dict else [],physics=rows))
            except (ValueError,TypeError) as error:
                issues.append(dict(path=path,git_blob=blob,error=str(error)))
    manual = []
    for row in parent['unversioned_manual_files']:
        file = Path(row['worktree'])/row['path']
        raw = file.read_bytes()
        require(hashlib.sha256(raw).hexdigest()==row['sha256'],'manual reservation changed: '+str(file))
        record = dict(path=row['path'],sha256=row['sha256'],status='observed_reserved_not_authorized')
        if 'metadata' in row: record['reservation_metadata'] = row['metadata']
        manual.append(record)
    require(len(manual)==7,'expected seven manual-reservation files')
    require(len({r['worktree'] for r in parent['unversioned_manual_files']})==1,
            'manual reservation must bind one worktree')
    manual_root = Path(parent['unversioned_manual_files'][0]['worktree'])
    manual_source = (manual_root/'src/nexus/world/xenv_context_adaptation.py').read_text()
    manual_config = (manual_root/'configs/xenv_context_adaptation.yaml').read_bytes()
    manual_certificate = certify(manual_source,parse_config(manual_config.decode()),
                                 old['conservative_seed_reservations'],'check_seeds')
    novel = sorted({tuple(r['physics']) for m in metadata for r in m['physics']} - excluded)
    # Do not turn incomplete static expression extraction or recognized-field
    # scanning into an unsupported global closure claim.
    return dict(verdict='BLOCKED_INCOMPLETE_EXCLUSION_COVERAGE',
                starting_sha='bc3cef2be5de5b9a028d7cab5e81544c015b2550',
                source_revision=git('rev-parse','HEAD').decode().strip(),
                parent_sha256=PARENT_SHA,registry_sha256=REGISTRY_SHA,
                historical_seed_certificates=certificates,unsupported_seed_functions=failures,
                artifact_metadata=metadata,artifact_parse_issues=issues,
                novel_metadata_physics=[list(v) for v in novel],manual_reservation_files=manual,
                manual_own_seed_certificate=manual_certificate,
                scope='fixed parent reachable-history snapshot; recognized metadata and explicit registry expressions',
                remaining_gaps=[
                    'Unsupported function records are enumerated with historical blobs/configuration bindings; no fallback values are invented.',
                    'Registry certificates do not certify that every historical RNG call is routed through its registry, including inherited older seed helpers.',
                    'All artifact schemas are now inventoried, but unrecognized registration fields require semantic classification.',
                    'Manual draft is portably recorded as reserved, not finalized or canceled; its owner/worktree remains unchanged.',
                    'Deleted/unfetched branches and unpublished external registrations cannot be certified from the available object graph.'
                ],
                existing_exclusions_preserved=sorted(map(list,excluded)),
                proposed_budget=validate_draft(json.loads((root/CONFIG).read_text())),
                ledger_used_s=ledger['ledger_used_s'],ledger_remaining_s=ledger['ledger_remaining_s'],
                target_selected=False,numerical_seeds_registered=False,locked=False,authorized=False,
                new_environment_steps=0,new_imagined_transitions=0,training_updates=0,model_inference_calls=0)
