"""Phase 8 Stage 2 source learning (NOT LOCKED).  python scripts/agi8_source.py COHORT REP BUDGET_S [--dev] [--batch=N]
COHORT Full | FixedLearner (lineage8). Both start from F0 and an empty memory; archive rule and M0 frozen. Paired exogenous
stream per repetition (seeds8.block(rep)['train']; project i = SOURCE_SPECS[seed % len]). Full runs a future-learning
round after every ROUND_AFTER main projects while at least ROUND_MIN_S remain. Checkpoint rewritten after every cycle /
round. Output artifacts/agi8_src/<COHORT>_r<REP>.json (never rerun; --dev writes artifacts/agi8_dev/src/)."""
import json, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase8 import lineage8 as L8, seeds8 as S  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
ROUND_AFTER, ROUND_MIN_S = 8, 100.0


def main(cohort, rep, budget, *flags):
    rep, budget = int(rep), float(budget)
    dev = "--dev" in flags
    out = ROOT / ("artifacts/agi8_dev/src" if dev else "artifacts/agi8_src")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{cohort}_r{rep}.json"
    if path.exists() and not dev:
        raise SystemExit("source lineages are never rerun")
    if dev:
        b = S.RANGES[("agi8de", "dev")].start + 1000 * rep
        blk = dict(train=range(b, b + 400), admit=range(b + 400, b + 550), pool=range(b + 550, b + 600), roll=range(b + 600, b + 800),
                   down=range(b + 800, b + 900), conf=range(b + 900, b + 1000))
    else:
        blk = S.block(rep)
    W.SparkCode.warm()
    deadline = T0 + budget - 8.0
    lin = L8.Lineage(f"{cohort}_r{rep}", cohort, blk, L8.WS / ("dev" if dev else "src") / f"{cohort}_r{rep}", deadline, f"{cohort}|{rep}|{dev}", out_path=path)
    round_after, round_min = ROUND_AFTER, ROUND_MIN_S
    for f in flags:
        if dev and f.startswith("--batch="):
            lin.mem["M"]["batch"] = int(f.split("=")[1])
        if dev and f.startswith("--round_after="):
            round_after = int(f.split("=")[1])
        if dev and f.startswith("--round_min="):
            round_min = float(f.split("=")[1])
    seeds = list(blk["train"])
    n, last_round = 0, 0
    while lin.left() > 10 and n < len(seeds):
        s = seeds[n]
        t = time.time()
        try:
            lin.learn_project(L8.SOURCE_SPECS[s % len(L8.SOURCE_SPECS)], s)
        except RuntimeError as e:
            lin.log.append(dict(step="build_failed", seed=s, err=str(e)[:80]))
        lin.cost["main_s"] += time.time() - t
        n += 1
        if n % lin.mem["M"]["batch"] == 0 and lin.left() > 12:
            lin.cycle(len(lin.cycles))
        if cohort == "Full" and n - last_round >= round_after and lin.left() > round_min:
            lin.future_round(len(lin.rounds))
            last_round = n
    lin.save()
    d = lin.checkpoint()
    print(f"{cohort}_r{rep}", "projects", d["n_projects"], "verified", sum(r["verified"] for r in d["rows"]), "wrong", sum(r["wrong_first"] for r in d["rows"]),
          "cycles", len(d["cycles"]), "skills", sorted(d["memory"]["de"]["skills"]), "trust", len(d["memory"]["trust"]["records"]),
          "rounds", [(r["round"], r["result"], r.get("round_s")) for r in d["rounds"]], "| procedure", json.dumps(d["procedure"])[:300],
          "| cost", {k: round(v, 1) for k, v in d["cost"].items()}, "| wall", round(time.time() - T0, 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
