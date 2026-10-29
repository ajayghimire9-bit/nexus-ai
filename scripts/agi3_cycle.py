"""Phase 3 Stage 1 milestone: ONE COMPLETE OPERATING CYCLE ON REAL PIPELINES (NOT LOCKED; agi3de/dev projects only,
which are never Stage 4 targets).  python scripts/agi3_cycle.py   -> artifacts/agi3_cycle.json
  1 INVESTIGATE  project A (G1 type-parse migration, level 2, SQLite): read contract / pipeline / state, run the legacy
                 pipeline on the real runtime and record the evidence
  2 ATTEMPT      memory-free best-first repair search
  3 LEARN FROM FAILURE  every failed candidate's error class, failing checks and diff kinds; refutations and partial
                 successes go to P_de (independently observed on the visible batch)
  4 REPAIR       the search continues from the best partial state to a full repair
  5 VERIFY       public checks on the real runtime, then the INDEPENDENT evaluator on 2 hidden batches; the verified
                 operator sequence becomes a candidate skill, admitted only if it lowers search cost on 2 separate
                 admission projects
  6 REUSE        project B: the same family on Spark 4 ANSI (different column names, different engine semantics);
                 project C: a different family (G2 derived metric, level 2) on SQLite; and project D: G2 on Spark.
                 Conditions: Full memory (pi_de + admitted skill + P_de), Memory-Reset (empty), Solved-Only (learned
                 from the solved project only: no refutations / partial records), Full-minus-skill (skill removed).
Then a small development batch: learn from 8 SQLite source-family dev projects, test on 8 other dev projects (4 SQLite,
4 Spark) under the same four conditions (runs = real runtime executions, the cost measure)."""
import copy, json, sys, time
from pathlib import Path
from nexus.campaign3 import de_world as W, de_learner as DL
ROOT = Path(__file__).resolve().parents[1]
WS = ROOT / "var/agi3_ws/cycle"
CFG = dict(lr=1.0, neg_lr=0.5, use_failures=True, max_P=60)


def episode(p, de, rt, budget):
    rec = DL.solve(p, de, rt, budget_s=budget)
    ev = W.evaluate(p, rec["spec"], rt) if rec["solved_visible"] else None
    return rec, ev


def summ(rec, ev):
    return dict(solved_visible=rec["solved_visible"], verified=bool(ev and ev["ok"]), runs=rec["runs"], wall=round(rec["wall"], 3),
                edits=rec["edits"], reused_skill=[t["skill"] for t in rec["trace"] if t.get("step") == "reuse"],
                hidden=ev and ev["fails"])


def admit(de, sk, projs, rt):
    base = [episode(p, de, rt, 0.6) for p in projs]
    trial = copy.deepcopy(de)
    trial["skills"]["tmp"] = sk
    res = [episode(p, trial, rt, 0.6) for p in projs]
    sb = sum(bool(e and e["ok"]) for _, e in base)
    sr = sum(bool(e and e["ok"]) for _, e in res)
    rb, rr = sum(r["runs"] for r, _ in base), sum(r["runs"] for r, _ in res)
    ok = sr >= sb and (sr > sb or rr <= 0.8 * rb)
    if ok:
        de["skills"][f"S{de['next_id']}"] = dict(sk, validated_on=[p["pid"] for p in projs], admission=dict(runs=[rb, rr], solved=[sb, sr]))
        de["next_id"] += 1
    return dict(ok=ok, runs_without=rb, runs_with=rr, solved_without=sb, solved_with=sr)


def conditions(full, solved_only):
    no_skill = copy.deepcopy(full)
    no_skill["skills"] = {}
    return {"Full": full, "Memory-Reset": DL.empty_de(), "Solved-Only": solved_only, "Full-minus-skill": no_skill}


def main():
    sq, sp = W.SQLiteRuntime(), W.SparkRuntime()
    t0 = time.time()
    W.SparkRuntime.warm()
    spark_start = round(time.time() - t0, 1)
    out = dict(spark_session_start_s=spark_start)
    # ---- project A: investigate -> attempt -> learn from failure -> repair -> verify
    A = W.make_project("G1", 2, 51200, "sqlite", WS)
    de, de_so = DL.empty_de(), DL.empty_de()
    rec, ev = episode(A, de, sq, 3.0)
    DL.learn(de, rec, A, CFG, bool(ev and ev["ok"]))
    DL.learn(de_so, rec, A, dict(CFG, use_failures=False), bool(ev and ev["ok"]))
    out["A"] = dict(project=A["pid"], contract=json.loads((Path(A["ws"]) / "contract.json").read_text())["notes"],
                    legacy=dict(failed=rec["start"]["failed"], error=rec["start"].get("error"), features=rec["start_features"]),
                    attempts=len([t for t in rec["trace"] if t["step"] == "attempt"]),
                    first_failures=[t for t in rec["trace"] if t["step"] == "attempt"][:6],
                    refutations=len(rec["refutations"]), partial_successes=rec["partials"][:6], result=summ(rec, ev),
                    P_de_after=len(de["P"]), weights_after={f: v for f, v in de["w"].items() if any(abs(x) > 0 for x in v.values())})
    sk = DL.skill_from(rec, A) if ev and ev["ok"] else None
    out["A"]["candidate_skill"] = sk
    adm_projs = [W.make_project("G1", 2, 51210 + i, "sqlite", WS) for i in range(2)]
    out["A"]["admission"] = admit(de, sk, adm_projs, sq) if sk else None
    admit(de_so, sk, adm_projs, sq) if sk else None
    out["A"]["admitted_skills"] = de["skills"]
    # ---- reuse on other projects
    reuse = {}
    for tag, (fam, lv, s, rtname) in {"B_same_family_spark": ("G1", 2, 51220, "spark"),
                                      "C_other_family_sqlite": ("G2", 2, 51221, "sqlite"),
                                      "D_other_family_spark": ("G2", 2, 51222, "spark")}.items():
        p = W.make_project(fam, lv, s, rtname, WS)
        rt = sp if rtname == "spark" else sq
        reuse[tag] = {cond: summ(*episode(p, copy.deepcopy(m), rt, 6.0 if rtname == "spark" else 2.0))
                      for cond, m in conditions(de, de_so).items()}
        reuse[tag]["project"] = p["pid"]
        print(tag, {k: (v["verified"], v["runs"], v["wall"]) for k, v in reuse[tag].items() if k != "project"}, flush=True)
    out["reuse"] = reuse
    # ---- development batch: learn on 8 SQLite projects, test 8 others (4 SQLite, 4 Spark)
    de_b, de_bs = copy.deepcopy(de), copy.deepcopy(de_so)
    learn_log = []
    for i, fam in enumerate(("G1", "G2", "G3", "G4") * 2):
        p = W.make_project(fam, i % 2 + 1, 51300 + i, "sqlite", WS)
        for m, cfg in ((de_b, CFG), (de_bs, dict(CFG, use_failures=False))):
            r, e = episode(p, m, sq, 2.0)
            ok = bool(e and e["ok"])
            DL.learn(m, r, p, cfg, ok)
            if ok and r["edits"]:
                s2 = DL.skill_from(r, p)
                ap = [W.make_project(fam, i % 2 + 1, 51330 + 2 * i + j, "sqlite", WS) for j in range(2)]
                admit(m, s2, ap, sq)
        learn_log.append(p["pid"])
    test = {}
    for i, fam in enumerate(("G1", "G2", "G3", "G4") * 2):
        rtname = "sqlite" if i < 4 else "spark"
        p = W.make_project(fam, 2 if i % 2 else 1, 51400 + i, rtname, WS)
        rt = sp if rtname == "spark" else sq
        conds = {"Full": de_b, "Memory-Reset": DL.empty_de(), "Solved-Only": de_bs}
        no_sk = copy.deepcopy(de_b)
        no_sk["skills"] = {}
        conds["Full-minus-skill"] = no_sk
        test[p["pid"]] = {c: summ(*episode(p, copy.deepcopy(m), rt, 6.0 if rtname == "spark" else 2.0)) for c, m in conds.items()}
        print(p["pid"], {c: (v["verified"], v["runs"]) for c, v in test[p["pid"]].items()}, flush=True)
    agg = {c: dict(verified=sum(v[c]["verified"] for v in test.values()), runs=sum(v[c]["runs"] for v in test.values()),
                   silent=sum(v[c]["solved_visible"] and not v[c]["verified"] for v in test.values()))
           for c in ("Full", "Memory-Reset", "Solved-Only", "Full-minus-skill")}
    out["dev_batch"] = dict(learned_on=learn_log, skills_full=list(de_b["skills"].values()), skills_solved_only=len(de_bs["skills"]),
                            test=test, aggregate=agg)
    print("aggregate", agg)
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts/agi3_cycle.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
