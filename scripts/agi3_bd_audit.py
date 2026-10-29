"""Phase 3 evaluator-side B / D audit (NOT LOCKED; agi2/dev instances; reference programs are evaluator-side witnesses,
never placed in any learner's library or archive). Re-uses the Phase 2 audit (scripts/agi2_audit.py) and separates
  1 interpreter expressibility   the reference AST executes and matches the Python reference (all inputs)
  2 enumerator reachability      type rules + lazy lambda pools admit it (cost <= MAX_COST, no hard body cap) and the
                                 focused enumerator generates it (5 s)
  3 budget discoverability       the full-grammar enumerator finds a verified program within the Phase 3 SOURCE cap
                                 (1.5 s) and the evaluation cap (0.6 s)
-> artifacts/agi3_bd_audit.json"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import agi2_audit as A                     # noqa: E402
from nexus.campaign2 import substrate as S, state as ST, seeds as SD  # noqa: E402
from nexus.campaign2.worlds2 import make_task2  # noqa: E402

rows = []
k = 0
for w, fams in (("B", "B1 B2 B3 B4"), ("D", "D1 D2 D3 D4")):
    for f in fams.split():
        for j in range(2):
            s = SD.RANGES[("agi2", "dev")].start + 2 * k + 400
            k += 1
            role = SD.role_of(w, f)
            t = make_task2(w, f, 1, s, role, SD.partners_for(w, f, role))
            ast, note = A.build(t)
            g = S.compile_ast(ast)
            from nexus.campaign.worlds import verify
            expr = verify(t, lambda x: g(tuple(x), (), ()))["ok"]
            costs = ST.pi0()["costs"]
            r = dict(tid=t.tid, descr=t.descr, expressible=expr, cost_pi0=A.cost(ast, costs),
                     max_lambda_cost=max(A.lam_costs(ast, costs), default=0), within_max_cost=A.cost(ast, costs) <= 18)
            prims = sorted({m[1] for m in S.nodes(ast) if m[0] == "p"})
            r["reach_focus_5s"] = A.reach(t, ast, prims, 5.0)
            r["discover_full_1.5s"] = A.reach(t, ast, None, 1.5)
            r["discover_full_0.6s"] = A.reach(t, ast, None, 0.6)
            rows.append(r)
            print(t.tid, t.descr[:30], "expr", expr, "cost", r["cost_pi0"], "focus", bool(r["reach_focus_5s"]["found"]),
                  "1.5s", bool(r["discover_full_1.5s"]["found"]), "lvl", r["discover_full_1.5s"]["level_completed"],
                  "0.6s", bool(r["discover_full_0.6s"]["found"]), flush=True)
(ROOT / "artifacts/agi3_bd_audit.json").write_text(json.dumps(rows, indent=1, default=str))
