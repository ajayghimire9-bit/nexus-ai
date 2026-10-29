"""Phase 7 Stage 2 source learning (NOT LOCKED).  python scripts/agi7_source.py COHORT REP BUDGET_S [--dev]
COHORT Full | FixedLearner (lineage7). Tiers 1-2 only; both cohorts of a repetition see the same exogenous stream
(seeds7.block(rep): project i of the stream is SOURCE_SPECS[seed % len] at seed train[i]). Repeated learn -> admit -> use
cycles until BUDGET_S minus a checkpoint margin; the checkpoint is rewritten after every cycle, so a timeout keeps the last
complete cycle. Output artifacts/agi7_src/<COHORT>_r<REP>.json (never rerun; --dev writes artifacts/agi7_dev/src/)."""
import json, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase7 import lineage7 as L7, seeds7 as S  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(cohort, rep, budget, *flags):
    rep, budget = int(rep), float(budget)
    dev = "--dev" in flags
    out = ROOT / ("artifacts/agi7_dev/src" if dev else "artifacts/agi7_src")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{cohort}_r{rep}.json"
    if path.exists() and not dev:
        raise SystemExit("source lineages are never rerun")
    if dev:
        b = S.RANGES[("agi7de", "dev")].start + 400 + 400 * rep
        blk = dict(train=range(b, b + 200), admit=range(b + 200, b + 300), pool=range(b + 300, b + 350), confirm=range(b + 350, b + 400))
    else:
        blk = S.block(rep)
    W.SparkCode.warm()
    deadline = T0 + budget - 10.0
    lin = L7.Lineage(f"{cohort}_r{rep}", cohort, blk, L7.WS / ("dev" if dev else "src") / f"{cohort}_r{rep}", deadline, f"{cohort}|{rep}|{dev}",
                     out_path=path)
    for f in flags:
        if f.startswith("--batch=") and dev:                       # development rehearsal only
            lin.mem["M"]["batch"] = int(f.split("=")[1])
    seeds = list(blk["train"])
    n = 0
    while lin.left() > 12 and n < len(seeds):
        s = seeds[n]
        try:
            lin.learn_project(L7.SOURCE_SPECS[s % len(L7.SOURCE_SPECS)], s)
        except RuntimeError as e:
            lin.log.append(dict(step="build_failed", seed=s, err=str(e)[:80]))
        n += 1
        if n % lin.mem["M"]["batch"] == 0 and lin.left() > 15:
            lin.cycle(len(lin.cycles))
    lin.save()
    d = lin.checkpoint()
    print(f"{cohort}_r{rep}", "projects", d["n_projects"], "verified", sum(r["verified"] for r in d["rows"]), "wrong", sum(r["wrong_first"] for r in d["rows"]),
          "cycles", len(d["cycles"]), "skills", sorted(d["memory"]["de"]["skills"]), "trust", len(d["memory"]["trust"]["records"]),
          "policy updates", len(d["memory"]["policy_prov"]), "| procedure", json.dumps(d["procedure"])[:240], "| touch", d["touch"],
          "| wall", round(time.time() - T0, 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
