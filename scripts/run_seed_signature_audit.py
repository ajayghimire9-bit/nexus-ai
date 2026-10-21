"""Run the Step 1 source-only input-output signature audit."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.seed.signature_audit import run_source_only_signature_audit

if __name__ == "__main__":
    res = run_source_only_signature_audit(ROOT)
    (ROOT / "artifacts/seed_signature_audit.json").write_text(
        json.dumps(res, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in res.items() if k != "source_program_signatures"}, indent=2))
