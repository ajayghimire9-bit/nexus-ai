"""Multi-world campaign Stage 2 source learning (NOT LOCKED).
  python scripts/agi_source.py COHORT REP BUDGET_S [--dev]
COHORT in Full, Fixed-M0, Random-Proposal; REP in 0 1 2. One lineage = one metered process (scripts/mi_exec.py cap 200 s);
the internal budget (wall or CPU, whichever is larger, since process start) stops new work so that the endpoint is saved
before the cap.
  Full             R, L, pi learn; M starts at M0 and evolves (meta edits adopted by paired admission comparison);
                   chooses its own curriculum; its logged task schedule is saved.
  Fixed-M0         identical, M frozen at M0; replays the Full lineage's logged schedule of the same repetition.
  Random-Proposal  M = the matched random improver (random L / R / pi proposals, same admission gate), frozen; replays
                   the same schedule.
Seeds: source tasks agi/source 31000 + 1000 * REP + k; admission tasks agi/admission 34000 + 300 * REP + k (the same
sequence for the three cohorts of a repetition). --dev uses agi/dev seeds instead (development of the runner only).
Endpoint -> artifacts/agi_src/<COHORT>_r<REP>.json (atomic saves every 5 tasks and at the end)."""
import json, random, sys, time
T_START = time.time()
from pathlib import Path  # noqa: E402
from nexus.campaign import agent_loop as AL, improver as I, seeds as SD, state as ST  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(cohort, rep, budget, *flags):
    rep, budget = int(rep), float(budget)
    dev = "--dev" in flags
    out = ROOT / ("artifacts/agi_dev/src" if dev else "artifacts/agi_src")
    name = f"{cohort}_r{rep}"
    if (out / f"{name}.json").exists() and not dev:
        raise SystemExit(f"{name} exists: source lineages are never rerun")
    if dev:
        tseeds = range(30600 + 100 * rep, 30700 + 100 * rep)
        aseeds = range(30900, 31000)
    else:
        tseeds = range(SD.RANGES[("agi", "source")].start + 1000 * rep, SD.RANGES[("agi", "source")].start + 1000 * (rep + 1))
        aseeds = range(SD.RANGES[("agi", "admission")].start + 300 * rep, SD.RANGES[("agi", "admission")].start + 300 * rep + 300)
    schedule = None
    if cohort == "Full":
        st = ST.empty_state(I.M0)
    elif cohort == "Fixed-M0":
        st = ST.empty_state(I.M0)
    elif cohort == "Random-Proposal":
        st = ST.empty_state(I.m_random(random.Random(f"agi-mrand-{rep}")))
    else:
        raise SystemExit(cohort)
    if cohort != "Full":
        full = json.loads((out / f"Full_r{rep}.json").read_text())
        if not full.get("final"):
            raise SystemExit("the Full lineage of this repetition has not finished")
        schedule = [tuple(x) for x in full["schedule"]]
    lin = AL.Lineage(name, st, budget, out, tseeds, aseeds, rng_key=f"{cohort}|{rep}|{'dev' if dev else 'src'}",
                     schedule=schedule, meta_edits=cohort == "Full")
    lin.T0, lin.C0 = T_START, 0.0
    lin.run()
    s = lin.rows
    print(name, "tasks", len(s), "solved", sum(r["solved"] for r in s), "silent", sum(r["silent"] for r in s), "rounds",
          len(lin.rounds), "L", len(lin.st["L"]), "R", len(lin.st["R"]), "meta adopted",
          sum(m["adopted"] for m in lin.meta_log), "/", len(lin.meta_log), "stop", lin.stop_reason,
          "elapsed", round(lin.elapsed(), 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
