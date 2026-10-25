"""Real-program repair arena over vendored QuixBugs (un-authored third-party bugs).

* Programs are real buggy Python functions; tests are the benchmark's own JSON cases.
* Each seed splits a program's tests into public (used for repair) and hidden
  (grading only). A patch is *plausible* if it passes every public test and
  *correct* if it also passes every hidden test.
* Cost = executed Python line events (sys.settrace), charged on every
  candidate evaluation, plus fault-localization coverage runs. Infinite loops
  in buggy/candidate code are cut by a per-call line budget.
* Fixed search: single-edit mutations in source order. Learned search: the
  same mutation space ordered by Ochiai spectrum fault localization on public
  tests x an edit-type prior learned on DEV programs only (cross-program transfer).
"""
from __future__ import annotations

import ast
import copy
import json
import math
import random
import signal
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUIX = ROOT / "fixtures" / "quixbugs"
ALLOWED_IMPORTS = {"heapq", "itertools", "math", "collections", "string", "functools", "copy"}
CALL_LINE_BUDGET = 5_000


CALL_WALL_S = 0.25


class LineBudgetExceeded(Exception):
    pass


def _alarm(signum, frame):
    raise LineBudgetExceeded("per-call wall-clock backstop")


def _safe_import(name, *args, **kw):
    if name.split(".")[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"import of {name} not allowed in repair sandbox")
    return __import__(name, *args, **kw)


SAFE_BUILTINS = {k: getattr(__builtins__, k) if hasattr(__builtins__, k) else __builtins__[k]
                 for k in ("abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int", "isinstance",
                           "iter", "len", "list", "map", "max", "min", "next", "range", "reversed", "set", "sorted",
                           "str", "sum", "tuple", "zip", "ValueError", "IndexError", "KeyError", "Exception",
                           "StopIteration", "ZeroDivisionError", "TypeError", "print", "round", "divmod", "ord", "chr",
                           "frozenset", "object", "super", "property", "staticmethod", "hash", "repr", "pow")}
SAFE_BUILTINS["__import__"] = _safe_import
SAFE_BUILTINS["__build_class__"] = __build_class__ if "__build_class__" in dir(__builtins__) else __builtins__["__build_class__"]


@dataclass
class Program:
    name: str
    source: str
    tests: list
    func: str

    @classmethod
    def load(cls, name):
        src = (QUIX / "python_programs" / f"{name}.py").read_text()
        tests = []
        for line in (QUIX / "json_testcases" / f"{name}.json").read_text().splitlines():
            line = line.strip()
            if line:
                tests.append(json.loads(line))
        tree = ast.parse(src)
        funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        func = name if name in funcs else funcs[0]
        return cls(name, src, tests, func)


def split_names(kind):
    split = json.loads((QUIX / "split.json").read_text())
    return sorted(n for n, v in split.items() if v == kind)


class Meter:
    def __init__(self, limit):
        self.limit, self.total = limit, 0

    def charge(self, n):
        self.total += n
        if self.total > self.limit:
            raise LineBudgetExceeded("repair work budget")


def _equal(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(float(a), float(b), rel_tol=1e-3, abs_tol=1e-3)
        except (TypeError, ValueError):
            return False
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    return a == b


def run_tests(code, func, tests, meter, *, coverage=None, filename="<candidate>", stop_on_fail=False,
              line_budget=None):
    """Run tests; returns list of pass booleans. Every line event is charged."""
    line_budget = CALL_LINE_BUDGET if line_budget is None else line_budget
    ns = {"__builtins__": SAFE_BUILTINS, "__name__": "nexus_repair"}
    try:
        exec(code, ns)
    except Exception:
        return [False] * len(tests)
    fn = ns.get(func)
    results = []
    for args, expected in tests:
        lines = [0]
        covered = set()
        def tracer(frame, event, arg):
            if frame.f_code.co_filename != filename:
                return None
            if event == "line":
                lines[0] += 1
                covered.add(frame.f_lineno)
                if lines[0] > line_budget:
                    raise LineBudgetExceeded("per-call line budget")
            return tracer
        ok = False
        # Wall-clock backstop for work done inside single C-level operations (not line-traced).
        signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, CALL_WALL_S)
        sys.settrace(tracer)
        try:
            out = fn(*copy.deepcopy(args))
            if hasattr(out, "__next__") or (hasattr(out, "__iter__") and not isinstance(out, (list, tuple, str, dict, set))):
                out = list(out)
            ok = _equal(out, expected)
        except LineBudgetExceeded:
            ok = False
        except Exception:
            ok = False
        finally:
            sys.settrace(None)
            signal.setitimer(signal.ITIMER_REAL, 0)
        meter.charge(lines[0] + 1)
        if coverage is not None:
            coverage.append((covered, ok))
        results.append(ok)
        if stop_on_fail and not ok:
            return results + [False] * (len(tests) - len(results))
    return results


# --------------------------------------------------------------------------- mutations
CMP = [ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq]
BIN = [ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Div, ast.Mod, ast.BitXor, ast.BitAnd, ast.BitOr]


@dataclass
class Mutation:
    kind: str
    lineno: int
    path: tuple
    apply: object = field(repr=False)


def _children(node):
    for name, value in ast.iter_fields(node):
        if isinstance(value, list):
            for i, v in enumerate(value):
                if isinstance(v, ast.AST):
                    yield (name, i), v
        elif isinstance(value, ast.AST):
            yield (name, None), value


def _get(tree, path):
    node = tree
    for name, i in path:
        node = getattr(node, name) if i is None else getattr(node, name)[i]
    return node


def _set(tree, path, new):
    parent = _get(tree, path[:-1])
    name, i = path[-1]
    if i is None:
        setattr(parent, name, new)
    else:
        getattr(parent, name)[i] = new


def enumerate_mutations(tree):
    """Single-edit repair space, in source (AST pre-order) order."""
    names_in_scope = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} |
                            {a.arg for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) for a in n.args.args})
    out = []
    def visit(node, path):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            for op in CMP:
                if not isinstance(node.ops[0], op):
                    out.append(Mutation("compare_op", line, path, lambda n, op=op: _replace(n, ops=[op()])))
        if isinstance(node, ast.BinOp):
            for op in BIN:
                if not isinstance(node.op, op):
                    out.append(Mutation("binary_op", line, path, lambda n, op=op: _replace(n, op=op())))
            out.append(Mutation("swap_operands", line, path, lambda n: _replace(n, left=n.right, right=n.left)))
        if isinstance(node, ast.AugAssign):
            for op in BIN:
                if not isinstance(node.op, op):
                    out.append(Mutation("binary_op", line, path, lambda n, op=op: _replace(n, op=op())))
        if isinstance(node, ast.BoolOp):
            alt = ast.Or if isinstance(node.op, ast.And) else ast.And
            out.append(Mutation("bool_op", line, path, lambda n, alt=alt: _replace(n, op=alt())))
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            for d in (1, -1):
                out.append(Mutation("constant_shift", line, path, lambda n, d=d: ast.Constant(n.value + d)))
        if isinstance(node, (ast.Subscript,)) and not isinstance(node.slice, ast.Slice):
            for d in (1, -1):
                out.append(Mutation("index_shift", line, path,
                                    lambda n, d=d: _replace(n, slice=ast.BinOp(n.slice, ast.Add() if d > 0 else ast.Sub(), ast.Constant(1)))))
        if isinstance(node, ast.Call) and len(node.args) >= 2:
            out.append(Mutation("swap_args", line, path, lambda n: _replace(n, args=[n.args[1], n.args[0], *n.args[2:]])))
        if isinstance(node, ast.Call):
            for i, a in enumerate(node.args):
                for d in (1, -1):
                    out.append(Mutation("arg_shift", line, path, lambda n, i=i, d=d: _replace(
                        n, args=[*n.args[:i], ast.BinOp(n.args[i], ast.Add() if d > 0 else ast.Sub(), ast.Constant(1)), *n.args[i + 1:]])))
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            for other in names_in_scope:
                if other != node.id and other not in ("True", "False", "None"):
                    out.append(Mutation("name_replace", line, path, lambda n, other=other: ast.Name(other, ast.Load())))
        if isinstance(node, (ast.If, ast.While)):
            out.append(Mutation("negate_condition", line, path, lambda n: _replace(n, test=ast.UnaryOp(ast.Not(), n.test))))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            out.append(Mutation("remove_not", line, path, lambda n: n.operand))
        for (name, i), child in _children(node):
            visit(child, path + ((name, i),))
            if name in ("body", "orelse") and i is not None and isinstance(child, (ast.Expr, ast.Assign, ast.AugAssign, ast.Return, ast.If)):
                out.append(Mutation("delete_statement", getattr(child, "lineno", 0), path + ((name, i),),
                                    lambda n: ast.Pass()))
    visit(tree, ())
    return out


def _replace(node, **fields):
    new = copy.copy(node)
    for k, v in fields.items():
        setattr(new, k, v)
    return new


def apply_mutation(tree, m):
    t = copy.deepcopy(tree)
    node = _get(t, m.path)
    _set(t, m.path, m.apply(node))
    ast.fix_missing_locations(t)
    return t


# --------------------------------------------------------------------------- fault localization
def ochiai(coverage):
    failed_total = sum(1 for _, ok in coverage if not ok)
    score = defaultdict(float)
    lines = set().union(*(c for c, _ in coverage)) if coverage else set()
    for line in lines:
        ef = sum(1 for c, ok in coverage if line in c and not ok)
        ep = sum(1 for c, ok in coverage if line in c and ok)
        if ef:
            score[line] = ef / math.sqrt(failed_total * (ef + ep))
    return score


@dataclass
class RepairResult:
    program: str
    method: str
    plausible: bool
    correct: bool
    work: int
    candidates_tried: int
    edit_kind: str = None
    edit_line: int = None
    status: str = ""


def split_tests(program, seed):
    """Public tests = one failing test (the bug report) + ~40% of the rest; hidden = remainder."""
    tests = list(program.tests)
    random.Random(f"quix:{program.name}:{seed}").shuffle(tests)
    code = compile(ast.parse(program.source), "<candidate>", "exec")
    passing = run_tests(code, program.func, tests, Meter(10**9))
    failing = [t for t, ok in zip(tests, passing) if not ok]
    if not failing:
        return None, None
    report = failing[0]
    rest = [t for t in tests if t is not report]
    k = max(1, int(len(rest) * 0.4))
    return [report] + rest[:k], rest[k:]


def repair(program, public, hidden, *, learned=False, prior=None, budget=300_000):
    meter = Meter(budget)
    tree = ast.parse(program.source)
    mutations = enumerate_mutations(tree)
    try:
        base_cov = []
        base = run_tests(compile(tree, "<candidate>", "exec"), program.func, public, meter, coverage=base_cov)
        if all(base):
            status = "PUBLIC_TESTS_ALREADY_PASS"
            ok = all(run_tests(compile(tree, "<candidate>", "exec"), program.func, hidden, Meter(10**9)))
            return RepairResult(program.name, "learned" if learned else "fixed", True, ok, meter.total, 0, status=status)
        if learned:
            sus = ochiai(base_cov)
            pri = prior or {}
            mutations.sort(key=lambda m: (-(sus.get(m.lineno, 0.0) + 1e-3) * (pri.get(m.kind, 0.05) + 0.05),
                                          m.lineno))
        for i, m in enumerate(mutations):
            meter.charge(1)  # compile/instantiate
            try:
                code = compile(apply_mutation(tree, m), "<candidate>", "exec")
            except (SyntaxError, ValueError, TypeError):
                continue
            if all(run_tests(code, program.func, public, meter, stop_on_fail=True)):
                correct = all(run_tests(code, program.func, hidden, Meter(10**9)))  # grading only, not charged
                return RepairResult(program.name, "learned" if learned else "fixed", True, correct, meter.total, i + 1,
                                    m.kind, m.lineno, "PLAUSIBLE_PATCH_PASSES_ALL_PUBLIC_TESTS")
        return RepairResult(program.name, "learned" if learned else "fixed", False, False, meter.total, len(mutations),
                            status="NO_SINGLE_EDIT_REPAIR")
    except LineBudgetExceeded:
        return RepairResult(program.name, "learned" if learned else "fixed", False, False, meter.total, -1,
                            status="BUDGET_EXHAUSTED")


def learn_edit_prior(names, seed):
    """Cross-program transfer: which edit kinds repaired DEV programs (hindsight from fixed search)."""
    wins, work = Counter(), 0
    for name in names:
        p = Program.load(name)
        pub, hid = split_tests(p, seed)
        if pub is None or not hid:
            continue
        r = repair(p, pub, hid, learned=True, prior=None)
        work += r.work
        if r.plausible and r.edit_kind:
            wins[r.edit_kind] += 1
    total = sum(wins.values()) or 1
    return {k: v / total for k, v in wins.items()}, work
