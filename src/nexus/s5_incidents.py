"""Stage 5 hidden-cause incidents and the operations harness (NOT LOCKED; evaluator side, semantic harness).

The harness owns the world: it appends the log tick by tick, applies incidents, enforces the deployment's resource quota,
credentials and source availability, runs the deployed pipeline, and exposes to an operator ONLY logs, metrics, lineage and
an authorised action API. Incident classes and their parameters are never given to an operator.

Seen classes (src / dev / val / test):
  I1 snapshot_interrupted   the backfill snapshot aborts at ~60% (control record snapshot_aborted) and its partition is
                            unreadable for one tick; only request_resnapshot() completes it
  I2 traffic_spike          ~10x telemetry in one tick; a run that consumes more than the pod quota (records per run) is
                            OOM-killed by the harness (state reverted, exit 137) - SIMULATED resource limit
  I3 unit_shift             one supplier silently switches its weights to pounds (producer_version v2) mid-stream
  I4 credential_expiry      the sink credential expires: lake.db becomes read-only until rotate_credentials()
  I5 partial_deploy_corruption  a half-applied migration deletes about half the bronze rows of the previous tick
Withheld (test only): U1 clock_skew (one telemetry producer emits event times days in the future), U2 poison_message (an
undecodable record at a fixed offset: a deterministic crash loop)."""
from __future__ import annotations

import json
import os
import random
import shutil
import sqlite3
import stat
from datetime import timedelta
from pathlib import Path

from nexus import s4_env as E

QUOTA = 300                     # pod memory quota, expressed as records consumed per run (simulated)
RUNS_PER_TICK = 6               # scheduler quota of runs per tick
SEEN = ["snapshot_interrupted", "traffic_spike", "unit_shift", "credential_expiry", "partial_deploy_corruption"]
WITHHELD = ["clock_skew", "poison_message"]


class Incident:
    name = "base"

    def __init__(self, tick, r):
        self.tick, self.r = tick, r
        self.resolved_actions = set()

    def apply(self, enc, w, r):          # mutate log + truth at encode time
        pass

    def on_tick_start(self, t, env):     # runtime environment effects
        pass

    def public(self):
        return {}


def _recs(enc, topic, part=None):
    out = []
    for tk, parts in enc["log"].items():
        for (tp, p), rs in parts.items():
            if tp == topic and (part is None or p == part):
                out += [(tk, p, x) for x in rs]
    return out


def _reoffset(enc):
    """Re-assign dense offsets in ingest order per partition after a mutation and update truth copies."""
    allr = {}
    for tk, parts in enc["log"].items():
        for k, rs in parts.items():
            allr.setdefault(k, []).extend((tk, x) for x in rs)
    new = {}
    remap = {}
    for k, items in allr.items():
        items.sort(key=lambda z: (z[0], z[1]["ingest_ts"], z[1]["offset"]))
        for i, (tk, x) in enumerate(items):
            remap[(k[0], k[1], x["offset"], x["msg_id"])] = i
            x["offset"] = i
            new.setdefault(tk, {}).setdefault(k, []).append(x)
    enc["log"] = new
    return remap


class SnapshotInterrupted(Incident):
    name = "snapshot_interrupted"

    def apply(self, enc, w, r):
        bf = sorted(_recs(enc, "backfill_orders"), key=lambda z: z[2]["offset"])
        rows = [z for z in bf if "control" not in z[2]]
        cut = int(len(rows) * 0.6)
        keep_keys = {z[2]["key"] for z in rows[:cut]}
        self.abort_tick = rows[cut][0]
        for tk, p, x in rows[cut:]:
            enc["log"][tk][("backfill_orders", 0)].remove(x)
        for tk, p, x in bf:
            if x.get("control") == "snapshot_end":
                enc["log"][tk][("backfill_orders", 0)].remove(x)
        enc["log"].setdefault(self.abort_tick, {}).setdefault(("backfill_orders", 0), []).append(
            dict(msg_id="snap-1-aborted", ingest_ts=E.iso(E.T0 + (self.abort_tick - 1) * E.D + timedelta(hours=40)),
                 control="snapshot_aborted", snapshot_id=1, offset=10**6))
        self.missing = [z[2] for z in rows[cut:]]
        truth = enc["truth"]
        truth["controls"] = [c for c in truth["controls"] if c["kind"] != "snapshot_end"] + [dict(tick=self.abort_tick, kind="aborted")]
        for v in truth["versions"]:
            if v["topic"] == "backfill_orders" and v["key"] not in keep_keys:
                v["copies"] = [(14, 0, -1)]   # required by the final checkpoint; only a re-snapshot can deliver it
                v["needs_resnapshot"] = True
        self.unavailable = (self.abort_tick + 1,)

    def on_tick_start(self, t, env):
        d = Path(env["log"]) / "backfill_orders" / "p0"
        if d.exists():
            os.chmod(d, 0o000 if t in self.unavailable else 0o755)

    def resnapshot(self, enc, t):
        """The source re-exports the full snapshot (new snapshot id, new msg_ids, same snapshot source_version)."""
        hist = sorted({x["key"]: x for _, _, x in _recs(enc, "backfill_orders") if "control" not in x}.values(), key=lambda x: x["key"])
        allrows = hist + [x for x in self.missing if x["key"] not in {h["key"] for h in hist}]
        base = E.T0 + (t - 1) * E.D + timedelta(hours=1)
        out = [dict(msg_id="snap-2-begin", ingest_ts=E.iso(base), control="snapshot_begin", snapshot_id=2, rows=len(allrows), offset=10**6)]
        for i, x in enumerate(sorted(allrows, key=lambda x: x["key"])):
            out.append(dict(x, msg_id=f"b2-{x['key']}", snapshot_id=2, ingest_ts=E.iso(base + timedelta(minutes=1 + i)), offset=10**6 + i + 1))
        out.append(dict(msg_id="snap-2-end", ingest_ts=E.iso(base + timedelta(minutes=len(allrows) + 2)), control="snapshot_end",
                        snapshot_id=2, rows=len(allrows), offset=10**6 + len(allrows) + 2))
        return out


class TrafficSpike(Incident):
    name = "traffic_spike"

    def apply(self, enc, w, r):
        t = self.tick
        base = E.T0 + (t - 1) * E.D
        orders = sorted({x["order_id"] for _, _, x in _recs(enc, "telemetry")})
        extra = []
        for i in range(1000):
            et = base + timedelta(minutes=r.uniform(5, 47 * 60))
            extra.append(dict(msg_id=f"spike{i:05d}", ingest_ts=E.iso(et + timedelta(seconds=30)), order_id=r.choice(orders),
                              type="PICKED", event_ts=E.iso(et), schema_version=1, offset=10**6 + i))
        for i, x in enumerate(extra):
            enc["log"].setdefault(t, {}).setdefault(("telemetry", i % 2), []).append(x)
        for x in extra:
            enc["truth"]["telemetry"].append(dict(msg_id=x["msg_id"], order_id=x["order_id"], type="PICKED", event_ts=x["event_ts"],
                                                  event_raw=x["event_ts"], copies=[(t, int(x["msg_id"][5:]) % 2, None, x["ingest_ts"])]))


class UnitShift(Incident):
    name = "unit_shift"

    def apply(self, enc, w, r):
        self.supplier = r.choice(E.SUPPLIERS)
        start = E.T0 + (self.tick - 1) * E.D
        for tk, p, x in _recs(enc, "manifests"):
            if x["supplier"] == self.supplier and x["ingest_ts"] >= E.iso(start) and isinstance(x["weight"], (int, float)):
                x["weight"] = round(x["weight"] / 0.45359237, 6)
                x["producer_version"] = "v2"
        # truth kg unchanged: the spec requires kg from the first affected message


class CredentialExpiry(Incident):
    name = "credential_expiry"

    def on_tick_start(self, t, env):
        db = Path(env["state"]) / "lake.db"
        if t == self.tick and db.exists() and not env.get("rotated_at", 0) >= t:
            os.chmod(db, stat.S_IRUSR | stat.S_IRGRP)
            env["expired"] = True

    def rotate(self, env):
        db = Path(env["state"]) / "lake.db"
        if db.exists():
            os.chmod(db, 0o644)
        env["expired"] = False


class PartialDeployCorruption(Incident):
    name = "partial_deploy_corruption"

    def on_tick_start(self, t, env):
        if t != self.tick:
            return
        db = Path(env["state"]) / "lake.db"
        con = sqlite3.connect(db)
        rows = con.execute("SELECT rowid FROM bronze_orders WHERE tick = ?", (t - 1,)).fetchall()
        for (rid,) in rows[::2]:
            con.execute("DELETE FROM bronze_orders WHERE rowid = ?", (rid,))
        con.commit(); con.close()
        env.setdefault("events", []).append(f"tick {t}: deployment v2 migration step 1/2 applied")


class ClockSkew(Incident):
    name = "clock_skew"

    def apply(self, enc, w, r):
        start = E.T0 + (self.tick - 1) * E.D
        end = start + E.D
        for tk, p, x in _recs(enc, "telemetry", 1):
            if E.iso(start) <= x["ingest_ts"] < E.iso(end):
                fdt = _dt(x["ingest_ts"]) + timedelta(days=3)
                fut = int(fdt.timestamp() * 1000) if isinstance(x["event_ts"], int) else E.iso(fdt)
                x["event_ts"] = fut
                for e in enc["truth"]["telemetry"]:
                    if e["msg_id"] == x["msg_id"]:
                        e.update(event_ts=E.iso(fdt), event_raw=fut, future=True)


class PoisonMessage(Incident):
    name = "poison_message"

    def apply(self, enc, w, r):
        cand = [(tk, p, x) for tk, p, x in _recs(enc, "telemetry", 0) if tk == self.tick]
        tk, p, x = cand[len(cand) // 2]
        x["_poison"] = True
        enc["truth"]["telemetry"] = [e for e in enc["truth"]["telemetry"] if e["msg_id"] != x["msg_id"]]
        self.msg = x["msg_id"]


def _dt(s):
    return E.datetime.fromisoformat(s.replace("Z", "+00:00"))


CLASSES = {c.name: c for c in (SnapshotInterrupted, TrafficSpike, UnitShift, CredentialExpiry, PartialDeployCorruption,
                                ClockSkew, PoisonMessage)}


def schedule(seed, split):
    r = random.Random(f"de2-incidents:{split}:{seed}")
    seen = r.sample(SEEN, 2 if split == "test" else 3)
    names = seen + ([WITHHELD[seed % 2]] if split == "test" else [])
    ticks = sorted(r.sample(range(8, 14), len(names)))
    if "snapshot_interrupted" in names:            # the snapshot runs at ticks 7-10: its incident must hit it
        i = names.index("snapshot_interrupted")
        names[i], names[0] = names[0], names[i]
    return [(n, t) for n, t in zip(names, ticks)]


def ops_world(w, split, seed, forced=None):
    r = random.Random(f"de2-ops:{split}:{seed}")
    incs = [CLASSES[n](t, r) for n, t in (forced or schedule(seed, split))]
    enc = E.encode(w, "ops", incidents=incs)
    remap = _reoffset(enc)
    t = enc["truth"]
    for coll, topic in ((t["versions"], None), (t["telemetry"], "telemetry"), (t["manifests"], "manifests")):
        pass
    _rebind(enc)
    t["poison"] = []
    for inc in incs:
        if inc.name == "poison_message":
            for tk, parts in enc["log"].items():
                for (tp, p), rs in parts.items():
                    for x in rs:
                        if x.get("_poison"):
                            t["poison"].append(dict(topic=tp, part=p, offset=x["offset"], tick=tk))
    t["incidents"] = [dict(name=i.name, tick=i.tick) for i in incs]
    return enc, incs


def _rebind(enc):
    """Truth copies -> (tick, part, offset[, ingest]) from the (re-offset) log, by msg_id and topic."""
    pos = {}
    for tk, parts in enc["log"].items():
        for (tp, p), rs in parts.items():
            for x in rs:
                pos.setdefault((tp, x["msg_id"]), []).append((tk, p, x["offset"], x["ingest_ts"]))
    t = enc["truth"]
    for v in t["versions"]:
        if v.get("needs_resnapshot"):
            continue
        cps = sorted(pos.get((v["topic"], v["msg_id"]), []))
        v["copies"] = [c[:3] for c in cps] or v["copies"]
    for coll, tp in ((t["telemetry"], "telemetry"), (t["manifests"], "manifests")):
        for e in coll:
            cps = sorted(pos.get((tp, e["msg_id"]), []))
            e["copies"] = ([c for c in cps] if tp == "telemetry" else [c[:3] for c in cps]) or e["copies"]


def write_tick(enc, root, t, incs):
    """Write tick t's segments (poison records written as undecodable lines)."""
    root = Path(root)
    if t == 1:
        for k in sorted({k for v in enc["log"].values() for k in v}):
            if not (k[0] == "orders_cdc" and k[1] >= 2):
                (root / "log" / k[0] / f"p{k[1]}").mkdir(parents=True, exist_ok=True)
    for (topic, part), recs in sorted(enc["log"].get(t, {}).items()):
        d = root / "log" / topic / f"p{part}"
        d.mkdir(parents=True, exist_ok=True)
        lines = []
        for x in sorted(recs, key=lambda x: x["offset"]):
            if x.get("_poison"):
                lines.append('{"msg_id": "' + x["msg_id"] + '", "ingest_ts": "' + x["ingest_ts"] + '", "order_id": ' + str(x["order_id"]) + ', "type": "DELIV')
            else:
                lines.append(json.dumps({k: v for k, v in x.items() if not k.startswith("_")}, sort_keys=True))
        (d / f"{recs[0]['offset']:08d}.jsonl").write_text("\n".join(lines) + "\n")


def append_records(root, topic, part, recs, start_offset):
    d = Path(root) / "log" / topic / f"p{part}"
    was = None
    if d.exists():
        was = stat.S_IMODE(os.stat(d).st_mode)
        os.chmod(d, 0o755)
    for i, x in enumerate(recs):
        x["offset"] = start_offset + i
    (d / f"{start_offset:08d}.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in recs))
    if was is not None and was == 0:
        os.chmod(d, 0)


def evaluate_ops(truth, env, service, ticks=14):
    """Evaluator: final outputs vs the truth reference (record_accounting by conservation, since re-snapshots legitimately
    add records), service at the end, per-tick freshness, duplicate keys, secret leakage in logs."""
    from nexus import s4_evaluator as V
    st = V.read_state(env.rt["state"])
    want = V.expected(truth, ticks)
    tables = {t: V.table_equal(t, st[t], want[t]) for t in V.OUT if t != "record_accounting"}
    acc = {(t, s): n for t, s, n in (st["record_accounting"] or [])}
    delivered = {}
    for d in Path(env.rt["log"]).glob("*/p*"):
        if d.parent.name == "_schemas" or not os.access(d, os.R_OK):
            continue
    conserv = not any(s == "dropped" for _, s in acc)
    dup = sum(len(v) - len(set(map(tuple, v))) for v in st.values() if isinstance(v, list))
    secret = env.secret.read_text()
    leaks = sum(secret in x for v in env.logs.values() for x in v)
    fresh_viol = sum(1 for s in service if not s["ok"])
    onset = {i["name"]: i["tick"] for i in truth["incidents"]}
    restore = {}
    for n, t0 in onset.items():
        ok_after = [s["tick"] for s in service if s["tick"] >= t0 and s["ok"]]
        restore[n] = (ok_after[0] - t0) if ok_after else None
    data_ok = all(ok for ok, _ in tables.values())
    return dict(data_ok=data_ok, service_restored=service[-1]["ok"], correct=data_ok and service[-1]["ok"] and conserv and not dup,
                tables={t: v[1] for t, v in tables.items() if not v[0]}, freshness_violations=fresh_viol, restore_ticks=restore,
                duplicate_rows=dup, secret_leaks=leaks, conservation_ok=conserv,
                quarantined=sum(n for (t, s), n in acc.items() if s == "quarantined"), late=acc.get(("telemetry", "late"), 0))
