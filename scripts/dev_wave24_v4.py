"""Dev-only v4 procedural run (seeds 1-5 are development seeds); every execution is ledgered."""
import argparse, json, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"


def summarize(res):
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))   # arm -> kind -> [solved, n, work, false]
    for r in res["rows"]:
        for k in (r["kind"], "ALL"):
            a = agg[r["arm"]][k]
            a[0] += r["solved"]; a[1] += 1; a[2] += r["work"]; a[3] += r["false_certificate"]
    for arm, d in agg.items():
        src = res["source_cost"].get(arm, 0) + res["setup_work"].get(arm, 0)
        print(f"{arm:34s} " + " ".join(f"{k}={v[0]}/{v[1]} w{v[2]} fc{v[3]}" for k, v in sorted(d.items()))
              + f" | src+setup {src}")
    pa = res["popper_audit"]
    off = sum(p["evals_off"] for p in pa); on = sum(p["evals_on"] for p in pa)
    print("popper evals", off, on, f"{1 - on / max(1, off):.3f}", "same", all(p["same_verdict"] for p in pa))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[1])
    ap.add_argument("--out")
    args = ap.parse_args()
    assert all(1 <= s <= 99 for s in args.seeds), "dev seeds only"
    from nexus.wave24_v4_agents import run_seed
    t0, c0 = time.perf_counter(), time.process_time()
    outs = []
    status = "FAILED"
    try:
        for s in args.seeds:
            t1 = time.perf_counter()
            res = run_seed(s)
            print(f"seed {s}: {time.perf_counter() - t1:.1f}s", flush=True)
            summarize(res)
            outs.append(res)
        status = "COMPLETE"
    finally:
        wall = time.perf_counter() - t0
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run="wave24-v4-dev:procedural", seeds=args.seeds, wall_s=wall,
                                    cpu_s=time.process_time() - c0, status=status)) + "\n")
        if args.out:
            Path(args.out).write_text(json.dumps(outs, default=repr))


if __name__ == "__main__":
    main()
