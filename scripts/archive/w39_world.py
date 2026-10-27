"""Wave 39 Step 5a (NOT LOCKED): cheap adaptation in the noisy / changing SwitchGrid world. 10,000-step streams (obs noise 0.15,
slip 0.1, hazard 1/200; change times hidden). Agents: reactive, fixed-model, N1-BOCPD (Wave 36, unchanged), and the N1-lite
frontier (w39_world.VARIANTS). Metrics: return, Brier, adaptation delay (returning / new goal), agent compute (OS retired
instructions of the agent's own calls) and its ratio to fixed-model. --split dev (wave39 dev seeds) | confirm (confirm_world)."""
import argparse, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
AGENTS = ("reactive", "fixed-model", "N1-BOCPD", "N1-merge-exact", "N1-lite-prune", "N1-lite-prune8", "N1-lite-gate0.3",
          "N1-lite-gate0.6")


def run(name, seed, T, instr):
    from nexus import w39_world as W
    import w38_world_long as WL
    orig = WL.__dict__.get("_make_orig")
    from nexus import wave36_world as Wd
    saved = Wd.make
    Wd.make = W.make if name in W.VARIANTS else saved
    try:
        out = WL.run(name, seed, T=T, instr=instr)
    finally:
        Wd.make = saved
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--out", required=True)
    ap.add_argument("--T", type=int, default=10000)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus.wave31_evaluator import instructions, ledger_append
    if a.split == "dev":
        seeds = [f"w39-world-{s}" for s in list(R.REGISTRY[("wave39", "dev")])[:3]]
    else:
        seeds = R.claim("wave39", "confirm_world", list(R.REGISTRY[("wave39", "confirm_world")]), run_id="w39-confirm_world")
        seeds = [f"w39-world-{s}" for s in seeds]
    t0 = time.perf_counter()
    res = {ag: [run(ag, s, a.T, lambda: instructions(os.getpid())) for s in seeds] for ag in AGENTS}
    Path(a.out).write_text(json.dumps(dict(seeds=seeds, T=a.T, results=res), sort_keys=True))
    ledger_append(dict(run=f"w39-world-{a.split}", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    fx = mean([r["instr"] for r in res["fixed-model"]])
    for ag, rs in res.items():
        g = lambda k: [r[k] for r in rs if r[k] is not None]
        print(f"{ag:16s} return {mean(g('ret')):7.1f} brier {mean(g('brier')):.4f} delay(ret) {mean(g('delay_return')):6.1f} "
              f"delay(new) {mean(g('delay_new')):6.1f} instr {mean(g('instr')) / 1e9:7.2f}G  x{mean(g('instr')) / fx:6.1f} fixed-model")


if __name__ == "__main__":
    main()
