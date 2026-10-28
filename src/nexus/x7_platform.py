"""x7 end-to-end platform (NOT LOCKED): the sc platform source (u5 + t7 + oc + ba + sc patches, unchanged) PLUS asserted x7
patches. No earlier platform file is edited; sc_dev projects regenerate byte-identically (tests/test_x7.py).

Generator / oracle side (privileged; never visible to NEXUS). f = the project's documented value field; from tick 9 ('late'):
  declared DEVELOPMENT families (split x7_dev, fault = X7_DEV[(seed // 4) % 4]):
    XD1  abrupt: f removed; f_gross and f_fee added (truth f = gross - fee; fee = 0 on ~30 % of records); correlated
         distractor f_est = round(f)
    XD2  gradual (each record new with p = 0.6): f removed; nested f_meta = {milli: round(1000 f), src: 'm2'} (truth milli / 1000)
    XD3  abrupt, FIELD STILL PRESENT, meaning changed: f now carries 10 x the value; marker f_v2 = 1 added (truth f / 10)
    XR   abrupt distractor churn: the first schema distractor is removed, the second renamed to <name>_id (truth unchanged)
  HELD-OUT families (split x7_test only; the platform check x7_pcheck runs the generator / oracle / human, never a NEXUS arm):
    X7a  gradual (p = 0.7): f removed; f_major = floor(f) and f_minor = round(100 (f - floor f)) added (truth major + minor / 100)
    X7b  abrupt, FIELD STILL PRESENT, meaning changed: f now carries a per-unit rate round(f / q, 4); f_qty = q in 1..8 added
         (truth f x qty)
  splits: x7_val / x7_val_b  X7_VAL (known classes + dev families, no X7);  x7_test  X7_TEST[i // 4] by index (each group of
  4 seeds covers the 4 domains);  sc_* splits are the sc generator unchanged.
  The reference normalisation (_x7_norm) maps every documented format back to f; the oracle and the corrected simulated human
  (HumanRefX7, counted assistance) use it.
Runtime: contract runners that report shape notices raise 'B:shape_change' (in addition to sc's 'B:schema_mismatch')."""
from __future__ import annotations

import copy
import importlib.util
import math
import random
import time
from pathlib import Path

from nexus import ba_platform as BP
from nexus import oc_platform as OCP
from nexus import sc_platform as SCP
from nexus import t7_platform as T7
from nexus import u5_platform as _U5

X7_DEV = ("XD1", "XD2", "XD3", "XR")
X7_HELD = ("X7a", "X7b")
X7_FAULTS = X7_DEV + X7_HELD
X7_VAL = ("X6", "XD1", "X3", "XD3", "X6P", "XD2", "X5", "X6M")
X7_TEST = (("X7a",) * 4, ("X7b",) * 4, ("X6", "X6P", "X6D", "X6M"), ("X3", "X5", "X3", "X5"))
X7_PCHECK = ("X7a", "X7a", "X7a", "X7a", "X7b", "X7b", "X7b", "X7b")

X7_PATCHES = [
    ('    if split in ("sc_dev", "sc_val", "sc_val_b", "sc_test"):\n        return _sc_fault(seed, split)\n',
     '    if split.startswith("sc_") or split.startswith("x7_"):\n        return _sc_fault(seed, split)\n'),
    ('            arm.incidents = inc\n',
     '            arm.incidents = inc\n'
     '            nt = obj.pop_notices() if hasattr(obj, "pop_notices") else []\n'
     '            if nt:\n                alarms.append("B:shape_change")\n            arm.notices = nt\n'),
]


def _load():
    s = Path(_U5.__file__).read_text()
    for a, b in T7.PATCHES + OCP.OC_PATCHES + BP.BA_PATCHES + SCP.SC_PATCHES + X7_PATCHES:
        if s.count(a) != 1:
            raise RuntimeError(f"x7 platform patch anchor not found exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    sp = importlib.util.spec_from_loader("nexus._x7_platform_core", loader=None)
    mod = importlib.util.module_from_spec(sp)
    mod.__file__ = _U5.__file__
    mod.__dict__.update(_sc_fault=_x7_fault, _sc_shape=_x7_shape, _sc_norm=_x7_norm, _sc_runner=_x7_runner, _sc_human=_x7_human)
    exec(compile(s, _U5.__file__ + "[x7-patched]", "exec"), mod.__dict__)
    return mod


# ------------------------------------------------------------------------------------------------ generator side (privileged)
def _x7_fault(seed, split):
    if split.startswith("sc_"):
        return SCP._sc_fault(seed, split)
    from nexus import seed_registry as R
    from nexus import x7_seeds  # noqa: F401
    if split == "x7_dev":
        return X7_DEV[(seed // 4) % len(X7_DEV)]
    if split == "x7_pcheck":
        return X7_PCHECK[list(R.REGISTRY[("x7", "pcheck")]).index(seed)]
    if split in ("x7_val", "x7_val_b"):
        return X7_VAL[list(R.REGISTRY[("x7", split[3:])]).index(seed)]
    i = list(R.REGISTRY[("x7", "test")]).index(seed)
    return X7_TEST[i // 4][i % 4]


def _isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _x7_shape(P, e, kd, st, late):
    if P.fault not in X7_FAULTS:
        return SCP._sc_shape(P, e, kd, st, late)
    if not late:
        return e
    f = P.schema.val
    rnd = random.Random(f"x7-shape-{P.seed}-{e[P.schema.seq]}-{e[P.schema.key]}")
    v = e.get(f)
    if P.fault == "XR":
        d0, d1 = P.schema.distract
        e = {k: x for k, x in e.items() if k not in (d0, d1)}
        e[d1 + "_id"] = rnd.randint(0, 9)
        return e
    if not _isnum(v):
        return e
    if P.fault == "XD1":
        fee = 0.0 if rnd.random() < 0.3 else round(rnd.uniform(0.5, 25), 2)
        e = {k: x for k, x in e.items() if k != f}
        e.update({f + "_gross": round(v + fee, 2), f + "_fee": fee, f + "_est": int(round(v))})
    elif P.fault == "XD2" and rnd.random() < 0.6:
        e = {k: x for k, x in e.items() if k != f}
        e[f + "_meta"] = {"milli": int(round(v * 1000)), "src": "m2"}
    elif P.fault == "XD3":
        e = dict(e, **{f: round(v * 10, 6), f + "_v2": 1})
    elif P.fault == "X7a" and rnd.random() < 0.7:
        major = math.floor(v)
        e = {k: x for k, x in e.items() if k != f}
        e.update({f + "_major": int(major), f + "_minor": int(round((v - major) * 100))})
    elif P.fault == "X7b":
        q = rnd.randint(1, 8)
        e = dict(e, **{f: round(v / q, 4), f + "_qty": q})
    return e


def _x7_norm(P, e):
    """Reference normalisation of one lifecycle record (privileged: knows every documented format)."""
    f = P.schema.val
    if _isnum(e.get(f)):
        if _isnum(e.get(f + "_qty")):
            return dict(e, **{f: e[f] * e[f + "_qty"]})
        if f + "_v2" in e:
            return dict(e, **{f: e[f] / 10})
        return e
    if _isnum(e.get(f + "_major")) and _isnum(e.get(f + "_minor")):
        return dict(e, **{f: e[f + "_major"] + e[f + "_minor"] / 100})
    if _isnum(e.get(f + "_gross")) and _isnum(e.get(f + "_fee")):
        return dict(e, **{f: e[f + "_gross"] - e[f + "_fee"]})
    if isinstance(e.get(f + "_meta"), dict) and _isnum(e[f + "_meta"].get("milli")):
        return dict(e, **{f: e[f + "_meta"]["milli"] / 1000})
    return SCP._sc_norm(P, e)


class HumanRefX7(SCP.HumanRefMachine):
    """Corrected simulated human repair: the documented lifecycle applied to x7-reference-normalised records (counted help)."""

    def ingest(self, e):
        return super().ingest(_x7_norm(self.P, e))


def _x7_human(P):
    return HumanRefX7(P)


def _x7_runner(payload):
    if payload.get("x7"):
        from nexus import x7_contract as XC
        return XC.ContractRunnerX(payload)
    from nexus import sc_contract as SC
    return SC.ContractRunner(payload)


PL = _load()
Project, NexusArm, FixedArm, run_project = PL.Project, PL.NexusArm, PL.FixedArm, PL.run_project


# ------------------------------------------------------------------------------------------------ the NEXUS x7 arm
class NexusArmX7(PL.NexusArm):
    """sc NexusArmSchema behaviour with the x7 components, each switchable for the ablations:
      learner_fix   reset-aware register search (x7_regsearch) in the build / relearn lifecycle learner
      prune         dependency pruning (x7_contract.prune) + live-dependency contract; off = emitted-code reads
      mapping       'expression' (x7_mapping tiers 0-2) | 'field' (tier 0 only) | None (relearn only)
    The A stream (status / value programs) is built once per project and shared by every NEXUS x7 arm (build_A)."""
    growth = None
    mapping = "expression"
    prune = True
    learner_fix = True
    boost = True
    _probe = T7.NexusArmStrong._probe
    _probe_sample = T7.NexusArmStrong._probe_sample
    learning_view = staticmethod(SCP.NexusArmSchema.learning_view)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.incidents, self.notices, self.log = [], [], []

    def _learn(self, events, outputs, query, seed, prior=None):
        from nexus import x7_regsearch as XR
        t0 = time.process_time()
        view, filled = self.learning_view(events, prior)
        r = XR.learn_class_bounded(view, outputs, query, seed=seed, growth=self.growth, fix=self.learner_fix)
        self.log.append(dict(step="learn", learner=(r or {}).get("learner"), accepted=r is not None, n_events=len(events),
                             filled_for_learning=filled, cpu_s=round(time.process_time() - t0, 3), queries=(r or {}).get("queries"),
                             growth_steps=(r or {}).get("growth_steps")))
        return r

    def _shape_machine(self, r, events):
        from nexus import u5_statesplit as SP
        from nexus import x7_contract as XC
        m = r["machine"]
        if not self.prune:
            return m, r["source"], r["name"], None
        pm, rep = XC.prune(m)
        rep["sensitivity"] = XC.sensitivity(m, pm, self.learning_view(events)[0])
        src, name = SP.class_source(pm, witnesses=r["witnesses"])
        return pm, src, name, rep

    def _payload(self, r, events, prior=None):
        from nexus import x7_contract as XC
        m, src, name, rep = self._shape_machine(r, events)
        import hashlib
        self.log.append(dict(step="dependencies", pruned=rep is not None, report=rep, reads=XC.reads(m, emitted=not self.prune),
                             unpruned_class_sha256=hashlib.sha256(r["source"].encode()).hexdigest(),
                             emitted_reads=XC.reads(r["machine"], emitted=True)))
        return dict(x7=True, source=src, name=name, machine=m, witnesses=r["witnesses"],
                    contract=XC.infer(m, events, prior, emitted=not self.prune), mappings=[], benign_paths={},
                    scope=r.get("scope"), learner=r.get("learner"), n_modes=m["n"], n_regs=len(m["regs"]), queries=r["queries"],
                    prune_report=rep)

    def _learn_b(self, events, outputs, query, mode, seed=0):
        r = self._learn(events, outputs, query, seed)
        if r is None:
            return None
        return ("contract", self._payload(r, events))

    # -- shared A-stream build: NexusArm.build split so that every x7 arm deploys the SAME status / value programs
    def build_A(self, P):
        recs = [(r, t) for t in range(1, PL.BUILD_TICKS + 1) for r in P.ticks[t]["A"]]
        labs = []
        for t in range(1, PL.BUILD_TICKS + 1):
            labs += P.oracle_A(P.ticks[t]["A"], t, "build_labels")
        envs = [{"r": r, "t": P.ticks[t]["registry"]} for r, t in recs]
        c0 = time.process_time()
        status, sst = PL.synth_status(envs, [s for s, _ in labs], self.status_s, self.learner["cfg"])
        ok = [(e, v) for e, (s, v) in zip(envs, labs) if s == "ok"]
        value, vst = PL.synth_value([e for e, _ in ok], [v for _, v in ok], self.learner, self.value_s, seed=P.seed)
        return dict(status=status, value=value, info=dict(status_stats={k: v for k, v in sst.items() if k != "per"}, value_stats=vst,
                                                          build_A_cpu_s=round(time.process_time() - c0, 3)))

    def build_B(self, P, A):
        c0 = time.process_time()
        evs = [e for t in range(1, PL.BUILD_TICKS + 1) for e in P.ticks[t]["B"]]
        outs = P.oracle_B(evs, "build_labels")
        b = self._learn_b(evs, outs, lambda x: P.oracle_B(x), self.b_mode, seed=P.seed)
        info = dict(A["info"], build_B_cpu_s=round(time.process_time() - c0, 3))
        if A["status"] is None or A["value"] is None or b is None:
            info["unsolved"] = [n for n, x in (("status", A["status"]), ("value", A["value"]), ("lifecycle", b)) if x is None]
            return None, info
        prog = PL.Program(A["value"], A["status"], self.learner["lib"], b[0], b[1])
        info.update(n_modes=b[1]["n_modes"], n_regs=b[1]["n_regs"], b_queries=b[1]["queries"])
        return prog, info

    def repair_B(self, P, prog, archive_events, archive_rows):
        from nexus import x7_contract as XC
        from nexus import x7_mapping as XM
        inc, self.incidents = list(self.incidents), []
        nts, self.notices = list(getattr(self, "notices", [])), []
        old = prog.b_payload if prog.b_kind == "contract" and prog.b_payload.get("x7") else None
        oracle = lambda x: P.oracle_B(x)                            # noqa: E731
        if old is not None and self.mapping:
            t0, q0 = time.process_time(), P.queries["mq"]

            def relearn(mapped, rows):
                r = self._learn(mapped, rows, oracle, len(mapped), old["contract"])
                if r is None:
                    return None
                m, src, name, _ = self._shape_machine(r, mapped)
                return m, src, name
            newp, lg = XM.repair(old, inc, nts, archive_events, archive_rows, oracle, relearn=relearn, mode=self.mapping,
                                 seed=len(archive_events))
            lg.update(step="mapping_repair", cpu_s=round(time.process_time() - t0, 3), mq=P.queries["mq"] - q0)
            ex = (inc or nts or [None])[0]
            if ex is not None:
                lg["evidence_example"] = {k: v for k, v in ex.items() if k in ("raw", "expected_fields", "observed_fields", "kind",
                                                                                 "mapping_version", "dependencies", "new_paths")}
            self.log.append(lg)
            if newp is not None:
                new = copy.copy(prog)
                new.b_kind, new.b_payload = "contract", newp
                new.version = prog.version + 1
                return new
            if lg.get("outcome") != "NO_SHAPE_EVIDENCE":
                return None
        if (inc or nts) and old is not None and not self.mapping:
            self.log.append(dict(step="mapping_repair", outcome="DISABLED (relearn only)", incidents=len(inc), notices=len(nts)))
        r = self._learn(archive_events, archive_rows, oracle, len(archive_events), old["contract"] if old else None)
        if r is None:
            return None
        new = copy.copy(prog)
        new.b_kind, new.b_payload = "contract", self._payload(r, archive_events, old["contract"] if old else None)
        if old:
            new.b_payload["mappings"] = list(old.get("mappings", []))
            new.b_payload["benign_paths"] = dict(old.get("benign_paths", {}))
        new.version = prog.version + 1
        return new
