"""R1 checks (NOT LOCKED): the Stage 4 suite (s4_checks) run over an OBSERVATION-DRIVEN replay, plus the independent monitor,
one metamorphic transform and scoped evidence records. Re-exports the s4_checks API so the Stage 4 agent code can be bound
to it unchanged (r1_agent).

grow_obs              the consumer's view at tick k is materialised from the authoritative observation log/_obs/tick_k.json
                      (partition directories by lifecycle, segments by publication / expiry), never from data records
rewrite observations  a metamorphic rewrite keeps each partition's observed creation tick and journals the rewritten
                      segments (the rewrite harness is the environment of its own synthetic log)
replay_conformance    every replayed view of every check equals its observation (r1_monitor.check_view)
ack_durability        after every replayed run and every enumerated crash point, no acknowledgement beyond the contiguous
                      available or durably consumed offsets, no aborted / open transaction record applied
chunk_invariance      max_records_per_run = 37 with runs repeated until the committed offsets stop moving must give the same
                      tables. Preconditions: the spec defines the watermark per ingest tick (not per run); no transaction in
                      the visible data spans a chunk (visible data has no transactions); gold is defined on the committed
                      state, so chunk boundaries are not observable in the outputs
Evidence: one record per required property {property, checker, evidence_source, assumptions, bounds, cost, result}; results
PASS_WITHIN_SCOPE | FAIL | UNKNOWN | NOT_APPLICABLE, mapped to the outcome contract by outcome()."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from nexus import r1_env as RE
from nexus import r1_monitor as M
from nexus import s4_checks as C
from nexus.s4_checks import Runner, records, replay, tables, diffcount, derive_silver, derive_late, tick_of, utc  # noqa: F401

STANDARD = list(C.STANDARD)
S4_NEXUS = list(C.NEXUS)
R1_EXTRA = ["replay_conformance", "ack_durability", "chunk_invariance"]
NEXUS = S4_NEXUS[:4] + ["replay_conformance"] + S4_NEXUS[4:] + ["ack_durability", "chunk_invariance"]
IMPLICATE = dict(C.IMPLICATE, replay_conformance=[], ack_durability=["commit_protocol", "gap_handling", "txn_isolation"],
                 chunk_invariance=["gold_maintenance", "dedup", "lateness", "commit_protocol"])


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:12]


CHECKER = {"s4": f"s4_checks@{_sha(C.__file__)}", "monitor": f"r1_monitor@{_sha(M.__file__)}", "r1": f"r1_checks@{_sha(__file__)}"}


# ------------------------------------------------------------------------------------------------ observation-driven replay
def grow_obs(full, dst, upto, spec=None, keep=6):
    full, dst = Path(full), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    obs = json.loads((full / "_obs" / f"tick_{upto:04d}.json").read_text())
    for p in obs["partitions"]:
        if p["state"] == "open":
            (dst / p["topic"] / f"p{p['part']}").mkdir(parents=True, exist_ok=True)
    open_ = {(p["topic"], p["part"]) for p in obs["partitions"] if p["state"] == "open"}
    for s in obs["segments"]:
        if (s["topic"], s["part"]) not in open_:
            continue                                  # an unavailable partition cannot be read at this tick
        if s["available"] or (keep >= 10 ** 5 and s["pub"] <= upto):
            src = full / s["topic"] / f"p{s['part']}" / f"{s['base']:08d}.jsonl"
            (dst / s["topic"] / f"p{s['part']}").mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst / s["topic"] / f"p{s['part']}" / src.name)
    return dst


def rewrite_obs(src_log, dst_log, written):
    """Observations for a rewritten log: partition creation ticks carried from the source observation, rewritten segments
    journalled at their record tick, registry / transaction facts from the rewritten records."""
    src_log, dst_log = Path(src_log), Path(dst_log)
    last = max(int(f.stem[5:]) for f in (src_log / "_obs").glob("tick_*.json"))
    created = {(p["topic"], p["part"]): p["created"]
               for p in json.loads((src_log / "_obs" / f"tick_{last:04d}.json").read_text())["partitions"]}
    obs = RE.Obs(dst_log.parent / "_rw" / dst_log.name)          # build the journal next to, then move into, the log
    if obs.j.exists():
        obs.j.unlink()
    for d in sorted(dst_log.glob("*/p*")):
        k = (d.parent.name, int(d.name[1:]))
        obs.event(ev="partition_created", topic=k[0], part=k[1], tick=created.get(k, 1))
    mx = last
    for topic, part, base, end, tk in sorted(written, key=lambda w: (w[4], w[0], w[1], w[2])):
        mx = max(mx, tk)
        obs.event(ev="segment", topic=topic, part=part, base=base, end=end, rtick=tk, tick=tk, n=end - base)
        for l in (dst_log / topic / f"p{part}" / f"{base:08d}.jsonl").read_text().splitlines():
            x = json.loads(l)
            if topic == "_schemas":
                obs.event(ev="schema", subject=x.get("subject", "orders"), version=x["version"], offset=x["offset"], tick=tk)
            elif x.get("txn_id") and "control" not in x:
                obs.event(ev="txn_record", txn_id=x["txn_id"], topic=topic, part=part, offset=x["offset"], tick=tk)
            elif str(x.get("control", "")).startswith("txn_"):
                obs.event(ev="txn_marker", txn_id=x["txn_id"], topic=topic, part=part, kind=x["control"][4:],
                          offset=x["offset"], tick=tk)
    for k in range(1, mx + 1):
        obs.materialize(k)
    if (dst_log / "_obs").exists():
        shutil.rmtree(dst_log / "_obs")
    shutil.move(str(obs.d), str(dst_log / "_obs"))
    shutil.rmtree(dst_log.parent / "_rw" / dst_log.name, ignore_errors=True)


class Conformance:
    def __init__(self):
        self.viol, self.views, self.states, self.crashes = [], 0, 0, 0
        self.txns, self.holes = 0, 0

    def replay_hook(self, full_log, view, st, t, r):
        obs = M.load_obs(full_log, t)
        self.viol += [dict(v, phase="view") for v in M.check_view(view, obs)]
        self.views += 1
        if r["exit"] == 0:
            self.viol += [dict(v, phase="consumer") for v in M.check_consumer(st, obs)]
            self.states += 1
            self.txns = max(self.txns, len(obs.get("txns", {})))
            self.holes = max(self.holes, sum(o["contiguous_end"] < o["log_end"] for o in obs["offsets"].values()))

    def crash_hook(self, full_log, st, t):
        self.viol += [dict(v, phase="crash") for v in M.check_consumer(st, M.load_obs(full_log, t))]
        self.crashes += 1


def install(conf):
    C.GROW, C.REWRITE_OBS = grow_obs, rewrite_obs
    C.REPLAY_HOOK, C.CRASH_HOOK = conf.replay_hook, conf.crash_hook


def uninstall():
    C.GROW = C.REWRITE_OBS = C.REPLAY_HOOK = C.CRASH_HOOK = None


# ------------------------------------------------------------------------------------------------ R1 suite
LAST = {}


def verify(bundle, spec, full_log, work, runner, suite=None, ticks=range(1, 9), stop_at_first=True, order=None,
           monitor=True):
    """The Stage 4 checks over grow_obs (+ the monitor when `monitor`), then the R1 checks in `suite`."""
    suite = NEXUS if suite is None else suite
    work = Path(work)
    conf = Conformance()
    if monitor:
        install(conf)
    else:
        C.GROW, C.REWRITE_OBS = grow_obs, rewrite_obs
    try:
        s4 = [c for c in suite if c in C.IMPLICATE]
        res = C.verify(bundle, spec, full_log, work, runner, suite=s4, ticks=ticks, stop_at_first=stop_at_first,
                       order=[c for c in (order or suite) if c in s4] or None)
        cont = all(r["ok"] for r in res) or not stop_at_first
        if res and res[0]["check"] == "runs_all_ticks" and not res[0]["ok"]:
            cont = False
        for name in [c for c in suite if c in R1_EXTRA]:
            if not cont:
                break
            c0, n0 = runner.cpu_s, runner.runs
            ok, det, score = _r1_one(name, bundle, spec, full_log, work, runner, list(ticks), conf)
            res.append(dict(check=name, ok=ok, detail=det, implicate=IMPLICATE[name], score=0 if ok else score,
                            cpu_s=round(runner.cpu_s - c0, 4), runs=runner.runs - n0))
            cont = ok or not stop_at_first
    finally:
        uninstall()
    out = dict(results=res, conformance=dict(views=conf.views, states=conf.states, crash_points=conf.crashes,
                                             violations=conf.viol[:50], n_violations=len(conf.viol),
                                             txns_observed=conf.txns, holes_observed=conf.holes))
    if set(suite) == set(NEXUS) or set(suite) == set(STANDARD):
        LAST.clear()
        LAST.update(out, suite=list(suite))
    for r in res:
        r.setdefault("cpu_s", 0.0)
    return res


def _r1_one(name, bundle, spec, full_log, work, runner, ticks, conf):
    if name == "replay_conformance":
        v = [x for x in conf.viol if x["phase"] == "view"]
        return not v, f"{len(v)} view violations over {conf.views} replayed views {sorted({x['kind'] for x in v})}", len(v)
    if name == "ack_durability":
        v = [x for x in conf.viol if x["phase"] in ("consumer", "crash")]
        return not v, (f"{len(v)} consumer violations over {conf.states} states + {conf.crashes} crash points "
                       f"{sorted({x['kind'] for x in v})}"), len(v)
    if name == "chunk_invariance":
        base_runs, base = replay(runner, bundle, full_log, spec, work / "ck_base", ticks)
        cfg = json.loads((Path(bundle) / "config.json").read_text())
        cfg["deploy"] = dict(cfg["deploy"], max_records_per_run=37)
        cf = work / "chunk_cfg.json"
        cf.write_text(json.dumps(cfg))
        st = work / "ck" / "state"
        if st.parent.exists():
            shutil.rmtree(st.parent)
        st.mkdir(parents=True)
        bad = 0
        for t in ticks:
            lg = grow_obs(full_log, work / "ck" / "log", t)
            prev = None
            for _ in range(60):
                r = runner.run(bundle, lg, st, tick=t, cfg=cf)
                cur = M._committed(st)
                if r["exit"] != 0:
                    bad += 1
                    break
                if cur == prev:
                    break
                prev = cur
        n = diffcount(spec, tables(st, spec), tables(base, spec)) + bad
        return n == 0, f"differing rows {n} (chunk 37 records, runs repeated until offsets stop)", n
    raise KeyError(name)


# ------------------------------------------------------------------------------------------------ scoped evidence
PROPS = [
    # property, evidence checks, assumptions, bounds
    ("runs", ["runs_all_ticks"], "sandboxed subprocess per tick", "visible ticks 1-8"),
    ("output_keys", ["schema_keys_not_null", "nonempty_outputs"], "declared primary keys", "state after tick 8"),
    ("idempotent_rerun", ["rerun_unchanged"], "same log, same tick", "one rerun of tick 8"),
    ("replay_conformance", ["replay_conformance"], "observations are authoritative", "every replayed view of every check"),
    ("input_coverage", ["accounting_and_lag", "ack_durability"], "observed offsets are the input universe",
     "visible ticks; committed offsets after each replayed run"),
    ("output_reconciliation", ["silver_rederivation", "gold_equals_recompute", "lateness_conformance"],
     "spec re-derivation by NEXUS code (not the pipeline's)", "visible records; 4 lateness boundary probes"),
    ("exactly_once", ["crash_sweep", "ack_durability"], "os._exit before each commit / os.replace, nested + SIGKILL",
     "ticks 4 and 7, enumerated crash points only"),
    ("dedup", ["duplicate_delivery_invariance"], "every record redelivered once", "visible ticks"),
    ("cdc_order", ["arrival_permutation_invariance"], "same-key permutation respecting registry causality", "visible ticks"),
    ("backfill_precedence", ["backfill_timing_invariance"], "snapshot moved to the first / last visible tick", "silver + gold"),
    ("tz_invariance", ["utc_offset_invariance"], "telemetry re-rendered in 6 offsets", "visible telemetry"),
    ("rollback", ["rollback_drill"], "fx x10 bad deploy, rollback crashed half way", "ticks 6-8"),
    ("chunk_invariance", ["chunk_invariance"], "watermark per ingest tick; no transaction spans a chunk", "chunk 37"),
    ("txn_isolation", [], "observed transactions only", "transactions observed in the visible log"),
    ("gap_safety", [], "observed offset holes only", "holes observed in the visible log"),
]


def evidence(res, conformance, suite):
    by = {r["check"]: r for r in res}
    out = []
    for prop, checks, assum, bounds in PROPS:
        rel = [by[c] for c in checks if c in by]
        cost = dict(cpu_s=round(sum(r.get("cpu_s", 0.0) for r in rel), 3), runs=sum(r.get("runs", 0) for r in rel))
        src = "visible log ticks 1-8 (+ probes / transforms named in bounds)"
        if prop == "txn_isolation":
            n = conformance.get("txns_observed", 0)
            fail = any(v["kind"] == "txn_effect_violation" for v in conformance.get("violations", []))
            result = "FAIL" if fail else "PASS_WITHIN_SCOPE" if n and "ack_durability" in by else "UNKNOWN"
            bounds_ = f"{n} transactions observed"
        elif prop == "gap_safety":
            n = conformance.get("holes_observed", 0)
            fail = any(v["kind"] == "ack_beyond_available" for v in conformance.get("violations", []))
            result = "FAIL" if fail else "PASS_WITHIN_SCOPE" if n and "ack_durability" in by else "UNKNOWN"
            bounds_ = f"{n} offset holes observed"
        else:
            missing = [c for c in checks if c not in by]
            bounds_ = bounds
            if any(not r["ok"] for r in rel):
                result = "FAIL"
            elif missing or not rel:
                result = "UNKNOWN"
            else:
                result = "PASS_WITHIN_SCOPE"
        checker = CHECKER["monitor"] if prop in ("replay_conformance", "txn_isolation", "gap_safety") else \
            CHECKER["r1"] if prop == "chunk_invariance" else CHECKER["s4"]
        out.append(dict(property=prop, checker=checker, evidence_source=src, assumptions=assum, bounds=bounds_, cost=cost,
                        result=result, checks=checks))
    return out


def outcome(ev):
    """Evidence -> outcome_contract project label."""
    res = {e["result"] for e in ev}
    if "FAIL" in res:
        return "ABSTAIN_UNSUPPORTED"
    if "UNKNOWN" in res:
        return "COMPLETED_UNVERIFIED"
    return "COMPLETED_VERIFIED"
