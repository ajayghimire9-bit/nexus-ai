"""Phase 4 Stage 2 source learning (NOT LOCKED).  python scripts/agi4_source.py COHORT REP BUDGET_S [--dev]
  Full             DE memory (pi_de, skills L, failure archive P, prefs) learns; M evolves by full-rollout checks (>= 10
                   distinct edits); own curriculum over multi-fault cells (6 source mechanisms x k = 1..4, SQLite / Spark)
  SolvedOnly       its OWN cohort from t = 0: the identical algorithm (own curriculum, own meta checks) with failure memory
                   OFF (no refutations, no partial repairs, no P-promoted stage skills, no preference updates from refuted
                   submissions); paired seed streams with Full
  Fixed-M0         M frozen at M0; replays Full_r<REP>'s learned-project sequence
  Random-Proposal  matched random M (lineage.m_random) and random skill proposals; replays Full_r<REP>'s sequence
Seeds: seeds.src_block(REP) (agi4de/source 54100 + 500 REP: learning / admission / rollout blocks). The Spark session is
warmed before the lineage clock starts. Output artifacts/agi4_src/<COHORT>_r<REP>.json (never rerun)."""
import json, random, sys, time
from pathlib import Path
from nexus.de_phase4 import lineage as LG, learner as L, seeds as SD, world as W
ROOT = Path(__file__).resolve().parents[1]


def main(cohort, rep, budget, *flags):
    rep, budget = int(rep), float(budget)
    dev = "--dev" in flags
    out = ROOT / ("artifacts/agi4_dev/src" if dev else "artifacts/agi4_src")
    name = f"{cohort}_r{rep}"
    if (out / f"{name}.json").exists() and not dev:
        raise SystemExit(f"{name} exists: source lineages are never rerun")
    if dev:
        b = SD.RANGES[("agi4de", "dev")].start + 200 + 100 * rep
        blk = dict(learn=range(b, b + 50), admit=range(b + 50, b + 70), roll=range(b + 70, b + 100))
    else:
        blk = SD.src_block(rep)
    t = time.time()
    W.SparkCode.warm()
    warm = round(time.time() - t, 2)
    M = LG.m_random(random.Random(f"agi4-mrand-{rep}")) if cohort == "Random-Proposal" else json.loads(json.dumps(LG.M0))
    st = dict(DE=L.empty_de(), M=M)
    schedule = None
    if cohort in ("Fixed-M0", "Random-Proposal"):
        full = json.loads((out / f"Full_r{rep}.json").read_text())
        if not full.get("final"):
            raise SystemExit("the Full lineage of this repetition has not finished")
        schedule = [tuple(x) for x in full["schedule"]]
    lin = LG.Lineage(name, st, budget, out, blk["learn"], blk["admit"], roll_seeds=blk["roll"] if cohort in ("Full", "SolvedOnly") else None,
                     schedule=schedule, meta_edits=cohort in ("Full", "SolvedOnly"), use_P=cohort != "SolvedOnly",
                     random_de=cohort == "Random-Proposal", rng_key=f"{'Full' if cohort == 'SolvedOnly' else cohort}|{rep}|{'dev' if dev else 'src'}")
    lin.run()
    s = [r for r in lin.rows]
    de = lin.st["DE"]
    print(name, "spark_warm", warm, "projects", len(s), "verified", sum(r["solved"] for r in s), "silent", sum(r["silent"] for r in s),
          "skills", len(de["skills"]), "P", len(de["P"]), "prefs", {k: v for k, v in de["prefs"].items() if v}, "meta adopted",
          sum(m["adopted"] for m in lin.meta_log), "/", len(lin.meta_log), "stop", lin.stop_reason, "elapsed", round(lin.elapsed(), 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
