"""Logistics data-engineering environment (Stage 2, NOT LOCKED).

make_project(seed, split) builds ONE project in two layers:
  truth   a clean, structured world (order version timeline, shipments, telemetry, manifest rows, inventory snapshots,
          stakeholder answers). Only the evaluator (src/nexus/de_evaluator.py) reads it.
  inputs  what an engineer receives: docs/spec.json (+ README.md) and two landing batches encoded messily from the truth
          (Debezium-style CDC envelopes op c/u/d/r with event_ts / ingest_ts / seq; append-only telemetry with duplicate
          deliveries and late events; CSV manifests with malformed rows, mixed units, schema drift and a re-delivered file;
          a sqlite operational snapshot per batch with PK/FK declarations and soft + hard deletes).
write_project() writes inputs/ and truth/ into separate directories so the agent's workspace never contains truth.

Splits draw physical names, units, currencies, deletion encodings, undocumented status codes and lateness windows from
pools: dev uses pool 0, val pools 0+1, test pools 1+2 (pool 2 = held out from dev and val). Every project contains every
core fault class (late corrections, out-of-order arrival, fan-out shipments, soft + hard deletes, malformed rows, mixed units,
duplicate deliveries); dev projects additionally force every optional trap (ambiguity, drift, re-delivered file)."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
CUT = {1: T0 + timedelta(days=10), 2: T0 + timedelta(days=20), 3: T0 + timedelta(days=30)}
BATCHES = (1, 2, 3)
VISIBLE = (1, 2)          # batches the engineer receives; batch 3 is held out for the evaluator
SPLIT_POOLS = {"dev": (0,), "val": (0, 1), "test": (1, 2)}

NAMES = {   # canonical -> (pool 0, pool 1, pool 2 = held out)
    "orders": ("orders", "sales_orders", "order_header"), "order_id": ("order_id", "ord_id", "order_ref"),
    "customer_id": ("customer_id", "cust_id", "client_ref"), "warehouse_id": ("warehouse_id", "wh_id", "site_code"),
    "status": ("status", "order_status", "lifecycle_state"), "amount": ("amount", "total_amount", "gross_value"),
    "currency": ("currency", "ccy", "currency_code"), "order_date": ("order_date", "created_on", "booking_date"),
    "promised_ts": ("promised_ts", "promise_by", "sla_deadline"),
    "shipments": ("shipments", "consignments", "parcels"), "shipment_id": ("shipment_id", "consignment_id", "parcel_ref"),
    "carrier": ("carrier", "carrier_name", "haulier"), "shipped_ts": ("shipped_ts", "dispatched_at", "handover_ts"),
    "warehouses": ("warehouses", "depots", "sites"), "wh_name": ("name", "depot_name", "site_label"),
    "region": ("region", "area", "zone"), "customers": ("customers", "accounts", "clients"),
    "cust_name": ("name", "account_name", "client_label"), "country": ("country", "country_code", "nation"),
    "inventory": ("inventory_adjustments", "stock_moves", "inv_ledger"), "adj_id": ("adj_id", "move_id", "entry_ref"),
    "sku": ("sku", "item_code", "article"), "qty": ("qty", "quantity", "delta_units"),
    "event_id": ("event_id", "evt_id", "signal_ref"), "event_type": ("event_type", "kind", "milestone"),
    "ev_shipment": ("shipment_id", "consignment", "parcel"), "ev_ts": ("event_ts", "occurred_at", "observed_ts"),
    "ev_ingest": ("ingest_ts", "received_at", "landed_ts"),
    "m_shipment": ("shipment_id", "consignment_no", "parcel_ref"), "weight": ("weight", "wt", "mass"),
    "weight_drift": ("gross_weight", "weight_total", "gross_mass"), "unit": ("unit", "uom", "unit_code"),
    "packages": ("packages", "pkg_count", "pieces"),
    "deleted_flag": ("is_deleted", "deleted", "void_flag"), "deleted_at": ("deleted_at", "removed_at", "voided_ts"),
}
CURRENCIES = ({"USD": 1.0, "EUR": 1.08, "GBP": 1.27}, {"USD": 1.0, "EUR": 1.08, "GBP": 1.27},
              {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CHF": 1.12})
UNITS = ({"kg": 1.0, "g": 0.001, "lb": 0.45359237}, {"kg": 1.0, "g": 0.001, "lb": 0.45359237},
         {"kg": 1.0, "g": 0.001, "lb": 0.45359237, "oz": 0.028349523125})
FLAG_VALUES = ([1], [1], [1, "Y"])                    # pool 2 adds a text flag encoding
UNDOC = (["HLD"], ["PEND"], ["QA_HOLD", "BKO"])
LATENESS = ([6, 12], [6, 12], [4, 24])
CARRIERS = (["DHL", "UPS", "FDX"], ["DHL", "UPS", "FDX", "TNT"], ["DPD", "GLS", "UPS", "PNL"])
OFFSETS = [timedelta(hours=-5), timedelta(hours=2), timedelta(hours=9), timedelta(0)]
BUCKETS = {"PLACED": "open", "SHIPPED": "open", "DELIVERED": "fulfilled", "RETURNED": "fulfilled", "CANCELLED": "cancelled"}
OUTPUTS = {
    "silver_orders": (["order_id", "customer_id", "warehouse_id", "status", "amount_usd", "order_date"], ["order_id"]),
    "silver_manifest": (["record_ref", "shipment_id", "weight_kg"], ["record_ref"]),
    "gold_warehouse_revenue": (["warehouse_id", "net_revenue_usd"], ["warehouse_id"]),
    "gold_sla": (["warehouse_id", "delivered", "on_time", "on_time_rate"], ["warehouse_id"]),
    "gold_carrier_volume": (["warehouse_id", "carrier", "weight_kg"], ["warehouse_id", "carrier"]),
    "gold_status_counts": (["warehouse_id", "bucket", "n"], ["warehouse_id", "bucket"]),
    "gold_inventory": (["warehouse_id", "sku", "on_hand"], ["warehouse_id", "sku"]),
    "late_events": (["event_id"], ["event_id"]),
    "quarantine": (["source", "record_ref", "reason"], ["source", "record_ref"]),
}


def iso(dt, off=timedelta(0)):
    d = (dt + off).replace(microsecond=0)
    if off == timedelta(0):
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")
    sign = "+" if off >= timedelta(0) else "-"
    m = abs(int(off.total_seconds())) // 60
    return d.strftime("%Y-%m-%dT%H:%M:%S") + f"{sign}{m // 60:02d}:{m % 60:02d}"


def ref_of(line):
    return hashlib.sha1(line.encode()).hexdigest()[:12]


def batch_of(ingest):
    return next((b for b in BATCHES if ingest <= CUT[b]), None)


class _Gen:
    def __init__(self, seed, split, force_all):
        self.r = random.Random(f"de1:{split}:{seed}")
        self.split, self.seed, self.force = split, seed, force_all
        pools = SPLIT_POOLS[split]
        r = self.r
        self.pool = lambda: r.choice(pools)
        picks = {k: self.pool() for k in NAMES}
        self.n = {k: NAMES[k][i] for k, i in picks.items()}
        self.heldout_names = sorted(k for k, i in picks.items() if i == 2)
        cp = max(pools)
        self.fx = dict(CURRENCIES[cp])
        self.units = dict(UNITS[cp])
        pc, pl, pu = self.pool(), self.pool(), self.pool()
        self.carriers = CARRIERS[pc]
        self.lateness = r.choice(LATENESS[pl])
        self.undoc_code = r.choice(UNDOC[pu])
        self.heldout_misc = dict(carriers=pc == 2, lateness=pl == 2, undoc_code=pu == 2)
        kind = r.choice(["flag", "timestamp"])
        self.deletion = dict(kind=kind, flag_value=r.choice(FLAG_VALUES[cp]) if kind == "flag" else None)
        self.tz_mixed = force_all or r.random() < 0.7
        self.unit_encoding = r.choice(["suffix", "column"])
        self.drift = force_all or r.random() < 0.6
        self.redeliver = force_all or r.random() < 0.7
        self.carrier_gap = force_all or r.random() < 0.5
        self.undoc = (r.random() < 0.5) if not force_all else r.random() < 0.5
        self.answers = {}
        if self.carrier_gap:
            self.answers["carrier_volume:CANCELLED"] = r.choice(["include", "exclude"])
        if self.undoc:
            self.answers[f"status_bucket:{self.undoc_code}"] = r.choice(["open", "fulfilled", "cancelled"])

    def ts(self, lo, hi):
        return lo + timedelta(seconds=self.r.uniform(0, (hi - lo).total_seconds()))

    def delay(self, late_p, lo_h, hi_h):
        r = self.r
        if r.random() < late_p:
            return timedelta(hours=r.uniform(lo_h, hi_h))
        return timedelta(minutes=r.uniform(1, 90))


def _orders(g):
    """Order version timeline. Each version: key, event_ts (UTC), ingest_ts, op, row (canonical), soft (deleted flag)."""
    r = g.r
    whs = [f"W{i}" for i in range(1, r.randint(3, 4) + 1)]
    custs = [f"C{i:02d}" for i in range(1, 13)]
    orders, versions = {}, []
    for i in range(70):
        oid = 1000 + i
        tc = g.ts(T0, T0 + timedelta(days=27))
        cur = r.choice(sorted(g.fx))
        row = dict(order_id=oid, customer_id=r.choice(custs), warehouse_id=r.choice(whs), status="PLACED",
                   amount=round(r.uniform(20, 900) / (g.fx[cur] if g.fx[cur] < 0.1 else 1), 2), currency=cur,
                   order_date=tc.strftime("%Y-%m-%d"), promised_ts=iso(tc + timedelta(days=r.uniform(2.5, 5))))
        orders[oid] = dict(created=tc)
        vs = [(tc, dict(row), "c")]
        t = tc
        u = r.random()
        if u < 0.80:
            t = t + timedelta(hours=r.uniform(8, 40)); vs.append((t, dict(vs[-1][1], status="SHIPPED"), "u"))
            orders[oid]["shipped"] = t
            v = r.random()
            if v < 0.72:
                t = t + timedelta(hours=r.uniform(20, 70)); vs.append((t, dict(vs[-1][1], status="DELIVERED"), "u"))
                orders[oid]["delivered"] = t
                if r.random() < 0.06:
                    t = t + timedelta(hours=r.uniform(10, 40)); vs.append((t, dict(vs[-1][1], status="RETURNED"), "u"))
            elif v < 0.86 and g.carrier_gap:
                t = t + timedelta(hours=r.uniform(4, 30)); vs.append((t, dict(vs[-1][1], status="CANCELLED"), "u"))
        elif u < 0.88:
            t = t + timedelta(hours=r.uniform(2, 20)); vs.append((t, dict(vs[-1][1], status="CANCELLED"), "u"))
        elif g.undoc:
            t = t + timedelta(hours=r.uniform(2, 20)); vs.append((t, dict(vs[-1][1], status=g.undoc_code), "u"))
        if r.random() < 0.18:      # price correction, often retroactive (event time inside an earlier batch, ingested late)
            tt = g.ts(tc + timedelta(minutes=5), max(tc + timedelta(minutes=10), t + timedelta(hours=6)))
            k = max(j for j, (vt, _, _) in enumerate(vs) if vt <= tt)
            vs.insert(k + 1, (tt, dict(vs[k][1], amount=round(vs[k][1]["amount"] * r.uniform(0.7, 1.2), 2)), "u"))
            for j in range(k + 2, len(vs)):
                vs[j] = (vs[j][0], dict(vs[j][1], amount=vs[k + 1][1]["amount"]), vs[j][2])
            orders[oid]["corrected"] = tt
        end = vs[-1][0]
        x = r.random()
        if x < 0.06:
            vs.append((end + timedelta(hours=r.uniform(1, 30)), None, "d"))
        elif x < 0.13:
            vs.append((end + timedelta(hours=r.uniform(1, 30)), dict(vs[-1][1]), "soft"))
        for j, (vt, row_, op) in enumerate(vs):
            late = 0.30 if (op == "u" and "corrected" in orders[oid] and vt == orders[oid]["corrected"]) else 0.10
            ing = vt + g.delay(late, 30, 150)
            if op == "c" and vt < T0 + timedelta(days=1):
                op = "r"
            versions.append(dict(key=oid, event_ts=vt, ingest_ts=ing, op="u" if op == "soft" else op, row=row_,
                                 soft=op == "soft"))
    versions = [v for v in versions if v["event_ts"] < CUT[3] and batch_of(v["ingest_ts"])]
    versions.sort(key=lambda v: (v["ingest_ts"], v["key"]))
    for s, v in enumerate(versions):
        v["seq"] = s + 1
        v["batch"] = batch_of(v["ingest_ts"])
    return whs, custs, orders, versions


def _shipments_events(g, orders, versions):
    r = g.r
    first_batch = {}
    for v in versions:
        first_batch.setdefault(v["key"], v["batch"])
    ships, events, n = [], [], 0
    for oid, o in sorted(orders.items()):
        if "shipped" not in o or oid not in first_batch:
            continue
        for _ in range(r.choices([1, 2, 3], [0.5, 0.32, 0.18])[0]):
            n += 1
            st = o["shipped"] + timedelta(minutes=r.uniform(5, 120))
            if st >= CUT[3]:
                continue
            sid = f"S{n:04d}"
            ships.append(dict(shipment_id=sid, order_id=oid, carrier=r.choice(g.carriers), shipped_ts=st, batch=batch_of(st)))
            evs = [("PICKED", st - timedelta(minutes=r.uniform(20, 90))), ("DEPARTED", st)]
            if "delivered" in o:
                evs.append(("DELIVERED", o["delivered"] + timedelta(minutes=r.uniform(-300, 300))))
            for typ, et in evs:
                ing = et + g.delay(0.12, g.lateness + 1, g.lateness + 48)
                b = batch_of(ing)
                if et >= CUT[3] or not b:
                    continue
                e = dict(event_id=f"E{len(events) + 1:05d}", shipment_id=sid, type=typ, event_ts=et, ingest_ts=ing, batches=[b])
                if r.random() < 0.07:
                    e["batches"].append(min(3, b + r.randint(0, 1)))
                events.append(e)
    return ships, events


def _manifest(g, ships):
    """Manifest rows: one per shipment (in the batch of its shipped_ts), plus single-fault malformed rows and orphans."""
    r = g.r
    units = sorted(g.units)
    rows = []
    for s in ships:
        kg = round(r.uniform(0.4, 60), 3)
        u = r.choice(units)
        val = round(kg / g.units[u], 3)
        rows.append(dict(kind="valid", shipment_id=s["shipment_id"], value=val, unit=u, kg=val * g.units[u], batch=s["batch"],
                         packages=r.randint(1, 4)))
    for b in BATCHES:
        cand = [x for x in rows if x["batch"] == b and x["kind"] == "valid"]
        for kind, k in (("unparseable_weight", 3), ("unknown_unit", 2), ("missing_key", 2)):
            for x in r.sample(cand, k):
                x["kind"] = kind
                cand.remove(x)
                if kind == "unparseable_weight":
                    x["token"] = r.choice(["N/A", "", "12..5", "??"])
                elif kind == "unknown_unit":
                    x["unit"] = r.choice(["kgs", "lbs.", "units"])
        for _ in range(2):
            u = r.choice(units)
            rows.append(dict(kind="orphan_shipment", shipment_id=f"S9{r.randint(100, 999)}", value=round(r.uniform(1, 20), 3),
                             unit=u, kg=None, batch=b, packages=1))
    return rows


def _inventory(g, whs):
    r = g.r
    skus = [f"SKU{i}" for i in range(1, 7)]
    rows = []
    for i in range(40):
        ct = g.ts(T0, CUT[3] - timedelta(days=1))
        row = dict(adj_id=f"A{i:03d}", warehouse_id=r.choice(whs), sku=r.choice(skus), qty=r.randint(-20, 60),
                   created=ct, batch=batch_of(ct))
        x = r.random()
        if x < 0.12:
            row["soft_deleted_in"] = r.randint(row["batch"], 3)
        elif x < 0.20 and row["batch"] < 3:
            row["hard_deleted_in"] = r.randint(row["batch"] + 1, 3)
        rows.append(row)
    return rows


def _features(versions, ships, events, manifest, lateness):
    """Fault-class counts in the VISIBLE batches (1-2) and in held-out batch 3 (every class must be detectable from the
    visible data AND exercised again by the held-out batch)."""
    L = timedelta(hours=lateness)

    def ooo(B):
        by = {}
        for v in versions:
            if v["batch"] <= B:
                by.setdefault(v["key"], []).append(v)
        return {k for k, vs in by.items()
                if [v["seq"] for v in sorted(vs, key=lambda v: (v["event_ts"], v["seq"]))] != sorted(v["seq"] for v in vs)}

    def late_newest(B):
        wm = max(v["event_ts"] for v in versions if v["batch"] < B)
        by = {}
        for v in versions:
            if v["batch"] <= B:
                by.setdefault(v["key"], []).append(v)
        return sum(1 for vs in by.values() if (lambda m: m["batch"] == B and m["event_ts"] <= wm)(
            max(vs, key=lambda v: (v["event_ts"], v["seq"]))))
    late_del = [e for e in events if e["type"] == "DELIVERED" and e["ingest_ts"] - e["event_ts"] > L]
    deliv_ships = {}
    for e in events:
        if e["type"] == "DELIVERED" and min(e["batches"]) <= 2:
            deliv_ships[e["shipment_id"]] = 1
    per = {}
    for s in ships:
        if s["shipment_id"] in deliv_ships and s["batch"] <= 2:
            per[s["order_id"]] = per.get(s["order_id"], 0) + 1
    vis = dict(out_of_order_keys=len(ooo(2)), late_newest_keys=late_newest(2),
               late_delivered_events=sum(1 for e in late_del if min(e["batches"]) <= 2),
               multi_ship_delivered_orders=sum(1 for c in per.values() if c > 1),
               soft=sum(v["soft"] for v in versions if v["batch"] <= 2), hard=sum(v["op"] == "d" for v in versions if v["batch"] <= 2),
               dup_events=sum(len(e["batches"]) > 1 for e in events if max(e["batches"]) <= 2),
               mixed_units=len({m["unit"] for m in manifest if m["kind"] == "valid" and m["batch"] <= 2}))
    b3 = dict(out_of_order_keys=len(ooo(3) - ooo(2)), late_newest_keys=late_newest(3),
              late_delivered_events=sum(1 for e in late_del if min(e["batches"]) == 3),
              soft=sum(v["soft"] for v in versions if v["batch"] == 3))
    return dict(visible=vis, batch3=b3)


def make_project(seed, split):
    force = split == "dev"
    for attempt in range(200):
        g = _Gen(f"{seed}:{attempt}", split, force)
        whs, custs, orders, versions = _orders(g)
        ships, events = _shipments_events(g, orders, versions)
        manifest = _manifest(g, ships)
        inv = _inventory(g, whs)
        f = _features(versions, ships, events, manifest, g.lateness)
        cancelled_shipped = {s["order_id"] for s in ships} & {v["key"] for v in versions if v["row"] and v["row"]["status"] == "CANCELLED"}
        undoc_seen = any(v["row"] and v["row"]["status"] == g.undoc_code for v in versions)
        v, h = f["visible"], f["batch3"]
        ok = (v["out_of_order_keys"] >= 2 and v["late_newest_keys"] >= 2 and v["late_delivered_events"] >= 1
              and v["multi_ship_delivered_orders"] >= 2 and v["soft"] >= 1 and v["hard"] >= 1 and v["dup_events"] >= 1
              and v["mixed_units"] >= 2 and h["out_of_order_keys"] >= 1 and h["late_newest_keys"] >= 1
              and h["late_delivered_events"] >= 1
              and (not g.carrier_gap or len(cancelled_shipped) >= 2) and (not g.undoc or undoc_seen))
        if ok:
            break
    else:
        raise RuntimeError("generator could not realise every fault class")
    if not cancelled_shipped:
        g.answers.pop("carrier_volume:CANCELLED", None)
    return _encode(g, f"{split}-{seed}", whs, custs, versions, ships, events, manifest, inv, f, attempt)


def _row_phys(g, row, soft):
    n = g.n
    out = {n[k]: row[k] for k in ("order_id", "customer_id", "warehouse_id", "status", "amount", "currency", "order_date",
                                   "promised_ts")}
    d = g.deletion
    if d["kind"] == "flag":
        out[n["deleted_flag"]] = d["flag_value"] if soft else (0 if isinstance(d["flag_value"], int) else "N")
    else:
        out[n["deleted_at"]] = iso(T0 + timedelta(days=29)) if soft else None
    return out


def _encode(g, pid, whs, custs, versions, ships, events, manifest, inv, feats, attempt):
    r, n = g.r, g.n
    files = {b: {} for b in BATCHES}
    # --- CDC envelopes: two partitions per batch (by key parity), seq order inside a partition, partition order random
    prev = {}
    env_by_batch = {b: [[], []] for b in BATCHES}
    for v in sorted(versions, key=lambda v: v["seq"]):
        before = prev.get(v["key"])
        after = _row_phys(g, v["row"], v["soft"]) if v["row"] else None
        off = r.choice(OFFSETS) if g.tz_mixed else timedelta(0)
        e = dict(op=v["op"], event_ts=iso(v["event_ts"], off), ingest_ts=iso(v["ingest_ts"]), seq=v["seq"],
                 key={n["order_id"]: v["key"]}, before=before, after=after, source=n["orders"])
        prev[v["key"]] = after
        v["event_ts_raw"] = e["event_ts"]
        part = env_by_batch[v["batch"]][v["key"] % 2]
        part.append(e)
        if r.random() < 0.05:
            env_by_batch[min(3, v["batch"] + r.randint(0, 1))][v["key"] % 2].append(dict(e))   # redelivered envelope
    for b in BATCHES:
        for p, envs in enumerate(env_by_batch[b]):
            files[b][f"cdc/{n['orders']}_b{b}_p{p}.jsonl"] = "".join(json.dumps(e, sort_keys=True) + "\n" for e in envs)
    # --- telemetry (append-only; duplicates; late)
    tel = {b: [] for b in BATCHES}
    for e in events:
        off = r.choice(OFFSETS) if g.tz_mixed else timedelta(0)
        rec = {n["event_id"]: e["event_id"], n["ev_shipment"]: e["shipment_id"], n["event_type"]: e["type"],
               n["ev_ts"]: iso(e["event_ts"], off), n["ev_ingest"]: iso(e["ingest_ts"])}
        e["event_ts_raw"] = rec[n["ev_ts"]]
        for b in e["batches"]:
            tel[b].append(rec)
    for b in BATCHES:
        r.shuffle(tel[b])
        h = len(tel[b]) // 2
        for k, chunk in enumerate((tel[b][:h], tel[b][h:])):
            files[b][f"events/telemetry_b{b}_{k}.jsonl"] = "".join(json.dumps(x, sort_keys=True) + "\n" for x in chunk)
    # --- manifests (CSV); batch 2 drifts if g.drift; one batch-1 file re-delivered in batch 2 if g.redeliver
    mrefs = []
    for b in BATCHES:
        drift = g.drift and b >= 2
        wcol = n["weight_drift"] if drift else n["weight"]
        enc = ("column" if g.unit_encoding == "suffix" else "suffix") if drift else g.unit_encoding
        cols = [n["m_shipment"], wcol] + ([n["unit"]] if enc == "column" else []) + [n["packages"]]
        rows = [m for m in manifest if m["batch"] == b]
        r.shuffle(rows)
        h = len(rows) // 2
        for k, chunk in enumerate((rows[:h], rows[h:])):
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(cols)
            lines = []
            for m in chunk:
                sid = "" if m["kind"] == "missing_key" else m["shipment_id"]
                tok = m.get("token") if m["kind"] == "unparseable_weight" else repr(m["value"])
                if enc == "suffix":
                    vals = [sid, tok + ("" if m["kind"] == "unparseable_weight" else m["unit"])]
                else:
                    vals = [sid, tok, m["unit"]]
                vals.append(m["packages"])
                lb = io.StringIO()
                csv.writer(lb, lineterminator="").writerow(vals)
                line = lb.getvalue()
                buf.write(line + "\n")
                lines.append(line)
                mrefs.append(dict(m, record_ref=ref_of(line)))
            files[b][f"drops/manifest_b{b}_{k}.csv"] = buf.getvalue()
    if g.redeliver:
        files[2]["drops/manifest_b1_0_redelivery.csv"] = files[1]["drops/manifest_b1_0.csv"]
        files[3]["drops/manifest_b2_1_redelivery.csv"] = files[2]["drops/manifest_b2_1.csv"]
    # --- operational snapshot (sqlite) per batch
    dbs = {}
    for b in BATCHES:
        dbs[b] = _snapshot(g, b, whs, custs, ships, inv)
    spec = _spec(g, pid)
    truth = dict(project=pid, split=g.split, generator_attempt=attempt, features=feats,
                 versions=[dict(v, event_ts=iso(v["event_ts"]), ingest_ts=iso(v["ingest_ts"])) for v in versions],
                 shipments=[dict(s, shipped_ts=iso(s["shipped_ts"])) for s in ships],
                 events=[dict(e, event_ts=iso(e["event_ts"]), ingest_ts=iso(e["ingest_ts"])) for e in events],
                 manifest=mrefs, inventory=[dict(x, created=iso(x["created"])) for x in inv], warehouses=whs,
                 fx=g.fx, units=g.units, lateness_hours=g.lateness, buckets=dict(BUCKETS),
                 carrier_include=["SHIPPED", "DELIVERED", "RETURNED"], answers=g.answers,
                 cancelled_documented=not g.carrier_gap, undoc_code=g.undoc_code if g.undoc else None,
                 heldout=dict(names=g.heldout_names, **g.heldout_misc,
                              currencies=sorted({v["row"]["currency"] for v in versions if v["row"]} - set(CURRENCIES[0])),
                              units=sorted({m["unit"] for m in manifest if m["kind"] == "valid"} - set(UNITS[0])),
                              text_flag=g.deletion.get("flag_value") == "Y"),
                 twists=dict(tz_mixed=g.tz_mixed, unit_encoding=g.unit_encoding, drift=g.drift, redeliver=g.redeliver,
                             carrier_gap="carrier_volume:CANCELLED" in g.answers, undoc=g.undoc, deletion=g.deletion))
    return dict(project=pid, spec=spec, files=files, dbs=dbs, truth=truth)


def _snapshot(g, b, whs, custs, ships, inv):
    n, d = g.n, g.deletion
    con = sqlite3.connect(":memory:")
    q = lambda s: '"' + s + '"'
    con.execute(f"CREATE TABLE {q(n['warehouses'])} ({q(n['warehouse_id'])} TEXT PRIMARY KEY, {q(n['wh_name'])} TEXT, {q(n['region'])} TEXT)")
    con.execute(f"CREATE TABLE {q(n['customers'])} ({q(n['customer_id'])} TEXT PRIMARY KEY, {q(n['cust_name'])} TEXT, {q(n['country'])} TEXT)")
    con.execute(f"CREATE TABLE {q(n['shipments'])} ({q(n['shipment_id'])} TEXT PRIMARY KEY, {q(n['order_id'])} INTEGER NOT NULL, "
                f"{q(n['carrier'])} TEXT, {q(n['shipped_ts'])} TEXT)")
    dcol = n["deleted_flag"] if d["kind"] == "flag" else n["deleted_at"]
    con.execute(f"CREATE TABLE {q(n['inventory'])} ({q(n['adj_id'])} TEXT PRIMARY KEY, {q(n['warehouse_id'])} TEXT REFERENCES "
                f"{q(n['warehouses'])}({q(n['warehouse_id'])}), {q(n['sku'])} TEXT, {q(n['qty'])} INTEGER, {q(dcol)})")
    for i, w in enumerate(whs):
        con.execute(f"INSERT INTO {q(n['warehouses'])} VALUES (?,?,?)", (w, f"Depot {w}", ["north", "south", "east", "west"][i % 4]))
    for i, c in enumerate(custs):
        con.execute(f"INSERT INTO {q(n['customers'])} VALUES (?,?,?)", (c, f"Customer {c}", ["DE", "FR", "US", "GB"][i % 4]))
    for s in ships:
        if s["batch"] <= b:
            con.execute(f"INSERT INTO {q(n['shipments'])} VALUES (?,?,?,?)", (s["shipment_id"], s["order_id"], s["carrier"],
                                                                         iso(s["shipped_ts"])))
    off = 0 if isinstance(d.get("flag_value"), int) or d["kind"] != "flag" else "N"
    for x in inv:
        if x["batch"] > b or x.get("hard_deleted_in", 9) <= b:
            continue
        soft = x.get("soft_deleted_in", 9) <= b
        dv = (d["flag_value"] if soft else off) if d["kind"] == "flag" else (iso(CUT[b] - timedelta(hours=3)) if soft else None)
        con.execute(f"INSERT INTO {q(n['inventory'])} VALUES (?,?,?,?,?)", (x["adj_id"], x["warehouse_id"], x["sku"], x["qty"], dv))
    con.commit()
    data = io.BytesIO()
    for line in con.iterdump():
        data.write((line + "\n").encode())
    con.close()
    return data.getvalue().decode()


def _spec(g, pid):
    n, d = g.n, g.deletion
    cv_ex = ["PLACED"] + ([] if g.carrier_gap else ["CANCELLED"])
    buckets = dict(BUCKETS)
    return {
        "project": pid,
        "goal": "Build an incremental, idempotent pipeline from the landing zone into state/lake.db producing the output tables.",
        "sources": {"operational_db": "landing/source.db (full snapshot of reference tables each batch; replaces the previous)",
                    "cdc": "landing/cdc/*.jsonl (change envelopes for the orders entity)",
                    "events": "landing/events/*.jsonl (append-only shipment telemetry; may redeliver events)",
                    "manifests": "landing/drops/*.csv (weight manifests; one row per shipment; files may be redelivered)"},
        "dictionary": {
            "orders": {"cdc_source": n["orders"], "columns": {k: n[k] for k in ("order_id", "customer_id", "warehouse_id", "status",
                                                                                   "amount", "currency", "order_date", "promised_ts")}},
            "shipments": {"table": n["shipments"], "columns": {"shipment_id": n["shipment_id"], "order_id": n["order_id"],
                                                               "carrier": n["carrier"], "shipped_ts": n["shipped_ts"]}},
            "warehouses": {"table": n["warehouses"], "columns": {"warehouse_id": n["warehouse_id"]}},
            "customers": {"table": n["customers"], "columns": {"customer_id": n["customer_id"]}},
            "inventory": {"table": n["inventory"], "columns": {"adj_id": n["adj_id"], "warehouse_id": n["warehouse_id"],
                                                               "sku": n["sku"], "qty": n["qty"]}},
            "events": {"columns": {"event_id": n["event_id"], "shipment_id": n["ev_shipment"], "event_type": n["event_type"],
                                   "event_ts": n["ev_ts"], "ingest_ts": n["ev_ingest"]}},
            "manifest": {"columns": {"shipment_id": [n["m_shipment"]], "weight": [n["weight"], n["weight_drift"]],
                                     "unit": [n["unit"]], "packages": [n["packages"]]},
                         "note": "the weight column may appear under any listed alias; the unit is either a separate unit "
                                 "column or a suffix of the weight value"},
        },
        "deletion": ({"kind": "flag", "column": n["deleted_flag"], "deleted_values": [d["flag_value"]]} if d["kind"] == "flag"
                     else {"kind": "timestamp", "column": n["deleted_at"], "deleted_when": "not null"}),
        "deletion_rules": "CDC op 'd' is a hard delete. A row whose deletion column marks it deleted is soft-deleted. Deleted "
                          "orders and inventory adjustments are excluded from every silver and gold table.",
        "cdc": {"semantics": "last writer wins by event_ts compared in UTC; ties broken by higher seq",
                "ops": {"r": "snapshot read", "c": "create", "u": "update", "d": "delete"},
                "late_changes": "changes may arrive in a later batch than their event time; they still apply"},
        "currency": {"base": "USD", "fx_to_usd": g.fx, "rounding": "amount_usd = round(amount * fx, 2) per order"},
        "units": {"base": "kg", "to_kg": g.units, "rounding": "weight_kg sums rounded to 3 decimals"},
        "lateness_hours": g.lateness,
        "late_event_rule": "a telemetry event with ingest_ts - event_ts greater than lateness_hours is late: it is listed in "
                           "late_events and excluded from gold_sla (it still counts as evidence of delivery for revenue)",
        "status_buckets": buckets,
        "rules": {
            "silver_orders": "current, non-deleted state of every order after all changes",
            "gold_warehouse_revenue": "per warehouse (every warehouse in the snapshot, 0 if none): sum of amount_usd over "
                                      "silver orders with status DELIVERED that have at least one shipment with a DELIVERED "
                                      "telemetry event",
            "gold_sla": "per warehouse with >= 1 delivered shipment: delivered = shipments of silver orders with a non-late "
                        "DELIVERED event; on_time = those whose DELIVERED event_ts <= the order's promised_ts; "
                        "on_time_rate = round(on_time / delivered, 4)",
            "gold_carrier_volume": {"text": "per (warehouse, carrier): sum of weight_kg of valid manifest rows whose shipment "
                                            "belongs to a silver order with an included status",
                                    "include_status": ["SHIPPED", "DELIVERED", "RETURNED"], "exclude_status": cv_ex},
            "gold_status_counts": "per (warehouse, bucket): number of silver orders; bucket from status_buckets",
            "gold_inventory": "per (warehouse, sku): sum of qty over non-deleted adjustments in the latest snapshot",
        },
        "quarantine": {"record_ref": "first 12 hex characters of sha1 of the raw CSV line (without the newline)",
                       "reasons": {"missing_key": "empty shipment id", "unparseable_weight": "weight is not a number",
                                   "unknown_unit": "unit not in units.to_kg", "orphan_shipment": "shipment not in snapshot"},
                       "rule": "malformed manifest rows are never dropped or zero-filled: they go to quarantine (source = "
                               "'manifest'); checks apply in the order listed"},
        "outputs": {k: {"columns": c, "pk": p} for k, (c, p) in OUTPUTS.items()},
        "retention": "landing/ holds only the current batch; earlier batches are removed when a new batch lands",
        "freshness": "after each run, every gold table reflects all records ingested up to and including the current batch",
        "idempotency": "re-running the same batch, or a restart after a crash, must leave exactly the same state",
        "stakeholder": "ask_clarification(topic, value) answers business questions the spec does not determine",
    }


def write_project(p, inputs_dir, truth_dir):
    """inputs/: docs/ + batch1/ batch2/ batch3/ (each a landing tree; batch3 is held out from the engineer);
    truth/truth.json for the evaluator only."""
    inputs_dir, truth_dir = Path(inputs_dir), Path(truth_dir)
    (inputs_dir / "docs").mkdir(parents=True, exist_ok=True)
    (inputs_dir / "docs/spec.json").write_text(json.dumps(p["spec"], indent=1, sort_keys=True))
    (inputs_dir / "docs/README.md").write_text(render_readme(p["spec"]))
    pick = lambda d, b: d[b] if b in d else d[str(b)]          # int keys, or str keys after a JSON round trip
    for b in BATCHES:
        root = inputs_dir / f"batch{b}"
        for rel, text in pick(p["files"], b).items():
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text)
        db = root / "source.db"
        if db.exists():
            db.unlink()
        con = sqlite3.connect(db)
        con.executescript(pick(p["dbs"], b))
        con.close()
    truth_dir.mkdir(parents=True, exist_ok=True)
    (truth_dir / "truth.json").write_text(json.dumps(p["truth"], sort_keys=True, default=str))


def render_readme(spec):
    out = [f"# Project {spec['project']}", "", spec["goal"], "", "## Sources"]
    out += [f"* **{k}**: {v}" for k, v in spec["sources"].items()]
    out += ["", "## Rules"] + [f"* **{k}**: {v if isinstance(v, str) else v['text']}" for k, v in spec["rules"].items()]
    out += ["", f"Deletion: {spec['deletion_rules']}", f"CDC: {spec['cdc']['semantics']}", f"Late events: {spec['late_event_rule']}",
            f"Retention: {spec['retention']}", f"Freshness: {spec['freshness']}", f"Idempotency: {spec['idempotency']}", ""]
    return "\n".join(out)
