"""Phase 11 abstraction (NOT LOCKED): reusable executable functions derived from SOLVED, VERIFIED programs (typed AST anti-unification).

INPUT  the expanded ASTs of verified source solutions, each tagged with its source project id (distinct projects counted once).
CANDIDATES  every pair of subtrees (from two DIFFERENT projects) with the same head operator is anti-unified: the least general
            generalisation keeps every shared structure and replaces each differing position by a typed PARAMETER, with consistent
            binding (the same pair of differing subtrees always becomes the same parameter: alpha-consistent sharing). Parameter
            kinds: rel (a relational subtree), scalar (a scalar subtree), name (a column name inside a column reference or a key list),
            lit (a literal value of a const). Operator tags, aggregate names, join kinds, cast targets, rank k / direction never become
            parameters (no higher-order holes): a differing tag generalises the whole enclosing subtree. Top-level project_map nodes
            (task-specific output lists) are not candidates; their scalar expressions are.
SUPPORT     a candidate's support = the distinct source projects holding at least one subtree that MATCHES it (pattern matching with
            consistent binding): pairwise generalisations + matching keep role-consistent SUBGROUPS (the typed-AST analogue of
            Abs_subgroup) instead of intersecting a whole cluster. k_min = 3 distinct verified projects.
COMPRESSION delta = sum over matching instances of (size(instance) - (1 + sum of argument sizes)) - size(body) > 0 (declared MDL).
ADMISSION   (a) every support project's solution, rewritten to CALL the function, must reproduce that task's separate VALIDATION batch
            (never seen by search) and its visible batches; (b) the body must differ (alpha-canonically) from every admitted body;
            (c) at most PER_SLEEP admissions per sleep, best compression first.
CLASSES     wrapper: exactly one primitive operator node in the body (with fixed sub-arguments: e.g. rank_window with k = 1 - a direct
            primitive wrapper, NOT discovery of the mechanism); multi: >= 2 primitive operator nodes; composite: the body, rewritten with
            earlier admitted functions, calls one of them."""
from __future__ import annotations

import itertools
import json

from nexus.de_phase11 import core11 as C

K_MIN, PER_SLEEP, MIN_OPS, MAX_PAIRS = 3, 3, 2, 6000
REL_TAGS = {"rel", "map", "filter", "fold", "rank", "join", "union"}
SC_TAGS = {"const", "col", "isnull", "cmp", "and", "or", "not", "arith", "branch", "json", "cast"}


def is_rel(x):
    return isinstance(x, tuple) and x and x[0] in REL_TAGS


def is_sc(x):
    return isinstance(x, tuple) and x and x[0] in SC_TAGS


def subtrees(x, top=True):
    """Candidate subtrees (relational nodes except the top-level map; scalar nodes that are not bare leaves)."""
    out = []
    if not isinstance(x, tuple) or not x:
        return out
    if x[0] in REL_TAGS:
        if not (top and x[0] == "map") and x[0] != "rel":
            out.append(x)
        if x[0] == "map":
            out += subtrees(x[1], False)
            for _, e in x[2]:
                out += subtrees(e, False)
        elif x[0] == "filter":
            out += subtrees(x[1], False) + subtrees(x[2], False)
        elif x[0] == "fold":
            out += subtrees(x[1], False)
            for _, _, e in x[3]:
                if e is not None:
                    out += subtrees(e, False)
        elif x[0] == "rank":
            out += subtrees(x[1], False)
            for e, _ in x[3]:
                out += subtrees(e, False)
        elif x[0] == "join":
            out += subtrees(x[2], False) + subtrees(x[3], False)
        elif x[0] == "union":
            out += subtrees(x[1], False) + subtrees(x[2], False)
        return out
    if x[0] in ("const", "col"):
        return out
    out.append(x)
    for y in x[1:]:
        if is_sc(y):
            out += subtrees(y, False)
    return out


class LGG:
    def __init__(self):
        self.env, self.kinds = {}, []

    def param(self, a, b, kind, meta=None):
        k = (repr(a), repr(b), kind)
        if k not in self.env:
            self.env[k] = len(self.kinds)
            self.kinds.append((kind, meta))
        return ("param", self.env[k])

    def gen(self, a, b):
        if a == b:
            return a
        if is_rel(a) and is_rel(b):
            if a[0] != b[0] or a[0] == "rel":
                return self.param(a, b, "rel")
            op = a[0]
            if op == "filter":
                return ("filter", self.gen(a[1], b[1]), self.gen(a[2], b[2]))
            if op == "union":
                return ("union", self.gen(a[1], b[1]), self.gen(a[2], b[2]))
            if op == "fold":
                if len(a[2]) != len(b[2]) or len(a[3]) != len(b[3]) or any(ma[1] != mb[1] or ma[0] != mb[0] for ma, mb in zip(a[3], b[3])):
                    return self.param(a, b, "rel")
                return ("fold", self.gen(a[1], b[1]), tuple(self.name(x, y) for x, y in zip(a[2], b[2])),
                        tuple((ma[0], ma[1], self.gen(ma[2], mb[2]) if ma[2] is not None else None) for ma, mb in zip(a[3], b[3])))
            if op == "rank":
                if len(a[2]) != len(b[2]) or len(a[3]) != len(b[3]) or a[4] != b[4] or any(oa[1] != ob[1] for oa, ob in zip(a[3], b[3])):
                    return self.param(a, b, "rel")
                return ("rank", self.gen(a[1], b[1]), tuple(self.name(x, y) for x, y in zip(a[2], b[2])),
                        tuple((self.gen(oa[0], ob[0]), oa[1]) for oa, ob in zip(a[3], b[3])), a[4])
            if op == "join":
                if a[1] != b[1] or len(a[4]) != len(b[4]):
                    return self.param(a, b, "rel")
                return ("join", a[1], self.gen(a[2], b[2]), self.gen(a[3], b[3]), tuple(self.name(x, y) for x, y in zip(a[4], b[4])),
                        tuple(self.name(x, y) for x, y in zip(a[5], b[5])))
            return self.param(a, b, "rel")
        if is_sc(a) and is_sc(b):
            if a[0] != b[0]:
                return self.param(a, b, "scalar")
            op = a[0]
            if op == "col":
                return ("col", self.name(a[1], b[1]))
            if op == "const":
                if a[2] != b[2]:
                    return self.param(a, b, "scalar")
                return ("const", self.param(a[1], b[1], "lit", a[2]) if a[1] != b[1] else a[1], a[2])
            if op in ("cmp", "arith"):
                if a[1] != b[1]:
                    return self.param(a, b, "scalar")
                return (op, a[1], self.gen(a[2], b[2]), self.gen(a[3], b[3]))
            if op in ("isnull", "not"):
                return (op, self.gen(a[1], b[1]))
            if op in ("and", "or"):
                return (op, self.gen(a[1], b[1]), self.gen(a[2], b[2]))
            if op == "branch":
                return ("branch", self.gen(a[1], b[1]), self.gen(a[2], b[2]), self.gen(a[3], b[3]))
            if op == "json":
                return ("json", self.gen(a[1], b[1]), a[2] if a[2] == b[2] else self.param(a[2], b[2], "lit", "path"))
            if op == "cast":
                if a[2] != b[2]:
                    return self.param(a, b, "scalar")
                return ("cast", self.gen(a[1], b[1]), a[2])
        return self.param(a, b, "scalar" if is_sc(a) or is_sc(b) else "rel")

    def name(self, x, y):
        return x if x == y else self.param(x, y, "name")


def canonical(body, kinds):
    """Alpha-canonical form: parameters renumbered by first occurrence (and their kinds permuted accordingly)."""
    order = []

    def walk(x):
        if isinstance(x, tuple):
            if len(x) == 2 and x[0] == "param" and isinstance(x[1], int):
                if x[1] not in order:
                    order.append(x[1])
                return
            for y in x:
                walk(y)
    walk(body)
    ren = {old: new for new, old in enumerate(order)}

    def sub(x):
        if isinstance(x, tuple):
            if len(x) == 2 and x[0] == "param" and isinstance(x[1], int):
                return ("param", ren[x[1]])
            return tuple(sub(y) for y in x)
        return x
    return sub(body), [kinds[o] for o in order]


def op_count(x):
    """Primitive operator nodes (parameters, literals and column references excluded)."""
    if not isinstance(x, tuple) or not x:
        return 0
    if x[0] == "param" and len(x) == 2:
        return 0
    if x[0] in ("const", "col"):
        return 0
    n = 1 if x[0] in REL_TAGS | SC_TAGS and x[0] != "rel" else 0
    return n + sum(op_count(y) for y in x[1:] if isinstance(y, tuple))


def match(p, t, bind, kinds):
    """Does tree t instantiate pattern p? (consistent binding of parameters, kind-checked)."""
    if isinstance(p, tuple) and len(p) == 2 and p[0] == "param" and isinstance(p[1], int):
        kind = kinds[p[1]][0]
        ok = (kind == "rel" and is_rel(t)) or (kind == "scalar" and is_sc(t)) or (kind == "name" and isinstance(t, str)) or \
             (kind == "lit" and not isinstance(t, tuple)) or (kind == "lit" and kinds[p[1]][1] == "path" and isinstance(t, tuple))
        if not ok:
            return False
        if p[1] in bind:
            return bind[p[1]] == t
        bind[p[1]] = t
        return True
    if isinstance(p, tuple) and isinstance(t, tuple):
        return len(p) == len(t) and all(match(a, b, bind, kinds) for a, b in zip(p, t))
    return p == t


def instances(body, kinds, programs):
    """-> {project: [(subtree, binding)]} of matches."""
    out = {}
    for pid, prog in programs:
        for st in subtrees(prog):
            b = {}
            if match(body, st, b, kinds):
                out.setdefault(pid, []).append((st, b))
    return out


def arg_size(v):
    return C.size(v) if isinstance(v, tuple) and v and isinstance(v[0], str) and (v[0] in REL_TAGS | SC_TAGS) else 1


def candidates(programs, library):
    """programs: [(project_id, expanded AST)] verified solutions. -> scored candidate functions (not yet admitted)."""
    known = {json.dumps(f["canonical"]) for f in library.values()}
    subs = [(pid, st) for pid, prog in programs for st in subtrees(prog)]
    by_head = {}
    for pid, st in subs:
        by_head.setdefault(st[0], []).append((pid, st))
    seen, out, pairs = set(), [], 0
    for head, items in sorted(by_head.items()):
        for (pa, a), (pb, b) in itertools.combinations(items, 2):
            if pa.split("#")[0] == pb.split("#")[0] or a == b:
                continue
            pairs += 1
            if pairs > MAX_PAIRS:
                break
            g = LGG()
            body = g.gen(a, b)
            if body[0] == "param":
                continue
            body, kinds = canonical(body, g.kinds)
            key = json.dumps([body, kinds], default=str)
            if key in seen or json.dumps(body) in known:
                continue
            seen.add(key)
            if op_count(body) < 1:
                continue
            inst = instances(body, kinds, programs)
            support = sorted({p.split("#")[0] for p in inst})
            if len(support) < K_MIN:
                continue
            bsize = C.size(_ground(body, kinds))
            gain = sum(C.size(st) - (1 + sum(arg_size(v) for v in b.values())) for lst in inst.values() for st, b in lst) - bsize
            out.append(dict(body=body, kinds=kinds, support=support, instances=sum(len(v) for v in inst.values()), compression=gain,
                            ops=op_count(body), kind="rel" if is_rel(body) else "scalar", canonical=body))
    out.sort(key=lambda c: (-c["compression"], -len(c["support"]), json.dumps(c["body"])))
    return out, pairs


def _ground(body, kinds):
    """The body with each parameter replaced by a size-1 placeholder of its kind (for size accounting)."""
    def sub(x):
        if isinstance(x, tuple):
            if len(x) == 2 and x[0] == "param" and isinstance(x[1], int):
                k, meta = kinds[x[1]][0], kinds[x[1]][1]
                if k == "lit" and meta == "path":
                    return ("_p",)
                return ("rel", "_p") if k == "rel" else ("col", "_p") if k == "scalar" else "_p" if k == "name" else 0
            return tuple(sub(y) for y in x)
        return x
    return sub(body)


def to_function(cand):
    """Library entry: params = [(kind, meta)], body with ("param", i)."""
    return dict(kind=cand["kind"], params=[(k, m) for k, m in cand["kinds"]], body=cand["body"], canonical=cand["body"], ops=cand["ops"])


def rewrite(prog, library, order=None):
    """Greedy rewrite of an expanded AST with library functions (largest bodies first), recursively in the arguments."""
    order = order or sorted(library, key=lambda f: (-C.size(_ground(library[f]["body"], library[f]["params"])), f))

    def rw(x):
        if not isinstance(x, tuple) or not x or not isinstance(x[0], str):
            return x
        for fname in order:
            f = library[fname]
            b = {}
            if (is_rel(x) or is_sc(x)) and match(f["body"], x, b, f["params"]):
                args = tuple(rw(b[i]) if isinstance(b[i], tuple) and b[i] and isinstance(b[i][0], str) else b[i] for i in range(len(f["params"])))
                return ("call", fname, args)
        if x[0] == "map":
            return ("map", rw(x[1]), tuple((n, rw(e)) for n, e in x[2]))
        if x[0] == "fold":
            return ("fold", rw(x[1]), x[2], tuple((n, a, rw(e) if e is not None else None) for n, a, e in x[3]))
        if x[0] == "rank":
            return ("rank", rw(x[1]), x[2], tuple((rw(e), d) for e, d in x[3]), x[4])
        if x[0] == "join":
            return ("join", x[1], rw(x[2]), rw(x[3]), x[4], x[5])
        if x[0] in ("filter",):
            return ("filter", rw(x[1]), rw(x[2]))
        if x[0] == "union":
            return ("union", rw(x[1]), rw(x[2]))
        if x[0] in SC_TAGS and x[0] not in ("const", "col"):
            return tuple(rw(y) if isinstance(y, tuple) else y for y in x)
        return x
    return rw(prog)


def classify(fn, library):
    if fn["ops"] <= 1:
        return "wrapper"
    if library:
        rb = rewrite(fn["body"], library)
        if _has_call(rb):
            return "composite"
    return "multi"


def _has_call(x):
    if isinstance(x, tuple):
        if x and x[0] == "call" and len(x) == 3 and isinstance(x[1], str):
            return True
        return any(_has_call(y) for y in x)
    return False


def admit(cands, programs, tasks_admin, library, tasks_vis, log):
    """Admission (see the module docstring). programs: [(pid, expanded)], tasks_admin[pid] = (valid_env, valid_expected),
    tasks_vis[pid] = [(env, expected)] visible batches. -> list of admitted (name, function, record)."""
    admitted = []
    for cand in cands:
        if len(admitted) >= PER_SLEEP:
            break
        if cand["compression"] <= 0 or len(cand["support"]) < K_MIN:
            continue
        fn = to_function(cand)
        name = f"F{len(library) + len(admitted)}"
        trial = dict(library, **{name: fn})
        ok, checked = True, 0
        for pid, prog in programs:
            if pid.split("#")[0] not in cand["support"]:
                continue
            rw = rewrite(prog, {name: fn})
            if not _has_call(rw):
                continue
            checked += 1
            env, exp = tasks_admin[pid]
            try:
                got = C.evaluate(rw, env, trial)
                good = got is not C.ERR and set(got.cols) == set(exp.cols) and C.same_bag(C.project_like(got, list(exp.cols)), exp)
                for venv, vexp in tasks_vis.get(pid, []):
                    g2 = C.evaluate(rw, venv, trial)
                    good = good and g2 is not C.ERR and C.same_bag(C.project_like(g2, list(vexp.cols)), vexp)
            except (C.TypeErr, C.Unsupported, KeyError, IndexError, ValueError):
                good = False
            ok = ok and good
        rec = dict(name=name, canonical=cand["body"], params=fn["params"], support=cand["support"], instances=cand["instances"],
                   compression=cand["compression"], ops=cand["ops"], kind=cand["kind"], validated_projects=checked)
        if not ok or checked < K_MIN:
            log.append(dict(rec, admitted=False, why="validation" if not ok else "fewer than k_min rewritable support projects"))
            continue
        rec["class"] = classify(fn, dict(library, **{n: f for n, f, _ in admitted}))
        fn["class"] = rec["class"]
        admitted.append((name, fn, rec))
        log.append(dict(rec, admitted=True))
    return admitted


def tuplify(x):
    """JSON lists -> the tuple ASTs the core uses."""
    if isinstance(x, list):
        return tuple(tuplify(y) for y in x)
    return x


def load_library(d):
    return {name: dict(f, body=tuplify(f["body"]), canonical=tuplify(f["canonical"]), params=[tuple(p) if isinstance(p, list) else p for p in f["params"]])
            for name, f in (d or {}).items()}
