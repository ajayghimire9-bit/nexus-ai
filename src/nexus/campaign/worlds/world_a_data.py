"""World A - structured data (tables of positional integer records; NOT LOCKED).
Inputs: tables = tuples of rows (records of 3-4 positional fields, no names). Training values 0..6, declared interface 0..9
(unseen values are probed by the verifier). Verification: finite hidden-test agreement (30 random interface tables).
  A1 relational predicate filtering      A2 grouped aggregation (sum / count by a key, multi-key at some seeds)
  A3 stream/table matching & joins       A4 conditional routing & schema projection"""
from .base import Mech, Post

WORLD = "A"
FAMILIES = ("A1", "A2", "A3", "A4")
Q_BUDGET = 4


def _table(rng, w, lo, hi, nmin, nmax):
    return tuple(tuple(rng.randint(lo, hi) for _ in range(w)) for _ in range(rng.randint(nmin, nmax)))


def _pred(rng, w):
    k, c = rng.randrange(w), rng.randint(1, 5)
    op = rng.choice(("lt", "ge", "eq"))
    f = {"lt": lambda r: r[k] < c, "ge": lambda r: r[k] >= c, "eq": lambda r: r[k] == c}[op]
    return f, f"{op}(f{k},{c})"


def _filter(rng, w):
    f, d = _pred(rng, w)
    if rng.random() < 0.3:
        g, d2 = _pred(rng, w)
        return (lambda T: tuple(r for r in T if f(r) and g(r))), f"filter[{d}&{d2}]"
    return (lambda T: tuple(r for r in T if f(r))), f"filter[{d}]"


def _group(rng, w):
    k = rng.randrange(w)
    v = rng.choice([j for j in range(w) if j != k] + [None])
    k2 = rng.choice([j for j in range(w) if j != k]) if rng.random() < 0.25 else None

    def g(T):
        acc = {}
        for r in T:
            key = r[k] * 10 + r[k2] if k2 is not None else r[k]
            acc[key] = acc.get(key, 0) + (r[v] if v is not None else 1)
        return tuple((a, acc[a]) for a in sorted(acc))
    return g, f"group[k=f{k}{'' if k2 is None else f'*10+f{k2}'},{'count' if v is None else f'sum f{v}'}]"


def _project(rng, w):
    a, b = rng.sample(range(w), 2)
    if rng.random() < 0.4:
        k, c = rng.randrange(w), rng.randint(1, 5)
        return (lambda T: tuple((r[a], r[b]) if r[k] < c else (r[b], r[a]) for r in T)), f"route[f{k}<{c}?(f{a},f{b}):(f{b},f{a})]"
    return (lambda T: tuple((r[a], r[b]) for r in T)), f"project[f{a},f{b}]"


def gen(family, rng, level):
    w = rng.choice((3, 4))
    tr = lambda r, w=w: (_table(r, w, 0, 6, 3, 7),)          # noqa: E731
    it = lambda r, w=w: (_table(r, w, 0, 9, 0, 8),)          # noqa: E731
    if family == "A1":
        f, d = _filter(rng, w)
        return Mech(fn=lambda x: f(x[0]), sig=("L",), out="L", descr=d, train=tr, iface=it)
    if family == "A2":
        f, d = _group(rng, w)
        return Mech(fn=lambda x: f(x[0]), sig=("L",), out="L", descr=d, train=tr, iface=it)
    if family == "A3":
        w2 = rng.choice((2, 3))
        i, j = rng.randrange(w), rng.randrange(w2)
        tr2 = lambda r: (_table(r, w, 0, 6, 3, 6), _table(r, w2, 0, 6, 2, 5))     # noqa: E731
        it2 = lambda r: (_table(r, w, 0, 9, 0, 6), _table(r, w2, 0, 9, 0, 6))     # noqa: E731
        if rng.random() < 0.5:
            f = lambda x: tuple(r for r in x[0] if r[i] in {s[j] for s in x[1]})   # noqa: E731
            d = f"semijoin[f{i} in T2.f{j}]"
        else:
            f = lambda x: tuple(r + s for r in x[0] for s in x[1] if r[i] == s[j])[:40]   # noqa: E731
            d = f"join[f{i}==T2.f{j}]"
        return Mech(fn=f, sig=("L", "L"), out="L", descr=d, train=tr2, iface=it2)
    if family == "A4":
        f, d = _project(rng, w)
        return Mech(fn=lambda x: f(x[0]), sig=("L",), out="L", descr=d, train=tr, iface=it)
    raise KeyError(family)


def _safe_rows(f, minw):
    return lambda L: f(tuple(r for r in L if len(r) >= minw)) if all(len(r) >= minw for r in L) else f(
        tuple(tuple(r) + (0,) * (minw - len(r)) for r in L))


def posts(family, rng):
    w = 2
    if family == "A1":
        f, d = _filter(rng, w)
        return [Post(_safe_rows(f, w), "L", "L", d)]
    if family == "A2":
        f, d = _group(rng, w)
        return [Post(_safe_rows(f, w), "L", "L", d)]
    if family == "A4":
        f, d = _project(rng, w)
        return [Post(_safe_rows(f, w), "L", "L", d)]
    return []
