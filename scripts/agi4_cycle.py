"""Phase 4 Stage 1 milestone: ONE COMPLETE OPERATING CYCLE ON REAL .sql / .py FILES (NOT LOCKED; agi4de/dev projects only).
  python scripts/agi4_cycle.py  -> artifacts/agi4_cycle.json, var/agi4_ws/cycle/<project>/workspace/submission/PATCH.diff
Project A (a 3-fault SQLite project, pipeline.sql):
  1 INVESTIGATE  contract, state files, visible batch; lift pipeline.sql with sqlglot into stages; run it on SQLite
  2 ATTEMPT      memory-free search at a deliberately small budget (0.15 s) -> typically unsolved
  3 LEARN FROM FAILURE  refutations and VERIFIED partial repairs (more synthesis checks, no held-back loss) -> P, pi_de;
                 then source-style attempts (explore: an ambiguous repair is submitted for SOURCE feedback) until one is
                 refuted or verified by the hidden-batch evaluator (at most 3); refuted choices update the preferences
  4 REPAIR       a final attempt at the eval budget (2.5 s), no exploration, with the learned memory
  5 VERIFY       de_accept_v2 (held-back fold, probes, closure), then the INDEPENDENT evaluator runs the submitted FILE on 2
                 hidden batches; the patch is written as submission/pipeline.sql + PATCH.diff
  6 ADMIT        the verified operator sequence is admitted as a skill only if it cuts runs on 2 admission projects
Then REUSE: learn from 12 dev projects (Full: failure memory on; Solved-Only: off), test 8 other dev projects (4 SQLite
.sql, 4 Spark .py, k = 2-3) at the eval budgets under Full, Memory-Reset, Solved-Only and Full-minus-skills."""
import copy, json, sys, time
from pathlib import Path
from nexus.de_phase4 import world as W, learner as L, adapter as AD, lineage as LG
ROOT = Path(__file__).resolve().parents[1]
WS = ROOT / "var/agi4_ws/cycle"
CFG = dict(lr=1.0, neg_lr=0.5, partial_lr=0.5, use_failures=True, max_P=80)
B = {"sqlite": 2.5, "spark": 10.0}


def ep(p, de, rt, budget, explore=False):
    rec = L.solve(p, de, rt, budget_s=budget, M=LG.M0, explore=explore)
    ev = W.evaluate(p, rec["code"], rt) if rec["outcome"] == "submitted" else None
    return rec, ev


def summ(rec, ev):
    return dict(outcome=rec["outcome"], status=rec.get("status"), verified=bool(ev and ev["ok"]),
                silent=rec["outcome"] == "submitted" and not (ev and ev["ok"]), runs=rec["runs"], runs_by=rec["runs_by"],
                wall=rec["wall"], edits=rec["edits"], reused=[t["skill"] for t in rec["trace"] if t.get("step") == "reuse"])


def admit(de, sk, projs, rt):
    def judge(m):
        out = []
        for p in projs:
            r, e = ep(p, m, rt, 0.5)
            out.append((bool(e and e["ok"]), r["runs"], r["outcome"] == "submitted" and not (e and e["ok"])))
        return out
    base = judge(copy.deepcopy(de))
    trial = copy.deepcopy(de)
    trial["skills"]["tmp"] = sk
    res = judge(trial)
    sb, sr = sum(x[0] for x in base), sum(x[0] for x in res)
    rb, rr = sum(x[1] for x in base), sum(x[1] for x in res)
    ok = sum(x[2] for x in res) <= sum(x[2] for x in base) and sr >= sb and (sr > sb or rr <= 0.8 * rb)
    if ok:
        de["skills"][f"S{de['next_id']}"] = dict(sk, validated_on=[p["pid"] for p in projs], admission=dict(runs=[rb, rr], solved=[sb, sr]), uses=0)
        de["next_id"] += 1
    return dict(ok=ok, runs_without=rb, runs_with=rr, solved_without=sb, solved_with=sr)


def main():
    sq, spk = W.SQLiteCode(), W.SparkCode()
    t = time.time()
    W.SparkCode.warm()
    out = dict(spark_warm_s=round(time.time() - t, 2))
    A = W.make_project("F2", 3, 53900, "sqlite", WS)
    text, lang, legacy = AD.read_pipeline(A["ws"])
    de, de_so = L.empty_de(), L.empty_de()
    r1, e1 = ep(A, de, sq, 0.15)
    L.learn(de, r1, A, CFG, bool(e1 and e1["ok"]))
    L.learn(de_so, r1, A, dict(CFG, use_failures=False), bool(e1 and e1["ok"]))
    explore_log = []
    for i in range(3):                                # source feedback on project A's sibling instances
        Ai = W.make_project("F2", 3, 53901 + i, "sqlite", WS)
        rx, ex = ep(Ai, de, sq, 0.5, explore=True)
        okx = bool(ex and ex["ok"])
        L.learn(de, rx, Ai, CFG, okx)
        L.learn(de_so, rx, Ai, dict(CFG, use_failures=False), okx)
        explore_log.append(dict(project=Ai["pid"], **summ(rx, ex), choices=rx["choices"], prefs_after=dict(de["prefs"])))
    r2, e2 = ep(A, de, sq, 2.5)
    ok2 = bool(e2 and e2["ok"])
    L.learn(de, r2, A, CFG, ok2)
    L.learn(de_so, r2, A, dict(CFG, use_failures=False), ok2)
    patch_path, diff = AD.write_patch(A["ws"], r2["spec"], lang) if r2["spec"] else (None, "")
    out["A"] = dict(project=A["pid"], faults=A["faults"], contract_notes=json.loads((Path(A["ws"]) / "contract.json").read_text())["notes"],
                    legacy_file=text, lifted_stages={k: legacy.get(k) for k in ("dedup", "filter", "quarantine", "group")},
                    investigate=r1["trace"][0], attempt1=summ(r1, e1), attempt1_refutations=len(r1["refutations"]),
                    attempt1_verified_partials=[p for p in r1["partials"] if p["verified"]][:8], P_after_attempt1=len(de["P"]),
                    weights_after_attempt1={f: v for f, v in de["w"].items() if any(abs(x) > 0 for x in v.values())},
                    source_feedback=explore_log, attempt2=summ(r2, e2), gate=r2["gate"][-1:], hidden=e2, patch_file=str(patch_path),
                    patch_diff=diff)
    if ok2 and r2["edits"]:
        sk = L.skill_from(r2, A)
        adm = [W.make_project("F2", 3, 53910 + i, "sqlite", WS) for i in range(2)]
        out["A"]["admission"] = admit(de, sk, adm, sq)
        admit(de_so, sk, adm, sq)
    print("A", out["A"]["attempt1"]["outcome"], "->", out["A"]["attempt2"]["outcome"], out["A"]["attempt2"]["verified"], out["A"].get("admission"), flush=True)
    # learn from 12 dev projects, then reuse on 8 others
    for i, (f, k) in enumerate([(f, k) for k in (2, 3) for f in W.SOURCE_FAMS]):
        p = W.make_project(f, k, 53920 + i, "sqlite", WS)
        for m, cfg in ((de, CFG), (de_so, dict(CFG, use_failures=False))):
            r, e = ep(p, m, sq, 0.5, explore=True)
            ok = bool(e and e["ok"])
            L.learn(m, r, p, cfg, ok)
            if ok and r["edits"]:
                admit(m, L.skill_from(r, p), [W.make_project(f, k, 53940 + 2 * i + j, "sqlite", WS) for j in range(2)], sq)
    test = {}
    plan = [("F1", 2, "sqlite"), ("F3", 3, "sqlite"), ("F4", 2, "sqlite"), ("F6", 3, "sqlite"),
            ("F2", 2, "spark"), ("F3", 2, "spark"), ("F4", 3, "spark"), ("F5", 2, "spark")]
    for i, (f, k, rtn) in enumerate(plan):
        p = W.make_project(f, k, 53970 + i, rtn, WS)
        rt = spk if rtn == "spark" else sq
        no_sk = copy.deepcopy(de)
        no_sk["skills"] = {}
        conds = {"Full": de, "Memory-Reset": L.empty_de(), "Solved-Only": de_so, "Full-minus-skills": no_sk}
        test[p["pid"]] = {c: summ(*ep(p, copy.deepcopy(m), rt, B[rtn])) for c, m in conds.items()}
        print(p["pid"], {c: (v["verified"], v["silent"], v["runs"], v["wall"]) for c, v in test[p["pid"]].items()}, flush=True)
    agg = {c: dict(verified=sum(v[c]["verified"] for v in test.values()), silent=sum(v[c]["silent"] for v in test.values()),
                   runs=sum(v[c]["runs"] for v in test.values()), wall=round(sum(v[c]["wall"] for v in test.values()), 2))
           for c in ("Full", "Memory-Reset", "Solved-Only", "Full-minus-skills")}
    out["reuse"] = dict(skills_full=list(de["skills"].values()), skills_solved_only=len(de_so["skills"]), P_full=len(de["P"]),
                        prefs_full=de["prefs"], prefs_solved_only=de_so["prefs"], test=test, aggregate=agg)
    print("aggregate", agg)
    (ROOT / "artifacts/agi4_cycle.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
