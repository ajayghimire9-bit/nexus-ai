"""Phase 3 Stage 2 source learning (NOT LOCKED).  python scripts/agi3_source.py COHORT REP BUDGET_S [--dev]
  Full         worlds R, L, P, pi + DE pi_de, L_de, P_de learn; M (Phase 3 M0, incl. de_policy) evolves by full-rollout
               checks; own curriculum over world cells and DE source families
  SolvedOnly   trained as its OWN cohort from t = 0: the identical algorithm (own curriculum, own full-rollout meta
               checks) with failure memory OFF (world P off; DE learner ignores refutations / partial records); paired
               seed streams with Full, free actions
  Fixed-M0     M frozen at M0; replays Full_r<REP>'s learned-task sequence (world tasks and DE projects)
  Random-Proposal  matched random improver (random world and DE proposals, same admission / archive bounds); replays
Seeds: agi3/source 45000 + 1000 * REP (world tasks), agi3de/source 51500 + 300 * REP (DE projects), DE admission
51500 + 300 * REP + 150, admission 48000 + 300 * REP, rollout 49000 + 300 * REP. Output artifacts/agi3_src/."""
import json, random, sys, time
T_START = time.time()
from pathlib import Path  # noqa: E402
from nexus.campaign3 import agent_loop as AL, seeds as SD  # noqa: E402
from nexus.campaign2 import state as ST  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(cohort, rep, budget, *flags):
    rep, budget = int(rep), float(budget)
    dev = "--dev" in flags
    out = ROOT / ("artifacts/agi3_dev/src" if dev else "artifacts/agi3_src")
    name = f"{cohort}_r{rep}"
    if (out / f"{name}.json").exists() and not dev:
        raise SystemExit(f"{name} exists: source lineages are never rerun")
    R = {k: SD.RANGES[k].start for k in SD.RANGES}
    if dev:
        b = R[("agi3", "dev")] + 100 * rep
        ts, as_, rs = range(b, b + 100), range(R[("agi3", "dev")] + 600, R[("agi3", "dev")] + 750), range(R[("agi3", "dev")] + 750, R[("agi3", "dev")] + 900)
        ds, das = range(51000 + 100 + 50 * rep, 51000 + 150 + 50 * rep), range(51000 + 400, 51000 + 480)
    else:
        ts = range(R[("agi3", "source")] + 1000 * rep, R[("agi3", "source")] + 1000 * (rep + 1))
        as_ = range(R[("agi3", "admission")] + 300 * rep, R[("agi3", "admission")] + 300 * rep + 200)
        rs = range(R[("agi3", "rollout")] + 300 * rep, R[("agi3", "rollout")] + 300 * (rep + 1))
        ds = range(R[("agi3de", "source")] + 300 * rep, R[("agi3de", "source")] + 300 * rep + 150)
        das = range(R[("agi3de", "source")] + 300 * rep + 150, R[("agi3de", "source")] + 300 * (rep + 1))
    M = AL.m_random3(random.Random(f"agi3-mrand-{rep}")) if cohort == "Random-Proposal" else AL.M3
    st = ST.empty_state(M)
    schedule = None
    if cohort in ("Fixed-M0", "Random-Proposal"):
        full = json.loads((out / f"Full_r{rep}.json").read_text())
        if not full.get("final"):
            raise SystemExit("the Full lineage of this repetition has not finished")
        schedule = [tuple(x) for x in full["schedule"]]
    lin = AL.Lineage3(name, st, budget, out, ts, as_, rng_key=f"{cohort if cohort != 'SolvedOnly' else 'Full'}|{rep}|{'dev' if dev else 'src'}",
                      schedule=schedule, meta_edits=cohort in ("Full", "SolvedOnly"), use_P=cohort != "SolvedOnly",
                      roll_seeds=rs if cohort in ("Full", "SolvedOnly") else None, de_seeds=ds, de_adm_seeds=das,
                      random_de=cohort == "Random-Proposal", cap_s=AL.SRC_CAP_S)
    lin.T0, lin.C0 = T_START, 0.0
    lin.run()
    s = lin.rows
    de_rows = [r for r in s if r.get("world") == "DE"]
    print(name, "tasks", len(s), "world solved", sum(r["solved"] for r in s if r.get("world") != "DE"), "DE", sum(r["solved"] for r in de_rows),
          "/", len(de_rows), "silent", sum(r["silent"] for r in s), "L", len(lin.st["L"]), "R", len(lin.st["R"]), "P", len(lin.st["P"]),
          "skills", len(lin.st["DE"]["skills"]), "meta adopted", sum(m["adopted"] for m in lin.meta_log), "/", len(lin.meta_log),
          "stop", lin.stop_reason, "elapsed", round(lin.elapsed(), 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
