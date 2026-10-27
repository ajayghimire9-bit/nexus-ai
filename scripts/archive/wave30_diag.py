"""Wave 30 initial diagnostics: Checker Kernel + A0 / A1 / A1b on `dev` (751-755) and `admission_val` (7001-7005).
Diagnostics only (no locked gate yet); admission_val is reserved for admission decisions, never final claims."""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"
SPLITS = {"dev": ("wave30", "dev", range(751, 756)), "admission_val": ("wave30", "admission_val", range(7001, 7006))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=sorted(SPLITS))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus.wave30_arms import run_split, summarise
    k0, k1, seeds = SPLITS[a.split]
    R.claim(k0, k1, seeds, run_id=f"wave30-diag-{a.split}", record=False)
    t0 = time.perf_counter()
    outs = []
    try:
        for s in seeds:
            outs.append(run_split(s))
            print(f"seed {s} done {time.perf_counter() - t0:.0f}s", flush=True)
    finally:
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run=f"wave30-diag-{a.split}", wall_s=time.perf_counter() - t0,
                                    status="COMPLETE" if len(outs) == len(seeds) else "PARTIAL", seeds=list(seeds))) + "\n")
    rep = summarise(outs)
    Path(a.out).write_text(json.dumps(dict(split=a.split, report=rep, raw=outs), default=repr, sort_keys=True))
    print(json.dumps(rep, default=repr))


if __name__ == "__main__":
    main()
