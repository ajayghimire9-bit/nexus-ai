"""Run only synthetic normalization bookkeeping. No scientific dispatch."""
import json
import subprocess
import time

from nexus.evolution2.persist_reset_scoring import ROOT,feedback_normalization_boundary_audit
from nexus.evolution2.persist_reset_request import file_sha256

if __name__ == "__main__":
    path=ROOT/"artifacts/evolution2_26_feedback_boundary.json"
    if path.exists():raise FileExistsError("preserve_previous_e226_audit")
    t0=time.perf_counter()
    try:
        p=feedback_normalization_boundary_audit()
        p["execution_sha"]=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
        p["source_sha256"]={name:file_sha256(ROOT/name) for name in (
            "src/nexus/evolution2/pendulum_acrobot_protocol_v2_pilot.py",
            "src/nexus/evolution2/persist_reset_scoring.py",
            "scripts/audit_evolution2_26_feedback_boundary.py",
            "docs/NEXUS_E2_26_FEEDBACK_BOUNDARY.md")}
        encoded=json.dumps(p,indent=2,allow_nan=False)+"\n"
    except Exception as e:
        path.write_text(json.dumps({"declared_complete":False,"failure":str(e),"wall_s":time.perf_counter()-t0})+"\n")
        raise
    path.write_text(encoded)
    print("complete",p["declared_complete"],"same_feedback_weights_choice",p["same_feedback_weights_choice"])
