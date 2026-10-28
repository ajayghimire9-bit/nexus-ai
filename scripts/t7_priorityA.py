"""Priority A dev reproduction (NOT LOCKED). Known failure classes X3 / X4 (known since the u5 sealed test) on FRESH dev
seeds t7/pdev 12401-12408 (Project4 with split 'test' only to select X3 on even / X4 on odd seeds; 4 domains incl.
energy), plus targeted lifecycle cases. Arms: NEXUS_U5 (frozen u5 learner + platform behaviour) vs NEXUS_Strong (priority
A). Reports coverage (completed), silent errors, escalations, independently correct, queries and CPU together.
python scripts/t7_priorityA.py SEEDS"""
import json, sys
sys.path.insert(0, "scripts")
from u5_run import learners
from nexus import t7_seeds, t7_platform as T7  # noqa: F401
from pathlib import Path
ART = Path(__file__).resolve().parents[1] / "artifacts/t7_dev"
nx, _ = learners()
L = nx["NEXUS_U5"][0]
arms = [T7.NexusArm("NEXUS_U5", L), T7.NexusArmStrong("NEXUS_Strong", L)]
rows = []
for s in [int(x) for x in sys.argv[1].split(",")]:
    for a in arms:
        P = T7.Project(s, "test")
        r = T7.run_project(P, a)
        q = r["cost"]["queries"]
        rows.append(dict(seed=s, domain=P.domain, fault=P.fault, arm=a.name, completed=r["completed"], data_ok=r["data_ok"], silent=r["silent"],
                         human=r["human_repairs"], indep=r["independently_correct"], bad_A=r.get("bad_A"), bad_B=r.get("bad_B"),
                         repairs=r.get("repairs"), cpu=round(r["cost"]["build_cpu_s"] + r["cost"]["ops_cpu_s"], 2), queries=q))
        print(s, P.domain, P.fault, a.name, "indep" if r["independently_correct"] else "-", "silent" if r["silent"] else "", "human", r["human_repairs"],
              "badA", r.get("bad_A"), "badB", r.get("bad_B"), "cpu", rows[-1]["cpu"], flush=True)
(ART / f"pA_{sys.argv[1].replace(',', '_')}.json").write_text(json.dumps(rows, indent=1, default=str))
