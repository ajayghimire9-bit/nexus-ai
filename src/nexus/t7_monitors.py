"""Trial 1, state arm - knockoff-gated state monitors over derived stream quantities (NOT LOCKED).

Quantities (a grammar; ~200 per project): for each log topic and each tick, over the records ingested in that tick -
count; distinct-key ratio; duplicate-msg ratio; event->ingest lag p10 / p50 / p90 / max (s); future fraction (event after
ingest + 5 min); late fraction (lag > 1 h); per-key max lag; offset-gap count; out-of-order-offset fraction; distinct
schema versions; non-numeric fraction of numeric fields - plus lake tables (row counts of every table, _consumed by status,
record_accounting by status, silver/bronze ratio, telemetry future flags, max(event) - max(ingest)). Each quantity enters as
its level and as its tick-to-tick delta.
Monitor j alarms at tick t when |q_j(t) - median_build| / (1.4826 * MAD_build + eps_j) > Z (build = ticks 1-8).
Knockoff twin of monitor j: the same quantity with its tick alignment permuted (seeded), so it has the same marginal
distribution and type but no causal alignment with incidents. W_j = (TPR_j - FPR_j) - (TPR~_j - FPR~_j) on dev incident ticks
(positive = a truth incident has onset at t or t - 1); knockoff+ at q."""
from __future__ import annotations

import json
import math
import os
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

Z = 6.0


def _ts(x):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return x / 1000.0 if x > 1e11 else float(x)
    if isinstance(x, str):
        try:
            return datetime.fromisoformat(x.replace("Z", "+00:00")).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            return None
    return None


def _q(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    return float(xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))])


def quantities(env, t):
    """Derived per-tick quantities for tick t of an operations environment (reads the log and the lake; read-only)."""
    out = {}
    log = Path(env.rt["log"])
    by_topic = defaultdict(list)
    for d in log.glob("*/p*"):
        if d.parent.name == "_obs" or not d.is_dir() or not os.access(d, os.R_OK):
            continue
        for f in d.glob("*.jsonl"):
            for l in f.read_text().splitlines():
                try:
                    x = json.loads(l)
                except ValueError:
                    continue
                it = _ts(x.get("ingest_ts"))
                if it is None:
                    continue
                x["_part"] = d.name
                by_topic[d.parent.name].append((it, x))
    for topic, recs in by_topic.items():
        tmax = max(it for it, _ in recs)
        cur = [x for it, x in recs if it > tmax - 3600 * 6]                 # the newest tick's window (6 h)
        n = len(cur)
        keys = [x.get("order_id") or x.get("msg_id") for x in cur]
        msgs = [x.get("msg_id") for x in cur]
        lags, perkey = [], defaultdict(float)
        for x in cur:
            e, i = _ts(x.get("event_ts")), _ts(x.get("ingest_ts"))
            if e is not None and i is not None:
                lags.append(i - e)
                k = x.get("order_id") or x.get("msg_id")
                perkey[k] = max(perkey[k], i - e)
        offs = defaultdict(list)
        for x in cur:
            if isinstance(x.get("offset"), int):
                offs[x["_part"]].append(x["offset"])
        gaps = sum(sum(1 for a, b in zip(sorted(v), sorted(v)[1:]) if b - a > 1) for v in offs.values())
        ooo = sum(sum(1 for a, b in zip(v, v[1:]) if b < a) for v in offs.values()) / max(1, n)
        numf = [k for k in ("amount", "weight", "qty", "discount") if any(k in x for x in cur)]
        nonnum = sum(1 for x in cur for k in numf if k in x and not isinstance(x[k], (int, float))) / max(1, n)
        vals = dict(count=n, distinct_key_ratio=len(set(keys)) / max(1, n), dup_msg_ratio=1 - len(set(msgs)) / max(1, n),
                    lag_p10=_q(lags, .1), lag_p50=_q(lags, .5), lag_p90=_q(lags, .9), lag_max=max(lags) if lags else 0.0,
                    future_frac=sum(1 for v in lags if v < -300) / max(1, len(lags)), late_frac=sum(1 for v in lags if v > 3600) / max(1, len(lags)),
                    perkey_lag_max=max(perkey.values()) if perkey else 0.0, perkey_lag_mean=sum(perkey.values()) / max(1, len(perkey)),
                    offset_gaps=gaps, out_of_order=ooo, schema_versions=len({x.get("schema_version") for x in cur}),
                    nonnumeric_frac=nonnum, partitions=len(offs))
        for k, v in vals.items():
            out[f"{topic}.{k}"] = float(v)
    db = Path(env.rt["state"]) / "lake.db"
    if db.exists():
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for tb in tabs:
                out[f"lake.rows.{tb}"] = float(con.execute(f'SELECT COUNT(*) FROM "{tb}"').fetchone()[0])
            if "_consumed" in tabs:
                for s, n in con.execute("SELECT status, COUNT(*) FROM _consumed GROUP BY status"):
                    out[f"lake.consumed.{s}"] = float(n)
            if "record_accounting" in tabs:
                for tp, s, n in con.execute("SELECT topic, status, n FROM record_accounting"):
                    out[f"lake.acct.{tp}.{s}"] = float(n)
            if "bronze_tel" in tabs:
                out["lake.tel_future"] = float(con.execute("SELECT COALESCE(SUM(future),0) FROM bronze_tel").fetchone()[0])
                me, mi = con.execute("SELECT MAX(ets), MAX(ingest) FROM bronze_tel").fetchone()
                a, b = _ts(me), _ts(mi)
                out["lake.event_minus_ingest_max"] = float(a - b) if a is not None and b is not None else 0.0
            if "silver_orders" in tabs and "bronze_orders" in tabs:
                out["lake.silver_bronze_ratio"] = out["lake.rows.silver_orders"] / max(1.0, out["lake.rows.bronze_orders"])
            con.close()
        except sqlite3.Error:
            pass
    return out


def series_table(per_tick):
    """{tick: {q: v}} -> {name: [v_1..v_T]} with level and delta versions."""
    ticks = sorted(per_tick)
    names = sorted({k for d in per_tick.values() for k in d})
    S = {}
    for n in names:
        lv = [per_tick[t].get(n, 0.0) for t in ticks]
        S[n] = lv
        S[n + ".delta"] = [0.0] + [b - a for a, b in zip(lv, lv[1:])]
    return S, ticks


def alarms(series, build=8, z=Z):
    base = series[:build]
    med = sorted(base)[len(base) // 2]
    mad = sorted(abs(v - med) for v in base)[len(base) // 2]
    eps = max(1e-9, 0.05 * abs(med))
    return [abs(v - med) / (1.4826 * mad + eps) > z for v in series]


def permuted(series, seed):
    idx = list(range(len(series)))
    random.Random(seed).shuffle(idx)
    return [series[i] for i in idx]


def score(al, labels, build=8):
    pos = [a for a, l in zip(al[build:], labels[build:]) if l]
    neg = [a for a, l in zip(al[build:], labels[build:]) if not l]
    tpr = sum(pos) / len(pos) if pos else 0.0
    fpr = sum(neg) / len(neg) if neg else 0.0
    return tpr - fpr
