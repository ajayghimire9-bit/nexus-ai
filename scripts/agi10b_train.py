"""Phase 10B Stage 3 training repetitions (NOT LOCKED).  python scripts/agi10b_train.py REP BUDGET_S [--dev] [--n=K]
REP 0 | 1: independent exogenous Repos_Train streams (manifest10b.train(rep)). Learner10b: P* on, valley detection + bridge
priority, learned ranker with bridge expansion, MDL + LOPO promotion, contract-guarded dreams, M* round at N1 with the fixed
gate (pi* rounds disabled). Checkpoints at N = 25 / 60 / 120 (a 'preM' N1 checkpoint before the M* round). Rows appended +
flushed to artifacts/agi10b_train/ (or artifacts/agi10b_dev/train/)."""
import json, shutil, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase10 import lineage10 as LN, manifest10 as MF, procedure10 as PR10  # noqa: E402
from nexus.de_phase10b import lineage10b as LB, manifest10b as MB  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(rep, budget, *flags):
    rep, budget, dev = int(rep), float(budget), "--dev" in flags
    n_max = next((int(f.split("=")[1]) for f in flags if f.startswith("--n=")), 120)
    out = ROOT / ("artifacts/agi10b_dev/train" if dev else "artifacts/agi10b_train")
    cps = (6, 12, n_max) if dev else MF.CHECKPOINTS
    name = f"rep{rep}"
    if dev:
        b = MB.RANGES[("agi10bde", "dev")].start + 400 * rep
        seeds = dict(wake=range(b, b + 60), dream=range(b + 60, b + 160), admit=range(b + 160, b + 260), pool=range(b + 260, b + 300),
                     mroll=range(b + 300, b + 360), mval=range(b + 360, b + 400))
    else:
        seeds = MB.train(rep)
        if (out / f"{name}.N{cps[-1]}.json").exists():
            raise SystemExit("repetitions are never rerun")
    W.SparkCode.warm()
    L = LB.Learner(name, LN.empty_memory(pstar=True), PR10.F0, ROOT / "var/agi10b_ws" / ("dev" if dev else "train") / name, T0 + budget - 10, out,
                   evolve_pi=False, seeds=seeds)
    wake = list(seeds["wake"])
    for i in range(n_max):
        if L.left() < 25:
            L.log("events", dict(kind="deadline", i=i))
            break
        s = wake[i]
        try:
            L.wake(MF.train_spec(i, s), s)
        except RuntimeError as e:
            L.log("events", dict(kind="build_failed", seed=s, err=str(e)[:80]))
            L.n += 1
        n = i + 1
        if n % L.mem["M"]["batch"] == 0 or n in cps:
            L.sleep()
        if n in cps:
            if n == cps[0]:
                ck = L.checkpoint(n)
                d = json.loads(ck.read_text())
                d["cursor"] = L.cursor
                (out / f"{name}.N{n}.preM.json").write_text(json.dumps(d, default=list))
                LB.m_round(L, ROOT / "var/agi10b_ws" / ("dev" if dev else "train") / name / "mround")
            L.checkpoint(n)
    fin = L.checkpoint(L.n)                                    # N3 = tasks reached within the cap (<= 120; pre-registered)
    shutil.copyfile(fin, out / f"{name}.final.json")
    L.log("events", dict(kind="end", n=L.n, cost={k: round(v, 1) for k, v in L.cost.items()}, wall=round(time.time() - T0, 1)))
    print(name, "tasks", L.n, "skills", len(L.mem["de"]["skills"]), "bridges", len(L.mem.get("bridges", [])), "P*", len(L.mem["P"]["hypotheses"]),
          "M", L.mem["M"], "cost", {k: round(v, 1) for k, v in L.cost.items()}, "wall", round(time.time() - T0, 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
