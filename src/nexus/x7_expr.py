"""Bounded typed expression grammar for field adapters (NOT LOCKED; x7 Part 4). Generic primitives only.

  E := ('f', path)            numeric field / one-level nested path ('a.b'); absent, None, bool or non-numeric -> MISSING
     | ('p', path)            explicit parse: a numeric value passes; a string matching -?D+(.D+)? is parsed; else MISSING
     | ('c', k)               constant, k in CONSTANTS
     | ('b', op, E1, E2)      op in + - * /; '/' is guarded (divisor 0 or MISSING -> MISSING); MISSING operands -> MISSING
     | ('if', path, E1, E2)   presence test: E1 if `path` holds a number (or a parseable string), else E2
MISSING never becomes 0: an adapter that yields MISSING leaves the field unresolved (the contract then reports a mismatch).

Size / depth convention (frozen): leaves ('f' | 'p' | 'c') have size 1, depth 0; 'b' adds 1 to size and 1 to depth; 'if' adds 2
to size (the node + its presence-test path) and 1 to depth. Arithmetic bodies are bounded by size <= 5 (at most 3 leaves, 2
operators, depth <= 2); a conditional wraps one body and one branch that is the target field itself, so conditionals have
size <= 8 and depth <= 3. Constants (frozen): CONSTANTS = (1, 2, 10, 100, 1000). Numeric semantics: IEEE doubles; results
compared with the platform tolerance (|a - b| <= 1e-6 max(1, |b|)).

Enumeration tiers (cheapest first): tier 0 = one path ('field selection'); tier 1 = size 2-3 (a parse, or one operator);
tier 2 = size 5 (two operators). Candidates are deduplicated by observational equivalence on the evidence records plus seeded
synthetic records drawn from their shape (first, i.e. smallest, representative kept)."""
from __future__ import annotations

import math
import random
import re

MISSING = object()
CONSTANTS = (1, 2, 10, 100, 1000)
OPS = ("+", "-", "*", "/")
MAX_BODY_SIZE = 5
_NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")


def isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not (isinstance(v, float) and math.isnan(v))


def get_path(e, path):
    cur = e
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def has_path(e, path):
    cur = e
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return False
        cur = cur[p]
    return True


def set_path(e, path, v):
    if "." not in path:
        e[path] = v
        return e
    a, b = path.split(".", 1)
    e[a] = dict(e[a], **{b: v})
    return e


def _parse(v):
    if isnum(v):
        return v
    if isinstance(v, str) and _NUM_RE.match(v.strip()):
        return float(v.strip())
    return MISSING


def ev(n, e):
    """Evaluate; returns a number or MISSING."""
    k = n[0]
    if k == "f":
        v = get_path(e, n[1])
        return v if isnum(v) else MISSING
    if k == "p":
        return _parse(get_path(e, n[1]))
    if k == "c":
        return n[1]
    if k == "b":
        a = ev(n[2], e)
        if a is MISSING:
            return MISSING
        b = ev(n[3], e)
        if b is MISSING:
            return MISSING
        op = n[1]
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if b == 0:
            return MISSING
        return a / b
    if k == "if":
        return ev(n[2], e) if _parse(get_path(e, n[1])) is not MISSING else ev(n[3], e)
    raise ValueError(n)


def branch(n, e):
    """Which branch a top-level conditional takes on e ('then' | 'else' | None for a non-conditional)."""
    if n[0] != "if":
        return None
    return "then" if _parse(get_path(e, n[1])) is not MISSING else "else"


def chosen(n, e):
    """The branch expression a top-level conditional selects on e (the node itself for a non-conditional)."""
    if n[0] != "if":
        return n
    return n[2] if _parse(get_path(e, n[1])) is not MISSING else n[3]


def src(n):
    k = n[0]
    if k == "f":
        return n[1]
    if k == "p":
        return f"parse({n[1]})"
    if k == "c":
        return repr(n[1])
    if k == "b":
        return f"({src(n[2])} {n[1]} {src(n[3])})"
    return f"(if present({n[1]}) then {src(n[2])} else {src(n[3])})"


def size(n):
    k = n[0]
    if k in ("f", "p", "c"):
        return 1
    if k == "b":
        return 1 + size(n[2]) + size(n[3])
    return 2 + size(n[2]) + size(n[3])


def depth(n):
    k = n[0]
    if k in ("f", "p", "c"):
        return 0
    if k == "b":
        return 1 + max(depth(n[2]), depth(n[3]))
    return 1 + max(depth(n[2]), depth(n[3]))


def paths(n):
    k = n[0]
    if k in ("f", "p"):
        return {n[1]}
    if k == "c":
        return set()
    if k == "b":
        return paths(n[2]) | paths(n[3])
    return {n[1]} | paths(n[2]) | paths(n[3])


def numeric_paths(e):
    out = []
    for k, v in e.items():
        if isnum(v):
            out.append(k)
        elif isinstance(v, dict):
            out += [f"{k}.{k2}" for k2, v2 in v.items() if isnum(v2)]
    return out


def string_numeric_paths(e):
    out = []
    for k, v in e.items():
        if isinstance(v, str) and _NUM_RE.match(v.strip()):
            out.append(k)
        elif isinstance(v, dict):
            out += [f"{k}.{k2}" for k2, v2 in v.items() if isinstance(v2, str) and _NUM_RE.match(v2.strip())]
    return out


def leaves(records, exclude=()):
    """Numeric paths present on ALL records (and parseable string paths, as parse leaves)."""
    if not records:
        return [], []
    num = set.intersection(*[set(numeric_paths(r)) for r in records]) - set(exclude)
    strs = set.intersection(*[set(string_numeric_paths(r)) for r in records]) - set(exclude) - num
    return sorted(num), sorted(strs)


def _fresh(e, rnd):
    e = dict(e)
    for p in numeric_paths(e):
        v = get_path(e, p)
        set_path(e, p, rnd.randint(0, 9) if isinstance(v, int) else round(rnd.uniform(1, 400), 2))
    return e


def _sig(n, recs):
    out = []
    for r in recs:
        v = ev(n, r)
        out.append(None if v is MISSING else round(v, 9))
    return tuple(out)


def enumerate_bodies(num_paths, parse_paths, records, max_tier=2, seed=0, cap=60000):
    """Arithmetic bodies by tier, deduplicated by observational equivalence. Every body must be defined (not MISSING) on
    every evidence record. Returns [(tier, body)] in tier / size order."""
    rnd = random.Random(seed)
    probe = list(records[:24]) + [_fresh(r, rnd) for r in records[:8] for _ in range(2)]
    seen, out = set(), []

    def add(tier, n):
        s = _sig(n, probe)
        if s in seen:
            return
        seen.add(s)
        if any(ev(n, r) is MISSING for r in records):
            return
        out.append((tier, n))
    fl = [("f", p) for p in num_paths]
    for n in fl:
        add(0, n)
    if max_tier < 1:
        return out
    pl = [("p", p) for p in parse_paths]
    for n in pl:
        add(1, n)
    lv = fl + pl + [("c", k) for k in CONSTANTS]
    t1 = []
    for op in OPS:
        for a in lv:
            for b in lv:
                if a[0] == "c" and b[0] == "c":
                    continue
                if op in "+*" and repr(a) > repr(b):
                    continue
                n = ("b", op, a, b)
                t1.append(n)
                add(1, n)
    if max_tier < 2:
        return out
    k = 0
    for op in OPS:
        for x in t1:
            for c in lv:
                for n in (("b", op, x, c), ("b", op, c, x)):
                    if len(paths(n)) == 0:
                        continue
                    k += 1
                    if k > cap:
                        return out
                    add(2, n)
    return out


def wrap_missing(f, body):
    """Adapter for a REQUIRED field that is absent: the raw field when present, else the body."""
    return ("if", f, ("f", f), body)


def wrap_trigger(t, body, f):
    """Adapter for a field whose meaning changed with a new path t: the body when t is present, else the raw field."""
    return ("if", t, body, ("f", f))
