#!/usr/bin/env python3
"""Generated exactly-once streaming consumer. Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "table", "gold_maintenance": "recompute_affected", "lateness": "processing_time", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc"}"""
import argparse, glob, json, os, shutil, sqlite3, sys
from datetime import datetime, timedelta, timezone

DEC = {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "table", "gold_maintenance": "recompute_affected", "lateness": "processing_time", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc"}


class StageError(Exception):
    pass


def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def ets_key(raw, fmt):
    if DEC["ts_format"] == "registry_typed" and fmt == "epoch_ms":
        return datetime.fromtimestamp(raw / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    if DEC["ts_parse"] == "utc":
        return utc(raw).strftime("%Y-%m-%dT%H:%M:%S")
    raw.replace("Z", "+00:00")          # a text timestamp: fails on non-strings
    return raw


def instant(raw):
    return datetime.fromtimestamp(raw / 1000, timezone.utc) if isinstance(raw, (int, float)) else utc(raw)


def registry(con, subject, version, default):
    b = con.execute("SELECT body FROM registry WHERE subject=? AND version=?", (subject, version)).fetchone()
    return json.loads(b[0]) if b else default


def tick_of(ingest, cfg):
    d = (utc(ingest) - utc(cfg["t0"])).total_seconds() / (cfg["tick_hours"] * 3600)
    return max(1, int(d) + 1) if d > 0 else 1


SCHEMA = """
CREATE TABLE IF NOT EXISTS _consumed (topic TEXT, part INTEGER, offset INTEGER, msg_id TEXT, tick INTEGER, status TEXT,
                                      PRIMARY KEY (topic, part, offset));
CREATE TABLE IF NOT EXISTS _offsets (topic TEXT, part INTEGER, next INTEGER, PRIMARY KEY (topic, part));
CREATE TABLE IF NOT EXISTS _meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS registry (subject TEXT, version INTEGER, body TEXT, PRIMARY KEY (subject, version));
CREATE TABLE IF NOT EXISTS snapshot_ctl (msg_id TEXT PRIMARY KEY, body TEXT);
CREATE TABLE IF NOT EXISTS bronze_orders (msg_id TEXT %(pk)s, key INTEGER, sv INTEGER, op TEXT, payload TEXT, soft INTEGER,
                                          source TEXT, tick INTEGER, seq INTEGER);
CREATE TABLE IF NOT EXISTS bronze_tel (msg_id TEXT %(pk)s, order_id INTEGER, type TEXT, ets TEXT, ingest TEXT, tick INTEGER,
                                       future INTEGER, raw TEXT);
CREATE TABLE IF NOT EXISTS bronze_man (msg_id TEXT %(pk)s, order_id INTEGER, supplier TEXT, kg REAL, tick INTEGER);
CREATE TABLE IF NOT EXISTS _rev_acc (warehouse_id TEXT PRIMARY KEY, revenue REAL);
"""


def offsets_load(con, st):
    if DEC["commit_protocol"] == "transactional":
        off = {(t, p): n for t, p, n in con.execute("SELECT topic, part, next FROM _offsets")}
        k = con.execute("SELECT v FROM _meta WHERE k='known'").fetchone()
        return off, (json.loads(k[0]) if k else None)
    f = os.path.join(st, "offsets.json")
    if not os.path.exists(f):
        return {}, None
    d = json.load(open(f))
    return {(t, int(p)): n for t, p, n in d["off"]}, d.get("known")


def offsets_store(con, st, off, known):
    if DEC["commit_protocol"] == "transactional":
        con.executemany("INSERT OR REPLACE INTO _offsets VALUES (?,?,?)", [(t, p, n) for (t, p), n in off.items()])
        con.execute("INSERT OR REPLACE INTO _meta VALUES ('known', ?)", (json.dumps(known),))
        return
    tmp = os.path.join(st, "offsets.json.tmp")
    with open(tmp, "w") as fh:
        json.dump({"off": [[t, p, n] for (t, p), n in sorted(off.items())], "known": known}, fh)
    os.replace(tmp, os.path.join(st, "offsets.json"))


def partitions(log, cfg, known):
    found = []
    for topic in cfg["processing_order"]:
        for d in sorted(glob.glob(os.path.join(log, topic, "p*"))):
            found.append([topic, int(os.path.basename(d)[1:])])
    if DEC["partition_discovery"] == "dynamic" or known is None:
        return found, found
    return [x for x in found if x in known], known


def read_new(log, topic, part, start, limit):
    out = []
    for f in sorted(glob.glob(os.path.join(log, topic, f"p{part}", "*.jsonl"))):
        base = int(os.path.basename(f).split(".")[0])
        with open(f) as fh:
            lines = fh.read().split("\n")
        for i, line in enumerate(lines):
            if not line:
                continue
            off = base + i
            if off < start:
                continue
            if limit is not None and len(out) >= limit:
                return out
            out.append((off, line))
    return out


def decode_payload(con, rec, cfg):
    reg = registry(con, "orders", rec.get("schema_version", 1), None)
    if reg is None:
        if DEC["schema_handling"].startswith("registry"):
            raise KeyError(f"schema_version {rec.get('schema_version')} not registered")
        reg = {"fields": cfg["v1"], "types": {"discount": "int"}}
    a = rec.get("after")
    if a is None:
        return None, reg
    sh = DEC["schema_handling"]
    names = cfg["v1"] if sh.startswith("v1") else reg["fields"]
    get = (lambda c: a[names[c]]) if sh == "v1_strict" else (lambda c: a.get(names[c]))
    disc = get("discount")
    if sh in ("registry_int_cast",):
        disc = int(disc or 0)
    elif sh == "registry_typed":
        disc = float(disc) if reg["types"].get("discount") == "float" else int(disc)
    else:
        disc = float(disc or 0)
    row = {"order_id": int(get("order_id")), "warehouse_id": get("warehouse_id"), "status": get("status"),
           "amount": float(get("amount") or 0), "currency": get("currency"), "discount": disc,
           "promised_ts": get("promised_ts"), "deleted": int(get("deleted") or 0)}
    return row, reg


def ingest(con, log, st, cfg, tick):
    dep = cfg["deploy"]
    off, known = offsets_load(con, st)
    parts, known = partitions(log, cfg, known)
    limit = dep.get("max_records_per_run")
    dead = {(t, p, o) for t, p, o in dep.get("dead_letter", [])}
    overrides = dep.get("unit_overrides", [])
    verb = "INSERT OR IGNORE" if DEC["dedup"] == "by_msg_id" else "INSERT"
    seq = con.execute("SELECT COALESCE(MAX(seq), 0) FROM bronze_orders").fetchone()[0]
    n_read, commits = 0, []
    for topic, part in parts:
        start = off.get((topic, part), 0)
        recs = read_new(log, topic, part, start, None if limit is None else max(0, limit - n_read))
        for o, line in recs:
            n_read += 1
            if (topic, part, o) in dead:
                con.execute("INSERT OR IGNORE INTO _consumed VALUES (?,?,?,?,?,?)", (topic, part, o, f"{topic}:{part}:{o}", tick, "poison"))
                off[(topic, part)] = o + 1
                continue
            try:
                rec = json.loads(line)
            except ValueError as e:
                raise StageError(f"stage=read decode error topic={topic} part={part} offset={o}: {e}")
            mid = rec["msg_id"]
            dup = DEC["dedup"] == "by_msg_id" and con.execute(
                "SELECT 1 FROM _consumed WHERE msg_id=? AND topic=? AND status!='dup' LIMIT 1", (mid, topic)).fetchone()
            status = "dup" if dup else "applied"
            rt = tick_of(rec["ingest_ts"], cfg)
            if dup:
                pass
            elif topic == "_schemas":
                con.execute("INSERT OR REPLACE INTO registry VALUES (?,?,?)", (rec.get("subject", "orders"), rec["version"],
                                                                              json.dumps(rec)))
            elif "control" in rec:
                con.execute("INSERT OR REPLACE INTO snapshot_ctl VALUES (?,?)", (mid, json.dumps(rec)))
            elif topic in ("orders_cdc", "backfill_orders"):
                try:
                    row, reg = decode_payload(con, rec, cfg)
                except (KeyError, TypeError, ValueError) as e:
                    raise StageError(f"stage=decode schema topic={topic} part={part} offset={o}: {type(e).__name__} {e}")
                soft = 1 if row and row["deleted"] else 0
                seq += 1
                con.execute(f"{verb} INTO bronze_orders VALUES (?,?,?,?,?,?,?,?,?)",
                            (mid, rec["key"], rec["source_version"], rec["op"], json.dumps(row), soft, topic, rt, seq))
            elif topic == "telemetry":
                treg = registry(con, "telemetry", rec.get("schema_version", 1), {"ts_format": "iso"})
                try:
                    ek = ets_key(rec["event_ts"], treg.get("ts_format", "iso"))
                except (AttributeError, TypeError, ValueError) as e:
                    raise StageError(f"stage=decode timestamp topic={topic} part={part} offset={o}: {type(e).__name__} {e}")
                fut = 1 if (dep.get("future_guard") and
                            (instant(rec["event_ts"]) - utc(rec["ingest_ts"])).total_seconds() > 300) else 0
                if fut:
                    status = "future"
                con.execute(f"{verb} INTO bronze_tel VALUES (?,?,?,?,?,?,?,?)", (mid, rec["order_id"], rec["type"], ek,
                                                                                 rec["ingest_ts"], rt, fut, str(rec["event_ts"])))
            elif topic == "manifests":
                try:
                    kg = float(rec["weight"])
                except (TypeError, ValueError):
                    kg = None
                if kg is None:
                    status = "malformed" if DEC["malformed"] == "quarantine" else "dropped"
                else:
                    for ov in overrides:
                        if ov["supplier"] == rec["supplier"] and o >= ov["from_offset"] and part == ov.get("part", 0):
                            kg = kg * ov["factor"]
                    con.execute(f"{verb} INTO bronze_man VALUES (?,?,?,?,?)", (mid, rec["order_id"], rec["supplier"], kg, rt))
            con.execute("INSERT OR IGNORE INTO _consumed VALUES (?,?,?,?,?,?)", (topic, part, o, mid, rt, status))
            off[(topic, part)] = o + 1
        commits.append(topic)
        if DEC["commit_protocol"] != "transactional":
            if DEC["commit_protocol"] == "offsets_first":
                offsets_store(con, st, off, known)
                con.commit()
            else:
                con.commit()
                offsets_store(con, st, off, known)
    return off, known, n_read


def build(con, cfg):
    rows = con.execute("SELECT msg_id, key, sv, op, payload, soft, source, seq FROM bronze_orders").fetchall()
    order = (lambda r: r[7]) if DEC["apply_order"] == "arrival" else (lambda r: (r[2], r[7]))   # source_version, then arrival
    live, bf = {}, {}
    for r in sorted(rows, key=order):
        (bf if r[6] == "backfill_orders" else live)[r[1]] = r
    if DEC["backfill_merge"] == "lww_tombstones":
        state = {}
        for r in sorted(rows, key=order):
            state[r[1]] = r
    elif DEC["backfill_merge"] == "blind_overwrite":
        state = dict(live); state.update(bf)
    else:
        state = dict(live)
        alive = {k for k, r in live.items() if r[3] != "d" and not (r[5] and DEC["deletes"] == "soft_and_hard")}
        for k, r in bf.items():
            if k not in alive:
                state[k] = r
    fx = cfg["fx"]
    out = []
    for k, r in state.items():
        if r[3] == "d" or (r[5] and DEC["deletes"] == "soft_and_hard"):
            continue
        p = json.loads(r[4])
        rate = fx[p["currency"]] if DEC["fx"] == "table" else 1.0
        out.append((k, p["warehouse_id"], p["status"], round(p["amount"] * (1 - p["discount"] / 100) * rate, 2), p["promised_ts"]))
    prev = {r[0]: r for r in con.execute("SELECT order_id, warehouse_id, status, net_usd, promised_ts FROM silver_orders")} \
        if con.execute("SELECT name FROM sqlite_master WHERE name='silver_orders'").fetchone() else {}
    con.execute("DROP TABLE IF EXISTS silver_orders")
    con.execute("CREATE TABLE silver_orders (order_id INTEGER PRIMARY KEY, warehouse_id TEXT, status TEXT, net_usd REAL, promised_ts TEXT)")
    con.executemany("INSERT INTO silver_orders VALUES (?,?,?,?,?)", out)
    changed = [r for r in out if prev.get(r[0]) != r]
    return changed, prev


def gold(con, cfg, changed, prev):
    whs = cfg["warehouses"]
    gm = DEC["gold_maintenance"]
    if gm == "delta_no_retract":
        for r in changed:
            if r[2] == "DELIVERED":
                con.execute("INSERT INTO _rev_acc VALUES (?, ?) ON CONFLICT(warehouse_id) DO UPDATE SET revenue = revenue + ?",
                            (r[1], r[3], r[3]))
        acc = dict(con.execute("SELECT warehouse_id, revenue FROM _rev_acc"))
        rev = [(w, round(acc.get(w, 0.0), 2)) for w in whs]
    else:
        tot = dict(con.execute("SELECT warehouse_id, SUM(net_usd) FROM silver_orders WHERE status='DELIVERED' GROUP BY warehouse_id"))
        if gm == "recompute_affected" and con.execute("SELECT name FROM sqlite_master WHERE name='gold_warehouse_revenue'").fetchone():
            old = dict(con.execute("SELECT warehouse_id, revenue_usd FROM gold_warehouse_revenue"))
            aff = {r[1] for r in changed} | {prev[k][1] for k in prev if k not in {r[0] for r in con.execute("SELECT order_id FROM silver_orders")}}
            aff |= {prev[r[0]][1] for r in changed if r[0] in prev}
            rev = [(w, round(tot.get(w, 0.0) or 0.0, 2) if w in aff or w not in old else old[w]) for w in whs]
        else:
            rev = [(w, round(tot.get(w, 0.0) or 0.0, 2)) for w in whs]
    con.execute("DROP TABLE IF EXISTS gold_warehouse_revenue")
    con.execute("CREATE TABLE gold_warehouse_revenue (warehouse_id TEXT, revenue_usd REAL)")
    con.executemany("INSERT INTO gold_warehouse_revenue VALUES (?,?)", rev)
    bk = cfg["buckets"]
    cnt = {}
    for w, s in con.execute("SELECT warehouse_id, status FROM silver_orders"):
        cnt[(w, bk.get(s, "other"))] = cnt.get((w, bk.get(s, "other")), 0) + 1
    con.execute("DROP TABLE IF EXISTS gold_status_counts")
    con.execute("CREATE TABLE gold_status_counts (warehouse_id TEXT, bucket TEXT, n INTEGER)")
    con.executemany("INSERT INTO gold_status_counts VALUES (?,?,?)", [(w, b, n) for (w, b), n in cnt.items()])
    tel = con.execute("SELECT msg_id, order_id, type, ets, ingest, tick, future, raw FROM bronze_tel").fetchall()
    L = timedelta(hours=cfg["allowed_hours"])
    by_tick = {}
    for t in tel:
        if not t[6]:
            by_tick.setdefault(t[5], []).append(t[3])
    late = []
    for t in tel:
        if t[6]:
            continue
        if DEC["lateness"] == "watermark":
            prior = [x for k, xs in by_tick.items() if k < t[5] for x in xs]
            if prior:
                wm = (datetime.fromisoformat(max(prior)) - L).strftime("%Y-%m-%dT%H:%M:%S") if DEC["ts_parse"] == "utc" else None
                if (wm is not None and t[3] < wm) or (wm is None and t[3] < max(prior)):
                    late.append(t)
        elif DEC["lateness"] == "processing_time":
            if (utc(t[4]) - instant(json.loads(t[7]) if t[7].isdigit() else t[7])).total_seconds() > L.total_seconds():
                late.append(t)
    late_ids = {t[0] for t in late}
    con.execute("DROP TABLE IF EXISTS late_events")
    con.execute("CREATE TABLE late_events (msg_id TEXT)")
    con.executemany("INSERT INTO late_events VALUES (?)", [(t[0],) for t in late])
    silver = {r[0]: r for r in con.execute("SELECT order_id, warehouse_id, status, net_usd, promised_ts FROM silver_orders")}
    sla, seen = {}, set()
    for t in sorted(tel, key=lambda t: t[0]):
        if t[2] != "DELIVERED" or t[6] or t[0] in late_ids or t[1] not in silver:
            continue
        if DEC["dedup"] == "by_msg_id":
            if t[1] in seen:
                continue
            seen.add(t[1])
        o = silver[t[1]]
        d, n = sla.get(o[1], (0, 0))
        pr = utc(o[4]).strftime("%Y-%m-%dT%H:%M:%S") if DEC["ts_parse"] == "utc" else o[4]
        sla[o[1]] = (d + 1, n + (t[3] <= pr))
    con.execute("DROP TABLE IF EXISTS gold_sla")
    con.execute("CREATE TABLE gold_sla (warehouse_id TEXT, delivered INTEGER, on_time INTEGER, on_time_rate REAL)")
    con.executemany("INSERT INTO gold_sla VALUES (?,?,?,?)", [(w, d, n, round(n / d, 4)) for w, (d, n) in sla.items()])
    vol = {}
    for oid, sup, kg in con.execute("SELECT order_id, supplier, kg FROM bronze_man"):
        o = silver.get(oid)
        if o and o[2] != "CANCELLED":
            vol[(o[1], sup)] = vol.get((o[1], sup), 0.0) + kg
    con.execute("DROP TABLE IF EXISTS gold_supplier_volume")
    con.execute("CREATE TABLE gold_supplier_volume (warehouse_id TEXT, supplier TEXT, weight_kg REAL)")
    con.executemany("INSERT INTO gold_supplier_volume VALUES (?,?,?)", [(w, s, round(x, 3)) for (w, s), x in vol.items()])
    con.execute("DROP TABLE IF EXISTS quarantine")
    con.execute("CREATE TABLE quarantine AS SELECT topic, msg_id, CASE status WHEN 'malformed' THEN 'malformed_weight' "
                "WHEN 'future' THEN 'future_event' ELSE 'poison' END AS reason FROM _consumed "
                "WHERE status IN ('malformed', 'future', 'poison')")
    acc = {}
    for topic, status, n in con.execute("SELECT topic, status, COUNT(*) FROM _consumed WHERE topic != '_schemas' GROUP BY topic, status"):
        st = {"applied": "applied", "dup": "duplicate", "dropped": "dropped"}.get(status, "quarantined")
        acc[(topic, st)] = acc.get((topic, st), 0) + n
    if late:
        acc[("telemetry", "late")] = len(late)
    con.execute("DROP TABLE IF EXISTS record_accounting")
    con.execute("CREATE TABLE record_accounting (topic TEXT, status TEXT, n INTEGER)")
    con.executemany("INSERT INTO record_accounting VALUES (?,?,?)", [(t, s, n) for (t, s), n in sorted(acc.items())])


def snapshot(st, tick):
    if DEC["snapshots"] != "per_tick":
        return
    d = os.path.join(st, "snapshots")
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".tmp{tick}")
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp)
    src = sqlite3.connect(os.path.join(st, "lake.db"))
    dst = sqlite3.connect(os.path.join(tmp, "lake.db"))
    src.backup(dst); dst.close(); src.close()
    if os.path.exists(os.path.join(st, "offsets.json")):
        shutil.copy(os.path.join(st, "offsets.json"), tmp)
    fin = os.path.join(d, f"{tick:04d}")
    if os.path.exists(fin):
        shutil.rmtree(fin)
    os.replace(tmp, fin)


def rollback(st, k):
    """Atomicity boundary: lake.db (tables + transactional offsets + dedup ledger) is replaced in ONE os.replace; offsets.json
    (non-transactional protocols) is a second step. A durable intent journal (rollback.intent) makes the pair recoverable:
    any later start that finds the journal re-executes the rollback before doing anything else."""
    j = os.path.join(st, "rollback.intent")
    with open(j + ".tmp", "w") as fh:
        json.dump({"k": k}, fh)
    os.replace(j + ".tmp", j)
    _rollback(st, k)
    os.remove(j)


def _rollback(st, k):
    d = os.path.join(st, "snapshots", f"{k:04d}")
    if DEC["snapshots"] == "per_tick" and os.path.exists(d):
        for f in ("lake.db", "offsets.json"):
            if os.path.exists(os.path.join(d, f)):
                shutil.copy(os.path.join(d, f), os.path.join(st, f + ".rb"))
            elif os.path.exists(os.path.join(st, f)):
                os.remove(os.path.join(st, f))
        for f in ("lake.db", "offsets.json"):
            if os.path.exists(os.path.join(st, f + ".rb")):
                os.replace(os.path.join(st, f + ".rb"), os.path.join(st, f))
        for s in glob.glob(os.path.join(st, "snapshots", "*")):
            if os.path.basename(s).isdigit() and int(os.path.basename(s)) > k:
                shutil.rmtree(s)
        return
    for f in ("lake.db", "offsets.json"):            # no snapshot: reset and reprocess whatever the log still retains
        if os.path.exists(os.path.join(st, f)):
            os.remove(os.path.join(st, f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log"); ap.add_argument("--state", required=True); ap.add_argument("--config", required=True)
    ap.add_argument("--tick", type=int); ap.add_argument("--rollback-to", type=int)
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    os.makedirs(a.state, exist_ok=True)
    j = os.path.join(a.state, "rollback.intent")
    if os.path.exists(j):                     # recover an interrupted rollback before anything else
        rollback(a.state, json.load(open(j))["k"])
    if a.rollback_to is not None:
        rollback(a.state, a.rollback_to)
        return
    con = sqlite3.connect(os.path.join(a.state, "lake.db"))
    con.executescript(SCHEMA % {"pk": "PRIMARY KEY" if DEC["dedup"] == "by_msg_id" else ""})
    try:
        off, known, n = ingest(con, a.log, a.state, cfg, a.tick)
        changed, prev = build(con, cfg)
        gold(con, cfg, changed, prev)
    except StageError:
        raise
    except Exception as e:
        raise StageError(f"stage=gold {type(e).__name__}: {e}") from e
    if DEC["commit_protocol"] == "transactional":
        offsets_store(con, a.state, off, known)
        con.commit()
    elif DEC["commit_protocol"] == "offsets_first":
        offsets_store(con, a.state, off, known)
        con.commit()
    else:
        con.commit()
        offsets_store(con, a.state, off, known)
    con.close()
    snapshot(a.state, a.tick)
    print(json.dumps({"records": n, "tick": a.tick}))


if __name__ == "__main__":
    main()
