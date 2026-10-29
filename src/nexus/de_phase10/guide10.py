"""Phase 10 search guides (NOT LOCKED).

G_fixed    the fixed archive order with EMPTY evidence weights (operator interleaving in fixed order)
G_count    the count-based prior: evidence weights w (feature -> operator counts from verified repairs / regressions), the
           existing mechanism (op order + interleaving weights)
G_learned  a small contextual RANKER: pairwise logistic model over sparse tokens of (operator, evidence feature of the
           node, schema role of each parameter slot, stage); children are emitted 70 % from the ranker's order and 30 %
           from the UNPRUNED fallback order (G_fixed), interleaved 7:3, so ranker errors never exclude a reachable repair
           (progressive widening keeps every child reachable; the ratio is an M field)
Training data: wake replays (each step of a VERIFIED repair path vs up to 8 sibling candidates at the same node) and
contract-guarded dreams (each step of a witness path on a Repos_Train task whose truth passes the v7 invariants). Sibling
candidates are UNVISITED / censored, not refuted: the pairwise objective only says the verified step should rank above a
random sibling (a selection-biased signal, disclosed). Registered at import as the children generator of search7 (the
hook falls back to search7's original generator unless mem['guide'] selects the learned ranker)."""
from __future__ import annotations

import math
import random

from nexus.de_phase6 import engines6 as E, pipeline6 as P6, skills6 as SK
from nexus.de_phase7 import search7 as S7

_ORIG_CHILDREN = getattr(S7._children, "_phase7_original", S7._children)
_ORIG_ROLES = getattr(SK.roles, "_phase6_original", SK.roles)


def _roles(dom, col, fine=True):
    """skills6.roles memoised on the (immutable) value-domain object: the guide scores every candidate of every
    expanded node, and roles() scans the column each call. Output-identical."""
    memo = dom.__dict__.setdefault("_roles_memo", {})
    key = (col, fine)
    if key not in memo:
        memo[key] = _ORIG_ROLES(dom, col, fine)
    return memo[key]


_roles._phase6_original = _ORIG_ROLES
SK.roles = _roles


def tokens(op, k, prm, feats, dom):
    t = [f"op:{op}", f"op:{op}|stage:{k}"]
    t += [f"op:{op}|ev:{f}" for f in sorted(feats)[:24]]
    try:
        ab = SK.abstract_edit(op, prm, dom, True)
        for x in ab[1:]:
            if isinstance(x[1], (tuple, list)):
                t += [f"op:{op}|{x[0]}:{r}" for r in x[1]]
            else:
                t.append(f"op:{op}|{x[0]}=lit")
    except Exception:                                          # noqa: BLE001
        pass
    return t


def score(w, toks):
    return sum(w.get(x, 0.0) for x in toks)


def children(inv, mem, node, mode, order):
    g = mem.get("guide") or {}
    if g.get("kind") != "learned" or not g.get("w"):
        yield from _ORIG_CHILDREN(inv, {**mem, "de": dict(mem.get("de", {}), w={})} if g.get("kind") == "fixed" else mem, node, mode, order)
        return
    stages = list(range(len(inv.stages)))
    if mode == "decompose":
        failing = [k for k, fs in enumerate(node["ev"]["stage_fail"]) if fs]
        stages = [failing[0]] if failing else [len(inv.stages) - 1]
    feats = node["ev"]["features"]
    cands = []
    for op in E.OPS:
        for k in stages:
            dom = inv.dom(k, node["specs"])
            for s2, prm in E.candidates(op, node["specs"][k], dom):
                cands.append((score(g["w"], tokens(op, k, prm, feats, dom)), k, op, s2, prm))
    guided = iter(sorted(cands, key=lambda c: -c[0]))
    fallback = _ORIG_CHILDREN(inv, {**mem, "de": dict(mem.get("de", {}), w={})}, node, mode, order)
    ratio = g.get("ratio", 0.7)
    seen, n = set(), 0
    alive = [True, True]
    while any(alive):
        use_guided = alive[0] and (not alive[1] or (n % 10) < round(10 * ratio))
        n += 1
        src = guided if use_guided else fallback
        try:
            item = next(src)
        except StopIteration:
            alive[0 if use_guided else 1] = False
            continue
        k, op, s2, prm = item[1:] if use_guided else item
        key = (k, op, prm)
        if key in seen:
            continue
        seen.add(key)
        yield k, op, s2, prm


children._phase7_original = _ORIG_CHILDREN
S7._children = children


def path_pairs(inv, path, rng, n_neg=8):
    """Pairwise training examples along a verified (or witness) path: (positive tokens, negative tokens) per sibling."""
    pairs = []
    specs = list(inv.legacy)
    for k, op, prm in path:
        ev = inv.run(specs, True)
        feats = ev["features"]
        sib = []
        pos = None
        for o in E.OPS:
            for kk in range(len(specs)):
                dom = inv.dom(kk, specs)
                for s2, p2 in E.candidates(o, specs[kk], dom):
                    if (kk, o, p2) == (k, op, prm):
                        pos = tokens(o, kk, p2, feats, dom)
                    else:
                        sib.append((o, kk, p2, dom))
        if pos is None:
            break
        for o, kk, p2, dom in rng.sample(sib, min(n_neg, len(sib))):
            pairs.append((pos, tokens(o, kk, p2, feats, dom)))
        specs = P6.replay(inv, [(k, op, prm)], specs)
    return pairs


def train(pairs, epochs=4, lr=0.2, l2=1e-3, seed=0):
    w = {}
    rng = random.Random(seed)
    data = list(pairs)
    for _ in range(epochs):
        rng.shuffle(data)
        for pos, neg in data:
            m = score(w, pos) - score(w, neg)
            g = 1.0 / (1.0 + math.exp(min(30.0, m)))
            for x in pos:
                w[x] = w.get(x, 0.0) * (1 - l2) + lr * g
            for x in neg:
                w[x] = w.get(x, 0.0) * (1 - l2) - lr * g
    return {k: round(v, 4) for k, v in w.items() if abs(v) > 1e-4}


def pair_accuracy(w, pairs):
    return round(sum(score(w, p) > score(w, n) for p, n in pairs) / max(1, len(pairs)), 3)
