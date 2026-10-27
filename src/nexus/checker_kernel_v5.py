"""NEXUS Checker Kernel v5 (separately versioned; v1-v4 unchanged). Owner authorisation 2026-10-27 (Wave 39): "Implement and
validate these general constructs in a separately versioned, hash-pinned src/nexus/checker_kernel_v5.py (standard library only,
zero shared prover code ...), leaving Checkers v1-v4 untouched." Spec: docs/NEXUS_CHECKER_V5_SPEC.md.
v5 = v4 semantics + the Wave 39 constructs (at, sl, cap, shape, pad, dsh, drnd lambdas; fn, toks, first, dflt tools), a SOUND
final-layer type-reachability pruning (tools whose result is always a list cannot fit non-list targets), and an explicit
output contract: SCOPE_UNIQUE (unique within the declared finite scope on the public examples; NOT a claim about unseen
inputs), AMBIGUOUS, ABSTAIN, plus per-extra-query uniqueness (extra[i].answers = number of distinct answers that the scope's
chains fitting every public pair give on future input i) and UNDER_SPECIFIED_WARNING when any supplied future input has more
than one such answer (the public examples do not pin the mechanism down on the inputs it will be used on). Two further signals
are reported but do not trigger the warning (PROSE-dev calibration: uninformative / always on with 3 examples): query shape
novelty and leave-one-out fragility.
Original v4 header follows.
NEXUS Checker Kernel v4 (separately versioned; v1, v2, v3 unchanged). Owner authorisation 2026-10-26 (broader programme):
"Where new pure constructs require deterministic scope checking, implement a separately versioned, independently tested,
hash-pinned src/nexus/checker_kernel_v4.py". Spec: docs/NEXUS_CHECKER_V4_SPEC.md.
Standard library only; imports nothing from NEXUS; its interpreter is written independently of the prover's (w38_lang).
Semantics: the Wave 38 language (typed tools with lambda-AST parameters). Verdicts: v3's semantics, computed by bottom-up
shared evaluation over exact value vectors on all public inputs + the query (exact canonical-JSON keys; per-depth counts and
minimal witnesses; no truncation; stateless). DO NOT MODIFY after its pin without explicit owner approval (RULE 2).
"""
import json

VERSION = 5
MAX_EXTRA = 16
MAX_DEPTH = 4
MAX_EDGE_EVALS = 3_000_000
MAX_NODES = 400_000
class _Error:
    """v5: a unique error marker (v4 used None, which conflates a legitimate None value with an error)."""
    __slots__ = ()

    def __repr__(self):
        return "<v5 ERROR>"


ERRK = _Error()
ERR_ANSWER = "<ERROR>"


class Fail(Exception):
    pass


def ck(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def _isint(v):
    return type(v) is int


def _check(v, depth=0):
    if depth > 5:
        raise Fail("depth")
    t = type(v)
    if v is None or t is bool:
        return
    if t is int:
        if not -10**6 <= v <= 10**6:
            raise Fail("int")
    elif t is str:
        if len(v) > 256:                                     # v5: 256 (v4: 64); external text fields are longer
            raise Fail("str")
    elif t is list:
        if len(v) > 64:
            raise Fail("list")
        for e in v:
            _check(e, depth + 1)
    elif t is dict:
        if len(v) > 12 or not all(type(k) is str for k in v):
            raise Fail("dict")
        for e in v.values():
            _check(e, depth + 1)
    else:
        raise Fail("type")


# --------------------------------------------------------------------------- lambda evaluation (independent)
_UN = {"len", "fst", "lst", "low", "up", "int", "str", "even", "isdig", "not"}
_ARITH = {"add", "sub", "mul", "mod", "max", "min"}


def ev(e, x):
    h = e[0]
    if h == "x":
        return x
    if h == "c":
        return e[1]
    if h == "f":
        if type(x) is not dict or e[1] not in x:
            raise Fail("field")
        return x[e[1]]
    if h == "bef" or h == "aft":
        a = ev(e[1], x)
        d = e[2]
        if type(a) is not str or type(d) is not str or not d:
            raise Fail(h)
        pos = a.find(d)
        if pos < 0:
            raise Fail(h)
        return a[:pos] if h == "bef" else a[pos + len(d):]
    if h in _V5L:
        return _ev5(h, e, ev(e[1], x))
    if h == "if":
        c = ev(e[1], x)
        if type(c) is not bool:
            raise Fail("if")
        return ev(e[2] if c else e[3], x)
    if h in _UN:
        a = ev(e[1], x)
        ta = type(a)
        if h == "len":
            if ta is str or ta is list:
                return len(a)
        elif h == "fst":
            if (ta is str or ta is list) and len(a) > 0:
                return a[0]
        elif h == "lst":
            if (ta is str or ta is list) and len(a) > 0:
                return a[len(a) - 1]
        elif h == "low":
            if ta is str:
                return a.lower()
        elif h == "up":
            if ta is str:
                return a.upper()
        elif h == "int":
            if ta is int:
                return a
            if ta is str and 0 < len(a) <= 6 and a.isdigit():
                return int(a)
        elif h == "str":
            if ta is int or ta is str:
                return str(a)
        elif h == "even":
            if ta is int:
                return a % 2 == 0
        elif h == "isdig":
            if ta is str:
                return a.isdigit()
        elif h == "not":
            if ta is bool:
                return not a
        raise Fail(h)
    a = ev(e[1], x)
    b = ev(e[2], x)
    if h == "and" or h == "or":
        if type(a) is bool and type(b) is bool:
            return (a and b) if h == "and" else (a or b)
        raise Fail(h)
    if h == "eq":
        return ck(a) == ck(b)
    if h == "ne":
        return ck(a) != ck(b)
    if h == "gt" or h == "lt":
        if (_isint(a) and _isint(b)) or (type(a) is str and type(b) is str):
            return (a > b) if h == "gt" else (a < b)
        raise Fail(h)
    if h == "cat":
        if type(a) is str and type(b) is str:
            return a + b
        raise Fail(h)
    if h in _ARITH:
        if not (_isint(a) and _isint(b)):
            raise Fail(h)
        if h == "add":
            return a + b
        if h == "sub":
            return a - b
        if h == "mul":
            return a * b
        if h == "mod":
            if b == 0:
                raise Fail("mod")
            return a % b
        return max(a, b) if h == "max" else min(a, b)
    raise Fail("lambda")


# --------------------------------------------------------------------------- v5 lambdas (independent of the prover)
_V5L = {"at", "sl", "cap", "shape", "pad", "dsh", "drnd"}
_DIG = "0123456789"
_UPP = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LOW = "abcdefghijklmnopqrstuvwxyz"


def _dec(a):
    """-?DIGITS(.DIGITS)? -> (signed integer of all digits, count of fraction digits)."""
    if type(a) is not str or len(a) == 0 or len(a) > 40:
        raise Fail("dec")
    sign, i = 1, 0
    if a[0] == "-":
        sign, i = -1, 1
    whole, frac, seen_dot = "", "", False
    for ch in a[i:]:
        if ch == "." and not seen_dot:
            seen_dot = True
        elif ch in _DIG:
            if seen_dot:
                frac += ch
            else:
                whole += ch
        else:
            raise Fail("dec")
    if whole == "" or (seen_dot and frac == ""):
        raise Fail("dec")
    v = 0
    for ch in whole + frac:
        v = v * 10 + _DIG.index(ch)
    return sign * v, len(frac)


def _render(v, places):
    neg = v < 0
    digits = str(-v if neg else v)
    if places > 0:
        while len(digits) <= places:
            digits = "0" + digits
        digits = digits[: len(digits) - places] + "." + digits[len(digits) - places:]
    return ("-" if neg else "") + digits


def _ev5(h, e, a):
    if h == "at":
        i = e[2]
        if (type(a) is str or type(a) is list) and -len(a) <= i < len(a):
            return a[i % len(a)] if len(a) else a[i]
        raise Fail("at")
    if h == "sl":
        if type(a) is str or type(a) is list:
            n = len(a)
            lo = 0 if e[2] is None else (max(0, n + e[2]) if e[2] < 0 else min(n, e[2]))
            hi = n if e[3] is None else (max(0, n + e[3]) if e[3] < 0 else min(n, e[3]))
            return a[lo:hi] if lo < hi else a[0:0]
        raise Fail("sl")
    if type(a) is not str:
        raise Fail(h)
    if h == "cap":
        return (a[0].upper() + a[1:].lower()) if a else ""
    if h == "shape":
        return "".join("9" if c in _DIG else "A" if c in _UPP else "a" if c in _LOW else c for c in a)
    if h == "pad":
        n, fill = e[2], e[3]
        while len(a) < n:
            a = fill + a
        return a
    v, f = _dec(a)
    if h == "dsh":
        sh = e[2]
        if sh >= 0:
            v = v * (10 ** sh)
        else:
            f = f - sh
        while f > 0 and v % 10 == 0:
            v, f = v // 10, f - 1
        return _render(v, f)
    k, mode, step = e[2], e[3], e[4]
    # value = v / 10^f ; unit = step / 10^k ; ratio = v * 10^k / (step * 10^f)
    top = v * (10 ** k if k > 0 else 1)
    bot = step * (10 ** f) * (10 ** (-k) if k < 0 else 1)
    q, r = divmod(top, bot)                     # floor division (bot > 0)
    if mode == "f":
        n = q
    elif mode == "c":
        n = q + (1 if r else 0)
    else:
        if top >= 0:
            n = q + (1 if 2 * r >= bot else 0)
        else:
            mag_q, mag_r = divmod(-top, bot)
            n = -(mag_q + (1 if 2 * mag_r >= bot else 0))
    n = n * step
    if n == 0:
        return _render(0, k if k > 0 else 0)
    if k > 0:
        return _render(n, k)
    return str(n * 10 ** (-k))


def _runs(s, kind):
    def inside(c):
        if kind == "d":
            return c in _DIG
        if kind == "a":
            return c in _UPP or c in _LOW
        if kind == "w":
            return c in _DIG or c in _UPP or c in _LOW
        if kind == "s":
            return not (c == " " or c == "\t" or c == "\n")
        return c in _DIG or c == "."
    res, start = [], None
    for i in range(len(s) + 1):
        ok = i < len(s) and inside(s[i])
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            res.append(s[start:i])
            start = None
    if kind == "n":
        trimmed = []
        for t in res:
            while t.startswith("."):
                t = t[1:]
            while t.endswith("."):
                t = t[:-1]
            if t != "":
                trimmed.append(t)
        res = trimmed
    return res


# --------------------------------------------------------------------------- tools (independent)
def _L(x):
    if type(x) is not list:
        raise Fail("list")
    return x


def _combine(o, a, b):
    if o == "cat":
        if type(a) is str and type(b) is str:
            return a + b
        raise Fail("cat")
    if not (_isint(a) and _isint(b)):
        raise Fail("fold")
    if o == "add":
        return a + b
    if o == "mul":
        return a * b
    if o == "max":
        return a if a >= b else b
    if o == "min":
        return a if a <= b else b
    raise Fail("fold op")


def _comps(g, conn, bg):
    if type(g) is not list or not g or any(type(r) is not list for r in g):
        raise Fail("grid")
    W = len(g[0])
    if any(len(r) != W for r in g) or any(not _isint(c) for r in g for c in r):
        raise Fail("grid")
    H = len(g)
    step = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if conn == 8:
        step = step + [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    mark = [[False] * W for _ in range(H)]
    res = []
    for i in range(H):
        for j in range(W):
            if mark[i][j] or g[i][j] == bg:
                continue
            col = g[i][j]
            mark[i][j] = True
            todo, cells = [(i, j)], []
            while todo:
                a, b = todo.pop()
                cells.append([a, b])
                for da, db in step:
                    u, w = a + da, b + db
                    if 0 <= u < H and 0 <= w < W and not mark[u][w] and g[u][w] == col:
                        mark[u][w] = True
                        todo.append((u, w))
            cells = sorted(cells)
            res.append({"color": col, "size": len(cells), "r": cells[0][0], "c": min(c[1] for c in cells), "cells": cells})
    return sorted(res, key=lambda o: (o["r"], o["c"], o["color"]))


def _G(x):
    if type(x) is not dict or set(x.keys()) != {"nodes", "edges"}:
        raise Fail("graph")
    return x


def tool(t, x):
    op = t["op"]
    if op == "fn":
        return ev(t["f"], x)
    if op == "toks":
        if type(x) is not str:
            raise Fail("toks")
        return _runs(x, t["c"])
    if op == "first":
        for e in _L(x):
            c = ev(t["p"], e)
            if type(c) is not bool:
                raise Fail("pred")
            if c:
                return e
        return t["v"]
    if op == "dflt":
        if x is None or (type(x) is str and x == "") or (type(x) is list and len(x) == 0):
            return t["v"]
        return x
    if op == "map":
        return [ev(t["f"], e) for e in _L(x)]
    if op == "filter":
        res = []
        for e in _L(x):
            c = ev(t["p"], e)
            if type(c) is not bool:
                raise Fail("pred")
            if c:
                res.append(e)
        return res
    if op == "sortby":
        xs = _L(x)
        keys = [ev(t["f"], e) for e in xs]
        ints = all(_isint(k) for k in keys)
        if not (ints or all(type(k) is str for k in keys)):
            raise Fail("sortkey")
        if t["desc"]:
            if not ints:
                raise Fail("desc")
            order = sorted(range(len(xs)), key=lambda i: (-keys[i], i))
        else:
            order = sorted(range(len(xs)), key=lambda i: (keys[i], i))
        return [xs[i] for i in order]
    if op == "groupby" or op == "countby":
        buckets = {}
        for e in _L(x):
            k = ev(t["f"], e)
            if not (_isint(k) or type(k) is str or type(k) is bool):
                raise Fail("gkey")
            ks = ck(k)
            if ks not in buckets:
                buckets[ks] = (k, [])
            buckets[ks][1].append(e)
        if op == "groupby":
            return [{"key": buckets[s][0], "items": buckets[s][1]} for s in sorted(buckets)]
        return [{"key": buckets[s][0], "count": len(buckets[s][1])} for s in sorted(buckets)]
    if op == "fold" or op == "scan":
        acc = t["init"]
        trace = []
        for e in _L(x):
            acc = _combine(t["o"], acc, e)
            trace.append(acc)
        return acc if op == "fold" else trace
    if op == "take":
        return _L(x)[: t["n"]]
    if op == "drop":
        return _L(x)[t["n"]:]
    if op == "rev":
        return list(reversed(_L(x)))
    if op == "uniq":
        seen, res = set(), []
        for e in _L(x):
            s = ck(e)
            if s not in seen:
                seen.add(s)
                res.append(e)
        return res
    if op == "flat":
        res = []
        for e in _L(x):
            res.extend(_L(e))
        return res
    if op == "enum":
        return [{"i": i, "v": e} for i, e in enumerate(_L(x))]
    if op == "pairs":
        xs = _L(x)
        return [{"a": xs[i], "b": xs[i + 1]} for i in range(len(xs) - 1)]
    if op == "len":
        if type(x) is list or type(x) is str:
            return len(x)
        raise Fail("len")
    if op == "best":
        xs = _L(x)
        if not xs:
            raise Fail("best")
        keys = [ev(t["f"], e) for e in xs]
        if not all(_isint(k) for k in keys):
            raise Fail("best key")
        bi = 0
        for i in range(1, len(xs)):
            if keys[i] > keys[bi]:
                bi = i
        return xs[bi]
    if op in ("split", "chars", "words", "strip"):
        if type(x) is not str:
            raise Fail(op)
        if op == "split":
            return x.split(t["d"])
        if op == "chars":
            return [c for c in x]
        if op == "words":
            return x.split()
        return x.strip()
    if op == "join":
        xs = _L(x)
        if any(type(e) is not str for e in xs):
            raise Fail("join")
        return t["d"].join(xs)
    if op == "get":
        if type(x) is not dict or t["k"] not in x:
            raise Fail("get")
        return x[t["k"]]
    if op == "proj":
        rows = _L(x)
        if any(type(r) is not dict for r in rows):
            raise Fail("proj")
        return [{k: r[k] for k in t["ks"] if k in r} for r in rows]
    if op == "tjoin":
        if type(x) is not dict or type(x.get("L")) is not list or type(x.get("R")) is not list:
            raise Fail("tjoin")
        k = t["k"]
        right = {}
        for r in x["R"]:
            if type(r) is not dict or k not in r:
                raise Fail("tjoin")
            s = ck(r[k])
            if s not in right:
                right[s] = r
        res = []
        for l in x["L"]:
            if type(l) is not dict or k not in l:
                raise Fail("tjoin")
            r = right.get(ck(l[k]))
            if r is None:
                continue
            m = dict(l)
            for kk in r:
                if kk not in l:
                    m[kk] = r[kk]
            res.append(m)
        return res
    if op == "fill":
        res = []
        for r in _L(x):
            if type(r) is not dict:
                raise Fail("fill")
            r2 = dict(r)
            if r2.get(t["k"]) is None:
                r2[t["k"]] = t["v"]
            res.append(r2)
        return res
    if op == "objs":
        return _comps(x, t["conn"], t["bg"])
    if op == "paint":
        H, W = t["h"], t["w"]
        g = [[t["bg"] for _ in range(W)] for _ in range(H)]
        for o in _L(x):
            if type(o) is not dict or "cells" not in o or "color" not in o:
                raise Fail("paint")
            for cell in o["cells"]:
                r, c = cell
                if not (0 <= r < H and 0 <= c < W):
                    raise Fail("paint")
                g[r][c] = o["color"]
        return g
    if op == "recolor_if":
        res = []
        for o in _L(x):
            if type(o) is not dict or "color" not in o:
                raise Fail("recolor")
            c = ev(t["p"], o)
            if type(c) is not bool:
                raise Fail("pred")
            if c:
                o = dict(o)
                o["color"] = t["color"]
            res.append(o)
        return res
    if op == "reach":
        g = _G(x)
        adj = {}
        for a, b in g["edges"]:
            adj.setdefault(a, []).append(b)
        start = t["s"]
        if start not in g["nodes"]:
            return []
        seen, todo = {start}, [start]
        while todo:
            n = todo.pop()
            for b in adj.get(n, []):
                if b not in seen:
                    seen.add(b)
                    todo.append(b)
        return sorted(seen)
    if op == "topo":
        g = _G(x)
        nodes = list(g["nodes"])
        indeg = {n: 0 for n in nodes}
        for a, b in g["edges"]:
            if b in indeg:
                indeg[b] += 1
        done, order = set(), []
        while len(order) < len(nodes):
            cand = sorted(n for n in nodes if n not in done and indeg[n] == 0)
            if not cand:
                raise Fail("cycle")
            n = cand[0]
            done.add(n)
            order.append(n)
            for a, b in g["edges"]:
                if a == n and b in indeg:
                    indeg[b] -= 1
        return order
    if op == "indeg" or op == "outdeg":
        g = _G(x)
        deg = {n: 0 for n in g["nodes"]}
        for a, b in g["edges"]:
            n = b if op == "indeg" else a
            if n in deg:
                deg[n] += 1
        return [{"node": n, "deg": deg[n]} for n in sorted(deg)]
    raise Fail("unknown op")


def apply_chain(chain, x):
    try:
        for t in chain:
            x = tool(t, x)
            _check(x)
        return x
    except Exception:
        return ERRK


# --------------------------------------------------------------------------- spec validation
_LAMBDA_ARITY = {"x": 0, "c": -1, "f": -2, "if": 3, "and": 2, "or": 2, "eq": 2, "ne": 2, "gt": 2, "lt": 2, "cat": 2}
_LAMBDA_ARITY.update({k: 1 for k in _UN})
_LAMBDA_ARITY.update({k: 2 for k in _ARITH})


def _small(v, lo, hi, none_ok=False):
    return (none_ok and v is None) or (_isint(v) and lo <= v <= hi)


def _lam_ok(e, d=0):
    if type(e) is list and e and e[0] in _V5L and d <= 6:
        h, n = e[0], len(e)
        if h in ("cap", "shape"):
            return n == 2 and _lam_ok(e[1], d + 1)
        if h == "at":
            return n == 3 and _small(e[2], -8, 8) and _lam_ok(e[1], d + 1)
        if h == "sl":
            return n == 4 and _small(e[2], -8, 8, True) and _small(e[3], -8, 8, True) and _lam_ok(e[1], d + 1)
        if h == "pad":
            return n == 4 and _small(e[2], 1, 16) and e[3] in ("0", " ") and _lam_ok(e[1], d + 1)
        if h == "dsh":
            return n == 3 and _small(e[2], -6, 6) and _lam_ok(e[1], d + 1)
        return n == 5 and _small(e[2], -6, 6) and e[3] in ("h", "f", "c") and e[4] in (1, 2, 5) and _lam_ok(e[1], d + 1)
    if type(e) is list and len(e) == 3 and e[0] in ("bef", "aft"):
        return type(e[2]) is str and 0 < len(e[2]) <= 3 and _lam_ok(e[1], d + 1)
    if type(e) is not list or not e or d > 6 or e[0] not in _LAMBDA_ARITY:
        return False
    n = _LAMBDA_ARITY[e[0]]
    if n == 0:
        return len(e) == 1
    if n == -1:
        return len(e) == 2 and (e[1] is None or type(e[1]) in (int, str, bool))
    if n == -2:
        return len(e) == 2 and type(e[1]) is str
    return len(e) == n + 1 and all(_lam_ok(a, d + 1) for a in e[1:])


def known(t):
    if type(t) is not dict or "op" not in t:
        return False
    op = t["op"]
    try:
        if op == "fn":
            return set(t) == {"op", "f"} and _lam_ok(t["f"])
        if op == "toks":
            return set(t) == {"op", "c"} and t["c"] in ("d", "a", "w", "s", "n")
        if op == "first":
            return set(t) == {"op", "p", "v"} and _lam_ok(t["p"]) and (t["v"] is None or type(t["v"]) is str) and \
                (t["v"] is None or len(t["v"]) <= 16)
        if op == "dflt":
            return set(t) == {"op", "v"} and type(t["v"]) is str and len(t["v"]) <= 16
        if op in ("map", "groupby", "countby", "best"):
            return set(t) == {"op", "f"} and _lam_ok(t["f"])
        if op == "filter":
            return set(t) == {"op", "p"} and _lam_ok(t["p"])
        if op == "sortby":
            return set(t) == {"op", "f", "desc"} and _lam_ok(t["f"]) and type(t["desc"]) is bool
        if op in ("fold", "scan"):
            return set(t) == {"op", "o", "init"} and t["o"] in ("add", "mul", "max", "min", "cat") and \
                (_isint(t["init"]) or type(t["init"]) is str)
        if op in ("take", "drop"):
            return set(t) == {"op", "n"} and _isint(t["n"]) and 0 <= t["n"] <= 64
        if op in ("rev", "uniq", "flat", "enum", "pairs", "len", "chars", "words", "strip", "topo", "indeg", "outdeg"):
            return set(t) == {"op"}
        if op in ("split", "join"):
            return set(t) == {"op", "d"} and type(t["d"]) is str and len(t["d"]) <= 3 and (op == "join" or t["d"] != "")
        if op in ("get", "tjoin"):
            return set(t) == {"op", "k"} and type(t["k"]) is str
        if op == "proj":
            return set(t) == {"op", "ks"} and type(t["ks"]) is list and all(type(k) is str for k in t["ks"])
        if op == "fill":
            return set(t) == {"op", "k", "v"} and type(t["k"]) is str and (_isint(t["v"]) or type(t["v"]) is str)
        if op == "objs":
            return set(t) == {"op", "conn", "bg"} and t["conn"] in (4, 8) and _isint(t["bg"])
        if op == "paint":
            return set(t) == {"op", "bg", "h", "w"} and all(_isint(t[k]) for k in ("bg", "h", "w")) and 1 <= t["h"] <= 30 \
                and 1 <= t["w"] <= 30
        if op == "recolor_if":
            return set(t) == {"op", "p", "color"} and _lam_ok(t["p"]) and _isint(t["color"])
        if op == "reach":
            return set(t) == {"op", "s"} and _isint(t["s"])
    except (KeyError, TypeError):
        return False
    return False


# --------------------------------------------------------------------------- the check (shared evaluation)
def _abst(reason, **kw):
    return dict(label="ABSTAIN", reason=reason, checker_version=VERSION, **kw)


def check(evidence):
    try:
        if evidence.get("checker_version") != VERSION:
            return _abst("wrong_checker_version")
        pub = [(p[0], p[1]) for p in evidence["public"]]
        q, claimed = evidence["query"], evidence["claimed_answer"]
        cand = list(evidence["candidate"])
        sc = evidence["scope"]
        tools, D, kind = list(sc["tools"]), int(sc["max_depth"]), sc["kind"]
        if evidence.get("lemmas") or evidence.get("proofs"):
            return _abst("lemmas_or_proofs_not_accepted_in_v5")
        extra = list(evidence.get("extra_queries") or [])
    except Exception:
        return _abst("malformed")
    if kind not in ("exhaustive", "proposal") or not 1 <= D <= MAX_DEPTH or not pub or not tools or len(extra) > MAX_EXTRA:
        return _abst("malformed")
    if not all(known(t) for t in tools + cand):
        return _abst("unsupported")
    try:
        for v in [x for x, _ in pub] + [y for _, y in pub] + [q] + extra:
            _check(v)
    except Exception:
        return _abst("unsupported_value")
    tk = {ck(t) for t in tools}
    if not 1 <= len(cand) <= D or any(ck(t) not in tk for t in cand):
        return _abst("candidate_outside_scope")
    for x, y in pub:
        o = apply_chain(cand, x)
        if o is ERRK or ck(o) != ck(y):
            return _abst("candidate_fails")
    co = apply_chain(cand, q)
    if co is ERRK or ck(co) != ck(claimed):
        return _abst("candidate_fails")
    return _share(pub, q, claimed, tools, D, kind, extra)


# always-list tools: their result can never equal a non-list target (sound final-layer pruning)
_LIST_OUT = {"map", "filter", "sortby", "groupby", "countby", "scan", "take", "drop", "rev", "uniq", "flat", "enum", "pairs",
             "split", "chars", "words", "toks", "proj", "tjoin", "fill", "objs", "recolor_if", "reach", "topo", "indeg",
             "outdeg", "paint"}


def coarse_shape(v):
    """Run-collapsed character-class shape of a string (digit runs -> 9, ASCII letter runs -> a, other chars kept); lists of
    strings -> the tuple of element shapes; other values -> their type name."""
    if type(v) is str:
        out = []
        for c in v:
            s = "9" if c in _DIG else "a" if (c in _UPP or c in _LOW) else c
            if not (out and out[-1] == s and s in ("9", "a")):
                out.append(s)
        return "".join(out)
    if type(v) is list and all(type(e) is str for e in v):
        return "L(" + ",".join(coarse_shape(e) for e in v) + ")"
    return type(v).__name__


def _share(pub, q, claimed, tools, D, kind, extra=()):
    pts = [x for x, _ in pub] + [q] + list(extra)
    P, T = len(pub), len(tools)
    targets = [ck(y) for _, y in pub]
    nodes, memo = {}, {}
    work = {"edge_evals": 0, "point_evals": 0}

    def key_of(vals):
        return tuple(ERRK if v is ERRK else ck(v) for v in vals)

    def add(vals):
        k = key_of(vals)
        if k not in nodes:
            if len(nodes) >= MAX_NODES:
                raise OverflowError
            nodes[k] = vals
        return k

    def edge(k, ti):
        r = memo.get((k, ti))
        if r is not None:
            return r
        work["edge_evals"] += 1
        if work["edge_evals"] > MAX_EDGE_EVALS:
            raise OverflowError
        out = []
        for v in nodes[k]:
            if v is ERRK:
                out.append(ERRK)
                continue
            work["point_evals"] += 1
            out.append(apply_chain([tools[ti]], v))
        r = memo[(k, ti)] = add(out)
        return r

    try:
        root = add(list(pts))
        layer = {root: [1, ()]}
        answers, first, fitting = {}, {}, 0
        loo = [set() for _ in range(P)]                         # query answers of chains fitting all public pairs but j
        xans = [set() for _ in extra]
        nonlist_target = all(not t.startswith("[") for t in targets)
        last_ok = [ti for ti in range(T) if not (nonlist_target and tools[ti]["op"] in _LIST_OUT)]
        for _d in range(D):
            nxt = {}
            final = _d == D - 1
            for k, (cnt, mc) in layer.items():
                if all(v is ERRK for v in nodes[k]):
                    continue                                   # an all-ERROR vector only extends to all-ERROR
                for ti in (last_ok if final else range(T)):
                    c = edge(k, ti)
                    ch = mc + (ti,)
                    e = nxt.get(c)
                    if e is None:
                        nxt[c] = [cnt, ch]
                    else:
                        e[0] += cnt
                        if ch < e[1]:
                            e[1] = ch
            best_here = {}
            for k, (cnt, mc) in nxt.items():
                miss = [j for j in range(P) if k[j] != targets[j]]
                if len(miss) == 1:
                    loo[miss[0]].add(ERR_ANSWER if k[P] is ERRK else k[P])
                if miss:
                    continue
                for j in range(P):
                    loo[j].add(ERR_ANSWER if k[P] is ERRK else k[P])
                for i in range(len(extra)):
                    xans[i].add(ERR_ANSWER if k[P + 1 + i] is ERRK else k[P + 1 + i])
                fitting += cnt
                a = ERR_ANSWER if k[P] is ERRK else k[P]
                answers[a] = answers.get(a, 0) + cnt
                if a not in first and (a not in best_here or mc < best_here[a]):
                    best_here[a] = mc
            for a, mc in best_here.items():
                first.setdefault(a, list(mc))
            layer = nxt
    except OverflowError:
        return _abst("budget_exhausted", **work)
    pshapes = {coarse_shape(x) for x, _ in pub}
    novel = coarse_shape(q) not in pshapes
    fragile = [j for j in range(P) if len(loo[j]) > 1]
    nonuniq = sum(1 for i in range(len(extra)) if len(xans[i]) > 1)
    res = dict(fitting=fitting, answers=len(answers), chains_total=sum(T ** k for k in range(1, D + 1)), nodes=len(nodes),
               checker_version=VERSION, scope_relative=True,
               warnings=["UNDER_SPECIFIED_WARNING"] if nonuniq else [],
               warning_reasons=dict(extra_nonunique=nonuniq, query_shape_novel=novel, loo_fragile=fragile),
               extra=[dict(answers=len(xans[i]), shape_novel=coarse_shape(extra[i]) not in pshapes) for i in range(len(extra))],
               **work)
    if len(answers) > 1:
        w = sorted(first)[:2]
        return dict(label="AMBIGUOUS", k=len(answers), k_exact=(kind == "exhaustive"),
                    witnesses=[dict(chain=first[a], answer=a) for a in w], **res)
    if len(answers) == 1 and ERR_ANSWER in answers:
        return dict(label="ABSTAIN", reason="query_error", **res)
    if len(answers) != 1 or ck(claimed) not in answers:
        return dict(label="ABSTAIN", reason="claimed_not_unique", **res)
    return dict(label="SCOPE_UNIQUE" if kind == "exhaustive" else "proposal_relative_UNIQUE", **res)
