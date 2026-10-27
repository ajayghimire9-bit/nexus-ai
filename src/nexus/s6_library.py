"""Stage 6 engineering-procedure library (NOT LOCKED). Learned ONLY from authorised source experience (NEXUS_Fresh runs on
de2/src); frozen before confirmation; no cross-test-project learning (observe() is a no-op once frozen).

Procedure kinds
  build    (decision -> option) with preconditions (data features the decision depends on), provenance (src projects),
           falsification evidence (src projects where another option failed a check), measured saving (CPU of the repair
           steps that changed this decision on src), and measured cost (retrieval + applicability per use, maintenance)
  ops      (symptom signature -> repair composition kinds), same bookkeeping (saving = shadow tests avoided x shadow CPU)
Admission / retirement: a procedure is kept only if its measured saving per use exceeds retrieval + applicability +
amortised maintenance, it has falsification evidence, its src evidence agrees, and its leave-one-out reuse on src never
failed (a failed reuse = the procedure's option was later rejected by a check). Using a procedure never removes a check: the
submitted configuration is still verified by the full suite. Placebo: the same number of procedures with the same
preconditions and permuted content (another option of the same decision; another signature's repair)."""
from __future__ import annotations

import json
import random
from collections import Counter

REL = {"commit_protocol": ["cdc"], "dedup": ["redelivery"], "apply_order": ["cdc"], "ts_parse": ["telemetry"],
       "gold_maintenance": ["cdc"], "lateness": ["telemetry"], "backfill_merge": ["backfill"],
       "schema_handling": ["registry_evolution"], "partition_discovery": ["partitioned"], "ts_format": ["telemetry"],
       "snapshots": ["cdc"], "fx": ["multi_currency"], "deletes": ["soft_delete_flag"], "malformed": ["manifests"]}


def features(spec, recs):
    f = set()
    topics = {t for t, p, r in recs}
    if "orders_cdc" in topics:
        f.add("cdc")
    if "backfill_orders" in topics:
        f.add("backfill")
    if "telemetry" in topics:
        f.add("telemetry")
    if "manifests" in topics:
        f.add("manifests")
    ids = Counter((t, r.get("msg_id")) for t, p, r in recs if t != "_schemas")
    if any(n > 1 for n in ids.values()):
        f.add("redelivery")
    if len({p for t, p, r in recs if t == "orders_cdc"}) > 1:
        f.add("partitioned")
    regs = [r for t, p, r in recs if t == "_schemas" and r.get("subject", "orders") == "orders"]
    if len(regs) > 1:
        f.add("registry_evolution")
    cur = {(r.get("after") or {}).get(spec["physical_names_v1"]["currency"]) for t, p, r in recs if t == "orders_cdc"}
    if len(cur - {None}) > 1:
        f.add("multi_currency")
    if spec.get("physical_names_v1", {}).get("deleted"):
        f.add("soft_delete_flag")
    return f


class Library:
    def __init__(self, procs=None, frozen=True, name="library"):
        self.procs, self.frozen, self.name = list(procs or []), frozen, name

    # --- use (all costs are measured by the caller)
    def retrieve(self, kind):
        return [p for p in self.procs if p["kind"] == kind and p.get("active", True)]

    def features(self, spec, recs):
        return features(spec, recs)

    def applicable(self, p, feats):
        return set(p["preconditions"]) <= feats

    def check_order(self):
        return None                                   # check ordering is not a learned procedure here (not claimed)

    def playbook(self, sig):
        key = "|".join(sig)
        for p in self.retrieve("ops"):
            if p["signature"] == key:
                return p["repair"]
        return None

    def observe(self, sig, comp):
        if not self.frozen:
            raise RuntimeError("online learning is disabled for this experiment")

    def to_json(self):
        return dict(name=self.name, frozen=self.frozen, procs=self.procs)

    @staticmethod
    def from_json(d):
        return Library(d["procs"], d.get("frozen", True), d.get("name", "library"))


def candidates(build_recs, ops_recs):
    """build_recs: NEXUS_Fresh build agent records on src (with history + per-step CPU and features);
    ops_recs: NEXUS_Fresh operator ledgers + costs on src."""
    procs = []
    accepted = [r for r in build_recs if r["outcome"] == "COMPLETED_VERIFIED"]
    for d, rel in REL.items():
        evid = [r for r in accepted if any(d in str(h.get("fix") or "").split("+") for h in r["history"])]
        if not evid:
            continue                                   # no falsification evidence on src: no procedure
        opts = Counter(r["final_choice"][d] for r in accepted if set(rel) <= set(r["features"]))
        o, n = opts.most_common(1)[0]
        saving = sum(sum(h.get("cpu_s", 0.0) for h in r["history"] if d in str(h.get("fix") or "").split("+")) for r in evid) / len(evid)
        procs.append(dict(id=f"build:{d}", kind="build", decision=d, option=o, preconditions=rel,
                          provenance=sorted(r["project"] for r in accepted), falsified_on=sorted(r["project"] for r in evid),
                          agreement=n / sum(opts.values()), est_saving_cpu_s=round(saving, 4), active=True))
    sigs = {}
    for rec in ops_recs:
        for e in rec["ledger"]:
            if e["kind"] in ("repaired", "partial_repair_waiting_for_source"):
                sigs.setdefault("|".join(e["signature"]), []).append((tuple(sorted(c[0] for c in e["repair"] if c[0] != "catch_up")),
                                                                     e.get("shadow_tests_before", 1), rec["project"]))
    for sig, obs in sigs.items():
        c = Counter(o[0] for o in obs)
        rep, n = c.most_common(1)[0]
        procs.append(dict(id=f"ops:{sig}", kind="ops", signature=sig, repair=list(rep), preconditions=[],
                          provenance=sorted({o[2] for o in obs}), agreement=n / len(obs),
                          est_saving_shadow_tests=round(sum(max(0, o[1] - 1) for o in obs) / len(obs), 3), active=True))
    return procs


def admit(procs, loo_failures, unit_costs, maintenance_cpu_s, expected_uses):
    """Admission / retirement rule (predeclared in the Stages 4-6 report section 0.6)."""
    per_use = unit_costs.get("retrieval_cpu_s", 0.0) + unit_costs.get("applicability_cpu_s", 0.0)
    maint = maintenance_cpu_s / max(1, len(procs)) / max(1, expected_uses)
    out = []
    for p in procs:
        p = dict(p)
        save = p.get("est_saving_cpu_s", p.get("est_saving_shadow_tests", 0.0) * unit_costs.get("shadow_cpu_s", 0.15))
        reasons = []
        if save <= per_use + maint:
            reasons.append(f"saving {save:.4f} <= cost {per_use + maint:.4f}")
        if p["agreement"] < 1.0:
            reasons.append(f"src evidence disagrees ({p['agreement']:.2f})")
        if loo_failures.get(p["id"], 0):
            reasons.append(f"failed reuse in leave-one-out ({loo_failures[p['id']]})")
        p["active"] = not reasons
        p["retired_because"] = reasons
        out.append(p)
    return out


def placebo(procs, seed="de2-placebo"):
    """Size-matched library with the same preconditions and permuted content."""
    from nexus import s4_template as T
    r = random.Random(seed)
    act = [p for p in procs if p.get("active")]
    ops = [p for p in act if p["kind"] == "ops"]
    reps = [p["repair"] for p in ops]
    r.shuffle(reps)
    if len(reps) > 1 and any(a == b["repair"] for a, b in zip(reps, ops)):
        reps = reps[1:] + reps[:1]
    out = []
    for p in act:
        q = dict(p, id="placebo:" + p["id"])
        if p["kind"] == "build":
            others = [o for o in T.DECISIONS[p["decision"]] if o != p["option"]]
            q["option"] = r.choice(others)
        else:
            q["repair"] = reps[ops.index(p)] if reps else p["repair"]
        out.append(q)
    return out
