"""Wave 26 Phase 4: three-way failure router (Delta-B / Delta-C / Delta-M) + bounded mechanism synthesizer.

Base M: the wave25 white-box mechanisms F[p], S[k, o], Sort[o] over the domain-free binding grammar
(base bindings: 3 threshold quantiles per numeric path, k in {1,2,3}); base certificate depth 2.

Synthesizer grammar (lower-level, strictly larger than M):
    comp(gen, cond, transform)(xs) = [transform(x) for x in gen(xs) if cond(position, x, history)]
    gen       in {fwd, rev, by(path, asc), by(path, desc)}            (stable)
    cond      in {all, head k, tail k, first_occ path, pred p}
    transform in {id, proj path}
F = comp(fwd, pred, id), S[k, pos] = comp(fwd, head, id), S[k, o] = comp(by, head, id), Sort = comp(by, all, id),
so a deleted primitive is a point of the grammar that can be re-synthesised.

Router, on a base-tier failure (no program over the current library fits the public pairs), in cost order:
  1. proved Delta-M barrier: every library mechanism has a VERIFIED sub-multiset/permutation class
     (S1-Auto), so any composition returns a sub-multiset of its input; a public output that is not a
     sub-multiset of its input (or not a list) proves no composition under any binding can fit -> Delta-M;
  2. Delta-B: the same mechanisms at the same depth under an extended binding grammar (every observed
     threshold value, k up to 5) fit -> rebind;
  3. Delta-C: base bindings, composition depth 3 fit -> recombine;
  4. Delta-M by exhaustion -> synthesize: library schemas, then the grammar (schemas pruned by verified
     class), every fitting instantiation (alone, or composed with one library mechanism) is added and the
     exact certifier + answer-directed probing decide. A schema used by a certified answer is admitted to
     the library (Tycho: discovery cost recorded; net benefit = invention cost avoided by later reuse -
     discovery - class verification).
Generator labels (fault kind, deleted primitive) are used for scoring only and never reach NEXUS.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from nexus.wave24_domains import Tool, vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import AMBIGUOUS, NONE_FOUND, UNIQUE, Searcher, meter
from nexus.wave25_contracts import _class_holds, p_provenance, universes
from nexus.wave25_factored import (Mech, Order, Pred, binding_grammar, get, ints_world, paths_of, run, tool_of, _num)
from nexus.wave25_s3 import choose_probe, enumerate_H
from nexus.wave26_phase1 import records_world_f

C_ORACLE = 20
PROBE_BUDGET = 3
CERT_BUDGET = 400_000
BASE = dict(n_thresholds=3, ks=(1, 2, 3))
EXTENDED = dict(n_thresholds=10, ks=(1, 2, 3, 4, 5))
CONDS = ("all", "head", "tail", "first_occ", "pred")
TRANSFORMS = ("id", "proj")
ROLE_SCHEMA = {"F": ("ord", "pred", "id"), "S_pos": ("ord", "head", "id"), "S_by": ("ord", "head", "id"),
               "Sort": ("ord", "all", "id")}
PRIMITIVES = ("F", "S", "Sort")


# --------------------------------------------------------------------------- synthesizer grammar
# The traversal order is a SLOT (factored M x B): ord(o), o in {position asc, position desc, field asc, field desc}.
POS_ASC, POS_DESC = Order("#", False), Order("#", True)


@dataclass(frozen=True)
class Comp:
    order: object                 # Order (path "#" = position)
    cond: str
    cparam: object
    transform: str
    tparam: object = None
    gen: str = "ord"

    @property
    def schema(self):
        return ("ord", self.cond, self.transform)

    @property
    def role(self):
        return "Inv:" + "/".join(self.schema)

    @property
    def slots(self):
        return tuple(x for x in (self.order, self.cparam, self.tparam) if x is not None)

    def __call__(self, xs):
        if not isinstance(xs, list):
            raise TypeError("list mechanism on a scalar")
        n = len(xs)
        o = self.order
        if o.path == "#":
            idx = list(range(n - 1, -1, -1)) if o.desc else list(range(n))
        else:
            idx = sorted(range(n), key=lambda i: ((-get(xs[i], o.path)) if o.desc else get(xs[i], o.path), i))
        out, seen = [], set()
        for pos, i in enumerate(idx):
            x = xs[i]
            c = self.cond
            if c == "all":
                ok = True
            elif c == "head":
                ok = pos < self.cparam
            elif c == "tail":
                ok = pos >= n - self.cparam
            elif c == "first_occ":
                k = vkey(get(x, self.cparam))
                ok = k not in seen
                seen.add(k)
            else:
                ok = self.cparam(x)
            if ok:
                out.append(get(x, self.tparam) if self.transform == "proj" else x)
        return out

    def name(self):
        cp = self.cparam.name() if isinstance(self.cparam, Pred) else self.cparam
        return f"Comp[{self.order.name()},{self.cond}:{cp},{self.transform}:{self.tparam}]"


def all_schemas():
    return [("ord", c, t) for c in CONDS for t in TRANSFORMS]


def base_equivalent_inst(c, present_roles):
    """An instantiation identical by construction to a PRESENT base mechanism (or the identity) is skipped."""
    if c.transform != "id":
        return False
    pos_asc = c.order.path == "#" and not c.order.desc
    if c.cond == "all" and pos_asc:
        return True                                                  # identity
    if c.cond == "pred" and pos_asc and "F" in present_roles:
        return True
    if c.cond == "head" and "S" in present_roles and not (c.order.path == "#" and c.order.desc):
        return True
    if c.cond == "all" and c.order.path != "#" and "Sort" in present_roles:
        return True
    return False


def instantiate(schema, inputs, *, ks=(1, 2, 3, 4, 5), present=()):
    _, c, t = schema
    items = [it for x in inputs if isinstance(x, list) for it in x]
    if not items:
        return []
    paths = paths_of(items)
    num_paths = [p for p in paths if all(_num(get(i, p)) for i in items)]
    preds = [m.slots[0] for m in (tl.fn for tl in binding_grammar(inputs, maps=False, **BASE)) if m.role == "F"]
    orders = [POS_ASC, POS_DESC] + [Order(p, d) for p in num_paths if p != "." for d in (False, True)] + \
        ([Order(".", False), Order(".", True)] if "." in num_paths else [])
    cps = {"all": [None], "head": list(ks), "tail": list(ks), "first_occ": paths, "pred": preds}[c]
    tps = [None] if t == "id" else [p for p in paths if p != "."]
    out = [Comp(o, c, cp, t, tp) for o in orders for cp in cps for tp in tps]
    return [x for x in out if not base_equivalent_inst(x, present)]


def base_equivalent(schema, present_roles):
    return False                     # schema-level redundancy is decided per instantiation now


_CLASS = {}


def schema_class(schema):
    """Structural class of a schema, verified on the declared universes for every binding (cached)."""
    if schema in _CLASS:
        return _CLASS[schema]
    held = {"submultiset": True, "permutation": True}
    n = 0
    for _, (U, _) in universes().items():
        items = [it for v in U for it in v]
        for mech in instantiate(schema, [items]):
            for v in U[:150]:
                n += 1
                try:
                    out = mech(v)
                except Exception:
                    continue
                for c in held:
                    if held[c] and not _class_holds(c, v, out, None):
                        held[c] = False
    cls = "permutation" if held["permutation"] else "submultiset" if held["submultiset"] else "none"
    _CLASS[schema] = (cls, n)
    return _CLASS[schema]


# --------------------------------------------------------------------------- library (base + admitted schemas)
class Library:
    def __init__(self, deleted=()):
        self.deleted = set(deleted)
        self.schemas = {}            # schema -> record
        self.log = []

    @property
    def base_roles(self):
        return [r for r in PRIMITIVES if r not in self.deleted]

    def tools(self, inputs, grammar=BASE, with_schemas=True, provenance_holds=False):
        out = [t for t in binding_grammar(inputs, maps=False, **grammar)
               if t.fn.role in self.base_roles]
        if with_schemas:
            for s in sorted(self.schemas):
                if provenance_holds and s[2] == "proj":
                    # contract index (sound): every public output is a sub-multiset of its input, and a projecting
                    # schema returns field values, never input items, so it cannot occur in any fitting chain
                    continue
                out += [Tool(c.name(), c, c.name(), kind="primitive", parts=(c.role,))
                        for c in instantiate(s, inputs, present=self.base_roles)]
        return out

    def admit(self, schema, *, discovery_cost, where):
        if schema in self.schemas:
            self.schemas[schema]["uses"] += 1
            return False
        cls, n = schema_class(schema)
        self.schemas[schema] = dict(cls=cls, uses=1, discovery_cost=discovery_cost, class_check=n, where=where,
                                    reuse_tasks=0, saving=0.0)
        return True


# --------------------------------------------------------------------------- certification + probing
def certify(public, query, tools, depth, m):
    s = Searcher(tuple(public), query, tools, popper=True, m=meter(CERT_BUDGET), partial_depth=0, max_depth=depth)
    res = s.run_to(depth)
    res.searcher = s
    m.charge("certify_work_units", res.work)
    return res


def provenance_barrier(public, lib, m):
    """Proved Delta-M: every library mechanism has a verified sub-multiset/permutation class, so any
    composition returns a sub-multiset of its input; an output that is not one cannot be produced."""
    classes = [schema_class(ROLE_SCHEMA["F"])[0]] if "F" in lib.base_roles else []
    classes += [schema_class(ROLE_SCHEMA["S_by"])[0]] if "S" in lib.base_roles else []
    classes += [schema_class(ROLE_SCHEMA["Sort"])[0]] if "Sort" in lib.base_roles else []
    classes += [v["cls"] for v in lib.schemas.values()]
    if any(c == "none" for c in classes):
        return False
    for x, y in public:
        m.charge("router_work_units", 1)
        if not isinstance(y, list) or not isinstance(x, list):
            return True
        a, b = p_provenance(x), p_provenance(y)
        if any(a[k] < c for k, c in b.items()):
            return True
    return False


def class_filter(schemas, public, m):
    prov = not provenance_barrier(public, Library(deleted=PRIMITIVES), m)
    if prov:
        return [s for s in schemas if s[2] != "proj"]
    return [s for s in schemas if schema_class(s)[0] == "none"]


def _fits(chain, public, m):
    try:
        for x, y in public:
            m.charge("synthesis_work_units", len(chain))
            if vkey(run(chain, x)) != vkey(y):
                return False
        return True
    except Exception:
        return False


def synthesize(public, query, lib, m):
    inputs = [x for x, _ in public] + [query]
    present = set(lib.base_roles)
    cands = [s for s in all_schemas() if s not in lib.schemas]
    cands = class_filter(cands, public, m)
    base = [t.fn for t in lib.tools(inputs, with_schemas=True)]
    found = []
    for s in sorted(cands):
        hit = []
        for c in instantiate(s, inputs, present=present):
            if _fits((c,), public, m) or any(_fits((b, c), public, m) or _fits((c, b), public, m) for b in base):
                hit.append(c)
        if hit:
            found.append((s, hit))
    return found


def _tool(c):
    return Tool(c.name(), c, c.name(), kind="primitive", parts=(c.role,))


def tiered_certify(public, query, tiers, m):
    """Certify each fitting tier (tool set, depth); UNIQUE only if every fitting tier agrees on the query."""
    results, answers = {}, set()
    for name, (tools, depth) in tiers.items():
        r = certify(public, query, tools, depth, m)
        if r.status == NONE_FOUND:
            continue
        results[name] = r
        answers |= {vkey(h[1]) for h in r.hypotheses}
        if r.status not in (UNIQUE, AMBIGUOUS):
            answers.add(("__unknown__", name))
    return results, answers


def solve(public, queries, oracle, lib, *, world_like, seed=0, label="", extra_tools=()):
    """Router + synthesizer over one task (possibly several queries). Only public pairs, queries and charged
    oracle calls reach NEXUS. Base tier first (Occam). If the base tier fails, the router's diagnosis is the
    first repair tier that fits (library, dB, dC, else dM), but the ANSWER is certified over the union of every
    repair tier: UNIQUE only if all fitting tiers agree; otherwise probe across them, or stay AMBIGUOUS."""
    m = meter(10**12)
    public = list(public)
    rng = random.Random(f"w26-p4:{seed}:{label}")
    inputs = [x for x, _ in public] + list(queries)
    q0 = queries[0]
    route, invented, admitted, used_library, syn_cost = "base", [], [], False, 0
    try:
        extra = list(extra_tools)          # e.g. opaque stdlib tools (unproved class: disables the barrier)
        base_tools = lib.tools(inputs, with_schemas=False) + extra
        r0 = certify(public, q0, base_tools, 2, m)
        if r0.status != NONE_FOUND:
            tiers = {"base": (base_tools, 2)}
        else:
            prov = not provenance_barrier(public, Library(deleted=PRIMITIVES), m)
            lib_tools = lib.tools(inputs, with_schemas=True, provenance_holds=prov) + extra
            ext_tools = lib.tools(inputs, grammar=EXTENDED, with_schemas=True, provenance_holds=prov) + extra
            barrier = provenance_barrier(public, lib, m) and not extra
            tiers = {}
            if not barrier:
                # dC = recombination of BASE mechanisms (depth 3, base tools only); library schemas enter at
                # depth <= 2 in the library / dB / dM tiers, so library growth never inflates the depth-3 search
                tiers = {"library": (lib_tools, 2), "dB": (ext_tools, 2), "dC": (base_tools, 3)}
            w0 = m.total
            found = synthesize(public, q0, lib, m)
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
                    work_by=dict(m.counts), probes=0, invented=[], admitted=[], used_library=used_library)
    answers, statuses, probes = [], [], 0
    for q in queries:
        try:
            results, ans = tiered_certify(public, q, tiers, m)
            while not (len(ans) == 1 and results and all(r.status == UNIQUE for r in results.values())):
                if probes >= PROBE_BUDGET * len(queries) or oracle is None or not results:
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
                probes += 1
                m.charge("oracle_work_units", C_ORACLE)
                try:
                    y = oracle(x)
                except Exception:
                    break
                public.append((x, y))
                results, ans = tiered_certify(public, q, tiers, m)
        except WorkExhausted:
            answers.append(None)
            statuses.append("EXHAUSTED")
            continue
        ok = len(ans) == 1 and results and all(r.status == UNIQUE for r in results.values())
        statuses.append(UNIQUE if ok else (AMBIGUOUS if results else NONE_FOUND))
        win = next(iter(results.values())) if ok else None
        answers.append(win.answer if ok else None)
        if ok and route == "dM" and "dM" in results:
            used = {t.fn.schema for t in results["dM"].hypotheses[0][2] if isinstance(t.fn, Comp)}
            for sc in sorted(used):
                if lib.admit(sc, discovery_cost=syn_cost, where=label):
                    admitted.append(sc)
                    m.charge("class_verification_work_units", lib.schemas[sc]["class_check"])
        if ok and route == "library" and "library" in results:
            for t in results["library"].hypotheses[0][2]:
                if isinstance(t.fn, Comp) and t.fn.schema in lib.schemas:
                    lib.schemas[t.fn.schema]["reuse_tasks"] += 1
    return dict(route=route, answers=answers, statuses=statuses, work=m.total, work_by=dict(m.counts), probes=probes,
                invented=[list(s) for s in invented], admitted=[list(s) for s in admitted], used_library=used_library)


# --------------------------------------------------------------------------- synthetic fault generator (scoring labels)
HIDDEN = (("ord", "all", "id"), ("ord", "tail", "id"), ("ord", "first_occ", "id"), ("ord", "pred", "id"),
          ("ord", "all", "proj"))


def worlds(seed):
    return [("ints", ints_world(seed)), ("records", records_world_f(seed, 5))]


def _base_fits(public, query, lib, grammar, depth):
    inputs = [x for x, _ in public] + [query]
    r = Searcher(tuple(public), query, lib.tools(inputs, grammar=grammar, with_schemas=False), popper=True,
                 m=meter(10**8), partial_depth=0, max_depth=depth).run_to(depth)
    return r


def make_fault_task(world, rng, kind, *, deleted=(), hidden_choice=None):
    """kind in {dB, dC, dM, del:<primitive>}; label is returned for scoring only."""
    lib = Library(deleted=deleted)
    for _ in range(400):
        xs = [world["sample"](rng) for _ in range(5)]
        if kind == "dB":
            ext = [t.fn for t in lib.tools(xs, grammar=EXTENDED, with_schemas=False)]
            basek = {t.fn.name() for t in lib.tools(xs, with_schemas=False)}
            novel = [m for m in ext if m.name() not in basek]
            if not novel:
                continue
            chain = (rng.choice(novel),) if rng.random() < 0.5 else (rng.choice(novel), rng.choice(ext))
        elif kind == "dC":
            b = [t.fn for t in lib.tools(xs, with_schemas=False)]
            chain = tuple(rng.choice(b) for _ in range(3))
        elif kind == "dM":
            s = hidden_choice or rng.choice(HIDDEN)
            inst = instantiate(s, xs, present=lib.base_roles)
            if not inst:
                continue
            b = [t.fn for t in lib.tools(xs, with_schemas=False)]
            h = rng.choice(inst)
            chain = (h,) if rng.random() < 0.5 or s[2] == "proj" else (rng.choice(b), h)
        else:
            prim = kind.split(":")[1]
            full = [t.fn for t in Library().tools(xs, with_schemas=False)]
            pm = [m for m in full if m.role == prim]
            rest = [m for m in full if m.role != prim]
            if not pm:
                continue
            chain = (rng.choice(pm),) if rng.random() < 0.5 else (rng.choice(rest), rng.choice(pm))
        try:
            ys = [run(chain, x) for x in xs]
        except Exception:
            continue
        if len({vkey(y) for y in ys[:4]}) < 3 or any(vkey(x) == vkey(y) for x, y in zip(xs, ys)):
            continue
        public = tuple(zip(xs[:4], ys[:4]))
        if _base_fits(public, xs[4], lib, BASE, 2).status != NONE_FOUND:
            continue                              # must be a genuine base-tier failure
        if kind == "dB" and _base_fits(public, xs[4], lib, EXTENDED, 2).status == NONE_FOUND:
            continue
        if kind == "dC":
            if _base_fits(public, xs[4], lib, EXTENDED, 2).status != NONE_FOUND:
                continue
            r3 = _base_fits(public, xs[4], lib, BASE, 3)
            if vkey(ys[4]) not in {vkey(h[1]) for h in r3.hypotheses}:
                continue
        if (kind == "dM" or kind.startswith("del:")) and (
                _base_fits(public, xs[4], lib, EXTENDED, 2).status != NONE_FOUND or
                _base_fits(public, xs[4], lib, BASE, 3).status != NONE_FOUND):
            continue                              # pure Delta-M: rebinding and recombination provably fail
        return dict(public=public, query=xs[4], answer=ys[4], teacher=chain, kind=kind)
    return None


def expected_route(kind):
    return "dM" if kind.startswith("del:") or kind == "dM" else kind


def long_world(w):
    """Deletion-stream variant: 6-7 items, so S[k <= 5, o] cannot stand in for a deleted Sort."""
    base = w["sample"]
    return dict(w, name=w["name"] + "_long", sample=lambda r, n=None: base(r, n or r.randint(6, 7)))


def run_dev_or_confirm(seed, *, n_per_kind=3, n_del=4):
    out = dict(seed=seed, mixed=[], deletion=[])
    for wname, w in worlds(seed):
        rng = random.Random(f"w26-p4-mixed:{seed}:{wname}")
        for kind in ("dB", "dC", "dM"):
            for i in range(n_per_kind):
                t = make_fault_task(w, rng, kind)
                if t is None:
                    out["mixed"].append(dict(world=wname, kind=kind, generated=False))
                    continue
                r = solve(list(t["public"]), [t["query"]], lambda x, c=t["teacher"]: run(c, x), Library(),
                          world_like=w, seed=seed, label=f"{wname}:{kind}:{i}")
                out["mixed"].append(_row(t, r, wname, kind, i))
    for prim in PRIMITIVES:
        for wname, w in worlds(seed):
            lw = long_world(w)
            rng = random.Random(f"w26-p4-del:{seed}:{prim}:{wname}")
            lib = Library(deleted=[prim])
            for i in range(n_del):
                t = make_fault_task(lw, rng, f"del:{prim}", deleted=[prim])
                if t is None:
                    out["deletion"].append(dict(world=wname, kind=f"del:{prim}", generated=False, encounter=i))
                    continue
                r = solve(list(t["public"]), [t["query"]], lambda x, c=t["teacher"]: run(c, x), lib,
                          world_like=lw, seed=seed, label=f"{wname}:{prim}:{i}")
                row = _row(t, r, wname, f"del:{prim}", i)
                row["encounter"] = i
                out["deletion"].append(row)
            out.setdefault("libraries", {})[f"{prim}/{wname}"] = {"/".join(k): v for k, v in lib.schemas.items()}
    return out


def _row(t, r, wname, kind, i):
    a = r["answers"][0]
    return dict(world=wname, kind=kind, generated=True, task=i, route=r["route"], expected=expected_route(kind),
                status=r["statuses"][0], solved=a is not None and vkey(a) == vkey(t["answer"]),
                false_certificate=a is not None and vkey(a) != vkey(t["answer"]), work=r["work"],
                work_by=r["work_by"], probes=r["probes"], invented=r["invented"], admitted=r["admitted"],
                used_library=r["used_library"])
