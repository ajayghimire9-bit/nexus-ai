"""Write artifacts/x7_freeze.json (NOT LOCKED): sha256 of every file the x7 evaluation executes + the pre-registered groups per
one-use split. x7_run refuses val / val_b / test if any hash differs."""
import hashlib, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FILES = ["src/nexus/" + f for f in ("x7_expr.py", "x7_contract.py", "x7_mapping.py", "x7_regsearch.py", "x7_platform.py", "x7_seeds.py",
         "sc_platform.py", "sc_contract.py", "sc_mapping.py", "sc_seeds.py", "ba_platform.py", "ba_accept.py", "ba_learn.py", "ba_seeds.py",
         "oc_platform.py", "oc_learner.py", "t7_platform.py", "t7_repair.py", "t7_world.py", "u5_platform.py", "u5_statesplit.py",
         "u5_stateful.py", "seed_registry.py")] + \
    ["scripts/" + f for f in ("x7_run.py", "x7_exec.py", "x7_budget.py", "x7_score.py", "x7_seal.py", "ba_eps.py", "u5_run.py")] + \
    ["artifacts/ba_dev/records_bounded.jsonl"]
rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
out = dict(commit=rev, files={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in FILES},
           groups={"x7_val": ["L", "F"], "x7_val_b": ["L", "F"], "x7_test": ["L", "H", "S", "SC", "F"]},
           candidate="Expression_Learned (A) = NexusArmX7(growth=learned, mapping=expression, prune=True, learner_fix=True)",
           revision=len(sys.argv) > 1 and sys.argv[1] == "--revision")
(ROOT / "artifacts/x7_freeze.json").write_text(json.dumps(out, indent=1, sort_keys=True))
print(len(FILES), "files frozen at", rev)
