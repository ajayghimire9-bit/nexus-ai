"""Protected data-engineering evaluator (Stage 2, NOT LOCKED). Lives OUTSIDE NEXUS: it imports nothing from the agent, the
pipeline template or the checks (tests/test_de_stage2.py enforces this), and its expected answers come from an independent
reference implementation over the generator's clean TRUTH world (de_env truth: the order version timeline, shipments, events,
manifest rows with their fault kind, inventory snapshots). It never parses the messy landing files and never reads a
pipeline's code.

Protocol (run_protocol): each pipeline is executed in a sandboxed subprocess on a fresh state directory:
  b1, b2      landing = batch 1, then batch 2 (earlier files removed: retention rule); the engineer had these two batches
  b3          landing = batch 3, HELD OUT: the engineer never saw it (new orders, corrections, faults of the same classes)
  b3_rerun    the same batch 3 again (idempotency)
  b3_crash    from a copy of the b2 state: batch 3 with a crash injected (os._exit(137) once half the landing files have been
              opened, via an audit hook the pipeline cannot see), then a normal restart (recovery)
evaluate() compares each state with the reference and classifies every mismatch. Diagnoses are exact: a counterfactual
reference with ONE rule violated (fan-out, dropped late changes, arrival-order apply, ...) must reproduce the observed table
exactly; structural reasons (rerun changed state, duplicate keys, schema, crash) are read off the states directly."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_COLS = {
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
TOL = {"amount_usd": 0.011, "net_revenue_usd": 0.011, "weight_kg": 0.0011, "on_time_rate": 0.00011}
# single-rule-violation variants of the reference (diagnosis vocabulary)
FLAGS = {
    "FANOUT_DOUBLE_COUNT": "revenue summed after joining orders to shipments/events (an order counted once per delivered shipment)",
    "DROPPED_LATE_CHANGES": "changes arriving in a later batch with event_ts <= the previous high-water mark were dropped",
    "ARRIVAL_ORDER_APPLY": "changes applied in arrival (seq) order instead of event-time order",
    "TEXT_TIMESTAMP_ORDER": "timestamps compared as text across UTC offsets instead of as instants",
    "IGNORED_SOFT_DELETES": "soft-deleted orders / inventory adjustments treated as live",
    "UNIT_MISMATCH": "weights summed without unit conversion (every value read as kg; unit never checked)",
    "NO_CURRENCY_CONVERSION": "amounts not converted to USD",
    "MALFORMED_ZERO_FILLED": "unparseable weights silently coerced to 0 instead of quarantined",
    "MALFORMED_DROPPED": "malformed manifest rows silently dropped instead of quarantined",
    "LATENESS_WINDOW_IGNORED": "late telemetry events not excluded from the SLA",
    "GUESSED_AMBIGUOUS_RULE": "an ambiguous business rule was resolved with the wrong answer (no clarification asked)",
}


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


# ----------------------------------------------------------------------------------------------- reference implementation
def expected(truth, b, flags=frozenset(), answers=None):
    """Reference output tables (dict name -> list of row tuples in OUT_COLS order) after batch b, from the truth world."""
    answers = dict(truth["answers"] if answers is None else answers)
    fx, units, L = truth["fx"], truth["units"], timedelta(hours=truth["lateness_hours"])
    vs = [v for v in truth["versions"] if v["batch"] <= b]
    if "DROPPED_LATE_CHANGES" in flags:     # a high-water-mark filter: batch k drops changes with event_ts <= max of batches < k
        wm = {k: max(ts(v["event_ts"]) for v in truth["versions"] if v["batch"] < k) for k in range(2, b + 1)}
        vs = [v for v in vs if v["batch"] == 1 or ts(v["event_ts"]) > wm[v["batch"]]]
    if "ARRIVAL_ORDER_APPLY" in flags:
        order = lambda v: v["seq"]
    elif "TEXT_TIMESTAMP_ORDER" in flags:
        order = lambda v: (v["event_ts_raw"], v["seq"])
    else:
        order = lambda v: (ts(v["event_ts"]), v["seq"])
    cur = {}
    for v in sorted(vs, key=order):
        cur[v["key"]] = v
    live = {k: v["row"] for k, v in cur.items()
            if v["op"] != "d" and (not v["soft"] or "IGNORED_SOFT_DELETES" in flags)}
    rate = (lambda c: 1.0) if "NO_CURRENCY_CONVERSION" in flags else (lambda c: fx[c])
    usd = {k: round(r["amount"] * rate(r["currency"]), 2) for k, r in live.items()}
    out = {"silver_orders": [(k, r["customer_id"], r["warehouse_id"], r["status"], usd[k], r["order_date"]) for k, r in live.items()]}
    ships = [s for s in truth["shipments"] if s["batch"] <= b]
    sh_by = {s["shipment_id"]: s for s in ships}
    evs = [e for e in truth["events"] if min(e["batches"]) <= b]
    deliv = {}
    for e in evs:
        if e["type"] == "DELIVERED" and e["shipment_id"] in sh_by:
            deliv[e["shipment_id"]] = e
    n_deliv = {}
    for sid in deliv:
        o = sh_by[sid]["order_id"]
        n_deliv[o] = n_deliv.get(o, 0) + 1
    rev = {w: 0.0 for w in truth["warehouses"]}
    for k, r in live.items():
        if r["status"] == "DELIVERED" and n_deliv.get(k):
            rev[r["warehouse_id"]] += usd[k] * (n_deliv[k] if "FANOUT_DOUBLE_COUNT" in flags else 1)
    out["gold_warehouse_revenue"] = [(w, round(x, 2)) for w, x in rev.items()]
    late = {e["event_id"] for e in evs if ts(e["ingest_ts"]) - ts(e["event_ts"]) > L}
    sla = {}
    for sid, e in deliv.items():
        o = sh_by[sid]["order_id"]
        if o not in live or (e["event_id"] in late and "LATENESS_WINDOW_IGNORED" not in flags):
            continue
        w = live[o]["warehouse_id"]
        d, t = sla.get(w, (0, 0))
        if "TEXT_TIMESTAMP_ORDER" in flags:
            on = e["event_ts_raw"] <= live[o]["promised_ts"]
        else:
            on = ts(e["event_ts"]) <= ts(live[o]["promised_ts"])
        sla[w] = (d + 1, t + on)
    out["gold_sla"] = [(w, d, t, round(t / d, 4)) for w, (d, t) in sla.items()]
    out["late_events"] = [(x,) for x in sorted(late)]
    seen, valid, quar = set(), {}, []
    for m in truth["manifest"]:
        if m["batch"] > b or m["record_ref"] in seen:
            continue
        seen.add(m["record_ref"])
        kind = m["kind"]
        if kind == "unparseable_weight" and "MALFORMED_ZERO_FILLED" in flags:
            valid[m["record_ref"]] = (m["shipment_id"], 0.0)
        elif kind == "unknown_unit" and "UNIT_MISMATCH" in flags:
            valid[m["record_ref"]] = (m["shipment_id"], m["value"])
        elif kind == "valid":
            valid[m["record_ref"]] = (m["shipment_id"], m["value"] if "UNIT_MISMATCH" in flags else m["value"] * units[m["unit"]])
        elif "MALFORMED_DROPPED" not in flags or kind == "orphan_shipment":
            quar.append(("manifest", m["record_ref"], kind))
    out["silver_manifest"] = [(ref, sid, round(kg, 3)) for ref, (sid, kg) in valid.items()]
    out["quarantine"] = quar
    inc = set(truth["carrier_include"])
    if answers.get("carrier_volume:CANCELLED") == "include":
        inc.add("CANCELLED")
    if "GUESSED_AMBIGUOUS_RULE" in flags and "carrier_volume:CANCELLED" in truth["answers"]:
        inc ^= {"CANCELLED"}
    vol = {}
    for ref, (sid, kg) in valid.items():
        s = sh_by.get(sid)
        if not s or s["order_id"] not in live or live[s["order_id"]]["status"] not in inc:
            continue
        key = (live[s["order_id"]]["warehouse_id"], s["carrier"])
        vol[key] = vol.get(key, 0.0) + kg
    out["gold_carrier_volume"] = [(w, c, round(x, 3)) for (w, c), x in vol.items()]
    bk = dict(truth["buckets"])
    for q, a in answers.items():
        if q.startswith("status_bucket:"):
            bk[q.split(":", 1)[1]] = a
    cnt = {}
    for k, r in live.items():
        key = (r["warehouse_id"], bk.get(r["status"], "UNMAPPED"))
        cnt[key] = cnt.get(key, 0) + 1
    out["gold_status_counts"] = [(w, x, n) for (w, x), n in cnt.items()]
    inv = {}
    for x in truth["inventory"]:
        if x["batch"] > b or x.get("hard_deleted_in", 9) <= b:
            continue
        if x.get("soft_deleted_in", 9) <= b and "IGNORED_SOFT_DELETES" not in flags:
            continue
        key = (x["warehouse_id"], x["sku"])
        inv[key] = inv.get(key, 0) + x["qty"]
    out["gold_inventory"] = [(w, s, q) for (w, s), q in inv.items()]
    return out


def guessed_variants(truth):
    """Every wrong resolution of each genuine ambiguity (for GUESSED_AMBIGUOUS_RULE diagnosis on status buckets)."""
    out = []
    for q, a in truth["answers"].items():
        if q.startswith("status_bucket:"):
            for alt in ("open", "fulfilled", "cancelled", "UNMAPPED", "other", "unknown"):
                if alt != a:
                    out.append(dict(truth["answers"], **{q: alt}))
    return out


# ----------------------------------------------------------------------------------------------- reading and comparing
def read_state(db):
    """Output tables of a state db as dict name -> list of tuples (missing table -> None; missing column -> 'SCHEMA')."""
    out = {}
    if not Path(db).exists():
        return {t: None for t in OUT_COLS}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for t, (cols, _) in OUT_COLS.items():
            try:
                have = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
                if not have:
                    out[t] = None
                elif any(c not in have for c in cols):
                    out[t] = "SCHEMA"
                else:
                    out[t] = [tuple(r) for r in con.execute(f'SELECT {",".join(chr(34) + c + chr(34) for c in cols)} FROM "{t}"')]
            except sqlite3.Error:
                out[t] = None
    finally:
        con.close()
    return out


def _norm(t, rows):
    cols = OUT_COLS[t][0]
    def cell(c, v):
        if isinstance(v, float) and v.is_integer() and c not in TOL:
            return int(v)
        if c == "order_id" and isinstance(v, str) and v.isdigit():
            return int(v)
        return v
    return [tuple(cell(c, v) for c, v in zip(cols, r)) for r in rows]


def table_equal(t, got, want):
    """Exact multiset equality by primary key with per-column numeric tolerance. Returns (equal, n_diff_rows)."""
    cols, pk = OUT_COLS[t]
    if got is None or got == "SCHEMA":
        return False, len(want)
    g, w = _norm(t, got), _norm(t, want)
    idx = [cols.index(c) for c in pk]
    key = lambda r: tuple(str(r[i]) for i in idx)
    gd, wd = {}, {}
    for r in g:
        gd.setdefault(key(r), []).append(r)
    for r in w:
        wd.setdefault(key(r), []).append(r)
    diff = 0
    for k in set(gd) | set(wd):
        a, b_ = gd.get(k, []), wd.get(k, [])
        if len(a) != len(b_):
            diff += max(len(a), len(b_)); continue
        for x, y in zip(sorted(a, key=str), sorted(b_, key=str)):
            for c, u, v in zip(cols, x, y):
                if c in TOL and isinstance(u, (int, float)) and isinstance(v, (int, float)):
                    if abs(u - v) > TOL[c]:
                        diff += 1; break
                elif str(u) != str(v):
                    diff += 1; break
    return diff == 0, diff


def dup_keys(t, rows):
    if not isinstance(rows, list):
        return 0
    cols, pk = OUT_COLS[t]
    idx = [cols.index(c) for c in pk]
    keys = [tuple(str(r[i]) for i in idx) for r in rows]
    return len(keys) - len(set(keys))


def digest(state):
    return hashlib.sha256(json.dumps({t: sorted(map(str, v)) if isinstance(v, list) else v for t, v in state.items()},
                                     sort_keys=True).encode()).hexdigest()


# ----------------------------------------------------------------------------------------------- stakeholder oracle
class Stakeholder:
    """Simulated domain stakeholder. Answers only questions the spec genuinely leaves open (truth.answers); everything else
    is answered NOT_A_QUESTION and counted as an unnecessary clarification. Every call is logged."""

    def __init__(self, truth):
        self._a = dict(truth["answers"])
        self.log = []

    def ask(self, topic, value):
        q = f"{topic}:{value}"
        a = self._a.get(q, "NOT_A_QUESTION")
        self.log.append(dict(question=q, answer=a))
        return a


# ----------------------------------------------------------------------------------------------- execution protocol
def _sandbox():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR", str(Path.home() / ".nexus_sealed_vault"))
    return ("(version 1)(allow default)" f'(deny file-write* (subpath "{ROOT}"))' f'(deny file-read* (subpath "{Path(vault).resolve()}"))'
            "(deny network*)")


CRASH_WRAPPER = r'''
import os, runpy, sys
LAND, K = os.path.realpath(sys.argv[1]), int(sys.argv[2])
n = [0]
def hook(ev, args):
    if ev in ("open", "sqlite3.connect") and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.fsdecode(args[0])
        if p.startswith("file:"):
            p = p[5:].split("?", 1)[0]
        p = os.path.realpath(p)
        if p.startswith(LAND + os.sep):
            n[0] += 1
            if n[0] > K:
                os._exit(137)
sys.addaudithook(hook)
sys.argv = sys.argv[3:]
runpy.run_path(sys.argv[0], run_name="__main__")
'''


def run_pipeline(bundle, landing, state, crash_after=None, timeout=120):
    """One sandboxed run of bundle/pipeline.py. Returns dict(exit, wall_s, stderr_tail)."""
    args = [str(Path(bundle) / "pipeline.py"), "--landing", str(landing), "--state", str(state), "--config",
            str(Path(bundle) / "config.json")]
    if crash_after is not None:
        w = Path(state).parent / "_crash_wrapper.py"
        w.write_text(CRASH_WRAPPER)
        args = [str(w), str(landing), str(crash_after)] + args
    env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/var/empty", "PYTHONHASHSEED": "0"}
    t0 = time.perf_counter()
    try:
        p = subprocess.run(["/usr/bin/sandbox-exec", "-p", _sandbox(), sys.executable, "-B", *args], capture_output=True,
                           text=True, env=env, cwd=str(Path(state).parent), timeout=timeout)
        code, err = p.returncode, p.stderr[-400:]
    except subprocess.TimeoutExpired:
        code, err = "TIMEOUT", ""
    return dict(exit=code, wall_s=time.perf_counter() - t0, stderr_tail=err)


def _land(inputs, b, landing):
    if landing.exists():
        shutil.rmtree(landing)
    shutil.copytree(Path(inputs) / f"batch{b}", landing)
    return sum(1 for f in landing.rglob("*") if f.is_file())


def run_protocol(bundle, inputs, work):
    """Execute the protocol; returns dict(states={name: tables}, runs=[...])."""
    work = Path(work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    land, st = work / "landing", work / "state"
    st.mkdir()
    runs, states = [], {}
    for b in (1, 2, 3):
        if b == 3:
            shutil.copytree(st, work / "state_b2")
        _land(inputs, b, land)
        runs.append(dict(stage=f"b{b}", **run_pipeline(bundle, land, st)))
        states[f"b{b}"] = read_state(st / "lake.db")
    runs.append(dict(stage="b3_rerun", **run_pipeline(bundle, land, st)))
    states["b3_rerun"] = read_state(st / "lake.db")
    shutil.rmtree(st)
    shutil.copytree(work / "state_b2", st)
    nfiles = _land(inputs, 3, land)
    runs.append(dict(stage="b3_crash", **run_pipeline(bundle, land, st, crash_after=max(1, nfiles // 2))))
    runs.append(dict(stage="b3_restart", **run_pipeline(bundle, land, st)))
    states["b3_crash"] = read_state(st / "lake.db")
    return dict(states=states, runs=runs)


# ----------------------------------------------------------------------------------------------- evaluation
def _diagnose(truth, b, t, got):
    found = []
    for f in FLAGS:
        if f == "GUESSED_AMBIGUOUS_RULE" and not truth["answers"]:
            continue
        want = expected(truth, b, frozenset([f]))
        if want != expected(truth, b) and table_equal(t, got, want[t])[0]:
            found.append(f)
    if t == "gold_status_counts":
        for ans in guessed_variants(truth):
            if table_equal(t, got, expected(truth, b, answers=ans)[t])[0]:
                found.append("GUESSED_AMBIGUOUS_RULE"); break
    if b >= 2 and table_equal(t, got, expected(truth, b - 1)[t])[0]:
        found.append("STALE_OUTPUT")
    return sorted(set(found))


def evaluate(truth, proto, oracle_log=(), freshness_sla_s=60.0):
    """Score one pipeline's protocol run. Returns the correctness / reliability block of the scorecard + exact diagnoses."""
    st, runs = proto["states"], {r["stage"]: r for r in proto["runs"]}
    exits_ok = all(runs[s]["exit"] == 0 for s in ("b1", "b2", "b3", "b3_rerun", "b3_restart"))
    crashed = runs["b3_crash"]["exit"] == 137
    tables, reasons = {}, set()
    for stage, b in (("b1", 1), ("b2", 2), ("b3", 3), ("b3_rerun", 3), ("b3_crash", 3)):
        want = expected(truth, b)
        for t in OUT_COLS:
            got = st[stage][t]
            ok, nd = table_equal(t, got, want[t])
            tables[f"{stage}/{t}"] = dict(ok=ok, diff_rows=nd)
            if got is None:
                reasons.add(f"MISSING_TABLE:{t}")
            elif got == "SCHEMA":
                reasons.add(f"SCHEMA_VIOLATION:{t}")
            elif dup_keys(t, got):
                reasons.add(f"DUPLICATE_KEYS:{t}")
            if not ok and stage in ("b1", "b2", "b3") and isinstance(got, list):
                d = _diagnose(truth, b, t, got)
                reasons.update(d if d else [f"UNEXPLAINED_MISMATCH:{t}"])
    if digest(st["b3_rerun"]) != digest(st["b3"]):
        reasons.add("NON_IDEMPOTENT_RERUN")
    recovered = crashed and digest(st["b3_crash"]) == digest(st["b3"])       # restart reproduces the pipeline's own clean run
    if crashed and not recovered:
        reasons.add("CRASH_RECOVERY_FAILED")
    asked = {x["question"] for x in oracle_log}
    genuine = set(truth["answers"])
    if genuine - asked:
        reasons.add("UNASKED_AMBIGUITY")
    data_ok = all(v["ok"] for k, v in tables.items() if k.split("/")[0] in ("b1", "b2", "b3"))
    seen_ok = all(v["ok"] for k, v in tables.items() if k.split("/")[0] in ("b1", "b2"))
    nonempty = all(isinstance(st[s][t], list) and st[s][t] for s in ("b1", "b2", "b3") for t in OUT_COLS)
    correct = data_ok and exits_ok and not (reasons - {"UNASKED_AMBIGUITY"}) and not (genuine - asked)
    silent = exits_ok and nonempty and not data_ok
    fresh_viol = sum(1 for s in ("b1", "b2", "b3") if runs[s]["exit"] != 0 or runs[s]["wall_s"] > freshness_sla_s) + \
        (1 if "STALE_OUTPUT" in reasons else 0)
    dup_side = sum(dup_keys(t, st[s][t]) for s in ("b3", "b3_rerun", "b3_crash") for t in OUT_COLS)
    return dict(correct=correct, silent_data_error=silent, seen_batches_ok=seen_ok,
                heldout_batch_ok=all(v["ok"] for k, v in tables.items() if k.startswith("b3/")), exits_ok=exits_ok, nonempty=nonempty,
                reasons=sorted(reasons), tables=tables, idempotent=digest(st["b3_rerun"]) == digest(st["b3"]),
                crash_injected=crashed, recovered=recovered,
                recovery_s=runs["b3_restart"]["wall_s"], freshness_violations=fresh_viol, duplicate_side_effects=dup_side,
                unresolved_ambiguity=len(genuine - asked), unnecessary_clarifications=len(asked - genuine),
                clarifications=len(oracle_log), exits={s: r["exit"] for s, r in runs.items()},
                wall_s={s: round(r["wall_s"], 3) for s, r in runs.items()})
