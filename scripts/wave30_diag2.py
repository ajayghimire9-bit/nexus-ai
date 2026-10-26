"""Wave 30 increment 2 diagnostics (NOT LOCKED). One (split, arm, prior) cell per call.
  --prior none|useful|shuffled   A1b transferred state, frozen before the target stream (--online lets the prior
                                 learn within the stream; used for the dev / source runs only)."""
import argparse, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"
SPLITS = {"dev": ("wave30", "dev", range(751, 756)), "admission_val": ("wave30", "admission_val", range(7001, 7006))}
SOURCE = ROOT / "artifacts" / "wave30_inc2_dev_A1b-full_online.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--prior", default="none")
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus.wave30_arms import FAMILIES
    from nexus.wave30_harness import FrozenPrior, run_stream, summarise, verify_kernel_pin
    pin = verify_kernel_pin()
    k0, k1, seeds = SPLITS[a.split]
    R.claim(k0, k1, seeds, run_id=f"wave30-inc2-{a.split}", record=False)
    source = None
    if a.prior == "none":
        counts = None
    else:
        src = json.loads(SOURCE.read_text())
        counts = src["prior_final"]
        source = dict(artifact=SOURCE.name, source_work=src["summary"]["work"], source_tasks=src["summary"]["n"])
        if a.prior == "shuffled":
            fams = sorted(counts)
            vals = [counts[f] for f in fams]
            random.Random("w30-shuffled-history").shuffle(vals)
            counts = dict(zip(fams, vals))                   # size-matched: same total mass, wrong families
    prior = FrozenPrior(counts, online=a.online) if a.arm.startswith("A1b") else None
    t0 = time.perf_counter()
    rows = []
    try:
        for s in seeds:
            rows += [dict(r, seed=s) for r in run_stream(s, a.arm, prior=prior)]
    finally:
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run=f"wave30-inc2-{a.split}-{a.arm}-{a.prior}", wall_s=time.perf_counter() - t0,
                                    status="COMPLETE", seeds=list(seeds))) + "\n")
    rep = summarise(rows)
    out = dict(split=a.split, arm=a.arm, prior=a.prior, online=a.online, kernel_sha256=pin, summary=rep,
               source=source, prior_final=dict(prior.c) if prior else None, rows=rows)
    Path(a.out).write_text(json.dumps(out, default=repr, sort_keys=True))
    print(json.dumps({k: rep[k] for k in ("n", "correct", "exhaustive_certified", "agreement_among_proposals",
                                          "wrong_outside_scope", "wrong_inside_scope", "invalid_claims", "ambiguous",
                                          "abstain", "work")}))


if __name__ == "__main__":
    main()
