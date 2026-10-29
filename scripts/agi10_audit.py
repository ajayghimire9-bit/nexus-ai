"""Phase 10 Stage 1A expressiveness audit (NOT LOCKED; development data only) of the 5 Phase 9 development tasks whose
search returned no repair candidate (artifacts/agi9_dev/sensitivity_lite.json). Per task:
  witness   reference-assisted greedy witness (scripts/agi7_diag.witness; reads the hidden truth specs - DEVELOPMENT
            DIAGNOSTIC ONLY, never learner memory): expressible in the operator language at depth d?
  budget    fresh-memory search at the standard work budget (3,000) and at 4x (12,000): does more budget reach a candidate?
  gap       when no witness exists: the truth-spec elements the closest reachable pipeline still lacks
Class: (a) EXPRESSIBLE + budget-limited (more budget finds it) | (a') EXPRESSIBLE, not found even at 4x (ranking) |
(b) NO WITNESS (candidate missing primitive; a greedy-witness failure is not proof) | (c) undecided intent."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agi7_diag as D  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase6 import pipeline6 as P6  # noqa: E402
from nexus.de_phase7 import search7 as S7, world7 as W7  # noqa: E402
from nexus.de_phase9 import blocks9 as B  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
st = B.STRATA
TASKS = [("conflict", st["conflict"][0], 77300), ("conflict", st["conflict"][2], 77302), ("legacy_disagreement", st["legacy_disagreement"][0], 77303),
         ("missing", st["missing"][0], 77305), ("undecided", st["undecided"][1], 77306)]
out = ROOT / "artifacts/agi10_dev/audit_5of9.jsonl"
out.parent.mkdir(parents=True, exist_ok=True)
for stratum, spec, seed in TASKS:
    p = W7.make_project7(spec, seed, ROOT / "var/agi10_ws/dev/audit")
    truths = json.loads((Path(p["hidden_dir"]) / "stakeholder.json").read_text())["truths"]
    wit = D.witness(P6.Inv6(p), p, truths)
    row = dict(stratum=stratum, seed=seed, pid=p["pid"], faults=p["faults"], undecided=bool(p["undecided"]), witness=dict(found=wit["found"], depth=wit["depth"],
               steps=[(s["stage"], s["op"], s["kind"]) for s in wit["steps"]]))
    for wb in (3000, 12000):
        t = time.time()
        r = S7.search(P6.Inv6(p), {}, work_budget=wb, wall_cap=20.0, mode="whole", use_skills=False)
        row[f"search_{wb}"] = dict(outcome=r["outcome"], work=r["work"], wall=round(time.time() - t, 2), verified=D.judge(p, r) if r["outcome"] == "submitted" else None)
    if not wit["found"]:
        inv = P6.Inv6(p)
        specs = list(inv.legacy)
        gap = []
        for k, (sp, tr) in enumerate(zip(specs, truths)):
            for key in sorted(set(sp) | set(tr)):
                if key == "filter":
                    miss = sorted(set(D.conj(tr.get(key))) - set(D.conj(sp.get(key))))
                    if miss:
                        gap.append(dict(stage=k, field="filter", missing_conjuncts=miss))
                elif sp.get(key) != tr.get(key):
                    gap.append(dict(stage=k, field=key, legacy=sp.get(key), truth=tr.get(key)))
        row["gap_vs_legacy"] = gap
    s3, s12 = row["search_3000"]["outcome"], row["search_12000"]["outcome"]
    row["class"] = ("c: undecided intent (no correct submission exists)" if p["undecided"] and not wit["found"] else
                    "a: expressible, budget-limited (4x budget finds a candidate)" if wit["found"] and s3 == "none" and s12 != "none" else
                    "a': expressible, not reached even at 4x budget (search ranking)" if wit["found"] and s12 == "none" else
                    "b: no witness (candidate missing primitive; greedy witness is not proof)" if not wit["found"] else "found at the standard budget now")
    with open(out, "a") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    print(json.dumps({k: row[k] for k in ("pid", "faults", "witness", "search_3000", "search_12000", "class")}, default=str)[:600], flush=True)
