"""Stage 4 protected evaluator (NOT LOCKED; semantic harness). Imports nothing from NEXUS agents, templates or checks.
The expected tables come from a reference implementation over the s4_env TRUTH (version timeline with source versions,
telemetry, manifests); it never parses the log or reads pipeline code.

Protocol (run_protocol), every run a separate OS process:
  clean        ticks 1..12, the log growing one segment per tick, retention 6 ticks; checkpoints after tick 4 (mid-backfill),
               8 (end of what the engineer saw) and 12 (held-out ticks 9-12)
  crash sweep  ticks 6 and 10: from the pre-tick state, the process is terminated (os._exit, no cleanup) immediately BEFORE
               each write / acknowledgement boundary of a probe run (every sqlite commit, every os.replace) and once after the
               last one; then restarted; for the first, middle and last boundary the RESTART is itself crashed at its first,
               middle and last boundary (crash during recovery) and restarted again; plus 5 external SIGKILLs at random
               times. Every final state must equal the uninterrupted run (outputs + offsets)
  rollback     from the tick-8 state: a bad deploy (fx x10) processes ticks 9-10, `--rollback-to 8` is crashed half way,
               the next start recovers, ticks 9-12 are reprocessed with the good config; outputs must equal the reference
Diagnoses: a counterfactual reference with ONE rule violated must reproduce an observed table exactly."""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = {
    "silver_orders": (["order_id", "warehouse_id", "status", "net_usd"], ["order_id"]),
    "gold_warehouse_revenue": (["warehouse_id", "revenue_usd"], ["warehouse_id"]),
    "gold_status_counts": (["warehouse_id", "bucket", "n"], ["warehouse_id", "bucket"]),
    "gold_sla": (["warehouse_id", "delivered", "on_time", "on_time_rate"], ["warehouse_id"]),
    "late_events": (["msg_id"], ["msg_id"]),
    "gold_supplier_volume": (["warehouse_id", "supplier", "weight_kg"], ["warehouse_id", "supplier"]),
    "quarantine": (["topic", "msg_id", "reason"], ["topic", "msg_id"]),
    "record_accounting": (["topic", "status", "n"], ["topic", "status"]),
}
TOL = {"net_usd": 0.011, "revenue_usd": 0.011, "weight_kg": 0.0021, "on_time_rate": 0.00011}
FLAGS = {
    "AT_LEAST_ONCE_DUPLICATES": "duplicate deliveries not deduplicated by msg_id (counted twice)",
    "ARRIVAL_ORDER_APPLY": "CDC applied in arrival order instead of source_version order",
    "TEXT_TIMESTAMP_ORDER": "event times compared as text across UTC offsets",
    "NO_RETRACTION": "gold revenue maintained by adding deltas without retracting corrected / deleted rows",
    "NO_LATENESS": "late telemetry not excluded",
    "PROCESSING_TIME_LATENESS": "lateness judged by ingest delay instead of the event-time watermark",
    "BACKFILL_OVERWRITE": "backfill snapshot rows overwrote newer live changes",
    "BACKFILL_RESURRECTION": "backfill snapshot rows revived keys deleted live",
    "SCHEMA_RENAME_LOST": "renamed field read under its old name (silently 0)",
    "TYPE_TRUNCATION": "widened field truncated to its old integer type",
    "STATIC_PARTITIONS": "partitions created after start never consumed",
    "NO_CURRENCY_CONVERSION": "amounts not converted to USD",
    "IGNORED_SOFT_DELETES": "soft-deleted orders treated as live",
    "MALFORMED_DROPPED": "malformed records dropped instead of quarantined",
}
RANK = {"orders_cdc": 1, "backfill_orders": 2}


def ts(s):
    if isinstance(s, (int, float)):
        return datetime.fromtimestamp(s / 1000, timezone.utc)
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


# ------------------------------------------------------------------------------------------------ reference
def _silver(truth, T, flags, fx):
    vs = [v for v in truth["versions"] if v["copies"][0][0] <= T and
          not ("STATIC_PARTITIONS" in flags and v["topic"] == "orders_cdc" and v["copies"][0][1] >= 2)]
    if "ARRIVAL_ORDER_APPLY" in flags:
        order = lambda v: (v["copies"][0][0], RANK[v["topic"]], v["copies"][0][1], v["copies"][0][2])
    else:
        order = lambda v: (v["sv"], v["copies"][0][0], RANK[v["topic"]], v["copies"][0][1], v["copies"][0][2])
    dead = lambda v: v["op"] == "d" or (v["soft"] and "IGNORED_SOFT_DELETES" not in flags)
    live, bf, allv = {}, {}, {}
    for v in sorted(vs, key=order):
        allv[v["key"]] = v
        (bf if v["topic"] == "backfill_orders" else live)[v["key"]] = v
    if "BACKFILL_OVERWRITE" in flags:
        state = dict(live); state.update(bf)
    elif "BACKFILL_RESURRECTION" in flags:
        state = dict(live)
        for k, v in bf.items():
            if k not in live or dead(live[k]):
                state[k] = v
    else:
        state = allv
    out = {}
    for k, v in state.items():
        if dead(v):
            continue
        r = v["row"]
        amt = 0.0 if ("SCHEMA_RENAME_LOST" in flags and v["schema_version"] >= 2) else r["amount"]
        disc = int(r["discount"]) if "TYPE_TRUNCATION" in flags else r["discount"]
        rate = 1.0 if "NO_CURRENCY_CONVERSION" in flags else fx[r["currency"]]
        out[k] = (k, r["warehouse_id"], r["status"], round(amt * (1 - disc / 100) * rate, 2), r["promised_ts"])
    return out


def expected(truth, T, flags=frozenset()):
    fx, L = truth["fx"], timedelta(hours=truth["L"])
    S = _silver(truth, T, flags, fx)
    res = {"silver_orders": [r[:4] for r in S.values()]}
    whs = truth["whs"]
    if "NO_RETRACTION" in flags:
        acc, prev = {w: 0.0 for w in whs}, {}
        for t in range(1, T + 1):
            cur = _silver(truth, t, flags - {"NO_RETRACTION"}, fx)
            for k, r in cur.items():
                if prev.get(k) != r and r[2] == "DELIVERED":
                    acc[r[1]] += r[3]
            prev = cur
        res["gold_warehouse_revenue"] = [(w, round(acc[w], 2)) for w in whs]
    else:
        tot = {w: 0.0 for w in whs}
        for r in S.values():
            if r[2] == "DELIVERED":
                tot[r[1]] += r[3]
        res["gold_warehouse_revenue"] = [(w, round(x, 2)) for w, x in tot.items()]
    cnt = {}
    for r in S.values():
        b = truth["buckets"].get(r[2], "other")
        cnt[(r[1], b)] = cnt.get((r[1], b), 0) + 1
    res["gold_status_counts"] = [(w, b, n) for (w, b), n in cnt.items()]
    dupok = "AT_LEAST_ONCE_DUPLICATES" in flags
    rows = []
    for e in truth["telemetry"]:
        cps = e["copies"] if dupok else e["copies"][:1]
        for c in cps:
            if c[0] <= T:
                rows.append(dict(msg=e["msg_id"], order=e["order_id"], type=e["type"], et=ts(e["event_ts"]), raw=e["event_raw"],
                                 tick=c[0], ing=ts(c[3]), future=e.get("future", False)))
    quar, acc = [], {}
    late = []
    by_tick = {}
    for r in rows:
        if not r["future"]:
            by_tick.setdefault(r["tick"], []).append(r)
    for r in rows:
        if r["future"]:
            continue
        if "NO_LATENESS" in flags:
            continue
        if "PROCESSING_TIME_LATENESS" in flags:
            if r["ing"] - r["et"] > L:
                late.append(r)
            continue
        prior = [x for k, xs in by_tick.items() if k < r["tick"] for x in xs]
        if not prior:
            continue
        if "TEXT_TIMESTAMP_ORDER" in flags:
            if str(r["raw"]) < max(str(x["raw"]) for x in prior):
                late.append(r)
        elif r["et"] < max(x["et"] for x in prior) - L:
            late.append(r)
    late_ids = {r["msg"] for r in late}
    res["late_events"] = [(r["msg"],) for r in late]
    sla, seen = {}, set()
    for r in sorted(rows, key=lambda r: r["msg"]):
        if r["type"] != "DELIVERED" or r["future"] or r["msg"] in late_ids or r["order"] not in S:
            continue
        if not dupok:
            if r["order"] in seen:
                continue
            seen.add(r["order"])
        o = S[r["order"]]
        on = (str(r["raw"]) <= o[4]) if "TEXT_TIMESTAMP_ORDER" in flags else r["et"] <= ts(o[4])
        d, n = sla.get(o[1], (0, 0))
        sla[o[1]] = (d + 1, n + on)
    res["gold_sla"] = [(w, d, n, round(n / d, 4)) for w, (d, n) in sla.items()]
    vol = {}
    for m in truth["manifests"]:
        cps = [c for c in (m["copies"] if dupok else m["copies"][:1]) if c[0] <= T]
        for _ in cps:
            if m["kind"] != "valid":
                if "MALFORMED_DROPPED" not in flags:
                    quar.append(("manifests", m["msg_id"], "malformed_weight"))
                continue
            o = S.get(m["order_id"])
            if o and o[2] != "CANCELLED":
                vol[(o[1], m["supplier"])] = vol.get((o[1], m["supplier"]), 0.0) + m["kg"]
    res["gold_supplier_volume"] = [(w, s, round(x, 3)) for (w, s), x in vol.items()]
    for r in rows:
        if r["future"]:
            quar.append(("telemetry", r["msg"], "future_event"))
    for p in truth.get("poison", []):
        if p["tick"] <= T:
            quar.append((p["topic"], f"{p['topic']}:{p['part']}:{p['offset']}", "poison"))
    res["quarantine"] = quar

    def bump(t, s, n=1):
        acc[(t, s)] = acc.get((t, s), 0) + n
    for v in truth["versions"]:
        if v["topic"] == "orders_cdc" and "STATIC_PARTITIONS" in flags and v["copies"][0][1] >= 2:
            continue
        cps = [c for c in v["copies"] if c[0] <= T]
        if cps:
            bump(v["topic"], "applied", len(cps) if dupok else 1)
            if not dupok and len(cps) > 1:
                bump(v["topic"], "duplicate", len(cps) - 1)
    for c in truth.get("controls", []):
        if c["tick"] <= T:
            bump("backfill_orders", "applied")
    for e in truth["telemetry"]:
        cps = [c for c in e["copies"] if c[0] <= T]
        if cps:
            bump("telemetry", "quarantined" if e.get("future") else "applied", len(cps) if dupok else 1)
            if not dupok and len(cps) > 1:
                bump("telemetry", "duplicate", len(cps) - 1)
    if late:
        bump("telemetry", "late", len(late))
    for m in truth["manifests"]:
        cps = [c for c in m["copies"] if c[0] <= T]
        if cps:
            st = "applied" if m["kind"] == "valid" else ("dropped" if "MALFORMED_DROPPED" in flags else "quarantined")
            bump("manifests", st, len(cps) if dupok else 1)
            if not dupok and len(cps) > 1:
                bump("manifests", "duplicate", len(cps) - 1)
    for p in truth.get("poison", []):
        if p["tick"] <= T:
            bump(p["topic"], "quarantined")
    res["record_accounting"] = [(t, s, n) for (t, s), n in acc.items()]
    return res


# ------------------------------------------------------------------------------------------------ reading / comparing
def read_state(st):
    db = Path(st) / "lake.db"
    out = {t: None for t in OUT}
    if not db.exists():
        return out
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for t, (cols, _) in OUT.items():
            have = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
            if have and all(c in have for c in cols):
                out[t] = [tuple(r) for r in con.execute(f'SELECT {",".join(chr(34) + c + chr(34) for c in cols)} FROM "{t}"')]
            elif have:
                out[t] = "SCHEMA"
    finally:
        con.close()
    return out


def offsets_of(st):
    st = Path(st)
    if (st / "lake.db").exists():
        con = sqlite3.connect(f"file:{st / 'lake.db'}?mode=ro", uri=True)
        try:
            rows = sorted(con.execute("SELECT topic, part, next FROM _offsets").fetchall())
        except sqlite3.Error:
            rows = []
        con.close()
        if rows:
            return rows
    f = st / "offsets.json"
    return sorted(tuple(x) for x in json.loads(f.read_text())["off"]) if f.exists() else []


def table_equal(t, got, want):
    cols, pk = OUT[t]
    if not isinstance(got, list):
        return False, len(want)
    idx = [cols.index(c) for c in pk]
    key = lambda r: tuple(str(r[i]) for i in idx)
    g, w = {}, {}
    for r in got:
        g.setdefault(key(r), []).append(r)
    for r in want:
        w.setdefault(key(r), []).append(r)
    diff = 0
    for k in set(g) | set(w):
        a, b = g.get(k, []), w.get(k, [])
        if len(a) != len(b):
            diff += max(len(a), len(b)); continue
        for x, y in zip(sorted(a, key=str), sorted(b, key=str)):
            for c, u, v in zip(cols, x, y):
                if c in TOL and isinstance(u, (int, float)) and isinstance(v, (int, float)):
                    if abs(u - v) > TOL[c]:
                        diff += 1; break
                elif str(u) != str(v):
                    diff += 1; break
    return diff == 0, diff


def digest(tabs, offs=None):
    return hashlib.sha256(json.dumps([{t: sorted(map(str, v)) if isinstance(v, list) else v for t, v in sorted(tabs.items())},
                                      offs], sort_keys=True, default=str).encode()).hexdigest()


# ------------------------------------------------------------------------------------------------ execution
CRASH = r'''
import os, runpy, sqlite3, sys
MODE, K = sys.argv[1], int(sys.argv[2])
n = [0]
def tick():
    n[0] += 1
    if MODE == "crash" and n[0] == K:
        os._exit(137)
_orig = sqlite3.connect
class C:
    def __init__(self, c): self._c = c
    def __getattr__(self, a): return getattr(self._c, a)
    def commit(self):
        tick(); self._c.commit()
    def backup(self, dst, **kw):
        return self._c.backup(dst._c if isinstance(dst, C) else dst, **kw)
sqlite3.connect = lambda *a, **k: C(_orig(*a, **k))
_rep = os.replace
def rep(a, b, **kw):
    tick(); return _rep(a, b, **kw)
os.replace = rep
sys.argv = sys.argv[3:]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
finally:
    if MODE == "count":
        sys.stderr.write("\nBOUNDARIES=%d\n" % n[0])
'''


def _sandbox():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR", str(Path.home() / ".nexus_sealed_vault"))
    return ("(version 1)(allow default)" f'(deny file-write* (subpath "{ROOT}"))' f'(deny file-read* (subpath "{Path(vault).resolve()}"))'
            "(deny network*)")


def run(bundle, log, st, tick=None, rollback=None, mode=None, k=0, cfg=None, sigkill_after=None, timeout=120):
    bundle, st = Path(bundle).resolve(), Path(st).resolve()
    args = [str(bundle / "pipeline.py"), "--state", str(st), "--config", str(cfg or bundle / "config.json")]
    if rollback is not None:
        args += ["--rollback-to", str(rollback)]
    else:
        args += ["--log", str(Path(log).resolve()), "--tick", str(tick)]
    if mode:
        w = st.parent / "_eval_crash.py"
        w.write_text(CRASH)
        args = [str(w), mode, str(k)] + args
    cmd = ["/usr/bin/sandbox-exec", "-p", _sandbox(), sys.executable, "-B", *args]
    env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/var/empty", "PYTHONHASHSEED": "0"}
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=str(st.parent))
    if sigkill_after is not None:
        try:
            out, err = p.communicate(timeout=sigkill_after)
        except subprocess.TimeoutExpired:
            p.send_signal(signal.SIGKILL)
            out, err = p.communicate()
    else:
        out, err = p.communicate(timeout=timeout)
    b = [int(x.split("=")[1]) for x in err.splitlines() if x.startswith("BOUNDARIES=")]
    return dict(exit=p.returncode, wall_s=time.perf_counter() - t0, err=err[-500:], boundaries=b[-1] if b else None)


def _log_at(enc, root, t, write_fn, retention_fn):
    """The log directory as a consumer sees it at tick t (segments 1..t, retention applied)."""
    if (Path(root) / "log").exists():
        shutil.rmtree(Path(root) / "log")
    write_fn(enc, root, t, start=1)
    for k in range(1, t + 1):
        retention_fn(root, k)


def run_protocol(bundle, enc, work, write_fn, retention_fn, bad_cfg, ticks=12, sweep=(6, 10), checkpoints=(4, 8, 12), seed=0):
    work = Path(work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    lg, st = work / "logroot", work / "state"
    lg.mkdir(); st.mkdir()
    runs, states, pre, post = [], {}, {}, {}
    for t in range(1, ticks + 1):
        write_fn(enc, lg, t, start=t); retention_fn(lg, t)
        if t in sweep:
            pre[t] = work / f"pre{t}"
            shutil.copytree(st, pre[t])
        r = run(bundle, lg / "log", st, tick=t)
        runs.append(dict(stage=f"t{t}", **r))
        if r["exit"] != 0:
            break
        if t in sweep:
            post[t] = (read_state(st), offsets_of(st))
        if t in checkpoints:
            states[t] = read_state(st)
        if t == 8:
            shutil.copytree(st, work / "state_t8")
    sweeps = {}
    rng = random.Random(f"s4-sweep:{seed}")
    for t in sweep:
        if t not in post:
            continue
        lgt = work / f"log{t}"
        lgt.mkdir()
        _log_at(enc, lgt, t, write_fn, retention_fn)
        s0 = work / f"probe{t}"
        shutil.copytree(pre[t], s0)
        P = run(bundle, lgt / "log", s0, tick=t, mode="count")["boundaries"] or 0
        want = digest(*post[t])
        bad, n = [], 0
        for k in range(1, P + 2):
            for j in ([None] + ([1, max(1, P // 2), P] if k in (1, max(1, P // 2), P) else [])):
                s = work / f"c{t}_{k}_{j}"
                shutil.copytree(pre[t], s)
                run(bundle, lgt / "log", s, tick=t, mode="crash", k=k)
                if j is not None:
                    run(bundle, lgt / "log", s, tick=t, mode="crash", k=j)
                r = run(bundle, lgt / "log", s, tick=t)
                n += 1
                got = digest(read_state(s), offsets_of(s))
                if r["exit"] != 0 or got != want:
                    bad.append(dict(k=k, j=j, exit=r["exit"]))
                shutil.rmtree(s)
        for i in range(5):
            s = work / f"kill{t}_{i}"
            shutil.copytree(pre[t], s)
            wall = run(bundle, lgt / "log", s0 if False else s, tick=t, sigkill_after=rng.uniform(0.005, 0.12))
            r = run(bundle, lgt / "log", s, tick=t)
            n += 1
            if r["exit"] != 0 or digest(read_state(s), offsets_of(s)) != want:
                bad.append(dict(sigkill=i, exit=r["exit"], killed_exit=wall["exit"]))
            shutil.rmtree(s)
        sweeps[t] = dict(boundaries=P, trials=n, failures=bad)
    rb = None
    if (work / "state_t8").exists() and ticks >= 12:
        s = work / "rb_state"
        shutil.copytree(work / "state_t8", s)
        lgr = work / "rb_log"
        lgr.mkdir()
        for t in (9, 10):
            write_fn(enc, lgr, t, start=t) if (lgr / "log").exists() else _log_at(enc, lgr, t, write_fn, retention_fn)
            retention_fn(lgr, t)
            run(bundle, lgr / "log", s, tick=t, cfg=bad_cfg)
        rc = run(bundle, None, s, rollback=8, mode="crash", k=2)
        r_rec = None
        for t in (9, 10, 11, 12):
            if t >= 11:
                write_fn(enc, lgr, t, start=t); retention_fn(lgr, t)
            r_rec = run(bundle, lgr / "log", s, tick=t)
            if r_rec["exit"] != 0:
                break
        rb = dict(crashed_rollback_exit=rc["exit"], final_exit=r_rec["exit"], state=read_state(s))
    return dict(runs=runs, states=states, sweeps=sweeps, rollback=rb)


def _diagnose(truth, T, t, got):
    found = [f for f in FLAGS if (lambda w: w[t] != expected(truth, T)[t] and table_equal(t, got, w[t])[0])(
        expected(truth, T, frozenset([f])))]
    return found


def evaluate(truth, proto, ticks=12):
    reasons, tables = set(), {}
    exits_ok = all(r["exit"] == 0 for r in proto["runs"]) and len(proto["runs"]) == ticks
    for T, st in proto["states"].items():
        want = expected(truth, T)
        for t in OUT:
            ok, nd = table_equal(t, st[t], want[t])
            tables[f"t{T}/{t}"] = dict(ok=ok, diff=nd)
            if st[t] is None:
                reasons.add(f"MISSING_TABLE:{t}")
            elif not ok and isinstance(st[t], list):
                d = _diagnose(truth, T, t, st[t])
                reasons.update(d or [f"UNEXPLAINED_MISMATCH:{t}"])
    if not exits_ok:
        last = proto["runs"][-1]
        reasons.add(f"RUN_FAILED:{last['stage']}")
    eo_fail = sum(len(s["failures"]) for s in proto["sweeps"].values())
    eo_trials = sum(s["trials"] for s in proto["sweeps"].values())
    if eo_fail:
        reasons.add("EXACTLY_ONCE_VIOLATION")
    rb_ok = None
    if proto["rollback"]:
        want = expected(truth, 12)
        rb_ok = proto["rollback"]["final_exit"] == 0 and all(table_equal(t, proto["rollback"]["state"][t], want[t])[0] for t in OUT)
        if not rb_ok:
            reasons.add("ROLLBACK_FAILED")
    cps = {T: all(tables[f"t{T}/{t}"]["ok"] for t in OUT) for T in proto["states"]}
    data_ok = exits_ok and all(cps.values()) and len(cps) == 3
    return dict(correct=data_ok and not eo_fail and bool(rb_ok), data_ok=data_ok, checkpoints=cps, exits_ok=exits_ok,
                eo_trials=eo_trials, eo_failures=eo_fail, rollback_ok=rb_ok, reasons=sorted(reasons),
                silent=exits_ok and not (data_ok and not eo_fail and rb_ok), tables=tables,
                heldout_ok=cps.get(12, False), seen_ok=cps.get(4, False) and cps.get(8, False))
