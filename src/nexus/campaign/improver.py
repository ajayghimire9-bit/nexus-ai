"""The bounded meta-improver M and the proposal machinery it parameterises (NOT LOCKED).

M is an inspectable program in a small meta-DSL: an ordered list of statements
  ["propose_L", {method: antiunify | subtree | random, min_uses, max_size, max_holes, top_k}]   (Delta L)
  ["propose_R", {method: closed | random, min_uses, max_size, top_k}]                         (Delta R)
  ["reweight",  {method: counts | random, lr, alpha, cmax}]                                   (Delta pi: grammar prior)
  ["tune",      {method: coord | random, params: [...]}]                                      (Delta pi: effort parameters)
  ["admit",     {n_tasks, neutral, speedup}]                                                  (admission rule)
  ["prune",     {max_L, max_R}]                                                               (bounded memory)
  ["curriculum",{rule: progress | frontier | round_robin, eps}]
  ["schedule",  {period, meta_period}]
Interpretation lives here (generate proposals, update pi, prune) and in agent_loop (admission, curriculum, meta edits).
M can only change these parameters / statements; the evaluator, verifiers, meter, splits and substrate are outside it.

Proposal methods
  antiunify: every subtree of a verified solution (size 3..max_size) is generalised by turning all task inputs, R
             leaves and free lambda arguments into positional holes (mandatory) and optionally constants into holes;
             a pattern's support = number of distinct solved tasks producing it; MDL score
             uses x (size - holes - 1) - size - (#constants kept). Patterns with support >= min_uses and score > 0.
  subtree:   the same without optional constant abstraction.
  closed:    R proposals = solution subtrees over exactly one input (no lambda arguments), as unary programs.
  random:    independent random well-typed programs of the same shape budget (no solution parent, no guidance)."""
from __future__ import annotations

import copy
import itertools
import math
import random

from nexus.campaign import substrate as S

M0 = [["propose_L", dict(method="antiunify", min_uses=2, max_size=8, max_holes=3, top_k=2)],
      ["propose_R", dict(method="closed", min_uses=2, max_size=5, top_k=2)],
      ["reweight", dict(method="counts", lr=1.0, alpha=1.0, cmax=4)],
      ["tune", dict(method="coord", params=["margin", "n_probes", "lam_max", "feat_k", "confirm_q", "qsel", "fit_alpha"])],
      ["admit", dict(n_tasks=4, neutral=True, speedup=0.2)],
      ["prune", dict(max_L=12, max_R=8)],
      ["curriculum", dict(rule="progress", eps=0.25)],
      ["schedule", dict(period=6, meta_period=2)]]

SPACE = {"propose_L": dict(method=["antiunify", "subtree"], min_uses=[2, 3], max_size=[4, 5, 6, 7, 8, 9, 10],
                           max_holes=[1, 2, 3], top_k=[1, 2, 3, 4]),
         "propose_R": dict(method=["closed"], min_uses=[2, 3], max_size=[2, 3, 4, 5, 6, 7], top_k=[0, 1, 2, 3]),
         "reweight": dict(method=["counts"], lr=[0.0, 0.5, 1.0, 1.5], alpha=[0.5, 1.0, 2.0, 4.0], cmax=[3, 4, 5]),
         "tune": dict(method=["coord"]),
         "admit": dict(n_tasks=[2, 3, 4, 5], neutral=[True, False], speedup=[0.1, 0.2, 0.3]),
         "prune": dict(max_L=[4, 6, 8, 10, 12, 14, 16], max_R=[2, 4, 6, 8, 10]),
         "curriculum": dict(rule=["progress", "frontier", "round_robin"], eps=[0.1, 0.25, 0.4]),
         "schedule": dict(period=[4, 5, 6, 8, 10], meta_period=[1, 2, 3])}
TUNE = dict(margin=[0, 1, 2], n_probes=[3, 4, 6, 8, 10], lam_max=[4, 5, 6, 7], feat_k=[2, 4, 8, 12], confirm_q=[0, 1, 2, 3, 4],
            qsel=["entropy", "first"], fit_alpha=[0.01, 0.1, 1.0, 10.0])


def stmt(M, name):
    return [s[1] for s in M if s[0] == name]


def first(M, name, default=None):
    v = stmt(M, name)
    return v[0] if v else default


def m_random(rng):
    """The matched random improver: M0's statement structure, random methods for every proposal statement and
    parameters drawn uniformly from the same bounded space."""
    M = []
    for name, p in M0:
        q = {k: rng.choice(SPACE[name][k]) if k in SPACE[name] and isinstance(SPACE[name][k], list) else v for k, v in p.items()}
        if name in ("propose_L", "propose_R", "reweight", "tune"):
            q["method"] = "random"
        M.append([name, q])
    return M


def m_mutate(M, rng):
    """One bounded structural edit of M: a parameter change, a method switch, or adding / removing a second
    propose_L / propose_R statement (at most 2 of each)."""
    M = copy.deepcopy(M)
    r = rng.random()
    if r < 0.15 and len(stmt(M, "propose_L")) < 2:
        p = copy.deepcopy(first(M, "propose_L"))
        k = rng.choice(["max_size", "max_holes", "min_uses", "method"])
        p[k] = rng.choice(SPACE["propose_L"][k])
        M.insert(1, ["propose_L", p])
        return M, f"add propose_L({k}={p[k]})"
    if r < 0.25 and len(stmt(M, "propose_L")) > 1:
        idx = [i for i, s in enumerate(M) if s[0] == "propose_L"][-1]
        del M[idx]
        return M, "remove extra propose_L"
    i = rng.randrange(len(M))
    name, p = M[i]
    keys = [k for k, v in SPACE[name].items() if isinstance(v, list) and len(v) > 1]
    if not keys:
        return m_mutate(M, rng)
    k = rng.choice(keys)
    opts = [v for v in SPACE[name][k] if v != p.get(k)]
    p[k] = rng.choice(opts)
    return M, f"{name}.{k}={p[k]}"


# ------------------------------------------------------------------ typed walking
def walk(n, sig, ctx, macros, feats):
    """Yield (node, type, ctx) for every node, bottom-up types; lambda bodies are walked in their own context."""
    out = []

    def rec(m, c):
        t = m[0]
        if t == "lam":
            ty = rec(m[2], m[1])
            return ("fn", m[1], ty)
        if t in ("x", "c", "a", "r", "h"):
            ty = S.type_of(m, sig, c, macros, feats)
        else:
            for a in m[2:]:
                rec(a, c)
            ty = macros[m[1]][2] if t == "m" else S.PRIMS[m[1]][1]
        out.append((m, ty, c))
        return ty
    rec(n, ctx)
    return out


def _free_inputs(n, inside=False):
    """Leaves to abstract in a candidate rooted at n: task inputs, R leaves, and lambda args bound outside n."""
    res = []

    def rec(m, depth):
        t = m[0]
        if t in ("x", "r"):
            res.append(m)
        elif t == "a" and depth == 0:
            res.append(m)
        elif t == "lam":
            rec(m[2], depth + 1)
        elif t in ("p", "m"):
            for a in m[2:]:
                rec(a, depth)
    rec(n, 0)
    return res


def _abstract(n, sig, ctx, feats, consts_to_hole, ztypes=()):
    """Replace mandatory leaves (task inputs, R leaves, lambda args bound outside n, 'z' anti-unification markers) and
    optionally every constant (also inside lambda bodies: a hole's value is computed in the calling context) by
    positional holes (numbered by first occurrence; equal leaves share a hole). Returns (body, hole types)."""
    holes, htypes = {}, []

    def ty(m):
        if m[0] == "x":
            return sig[m[1]]
        if m[0] == "r":
            return feats[m[1]][2]
        if m[0] == "a":
            return S.LAM_ARGS[ctx][m[1]]
        if m[0] == "z":
            return ztypes[m[1]]
        return "i"

    def rec(m, depth):
        t = m[0]
        if t in ("x", "r", "z") or (t == "a" and depth == 0) or (t == "c" and consts_to_hole):
            if m not in holes:
                holes[m] = len(htypes)
                htypes.append(ty(m))
            return ("h", holes[m])
        if t == "lam":
            return ("lam", m[1], rec(m[2], depth + 1))
        if t in ("p", "m"):
            return m[:2] + tuple(rec(a, depth) for a in m[2:])
        return m
    body = rec(n, 0)
    return body, tuple(htypes)


def _subtrees(n, ctx):
    """(subtree, ctx) for every application node (lambda bodies in their own ctx)."""
    res = []

    def rec(m, c):
        if m[0] == "lam":
            rec(m[2], m[1])
            return
        if m[0] in ("p", "m"):
            res.append((m, c))
            for a in m[2:]:
                rec(a, c)
    rec(n, ctx)
    return res


def _fo_paths(n):
    """Paths of proper application subtrees not inside a lambda body."""
    out = []

    def rec(m, path):
        for i, a in enumerate(m[2:]):
            if a[0] in ("p", "m"):
                out.append(path + (i + 2,))
                rec(a, path + (i + 2,))
    rec(n, ())
    return out


def _at(n, path):
    for i in path:
        n = n[i]
    return n


def _replace(n, repl, path=()):
    if path in repl:
        return repl[path]
    if n[0] in ("p", "m"):
        return n[:2] + tuple(_replace(a, repl, path + (i + 2,)) for i, a in enumerate(n[2:]))
    return n


def _n_consts(b):
    return sum(1 for m in S.nodes(b) if m[0] == "c")


def propose_L(archive, st, p, rng, existing):
    if p["method"] == "random":
        return random_macros(rng, p, existing, st)
    support, info = {}, {}
    macros = {lid: (m["body"], tuple(m["holes"]), m["out"]) for lid, m in st["L"].items()}
    feats = {rid: (r["body"], r["tin"], r["tout"]) for rid, r in st["R"].items()}
    for ent in archive:
        prog, sig = ent["prog"], tuple(ent["sig"])
        try:
            typed = {id(m): (t, c) for m, t, c in walk(prog, sig, "top", macros, feats)}
        except Exception:                                    # noqa: BLE001
            continue
        for sub, c in _subtrees(prog, "top"):
            sz = S.size(sub)
            if sz < 3 or sz > p["max_size"]:
                continue
            variants = [(sub, ())]
            if p["method"] == "antiunify":
                # anti-unification: up to two non-nested first-order proper subtrees (outside lambda bodies) may also
                # become typed holes
                paths = _fo_paths(sub)
                for k in (1, 2):
                    for combo in itertools.combinations(paths, k):
                        if any(a != b and a[:len(b)] == b for a in combo for b in combo):
                            continue
                        zt = [typed[id(_at(sub, q))][0] for q in combo]
                        variants.append((_replace(sub, {q: ("z", j) for j, q in enumerate(combo)}), tuple(zt)))
            for (vsub, zt), ch in itertools.product(variants, (False, True) if p["method"] == "antiunify" else (False,)):
                if S.size(vsub) < 3:
                    continue
                body, ht = _abstract(vsub, sig, c, feats, ch, zt)
                if len(ht) > p["max_holes"] or any(isinstance(h, tuple) for h in ht):
                    continue
                out_t = typed.get(id(sub), (None,))[0]
                if out_t is None or isinstance(out_t, tuple):
                    continue
                key = (S.to_src(body), ht, out_t)
                support.setdefault(key, set()).add(ent["tid"])
                info[key] = (body, ht, out_t, ent["tid"])
    cands = []
    for key, tids in support.items():
        body, ht, out_t, birth = info[key]
        sz = S.size(body)
        score = len(tids) * (sz - len(ht) - 1) - sz - _n_consts(body)
        if len(tids) >= p["min_uses"] and score > 0 and key[0] not in existing:
            cands.append((score, len(tids), key, body, ht, out_t, sorted(tids)))
    cands.sort(key=lambda z: (-z[0], -z[1], z[2][0]))
    return [dict(kind="L", body=body, holes=ht, out=out_t, mdl=score, support=tids, method=p["method"])
            for score, _, key, body, ht, out_t, tids in cands[:p["top_k"]]]


def propose_R(archive, st, p, rng, existing):
    if p["method"] == "random":
        return random_feats(rng, p, existing, st)
    support, info = {}, {}
    macros = {lid: (m["body"], tuple(m["holes"]), m["out"]) for lid, m in st["L"].items()}
    feats = {rid: (r["body"], r["tin"], r["tout"]) for rid, r in st["R"].items()}
    for ent in archive:
        prog, sig = ent["prog"], tuple(ent["sig"])
        try:
            typed = {id(m): (t, c) for m, t, c in walk(prog, sig, "top", macros, feats)}
        except Exception:                                    # noqa: BLE001
            continue
        for sub, c in _subtrees(prog, "top"):
            sz = S.size(sub)
            if sz < 2 or sz > p["max_size"] or c != "top":
                continue
            fr = _free_inputs(sub)
            if not fr or any(m[0] != "x" for m in fr) or len({m for m in fr}) != 1:
                continue
            k = fr[0][1]
            tin, tout = sig[k], typed[id(sub)][0]
            body = _abstract(sub, sig, c, feats, False)[0]
            key = (S.to_src(body), tin, tout)
            support.setdefault(key, set()).add(ent["tid"])
            info[key] = (body, tin, tout)
    cands = []
    for key, tids in support.items():
        body, tin, tout = info[key]
        sz = S.size(body)
        score = len(tids) * (sz - 1) - sz - _n_consts(body)
        if len(tids) >= p["min_uses"] and score > 0 and key[0] not in existing:
            cands.append((score, key, body, tin, tout, sorted(tids)))
    cands.sort(key=lambda z: (-z[0], z[1][0]))
    return [dict(kind="R", body=body, tin=tin, tout=tout, mdl=score, support=tids, method=p["method"])
            for score, key, body, tin, tout, tids in cands[:p["top_k"]]]


# ------------------------------------------------------------------ random typed programs
TYPES = ("i", "b", "l", "L")


def _probe_env(t):
    return {"i": [0, 1, 3, 7], "b": [True, False], "l": [(), (1, 2, 3), (4, 0, 2, 2)],
            "L": [(), ((1, 2), (3, 4)), ((0, 1, 2), (2, 2, 0), (5, 1, 1))]}[t]


def random_expr(rng, t, budget, holes, ctx="top", depth=0, st_macros=None):
    """A random well-typed expression of type t with at most `budget` nodes; holes = tuple of hole types."""
    leaves = [("h", k) for k, ht in enumerate(holes) if ht == t]
    if ctx != "top":
        leaves += [("a", k) for k, at in enumerate(S.LAM_ARGS[ctx]) if at == t]
    if t == "i":
        leaves += [("c", v) for v in S.BASE_CONSTS]
    if budget <= 1 or (leaves and rng.random() < 0.25):
        return rng.choice(leaves) if leaves else None
    prims = [p for p, (sl, o, _) in S.PRIMS.items() if o == t and len(sl) < budget]
    rng.shuffle(prims)
    for p in prims[:6]:
        sl = S.PRIMS[p][0]
        rem = budget - 1
        args = []
        for j, s in enumerate(sl):
            share = max(1, rem // (len(sl) - j)) if j < len(sl) - 1 else rem
            share = rng.randint(1, max(1, share))
            if S.is_fn(s):
                a = random_expr(rng, s[2], share, holes, s[1], depth + 1)
                a = None if a is None else ("lam", s[1], a)
            else:
                a = random_expr(rng, s, share, holes, ctx, depth + 1)
            if a is None:
                break
            args.append(a)
            rem -= S.size(a)
        else:
            if rem >= 0:
                return ("p", p) + tuple(args)
    return rng.choice(leaves) if leaves else None


def _executes(body, holes, out):
    """Valid on probe hole values and not constant across them."""
    g = S.compile_ast(body)
    vals = set()
    combos = list(itertools.product(*[_probe_env(h) for h in holes]))[:24] or [()]
    for hv in combos:
        try:
            v = g(None, (), hv)
        except Exception:                                    # noqa: BLE001
            return False
        if v is None:
            return False
        vals.add(repr(v))
    return len(vals) > 1


def random_macros(rng, p, existing, st, n=None):
    out = []
    for _ in range(200):
        if len(out) >= (n or p["top_k"]):
            break
        nh = rng.randint(1, max(1, p.get("max_holes", 2)))
        holes = tuple(rng.choice(TYPES) for _ in range(nh))
        t = rng.choice(TYPES)
        b = random_expr(rng, t, rng.randint(3, p.get("max_size", 8)), holes)
        if b is None or S.size(b) < 3 or S.to_src(b) in existing:
            continue
        used = sorted({m[1] for m in S.nodes(b) if m[0] == "h"})
        if used != list(range(nh)):
            continue
        try:
            if S.check_types(b, (), "top", holes=holes) != t or not _executes(b, holes, t):
                continue
        except (TypeError, KeyError, IndexError):
            continue
        out.append(dict(kind="L", body=b, holes=holes, out=t, mdl=None, support=[], method="random"))
    return out


def random_feats(rng, p, existing, st, n=None):
    out = []
    for _ in range(200):
        if len(out) >= (n or p["top_k"]):
            break
        tin, t = rng.choice(("l", "L", "i")), rng.choice(TYPES)
        b = random_expr(rng, t, rng.randint(2, p.get("max_size", 5)), (tin,))
        if b is None or S.size(b) < 2 or S.to_src(b) in existing or not any(m[0] == "h" for m in S.nodes(b)):
            continue
        try:
            if S.check_types(b, (), "top", holes=(tin,)) != t or not _executes(b, (tin,), t):
                continue
        except (TypeError, KeyError, IndexError):
            continue
        out.append(dict(kind="R", body=b, tin=tin, tout=t, mdl=None, support=[], method="random"))
    return out


def _fill_holes(b, holes, rng):
    """Put every unused hole into a random leaf of the same type outside lambda bodies (an int constant, or a duplicate
    occurrence of another hole of that type); None if impossible."""
    for k, ht in enumerate(holes):
        used = {m[1] for m in S.nodes(b) if m[0] == "h"}
        if k in used:
            continue
        counts = {}
        for m in S.nodes(b):
            if m[0] == "h":
                counts[m[1]] = counts.get(m[1], 0) + 1
        paths = []

        def rec(n, path):
            if n[0] == "c" and ht == "i" or (n[0] == "h" and holes[n[1]] == ht and counts[n[1]] > 1):
                paths.append(path)
            if n[0] in ("p", "m"):
                for i, a in enumerate(n[2:]):
                    rec(a, path + (i + 2,))
        rec(b, ())
        if not paths:
            return None
        b = _replace(b, {rng.choice(paths): ("h", k)})
    return b


def placebo_for(item, rng, existing):
    """An operationally matched irrelevant item: same kind, hole / input types, output type and description length,
    executable and non-constant on probes, but generated at random (no solution parent)."""
    for _ in range(4000):
        if item["kind"] == "L":
            holes, t, sz = tuple(item["holes"]), item["out"], S.size(item["body"])
        else:
            holes, t, sz = (item["tin"],), item["tout"], S.size(item["body"])
        b = random_expr(rng, t, sz, holes)
        if b is None or S.size(b) != sz or S.to_src(b) in existing:
            continue
        b = _fill_holes(b, holes, rng)          # size- and type-preserving: unused holes replace same-typed leaves
        if b is None or sorted({m[1] for m in S.nodes(b) if m[0] == "h"}) != list(range(len(holes))):
            continue
        try:
            if S.check_types(b, (), "top", holes=holes) != t or not _executes(b, holes, t):
                continue
        except (TypeError, KeyError, IndexError):
            continue
        return b
    return None


# ------------------------------------------------------------------ pi updates
def reweight(archive, st, p, rng):
    """Delta pi (grammar prior): production costs from usage in verified solutions (counts), or a random perturbation."""
    pi = copy.deepcopy(st["pi"])
    keys = [k for k in pi["costs"] if k not in ("x", "a")] + [f"L:{l}" for l in st["L"]] + [f"R:{r}" for r in st["R"]]
    if p["method"] == "random":
        for k in rng.sample(keys, min(len(keys), 8)):
            pi["costs"][k] = max(1, min(4, pi["costs"].get(k, 2) + rng.choice((-1, 1))))
        return pi, "random cost perturbation of 8 productions"
    counts = {}
    for ent in archive:
        for name in S.prod_names(ent["prog"]):
            counts[name] = counts.get(name, 0) + 1
    if not counts or p["lr"] == 0:
        return None, None
    mx = max(counts.values())
    for k in keys:
        f = counts.get(k, 0)
        c = 1 + round(p["lr"] * math.log2((mx + p["alpha"]) / (f + p["alpha"])))
        pi["costs"][k] = max(1, min(p["cmax"], c))
    return pi, f"counts-based costs over {len(archive)} solutions (lr {p['lr']}, alpha {p['alpha']})"


def tune(st, p, rng, k):
    """Delta pi (effort parameters): coordinate step on one parameter (k-th round), or a random setting."""
    pi = copy.deepcopy(st["pi"])
    if p["method"] == "random":
        name = rng.choice(list(TUNE))
        pi[name] = rng.choice(TUNE[name])
        return pi, f"random {name}={pi[name]}"
    params = p.get("params") or list(TUNE)
    name = params[k % len(params)]
    opts = TUNE[name]
    i = opts.index(pi[name]) if pi[name] in opts else 0
    j = max(0, min(len(opts) - 1, i + rng.choice((-1, 1))))
    if j == i:
        j = max(0, min(len(opts) - 1, i + (1 if i == 0 else -1)))
    pi[name] = opts[j]
    return pi, f"{name} {opts[i]}->{opts[j]}"
