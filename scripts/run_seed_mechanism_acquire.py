"""Run the acquisition study. No language-model calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.mechanism_acquire import run_acquire_study


def main(directory: Path) -> dict:
    payload = run_acquire_study(directory)
    print(json.dumps({
        "hash": payload.get("hash"),
        "synthesis_gate": payload.get("synthesis_gate"),
        "competence": payload.get("competence"),
        "assessment_closed": payload.get("assessment_closed"),
        "columns": payload.get("columns"),
        "verdict": payload.get("verdict"),
        "usage": payload.get("usage"),
    }, indent=2, default=str))
    return payload


if __name__ == "__main__":
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/seed_mechanism_acquire")
    main(dest)
