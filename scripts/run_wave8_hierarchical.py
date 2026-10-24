"""Run Wave-8 hierarchical gated evolution. No language-model calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.mechanism_wave8_hierarchical import run_wave8


def main(directory: Path) -> dict:
    payload = run_wave8(directory)
    print(json.dumps({
        "hash": payload.get("hash"),
        "gates": payload.get("gates"),
        "totals": payload.get("totals"),
        "usage": payload.get("usage"),
    }, indent=2, default=str))
    return payload


if __name__ == "__main__":
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/seed_wave8_hierarchical_gated_evolution")
    main(dest)
