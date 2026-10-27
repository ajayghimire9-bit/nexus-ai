"""Stage 4-5 streaming logistics environment (NOT LOCKED).

make_world(seed, split) -> a clean TRUTH world (order version timeline incl. a pre-history snapshot, telemetry, supplier
manifests, schema-registry evolution) plus a predeclared spec. encode(world, scenario, incidents) -> a partitioned,
append-only OFFSET LOG delivered tick by tick (one segment file per tick per partition, explicit offsets), exactly what a
streaming consumer sees:
  _schemas         registry messages. Subject orders: v1; v2 renames amount + adds a column (tick 4); v3 widens discount
                   int->float (tick 6). Subject telemetry: v1 iso event_ts; v2 epoch-ms event_ts from tick 7
                   [WITHHELD class W2: test worlds only]
  orders_cdc       live Debezium-style envelopes: op c/u/d, source_version (a monotone commit position, like a WAL LSN:
                   the ONLY ordering authority for a key), event_ts (business time, mixed UTC offsets), schema_version,
                   msg_id (event identity); delivery is out of order across retries / partitions; soft + hard deletes;
                   producer-retry duplicates; a 3rd partition appears at tick 7 [WITHHELD class W1: test worlds only]
  backfill_orders  a historical snapshot (op r) taken at snapshot source_version SV0 (lower than every live change),
                   streamed CONCURRENTLY with live CDC (ticks 2-6 in the build scenario); some keys were updated or deleted
                   live before their snapshot row arrives, so precedence must come from source_version, not arrival
  telemetry        PICKED / DELIVERED events; event-time watermark lateness; duplicates
  manifests        supplier weights (kg) with producer metadata; malformed rows; duplicates
Scenario 'build' (Stage 4): no incidents; the engineer sees ticks 1-8, the evaluator also runs held-out ticks 9-12.
Scenario 'ops' (Stage 5): ticks 1-14, backfill at ticks 7-10, plus the world's hidden-cause incidents (s5_ops).
Truth is never derived from the log; the evaluator's reference reads only the truth."""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

T0 = datetime(2026, 4, 1, tzinfo=timezone.utc)
D = timedelta(days=2)
NT = {"build": 12, "ops": 14}
VISIBLE = 8
SPLIT_POOLS = {"src": (0,), "dev": (0,), "val": (0, 1), "test": (1, 2)}
TOPICS = ["_schemas", "orders_cdc", "backfill_orders", "telemetry", "manifests"]
NAMES = {"order_id": ("order_id", "ord_id", "order_ref"), "warehouse_id": ("warehouse_id", "wh_id", "site_code"),
         "status": ("status", "order_status", "lifecycle_state"), "amount": ("amount", "total", "gross_value"),
         "amount_v2": ("amount_total", "total_value", "value_gross"), "currency": ("currency", "ccy", "currency_code"),
         "discount": ("discount_pct", "disc", "rebate_pct"), "promised_ts": ("promised_ts", "promise_by", "sla_deadline"),
         "deleted": ("is_deleted", "deleted", "void_flag"), "channel": ("channel", "sales_channel", "origin")}
FX = ({"USD": 1.0, "EUR": 1.08, "GBP": 1.27}, {"USD": 1.0, "EUR": 1.08, "GBP": 1.27},
      {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CHF": 1.12})
LATENESS_H = ([12, 24], [12, 24], [6, 36])
SUPPLIERS = ["S1", "S2", "S3"]
SUPPLIER_KG = [5.0, 20.0, 2.0]
OFFS = [timedelta(hours=-5), timedelta(hours=2), timedelta(hours=9), timedelta(0)]
BUCKETS = {"PLACED": "open", "SHIPPED": "open", "DELIVERED": "fulfilled", "RETURNED": "fulfilled", "CANCELLED": "cancelled"}
UNITS_TO_KG = {"kg": 1.0, "lb": 0.45359237, "g": 0.001}
OUTPUTS = {
    "silver_orders": (["order_id", "warehouse_id", "status", "net_usd"], ["order_id"]),
    "gold_warehouse_revenue": (["warehouse_id", "revenue_usd"], ["warehouse_id"]),
    "gold_status_counts": (["warehouse_id", "bucket", "n"], ["warehouse_id", "bucket"]),
    "gold_sla": (["warehouse_id", "delivered", "on_time", "on_time_rate"], ["warehouse_id"]),
    "late_events": (["msg_id"], ["msg_id"]),
    "gold_supplier_volume": (["warehouse_id", "supplier", "weight_kg"], ["warehouse_id", "supplier"]),
    "quarantine": (["topic", "msg_id", "reason"], ["topic", "msg_id"]),
    "record_accounting": (["topic", "status", "n"], ["topic", "status"]),
}


def iso(dt, off=timedelta(0)):
    d = (dt + off).replace(microsecond=0)
    if off == timedelta(0):
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")
    sign = "+" if off >= timedelta(0) else "-"
    m = abs(int(off.total_seconds())) // 60
    return d.strftime("%Y-%m-%dT%H:%M:%S") + f"{sign}{m // 60:02d}:{m % 60:02d}"


def tick_of(ingest):
    return int((ingest - T0) / D) + 1 if ingest > T0 else 1


class _G:
    def __init__(self, seed, split):
        self.r = random.Random(f"de2:{split}:{seed}")
        pools = SPLIT_POOLS[split]
        r = self.r
        self.n = {k: v[r.choice(pools)] for k, v in NAMES.items()}
        self.fx = dict(FX[max(pools)])
        self.L = r.choice(LATENESS_H[r.choice(pools)])
        self.tz_mixed = r.random() < 0.7
        self.withheld = split == "test"          # W1 partition growth + W2 epoch-ms timestamps exist only in test worlds


def _versions(g):
    """Live orders (created after T0) and historical orders (state as of T0 arrives only through the backfill snapshot)."""
    r = g.r
    whs = ["W1", "W2", "W3", "W4"]
    live, hist = [], []
    disc_float_from = T0 + 5 * D           # schema v3 (discount widened to float) is effective from tick 6

    def disc(t):
        return r.choice([0, 5, 10, 15, 20]) if t < disc_float_from or r.random() < 0.5 else r.choice([2.5, 7.5, 12.5, 17.5])

    def flow(key, t, row, out, allow_hist=False):
        vs = []
        u = r.random()
        if u < 0.8:
            t = t + timedelta(hours=r.uniform(8, 40)); vs.append((t, dict(row, status="SHIPPED"), "u"))
            if r.random() < 0.75:
                t = t + timedelta(hours=r.uniform(20, 70)); vs.append((t, dict(vs[-1][1], status="DELIVERED"), "u"))
                if r.random() < 0.06:
                    t = t + timedelta(hours=r.uniform(10, 40)); vs.append((t, dict(vs[-1][1], status="RETURNED"), "u"))
        elif u < 0.9:
            t = t + timedelta(hours=r.uniform(2, 20)); vs.append((t, dict(row, status="CANCELLED"), "u"))
        if r.random() < 0.2:                                       # retroactive correction (often ingested late)
            base = vs[-1][1] if vs else row
            tt = t + timedelta(hours=r.uniform(1, 30))
            vs.append((tt, dict(base, amount=round(base["amount"] * r.uniform(0.7, 1.2), 2), discount=disc(tt)), "u"))
            t = tt
        x = r.random()
        if x < 0.07:
            vs.append((t + timedelta(hours=r.uniform(1, 30)), None, "d"))
        elif x < 0.14:
            vs.append((t + timedelta(hours=r.uniform(1, 30)), dict(vs[-1][1] if vs else row), "soft"))
        for vt, vr, op in vs:
            out.append(dict(key=key, t=vt, row=vr, op="u" if op == "soft" else op, soft=op == "soft"))

    for i in range(80):
        key = 1000 + i
        tc = T0 + timedelta(hours=r.uniform(1, 26 * 24))
        cur = r.choice(sorted(g.fx))
        row = dict(order_id=key, warehouse_id=r.choice(whs), status="PLACED", amount=round(r.uniform(20, 900), 2),
                   currency=cur, discount=disc(tc), promised_ts=tc + timedelta(days=r.uniform(2.5, 5)), channel="web")
        live.append(dict(key=key, t=tc, row=row, op="c", soft=False))
        flow(key, tc, row, live)
    for i in range(30):                                              # pre-history: snapshot as of T0
        key = 500 + i
        tc = T0 - timedelta(hours=r.uniform(48, 20 * 24))
        st = r.choice(["PLACED", "SHIPPED", "SHIPPED", "DELIVERED"])
        row = dict(order_id=key, warehouse_id=r.choice(whs), status=st, amount=round(r.uniform(20, 900), 2),
                   currency=r.choice(sorted(g.fx)), discount=r.choice([0, 5, 10]), promised_ts=tc + timedelta(days=4),
                   channel="store")
        hist.append(dict(key=key, row=row))
        if r.random() < 0.45:                                        # live changes to historical orders after T0
            t = T0 + timedelta(hours=r.uniform(2, 12 * 24))
            if r.random() < 0.35:
                live.append(dict(key=key, t=t, row=None, op="d", soft=False))
            else:
                nxt = {"PLACED": "SHIPPED", "SHIPPED": "DELIVERED", "DELIVERED": "RETURNED"}[st]
                live.append(dict(key=key, t=t, row=dict(row, status=nxt), op="u", soft=False))
    return whs, live, hist


def make_world(seed, split):
    for attempt in range(300):
        g = _G(f"{seed}:{attempt}", split)
        whs, live, hist = _versions(g)
        w = dict(seed=seed, split=split, attempt=attempt, whs=whs, n=g.n, fx=g.fx, L=g.L, tz_mixed=g.tz_mixed,
                 withheld=g.withheld, live=live, hist=hist, rseed=f"de2-enc:{split}:{seed}:{attempt}")
        enc = encode(w, "build")
        f = features(enc["truth"])
        ok = (f["out_of_order_keys"] >= 2 and f["late_corrections"] >= 2 and f["backfill_overwrite_traps"] >= 2
              and f["backfill_resurrection_traps"] >= 2 and f["late_telemetry"] >= 2 and f["soft"] >= 1 and f["hard"] >= 1
              and f["dups"] >= 2 and f["float_discounts"] >= 2 and f["renamed_amounts"] >= 2 and f["malformed"] >= 1
              and f["heldout_late_corrections"] >= 1 and (not g.withheld or f["partition2_keys"] >= 2))
        if ok:
            w["features"] = f
            w["spec"] = spec(w)
            return w
    raise RuntimeError("could not realise every fault class")


def _ingest(r, t, late_p, lo_h, hi_h):
    if r.random() < late_p:
        return t + timedelta(hours=r.uniform(lo_h, hi_h))
    return t + timedelta(minutes=r.uniform(1, 90))


def encode(w, scenario, incidents=(), hook=None):
    """Log + truth for a scenario. Returns dict(log={tick: {(topic, part): [records]}}, truth=...). hook(pending, w, r,
    scenario) -> dict (R1 withheld classes; default None = the Stages 4-6 behaviour, byte-for-byte) may append records
    before offsets are assigned; its returned dict is merged into the truth."""
    r = random.Random(w["rseed"] + ":" + scenario)
    n, nt = w["n"], NT[scenario]
    end = T0 + nt * D
    sched = {2: 1, 3: 4, 4: 6}                                         # schema version -> effective tick
    if w["withheld"]:
        sched[5] = 7                                                    # W2: v4 (epoch-ms event_ts) from tick 7 (index 5 = v4)
    log, truth_v, tel, man = {}, [], [], []
    offs = {}

    pending = []

    def put(tick, topic, part, rec):
        """Queue a record; offsets are assigned at the end in ingest order per partition (an append-only log)."""
        rec = dict(rec)
        pending.append((tick, topic, part, rec))
        return rec

    # registry
    regs = [(1, 1, dict(fields={c: n[c] for c in ("order_id", "warehouse_id", "status", "amount", "currency", "discount",
                                                   "promised_ts", "deleted")}, types={"discount": "int"}))]
    f2 = dict(regs[0][2]["fields"], amount=n["amount_v2"], channel=n["channel"])
    regs.append((2, 4, dict(fields=f2, types={"discount": "int"})))
    regs.append((3, 6, dict(fields=f2, types={"discount": "float"})))
    tregs = [(1, 1, dict(ts_format="iso"))] + ([(2, 7, dict(ts_format="epoch_ms"))] if w["withheld"] else [])
    for subj, rs in (("orders", regs), ("telemetry", tregs)):
        for v, tk, body in rs:
            put(tk, "_schemas", 0, dict(msg_id=f"reg-{subj}-{v}", ingest_ts=iso(T0 + (tk - 1) * D + timedelta(minutes=1)),
                                        subject=subj, version=v, **body))

    def tel_version(tick):
        return max(v for v, tk, _ in tregs if tk <= tick)
    tregmap = {v: b for v, _, b in tregs}

    def version_at(tick):
        return max(v for v, tk, _ in regs if tk <= tick)
    regmap = {v: b for v, _, b in regs}

    def payload(row, soft, v):
        b = regmap[v]
        fl = b["fields"]
        out = {fl[c]: row[c] for c in ("order_id", "warehouse_id", "status", "amount", "currency") if c in row}
        out[fl["discount"]] = row["discount"] if b["types"]["discount"] == "float" else int(row["discount"])
        out[fl["promised_ts"]] = iso(row["promised_ts"])
        out[fl["deleted"]] = 1 if soft else 0
        if "channel" in fl:
            out[fl["channel"]] = row.get("channel", "web")
        return out

    first_tick = {}
    # live CDC; source_version = commit position in event (commit) order; the snapshot was taken at SV0 = 1000
    events = sorted(w["live"], key=lambda v: (v["t"], v["key"]))
    lsn = {id(v): 1001 + i for i, v in enumerate(events)}
    for v in events:
        if v["t"] >= end - timedelta(hours=1):
            continue
        late = r.random() < (0.25 if v["op"] == "u" and v["row"] and v["row"].get("amount") else 0.10)
        ing = _ingest(r, v["t"], 0.12 if late else 0.0, 30, 110)
        if ing >= end:
            continue
        tk = tick_of(ing)
        if v["row"] is not None and v["row"]["discount"] != int(v["row"]["discount"]) and version_at(tk) < 3:
            v = dict(v, row=dict(v["row"], discount=int(v["row"]["discount"])))   # a float discount needs schema v3
        first_tick.setdefault(v["key"], tk)
        nparts = 3 if (w["withheld"] and first_tick[v["key"]] >= 7) else 2
        part = v["key"] % nparts
        sv = version_at(tk)
        off = r.choice(OFFS) if w["tz_mixed"] else timedelta(0)
        ets = iso(v["t"], off)
        mid = f"o{len(truth_v):05d}"
        rec = dict(msg_id=mid, ingest_ts=iso(ing), op=v["op"], event_ts=ets, key=v["key"], schema_version=sv,
                   source_version=lsn[id(v)], after=payload(v["row"], v["soft"], sv) if v["row"] else None)
        o = put(tk, "orders_cdc", part, rec)
        tv = dict(key=v["key"], event_ts=iso(v["t"]), event_raw=ets, op=v["op"], row=_canon(v["row"]), soft=v["soft"],
                  topic="orders_cdc", copies=[(tk, part, o)], tick=tk, msg_id=mid, schema_version=sv, sv=lsn[id(v)])
        if r.random() < 0.05:                                             # producer retry duplicate (same msg_id)
            tk2 = min(nt, tk + r.randint(0, 1))
            o2 = put(tk2, "orders_cdc", part, dict(rec, ingest_ts=iso(max(ing, T0 + (tk2 - 1) * D + timedelta(minutes=5)))))
            tv["copies"].append((tk2, part, o2))
        truth_v.append(tv)
    # backfill snapshot (concurrent with live)
    bf_ticks = (2, 6) if scenario == "build" else (7, 10)
    hist = sorted(w["hist"], key=lambda h: h["key"])
    span = (bf_ticks[1] - bf_ticks[0] + 1) * D
    t_begin = T0 + (bf_ticks[0] - 1) * D
    controls = [dict(tick=bf_ticks[0], kind="snapshot_begin"), dict(tick=bf_ticks[1], kind="snapshot_end")]
    put(bf_ticks[0], "backfill_orders", 0, dict(msg_id="snap-1-begin", ingest_ts=iso(t_begin + timedelta(minutes=2)),
                                                control="snapshot_begin", snapshot_id=1, rows=len(hist)))
    snap_ts = T0 - timedelta(minutes=1)
    for i, h in enumerate(hist):
        ing = t_begin + span * (i + 0.5) / len(hist)
        tk = tick_of(ing)
        mid = f"b1-{h['key']}"
        rec = dict(msg_id=mid, ingest_ts=iso(ing), op="r", event_ts=iso(snap_ts), key=h["key"], schema_version=1,
                   source_version=1000, snapshot_id=1, after=payload(h["row"], False, 1))
        o = put(tk, "backfill_orders", 0, rec)
        truth_v.append(dict(key=h["key"], event_ts=iso(snap_ts), event_raw=iso(snap_ts), op="r", row=_canon(h["row"]),
                            soft=False, topic="backfill_orders", copies=[(tk, 0, o)], tick=tk, msg_id=mid, schema_version=1,
                            sv=1000))
    put(bf_ticks[1], "backfill_orders", 0, dict(msg_id="snap-1-end", ingest_ts=iso(t_begin + span - timedelta(minutes=5)),
                                                control="snapshot_end", snapshot_id=1, rows=len(hist)))
    # telemetry + manifests for every order that ships / delivers (live and historical)
    state_t = {}
    for v in sorted(truth_v, key=lambda v: v["event_ts"]):
        if v["row"] and v["topic"] == "orders_cdc" and v["row"]["status"] in ("SHIPPED", "DELIVERED"):
            state_t.setdefault((v["key"], v["row"]["status"]), datetime.fromisoformat(v["event_ts"].replace("Z", "+00:00")))
    for (key, st), t in sorted(state_t.items()):
        typ = "PICKED" if st == "SHIPPED" else "DELIVERED"
        et = t + timedelta(minutes=r.uniform(-120, 120))
        ing = _ingest(r, et, 0.12, 50, 140)
        if ing >= end or et <= T0:
            continue
        tk = tick_of(ing)
        part = key % 2
        mid = f"t{len(tel):05d}"
        off = r.choice(OFFS) if w["tz_mixed"] else timedelta(0)
        tsv = tel_version(tk)
        raw = int(et.timestamp() * 1000) if tregmap[tsv]["ts_format"] == "epoch_ms" else iso(et, off)
        rec = dict(msg_id=mid, ingest_ts=iso(ing), order_id=key, type=typ, event_ts=raw, schema_version=tsv)
        o = put(tk, "telemetry", part, rec)
        e = dict(msg_id=mid, order_id=key, type=typ, event_ts=iso(et), event_raw=rec["event_ts"],
                 copies=[(tk, part, o, iso(ing))])
        if r.random() < 0.06:
            tk2 = min(nt, tk + r.randint(0, 1))
            ing2 = max(ing + timedelta(minutes=3), T0 + (tk2 - 1) * D + timedelta(minutes=5))
            o2 = put(tk2, "telemetry", part, dict(rec, ingest_ts=iso(ing2)))
            e["copies"].append((tk2, part, o2, iso(ing2)))
        tel.append(e)
        if typ == "PICKED":
            kg = round(SUPPLIER_KG[key % 3] * math.exp(r.gauss(0, 0.35)), 3)   # per-supplier product weights (log-normal)
            mal = r.random() < 0.04
            ing_m = ing + timedelta(minutes=r.uniform(1, 30))
            if ing_m >= end:
                continue
            tkm = tick_of(ing_m)
            mm = f"m{len(man):05d}"
            sup = SUPPLIERS[key % 3]
            rec = dict(msg_id=mm, ingest_ts=iso(ing_m), order_id=key, supplier=sup, weight="N/A" if mal else kg,
                       producer_version="v1")
            o = put(tkm, "manifests", 0, rec)
            m = dict(msg_id=mm, order_id=key, supplier=sup, kg=None if mal else kg, raw=rec["weight"], kind="malformed" if mal else "valid",
                     copies=[(tkm, 0, o)], producer_version="v1")
            if r.random() < 0.05:
                tk2 = min(nt, tkm + 1)
                o2 = put(tk2, "manifests", 0, dict(rec, ingest_ts=iso(max(ing_m, T0 + (tk2 - 1) * D + timedelta(minutes=7)))))
                m["copies"].append((tk2, 0, o2))
            man.append(m)
    extra = hook(pending, w, random.Random(w["rseed"] + ":hook:" + scenario), scenario) if hook else {}
    for i, (tk, topic, part, rec) in sorted(enumerate(pending), key=lambda x: (x[1][1], x[1][2], x[1][0], x[1][3]["ingest_ts"], x[0])):
        k = (topic, part)
        rec["offset"] = offs.get(k, 0)
        offs[k] = rec["offset"] + 1
        log.setdefault(tk, {}).setdefault(k, []).append(rec)
    for coll in (truth_v, tel, man):
        for x in coll:
            x["copies"] = [(c[0], c[1], c[2]["offset"]) + tuple(c[3:]) for c in x["copies"]]
    truth = dict(scenario=scenario, nt=nt, whs=w["whs"], fx=w["fx"], L=w["L"], buckets=dict(BUCKETS), versions=truth_v,
                 telemetry=tel, manifests=man, snapshot_rows=len(hist), withheld=w["withheld"], incidents=[], controls=controls,
                 schemas={v: dict(tick=tk, **b) for v, tk, b in regs},
                 tel_schemas={v: dict(tick=tk, **b) for v, tk, b in tregs})
    truth.update(extra)
    out = dict(log=log, truth=truth)
    for inc in incidents:                                              # Stage 5 hidden-cause incidents mutate log + truth
        inc.apply(out, w, r)
    return out


def _canon(row):
    if row is None:
        return None
    d = dict(row)
    d["promised_ts"] = iso(row["promised_ts"])
    return d


def features(t):
    by = {}
    for v in t["versions"]:
        if v["topic"] == "orders_cdc":
            by.setdefault(v["key"], []).append(v)
    ooo = sum(1 for vs in by.values() if [x["copies"][0] for x in sorted(vs, key=lambda x: x["sv"])] !=
              sorted(x["copies"][0] for x in vs))
    late_corr = 0
    for vs in by.values():
        last = max(vs, key=lambda x: x["sv"])
        earlier_max = max((x["sv"] for x in t["versions"] if x["tick"] < last["tick"] and x["topic"] == "orders_cdc"), default=0)
        late_corr += last["tick"] > 1 and last["sv"] < earlier_max and last["op"] == "u"
    bf = {v["key"]: v for v in t["versions"] if v["topic"] == "backfill_orders"}
    over = sum(1 for k, b in bf.items() if any(x["tick"] <= b["tick"] and x["op"] == "u" for x in by.get(k, [])))
    res = sum(1 for k, b in bf.items() if any(x["tick"] <= b["tick"] and x["op"] == "d" for x in by.get(k, [])))
    lat = 0
    wm_by_tick = {}
    for e in t["telemetry"]:
        for tk, *_ in e["copies"]:
            wm_by_tick.setdefault(tk, []).append(e["event_ts"])
    for e in t["telemetry"]:
        tk = e["copies"][0][0]
        prev = [x for k, xs in wm_by_tick.items() if k < tk for x in xs]
        if prev:
            wm = datetime.fromisoformat(max(prev).replace("Z", "+00:00")) - timedelta(hours=t["L"])
            lat += datetime.fromisoformat(e["event_ts"].replace("Z", "+00:00")) < wm
    vis = [v for v in t["versions"] if v["tick"] <= VISIBLE]
    return dict(out_of_order_keys=ooo, late_corrections=late_corr, backfill_overwrite_traps=over,
                backfill_resurrection_traps=res, late_telemetry=lat, soft=sum(v["soft"] for v in vis),
                hard=sum(v["op"] == "d" for v in vis), dups=sum(len(v["copies"]) > 1 for v in vis),
                float_discounts=sum(1 for v in vis if v["row"] and v["row"]["discount"] != int(v["row"]["discount"])),
                renamed_amounts=sum(1 for v in vis if v["schema_version"] >= 2 and v["row"]),
                malformed=sum(m["kind"] == "malformed" for m in t["manifests"]),
                heldout_late_corrections=sum(1 for vs in by.values() for x in vs if x["tick"] > VISIBLE and x["op"] == "u"),
                partition2_keys=len({v["key"] for v in t["versions"] if v["copies"][0][1] == 2 and v["topic"] == "orders_cdc"}))


def spec(w):
    n = w["n"]
    return {
        "project": f"{w['split']}-{w['seed']}",
        "goal": "Operate an exactly-once streaming pipeline from the offset log into state/lake.db producing the outputs.",
        "log": {"layout": "log/<topic>/p<partition>/<base_offset>.jsonl; one segment per tick; records carry 'offset'",
                "topics": TOPICS, "processing_order": TOPICS,
                "partitions": "a topic may gain partitions at any time; every partition directory present must be consumed",
                "retention": "segments older than 6 ticks may be deleted; a consumer cannot rely on re-reading them",
                "delivery": "at-least-once: a record can be redelivered at a later offset with the same msg_id"},
        "ticks": {"t0": iso(T0), "tick_hours": 48, "rule": "tick(record) = ceil((ingest_ts - t0) / 48h), minimum 1"},
        "registry": {"topic": "_schemas", "subjects": ["orders", "telemetry"],
                     "semantics": "every orders / telemetry record names its schema_version (per subject); orders fields map "
                                  "canonical -> physical names; types declare value types; telemetry ts_format declares the "
                                  "event_ts encoding (iso | epoch_ms)"},
        "identity": "msg_id identifies an event; a redelivered record (same msg_id, any offset) is the same event",
        "cdc": {"semantics": "per key, the change with the highest source_version wins, across live CDC and the backfill "
                             "snapshot (snapshot rows carry the snapshot's source_version); arrival order and event_ts never "
                             "decide CDC order; a delete (op d, or deleted flag = 1) is a tombstone that a lower-versioned row "
                             "arriving later cannot revive",
                "backfill": "backfill_orders carries a snapshot (op r) streamed concurrently with live changes; control "
                            "records snapshot_begin (with row count) / snapshot_end / snapshot_aborted bound it; a snapshot "
                            "must be complete"},
        "visibility": "output tables change only at a run's final commit; readers see the last committed run",
        "accounting": "record_accounting lists, per topic, how many records were applied, duplicates, late, and quarantined; "
                      "every consumed record is accounted for (nothing silently disappears)",
        "net_usd": "round(amount * (1 - discount/100) * fx_to_usd[currency], 2)",
        "fx_to_usd": w["fx"], "status_buckets": dict(BUCKETS),
        "lateness": {"allowed_hours": w["L"],
                     "rule": "watermark(tick k) = max event_ts of telemetry records of ticks < k minus allowed_hours; a "
                             "telemetry record of tick k with event_ts < watermark(k) is late: listed in late_events and "
                             "excluded from gold_sla",
                     "future_events": "a telemetry record with event_ts more than 5 minutes after its ingest_ts is invalid "
                                      "(producer clock skew): quarantine reason future_event; excluded from the watermark"},
        "units": {"to_kg": UNITS_TO_KG, "rule": "supplier weights are kg; if a supplier's feed silently changes unit, weights "
                                                "from the first affected message must be converted to kg"},
        "rules": {"silver_orders": "current, non-deleted orders",
                  "gold_warehouse_revenue": "per warehouse (all 4: W1-W4, 0 if none): sum net_usd of silver orders with status "
                                            "DELIVERED",
                  "gold_status_counts": "per (warehouse, bucket): number of silver orders",
                  "gold_sla": "per warehouse with >= 1: delivered = silver orders with a non-late DELIVERED telemetry event "
                              "(first by msg_id); on_time = event_ts <= promised_ts; rate = round(on_time/delivered, 4)",
                  "gold_supplier_volume": "per (warehouse, supplier): sum weight_kg of valid manifests (one per msg_id) of "
                                          "silver orders not CANCELLED, rounded to 3 decimals"},
        "quarantine": {"reasons": ["malformed_weight", "future_event", "poison"],
                       "rule": "malformed or undecodable records are quarantined, never dropped or zero-filled"},
        "exactly_once": "after any crash and restart, the state must equal an uninterrupted run",
        "rollback": "pipeline.py --rollback-to K restores tables, offsets and processing state as of the end of tick K; "
                    "acknowledged records after K are re-read from the log (they must not be lost); a crash during "
                    "rollback must be recovered on the next start (the atomicity boundary is declared by the pipeline)",
        "outputs": {k: {"columns": c, "pk": p} for k, (c, p) in OUTPUTS.items()},
        "physical_names_v1": {c: n[c] for c in ("order_id", "warehouse_id", "status", "amount", "currency", "discount",
                                                 "promised_ts", "deleted")},
    }


def write_log(enc, root, upto, start=1):
    """Write segments of ticks start..upto under root/log (one file per tick per partition)."""
    root = Path(root)
    if start == 1:          # every partition is provisioned at tick 1, except W1's partition that appears mid-stream
        for k in sorted({k for v in enc["log"].values() for k in v}):
            if not (k[0] == "orders_cdc" and k[1] >= 2):
                (root / "log" / k[0] / f"p{k[1]}").mkdir(parents=True, exist_ok=True)
    for tk in range(start, upto + 1):
        for (topic, part), recs in sorted(enc["log"].get(tk, {}).items()):
            d = root / "log" / topic / f"p{part}"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{recs[0]['offset']:08d}.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in recs))


def retention(root, tick, keep=6):
    """Delete segments of ticks <= tick - keep (a segment's tick = its records' tick)."""
    for f in Path(root, "log").rglob("*.jsonl"):
        first = json.loads(f.read_text().split("\n", 1)[0])
        if tick_of(datetime.fromisoformat(first["ingest_ts"].replace("Z", "+00:00"))) <= tick - keep:
            f.unlink()


def world_to_json(w):
    def enc(x):
        if isinstance(x, datetime):
            return {"__dt__": x.isoformat()}
        if isinstance(x, dict):
            return {k: enc(v) for k, v in x.items()}
        if isinstance(x, list):
            return [enc(v) for v in x]
        return x
    return json.dumps(enc(w), sort_keys=True)


def world_from_json(s):
    def dec(x):
        if isinstance(x, dict):
            if set(x) == {"__dt__"}:
                return datetime.fromisoformat(x["__dt__"])
            return {k: dec(v) for k, v in x.items()}
        if isinstance(x, list):
            return [dec(v) for v in x]
        return x
    return dec(json.loads(s))
