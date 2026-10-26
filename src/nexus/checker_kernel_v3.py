"""NEXUS Checker Kernel v3 (separately versioned; v1 and v2 are unchanged). Specification: docs/NEXUS_CHECKER_V3_SPEC.md.
Standard library only; imports nothing from NEXUS; its interpreter is written anew (no shared code with v2 or the
prover). Verdicts are computed by bottom-up shared evaluation over exact value vectors on all public inputs + the
query, with independently verified rewrite proofs. DO NOT MODIFY after its pin (src/nexus/checker_kernel_v3.sha256)
without explicit owner approval (AGENTS.md RULE 2).
"""
import itertools
import json

VERSION = 3
MAX_DEPTH = 4
STEP_BOUND = 100_000
MAX_EDGE_EVALS = 2_000_000
MAX_NODES = 500_000
ERR = None                      # error marker inside node keys / value vectors (never a JSON value here)
ERROR_ANSWER = "<ERROR>"        # v2-compatible answer key for an erroring query point


class Bad(Exception):
    pass


def canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


# --------------------------------------------------------------------------- representation set (v2 contract)
def _int(v):
    return type(v) is int


def _scalar(v):
    if _int(v):
        return -10**6 <= v <= 10**6
    if type(v) is bool:
        return True
    if type(v) is str:
        return len(v) <= 32
    return False


def is_grid(v):
    if type(v) is not list or not 1 <= len(v) <= 12 or any(type(r) is not list for r in v):
        return False
    w = len(v[0])
    return 1 <= w <= 12 and all(len(r) == w for r in v) and all(_int(c) and 0 <= c <= 9 for r in v for c in r)


def valid(v, depth=0):
    if depth > 4:
        raise Bad("nesting")
    if _scalar(v):
        return
    if type(v) is list:
        if is_grid(v):
            return
        if len(v) > 64:
            raise Bad("list length")
        for e in v:
            valid(e, depth + 1)
        return
    if type(v) is dict:
        ks = set(v)
        if ks == {"objects"}:
            objs = v["objects"]
            if type(objs) is not list:
                raise Bad("objects")
            total = 0
            for o in objs:
                if type(o) is not dict:
                    raise Bad("object")
                total += len(o.get("cells", []))
            if total > 144:
                raise Bad("objects size")
            return
        if ks == {"nodes", "edges"}:
            if len(v["nodes"]) > 144 or len(v["edges"]) > 2048:
                raise Bad("graph size")
            return
        if ks == {"counts"}:
            if len(v["counts"]) > 64:
                raise Bad("counter size")
            return
        if len(v) > 8 or any(type(k) is not str or not _scalar(e) for k, e in v.items()):
            raise Bad("record")
        return
    raise Bad("type")


def size(v):
    if type(v) in (list, str):
        return sum(len(r) for r in v) if is_grid(v) else len(v)
    if type(v) is dict:
        if "objects" in v and type(v["objects"]) is list:
            return sum(len(o.get("cells", [])) for o in v["objects"] if type(o) is dict)
        if "edges" in v and type(v["edges"]) is list:
            return len(v["edges"])
        if "counts" in v and type(v["counts"]) is list:
            return len(v["counts"])
        return len(v)
    return 1


# --------------------------------------------------------------------------- interpreter (independent)
def _seq(x):
    if type(x) is not list:
        raise Bad("not a sequence")
    return x


def _ints(x):
    x = _seq(x)
    for e in x:
        if not _int(e):
            raise Bad("not ints")
    return x


def _field(item, path):
    if path == ".":
        return item
    if type(item) is dict and path in item:
        return item[path]
    raise Bad("field")


def _holds(p, item):
    v = _field(item, p["path"])
    if p["cmp"] == "eq":
        return v == p["val"]
    if not (_int(v) and _int(p["val"])):
        return False
    return v >= p["val"] if p["cmp"] == "ge" else v <= p["val"]


def _perm(xs, path, desc):
    n = len(xs)
    if path == "#":
        return list(range(n - 1, -1, -1)) if desc else list(range(n))
    vals = [_field(e, path) for e in xs]
    if desc:
        for e in vals:
            if not _int(e):
                raise Bad("desc on non-int")
        return sorted(range(n), key=lambda i: (-vals[i], i))
    return sorted(range(n), key=lambda i: (vals[i], i))


def _grid_in(x):
    if not is_grid(x):
        raise Bad("not a grid")
    return x


def _objs_in(x):
    if type(x) is not dict or set(x) != {"objects"}:
        raise Bad("not objects")
    return x["objects"]


def _counter_in(x):
    if type(x) is not dict or set(x) != {"counts"}:
        raise Bad("not a counter")
    return x["counts"]


def _graph_in(x):
    if type(x) is not dict or set(x) != {"nodes", "edges"}:
        raise Bad("not a graph")
    return x


def _components(g, conn, bg):
    H, W = len(g), len(g[0])
    steps = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if conn == 8:
        steps += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    label = [[None] * W for _ in range(H)]
    out = []
    for r in range(H):
        for c in range(W):
            if g[r][c] == bg or label[r][c] is not None:
                continue
            col, stack, cells = g[r][c], [(r, c)], []
            label[r][c] = len(out)
            while stack:
                a, b = stack.pop()
                cells.append([a, b])
                for da, db in steps:
                    u, w = a + da, b + db
                    if 0 <= u < H and 0 <= w < W and label[u][w] is None and g[u][w] == col:
                        label[u][w] = len(out)
                        stack.append((u, w))
            out.append({"color": col, "cells": sorted(cells)})
    out.sort(key=lambda o: (o["cells"][0], o["color"]))
    return {"objects": out}


def run_op(s, x):
    """One op on one value (raises Bad on any failure). Pure function of (s, x)."""
    op = s["op"]
    if op == "F":
        return [e for e in _seq(x) if _holds(s["pred"], e)]
    if op == "S":
        xs = _seq(x)
        return [xs[i] for i in _perm(xs, s["path"], s["desc"])][: s["k"]]
    if op == "Sort":
        xs = _seq(x)
        return [xs[i] for i in _perm(xs, s["path"], s["desc"])]
    if op == "comp":
        xs = _seq(x)
        n, res, seen = len(xs), [], set()
        for pos, i in enumerate(_perm(xs, s["path"], s["desc"])):
            e, c = xs[i], s["cond"]
            if c == "all":
                keep = True
            elif c == "head":
                keep = pos < s["cparam"]
            elif c == "tail":
                keep = pos >= n - s["cparam"]
            elif c == "first_occ":
                kk = canon(_field(e, s["cparam"]))
                keep = kk not in seen
                seen.add(kk)
            elif c == "pred":
                keep = _holds(s["cparam"], e)
            else:
                raise Bad("cond")
            if keep:
                res.append(_field(e, s["tparam"]) if s["transform"] == "proj" else e)
        return res
    if op == "proj":
        return [_field(e, s["path"]) for e in _seq(x)]
    if op == "map_add":
        return [e + s["c"] for e in _ints(x)]
    if op == "map_mul":
        return [e * s["c"] for e in _ints(x)]
    if op == "map_mod":
        if s["c"] == 0:
            raise Bad("mod 0")
        return [e % s["c"] for e in _ints(x)]
    if op == "prefix_sum":
        return list(itertools.accumulate(_ints(x)))
    if op == "running_max":
        return list(itertools.accumulate(_ints(x), max))
    if op == "diff":
        xs = _ints(x)
        return [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    if op == "rotate":
        xs = _seq(x)
        if not xs:
            return []
        k = s["k"] % len(xs)
        return xs[k:] + xs[:k]
    if op == "run_heads":
        xs = _seq(x)
        return [e for i, e in enumerate(xs) if i == 0 or canon(xs[i - 1]) != canon(e)]
    if op == "group_count":
        counts = {}
        for e in _seq(x):
            kk = canon(_field(e, s["path"]))
            counts[kk] = counts.get(kk, 0) + 1          # dicts keep first-insertion order
        return list(counts.values())
    if op == "repeat":
        for _ in range(s["n"]):
            x = _seq(run_op(s["body"], x))
        return x
    if op == "grid_coord":
        g = _grid_in(x)
        H, W = len(g), len(g[0])
        return [[g[(s["a"] * i + s["b"]) % H][(s["c"] * j + s["d"]) % W] for j in range(W)] for i in range(H)]
    if op == "grid_connect":
        g = _grid_in(x)
        H, W = len(g), len(g[0])
        res = [list(r) for r in g]
        reached = {(i, j) for i in range(H) for j in range(W) if g[i][j] == s["seed"]}
        stack = list(reached)
        while stack:
            i, j = stack.pop()
            for dr, dc in s["moves"]:
                a, b = i + dr, j + dc
                if 0 <= a < H and 0 <= b < W and (a, b) not in reached and g[a][b] == s["passable"]:
                    reached.add((a, b))
                    res[a][b] = s["fill"]
                    stack.append((a, b))
        return res
    if op == "grid_cellwise":
        g = _grid_in(x)
        H, W = len(g), len(g[0])
        table = {(r[0], r[1]): r[2] for r in s["table"]}
        res = []
        for i in range(H):
            row = []
            for j in range(W):
                pair = (g[i][j], g[(i + s["dr"]) % H][(j + s["dc"]) % W])
                if pair not in table:
                    raise Bad("table miss")
                row.append(table[pair])
            res.append(row)
        return res
    if op == "enc_objects":
        return _components(_grid_in(x), s["conn"], s["background"])
    if op == "dec_objects":
        objs = _objs_in(x)
        cells = [cl for o in objs for cl in o["cells"]]
        if "shape" in s:
            H, W = s["shape"]
        elif cells:
            H, W = 1 + max(cl[0] for cl in cells), 1 + max(cl[1] for cl in cells)
        else:
            raise Bad("no shape")
        if not (1 <= H <= 12 and 1 <= W <= 12):
            raise Bad("shape")
        g = [[s["background"]] * W for _ in range(H)]
        for o in objs:
            for r, c in o["cells"]:
                if not (0 <= r < H and 0 <= c < W):
                    raise Bad("cell outside")
                g[r][c] = o["color"]
        return g
    if op == "ir_objects_filter_size":
        return {"objects": [o for o in _objs_in(x) if s["min"] <= len(o["cells"]) <= s["max"]]}
    if op == "ir_objects_recolor":
        return {"objects": [{"color": s["color"], "cells": o["cells"]} for o in _objs_in(x)]}
    if op == "ir_objects_keep_color":
        return {"objects": [o for o in _objs_in(x) if o["color"] == s["color"]]}
    if op == "ir_objects_sizes":
        return [len(o["cells"]) for o in _objs_in(x)]
    if op == "enc_counter":
        acc = {}
        for e in _seq(x):
            v = _field(e, s["path"])
            if not _scalar(v):
                raise Bad("counter key")
            kk = canon(v)
            acc[kk] = [v, acc[kk][1] + 1] if kk in acc else [v, 1]
        return {"counts": [acc[k] for k in sorted(acc)]}
    if op == "dec_counter":
        return [list(p) for p in _counter_in(x)]
    if op == "ir_counter_top":
        cs = _counter_in(x)
        best = sorted(cs, key=lambda p: (-p[1], canon(p[0])))[: s["k"]]
        return {"counts": sorted(best, key=lambda p: canon(p[0]))}
    if op == "ir_counter_keys":
        return [p[0] for p in _counter_in(x)]
    if op == "enc_graph":
        g = _grid_in(x)
        H, W = len(g), len(g[0])
        nodes = [i * W + j for i in range(H) for j in range(W) if g[i][j] == s["passable"]]
        member = set(nodes)
        edges = []
        for nd in nodes:
            i, j = divmod(nd, W)
            for dr, dc in s["moves"]:
                a, b = i + dr, j + dc
                if 0 <= a < H and 0 <= b < W and a * W + b in member:
                    edges.append([nd, a * W + b])
        return {"nodes": nodes, "edges": sorted(edges)}
    if op == "ir_graph_reach":
        gr = _graph_in(x)
        nodes = set(gr["nodes"])
        succ = {}
        for a, b in gr["edges"]:
            succ.setdefault(a, []).append(b)
        reached = {sd for sd in s["seeds"] if sd in nodes}
        stack = list(reached)
        while stack:
            for b in succ.get(stack.pop(), []):
                if b not in reached:
                    reached.add(b)
                    stack.append(b)
        return sorted(reached)
    if op == "ir_graph_degrees":
        gr = _graph_in(x)
        deg = {nd: 0 for nd in gr["nodes"]}
        for a, _b in gr["edges"]:
            if a in deg:
                deg[a] += 1
        return {"counts": [[nd, deg[nd]] for nd in sorted(deg)]}
    if op == "enc_chars":
        if type(x) is not str:
            raise Bad("not a string")
        return list(x)
    if op == "dec_chars":
        xs = _seq(x)
        if len(xs) > 32 or any(type(c) is not str or len(c) != 1 for c in xs):
            raise Bad("not chars")
        return "".join(xs)
    if op == "enc_cells":
        g = _grid_in(x)
        return [c for r in g for c in r]
    raise Bad("unknown op")


def apply_tool(s, x):
    """(value, cost). `seq` applies its body with a validity check after each body op."""
    if s["op"] == "seq":
        cost = 0
        for b in s["body"]:
            cost += 1 + size(x)
            x = run_op(b, x)
            valid(x)
        return x, cost
    cost = 1 + size(x)
    y = run_op(s, x)
    return y, cost


def run_chain(chain, x):
    """Direct application of a chain to one value: (value or ERR, cost)."""
    total = 0
    try:
        for s in chain:
            x, c = apply_tool(s, x)
            total += c
            valid(x)
            if total > STEP_BOUND:
                return ERR, total
        return x, total
    except Exception:
        return ERR, total


# --------------------------------------------------------------------------- spec validation (v2 contract)
def _ok_ints(s, names, lo=-12, hi=12):
    return all(_int(s.get(n)) and lo <= s[n] <= hi for n in names)


def _ok_pred(p):
    return type(p) is dict and set(p) == {"path", "cmp", "val"} and p["cmp"] in ("ge", "le", "eq")


def _ok_moves(m):
    return (type(m) is list and 1 <= len(m) <= 16 and
            all(type(d) is list and len(d) == 2 and all(_int(u) and abs(u) <= 3 for u in d) for d in m))


def known(s):
    if type(s) is not dict or "op" not in s:
        return False
    op = s["op"]
    try:
        if op == "F":
            return _ok_pred(s["pred"])
        if op == "S":
            return _int(s["k"]) and 0 <= s["k"] <= 64 and type(s["path"]) is str and type(s["desc"]) is bool
        if op == "Sort":
            return type(s["path"]) is str and type(s["desc"]) is bool
        if op == "comp":
            c = s["cond"]
            okc = {"all": s["cparam"] is None, "head": _int(s["cparam"]), "tail": _int(s["cparam"]),
                   "first_occ": type(s["cparam"]) is str, "pred": _ok_pred(s["cparam"])}.get(c, False)
            return okc and s["transform"] in ("id", "proj") and type(s["desc"]) is bool
        if op in ("proj", "group_count", "enc_counter"):
            return type(s["path"]) is str
        if op in ("map_add", "map_mul", "map_mod"):
            return _int(s["c"]) and abs(s["c"]) <= 100
        if op in ("prefix_sum", "running_max", "diff", "run_heads", "dec_counter", "enc_chars", "dec_chars",
                  "enc_cells", "ir_counter_keys", "ir_graph_degrees", "ir_objects_sizes"):
            return set(s) == {"op"}
        if op == "rotate":
            return _int(s["k"]) and 0 <= s["k"] <= 64
        if op == "repeat":
            return _int(s["n"]) and 1 <= s["n"] <= 4 and known(s["body"]) and s["body"]["op"] != "repeat"
        if op == "grid_coord":
            return _ok_ints(s, ("a", "b", "c", "d"))
        if op == "grid_connect":
            return _ok_moves(s["moves"]) and _ok_ints(s, ("passable", "seed", "fill"), 0, 9)
        if op == "grid_cellwise":
            t = s["table"]
            if type(t) is not list or not all(type(r) is list and len(r) == 3 and all(_int(u) and 0 <= u <= 9 for u in r)
                                              for r in t):
                return False
            ks = [(r[0], r[1]) for r in t]
            return len(set(ks)) == len(ks) and _ok_ints(s, ("dr", "dc"), -3, 3)
        if op == "enc_objects":
            return s["conn"] in (4, 8) and _ok_ints(s, ("background",), 0, 9)
        if op == "dec_objects":
            return _ok_ints(s, ("background",), 0, 9) and ("shape" not in s or (
                type(s["shape"]) is list and len(s["shape"]) == 2 and all(_int(u) for u in s["shape"])))
        if op == "ir_objects_filter_size":
            return _ok_ints(s, ("min", "max"), 0, 144)
        if op in ("ir_objects_recolor", "ir_objects_keep_color"):
            return _ok_ints(s, ("color",), 0, 9)
        if op == "ir_counter_top":
            return _ok_ints(s, ("k",), 1, 64)
        if op == "enc_graph":
            return _ok_moves(s["moves"]) and _ok_ints(s, ("passable",), 0, 9)
        if op == "ir_graph_reach":
            return type(s["seeds"]) is list and all(_int(u) and 0 <= u < 144 for u in s["seeds"])
        if op == "seq":
            b = s["body"]
            return type(b) is list and 1 <= len(b) <= 4 and all(type(e) is dict and e.get("op") != "seq" and known(e)
                                                                for e in b)
    except (KeyError, TypeError):
        return False
    return False


# --------------------------------------------------------------------------- proved rewrite axioms (spec §3)
def _nondecreasing_homog(v):
    if type(v) is not list:
        return False
    if all(_int(e) for e in v) or all(type(e) is str for e in v):
        return all(v[i] <= v[i + 1] for i in range(len(v) - 1))
    return False


AXIOMS = {
    "sort_fixpoint": (lambda s: s == {"op": "Sort", "path": ".", "desc": False}, _nondecreasing_homog),
    "runheads_fixpoint": (lambda s: s == {"op": "run_heads"},
                          lambda v: type(v) is list and all(canon(v[i]) != canon(v[i + 1]) for i in range(len(v) - 1))),
    "runmax_fixpoint": (lambda s: s == {"op": "running_max"},
                        lambda v: type(v) is list and all(_int(e) for e in v) and _nondecreasing_homog(v)),
    "top_fixpoint": (lambda s: s.get("op") == "ir_counter_top" and set(s) == {"op", "k"},
                     None),
}


def _top_cond(k):
    def cond(v):
        if type(v) is not dict or set(v) != {"counts"} or type(v["counts"]) is not list or len(v["counts"]) > k:
            return False
        ks = [canon(p[0]) for p in v["counts"] if type(p) is list and len(p) == 2]
        return len(ks) == len(v["counts"]) and ks == sorted(ks)
    return cond


# --------------------------------------------------------------------------- the check
def _abstain(reason, **kw):
    return dict(label="ABSTAIN", reason=reason, checker_version=VERSION, **kw)


def check(evidence):
    try:
        if evidence.get("checker_version") != VERSION:
            return _abstain("wrong_checker_version")
        pub = [(p[0], p[1]) for p in evidence["public"]]
        q, claimed = evidence["query"], evidence["claimed_answer"]
        cand = list(evidence["candidate"])
        scope = evidence["scope"]
        tools, D, kind = list(scope["tools"]), int(scope["max_depth"]), scope["kind"]
        lemmas = list(evidence.get("lemmas", []))
        proofs = list(evidence.get("proofs", []))
    except Exception:
        return _abstain("malformed")
    if kind not in ("exhaustive", "proposal") or not 1 <= D <= MAX_DEPTH or not pub or not tools:
        return _abstain("malformed")
    if not all(known(s) for s in tools + cand):
        return _abstain("unsupported")
    try:
        for v in [x for x, _ in pub] + [y for _, y in pub] + [q]:
            valid(v)
    except Exception:
        return _abstain("unsupported_value")
    tool_keys = [canon(s) for s in tools]
    if not 1 <= len(cand) <= D or not all(canon(s) in set(tool_keys) for s in cand):
        return _abstain("candidate_outside_scope")
    for x, y in pub:
        o, _ = run_chain(cand, x)
        if o is ERR or canon(o) != canon(y):
            return _abstain("candidate_fails")
    co, _ = run_chain(cand, q)
    if co is ERR or canon(co) != canon(claimed):
        return _abstain("candidate_fails")
    if lemmas:
        return _abstain("v2_lemmas_not_accepted")
    shortcut = {}
    for pf in proofs:
        try:
            ax, i = pf["axiom"], pf["tool"]
            if ax not in AXIOMS or not _int(i) or not 0 <= i < len(tools) or not AXIOMS[ax][0](tools[i]):
                return _abstain("bad_proof")
        except Exception:
            return _abstain("bad_proof")
        shortcut[i] = _top_cond(tools[i]["k"]) if ax == "top_fixpoint" else AXIOMS[ax][1]
    return _shared_eval(pub, q, claimed, tools, D, kind, shortcut)


def _shared_eval(pub, q, claimed, tools, D, kind, shortcut):
    X = [x for x, _ in pub] + [q]
    P, T = len(pub), len(tools)
    targets = [canon(y) for _, y in pub]
    nodes = {}                       # key -> value vector
    edges = {}                       # (key, tool) -> (child key, cost vector)
    work = {"edge_evals": 0, "point_evals": 0, "steps": 0, "proofs_applied": 0, "proof_checks": 0}

    def node_key(vals):
        return tuple(None if v is ERR else canon(v) for v in vals)

    def intern(vals):
        k = node_key(vals)
        if k not in nodes:
            if len(nodes) >= MAX_NODES:
                raise OverflowError
            nodes[k] = vals
        return k

    def edge(k, ti):
        e = edges.get((k, ti))
        if e is not None:
            return e
        work["edge_evals"] += 1
        if work["edge_evals"] > MAX_EDGE_EVALS:
            raise OverflowError
        vals, s = nodes[k], tools[ti]
        cond = shortcut.get(ti)
        if cond is not None:
            work["proof_checks"] += 1
            if all(v is ERR or cond(v) for v in vals):
                work["proofs_applied"] += 1
                cost = [0 if v is ERR else 1 + size(v) for v in vals]
                e = edges[(k, ti)] = (k, cost)
                return e
        out, cost = [], []
        for v in vals:
            if v is ERR:
                out.append(ERR); cost.append(0)
                continue
            work["point_evals"] += 1
            try:
                y, c = apply_tool(s, v)
                valid(y)
            except Exception:
                y, c = ERR, 0
            work["steps"] += c
            out.append(y); cost.append(c)
        e = edges[(k, ti)] = (intern(out), cost)
        return e

    try:
        root = intern(list(X))
        layer = {root: [1, (), [0] * len(X), [0] * len(X)]}
        answers, first, fitting = {}, {}, 0
        for depth in range(1, D + 1):
            nxt = {}
            for k in layer:
                cnt, mc, smin, smax = layer[k]
                for ti in range(T):
                    ck, cost = edge(k, ti)
                    cvals = nodes[ck]
                    nmin, nmax, forced = [], [], False
                    for j, v in enumerate(cvals):
                        if v is ERR:
                            nmin.append(0); nmax.append(0)
                            continue
                        lo, hi = smin[j] + cost[j], smax[j] + cost[j]
                        if hi <= STEP_BOUND:
                            nmin.append(lo); nmax.append(hi)
                        elif lo > STEP_BOUND:
                            forced = True
                            nmin.append(-1); nmax.append(-1)
                        else:
                            return _abstain("step_bound_straddle")
                    if forced:
                        ck = intern([ERR if nmin[j] == -1 else v for j, v in enumerate(cvals)])
                        nmin = [0 if u == -1 else u for u in nmin]
                        nmax = [0 if u == -1 else u for u in nmax]
                    chain = mc + (ti,)
                    ent = nxt.get(ck)
                    if ent is None:
                        nxt[ck] = [cnt, chain, nmin, nmax]
                    else:
                        ent[0] += cnt
                        if chain < ent[1]:
                            ent[1] = chain
                        ent[2] = [min(a, b) for a, b in zip(ent[2], nmin)]
                        ent[3] = [max(a, b) for a, b in zip(ent[3], nmax)]
            layer_first = {}
            for k, (cnt, mc, _a, _b) in nxt.items():
                if list(k[:P]) != targets:
                    continue
                fitting += cnt
                ak = ERROR_ANSWER if k[P] is None else k[P]
                answers[ak] = answers.get(ak, 0) + cnt
                if ak not in first and (ak not in layer_first or mc < layer_first[ak]):
                    layer_first[ak] = mc
            for ak, mc in layer_first.items():
                first.setdefault(ak, list(mc))
            layer = nxt
    except OverflowError:
        return _abstain("budget_exhausted", **work)
    total = sum(T ** k for k in range(1, D + 1))
    res = dict(fitting=fitting, answers=len(answers), chains_total=total, chains_checked=total, nodes=len(nodes),
               checker_version=VERSION, **work)
    if len(answers) > 1:
        wk = sorted(first)[:2]
        return dict(label="AMBIGUOUS", k=len(answers), k_exact=(kind == "exhaustive"),
                    witnesses=[dict(chain=first[w], answer=w) for w in wk], **res)
    if len(answers) == 1 and ERROR_ANSWER in answers:
        return dict(label="ABSTAIN", reason="query_error", **res)
    if len(answers) != 1 or canon(claimed) not in answers:
        return dict(label="ABSTAIN", reason="claimed_not_unique", **res)
    return dict(label="exhaustive_UNIQUE" if kind == "exhaustive" else "proposal_relative_UNIQUE", **res)
