"""Wave 26 Phase 2 driver: --dev (seeds 711-715) or --confirm (one-use 2001-2005), per-seed checkpoint, artifact
written before any replay, replay as a separate bounded call (--replay-of).

Phase 2 PASS (confirmation): calibrated soundness - in every noise-tolerant arm and every eps, false
certificates <= the 99% upper quantile of Binomial(#certificates, delta=0.01) - AND full_noisy fully loaded <
exact_eig_noisy with solved(full) >= solved(exact), AND G_tycho, AND identical fresh-process replay digest.
The naive exact-elimination control is reported (its failures under noise are the point of the rule).
"""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"


def digest(outs):
    from nexus.standing_gates import json_digest
    return json_digest([(o["seed"], r["episode"], r["arm"], r["eps"], r["status"], r["probes"], r["work"])
                        for o in outs for r in o["rows"]])


def run(seeds, n, checkpoint=None):
    from nexus.wave26_phase2 import run_seed
    outs, done = [], set()
    ck = Path(checkpoint) if checkpoint else None
    if ck and ck.exists():
        for l in ck.read_text().splitlines():
            o = json.loads(l)
            outs.append(o)
            done.add(o["seed"])
    for s in seeds:
        if s in done:
            continue
        o = run_seed(s, n)
        outs.append(o)
        if ck:
            with ck.open("a") as f:
                f.write(json.dumps(o, default=repr) + "\n")
        print(f"seed {s}: {o['n']} episodes", flush=True)
    return sorted(outs, key=lambda o: o["seed"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--digest-only", action="store_true")
    ap.add_argument("--replay-of")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--checkpoint")
    ap.add_argument("--out")
    a = ap.parse_args()
    from nexus import seed_registry as R
    seeds = list(range(711, 716)) if a.dev else list(range(2001, 2006))
    if a.digest_only:
        print(digest(run(seeds, a.n)))
        return
    if a.replay_of:
        from nexus.standing_gates import g_replay
        art = json.loads(Path(a.replay_of).read_text())
        t0 = time.perf_counter()
        try:
            art["report"]["G_replay"] = g_replay(__file__, ["--confirm", "--n", str(a.n)], art["report"]["digest"])
        finally:
            with LEDGER.open("a") as f:
                f.write(json.dumps(dict(run="wave26-phase2-replay", wall_s=time.perf_counter() - t0, status="COMPLETE")) + "\n")
        art["report"]["phase2_pass"] = art["report"]["phase2_pass_excluding_replay"] and art["report"]["G_replay"]["passed"]
        Path(a.replay_of).write_text(json.dumps(art, default=repr, sort_keys=True))
        print(json.dumps(art["report"]["G_replay"]), art["report"]["phase2_pass"])
        return
    if a.dev:
        R.claim("phase2", "dev", seeds, run_id="phase2-dev", record=False)
    else:
        if not a.checkpoint:
            raise SystemExit("confirmation requires --checkpoint")
        R.claim("phase2", "confirm", seeds, run_id="phase2-confirm")
    t0, status = time.perf_counter(), "FAILED"
    try:
        outs = run(seeds, a.n, a.checkpoint)
        status = "COMPLETE"
    finally:
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run="wave26-phase2-" + ("dev" if a.dev else "confirm"), seeds=seeds,
                                    wall_s=time.perf_counter() - t0, status=status)) + "\n")
    from nexus.standing_gates import g_tycho
    from nexus.wave26_phase2 import score
    rep = score(outs)
    rep["digest"] = digest(outs)
    rep["G_tycho"] = g_tycho([r for o in outs for r in o["rows"]])
    rep["phase2_pass_excluding_replay"] = rep["calibrated_soundness"] and rep["full_beats_exact"] and rep["G_tycho"]["passed"]
    rep["G_replay"] = "PENDING (--replay-of)" if a.confirm else "n/a (dev)"
    Path(a.out).write_text(json.dumps(dict(schema="wave26_phase2", report=rep, seeds_raw=outs), default=repr, sort_keys=True))
    for k, v in sorted(rep["table"].items()):
        print(f"{k:28s} solved {v['solved']}/{v['episodes']} certs {v['certs']} false {v['false']} (<= {v['false_bound_99']}) "
              f"empty {v['empty']} probes {v['probes']} fully_loaded {int(v['fully_loaded'])}")
    print({k: rep[k] for k in ("calibrated_soundness", "full_beats_exact", "phase2_pass_excluding_replay", "digest")})


if __name__ == "__main__":
    main()
