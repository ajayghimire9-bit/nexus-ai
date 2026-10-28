"""oc revision-1 dev check (NOT LOCKED): frozen NEXUS_Confirmed vs NEXUS_Certified on 8 ENERGY dev projects (oc/edev,
seed % 4 == 3, D1/D2), paired. Never uses validation data."""
import json, sys
sys.path.insert(0, "scripts")
from u5_run import learners
from nexus import oc_seeds, oc_platform as OP, seed_registry as R  # noqa: F401
from pathlib import Path
nx, _ = learners()
L = nx["NEXUS_U5"][0]
seeds = [s for s in R.REGISTRY[("oc", "edev")] if s % 4 == 3][int(sys.argv[1]):int(sys.argv[2])]
rows = []
for s in seeds:
    for a in (OP.NexusArmStrong("NEXUS_Confirmed", L), OP.NexusArmCertified("NEXUS_Certified", L)):
        r = OP.run_project(OP.Project(s, "dev"), a)
        rows.append(dict(seed=s, arm=a.name, indep=r["independently_correct"], silent=r["silent"], human=r["human_repairs"], completed=r["completed"],
                         mq=r["cost"]["queries"]["mq"], cpu=round(r["cost"]["build_cpu_s"] + r["cost"]["ops_cpu_s"], 1)))
        print(rows[-1], flush=True)
Path(f"artifacts/oc_dev/rev1_{sys.argv[1]}.json").write_text(json.dumps(rows, indent=1))
