"""Wave 29 (Occam-margin + mandatory out-of-sample verification), built on the Wave 28 engine text below.

Wave 29 changes (owner design, 2026-10-26):
  * k_min + 1 shell: in the core tier and every repair tier (library, dB, dC, dM) the certificate is not issued from the
    minimal size alone: the next size shell (k_min + 1, within the tier's depth) is enumerated too (Searcher
    level() + macro completions), and UNIQUE requires every fitting program in both shells to agree on the query.
    If the shell cannot be finished within the budget the tier is not UNIQUE (conservative). Only the base tier
    (Occam convention) keeps the plain minimal-size certificate.
  * the core-tier audit (drift detector) uses the same rich x_verify input instead of a reordered query.
  * x_verify: no non-core route may certify from passive public examples alone. Before issuing the answer, one
    verification input is synthesised from the task's own inputs (reorderings, a duplicated item, a dropped
    item, concatenations of two inputs - domain-free, built only from observed items), chosen to maximise the
    number of distinct predictions among the certified programs, the identity, every proper sub-program
    ablation and the shell alternatives (ties: prefer inputs where the certified program is not the identity).
    One charged oracle call gives y_verify. If no certified program predicts it, the pair is appended and the
    tiers are re-certified (with the remaining S3 probe budget); only a UNIQUE answer that survives is issued.
Wave 28 text follows.

Wave 28: pre-enumeration postcondition filter for EVERY tier (incl. core and Delta-B with unproved tools), and
the Wave 26 library certification restored (no library-route withdrawal audit). Built on the Wave 27 engine
(`wave27_core`: ladder, audited core tier, MDL / falsification admission) - only the index and the solver change.

Contract-signature algebra (replaces the Wave 27 tier-level on/off index):
  * postconditions of a mechanism (proved by construction; checked in tests):
      len_le k (head/tail k, S[k]); all p (F[p], comp pred p); distinct path (first_occ path)  -- "closed" kinds;
      sorted(path, desc) (any id-transform mechanism that traverses in a FIELD order: comp by-field, S[k, field],
      Sort[field])                                                                                -- order kind.
  * preservation: a closed postcondition survives any later mechanism with a VERIFIED sub-multiset/permutation
    class; a sortedness postcondition survives any later mechanism that is a proved SUBSEQUENCE map (F; S / comp
    in position-ascending order with id transform). Unproved tools (opaque stdlib tools: empirical contracts
    only - vault firewall) and projecting schemas preserve nothing.
  * V(t) = postconditions of t violated by some public output. A chain can fit only if its LAST tool has
    V = {} and every earlier tool t is followed by some tool that does not preserve all of V(t).
  * Depth-2 tiers: tools with V != {} leave the enumerated tool set; the only chains through them that could
    still fit, (t, g) with V(g) = {} and g not preserving V(t), are re-admitted as macro hypotheses that join
    the tier's certificate exactly where the Searcher would have met them (depth 2, only if no depth-1 program
    fits - the certificate is minimal-size). The fitting hypothesis set is therefore identical to the unpruned
    tier's; only the enumeration shrinks. Depth-3 tiers drop only tools nothing in the tier can rescue.
  * The synthesis scan applies the same pair rule to candidate instantiations and partners.
Library-route answers are certified exactly as in Wave 26 (union of repair tiers, S3 probes); the core-tier
audit (drift detector for consolidated schemas) is kept.
"""
from __future__ import annotations

import random

from nexus.wave24_domains import Tool, vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import AMBIGUOUS, NONE_FOUND, UNIQUE, meter
from nexus.wave25_factored import Mech, get, run, _num
from nexus.wave25_s3 import choose_probe, enumerate_H
from nexus.wave26_phase4 import (C_ORACLE, EXTENDED, PRIMITIVES, PROBE_BUDGET, Comp, Library, _fits, _tool,
                                 all_schemas, certify, class_filter, instantiate, provenance_barrier, schema_class)
from nexus.wave27_core import (NODE_PRICE, PROBATIONARY, EpistemicLibrary as _Lib27, _chains_predict, _variants,
                               _violates, expanded_size, postconditions, proved_class)


class EpistemicLibrary(_Lib27):
    """Wave 27 ladder; the projected benefit of promotion also counts the measured cost of staying probationary.

    Wave 27: net = (support - 1) x invention cost - class check - description price. With the index, invention
    is cheap while a probationary reuse pays the full union scan, so the value of one more use is taken as
    max(invention cost, mean observed work of the probationary-library reuses so far)."""

    def support(self, schema, label, work=None):
        r = self.schemas[schema]
        if work is not None and label not in r["support"]:
            r.setdefault("reuse_work", []).append(work)
        super().support(schema, label)

    def net_benefit(self, schema):
        r = self.schemas[schema]
        rw = r.get("reuse_work") or []
        per_use = max(r["discovery_cost"], sum(rw) / len(rw) if rw else 0)
        return (len(r["support"]) - 1) * per_use - r["class_check"] - NODE_PRICE * expanded_size(schema)

__all__ = ["EpistemicLibrary", "solve29"]


# --------------------------------------------------------------------------- contract-signature algebra
def order_post(fn):
    if isinstance(fn, Comp) and fn.transform == "id" and fn.order.path != "#":
        return ("sorted", (fn.order.path, fn.order.desc))
    if isinstance(fn, Mech) and fn.role in ("S", "Sort"):
        o = fn.slots[1] if fn.role == "S" else fn.slots[0]
        if o.path != "#":
            return ("sorted", (o.path, o.desc))
    return None


def posts28(fn):
    out = list(postconditions(fn))
    op = order_post(fn)
    if op is not None:
        out.append(op)
    return tuple(out)


def _violates28(post, y):
    if post[0] != "sorted":
        return _violates(post, y)
    if not isinstance(y, list):
        return False
    path, desc = post[1]
    try:
        vals = [get(it, path) for it in y]
    except Exception:
        return False
    if not all(_num(v) for v in vals):
        return False
    return any((a < b) if desc else (a > b) for a, b in zip(vals, vals[1:]))


def is_subsequence_map(fn):
    if isinstance(fn, Mech):
        if fn.role == "F":
            return True
        if fn.role == "S":
            o = fn.slots[1]
            return o.path == "#" and not o.desc
        return False
    if isinstance(fn, Comp):
        return fn.transform == "id" and fn.order.path == "#" and not fn.order.desc
    return False


def preserves(g, post):
    if post[0] == "sorted":
        return is_subsequence_map(g)
    return proved_class(g) in ("submultiset", "permutation")


def violated(fn, public, m):
    ys = [y for _, y in public]
    out = []
    for post in posts28(fn):
        for y in ys:
            m.charge("index_work_units", 1)
            if _violates28(post, y):
                out.append(post)
                break
    return tuple(out)


def pair_ok(a, va, b, vb):
    """Can the chain (a, b) fit, given the violated sets? Last tool clean; a rescued by b."""
    if vb:
        return False
    return not va or not all(preserves(b, p) for p in va)


class Macro:
    """(t, g) as one hypothesis (only ever a depth-2 completion of a pruned tier)."""

    def __init__(self, t, g):
        self.t, self.g = t, g

    def __call__(self, xs):
        return self.g(self.t(xs))


def _macro_tool(t, g):
    return Tool(f"{t.name}>{g.name}", Macro(t.fn, g.fn), f"{t.name} then {g.name}", cost=2, layer=1,
                parts=(t.name, g.name), children=(t, g), kind="macro")


def index28(tools, public, depth, m, stats):
    """Returns (enumerated tools, macro completions). Sound and complete for the minimal-depth certificate."""
    V = [violated(t.fn, public, m) for t in tools]
    keep, macros = [], []
    clean = [(t, v) for t, v in zip(tools, V) if not v]
    for t, v in zip(tools, V):
        if not v:
            keep.append(t)
            continue
        rescuers = [g for g, vg in clean if pair_ok(t.fn, v, g.fn, vg)]
        if depth >= 3:
            if rescuers:
                keep.append(t)          # depth 3: keep anything a later tool could rescue
            continue
        if depth == 2 and rescuers:
            macros.append((t, rescuers))
    stats["index_pruned_tools"] = stats.get("index_pruned_tools", 0) + len(tools) - len(keep)
    stats["index_macro_heads"] = stats.get("index_macro_heads", 0) + len(macros)
    return keep, macros


# --------------------------------------------------------------------------- certification with macro completion
class _Res:
    pass


_RAISED = object()


def _macro_hyps(public, query, macros, m):
    # Searcher convention: depth-2 chains extend one representative per observational class of depth-1 outputs
    # (on public inputs + query); each application costs tool.cost per value.
    xs = [x for x, _ in public] + [query]
    targets = [vkey(y) for _, y in public]
    heads = {}
    for t, rescuers in macros:
        outs = []
        for v in xs:
            m.charge("search_work_units", t.cost)
            try:
                outs.append(t.fn(v))
            except Exception:
                outs.append(_RAISED)
        key = tuple("<raised>" if o is _RAISED else vkey(o) for o in outs)
        if key in heads:
            known = {g.name for g in heads[key][2]}
            heads[key][2].extend(g for g in rescuers if g.name not in known)
        else:
            heads[key] = (t, outs, list(rescuers))
    hyps = []
    for t, outs, rescuers in heads.values():
        if any(o is _RAISED for o in outs):
            continue
        for g in rescuers:
            res = []
            for o in outs:
                m.charge("search_work_units", g.cost)
                try:
                    res.append(g.fn(o))
                except Exception:
                    res.append(_RAISED)
                    break
            if len(res) == len(outs) and all(r is not _RAISED for r in res) and \
                    all(vkey(r) == k for r, k in zip(res, targets)):
                mt = _macro_tool(t, g)
                hyps.append(((mt.name,), res[-1], (mt,)))
    return hyps


def certify_pm(public, query, tier, m):
    tools, depth, macros = tier
    r = certify(public, query, tools, depth, m)
    if not macros or depth < 2 or r.status not in (NONE_FOUND, UNIQUE, AMBIGUOUS):
        return r
    if r.status != NONE_FOUND and r.size < 2:
        return r                          # a depth-1 program fits: depth-2 chains are never reached
    hyps = _macro_hyps(public, query, macros, m)
    if not hyps:
        return r
    out = _Res()
    out.searcher = getattr(r, "searcher", None)
    out.work = r.work
    base_h = list(r.hypotheses) if r.status != NONE_FOUND else []
    seen = {vkey(h[1]) for h in base_h}
    merged = list(base_h)
    for h in hyps:                                  # one representative per new answer (class semantics)
        k = vkey(h[1])
        if k not in seen:
            seen.add(k)
            merged.append(h)
    out.hypotheses = merged
    out.size = 2
    out.answer = merged[0][1]
    out.witness = merged[0][0]
    out.status = UNIQUE if len(seen) == 1 else AMBIGUOUS
    return out


MARGIN_TIERS = ("core", "library", "dB", "dC", "dM")


def certify_shell(public, query, tier, m):
    """Minimal-size certificate + the k_min + 1 shell (within the tier depth): UNIQUE only if both shells agree."""
    tools, depth, macros = tier
    r = certify_pm(public, query, tier, m)
    if r.status not in (UNIQUE, AMBIGUOUS) or r.size >= depth:
        return r
    s = getattr(r, "searcher", None)
    out = _Res()
    out.searcher, out.work, out.size = s, r.work, r.size
    hyps = list(r.hypotheses)
    unknown = s is None
    if s is not None:
        w0 = s.m.total
        try:
            found = s.level()
            hyps += [(tuple(t.name for t in p), q, p) for p, q in found.values()]
        except WorkExhausted:
            unknown = True
        m.charge("shell_work_units", s.m.total - w0)
    if r.size + 1 == 2 and macros:
        hyps += _macro_hyps(public, query, macros, m)
    seen, merged = set(), []
    for h in hyps:
        k = vkey(h[1])
        if k not in seen:
            seen.add(k)
            merged.append(h)
    out.hypotheses = merged
    out.shell_hypotheses = len(hyps) - len(r.hypotheses)
    out.answer, out.witness = merged[0][1], merged[0][0]
    out.status = UNIQUE if len(seen) == 1 and not unknown else AMBIGUOUS
    return out


def tiered_certify28(public, query, tiers, m):
    results, answers = {}, set()
    for name, tier in tiers.items():
        r = certify_shell(public, query, tier, m) if name in MARGIN_TIERS else certify_pm(public, query, tier, m)
        if r.status == NONE_FOUND:
            continue
        results[name] = r
        answers |= {vkey(h[1]) for h in r.hypotheses}
        if r.status not in (UNIQUE, AMBIGUOUS):
            answers.add(("__unknown__", name))
    return results, answers


def _flat(chain_tools):
    out = []
    for t in chain_tools:
        if t.kind == "macro" and t.children:
            out += _flat(t.children)
        else:
            out.append(t)
    return out


def _schemas_in(h):
    return {t.fn.schema for t in _flat(h[2]) if isinstance(t.fn, Comp)}


def synthesize28(public, query, lib, m, stats):
    inputs = [x for x, _ in public] + [query]
    present = set(lib.base_roles)
    cands = class_filter([s for s in all_schemas() if s not in lib.schemas], public, m)
    base = [t.fn for t in lib.tools(inputs, with_schemas=True)]
    vb = [violated(b, public, m) for b in base]
    found = []
    for s in sorted(cands):
        hit = []
        for c in instantiate(s, inputs, present=present):
            vc = violated(c, public, m)
            ok = False
            if not vc and _fits((c,), public, m):
                ok = True
            else:
                for b, v in zip(base, vb):
                    if (pair_ok(b, v, c, vc) and _fits((b, c), public, m)) or \
                            (pair_ok(c, vc, b, v) and _fits((c, b), public, m)):
                        ok = True
                        break
            if ok:
                hit.append(c)
            stats["synth_insts"] = stats.get("synth_insts", 0) + 1
        if hit:
            found.append((s, hit))
    return found


def _tier(tools, depth, public, m, stats):
    keep, macros = index28(tools, public, depth, m, stats)
    return (keep, depth, macros)


# --------------------------------------------------------------------------- x_verify
def verify_candidates(inputs, rng, limit=24):
    """Domain-free rich inputs built only from observed items: reorderings, duplicated item, dropped item,
    concatenations of two inputs."""
    lists = [x for x in inputs if isinstance(x, list) and len(x) >= 2]
    seen = {vkey(x) for x in inputs}
    out = []

    def add(v):
        k = vkey(v)
        if k not in seen:
            seen.add(k)
            out.append(v)
    for x in lists:
        add(list(reversed(x)))
        add(x[1:] + x[:1])
        add(x + [x[len(x) // 2]])
        add(x[:-1])
        y = list(x)
        rng.shuffle(y)
        add(y)
        add(y + [y[0]])
    for a, b in zip(lists, lists[1:] + lists[:1]):
        if a is not b:
            add(a + b)
            add(b[: len(b) // 2] + a[len(a) // 2:])
    return out[:limit]


def _ablations(chain):
    return [chain[:i] + chain[i + 1:] for i in range(len(chain))] if len(chain) > 1 else [()]


def choose_verify(cert_chains, alt_chains, inputs, rng, m):
    """Pick the candidate maximising distinct predictions among certified programs, identity, ablations and
    shell / tier alternatives; tie-break toward inputs the certified program changes."""
    models = list(cert_chains) + list(alt_chains) + [()] + [a for c in cert_chains for a in _ablations(c)]
    best, best_score = None, None
    for v in verify_candidates(inputs, rng):
        outs = set()
        moved = 0
        for ch in models:
            m.charge("verify_design_work_units", max(1, len(ch)))
            try:
                outs.add(vkey(run(ch, v)))
            except Exception:
                outs.add("<raised>")
        try:
            moved = int(any(vkey(run(c, v)) != vkey(v) for c in cert_chains))
        except Exception:
            moved = 1
        score = (len(outs), moved)
        if best_score is None or score > best_score:
            best, best_score = v, score
    return best


# --------------------------------------------------------------------------- solver
def solve29(public, queries, oracle, lib, *, world_like, seed=0, label="", extra_tools=()):
    m = meter(10**12)
    public = list(public)
    rng = random.Random(f"w29:{seed}:{label}")
    inputs = [x for x, _ in public] + list(queries)
    q0 = queries[0]
    stats = {}
    route, invented, admitted, used_library, syn_cost = "base", [], [], False, 0
    audit = None
    try:
        extra = list(extra_tools)
        base_t = _tier(lib.tools(inputs, with_schemas=False) + extra, 2, public, m, stats)
        r0 = certify_pm(public, q0, base_t, m)
        tiers = None
        if r0.status != NONE_FOUND:
            tiers = {"base": base_t}
        elif lib.core():
            prov0 = not provenance_barrier(public, Library(deleted=PRIMITIVES), m)
            core_t = _tier(lib.tools(inputs, with_schemas=False) + lib.core_tools(inputs, provenance_holds=prov0)
                           + extra, 2, public, m, stats)
            rc = certify_shell(public, q0, core_t, m)          # Wave 29: core also checks the k_min + 1 shell
            if rc.status == UNIQUE and oracle is not None:
                # Wave 29: the core audit input is the same rich x_verify (not just a reordering of the query)
                cchains = [tuple(t.fn for t in _flat(h[2])) for h in rc.hypotheses]
                v0 = choose_verify(cchains, [], inputs, rng, m)
                vs = [v0] if v0 is not None else []
                if vs:
                    m.charge("oracle_work_units", C_ORACLE)
                    try:
                        y = oracle(vs[0])
                    except Exception:
                        y = None
                    chains = [tuple(t.fn for t in _flat(h[2])) for h in rc.hypotheses]
                    falsified = False
                    if y is not None and not _chains_predict(chains, vs[0], y):
                        rc2 = certify_shell(public + [(vs[0], y)], q0, core_t, m)
                        falsified = not (rc2.status == UNIQUE and vkey(rc2.answer) == vkey(rc.answer))
                        if not falsified:
                            public.append((vs[0], y))
                            rc = rc2
                    if falsified:
                        for sc in sorted({s for h in rc.hypotheses for s in _schemas_in(h)}):
                            if sc in lib.schemas:
                                lib.counterexample(sc, label)
                        audit = "counterexample"
                        public.append((vs[0], y))
                        rc = None
                    else:
                        audit = "passed" if y is not None else "unavailable"
            if rc is not None and rc.status == UNIQUE:
                tiers = {"core": core_t}
                route = "core"
        if tiers is None:
            prov = not provenance_barrier(public, Library(deleted=PRIMITIVES), m)
            lib_raw = lib.tools(inputs, with_schemas=True, provenance_holds=prov) + extra
            lib_t = _tier(lib_raw, 2, public, m, stats)
            ext_t = _tier(lib.tools(inputs, grammar=EXTENDED, with_schemas=True, provenance_holds=prov) + extra, 2,
                          public, m, stats)
            dc_t = _tier(lib.tools(inputs, with_schemas=False) + extra, 3, public, m, stats)
            barrier = provenance_barrier(public, lib, m) and not extra
            tiers = {}
            if not barrier:
                tiers = {"library": lib_t, "dB": ext_t, "dC": dc_t}
            w0 = m.total
            found = synthesize28(public, q0, lib, m, stats)
            syn_cost = m.total - w0
            inv_tools = [_tool(c) for _, inst in found for c in inst]
            invented = [s for s, _ in found]
            if inv_tools:
                tiers["dM"] = _tier(lib_raw + inv_tools, 2, public, m, stats)
            fitting, _ = tiered_certify28(public, q0, tiers, m)
            for name in ("library", "dB", "dC", "dM"):
                if name in fitting:
                    route = name
                    break
            else:
                route = "dM"
            if barrier:
                route = "dM"
            used_library = route == "library"
    except WorkExhausted:
        return dict(route=route, answers=[None] * len(queries), statuses=["EXHAUSTED"] * len(queries), work=m.total,
                    work_by=dict(m.counts), probes=0, invented=[], admitted=[], used_library=used_library,
                    audit=audit, index=stats, verify=[])
    answers, statuses, probes = [], [], 0
    verify_log = []
    for q in queries:
        try:
            results, ans = tiered_certify28(public, q, tiers, m)
            while not (len(ans) == 1 and results and all(r.status == UNIQUE for r in results.values())):
                if probes >= PROBE_BUDGET * len(queries) or oracle is None or not results:
                    break
                H = []
                for name, r in results.items():
                    if r.size in (1, 2):
                        H += enumerate_H(public, [t.fn for t in tiers[name][0]], r.size, m)
                if len(H) < 2:
                    break
                reps = [p for r in results.values() if getattr(r, "searcher", None) is not None for rest, (p, v) in
                        r.searcher.graph.classes.get(tuple(r.searcher.targets), {}).items()]
                x, _ = choose_probe("s3", H, public, q, world_like, rng, m, reps)
                if x is None:
                    break
                probes += 1
                m.charge("oracle_work_units", C_ORACLE)
                try:
                    y = oracle(x)
                except Exception:
                    break
                public.append((x, y))
                results, ans = tiered_certify28(public, q, tiers, m)
        except WorkExhausted:
            answers.append(None)
            statuses.append("EXHAUSTED")
            continue
        ok = len(ans) == 1 and results and all(r.status == UNIQUE for r in results.values())
        if ok and route not in ("base", "core") and oracle is not None:
            try:
                hyps = [h for r in results.values() for h in r.hypotheses]
                cert = [tuple(t.fn for t in _flat(h[2])) for h in hyps]
                v = choose_verify(cert, [], [x for x, _ in public] + list(queries), rng, m)
                if v is not None:
                    m.charge("oracle_work_units", C_ORACLE)
                    try:
                        yv = oracle(v)
                    except Exception:
                        yv = None
                    if yv is not None:
                        public.append((v, yv))
                        verify_log.append("passed" if _chains_predict(cert, v, yv) else "falsified")
                        if verify_log[-1] == "falsified":
                            results, ans = tiered_certify28(public, q, tiers, m)
                            while not (len(ans) == 1 and results and
                                       all(r.status == UNIQUE for r in results.values())):
                                if probes >= PROBE_BUDGET * len(queries) or not results:
                                    break
                                H = []
                                for name, r in results.items():
                                    if r.size in (1, 2):
                                        H += enumerate_H(public, [t.fn for t in tiers[name][0]], r.size, m)
                                if len(H) < 2:
                                    break
                                reps = [p for r in results.values() if getattr(r, "searcher", None) is not None
                                        for rest, (p, vv) in
                                        r.searcher.graph.classes.get(tuple(r.searcher.targets), {}).items()]
                                x, _ = choose_probe("s3", H, public, q, world_like, rng, m, reps)
                                if x is None:
                                    break
                                probes += 1
                                m.charge("oracle_work_units", C_ORACLE)
                                try:
                                    y = oracle(x)
                                except Exception:
                                    break
                                public.append((x, y))
                                results, ans = tiered_certify28(public, q, tiers, m)
                            ok = len(ans) == 1 and results and all(r.status == UNIQUE for r in results.values())
            except WorkExhausted:
                ok = False
        statuses.append(UNIQUE if ok else (AMBIGUOUS if results else NONE_FOUND))
        win = next(iter(results.values())) if ok else None
        answers.append(win.answer if ok else None)
        if ok and route == "dM" and "dM" in results:
            hyps = results["dM"].hypotheses
            for sc in sorted(_schemas_in(hyps[0])):
                if sc in lib.schemas:
                    lib.support(sc, label)
                    continue
                chains = [tuple(t.fn for t in _flat(h[2])) for h in hyps if sc in _schemas_in(h)]
                passed = False
                if oracle is not None:
                    vs = _variants(q, rng, 1) + _variants(public[0][0], rng, 1)
                    passed = bool(vs)
                    for v in vs:
                        m.charge("oracle_work_units", C_ORACLE)
                        try:
                            y = oracle(v)
                        except Exception:
                            passed = False
                            break
                        if not _chains_predict(chains, v, y):
                            passed = False
                            break
                dcost = m.total + (0 if sc in lib.schemas else schema_class(sc)[1])
                if lib.propose(sc, label=label, discovery_cost=dcost, public=public, probe_passed=passed, m=m):
                    admitted.append(sc)
        if ok and route in ("library", "core") and route in results:
            for sc in sorted({s for h in results[route].hypotheses for s in _schemas_in(h)}):
                if sc in lib.schemas:
                    lib.schemas[sc]["reuse_tasks"] += 1
                    lib.support(sc, label, work=m.total if route == "library" else None)
    return dict(route=route, answers=answers, statuses=statuses, work=m.total, work_by=dict(m.counts), probes=probes,
                invented=[list(s) for s in invented], admitted=[list(s) for s in admitted], used_library=used_library,
                audit=audit, index=stats, verify=verify_log)
