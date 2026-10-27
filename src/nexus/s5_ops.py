"""Stage 5 operations (NOT LOCKED; semantic harness).

OpsEnv (evaluator side) runs the handed-over production pipeline (the s4 template's correct-shape build, identical for
every operator arm) tick by tick with hidden-cause incidents (s5_incidents). An operator sees only:
  logs(t)       stderr / stdout of every run of tick t, harness messages (OOM kills), deployment event notes
  metrics()     per-partition lag, last exit code, records per run, state size, monitor readings it deployed
  lineage()     which output tables derive from which topics
  snapshots()   available end-of-tick snapshots (paths, read-only inspection)
and may act only through the authorised API: run_now (catch-up runs within the per-tick quota), set_deploy (keys and
ranges below), rotate_credentials, request_resnapshot, rollback(k), shadow(fn) (an isolated clone to test a repair).
Deployment authority: max_records_per_run in [50, 300]; future_guard on/off; dead_letter entries; unit_overrides entries;
monitoring rules; no code changes, no access to the evaluator, truth or incident ids.

Operators:
  RestartOnly            rerun a failed job (descriptive ablation)
  ConventionalOps        restart + runbooks keyed on explicit error text (read-only sink -> rotate credentials; source
                         permission denied -> wait; OOM -> halve the batch size); no data invariants
  NexusOps               deploys data monitors + a drift detector; on any symptom, investigates (logs, metrics, lineage,
                         state, snapshots, record metadata), instantiates AUTHORED repair primitives with parameters inferred
                         by AUTHORED diagnosis functions, and SEARCHES compositions (subsets, canonical order) with shadow
                         tests; applies the first composition whose shadow run restores service and every monitor;
                         reconciles by rollback + replay; writes a durable incident ledger
Drift detectors (hypothesis under test): MergeExactBOCPD (the N1-merge-exact method: constant-hazard BOCPD with exact merging
of runs whose posteriors are identical, here with a Dirichlet-multinomial model of binned log-weights), FixedRatio (rolling
median ratio threshold), Disabled."""
from __future__ import annotations

import itertools
import json
import math
import os
import random
import resource
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
from pathlib import Path

from nexus import s4_env as E
from nexus import s5_incidents as I

AUTH = {"max_records_per_run": (50, 300)}


def _cpu():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


# ------------------------------------------------------------------------------------------------ drift detectors
class MergeExactBOCPD:
    """Bayesian online change-point detection (Adams & MacKay) on y = log(weight) with a Normal unknown-mean model
    (variance plugged in from a warm-up window), constant hazard H. Runs whose sufficient statistics (n, sum y) are identical
    are merged exactly - the N1-merge-exact reduction (their future predictions are identical). Alarm when the posterior mass
    of run lengths < `short` exceeds `p`. A model-family change from N1 (which tracked a 4-goal posterior): the METHOD is
    reused, the likelihood is new."""
    name = "bocpd_merge_exact"

    def __init__(self, H=1 / 20, s0=1.0, short=6, p=0.5, warm=6):          # calibrated on src+dev (s5_calibrate_detectors)
        self.H, self.s0, self.short, self.p, self.warm = H, s0, short, p, warm
        self.ys, self.runs, self.n = [], None, 0

    def _pred(self, n, S, y):
        v0, s2 = self.s0 ** 2, self.var
        vn = 1.0 / (1.0 / v0 + n / s2)
        mn = vn * (self.mu0 / v0 + S / s2)
        var = vn + s2
        return math.exp(-(y - mn) ** 2 / (2 * var)) / math.sqrt(2 * math.pi * var)

    def update(self, x):
        y = math.log(max(x, 1e-6))
        self.n += 1
        if self.runs is None:
            self.ys.append(y)
            if len(self.ys) >= self.warm:
                m = sum(self.ys) / len(self.ys)
                self.mu0 = m
                self.var = max(0.02, sum((v - m) ** 2 for v in self.ys) / (len(self.ys) - 1))
                self.runs = {(len(self.ys), round(sum(self.ys), 12)): [1.0, len(self.ys)]}
            return False
        new, total = {}, 0.0
        for (n, S), (mass, rl) in self.runs.items():
            g = mass * self._pred(n, S, y) * (1 - self.H)
            k = (n + 1, round(S + y, 12))
            if k in new:
                new[k][0] += g; new[k][1] = min(new[k][1], rl + 1)
            else:
                new[k] = [g, rl + 1]
            total += mass
        cp = self.H * total * self._pred(0, 0.0, y)
        k = (1, round(y, 12))
        if k in new:
            new[k][0] += cp; new[k][1] = 1
        else:
            new[k] = [cp, 1]
        z = sum(v[0] for v in new.values())
        self.runs = {k: [v[0] / z, v[1]] for k, v in new.items() if v[0] / z > 1e-12}
        return sum(v[0] for v in self.runs.values() if v[1] < self.short) > self.p


class FixedRatio:
    """Alarm when the median of the last w values differs from the median of the previous 3w by a factor > k."""
    name = "fixed_ratio"

    def __init__(self, w=4, k=1.4):                                           # calibrated on src+dev
        self.w, self.k, self.xs = w, k, []

    def update(self, x):
        self.xs.append(x)
        if len(self.xs) < 4 * self.w:
            return False
        a = sorted(self.xs[-self.w:])[self.w // 2]
        b = sorted(self.xs[-4 * self.w:-self.w])[(3 * self.w) // 2]
        return b > 0 and (a / b > self.k or b / a > self.k)


class Disabled:
    name = "disabled"

    def update(self, x):
        return False


DETECTORS = {"bocpd_merge_exact": MergeExactBOCPD, "fixed_ratio": FixedRatio, "disabled": Disabled}


# ------------------------------------------------------------------------------------------------ the environment
class OpsEnv:
    def __init__(self, enc, incs, work, bundle, profile=None):
        self.enc, self.incs, self.work = enc, incs, Path(work)
        self.bundle, self.profile = Path(bundle), profile
        self.root = self.work / "env"
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "state").mkdir(exist_ok=True)
        self.cfg_path = self.root / "deploy.json"
        self.cfg = json.loads((self.bundle / "config.json").read_text())
        self.secret = self.root / "secrets" / "sink_token"
        self.secret.parent.mkdir(exist_ok=True)
        self.secret.write_text("tok-" + "".join(random.Random(str(work)).choice("abcdef0123456789") for _ in range(24)))
        self.cfg["deploy"]["credential_file"] = str(self.secret)
        self._save()
        self.rt = dict(state=str(self.root / "state"), log=str(self.root / "log"))
        self.t, self.logs, self.runs_this_tick, self.history = 0, {}, 0, []
        self.extra_offsets = {}
        self.actions, self.cpu_child = [], 0.0

    def _save(self):
        self.cfg_path.write_text(json.dumps(self.cfg, sort_keys=True))

    def clone(self, dst):
        """An isolated copy for shadow tests (permissions preserved)."""
        dst = Path(dst)
        if dst.exists():
            _rm(dst)
        _copytree(self.root, dst / "env")
        c = OpsEnv.__new__(OpsEnv)
        c.__dict__.update({k: v for k, v in self.__dict__.items()})
        c.work, c.root = dst, dst / "env"
        c.cfg = json.loads(json.dumps(self.cfg))
        c.cfg_path, c.secret = c.root / "deploy.json", c.root / "secrets" / "sink_token"
        c.rt = dict(self.rt, state=str(c.root / "state"), log=str(c.root / "log"))
        c.logs, c.history, c.actions = {k: list(v) for k, v in self.logs.items()}, list(self.history), []
        c.extra_offsets = dict(self.extra_offsets)
        c.cpu_child = 0.0
        c._save()
        return c

    # --- scheduler
    def advance(self):
        self.t += 1
        t = self.t
        I.write_tick(self.enc, self.root, t, self.incs)
        _retention(self.root, t)
        for inc in self.incs:
            inc.on_tick_start(t, self.rt)
        self.runs_this_tick = 0
        self.logs[t] = list(self.rt.pop("events", []) if "events" in self.rt else [])
        return self.run_now()

    def run_now(self):
        if self.runs_this_tick >= I.RUNS_PER_TICK:
            self.logs[self.t].append("scheduler: run quota for this tick exhausted")
            return dict(exit="QUOTA")
        self.runs_this_tick += 1
        st = Path(self.rt["state"])
        pre = self.work / "_prerun"
        if pre.exists():
            _rm(pre)
        _copytree(st, pre)
        before = _offsets(st)
        args = [sys.executable, "-B", str(self.bundle / "pipeline.py"), "--log", self.rt["log"], "--state", str(st),
                "--config", str(self.cfg_path), "--tick", str(self.t)]
        if self.profile and Path("/usr/bin/sandbox-exec").exists():
            args = ["/usr/bin/sandbox-exec", "-p", self.profile] + args
        r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        p = subprocess.run(args, capture_output=True, text=True, cwd=str(self.root),
                           env={"PATH": "/usr/bin:/bin", "HOME": "/var/empty", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"})
        r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.cpu_child += (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
        after = _offsets(st)
        consumed = sum(after.get(k, 0) - before.get(k, 0) for k in after)
        msg = (p.stderr or "")[-700:]
        code = p.returncode
        if code == 0 and consumed > I.QUOTA:
            _rm(st); _copytree(pre, st)            # OOM kill: the pod dies, uncommitted work is lost (simulated)
            code, msg = 137, f"Killed: pod exceeded its memory quota (records_in_run={consumed} > {I.QUOTA})"
        rec = dict(tick=self.t, exit=code, consumed=consumed if code == 0 else 0, err=msg.replace(self.secret.read_text(), "***"))
        self.history.append(rec)
        self.logs[self.t].append(json.dumps(rec))
        return rec

    # --- authorised actions
    def ask(self, topic, value):
        """Simulated stakeholder (counted as human dependence). Answers business facts only, never incident ids or fixes."""
        self.clarifications = getattr(self, "clarifications", []) + [f"{topic}:{value}"]
        if topic == "supplier_unit":
            inc = next((i for i in self.incs if i.name == "unit_shift" and i.supplier == value), None)
            return "lb" if inc else "kg"
        return "NOT_A_QUESTION"

    def set_deploy(self, key, value):
        if key in AUTH:
            lo, hi = AUTH[key]
            if value is not None and not lo <= value <= hi:
                raise PermissionError(f"{key}={value} outside authority {AUTH[key]}")
        elif key not in ("future_guard", "dead_letter", "unit_overrides"):
            raise PermissionError(f"{key} not within deployment authority")
        self.cfg["deploy"][key] = value
        self._save()
        self.actions.append(("set_deploy", key, value))

    def rotate_credentials(self):
        for inc in self.incs:
            if inc.name == "credential_expiry":
                inc.rotate(self.rt)
        self.rt["rotated_at"] = self.t
        self.secret.write_text("tok-" + "".join(random.Random(f"rot{self.t}").choice("abcdef0123456789") for _ in range(24)))
        db = Path(self.rt["state"]) / "lake.db"
        if db.exists():
            os.chmod(db, 0o644)
        self.actions.append(("rotate_credentials",))

    def request_resnapshot(self, topic="backfill_orders"):
        inc = next((i for i in self.incs if i.name == "snapshot_interrupted"), None)
        self.actions.append(("request_resnapshot", topic))
        if inc is None or getattr(self, "_resnap_done", False):
            self.logs[self.t].append("source: snapshot requested; no snapshot outstanding")
            return
        recs = inc.resnapshot(self.enc, self.t)
        d = Path(self.rt["log"]) / topic / "p0"
        start = max([json.loads(l)["offset"] for f in d.glob("*.jsonl") for l in f.read_text().splitlines() if l.strip()] + [-1]) + 1 \
            if os.access(d, os.R_OK) else 10**5
        I.append_records(self.root, topic, 0, recs, start)
        self._resnap_done = True

    def rollback(self, k):
        args = [sys.executable, "-B", str(self.bundle / "pipeline.py"), "--state", self.rt["state"], "--config", str(self.cfg_path),
                "--rollback-to", str(k)]
        p = subprocess.run(args, capture_output=True, text=True, cwd=str(self.root))
        self.actions.append(("rollback", k))
        return p.returncode

    # --- observation
    def metrics(self):
        st = Path(self.rt["state"])
        off = _offsets(st)
        ends = {}
        for d in Path(self.rt["log"]).glob("*/p*"):
            if not os.access(d, os.R_OK):
                continue
            for f in d.glob("*.jsonl"):
                n = sum(1 for l in f.read_text().split("\n") if l.strip())
                ends[(d.parent.name, int(d.name[1:]))] = max(ends.get((d.parent.name, int(d.name[1:])), 0), int(f.stem) + n)
        lag = {f"{k[0]}/{k[1]}": e - off.get(k, 0) for k, e in ends.items() if e - off.get(k, 0) > 0}
        last = self.history[-1] if self.history else {}
        return dict(tick=self.t, lag=lag, last_exit=last.get("exit"), last_consumed=last.get("consumed"),
                    state_bytes=sum(f.stat().st_size for f in st.rglob("*") if f.is_file()))

    def lineage(self):
        return {"silver_orders": ["orders_cdc", "backfill_orders", "_schemas"], "gold_warehouse_revenue": ["silver_orders"],
                "gold_status_counts": ["silver_orders"], "gold_sla": ["silver_orders", "telemetry"],
                "late_events": ["telemetry"], "gold_supplier_volume": ["silver_orders", "manifests"],
                "quarantine": ["telemetry", "manifests", "orders_cdc"], "record_accounting": ["*"]}

    def snapshots(self):
        d = Path(self.rt["state"]) / "snapshots"
        return sorted(int(p.name) for p in d.iterdir() if p.name.isdigit()) if d.exists() else []


def _offsets(st):
    st = Path(st)
    if (st / "lake.db").exists():
        try:
            con = sqlite3.connect(f"file:{st / 'lake.db'}?mode=ro", uri=True)
            rows = con.execute("SELECT topic, part, next FROM _offsets").fetchall()
            con.close()
            if rows:
                return {(t, p): n for t, p, n in rows}
        except sqlite3.Error:
            pass
    f = st / "offsets.json"
    return {(t, p): n for t, p, n in json.loads(f.read_text())["off"]} if f.exists() else {}


def _retention(root, t, keep=6):
    for f in Path(root, "log").rglob("*.jsonl"):
        if not os.access(f.parent, os.W_OK | os.X_OK):
            continue
        try:
            first = json.loads(f.read_text().split("\n", 1)[0])
        except ValueError:
            continue
        if E.tick_of(E.datetime.fromisoformat(first["ingest_ts"].replace("Z", "+00:00"))) <= t - keep:
            f.unlink()


def _copytree(a, b):
    """Copy preserving modes; temporarily open unreadable directories."""
    locked = [d for d in Path(a).rglob("*") if d.is_dir() and not os.access(d, os.R_OK | os.X_OK)]
    for d in locked:
        os.chmod(d, 0o755)
    try:
        shutil.copytree(a, b, copy_function=shutil.copy2)
    finally:
        for d in locked:
            os.chmod(d, 0)
            os.chmod(Path(b) / d.relative_to(a), 0)


def _rm(p):
    for d in Path(p).rglob("*"):
        try:
            os.chmod(d, 0o755 if d.is_dir() else 0o644)
        except OSError:
            pass
    shutil.rmtree(p, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ NEXUS monitors
def monitors(env, detector=None, det_state=None):
    """Data monitors NEXUS deploys. Returns {name: (ok, evidence)}."""
    st = Path(env.rt["state"])
    out = {}
    m = env.metrics()
    out["service"] = (m["last_exit"] == 0 and not m["lag"], dict(exit=m["last_exit"], lag=m["lag"]))
    db = st / "lake.db"
    if not db.exists():
        return out
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        applied = con.execute("SELECT COUNT(*) FROM _consumed WHERE status='applied' AND topic IN ('orders_cdc','backfill_orders') "
                              "AND msg_id NOT LIKE 'snap-%'").fetchone()[0]
        bronze = con.execute("SELECT COUNT(*) FROM bronze_orders").fetchone()[0]
        out["integrity"] = (applied == bronze, dict(consumed_applied=applied, bronze=bronze))
        sil = con.execute("SELECT warehouse_id, status, net_usd FROM silver_orders").fetchall()
        rev = {}
        for w, s, n in sil:
            if s == "DELIVERED":
                rev[w] = rev.get(w, 0.0) + n
        gold = dict(con.execute("SELECT warehouse_id, revenue_usd FROM gold_warehouse_revenue"))
        out["gold_recompute"] = (all(abs(gold.get(w, 0) - round(rev.get(w, 0.0), 2)) < 0.011 for w in set(gold) | set(rev)), {})
        mx_e = con.execute("SELECT MAX(ets) FROM bronze_tel WHERE future = 0").fetchone()[0]
        mx_i = con.execute("SELECT MAX(ingest) FROM bronze_tel").fetchone()[0]
        out["watermark_sanity"] = (mx_e is None or mx_e <= (E.datetime.fromisoformat(mx_i.replace("Z", "+00:00")) +
                                   E.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S"), dict(max_event=mx_e, max_ingest=mx_i))
        ctl = [json.loads(b) for (b,) in con.execute("SELECT body FROM snapshot_ctl")]
        aborted = {c["snapshot_id"] for c in ctl if c["control"] == "snapshot_aborted"}
        done = {c["snapshot_id"] for c in ctl if c["control"] == "snapshot_end"}
        out["snapshot_complete"] = (not aborted or bool(done - aborted), dict(aborted=sorted(aborted), complete=sorted(done)))
        acc = dict(((t, s), n) for t, s, n in con.execute("SELECT topic, status, n FROM record_accounting"))
        out["accounting"] = (not any(s == "dropped" for _, s in acc), {})
        con.close()
    except sqlite3.Error as e:
        out["integrity"] = (False, dict(error=str(e)))
    out["config_state_consistency"] = consistency(env)
    if detector is not None and det_state is not None:
        drift_scan(env, detector, det_state)
        handled = {o["supplier"] for o in env.cfg["deploy"].get("unit_overrides", [])}
        open_ = [a for a in det_state.get("alarms", []) if a["supplier"] not in handled]
        out["drift"] = (not open_, dict(alarms=open_))
    return out


def consistency(env):
    """Materialised state must equal the CURRENT deployment applied to the retained raw records (ingest-time transforms:
    unit overrides, the future-event guard). Returns (ok, evidence with the earliest inconsistent tick)."""
    st = Path(env.rt["state"]) / "lake.db"
    if not st.exists():
        return (True, {})
    dep = env.cfg["deploy"]
    con = sqlite3.connect(f"file:{st}?mode=ro", uri=True)
    try:
        man = dict(con.execute("SELECT msg_id, kg FROM bronze_man").fetchall())
        fut = dict(con.execute("SELECT msg_id, future FROM bronze_tel").fetchall())
    except sqlite3.Error:
        con.close()
        return (True, {})
    con.close()
    bad = []
    for topic in ("manifests", "telemetry"):
        for d in Path(env.rt["log"]).glob(f"{topic}/p*"):
            if not os.access(d, os.R_OK):
                continue
            part = int(d.name[1:])
            for f in d.glob("*.jsonl"):
                for l in f.read_text().splitlines():
                    try:
                        x = json.loads(l)
                    except ValueError:
                        continue
                    tk = E.tick_of(E.datetime.fromisoformat(x["ingest_ts"].replace("Z", "+00:00")))
                    if topic == "manifests" and x["msg_id"] in man and isinstance(x.get("weight"), (int, float)):
                        kg = x["weight"]
                        for ov in dep.get("unit_overrides", []):
                            if ov["supplier"] == x["supplier"] and x["offset"] >= ov["from_offset"] and part == ov.get("part", 0):
                                kg *= ov["factor"]
                        if abs(kg - man[x["msg_id"]]) > 1e-6:
                            bad.append(tk)
                    if topic == "telemetry" and x["msg_id"] in fut and dep.get("future_guard"):
                        ev = x["event_ts"]
                        et = E.datetime.fromtimestamp(ev / 1000, E.timezone.utc) if isinstance(ev, (int, float)) else \
                            E.datetime.fromisoformat(ev.replace("Z", "+00:00"))
                        want = int((et - E.datetime.fromisoformat(x["ingest_ts"].replace("Z", "+00:00"))).total_seconds() > 300)
                        if want != fut[x["msg_id"]]:
                            bad.append(tk)
    return (not bad, dict(inconsistent_records=len(bad), earliest_tick=min(bad) if bad else None))


def drift_scan(env, detector, det_state):
    """Feed new manifest weights (per supplier, in offset order) to the deployed detector; returns open alarms."""
    d = Path(env.rt["log"]) / "manifests" / "p0"
    seen = det_state.setdefault("seen", set())
    dets = det_state.setdefault("dets", {})
    alarms = det_state.setdefault("alarms", [])
    if not os.access(d, os.R_OK):
        return alarms
    recs = []
    for f in sorted(d.glob("*.jsonl")):
        for l in f.read_text().splitlines():
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if x["offset"] not in seen and isinstance(x.get("weight"), (int, float)):
                recs.append(x)
    t0 = _cpu()
    ver = det_state.setdefault("versions", {})
    for x in sorted(recs, key=lambda x: x["offset"]):
        seen.add(x["offset"])
        s = x["supplier"]
        pv = x.get("producer_version")
        if s in ver and ver[s] != pv and not any(a["supplier"] == s for a in alarms):
            alarms.append(dict(supplier=s, offset=x["offset"], tick=env.t, trigger="producer_metadata"))
        ver[s] = pv
        det = dets.setdefault(s, DETECTORS[detector]())
        if det.update(x["weight"]) and not any(a["supplier"] == s for a in alarms):
            alarms.append(dict(supplier=s, offset=x["offset"], tick=env.t, trigger=detector))
    det_state["cpu_s"] = det_state.get("cpu_s", 0.0) + _cpu() - t0
    return alarms


# ------------------------------------------------------------------------------------------------ diagnosis (authored)
def diagnose(env, mons, det_state):
    """Symptoms -> candidate repair primitives with inferred parameters (authored diagnosis functions)."""
    cands, sig = [], []
    errs = [json.loads(x) for t in sorted(env.logs)[-2:] for x in env.logs[t] if x.startswith("{")]
    last = errs[-1] if errs else {}
    txt = last.get("err", "") if last.get("exit") not in (0, None) else ""
    if "decode error" in txt and "offset=" in txt:
        import re
        m = re.search(r"topic=(\w+) part=(\d+) offset=(\d+)", txt)
        if m:
            sig.append("crash:decode")
            cands.append(("dead_letter", (m.group(1), int(m.group(2)), int(m.group(3)))))
    if "readonly" in txt or "read-only" in txt:
        sig.append("crash:readonly"); cands.append(("rotate_credentials", None))
    if "Permission denied" in txt or "PermissionError" in txt:
        sig.append("crash:permission"); cands.append(("wait", None))
    if "memory quota" in txt:
        sig.append("oom"); cands += [("batch", 240), ("batch", 150)]
    if txt and not sig:
        sig.append("crash:other")
    for name, (ok, ev) in mons.items():
        if ok or name == "service":
            continue
        sig.append(f"monitor:{name}")
        if name == "snapshot_complete":
            cands.append(("resnapshot", "backfill_orders"))
        elif name == "watermark_sanity":
            cands.append(("future_guard", True))
            k = _first_future_tick(env)
            cands += [("rollback", s) for s in env.snapshots() if s < (k or 99)][-1:]
        elif name == "integrity":
            good = _intact_snapshots(env)
            cands += [("rollback", s) for s in good[-2:]]
        elif name == "drift":
            for a in ev["alarms"]:
                loc = a.get("localized") or _localize_unit_shift(env, a["supplier"])
                if loc:
                    cands.append(("unit_override", loc))
                    tk = loc["tick"]
                    cands += [("rollback", s) for s in env.snapshots() if s < tk][-1:]
        elif name == "gold_recompute":
            cands += [("rollback", s) for s in env.snapshots()[-1:]]
        elif name == "config_state_consistency":
            k = ev.get("earliest_tick") or 99
            cands += [("rollback", s) for s in env.snapshots() if s < k][-1:]
    if "monitor:drift" in sig and not any(c[0] == "unit_override" for c in cands):
        sig.append("drift:unexplained")
    cands.append(("catch_up", None))
    out, seen = [], set()
    for c in cands:
        k = json.dumps(c, sort_keys=True, default=str)
        if k not in seen:
            seen.add(k); out.append(c)
    return sorted(set(sig)), out


def _first_future_tick(env):
    db = Path(env.rt["state"]) / "lake.db"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute("SELECT tick, ets, ingest FROM bronze_tel").fetchall()
    con.close()
    bad = [t for t, e, i in rows if e and i and e > (E.datetime.fromisoformat(i.replace("Z", "+00:00")) +
                                                     E.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")]
    return min(bad) if bad else None


def _intact_snapshots(env):
    good = []
    for s in env.snapshots():
        db = Path(env.rt["state"]) / "snapshots" / f"{s:04d}" / "lake.db"
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            a = con.execute("SELECT COUNT(*) FROM _consumed WHERE status='applied' AND topic IN ('orders_cdc','backfill_orders') "
                            "AND msg_id NOT LIKE 'snap-%'").fetchone()[0]
            b = con.execute("SELECT COUNT(*) FROM bronze_orders").fetchone()[0]
            con.close()
            if a == b:
                good.append(s)
        except sqlite3.Error:
            pass
    return good


def _metadata_changed(env, supplier):
    vs = []
    for f in sorted((Path(env.rt["log"]) / "manifests" / "p0").glob("*.jsonl")):
        for l in f.read_text().splitlines():
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if x["supplier"] == supplier:
                vs.append((x["offset"], x.get("producer_version")))
    vs.sort()
    return any(a[1] != b[1] for a, b in zip(vs, vs[1:]))


def _localize_by_metadata(env, supplier, unit):
    recs = []
    for f in sorted((Path(env.rt["log"]) / "manifests" / "p0").glob("*.jsonl")):
        for l in f.read_text().splitlines():
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if x["supplier"] == supplier:
                recs.append(x)
    recs.sort(key=lambda x: x["offset"])
    ch = next((i for i in range(1, len(recs)) if recs[i].get("producer_version") != recs[i - 1].get("producer_version")), None)
    if ch is None:
        return None
    return dict(supplier=supplier, part=0, from_offset=recs[ch]["offset"], factor=E.UNITS_TO_KG[unit], unit=unit,
                tick=E.tick_of(E.datetime.fromisoformat(recs[ch]["ingest_ts"].replace("Z", "+00:00"))), source="stakeholder")


def _count_after(env, supplier, offset):
    n = 0
    for f in (Path(env.rt["log"]) / "manifests" / "p0").glob("*.jsonl"):
        for l in f.read_text().splitlines():
            try:
                x = json.loads(l)
            except ValueError:
                continue
            n += x["supplier"] == supplier and x["offset"] > offset
    return n


def _localize_unit_shift(env, supplier):
    """Investigate record metadata: the offset where the supplier's producer_version changed, and the ratio of median weights
    after / before, matched to a unit in the spec's unit table (within 5%)."""
    d = Path(env.rt["log"]) / "manifests" / "p0"
    recs = []
    for f in sorted(d.glob("*.jsonl")):
        for l in f.read_text().splitlines():
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if x["supplier"] == supplier and isinstance(x.get("weight"), (int, float)):
                recs.append(x)
    recs.sort(key=lambda x: x["offset"])
    ch = next((i for i in range(1, len(recs)) if recs[i].get("producer_version") != recs[i - 1].get("producer_version")), None)
    if ch is None or ch < 3 or len(recs) - ch < 2:
        return None
    med = lambda xs: sorted(xs)[len(xs) // 2]
    ratio = med([x["weight"] for x in recs[ch:]]) / med([x["weight"] for x in recs[:ch]])
    units = E.UNITS_TO_KG
    best = min(units, key=lambda u: abs(math.log(ratio) - math.log(1 / units[u])))
    if abs(math.log(ratio) - math.log(1 / units[best])) > 0.35 or best == "kg":
        return None
    return dict(supplier=supplier, part=0, from_offset=recs[ch]["offset"], factor=units[best], unit=best,
                tick=E.tick_of(E.datetime.fromisoformat(recs[ch]["ingest_ts"].replace("Z", "+00:00"))))


# ------------------------------------------------------------------------------------------------ repair application
ORDER = {"rotate_credentials": 0, "wait": 0, "future_guard": 1, "dead_letter": 1, "unit_override": 1, "batch": 1,
         "resnapshot": 2, "rollback": 3, "catch_up": 4}


def apply_composition(env, comp):
    """Apply primitives in canonical order; ends with catch-up runs. Returns the final run record."""
    for name, arg in sorted(comp, key=lambda c: ORDER[c[0]]):
        if name == "rotate_credentials":
            env.rotate_credentials()
        elif name == "future_guard":
            env.set_deploy("future_guard", True)
        elif name == "dead_letter":
            env.set_deploy("dead_letter", list(env.cfg["deploy"].get("dead_letter", [])) + [list(arg)])
        elif name == "unit_override":
            env.set_deploy("unit_overrides", list(env.cfg["deploy"].get("unit_overrides", [])) +
                           [{k: arg[k] for k in ("supplier", "part", "from_offset", "factor")}])
        elif name == "batch":
            env.set_deploy("max_records_per_run", arg)
        elif name == "resnapshot":
            env.request_resnapshot(arg)
        elif name == "rollback":
            env.rollback(arg)
    last = None
    for _ in range(I.RUNS_PER_TICK):
        if env.runs_this_tick >= I.RUNS_PER_TICK:
            break
        last = env.run_now()
        if last["exit"] != 0 or not env.metrics()["lag"]:
            break
    return last


class Operator:
    kind = "base"

    def __init__(self, name, detector=None, library=None, seed=0):
        self.name, self.detector, self.library, self.seed = name, detector, library, seed
        self.ledger, self.det_state = [], {}
        self.cost = dict(shadow_tests=0, shadow_cpu_s=0.0, agent_cpu_s=0.0, actions=0, library_retrieval_cpu_s=0.0,
                         library_applicability_cpu_s=0.0, failed_reuse=0, escalations=0)

    def turn(self, env):
        pass


class RestartOnly(Operator):
    def turn(self, env):
        for _ in range(2):
            m = env.metrics()
            if m["last_exit"] in (0, None) and not m["lag"]:
                return
            r = env.run_now()
            if r.get("exit") == "QUOTA":
                return


class ConventionalOps(Operator):
    def turn(self, env):
        for _ in range(I.RUNS_PER_TICK):
            m = env.metrics()
            if m["last_exit"] in (0, None) and not m["lag"]:
                return
            txt = env.history[-1].get("err", "") if env.history else ""
            if "readonly" in txt:
                env.rotate_credentials(); self.cost["actions"] += 1
            elif "memory quota" in txt:
                env.set_deploy("max_records_per_run", 150); self.cost["actions"] += 1
            elif "Permission denied" in txt or "PermissionError" in txt:
                return                                     # source unavailable: wait for the next tick
            r = env.run_now()
            if r.get("exit") == "QUOTA":
                return


class NexusOps(Operator):
    MAX_SHADOW = 40

    def turn(self, env):
        c0 = _cpu()
        try:
            self._turn(env)
        finally:
            self.cost["agent_cpu_s"] += _cpu() - c0

    def _triage_alarms(self, env):
        """An alarm is a hypothesis, not a diagnosis: localise it (producer metadata change + unit-ratio match); dismiss it as
        a false alarm once >= 3 later records show no explainable change; keep it pending otherwise."""
        keep = []
        fixed = {o["supplier"] for o in env.cfg["deploy"].get("unit_overrides", [])}
        for a in self.det_state.get("alarms", []):
            if a["supplier"] in fixed:
                self.det_state.setdefault("resolved", []).append(a)
                continue
            loc = a.get("localized") or _localize_unit_shift(env, a["supplier"])
            if loc:
                keep.append(dict(a, localized=loc))
                continue
            if a.get("trigger") == "producer_metadata" and a["tick"] < env.t and not a.get("asked"):
                unit = env.ask("supplier_unit", a["supplier"])          # too little data to infer the unit: ask
                a["asked"] = unit
                if unit in E.UNITS_TO_KG and unit != "kg":
                    loc = _localize_by_metadata(env, a["supplier"], unit)
                    if loc:
                        keep.append(dict(a, localized=loc))
                        continue
                if unit == "kg":
                    self.det_state.setdefault("dismissed", []).append(a)
                    self.ledger.append(dict(tick=env.t, kind="metadata_change_no_unit_change", alarm=a))
                    continue
            later = _count_after(env, a["supplier"], a["offset"])
            if later >= 3 and not _metadata_changed(env, a["supplier"]):
                self.det_state.setdefault("dismissed", []).append(a)
                self.ledger.append(dict(tick=env.t, kind="false_alarm", alarm=a))
            else:
                keep.append(a)
        self.det_state["alarms"] = [a for a in keep if a.get("localized")] + [a for a in keep if not a.get("localized")]
        pend = [a for a in keep if not a.get("localized")]
        return pend

    def _turn(self, env):
        for attempt in range(3):
            mons = monitors(env, self.detector, self.det_state)
            pend = self._triage_alarms(env) if self.detector else []
            if "drift" in mons:
                open_ = [a for a in self.det_state.get("alarms", []) if a.get("localized") and
                         a["supplier"] not in {o["supplier"] for o in env.cfg["deploy"].get("unit_overrides", [])}]
                mons["drift"] = (not open_, dict(alarms=open_, pending=pend))
            bad = {k: v for k, v in mons.items() if not v[0]}
            if not bad:
                return
            sig, cands = diagnose(env, mons, self.det_state)

            if sig == ["crash:permission"]:
                self.ledger.append(dict(tick=env.t, kind="source_unavailable", action="wait", evidence=bad.get("service", [0, {}])[1]))
                return
            comps = self._compositions(sig, cands, env)
            chosen, tried = None, 0
            for comp in comps:
                tried += 1
                if self.cost["shadow_tests"] >= self.MAX_SHADOW:
                    break
                ok = self._shadow(env, comp)
                if ok:
                    chosen, self._last_ok = comp, ok
                    break
                if self.library is not None and comp is comps[0] and self._from_library:
                    self.cost["failed_reuse"] += 1
            if chosen is None:
                chosen = self._deepen(env, sig, comps[:6])
                if chosen:
                    self._last_ok = True
            if chosen is None:
                self.cost["escalations"] += 1
                self.ledger.append(dict(tick=env.t, kind="escalated", signature=sig, candidates=[c[0] for c in cands]))
                return
            apply_composition(env, chosen)
            self.cost["actions"] += len(chosen)
            self.ledger.append(dict(tick=env.t, kind="repaired" if self._last_ok is True else "partial_repair_waiting_for_source",
                                    signature=sig, repair=[[c[0], c[1]] for c in chosen],
                                    verified_in_shadow=True, shadow_tests_before=tried, from_library=self._from_library and tried == 1))
            if self.library is not None:
                self.library.observe(sig, chosen)
            if self._last_ok == "partial":
                return

    def _compositions(self, sig, cands, env):
        prim = [c for c in cands if c[0] != "catch_up"]
        comps = [()] + [tuple(c) for k in (1, 2, 3) for c in itertools.combinations(prim, k)]
        comps = [tuple(c) + (("catch_up", None),) for c in comps]
        random.Random(f"de2-ops-order:{self.seed}:{env.t}:{'|'.join(sig)}").shuffle(comps)
        self._from_library = False
        if self.library is not None:
            a = _cpu()
            pref = self.library.playbook(sig)
            self.cost["library_retrieval_cpu_s"] += _cpu() - a
            a = _cpu()
            if pref:
                kinds = sorted(pref)
                match = [c for c in comps if sorted(x[0] for x in c if x[0] != "catch_up") == kinds]
                if match:
                    comps = match + [c for c in comps if c not in match]
                    self._from_library = True
            self.cost["library_applicability_cpu_s"] += _cpu() - a
        return comps

    def _deepen(self, env, sig, firsts):
        """Round 2: apply a first composition in a shadow, re-diagnose the shadow's NEW symptoms, test extensions."""
        for first in firsts:
            if self.cost["shadow_tests"] >= self.MAX_SHADOW:
                return None
            c = env.clone(env.work / "deep")
            c.runs_this_tick = 0
            apply_composition(c, first)
            m2 = monitors(c, None, None)
            sig2, cands2 = diagnose(c, m2, {})
            self.cost["shadow_tests"] += 1
            _rm(env.work / "deep")
            extra = [x for x in cands2 if x[0] != "catch_up" and x not in first]
            for k in (1, 2):
                for ext in itertools.combinations(extra, k):
                    comp = tuple(x for x in first if x[0] != "catch_up") + ext + (("catch_up", None),)
                    if self.cost["shadow_tests"] >= self.MAX_SHADOW:
                        return None
                    if self._shadow(env, comp):
                        return comp
        return None

    def _shadow(self, env, comp):
        a = _cpu()
        c = env.clone(env.work / "shadow")
        c.runs_this_tick = 0
        r = apply_composition(c, comp)
        mons = monitors(c, self.detector, json.loads(json.dumps({k: v for k, v in self.det_state.items() if k == "alarms"})))
        self.cost["shadow_tests"] += 1
        self.cost["shadow_cpu_s"] += _cpu() - a + c.cpu_child
        drift_ok = all(a["supplier"] in {o["supplier"] for o in c.cfg["deploy"].get("unit_overrides", [])}
                       for a in self.det_state.get("alarms", []) if a.get("localized"))
        ok = r is not None and r.get("exit") == 0 and all(v[0] for k, v in mons.items() if k != "drift") and drift_ok
        if not ok and r is not None and r.get("exit") not in (0, None, "QUOTA"):
            err = r.get("err", "")
            if ("Permission denied" in err or "PermissionError" in err) and drift_ok and \
                    all(v[0] for k, v in mons.items() if k not in ("drift", "service", "snapshot_complete")):
                ok = "partial"                          # original symptom gone; only an unavailable source remains
        _rm(env.work / "shadow")
        return ok


def run_ops(enc, incs, work, bundle, operator, profile=None, ticks=14):
    env = OpsEnv(enc, incs, work, bundle, profile)
    service = []
    for t in range(1, ticks + 1):
        env.advance()
        operator.turn(env)
        m = env.metrics()
        service.append(dict(tick=t, ok=m["last_exit"] == 0 and not m["lag"], lag=sum(m["lag"].values())))
    return env, service
