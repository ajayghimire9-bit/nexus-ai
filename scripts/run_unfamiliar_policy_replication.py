"""Run the policy-only unfamiliar-mechanism replication. No language-model calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.mechanism_policy_replication import run_replication


def main(directory: Path) -> dict:
    payload = run_replication(directory)
    print(json.dumps({
        "hash": payload.get("hash"),
        "gates": payload.get("gates"),
        "totals": payload.get("totals"),
        "source_training_work": payload.get("source_training_work"),
        "breakeven": payload.get("breakeven"),
        "bounded_claim": payload.get("bounded_claim"),
        "usage": payload.get("usage"),
    }, indent=2, default=str))
    return payload


if __name__ == "__main__":
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/seed_unfamiliar_policy_replication")
    main(dest)
