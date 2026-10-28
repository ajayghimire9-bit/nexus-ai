"""Runtime field-access contract for deployed lifecycle machines (NOT LOCKED; engineering change of the sc track).

The u5 emitted class reads `x = rec.get(field); x = x if numeric else 0`: a missing value field silently became 0 (the X6
failure). The contract layer wraps the deployed machine and gives every event one explicit field-access outcome:
  PRESENT_VALID          the field the machine needs on this event kind is present and numeric
  LEGITIMATELY_MISSING   the field is not needed on this kind, or the build data showed it is nullable on this kind
  MAPPED(v)              absent, but mapping version v (schema signature: field absent, its mapped path present) supplies it
  SCHEMA_MISMATCH        needed but absent / non-numeric and no mapping applies: an INCIDENT is recorded, the event yields an
                         explicit unresolved row ('?schema_mismatch'), and the machine state is NOT advanced
The contract is inferred from what NEXUS can see at build: the accepted machine (which fields it reads on which kinds) and the
build stream (whether those fields were always present). Detection does not use the machine's output labels."""
from __future__ import annotations

import copy

from nexus import u5_statesplit as SP

MISMATCH_ROW = ("?schema_mismatch", None, None)


def _isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def get_path(e, path):
    cur = e
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def reads(m):
    """{kind: {field: [dependencies]}} - the fields the machine reads per event kind (register updates using x, value sources)."""
    out = {}
    for i, rg in enumerate(m["regs"]):
        f = rg.get("field")
        if not f:
            continue
        for (q, a), g in rg["upd"].items():
            if "x" in SP.S._vars(g):
                out.setdefault(a, {}).setdefault(f, []).append(f"reg_{i} update in mode_{q}")
    for ((q, a), ri, vj), src in m["sources"].items():
        if src and src[0] == "cur":
            out.setdefault(a, {}).setdefault(src[1], []).append(f"row {ri} slot {vj} in mode_{q}")
    return out


def infer(m, events, prior=None):
    """Contract from the machine + the stream it was learned on. `prior` (an earlier contract) is kept for every kind it
    covers: a relearn on an archive that already contains schema-changed records must never turn a required field into
    a nullable one."""
    ctrl = m["ctrl"]
    need = reads(m)
    req, nul = {}, {}
    for a, fs in need.items():
        evs = [e for e in events if e.get(ctrl) == a]
        for f in fs:
            if evs and all(_isnum(e.get(f)) for e in evs):
                req.setdefault(a, []).append(f)
            elif evs:
                nul.setdefault(a, []).append(f)
            else:
                req.setdefault(a, []).append(f)                 # never observed: be strict
    c = dict(required=req, nullable=nul, deps={a: {f: d for f, d in fs.items()} for a, fs in need.items()})
    if prior:
        for k in ("required", "nullable"):
            for a, fs in prior[k].items():
                c[k][a] = list(fs)
        for a, d in prior.get("deps", {}).items():
            c["deps"].setdefault(a, d)
    return c


class ContractRunner:
    """Deployed lifecycle runner = compiled NEXUS class + contract + versioned field mappings. Checkpointable."""

    def __init__(self, payload):
        self.payload = payload
        self.inner = SP.compile_class(payload["source"], payload["name"])()
        self.contract, self.mappings = payload["contract"], payload.get("mappings", [])
        self.ctrl = payload["machine"]["ctrl"]
        self.incidents = []
        self.outcomes = {}

    def resolve(self, e):
        a = e.get(self.ctrl)
        ev, bad = e, []
        for f in self.contract["required"].get(a, []) + self.contract["nullable"].get(a, []):
            v = e.get(f)
            if _isnum(v):
                self.outcomes["PRESENT_VALID"] = self.outcomes.get("PRESENT_VALID", 0) + 1
                continue
            hit = None
            if f not in e:
                for mv in reversed(self.mappings):
                    if mv["field"] == f and _isnum(get_path(e, mv["path"])):
                        hit = mv
                        break
            if hit is not None:
                ev = dict(ev, **{f: get_path(e, hit["path"])})
                self.outcomes[f"MAPPED_v{hit['version']}"] = self.outcomes.get(f"MAPPED_v{hit['version']}", 0) + 1
            elif f in self.contract["nullable"].get(a, []):
                self.outcomes["LEGITIMATELY_MISSING"] = self.outcomes.get("LEGITIMATELY_MISSING", 0) + 1
            else:
                bad.append(f)
        return ev, bad

    def ingest(self, e):
        a = e.get(self.ctrl)
        ev, bad = self.resolve(e)
        if bad:
            self.outcomes["SCHEMA_MISMATCH"] = self.outcomes.get("SCHEMA_MISMATCH", 0) + 1
            self.incidents.append(dict(raw=copy.deepcopy(e), expected_fields=bad, observed_fields=sorted(e),
                                       kind=a, mapping_version=len(self.mappings),
                                       dependencies={f: self.contract.get("deps", {}).get(a, {}).get(f, []) for f in bad}))
            return [MISMATCH_ROW]
        return self.inner.ingest(ev)

    def pop_incidents(self):
        out, self.incidents = self.incidents, []
        return out

    def get_state(self):
        return dict(inner=copy.deepcopy({k: v for k, v in self.inner.__dict__.items()}))

    def set_state(self, s):
        self.inner.__dict__.update(copy.deepcopy(s["inner"]))
        self.incidents = []
