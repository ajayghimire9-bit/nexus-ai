"""Wave 27: robust memory / abstraction / certification core on top of the Wave 26 Phase 4 router + synthesizer.

Three architectural changes, all reusing the Phase 4 grammar, Searcher certifier, S1 class verification and
S3 probing unchanged:

1. Epistemic promotion & drift-demotion ladder.
   * CANDIDATE: a schema used by a certified Delta-M answer, not yet retained (no transfer).
   * PROBATIONARY: retained in the library (cross-task transfer), but still subject to the union synthesis
     scan (library / dB / dC / dM tiers must agree).
   * CONSOLIDATED (core): certified support on >= 2 distinct tasks, 0 counterexamples and positive projected net
     benefit (invention cost avoided by the reuse - class verification - an expanded-AST description price).
     Consolidated schemas join a CORE tier consulted right after the base tier: base-only tools first (Occam),
     then base + core; when the core tier fits, the answer is certified there and the synthesis scan is skipped.
   * DEMOTED: one audit counterexample against a consolidated schema demotes it for good (it stays usable as a
     probationary library schema under the union scan, never in the core tier again) and the task falls
     through to the full ladder. Every core-tier answer is audited by one charged oracle call on a perturbed
     query (domain-free: a reordering of the query list); this is the Phase 5 drift detector applied to the core.
2. Cross-task MDL admission filter. A candidate is retained (PROBATIONARY) only if it passes an active
   boundary-falsification probe (two charged oracle calls on perturbed inputs that some certified chain using the
   schema must predict) or is certified on >= 2 distinct tasks, AND its summed MDL gain (pointer-coded outputs
   minus expanded-AST model bits) is positive. A coincidental one-off fit on a noise world fails the probe.
3. Contract-signature index. Every proved-submultiset mechanism carries postconditions that are closed under
   any sub-multiset map: |out| <= k (head/tail k, S[k]); every item satisfies p (F[p], comp pred p); out distinct
   on path (first_occ path). If every tool of a tier has a VERIFIED sub-multiset/permutation class, every later
   step of any chain preserves these, so a tool whose postcondition some public output violates cannot occur in
   any fitting chain and is pruned before enumeration (sound). Tiers containing a tool without a proved class
   (opaque stdlib tools: empirical contracts only - vault firewall) are not pruned. The synthesis scan prunes
   candidate instantiations and partner mechanisms the same way.
"""
from __future__ import annotations

import math
import random

from nexus.wave24_domains import Tool, vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import AMBIGUOUS, NONE_FOUND, UNIQUE, meter
from nexus.wave25_factored import Mech, get, run
from nexus.wave25_s3 import choose_probe, enumerate_H
from nexus.wave26_phase4 import (C_ORACLE, EXTENDED, PRIMITIVES, PROBE_BUDGET, ROLE_SCHEMA, Comp, Library,
                                 _fits, _tool, all_schemas, certify, class_filter, instantiate, provenance_barrier,
                                 schema_class, tiered_certify)

CANDIDATE, PROBATIONARY, CONSOLIDATED, DEMOTED = "CANDIDATE", "PROBATIONARY", "CONSOLIDATED", "DEMOTED"
NODE_PRICE = 1000            # work units per expanded-AST node (description price of a consolidated schema)
MDL_SYMBOL_BITS = 4.0        # bits per expanded-AST node
FALSIFY_PROBES = 2


# --------------------------------------------------------------------------- 3. contract-signature index
def proved_class(fn):
    """Verified structural class of a mechanism, or None if unproved (opaque / empirical)."""
    if isinstance(fn, Comp):
        return schema_class(fn.schema)[0]
    if isinstance(fn, Mech) and fn.role in ("F", "S", "Sort"):
        return schema_class(ROLE_SCHEMA["S_by" if fn.role == "S" else fn.role])[0]
    return None


def postconditions(fn):
    """Postconditions closed under every sub-multiset map (only for item-preserving mechanisms)."""
    if isinstance(fn, Comp):
        if fn.transform != "id":
            return ()
        if fn.cond in ("head", "tail"):
            return (("len_le", fn.cparam),)
        if fn.cond == "pred":
            return (("all", fn.cparam),)
        if fn.cond == "first_occ":
            return (("distinct", fn.cparam),)
        return ()
    if isinstance(fn, Mech):
        if fn.role == "F":
            return (("all", fn.slots[0]),)
        if fn.role == "S":
            return (("len_le", fn.slots[0]),)
    return ()


def _violates(post, y):
    kind, p = post
    if not isinstance(y, list):
        return False
    if kind == "len_le":
        return len(y) > p
    if kind == "all":
        try:
            return not all(p(it) for it in y)
        except Exception:
            return False
    try:
        keys = [vkey(get(it, p)) for it in y]
    except Exception:
        return False
    return len(keys) != len(set(keys))


def tier_provable(fns):
    return all(proved_class(f) in ("submultiset", "permutation") for f in fns)


def prune_fns(fns, public, m, *, enabled=True):
    """Drop mechanisms whose postcondition some public output violates (caller guarantees soundness)."""
    if not enabled:
        return list(fns)
    ys = [y for _, y in public]
    out = []
    for f in fns:
        ok = True
        for post in postconditions(f):
            for y in ys:
                m.charge("index_work_units", 1)
                if _violates(post, y):
                    ok = False
                    break
            if not ok:
                break
        if ok:
            out.append(f)
    return out


def index_tools(tools, public, m, stats):
    """Sound tier pruning: only when every tool in the tier has a verified sub-multiset/permutation class."""
    fns = [t.fn for t in tools]
    if not tier_provable(fns):
        stats["index_disabled_tiers"] = stats.get("index_disabled_tiers", 0) + 1
        return list(tools)
    keep = {id(f) for f in prune_fns(fns, public, m)}
    out = [t for t in tools if id(t.fn) in keep]
    stats["index_pruned_tools"] = stats.get("index_pruned_tools", 0) + len(tools) - len(out)
    return out


def synthesize_indexed(public, query, lib, m, stats):
    """Phase 4 synthesis scan with the contract index applied to candidate instantiations and partners."""
    inputs = [x for x, _ in public] + [query]
    present = set(lib.base_roles)
    cands = [s for s in all_schemas() if s not in lib.schemas]
    cands = class_filter(cands, public, m)
    base_all = [t.fn for t in lib.tools(inputs, with_schemas=True)]
    base_ok = tier_provable(base_all)
    base_pruned = prune_fns(base_all, public, m, enabled=base_ok)
    found = []
    for s in sorted(cands):
        inst = instantiate(s, inputs, present=present)
        idpath = s[2] == "id" and base_ok
        insts = prune_fns(inst, public, m, enabled=idpath)
        base = base_pruned if idpath else base_all
        stats["index_pruned_insts"] = stats.get("index_pruned_insts", 0) + len(inst) - len(insts)
        hit = []
        for c in insts:
            if _fits((c,), public, m) or any(_fits((b, c), public, m) or _fits((c, b), public, m) for b in base):
                hit.append(c)
        if hit:
            found.append((s, hit))
    return found


# --------------------------------------------------------------------------- 1+2. epistemic library
def expanded_size(schema):
    return 3 + 1              # order + cond + transform nodes + one bound slot


def mdl_gain(public, schema):
    """Pointer-coded raw outputs minus expanded-AST model bits for one task (bits)."""
    raw = 0.0
    for x, y in public:
        n = len(x) if isinstance(x, list) else 1
        raw += (len(y) if isinstance(y, list) else 1) * math.log2(n + 1) + math.log2(n + 2)
    return raw - expanded_size(schema) * MDL_SYMBOL_BITS


class EpistemicLibrary(Library):
    """Phase 4 Library + the promotion / demotion ladder. `schemas` holds PROBATIONARY, CONSOLIDATED and DEMOTED
    schemas (all usable in the union scan); `candidates` holds non-transferring candidates."""

    def __init__(self, deleted=()):
        super().__init__(deleted)
        self.candidates = {}
        self.events = []

    def status(self, s):
        if s in self.schemas:
            return self.schemas[s]["status"]
        return CANDIDATE if s in self.candidates else None

    def core(self):
        return sorted(s for s, v in self.schemas.items() if v["status"] == CONSOLIDATED)

    def core_tools(self, inputs, provenance_holds=False):
        out = []
        for s in self.core():
            if provenance_holds and s[2] == "proj":
                continue             # same sound contract index as Library.tools: proj cannot occur in a fit
            out += [Tool(c.name(), c, c.name(), kind="primitive", parts=(c.role,))
                    for c in instantiate(s, inputs, present=self.base_roles)]
        return out

    def propose(self, schema, *, label, discovery_cost, public, probe_passed, m):
        """A schema used by a certified Delta-M answer. Returns True if it is (now) retained."""
        if schema in self.schemas:
            self.support(schema, label)
            return False
        c = self.candidates.setdefault(schema, dict(support=set(), gain=0.0, probe_passed=False,
                                                    discovery_cost=discovery_cost))
        if label not in c["support"]:
            c["support"].add(label)
            c["gain"] += mdl_gain(public, schema)
        c["probe_passed"] |= bool(probe_passed)
        mdl_ok = c["gain"] - expanded_size(schema) * MDL_SYMBOL_BITS > 0
        if mdl_ok and (c["probe_passed"] or len(c["support"]) >= 2):
            cls, n = schema_class(schema)
            self.schemas[schema] = dict(cls=cls, uses=len(c["support"]), discovery_cost=c["discovery_cost"],
                                        class_check=n, where=label, reuse_tasks=0, saving=0.0,
                                        status=PROBATIONARY, support=set(c["support"]), counterexamples=0,
                                        mdl_gain=c["gain"], probe_passed=c["probe_passed"])
            m.charge("class_verification_work_units", n)
            del self.candidates[schema]
            self.events.append(("retained", "/".join(schema), label))
            self._maybe_consolidate(schema, label)
            return True
        return False

    def support(self, schema, label):
        r = self.schemas[schema]
        if label not in r["support"]:
            r["support"].add(label)
            r["uses"] += 1
        self._maybe_consolidate(schema, label)

    def net_benefit(self, schema):
        r = self.schemas[schema]
        return (len(r["support"]) - 1) * r["discovery_cost"] - r["class_check"] - NODE_PRICE * expanded_size(schema)

    def _maybe_consolidate(self, schema, label):
        r = self.schemas[schema]
        if r["status"] == PROBATIONARY and len(r["support"]) >= 2 and r["counterexamples"] == 0 and \
                self.net_benefit(schema) > 0:
            r["status"] = CONSOLIDATED
            self.events.append(("consolidated", "/".join(schema), label))

    def counterexample(self, schema, label):
        r = self.schemas[schema]
        r["counterexamples"] += 1
        if r["status"] == CONSOLIDATED:
            r["status"] = DEMOTED
            self.events.append(("demoted", "/".join(schema), label))

    def summary(self):
        return {"/".join(s): dict(status=v["status"], support=len(v["support"]), counterexamples=v["counterexamples"],
                                  mdl_gain=round(v["mdl_gain"], 2), probe_passed=v["probe_passed"],
                                  discovery_cost=v["discovery_cost"], class_check=v["class_check"],
                                  reuse_tasks=v["reuse_tasks"], net_benefit=self.net_benefit(s))
                for s, v in sorted(self.schemas.items())}


def _variants(x, rng, n):
    """Domain-free perturbations of a list input (reorderings), distinct from x where possible."""
    if not isinstance(x, list) or len(x) < 2:
        return []
    out, seen = [], {vkey(x)}
    cands = [list(reversed(x)), x[1:] + x[:1]]
    for _ in range(6):
        y = list(x)
        rng.shuffle(y)
        cands.append(y)
    for v in cands:
        if vkey(v) not in seen:
            seen.add(vkey(v))
            out.append(v)
        if len(out) == n:
            break
    return out


def _chains_predict(chains, v, y):
    for ch in chains:
        try:
            if vkey(run(ch, v)) == vkey(y):
                return True
        except Exception:
            continue
    return False


# --------------------------------------------------------------------------- solver
def solve27(public, queries, oracle, lib, *, world_like, seed=0, label="", extra_tools=()):
    """Base tier -> core tier (audited) -> Phase 4 union-of-repair-tiers ladder, with the contract index on every
    provable tier and in the synthesis scan, and the MDL / falsification admission filter."""
    m = meter(10**12)
    public = list(public)
    rng = random.Random(f"w27:{seed}:{label}")
    inputs = [x for x, _ in public] + list(queries)
    q0 = queries[0]
    stats = {}
    route, invented, admitted, used_library, syn_cost = "base", [], [], False, 0
    audit = None
    try:
        extra = list(extra_tools)
        base_tools = index_tools(lib.tools(inputs, with_schemas=False) + extra, public, m, stats)
        r0 = certify(public, q0, base_tools, 2, m)
        tiers = None
        if r0.status != NONE_FOUND:
            tiers = {"base": (base_tools, 2)}
        elif lib.core():
            prov0 = not provenance_barrier(public, Library(deleted=PRIMITIVES), m)
            core_tools = index_tools(lib.tools(inputs, with_schemas=False) +
                                     lib.core_tools(inputs, provenance_holds=prov0) + extra, public, m, stats)
            rc = certify(public, q0, core_tools, 2, m)
            if rc.status == UNIQUE and oracle is not None:
                # drift detector on the core: one charged audit call on a reordering of the query
                vs = _variants(q0, rng, 1)
                if vs:
                    m.charge("oracle_work_units", C_ORACLE)
                    try:
                        y = oracle(vs[0])
                    except Exception:
                        y = None
                    chains = [tuple(t.fn for t in h[2]) for h in rc.hypotheses]
                    falsified = False
                    if y is not None and not _chains_predict(chains, vs[0], y):
                        # representatives disagree: the answer is falsified only if certifying with the audit pair
                        # no longer yields the same UNIQUE answer
                        rc2 = certify(public + [(vs[0], y)], q0, core_tools, 2, m)
                        falsified = not (rc2.status == UNIQUE and vkey(rc2.answer) == vkey(rc.answer))
                        if not falsified:
                            public.append((vs[0], y))
                            rc = rc2
                    if falsified:
                        used = {t.fn.schema for h in rc.hypotheses for t in h[2] if isinstance(t.fn, Comp)}
                        for sc in sorted(used):
                            if sc in lib.schemas:
                                lib.counterexample(sc, label)
                        audit = "counterexample"
                        public.append((vs[0], y))
                        rc = None
                    else:
                        audit = "passed" if y is not None else "unavailable"
            if rc is not None and rc.status == UNIQUE:          # ambiguous core -> full ladder
                tiers = {"core": (core_tools, 2)}
                route = "core"
        if tiers is None:
            prov = not provenance_barrier(public, Library(deleted=PRIMITIVES), m)
            lib_tools = index_tools(lib.tools(inputs, with_schemas=True, provenance_holds=prov) + extra, public, m,
                                    stats)
            ext_tools = index_tools(lib.tools(inputs, grammar=EXTENDED, with_schemas=True, provenance_holds=prov)
                                    + extra, public, m, stats)
            dc_tools = index_tools(lib.tools(inputs, with_schemas=False) + extra, public, m, stats)
            barrier = provenance_barrier(public, lib, m) and not extra
            tiers = {}
            if not barrier:
                tiers = {"library": (lib_tools, 2), "dB": (ext_tools, 2), "dC": (dc_tools, 3)}
            w0 = m.total
            found = synthesize_indexed(public, q0, lib, m, stats)
            syn_cost = m.total - w0
            inv_tools = [_tool(c) for _, inst in found for c in inst]
            invented = [s for s, _ in found]
            if inv_tools:
                tiers["dM"] = (lib_tools + inv_tools, 2)
            fitting, _ = tiered_certify(public, q0, tiers, m)
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
                    audit=audit, index=stats)
    answers, statuses = [], []
    probes = [0]

    def certify_probe(q):
        results, ans = tiered_certify(public, q, tiers, m)
        while not (len(ans) == 1 and results and all(r.status == UNIQUE for r in results.values())):
            if probes[0] >= PROBE_BUDGET * len(queries) or oracle is None or not results:
                break
            H = []
            for name, r in results.items():
                if r.size in (1, 2):
                    H += enumerate_H(public, [t.fn for t in tiers[name][0]], r.size, m)
            if len(H) < 2:
                break
            reps = [p for r in results.values() for rest, (p, v) in
                    r.searcher.graph.classes.get(tuple(r.searcher.targets), {}).items()]
            x, _ = choose_probe("s3", H, public, q, world_like, rng, m, reps)
            if x is None:
                break
            probes[0] += 1
            m.charge("oracle_work_units", C_ORACLE)
            try:
                y = oracle(x)
            except Exception:
                break
            public.append((x, y))
            results, ans = tiered_certify(public, q, tiers, m)
        return results, ans

    for q in queries:
        try:
            results, ans = certify_probe(q)
            ok = len(ans) == 1 and results and all(r.status == UNIQUE for r in results.values())
            if ok and route == "library" and oracle is not None:
                # audit of a probationary-library answer (same detector as the core audit)
                vs = _variants(q, rng, 1)
                if vs:
                    m.charge("oracle_work_units", C_ORACLE)
                    try:
                        y = oracle(vs[0])
                    except Exception:
                        y = None
                    hyps = [h for r in results.values() for h in r.hypotheses]
                    chains = [tuple(t.fn for t in h[2]) for h in hyps]
                    if y is not None and not _chains_predict(chains, vs[0], y):
                        old = set(ans)
                        public.append((vs[0], y))
                        results, ans = certify_probe(q)
                        ok2 = len(ans) == 1 and results and all(r.status == UNIQUE for r in results.values())
                        if ok2 and set(ans) == old:
                            audit = audit or "passed"
                        else:
                            for sc in sorted({t.fn.schema for h in hyps for t in h[2] if isinstance(t.fn, Comp)}):
                                if sc in lib.schemas:
                                    lib.counterexample(sc, label)
                            audit = "counterexample"
                    elif y is not None:
                        audit = audit or "passed"
        except WorkExhausted:
            answers.append(None)
            statuses.append("EXHAUSTED")
            continue
        ok = len(ans) == 1 and results and all(r.status == UNIQUE for r in results.values())
        statuses.append(UNIQUE if ok else (AMBIGUOUS if results else NONE_FOUND))
        win = next(iter(results.values())) if ok else None
        answers.append(win.answer if ok else None)
        if ok and route == "dM" and "dM" in results:
            hyps = results["dM"].hypotheses
            used = sorted({t.fn.schema for t in hyps[0][2] if isinstance(t.fn, Comp)})
            for sc in used:
                if sc in lib.schemas:
                    lib.support(sc, label)
                    continue
                chains = [tuple(t.fn for t in h[2]) for h in hyps
                          if any(isinstance(t.fn, Comp) and t.fn.schema == sc for t in h[2])]
                passed = False
                if oracle is not None:
                    # active boundary-falsification probe: reorderings of the query and of a public input
                    vs = _variants(q, rng, 1) + _variants(public[0][0], rng, FALSIFY_PROBES - 1)
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
                # discovery cost = fully loaded invention cost (Tycho): task work so far + the class verification
                dcost = m.total + (0 if sc in lib.schemas else schema_class(sc)[1])
                if lib.propose(sc, label=label, discovery_cost=dcost, public=public, probe_passed=passed, m=m):
                    admitted.append(sc)
        if ok and route in ("library", "core") and route in results:
            for sc in sorted({t.fn.schema for h in results[route].hypotheses for t in h[2] if isinstance(t.fn, Comp)}):
                if sc in lib.schemas:
                    lib.schemas[sc]["reuse_tasks"] += 1
                    lib.support(sc, label)
    return dict(route=route, answers=answers, statuses=statuses, work=m.total, work_by=dict(m.counts),
                probes=probes[0], invented=[list(s) for s in invented], admitted=[list(s) for s in admitted],
                used_library=used_library, audit=audit, index=stats)
