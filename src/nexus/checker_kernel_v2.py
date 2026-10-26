"""NEXUS Checker Kernel v2 (separately versioned; v1 `checker_kernel.py` is unchanged). Specification:
docs/NEXUS_CHECKER_V2_SPEC.md. Standard library only; imports nothing from NEXUS. DO NOT MODIFY after its pin
(src/nexus/checker_kernel_v2.sha256) without explicit owner approval.
"""
import itertools
import json

VERSION = 2
MAX_DEPTH = 4
MAX_CHAINS = 3_000_000
MAX_STEPS_APP = 100_000
MAX_STEPS_CHECK = 200_000_000
ERROR = "<ERROR>"


class _Err(Exception):
    pass


def key(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


# --------------------------------------------------------------------------- value bounds
def _isint(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _scalar_ok(v):
    if _isint(v):
        return abs(v) <= 10**6
    if isinstance(v, bool):
        return True
    if isinstance(v, str):
        return len(v) <= 32
    return False


def _grid(v):
    return (isinstance(v, list) and 1 <= len(v) <= 12 and all(isinstance(r, list) for r in v) and
            1 <= len(v[0]) <= 12 and all(len(r) == len(v[0]) for r in v) and
            all(_isint(c) and 0 <= c <= 9 for r in v for c in r))


def check_value(v, depth=0):
    """Raise _Err unless v is inside the declared representation set."""
    if depth > 4:
        raise _Err("nesting")
    if _scalar_ok(v):
        return
    if isinstance(v, list):
        if _grid(v):
            return
        if len(v) > 64:
            raise _Err("list too long")
        for x in v:
            check_value(x, depth + 1)
        return
    if isinstance(v, dict):
        if set(v) == {"objects"}:
            objs = v["objects"]
            if not isinstance(objs, list) or sum(len(o.get("cells", [])) for o in objs) > 144:
                raise _Err("objects")
            return
        if set(v) == {"nodes", "edges"}:
            if len(v["nodes"]) > 144 or len(v["edges"]) > 2048:
                raise _Err("graph")
            return
        if set(v) == {"counts"}:
            if len(v["counts"]) > 64:
                raise _Err("counter")
            return
        if len(v) > 8 or not all(isinstance(k, str) and _scalar_ok(x) for k, x in v.items()):
            raise _Err("record")
        return
    raise _Err("type")


# --------------------------------------------------------------------------- interpreter
class _Steps:
    def __init__(self):
        self.n = 0

    def add(self, k):
        self.n += k
        if self.n > MAX_STEPS_APP:
            raise _Err("step bound")


def _get(item, path):
    if path == ".":
        return item
    if isinstance(item, dict) and path in item:
        return item[path]
    raise _Err("path")


def _num(v):
    return _isint(v)


def _pred(p, item):
    v = _get(item, p["path"])
    if p["cmp"] == "eq":
        return v == p["val"]
    if not _num(v) or not _num(p["val"]):
        return False
    return v >= p["val"] if p["cmp"] == "ge" else v <= p["val"]


def _order(xs, path, desc):
    idx = list(range(len(xs)))
    if path == "#":
        return idx[::-1] if desc else idx
    vals = [_get(x, path) for x in xs]
    if desc and not all(_num(v) for v in vals):
        raise _Err("desc on non-number")
    try:
        return sorted(idx, key=lambda i: ((-vals[i]) if desc else vals[i], i))
    except TypeError:
        raise _Err("unorderable")


def _list(xs):
    if not isinstance(xs, list):
        raise _Err("not a list")
    return xs


def _nums(xs):
    if not all(_num(v) for v in _list(xs)):
        raise _Err("not numbers")
    return xs


def _need_grid(g):
    if not _grid(g):
        raise _Err("not a grid")
    return g


def _objects(g, conn, background, st):
    H, W = len(g), len(g[0])
    nb = [(0, 1), (1, 0), (0, -1), (-1, 0)] + ([(1, 1), (1, -1), (-1, 1), (-1, -1)] if conn == 8 else [])
    seen, objs = set(), []
    for i in range(H):
        for j in range(W):
            if (i, j) in seen or g[i][j] == background:
                continue
            c, comp, todo = g[i][j], [], [(i, j)]
            seen.add((i, j))
            while todo:
                a, b = todo.pop()
                st.add(1)
                comp.append([a, b])
                for da, db in nb:
                    x, y = a + da, b + db
                    if 0 <= x < H and 0 <= y < W and (x, y) not in seen and g[x][y] == c:
                        seen.add((x, y))
                        todo.append((x, y))
            objs.append({"color": c, "cells": sorted(comp)})
    objs.sort(key=lambda o: (o["cells"][0], o["color"]))
    return {"objects": objs}


def _need_objs(v):
    if not (isinstance(v, dict) and set(v) == {"objects"}):
        raise _Err("not an ObjectSet")
    return v["objects"]


def apply(spec, x, st):
    op = spec["op"]
    if op == "F":
        return [y for y in _list(x) if _pred(spec["pred"], y)]
    if op == "S":
        xs = _list(x)
        st.add(len(xs))
        return [xs[i] for i in _order(xs, spec["path"], spec["desc"])][: spec["k"]]
    if op == "Sort":
        xs = _list(x)
        st.add(len(xs))
        return [xs[i] for i in _order(xs, spec["path"], spec["desc"])]
    if op == "comp":
        xs = _list(x)
        n, out, seen = len(xs), [], set()
        st.add(n)
        for pos, i in enumerate(_order(xs, spec["path"], spec["desc"])):
            y, c = xs[i], spec["cond"]
            if c == "all":
                ok = True
            elif c == "head":
                ok = pos < spec["cparam"]
            elif c == "tail":
                ok = pos >= n - spec["cparam"]
            elif c == "first_occ":
                kk = key(_get(y, spec["cparam"]))
                ok = kk not in seen
                seen.add(kk)
            elif c == "pred":
                ok = _pred(spec["cparam"], y)
            else:
                raise _Err("cond")
            if ok:
                out.append(_get(y, spec["tparam"]) if spec["transform"] == "proj" else y)
        return out
    if op == "proj":
        return [_get(y, spec["path"]) for y in _list(x)]
    if op == "map_add":
        return [y + spec["c"] for y in _nums(x)]
    if op == "map_mul":
        return [y * spec["c"] for y in _nums(x)]
    if op == "map_mod":
        if spec["c"] == 0:
            raise _Err("mod 0")
        return [y % spec["c"] for y in _nums(x)]
    if op == "prefix_sum":
        out, acc = [], 0
        for y in _nums(x):
            acc += y
            out.append(acc)
        return out
    if op == "running_max":
        out = []
        for y in _nums(x):
            out.append(y if not out else max(out[-1], y))
        return out
    if op == "diff":
        xs = _nums(x)
        return [b - a for a, b in zip(xs, xs[1:])]
    if op == "rotate":
        xs = _list(x)
        if not xs:
            return []
        k = spec["k"] % len(xs)
        return xs[k:] + xs[:k]
    if op == "run_heads":
        out = []
        for y in _list(x):
            if not out or key(out[-1]) != key(y):
                out.append(y)
        return out
    if op == "group_count":
        order, cnt = [], {}
        for y in _list(x):
            kk = key(_get(y, spec["path"]))
            if kk not in cnt:
                order.append(kk)
                cnt[kk] = 0
            cnt[kk] += 1
        return [cnt[k] for k in order]
    if op == "repeat":
        for _ in range(spec["n"]):
            x = _list(apply(spec["body"], x, st))
        return x
    # ---- grids
    if op == "grid_coord":
        g = _need_grid(x)
        H, W = len(g), len(g[0])
        st.add(H * W)
        return [[g[(spec["a"] * i + spec["b"]) % H][(spec["c"] * j + spec["d"]) % W] for j in range(W)]
                for i in range(H)]
    if op == "grid_connect":
        g = _need_grid(x)
        H, W = len(g), len(g[0])
        out = [r[:] for r in g]
        todo = [(i, j) for i in range(H) for j in range(W) if g[i][j] == spec["seed"]]
        seen = set(todo)
        while todo:
            i, j = todo.pop()
            st.add(len(spec["moves"]))
            for dr, dc in spec["moves"]:
                a, b = i + dr, j + dc
                if 0 <= a < H and 0 <= b < W and (a, b) not in seen and g[a][b] == spec["passable"]:
                    seen.add((a, b))
                    todo.append((a, b))
                    out[a][b] = spec["fill"]
        return out
    if op == "grid_cellwise":
        g = _need_grid(x)
        H, W = len(g), len(g[0])
        t = {(a, b): c for a, b, c in spec["table"]}
        st.add(H * W)
        out = []
        for i in range(H):
            row = []
            for j in range(W):
                k = (g[i][j], g[(i + spec["dr"]) % H][(j + spec["dc"]) % W])
                if k not in t:
                    raise _Err("table miss")
                row.append(t[k])
            out.append(row)
        return out
    # ---- middle-IR adapters
    if op == "enc_objects":
        return _objects(_need_grid(x), spec["conn"], spec["background"], st)
    if op == "dec_objects":
        objs = _need_objs(x)
        cells = [c for o in objs for c in o["cells"]]
        if "shape" in spec:
            H, W = spec["shape"]
        else:
            if not cells:
                raise _Err("empty objects without shape")
            H, W = max(c[0] for c in cells) + 1, max(c[1] for c in cells) + 1
        if not (1 <= H <= 12 and 1 <= W <= 12):
            raise _Err("shape")
        g = [[spec["background"]] * W for _ in range(H)]
        for o in objs:
            for r, c in o["cells"]:
                st.add(1)
                if not (0 <= r < H and 0 <= c < W):
                    raise _Err("cell outside shape")
                g[r][c] = o["color"]
        return g
    if op == "ir_objects_filter_size":
        return {"objects": [o for o in _need_objs(x) if spec["min"] <= len(o["cells"]) <= spec["max"]]}
    if op == "ir_objects_recolor":
        return {"objects": [{"color": spec["color"], "cells": o["cells"]} for o in _need_objs(x)]}
    if op == "ir_objects_keep_color":
        return {"objects": [o for o in _need_objs(x) if o["color"] == spec["color"]]}
    if op == "enc_counter":
        cnt = {}
        for y in _list(x):
            st.add(1)
            v = _get(y, spec["path"])
            if not _scalar_ok(v):
                raise _Err("counter key")
            cnt[key(v)] = (v, cnt.get(key(v), (v, 0))[1] + 1)
        return {"counts": [[v, n] for _, (v, n) in sorted(cnt.items())]}
    if op == "dec_counter":
        if not (isinstance(x, dict) and set(x) == {"counts"}):
            raise _Err("not a Counter")
        return [list(p) for p in x["counts"]]
    if op == "ir_counter_top":
        if not (isinstance(x, dict) and set(x) == {"counts"}):
            raise _Err("not a Counter")
        top = sorted(x["counts"], key=lambda p: (-p[1], key(p[0])))[: spec["k"]]
        return {"counts": sorted(top, key=lambda p: key(p[0]))}
    if op == "enc_graph":
        g = _need_grid(x)
        H, W = len(g), len(g[0])
        nodes = [i * W + j for i in range(H) for j in range(W) if g[i][j] == spec["passable"]]
        ns = set(nodes)
        edges = []
        for n in nodes:
            i, j = divmod(n, W)
            for dr, dc in spec["moves"]:
                st.add(1)
                a, b = i + dr, j + dc
                if 0 <= a < H and 0 <= b < W and a * W + b in ns:
                    edges.append([n, a * W + b])
        return {"nodes": nodes, "edges": sorted(edges)}
    if op == "ir_graph_reach":
        if not (isinstance(x, dict) and set(x) == {"nodes", "edges"}):
            raise _Err("not a RelationGraph")
        adj = {}
        for a, b in x["edges"]:
            adj.setdefault(a, []).append(b)
        seen = [s for s in spec["seeds"] if s in set(x["nodes"])]
        todo, seen = list(seen), set(seen)
        while todo:
            n = todo.pop()
            for b in adj.get(n, []):
                st.add(1)
                if b not in seen:
                    seen.add(b)
                    todo.append(b)
        return sorted(seen)
    raise _Err("unknown op")


# --------------------------------------------------------------------------- spec validation
def _pspec(p):
    return isinstance(p, dict) and set(p) == {"path", "cmp", "val"} and p["cmp"] in ("ge", "le", "eq")


def _ints(spec, names, lo=-12, hi=12):
    return all(_isint(spec.get(n)) and lo <= spec[n] <= hi for n in names)


def _moves(m):
    return (isinstance(m, list) and 1 <= len(m) <= 16 and
            all(isinstance(d, list) and len(d) == 2 and all(_isint(v) and abs(v) <= 3 for v in d) for d in m))


def known(spec):
    if not isinstance(spec, dict) or "op" not in spec:
        return False
    op = spec["op"]
    try:
        if op == "F":
            return _pspec(spec["pred"])
        if op == "S":
            return _isint(spec["k"]) and 0 <= spec["k"] <= 64 and isinstance(spec["path"], str) and isinstance(spec["desc"], bool)
        if op == "Sort":
            return isinstance(spec["path"], str) and isinstance(spec["desc"], bool)
        if op == "comp":
            c = spec["cond"]
            ok = {"all": spec["cparam"] is None, "head": _isint(spec["cparam"]), "tail": _isint(spec["cparam"]),
                  "first_occ": isinstance(spec["cparam"], str), "pred": _pspec(spec["cparam"])}.get(c, False)
            return ok and spec["transform"] in ("id", "proj") and isinstance(spec["desc"], bool)
        if op in ("proj", "group_count"):
            return isinstance(spec["path"], str)
        if op in ("map_add", "map_mul", "map_mod"):
            return _isint(spec["c"]) and abs(spec["c"]) <= 100
        if op in ("prefix_sum", "running_max", "diff", "run_heads"):
            return set(spec) == {"op"}
        if op == "rotate":
            return _isint(spec["k"]) and 0 <= spec["k"] <= 64
        if op == "repeat":
            return _isint(spec["n"]) and 1 <= spec["n"] <= 4 and known(spec["body"]) and spec["body"]["op"] != "repeat"
        if op == "grid_coord":
            return _ints(spec, ("a", "b", "c", "d"))
        if op == "grid_connect":
            return _moves(spec["moves"]) and _ints(spec, ("passable", "seed", "fill"), 0, 9)
        if op == "grid_cellwise":
            t = spec["table"]
            keys = [(r[0], r[1]) for r in t]
            return (isinstance(t, list) and all(isinstance(r, list) and len(r) == 3 and all(_isint(v) and 0 <= v <= 9 for v in r) for r in t)
                    and len(set(keys)) == len(keys) and _ints(spec, ("dr", "dc"), -3, 3))
        if op == "enc_objects":
            return spec["conn"] in (4, 8) and _ints(spec, ("background",), 0, 9)
        if op == "dec_objects":
            return _ints(spec, ("background",), 0, 9) and ("shape" not in spec or (
                isinstance(spec["shape"], list) and len(spec["shape"]) == 2 and all(_isint(v) for v in spec["shape"])))
        if op == "ir_objects_filter_size":
            return _ints(spec, ("min", "max"), 0, 144)
        if op in ("ir_objects_recolor", "ir_objects_keep_color"):
            return _ints(spec, ("color",), 0, 9)
        if op == "enc_counter":
            return isinstance(spec["path"], str)
        if op == "dec_counter":
            return set(spec) == {"op"}
        if op == "ir_counter_top":
            return _ints(spec, ("k",), 1, 64)
        if op == "enc_graph":
            return _moves(spec["moves"]) and _ints(spec, ("passable",), 0, 9)
        if op == "ir_graph_reach":
            return isinstance(spec["seeds"], list) and all(_isint(s) and 0 <= s < 144 for s in spec["seeds"])
    except (KeyError, TypeError):
        return False
    return False


def run(chain, x):
    """Apply a chain; returns (value or ERROR, steps)."""
    st = _Steps()
    try:
        for spec in chain:
            x = apply(spec, x, st)
            check_value(x)
        return x, st.n
    except (_Err, KeyError, TypeError, ValueError, ZeroDivisionError, IndexError, RecursionError):
        return ERROR, st.n


# --------------------------------------------------------------------------- postconditions (list ops only)
LIST_OPS = {"F", "S", "Sort", "comp", "proj", "map_add", "map_mul", "map_mod", "prefix_sum", "running_max", "diff",
            "rotate", "run_heads", "group_count", "repeat"}


def posts(spec):
    op, out = spec["op"], []
    if op == "F":
        out.append(["all", spec["pred"]])
    if op == "S":
        out.append(["len_le", spec["k"]])
    if op == "comp" and spec["transform"] == "id":
        if spec["cond"] in ("head", "tail"):
            out.append(["len_le", spec["cparam"]])
        if spec["cond"] == "pred":
            out.append(["all", spec["cparam"]])
        if spec["cond"] == "first_occ":
            out.append(["distinct", spec["cparam"]])
    if op in ("S", "Sort") or (op == "comp" and spec["transform"] == "id"):
        if spec["path"] != "#":
            out.append(["sorted", spec["path"], spec["desc"]])
    return out


def _item_preserving(g):
    return g["op"] in ("F", "S", "Sort", "rotate", "run_heads") or (g["op"] == "comp" and g["transform"] == "id")


def _subsequence(g):
    if g["op"] in ("F", "run_heads"):
        return True
    if g["op"] in ("S", "comp"):
        return g["path"] == "#" and not g["desc"] and (g["op"] == "S" or g["transform"] == "id")
    return False


def preserves(g, post):
    if g["op"] not in LIST_OPS:
        return False
    if post[0] == "sorted":
        return _subsequence(g)
    if post[0] == "len_le":
        return _item_preserving(g) or g["op"] in ("proj", "map_add", "map_mul", "map_mod", "prefix_sum",
                                                  "running_max", "diff", "group_count")
    return _item_preserving(g)


def violates(post, y):
    if not isinstance(y, list):
        return False
    try:
        if post[0] == "len_le":
            return len(y) > post[1]
        if post[0] == "all":
            return not all(_pred(post[1], it) for it in y)
        if post[0] == "distinct":
            ks = [key(_get(it, post[1])) for it in y]
            return len(ks) != len(set(ks))
        if post[0] == "sorted":
            vals = [_get(it, post[1]) for it in y]
            if not all(_num(v) for v in vals):
                return False
            return any((a < b) if post[2] else (a > b) for a, b in zip(vals, vals[1:]))
    except (_Err, KeyError, TypeError):
        return False
    return False


# --------------------------------------------------------------------------- check
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
        tools, d, kind = list(scope["tools"]), int(scope["max_depth"]), scope["kind"]
        lemmas = list(evidence.get("lemmas", []))
    except Exception:
        return _abstain("malformed")
    if kind not in ("exhaustive", "proposal") or not 1 <= d <= MAX_DEPTH or not pub or not tools:
        return _abstain("malformed")
    if not all(known(s) for s in tools + cand):
        return _abstain("unsupported")
    try:
        for v in [x for x, _ in pub] + [y for _, y in pub] + [q]:
            check_value(v)
    except _Err:
        return _abstain("unsupported_value")
    tk = {key(s) for s in tools}
    if not 1 <= len(cand) <= d or not all(key(s) in tk for s in cand):
        return _abstain("candidate_outside_scope")
    for x, y in pub:
        o, _ = run(cand, x)
        if o == ERROR or key(o) != key(y):
            return _abstain("candidate_fails")
    co, _ = run(cand, q)
    if co == ERROR or key(co) != key(claimed):
        return _abstain("candidate_fails")
    viol = {}
    for lm in lemmas:
        try:
            i, post, j = int(lm["tool"]), lm["post"], int(lm["public_index"])
            if tools[i]["op"] not in LIST_OPS or key(post) not in {key(p) for p in posts(tools[i])} or \
                    not violates(post, pub[j][1]):
                return _abstain("bad_lemma")
        except Exception:
            return _abstain("bad_lemma")
        viol.setdefault(i, []).append(post)
    total = sum(len(tools) ** k for k in range(1, d + 1))
    if total > MAX_CHAINS:
        return _abstain("budget_exhausted", chains=total)
    targets = [key(y) for _, y in pub]
    answers, first, fitting, checked, steps = {}, {}, 0, 0, 0
    for k in range(1, d + 1):
        for chain in itertools.product(range(len(tools)), repeat=k):
            if chain[-1] in viol or any(i in viol and all(all(preserves(tools[g], p) for p in viol[i])
                                                          for g in chain[a + 1:]) for a, i in enumerate(chain)):
                continue
            checked += 1
            prog = [tools[i] for i in chain]
            ok = True
            for (x, _), t in zip(pub, targets):
                o, s = run(prog, x)
                steps += s
                if o == ERROR or key(o) != t:
                    ok = False
                    break
            if steps > MAX_STEPS_CHECK:
                return _abstain("budget_exhausted", steps=steps)
            if not ok:
                continue
            fitting += 1
            a, s = run(prog, q)
            steps += s
            ak = ERROR if a == ERROR else key(a)
            answers[ak] = answers.get(ak, 0) + 1
            first.setdefault(ak, list(chain))
    res = dict(fitting=fitting, answers=len(answers), chains_checked=checked, chains_total=total, steps=steps,
               checker_version=VERSION)
    if len(answers) > 1:
        wk = sorted(first)[:2]
        return dict(label="AMBIGUOUS", k=len(answers), k_exact=(kind == "exhaustive"),
                    witnesses=[dict(chain=first[w], answer=w) for w in wk], **res)
    if len(answers) == 1 and ERROR in answers:
        return dict(label="ABSTAIN", reason="query_error", **res)
    if len(answers) != 1 or key(claimed) not in answers:
        return dict(label="ABSTAIN", reason="claimed_not_unique", **res)
    return dict(label="exhaustive_UNIQUE" if kind == "exhaustive" else "proposal_relative_UNIQUE", **res)
