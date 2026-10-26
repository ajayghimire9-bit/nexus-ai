"""Wave 31 (development, NOT LOCKED): shared middle IR across 4 surface domains, thin adapters, typed skeleton
macros, transfer controls. Every certificate is issued by Checker v2 (`checker_kernel_v2`, pinned).

Middle IR types (checker v2 §1): Sequence, Counter, ObjectSet, RelationGraph.
Surface adapters phi_d (checker v2 ops; every arm has identical access):
  strings: enc_chars / dec_chars   grids: enc_cells, enc_objects / dec_objects   graphs: ir_graph_degrees (a
  RelationGraph surface is already IR)   lists / records: identity (lists are Sequences).
Adapter audit: adapter ops are charged on the meter separately ("adapter"). enc_objects runs connected-component
analysis, which is substantive computation, and the audit reports its share.

Prover: exhaustive layered enumeration of the declared grammar with observational deduplication (classes of
equal outputs on public inputs + query), over ALL sizes <= depth (the checker's semantics). DISCLOSED: the prover
executes candidates with checker v2's interpreter. Correctness is still decided by the checker alone: it
re-enumerates and re-executes everything itself, and the prover never vouches for semantics.

Arms (identical adapters and primitives):
  * Fresh: primitive grammar G_P, depth <= 4.
  * Useful: G_P primitives + library macros (seq ops) learned from SOURCE domains (lists, strings), depth <= 2;
    if nothing fits, escalate to G_P depth <= 4 (charged).
  * Placebo: the same, but with size-matched macros built from irrelevant random IR op sequences of the same
    lengths.
Library learning (source only): Fresh-certify the source tasks; strip the surface adapters; anti-unify the
cores (wave30_skeleton.anti_unify) into typed skeletons. Skeletons and their contiguous sub-skeletons of length
>= 2 become macros, with holes instantiated from small typed candidate sets.
Certificates are exhaustive relative to each arm's DECLARED grammar. A macro grammar is a different grammar,
not a subset or superset of G_P at depth 4, so a scope-relative UNIQUE can be wrong when the teacher lies outside
it. That is reported as wrong_outside_scope.
Evaluator-only labels: domain, mechanism, familiar (mechanism core seen in source) vs held_out.
"""
from __future__ import annotations

import random
from collections import Counter

from nexus import checker_kernel_v2 as V
from nexus.wave30_skeleton import Hole, anti_unify

ADAPTER_OPS = {"enc_chars", "dec_chars", "enc_cells", "enc_objects", "dec_objects"}
SOURCE_DOMAINS = ("lists", "strings")
TARGET_DOMAINS = ("grids", "graphs")
FAMILIAR = {"topk", "sortdedupe", "rotate"}
HELD_OUT = {"objfilter", "reach"}


# --------------------------------------------------------------------------- surface samplers
def sample(domain, rng):
    if domain == "lists":
        return [rng.randrange(6) for _ in range(rng.randint(5, 7))]
    if domain == "strings":
        return "".join(rng.choice("abcd") for _ in range(rng.randint(5, 8)))
    if domain == "grids":
        n = rng.choice((4, 5))
        return [[rng.choice((0, 0, 1, 1, 2, 3)) for _ in range(n)] for _ in range(n)]
    nodes = list(range(6))
    edges = sorted({(rng.randrange(6), rng.randrange(6)) for _ in range(8)} - {(i, i) for i in range(6)})
    return {"nodes": nodes, "edges": [list(e) for e in edges]}


def top(k):
    return {"op": "ir_counter_top", "k": k}


ENC_CNT = {"op": "enc_counter", "path": "."}
KEYS = {"op": "ir_counter_keys"}
SORT = {"op": "Sort", "path": ".", "desc": False}
RUNH = {"op": "run_heads"}


def teacher(domain, mech, k, color, x):
    """The hidden program (evaluator side)."""
    pre = {"lists": [], "strings": [{"op": "enc_chars"}], "grids": [{"op": "enc_cells"}], "graphs": []}[domain]
    post = [{"op": "dec_chars"}] if domain == "strings" and mech in ("sortdedupe", "rotate") else []
    if mech == "topk":
        if domain == "graphs":
            return [{"op": "ir_graph_degrees"}, top(k), KEYS]
        return pre + [ENC_CNT, top(k), KEYS]
    if mech == "sortdedupe":
        return pre + [SORT, RUNH] + post
    if mech == "rotate":
        return pre + [{"op": "rotate", "k": 1}] + post
    if mech == "objfilter":
        return [{"op": "enc_objects", "conn": 4, "background": 0}, {"op": "ir_objects_filter_size", "min": 2, "max": 144},
                {"op": "ir_objects_recolor", "color": color},
                {"op": "dec_objects", "background": 0, "shape": [len(x), len(x[0])]}]
    if mech == "reach":
        return [{"op": "ir_graph_reach", "seeds": [0]}]
    raise ValueError(mech)


MECHS = {"lists": ("topk", "sortdedupe", "rotate"), "strings": ("topk", "sortdedupe", "rotate"),
         "grids": ("topk", "sortdedupe", "objfilter"), "graphs": ("topk", "reach")}


def make_task(domain, mech, rng, n_public=4):
    for _ in range(100):
        k, color = rng.choice((1, 2)), rng.choice((3, 4, 5))
        xs = [sample(domain, rng) for _ in range(n_public + 1)]
        prog = teacher(domain, mech, k, color, xs[0])
        if mech == "objfilter":
            n = len(xs[0])
            xs = [[r[:n] + [0] * (n - len(r)) for r in x[:n]] + [[0] * n] * (n - len(x)) for x in xs]
        ys = [V.run(prog, x)[0] for x in xs]
        if any(y == V.ERROR for y in ys) or len({V.key(y) for y in ys[:n_public]}) < 2:
            continue
        return dict(domain=domain, mechanism=mech, public=[[x, y] for x, y in zip(xs[:n_public], ys[:n_public])],
                    query=xs[-1], answer=ys[-1], teacher=prog,
                    transfer=("source" if domain in SOURCE_DOMAINS else
                              "familiar_mechanism_new_surface" if mech in FAMILIAR else "held_out_mechanism"))
    return None


def stream(split_seed, domains, n_per=2):
    rng = random.Random(f"w31:{split_seed}:{','.join(domains)}")
    out = []
    for d in domains:
        for mech in MECHS[d]:
            for _ in range(n_per):
                t = make_task(d, mech, rng)
                if t is not None:
                    out.append(t)
    return out


# --------------------------------------------------------------------------- grammar
def primitives(public, query):
    """Data-instantiated primitive tools (identical for every arm)."""
    outs = [y for _, y in public]
    colors = sorted({c for y in outs if V._grid(y) for r in y for c in r} - {0})[:3]
    shapes = sorted({(len(x), len(x[0])) for x, _ in public if V._grid(x)})
    t = [{"op": "enc_chars"}, {"op": "dec_chars"}, {"op": "enc_cells"}, {"op": "enc_objects", "conn": 4, "background": 0},
         {"op": "ir_objects_sizes"}, {"op": "ir_objects_filter_size", "min": 2, "max": 144}, ENC_CNT,
         {"op": "dec_counter"}, top(1), top(2), KEYS, {"op": "ir_graph_degrees"}, {"op": "ir_graph_reach", "seeds": [0]},
         SORT, RUNH, {"op": "prefix_sum"}, {"op": "rotate", "k": 1}, {"op": "diff"}]
    t += [{"op": "ir_objects_recolor", "color": c} for c in colors]
    t += [{"op": "dec_objects", "background": 0, "shape": [h, w]} for h, w in shapes]
    return t


def is_adapter(spec):
    return spec["op"] in ADAPTER_OPS


# --------------------------------------------------------------------------- prover
def prove(public, query, tools, depth, meter):
    """All-sizes exhaustive enumeration with observational dedup. Returns (status, hyps[(chain, answer)])."""
    xs = [x for x, _ in public] + [query]
    targets = [V.key(y) for _, y in public]
    n = len(public)
    frontier = {tuple(V.key(x) for x in xs): ((), list(xs))}
    seen = set(frontier)
    fits = {}
    for d in range(1, depth + 1):
        nxt = {}
        for chain, vals in frontier.values():
            for ti, spec in enumerate(tools):
                outs, err = [], False
                for v in vals:
                    st = V._Steps()
                    try:
                        o = V.apply(spec, v, st)
                        V.check_value(o)
                    except Exception:
                        err = True
                    meter["adapter" if is_adapter(spec) else "prover"] = \
                        meter.get("adapter" if is_adapter(spec) else "prover", 0) + st.n + 1
                    if err:
                        break
                    outs.append(o)
                if err:
                    continue
                kk = tuple(V.key(o) for o in outs)
                if list(kk[:n]) == targets:
                    fits.setdefault(kk[n], chain + (ti,))
                if kk in seen:
                    continue
                seen.add(kk)
                nxt[kk] = (chain + (ti,), outs)
        frontier = nxt
    if not fits:
        return "NONE", []
    hyps = [(list(c), a) for a, c in sorted(fits.items())]
    return ("UNIQUE" if len(hyps) == 1 else "AMBIGUOUS"), hyps


def certify(public, query, tools, depth, kind, meter):
    st, hyps = prove(public, query, tools, depth, meter)
    if st == "NONE":
        return dict(label="ABSTAIN", reason="no_program_in_declared_grammar", prover=st), None
    chain, ans = hyps[0]
    ev = {"checker_version": 2, "public": public, "query": query, "claimed_answer": __import__("json").loads(ans),
          "candidate": [tools[i] for i in chain], "scope": {"kind": kind, "tools": tools, "max_depth": depth},
          "lemmas": [], "trace": {"prover": st}}
    v = V.check(ev)
    meter["checker"] = meter.get("checker", 0) + v.get("steps", 0) + v.get("chains_checked", 0)
    v["prover"] = st
    return v, ev


# --------------------------------------------------------------------------- library (source learning)
def core(prog):
    return [s for s in prog if not is_adapter(s)]


HOLE_VALUES = {"int": (1, 2, 3)}


def _fill(sk):
    """All instantiations of a skeleton's int holes from small typed candidate sets."""
    if isinstance(sk, Hole):
        return [v for v in HOLE_VALUES.get(sk.type, ())]
    if isinstance(sk, dict):
        keys = sorted(sk)
        opts = [_fill(sk[k]) for k in keys]
        return [dict(zip(keys, combo)) for combo in __import__("itertools").product(*opts)]
    if isinstance(sk, list):
        opts = [_fill(v) for v in sk]
        return [list(c) for c in __import__("itertools").product(*opts)]
    return [sk]


def library_from(programs):
    """Typed skeletons from pairwise anti-unification of certified cores (+ identical cores kept as-is), then
    macros = instantiated skeletons and their contiguous sub-skeletons of length >= 2."""
    cores = [core(p) for p in programs if len(core(p)) >= 2]
    sks = {}
    for i in range(len(cores)):
        for j in range(i + 1, len(cores)):
            sk = anti_unify(cores[i], cores[j])
            if sk is not None:
                sks[repr(sk)] = sk
    macros = {}
    for sk in sks.values():
        for a in range(len(sk)):
            for b in range(a + 2, len(sk) + 1):
                for inst in _fill(sk[a:b]):
                    m = {"op": "seq", "body": inst}
                    if V.known(m):
                        macros[V.key(m)] = m
    return [macros[k] for k in sorted(macros)], [repr(s) for s in sks.values()]


def placebo_library(n_macros, lengths, rng):
    pool = [ENC_CNT, top(1), top(2), KEYS, SORT, RUNH, {"op": "prefix_sum"}, {"op": "rotate", "k": 1},
            {"op": "diff"}, {"op": "ir_objects_sizes"}, {"op": "dec_counter"}]
    out = {}
    tries = 0
    while len(out) < n_macros and tries < 1000:
        tries += 1
        L = lengths[len(out) % len(lengths)] if lengths else 2
        m = {"op": "seq", "body": [rng.choice(pool) for _ in range(L)]}
        out[V.key(m)] = m
    return [out[k] for k in sorted(out)]


# --------------------------------------------------------------------------- arms
def solve(arm, public, query, library):
    meter = {}
    prims = primitives(public, query)
    meter["scope_construction"] = len(prims) + len(library)
    if arm == "Fresh":
        v, ev = certify(public, query, prims, 4, "exhaustive", meter)
        grammar = "G_P(depth<=4)"
    else:
        tools = prims + library
        v, ev = certify(public, query, tools, 2, "exhaustive", meter)
        grammar = f"G_P+{len(library)}macros(depth<=2)"
        if v["label"] == "ABSTAIN" and v.get("reason") == "no_program_in_declared_grammar":
            failed = dict(meter)
            meter = {"failed_proposal": sum(failed.values())}
            v, ev = certify(public, query, prims, 4, "exhaustive", meter)
            grammar = "escalated:G_P(depth<=4)"
    return v, ev, meter, grammar


def evaluate(task, v, ev, meter, grammar):
    uniq = v["label"] in ("exhaustive_UNIQUE", "proposal_relative_UNIQUE")
    correct = uniq and V.key(ev["claimed_answer"]) == V.key(task["answer"])
    tk = [V.key(s) for s in task["teacher"]]
    scope = [V.key(s) for s in ev["scope"]["tools"]] if ev else []
    teacher_in = ev is not None and len(tk) <= ev["scope"]["max_depth"] and set(tk) <= set(scope)
    return dict(domain=task["domain"], mechanism=task["mechanism"], transfer=task["transfer"], label=v["label"],
                reason=v.get("reason"), k=v.get("k"), correct=correct, grammar=grammar,
                wrong=(None if not uniq or correct else
                       "wrong_teacher_inside_scope" if teacher_in else "wrong_teacher_outside_scope"),
                work=sum(meter.values()), work_by=meter)


def summarise(rows):
    out = {}
    for cat in sorted({r["transfer"] for r in rows}):
        rs = [r for r in rows if r["transfer"] == cat]
        wb = Counter()
        for r in rs:
            wb.update(r["work_by"])
        out[cat] = dict(n=len(rs), correct=sum(r["correct"] for r in rs),
                        exhaustive=sum(r["label"] == "exhaustive_UNIQUE" for r in rs),
                        ambiguous=sum(r["label"] == "AMBIGUOUS" for r in rs),
                        abstain=sum(r["label"] == "ABSTAIN" for r in rs),
                        wrong_outside=sum(r["wrong"] == "wrong_teacher_outside_scope" for r in rs),
                        wrong_inside=sum(r["wrong"] == "wrong_teacher_inside_scope" for r in rs),
                        escalated=sum(r["grammar"].startswith("escalated") for r in rs),
                        work=sum(r["work"] for r in rs), work_by=dict(wb),
                        adapter_share=round(wb.get("adapter", 0) / max(1, sum(wb.values())), 4))
    return out
