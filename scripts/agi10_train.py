"""Phase 10 Stage 3 wake-sleep lineages (NOT LOCKED).  python scripts/agi10_train.py LINEAGE BUDGET_S [--dev] [--n=K]
  main  C1 lineage: P* on, pi* rounds at N1 / N2, M* round at N1 (a 'preM' N1 checkpoint is saved before it)
  C2    identical except P* is DISCARDED (no partial / failed hypotheses, no partial skill sources); applies the main
        lineage's M* decision at N1 (read from its log) so that P* is the only difference
  C3    only when main adopted M*: continues from main's preM N1 checkpoint with M LOCKED at M0 (pi* round at N2)
Every wake / sleep / round row is appended + flushed (artifacts/agi10_train/ or artifacts/agi10_dev/train/); checkpoints
are written atomically at N = 25 / 60 / 120. --dev uses agi10de/dev seeds and N = 6 / 12 / --n."""
import copy, json, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase10 import lineage10 as LN, manifest10 as MF, procedure10 as PR10  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(lineage, budget, *flags):
    dev = "--dev" in flags
    budget = float(budget)
    n_max = next((int(f.split("=")[1]) for f in flags if f.startswith("--n=")), 120)
    out = ROOT / ("artifacts/agi10_dev/train" if dev else "artifacts/agi10_train")
    cps = (6, 12, n_max) if dev else MF.CHECKPOINTS
    seeds = MF.TRAIN
    if dev:
        b = MF.RANGES[("agi10de", "dev")].start
        seeds = dict(wake=range(b, b + 200), dream=range(b + 200, b + 400), admit=range(b + 400, b + 600), pool=range(b + 600, b + 700),
                     mroll=range(b + 700, b + 800), mval=range(b + 800, b + 900))
    if not dev and (out / f"{lineage}.N{cps[-1]}.json").exists():
        raise SystemExit("lineages are never rerun")
    W.SparkCode.warm()
    deadline = T0 + budget - 10
    root = ROOT / "var/agi10_ws" / ("dev" if dev else "train") / lineage
    start, m_decision = 0, None
    if lineage == "C3":
        ck = json.loads((out / f"main.N{cps[0]}.preM.json").read_text())
        L = LN.Learner("C3", ck["memory"], ck["procedure"], root, deadline, out, evolve_pi=True, seeds=seeds)
        L.n, start, L.cursor = ck["n"], ck["n"], ck.get("cursor", L.cursor)
    else:
        L = LN.Learner(lineage, LN.empty_memory(pstar=lineage != "C2"), PR10.F0, root, deadline, out, evolve_pi=True, seeds=seeds)
    if lineage == "C2":
        m_rows = [json.loads(l) for l in (out / "main.m.jsonl").read_text().splitlines()] if (out / "main.m.jsonl").exists() else []
        m_decision = m_rows[-1] if m_rows else None
    wake = list(seeds["wake"])
    for i in range(start, n_max):
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
            if n in cps[:2]:
                L.pi_round(cps.index(n))
            if n == cps[0] and lineage == "main":
                ck = L.checkpoint(n)
                ck.rename(out / f"main.N{n}.preM.json")
                d = json.loads((out / f"main.N{n}.preM.json").read_text())
                d["cursor"] = L.cursor
                (out / f"main.N{n}.preM.json").write_text(json.dumps(d, default=list))
                LN.m_round(L, root / "mround")
            if n == cps[0] and lineage == "C2" and m_decision and m_decision.get("adopted"):
                L.mem["M"] = copy.deepcopy(m_decision["results"]["M_edit"]["M"])
                L.log("events", dict(kind="applied main M* decision", M=L.mem["M"]))
            L.checkpoint(n)
    L.log("events", dict(kind="end", n=L.n, cost={k: round(v, 1) for k, v in L.cost.items()}, wall=round(time.time() - T0, 1)))
    print(lineage, "tasks", L.n, "cycles", L.cycles, "skills", len(L.mem["de"]["skills"]), "P*", len(L.mem["P"]["hypotheses"]), "pairs", len(L.mem["pairs"]),
          "cost", {k: round(v, 1) for k, v in L.cost.items()}, "wall", round(time.time() - T0, 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
