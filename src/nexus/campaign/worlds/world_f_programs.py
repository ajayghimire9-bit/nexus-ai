"""World F - small executable programs: synthesis & repair (NOT LOCKED).
Each task gives input/output examples AND a buggy draft program (the intended program with one random mutation: a wrong
constant, a swapped operator or swapped branches). The intended program exists as a substrate AST only to make the draft;
the reference used for labels and verification is an independent Python function. Training values 0..6, interface 0..9.
Verification: bounded exhaustive equivalence (all (a, b) in 0..9^2; all lists of length <= 3 over 0..9) + 30 hidden inputs.
  F1 symbolic/arithmetic expression synthesis & repair   F2 nested conditional guard synthesis & repair
  F3 bounded iteration / fold synthesis & repair         F4 multi-function composition / helper repair"""
import itertools

from .base import Mech, Post, exhaustive_lists

WORLD = "F"
FAMILIES = ("F1", "F2", "F3", "F4")
Q_BUDGET = 3


def P(name, *a):
    return ("p", name) + a


X0, X1, XA, YA = ("x", 0), ("x", 1), ("a", 0), ("a", 1)


def C(v):
    return ("c", v)


def LAM(ctx, body):
    return ("lam", ctx, body)


def _f1(rng):
    k = rng.randint(2, 4)
    v = rng.choice(("lin", "scale_sum", "diff", "modprod"))
    py = {"lin": lambda a, b: a * k + b, "scale_sum": lambda a, b: (a + b) * k, "diff": lambda a, b: a - b * k,
          "modprod": lambda a, b: (a * b) % k}[v]
    ast = {"lin": P("add", P("mul", X0, C(k)), X1), "scale_sum": P("mul", P("add", X0, X1), C(k)),
           "diff": P("sub", X0, P("mul", X1, C(k))), "modprod": P("mod", P("mul", X0, X1), C(k))}[v]
    return py, ast, f"arith[{v},k={k}]"


def _f2(rng):
    k = rng.randint(2, 5)
    v = rng.choice(("branch", "nested", "eqmax", "both"))
    py = {"branch": lambda a, b: a + k if a < b else b - a,
          "nested": lambda a, b: b if a < k else (a if b < k else a + b),
          "eqmax": lambda a, b: k if a == b else max(a, b),
          "both": lambda a, b: a * b if (k < a and k < b) else a + b}[v]
    ast = {"branch": P("ite_i", P("lt", X0, X1), P("add", X0, C(k)), P("sub", X1, X0)),
           "nested": P("ite_i", P("lt", X0, C(k)), X1, P("ite_i", P("lt", X1, C(k)), X0, P("add", X0, X1))),
           "eqmax": P("ite_i", P("eq", X0, X1), C(k), P("max2", X0, X1)),
           "both": P("ite_i", P("and", P("lt", C(k), X0), P("lt", C(k), X1)), P("mul", X0, X1), P("add", X0, X1))}[v]
    return py, ast, f"guard[{v},k={k}]"


def _f3(rng):
    k = rng.randint(1, 4)
    v = rng.choice(("sum_gt", "count_eq", "sumsq", "horner", "max_plus"))
    py = {"sum_gt": lambda l: sum(x for x in l if x > k), "count_eq": lambda l: sum(1 for x in l if x == k),
          "sumsq": lambda l: sum(x * x for x in l),
          "horner": lambda l: (lambda acc: acc)(_horner(l, k)), "max_plus": lambda l: max((x + k for x in l), default=0)}[v]
    ast = {"sum_gt": P("sum", P("filter", LAM("i", P("lt", C(k), XA)), X0)),
           "count_eq": P("count", LAM("i", P("eq", XA, C(k))), X0),
           "sumsq": P("sum", P("map", LAM("i", P("mul", XA, XA)), X0)),
           "horner": P("fold", LAM("ii", P("add", P("mul", XA, C(k)), YA)), C(0), X0),
           "max_plus": P("maxl", P("map", LAM("i", P("add", XA, C(k))), X0))}[v]
    return py, ast, f"fold[{v},k={k}]"


def _horner(l, k):
    acc = 0
    for x in l:
        acc = acc * k + x
    return acc


def _f4(rng):
    k = rng.randint(1, 4)
    v = rng.choice(("take_sorted", "filter_rev", "shift_sorted", "mirror", "scaled_prefix"))
    py = {"take_sorted": lambda l: tuple(sorted(l))[:k], "filter_rev": lambda l: tuple(x for x in l[::-1] if x < k + 2),
          "shift_sorted": lambda l: tuple(x + k for x in sorted(l)), "mirror": lambda l: tuple(l) + tuple(l[::-1]),
          "scaled_prefix": lambda l: tuple(itertools.accumulate(x * k for x in l))}[v]
    ast = {"take_sorted": P("take", P("sort", X0), C(k)),
           "filter_rev": P("filter", LAM("i", P("lt", XA, C(k + 2))), P("rev", X0)),
           "shift_sorted": P("map", LAM("i", P("add", XA, C(k))), P("sort", X0)),
           "mirror": P("cat", X0, P("rev", X0)),
           "scaled_prefix": P("scan", LAM("ii", P("add", XA, YA)), C(0), P("map", LAM("i", P("mul", XA, C(k))), X0))}[v]
    return py, ast, f"compose[{v},k={k}]"


SWAP = {"add": "sub", "sub": "add", "mul": "add", "max2": "min2", "min2": "max2", "lt": "eq", "eq": "lt", "sort": "rev",
        "rev": "sort", "take": "drop", "drop": "take", "sum": "maxl", "maxl": "sum"}


def mutate(ast, rng):
    """One random mutation: a constant +-1, an operator swap, or swapped ite branches."""
    paths = []

    def walk(n, path):
        if n[0] == "c" or (n[0] == "p" and (n[1] in SWAP or n[1] == "ite_i")):
            paths.append(path)
        if n[0] == "lam":
            walk(n[2], path + (2,))
        elif n[0] == "p":
            for i, c in enumerate(n[2:]):
                walk(c, path + (i + 2,))
    walk(ast, ())
    path = rng.choice(paths)

    def rebuild(n, path):
        if not path:
            if n[0] == "c":
                return ("c", max(0, n[1] + rng.choice((-1, 1))))
            if n[1] == "ite_i":
                return n[:3] + (n[4], n[3])
            return ("p", SWAP[n[1]]) + n[2:]
        i = path[0]
        return n[:i] + (rebuild(n[i], path[1:]),) + n[i + 1:]
    return rebuild(ast, path)


def _ints_tr(r):
    return (r.randint(0, 6), r.randint(0, 6))


def _ints_if(r):
    return (r.randint(0, 9), r.randint(0, 9))


def _list_tr(r):
    return (tuple(r.randint(0, 6) for _ in range(r.randint(3, 6))),)


def _list_if(r):
    return (tuple(r.randint(0, 9) for _ in range(r.randint(0, 8))),)


GEN = {"F1": _f1, "F2": _f2, "F3": _f3, "F4": _f4}


def gen(family, rng, level):
    py, ast, d = GEN[family](rng)
    draft = mutate(ast, rng)
    if family in ("F1", "F2"):
        return Mech(fn=lambda x: py(*x), sig=("i", "i"), out="i", descr=d, train=_ints_tr, iface=_ints_if, draft=draft,
                    exhaustive=lambda: [(a, b) for a in range(10) for b in range(10)], verify_kind="bounded_exhaustive+hidden")
    out = "i" if family == "F3" else "l"
    return Mech(fn=lambda x: py(x[0]), sig=("l",), out=out, descr=d, train=_list_tr, iface=_list_if, draft=draft,
                exhaustive=lambda: exhaustive_lists(3, range(10)), verify_kind="bounded_exhaustive+hidden")


def intended(family, seed_rng):
    """(python ref, intended AST) for tests only: never given to a learner."""
    py, ast, _ = GEN[family](seed_rng)
    return py, ast


def posts(family, rng):
    k = rng.randint(2, 4)
    if family == "F1":
        c = rng.randint(0, 3)
        return [Post(lambda v: v * k + c, "i", "i", f"arith[{k}x+{c}]")]
    if family == "F2":
        return [Post(lambda v: v if v < k + 2 else k + 2, "i", "i", f"guard[clip{k + 2}]")]
    if family == "F3":
        py, _, d = _f3(rng)
        return [Post(py, "l", "i", d)]
    if family == "F4":
        py, _, d = _f4(rng)
        return [Post(py, "l", "l", d)]
    return []
