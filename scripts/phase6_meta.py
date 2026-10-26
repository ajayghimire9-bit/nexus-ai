"""Wave 26 Phase 6 driver: Experienced vs Fresh vs compute-matched Placebo over independent source-world orderings.

  --dev --seeds 741 ...       dev orderings, evaluated on held-out synthetic worlds
  --confirm                   one-use orderings 6001-6005, evaluated on Sealed Group B (3011-3020) + external ARC grid
                              (3021-3030) through the token-gated loader (checkpointed per ordering)
  --replay-of A --seeds ...   fresh-process replay of the listed orderings vs per-ordering digests in A
Phase 6 PASS (declared in docs/NEXUS_WAVE26_PHASE6.md before confirmation), orderings as the units (n = 5):
  Experienced evaluation cost < Fresh AND < Placebo in 5 / 5 orderings (one-sided sign test p = 1/32 < 0.05), AND
  Experienced learning slope < Fresh AND < Placebo in 5 / 5 orderings, AND 0 false certificates, AND identical replays.
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"
SPLITS = (("group_b", range(3011, 3021)), ("external_arc_1d_grid", range(3021, 3031)))


def ledger(run, wall, status, **kw):
    with LEDGER.open("a") as f:
        f.write(json.dumps(dict(run=run, wall_s=wall, status=status, **kw)) + "\n")


def odigest(o):
    from nexus.standing_gates import json_digest
    return json_digest({a: [(r["i"], r["route"], r["solved"], r["work"]) for r in v["rows"]] + [v["source"]["work"]]
                        for a, v in o["arms"].items()})


def factory(dev, seed):
    from nexus.wave26_phase6 import dev_stream_factory, sealed_stream_factory
    return dev_stream_factory(seed) if dev else sealed_stream_factory(SPLITS)


def score(outs):
    per = []
    for o in outs:
        A = o["arms"]
        per.append(dict(seed=o["seed"], cost={a: A[a]["eval_cost"] for a in A}, slope={a: A[a]["slope"] for a in A},
                        solved={a: A[a]["solved"] for a in A}, false={a: A[a]["false_certificates"] for a in A},
                        errors={a: A[a]["errors"] for a in A}, source_work={a: A[a]["source"]["work"] for a in A},
                        library={a: A[a]["source"].get("library", []) for a in A}))
    n = len(per)
    cost_wins = sum(p["cost"]["experienced"] < min(p["cost"]["fresh"], p["cost"]["placebo"]) for p in per)
    slope_wins = sum(p["slope"]["experienced"] < min(p["slope"]["fresh"], p["slope"]["placebo"]) for p in per)
    false = sum(sum(p["false"].values()) for p in per)
    return dict(orderings=per, cost_wins=cost_wins, slope_wins=slope_wins, n=n, false_certificates=false,
                gate=n >= 5 and cost_wins == n and slope_wins == n and false == 0)


def main():
    ap = argparse.ArgumentParser()
    for f in ("--dev", "--confirm", "--digest-only"):
        ap.add_argument(f, action="store_true")
    ap.add_argument("--replay-of")
    ap.add_argument("--seeds", type=int, nargs="*")
    ap.add_argument("--checkpoint")
    ap.add_argument("--out")
    ap.add_argument("--wall-cap", type=float, default=840.0)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus.wave26_phase6 import run_ordering
    if a.digest_only:
        fc = {}
        print(json.dumps({s: odigest(run_ordering(s, factory(a.dev, s), fresh_cache=fc)) for s in a.seeds}))
        return
    if a.replay_of:
        art = json.loads(Path(a.replay_of).read_text())
        t0 = time.perf_counter()
        try:
            env = dict(os.environ, PYTHONHASHSEED="271828")
            cmd = [sys.executable, __file__, "--digest-only", "--seeds", *map(str, a.seeds)] + (["--dev"] if art.get("dev") else [])
            got = json.loads(subprocess.run(cmd, env=env, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
        finally:
            ledger("wave26-phase6-replay", time.perf_counter() - t0, "COMPLETE", seeds=a.seeds)
        rp = art["report"].setdefault("G_replay_per_ordering", {})
        for s, d in got.items():
            rp[s] = dict(recorded=art["report"]["digests"][s], replayed=d, passed=art["report"]["digests"][s] == d)
        art["report"]["G_replay"] = len(rp) == len(art["report"]["digests"]) and all(v["passed"] for v in rp.values())
        Path(a.replay_of).write_text(json.dumps(art, default=repr, sort_keys=True))
        print(json.dumps(rp), art["report"]["G_replay"])
        return
    seeds = a.seeds or (list(range(741, 746)) if a.dev else list(range(6001, 6006)))
    ck = Path(a.checkpoint) if a.checkpoint else None
    if not ck:
        raise SystemExit("--checkpoint required")
    if a.dev:
        R.claim("phase6", "dev", seeds, run_id="phase6-dev", record=False)
    elif not ck.exists():
        if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
            raise SystemExit("confirmation needs the sealed harness token")
        from nexus.sealed_vault_loader import verify_vault
        verify_vault()
        R.claim("phase6", "orderings_confirm", range(6001, 6006), run_id="phase6-confirm")
        R.claim("phase3", "vault_group_b", range(3011, 3021), run_id="phase6-confirm")
        R.claim("phase3", "vault_external", range(3021, 3031), run_id="phase6-confirm")
    outs, done, fc = [], set(), {}
    if ck.exists():
        for l in ck.read_text().splitlines():
            o = json.loads(l); outs.append(o); done.add(o["seed"])
            fc.setdefault("fresh", o["arms"]["fresh"])
    t0, status = time.perf_counter(), "COMPLETE"
    try:
        for s in seeds:
            if s in done:
                continue
            if outs and time.perf_counter() - t0 > a.wall_cap * 0.5:
                status = "PARTIAL_WALL_CAP"
                break
            o = run_ordering(s, factory(a.dev, s), fresh_cache=fc)
            outs.append(o)
            with ck.open("a") as f:
                f.write(json.dumps(o, default=repr) + "\n")
            print(f"ordering {s} done", flush=True)
    finally:
        ledger("wave26-phase6-" + ("dev" if a.dev else "confirm"), time.perf_counter() - t0, status, seeds=seeds)
    rep = score(sorted(outs, key=lambda o: o["seed"]))
    rep["digests"] = {str(o["seed"]): odigest(o) for o in outs}
    rep["status"] = status if len(outs) == len(seeds) else "PARTIAL"
    Path(a.out).write_text(json.dumps(dict(schema="wave26_phase6", dev=a.dev, report=rep, seeds_raw=outs), default=repr,
                                      sort_keys=True))
    print(json.dumps({k: v for k, v in rep.items() if k != "orderings"}),
          json.dumps([{k: p[k] for k in ("seed", "cost", "slope", "solved", "false", "errors")} for p in rep["orderings"]]))


if __name__ == "__main__":
    main()
