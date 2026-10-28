"""sc end-to-end platform (NOT LOCKED): the ba platform source (u5 + t7 + oc + ba patches, unchanged) PLUS asserted sc patches.
No earlier platform file is edited; the ba platform and its X6 scorecard stay as they were.

Evaluation-side changes (privileged; never visible to NEXUS):
  * one REFERENCE NORMALISATION of a lifecycle record (X5 '_V2' kinds back; a renamed / nested / migrated value field back
    to the documented field) used by the oracle AND by the corrected SIMULATED HUMAN REPAIR (HumanRefMachine). The ba human
    patch (DocMachine) read the documented field and was wrong under X6; this one restores the data, including mixed
    old / new records. It remains human assistance (counted) and its normalisation is not reachable from NEXUS.
  * outcome bookkeeping: ticks served by the human patch are recorded in the ledger ('served_by').
  * splits / dev conditions:  sc_dev (fault = SC_DEV[(seed // 4) % 7]):  X6  value field renamed to <val>_amount from tick 9
        X6P  value moved to a nested path <val>_info.amount   X6D  renamed + an exact-copy decoy field legacy_<val>
        X6M  gradual migration (each record independently old or new schema from tick 9)
        LM   legitimately valueless kinds omit the value field from tick 1; 10 % of the other records carry value None
        X3, X5 (as before);   sc_val: X6 x4 (one per domain), X3 x2, X5 x2;   sc_test: (X6, X3, X6, X5)[i // 4]
Runtime changes for NEXUS arms that deploy a contract runner (b_kind 'contract'):
  * 'B:schema_mismatch' alarm from the contract layer's incidents (independent of the machine's output labels); the
    incidents are handed to the arm's repair; a tick whose outputs still hold an unresolved row makes the arm claim
    UNHEALTHY instead of healthy."""
from __future__ import annotations

import copy
import importlib.util
import random
import time
from pathlib import Path

from nexus import ba_platform as BP
from nexus import oc_platform as OCP
from nexus import t7_platform as T7
from nexus import u5_platform as _U5

SC_DEV = ("X6", "X6P", "X6D", "X6M", "LM", "X3", "X5")
SC_VAL = {13361: "X6", 13362: "X6", 13363: "X6", 13364: "X6", 13365: "X3", 13366: "X5", 13367: "X3", 13368: "X5"}
SC_VAL_B = {s + 10: f for s, f in SC_VAL.items()}

SC_PATCHES = [
    ('    if split == "ba_test":\n',
     '    if split in ("sc_dev", "sc_val", "sc_val_b", "sc_test"):\n        return _sc_fault(seed, split)\n    if split == "ba_test":\n'),
    ('                evs.append(e)\n',
     '                e = _sc_shape(self, e, kd, st, late)\n                evs.append(e)\n'),
    ('        return SF.reference(self.sfam, events, self.schema, self.x3)\n',
     '        events = [_sc_norm(self, e) for e in events]\n        return SF.reference(self.sfam, events, self.schema, self.x3)\n'),
    ('        if self.b_kind == "class":\n            parts.append(self.b_payload["source"])\n',
     '        if self.b_kind in ("class", "contract"):\n            parts.append(self.b_payload["source"])\n'
     '            for mv in self.b_payload.get("mappings", []):\n                parts.append(f"# field mapping v{mv[\'version\']}: read {mv[\'field\']!r} from {mv[\'path\']!r} when {mv[\'when\']}")\n'),
    ('        if self.b_kind == "class":\n            return SP.compile_class(',
     '        if self.b_kind == "contract":\n            return _sc_runner(self.b_payload)\n        if self.b_kind == "class":\n            return SP.compile_class('),
    ('                alarms.append("B:unknown_symbol")\n',
     '                alarms.append("B:unknown_symbol")\n'
     '            inc = obj.pop_incidents() if hasattr(obj, "pop_incidents") else []\n'
     '            if inc:\n                alarms.append("B:schema_mismatch")\n            arm.incidents = inc\n'),
    ('    claims = True                     # every alarm ends repaired or escalated; an arm believes its final tables\n',
     '    claims = not any(r[0] == "?schema_mismatch" for o in outputs.values() for rows in o["B"] for r in rows)\n'),
    ('    new.b_payload = dict(factory=lambda: DocMachine(fam, schema, x3=x3))\n',
     '    new.b_payload = dict(factory=lambda: _sc_human(P))\n'),
]


def _load():
    s = Path(_U5.__file__).read_text()
    for a, b in T7.PATCHES + OCP.OC_PATCHES + BP.BA_PATCHES + SC_PATCHES:
        if s.count(a) != 1:
            raise RuntimeError(f"sc platform patch anchor not found exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    sp = importlib.util.spec_from_loader("nexus._sc_platform_core", loader=None)
    mod = importlib.util.module_from_spec(sp)
    mod.__file__ = _U5.__file__
    mod.__dict__.update(_sc_fault=_sc_fault, _sc_shape=_sc_shape, _sc_norm=_sc_norm, _sc_runner=_sc_runner, _sc_human=_sc_human)
    exec(compile(s, _U5.__file__ + "[sc-patched]", "exec"), mod.__dict__)
    return mod


# ------------------------------------------------------------------------------------------------ generator side (privileged)
def _sc_fault(seed, split):
    if split == "sc_dev":
        return SC_DEV[(seed // 4) % len(SC_DEV)]
    if split == "sc_val":
        return SC_VAL[seed]
    if split == "sc_val_b":
        return SC_VAL_B[seed]
    from nexus import sc_seeds  # noqa: F401
    from nexus import seed_registry as R
    i = list(R.REGISTRY[("sc", "test")]).index(seed)
    return ("X6", "X3", "X6", "X5")[i // 4]


def _valueless(P, kd, st):
    from nexus import u5_stateful as SF
    a = SF.step(P.sfam, tuple(st), kd, 1.0, P.x3)
    b = SF.step(P.sfam, tuple(st), kd, 7.5, P.x3)
    return a == b


def _sc_shape(P, e, kd, st, late):
    f = P.schema.val
    fault = P.fault
    if fault not in ("X6P", "X6D", "X6M", "LM"):
        return e
    rnd = random.Random(f"sc-shape-{P.seed}-{e[P.schema.seq]}-{e[P.schema.key]}")
    if fault == "LM":
        if _valueless(P, kd, st):
            e = {k: v for k, v in e.items() if k != f}
        elif rnd.random() < 0.10:
            e = dict(e, **{f: None})
        return e
    if not late:
        return e
    v = e.get(f, e.get(f + "_amount"))
    if fault == "X6P":
        e = {k: x for k, x in e.items() if k != f}
        e[f + "_info"] = {"amount": v, "unit": "std"}
    elif fault == "X6D":
        e = {k: x for k, x in e.items() if k != f}
        e[f + "_amount"] = v
        e["legacy_" + f] = v
    elif fault == "X6M" and rnd.random() < 0.5:
        e = {k: x for k, x in e.items() if k != f}
        e[f + "_amount"] = v
    return e


def _sc_norm(P, e):
    """Reference normalisation of one lifecycle record (privileged: knows every documented rename)."""
    f = P.schema.val
    if f in e:
        return e
    if f + "_amount" in e:
        return dict({k: v for k, v in e.items() if k != f + "_amount"}, **{f: e[f + "_amount"]})
    if isinstance(e.get(f + "_info"), dict):
        return dict(e, **{f: e[f + "_info"].get("amount")})
    return e


class HumanRefMachine:
    """Corrected simulated human repair: the documented lifecycle applied to reference-normalised records."""

    def __init__(self, P):
        self.P, self.st = P, {}

    def ingest(self, e):
        from nexus import u5_stateful as SF
        P = self.P
        e = _sc_norm(P, e)
        kd = e.get(P.schema.kind)
        if P.fault == "X5" and isinstance(kd, str) and kd.endswith("_V2"):
            kd = kd[:-3]
        k = e.get(P.schema.key)
        s = tuple(self.st.get(k, SF.INIT[P.sfam]))
        v = e.get(P.schema.val)
        v = v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0
        s2, rows = SF.step(P.sfam, s, kd, v, P.x3)
        self.st[k] = list(s2)
        return rows

    def get_state(self):
        return dict(st=copy.deepcopy(self.st))

    def set_state(self, s):
        self.st = copy.deepcopy(s["st"])


def _sc_human(P):
    return HumanRefMachine(P)


def _sc_runner(payload):
    from nexus import sc_contract as SC
    return SC.ContractRunner(payload)


PL = _load()
Project, NexusArm, FixedArm, run_project = PL.Project, PL.NexusArm, PL.FixedArm, PL.run_project


# ------------------------------------------------------------------------------------------------ the NEXUS schema arm
class NexusArmSchema(PL.NexusArm):
    """ba NexusArmBounded behaviour (bounded acceptance on every (re)learned lifecycle class, growth rule first, full-space
    fallback) + the runtime field contract + (optionally) generic field-mapping repair on schema incidents."""
    growth = None
    mapping_repair = True
    boost = True                                                     # f45da4e priority-A components (as NexusArmStrong)
    _probe = T7.NexusArmStrong._probe
    _probe_sample = T7.NexusArmStrong._probe_sample

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.incidents, self.log = [], []

    @staticmethod
    def learning_view(events, prior=None):
        """Events as the (unchanged) u5 learner sees them: a field that is numeric wherever present but absent / None on
        some records gets an explicit 0 there (structured dict / list values are left out of the learner's view; the contract
        and the mapping repair still see them) - at BUILD for any such field (the build data define the task contract),
        on a relearn ONLY where the prior contract marks that (kind, field) nullable, so a schema change is never masked.
        The runtime contract is always inferred from the ORIGINAL records."""
        from nexus import sc_contract as SC
        if any(isinstance(v, (dict, list)) for e in events for v in e.values()):      # structured values are not scalars the
            events = [{k: v for k, v in e.items() if not isinstance(v, (dict, list))} for e in events]   # u5 learner can use
        num = {k for e in events for k, v in e.items() if SC._isnum(v)}
        mixed = {f for f in num if any(not SC._isnum(e.get(f)) for e in events)}
        if not mixed:
            return events, []
        ctrl = (prior or {}).get("_ctrl", [None])[0]
        allowed = None if prior is None else {(a, f) for a, fs in prior["nullable"].items() for f in fs}
        out, filled = [], set()
        for e in events:
            fill = [f for f in mixed if not SC._isnum(e.get(f)) and (allowed is None or (e.get(ctrl), f) in allowed)]
            if fill:
                e = dict(e, **{f: 0 for f in fill})
                filled |= set(fill)
            out.append(e)
        return out, sorted(filled)

    def _learn(self, events, outputs, query, seed, prior=None):
        t0 = time.process_time()
        view, filled = self.learning_view(events, prior)
        r = BP.learn_class_bounded(view, outputs, query, seed=seed, growth=self.growth)
        self.log.append(dict(step="learn", learner=(r or {}).get("learner"), accepted=r is not None, n_events=len(events),
                             filled_for_learning=filled, cpu_s=round(time.process_time() - t0, 3), queries=(r or {}).get("queries")))
        return r

    def _payload(self, r, events, prior=None):
        from nexus import sc_contract as SC
        return dict(source=r["source"], name=r["name"], machine=r["machine"], witnesses=r["witnesses"],
                    contract=dict(SC.infer(r["machine"], events, prior), _ctrl=[r["machine"]["ctrl"]]), mappings=[], scope=r.get("scope"), learner=r.get("learner"),
                    n_modes=r["machine"]["n"], n_regs=len(r["machine"]["regs"]), queries=r["queries"])

    def _learn_b(self, events, outputs, query, mode, seed=0):
        r = self._learn(events, outputs, query, seed)
        if r is None:
            return None
        return ("contract", self._payload(r, events))

    def repair_B(self, P, prog, archive_events, archive_rows):
        from nexus import sc_mapping as SM
        inc, self.incidents = list(self.incidents), []
        old = prog.b_payload if prog.b_kind == "contract" else None
        oracle = lambda x: P.oracle_B(x)                            # noqa: E731  (declared API; every call charged)
        if inc and old is not None and not self.mapping_repair:
            self.log.append(dict(step="mapping_repair", outcome="DISABLED (relearn only)", incidents=len(inc)))
        if inc and old is not None and self.mapping_repair:
            t0 = time.process_time()
            q0 = P.queries["mq"]

            def relearn(mapped, rows):
                r = self._learn(mapped, rows, oracle, len(mapped), old["contract"])
                return None if r is None else (r["machine"], r["source"], r["name"])

            newp, lg = SM.repair(old, inc, archive_events, archive_rows, oracle, relearn=relearn, seed=len(archive_events))
            lg.update(step="mapping_repair", cpu_s=round(time.process_time() - t0, 3), mq=P.queries["mq"] - q0,
                      incident_example=dict(raw=inc[0]["raw"], expected=inc[0]["expected_fields"], observed=inc[0]["observed_fields"],
                                            kind=inc[0]["kind"], mapping_version=inc[0]["mapping_version"],
                                            dependencies=inc[0]["dependencies"]))
            self.log.append(lg)
            if newp is None:
                return None
            if newp["machine"] is not old["machine"]:
                from nexus import sc_contract as SC
                newp["contract"] = dict(SC.infer(newp["machine"], archive_events, old["contract"]), _ctrl=old["contract"].get("_ctrl", []))
            new = copy.copy(prog)
            new.b_kind, new.b_payload = "contract", newp
            new.version = prog.version + 1
            return new
        r = self._learn(archive_events, archive_rows, oracle, len(archive_events), old["contract"] if old else None)
        if r is None:
            return None
        new = copy.copy(prog)
        new.b_kind, new.b_payload = "contract", self._payload(r, archive_events, old["contract"] if old else None)
        if old:
            new.b_payload["mappings"] = list(old.get("mappings", []))
        new.version = prog.version + 1
        return new
