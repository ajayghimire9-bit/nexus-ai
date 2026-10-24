"""Run Wave-5 prior and event-record transfer. No language-model calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.mechanism_wave5_prior_transfer import run_wave5


def main(directory: Path) -> dict:
    payload = run_wave5(directory)
    print(json.dumps({
        "hash": payload.get("hash"),
        "gates": payload.get("gates"),
        "totals": {
            key: {
                name: {
                    "useful": cell.get("useful_acquisition"),
                    "tot": cell.get("total_acquisition_work"),
                    "lock": cell.get("false_positive_parity_lock"),
                    "map": cell.get("mapping_correct"),
                }
                for name, cell in (payload.get("totals") or {}).get(key, {}).items()
            }
            for key in (
                "a_related", "a_lookalike", "a_unrelated", "a_oog", "a_retain",
                "b_supplied_related", "b_acquired_related",
            )
        },
        "usage": payload.get("usage"),
    }, indent=2, default=str))
    return payload


if __name__ == "__main__":
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/seed_wave5_prior_and_transfer")
    main(dest)
