"""Bounded inspected-source proxy experiment; no environment construction."""
import json
import subprocess
from nexus.evolution2.unified_source_bench import CONFIG, RESULT, ROOT, run, sha

if __name__ == "__main__":
    if RESULT.exists(): raise FileExistsError("preserve_previous_unified_result")
    if subprocess.check_output(["git", "diff", "HEAD", "--name-only"], cwd=ROOT, text=True).strip():
        raise RuntimeError("commit_protocol_and_implementation_first")
    p = run(json.loads(CONFIG.read_text()))
    p["execution_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    p["config_sha256"] = sha(CONFIG)
    p["code_sha256"] = {name: sha(ROOT/name) for name in (
        "src/nexus/evolution2/generated_strategies.py", "src/nexus/evolution2/unified_source_bench.py",
        "src/nexus/evolution2/planner_quality_diagnostic.py", "src/nexus/evolution2/planner_adapter.py",
        "scripts/run_unified_e225_e30.py", "docs/NEXUS_UNIFIED_AUTONOMOUS_LEARNING.md")}
    with RESULT.open("x") as f:
        json.dump(p, f, indent=2, allow_nan=False); f.write("\n")
    print(json.dumps({"complete": p["declared_complete"], "failure": p.get("failure"), "summary": p.get("summary"), "resources": {k:v for k,v in p["resources"].items() if k!="ledger_reports"}}))
