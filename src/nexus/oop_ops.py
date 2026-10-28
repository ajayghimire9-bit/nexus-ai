"""OOP-track operations (NOT LOCKED). The R2 operations code (r2_ops, unchanged) loaded as a SEPARATE module from its source
with exact, asserted patches, so the R2 operator - incident search, shadow tests, B1 localisation (provenance contrast +
typed evidence + ddmin trace shrinking + CEGIS over shrunk counterexamples), C0 ordering, B0 secondary - is unchanged except:
  * template = oop_template (14 decisions: 10 switches + 4 synthesised holes); monitor = oop_reconcile (de5 rules)
  * typed evidence naming a removed switch is mapped to its hole; every quarantine-class symptom (want q:<reason>) types
    syn_status
  * RESYNTHESIS before the candidate set is formed: every synthesised hole among the localised holes (B1: the top 6;
    B0: the implicated decisions) whose current program disagrees with the examples the spec monitor gives on the operator
    archive is synthesised again from primitives on those examples; the new program becomes a new option of the hole and
    goes through the unchanged candidate pipeline (cheap checks on the shrunk counterexamples, then full shadow verification
    with redeploy + rollback). Its CPU is inside localisation CPU, which is charged."""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter

from nexus import oop_examples as X
from nexus import oop_template as OT
from nexus import r2_ops as _R2O

TEXT = [
    ("from nexus import r2_reconcile as R2R\n", "from nexus import oop_reconcile as R2R\n"),
    ("from nexus import r2_template as RT2\n", "from nexus import oop_template as RT2\n"),
    ('    ("from nexus import r1_template as RT\\n", "from nexus import r2_template as RT\\n"),\n',
     '    ("from nexus import r1_template as RT\\n", "from nexus import oop_template as RT\\n"),\n'
     '    ("            cands = [((d, o),) for d in holes for o in RT.DECISIONS[d] if o != choice[d]]\\n",\n'
     '     "            RESYNTH(self, env, holes, arch)\\n            cands = [((d, o),) for d in holes for o in RT.DECISIONS[d] if o != choice[d]]\\n"),\n'
     '    ("            impl = [d for d in suspects if d in stage_holes(env) or any(d in B0_TABLE.get(k, []) for k in bad)]\\n",\n'
     '     "            impl = [d for d in suspects if d in stage_holes(env) or any(d in B0_TABLE.get(k, []) for k in bad)]\\n'
     '            RESYNTH(self, env, impl, arch)\\n"),\n'),
    ('_rec.insert(_rec.index("schema_handling") + 1, "discount_unit")\n_rec.insert(_rec.index("fx") + 1, "fx_unknown")\n', ""),
]


def _load():
    s = open(_R2O.__file__).read()
    for a, b in TEXT:
        if s.count(a) != 1:
            raise RuntimeError(f"OOP ops patch anchor not found exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    sp = importlib.util.spec_from_loader("nexus._oop_ops_r2", loader=None)
    mod = importlib.util.module_from_spec(sp)
    mod.__file__ = _R2O.__file__
    exec(compile(s, _R2O.__file__ + "[oop-patched]", "exec"), mod.__dict__)
    return mod


R2 = _load()
O3 = R2.O2                                               # the r1_ops core, patched by r2 and then by the TEXT above
for name in ("B0_TABLE", "FEAT_HOLES", "VIOL_HOLES"):
    setattr(O3, name, {k: OT.remap(v) for k, v in getattr(O3, name).items()})
O3.ACC_HOLES = {k: OT.remap(v) for k, v in O3.ACC_HOLES.items()}
_rec = list(O3.B0_TABLE["reconciliation"])
_rec.insert(_rec.index("syn_net") + 1, "syn_status")         # as R2 listed fx_unknown next to fx
O3.B0_TABLE["reconciliation"] = _rec
R2.EVENT_HOLES = {k: OT.remap(v) for k, v in R2.EVENT_HOLES.items()}
_lb1 = R2.localize_b1


def localize_b1(env, spec, bad, arch=None, first=()):
    holes, score = _lb1(env, spec, bad, arch, first)
    sc = Counter()
    for h, v in score.items():
        for m in OT.remap([h]):
            sc[m] += v
    rec = bad.get("reconciliation", (True, {}))[1]
    for e in rec.get("event_class", []):
        if str(e.get("want", "")).startswith("q:") or str(e.get("got", "")).startswith("q:"):
            sc["syn_status"] += 3.0
    for q in rec.get("quarantine_rows", []):
        sc["syn_status"] += 3.0
    return [h for h, s in sc.most_common() if s > 0], dict(sc)


O3.localize_b1 = localize_b1
RESYNTH_MAX_S = 160.0


def RESYNTH(op, env, holes, arch):
    hs = [h for h in holes if h in OT.SYNTH_HOLES]
    if not hs:
        return
    ex = X.merged(op.spec, [X.BUILD_ARCH.get(op.spec["project"], []), arch])   # build experience + operator archive
    for h in hs:
        cur = env.choice.get(h)
        if X.consistent(h, cur, ex):
            continue
        n0 = len(OT.DECISIONS[h])
        pid, st = X.synth_hole(h, ex, max_s=RESYNTH_MAX_S)
        op.cost["resyntheses"] = op.cost.get("resyntheses", 0) + 1
        op.ledger.append(dict(tick=env.t, kind="resynthesis", hole=h, previous=cur, new=pid,
                              new_option=len(OT.DECISIONS[h]) > n0, stats={k: v for k, v in st.items() if k != "per"}))


O3.RESYNTH = RESYNTH
NexusOpsSynth, run_ops, claims_healthy, monitors = O3.NexusOpsR1, O3.run_ops, O3.claims_healthy, O3.monitors_r1
OpsEnv, apply_comp, ORDER_C = O3.OpsEnvR1, O3.apply_comp, R2.ORDER_C
_ = (json, sys)
