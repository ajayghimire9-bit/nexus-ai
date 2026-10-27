"""Stage 4 engineering checks (NOT LOCKED). Standalone (stdlib only, imports nothing from NEXUS or the evaluator); shipped
in every deliverable bundle. Inputs: the spec and the VISIBLE log (ticks 1-8) only. Nothing here knows expected outputs.

STANDARD (what a careful conventional engineer runs; the Conventional_Checked suite):
  runs_all_ticks, schema_keys_not_null, rerun_unchanged, nonempty_outputs
NEXUS (added on top):
  accounting_and_lag             every visible record is applied / duplicate / quarantined (none dropped); offsets reach the
                                 end of every partition directory
  crash_sweep                    terminate before every write / ack boundary, again during recovery, and by random SIGKILL;
                                 the restarted state must equal the uninterrupted run
  duplicate_delivery_invariance  every record redelivered (same msg_id) must not change the outputs
  arrival_permutation_invariance same-key CDC records permuted in arrival must not change the outputs (source_version order)
  backfill_timing_invariance     the snapshot delivered earlier or later must not change silver
  utc_offset_invariance          timestamps re-rendered in other UTC offsets must not change the outputs
  gold_equals_recompute          gold recomputed from the pipeline's own silver per the spec rules
  lateness_conformance           late_events equals the spec watermark rule applied to the visible telemetry
  silver_rederivation            silver equals the spec (source_version LWW, tombstones, registry decoding, net_usd) applied to
                                 the visible log
  rollback_drill                 bad deploy, rollback crashed half way, recovery, reprocessing: equals the clean run"""
from __future__ import annotations

import hashlib
import json
import os
import random
import resource
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

STANDARD = ["runs_all_ticks", "schema_keys_not_null", "rerun_unchanged", "nonempty_outputs"]
NEXUS = STANDARD + ["accounting_and_lag", "gold_equals_recompute", "silver_rederivation", "lateness_conformance",
                    "duplicate_delivery_invariance", "arrival_permutation_invariance", "backfill_timing_invariance",
                    "utc_offset_invariance", "crash_sweep", "rollback_drill"]     # cheap specific re-derivations first
IMPLICATE = {"runs_all_ticks": [], "schema_keys_not_null": ["dedup", "gold_maintenance"],
             "rerun_unchanged": ["dedup", "gold_maintenance", "commit_protocol"], "nonempty_outputs": ["lateness", "malformed"],
             "accounting_and_lag": ["partition_discovery", "malformed", "dedup", "commit_protocol"],
             "crash_sweep": ["commit_protocol", "dedup", "gold_maintenance"], "duplicate_delivery_invariance": ["dedup"],
             "arrival_permutation_invariance": ["apply_order", "backfill_merge"],
             "backfill_timing_invariance": ["backfill_merge", "apply_order"], "utc_offset_invariance": ["ts_parse"],
             "gold_equals_recompute": ["gold_maintenance"], "lateness_conformance": ["lateness", "ts_parse", "ts_format"],
             "silver_rederivation": ["schema_handling", "fx", "deletes", "backfill_merge", "apply_order"],
             "rollback_drill": ["snapshots"]}
TOL = {"net_usd": 0.011, "revenue_usd": 0.011, "weight_kg": 0.0021, "on_time_rate": 0.00011}

CRASH = r'''
import os, runpy, sqlite3, sys
MODE, K = sys.argv[1], int(sys.argv[2])
n = [0]
def step():
    n[0] += 1
    if MODE == "crash" and n[0] == K:
        os._exit(137)
_c = sqlite3.connect
class P:
    def __init__(s, c): s._c = c
    def __getattr__(s, a): return getattr(s._c, a)
    def commit(s): step(); s._c.commit()
    def backup(s, d, **k): return s._c.backup(getattr(d, "_c", d), **k)
sqlite3.connect = lambda *a, **k: P(_c(*a, **k))
_r = os.replace
os.replace = lambda a, b, **k: (step(), _r(a, b, **k))[1]
sys.argv = sys.argv[3:]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
finally:
    if MODE == "count":
        sys.stderr.write("\nSTEPS=%d\n" % n[0])
'''


def utc(s):
    if isinstance(s, (int, float)):
        return datetime.fromtimestamp(s / 1000, timezone.utc)
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


class Runner:
    def __init__(self, profile=None):
        self.profile, self.runs, self.cpu_s = profile, 0, 0.0

    def run(self, bundle, log, st, tick=None, rollback=None, mode=None, k=0, cfg=None, kill_after=None):
        bundle, st = Path(bundle).resolve(), Path(st).resolve()
        args = [str(bundle / "pipeline.py"), "--state", str(st), "--config", str(cfg or bundle / "config.json")]
        args += ["--rollback-to", str(rollback)] if rollback is not None else ["--log", str(Path(log).resolve()), "--tick", str(tick)]
        if mode:
            w = st.parent / "_chk_crash.py"
            w.write_text(CRASH)
            args = [str(w), mode, str(k)] + args
        cmd = [sys.executable, "-B", *args]
        if self.profile and Path("/usr/bin/sandbox-exec").exists():
            cmd = ["/usr/bin/sandbox-exec", "-p", self.profile] + cmd
        env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/var/empty", "PYTHONHASHSEED": "0"}
        r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=str(st.parent))
        try:
            out, err = p.communicate(timeout=kill_after if kill_after is not None else 120)
        except subprocess.TimeoutExpired:
            p.send_signal(signal.SIGKILL)
            out, err = p.communicate()
        r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.runs += 1
        self.cpu_s += (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
        steps = [int(x.split("=")[1]) for x in err.splitlines() if x.startswith("STEPS=")]
        stage = [x for x in err.splitlines() if "StageError: stage=" in x]
        return dict(exit=p.returncode, err=err[-600:], steps=steps[-1] if steps else None,
                    stage=stage[-1].split("stage=")[1].split()[0] if stage else None)


# ------------------------------------------------------------------------------------------------ the visible log
def segments(log):
    """[(topic, part, path, tick)] of every segment in a log dir (tick from the first record's ingest_ts and the spec)."""
    out = []
    for f in sorted(Path(log).rglob("*.jsonl")):
        out.append((f.parent.parent.name, int(f.parent.name[1:]), f))
    return out


def tick_of(ingest, spec):
    t0 = utc(spec["ticks"]["t0"])
    d = (utc(ingest) - t0).total_seconds() / (spec["ticks"]["tick_hours"] * 3600)
    return max(1, int(d) + 1) if d > 0 else 1


def records(log):
    out = []
    for topic, part, f in segments(log):
        for line in f.read_text().split("\n"):
            if line.strip():
                try:
                    out.append((topic, part, json.loads(line)))
                except ValueError:
                    out.append((topic, part, {"_undecodable": line}))
    return out


def rewrite(log, dst, fn):
    """Copy a log applying fn(topic, part, [records]) -> [records] per partition; offsets reassigned densely, one segment
    per tick (records keep their ingest_ts, so tick membership is preserved)."""
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    parts = {}
    for topic, part, f in segments(log):
        parts.setdefault((topic, part), []).extend(json.loads(l) for l in f.read_text().split("\n") if l.strip())
    for d in Path(log).glob("*/p*"):
        (dst / d.parent.name / d.name).mkdir(parents=True, exist_ok=True)
    for (topic, part), recs in parts.items():
        recs = fn(topic, part, recs)
        seg = {}
        for i, r in enumerate(recs):
            r = dict(r, offset=i)
            seg.setdefault(r["_tick"], []).append(r)
        for tk, rs in seg.items():
            (dst / topic / f"p{part}" / f"{rs[0]['offset']:08d}.jsonl").write_text(
                "".join(json.dumps({k: v for k, v in x.items() if k != "_tick"}, sort_keys=True) + "\n" for x in rs))
    return dst


def with_ticks(spec, fn):
    def g(topic, part, recs):
        recs = [dict(r, _tick=tick_of(r["ingest_ts"], spec)) for r in recs]
        out = fn(topic, part, recs)
        return sorted(out, key=lambda r: r["_tick"])
    return g


def grow(full, dst, upto, spec, keep=6):
    """The log as a consumer sees it at tick `upto`: segments of ticks <= upto, retention applied."""
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    for d in Path(full).glob("*/p*"):
        (dst / d.parent.name / d.name).mkdir(parents=True, exist_ok=True)
    for topic, part, f in segments(full):
        first = json.loads(f.read_text().split("\n", 1)[0])
        tk = tick_of(first["ingest_ts"], spec)
        if upto - keep < tk <= upto:
            shutil.copy(f, dst / topic / f"p{part}" / f.name)
    return dst


def replay(runner, bundle, full_log, spec, work, ticks, cfg_at=None):
    """Fresh state; run tick by tick over a growing log. Returns (runs, state, per-tick log dirs)."""
    work = Path(work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    st, runs = work / "state", []
    st.mkdir()
    for t in ticks:
        lg = grow(full_log, work / "log", t, spec)
        r = runner.run(bundle, lg, st, tick=t, cfg=(cfg_at or {}).get(t))
        runs.append(r)
        if r["exit"] != 0:
            break
    return runs, st


def tables(st, spec, internal=False):
    db = Path(st) / "lake.db"
    out = {}
    if not db.exists():
        return out
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for t, o in spec["outputs"].items():
            have = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
            out[t] = ([tuple(r) for r in con.execute(f'SELECT {",".join(chr(34) + c + chr(34) for c in o["columns"])} FROM "{t}"')]
                      if have and all(c in have for c in o["columns"]) else None)
        if internal:
            for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                if t not in out:
                    out[t] = sorted(map(str, con.execute(f'SELECT * FROM "{t}"').fetchall()))
    finally:
        con.close()
    return out


def same(spec, a, b, only=None, skip=()):
    bad = []
    for t in (only or spec["outputs"]):
        if t in skip:
            continue
        x, y = a.get(t), b.get(t)
        if not isinstance(x, list) or not isinstance(y, list):
            if x != y:
                bad.append(t)
            continue
        cols = spec["outputs"][t]["columns"]
        def norm(rs):
            return sorted((tuple(round(v, 2) if isinstance(v, float) and c in TOL else v for c, v in zip(cols, r)) for r in rs), key=str)
        if norm(x) != norm(y):
            nx, ny = norm(x), norm(y)
            ok = len(nx) == len(ny) and all(all((abs(u - v) <= TOL.get(c, 0)) if isinstance(u, (int, float)) and isinstance(v, (int, float))
                                                 else str(u) == str(v) for c, u, v in zip(cols, r, s)) for r, s in zip(nx, ny))
            if not ok:
                bad.append(t)
    return bad


def diffcount(spec, a, b, only=None, skip=()):
    """Severity: rows in the symmetric difference of the normalized tables (a missing table counts its other side)."""
    n = 0
    for t in (only or spec["outputs"]):
        if t in skip:
            continue
        x, y = a.get(t) or [], b.get(t) or []
        cols = spec["outputs"][t]["columns"]
        norm = lambda rs: {tuple(round(v, 2) if isinstance(v, float) else v for v in r) for r in rs}
        n += len(norm(x) ^ norm(y)) + abs(len(x) - len(set(map(tuple, x)))) + abs(len(y) - len(set(map(tuple, y))))
    return n


def digest(st, spec):
    t = tables(st, spec)
    st = Path(st)
    off = None
    if (st / "offsets.json").exists():
        off = json.loads((st / "offsets.json").read_text())["off"]
    elif (st / "lake.db").exists():
        con = sqlite3.connect(f"file:{st / 'lake.db'}?mode=ro", uri=True)
        try:
            off = sorted(con.execute("SELECT topic, part, next FROM _offsets").fetchall())
        except sqlite3.Error:
            pass
        con.close()
    return hashlib.sha256(json.dumps([{k: sorted(map(str, v)) if isinstance(v, list) else v for k, v in sorted(t.items())}, off],
                                     default=str).encode()).hexdigest()


# ------------------------------------------------------------------------------------------------ spec re-derivations
def registry(recs):
    reg = {}
    for topic, part, r in recs:
        if topic == "_schemas":
            reg[(r.get("subject", "orders"), r["version"])] = r
    return reg


def derive_silver(spec, recs):
    reg = registry(recs)
    fx = spec["fx_to_usd"]
    best = {}
    for topic, part, r in recs:
        if topic not in ("orders_cdc", "backfill_orders") or "control" in r or "_undecodable" in r:
            continue
        cur = best.get(r["key"])
        if cur is None or r["source_version"] > cur["source_version"]:
            best[r["key"]] = r
    out = {}
    for k, r in best.items():
        a = r.get("after")
        if r["op"] == "d" or a is None:
            continue
        rg = reg.get(("orders", r.get("schema_version", 1)), {"fields": spec["physical_names_v1"], "types": {"discount": "int"}})
        f = rg["fields"]
        if int(a.get(f["deleted"]) or 0):
            continue
        disc = float(a[f["discount"]])
        out[k] = (k, a[f["warehouse_id"]], a[f["status"]], round(float(a[f["amount"]]) * (1 - disc / 100) * fx[a[f["currency"]]], 2),
                  a[f["promised_ts"]], r.get("schema_version", 1), disc, a[f["currency"]])
    return out


def derive_late(spec, recs):
    reg = registry(recs)
    L = timedelta(hours=spec["lateness"]["allowed_hours"])
    rows, seen = [], set()
    for topic, part, r in recs:
        if topic != "telemetry" or "_undecodable" in r or r["msg_id"] in seen:
            continue
        seen.add(r["msg_id"])
        et = utc(r["event_ts"])
        if (et - utc(r["ingest_ts"])).total_seconds() > 300:
            continue                                                  # future events: quarantined, not in the watermark
        rows.append((r["msg_id"], tick_of(r["ingest_ts"], spec), et))
    late = set()
    for m, k, et in rows:
        prior = [x for _, kk, x in rows if kk < k]
        if prior and et < max(prior) - L:
            late.add(m)
    return late


# ------------------------------------------------------------------------------------------------ the suite
def verify(bundle, spec, full_log, work, runner, suite=NEXUS, ticks=range(1, 9), stop_at_first=True, order=None):
    work = Path(work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    res, ticks = [], list(ticks)
    names = [c for c in (order or suite) if c in suite]

    def add(name, ok, detail="", implicate=None, score=None):
        res.append(dict(check=name, ok=bool(ok), detail=detail, implicate=implicate if implicate is not None else IMPLICATE[name],
                        score=(0 if ok else 1) if score is None else score))
        return ok or not stop_at_first

    runs, st = replay(runner, bundle, full_log, spec, work / "base", ticks)
    ok_runs = add("runs_all_ticks", all(r["exit"] == 0 for r in runs) and len(runs) == len(ticks),
                  runs[-1]["err"][-200:] if runs[-1]["exit"] else "", [])
    res[-1]["stage"] = runs[-1]["stage"]
    if not ok_runs:
        return res
    base = tables(st, spec)
    recs = records(grow(full_log, work / "vis", ticks[-1], spec, keep=10**6))
    for name in names[1:] if names[0] == "runs_all_ticks" else names:
        if name == "runs_all_ticks":
            continue
        ok, det, imp, score = _one(name, bundle, spec, full_log, work, runner, ticks, st, base, recs)
        if not add(name, ok, det, imp, score if not ok else 0):
            return res
    return res


def _one(name, bundle, spec, full_log, work, runner, ticks, st, base, recs):
    imp = None
    if name == "schema_keys_not_null":
        bad = []
        for t, o in spec["outputs"].items():
            rows = base.get(t)
            if rows is None:
                bad.append(f"{t}:missing"); continue
            idx = [o["columns"].index(c) for c in o["pk"]]
            ks = [tuple(r[i] for i in idx) for r in rows]
            if len(ks) != len(set(ks)) or any(v is None for k in ks for v in k):
                bad.append(t)
        return not bad, f"bad {bad}", None, len(bad)
    if name == "rerun_unchanged":
        s2 = work / "rerun"
        shutil.copytree(st, s2)
        before = tables(st, spec, internal=True)
        r = runner.run(bundle, grow(full_log, work / "log_rr", ticks[-1], spec), s2, tick=ticks[-1])
        after = tables(s2, spec, internal=True)
        ch = sorted(t for t in after if after.get(t) != before.get(t) and not t.startswith("_rev") or (t == "_rev_acc" and after.get(t) != before.get(t)))
        sev = diffcount(spec, before, after) + (after.get("_rev_acc") != before.get("_rev_acc")) + (r["exit"] != 0)
        return sev == 0, f"changed {ch[:5]}", None, sev
    if name == "nonempty_outputs":
        empty = [t for t, v in base.items() if not v and t not in ("quarantine", "late_events")]
        return not empty, f"empty {empty}", None, len(empty)
    if name == "accounting_and_lag":
        acc = {(t, s): n for t, s, n in base["record_accounting"]}
        per = {}
        for topic, part, r in recs:
            if topic != "_schemas":
                per[topic] = per.get(topic, 0) + 1
        bad = [t for t, n in per.items() if sum(v for (tt, s), v in acc.items() if tt == t and s in ("applied", "duplicate", "quarantined")) != n]
        dropped = [k for k in acc if k[1] == "dropped"]
        ends = {}
        for topic, part, r in recs:
            ends[(topic, part)] = max(ends.get((topic, part), -1), r["offset"])
        offs = {}
        if (Path(st) / "offsets.json").exists():
            offs = {(t, p): n for t, p, n in json.loads((Path(st) / "offsets.json").read_text())["off"]}
        else:
            con = sqlite3.connect(f"file:{Path(st) / 'lake.db'}?mode=ro", uri=True)
            offs = {(t, p): n for t, p, n in con.execute("SELECT topic, part, next FROM _offsets")}
            con.close()
        lag = [k for k, e in ends.items() if offs.get(k, 0) != e + 1]
        imp = (["partition_discovery", "commit_protocol"] if lag else ["malformed"] if dropped else ["dedup", "partition_discovery"])
        sev = len(bad) + sum(acc[k] for k in dropped) + sum(abs(offs.get(k, 0) - e - 1) for k, e in ends.items())
        return sev == 0, f"unaccounted {bad} dropped {dropped} lagging {lag}", imp, sev
    if name == "crash_sweep":
        want_fail = []
        for t in (4, 7):
            pre_runs, pre = replay(runner, bundle, full_log, spec, work / f"pre{t}", ticks[:t - 1]) if t > 1 else (None, None)
            lg = grow(full_log, work / f"lg{t}", t, spec)
            clean = work / f"cl{t}"
            shutil.copytree(pre, clean)
            runner.run(bundle, lg, clean, tick=t)
            want = digest(clean, spec)
            probe = work / f"pb{t}"
            shutil.copytree(pre, probe)
            P = runner.run(bundle, lg, probe, tick=t, mode="count")["steps"] or 0
            trials = [(k, None) for k in range(1, P + 2)] + [(1, 1), (P, max(1, P // 2)), (max(1, P // 2), P)]
            rng = random.Random(f"chk:{t}")
            for k, j in trials + [("kill", i) for i in range(3)]:
                s = work / f"cr{t}_{k}_{j}"
                shutil.copytree(pre, s)
                if k == "kill":
                    runner.run(bundle, lg, s, tick=t, kill_after=rng.uniform(0.005, 0.1))
                else:
                    runner.run(bundle, lg, s, tick=t, mode="crash", k=k)
                    if j is not None:
                        runner.run(bundle, lg, s, tick=t, mode="crash", k=j)
                r = runner.run(bundle, lg, s, tick=t)
                if r["exit"] != 0 or digest(s, spec) != want:
                    want_fail.append((t, k, j))
                shutil.rmtree(s)
        return not want_fail, f"failed crash trials {want_fail[:4]} of {len(want_fail)}", None, len(want_fail)
    if name == "duplicate_delivery_invariance":
        fl = rewrite(full_log, work / "dup_log", with_ticks(spec, lambda tp, p, rs: rs + [dict(r) for r in rs if tp != "_schemas"]))
        _, s = replay(runner, bundle, fl, spec, work / "dup", ticks)
        n = diffcount(spec, tables(s, spec), base, skip=("record_accounting",))
        return n == 0, f"differing rows {n}", None, n
    if name == "arrival_permutation_invariance":
        eff = {}                                   # registry causality: a version can only arrive once it is registered
        for tp, p, r in recs:
            if tp == "_schemas" and r.get("subject", "orders") == "orders":
                eff[r["version"]] = min(eff.get(r["version"], 99), tick_of(r["ingest_ts"], spec))

        def perm(tp, p, rs):
            if tp != "orders_cdc":
                return rs
            rng = random.Random(f"perm:{p}")
            by = {}
            for i, r in enumerate(rs):
                by.setdefault(r["key"], []).append(i)
            out = list(rs)
            for k, idx in by.items():
                vals = [rs[i] for i in idx]
                for _ in range(20):
                    rng.shuffle(vals)
                    if all(eff.get(v.get("schema_version", 1), 1) <= rs[i]["_tick"] for i, v in zip(idx, vals)):
                        break
                else:
                    vals = [rs[i] for i in idx]
                for i, v in zip(idx, vals):
                    out[i] = dict(v, ingest_ts=rs[i]["ingest_ts"], _tick=rs[i]["_tick"])
            return out
        fl = rewrite(full_log, work / "perm_log", with_ticks(spec, perm))
        _, s = replay(runner, bundle, fl, spec, work / "perm", ticks)
        n = diffcount(spec, tables(s, spec), base, skip=("record_accounting", "late_events", "gold_sla"))
        return n == 0, f"differing rows {n}", None, n
    if name == "backfill_timing_invariance":
        bad = 0
        for when in (ticks[0], ticks[-1]):
            def mv(tp, p, rs, when=when):
                if tp != "backfill_orders":
                    return rs
                t0 = utc(spec["ticks"]["t0"]) + timedelta(hours=spec["ticks"]["tick_hours"] * (when - 1) + 0.5)
                return [dict(r, ingest_ts=(t0 + timedelta(seconds=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), _tick=when) for i, r in enumerate(rs)]
            fl = rewrite(full_log, work / f"bf_log{when}", with_ticks(spec, mv))
            _, s = replay(runner, bundle, fl, spec, work / f"bf{when}", ticks)
            bad += diffcount(spec, tables(s, spec), base, only=["silver_orders", "gold_warehouse_revenue", "gold_status_counts"])
        return bad == 0, f"differing rows {bad}", None, bad
    if name == "utc_offset_invariance":
        offs = [-480, -300, 0, 120, 330, 540]
        def tz(tp, p, rs):
            rng = random.Random(f"tz:{tp}:{p}")
            out = []
            for r in rs:
                r = dict(r)
                if tp == "telemetry" and isinstance(r.get("event_ts"), str):
                    r["event_ts"] = _render(utc(r["event_ts"]), rng.choice(offs))
                out.append(r)
            return out
        fl = rewrite(full_log, work / "tz_log", with_ticks(spec, tz))
        _, s = replay(runner, bundle, fl, spec, work / "tz", ticks)
        n = diffcount(spec, tables(s, spec), base)
        return n == 0, f"differing rows {n}", None, n
    if name == "gold_equals_recompute":
        rev = {w: 0.0 for w in ("W1", "W2", "W3", "W4")}
        cnt = {}
        for k, w, s, net in base["silver_orders"]:
            if s == "DELIVERED":
                rev[w] = rev.get(w, 0.0) + net
            b = spec["status_buckets"].get(s, "other")
            cnt[(w, b)] = cnt.get((w, b), 0) + 1
        n = diffcount(spec, {"gold_warehouse_revenue": [(w, round(x, 2)) for w, x in rev.items()],
                             "gold_status_counts": [(w, b, n) for (w, b), n in cnt.items()]}, base,
                      only=["gold_warehouse_revenue", "gold_status_counts"])
        return n == 0, f"differing rows {n}", None, n
    if name == "lateness_conformance":
        # boundary-value probes derived from the declared rule: synthetic telemetry just before / after the watermark of the
        # last visible tick, with short and long ingest delays (so the rule, not a correlate of it, is what is tested)
        L = timedelta(hours=spec["lateness"]["allowed_hours"])
        tel = [(r, tick_of(r["ingest_ts"], spec)) for tp, p, r in recs if tp == "telemetry" and "_undecodable" not in r
               and isinstance(r.get("event_ts"), str)]
        last = ticks[-1]
        prior = [utc(r["event_ts"]) for r, k in tel if k < last]
        probes = []
        if prior:
            wm = max(prior) - L
            t_start = utc(spec["ticks"]["t0"]) + timedelta(hours=spec["ticks"]["tick_hours"] * (last - 1))
            for i, (dt, delay_h) in enumerate([(-1, 0.2), (+1, 0.2), (-1, L.total_seconds() / 3600 + 30), (+1, L.total_seconds() / 3600 + 30)]):
                et = wm + timedelta(minutes=30 * dt)
                ing = max(et + timedelta(hours=delay_h), t_start + timedelta(minutes=10 + i))
                probes.append(dict(msg_id=f"probe-late-{i}", ingest_ts=ing.strftime("%Y-%m-%dT%H:%M:%SZ"), order_id=-1, type="PICKED",
                                   event_ts=et.strftime("%Y-%m-%dT%H:%M:%SZ"), schema_version=1))
        fl = rewrite(full_log, work / "late_log", with_ticks(spec, lambda tp, p, rs: rs + ([dict(x, _tick=last) for x in probes]
                                                                                            if (tp, p) == ("telemetry", 0) else [])))
        _, s = replay(runner, bundle, fl, spec, work / "late", ticks)
        aug = records(grow(fl, work / "late_vis", ticks[-1], spec, keep=10**6))
        want = derive_late(spec, aug)
        got = {r[0] for r in (tables(s, spec).get("late_events") or [])}
        return want == got, f"late: expected {len(want)} got {len(got)} (sym diff {len(want ^ got)}; {len(probes)} probes)", None, len(want ^ got)
    if name == "silver_rederivation":
        want = derive_silver(spec, recs)
        got = {r[0]: r for r in base["silver_orders"]}
        extra, missing = set(got) - set(want), set(want) - set(got)
        wrong = [k for k in set(got) & set(want) if got[k][2] != want[k][2] or abs(got[k][3] - want[k][3]) > 0.011]
        imp = []
        if any(want[k][5] >= 2 and got[k][3] == 0 for k in wrong) or any(want[k][6] != int(want[k][6]) for k in wrong):
            imp.append("schema_handling")
        if any(want[k][7] != "USD" for k in wrong) and "schema_handling" not in imp:
            imp.append("fx")
        if extra:
            imp += ["deletes", "backfill_merge"]
        if any(got[k][2] != want[k][2] for k in wrong) or missing:
            imp += ["apply_order", "backfill_merge"]
        imp += [x for x in IMPLICATE["silver_rederivation"] if x not in imp]
        sev = len(extra) + len(missing) + len(wrong)
        return sev == 0, f"extra {len(extra)} missing {len(missing)} wrong {len(wrong)}", imp, sev
    if name == "rollback_drill":
        cfg = json.loads((Path(bundle) / "config.json").read_text())
        bad = dict(cfg, fx={k: v * 10 for k, v in cfg["fx"].items()})
        badf = work / "bad.json"
        badf.write_text(json.dumps(bad))
        runs, s = replay(runner, bundle, full_log, spec, work / "rb", ticks[:6])
        for t in (7,):
            runner.run(bundle, grow(full_log, work / "rb_lg", t, spec), s, tick=t, cfg=badf)
        runner.run(bundle, None, s, rollback=6, mode="crash", k=2)
        for t in (7, 8):
            r = runner.run(bundle, grow(full_log, work / "rb_lg", t, spec), s, tick=t)
        n = diffcount(spec, tables(s, spec), base) + (r["exit"] != 0)
        return n == 0, f"differing rows {n}", None, n
    raise KeyError(name)


def _render(dt, off_min):
    d = dt.astimezone(timezone(timedelta(minutes=off_min))).replace(microsecond=0)
    if off_min == 0:
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")
    m = abs(off_min)
    return d.strftime("%Y-%m-%dT%H:%M:%S") + ("+" if off_min > 0 else "-") + f"{m // 60:02d}:{m % 60:02d}"
