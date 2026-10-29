"""Phase 6 Stage 3: full-trajectory improver versus improver (NOT LOCKED).  python scripts/agi6_meta.py REP IMP BUDGET_S [--dev]
Each clone starts from the identical frozen Full_r<REP> endpoint (memory: pi weights, invented skills and their sources,
calibrated trust) and runs a COMPLETE learning trajectory controlled by its improver M - its skill-invention settings,
trust calibration, search effort, curriculum order and procedure-composition settings:
  Mstar = the Full endpoint's evolved M;  M0 = lineage6.M0;  Mrand = lineage6.m_random(random.Random(f"agi6-mrand-{REP}"))
Trajectory: Tier-2 source projects (paired stream seeds6.meta_block(REP)), skill invention + corrected admission every 5
projects, then validation caches and procedure composition from SEED under its M. No meta-edits inside the clone.
Output artifacts/agi6_meta/r<REP>_<IMP>.json (never rerun)."""
import json, random, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase6 import lineage6 as L6, procedure6 as PR, seeds6 as S6, world6 as W6  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(rep, imp, budget, *flags):
    rep, budget = int(rep), float(budget)
    dev = "--dev" in flags
    src = ROOT / ("artifacts/agi6_dev/src" if dev else "artifacts/agi6_src")
    out = ROOT / ("artifacts/agi6_dev/meta" if dev else "artifacts/agi6_meta")
    out.mkdir(parents=True, exist_ok=True)
    if (out / f"r{rep}_{imp}.json").exists() and not dev:
        raise SystemExit("meta clones are never rerun")
    mem = json.loads((src / f"Full_r{rep}.json").read_text())["memory"]
    if imp == "M0":
        mem["M"] = dict(L6.M0)
    elif imp == "Mrand":
        mem["M"] = L6.m_random(random.Random(f"agi6-mrand-{rep}"))
    elif imp != "Mstar":
        raise SystemExit(imp)
    L6.redigest(mem)
    W.SparkCode.warm()
    blk = S6.meta_block(rep) if not dev else dict(train=range(61850, 61900), admit=range(61900, 61950), val=range(61950, 61990))
    deadline = T0 + budget - 3.0
    lin = L6.Lineage(f"r{rep}_{imp}", "Full", mem, blk["train"], blk["admit"], [], L6.WS / ("dev_meta" if dev else "meta") / f"r{rep}_{imp}",
                     deadline - 0.35 * budget, f"meta6|{rep}")
    tier2 = [s for s in L6.SOURCE_SPECS if W6.TIER[s["paradigm"]] == 2]
    stream = L6.order_stream([tier2[s % len(tier2)] for s in blk["train"]], mem["M"], random.Random(f"agi6-meta-stream|{rep}"))
    n = 0
    while lin.left() > 2 and n < len(stream):
        try:
            lin.learn_project(stream[n], list(blk["train"])[n])
        except RuntimeError:
            pass
        n += 1
        if n % 5 == 0:
            lin.invent_and_admit()
    live = PR.Live(lambda p: lin.mem["M"]["src_budget"])
    val, caches = [], {}
    for s in list(blk["val"])[:6]:
        if time.time() > deadline - 0.1 * budget:
            break
        try:
            p = W6.make_project6(tier2[(s * 5) % len(tier2)], s, lin.root / "val")
        except RuntimeError:
            continue
        caches[p["pid"]] = PR.build_entry(p, live, lin.mem)
        val.append(p)
    prog, lib, plog = PR.learn_policy(PR.SEED, val, caches, lin.mem, random.Random(f"agi6-meta-pl|{rep}|{imp}"), cycles=lin.mem["M"]["proc_cycles"],
                                      typed_pairs=lin.mem["M"]["typed_pairs"])
    doc = dict(rep=rep, imp=imp, M=lin.mem["M"], memory=lin.mem, procedure=prog, library=lib, policy_log=plog, rows=lin.rows, log=lin.log,
               learning_curve=[(i + 1, sum(r["verified"] for r in lin.rows[:i + 1])) for i in range(len(lin.rows))],
               wall=round(time.time() - T0, 1))
    (out / f"r{rep}_{imp}.json").write_text(json.dumps(doc, default=list))
    print(f"r{rep}_{imp}", "projects", len(lin.rows), "verified", sum(r["verified"] for r in lin.rows), "skills", len(lin.mem["de"]["skills"]),
          "procedure", json.dumps(prog)[:160], "wall", doc["wall"], flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
