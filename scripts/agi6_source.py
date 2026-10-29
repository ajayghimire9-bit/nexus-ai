"""Phase 6 Stage 2 source learning (NOT LOCKED).  python scripts/agi6_source.py COHORT REP BUDGET_S [--dev]
Cohorts: Full | SolvedOnly | Fixed | Scrambled (lineage6). Tiers 1-2 only. Every cohort of a repetition sees the same
exogenous project stream (seeds6.lineage_block). Steps, all within BUDGET_S:
  1 training pass (sequential, real execution) with skill invention + corrected admission every 6 projects; Full and
    SolvedOnly evolve M by paired rollouts (one after 12 projects, another after 18 if time allows)
  2 validation caches under the frozen memory (4 search configurations per project)
  3 procedure composition from SEED (Full / SolvedOnly / Scrambled; Fixed keeps F0)
Output artifacts/agi6_src/<COHORT>_r<REP>.json (never rerun; --dev writes artifacts/agi6_dev/)."""
import copy, json, random, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase6 import lineage6 as L6, procedure6 as PR, seeds6 as S6, world6 as W6  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]


def main(cohort, rep, budget, *flags):
    rep, budget = int(rep), float(budget)
    dev = "--dev" in flags
    out = ROOT / ("artifacts/agi6_dev/src" if dev else "artifacts/agi6_src")
    out.mkdir(parents=True, exist_ok=True)
    if (out / f"{cohort}_r{rep}.json").exists() and not dev:
        raise SystemExit("source lineages are never rerun")
    if dev:
        b = S6.RANGES[("agi6de", "dev")].start + 300 * rep
        blk = dict(train=range(b, b + 150), admit=range(b + 150, b + 200), roll=range(b + 200, b + 250))
    else:
        blk = S6.lineage_block(cohort, rep)
    W.SparkCode.warm()
    deadline = T0 + budget - 4.0
    reserve = 0.32 * budget                                     # time kept for validation caches + procedure composition
    mem = L6.empty_memory()
    lin = L6.Lineage(f"{cohort}_r{rep}", cohort, mem, blk["train"], blk["admit"], blk["roll"] if cohort in ("Full", "SolvedOnly") else [],
                     L6.WS / ("dev" if dev else "src") / f"{cohort}_r{rep}", deadline - reserve, f"{cohort}|{rep}|{dev}")
    rng = random.Random(f"agi6-stream|{rep}|{dev}")
    stream = L6.order_stream([L6.SOURCE_SPECS[s % len(L6.SOURCE_SPECS)] for s in blk["train"]], mem["M"], rng)
    seeds = list(blk["train"])
    n = 0
    while lin.left() > 3 and n < len(seeds):
        try:
            lin.learn_project(stream[n], seeds[n])
        except RuntimeError as e:
            lin.log.append(dict(step="build_failed", seed=seeds[n], err=str(e)[:80]))
        n += 1
        if n % 6 == 0:
            lin.invent_and_admit()
        if cohort in ("Full", "SolvedOnly") and n in (12, 18):
            lin.meta_rollout()
    t_train = time.time() - T0
    # validation caches under the frozen memory
    live = PR.Live(lambda p: lin.mem["M"]["src_budget"])
    val, caches = [], {}
    vseeds = list(blk["admit"])[-8:]
    for s in vseeds:
        if time.time() > deadline - 0.12 * budget:
            break
        try:
            p = W6.make_project6(L6.SOURCE_SPECS[(s * 7) % len(L6.SOURCE_SPECS)], s, lin.root / "val")
        except RuntimeError:
            continue
        caches[p["pid"]] = PR.build_entry(p, live, lin.mem)
        val.append(p)
    # procedure composition (from the minimal seed; Fixed keeps F0)
    if cohort == "Fixed":
        prog, lib, plog = PR.F0, {}, []
    else:
        prog, lib, plog = PR.learn_policy(PR.SEED, val, caches, lin.mem, random.Random(f"agi6-pl|{cohort}|{rep}"), cycles=lin.mem["M"]["proc_cycles"],
                                          typed_pairs=lin.mem["M"]["typed_pairs"], history=[r["project"] for r in lin.rows][:40])
    abl = {name: _summ(PR.score(pr, lb, val, caches, lin.mem)) for name, (pr, lb) in
           {"F0": (PR.F0, {}), "learned": (prog, lib), "SEED": (PR.SEED, {})}.items()}
    doc = dict(cohort=cohort, rep=rep, dev=dev, memory=lin.mem, procedure=prog, library=lib, policy_log=plog, meta_log=lin.meta_log,
               rows=lin.rows, log=lin.log, val=[p["pid"] for p in val], val_caches=caches, ablations=abl,
               wall=dict(train=round(t_train, 1), total=round(time.time() - T0, 1)), n_projects=len(lin.rows))
    (out / f"{cohort}_r{rep}.json").write_text(json.dumps(doc, default=list))
    print(f"{cohort}_r{rep}", "projects", len(lin.rows), "verified", sum(r["verified"] for r in lin.rows), "skills", len(lin.mem["de"]["skills"]),
          "trust records", len(lin.mem["trust"]["records"]), "M", {k: v for k, v in lin.mem["M"].items() if v != L6.M0[k]},
          "meta", [(m["edit"], m["adopted"]) for m in lin.meta_log], "| procedure", json.dumps(prog)[:200], "| abl",
          {k: (v["correct"], v["wrong"], v["questions"], v["cost_s"]) for k, v in abl.items()}, "| wall", doc["wall"], flush=True)


def _summ(rows):
    return dict(n=len(rows), correct=sum(r["correct"] for r in rows.values()), completed=sum(r["completed"] for r in rows.values()),
                wrong=sum(r["wrong"] for r in rows.values()), questions=sum(r["questions"] for r in rows.values()),
                cost_s=round(sum(r["cost"]["wall_s"] + 2.0 * r["cost"]["questions"] for r in rows.values()), 2))


if __name__ == "__main__":
    main(*sys.argv[1:])
