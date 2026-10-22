"""Strong source-free repair of a supplied null/default/zero configuration contract.

Reuse RepositoryModel, ordinary exact caches and the existing host. No learner,
new model, invented model outputs, or compulsory candidate search.
"""
import ast
from copy import deepcopy
from dataclasses import dataclass
import difflib
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

from nexus.seed.master.coding import RepositoryModel


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def fixture(spec):
    key, default = spec['key'], spec['default']
    expressions = dict(correct=f'{default} if value is None else value',
                       or_=f'value or {default}', ternary=f'value if value else {default}')
    def statement(mode):
        if mode == 'if': return f'    if not value:\n        value = {default}\n'
        return ''
    parser = spec['parser']
    if parser in ('get_default', 'subscript'):
        body = (f"settings.get({key!r}, {default})" if parser == 'get_default' else f"settings[{key!r}]")
        parser_source = f'def read(settings):\n    return int({body})\n'
    else:
        expression = expressions['or_' if parser == 'or' else 'correct']
        parser_source = f"def read(settings):\n    value = settings.get({key!r})\n"+statement(parser)+f'    return int({expression})\n'
    parser_source += f'\ndef legacy_fallback(value):\n    return value or {default}\n'
    core = spec['core']
    expression = 'max(1, value)' if core == 'floor' else expressions['or_' if core == 'or' else core]
    core_source = f'def consume(value):\n    return {expression}\n'
    caller = spec['caller']
    expression = expressions['or_' if caller == 'or' else 'ternary' if caller == 'ternary' else 'correct']
    app_source = ('from cfgparse import read\nfrom engine import consume\n\ndef run(settings):\n'
                  '    value = read(settings)\n'+statement(caller)+f'    return consume({expression})\n')
    def case(entry, value, expected): return dict(entry=entry, input=value, expected=expected)
    public = [case('app.run', {}, default), case('app.run', {key: 0}, 0),
              case('app.run', {key: 2}, 2), case('app.run', {key: None}, default),
              case('cfgparse.read', {key: 0}, 0), case('engine.consume', 0, 0)]
    final = [case('app.run', value, expected) for value, expected in (
        ({}, default), ({key: None}, default), ({key: 0}, 0), ({key: 1}, 1),
        ({key: '0'}, 0), ({key: '7'}, 7), ({'unrelated': 0}, default), ({key: 12, 'noise': 1}, 12))]
    final += [case('cfgparse.read', {key: None}, default), case('cfgparse.read', {key: '0'}, 0),
              case('engine.consume', 0, 0), case('engine.consume', None, default),
              case('cfgparse.legacy_fallback', 0, default), case('cfgparse.legacy_fallback', 2, 2)]
    task = PublicTask(request=f"Handle {key!r} consistently. Missing or None means {default}; zero remains zero. Parse numeric strings. Preserve unrelated behavior.",
                      files={'cfgparse.py': parser_source, 'engine.py': core_source, 'app.py': app_source}, tests=public)
    return task, final


@dataclass(frozen=True)
class PublicTask:
    request: str
    files: dict
    tests: list


def contract_from_public_tests(task):
    tests = [c for c in task.tests if c['entry'] == 'app.run']
    defaults = {c['expected'] for c in tests if c['input'] == {}}
    keys = {k for c in tests for k in c['input']}
    if len(defaults) != 1 or len(keys) != 1: raise ValueError('contract_not_identified_abstain')
    default, key = next(iter(defaults)), next(iter(keys))
    if type(default) is not int or not 1 <= default <= 16: raise ValueError('bounded_default')
    for value, expected in ((0, 0), (None, default), (2, 2)):
        if not any(c['input'] == {key: value} and type(c['expected']) is int and c['expected'] == expected for c in tests):
            raise ValueError('contract_not_identified_abstain')
    return dict(key=key, default=default)


def evaluate(files, cases, trace=False):
    worker = Path(__file__).with_name('config_repair_worker.py')
    payload = json.dumps(dict(files=files, cases=cases, trace=trace), allow_nan=False)
    started = time.perf_counter()
    proc = subprocess.run([sys.executable, '-I', '-B', str(worker)], input=payload, text=True,
                          capture_output=True, timeout=3)
    elapsed = time.perf_counter()-started
    if proc.returncode: raise RuntimeError('fixture_worker_failed:'+proc.stderr[-500:])
    report = json.loads(proc.stdout)
    report.update(wall_s=elapsed, process_overhead_residual_s=max(0, elapsed-report['internal_s']))
    return report


class NullRepair(ast.NodeTransformer):
    def __init__(self, allowed, contract):
        self.allowed, self.contract, self.active, self.edits = allowed, contract, False, []

    def visit_FunctionDef(self, node):
        previous = self.active; self.active = node.name in self.allowed
        result = self.generic_visit(node) if self.active else node
        self.active = previous
        return result

    def fallback(self, expression, node):
        self.edits.append(dict(line=getattr(node, 'lineno', None), rule='explicit_none_default'))
        return ast.copy_location(ast.IfExp(test=ast.Compare(left=deepcopy(expression), ops=[ast.Is()], comparators=[ast.Constant(None)]),
                           body=ast.Constant(self.contract['default']), orelse=deepcopy(expression)), node)

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if self.active and isinstance(node.op, ast.Or) and len(node.values) == 2 and isinstance(node.values[1], ast.Constant) and node.values[1].value == self.contract['default']:
            return self.fallback(node.values[0], node)
        return node

    def visit_IfExp(self, node):
        self.generic_visit(node)
        if self.active and isinstance(node.test, ast.Name) and isinstance(node.orelse, ast.Constant) and node.orelse.value == self.contract['default']:
            self.edits.append(dict(line=node.lineno, rule='truthiness_to_not_none'))
            node.test = ast.Compare(left=node.test, ops=[ast.IsNot()], comparators=[ast.Constant(None)])
        return node

    def visit_If(self, node):
        self.generic_visit(node)
        if self.active and isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not) and isinstance(node.test.operand, ast.Name):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Assign) and isinstance(node.body[0].value, ast.Constant) and node.body[0].value.value == self.contract['default']:
                self.edits.append(dict(line=node.lineno, rule='not_to_none'))
                node.test = ast.Compare(left=node.test.operand, ops=[ast.Is()], comparators=[ast.Constant(None)])
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if not self.active: return node
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'get' and len(node.args) == 2 and isinstance(node.args[0], ast.Constant) and node.args[0].value == self.contract['key']:
            return self.fallback(ast.Call(func=node.func, args=[node.args[0]], keywords=[]), node)
        if isinstance(node.func, ast.Name) and node.func.id == 'max' and len(node.args) == 2 and isinstance(node.args[0], ast.Constant) and node.args[0].value == 1:
            self.edits.append(dict(line=node.lineno, rule='allow_zero_floor')); node.args[0] = ast.Constant(0)
            node.args[1] = self.fallback(node.args[1], node)
        return node

    def visit_Subscript(self, node):
        self.generic_visit(node)
        if self.active and isinstance(node.slice, ast.Constant) and node.slice.value == self.contract['key']:
            expression = ast.Call(func=ast.Attribute(value=node.value, attr='get', ctx=ast.Load()), args=[node.slice], keywords=[])
            return self.fallback(expression, node)
        return node


class Baseline:
    def __init__(self):
        started = time.perf_counter(); self.cache = {}
        self.construction_s = time.perf_counter()-started

    def solve(self, task):
        started = time.perf_counter(); stages = {}; tools = {}
        t = time.perf_counter(); contract = contract_from_public_tests(task)
        stages['interpretation_s'] = time.perf_counter()-t
        key = digest([task.request, task.files, task.tests, contract])
        t = time.perf_counter(); cached = deepcopy(self.cache.get(key))
        stages['cache_lookup_s'] = time.perf_counter()-t
        if cached:
            return dict(files=cached['files'], edits=cached['edits'], contract=contract, cache_hit=True,
                        cache_key=key, public_receipt_sha256=cached['receipt'],
                        stages=stages, tools=dict(project_subprocesses=0, candidate_plans=0),
                        public_passed=True, wall_s=time.perf_counter()-started, public_receipt_reused=True)
        t = time.perf_counter(); model = RepositoryModel(); graph = model.index_files(task.files)
        # Source search and dependency navigation are available to the baseline.
        search_hits = {path: [i+1 for i, line in enumerate(source.splitlines()) if contract['key'] in line]
                       for path, source in task.files.items()}
        stages['source_index_search_s'] = time.perf_counter()-t
        original = evaluate(task.files, task.tests, trace=True)
        t = time.perf_counter(); reachable = {'run'} | {call['function'] for r in original['results'] for call in r['calls']}
        while True:
            grown = reachable | {edge['callee'] for edge in graph['call_graph'] if edge['caller'].split(':')[-1] in reachable}
            if grown == reachable: break
            reachable = grown
        stages['fault_localization_s'] = time.perf_counter()-t
        t = time.perf_counter(); repaired = {}; edits = []
        for path, source in task.files.items():
            transformer = NullRepair(reachable, contract)
            tree = ast.fix_missing_locations(transformer.visit(ast.parse(source)))
            repaired[path] = ast.unparse(tree)+'\n' if transformer.edits else source
            edits.extend(dict(path=path, **edit) for edit in transformer.edits)
        stages['patch_construction_s'] = time.perf_counter()-t
        checked = evaluate(repaired, task.tests)
        passed = all(r['passed'] for r in checked['results'])
        t = time.perf_counter()
        receipt = digest([repaired, task.tests, checked['results']])
        if passed: self.cache[key] = dict(files=deepcopy(repaired), edits=deepcopy(edits), receipt=receipt)
        stages['cache_retention_s'] = time.perf_counter()-t
        tools.update(project_subprocesses=2, candidate_plans=1)
        return dict(files=repaired, edits=edits, contract=contract, cache_hit=False, stages=stages, tools=tools,
                    cache_key=key, public_receipt_sha256=receipt,
                    public_passed=passed, original_public=original, patched_public=checked,
                    search_hits=search_hits, reachable=sorted(reachable), graph=graph,
                    wall_s=time.perf_counter()-started, public_receipt_reused=False)


def run(config, emit):
    baseline = Baseline()
    for spec in config['tasks']:
        public, private = fixture(spec)
        try:
            outcome = baseline.solve(public)
            locked_hash = digest(outcome['files'])
            # Assessment is invoked only AFTER solve returns. Never feed it back.
            assessed = evaluate(outcome['files'], private)
            diff = {path: ''.join(difflib.unified_diff(public.files[path].splitlines(True), outcome['files'][path].splitlines(True), fromfile=path, tofile=path)) for path in public.files}
            emit(dict(kind='task', id=spec['id'], cohort=spec['cohort'], public=public.__dict__,
                      locked_patch_sha256=locked_hash, assessment_cases=private, assessment=assessed,
                      final_passed=all(r['passed'] for r in assessed['results']), patch=diff, **outcome))
        except Exception as exc:
            emit(dict(kind='task', id=spec['id'], cohort=spec['cohort'], failure=type(exc).__name__+':'+str(exc), final_passed=False))
    emit(dict(kind='cache', entries=len(baseline.cache), serialized_bytes=len(json.dumps(baseline.cache).encode()),
              construction_s=baseline.construction_s,
              model_calls=0, training_updates=0, new_environment_steps=0, learned_abstractions=0))


def summarize(records, config):
    tasks = [r for r in records if r.get('kind') == 'task']
    expected = {t['id'] for t in config['tasks']}
    complete = len(tasks) == len(expected) and {r['id'] for r in tasks} == expected and sum(r.get('kind') == 'cache' for r in records) == 1
    if not complete: return dict(declared_complete=False, verdict='INCOMPLETE', ready_for_learning_study=False)
    primary = [r for r in tasks if r['cohort'] == 'primary']
    if any('failure' in r for r in tasks):
        return dict(declared_complete=False, verdict='INVALID_OR_INCOMPLETE', failures=[r for r in tasks if 'failure' in r], ready_for_learning_study=False)
    discovery_keys = ('source_index_search_s', 'fault_localization_s', 'patch_construction_s')
    discoveries = [sum(r['stages'][k] for k in discovery_keys) for r in primary]
    for row in tasks:
        if any(type(v) not in (int, float) or not 0 <= v < float('inf') for v in row['stages'].values()):
            return dict(declared_complete=False, verdict='INVALID', ready_for_learning_study=False)
    accuracy = sum(r['final_passed'] for r in primary)/len(primary)
    median = statistics.median(discoveries)
    fraction = sum(discoveries)/sum(r['wall_s'] for r in primary)
    screen = config['screen']
    passed = accuracy >= screen['minimum_accuracy'] and median >= screen['minimum_discovery_s'] and fraction >= screen['minimum_discovery_fraction']
    return dict(declared_complete=True, primary_tasks=len(primary), total_tasks=len(tasks), primary_accuracy=accuracy,
                all_final_passed=sum(r['final_passed'] for r in tasks), median_discovery_s=median,
                discovery_fraction_of_repair_wall=fraction, practical_headroom_passed=passed,
                cache_hits=sum(r['cache_hit'] for r in tasks), model_calls=0,
                verdict='PREPARE_SEPARATE_LEARNING_COMPARISON' if passed else 'NO_PRACTICAL_DISCOVERY_HEADROOM',
                ready_for_learning_study=False)
