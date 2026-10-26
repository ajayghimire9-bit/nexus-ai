"""Wave 38 experiment 6, world track (NOT LOCKED): long non-stationary interactive streams (2,000 steps; obs noise 0.15, slip
0.1, unannounced goal switches at hazard 1/200; change times hidden). CALIBRATED_PREDICTION class: return, Brier, adaptation
delay split by whether the new goal was seen before (retention) or not; compute = OS instructions. --split dev | confirm_cont."""
import argparse, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def run(name, seed, T=2000, instr=lambda: 0):
    from nexus import wave36_world as Wd
    env = Wd.SwitchGrid(seed, obs_noise=0.15, slip=0.1, hazard=1 / 200)
    ag = Wd.make(name, seed)
    seen_goals, hits, brier, total = {env.goal}, [], 0.0, 0
    i0 = instr(); o = env.observe(); change_meta = []
    for t in range(T):
        before = len(env.changes)
        a, p = ag.act(o)
        rew = env.step(a, t)
        if len(env.changes) > before:
            change_meta.append((t, env.goal in seen_goals)); seen_goals.add(env.goal)
        o2 = env.observe(); ag.learn(o, a, rew, o2)
        total += rew; brier += (p - rew) ** 2; hits.append(rew); o = o2
    dl = {True: [], False: []}
    for c, ret in change_meta:
        nh = next((t for t in range(c, T) if hits[t]), None)
        dl[ret].append((nh - c) if nh is not None else T - c)
    m = lambda xs: sum(xs) / len(xs) if xs else None
    return dict(ret=total, brier=brier / T, delay_return=m(dl[True]), delay_new=m(dl[False]), n_return=len(dl[True]),
                n_new=len(dl[False]), instr=instr() - i0)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus.wave31_evaluator import instructions, ledger_append
    if a.split == "dev":
        seeds = [f"wlong-dev{i}" for i in range(4)]
    else:
        seeds = [f"wlong-{s}" for s in R.REGISTRY[("wave38", "confirm_cont")]]
    t0 = time.perf_counter()
    agents = ("reactive", "model-free", "fixed-model", "N1-BOCPD")
    res = {ag: [run(ag, s, instr=lambda: instructions(os.getpid())) for s in seeds] for ag in agents}
    Path(a.out).write_text(json.dumps(dict(seeds=seeds, results=res), sort_keys=True))
    ledger_append(dict(run=f"w38-world-long-{a.split}", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    for ag, rs in res.items():
        g = lambda k: [r[k] for r in rs if r[k] is not None]
        mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
        print(f"{ag:12s} return {mean(g('ret')):.1f} brier {mean(g('brier')):.4f} delay(return) {mean(g('delay_return')):.1f} "
              f"delay(new) {mean(g('delay_new')):.1f} instr {mean(g('instr')) / 1e9:.2f}G")


if __name__ == "__main__":
    main()
