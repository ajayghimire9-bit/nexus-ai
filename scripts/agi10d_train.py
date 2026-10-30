"""Phase 10D Stage 2 compositional wake-sleep repetitions on multi-table DAGs (NOT LOCKED).  python scripts/agi10d_train.py REP BUDGET_S [--dev] [--n=K]
REP 0 | 1: independent numeric-seeded training streams (manifest10d.train(rep) / train_spec(rep, i)); held-out multi-node compositions
never appear (manifest10d.leakage). Sleep every 10 tasks; checkpoints N = 30 / 60 / 120 (N0 = empty learned memory); stops at the cap
(N3 = tasks reached; disclosed). Rows appended + flushed to artifacts/agi10d_train/ (or artifacts/agi10d_dev/train/)."""
import json, shutil, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase10d import lineage10d as LD, manifest10d as MD  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(rep, budget, *flags):
    rep, budget, dev = int(rep), float(budget), "--dev" in flags
    n_max = next((int(f.split("=")[1]) for f in flags if f.startswith("--n=")), MD.CHECKPOINTS[-1])
    out = ROOT / ("artifacts/agi10d_dev/train" if dev else "artifacts/agi10d_train")
    cps = (max(1, n_max // 4), max(2, n_max // 2), n_max) if dev else MD.CHECKPOINTS
    name = f"rep{rep}"
    if dev:
        b = MD.RANGES[("agi10dde", "dev")].start + 200 + 300 * rep
        seeds = dict(wake=range(b, b + 100), dream=range(b + 100, b + 200), admit=range(b + 200, b + 300))
    else:
        seeds = MD.train(rep)
        if (out / f"{name}.final.json").exists():
            raise SystemExit("repetitions are never rerun")
    L = LD.Learner(rep, name, ROOT / "var/agi10d_ws" / ("dev" if dev else "train") / name, T0 + budget - 10, out, seeds)
    L.log("events", dict(kind="start", rep=rep, n_max=n_max, checkpoints=list(cps)))
    wake = list(seeds["wake"])
    for i in range(n_max):
        if L.left() < 25:
            L.log("events", dict(kind="deadline", i=i))
            break
        try:
            L.wake(i, wake[i])
        except RuntimeError as e:
            L.log("events", dict(kind="build_failed", seed=wake[i], err=str(e)[:80]))
            L.n += 1
        n = i + 1
        if n % L.M["batch"] == 0 or n in cps:
            L.sleep()
        if n in cps:
            L.checkpoint(n)
    fin = L.checkpoint(L.n)
    shutil.copyfile(fin, out / f"{name}.final.json")
    L.log("events", dict(kind="end", n=L.n, cost={k: round(v, 1) for k, v in L.cost.items()}, wall=round(time.time() - T0, 1)))
    w = [json.loads(l) for l in open(out / f"{name}.wake.jsonl")]
    print(name, "tasks", L.n, "verified", sum(x["verified"] for x in w), "wrong", sum(x["wrong"] for x in w), "skills", len(L.mem["de"]["skills"]),
          "guides", sorted(L.mem["guides"]), "cost", {k: round(v, 1) for k, v in L.cost.items()}, "wall", round(time.time() - T0, 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
