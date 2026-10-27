"""NEXUS data-engineering invariants (Stage 3, NOT LOCKED). Standalone: standard library only, imports nothing from NEXUS
or the evaluator, so it is copied verbatim into every deliverable bundle as tests/invariants.py.

Every check uses only what an engineer has: the docs (spec.json) and the visible landing batches. None of them knows the
answer tables. Three kinds:
  metamorphic   semantics-preserving rewrites of the inputs must not change the outputs (seq relabelling, timestamps
                re-rendered in other UTC offsets, all batches merged into one vs incremental, amounts re-expressed in USD,
                weights re-expressed in another unit, every file delivered twice)
  operational   rerun of the last batch and crash-then-restart leave exactly the state of a clean run
  conformance   spec rules checked against the raw sources: schema and primary keys, quarantine conservation (every raw
                manifest line is valid or quarantined with the right reason), deletions, measure conservation across joins
                (fan-out: shipments split into twins), the lateness rule (late events removed)
coverage() is the pre-build ambiguity detector: categorical values observed in the data that a rule does not cover.
Each failing check names the generator decisions it implicates (so a repair loop knows what to change)."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import resource
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

NUM = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([A-Za-z.]*)\s*$")
TOL = {"amount_usd": 0.011, "net_revenue_usd": 0.011, "weight_kg": 0.0021, "on_time_rate": 0.00011}


# ------------------------------------------------------------------------------------------------ running pipelines
CRASH = r'''
import os, runpy, sys
LAND, K = os.path.realpath(sys.argv[1]), int(sys.argv[2])
n = [0]
def hook(ev, args):
    if ev in ("open", "sqlite3.connect") and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.fsdecode(args[0])
        p = os.path.realpath(p[5:].split("?", 1)[0] if p.startswith("file:") else p)
        if p.startswith(LAND + os.sep):
            n[0] += 1
            if n[0] > K:
                os._exit(137)
sys.addaudithook(hook)
sys.argv = sys.argv[3:]
runpy.run_path(sys.argv[0], run_name="__main__")
'''


class Runner:
    """Runs a bundle's pipeline in a subprocess (macOS sandbox when available: no network, no writes outside the work dir's
    parent tree being allowed is not enforced here beyond the OS profile). Meters child CPU seconds and wall time."""

    def __init__(self, sandbox_profile=None):
        self.profile = sandbox_profile
        self.runs, self.cpu_s, self.wall_s = 0, 0.0, 0.0

    def run(self, bundle, landing, state, crash_after=None, timeout=120):
        args = [str(Path(bundle) / "pipeline.py"), "--landing", str(landing), "--state", str(state), "--config",
                str(Path(bundle) / "config.json")]
        if crash_after is not None:
            w = Path(state).parent / "_nexus_crash.py"
            w.write_text(CRASH)
            args = [str(w), str(landing), str(crash_after)] + args
        cmd = [sys.executable, "-B", *args]
        if self.profile and Path("/usr/bin/sandbox-exec").exists():
            cmd = ["/usr/bin/sandbox-exec", "-p", self.profile] + cmd
        env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/var/empty", "PYTHONHASHSEED": "0"}
        r0, t0 = resource.getrusage(resource.RUSAGE_CHILDREN), time.perf_counter()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(Path(state).parent), timeout=timeout)
            code, err = p.returncode, p.stderr
        except subprocess.TimeoutExpired:
            code, err = "TIMEOUT", ""
        r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
        wall = time.perf_counter() - t0
        self.runs += 1; self.cpu_s += cpu; self.wall_s += wall
        stage = re.findall(r"StageError: stage=(\w+)", err or "")
        return dict(exit=code, stage=stage[-1] if stage else None, err=(err or "")[-600:], cpu_s=cpu, wall_s=wall)

    def run_seq(self, bundle, landings, work, crash_last=False):
        """Fresh state; run each landing in order (landing dir replaced each time: retention). Returns (runs, state_dir)."""
        work = Path(work)
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        st, land, out = work / "state", work / "landing", []
        st.mkdir()
        for i, src in enumerate(landings):
            if land.exists():
                shutil.rmtree(land)
            shutil.copytree(src, land)
            if crash_last and i == len(landings) - 1:
                n = sum(1 for f in land.rglob("*") if f.is_file())
                out.append(self.run(bundle, land, st, crash_after=max(1, n // 2)))
            r = self.run(bundle, land, st)
            out.append(r)
            if r["exit"] != 0:
                break
        return out, st


def tables(state, spec, internal=False):
    db = Path(state) / "lake.db"
    out = {}
    if not db.exists():
        return out
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in names:
            if t in spec["outputs"]:
                cols = spec["outputs"][t]["columns"]
                have = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
                if all(c in have for c in cols):
                    out[t] = [tuple(r) for r in con.execute(f'SELECT {",".join(chr(34) + c + chr(34) for c in cols)} FROM "{t}"')]
                else:
                    out[t] = "SCHEMA"
            elif internal:
                out[t] = [tuple(r) for r in con.execute(f'SELECT * FROM "{t}"')]
    finally:
        con.close()
    return out


def same(spec, a, b, only=None, ignore=()):
    """Compare output tables (multisets keyed by PK, numeric tolerance). Returns list of differing table names."""
    bad = []
    for t in (only or spec["outputs"]):
        if t in ignore:
            continue
        x, y = a.get(t), b.get(t)
        if not isinstance(x, list) or not isinstance(y, list):
            if x != y:
                bad.append(t)
            continue
        cols, pk = spec["outputs"][t]["columns"], spec["outputs"][t]["pk"]
        idx = [cols.index(c) for c in pk]
        key = lambda r: tuple(str(r[i]) for i in idx)
        dx, dy = {}, {}
        for r in x:
            dx.setdefault(key(r), []).append(r)
        for r in y:
            dy.setdefault(key(r), []).append(r)
        ok = set(dx) == set(dy)
        for k in dx if ok else ():
            if len(dx[k]) != len(dy[k]):
                ok = False; break
            for r, s in zip(sorted(dx[k], key=str), sorted(dy[k], key=str)):
                for c, u, v in zip(cols, r, s):
                    if c in TOL and isinstance(u, (int, float)) and isinstance(v, (int, float)):
                        ok = ok and abs(u - v) <= TOL[c]
                    else:
                        ok = ok and str(u) == str(v)
        if not ok:
            bad.append(t)
    return bad


def digest(tabs):
    return hashlib.sha256(json.dumps({t: sorted(map(str, v)) if isinstance(v, list) else v for t, v in sorted(tabs.items())},
                                     sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------------------------------------ raw-source readers
def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def render(dt, off_min):
    d = dt.astimezone(timezone(timedelta(minutes=off_min))).replace(microsecond=0)
    if off_min == 0:
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")
    sign = "+" if off_min > 0 else "-"
    m = abs(off_min)
    return d.strftime("%Y-%m-%dT%H:%M:%S") + f"{sign}{m // 60:02d}:{m % 60:02d}"


def jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def manifest_lines(batch, spec):
    """(record_ref, raw line, parsed fields dict) for every data line of every manifest file in a landing dir."""
    mc = spec["dictionary"]["manifest"]["columns"]
    out = []
    for f in sorted(Path(batch).glob("drops/*.csv")):
        lines = f.read_text().split("\n")
        header = next(csv.reader([lines[0]]))
        i_s = next((header.index(a) for a in mc["shipment_id"] if a in header), None)
        i_w = next((header.index(a) for a in mc["weight"] if a in header), None)
        i_u = next((header.index(a) for a in mc["unit"] if a in header), None)
        for line in lines[1:]:
            if line:
                fld = next(csv.reader([line]))
                out.append((hashlib.sha1(line.encode()).hexdigest()[:12], line, dict(
                    sid=fld[i_s].strip() if i_s is not None else "", w=fld[i_w].strip() if i_w is not None else "",
                    u=fld[i_u].strip() if i_u is not None else None, header=header, i_w=i_w, i_u=i_u, file=f.name)))
    return out


def classify(fields, spec):
    """Spec quarantine rules (in order) -> reason or None (valid; orphan status needs the snapshot)."""
    if not fields["sid"]:
        return "missing_key"
    if fields["u"] is None:
        m = NUM.match(fields["w"])
        num, unit = (m.group(1), m.group(2)) if m else (None, None)
    else:
        num, unit = (fields["w"] if re.match(r"^\s*[0-9]*\.?[0-9]+\s*$", fields["w"]) else None), fields["u"]
    if num is None:
        return "unparseable_weight"
    if unit not in spec["units"]["to_kg"]:
        return "unknown_unit"
    return None


# ------------------------------------------------------------------------------------------------ input rewrites
def _copy(src, dst):
    if Path(dst).exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return Path(dst)


def rw_seq(src, dst, spec):
    d = _copy(src, dst)
    for f in d.glob("cdc/*.jsonl"):
        f.write_text("".join(json.dumps(dict(e, seq=10**7 - e["seq"]), sort_keys=True) + "\n" for e in jsonl(f)))
    return d


def rw_tz(src, dst, spec, seed=0):
    rng = random.Random(seed)
    offs = [-480, -300, 0, 120, 330, 540, 780]
    d = _copy(src, dst)
    oc, ec = spec["dictionary"]["orders"]["columns"], spec["dictionary"]["events"]["columns"]
    for f in d.glob("cdc/*.jsonl"):
        out = []
        for e in jsonl(f):
            e["event_ts"] = render(utc(e["event_ts"]), rng.choice(offs))
            for side in ("before", "after"):
                if e.get(side) and e[side].get(oc["promised_ts"]):
                    e[side][oc["promised_ts"]] = render(utc(e[side][oc["promised_ts"]]), rng.choice(offs))
            out.append(json.dumps(e, sort_keys=True) + "\n")
        f.write_text("".join(out))
    for f in d.glob("events/*.jsonl"):
        out = []
        for e in jsonl(f):
            for c in (ec["event_ts"], ec["ingest_ts"]):
                e[c] = render(utc(e[c]), rng.choice(offs))
            out.append(json.dumps(e, sort_keys=True) + "\n")
        f.write_text("".join(out))
    return d


def rw_fx(src, dst, spec):
    d = _copy(src, dst)
    oc, fx = spec["dictionary"]["orders"]["columns"], spec["currency"]["fx_to_usd"]
    for f in d.glob("cdc/*.jsonl"):
        out = []
        for e in jsonl(f):
            for side in ("before", "after"):
                r = e.get(side)
                if r and r.get(oc["currency"]) in fx:
                    r[oc["amount"]] = round(float(r[oc["amount"]]) * fx[r[oc["currency"]]], 2)
                    r[oc["currency"]] = "USD"
            out.append(json.dumps(e, sort_keys=True) + "\n")
        f.write_text("".join(out))
    return d


def rw_unit(src, dst, spec):
    """Re-express every valid weight in the smallest-factor unit of the docs' table (e.g. kg -> g), same encoding."""
    d = _copy(src, dst)
    units = spec["units"]["to_kg"]
    target = min(units, key=lambda u: units[u])
    for f in d.glob("drops/*.csv"):
        lines = f.read_text().split("\n")
        out = [lines[0]]
        rows = [x for x in manifest_lines(d, spec) if x[2]["file"] == f.name]
        for (ref, line, fl) in rows:
            if classify(fl, spec) is None:
                fld = next(csv.reader([line]))
                if fl["u"] is None:
                    m = NUM.match(fl["w"])
                    kg = float(m.group(1)) * units[m.group(2)]
                    fld[fl["i_w"]] = repr(kg / units[target]) + target
                else:
                    kg = float(fl["w"]) * units[fl["u"]]
                    fld[fl["i_w"]], fld[fl["i_u"]] = repr(kg / units[target]), target
                lb = __import__("io").StringIO()
                csv.writer(lb, lineterminator="").writerow(fld)
                line = lb.getvalue()
            out.append(line)
        f.write_text("\n".join(out) + "\n")
    return d


def rw_dup(src, dst, spec):
    d = _copy(src, dst)
    for f in list(d.rglob("*")):
        if f.is_file() and f.suffix in (".jsonl", ".csv"):
            shutil.copy(f, f.with_name(f.stem + "_dup" + f.suffix))
    return d


def rw_split(src, dst, spec):
    """Every shipment gets a twin of the same order (and every DELIVERED event a twin on that twin): an order's revenue
    must not change, because revenue counts orders, not shipments."""
    d = _copy(src, dst)
    s, ec = spec["dictionary"]["shipments"], spec["dictionary"]["events"]["columns"]
    con = sqlite3.connect(d / "source.db")
    c = s["columns"]
    rows = con.execute(f'SELECT "{c["shipment_id"]}", "{c["order_id"]}", "{c["carrier"]}", "{c["shipped_ts"]}" FROM "{s["table"]}"').fetchall()
    con.executemany(f'INSERT INTO "{s["table"]}" ("{c["shipment_id"]}", "{c["order_id"]}", "{c["carrier"]}", "{c["shipped_ts"]}") '
                    "VALUES (?,?,?,?)", [(r[0] + "X", r[1], r[2], r[3]) for r in rows])
    con.commit(); con.close()
    for f in d.glob("events/*.jsonl"):
        out = []
        for e in jsonl(f):
            out.append(json.dumps(e, sort_keys=True) + "\n")
            if e[ec["event_type"]] == "DELIVERED":
                out.append(json.dumps(dict(e, **{ec["event_id"]: e[ec["event_id"]] + "X",
                                                 ec["shipment_id"]: e[ec["shipment_id"]] + "X"}), sort_keys=True) + "\n")
        f.write_text("".join(out))
    return d


def rw_drop_late(src, dst, spec):
    """Remove every late telemetry event (spec lateness rule): the SLA, which must exclude them, cannot change."""
    d = _copy(src, dst)
    ec, L = spec["dictionary"]["events"]["columns"], timedelta(hours=spec["lateness_hours"])
    for f in d.glob("events/*.jsonl"):
        f.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in jsonl(f)
                             if utc(e[ec["ingest_ts"]]) - utc(e[ec["event_ts"]]) <= L))
    return d


def rw_merge(batches, dst):
    d = Path(dst)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for i, b in enumerate(batches):
        for f in Path(b).rglob("*"):
            if f.is_file() and f.name != "source.db":
                rel = f.relative_to(b)
                t = d / rel.parent / f"m{i}_{rel.name}"
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, t)
    shutil.copy(Path(batches[-1]) / "source.db", d / "source.db")
    return d


# ------------------------------------------------------------------------------------------------ ambiguity coverage
def coverage(spec, batches):
    """Questions the spec leaves open for the observed data: (topic, value) pairs."""
    oc = spec["dictionary"]["orders"]["columns"]
    statuses, by_key = set(), {}
    for b in batches:
        for f in sorted(Path(b).glob("cdc/*.jsonl")):
            for e in jsonl(f):
                a = e.get("after")
                if a:
                    statuses.add(a[oc["status"]])
                    by_key.setdefault(str(a[oc["order_id"]]), set()).add(a[oc["status"]])
    shipped = set()
    for b in batches:
        con = sqlite3.connect(f"file:{Path(b) / 'source.db'}?mode=ro", uri=True)
        s = spec["dictionary"]["shipments"]
        shipped |= {str(r[0]) for r in con.execute(f'SELECT "{s["columns"]["order_id"]}" FROM "{s["table"]}"')}
        con.close()
    qs = [("status_bucket", x) for x in sorted(statuses - set(spec["status_buckets"]))]
    rule = spec["rules"]["gold_carrier_volume"]
    covered = set(rule["include_status"]) | set(rule["exclude_status"])
    with_ship = set().union(*(by_key.get(k, set()) for k in shipped)) if shipped else set()
    qs += [("carrier_volume", x) for x in sorted(with_ship - covered - (statuses - set(spec["status_buckets"])))]
    return qs


# ------------------------------------------------------------------------------------------------ the checks
def verify(bundle, spec, batches, work, runner, stop_at_first=True, base=None):
    """Run the invariant suite on a bundle against the visible batches. Returns list of dict(check, ok, detail, implicate).
    base = (runs, state_dir) of an already executed clean run over `batches` (reused instead of running it again)."""
    work = Path(work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    res = []

    def add(name, ok, detail="", implicate=()):
        res.append(dict(check=name, ok=bool(ok), detail=detail, implicate=list(implicate)))
        return ok or not stop_at_first

    base_runs, base_st = base if base is not None else runner.run_seq(bundle, batches, work / "base")
    if any(r["exit"] != 0 for r in base_runs):
        add("runs_without_error", False, base_runs[-1]["err"][-200:], [])
        return res
    base, base_int = tables(base_st, spec), tables(base_st, spec, internal=True)
    # schema and keys
    miss = [t for t in spec["outputs"] if not isinstance(base.get(t), list)]
    dups = []
    for t in spec["outputs"]:
        if isinstance(base.get(t), list):
            cols, pk = spec["outputs"][t]["columns"], spec["outputs"][t]["pk"]
            ks = [tuple(r[cols.index(c)] for c in pk) for r in base[t]]
            if len(ks) != len(set(ks)):
                dups.append(t)
    imp = []
    if dups:
        dim = any(t in dups for t in ("gold_warehouse_revenue", "gold_inventory"))
        imp = ["dims_load", "bronze_dedup"] if dim else ["bronze_dedup", "dims_load"]
    if not add("schema_and_primary_keys", not miss and not dups, f"missing {miss} duplicate keys {dups}", imp):
        return res
    # rerun of the last batch
    shutil.copytree(base_st, work / "rerun_state")
    land = work / "rerun_landing"
    _copy(batches[-1], land)
    r = runner.run(bundle, land, work / "rerun_state")
    after = tables(work / "rerun_state", spec, internal=True)
    changed = sorted(t for t in set(after) | set(base_int) if after.get(t) is not None and sorted(map(str, after.get(t, []))) != sorted(map(str, base_int.get(t, []))))
    dim_changed = any(t.startswith("dim_") for t in changed)
    if not add("idempotent_rerun", r["exit"] == 0 and not changed, f"tables changed {changed[:6]}",
               ["dims_load", "bronze_dedup"] if dim_changed else ["bronze_dedup", "dims_load"]):
        return res
    # duplicate delivery
    dupb = [rw_dup(b, work / f"dup_in{i}", spec) for i, b in enumerate(batches)]
    _, st = runner.run_seq(bundle, dupb, work / "dup")
    d = same(spec, tables(st, spec), base)
    if not add("duplicate_delivery_invariance", not d, f"differs {d}", ["bronze_dedup"]):
        return res
    # crash then restart
    runs, st = runner.run_seq(bundle, batches, work / "crash", crash_last=True)
    d = same(spec, tables(st, spec), base)
    if not add("crash_restart_equivalence", not d and runs[-1]["exit"] == 0, f"differs {d}", ["bronze_dedup", "dims_load"]):
        return res
    # seq relabelling (ties only matter within identical event times)
    _, st = runner.run_seq(bundle, [rw_seq(b, work / f"seq_in{i}", spec) for i, b in enumerate(batches)], work / "seq")
    d = same(spec, tables(st, spec), base)
    if not add("seq_relabel_invariance", not d, f"differs {d}", ["cdc_apply"]):
        return res
    # timestamp representation
    _, st = runner.run_seq(bundle, [rw_tz(b, work / f"tz_in{i}", spec, seed=i) for i, b in enumerate(batches)], work / "tz")
    d = same(spec, tables(st, spec), base)
    if not add("utc_offset_invariance", not d, f"differs {d}", ["ts_parse"]):
        return res
    # merged vs incremental
    _, st = runner.run_seq(bundle, [rw_merge(batches, work / "merged_in")], work / "merged")
    d = same(spec, tables(st, spec), base)
    if not add("incremental_equals_full_refresh", not d, f"differs {d}", ["cdc_incremental"]):
        return res
    # currency representation
    _, st = runner.run_seq(bundle, [rw_fx(b, work / f"fx_in{i}", spec) for i, b in enumerate(batches)], work / "fx")
    d = same(spec, tables(st, spec), base, only=["silver_orders", "gold_warehouse_revenue"])
    if not add("currency_representation_invariance", not d, f"differs {d}", ["fx"]):
        return res
    # unit representation
    _, st = runner.run_seq(bundle, [rw_unit(b, work / f"unit_in{i}", spec) for i, b in enumerate(batches)], work / "unit")
    d = same(spec, tables(st, spec), base, only=["gold_carrier_volume"])
    if not add("unit_representation_invariance", not d, f"differs {d}", ["units"]):
        return res
    # quarantine conservation against the raw lines
    raw = {}
    for b in batches:
        for ref, line, fl in manifest_lines(b, spec):
            raw[ref] = classify(fl, spec)
    silver = {r[0] for r in base["silver_manifest"]}
    quar = {r[1]: r[2] for r in base["quarantine"] if r[0] == "manifest"}
    lost = sorted(set(raw) - silver - set(quar))
    bad_valid = sorted(k for k in silver if raw.get(k))
    wrong_reason = sorted(k for k, why in quar.items() if raw.get(k) and raw[k] != why)
    imp = ["units"] if any(raw.get(k) == "unknown_unit" for k in bad_valid) else ["weight_parse"]
    if not add("quarantine_conservation", not lost and not bad_valid and not wrong_reason,
               f"lost {len(lost)} malformed-in-silver {len(bad_valid)} wrong-reason {len(wrong_reason)}", imp):
        return res
    # deletions: no soft-deleted payload is live; inventory equals the non-deleted snapshot aggregate
    dl, oc = spec["deletion"], spec["dictionary"]["orders"]["columns"]
    def dead(v):
        return (v is not None and str(v) in {str(x) for x in dl["deleted_values"]}) if dl["kind"] == "flag" else v not in (None, "")
    latest = {}
    for b in batches:
        for f in sorted(Path(b).glob("cdc/*.jsonl")):
            for e in jsonl(f):
                k = str(next(iter(e["key"].values())))
                cand = (utc(e["event_ts"]), e["seq"])
                if k not in latest or cand > latest[k][0]:
                    latest[k] = (cand, e)
    should_dead = {k for k, (_, e) in latest.items() if e["op"] == "d" or (e.get("after") and dead(e["after"].get(dl["column"])))}
    live = {str(r[0]) for r in base["silver_orders"]}
    inv_ok = True
    con = sqlite3.connect(f"file:{Path(batches[-1]) / 'source.db'}?mode=ro", uri=True)
    it = spec["dictionary"]["inventory"]
    cur = con.execute(f'SELECT * FROM "{it["table"]}"')
    names = [c[0] for c in cur.description]
    agg = {}
    for row in cur.fetchall():
        g = dict(zip(names, row))
        if not dead(g.get(dl["column"])):
            k = (g[it["columns"]["warehouse_id"]], g[it["columns"]["sku"]])
            agg[k] = agg.get(k, 0) + g[it["columns"]["qty"]]
    con.close()
    got = {(r[0], r[1]): r[2] for r in base["gold_inventory"]}
    inv_ok = got == agg
    if not add("deletion_contract", not (live & should_dead) and inv_ok,
               f"deleted-but-live {len(live & should_dead)} inventory_ok {inv_ok}", ["deletes"]):
        return res
    # fan-out: splitting shipments must not change revenue (measure conservation across the order -> shipment join)
    _, st = runner.run_seq(bundle, [rw_split(b, work / f"split_in{i}", spec) for i, b in enumerate(batches)], work / "split")
    d = same(spec, tables(st, spec), base, only=["gold_warehouse_revenue"])
    if not add("shipment_split_invariance", not d, f"differs {d}", ["revenue_join"]):
        return res
    # lateness rule: the late set matches the rule, and removing late events leaves the SLA unchanged
    ec, L = spec["dictionary"]["events"]["columns"], timedelta(hours=spec["lateness_hours"])
    evs = {}
    for b in batches:
        for f in sorted(Path(b).glob("events/*.jsonl")):
            for e in jsonl(f):
                evs[e[ec["event_id"]]] = e
    late = {k for k, e in evs.items() if utc(e[ec["ingest_ts"]]) - utc(e[ec["event_ts"]]) > L}
    ok_late = {r[0] for r in base["late_events"]} == late
    _, st = runner.run_seq(bundle, [rw_drop_late(b, work / f"late_in{i}", spec) for i, b in enumerate(batches)], work / "late")
    d = same(spec, tables(st, spec), base, only=["gold_sla"])
    if not add("late_event_removal_invariance", ok_late and not d, f"late set ok {ok_late}; differs {d}", ["sla_window"]):
        return res
    return res


CHECK_NAMES = ["runs_without_error", "schema_and_primary_keys", "idempotent_rerun", "duplicate_delivery_invariance",
               "crash_restart_equivalence", "seq_relabel_invariance", "utc_offset_invariance", "incremental_equals_full_refresh",
               "currency_representation_invariance", "unit_representation_invariance", "quarantine_conservation",
               "deletion_contract", "shipment_split_invariance", "late_event_removal_invariance"]


if __name__ == "__main__":       # standalone use inside a deliverable bundle: python invariants.py BUNDLE SPEC BATCH...
    b, sp, *bs = sys.argv[1:]
    out = verify(b, json.loads(Path(sp).read_text()), bs, Path(os.environ.get("TMPDIR", "/tmp")) / "nexus_invariants", Runner(),
                 stop_at_first=False)
    for x in out:
        print("PASS" if x["ok"] else "FAIL", x["check"], x["detail"])
    sys.exit(0 if all(x["ok"] for x in out) else 1)
