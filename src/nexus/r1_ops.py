"""R1 operations (NOT LOCKED; semantic harness + operators). Builds on s5_ops (unchanged).

OpsEnvR1 runs the arm's OWN submitted pipeline (its bundle copy) on the live log (retention, publication delays, incidents)
and keeps, for operators only, a read-only ARCHIVE of every published segment (tiered storage) and the authoritative
observations log/_obs/tick_k.json. New authorised action: redeploy(decisions) - a change of the operator's own pipeline
inside the template's repair language. Lag (and so service) is measured against the OBSERVED contiguous-available end: a
consumer waiting at an offset hole is not lagging.

monitors_r1 = the Stage 5 monitors + observation_conformance (r1_monitor.check_consumer: acks vs observed offsets and durable
consumption, aborted / open transaction records applied) + reconciliation:
    coverage   every open observed partition consumed up to its contiguous-available end; nothing below a committed offset
               missing from the durable consumption ledger
    output     silver (key, warehouse, status, net) and late_events re-derived PER THE SPEC by NEXUS code from the archived
               records below the committed offsets (redeliveries ignored by msg_id, only committed transactions, undecodable
               lines skipped), compared with the pipeline's tables (gold is reconciled by the Stage 5 gold monitor)
An incident counts as resolved only when reconciliation passes in the shadow AND after the real application.

NexusOpsR1: the Stage 5 incident search (diagnose -> compositions -> shadow tests, two-round deepening), with
  * per-turn shadow cap 40 and per-run cap 200 (code == protocol);
  * own-pipeline repair when the remaining symptoms are pipeline-suspect (reconciliation / conformance / coverage):
      B0  the existing search strategy: decisions implicated by the failing monitor (authored table) first, then every
          other decision; every alternative option tested by a full shadow verification (redeploy + rollback + replay)
      B1  provenance-assisted localisation (features of the counterexample's archived source records contrasted with
          agreeing keys, plus typed observation violations -> typed holes) + failure-trace shrinking (ddmin over the
          counterexample keys keeping causal dependencies: registry records, snapshot / transaction controls, per-partition
          order) + typed CEGIS (each candidate is checked first on the shrunk counterexample traces; only survivors get a
          full shadow verification; a failed full verification adds its counterexample). At most 12 full verifications.
FixedPolicyOps: the same monitors and reconciliation, a fixed canonical runbook (all diagnosed primitives at once, no shadow
search), one typed redeploy attempt (top suspect, first alternative) per signature, else escalate."""
from __future__ import annotations

import itertools
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from nexus import r1_env as RE
from nexus import r1_monitor as M
from nexus import r1_template as RT
from nexus import s4_checks as C
from nexus import s5_incidents as I
from nexus import s5_ops as O

PER_TURN_SHADOW, PER_RUN_SHADOW, MAX_FULL = 40, 200, 12
_cpu = O._cpu


# ------------------------------------------------------------------------------------------------ environment
class OpsEnvR1(O.OpsEnv):
    def __init__(self, enc, incs, work, bundle, profile=None, choice=None):
        super().__init__(enc, incs, work, bundle, profile)
        b = self.root / "bundle"
        b.mkdir(exist_ok=True)
        shutil.copy(Path(bundle) / "pipeline.py", b / "pipeline.py")
        self.bundle, self.arch, self.choice = b, self.root / "archive", dict(choice or {})

    def clone(self, dst):
        c = super().clone(dst)
        c.__class__ = OpsEnvR1                       # the base clone constructs a plain OpsEnv
        c.bundle, c.arch, c.choice = c.root / "bundle", c.root / "archive", dict(self.choice)
        return c

    def advance(self):
        self.t += 1
        t = self.t
        RE.write_tick(self.enc, self.root, t)
        RE.write_tick(self.enc, self.arch, t)
        RE.retention(self.root, t)
        for inc in self.incs:
            inc.on_tick_start(t, self.rt)
        self._mirror(t)
        self.runs_this_tick = 0
        self.logs[t] = list(self.rt.pop("events", []) if "events" in self.rt else [])
        return self.run_now()

    def _mirror(self, t):
        RE.partition_states(self.root, t)
        a = RE.Obs(self.arch)
        have = {json.dumps(e, sort_keys=True) for e in a.events() if e["ev"] == "partition_state"}
        for e in RE.Obs(self.root).events():
            if e["ev"] == "partition_state" and json.dumps(e, sort_keys=True) not in have:
                a.event(**e)
        a.materialize(t)

    def obs(self):
        return M.load_obs(Path(self.rt["log"]), self.t)

    def request_resnapshot(self, topic="backfill_orders"):
        inc = next((i for i in self.incs if i.name == "snapshot_interrupted"), None)
        self.actions.append(("request_resnapshot", topic))
        if inc is None or getattr(self, "_resnap_done", False):
            self.logs[self.t].append("source: snapshot requested; no snapshot outstanding")
            return
        recs = inc.resnapshot(self.enc, self.t)
        o = self.obs()
        start = o["offsets"].get(f"{topic}/0", {}).get("log_end", 10 ** 5)
        RE.append_records(self.root, topic, 0, [dict(x) for x in recs], start, self.t)
        RE.append_records(self.arch, topic, 0, [dict(x) for x in recs], start, self.t)
        self._resnap_done = True

    def redeploy(self, choice):
        diff = {d: o for d, o in choice.items() if self.choice.get(d) != o}
        self.choice = dict(choice)
        (self.bundle / "pipeline.py").write_text(RT.emit(self.choice))
        self.actions.append(("redeploy", diff))

    def metrics(self):
        st = Path(self.rt["state"])
        off = O._offsets(st)
        lag = {}
        try:
            o = self.obs()
        except (OSError, ValueError):
            o = None
        if o is not None:
            open_ = {(p["topic"], p["part"]) for p in o["partitions"] if p["state"] == "open"}
            for key, v in o["offsets"].items():
                t, p = key.rsplit("/", 1)
                if (t, int(p)) in open_ and v["contiguous_end"] - off.get((t, int(p)), 0) > 0:
                    lag[f"{t}/{p}"] = v["contiguous_end"] - off.get((t, int(p)), 0)
        last = self.history[-1] if self.history else {}
        return dict(tick=self.t, lag=lag, last_exit=last.get("exit"), last_consumed=last.get("consumed"),
                    state_bytes=sum(f.stat().st_size for f in st.rglob("*") if f.is_file()))


# ------------------------------------------------------------------------------------------------ reconciliation
def _archive(env):
    """[(topic, part, offset, record or None (undecodable), record_tick)] of every archived published segment."""
    out = []
    o = M.load_obs(env.arch / "log", env.t)
    for s in o["segments"]:
        f = env.arch / "log" / s["topic"] / f"p{s['part']}" / f"{s['base']:08d}.jsonl"
        if not f.exists():
            continue
        for i, l in enumerate(x for x in f.read_text().split("\n") if x):
            try:
                r = json.loads(l)
            except ValueError:
                r = None
            out.append((s["topic"], s["part"], s["base"] + i, r, s["tick"]))
    return out


def _prefix(env, arch=None):
    com = M._committed(env.rt["state"])
    arch = _archive(env) if arch is None else arch
    pre = [x for x in arch if x[2] < com.get((x[0], x[1]), 0)]
    committed = {r["txn_id"] for tp, p, o, r, tk in pre if r and r.get("control") == "txn_commit"}
    keep = []
    for tp, p, o, r, tk in pre:
        if r is None:
            continue
        if r.get("txn_id") and "control" not in r and r["txn_id"] not in committed:
            continue
        keep.append((tp, p, r))
    return keep, com, arch


def derive(spec, keep):
    return C.derive_silver(spec, keep), C.derive_late(spec, keep)


def derive_accounting(pre):
    """Per (topic, status) counts the spec implies for the consumed prefix [(topic, part, offset, record|None)]:
    first copy of a msg_id -> its class (applied / quarantined malformed, future or undecodable / aborted / pending), later
    copies -> duplicate; registry records are not accounted (the template's declared scope)."""
    fin = {}
    for tp, p, o, r in pre:
        if r and str(r.get("control", "")).startswith("txn_"):
            fin[r["txn_id"]] = r["control"]
    acc, seen = Counter(), set()
    for tp, p, o, r in pre:
        if tp == "_schemas":
            continue
        if r is None:
            acc[(tp, "quarantined")] += 1
            continue
        if (tp, r.get("msg_id")) in seen:
            acc[(tp, "duplicate")] += 1
            continue
        seen.add((tp, r.get("msg_id")))
        if r.get("txn_id") and "control" not in r:
            acc[(tp, {"txn_commit": "applied", "txn_abort": "aborted"}.get(fin.get(r["txn_id"]), "pending"))] += 1
        elif tp == "telemetry" and (C.utc(r["event_ts"]) - C.utc(r["ingest_ts"])).total_seconds() > 300:
            acc[(tp, "quarantined")] += 1
        elif tp == "manifests" and not isinstance(r.get("weight"), (int, float)):
            acc[(tp, "quarantined")] += 1
        else:
            acc[(tp, "applied")] += 1
    return acc


def derive_gold(spec, silver, keep, late, overrides):
    """gold_sla and gold_supplier_volume per the spec rules, from the derived silver and the consumed prefix."""
    sla, first = {}, {}
    tel, seen = [], set()
    for tp, p, r in keep:
        if tp == "telemetry" and r["msg_id"] not in seen:
            seen.add(r["msg_id"])
            tel.append(r)
    for r in sorted(tel, key=lambda r: r["msg_id"]):
        if r["type"] != "DELIVERED" or r["msg_id"] in late or r["order_id"] not in silver or r["order_id"] in first:
            continue
        et = C.utc(r["event_ts"])
        if (et - C.utc(r["ingest_ts"])).total_seconds() > 300:
            continue
        first[r["order_id"]] = r
        o = silver[r["order_id"]]
        d, n = sla.get(o[1], (0, 0))
        sla[o[1]] = (d + 1, n + (et <= C.utc(o[4])))
    vol, seen = {}, set()
    for tp, p, r in keep:
        if tp != "manifests" or r["msg_id"] in seen:
            continue
        seen.add(r["msg_id"])
        if not isinstance(r.get("weight"), (int, float)):
            continue
        kg = r["weight"]
        for ov in overrides:
            if ov["supplier"] == r["supplier"] and r["offset"] >= ov["from_offset"] and p == ov.get("part", 0):
                kg *= ov["factor"]
        o = silver.get(r["order_id"])
        if o and o[2] != "CANCELLED":
            vol[(o[1], r["supplier"])] = vol.get((o[1], r["supplier"]), 0.0) + kg
    return ({w: (d, n, round(n / d, 4)) for w, (d, n) in sla.items()}, {k: round(v, 3) for k, v in vol.items()})


def reconcile(env, spec):
    keep, com, arch = _prefix(env)
    st = Path(env.rt["state"])
    ev = dict(silver_mismatch=[], late_mismatch=0, coverage=[], accounting=[], sla_mismatch=0, volume_mismatch=0)
    last_ok = (env.history[-1].get("exit") == 0) if env.history else True
    try:
        o = env.obs()
        for p in o["partitions"]:
            key = f"{p['topic']}/{p['part']}"
            c = com.get((p["topic"], p["part"]), 0)
            if p["state"] == "open" and o["offsets"].get(key, {}).get("contiguous_end", 0) > c:
                ev["coverage"].append(dict(kind="partition_not_consumed" if c == 0 and last_ok else "lag" if last_ok else "lag_after_failed_run",
                                           where=key, behind=o["offsets"][key]["contiguous_end"] - c))
        ev["coverage"] += [dict(kind=v["kind"], where=v["where"]) for v in M.check_consumer(st, o) if v["kind"] == "ack_beyond_durable"]
    except (OSError, ValueError):
        pass
    tabs = C.tables(st, spec)
    if not tabs.get("silver_orders") and not keep:
        return (not ev["coverage"], ev)
    want_s, want_l = derive(spec, keep)
    got = {r[0]: r for r in (tabs.get("silver_orders") or [])}
    for k in sorted(set(want_s) | set(got)):
        w, g = want_s.get(k), got.get(k)
        if w is None or g is None or w[2] != g[2] or w[1] != g[1] or abs(w[3] - g[3]) > 0.011:
            ev["silver_mismatch"].append(k)
    got_l = {r[0] for r in (tabs.get("late_events") or [])}
    ev["late_mismatch"] = len(want_l ^ got_l)
    pre = [(tp, p, o_, r) for tp, p, o_, r, tk in arch if o_ < com.get((tp, p), 0)]
    want_a = derive_accounting(pre)
    got_a = Counter({(t, s_): n for t, s_, n in (tabs.get("record_accounting") or []) if s_ != "late"})
    ev["accounting"] = [dict(topic=t, status=s_, want=want_a.get((t, s_), 0), got=got_a.get((t, s_), 0))
                        for t, s_ in sorted(set(want_a) | set(got_a)) if want_a.get((t, s_), 0) != got_a.get((t, s_), 0)]
    sla, vol = derive_gold(spec, want_s, keep, want_l, env.cfg["deploy"].get("unit_overrides", []))
    g_sla = {r[0]: r[1:] for r in (tabs.get("gold_sla") or [])}
    ev["sla_mismatch"] = sum(1 for w in set(sla) | set(g_sla) if sla.get(w) is None or g_sla.get(w) is None or
                             sla[w][0] != g_sla[w][0] or sla[w][1] != g_sla[w][1])
    g_vol = {(r[0], r[1]): r[2] for r in (tabs.get("gold_supplier_volume") or [])}
    ev["volume_mismatch"] = sum(1 for k in set(vol) | set(g_vol) if vol.get(k) is None or g_vol.get(k) is None or
                                abs(vol[k] - g_vol[k]) > 0.0021)
    ok = not (ev["silver_mismatch"] or ev["late_mismatch"] or ev["coverage"] or ev["accounting"] or ev["sla_mismatch"]
              or ev["volume_mismatch"])
    ev["silver_mismatch"] = ev["silver_mismatch"][:200]
    return ok, ev


def consistency_first_copy(env):
    """s5_ops.consistency judged on the FIRST delivered copy of each msg_id only (the copy the pipeline applies; later copies
    are duplicates by the identity rule even when a faulty producer changed their payload). R1 revision after val (dev log)."""
    st = Path(env.rt["state"]) / "lake.db"
    if not st.exists():
        return (True, {})
    dep = env.cfg["deploy"]
    try:
        con = sqlite3.connect(f"file:{st}?mode=ro", uri=True)
        man = dict(con.execute("SELECT msg_id, kg FROM bronze_man").fetchall())
        fut = dict(con.execute("SELECT msg_id, future FROM bronze_tel").fetchall())
        con.close()
    except sqlite3.Error:
        return (True, {})
    first = {}
    for topic in ("manifests", "telemetry"):
        for d in Path(env.rt["log"]).glob(f"{topic}/p*"):
            if not os.access(d, os.R_OK):
                continue
            part = int(d.name[1:])
            for f in d.glob("*.jsonl"):
                for l in f.read_text().splitlines():
                    try:
                        x = json.loads(l)
                    except ValueError:
                        continue
                    k = (topic, x.get("msg_id"))
                    if k not in first or (x["ingest_ts"], part, x["offset"]) < first[k][0]:
                        first[k] = ((x["ingest_ts"], part, x["offset"]), part, x)
    bad = []
    for (topic, mid), (_, part, x) in first.items():
        tk = E_tick(x["ingest_ts"])
        if topic == "manifests" and mid in man and isinstance(x.get("weight"), (int, float)):
            kg = x["weight"]
            for ov in dep.get("unit_overrides", []):
                if ov["supplier"] == x["supplier"] and x["offset"] >= ov["from_offset"] and part == ov.get("part", 0):
                    kg *= ov["factor"]
            if abs(kg - man[mid]) > 1e-6:
                bad.append(tk)
        if topic == "telemetry" and mid in fut and dep.get("future_guard"):
            want = int((C.utc(x["event_ts"]) - C.utc(x["ingest_ts"])).total_seconds() > 300)
            if want != fut[mid]:
                bad.append(tk)
    return (not bad, dict(inconsistent_records=len(bad), earliest_tick=min(bad) if bad else None))


def E_tick(ingest):
    return RE.E.tick_of(RE.E.datetime.fromisoformat(ingest.replace("Z", "+00:00")))


def monitors_r1(env, spec, detector=None, det_state=None):
    out = O.monitors(env, detector, det_state)
    if "config_state_consistency" in out:
        out["config_state_consistency"] = consistency_first_copy(env)
    try:
        v = M.check_consumer(env.rt["state"], env.obs())
    except (OSError, ValueError):
        v = []
    out["observation_conformance"] = (not v, dict(violations=v[:20]))
    out["reconciliation"] = reconcile(env, spec)
    return out


PIPELINE_SUSPECT = ("reconciliation", "observation_conformance", "integrity", "gold_recompute", "accounting", "watermark_sanity")


def apply_comp(env, comp):
    """s5_ops.apply_composition plus redeploy (applied before resnapshot / rollback / catch-up)."""
    rest = []
    for name, arg in comp:
        if name == "redeploy":
            env.redeploy(arg)
        else:
            rest.append((name, arg))
    return O.apply_composition(env, rest)


# ------------------------------------------------------------------------------------------------ localisation
VIOL_HOLES = {"txn_effect_violation": ["txn_isolation"], "ack_beyond_available": ["gap_handling"],
              "ack_beyond_durable": ["gap_handling", "commit_protocol"], "partition_not_consumed": ["partition_discovery"],
              }
FEAT_HOLES = {"txn": ["txn_isolation"], "dup_msg": ["dedup"], "sv_out_of_order": ["apply_order"], "backfill": ["backfill_merge"],
              "schema_v2plus": ["schema_handling"], "float_discount": ["schema_handling"], "non_usd": ["fx"],
              "soft_delete": ["deletes"], "hard_delete": ["deletes", "backfill_merge"], "late_partition": ["partition_discovery"],
              "in_hole": ["gap_handling"], "late_tel": ["lateness", "ts_parse", "ts_format"]}
ACC_HOLES = {(t, "duplicate"): ["dedup"] for t in ("orders_cdc", "backfill_orders", "telemetry", "manifests")}
ACC_HOLES.update({("orders_cdc", "aborted"): ["txn_isolation"], ("orders_cdc", "pending"): ["txn_isolation"],
                  ("manifests", "quarantined"): ["malformed"], ("manifests", "dropped"): ["malformed"]})
B0_TABLE = {"reconciliation": C.IMPLICATE["silver_rederivation"] + ["lateness", "ts_parse", "ts_format", "dedup",
                                                                     "partition_discovery", "commit_protocol"],
            "observation_conformance": ["commit_protocol", "partition_discovery"], "integrity": ["dedup", "commit_protocol"],
            "gold_recompute": ["gold_maintenance"], "accounting": ["malformed", "dedup"],
            "watermark_sanity": ["ts_parse", "ts_format", "lateness"]}


def _features(keys, arch, obs):
    """Per key: the features of its archived source records (provenance)."""
    holes = set()
    for key, v in obs["offsets"].items():
        if v["contiguous_end"] < v["log_end"]:
            holes.add(key)
    created = {(p["topic"], p["part"]): p["created"] for p in obs["partitions"]}
    by = {}
    for tp, p, o, r, tk in arch:
        if r and tp in ("orders_cdc", "backfill_orders") and "control" not in r and r.get("key") in keys:
            by.setdefault(r["key"], []).append((tp, p, o, r, tk))
    seen = Counter((tp, r.get("msg_id")) for tp, p, o, r, tk in arch if r)
    out = {}
    for k, recs in by.items():
        f = set()
        arr = [r["source_version"] for tp, p, o, r, tk in sorted(recs, key=lambda x: (x[4], x[2]))]
        if arr != sorted(arr):
            f.add("sv_out_of_order")
        for tp, p, o, r, tk in recs:
            if r.get("txn_id"):
                f.add("txn")
            if seen[(tp, r.get("msg_id"))] > 1:
                f.add("dup_msg")
            if tp == "backfill_orders":
                f.add("backfill")
            if r.get("schema_version", 1) >= 2:
                f.add("schema_v2plus")
            a = r.get("after") or {}
            if any(isinstance(v, float) and v != int(v) and v < 100 for v in a.values()):
                f.add("float_discount")
            if any(v in ("EUR", "GBP", "CHF") for v in a.values()):
                f.add("non_usd")
            if r.get("op") == "d":
                f.add("hard_delete")
            if any(v == 1 for kk, v in a.items() if kk in ("is_deleted", "deleted", "void_flag")):
                f.add("soft_delete")
            if created.get((tp, p), 1) > 1:
                f.add("late_partition")
            if f"{tp}/{p}" in holes:
                f.add("in_hole")
        out[k] = f
    return out


def localize_b1(env, spec, bad, arch=None, first=()):
    """Ranked typed holes with their evidence weights (contrast of counterexample vs agreeing keys + typed violations)."""
    arch = _archive(env) if arch is None else arch
    obs = env.obs()
    score = Counter({h: 2.0 for h in first})
    for v in bad.get("observation_conformance", (True, {}))[1].get("violations", []):
        for h in VIOL_HOLES.get(v["kind"], []):
            score[h] += 3.0
    rec = bad.get("reconciliation", (True, {}))[1]
    for c in rec.get("coverage", []):
        for h in VIOL_HOLES.get(c["kind"], []):
            score[h] += 2.0
    for a in rec.get("accounting", []):
        for h in ACC_HOLES.get((a["topic"], a["status"]), []):
            score[h] += 3.0
    if rec.get("sla_mismatch") or rec.get("volume_mismatch"):
        for h in ("dedup", "gold_maintenance"):
            score[h] += 0.5
    mism = set(rec.get("silver_mismatch", []))
    if mism:
        allk = {r["key"] for tp, p, o, r, tk in arch if r and tp in ("orders_cdc", "backfill_orders") and "control" not in r}
        agree = sorted(allk - mism)
        feats = _features(mism | set(agree), arch, obs)
        for f in FEAT_HOLES:
            fm = sum(f in feats.get(k, set()) for k in mism) / max(1, len(mism))
            fa = sum(f in feats.get(k, set()) for k in agree) / max(1, len(agree))
            if fm - fa > 0.05:
                for h in FEAT_HOLES[f]:
                    score[h] += fm - fa
    if rec.get("late_mismatch"):
        for h in FEAT_HOLES["late_tel"]:
            score[h] += 1.0
    if not bad.get("gold_recompute", (True,))[0]:
        score["gold_maintenance"] += 1.0
    if not bad.get("watermark_sanity", (True,))[0]:
        for h in ("ts_parse", "ts_format"):
            score[h] += 1.0
    return [h for h, s in score.most_common() if s > 0], dict(score)


def stage_holes(env):
    """Decisions of the pipeline stage a failed run names (StageError stage=X), as in the Stage 4 attribution."""
    err = (env.history[-1].get("err", "") if env.history and env.history[-1].get("exit") not in (0, None) else "")
    if "stage=" not in err:
        return []
    st = err.split("stage=")[1].split()[0]
    return [d for d in RT.DECISIONS if RT.STAGE_OF[d] == st]


def localize_b0(bad, first=()):
    order = list(first)
    for name in PIPELINE_SUSPECT:
        if name in bad:
            order += [d for d in B0_TABLE.get(name, []) if d not in order]
    return order + [d for d in RT.DECISIONS if d not in order]


def _onset(env, bad, arch):
    ticks = [v.get("tick") for v in bad.get("observation_conformance", (True, {}))[1].get("violations", []) if v.get("tick")]
    mism = set(bad.get("reconciliation", (True, {}))[1].get("silver_mismatch", []))
    ticks += [tk for tp, p, o, r, tk in arch if r and r.get("key") in mism and tp in ("orders_cdc", "backfill_orders")]
    for c in bad.get("reconciliation", (True, {}))[1].get("coverage", []):
        if c["kind"] == "partition_not_consumed":
            t, p = c["where"].rsplit("/", 1)
            ticks += [next((pp["created"] for pp in env.obs()["partitions"] if pp["topic"] == t and pp["part"] == int(p)), 1)]
    return min(ticks) if ticks else env.t


def _rollback_tail(env, onset):
    """Rollback to the last snapshot before the onset; else, if no segment has expired yet (the whole log is retained),
    rollback 0 = reset and replay everything; else no rollback (the repair can then only be verified, not replayed)."""
    snaps = [s for s in env.snapshots() if s < onset]
    if snaps:
        return (("rollback", snaps[-1]), ("catch_up", None))
    o = env.obs()
    if all(s["expires"] > env.t for s in o["segments"]):
        return (("rollback", 0), ("catch_up", None))
    return (("catch_up", None),)


def shrink_trace(env, spec, keys, arch, work, runner, choice, max_tests=8):
    """ddmin over counterexample keys: the smallest key set whose mini-trace (those keys' archived records + causal
    dependencies, per-partition order and ticks preserved, offsets re-laid densely) still makes `choice` disagree with the
    spec derivation. Returns (keys, mini_log_dir) or (None, None) when the mini-trace does not reproduce the failure."""
    tests = [0]

    def mini(ks, d):
        sel = []
        txns = {r["txn_id"] for tp, p, o, r, tk in arch if r and r.get("key") in ks and r.get("txn_id")}
        for tp, p, o, r, tk in arch:
            if r is None:
                continue
            if tp == "_schemas" or (tp in ("orders_cdc", "backfill_orders") and (r.get("key") in ks or
                                                                                   r.get("txn_id") in txns or
                                                                                   str(r.get("control", "")).startswith("snapshot"))):
                sel.append((tp, p, o, r, tk))
        d = Path(d)
        if d.exists():
            shutil.rmtree(d)
        segs = {}
        for tp, p, o, r, tk in sorted(sel, key=lambda x: (x[0], x[1], x[2])):
            segs.setdefault((tp, p), []).append((tk, r))
        written = []
        for (tp, p), items in segs.items():
            (d / tp / f"p{p}").mkdir(parents=True, exist_ok=True)
            by = {}
            for i, (tk, r) in enumerate(items):
                by.setdefault(tk, []).append(dict(r, offset=i))
            for tk, rs in by.items():
                (d / tp / f"p{p}" / f"{rs[0]['offset']:08d}.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in rs))
                written.append((tp, p, rs[0]["offset"], rs[-1]["offset"] + 1, tk))
        _mini_obs(d, written, env.t)
        return d

    def fails(ks, ch, tag):
        tests[0] += 1
        d = mini(ks, work / f"mini_{tag}")
        want = C.derive_silver(spec, _mini_recs(d))
        got = run_mini(d, ch, spec, work / f"st_{tag}", runner, env.t)
        return any(want.get(k, (None,) * 4)[:4] != got.get(k, (None,) * 4)[:4] and
                   not (k in want and k in got and want[k][2] == got[k][2] and abs(want[k][3] - got[k][3]) <= 0.011)
                   for k in ks), d

    ks = sorted(keys)[:40]
    ok, d = fails(ks, choice, "full")
    if not ok:
        return None, None, tests[0]
    n = 2
    while len(ks) >= 2 and tests[0] < max_tests:
        chunk = max(1, len(ks) // n)
        reduced = False
        for i in range(0, len(ks), chunk):
            sub = ks[i:i + chunk]
            if tests[0] >= max_tests:
                break
            ok, dd = fails(sub, choice, f"s{tests[0]}")
            if ok:
                ks, d, n, reduced = sub, dd, 2, True
                break
        if not reduced:
            if n >= len(ks):
                break
            n = min(len(ks), n * 2)
    return ks, d, tests[0]


def _mini_obs(d, written, upto):
    obs = RE.Obs(Path(d).parent / f"_obs_{Path(d).name}")
    if obs.j.exists():
        obs.j.unlink()
    for x in sorted({(w[0], w[1]) for w in written}):
        obs.event(ev="partition_created", topic=x[0], part=x[1], tick=1)
    mx = upto
    for tp, p, base, end, tk in sorted(written, key=lambda w: w[4]):
        mx = max(mx, tk)
        obs.event(ev="segment", topic=tp, part=p, base=base, end=end, rtick=tk, tick=tk, n=end - base)
    for k in range(1, mx + 1):
        obs.materialize(k)
    shutil.move(str(obs.d), str(Path(d) / "_obs"))
    shutil.rmtree(Path(d).parent / f"_obs_{Path(d).name}", ignore_errors=True)


def run_mini(log, choice, spec, st, runner, upto):
    """Run `choice` tick by tick over a mini log (no retention: a shrunk trace is replayed whole). Returns silver by key."""
    b = Path(st).parent / f"{Path(st).name}_b"
    b.mkdir(parents=True, exist_ok=True)
    (b / "pipeline.py").write_text(RT.emit(choice))
    (b / "config.json").write_text(json.dumps(RT.config_from_spec(spec)))
    st = Path(st)
    if st.exists():
        shutil.rmtree(st)
    st.mkdir(parents=True)
    from nexus import r1_checks as RC
    # ONE run over the whole mini trace: a shrunk trace holds orders / backfill / registry records only, whose silver is
    # defined by source_version precedence and does not depend on run batching (the chunk_invariance property)
    r = runner.run(b, RC.grow_obs(log, Path(st).parent / f"{st.name}_v", upto, keep=10 ** 6), st, tick=upto)
    if r["exit"] != 0:
        return {}
    return {r[0]: r for r in (C.tables(st, spec).get("silver_orders") or [])}


# ------------------------------------------------------------------------------------------------ operators
class NexusOpsR1(O.NexusOps):
    def __init__(self, name, detector=None, library=None, seed=0, spec=None, mode="B1"):
        super().__init__(name, detector=detector, library=library, seed=seed)
        self.spec, self.mode = spec, mode
        self.cost.update(redeploy_trials=0, full_verifications=0, cheap_checks=0, shrink_tests=0, localisation_cpu_s=0.0,
                         reconcile_cpu_s=0.0, own_repairs=0)
        self.MAX_SHADOW = PER_TURN_SHADOW
        self.open = None

    def turn(self, env):
        c0 = _cpu()
        self.MAX_SHADOW = min(self.cost["shadow_tests"] + PER_TURN_SHADOW, PER_RUN_SHADOW)
        try:
            self._turn(env)
        finally:
            self.cost["agent_cpu_s"] += _cpu() - c0

    def _mons(self, env, det_state=None):
        a = _cpu()
        m = monitors_r1(env, self.spec, self.detector, self.det_state if det_state is None else det_state)
        self.cost["reconcile_cpu_s"] += _cpu() - a
        return m

    def _turn(self, env):
        for attempt in range(3):
            self._shadow_bad = {}
            mons = self._mons(env)
            pend = self._triage_alarms(env) if self.detector else []
            if "drift" in mons:
                open_ = [a for a in self.det_state.get("alarms", []) if a.get("localized") and
                         a["supplier"] not in {o["supplier"] for o in env.cfg["deploy"].get("unit_overrides", [])}]
                mons["drift"] = (not open_, dict(alarms=open_, pending=pend))
            bad = {k: v for k, v in mons.items() if not v[0]}
            if not bad:
                self.open = None
                return
            sig, cands = O.diagnose(env, mons, self.det_state)
            if sig == ["crash:permission"]:
                self.ledger.append(dict(tick=env.t, kind="source_unavailable", action="wait"))
                return
            comps = self._compositions(sig, cands, env)
            chosen, tried = None, 0
            for comp in comps:
                tried += 1
                if self.cost["shadow_tests"] >= self.MAX_SHADOW:
                    break
                ok = self._shadow(env, comp)
                if ok:
                    chosen, self._last_ok = comp, ok
                    break
                if self.library is not None and comp is comps[0] and self._from_library:
                    self.cost["failed_reuse"] += 1
            if chosen is None:
                chosen = self._deepen(env, sig, comps[:6])
                if chosen:
                    self._last_ok = True
            own = False
            shadow_bad = {k: v for k, v in self._shadow_bad.items() if k not in bad}
            if chosen is None and any(k in PIPELINE_SUSPECT for k in list(bad) + list(shadow_bad)):
                # CEGIS: pipeline-suspect failures seen only in failed shadow verifications are counterexamples too; the best
                # incident composition that fixes every non-pipeline symptom is kept and combined with the redeploy candidates
                relaxed = next((c for c in comps[:8] if c != (("catch_up", None),) and self.cost["shadow_tests"] < self.MAX_SHADOW
                                and self._shadow(env, c, relax=True)), None)
                chosen = self._repair_pipeline(env, sig, dict(bad, **shadow_bad), relaxed)
                own = chosen is not None
                if own:
                    self._last_ok = True
            if chosen is None:
                self.cost["escalations"] += 1
                self.open = sig
                self.ledger.append(dict(tick=env.t, kind="escalated", signature=sig, candidates=[c[0] for c in cands],
                                        pipeline_suspect=sorted(k for k in bad if k in PIPELINE_SUSPECT)))
                return
            apply_comp(env, chosen)
            self.cost["actions"] += len(chosen)
            post = self._mons(env)
            reconciled = post["reconciliation"][0] and post["observation_conformance"][0]
            self.cost["own_repairs"] += own
            self.ledger.append(dict(tick=env.t, kind=("repaired" if self._last_ok is True else "partial_repair_waiting_for_source")
                                    if reconciled else "applied_not_reconciled", signature=sig,
                                    repair=[[c[0], c[1]] for c in chosen], own_pipeline=own, verified_in_shadow=True,
                                    reconciled=reconciled, shadow_tests_before=tried, from_library=self._from_library and tried == 1))
            if self.library is not None:
                self.library.observe(sig, chosen)
            if self._last_ok == "partial":
                return

    def _shadow(self, env, comp, relax=False):
        a = _cpu()
        c = env.clone(env.work / "shadow")
        c.runs_this_tick = 0
        r = apply_comp(c, comp)
        mons = monitors_r1(c, self.spec, self.detector,
                           json.loads(json.dumps({k: v for k, v in self.det_state.items() if k == "alarms"})))
        self.cost["shadow_tests"] += 1
        self.cost["shadow_cpu_s"] += _cpu() - a + c.cpu_child
        drift_ok = all(x["supplier"] in {o["supplier"] for o in c.cfg["deploy"].get("unit_overrides", [])}
                       for x in self.det_state.get("alarms", []) if x.get("localized"))
        skip = ("drift",) + (PIPELINE_SUSPECT if relax else ())
        for k, v in mons.items():
            if k in PIPELINE_SUSPECT and not v[0]:
                getattr(self, "_shadow_bad", {}).setdefault(k, v)
        ok = r is not None and r.get("exit") == 0 and all(v[0] for k, v in mons.items() if k not in skip) and drift_ok
        if not ok and r is not None and r.get("exit") not in (0, None, "QUOTA") and not relax:
            err = r.get("err", "")
            if ("Permission denied" in err or "PermissionError" in err) and drift_ok and \
                    all(v[0] for k, v in mons.items() if k not in ("drift", "service", "snapshot_complete")):
                ok = "partial"
        O._rm(env.work / "shadow")
        return ok

    def _repair_pipeline(self, env, sig, bad, relaxed):
        """Own-pipeline repair (B0 or B1). Returns a composition or None."""
        a = _cpu()
        arch = _archive(env)
        base = tuple(x for x in (relaxed or ()) if x[0] not in ("catch_up", "rollback"))
        onset = _onset(env, bad, arch)
        tail = _rollback_tail(env, onset)
        choice = dict(env.choice)
        cex, survivors = [], []
        if self.mode == "B1":
            suspects, scores = localize_b1(env, self.spec, bad, arch, stage_holes(env))
            holes = suspects[:4]
            cands = [((d, o),) for d in holes for o in RT.DECISIONS[d] if o != choice[d]]
            cands += [((d1, o1), (d2, o2)) for d1, d2 in itertools.combinations(holes[:3], 2)
                      for o1 in RT.DECISIONS[d1] if o1 != choice[d1] for o2 in RT.DECISIONS[d2] if o2 != choice[d2]]
            mism = bad.get("reconciliation", (True, {}))[1].get("silver_mismatch", [])
            runner = C.Runner(env.profile)
            work = Path(tempfile.mkdtemp(prefix="cegis_"))
            if mism:
                ks, d, n = shrink_trace(env, self.spec, mism, arch, work, runner, choice)
                self.cost["shrink_tests"] += n
                if ks:
                    cex.append((ks, d))
            for cand in cands:
                ch = dict(choice, **dict(cand))
                passed = True
                for ks, d in cex:                                     # cheap: every accumulated shrunk counterexample
                    self.cost["cheap_checks"] += 1
                    want = C.derive_silver(self.spec, _mini_recs(d))
                    got = run_mini(d, ch, self.spec, work / "cc", runner, env.t)
                    if any(k not in got and k in want or k in got and k not in want or
                           (k in got and k in want and (got[k][2] != want[k][2] or abs(got[k][3] - want[k][3]) > 0.011)) for k in ks):
                        passed = False
                        break
                if passed:
                    survivors.append(cand)
            self.cost["shadow_cpu_s"] += runner.cpu_s
            shutil.rmtree(work, ignore_errors=True)
        else:
            suspects = localize_b0(bad, stage_holes(env))
            scores = {}
            # as in the Stage 4 search: single changes of the implicated decisions, then pairs among the first implicated
            # decisions, then single changes of every other decision
            impl = [d for d in suspects if d in stage_holes(env) or any(d in B0_TABLE.get(k, []) for k in bad)]
            single = lambda ds: [((d, o),) for d in ds for o in RT.DECISIONS[d] if o != choice[d]]
            survivors = single(impl) + [((d1, o1), (d2, o2)) for d1, d2 in itertools.combinations(impl[:4], 2)
                                        for o1 in RT.DECISIONS[d1] if o1 != choice[d1] for o2 in RT.DECISIONS[d2] if o2 != choice[d2]] \
                + single([d for d in suspects if d not in impl])
        self.cost["localisation_cpu_s"] += _cpu() - a
        full = 0
        for cand in survivors:
            if full >= MAX_FULL or self.cost["shadow_tests"] >= self.MAX_SHADOW:
                break
            ch = dict(choice, **dict(cand))
            comp = base + (("redeploy", ch),) + tail
            full += 1
            self.cost["full_verifications"] += 1
            self.cost["redeploy_trials"] += 1
            if self._shadow(env, comp) is True:
                self.ledger.append(dict(tick=env.t, kind="own_pipeline_localised", mode=self.mode, suspects=suspects,
                                        scores={k: round(v, 3) for k, v in scores.items()}, changed=dict(cand),
                                        full_verifications=full, survivors=len(survivors), onset=onset))
                return comp
        self.ledger.append(dict(tick=env.t, kind="own_pipeline_unrepaired", mode=self.mode, suspects=suspects,
                                scores={k: round(v, 3) for k, v in scores.items()}, full_verifications=full,
                                survivors=len(survivors), onset=onset))
        return None


def _mini_recs(d):
    recs = C.records(d)
    committed = {r["txn_id"] for tp, p, r in recs if r.get("control") == "txn_commit"}
    return [(tp, p, r) for tp, p, r in recs if not (r.get("txn_id") and "control" not in r and r["txn_id"] not in committed)]


class FixedPolicyOps(NexusOpsR1):
    """Same monitors / reconciliation / authority; a fixed sequential runbook, no shadow search:
    1. the incident runbook: every diagnosed primitive at once (one rollback, one batch size) + catch-up;
    2. only if pipeline-suspect symptoms remain (other than lag), ONE typed redeploy per signature: the top typed hole,
       its first alternative option, rollback before the onset, catch-up;
    3. otherwise escalate. An incident is resolved only when reconciliation passes."""

    def _bad(self, env):
        mons = self._mons(env)
        if self.detector:
            self._triage_alarms(env)
            if "drift" in mons:
                open_ = [a for a in self.det_state.get("alarms", []) if a.get("localized") and
                         a["supplier"] not in {o["supplier"] for o in env.cfg["deploy"].get("unit_overrides", [])}]
                mons["drift"] = (not open_, dict(alarms=open_))
        return mons, {k: v for k, v in mons.items() if not v[0]}

    def _turn(self, env):
        mons, bad = self._bad(env)
        if not bad:
            self.open = None
            return
        sig, cands = O.diagnose(env, mons, self.det_state)
        if sig == ["crash:permission"]:
            return
        prim, seen_rb = [], False
        for c in cands:
            if c[0] == "catch_up" or (c[0] == "rollback" and seen_rb) or (c[0] == "batch" and any(x[0] == "batch" for x in prim)):
                continue
            seen_rb |= c[0] == "rollback"
            prim.append(c)
        comp = tuple(prim) + (("catch_up", None),)
        apply_comp(env, comp)
        self.cost["actions"] += len(comp)
        mons, bad = self._bad(env)
        rec = bad.get("reconciliation", (True, {}))[1]
        lag_only = "reconciliation" in bad and not any(rec.get(k) for k in ("silver_mismatch", "late_mismatch", "accounting",
                                                                             "sla_mismatch", "volume_mismatch")) and \
            all(c["kind"].startswith("lag") for c in rec.get("coverage", []))
        key = "|".join(sig)
        tried = self.__dict__.setdefault("_redeployed", set())
        if any(k in PIPELINE_SUSPECT for k in bad) and not lag_only and key not in tried:
            arch = _archive(env)
            hole = next(iter(localize_b1(env, self.spec, bad, arch, stage_holes(env))[0]), None)
            tried.add(key)
            if hole:
                alt = next(o for o in RT.DECISIONS[hole] if o != env.choice[hole])
                comp2 = (("redeploy", dict(env.choice, **{hole: alt})),) + _rollback_tail(env, _onset(env, bad, arch))
                apply_comp(env, comp2)
                self.cost["actions"] += len(comp2)
                comp = comp + comp2
                mons, bad = self._bad(env)
        if not bad:
            self.ledger.append(dict(tick=env.t, kind="repaired", signature=sig, repair=[[c[0], c[1]] for c in comp], reconciled=True))
            self.open = None
        else:
            self.cost["escalations"] += 1
            self.open = sig
            self.ledger.append(dict(tick=env.t, kind="escalated", signature=sig, repair=[[c[0], c[1]] for c in comp],
                                    remaining=sorted(bad)))


def run_ops(enc, incs, work, bundle, operator, choice, profile=None, ticks=14):
    env = OpsEnvR1(enc, incs, work, bundle, profile, choice=choice)
    service = []
    for t in range(1, ticks + 1):
        env.advance()
        operator.turn(env)
        m = env.metrics()
        service.append(dict(tick=t, ok=m["last_exit"] == 0 and not m["lag"], lag=sum(m["lag"].values())))
    return env, service


def claims_healthy(op, env, spec):
    """Does the arm END claiming a healthy pipeline? NEXUS / Fixed: no open escalation and its own monitors pass; a
    conventional operator: its last run succeeded and nothing lags (it has no data invariants)."""
    if isinstance(op, NexusOpsR1):
        m = monitors_r1(env, spec, None, None)
        return op.open is None and all(v[0] for k, v in m.items() if k != "drift")
    m = env.metrics()
    return m["last_exit"] == 0 and not m["lag"]
