"""Wave 38 declared scope (shared declaration; NOT LOCKED). A deterministic function of the task's PUBLIC data and a fixed
config: identical for every arm in any deterministic comparison (matched certification strength).
Lambda pools (unary U, predicates P) are enumerated from a fixed grammar of depth <= 2 with constants from a fixed set,
fields observed in the inputs, and delimiters present in the inputs."""
from __future__ import annotations

DELIMS = (",", " ", "-", ":", ";", "|", "/", ".", "=")
X = ["x"]


def _walk(v, acc, d=0):
    if d > 4:
        return
    if isinstance(v, dict):
        if set(v) == {"nodes", "edges"}:
            acc["graph"] = True
        for k, e in v.items():
            acc["fields"].add(k)
            _walk(e, acc, d + 1)
    elif isinstance(v, list):
        if v and all(isinstance(r, list) for r in v) and all(isinstance(c, int) for r in v for c in r):
            acc["grid"] = (len(v), len(v[0]) if v else 0)
            acc["colors"] |= {c for r in v for c in r}
        for e in v[:8]:
            _walk(e, acc, d + 1)
    elif isinstance(v, str):
        acc["delims"] |= {d_ for d_ in DELIMS if d_ in v}


def features(public, query):
    acc = {"fields": set(), "delims": set(), "colors": set(), "grid": None, "graph": False}
    for x, y in public:
        _walk(x, acc); _walk(y, acc)
    _walk(query, acc)
    for k in ("cells", "c"):
        acc["fields"].discard(k)
    # structural fields produced by tools (not visible in raw inputs), added by input kind
    acc["fields"] |= {"key", "count"}
    if acc["grid"]:
        acc["fields"] |= {"size", "color", "r"}
    if acc["graph"]:
        acc["fields"] |= {"node", "deg"}
    return acc


def lambdas(fe):
    U = [X, ["len", X], ["fst", X], ["lst", X], ["low", X], ["up", X], ["int", X], ["str", X],
         ["add", X, ["c", 1]], ["sub", X, ["c", 1]], ["mul", X, ["c", 2]], ["mod", X, ["c", 2]], ["mod", X, ["c", 3]],
         ["if", ["gt", X, ["c", 0]], X, ["c", 0]], ["if", ["even", X], X, ["c", 0]], ["up", ["fst", X]], ["low", ["fst", X]]]
    for d in sorted(fe["delims"]):
        U += [["bef", X, d], ["aft", X, d], ["int", ["aft", X, d]]]
    for k in sorted(fe["fields"]):
        F = ["f", k]
        U += [F, ["int", F], ["len", F], ["fst", F]]
    P = [["gt", X, ["c", 0]], ["gt", X, ["c", 1]], ["gt", X, ["c", 2]], ["lt", X, ["c", 2]], ["eq", X, ["c", 0]],
         ["eq", X, ["c", 1]], ["even", X], ["isdig", X], ["not", ["isdig", X]], ["gt", ["len", X], ["c", 1]],
         ["eq", X, ["c", ""]], ["not", ["eq", X, ["c", ""]]]]
    for k in sorted(fe["fields"]):
        F = ["f", k]
        P += [["gt", F, ["c", 0]], ["gt", F, ["c", 1]], ["gt", F, ["c", 2]], ["eq", F, ["c", 0]], ["eq", F, ["c", 1]],
              ["eq", F, ["c", None]], ["not", ["eq", F, ["c", None]]], ["even", F]]
    return U, P


def scope(public, query, depth=2):
    fe = features(public, query)
    U, P = lambdas(fe)
    T = []
    T += [{"op": "map", "f": u} for u in U]
    T += [{"op": "filter", "p": p} for p in P]
    T += [{"op": "sortby", "f": u, "desc": d} for u in U for d in (False, True)]
    T += [{"op": g, "f": u} for u in U for g in ("groupby", "countby")]
    T += [{"op": o, "o": a, "init": i} for o in ("fold", "scan") for a, i in (("add", 0), ("mul", 1), ("max", -10**6),
                                                                            ("min", 10**6), ("cat", ""))]
    T += [{"op": o, "n": n} for o in ("take", "drop") for n in (1, 2)]
    T += [{"op": o} for o in ("rev", "uniq", "flat", "enum", "pairs", "len", "chars", "words", "strip")]
    T += [{"op": "best", "f": u} for u in U]
    for d in sorted(fe["delims"]):
        T += [{"op": "split", "d": d}, {"op": "join", "d": d}]
    T += [{"op": "join", "d": ""}]
    for k in sorted(fe["fields"]):
        T += [{"op": "get", "k": k}, {"op": "proj", "ks": [k]}, {"op": "tjoin", "k": k}, {"op": "fill", "k": k, "v": 0}]
    if fe["grid"]:
        h, w = fe["grid"]
        T += [{"op": "objs", "conn": c, "bg": 0} for c in (4, 8)]
        T += [{"op": "paint", "bg": 0, "h": h, "w": w}]
        for col in sorted(fe["colors"] - {0})[:4]:
            T += [{"op": "recolor_if", "p": p, "color": col} for p in (["gt", ["f", "size"], ["c", 1]], ["gt", ["f", "size"], ["c", 2]],
                                                                      ["eq", ["f", "size"], ["c", 1]])]
    if fe["graph"]:
        T += [{"op": "reach", "s": 0}, {"op": "topo"}, {"op": "indeg"}, {"op": "outdeg"}]
    return {"kind": "exhaustive", "tools": T, "max_depth": depth}
