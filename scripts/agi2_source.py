"""Phase 2 Stage 2 source learning (NOT LOCKED).  python scripts/agi2_source.py COHORT REP BUDGET_S [--dev]
COHORT:
  Full        R, L, P, pi learn; M starts at M0 and evolves by FULL-ROLLOUT comparisons (agent_loop.Lineage.meta_rollout);
              own curriculum; its learned-task sequence (main loop + winning rollouts) is saved for the controls.
  Fixed-M0    R, L, P, pi learn; M frozen at M0; replays Full_r<REP>'s learned-task sequence.
  SolvedOnly  the No-Incomplete-Experience ablation: identical to Fixed-M0 (same replayed sequence, M0) with the
              provisional archive P DISABLED (only verified solutions feed proposals). Fixed-M0 vs SolvedOnly isolates P;
              Full vs SolvedOnly is the Arm 1 vs Arm 2 contrast (it also contains Full's M evolution, if any).
  Random-Proposal  M = matched random improver (random proposals; same archive capacity, admission and budget), frozen;
              replays the same sequence.
Seeds: source agi2/source 37600 + 1000 * REP; admission agi2/admission 40600 + 300 * REP; Full's rollout-evaluation
tasks agi2/rollout 41600 + 300 * REP. --dev uses agi2/dev seeds. Output artifacts/agi2_src/<COHORT>_r<REP>.json."""
import json, random, sys, time
T_START = time.time()
from pathlib import Path  # noqa: E402
from nexus.campaign2 import agent_loop as AL, improver as I, seeds as SD, state as ST  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(cohort, rep, budget, *flags):
    rep, budget = int(rep), float(budget)
    dev = "--dev" in flags
    out = ROOT / ("artifacts/agi2_dev/src" if dev else "artifacts/agi2_src")
    name = f"{cohort}_r{rep}"
    if (out / f"{name}.json").exists() and not dev:
        raise SystemExit(f"{name} exists: source lineages are never rerun")
    R0 = {k: SD.RANGES[("agi2", k)].start for k in ("dev", "source", "admission", "rollout")}
    if dev:
        ts, as_, rs = range(R0["dev"] + 400 + 100 * rep, R0["dev"] + 500 + 100 * rep), range(R0["dev"] + 700, R0["dev"] + 850), \
            range(R0["dev"] + 850, R0["dev"] + 1000)
    else:
        ts = range(R0["source"] + 1000 * rep, R0["source"] + 1000 * (rep + 1))
        as_ = range(R0["admission"] + 300 * rep, R0["admission"] + 300 * rep + 200)
        rs = range(R0["rollout"] + 300 * rep, R0["rollout"] + 300 * (rep + 1))
    M = I.m_random(random.Random(f"agi2-mrand-{rep}")) if cohort == "Random-Proposal" else I.M0
    st = ST.empty_state(M)
    schedule = None
    if cohort != "Full":
        full = json.loads((out / f"Full_r{rep}.json").read_text())
        if not full.get("final"):
            raise SystemExit("the Full lineage of this repetition has not finished")
        schedule = [tuple(x) for x in full["schedule"]]
    lin = AL.Lineage(name, st, budget, out, ts, as_, rng_key=f"{cohort}|{rep}|{'dev' if dev else 'src'}", schedule=schedule,
                     meta_edits=cohort == "Full", use_P=cohort != "SolvedOnly", roll_seeds=rs if cohort == "Full" else None)
    lin.T0, lin.C0 = T_START, 0.0
    lin.run()
    s = [r for r in lin.rows]
    print(name, "tasks", len(s), "solved", sum(r["solved"] for r in s), "silent", sum(r["silent"] for r in s), "rounds",
          len(lin.rounds), "L", len(lin.st["L"]), "R", len(lin.st["R"]), "P", len(lin.st["P"]), "meta adopted",
          sum(m["adopted"] for m in lin.meta_log), "/", len(lin.meta_log), "stop", lin.stop_reason, "elapsed",
          round(lin.elapsed(), 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
