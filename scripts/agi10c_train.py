"""Phase 10C Stage 3 compositional wake-sleep repetitions (NOT LOCKED).  python scripts/agi10c_train.py REP BUDGET_S [--dev] [--n=K]
REP 0 | 1: independent numeric-seeded Repos_Train streams (manifest10c.train(rep) / train_spec(rep, i)); held-out composition
families never appear (manifest10c.leakage). Fixed trust = the frozen Phase 10B rep0 final trust state (sha256 recorded).
Sleep every 10 tasks; checkpoints at N = 15 / 30 / 60 (revised Phase 10C) (N0 = the empty learned memory). Stops at the cap (N3 = tasks reached;
disclosed). Rows appended + flushed to artifacts/agi10c_train/ (or artifacts/agi10c_dev/train/)."""
import hashlib, json, shutil, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase10c import lineage10c as LC, manifest10c as MC  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
TRUST_SRC = ROOT / "artifacts/agi10b_train/rep0.final.json"


def fixed_trust():
    return json.loads(TRUST_SRC.read_text())["memory"]["trust"], hashlib.sha256(TRUST_SRC.read_bytes()).hexdigest()


def main(rep, budget, *flags):
    rep, budget, dev = int(rep), float(budget), "--dev" in flags
    n_max = next((int(f.split("=")[1]) for f in flags if f.startswith("--n=")), MC.CHECKPOINTS[-1])
    out = ROOT / ("artifacts/agi10c_dev/train" if dev else "artifacts/agi10c_train")
    cps = (max(1, n_max // 4), max(2, n_max // 2), n_max) if dev else MC.CHECKPOINTS
    name = f"rep{rep}"
    if dev:
        b = MC.RANGES[("agi10cde", "dev")].start + 400 * rep
        seeds = dict(wake=range(b, b + 100), dream=range(b + 100, b + 250), admit=range(b + 250, b + 400))
    else:
        seeds = MC.train(rep)
        if (out / f"{name}.final.json").exists():
            raise SystemExit("repetitions are never rerun")
    trust, th = fixed_trust()
    W.SparkCode.warm()
    L = LC.Learner(rep, name, trust, ROOT / "var/agi10c_ws" / ("dev" if dev else "train") / name, T0 + budget - 10, out, seeds)
    L.log("events", dict(kind="start", rep=rep, trust_source=str(TRUST_SRC.relative_to(ROOT)), trust_sha256=th, n_max=n_max, checkpoints=list(cps)))
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
    print(name, "tasks", L.n, "verified", sum(json.loads(l)["verified"] for l in open(out / f"{name}.wake.jsonl")), "skills", len(L.mem["de"]["skills"]),
          "guides", sorted(L.mem["guides"]), "cost", {k: round(v, 1) for k, v in L.cost.items()}, "wall", round(time.time() - T0, 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
