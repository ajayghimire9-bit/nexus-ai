"""Wave 41 hierarchy (SOLVER SIDE; NOT LOCKED): micro-specialists, the shared workspace record, routing, compiled skills, and
the certificate-tier law. Reuses w38_learn.akey (abstract tool keys), w41_lemmas (summaries) and the Wave 31 Middle-IR type
vocabulary (Sequence / Counter / ObjectSet / RelationGraph, plus Text / Int / Bool / Record) for workspace type tags. The v5
language is unchanged; specialists are a PARTITION of each task's declared v5 scope (every tool belongs to exactly one), so the
union of all specialist decompositions of total primitive depth <= D is exactly the flat depth-D scope (matched depth/scope).

Level 3 root controller: routing (which specialists to try first, per task signature), skill dispatch, budget (same per-task
cap as Flat), distinguishing queries (k), certificate tiers. Level 2: 12 micro-specialists. Level 1: compiled skills = abstract
multi-step templates (akey sequences of certified programs) + a composed assume-guarantee summary (union of stage intros;
stage i's output type class must be accepted by stage i+1), excluded in O(1) when a public example needs a character none of
the stages can introduce.

CERTIFICATE LAW (tests/test_hierarchical_soundness.py): GLOBAL_SCOPE_UNIQUE is emitted only from Checker v5's own SCOPE_UNIQUE
verdict on the ORIGINAL declared v5 scope with clean D1/D2 flags. A verdict on a specialist slice is LOCAL_SLICE_UNIQUE_ONLY.
Any disagreeing in-scope witness (from any specialist) -> AMBIGUOUS. Solver-side summaries can exclude work but never upgrade a
label."""
from __future__ import annotations

import hashlib
import json
import math
import random

from nexus import w38_learn as K
from nexus import w39_lang as L
from nexus import w41_lemmas as M

SPECS = ("span", "tokenize", "slice_pad", "numeric", "format", "list_map", "list_order", "aggregate", "table", "grid", "graph",
         "fallback")

_SPAN, _SLICE, _NUM, _FMT = {"bef", "aft"}, {"at", "sl", "pad", "cap"}, {"dsh", "drnd", "int", "add", "sub", "mul", "mod", "max",
                                                                         "min", "len", "even"}, {"cat", "low", "up", "shape",
                                                                                                 "fst", "lst", "str"}


def _head(e):
    """The specialist-relevant head of a lambda: the outermost op below cat/if wrappers is not enough; we take the set of ops."""
    ops = set()

    def walk(x):
        if isinstance(x, list) and x and isinstance(x[0], str):
            ops.add(x[0])
            for y in x[1:]:
                walk(y)
    walk(e)
    return ops


def spec_of(t):
    op = t["op"]
    if op in ("fn", "map"):
        ops = _head(t["f"])
        if op == "fn":
            if ops & _SPAN:
                return "span"
            if ops & {"dsh", "drnd"} or (ops & _NUM and not ops & (_FMT | _SLICE)):
                return "numeric"
            if ops & _SLICE:
                return "slice_pad"
            return "format"
        return "numeric" if ops & _NUM and not ops & (_FMT | _SPAN | _SLICE) else "list_map"
    if op in ("split", "toks", "chars", "words", "strip"):
        return "tokenize"
    if op in ("take", "drop"):
        return "slice_pad"
    if op in ("filter", "enum", "pairs", "flat"):
        return "list_map"
    if op in ("sortby", "rev", "uniq", "scan"):
        return "list_order"
    if op in ("groupby", "countby", "fold", "best", "len", "join"):
        return "aggregate"
    if op in ("get", "proj", "fill", "tjoin"):
        return "table"
    if op in ("objs", "paint", "recolor_if"):
        return "grid"
    if op in ("reach", "topo", "indeg", "outdeg"):
        return "graph"
    return "fallback"                          # first, dflt and anything else (total partition)


# --------------------------------------------------------------------------- workspace (Middle-IR typed records)
def ir_type(v):
    if isinstance(v, str):
        return "Text"
    if isinstance(v, bool):
        return "Bool"
    if isinstance(v, int):
        return "Int"
    if isinstance(v, dict):
        return "RelationGraph" if set(v) == {"nodes", "edges"} else "Record"
    if isinstance(v, list):
        if v and all(isinstance(r, list) and r and all(type(c) is int for c in r) for r in v):
            return "Grid"
        if v and all(isinstance(e, dict) and {"key", "count"} <= set(e) for e in v):
            return "Counter"
        if v and all(isinstance(e, dict) and {"color", "cells"} <= set(e) for e in v):
            return "ObjectSet"
        return "Sequence"
    return "None"


def record(result, alternatives, assumptions, declared_scope, proof_summary_evidence, actual_cost):
    """The universal specialist / skill return contract. A compact reference (token) points to the record; it never replaces
    the alternatives, assumptions or scope boundary."""
    r = dict(result=result, alternatives=list(alternatives), assumptions=dict(assumptions), declared_scope=dict(declared_scope),
             proof_summary_evidence=dict(proof_summary_evidence), actual_cost=dict(actual_cost))
    r["token"] = hashlib.sha256(json.dumps(r, sort_keys=True, default=repr).encode()).hexdigest()[:16]
    return r


def scope_ref(tools, depth):
    return dict(sha256=hashlib.sha256(json.dumps([tools, depth], sort_keys=True).encode()).hexdigest(), n_tools=len(tools),
                max_depth=depth, partition={s: sum(spec_of(t) == s for t in tools) for s in SPECS})


# --------------------------------------------------------------------------- certificate law
def global_label(kernel_full=None, flags_clean=True, slice_verdict=None, witness_found=False):
    """kernel_full: Checker v5 verdict on the ORIGINAL declared scope (or None if not run); slice_verdict: Checker v5 verdict on a
    specialist slice (or None). Only kernel_full can yield GLOBAL_SCOPE_UNIQUE."""
    if witness_found:
        return "AMBIGUOUS"
    if kernel_full is not None:
        lab = kernel_full["label"]
        if lab == "SCOPE_UNIQUE" and flags_clean:
            return "GLOBAL_SCOPE_UNIQUE"
        return "AMBIGUOUS" if lab == "AMBIGUOUS" else "ABSTAIN"
    if slice_verdict is not None and slice_verdict["label"] == "SCOPE_UNIQUE":
        return "LOCAL_SLICE_UNIQUE_ONLY"
    if slice_verdict is not None and slice_verdict["label"] == "AMBIGUOUS":
        return "AMBIGUOUS"
    return "ABSTAIN"


# --------------------------------------------------------------------------- routing
def signature(public):
    xs, ys = [x for x, _ in public], [y for _, y in public]
    newc = any(M.chars_of(y) - M.chars_of(x) - M.NUM for x, y in public)
    return f"{ir_type(xs[0])}>{ir_type(ys[0])}>{'new' if newc else 'sub'}"


FIXED_ROUTES = {                                  # human-written routing (Arm B): preferred specialists per signature class
    "Text>Text>sub": ("span", "tokenize", "slice_pad", "format", "list_map", "aggregate"),
    "Text>Text>new": ("format", "span", "tokenize", "slice_pad", "numeric", "aggregate"),
    "Text>Sequence": ("tokenize", "span", "list_map", "list_order", "slice_pad"),
    "Text>Int": ("tokenize", "numeric", "aggregate", "list_map"),
    "Sequence": ("list_map", "list_order", "aggregate", "table", "slice_pad"),
    "Record": ("table", "aggregate", "list_map"),
    "grid": ("grid", "list_map", "aggregate", "list_order"),
    "graph": ("graph", "list_map", "aggregate", "list_order"),
}


def fixed_routing(sig):
    a, b, c = sig.split(">")
    if a == "Grid":
        key = "grid"
    elif a == "RelationGraph":
        key = "graph"
    elif a == "Record":
        key = "Record"
    elif a == "Sequence":
        key = "Sequence"
    elif f"{a}>{b}>{c}" in FIXED_ROUTES:
        key = f"{a}>{b}>{c}"
    elif f"{a}>{b}" in FIXED_ROUTES:
        key = f"{a}>{b}"
    else:
        key = "Sequence"
    pref = FIXED_ROUTES[key]
    return {"kind": "routing", "first": {s: (0.0 if s in pref else 2.0) for s in SPECS},
            "trans": {}, "w": 1.0}


def fit_routing(programs, sigs, alpha=1.0):
    """Learned routing (Arms C/D): specialist presence per signature + specialist bigrams, from certified programs."""
    pres, trans = {}, {}
    for p, sg in zip(programs, sigs):
        ss = [spec_of(t) for t in p]
        for s in set(ss):
            pres.setdefault(sg, {}); pres[sg][s] = pres[sg].get(s, 0) + 1
        for a, b in zip(["<S>"] + ss, ss):
            trans.setdefault(a, {}); trans[a][b] = trans[a].get(b, 0) + 1
    return {"kind": "routing_learned", "pres": pres, "trans": trans, "alpha": alpha, "n": len(programs)}


def placebo_routing(r, seed):
    perm = list(SPECS)
    random.Random(f"w41-placebo-route:{seed}").shuffle(perm)
    m = dict(zip(SPECS, perm)); m["<S>"] = "<S>"
    if r["kind"] == "routing":
        return dict(r, first={m[s]: v for s, v in r["first"].items()})
    return dict(r, pres={g: {m[s]: c for s, c in d.items()} for g, d in r["pres"].items()},
                trans={m[a]: {m[b]: c for b, c in d.items()} for a, d in r["trans"].items()}, placebo=True)


def route_costs(r, sig):
    """(first-step cost per specialist, transition cost (prev specialist -> specialist))."""
    if r is None:
        return {s: 0.0 for s in SPECS}, lambda a, b: 0.0
    if r["kind"] == "routing":
        return r["first"], lambda a, b: 0.0
    a = r["alpha"]
    pres = r["pres"].get(sig, {})
    n = sum(pres.values())
    first = {s: -math.log((pres.get(s, 0) + a) / (n + a * len(SPECS))) + math.log(1.0 / len(SPECS)) for s in SPECS}

    def tr(p, s):
        row = r["trans"].get(p, {})
        m = sum(row.values())
        return -math.log((row.get(s, 0) + a) / (m + a * len(SPECS))) + math.log(1.0 / len(SPECS))
    return first, tr


def routed_cost_matrix(base, tools, routing, sig, w=1.0):
    """Tool cost = base (Flat's Fixed+Repr-v5 cost) + w * specialist routing cost. Same tools, same depth: order only."""
    first, tr = route_costs(routing, sig)
    sp = [spec_of(t) for t in tools]
    act = [first[s] for s in sp]
    bc = base["cost"]

    def row(r):
        b = bc[r]
        if r == 0:
            return [b[j] + w * (act[j] + tr("<S>", sp[j])) for j in range(len(tools))]
        p = sp[r - 1]
        return [b[j] + w * (0.5 * act[j] + tr(p, sp[j])) for j in range(len(tools))]
    return {"cost": K.Lazy(len(tools) + 1, row)}


def decomposition_exclusion(public, tools, depth):
    """Proof-summary evidence: how many specialist decompositions (sequences of length <= depth over the specialists present)
    are excluded in O(1) by their composed summary (some public example needs a character no stage can introduce)."""
    lem = M.TaskLemmas(public, tools)
    need = lem.need([x for x, _ in public])
    by = {}
    for t, it in zip(tools, lem.intro):
        s = spec_of(t)
        by[s] = by.get(s, M.EMPTY) | it
    present = sorted(by)
    total = excl = 0
    seqs = [()]
    for _ in range(depth):
        seqs = [q + (s,) for q in seqs for s in present]
        for q in seqs:
            total += 1
            u = M.EMPTY
            for s in q:
                u = u | by[s]
            excl += not all(u.covers(nd) for nd in need)
    return dict(decompositions=total, excluded=excl)


# --------------------------------------------------------------------------- compiled skills (Arm D)
class Library:
    """Compiled skills = akey templates of certified programs seen >= `min_seen` times, each with a composed summary.
    Rent: every attempt costs its executions; income when the skill produced the final candidate = the search executions the
    last search-solved task with the same template needed (else the running median of search executions), minus the attempt.
    A skill with negative net after >= `grace` attempts is retired. Versions are adopted only through the shadow vault
    (deterministic execution counts; see adopt())."""

    def __init__(self, min_seen=2, grace=4, max_try=8, max_inst=64, permute=None):
        self.min_seen, self.grace, self.max_try, self.max_inst = min_seen, grace, max_try, max_inst
        self.seen, self.skills, self.version, self.search_execs, self.by_tpl_execs = {}, {}, 0, [], {}
        self.permute = permute                     # placebo: a fixed permutation of akeys (seeded)
        self.log = []

    def template(self, prog):
        return tuple(K.akey(t) for t in prog)

    def observe(self, prog, search_execs=None):
        """A certified program. Returns the template if it becomes a PROPOSED skill (adoption is separate)."""
        tp = self.template(prog)
        self.seen[tp] = self.seen.get(tp, 0) + 1
        if search_execs is not None:
            self.search_execs.append(search_execs)
            self.by_tpl_execs[tp] = search_execs
        if self.seen[tp] >= self.min_seen and tp not in self.skills:
            return tp
        return None

    def _tpl_run(self, tp):
        if self.permute is None:
            return tp
        return tuple(self.permute.get(a, a) for a in tp)

    def add(self, tp):
        self.skills[tp] = dict(attempts=0, rent=0, income=0, wins=0, active=True, created=self.version)
        self.version += 1

    def instantiate(self, public, query, tools, lem, meter):
        """Try active skills (most wins first). Returns (chain or None, template, executions spent)."""
        ix = {}
        for i, t in enumerate(tools):
            ix.setdefault(K.akey(t), []).append(i)
        need = lem.need([x for x, _ in public]) if lem is not None else []
        xs = [x for x, _ in public] + [query]
        targets = [L.key(y) for _, y in public]
        live = [tp for tp, s in self.skills.items() if s["active"] and all(a in ix for a in self._tpl_run(tp))]
        meter["skill_excluded_scope"] = meter.get("skill_excluded_scope", 0) + sum(1 for s in self.skills.values() if s["active"]) - len(live)
        order = sorted(live, key=lambda tp: (-self.skills[tp]["wins"], -self.seen.get(tp, 0), tp))[: self.max_try]
        spent_total = 0
        for tp in order:
            run = self._tpl_run(tp)
            slots = [ix.get(a, []) for a in run]
            st = self.skills[tp]
            st["attempts"] += 1
            if not all(slots):
                meter["skill_excluded_scope"] = meter.get("skill_excluded_scope", 0) + 1
                continue
            if lem is not None:                  # composed assume-guarantee summary: O(1) exclusion
                u = M.EMPTY
                for sl in slots:
                    for i in sl:
                        u = u | lem.intro[i]
                if not all(u.covers(nd) for nd in need):
                    meter["skill_excluded_summary"] = meter.get("skill_excluded_summary", 0) + 1
                    continue
            spent = 0
            combos = [[]]
            for sl in slots:
                combos = [c + [i] for c in combos for i in sl][: self.max_inst]
            for c in combos:
                chain = [tools[i] for i in c]
                spent += 1
                ok = True
                for x, tg in zip(xs, targets + [None]):
                    o = L.run(chain, x)
                    if o == L.ERROR or (tg is not None and L.key(o) != tg):
                        ok = False
                        break
                if ok:
                    st["rent"] += spent
                    spent_total += spent
                    return chain, tp, spent_total
            st["rent"] += spent
            spent_total += spent
        return None, None, spent_total

    def credit(self, tp, attempt_execs):
        st = self.skills[tp]
        st["wins"] += 1
        ref = self.by_tpl_execs.get(tp)
        if ref is None and self.search_execs:
            s = sorted(self.search_execs)
            ref = s[len(s) // 2]
        st["income"] += max(0, (ref or 0) - attempt_execs)

    def retire(self):
        out = []
        for tp, st in self.skills.items():
            if st["active"] and st["attempts"] >= self.grace and st["income"] - st["rent"] < 0:
                st["active"] = False
                out.append(tp)
        if out:
            self.log.append(dict(event="retire", n=len(out), version=self.version))
        return out

    def adopt(self, tp, vault, scope_fn, lem_fn):
        """Shadow-vault rule: a proposed skill is adopted only if complete-task work on the vault (recently certified tasks,
        each with its recorded search executions) does not get worse: with the skill, a vault task costs the skill attempt
        (if the skill solves it) or recorded + attempt executions (if it does not). Deterministic execution counts."""
        self.add(tp)
        cur = new = 0
        for v in vault:
            tools = scope_fn(v)
            m = {}
            only = {tp: self.skills[tp]}
            keep, self.skills = self.skills, only
            ch, _, spent = self.instantiate(v["public"], v["query"], tools, lem_fn(v, tools), m)
            self.skills = keep
            cur += v["execs"]
            new += spent if ch is not None else v["execs"] + spent
        st = self.skills[tp]
        st["attempts"], st["rent"] = 0, 0                    # vault trials are charged by the caller, not as rent
        ok = new <= cur
        if not ok:
            del self.skills[tp]
            self.version -= 1
        self.log.append(dict(event="adopt" if ok else "rollback", vault=len(vault), cur=cur, new=new, version=self.version))
        return ok

    def size(self):
        return sum(1 for s in self.skills.values() if s["active"])

    def to_json(self):
        return dict(seen=[[list(k), v] for k, v in self.seen.items()],
                    skills=[[list(k), v] for k, v in self.skills.items()], version=self.version,
                    search_execs=self.search_execs, by_tpl=[[list(k), v] for k, v in self.by_tpl_execs.items()],
                    permute=self.permute, log=self.log, cfg=[self.min_seen, self.grace, self.max_try, self.max_inst])

    @classmethod
    def from_json(cls, d):
        lib = cls(*d["cfg"], permute=d["permute"])
        lib.seen = {tuple(k): v for k, v in d["seen"]}
        lib.skills = {tuple(k): v for k, v in d["skills"]}
        lib.version, lib.search_execs, lib.log = d["version"], d["search_execs"], d["log"]
        lib.by_tpl_execs = {tuple(k): v for k, v in d["by_tpl"]}
        return lib


def placebo_permutation(akeys, seed):
    ks = sorted(set(akeys))
    p = ks[:]
    random.Random(f"w41-placebo-skill:{seed}").shuffle(p)
    return dict(zip(ks, p))
