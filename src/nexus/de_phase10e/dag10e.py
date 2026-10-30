"""Phase 10E investigation layer (NOT LOCKED): dag10d with the Stage 1 replay-reachability and verifier fixes. Every change is
SHARED by every arm, by training, dreams and admission (none is a learned component):

1  DISCRIMINATIVE SCHEMA ROLES (Dom10e.roles; general, name-agnostic, from visible information only)
     ckey     the column carries a `unique` test for this relation in models/schema.yml (the documented grain)
     arrival  an int column that strictly increases with landing (row) order inside EVERY duplicate group of one of the
              relation's ckey columns (re-delivered versions arrive later: an ingest / replay sequence)
   Phase 10D roles (int / text / lowcard / unique / dupes / json / padded / nulls) could not tell the replay key and sequence
   from 19-131 int distractors (scripts/agi10e_diag_replay.py: median 29 role-identical twins per task).
2  TWO-STEP DEDUP: a relation WITHOUT a dedup is no longer offered the one-shot 3-parameter set_dedup. Instead
     add_partition(rel, key)   QUALIFY ROW_NUMBER() OVER (PARTITION BY key) = 1 (no ordering yet: the order expression is the
                               key itself, so every duplicate group is a tie)
   followed by the existing set_dedup, whose MINIMAL-CHANGE order (amendment 1 of Phase 10D) puts the one-field ORDER BY changes
   first. A replay repair is therefore the 2-step path add_partition -> set_dedup (partition by the entity key, then order by the
   replay sequence), which Sleep can abstract into one atomic macro.
3  ACCEPTANCE RULES (Inv10e.run; a candidate failing either is never `ok`, so it is never submitted):
     deterministic_dedup   on every visible batch, no dedup partition may have >= 2 DIFFERENT rows tied at the top of its
                           ORDER BY (ROW_NUMBER over ties is engine-dependent: DuckDB / SQLite / Polars / Spark may disagree)
     latest_state_witness  the SHADOW-SEQUENCE WITNESS (the Target 96088 request): for every filter evaluated BEFORE a
                           latest-per-key dedup, a boundary key with two versions (r_old, r_new) is synthesised from the
                           relation's visible values such that r_new is the latest and FAILS the predicate while r_old
                           SATISFIES it; if filter-then-dedup and dedup-then-filter disagree on it (r_old resurrected as the
                           key's state), the placement is rejected. A predicate that commutes with the dedup (e.g. one on the
                           key itself) passes.
   Both rules are checks on the spec and the visible rows; they run no candidate and are not charged as executions (disclosed).
   A violation only blocks acceptance (ok = False, a failed check + a `fail:` symptom); the graded score is unchanged, so a
   partition step that makes a unique contract pass still counts as partial progress.
Everything else (operators, evidence, scoring, hidden verification) is dag10d unchanged."""
from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import yaml

from nexus.de_phase6 import skills6 as SK
from nexus.de_phase10d import dag10d as D10, ir10d as IR, world10d as W
from nexus.de_phase10d.dag10d import NODES, verify_hidden, sig, rel_role, _proj_rows, _with   # noqa: F401  (re-exported)

OPS = ("set_dedup", "add_partition") + D10.OPS[1:]
OP_NODE = dict(D10.OP_NODE, add_partition=0)


class Dom10e(D10.Dom):
    def __init__(self, k, rels, spec_k, ukeys):
        super().__init__(k, rels, spec_k)
        self.ukeys = ukeys
        self._arr = {}

    def roles(self, rel, col):
        base = super().roles(rel, col)
        extra = set()
        if (rel, col) in self.ukeys:
            extra.add("ckey")
        if self.k == 0 and "int" in base and col in self.arrival_cols(rel):
            extra.add("arrival")
        return tuple(sorted(set(base) | extra))

    def arrival_cols(self, rel):
        if rel not in self._arr:
            rows = self.rels.get(rel, [])
            out = set()
            for kc in [c for r, c in self.ukeys if r == rel]:
                groups = {}
                for i, r in enumerate(rows):
                    if r.get(kc) not in (None, ""):
                        groups.setdefault(str(r.get(kc)), []).append(r)
                dup = [g for g in groups.values() if len(g) > 1]
                if not dup:
                    continue
                for c in (rows[0] if rows else {}):
                    if c == kc:
                        continue
                    ok = True
                    for g in dup:
                        v = [IR.ev(["try_int", ["col", c]], r) for r in g]
                        if any(x is None for x in v) or any(b <= a for a, b in zip(v, v[1:])):
                            ok = False
                            break
                    if ok:
                        out.add(c)
            self._arr[rel] = out
        return self._arr[rel]


def schema_unique(ws):
    """(model, column) pairs carrying a `unique` test in models/schema.yml (visible)."""
    p = Path(ws) / "models" / "schema.yml"
    if not p.exists():
        return set()
    out = set()
    for m in (yaml.safe_load(p.read_text()) or {}).get("models", []):
        for c in m.get("columns", []):
            if any(t == "unique" or (isinstance(t, dict) and "unique" in t) for t in c.get("tests", [])):
                out.add((m["name"], c["name"]))
    return out


# ------------------------------------------------------------------ acceptance rules (spec + visible rows; uncharged)
def dedup_ties(t, rows):
    """Partitions whose top-of-ORDER-BY is shared by >= 2 different projected rows (after the pre filters)."""
    d = t.get("dedup")
    if not d:
        return 0
    rows = [r for r in rows if all(IR.ev(c, r) is True for c in t.get("pre", []))]
    top = {}
    for r in rows:
        k, o = IR.ev(d["key"], r), IR.ev(d["order"], r)
        if o is None:
            continue
        cur = top.get(k)
        better = cur is None or (o > cur[0] if d.get("desc", True) else o < cur[0])
        if better:
            top[k] = (o, [r])
        elif o == cur[0]:
            cur[1].append(r)
    return sum(1 for o, rs in top.values() if len({json.dumps(r, sort_keys=True, default=str) for r in rs}) > 1)


def _walk(e):
    if isinstance(e, list):
        yield e
        for x in e[1:]:
            yield from _walk(x)


def _assign(cond, cols, pool, want):
    """A dict over the predicate's columns making `cond` evaluate True (want=True) or not True (want=False), searched over the
    relation's visible values plus NULL and a fresh sentinel."""
    cs = sorted(IR.cols_of(cond))
    lits = [str(n[1]) for n in _walk(cond) if n and n[0] == "lit"]
    vals = [pool.get(c, []) + lits + [None, "__w__"] for c in cs]
    for combo in itertools.islice(itertools.product(*vals), 400):
        r = dict(zip(cs, combo))
        try:
            hit = (IR.ev(cond, r) is True) == want
        except Exception:                                         # noqa: BLE001
            return None
        if hit:
            return r
    return None


def stale_witness(t, rows):
    """The shadow-sequence witness for every PRE-dedup predicate of relation spec t. Returns the predicates for which
    filter-before-dedup resurrects the older version (disagrees with dedup-then-filter) on a synthesised two-version key."""
    d = t.get("dedup")
    if not d or not t.get("pre"):
        return []
    names = [n for n, _ in t["cols"]]
    pool = {c: sorted({str(r.get(c)) for r in rows if r.get(c) not in (None, "")})[:6] for c in names}
    kcols, ocols = IR.cols_of(d["key"]), IR.cols_of(d["order"])
    if not rows:
        return []
    bad = []
    for cond in t["pre"]:
        if IR.cols_of(cond) & (kcols | ocols):
            continue                                           # a predicate on the key / order commutes or is not separable
        new_v, old_v = _assign(cond, names, pool, False), _assign(cond, names, pool, True)
        if new_v is None or old_v is None:
            continue
        base = dict(rows[0])
        r_old, r_new = dict(base, **old_v), dict(base, **new_v)
        oc = sorted(ocols)[0]
        lo, hi = ("1", "2") if d.get("desc", True) else ("2", "1")
        r_old[oc], r_new[oc] = lo, hi
        w = [r_old, r_new]
        ident = dict(src="__w", cols=[[n, ["col", n]] for n in names], dedup=d)
        pre_first = IR.run_stg(dict(ident, pre=[cond], post=[]), {"__w": w}, {})
        post_first = IR.run_stg(dict(ident, pre=[], post=[cond]), {"__w": w}, {})
        key = lambda rs: sorted(json.dumps(r, sort_keys=True, default=str) for r in rs)            # noqa: E731
        if key(pre_first) != key(post_first):
            bad.append(cond)
    return bad


class Inv10e(D10.Inv10d):
    def __init__(self, project, engine=None):
        super().__init__(project, engine)
        self.ukeys = schema_unique(project["ws"])
        self._proj = {}

    def proj(self, t, bid):
        key = (bid, t["src"], json.dumps(t["cols"]))
        if key not in self._proj:
            self._proj[key] = _proj_rows(t, self.batches[bid][0])
        return self._proj[key]

    def dom(self, k, specs):
        key = (k, json.dumps(specs[:k + 1], sort_keys=True, default=str))
        if key not in self._dom:
            if k == 0:
                rels = {name: _proj_rows(t, self.tables) for name, t in specs[0].items()}
            else:
                try:
                    R = IR.interpret(dict(stg=specs[0], int=specs[1], fct=specs[2]), self.tables, self.state)
                except Exception:                                   # noqa: BLE001
                    R = {}
                rels = {r: R.get(r, []) for r in (list(specs[0]) + [t["latest_as"] for t in specs[0].values() if t.get("latest_as")] + ["int_orders"])}
            self._dom[key] = Dom10e(k, rels, specs[k], self.ukeys)
        return self._dom[key]

    def rules(self, specs):
        """-> list of acceptance-rule violations of the stg node on the visible batches."""
        out = []
        for rel, t in sorted(specs[0].items()):
            if not t.get("dedup"):
                continue
            for bid in range(len(self.batches)):
                try:
                    rows = self.proj(t, bid)
                except Exception:                                   # noqa: BLE001
                    continue
                if dedup_ties(t, rows):
                    out.append(f"deterministic_dedup:{rel}")
                    break
            try:
                rows = self.proj(t, 0)
            except Exception:                                       # noqa: BLE001
                rows = []
            if stale_witness(t, rows):
                out.append(f"latest_state_witness:{rel}")
        return sorted(set(out))

    def run(self, specs, prescreen=True):
        ev = super().run(specs, prescreen)
        if ev.get("error"):
            return ev
        bad = self.rules(specs)
        if bad:
            ev = dict(ev, ok=False, failed=ev["failed"] + bad, features=set(ev["features"]) | {f"fail:{b.split(':')[0]}" for b in bad})
        return ev


Inv10d = Inv10e                                                  # lineage / search copies construct D.Inv10d


# ------------------------------------------------------------------ operators
def candidates(op, spec_k, dom):
    if OP_NODE[op] != dom.k:
        return []
    if op == "add_partition":
        out = []
        for rel in sorted(spec_k):
            t = spec_k[rel]
            if t.get("dedup"):
                continue
            for kc in [n for n, _ in t["cols"] if "int" in dom.roles(rel, n)]:
                x = ["try_int", ["col", kc]]
                out.append((_with(spec_k, rel, dedup=dict(key=x, order=x, desc=True)), f"{rel}|{kc}"))
        return out
    if op == "set_dedup":                                         # only on relations that already have a dedup (see 2)
        return [(s, prm) for s, prm in D10.candidates(op, spec_k, dom) if spec_k[prm.split("|")[0]].get("dedup")]
    return D10.candidates(op, spec_k, dom)


def abstract_edit(op, prm, dom, fine=True):
    if op == "add_partition":
        rel, kc = prm.split("|")
        return (op, ("rel", rel_role(dom, rel)), ("key", dom.roles(rel, kc)))
    return D10.abstract_edit(op, prm, dom, fine)


def bind(skill, inv, specs, k, cap=2):
    """dag10d.bind over the Phase 10E operators."""
    paths = [([], specs)]
    for e in skill["edits"]:
        e = SK._tup(e)
        if OP_NODE.get(e[0]) != k:
            return []
        nxt = []
        for path, sp in paths:
            dom = inv.dom(k, sp)
            for s2, prm in candidates(e[0], sp[k], dom):
                if SK._matches(e, abstract_edit(e[0], prm, dom)):
                    sp2 = list(sp)
                    sp2[k] = s2
                    nxt.append((path + [(k, e[0], prm)], sp2))
                    if len(nxt) >= cap:
                        break
        paths = nxt[:cap]
        if not paths:
            return []
    return [p for p, _ in paths]


def replay(inv, path, start=None):
    specs = [copy.deepcopy(s) for s in (start if start is not None else inv.legacy)]
    for k, op, prm in path:
        nxt = next((s for s, p in candidates(op, specs[k], inv.dom(k, specs)) if p == prm), None)
        if nxt is not None:
            specs[k] = nxt
    return specs
