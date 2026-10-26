"""Wave 31 increment 2 solver: SOLVER SIDE (development, NOT LOCKED). It runs inside a sandboxed child process
(wave31_evaluator). It sees only TaskViews (public pairs + query), and it reaches the checker and the oracle
only through the evaluator's channel (`chan.check(evidence)`, `chan.oracle(x)`), which meters both. It never
imports wave31_tasks, and it never writes files.

DISCLOSED: the prover executes candidates with checker v2's interpreter (V.run). Verdicts come only from the
evaluator-side checker call.

Proposal (how a candidate is found):
  * Fresh: first-fit layered search over G_P (depth <= 3), with observational dedup.
  * Useful / Placebo: first-fit search over G_P + library macros (depth <= 2), then over G_P if nothing fits.
Certification modes:
  * matched: the candidate is expanded to G_P ops (seq bodies inlined) and checked over the matched scope
    (G_P, depth 3). The same kernel-checkable pruning lemmas are supplied for every arm. If the macro candidate
    does not expand into the matched scope, the arm falls back to the G_P proposal (charged).
  * macro: checked over the arm's macro scope (G_P + macros, depth 2). The evaluator reports UNIQUE there as
    MACRO_SCOPE_UNIQUE.
Active probing (every arm, both modes, <= MAX_PROBES): on AMBIGUOUS, the solver mutates public inputs until the
kernel's two witness programs disagree, asks the oracle for that input, adds the pair, and re-proposes.

Library learning (source only, LODO): source tasks are solved as Fresh in matched mode (with probing) through the
same evaluator path, and only the candidates that the evaluator's checker labels exhaustive_UNIQUE come back. Leaf adapters
are stripped to cores. Pairwise op-level anti-unification (anti_unify_ops) gives typed skeletons; skeletons
with no concrete op are dropped. Op holes are instantiated with every non-adapter G_P op, and each instance is
a seq macro. Identical cores give exact macros.
Placebo: the same number of skeletons with the same hole positions, with concrete ops drawn at random from an
irrelevant pool, instantiated the same way (so the macro count and lengths are size-matched).
"""
from __future__ import annotations

import random

from nexus import checker_kernel_v2 as V
from nexus import wave31_grammar as G
from nexus.wave30_skeleton import Hole, anti_unify


# --------------------------------------------------------------------------- proposal
DEFAULT_POLICY = {"matched_depth": 3, "lemmas": "all", "order": "canonical", "macro_first": True, "macro_depth": 2,
                  "probe_mut": 2, "probe_tries": 300}


def _order(tools, policy):
    """Search ordering (editable in Wave 32). Returns a permutation of tool indices; scopes keep their tools."""
    idx = list(range(len(tools)))
    o = policy.get("order", "canonical")
    if o == "reverse":
        return idx[::-1]
    if o == "macros_last":
        return sorted(idx, key=lambda i: (tools[i].get("op") == "seq", i))
    if o == "short_first":
        return sorted(idx, key=lambda i: (len(tools[i].get("body", [0])), i))
    return idx


def first_fit(public, query, tools, depth, meter, order=None):
    xs = [x for x, _ in public] + [query]
    targets = [V.key(y) for _, y in public]
    n = len(public)
    frontier = [((), list(xs))]
    seen = {tuple(V.key(x) for x in xs)}
    for _d in range(depth):
        nxt = []
        for chain, vals in frontier:
            for ti in (order if order is not None else range(len(tools))):
                spec = tools[ti]
                outs = []
                for v in vals:
                    o, s = V.run([spec], v)
                    meter["prover"] = meter.get("prover", 0) + s + 1
                    if o == V.ERROR:
                        break
                    outs.append(o)
                if len(outs) < len(vals):
                    continue
                kk = tuple(V.key(o) for o in outs)
                if list(kk[:n]) == targets:
                    return list(chain + (ti,))
                if kk not in seen:
                    seen.add(kk)
                    nxt.append((chain + (ti,), outs))
        frontier = nxt
    return None


def expand(chain_specs):
    out = []
    for s in chain_specs:
        out += [dict(b) for b in s["body"]] if s.get("op") == "seq" else [dict(s)]
    return out


def lemmas_for(public, tools):
    """Kernel-checkable list-op lemmas (identical for every arm): tool i establishes `post`, public output j
    violates it."""
    out = []
    for i, t in enumerate(tools):
        if t.get("op") not in V.LIST_OPS:
            continue
        for post in V.posts(t):
            for j, (_x, y) in enumerate(public):
                if V.violates(post, y):
                    out.append({"tool": i, "post": post, "public_index": j})
                    break
    return out


# --------------------------------------------------------------------------- probing
def _mutate(x, rng, alphabet):
    if isinstance(x, str):
        i = rng.randrange(len(x)) if x else 0
        return x[:i] + rng.choice(alphabet["chars"] or ["a"]) + x[i + 1:]
    if isinstance(x, dict) and set(x) == {"nodes", "edges"}:
        e = [list(p) for p in x["edges"]]
        if e and rng.random() < 0.5:
            e.pop(rng.randrange(len(e)))
        else:
            a, b = rng.sample(x["nodes"], 2) if len(x["nodes"]) > 1 else (0, 0)
            if [a, b] not in e and a != b:
                e.append([a, b])
        return {"nodes": list(x["nodes"]), "edges": sorted(e)}
    if V._grid(x):
        g = [list(r) for r in x]
        i, j = rng.randrange(len(g)), rng.randrange(len(g[0]))
        g[i][j] = rng.choice(alphabet["colors"] or [0, 1])
        return g
    if isinstance(x, list) and x and all(isinstance(r, dict) for r in x):
        r = [dict(v) for v in x]
        i = rng.randrange(len(r))
        k = rng.choice(sorted(r[i]))
        r[i][k] = rng.choice(alphabet["ints"] or [0, 1])
        if rng.random() < 0.3:
            rng.shuffle(r)
        return r
    if isinstance(x, list) and x:
        r = list(x)
        r[rng.randrange(len(r))] = rng.choice(alphabet["ints"] or [0, 1])
        return r
    return x


def _alphabet(public, query):
    chars, colors, ints = set(), set(), set()
    for x in [p[0] for p in public] + [query]:
        if isinstance(x, str):
            chars |= set(x)
        elif V._grid(x):
            colors |= {c for r in x for c in r}
        elif isinstance(x, list):
            for v in x:
                if isinstance(v, dict):
                    ints |= {u for u in v.values() if V._isint(u)}
                elif V._isint(v):
                    ints.add(v)
    return {"chars": sorted(chars), "colors": sorted(colors), "ints": sorted(ints)}


def design_probe(public, query, tools, verdict, rng, meter, tries=300, n_mut=2):
    w = verdict.get("witnesses") or []
    if len(w) < 2:
        return None
    p1, p2 = [tools[i] for i in w[0]["chain"]], [tools[i] for i in w[1]["chain"]]
    alpha = _alphabet(public, query)
    pool = [p[0] for p in public] + [query]
    for _ in range(tries):
        x = rng.choice(pool)
        for _k in range(rng.randint(1, n_mut)):
            x = _mutate(x, rng, alpha)
        try:
            V.check_value(x)
        except Exception:
            continue
        a, s1 = V.run(p1, x)
        b, s2 = V.run(p2, x)
        meter["probe_design"] = meter.get("probe_design", 0) + s1 + s2 + 2
        # the query input is never probed (that would ask the oracle for the answer; fixed after the increment-2 audit)
        if V.key(a) != V.key(b) and V.key(x) != V.key(query) and all(V.key(x) != V.key(p[0]) for p in public):
            return x
    return None


# --------------------------------------------------------------------------- one task
def solve(chan, arm, mode, view, library, seed, policy=None):
    """Returns (final evidence or None, meter, info). `policy` (Wave 32 genome) defaults to DEFAULT_POLICY."""
    pol = dict(DEFAULT_POLICY, **(policy or {}))
    meter, info = {}, {"probes": 0, "fallback": False, "checks": 0}
    public = [list(p) for p in view["public"]]
    query = view["query"]
    rng = random.Random(f"w31b-probe:{seed}:{V.key(query)}")
    gp = [dict(t) for t in G.G_P]
    macro_tools = gp + list(library)
    while True:
        cand = None
        if arm != "Fresh" and library and pol["macro_first"]:
            c = first_fit(public, query, macro_tools, pol["macro_depth"], meter, _order(macro_tools, pol))
            if c is not None:
                cand = [macro_tools[i] for i in c]
        if mode == "matched":
            tools, depth = gp, pol["matched_depth"]
            if cand is not None:
                exp = expand(cand)
                keys = {V.key(t) for t in gp}
                if len(exp) > depth or any(V.key(t) not in keys for t in exp):
                    cand, info["fallback"] = None, True
                else:
                    cand = exp
            if cand is None:
                c = first_fit(public, query, gp, depth, meter, _order(gp, pol))
                cand = None if c is None else [gp[i] for i in c]
        else:
            tools, depth = macro_tools, G.MACRO_DEPTH
            if cand is None:
                c = first_fit(public, query, gp, G.MACRO_DEPTH, meter)
                cand = None if c is None else [gp[i] for i in c]
        if cand is None:
            return None, meter, dict(info, status="no_program_in_scope")
        ans, s = V.run(cand, query)
        meter["prover"] = meter.get("prover", 0) + s
        if pol.get("record_lemmas") and mode == "matched":
            record_lemmas(lemmas_for(public, tools), tools)
        lem = (lemmas_for(public, tools) if mode == "matched" and pol["lemmas"] == "all" else
               [m for m in lemmas_for(public, tools) if V.key([tools[m["tool"]]["op"], m["post"]]) in set(pol.get("lemma_kinds", []))]
               if mode == "matched" and pol["lemmas"] == "learned" else [])
        ev = {"checker_version": 2, "public": public, "query": query, "claimed_answer": ans, "candidate": cand,
              "scope": {"kind": "exhaustive", "tools": tools, "max_depth": depth}, "lemmas": lem,
              "trace": {"arm": arm, "mode": mode}}
        v = chan.check(ev)
        info["checks"] += 1
        if v["label"] != "AMBIGUOUS" or info["probes"] >= G.MAX_PROBES:
            return ev, meter, dict(info, status=v["label"])
        x = design_probe(public, query, tools, v, rng, meter, pol["probe_tries"], pol["probe_mut"])
        if x is None:
            return ev, meter, dict(info, status="AMBIGUOUS_no_probe_found")
        y = chan.oracle(x)
        info["probes"] += 1
        if y.get("error"):
            return ev, meter, dict(info, status="AMBIGUOUS_probe_error")
        public = public + [[x, y["output"]]]


# --------------------------------------------------------------------------- library learning
def core(prog):
    return [dict(s) for s in prog if s["op"] not in G.ADAPTER_OPS]


def hole_values():
    return [dict(t) for t in G.G_P if t["op"] not in G.ADAPTER_OPS]


def instantiate(sk):
    outs = [[]]
    for pos in sk:
        opts = hole_values() if isinstance(pos, Hole) else [pos]
        outs = [o + [dict(p)] for o in outs for p in opts]
    ms = {}
    for body in outs:
        m = {"op": "seq", "body": body}
        if V.known(m):
            ms[V.key(m)] = m
    return ms


def anti_unify_ops(p, q):
    """Op-level anti-unification (increment 2; wave30_skeleton.anti_unify generalises constants only): equal-length
    programs; equal specs are kept, a position whose op differs becomes a typed op hole, and a position with the
    same op but different constants uses wave30_skeleton.anti_unify's constant holes."""
    if len(p) != len(q):
        return None
    out = []
    for a, b in zip(p, q):
        if a.get("op") == b.get("op"):
            out.append(anti_unify([a], [b])[0])
        else:
            out.append(Hole("op"))
    return out


def skeletons_from(programs, max_holes=1):
    cores = [core(p) for p in programs if len(core(p)) >= 2]
    sks = {}
    for i in range(len(cores)):
        for j in range(i + 1, len(cores)):
            sk = anti_unify_ops(cores[i], cores[j])
            if sk is None or all(isinstance(p, Hole) for p in sk):
                continue
            if sum(isinstance(p, Hole) or any(isinstance(v, Hole) for v in p.values()) for p in sk) > max_holes:
                continue
            sk = [p if isinstance(p, Hole) or not any(isinstance(v, Hole) for v in p.values()) else Hole("op")
                  for p in sk]
            sks[repr(sk)] = sk
    return [sks[k] for k in sorted(sks)]


def library_from_skeletons(sks):
    ms = {}
    for sk in sks:
        ms.update(instantiate(sk))
    return [ms[k] for k in sorted(ms)]


PLACEBO_POOL = [{"op": "enc_counter", "path": "."}, {"op": "ir_counter_top", "k": 1}, {"op": "ir_counter_keys"},
                {"op": "ir_objects_sizes"}, {"op": "dec_counter"}, {"op": "ir_graph_degrees"},
                {"op": "map_add", "c": 1}, {"op": "map_mod", "c": 2}]


def placebo_skeletons(sks, rng):
    out = []
    for sk in sks:
        out.append([p if isinstance(p, Hole) else dict(rng.choice(PLACEBO_POOL)) for p in sk])
    return out


LEMMA_STATS = {"tasks": 0, "kinds": {}}


def record_lemmas(lem, tools):
    LEMMA_STATS["tasks"] += 1
    for k in {V.key([tools[m["tool"]]["op"], m["post"]]) for m in lem}:
        LEMMA_STATS["kinds"][k] = LEMMA_STATS["kinds"].get(k, 0) + 1


def learned_identities(views, min_obs=8):
    """Observational identities learned from SOURCE inputs: a bigram [a, b] of non-adapter G_P ops that equals a
    shorter chain ([] / [a] / [b]) on every leaf-transformed source input where both are defined (>= min_obs).
    These are NOT proofs. Checker v2 cannot verify them (it has no equivalence-proof form), so they are used only to
    PROJECT how much of the matched scope a future checker could skip."""
    seqs = []
    for v in views:
        for x in [p[0] for p in v["public"]] + [v["query"]]:
            for leaf in G.LEAF.values():
                y, _ = V.run(leaf, x)
                if y != V.ERROR:
                    seqs.append(y)
    ops = hole_values()
    out = []
    for a in ops:
        for b in ops:
            for short in ([], [a], [b]):
                n, ok = 0, True
                for x in seqs:
                    y1, _ = V.run([a, b], x)
                    y2 = x if not short else V.run(short, x)[0]
                    if y1 == V.ERROR or y2 == V.ERROR:
                        continue
                    n += 1
                    if V.key(y1) != V.key(y2):
                        ok = False
                        break
                if ok and n >= min_obs:
                    out.append([a, b, short])
                    break
    return out


def projected_skip(identities, tools, depth):
    """Fraction of all chains (length <= depth) over `tools` that contain an adjacent bigram covered by an identity
    (so they are observationally redundant under that identity)."""
    red = {(V.key(a), V.key(b)) for a, b, _ in identities}
    keys = [V.key(t) for t in tools]
    n = len(tools)
    total = sum(n ** k for k in range(1, depth + 1))
    clean = [1] * n                                  # chains of length 1 ending at tool j with no redundant bigram
    clean_total = n
    for _k in range(2, depth + 1):
        clean = [sum(clean[i] for i in range(n) if (keys[i], keys[j]) not in red) for j in range(n)]
        clean_total += sum(clean)
    return 1 - clean_total / total


def build(programs, seed, views=(), max_holes=1, depth=3):
    """Library learning from the source programs the evaluator's checker certified (source-only feedback)."""
    sks = skeletons_from(programs, max_holes)
    psks = placebo_skeletons(sks, random.Random(f"w31b-placebo:{seed}"))
    ids = learned_identities(views) if views else []
    nst = max(1, LEMMA_STATS["tasks"])
    return dict(useful=library_from_skeletons(sks), placebo=library_from_skeletons(psks),
                skeletons=[repr(s) for s in sks], placebo_skeletons=[repr(s) for s in psks],
                lemma_kinds=sorted(k for k, c in LEMMA_STATS["kinds"].items() if c / nst >= 0.5),
                identities=ids, projected_skip=projected_skip(ids, G.G_P, depth) if ids else 0.0)
