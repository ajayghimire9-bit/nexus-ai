"""Run Track A continual waves. No language-model calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.mechanism_continual import run_continual


def main(directory: Path) -> dict:
    payload = run_continual(directory)
    print(json.dumps({
        "hash": payload.get("hash"),
        "inner": payload.get("inner"),
        "competence": payload.get("competence"),
        "assessment_closed": payload.get("assessment_closed"),
        "columns": payload.get("columns"),
        "verdicts": payload.get("verdicts"),
        "usage": payload.get("usage"),
    }, indent=2, default=str))
    return payload


if __name__ == "__main__":
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/seed_mechanism_continual")
    main(dest)
