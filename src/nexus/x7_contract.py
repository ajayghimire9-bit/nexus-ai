"""x7 runtime contract (NOT LOCKED): dependency analysis + semantics-preserving pruning, versioned EXPRESSION adapters, and
shape notices. A separately versioned extension of sc_contract (which stays unchanged).

Dependencies (Part 3) are derived from the executable machine, not from what the emitted code happens to read:
  control      the key and control fields are read on every event (structural; required wherever the build data had them)
  updates      a register's field is a dependency of kind a only if some LIVE register update on a transition (q, a) reads x
  outputs      an output slot whose source is ('cur', f) makes f a dependency of that kind
A register is LIVE if some output slot reads it (registers only read their own accumulator and x, so liveness is not
transitive). prune() removes dead registers, identity updates (acc -> acc) and the field binding of registers whose live
updates never read x, renumbers the sources, and re-emits the class. These rewrites are exact for this machine language (the
removed code cannot influence any output), and sensitivity() additionally replays the original and the pruned machine on the
build stream and on counterfactual copies in which every removed input is deleted / redrawn (support, not proof).
The no-pruning ablation uses the EMITTED-CODE reads instead: every bound register field on every kind.

Runtime outcomes per (event, needed field): PRESENT_VALID | LEGITIMATELY_MISSING | MAPPED_vN | SCHEMA_MISMATCH (incident,
explicit '?schema_mismatch' row, state not advanced). Adapters are expressions (x7_expr) evaluated newest first; an adapter
whose value is MISSING does not apply. SHAPE NOTICE: an event of kind a carrying a numeric path never seen on kind a at build
(and not in an accepted adapter's or a verified-benign signature) is recorded as a notice; the event is processed normally;
notices raise the operator's 'B:shape_change' alarm (verification, never a silent substitution). Removing a field is never a
notice; it is a mismatch only if a live dependency needs that field."""
from __future__ import annotations

import copy
import random

from nexus import u5_statesplit as SP
from nexus import x7_expr as X

MISMATCH_ROW = ("?schema_mismatch", None, None)
_CLS = {}


# ------------------------------------------------------------------------------------------------ dependencies + pruning
def live_regs(m):
    return sorted({src[1] for src in m["sources"].values() if src and src[0] == "reg"})


def reads(m, emitted=False):
    """{kind: {field: [dependencies]}}. emitted=True: what the emitted class reads (every bound field, every kind)."""
    out = {}
    if emitted:
        for i, rg in enumerate(m["regs"]):
            if rg.get("field"):
                for a in m["alpha"]:
                    out.setdefault(a, {}).setdefault(rg["field"], []).append(f"reg_{i} binding (emitted code reads it)")
    live = set(live_regs(m))
    for i, rg in enumerate(m["regs"]):
        f = rg.get("field")
        if not f or i not in live:
            continue
        for (q, a), g in rg["upd"].items():
            if "x" in SP.S._vars(g):
                out.setdefault(a, {}).setdefault(f, []).append(f"reg_{i} update in mode_{q}")
    for ((q, a), ri, vj), s in m["sources"].items():
        if s and s[0] == "cur":
            out.setdefault(a, {}).setdefault(s[1], []).append(f"row {ri} slot {vj} in mode_{q}")
    return out


def prune(m):
    """Semantics-preserving simplification. Returns (pruned machine, report)."""
    live = live_regs(m)
    rep = dict(regs_before=len(m["regs"]), dead_regs=[i for i in range(len(m["regs"])) if i not in live],
               unbound_fields=[], identity_updates_removed=0,
               reads_before=sorted({rg["field"] for rg in m["regs"] if rg.get("field")}))
    remap = {old: new for new, old in enumerate(live)}
    regs = []
    for old in live:
        rg = copy.deepcopy(m["regs"][old])
        upd = {}
        for t, g in rg["upd"].items():
            if g == ("var", "acc"):
                rep["identity_updates_removed"] += 1
                continue
            upd[t] = g
        rg["upd"] = upd
        if rg.get("field") and not any("x" in SP.S._vars(g) for g in upd.values()):
            rep["unbound_fields"].append(dict(reg=old, field=rg["field"]))
            rg["field"] = None
        regs.append(rg)
    sources = {k: (("reg", remap[s[1]]) if s and s[0] == "reg" else s) for k, s in m["sources"].items()}
    pm = dict(m, regs=regs, sources=sources)
    rep["reads_after"] = sorted({rg["field"] for rg in regs if rg.get("field")} |
                                {s[1] for s in sources.values() if s and s[0] == "cur"})
    rep["regs_after"] = len(regs)
    return pm, rep


def sensitivity(m, pm, events, n_draws=8, seed=0):
    """Replay original vs pruned on the build stream and on counterfactual copies where every input the pruning removed is
    deleted or redrawn. Returns the number of disagreeing events (0 expected)."""
    removed = sorted(set(prune_removed_inputs(m, pm)))
    rnd = random.Random(seed)
    bad = 0
    streams = [events]
    for d in range(n_draws):
        cf = []
        for e in events:
            e2 = dict(e)
            for f in removed:
                if d % 2 == 0:
                    e2.pop(f, None)
                else:
                    e2[f] = round(rnd.uniform(-500, 500), 3)
            cf.append(e2)
        streams.append(cf)
    for s in streams:
        a, b = SP.run_machine(m, s), SP.run_machine(pm, s)
        bad += sum(not SP._rows_eq(list(map(tuple, x)), list(map(tuple, y))) for x, y in zip(a, b))
    return dict(removed_inputs=removed, streams=len(streams), disagreeing_events=bad)


def prune_removed_inputs(m, pm):
    a = {rg["field"] for rg in m["regs"] if rg.get("field")}
    b = {rg["field"] for rg in pm["regs"] if rg.get("field")} | {s[1] for s in pm["sources"].values() if s and s[0] == "cur"}
    return a - b


# ------------------------------------------------------------------------------------------------ contract inference
def signature(e):
    return tuple(sorted(X.numeric_paths(e)))


def infer(m, events, prior=None, emitted=False):
    """Contract from the machine + its build stream. prior: kept for every kind it covers (a relearn on an archive that
    already holds schema-changed records never turns a required field into a nullable one)."""
    ctrl, key = m["ctrl"], m["key"]
    need = reads(m, emitted=emitted)
    req, nul = {}, {}
    for a, fs in need.items():
        evs = [e for e in events if e.get(ctrl) == a]
        for f in fs:
            if evs and all(X.isnum(e.get(f)) for e in evs):
                req.setdefault(a, []).append(f)
            elif evs:
                nul.setdefault(a, []).append(f)
            else:
                req.setdefault(a, []).append(f)
    seen = {}
    for e in events:
        seen.setdefault(e.get(ctrl), set()).update(X.numeric_paths(e))
    c = dict(required=req, nullable=nul, deps={a: dict(fs) for a, fs in need.items()}, structural=[key, ctrl],
             seen_paths={a: sorted(v) for a, v in seen.items() if a is not None}, _ctrl=[ctrl], emitted_reads=emitted)
    if prior:
        for k in ("required", "nullable"):
            for a, fs in prior[k].items():
                c[k][a] = list(fs)
        for a, d in prior.get("deps", {}).items():
            c["deps"].setdefault(a, d)
        for a, ps in prior.get("seen_paths", {}).items():
            c["seen_paths"][a] = sorted(set(ps) | set(c["seen_paths"].get(a, [])))
    return c


# ------------------------------------------------------------------------------------------------ the deployed runner
class ContractRunnerX:
    """Compiled NEXUS class + contract + versioned expression adapters + shape notices. Checkpointable."""

    def __init__(self, payload):
        self.payload = payload
        key = (payload["name"], hash(payload["source"]))
        if key not in _CLS:
            _CLS[key] = SP.compile_class(payload["source"], payload["name"])
        self.inner = _CLS[key]()
        self.contract, self.mappings = payload["contract"], payload.get("mappings", [])
        self.ctrl = payload["machine"]["ctrl"]
        self.known = {a: set(ps) for a, ps in self.contract.get("seen_paths", {}).items()}
        for a, ps in payload.get("benign_paths", {}).items():
            self.known.setdefault(a, set()).update(ps)
        for mv in self.mappings:
            for a in mv.get("kinds", []):
                self.known.setdefault(a, set()).update(mv.get("paths", []))
        self.incidents, self.notices, self.outcomes = [], [], {}

    def _count(self, k):
        self.outcomes[k] = self.outcomes.get(k, 0) + 1

    def resolve(self, e):
        a = e.get(self.ctrl)
        ev, bad = e, []
        for f in self.contract.get("structural", []):
            if f not in e:
                bad.append(f)
        if bad:
            return ev, bad
        for f in self.contract["required"].get(a, []) + self.contract["nullable"].get(a, []):
            hit = None
            for mv in reversed(self.mappings):
                if mv["field"] != f:
                    continue
                v = X.ev(mv["expr"], e)
                if v is not X.MISSING:
                    hit = (mv, v)
                    break
            if hit is not None:
                mv, v = hit
                raw = e.get(f)
                if X.chosen(mv["expr"], e) == ("f", f) and X.isnum(raw):
                    self._count("PRESENT_VALID")
                else:
                    self._count(f"MAPPED_v{mv['version']}")
                    ev = dict(ev, **{f: v})
                continue
            if X.isnum(e.get(f)):
                self._count("PRESENT_VALID")
            elif f in self.contract["nullable"].get(a, []):
                self._count("LEGITIMATELY_MISSING")
            else:
                bad.append(f)
        return ev, bad

    def ingest(self, e):
        a = e.get(self.ctrl)
        ev, bad = self.resolve(e)
        if bad:
            self._count("SCHEMA_MISMATCH")
            self.incidents.append(dict(raw=copy.deepcopy(e), expected_fields=bad, observed_fields=sorted(e), kind=a,
                                       mapping_version=len(self.mappings),
                                       dependencies={f: self.contract.get("deps", {}).get(a, {}).get(f, ["structural"]) for f in bad}))
            return [MISMATCH_ROW]
        new = [p for p in X.numeric_paths(e) if p not in self.known.get(a, set())]
        if new and a in self.known:
            self.notices.append(dict(raw=copy.deepcopy(e), kind=a, new_paths=sorted(new)))
        return self.inner.ingest(ev)

    def pop_incidents(self):
        out, self.incidents = self.incidents, []
        return out

    def pop_notices(self):
        out, self.notices = self.notices, []
        return out

    def get_state(self):
        return dict(inner=copy.deepcopy({k: v for k, v in self.inner.__dict__.items()}))

    def set_state(self, s):
        self.inner.__dict__.update(copy.deepcopy(s["inner"]))
        self.incidents, self.notices = [], []
