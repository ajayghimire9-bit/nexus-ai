"""Run the mismatch challenge. No language-model calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.mechanism_mismatch import run_mismatch


def main(directory: Path, prior: Path | None) -> dict:
    payload = run_mismatch(directory, prior)
    print(json.dumps({
        "hash": payload.get("hash"),
        "diagnosis": payload.get("diagnosis", {}).get("finding"),
        "competence": payload.get("competence"),
        "assessment_closed": payload.get("assessment_closed"),
        "columns": payload.get("columns"),
        "verdict": payload.get("verdict"),
        "usage": payload.get("usage"),
    }, indent=2, default=str))
    return payload


if __name__ == "__main__":
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/seed_mechanism_mismatch")
    prior = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        "artifacts/seed_mechanism_competence/seed_mechanism_competence.json")
    main(dest, prior if prior.is_file() else None)
