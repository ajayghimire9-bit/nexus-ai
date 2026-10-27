"""Wave 39 language = the Wave 38 language + a small set of general constructs (PROVER SIDE; NOT LOCKED). Checker v5
(src/nexus/checker_kernel_v5.py) re-implements these semantics independently; the two are cross-checked.
Added (Wave 39, from the PROSE-dev failure audit; no task-specific macros):
  lambdas: ["at", A, i] signed index (str/list) | ["sl", A, a, b] signed slice (a, b int or None) | ["cap", A] capitalise
    | ["shape", A] character-class shape (ASCII digit -> 9, upper -> A, lower -> a, other kept)
    | ["pad", A, n, ch] left-pad to width n | ["dsh", A, e] exact decimal shift x * 10^e (canonical decimal string)
    | ["drnd", A, k, m, s] exact decimal rounding to a multiple of s * 10^-k (m: h = half away from zero, f = floor, c = ceil;
      exactly max(k, 0) decimals; no negative zero)
  tools: fn{f} (apply a lambda to the whole value) | toks{c} (maximal character-class runs: d digits, a letters, w letters or
    digits, s non-space, n runs of [0-9.] with outer dots stripped) | first{p, v} (first element satisfying p, else v)
    | dflt{v} (v if the value is "", [] or None, else the value)
Original Wave 38 header follows.

Wave 38 language (PROVER SIDE; NOT LOCKED). Typed tools with lambda-AST parameters, chained (encode -> transform -> decode).
Checker v4 (src/nexus/checker_kernel_v4.py) re-implements these semantics independently; the two are cross-checked.

Lambda AST over one element x (variables, conditionals, arithmetic, string functions, record fields):
  ["x"] | ["c", v] | ["f", name] | ["len", A] | ["fst", A] | ["lst", A] | ["low", A] | ["up", A] | ["int", A] | ["str", A]
  | [op, A, B] for op in add sub mul mod max min cat | [cmp, A, B] for cmp in gt lt eq ne | ["and"|"or", P, Q] | ["not", P]
  | ["even", A] | ["isdig", A] | ["if", P, A, B] | ["bef"|"aft", A, d] (substring before / after the first d)
Tools (dicts with "op"): list: map{f} filter{p} sortby{f,desc} groupby{f} countby{f} fold{o,init} scan{o,init} take{n}
drop{n} rev uniq flat enum pairs len best{f}; strings: split{d} join{d} chars words strip; records/tables: get{k} proj{ks}
tjoin{k} fill{k,v}; grids: objs{conn,bg} paint{bg,h,w} recolor_if{p,color}; graphs: reach{s} topo indeg outdeg.
Folds / scans are bounded loops over the list; lambdas are parameterised functions (closures over constants).
Bounds: ints |v| <= 10^6, strings <= 64 (Wave 39: 256), lists <= 64 items, nesting <= 5. Errors raise LangError.
"""
from __future__ import annotations

import json


class LangError(Exception):
    pass


ERROR = "<ERROR>"


def key(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def _i(v):
    return type(v) is int


def bound(v, d=0):
    if d > 5:
        raise LangError("nesting")
    if v is None or type(v) is bool:
        return
    if _i(v):
        if abs(v) > 10**6:
            raise LangError("int")
        return
    if type(v) is str:
        if len(v) > 256:                                     # Wave 39: 256 (Wave 38: 64)
            raise LangError("str")
        return
    if type(v) is list:
        if len(v) > 64:
            raise LangError("list")
        for e in v:
            bound(e, d + 1)
        return
    if type(v) is dict:
        if len(v) > 12 or any(type(k) is not str for k in v):
            raise LangError("record")
        for e in v.values():
            bound(e, d + 1)
        return
    raise LangError("type")


# --------------------------------------------------------------------------- lambdas
def lam(e, x):
    op = e[0]
    if op == "x":
        return x
    if op == "c":
        return e[1]
    if op == "f":
        if type(x) is dict and e[1] in x:
            return x[e[1]]
        raise LangError("field")
    if op in ("len", "fst", "lst", "low", "up", "int", "str", "even", "isdig", "not"):
        a = lam(e[1], x)
        if op == "len":
            if type(a) in (str, list):
                return len(a)
            raise LangError("len")
        if op in ("fst", "lst"):
            if type(a) in (str, list) and a:
                return a[0] if op == "fst" else a[-1]
            raise LangError("fst")
        if op in ("low", "up"):
            if type(a) is str:
                return a.lower() if op == "low" else a.upper()
            raise LangError("case")
        if op == "int":
            if type(a) is str and a.isdigit() and len(a) <= 6:
                return int(a)
            if _i(a):
                return a
            raise LangError("int")
        if op == "str":
            if _i(a) or type(a) is str:
                return str(a)
            raise LangError("str")
        if op == "even":
            if _i(a):
                return a % 2 == 0
            raise LangError("even")
        if op == "isdig":
            if type(a) is str:
                return a.isdigit()
            raise LangError("isdig")
        if type(a) is bool:
            return not a
        raise LangError("not")
    if op in ("bef", "aft"):
        a = lam(e[1], x)
        if type(a) is not str or e[2] not in a:
            raise LangError("bef/aft")
        i = a.index(e[2])
        return a[:i] if op == "bef" else a[i + len(e[2]):]
    if op in NEW_LAMBDAS:
        return _new_lam(e, x)
    if op == "if":
        p = lam(e[1], x)
        if type(p) is not bool:
            raise LangError("if")
        return lam(e[2], x) if p else lam(e[3], x)
    a, b = lam(e[1], x), lam(e[2], x)
    if op in ("and", "or"):
        if type(a) is bool and type(b) is bool:
            return (a and b) if op == "and" else (a or b)
        raise LangError("bool")
    if op in ("eq", "ne"):
        return (key(a) == key(b)) if op == "eq" else (key(a) != key(b))
    if op in ("gt", "lt"):
        if _i(a) and _i(b) or (type(a) is str and type(b) is str):
            return a > b if op == "gt" else a < b
        raise LangError("cmp")
    if op == "cat":
        if type(a) is str and type(b) is str:
            return a + b
        raise LangError("cat")
    if not (_i(a) and _i(b)):
        raise LangError("arith")
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "mul":
        return a * b
    if op == "mod":
        if b == 0:
            raise LangError("mod0")
        return a % b
    if op == "max":
        return max(a, b)
    if op == "min":
        return min(a, b)
    raise LangError("lambda op")


def _lst(x):
    if type(x) is not list:
        raise LangError("not list")
    return x


def _fold_op(o, a, b):
    if o == "cat":
        if type(a) is str and type(b) is str:
            return a + b
        raise LangError("cat")
    if not (_i(a) and _i(b)):
        raise LangError("fold arith")
    return {"add": a + b, "mul": a * b, "max": max(a, b), "min": min(a, b)}[o]


def _objects(g, conn, bg):
    if not (type(g) is list and g and all(type(r) is list for r in g) and all(len(r) == len(g[0]) for r in g)
            and all(_i(c) for r in g for c in r)):
        raise LangError("grid")
    H, W = len(g), len(g[0])
    nb = [(1, 0), (-1, 0), (0, 1), (0, -1)] + ([(1, 1), (1, -1), (-1, 1), (-1, -1)] if conn == 8 else [])
    seen, out = set(), []
    for r in range(H):
        for c in range(W):
            if (r, c) in seen or g[r][c] == bg:
                continue
            col, st, cells = g[r][c], [(r, c)], []
            seen.add((r, c))
            while st:
                a, b = st.pop()
                cells.append([a, b])
                for da, db in nb:
                    u, v = a + da, b + db
                    if 0 <= u < H and 0 <= v < W and (u, v) not in seen and g[u][v] == col:
                        seen.add((u, v)); st.append((u, v))
            cells.sort()
            out.append({"color": col, "size": len(cells), "r": cells[0][0], "c": min(x[1] for x in cells), "cells": cells})
    out.sort(key=lambda o: (o["r"], o["c"], o["color"]))
    return out


def _graph(x):
    if not (type(x) is dict and set(x) == {"nodes", "edges"}):
        raise LangError("graph")
    return x


def apply(t, x):
    op = t["op"]
    if op == "map":
        return [lam(t["f"], e) for e in _lst(x)]
    if op == "filter":
        out = []
        for e in _lst(x):
            p = lam(t["p"], e)
            if type(p) is not bool:
                raise LangError("pred")
            if p:
                out.append(e)
        return out
    if op == "sortby":
        xs = _lst(x)
        ks = [lam(t["f"], e) for e in xs]
        if not (all(_i(k) for k in ks) or all(type(k) is str for k in ks)):
            raise LangError("sort key")
        if t["desc"]:
            if not all(_i(k) for k in ks):
                raise LangError("desc needs int keys")
            idx = sorted(range(len(xs)), key=lambda i: (-ks[i], i))
        else:
            idx = sorted(range(len(xs)), key=lambda i: (ks[i], i))
        return [xs[i] for i in idx]
    if op in ("groupby", "countby"):
        groups = {}
        for e in _lst(x):
            k = lam(t["f"], e)
            if not (_i(k) or type(k) in (str, bool)):
                raise LangError("group key")
            groups.setdefault(key(k), [k, []])[1].append(e)
        ordered = [groups[k] for k in sorted(groups)]
        if op == "groupby":
            return [{"key": k, "items": v} for k, v in ordered]
        return [{"key": k, "count": len(v)} for k, v in ordered]
    if op in ("fold", "scan"):
        acc, out = t["init"], []
        for e in _lst(x):
            acc = _fold_op(t["o"], acc, e)
            out.append(acc)
        return acc if op == "fold" else out
    if op == "take":
        return _lst(x)[: t["n"]]
    if op == "drop":
        return _lst(x)[t["n"]:]
    if op == "rev":
        return _lst(x)[::-1]
    if op == "uniq":
        out, seen = [], set()
        for e in _lst(x):
            if key(e) not in seen:
                seen.add(key(e)); out.append(e)
        return out
    if op == "flat":
        out = []
        for e in _lst(x):
            out += _lst(e)
        return out
    if op == "enum":
        return [{"i": i, "v": e} for i, e in enumerate(_lst(x))]
    if op == "pairs":
        xs = _lst(x)
        return [{"a": xs[i], "b": xs[i + 1]} for i in range(len(xs) - 1)]
    if op == "len":
        if type(x) in (list, str):
            return len(x)
        raise LangError("len")
    if op == "best":
        xs = _lst(x)
        if not xs:
            raise LangError("best empty")
        ks = [lam(t["f"], e) for e in xs]
        if not all(_i(k) for k in ks):
            raise LangError("best key")
        return xs[max(range(len(xs)), key=lambda i: (ks[i], -i))]
    if op == "split":
        if type(x) is not str:
            raise LangError("split")
        return x.split(t["d"])
    if op == "join":
        xs = _lst(x)
        if not all(type(e) is str for e in xs):
            raise LangError("join")
        return t["d"].join(xs)
    if op == "chars":
        if type(x) is not str:
            raise LangError("chars")
        return list(x)
    if op == "words":
        if type(x) is not str:
            raise LangError("words")
        return x.split()
    if op == "strip":
        if type(x) is not str:
            raise LangError("strip")
        return x.strip()
    if op == "get":
        if type(x) is dict and t["k"] in x:
            return x[t["k"]]
        raise LangError("get")
    if op == "proj":
        rows = _lst(x)
        if not all(type(r) is dict for r in rows):
            raise LangError("proj")
        return [{k: r[k] for k in t["ks"] if k in r} for r in rows]
    if op == "tjoin":
        if not (type(x) is dict and type(x.get("L")) is list and type(x.get("R")) is list):
            raise LangError("tjoin")
        k = t["k"]
        idx = {}
        for r in x["R"]:
            if type(r) is not dict or k not in r:
                raise LangError("tjoin row")
            idx.setdefault(key(r[k]), r)
        out = []
        for l in x["L"]:
            if type(l) is not dict or k not in l:
                raise LangError("tjoin row")
            r = idx.get(key(l[k]))
            if r is not None:
                m = dict(l); m.update({kk: vv for kk, vv in r.items() if kk not in l})
                out.append(m)
        return out
    if op == "fill":
        out = []
        for r in _lst(x):
            if type(r) is not dict:
                raise LangError("fill")
            r = dict(r)
            if r.get(t["k"]) is None:
                r[t["k"]] = t["v"]
            out.append(r)
        return out
    if op == "objs":
        return _objects(x, t["conn"], t["bg"])
    if op == "paint":
        g = [[t["bg"]] * t["w"] for _ in range(t["h"])]
        for o in _lst(x):
            if type(o) is not dict or "cells" not in o or "color" not in o:
                raise LangError("paint")
            for r, c in o["cells"]:
                if not (0 <= r < t["h"] and 0 <= c < t["w"]):
                    raise LangError("paint bounds")
                g[r][c] = o["color"]
        return g
    if op == "recolor_if":
        out = []
        for o in _lst(x):
            if type(o) is not dict or "color" not in o:
                raise LangError("recolor")
            p = lam(t["p"], o)
            if type(p) is not bool:
                raise LangError("pred")
            out.append(dict(o, color=t["color"]) if p else o)
        return out
    if op == "reach":
        g = _graph(x)
        succ = {}
        for a, b in g["edges"]:
            succ.setdefault(a, []).append(b)
        seen = {t["s"]} if t["s"] in g["nodes"] else set()
        st = list(seen)
        while st:
            for b in succ.get(st.pop(), []):
                if b not in seen:
                    seen.add(b); st.append(b)
        return sorted(seen)
    if op == "topo":
        g = _graph(x)
        indeg = {n: 0 for n in g["nodes"]}
        for a, b in g["edges"]:
            if b in indeg:
                indeg[b] += 1
        ready = sorted(n for n, d in indeg.items() if d == 0)
        out = []
        while ready:
            n = ready.pop(0)
            out.append(n)
            for a, b in g["edges"]:
                if a == n and b in indeg:
                    indeg[b] -= 1
                    if indeg[b] == 0:
                        ready.append(b); ready.sort()
        if len(out) != len(g["nodes"]):
            raise LangError("cycle")
        return out
    if op in ("indeg", "outdeg"):
        g = _graph(x)
        d = {n: 0 for n in g["nodes"]}
        for a, b in g["edges"]:
            n = b if op == "indeg" else a
            if n in d:
                d[n] += 1
        return [{"node": n, "deg": d[n]} for n in sorted(d)]
    raise LangError("unknown op")


def _num(a):
    """Parse a decimal string -?D+(.D+)? into (integer numerator, number of fractional digits)."""
    if type(a) is not str or not a or len(a) > 40:
        raise LangError("decimal")
    neg = a[0] == "-"
    body = a[1:] if neg else a
    ip, dot, fp = body.partition(".")
    if not ip or not ip.isascii() or not ip.isdigit() or (dot and (not fp or not fp.isascii() or not fp.isdigit())):
        raise LangError("decimal")
    n = int(ip + fp)
    return (-n if neg else n), len(fp)


def _fmt(n, places):
    """Integer n scaled by 10^-places, rendered with exactly `places` decimals; never '-0'."""
    s = str(abs(n)).rjust(places + 1, "0")
    out = s if places == 0 else s[:-places] + "." + s[-places:]
    return ("-" + out) if n < 0 else out


def _canon(n, places):
    while places > 0 and n % 10 == 0:
        n //= 10
        places -= 1
    return _fmt(n, places)


def _ascii_shape(a):
    out = []
    for ch in a:
        if "0" <= ch <= "9":
            out.append("9")
        elif "A" <= ch <= "Z":
            out.append("A")
        elif "a" <= ch <= "z":
            out.append("a")
        else:
            out.append(ch)
    return "".join(out)


NEW_LAMBDAS = {"at", "sl", "cap", "shape", "pad", "dsh", "drnd"}


def _new_lam(e, x):
    op = e[0]
    a = lam(e[1], x)
    if op == "at":
        if type(a) not in (str, list) or not -len(a) <= e[2] < len(a):
            raise LangError("at")
        return a[e[2]]
    if op == "sl":
        if type(a) not in (str, list):
            raise LangError("sl")
        return a[e[2]:e[3]]
    if type(a) is not str:
        raise LangError(op)
    if op == "cap":
        return a[:1].upper() + a[1:].lower()
    if op == "shape":
        return _ascii_shape(a)
    if op == "pad":
        return a if len(a) >= e[2] else e[3] * (e[2] - len(a)) + a
    n, f = _num(a)
    if op == "dsh":
        sh = e[2]
        return _canon(n * 10 ** sh, f) if sh >= 0 else _canon(n, f - sh)
    k, mode, step = e[2], e[3], e[4]
    # q = value / (step * 10^-k) = n * 10^k / (step * 10^f), as an exact fraction num / den with den > 0
    num, den = n * 10 ** max(k, 0), step * 10 ** f * 10 ** max(-k, 0)
    if mode == "f":
        r = num // den
    elif mode == "c":
        r = -((-num) // den)
    else:
        r = (2 * abs(num) + den) // (2 * den)
        r = -r if num < 0 else r
    m = r * step
    return _fmt(m, k) if k > 0 else str(m * 10 ** (-k)) if m != 0 else "0"


_CLS = {"d": lambda c: "0" <= c <= "9", "a": lambda c: "a" <= c.lower() <= "z" and c.isascii(),
        "w": lambda c: "0" <= c <= "9" or ("a" <= c.lower() <= "z" and c.isascii()), "s": lambda c: c not in " \t\n",
        "n": lambda c: "0" <= c <= "9" or c == "."}


def _toks(x, c):
    if type(x) is not str:
        raise LangError("toks")
    test, out, cur = _CLS[c], [], ""
    for ch in x:
        if test(ch):
            cur += ch
        else:
            if cur:
                out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    if c == "n":
        out = [t.strip(".") for t in out]
        out = [t for t in out if t]
    return out


def apply5(t, x):
    op = t["op"]
    if op == "fn":
        return lam(t["f"], x)
    if op == "toks":
        return _toks(x, t["c"])
    if op == "first":
        for e in _lst(x):
            p = lam(t["p"], e)
            if type(p) is not bool:
                raise LangError("pred")
            if p:
                return e
        return t["v"]
    if op == "dflt":
        return t["v"] if x in ("", [], None) else x
    return apply(t, x)


def run(chain, x):
    try:
        for t in chain:
            x = apply5(t, x)
            bound(x)
        return x
    except (LangError, KeyError, TypeError, ValueError, IndexError, RecursionError, ZeroDivisionError):
        return ERROR
