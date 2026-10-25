"""QuixBugs repair v3: Qwen-1.5B proposals + exact sandbox verification + differential twin fuzzing.

Methods (same programs, same public/hidden split, same sandbox):
  * mutation_search   - unguided single-edit mutation search in source order (baseline).
  * qwen_standalone   - Qwen's greedy whole-function repair, returned UNVERIFIED (baseline).
  * nexus_qwen        - Ochiai fault localization in the prompt, k Qwen samples + FL-ordered
                        mutation patches, every candidate verified on the public tests, then a
                        Qwen-written *twin* (from the docstring only, never from the buggy code)
                        and fuzzed boundary inputs rank plausible patches: patches that disagree
                        with a public-test-validated twin are demoted (overfitting filter).
Work = executed Python line events (all candidates, twin, fuzz) + LLM work units
(1 per evaluated prompt token + 4 per generated token). Hidden tests are used only for grading.
"""
from __future__ import annotations

import ast
import copy
import difflib
import random
import re

from nexus.wave24_code_repair import (
    LineBudgetExceeded, Meter, Program, apply_mutation, enumerate_mutations, ochiai, run_tests,
)

SYSTEM = ("You are an expert Python programmer who repairs buggy functions. Reply with the complete corrected "
          "function inside one ```python code block and nothing else.")
TWIN_SYSTEM = ("You are an expert Python programmer. Implement the requested function correctly. Reply with the "
               "complete function inside one ```python code block and nothing else.")
FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.S)


def split_source(src):
    """Code part and the module docstring (QuixBugs keeps the spec in a trailing string literal)."""
    tree = ast.parse(src)
    doc = "\n".join(n.value.value for n in tree.body if isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant)
                    and isinstance(n.value.value, str))
    code = "\n".join(ast.get_source_segment(src, n) for n in tree.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)))
    return code, doc.strip()


def extract_function(text, func):
    blocks = FENCE.findall(text) or [text]
    for block in blocks:
        try:
            tree = ast.parse(block)
        except SyntaxError:
            continue
        keep = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Import, ast.ImportFrom, ast.Assign))]
        if any(isinstance(n, ast.FunctionDef) and n.name == func for n in keep):
            return ast.unparse(ast.Module(keep, []))
    return None


def _fmt_test(t):
    args, expected = t
    return f"{', '.join(map(repr, args))} -> {expected!r}"


def repair_prompt(program, public, suspicious=None):
    code, doc = split_source(program.source)
    lines = code.splitlines()
    parts = [f"Specification:\n{doc}\n", f"Buggy code:\n```python\n{code}\n```",
             "Failing test (input -> expected output): " + _fmt_test(public[0])]
    if suspicious:
        parts.append("Most suspicious lines (spectrum-based fault localization):\n" +
                     "\n".join(f"line {n}: {lines[n - 1].strip()}" for n in suspicious if 0 < n <= len(lines)))
    parts.append(f"Return the corrected `{program.func}` function.")
    return "\n\n".join(parts)


def twin_prompt(program, public):
    _, doc = split_source(program.source)
    sig = next(n for n in ast.parse(program.source).body if isinstance(n, ast.FunctionDef) and n.name == program.func)
    args = ", ".join(a.arg for a in sig.args.args)
    examples = "\n".join(_fmt_test(t) for t in public[:3])
    return (f"Write a Python function `def {program.func}({args}):` that satisfies this specification.\n\n"
            f"{doc}\n\nExamples (input -> expected output):\n{examples}")


# --------------------------------------------------------------------------- fuzzing
def _mutate(value, rng, depth=0):
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return rng.choice([value + 1, value - 1, 0, value * 2, abs(value) + rng.randint(1, 5)])
    if isinstance(value, float):
        return rng.choice([value + 1.0, value * 2, 0.0, abs(value) + 0.5])
    if isinstance(value, str):
        ops = [value[::-1], value + value[-1:] if value else "a", value[1:], value.upper()]
        return rng.choice(ops)
    if isinstance(value, list):
        v = list(value)
        op = rng.randrange(5)
        if op == 0 and v:
            rng.shuffle(v)
        elif op == 1 and v:
            v = v[:-1]
        elif op == 2 and v:
            v.append(copy.deepcopy(rng.choice(v)))
        elif op == 3 and v and depth < 2:
            i = rng.randrange(len(v))
            v[i] = _mutate(v[i], rng, depth + 1)
        else:
            v = list(reversed(v))
        return v
    return value


def fuzz_inputs(public, seed, n=16):
    rng = random.Random(f"twinfuzz:{seed}")
    out, seen = [], set()
    for _ in range(n * 4):
        args, _ = rng.choice(public)
        new = [copy.deepcopy(a) for a in args]
        i = rng.randrange(len(new)) if new else 0
        if new:
            new[i] = _mutate(new[i], rng)
        key = repr(new)
        if key not in seen:
            seen.add(key)
            out.append(new)
        if len(out) == n:
            break
    return out


def run_tests_capture(code, func, args, meter):
    from nexus.wave24_code_repair import SAFE_BUILTINS, CALL_LINE_BUDGET, CALL_WALL_S, _alarm
    import signal
    import sys
    ns = {"__builtins__": SAFE_BUILTINS, "__name__": "nexus_repair"}
    try:
        exec(code, ns)
    except Exception:
        return ("raise", "exec")
    fn = ns.get(func)
    lines = [0]
    def tracer(frame, event, arg):
        if frame.f_code.co_filename != "<candidate>":
            return None
        if event == "line":
            lines[0] += 1
            if lines[0] > CALL_LINE_BUDGET:
                raise LineBudgetExceeded("per-call line budget")
        return tracer
    signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, CALL_WALL_S)
    sys.settrace(tracer)
    try:
        out = fn(*copy.deepcopy(args))
        if hasattr(out, "__next__"):
            out = list(out)
        result = ("ok", repr(out))
    except LineBudgetExceeded:
        result = ("raise", "budget")
    except Exception as exc:
        result = ("raise", type(exc).__name__)
    finally:
        sys.settrace(None)
        signal.setitimer(signal.ITIMER_REAL, 0)
    meter.charge(lines[0] + 1)
    return result


# --------------------------------------------------------------------------- methods
def _compile(src):
    try:
        return compile(ast.parse(src), "<candidate>", "exec")
    except (SyntaxError, ValueError, TypeError):
        return None


def _passes(code, program, tests, meter):
    return code is not None and all(run_tests(code, program.func, tests, meter, stop_on_fail=True))


def _grade(code, program, hidden):
    return code is not None and all(run_tests(code, program.func, hidden, Meter(10**12)))


def method_mutation_search(program, public, hidden, *, budget=300_000):
    from nexus.wave24_code_repair import repair
    r = repair(program, public, hidden, learned=False, prior={}, budget=budget)
    return dict(method="mutation_search", plausible=r.plausible, correct=r.correct, work=r.work, llm_work=0,
                patch_kind=r.edit_kind)


def method_qwen_standalone(program, public, hidden, engine):
    text, row = engine.complete(SYSTEM, repair_prompt(program, public), temperature=0.0, seed=0,
                                purpose=f"standalone:{program.name}")
    src = extract_function(text, program.func)
    code = _compile(src) if src else None
    # UNVERIFIED: the answer is returned as-is; grading uses public + hidden tests.
    correct = code is not None and _grade(code, program, list(public) + list(hidden))
    return dict(method="qwen_standalone", plausible=code is not None, correct=correct, work=engine.work_units(row),
                llm_work=engine.work_units(row), patch=src)


def _twin(program, public, engine, seed, meter):
    text, row = engine.complete(TWIN_SYSTEM, twin_prompt(program, public), temperature=0.0, seed=seed,
                                purpose=f"twin:{program.name}")
    src = extract_function(text, program.func)
    code = _compile(src) if src else None
    return (code if _passes(code, program, public, meter) else None), engine.work_units(row)


def _rank(plausible, program, public, twin, seed, meter, fuzz_n):
    fuzz = fuzz_inputs(public, seed, fuzz_n)
    twin_vec = [run_tests_capture(twin, program.func, a, meter) for a in fuzz] if twin is not None else None
    code_part, _ = split_source(program.source)
    scored = []
    for origin, src, code in plausible:
        vec = [run_tests_capture(code, program.func, a, meter) for a in fuzz]
        agree = sum(a == b for a, b in zip(vec, twin_vec)) if twin_vec else None
        crash = sum(v[0] == "raise" for v in vec)
        closeness = difflib.SequenceMatcher(None, code_part, src).ratio()
        scored.append(((-(agree or 0), crash, -closeness), origin, src, code, agree))
    scored.sort(key=lambda x: x[0])
    return scored, len(fuzz)


def method_nexus_qwen(program, public, hidden, engine, *, seed, k=3, mutation_budget=150_000, fuzz_n=16,
                      overfit_floor=0.5):
    """Cascade: Qwen candidates (FL-guided) -> verify -> twin-fuzz check; mutation search only as fallback."""
    meter = Meter(10**12)
    llm = 0
    tree = ast.parse(program.source)
    cov = []
    run_tests(compile(tree, "<candidate>", "exec"), program.func, public, meter, coverage=cov)
    sus = ochiai(cov)
    top = [ln for ln, _ in sorted(sus.items(), key=lambda kv: -kv[1])[:3]]
    plausible, n_candidates = [], 0
    for i in range(k):
        text, row = engine.complete(SYSTEM, repair_prompt(program, public, suspicious=top),
                                    temperature=0.0 if i == 0 else 0.7, seed=seed * 10 + i,
                                    purpose=f"nexus:{program.name}:{i}")
        llm += engine.work_units(row)
        src = extract_function(text, program.func)
        if src:
            n_candidates += 1
            code = _compile(src)
            if _passes(code, program, public, meter):
                plausible.append(("qwen", src, code))
    twin, w = _twin(program, public, engine, seed, meter) if plausible else (None, 0)
    llm += w
    stage = "qwen"
    if plausible:
        scored, n_fuzz = _rank(plausible, program, public, twin, seed, meter, fuzz_n)
        best = scored[0]
        overfit = twin is not None and best[4] is not None and best[4] < overfit_floor * n_fuzz
    if not plausible or overfit:
        # Fallback: FL-ordered mutation patches (up to 3 plausible), re-ranked together with Qwen's.
        stage = "mutation_fallback"
        mutations = enumerate_mutations(tree)
        mutations.sort(key=lambda m: (-(sus.get(m.lineno, 0.0) + 1e-3), m.lineno))
        mut_meter, found = Meter(mutation_budget), 0
        try:
            for m in mutations:
                mut_meter.charge(1)
                try:
                    t = apply_mutation(tree, m)
                    code = compile(t, "<candidate>", "exec")
                except (SyntaxError, ValueError, TypeError):
                    continue
                if all(run_tests(code, program.func, public, mut_meter, stop_on_fail=True)):
                    plausible.append(("mutation", ast.unparse(t), code))
                    found += 1
                    if found >= 3:
                        break
        except LineBudgetExceeded:
            pass
        meter.total += mut_meter.total
        if plausible and twin is None:
            twin, w = _twin(program, public, engine, seed, meter)
            llm += w
        if not plausible:
            return dict(method="nexus_qwen", plausible=False, correct=False, work=meter.total + llm, llm_work=llm,
                        candidates=n_candidates, stage=stage)
        scored, n_fuzz = _rank(plausible, program, public, twin, seed, meter, fuzz_n)
        best = scored[0]
    return dict(method="nexus_qwen", plausible=True, correct=_grade(best[3], program, hidden),
                work=meter.total + llm, llm_work=llm, candidates=n_candidates, plausible_pool=len(plausible),
                chosen_origin=best[1], twin_validated=twin is not None, twin_agreement=best[4], fuzz_inputs=n_fuzz,
                stage=stage, patch=best[2])
