#!/usr/bin/env python3
"""Generated logistics pipeline. Decisions: {"bronze_dedup": "dedup", "bucket_uncovered": "other", "carrier_uncovered": "exclude", "cdc_apply": "event_time", "cdc_incremental": "rebuild", "deletes": "soft_and_hard", "dims_load": "replace", "drift": "alias", "fx": "table", "revenue_join": "semi_join", "sla_window": "apply", "ts_parse": "utc", "units": "table", "weight_parse": "drop_silent"}
Contract: python pipeline.py --landing DIR --state DIR --config FILE (state/lake.db: bronze, silver and gold tables)."""
import argparse, csv, glob, hashlib, json, os, re, sqlite3
from datetime import datetime, timezone

DEC = {"bronze_dedup": "dedup", "bucket_uncovered": "other", "carrier_uncovered": "exclude", "cdc_apply": "event_time", "cdc_incremental": "rebuild", "deletes": "soft_and_hard", "dims_load": "replace", "drift": "alias", "fx": "table", "revenue_join": "semi_join", "sla_window": "apply", "ts_parse": "utc", "units": "table", "weight_parse": "drop_silent"}


class StageError(Exception):
    pass


def q(s):
    return '"' + str(s).replace('"', '""') + '"'


def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def tkey(s):
    if DEC["ts_parse"] == "utc":
        return utc(s).strftime("%Y-%m-%dT%H:%M:%S")
    return s


def is_deleted(row_get, cfg):
    d = cfg["deletion"]
    v = row_get(d["column"])
    if d["kind"] == "flag":
        return v is not None and str(v) in {str(x) for x in d["deleted_values"]}
    return v not in (None, "")


def setup(con):
    pk = DEC["bronze_dedup"] == "dedup"
    con.execute("CREATE TABLE IF NOT EXISTS bronze_cdc (seq INTEGER %s, event_ts TEXT, ingest_ts TEXT, op TEXT, k TEXT, after TEXT)"
                % ("PRIMARY KEY" if pk else ""))
    con.execute("CREATE TABLE IF NOT EXISTS bronze_events (event_id TEXT %s, shipment_id TEXT, type TEXT, event_ts TEXT, "
                "ingest_ts TEXT)" % ("PRIMARY KEY" if pk else ""))
    con.execute("CREATE TABLE IF NOT EXISTS bronze_manifest (record_ref TEXT %s, shipment_id TEXT, weight_kg REAL, reason TEXT)"
                % ("PRIMARY KEY" if pk else ""))
    con.execute("CREATE TABLE IF NOT EXISTS dim_shipments (shipment_id TEXT, order_id INTEGER, carrier TEXT, shipped_ts TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS dim_warehouses (warehouse_id TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS dim_inventory (adj_id TEXT, warehouse_id TEXT, sku TEXT, qty INTEGER, deleted INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS silver_state (k TEXT PRIMARY KEY, after TEXT, tk TEXT, seq INTEGER)")
    con.commit()


def ins(con, table, row):
    verb = "INSERT OR IGNORE" if DEC["bronze_dedup"] == "dedup" else "INSERT"
    con.execute(f"{verb} INTO {table} VALUES ({','.join('?' * len(row))})", row)


def ingest_dims(con, landing, cfg):
    src = sqlite3.connect(f"file:{os.path.join(landing, 'source.db')}?mode=ro", uri=True)
    db = cfg["db"]
    s, w, i = db["shipments"], db["warehouses"], db["inventory"]
    sc, ic = s["columns"], i["columns"]
    ships = src.execute(f"SELECT {q(sc['shipment_id'])}, {q(sc['order_id'])}, {q(sc['carrier'])}, {q(sc['shipped_ts'])} "
                        f"FROM {q(s['table'])}").fetchall()
    whs = src.execute(f"SELECT {q(w['columns']['warehouse_id'])} FROM {q(w['table'])}").fetchall()
    cur = src.execute(f"SELECT * FROM {q(i['table'])}")
    names = [c[0] for c in cur.description]
    inv = []
    for r in cur.fetchall():
        get = lambda c, r=r: r[names.index(c)] if c in names else None
        dele = 1 if (DEC["deletes"] == "soft_and_hard" and is_deleted(get, cfg)) else 0
        inv.append((get(ic["adj_id"]), get(ic["warehouse_id"]), get(ic["sku"]), get(ic["qty"]), dele))
    src.close()
    if DEC["dims_load"] == "replace":
        for t in ("dim_shipments", "dim_warehouses", "dim_inventory"):
            con.execute(f"DELETE FROM {t}")
    con.executemany("INSERT INTO dim_shipments VALUES (?,?,?,?)", ships)
    con.executemany("INSERT INTO dim_warehouses VALUES (?)", whs)
    con.executemany("INSERT INTO dim_inventory VALUES (?,?,?,?,?)", inv)
    con.commit()


def ingest_cdc(con, landing, cfg):
    pk = cfg["orders_cols"]["order_id"]
    for f in sorted(glob.glob(os.path.join(landing, "cdc", "*.jsonl"))):
        with open(f) as fh:
            for line in fh:
                if not line.strip():
                    continue
                e = json.loads(line)
                if e.get("source") not in (None, cfg["cdc_source"]):
                    continue
                ins(con, "bronze_cdc", (e["seq"], e["event_ts"], e["ingest_ts"], e["op"], str(e["key"][pk]),
                                        json.dumps(e["after"], sort_keys=True)))
        con.commit()


def ingest_events(con, landing, cfg):
    c = cfg["events_cols"]
    for f in sorted(glob.glob(os.path.join(landing, "events", "*.jsonl"))):
        with open(f) as fh:
            for line in fh:
                if line.strip():
                    e = json.loads(line)
                    ins(con, "bronze_events", (e[c["event_id"]], e[c["shipment_id"]], e[c["event_type"]], e[c["event_ts"]],
                                               e[c["ingest_ts"]]))
        con.commit()


NUM = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([A-Za-z.]*)\s*$")


def parse_weight(tok, unit_tok, cfg):
    """-> (kg, reason). reason None = valid; 'DROP' = silently dropped."""
    mode, units = DEC["weight_parse"], cfg["units"]
    if unit_tok is None:
        m = NUM.match(tok)
        num, unit = (m.group(1), m.group(2)) if m else (tok, "")
    else:
        num, unit = tok, unit_tok.strip()
    if mode == "float_strict":
        value = float(num)
    else:
        try:
            value = float(num)
        except ValueError:
            if mode == "coerce_zero":
                return 0.0, None
            return (None, "DROP") if mode == "drop_silent" else (None, "unparseable_weight")
    if DEC["units"] == "assume_kg":
        return value, None
    if unit not in units:
        return (None, "DROP") if mode == "drop_silent" else (None, "unknown_unit")
    return value * units[unit], None


def ingest_manifests(con, landing, cfg):
    mc = cfg["manifest"]
    for f in sorted(glob.glob(os.path.join(landing, "drops", "*.csv"))):
        with open(f, newline="") as fh:
            lines = fh.read().split("\n")
        header = next(csv.reader([lines[0]]))
        try:
            i_s = next(header.index(a) for a in mc["shipment_id"] if a in header)
            if DEC["drift"] == "strict":
                i_w = header.index(mc["weight"][0])
            else:
                i_w = next(header.index(a) for a in mc["weight"] if a in header)
        except (ValueError, StopIteration) as e:
            raise StageError(f"stage=manifest_header {type(e).__name__}: {e} in {os.path.basename(f)}") from e
        i_u = next((header.index(a) for a in mc["unit"] if a in header), None)
        for line in lines[1:]:
            if not line:
                continue
            ref = hashlib.sha1(line.encode()).hexdigest()[:12]
            fld = next(csv.reader([line]))
            sid = fld[i_s].strip()
            if not sid:
                if DEC["weight_parse"] == "drop_silent":
                    continue
                ins(con, "bronze_manifest", (ref, None, None, "missing_key")); continue
            try:
                kg, reason = parse_weight(fld[i_w].strip(), fld[i_u] if i_u is not None else None, cfg)
            except ValueError as e:
                raise StageError(f"stage=manifest_parse ValueError: {e}") from e
            if reason == "DROP":
                continue
            ins(con, "bronze_manifest", (ref, sid, kg, reason))
        con.commit()


def build_silver_orders(con, cfg):
    rows = con.execute("SELECT seq, event_ts, ingest_ts, op, k, after FROM bronze_cdc").fetchall()
    order = (lambda r: r[0]) if DEC["cdc_apply"] == "seq_order" else (lambda r: (tkey(r[1]), r[0]))
    if DEC["cdc_incremental"] == "rebuild":
        state = {}
        for r in sorted(rows, key=order):
            state[r[4]] = None if r[3] == "d" else r[5]
    else:
        wm = con.execute("SELECT v FROM meta WHERE k='watermark'").fetchone()
        wm = wm[0] if wm else ""
        state = {k: a for k, a, _, _ in con.execute("SELECT k, after, tk, seq FROM silver_state")}
        new = [r for r in rows if tkey(r[1]) > wm]
        for r in sorted(new, key=order):
            state[r[4]] = None if r[3] == "d" else r[5]
        if new:
            con.execute("INSERT OR REPLACE INTO meta VALUES ('watermark', ?)", (max(tkey(r[1]) for r in new),))
        con.execute("DELETE FROM silver_state")
        con.executemany("INSERT INTO silver_state VALUES (?,?,?,?)", [(k, a, "", 0) for k, a in state.items()])
    oc, fx = cfg["orders_cols"], cfg["fx"]
    out = []
    for k, a in state.items():
        if a is None:
            continue
        row = json.loads(a)
        if DEC["deletes"] == "soft_and_hard" and is_deleted(row.get, cfg):
            continue
        amt = float(row[oc["amount"]])
        rate = fx[row[oc["currency"]]] if DEC["fx"] == "table" else 1.0
        out.append((int(row[oc["order_id"]]), row[oc["customer_id"]], row[oc["warehouse_id"]], row[oc["status"]],
                    round(amt * rate, 2), row[oc["order_date"]], row[oc["promised_ts"]]))
    con.execute("DROP TABLE IF EXISTS silver_orders")
    con.execute("CREATE TABLE silver_orders (order_id INTEGER, customer_id TEXT, warehouse_id TEXT, status TEXT, "
                "amount_usd REAL, order_date TEXT, promised_ts TEXT)")
    con.executemany("INSERT INTO silver_orders VALUES (?,?,?,?,?,?,?)", out)
    con.commit()


def build_gold(con, cfg):
    L = float(cfg["lateness_hours"]) * 3600
    con.execute("DROP TABLE IF EXISTS silver_manifest")
    con.execute("CREATE TABLE silver_manifest AS SELECT m.record_ref, m.shipment_id, m.weight_kg FROM bronze_manifest m "
                "WHERE m.reason IS NULL AND m.shipment_id IN (SELECT shipment_id FROM dim_shipments)")
    con.execute("DROP TABLE IF EXISTS quarantine")
    con.execute("CREATE TABLE quarantine AS SELECT 'manifest' AS source, record_ref, reason FROM bronze_manifest "
                "WHERE reason IS NOT NULL UNION ALL SELECT 'manifest', record_ref, 'orphan_shipment' FROM bronze_manifest "
                "WHERE reason IS NULL AND shipment_id NOT IN (SELECT shipment_id FROM dim_shipments)")
    con.execute("DROP TABLE IF EXISTS gold_warehouse_revenue")
    if DEC["revenue_join"] == "semi_join":
        con.execute("CREATE TABLE gold_warehouse_revenue AS SELECT w.warehouse_id, ROUND(COALESCE((SELECT SUM(o.amount_usd) "
                    "FROM silver_orders o WHERE o.warehouse_id = w.warehouse_id AND o.status = 'DELIVERED' AND EXISTS ("
                    "SELECT 1 FROM dim_shipments s JOIN bronze_events e ON e.shipment_id = s.shipment_id AND e.type = "
                    "'DELIVERED' WHERE s.order_id = o.order_id)), 0), 2) AS net_revenue_usd FROM dim_warehouses w")
    else:
        con.execute("CREATE TABLE gold_warehouse_revenue AS SELECT w.warehouse_id, ROUND(COALESCE((SELECT SUM(o.amount_usd) "
                    "FROM silver_orders o JOIN dim_shipments s ON s.order_id = o.order_id JOIN (SELECT DISTINCT shipment_id "
                    "FROM bronze_events WHERE type = 'DELIVERED') e ON e.shipment_id = s.shipment_id WHERE o.warehouse_id = "
                    "w.warehouse_id AND o.status = 'DELIVERED'), 0), 2) AS net_revenue_usd FROM dim_warehouses w")
    ev = con.execute("SELECT event_id, shipment_id, type, event_ts, ingest_ts FROM bronze_events").fetchall()
    late = [e for e in ev if (utc(e[4]) - utc(e[3])).total_seconds() > L]
    late_ids = {e[0] for e in late}
    con.execute("DROP TABLE IF EXISTS late_events")
    con.execute("CREATE TABLE late_events (event_id TEXT)")
    con.executemany("INSERT INTO late_events VALUES (?)", [(e[0],) for e in late])
    orders = {r[0]: r for r in con.execute("SELECT order_id, warehouse_id, status, promised_ts FROM silver_orders")}
    ship = {r[0]: r for r in con.execute("SELECT shipment_id, order_id, carrier FROM dim_shipments")}
    sla, seen = {}, set()
    for e in ev:
        if e[2] != "DELIVERED" or e[1] not in ship or e[1] in seen:
            continue
        if DEC["sla_window"] == "apply" and e[0] in late_ids:
            continue
        o = orders.get(ship[e[1]][1])
        if o is None:
            continue
        seen.add(e[1])
        d, t = sla.get(o[1], (0, 0))
        sla[o[1]] = (d + 1, t + (tkey(e[3]) <= tkey(o[3])))
    con.execute("DROP TABLE IF EXISTS gold_sla")
    con.execute("CREATE TABLE gold_sla (warehouse_id TEXT, delivered INTEGER, on_time INTEGER, on_time_rate REAL)")
    con.executemany("INSERT INTO gold_sla VALUES (?,?,?,?)", [(w, d, t, round(t / d, 4)) for w, (d, t) in sla.items()])
    clar = cfg["clarifications"]
    inc = set(cfg["carrier_include"]) | {k.split(":", 1)[1] for k, a in clar.items() if k.startswith("carrier_volume:") and a == "include"}
    known = set(cfg["carrier_include"]) | set(cfg["carrier_exclude"]) | {k.split(":", 1)[1] for k in clar if k.startswith("carrier_volume:")}
    seen_status = {r[0] for r in con.execute("SELECT DISTINCT o.status FROM silver_manifest m JOIN dim_shipments s ON "
                                            "s.shipment_id = m.shipment_id JOIN silver_orders o ON o.order_id = s.order_id")}
    if DEC["carrier_uncovered"] == "include":
        inc |= seen_status - known
    con.execute("DROP TABLE IF EXISTS gold_carrier_volume")
    con.execute("CREATE TABLE gold_carrier_volume (warehouse_id TEXT, carrier TEXT, weight_kg REAL)")
    if inc:
        con.execute("INSERT INTO gold_carrier_volume SELECT o.warehouse_id, s.carrier, ROUND(SUM(m.weight_kg), 3) FROM "
                    "silver_manifest m JOIN dim_shipments s ON s.shipment_id = m.shipment_id JOIN silver_orders o ON "
                    f"o.order_id = s.order_id WHERE o.status IN ({','.join('?' * len(inc))}) GROUP BY o.warehouse_id, s.carrier",
                    sorted(inc))
    bk = dict(cfg["buckets"])
    bk.update({k.split(":", 1)[1]: a for k, a in clar.items() if k.startswith("status_bucket:")})
    cnt = {}
    for o in orders.values():
        key = (o[1], bk.get(o[2], DEC["bucket_uncovered"]))
        cnt[key] = cnt.get(key, 0) + 1
    con.execute("DROP TABLE IF EXISTS gold_status_counts")
    con.execute("CREATE TABLE gold_status_counts (warehouse_id TEXT, bucket TEXT, n INTEGER)")
    con.executemany("INSERT INTO gold_status_counts VALUES (?,?,?)", [(w, b, n) for (w, b), n in cnt.items()])
    con.execute("DROP TABLE IF EXISTS gold_inventory")
    con.execute("CREATE TABLE gold_inventory AS SELECT warehouse_id, sku, SUM(qty) AS on_hand FROM dim_inventory "
                "WHERE deleted = 0 GROUP BY warehouse_id, sku")
    con.commit()


STAGES = [("dims", ingest_dims), ("bronze", ingest_cdc), ("bronze", ingest_events), ("manifests", ingest_manifests),
          ("silver_orders", build_silver_orders), ("gold", build_gold)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--landing", required=True); ap.add_argument("--state", required=True); ap.add_argument("--config", required=True)
    a = ap.parse_args()
    with open(a.config) as fh:
        cfg = json.load(fh)
    os.makedirs(a.state, exist_ok=True)
    con = sqlite3.connect(os.path.join(a.state, "lake.db"))
    setup(con)
    for name, fn in STAGES:
        try:
            fn(con, a.landing, cfg) if fn.__code__.co_argcount == 3 else fn(con, cfg)
        except StageError:
            raise
        except Exception as e:
            raise StageError(f"stage={name} {type(e).__name__}: {e}") from e
    con.close()


if __name__ == "__main__":
    main()
