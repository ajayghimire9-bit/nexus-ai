"""Wave 38 domain 6: small Python repairs (NOT LOCKED). Evidence class: TEST_VERIFIED_PATCH = the chosen patch passes an
independent HELD-OUT test oracle run in a separate sandboxed process (public-fit and held-out pass rates are reported
separately; passing tests is not a proof of correctness).

Task families (bugs needing conditionals, state updates or bounded loops): each has a correct reference (evaluator side),
injected bugs, few public tests and more held-out tests.
Patch space (bounded): one or two AST mutations from: compare-op swap, arithmetic-op swap, int constant +-1, max<->min,
insert a guard `if not <arg>: return <c>` at the top. Search order: operator-kind prior (learned from past successful
repairs = experience; uniform for Fresh; permuted for Placebo)."""
from __future__ import annotations

import ast
import itertools
import random

FAMILIES = {
    "sum_pos": ("def f(xs):\n    s = 0\n    for x in xs:\n        if x > 0:\n            s += x\n    return s\n",
                lambda r: [r.randint(-5, 5) for _ in range(r.randint(0, 6))]),
    "run_max": ("def f(xs):\n    if not xs:\n        return None\n    m = xs[0]\n    for x in xs:\n        m = max(m, x)\n    return m\n",
                lambda r: [r.randint(-9, 9) for _ in range(r.randint(0, 6))]),
    "count_lt": ("def f(xs):\n    c = 0\n    for x in xs:\n        if x < 3:\n            c += 1\n    return c\n",
                 lambda r: [r.randint(0, 6) for _ in range(r.randint(0, 6))]),
    "last_even": ("def f(xs):\n    out = -1\n    for i in range(len(xs)):\n        if xs[i] % 2 == 0:\n            out = i\n    return out\n",
                  lambda r: [r.randint(0, 9) for _ in range(r.randint(0, 6))]),
    "safe_avg": ("def f(xs):\n    if not xs:\n        return 0\n    t = 0\n    for x in xs:\n        t += x\n    return t // len(xs)\n",
                 lambda r: [r.randint(0, 9) for _ in range(r.randint(0, 5))]),
    "min_pos": ("def f(xs):\n    best = 100\n    for x in xs:\n        if x > 0:\n            best = min(best, x)\n    return best\n",
                lambda r: [r.randint(-4, 9) for _ in range(r.randint(0, 6))]),
}
CMP = [ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq]
ARITH = [ast.Add, ast.Sub]
KINDS = ("cmp", "arith", "const", "maxmin", "guard")


def _mutations(tree):
    """All single mutations as (kind, path-id, apply-fn). Deterministic order."""
    out = []
    nodes = list(ast.walk(tree))
    for i, n in enumerate(nodes):
        if isinstance(n, ast.Compare) and len(n.ops) == 1:
            for op in CMP:
                if not isinstance(n.ops[0], op):
                    out.append(("cmp", i, op))
        if isinstance(n, (ast.BinOp, ast.AugAssign)) and type(n.op) in ARITH:
            for op in ARITH:
                if not isinstance(n.op, op):
                    out.append(("arith", i, op))
        if isinstance(n, ast.Constant) and type(n.value) is int:
            for d in (-1, 1):
                out.append(("const", i, d))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("max", "min"):
            out.append(("maxmin", i, None))
    for c in (0, -1, None):
        out.append(("guard", -1, c))
    return out


def _apply(src, muts):
    tree = ast.parse(src)
    nodes = list(ast.walk(tree))
    for kind, i, arg in muts:
        if kind == "guard":
            fn = tree.body[0]
            g = ast.parse(f"if not {fn.args.args[0].arg}:\n    return {arg!r}\n").body[0]
            fn.body.insert(0, g)
            continue
        n = nodes[i]
        if kind == "cmp":
            n.ops = [arg()]
        elif kind == "arith":
            n.op = arg()
        elif kind == "const":
            n.value = n.value + arg
        elif kind == "maxmin":
            n.func.id = "min" if n.func.id == "max" else "max"
    return ast.unparse(ast.fix_missing_locations(tree))


def make_task(fam, r):
    """Inject one or two mutations into the reference (a bug), keep it only if the bug is observable on the tests."""
    ref, gen = FAMILIES[fam]
    ns = {}
    exec(compile(ref, "ref", "exec"), ns)
    reff = ns["f"]
    muts = _mutations(ast.parse(ref))
    for _ in range(50):
        k = r.choice((1, 1, 2))
        bug = r.sample(muts, k)
        if any(m[0] == "guard" for m in bug):
            continue
        buggy = _apply(ref, bug)
        xs = [gen(r) for _ in range(14)] + [[]]
        tests = []
        for x in xs:
            try:
                tests.append([x, reff(list(x))])
            except Exception:
                tests.append([x, "<EXC>"])
        ns2 = {}
        try:
            exec(compile(buggy, "bug", "exec"), ns2)
        except Exception:
            continue
        fails = 0
        for x, y in tests:
            try:
                fails += ns2["f"](list(x)) != y
            except Exception:
                fails += 1
        if fails >= 2:
            return dict(family=fam, buggy=buggy, public=tests[:4], heldout=tests[4:], bug=[m[0] for m in bug])
    return None


def candidates(src, prior, max_edits=2):
    """Patches in prior order: single edits first, then pairs; within each, by summed kind cost (then canonical)."""
    muts = _mutations(ast.parse(src))
    cost = lambda ms: sum(prior.get(m[0], 1.0) for m in ms)
    singles = sorted(([m] for m in muts), key=cost)
    pairs = sorted((list(p) for p in itertools.combinations(muts, 2) if p[0][0] != "guard" or p[1][0] != "guard"), key=cost) \
        if max_edits > 1 else []
    for ms in singles + pairs:
        yield ms


def learn_prior(fixes):
    """Experience: cost of a mutation kind = -log(share of successful patches using it) (smoothed)."""
    import math
    cnt = {k: 1.0 for k in KINDS}
    for kinds in fixes:
        for k in kinds:
            cnt[k] += 1
    z = sum(cnt.values())
    return {k: -math.log(v / z) for k, v in cnt.items()}


def placebo_prior(prior, seed):
    ks = list(KINDS)
    perm = ks[:]
    random.Random(f"w38-repair-placebo:{seed}").shuffle(perm)
    return {k: prior[p] for k, p in zip(ks, perm)}
