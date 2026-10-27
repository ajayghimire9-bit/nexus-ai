"""R2 operations (NOT LOCKED). The R1 operations code (r1_ops, unchanged) loaded as a SEPARATE module from its source with
exact, asserted patches, then rebound:
  * template = r2_template (18 decisions); reconciliation = r2_reconcile (event-level); spec derivations for shrunk traces use
    the de4 rules (r2_reconcile.derive_silver)
  * B1 considers the top 6 typed holes (R1: 4; set before any R2 comparison)
  * typed evidence extended with the event-level fields, for B1 AND the Fixed_Policy runbook (same knowledge):
      event / quarantine class want unknown_currency -> fx_unknown; want duplicate got accepted, or a bronze multiplicity > 1
      -> dedup; want aborted / pending -> txn_isolation; want malformed -> malformed; orders content -> decode-stage
      decisions; telemetry content -> ts_parse / ts_format; feature "record names a registry version first registered after
      the build window" -> decode-stage decisions
  * B0's authored table lists the two new decisions next to their neighbours (discount_unit after schema_handling,
    fx_unknown after fx), as any template extension would
  * localisation uses the evidence observed AFTER the relaxed incident composition when one exists (CEGIS on the
    counterexample with the incident removed); R1 merged it only for monitors not already failing
  * comparison C: an ordering hook over the verified candidates (C0 = identity, the fallback; C1 = cheap contextual stage /
    lineage order; C2 = cost / information-gain HEURISTIC: estimated fix probability / estimated verification cost - not IDS);
    its CPU is inside localisation CPU, which is charged"""
from __future__ import annotations

import importlib.util
import sys
from collections import Counter

from nexus import r1_ops as _R1O
from nexus import r2_reconcile as R2R
from nexus import r2_template as RT2
from nexus import s4_checks as _C

PATCHES = [
    ("from nexus import r1_template as RT\n", "from nexus import r2_template as RT\n"),
    ("            holes = suspects[:4]\n", "            holes = suspects[:6]\n"),
    ("""        self.cost["localisation_cpu_s"] += _cpu() - a
        full = 0""", """        survivors = ORDER_C(self, env, survivors, scores, bad)
        self.cost["localisation_cpu_s"] += _cpu() - a
        full = 0"""),
    ("""            self._shadow_bad = {}
            mons = self._mons(env)""", """            self._shadow_bad, self._shadow_mons = {}, {}
            mons = self._mons(env)"""),
    ("""        for k, v in mons.items():
            if k in PIPELINE_SUSPECT and not v[0]:
                getattr(self, "_shadow_bad", {}).setdefault(k, v)""", """        for k, v in mons.items():
            if k in PIPELINE_SUSPECT and not v[0]:
                getattr(self, "_shadow_bad", {}).setdefault(k, v)
        getattr(self, "_shadow_mons", {})[json.dumps(comp, sort_keys=True, default=str)] = mons"""),
    ("""                chosen = self._repair_pipeline(env, sig, dict(bad, **shadow_bad), relaxed)""",
     """                # R2: localise on the counterexample observed AFTER the relaxed incident composition (its shadow), where
                # the incident's own symptoms are removed; otherwise on the real + shadow evidence (R1)
                loc_bad = {k: v for k, v in self._shadow_mons.get(json.dumps(relaxed, sort_keys=True, default=str), {}).items() if not v[0] and k != "drift"} if relaxed else {}
                chosen = self._repair_pipeline(env, sig, loc_bad or dict(bad, **shadow_bad), relaxed)"""),
    ("""                alt = next(o for o in RT.DECISIONS[hole] if o != env.choice[hole])""",
     """                alt = SRC_ALT(self, hole, env.choice[hole])"""),
]


def _load():
    src = open(_R1O.__file__).read()
    for a, b in PATCHES:
        if src.count(a) != 1:
            raise RuntimeError(f"R2 ops patch anchor not found exactly once: {a[:60]!r}")
        src = src.replace(a, b)
    spec = importlib.util.spec_from_loader("nexus._r2_ops_core", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = _R1O.__file__
    exec(compile(src, _R1O.__file__ + "[r2-patched]", "exec"), mod.__dict__)
    return mod


O2 = _load()
C2 = type(sys)("nexus._r2_checks_shim")
C2.__dict__.update({k: v for k, v in _C.__dict__.items() if not k.startswith("__")})
C2.derive_silver = R2R.derive_silver
O2.C = C2
O2.reconcile = R2R.reconcile
O2.B0_TABLE = dict(O2.B0_TABLE)
_rec = list(O2.B0_TABLE["reconciliation"])
_rec.insert(_rec.index("schema_handling") + 1, "discount_unit")
_rec.insert(_rec.index("fx") + 1, "fx_unknown")
O2.B0_TABLE["reconciliation"] = _rec
DECODE = [d for d in RT2.DECISIONS if RT2.STAGE_OF[d] == "decode"]
O2.FEAT_HOLES = dict(O2.FEAT_HOLES, new_schema=DECODE)

_features_r1 = O2._features
_localize_b1_r1 = O2.localize_b1


def _features(keys, arch, obs):
    out = _features_r1(keys, arch, obs)
    late = {(r["subject"], r["version"]) for r in obs["registry"] if r["tick"] > 8}
    for tp, p, o, r, tk in arch:
        if r and r.get("key") in out and tp in ("orders_cdc", "backfill_orders") and ("orders", r.get("schema_version", 1)) in late:
            out[r["key"]].add("new_schema")
    return out


EVENT_HOLES = {"q:unknown_currency": ["fx_unknown"], "duplicate": ["dedup"], "aborted": ["txn_isolation"],
               "pending": ["txn_isolation"], "q:malformed_weight": ["malformed"]}


def localize_b1(env, spec, bad, arch=None, first=()):
    holes, score = _localize_b1_r1(env, spec, bad, arch, first)
    score = Counter(score)
    rec = bad.get("reconciliation", (True, {}))[1]
    for e in rec.get("event_class", []) + [dict(want=f"q:{q['row'][2]}") for q in rec.get("quarantine_rows", []) if q["want"] > q["got"]]:
        for h in EVENT_HOLES.get(e.get("want"), []):
            score[h] += 3.0
        if e.get("want") == "duplicate" and e.get("got") == "accepted":
            score["dedup"] += 3.0
    for m in rec.get("multiplicity", []):
        if m["got"] > 1:
            score["dedup"] += 3.0
    for c in rec.get("content", []):
        for h in (DECODE if c["table"] == "orders" else ["ts_parse", "ts_format"] if c["table"] == "telemetry" else []):
            score[h] += 1.0
    return [h for h, s in score.most_common() if s > 0], dict(score)


O2._features = _features
O2.localize_b1 = localize_b1

STAGE_TABLES = {"silver": {"silver_mismatch", "content", "event_class", "quarantine_rows", "multiplicity"},
                "decode": {"silver_mismatch", "content", "late_mismatch"}, "ingest": {"event_class", "quarantine_rows", "multiplicity",
                                                                                       "accounting"},
                "read": {"coverage"}, "commit": {"coverage"}, "gold": {"sla_mismatch", "volume_mismatch", "late_mismatch"},
                "snapshot": set()}


def ORDER_C(op, env, cands, scores, bad):
    mode = getattr(op, "c_mode", "C0")
    if mode == "C0" or len(cands) < 2:
        return cands
    rec = bad.get("reconciliation", (True, {}))[1]
    failing = {k for k, v in rec.items() if v and k in {x for s in STAGE_TABLES.values() for x in s}}
    stages = [O2.stage_holes(env)]
    if mode == "C1":
        def key(c):
            st = {RT2.STAGE_OF[d] for d, o in c}
            hit = any(failing & STAGE_TABLES.get(s, set()) for s in st) or any(d in stages[0] for d, o in c)
            return (0 if hit else 1, len(c))
        return sorted(cands, key=key)
    # C2: estimated fix probability (normalised suspect score; B0: rank prior) / estimated verification cost (rollback depth
    # in ticks to replay + 1, x2 for a pair)
    tot = sum(scores.values()) or 1.0
    order = {c: i for i, c in enumerate(cands)}
    onset = O2._onset(env, bad, O2._archive(env))
    depth = max(1, env.t - max([s for s in env.snapshots() if s < onset] or [0]))

    def ratio(c):
        p = sum(scores.get(d, 0.0) for d, o in c) / tot if scores else 1.0 / (1 + order[c])
        cost = (depth + 1) * (2 if len(c) > 1 else 1) * len(RT2.DECISIONS[c[0][0]])
        return -p / cost
    return sorted(cands, key=ratio)


O2.ORDER_C = ORDER_C


def SRC_ALT(op, d, cur):
    """Fixed_Policy's typed redeploy option: the most frequent src option of that decision other than the current one
    (src experience: artifacts/r2_library.json option_counts); the first alternative when src has no evidence."""
    cnt = getattr(op, "src_counts", {}).get(d, {})
    alts = [o for o in RT2.DECISIONS[d] if o != cur]
    return max(alts, key=lambda o: (cnt.get(o, 0), -alts.index(o)))


O2.SRC_ALT = SRC_ALT
NexusOpsR2, FixedPolicyOps, run_ops, claims_healthy, monitors = (O2.NexusOpsR1, O2.FixedPolicyOps, O2.run_ops, O2.claims_healthy,
                                                                 O2.monitors_r1)
OpsEnv, apply_comp = O2.OpsEnvR1, O2.apply_comp
