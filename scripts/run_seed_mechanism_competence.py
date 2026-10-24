"""Run the competence-gated mechanism study. No language-model calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.mechanism_l2l import run_study


def main(directory: Path) -> dict:
    payload = run_study(directory)
    print(json.dumps({
        "hash": payload.get("hash"),
        "competence": payload.get("competence"),
        "assessment_closed": payload.get("assessment_closed"),
        "verdict": payload.get("verdict"),
        "development_summary": {
            name: dict(success=cell["success"], mean_work=cell["mean_work"],
                       budget_stop=cell["budget_stop"])
            for name, cell in (payload.get("development_summary") or {}).items()
        },
        "usage": payload.get("usage"),
    }, indent=2, default=str))
    return payload


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/seed_mechanism_competence"))
