"""Phase 7 dev debugging (NOT LOCKED; development projects only)."""
import json, sys, time, cProfile, pstats
from pathlib import Path
from nexus.de_phase6 import pipeline6 as P6
from nexus.de_phase7 import search7 as S7
d = json.load(open("artifacts/agi7_dev/diag.json"))
for i in map(int, sys.argv[1].split(",")):
    row = d["rows"][i]
    pid = row["pid"]
    root = Path("var/agi7_ws/dev/diag") / pid
    p = dict(pid=pid, ws=str(root / "workspace"))
    inv = P6.Inv6(p)
    print(pid, "witness", [(s["stage"], s["op"], s["kind"], s["gain"]) for s in row["witness"]["steps"]])
    ev0 = inv.run(inv.legacy)
    print(" legacy failed", ev0["failed"], "stage_fail", ev0["stage_fail"], "score", round(ev0["score"], 3), "folds", len(inv.folds))
    pr = cProfile.Profile(); pr.enable()
    t = time.time()
    r = S7.search(inv, {}, work_budget=4000, wall_cap=12.0, mode="whole", use_skills=False)
    pr.disable()
    print(" outcome", r["outcome"], "wall", round(time.time() - t, 2), "work", r["work"], r["events"])
    print(" trace", [(x["step"], x.get("status"), x.get("violations"), x.get("error")) for x in r["trace"][1:12]])
    print(" partial", r.get("best_partial"))
    st_ = pstats.Stats(pr); st_.sort_stats("cumulative").print_callers("_find_and_load'"[:0] or "_find_and_load")
