"""Dev sanity / crash check of the ba NEXUS_Confirmed platform arm (NOT LOCKED).  python scripts/ba_pdev.py SEED [growth|none] [dev|oc_test]
oc/pdev projects (dev split; D1/D2 faults only); bounded acceptance + (optionally) the promoted learned growth rule.
Writes artifacts/ba_dev/pdev_<SEED>_<mode>.json."""
import json, sys
from pathlib import Path
sys.path.insert(0, "scripts")
from u5_run import learners
from nexus import oc_seeds, ba_seeds, ba_platform as BP  # noqa: F401
import ba_eps
ROOT = Path(__file__).resolve().parents[1]
s, mode = int(sys.argv[1]), (sys.argv[2] if len(sys.argv) > 2 else "growth")
split = sys.argv[3] if len(sys.argv) > 3 else "dev"           # oc_test = a SPENT oc project regenerated in memory (dev now)
nx, _ = learners()
arm = BP.NexusArmBounded("NEXUS_Confirmed", nx["NEXUS_U5"][0])
arm.growth = ba_eps.policy("learned") if mode == "growth" else None
P = BP.Project(s, split)
if split == "oc_test":
    import hashlib
    from nexus import seed_registry as R
    man = json.loads((ROOT / "artifacts/oc_test_vault/MANIFEST.json").read_text())
    assert hashlib.sha256(P.to_json().encode()).hexdigest() == man["files"][f"oc_test/{list(R.REGISTRY[('oc', 'test')]).index(s)}.json"]
r = BP.run_project(P, arm)
keep = {k: r.get(k) for k in ("project", "domain", "fault", "outcome", "data_ok", "bad_A", "bad_B", "silent", "human_repairs",
                              "independently_correct", "repairs", "alarms", "cost", "build")}
(ROOT / f"artifacts/ba_dev/pdev_{s}_{mode}.json").write_text(json.dumps(keep, indent=1, default=str))
print(s, r["domain"], r["fault"], r["outcome"], "OK" if r["data_ok"] else "BAD", "indep" if r["independently_correct"] else "-",
      "silent" if r["silent"] else "", "human", r["human_repairs"], r["cost"])
