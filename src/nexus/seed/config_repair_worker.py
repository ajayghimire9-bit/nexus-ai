"""Bounded CPython execution of vetted three-module configuration fixtures.

Not a general security sandbox. No unrestricted patches, imports, loops or I/O.
Reuse the historical evaluator's safe builtins, never its scientific tasks.
"""
import ast
import json
from pathlib import Path
import resource
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nexus.seed.blackbox_evaluator_worker import SAFE_BUILTINS, SAFE_AST_NODES

MODULES = ('cfgparse', 'engine', 'app')


def compile_project(files):
    if set(files) != {m+'.py' for m in MODULES} or sum(map(len, files.values())) > 20000:
        raise ValueError('bounded_three_module_project_required')
    trees = {}
    for filename, source in files.items():
        tree = ast.parse(source, filename=filename)
        nodes = list(ast.walk(tree))
        callable_names = {'int', 'max', 'min'} | {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        callable_names |= {a.asname or a.name for n in tree.body if isinstance(n, ast.ImportFrom) for a in n.names}
        if len(nodes) > 300: raise ValueError('ast_size')
        for node in nodes:
            if not isinstance(node, SAFE_AST_NODES+(ast.Is, ast.IsNot, ast.ImportFrom, ast.alias)):
                raise ValueError('forbidden_ast:'+type(node).__name__)
            if isinstance(node, (ast.For, ast.While, ast.ListComp, ast.GeneratorExp)):
                raise ValueError('loop_not_permitted')
            if isinstance(node, ast.Name) and node.id.startswith('__'): raise ValueError('dunder_name')
            if isinstance(node, ast.Attribute) and node.attr != 'get': raise ValueError('attribute_not_get')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id not in callable_names:
                raise ValueError('call_not_allowed:'+node.func.id)
            if isinstance(node, ast.Constant):
                if type(node.value) in (int, float) and abs(node.value) > 1000: raise ValueError('literal_bound')
                if type(node.value) is str and len(node.value) > 128: raise ValueError('literal_bound')
            if isinstance(node, ast.FunctionDef) and (node.decorator_list or node.name.startswith('__')):
                raise ValueError('decorator_or_dunder')
            if isinstance(node, ast.ImportFrom) and (node.module not in MODULES or node.level or any(a.name == '*' for a in node.names)):
                raise ValueError('non_fixture_import')
        if any(not isinstance(n, (ast.FunctionDef, ast.ImportFrom)) for n in tree.body):
            raise ValueError('module_top_level_effect')
        trees[filename[:-3]] = tree
    loaded = {}; loading = set()
    def load(module):
        if module in loaded: return loaded[module]
        if module in loading: raise ValueError('import_cycle')
        loading.add(module)
        namespace = {'__builtins__': {k: SAFE_BUILTINS[k] for k in ('int', 'max', 'min')}}
        body = []
        for node in trees[module].body:
            if isinstance(node, ast.ImportFrom):
                dependency = load(node.module)
                for alias in node.names: namespace[alias.asname or alias.name] = dependency[alias.name]
            else: body.append(node)
        code = compile(ast.Module(body=body, type_ignores=[]), module+'.py', 'exec')
        exec(code, namespace, namespace)
        loaded[module] = namespace; loading.remove(module)
        return namespace
    for module in MODULES: load(module)
    return loaded


def evaluate(payload):
    started = time.perf_counter()
    modules = compile_project(payload['files'])
    compilation_s = time.perf_counter()-started
    t = time.perf_counter(); results = []
    for case in payload['cases']:
        module, function = case['entry'].split('.')
        if module not in MODULES or function.startswith('__'): raise ValueError('entry_not_allowed')
        calls = []
        def profile(frame, event, value):
            if event in ('call', 'return') and frame.f_code.co_filename in {m+'.py' for m in MODULES}:
                calls.append(dict(file=frame.f_code.co_filename, function=frame.f_code.co_name,
                                  event=event, line=frame.f_lineno))
        try:
            if payload.get('trace', False): sys.setprofile(profile)
            actual = modules[module][function](case['input'])
            passed = type(actual) is type(case['expected']) and actual == case['expected']
            results.append(dict(actual=actual, passed=passed, trace=None, calls=calls))
        except Exception as exc:
            results.append(dict(actual=None, passed=False, trace=traceback.format_exc(limit=5), error=type(exc).__name__, calls=calls))
        finally:
            sys.setprofile(None)
    return dict(results=results, compilation_s=compilation_s, tests_s=time.perf_counter()-t,
                internal_s=time.perf_counter()-started)


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024*1024, 1024*1024))
    payload = json.loads(sys.stdin.read(100000))
    if len(payload['cases']) > 32: raise ValueError('case_bound')
    print(json.dumps(evaluate(payload), allow_nan=False))
