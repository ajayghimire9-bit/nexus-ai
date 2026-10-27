"""Wave 39 declared scope (shared declaration; NOT LOCKED) = the Wave 38 scope + the Wave 39 general constructs. A deterministic
function of the task's PUBLIC data and a fixed config: identical for every arm (Fresh, Placebo, Fixed, Learned/Repr, online).
Data-keyed inclusion rules (generic value-type conditions, never task names):
  * text present (any string in inputs/outputs) -> signed index `at`, signed slice `sl`, `cap`; tools toks{d,a,w,s,n}
  * decimal-string inputs (a top-level input, or an element of a top-level list input, matches -?D+(.D+)?) -> dsh, drnd
  * output literals: public output strings occurring >= 2 times and in no public input (<= 3, len <= 16) -> dflt{v}, first{p, v}
  * output affixes: the longest common prefix / suffix of the public output strings (1..12 chars) -> cat templates
  * zero padding: some public output is a digit string with a leading 0 -> pad to each public output width
  * output shapes: character-class shapes of the public outputs (<= 3) -> predicates shape(x) == s
New formatting lambdas (V) feed map and fn only; key lambdas (U) feed every lambda-parameterised tool as in Wave 38."""
from __future__ import annotations

from nexus import w38_scope as S38

X = ["x"]
AT = (-2, -1, 0, 1, 2, 3)
SL = ((0, 1), (0, 2), (0, 3), (0, 4), (1, None), (2, None), (3, None), (None, -1), (None, -2), (-1, None), (-2, None),
      (-3, None), (-4, None))


def _strings(v, acc, d=0):
    if d > 4:
        return
    if isinstance(v, str):
        acc.append(v)
    elif isinstance(v, list):
        for e in v[:16]:
            _strings(e, acc, d + 1)
    elif isinstance(v, dict):
        for e in v.values():
            _strings(e, acc, d + 1)


def is_dec(s):
    if not isinstance(s, str) or not s or len(s) > 40:
        return False
    b = s[1:] if s[0] == "-" else s
    ip, dot, fp = b.partition(".")
    return ip.isascii() and ip.isdigit() and (not dot or (fp.isascii() and fp.isdigit()))


def shape(s):
    return "".join("9" if "0" <= c <= "9" else "A" if "A" <= c <= "Z" else "a" if "a" <= c <= "z" else c for c in s)


def _lcp(ss):
    p = ss[0]
    for s in ss[1:]:
        while not s.startswith(p):
            p = p[:-1]
    return p


def features5(public, query):
    fe = S38.features(public, query)
    texts = []
    for x, y in public:
        _strings(x, texts); _strings(y, texts)
    _strings(query, texts)
    ins = [x for x, _ in public] + [query]
    flat_in = [e for x in ins for e in (x if isinstance(x, list) else [x])]
    outs = [y for _, y in public]
    so = [y for y in outs if isinstance(y, str)]
    ins_text = []
    for x in ins:
        _strings(x, ins_text)
    fe["text"] = bool(texts)
    fe["decimal"] = any(is_dec(e) for e in flat_in)
    fe["literals"] = sorted({y for y in so if 0 < len(y) <= 16 and so.count(y) >= 2 and not any(y in t for t in ins_text)})[:3]
    fe["prefix"] = fe["suffix"] = ""
    fe["widths"], fe["shapes"] = [], []
    if len(so) == len(outs) and len(so) >= 2:
        pre, suf = _lcp(so), _lcp([s[::-1] for s in so])[::-1]
        fe["prefix"] = pre if 0 < len(pre) <= 12 and pre not in so else ""
        fe["suffix"] = suf if 0 < len(suf) <= 12 and suf not in so else ""
        if any(len(s) > 1 and s[0] == "0" and s.isdigit() for s in so):
            fe["widths"] = sorted({len(s) for s in so})[:2]
        fe["shapes"] = sorted({shape(s) for s in so if s})[:3]
    return fe


def lambdas5(fe):
    U, P = S38.lambdas(fe)
    V = []
    if fe["text"]:
        U += [["at", X, i] for i in AT] + [["sl", X, a, b] for a, b in SL] + [["cap", X]]
    if fe["decimal"]:
        V += [["dsh", X, e] for e in (-3, -2, -1, 0, 1, 2, 3)]
        V += [["drnd", X, k, m, 1] for k in range(-3, 4) for m in ("h", "f", "c")]
        V += [["drnd", X, k, "h", 5] for k in range(0, 4)]
    pre, suf = fe["prefix"], fe["suffix"]
    if pre:
        V.append(["cat", ["c", pre], X])
    if suf:
        V.append(["cat", X, ["c", suf]])
    if pre and suf:
        V.append(["cat", ["cat", ["c", pre], X], ["c", suf]])
    V += [["pad", X, n, "0"] for n in fe["widths"]]
    P += [["eq", ["shape", X], ["c", s]] for s in fe["shapes"]]
    return U, V, P


def scope(public, query, depth=2):
    fe = features5(public, query)
    U, V, P = lambdas5(fe)
    T = S38.scope(public, query, depth)["tools"]
    have = {S38_key(t) for t in T}
    new = [{"op": "map", "f": u} for u in U + V] + [{"op": "filter", "p": p} for p in P]
    new += [{"op": "sortby", "f": u, "desc": d} for u in U for d in (False, True)]
    new += [{"op": g, "f": u} for u in U for g in ("groupby", "countby")]
    new += [{"op": "best", "f": u} for u in U]
    new += [{"op": "fn", "f": u} for u in U + V if u != X]
    if fe["text"]:
        new += [{"op": "toks", "c": c} for c in ("d", "a", "w", "s", "n")]
    for v in fe["literals"]:
        new += [{"op": "dflt", "v": v}] + [{"op": "first", "p": p, "v": v} for p in P]
    if fe["shapes"]:
        new += [{"op": "first", "p": ["eq", ["shape", X], ["c", s]], "v": ""} for s in fe["shapes"]]
    for t in new:
        k = S38_key(t)
        if k not in have:
            have.add(k); T.append(t)
    return {"kind": "exhaustive", "tools": T, "max_depth": depth}


def S38_key(t):
    import json
    return json.dumps(t, sort_keys=True, separators=(",", ":"))
