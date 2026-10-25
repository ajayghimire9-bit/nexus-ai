"""MBPP v3: natural-language program synthesis on a real external benchmark (974 human-written tasks).

Every task is `text` + `assert f(args) == expected` tests. The solver sees the text and the FIRST
assert only (public); the remaining asserts + challenge asserts are hidden and used only for grading
after an answer is locked. Reference solutions are never read.

Sandbox: candidate code is AST-screened (no dunder attribute access, no eval/exec/open/...),
executed with restricted builtins and an import allow-list, and every executed line event in
candidate frames is charged to the work meter (per-call line budget + wall-clock backstop).

Arms (same tasks, same sandbox, same LLM cost model; every LLM call an arm uses is charged to
that arm even when the engine serves it from its deterministic cache):
  * standalone          - one greedy Qwen completion, returned UNVERIFIED.
  * verified_sampling   - greedy then up to k-1 temperature samples; return the first that passes
                          the public assert (no counterexample feedback, no library).
  * nexus_frozen        - greedy sample, then counterexample-guided (CEGIS) repair prompts carrying
                          the failing assert and the observed result / exception.
  * nexus_evolved       - nexus_frozen + an evolving library of verified helpers (wave24_helpers):
                          execution-based helper composition (no LLM) first, then retrieval of
                          verified exemplars / helpers into the prompt and the execution namespace.
"""
from __future__ import annotations

import ast
import builtins
import copy
import hashlib
import json
import math
import re
import signal
import sys
import types
import warnings
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MBPP = ROOT / "fixtures" / "mbpp"
ALLOWED_IMPORTS = {"re", "math", "cmath", "collections", "heapq", "itertools", "operator", "array", "bisect",
                   "copy", "datetime", "functools", "string", "statistics", "fractions", "decimal", "sys",
                   "typing", "random"}
FORGED_COMPARISON_DEFS = {"__eq__", "__ne__", "__getattribute__", "__getattr__", "__class_getitem__",
                          "__init_subclass__", "__set_name__", "__del__", "__reduce__", "__reduce_ex__"}
BLOCKED_ATTRS = {"__class__", "__bases__", "__base__", "__mro__", "__subclasses__", "__globals__", "__code__",
                 "__closure__", "__builtins__", "__dict__", "__getattribute__", "__reduce__", "__reduce_ex__",
                 "__func__", "__self__", "__loader__", "__spec__", "__import__", "__traceback__", "__frame__",
                 "f_globals", "f_locals", "f_back", "gi_frame", "gi_code", "cr_frame", "tb_frame", "__setattr__",
                 "__delattr__", "__init_subclass__", "__eq__", "__ne__"}
BANNED_NAMES = {"eval", "exec", "compile", "open", "input", "globals", "locals", "vars", "breakpoint",
                "__import__", "memoryview", "help", "exit", "quit", "setattr", "delattr"}
CALL_LINE_BUDGET = 20_000       # 514/515 dev reference solutions fit; non-terminating candidates are cut
CALL_WALL_S = 1.0
EXEC_LINE_BUDGET = 20_000


class Budget(Exception):
    pass


def _alarm(signum, frame):
    raise Budget("wall-clock backstop")


_SYS_STUB = types.SimpleNamespace(maxsize=sys.maxsize, float_info=sys.float_info, maxunicode=sys.maxunicode,
                                  setrecursionlimit=lambda n: None, getrecursionlimit=lambda: 1000,
                                  getsizeof=sys.getsizeof,
                                  version_info=sys.version_info)


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root not in ALLOWED_IMPORTS or level:
        raise ImportError(f"import of {name} not allowed in the MBPP sandbox")
    if root == "sys":
        return _SYS_STUB
    return __import__(name, globals, locals, fromlist, level)


def _safe_getattr(obj, name, *default):
    if name in BLOCKED_ATTRS:
        raise AttributeError("attribute access blocked in the MBPP sandbox")
    return getattr(obj, name, *default)


def _safe_hasattr(obj, name):
    return name not in BLOCKED_ATTRS and hasattr(obj, name)


SAFE_BUILTINS = {k: getattr(builtins, k) for k in dir(builtins)
                 if not k.startswith("_") and k not in BANNED_NAMES and k not in {"getattr", "hasattr", "id"}}
SAFE_BUILTINS.update(__import__=_safe_import, getattr=_safe_getattr, hasattr=_safe_hasattr,
                     __build_class__=builtins.__build_class__, __name__="mbpp_candidate")


def _compile(src, filename, mode="exec"):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return compile(src, filename, mode)


def screen(src):
    """AST screen; returns the parsed module or None (introspection escapes / banned names refused)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in BLOCKED_ATTRS:
            return None
        if isinstance(node, ast.Name) and (node.id in BANNED_NAMES or node.id.startswith("__")):
            return None
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in FORGED_COMPARISON_DEFS:
            return None                     # e.g. a forged __eq__ that would fake a passing assert
    return tree


# --------------------------------------------------------------------------- tasks
@dataclass(frozen=True)
class Test:
    source: str
    func: str
    call: str
    expected: str
    args: tuple          # literal args when they are literals (for fuzzing), else ()


def parse_test(src):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        t = ast.parse(src).body[0].test
    call = t.left
    args = ()
    try:
        args = tuple(ast.literal_eval(a) for a in call.args) if not call.keywords else ()
    except (ValueError, SyntaxError, TypeError):
        args = ()
    return Test(src, call.func.id, ast.unparse(call), ast.unparse(t.comparators[0]), args)


@dataclass
class MbppTask:
    task_id: int
    text: str
    tests: list
    challenge: list
    setup: str

    @property
    def func(self):
        return parse_test(self.tests[0]).func

    @property
    def public(self):
        return [parse_test(self.tests[0])]

    @property
    def hidden(self):
        return [parse_test(t) for t in self.tests[1:] + self.challenge]

    @property
    def all_tests(self):
        return self.public + self.hidden


def load_tasks(kind=None):
    split = json.loads((MBPP / "split.json").read_text())
    out = []
    for line in (MBPP / "mbpp.jsonl").read_text().splitlines():
        r = json.loads(line)
        if kind is None or split[str(r["task_id"])] == kind:
            out.append(MbppTask(r["task_id"], r["text"], r["test_list"], r.get("challenge_test_list") or [],
                                r.get("test_setup_code") or ""))
    return sorted(out, key=lambda t: t.task_id)


def ordered(tasks, salt):
    """Deterministic, outcome-blind task order (sha256 of salt + task id)."""
    return sorted(tasks, key=lambda t: hashlib.sha256(f"{salt}:{t.task_id}".encode()).hexdigest())


# --------------------------------------------------------------------------- execution
class Meter:
    def __init__(self, limit=10**12):
        self.limit, self.total = limit, 0

    def charge(self, n):
        self.total += n
        if self.total > self.limit:
            raise Budget("work budget")


def _traced(fn, meter, budget, filenames=("<candidate>", "<helpers>")):
    lines = [0]

    def tracer(frame, event, arg):
        if frame.f_code.co_filename not in filenames:
            return None
        if event == "line":
            lines[0] += 1
            if lines[0] > budget:
                raise Budget("per-call line budget")
        return tracer
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, CALL_WALL_S)
    with warnings.catch_warnings():          # warnings raised BY candidate code are data, not harness noise
        warnings.simplefilter("ignore")
        sys.settrace(tracer)
        try:
            return fn()
        finally:
            sys.settrace(None)
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
            meter.charge(lines[0] + 1)


def load_namespace(code_src, meter, *, setup="", helpers_src=""):
    """Exec helpers + candidate in a fresh sandbox namespace; None if it fails (charged)."""
    ns = {"__builtins__": SAFE_BUILTINS, "__name__": "mbpp_candidate"}
    try:
        if screen(code_src) is None or (helpers_src and screen(helpers_src) is None):
            return None
        if helpers_src:
            exec(_compile(helpers_src, "<helpers>"), ns)
        code = _compile(code_src, "<candidate>")
        _traced(lambda: exec(code, ns), meter, EXEC_LINE_BUDGET)
        if setup:                       # MBPP harness order: solution, then test setup, then asserts
            exec(_compile(setup, "<setup>"), ns)
    except BaseException as exc:            # noqa: BLE001 - candidate faults are data, Budget included
        if isinstance(exc, KeyboardInterrupt):
            raise
        return None
    return ns


def _short(value, n=160):
    r = repr(value)
    return r if len(r) <= n else r[:n] + "..."


def run_test(ns, test, meter):
    """Returns (status, observed): status in pass / fail / error / budget."""
    if ns is None:
        return ("error", "definition failed")
    try:
        call = _compile(test.call, "<test>", "eval")
        expected = eval(_compile(test.expected, "<test>", "eval"), {"__builtins__": SAFE_BUILTINS, **_test_ns(ns)})
    except Exception as exc:  # malformed benchmark row: counts as failure, never as pass
        return ("error", f"test setup: {type(exc).__name__}")
    try:
        actual = _traced(lambda: eval(call, ns), meter, CALL_LINE_BUDGET)
    except Budget:
        return ("budget", "exceeded the execution budget (possible infinite loop)")
    except RecursionError:
        return ("error", "RecursionError")
    except Exception as exc:
        return ("error", f"{type(exc).__name__}: {str(exc)[:120]}")
    try:
        ok = bool(actual == expected)
    except Exception:
        ok = False
    return ("pass", _short(actual)) if ok else ("fail", _short(actual))


def _test_ns(ns):
    return {k: v for k, v in ns.items() if isinstance(v, types.ModuleType) or v is _SYS_STUB}


def passes(src, tests, meter, *, setup="", helpers_src=""):
    ns = load_namespace(src, meter, setup=setup, helpers_src=helpers_src)
    results = []
    for t in tests:
        r = run_test(ns, t, meter)
        results.append(r)
        if r[0] != "pass":
            break
    return all(r[0] == "pass" for r in results) and len(results) == len(tests), results


def grade(answer_src, task):
    """Hidden grading on an UNCHARGED meter; used only after the answer is locked."""
    if answer_src is None:
        return False
    ok, _ = passes(answer_src, task.all_tests, Meter(), setup=task.setup)
    return ok


# --------------------------------------------------------------------------- prompting
SYSTEM = ("You are an expert Python programmer. Write a correct, self-contained Python solution. "
          "Reply with only the code in one ```python block.")
FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)
PREFIX = "```python\n"
STOP = ("```",)


def extract_code(text, func):
    """Keep imports / defs / classes / constant assignments; drop asserts, prints and demo calls."""
    blocks = FENCE.findall(text)
    if not blocks:                     # unterminated fence (generation stopped at the closing ```)
        m = re.match(r"\s*```(?:python|py)?[ \t]*\n(.*)", text, re.S)
        blocks = [m.group(1) if m else text]
    for block in blocks:
        tree = screen(block)
        lines = block.rstrip().splitlines()
        while tree is None and len(lines) > 1 and _parse_fails(block):
            lines = lines[:-1]          # salvage: drop a trailing line cut off by the token limit
            block = "\n".join(lines)
            tree = screen(block)
        if tree is None:
            continue
        keep = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))
                or (isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) for t in n.targets))]
        if any(isinstance(n, ast.FunctionDef) and n.name == func for n in keep):
            return ast.unparse(ast.Module(keep, []))
    return None


PROMPT_TEST_CHARS = 1200      # very long benchmark asserts are clipped in prompts (never in grading)


def _clip(text, n):
    return text if len(text) <= n else text[:n] + " ..."


def _parse_fails(src):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            ast.parse(src)
        return False
    except (SyntaxError, ValueError):
        return True


def base_prompt(task):
    return f"{task.text}\nYour code should pass this test:\n{_clip(task.public[0].source, PROMPT_TEST_CHARS)}"


def feedback(test, result):
    status, observed = result
    call = _clip(test.call, 300)
    if status == "fail":
        return f"`{call}` returned {observed}, but the expected value is {_clip(test.expected, 300)}."
    if status == "budget":
        return f"`{call}` did not finish: it {observed}."
    return f"`{call}` raised {observed}."


def repair_prompt(task, code, test, result, extra=""):
    return (f"{extra}{base_prompt(task)}\n\nYour previous attempt:\n```python\n{code}\n```\n"
            f"It fails that test: {feedback(test, result)}\nWrite a corrected solution.")


def _row(method, task, answer, *, work, llm_work, calls, stage, **extra):
    return dict(method=method, task_id=task.task_id, plausible=answer is not None,
                correct=grade(answer, task), work=work, llm_work=llm_work, llm_calls=calls, stage=stage,
                answer=answer, **extra)


def _ask(engine, user, *, temperature, seed, purpose, extra_system=""):
    text, row = engine.complete(SYSTEM + extra_system, user, temperature=temperature, seed=seed,
                                purpose=purpose, prefix=PREFIX, stop=STOP)
    return text, engine.work_units(row)


# --------------------------------------------------------------------------- arms
def method_standalone(task, engine):
    text, w = _ask(engine, base_prompt(task), temperature=0.0, seed=0, purpose=f"mbpp:{task.task_id}:greedy")
    code = extract_code(text, task.func)
    return _row("standalone", task, code, work=w, llm_work=w, calls=1, stage="unverified")


def method_verified_sampling(task, engine, *, k=3, temperature=0.8):
    meter, llm = Meter(), 0
    for i in range(k):
        text, w = _ask(engine, base_prompt(task), temperature=0.0 if i == 0 else temperature, seed=i,
                       purpose=f"mbpp:{task.task_id}:{'greedy' if i == 0 else f'sample{i}'}")
        llm += w
        code = extract_code(text, task.func)
        meter.charge(1)
        if code is not None and passes(code, task.public, meter, setup=task.setup)[0]:
            return _row("verified_sampling", task, code, work=meter.total + llm, llm_work=llm, calls=i + 1,
                        stage=f"sample{i}")
    return _row("verified_sampling", task, None, work=meter.total + llm, llm_work=llm, calls=k, stage="none")


# --------------------------------------------------------------------------- strategy allocation
def signature(result):
    """Domain-agnostic failure signature of the last verified attempt."""
    if result is None:
        return "no_code"
    status, observed = result
    if status == "error":
        head = observed.split(":")[0]
        return "error:" + (head if head in ("TypeError", "NameError", "IndexError", "definition failed") else "other")
    return status                       # fail | budget


class StrategyAllocator:
    """Per-signature meta-policy over follow-up proposal strategies, learned from charged dev experience.

    score(action | sig) = posterior success rate (Beta(1,1), backed off to the pooled rate when the
    signature has < 3 trials) / mean measured work of that action; ties -> "resample".
    """
    ACTIONS = ("resample", "cegis")

    def __init__(self, stats=None):
        self.stats = stats or {}

    def record(self, sig, action, success, work):
        s = self.stats.setdefault(sig, {a: [0, 0, 0] for a in self.ACTIONS})
        s[action][0] += int(bool(success))
        s[action][1] += 1
        s[action][2] += int(work)

    def _pooled(self, action):
        succ = sum(v[action][0] for v in self.stats.values())
        n = sum(v[action][1] for v in self.stats.values())
        work = sum(v[action][2] for v in self.stats.values())
        return succ, n, work

    def choose(self, sig):
        best, best_score = "resample", None
        for a in self.ACTIONS:
            succ, n, work = self.stats.get(sig, {}).get(a, [0, 0, 0])
            if n < 3:
                succ, n, work = self._pooled(a)
            if n == 0:
                continue
            score = ((succ + 1) / (n + 2)) / max(1.0, work / n)
            if best_score is None or score > best_score + 1e-12:
                best, best_score = a, score
        return best

    def to_json(self):
        return {k: {a: list(v) for a, v in d.items()} for k, d in self.stats.items()}


def _attempt(task, engine, user, *, temperature, seed, purpose, meter, helpers_src):
    text, w = _ask(engine, user, temperature=temperature, seed=seed, purpose=purpose)
    code = extract_code(text, task.func)
    meter.charge(1)
    if code is None:
        return None, None, w
    ok, results = passes(code, task.public, meter, setup=task.setup, helpers_src=helpers_src)
    if ok:
        return code, ("pass", ""), w
    return code, next(r for r in results if r[0] != "pass"), w


def propose(task, engine, *, k=3, meter=None, library=None, allocator=None, explore=False, temperature=0.8):
    """Greedy proposal, then k-1 follow-ups; every candidate verified on the public test.

    Follow-up strategy: counterexample-guided repair (CEGIS) when no allocator is given, else the
    allocator's choice for the failure signature. explore=True (dev training only) runs BOTH
    strategies on each failure state and records their charged outcomes in the allocator.
    """
    meter = meter or Meter()
    llm, calls, trace = 0, 0, []
    extra, helpers_src, used = ("", "", [])
    if library is not None:
        extra, helpers_src, used = library.context(task, meter)
    user0 = extra + base_prompt(task)
    code, result, w = _attempt(task, engine, user0, temperature=0.0, seed=0, meter=meter, helpers_src=helpers_src,
                               purpose=f"mbpp:{task.task_id}:{'greedy' if not extra else 'greedy+lib'}")
    llm, calls = llm + w, calls + 1
    trace.append("greedy")
    best = code if result == ("pass", "") else None
    last = (code, result)
    for i in range(1, k):
        if best is not None:
            break
        state = last                    # every strategy in this round starts from the same failure state
        sig = signature(state[1] if state[0] is not None else None)
        actions = list(StrategyAllocator.ACTIONS) if explore else \
            ["cegis" if allocator is None else allocator.choose(sig)]
        for action in actions:
            if action == "cegis" and state[0] is not None:
                user = repair_prompt(task, state[0], task.public[0], state[1], extra)
                temp, seed = (0.0, i) if i == 1 else (temperature, i)
            else:                       # resample (also the only option when nothing was extractable)
                action = "resample"
                user, temp, seed = user0, temperature, i
            before = meter.total
            c, r, w = _attempt(task, engine, user, temperature=temp, seed=seed, meter=meter,
                               helpers_src=helpers_src, purpose=f"mbpp:{task.task_id}:{action}{i}")
            llm, calls = llm + w, calls + 1
            trace.append(action)
            ok = r == ("pass", "")
            if allocator is not None and explore:
                allocator.record(sig, action, ok, w + meter.total - before)
            if ok and best is None:
                best = c
            if c is not None and not ok:
                last = (c, r)
    answer = None
    if best is not None:
        answer = library.bundle(best, helpers_src) if library is not None else best
    return answer, dict(work=meter.total + llm, llm_work=llm, calls=calls, trace=trace, library_used=used,
                        stage=trace[-1] if best is not None else "none")


def method_nexus_frozen(task, engine, *, k=3):
    """Untrained NEXUS cascade: greedy -> counterexample-guided repair (no learned state)."""
    answer, info = propose(task, engine, k=k)
    return _row("nexus_frozen", task, answer, work=info["work"], llm_work=info["llm_work"], calls=info["calls"],
                stage=info["stage"], trace=info["trace"])


def method_nexus_evolved(task, engine, library, *, allocator=None, k=3, online=True, explore=False):
    """Learned state from wake-sleep: execution-only helper composition (no LLM) first, then proposals
    whose follow-up strategy comes from the learned allocator; verified answers feed the library."""
    meter = Meter()
    hit = library.compose(task, meter)
    if hit is not None:
        answer, info = hit, dict(work=meter.total, llm_work=0, calls=0, stage="helper_composition",
                                 library_used=[], trace=["compose"])
    else:
        answer, info = propose(task, engine, k=k, meter=meter, library=library, allocator=allocator,
                               explore=explore)
    row = _row("nexus_evolved", task, answer, work=info["work"], llm_work=info["llm_work"], calls=info["calls"],
               stage=info["stage"], trace=info["trace"], library_used=info.get("library_used", []),
               answer_layer=library.layer_of(answer) if answer else 0,
               max_helper_layer=library.max_helper_layer_in(answer) if answer else 0)
    if online and answer is not None:
        # Online growth uses ONLY the public test that already verified the answer (no hidden labels).
        library.add_solution(task, answer, verified_on="public")
    return row
