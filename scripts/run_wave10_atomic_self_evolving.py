"""Execute the Wave-10 atomic self-evolving operators benchmark."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from nexus.seed.mechanism_wave10_atomic_evolution import run_wave10_atomic_self_evolving


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "artifacts"
    payload = run_wave10_atomic_self_evolving(out_dir)
    summary = {
        "kind": payload["kind"],
        "gates": payload["gates"],
        "suite_totals": payload["totals"]["suite"],
        "hash": payload["hash"],
    }
    print(json.dumps(summary, indent=2))
    if not payload["gates"].get("passed"):
        sys.exit(1)


if __name__ == "__main__":
    main()
