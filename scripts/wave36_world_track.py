"""Wave 36 noisy / changing-world track driver (NOT LOCKED). Conditions vary ONE factor at a time, plus all combined.
--split dev (seeds dev0..dev4) or --split confirm_world (one-use 7611-7620, run once after freezing)."""
import argparse, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CONDS = {"clean": {}, "obs_noise": {"obs_noise": 0.2}, "slip": {"slip": 0.2}, "change": {"hazard": 1 / 150},
         "all": {"obs_noise": 0.2, "slip": 0.2, "hazard": 1 / 150}}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave36_world as Wd
    from nexus.wave31_evaluator import instructions, ledger_append
    if a.split == "dev":
        seeds = [f"dev{i}" for i in range(5)]
    else:
        seeds = list(R.REGISTRY[("wave36", "confirm_world")])
        R.claim("wave36", "confirm_world", seeds, run_id="w36-confirm_world")
    t0 = time.perf_counter()
    res = {c: {ag: [Wd.run(ag, s, cond, instr=lambda: instructions(os.getpid())) for s in seeds] for ag in Wd.AGENTS}
           for c, cond in CONDS.items()}
    out = {"seeds": [str(s) for s in seeds], "results": res, "summary": {}}
    for c in CONDS:
        out["summary"][c] = {}
        for ag in Wd.AGENTS:
            rs = res[c][ag]
            d = [r["delay"] for r in rs if r["delay"] is not None]
            out["summary"][c][ag] = dict(ret=sum(r["ret"] for r in rs) / len(rs), brier=sum(r["brier"] for r in rs) / len(rs),
                                         delay=(sum(d) / len(d)) if d else None, instr=sum(r["instr"] for r in rs) / len(rs))
    Path(a.out).write_text(json.dumps(out, sort_keys=True, default=repr))
    ledger_append(dict(run=f"w36-world-{a.split}", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    for c in CONDS:
        print(c, " | ".join(f"{ag}: ret {v['ret']:.1f} brier {v['brier']:.4f} delay {v['delay'] if v['delay'] is None else round(v['delay'], 1)} "
                             f"{v['instr'] / 1e6:.0f}M" for ag, v in out["summary"][c].items()))


if __name__ == "__main__":
    main()
