"""Phase 5 development demonstration (NOT LOCKED; REPLAY of recorded source experience - no engine executes, no target data).
  python scripts/agi5_trace.py  -> artifacts/agi5_demonstration.json
1 CYCLE        the learned procedure on validation projects: evidence -> action -> revision -> verified submission, and a
               justified abstention (stakeholder: undetermined)
2 FAILURE MEMORY  a conflict decision made with the full evidence memory versus the same memory WITHOUT the records that came
               from refuted source submissions (counterfactual): the failure-derived records change the later decision
3 REBINDING    the same stored procedure bound to decision points with different column names and state references"""
import copy, json
from pathlib import Path
from nexus.de_phase5 import investigate as IV, policy_learn as PL
ROOT = Path(__file__).resolve().parents[1]


def proj(pid):
    return dict(pid=pid, ws=str(ROOT / "var"))


def run(d, pid, em, prog, lib):
    st = IV.investigate(proj(pid), PL.Cached(d["val_caches"]), copy.deepcopy(em), d["mem"], prog, lib)
    row = PL.replay_row(proj(pid), d["val_caches"][pid], st)
    return dict(project=pid, decision=st.decision, verified=row["completed"], correct=row["correct"],
                trace=[dict(action=t["action"], obs=t["obs"], decision=t["decision"]) for t in st.trace],
                bindings=[dict(pos=x["pos"], column=x.get("col"), state_ref=x.get("ref"), options=x["options"], via=x["via"]) for x in st.dps])


def main():
    out = {}
    for r in (0, 1, 2):
        d = json.loads((ROOT / f"artifacts/agi5_src/r{r}.json").read_text())
        prog, lib, em = d["policy"], d["library"], d["evidence"]
        val = sorted(d["val_caches"])
        rec = dict(policy=prog, library=lib)
        rec["cycle"] = [x for x in (run(d, p, em, prog, lib) for p in val) if any(t["action"] == "ask" for t in x["trace"])][:3]
        # failure memory counterfactual: drop claim records learned from refuted submissions
        em_cf = copy.deepcopy(em)
        em_cf["claim_outcomes"] = [c for c in em_cf["claim_outcomes"] if c["how"] != "refuted then verified submission"]
        em_cf["trust"] = IV.trust_weights(em_cf)
        changed = []
        for p in val:
            a, b = run(d, p, em, IV.F0, {}), run(d, p, em_cf, IV.F0, {})
            if a["decision"] != b["decision"] or [x["via"] for x in a["bindings"]] != [x["via"] for x in b["bindings"]]:
                changed.append(dict(project=p, with_failure_records=dict(decision=a["decision"], correct=a["correct"], bindings=a["bindings"],
                                                                         resolve=[t for t in a["trace"] if t["action"] == "resolve"]),
                                    without=dict(decision=b["decision"], correct=b["correct"], bindings=b["bindings"],
                                                 resolve=[t for t in b["trace"] if t["action"] == "resolve"])))
        rec["failure_memory"] = dict(n_refuted_records=sum(c["how"] == "refuted then verified submission" for c in em["claim_outcomes"]),
                                     source_records=[c for c in em["claim_outcomes"] if c["how"] == "refuted then verified submission"][:6],
                                     trust_with=em["trust"], trust_without=em_cf["trust"], changed_decisions=changed)
        reb = [run(d, p, em, prog, lib) for p in val]
        rec["rebinding"] = [dict(project=x["project"], call=[t["obs"] for t in x["trace"] if t["action"] == "call"][:1], bindings=x["bindings"],
                                 decision=x["decision"], verified=x["verified"]) for x in reb if x["bindings"]][:4]
        out[f"r{r}"] = rec
        print(f"r{r}", "cycle traces", len(rec["cycle"]), "| failure-derived records", rec["failure_memory"]["n_refuted_records"],
              "decisions changed", len(changed), [(c["project"][-6:], c["with_failure_records"]["correct"], c["without"]["correct"]) for c in changed],
              "| rebinding columns", sorted({b["column"] for x in rec["rebinding"] for b in x["bindings"] if b["column"]}))
    (ROOT / "artifacts/agi5_demonstration.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
