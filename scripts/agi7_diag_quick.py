"""Phase 7 Stage 1 re-diagnosis after the search fixes (NOT LOCKED; development projects only).
python scripts/agi7_diag_quick.py IDX,IDX,... OUT.json  - archive search (whole, work 1500 / 4000) on listed diag projects."""
import json, sys, time
from pathlib import Path
from nexus.de_phase4 import world as W
from nexus.de_phase6 import pipeline6 as P6
from nexus.de_phase7 import search7 as S7, seeds7 as S, world7 as W7
sys.path.insert(0, "scripts")
import agi7_diag as D  # noqa: E402
if any(i in (9, 18, 19) for i in map(int, sys.argv[1].split(","))):
    W.SparkCode.warm()
base = S.RANGES[("agi7de", "dev")].start
out = []
for i in map(int, sys.argv[1].split(",")):
    p = W7.make_project7(D.DEV_SPECS[i], base + i, Path("var/agi7_ws/dev/diag"))
    row = dict(idx=i, pid=p["pid"])
    for wb in [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "1500,4000").split(",")]:
        t = time.time()
        r = S7.search(P6.Inv6(p), {}, work_budget=wb, wall_cap=10.0, mode="whole", use_skills=False)
        row[f"s7_{wb}"] = dict(outcome=D.judge(p, r), wall=round(time.time() - t, 2), work=r["work"], kinds=r.get("solution_kinds"),
                               expanded=r["events"]["expanded"], path=r.get("path") or (r.get("best_partial") or {}).get("path"))
    out.append(row)
    print(i, p["pid"], {k: (v["outcome"], v["wall"], v["work"], v["expanded"], v["kinds"]) for k, v in row.items() if k.startswith("s7")}, flush=True)
Path(sys.argv[2]).write_text(json.dumps(out, indent=1, default=str))
