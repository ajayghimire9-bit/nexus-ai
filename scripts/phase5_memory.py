"""Wave 26 Phase 5 driver: continual drifting stream (25 base worlds + 25 lagged revisits = 50 visits per stream).

  --dev --seeds ...      dev streams (731-735)
  --confirm              one-use streams 5001-5005 (checkpointed per stream; resumable across calls)
  --replay-of A --seeds  fresh-process replay of the listed streams, compared with the per-stream digests in A
Phase 5 PASS (declared in docs/NEXUS_WAVE26_PHASE5.md before confirmation):
  revisit cost ratio sum(visit 2) / sum(visit 1) < 1 for every lag k in {5, 10, 20} (pooled);
  backward interference (sum full-library visit-2 cost - sum snapshot cost) / sum snapshot <= 0.10;
  100% of opaque tools used in drift worlds retired (RETIRED_BY_DRIFT) and 0 false certificates;
  G_tycho; identical per-stream replay digests.
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"


def ledger(run, wall, status, **kw):
    with LEDGER.open("a") as f:
        f.write(json.dumps(dict(run=run, wall_s=wall, status=status, **kw)) + "\n")


def stream_digest(o):
    from nexus.standing_gates import json_digest
    return json_digest([(r["pos"], r["wid"], r["visit"], r["solved"], r["work"], r.get("snapshot_work")) for r in o["rows"]]
                       + [sorted(o["contracts"].items())])


def score(outs):
    rows = [r for o in outs for r in o["rows"]]
    rev = [r for r in rows if r["visit"] == 2]
    lag = {}
    for k in (5, 10, 20):
        rs = [r for r in rev if r["lag"] == k]
        v1, v2 = sum(r["first_visit_work"] for r in rs), sum(r["work"] for r in rs)
        lag[k] = dict(worlds=len(rs), visit1=v1, visit2=v2, ratio=v2 / v1 if v1 else None,
                      cheaper_worlds=sum(r["work"] < r["first_visit_work"] for r in rs))
    full, snap = sum(r["work"] for r in rev), sum(r["snapshot_work"] for r in rev)
    drift_tools, retired = 0, 0
    for o in outs:
        drift_w = set(o["drift_worlds"])
        used = {n for n in o["contracts"]}
        for n, st in o["contracts"].items():
            drift_tools += 0
        broken = [n for n, st in o["contracts"].items() if n in o.get("drift_tool_names", [])]
        drift_tools += len(broken)
        retired += sum(o["contracts"][n] == "RETIRED_BY_DRIFT" for n in broken)
    false = sum(r["false_certificates"] for r in rows)
    rep = dict(lags=lag, interference=(full - snap) / snap if snap else None, revisit_full=full, revisit_snapshot=snap,
               drift_broken_tools=drift_tools, retired=retired, false_certificates=false,
               solved=sum(r["solved"] for r in rows), tasks=sum(r["tasks"] for r in rows),
               library_final={o["seed"]: o["library"] for o in outs})
    rep["gate_revisit"] = all(v["ratio"] is not None and v["ratio"] < 1 for v in lag.values())
    rep["gate_interference"] = rep["interference"] is not None and rep["interference"] <= 0.10
    rep["gate_retirement"] = drift_tools > 0 and retired == drift_tools and false == 0
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--digest-only", action="store_true")
    ap.add_argument("--replay-of")
    ap.add_argument("--seeds", type=int, nargs="*")
    ap.add_argument("--checkpoint")
    ap.add_argument("--out")
    ap.add_argument("--wall-cap", type=float, default=840.0)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus.wave26_phase5 import run_stream
    if a.digest_only:
        print(json.dumps({s: stream_digest(run_stream(s)) for s in a.seeds}))
        return
    if a.replay_of:
        art = json.loads(Path(a.replay_of).read_text())
        t0 = time.perf_counter()
        try:
            env = dict(os.environ, PYTHONHASHSEED="271828")
            p = subprocess.run([sys.executable, __file__, "--digest-only", "--seeds", *map(str, a.seeds)], env=env,
                               capture_output=True, text=True, check=True)
            got = json.loads(p.stdout.strip().splitlines()[-1])
        finally:
            ledger("wave26-phase5-replay", time.perf_counter() - t0, "COMPLETE", seeds=a.seeds)
        rp = art["report"].setdefault("G_replay_per_stream", {})
        for s, d in got.items():
            rp[s] = dict(recorded=art["report"]["stream_digests"][s], replayed=d,
                         passed=art["report"]["stream_digests"][s] == d)
        art["report"]["G_replay"] = len(rp) == len(art["report"]["stream_digests"]) and all(v["passed"] for v in rp.values())
        Path(a.replay_of).write_text(json.dumps(art, default=repr, sort_keys=True))
        print(json.dumps(rp), art["report"]["G_replay"])
        return
    seeds = a.seeds or (list(range(731, 736)) if a.dev else list(range(5001, 5006)))
    if a.dev:
        R.claim("phase5", "dev", seeds, run_id="phase5-dev", record=False)
        if not a.checkpoint:
            raise SystemExit("dev runs must checkpoint too")
    else:
        if not a.checkpoint:
            raise SystemExit("confirmation requires --checkpoint")
        ck = Path(a.checkpoint)
        if not ck.exists():
            R.claim("phase5", "confirm", range(5001, 5006), run_id="phase5-confirm")
    t0, outs, done = time.perf_counter(), [], set()
    ck = Path(a.checkpoint) if a.checkpoint else None
    if ck and ck.exists():
        for l in ck.read_text().splitlines():
            o = json.loads(l); outs.append(o); done.add(o["seed"])
    status = "COMPLETE"
    try:
        for s in seeds:
            if s in done:
                continue
            if time.perf_counter() - t0 > a.wall_cap - 260:
                status = "PARTIAL_WALL_CAP"
                break
            o = run_stream(s)
            outs.append(o)
            if ck:
                with ck.open("a") as f:
                    f.write(json.dumps(o, default=repr) + "\n")
            print(f"stream {s} done", flush=True)
    finally:
        ledger("wave26-phase5-" + ("dev" if a.dev else "confirm"), time.perf_counter() - t0, status, seeds=seeds)
    from nexus.standing_gates import g_tycho
    rep = score(outs)
    rep["stream_digests"] = {str(o["seed"]): stream_digest(o) for o in outs}
    rep["G_tycho"] = g_tycho([dict(work=r["work"], work_by={"visit": r["work"]}) for o in outs for r in o["rows"]])
    rep["status"] = status if len(outs) == len(seeds) else "PARTIAL"
    Path(a.out).write_text(json.dumps(dict(schema="wave26_phase5", report=rep, seeds_raw=outs), default=repr, sort_keys=True))
    print(json.dumps({k: v for k, v in rep.items() if k not in ("library_final",)}, default=repr))


if __name__ == "__main__":
    main()
