"""Synthetic integration audit; no scientific dispatch or model execution."""
import json
import subprocess
import time

from nexus.evolution2.persist_reset_scoring import ROOT,prospective_feedback_integration_audit
from nexus.evolution2.persist_reset_request import file_sha256

if __name__ == "__main__":
    path=ROOT/"artifacts/evolution2_27_feedback_integration.json"
    if path.exists():raise FileExistsError("preserve_previous_e227_audit")
    t0=time.perf_counter()
    try:
        p=prospective_feedback_integration_audit()
        p["execution_sha"]=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
        p["source_sha256"]={name:file_sha256(ROOT/name) for name in (
            "src/nexus/evolution2/persist_reset_scoring.py",
            "src/nexus/evolution2/persist_reset_science.py",
            "src/nexus/evolution2/pendulum_acrobot_protocol_v2_pilot.py",
            "scripts/audit_evolution2_27_feedback_integration.py",
            "docs/NEXUS_E2_27_FEEDBACK_INTEGRATION.md")}
        encoded=json.dumps(p,indent=2,allow_nan=False)+"\n"
    except Exception as e:
        path.write_text(json.dumps({"declared_complete":False,"failure":str(e),"wall_s":time.perf_counter()-t0})+"\n")
        raise
    path.write_text(encoded)
    print("complete",p["declared_complete"],"historical_preserved",p["historical_artifacts_preserved"])
