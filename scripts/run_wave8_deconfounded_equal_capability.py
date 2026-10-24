"""Run the Wave-8 deconfounded equal-capability suite and write its JSON artifact."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.mechanism_wave8_deconfounded import run_wave8_deconfounded


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = run_wave8_deconfounded(root / "artifacts")
    print(
        json.dumps(
            {
                "kind": payload["kind"],
                "hash": payload["hash"],
                "gates": payload["gates"],
                "suite_totals": payload["totals"]["suite"],
                "suite_seed_dispersion": payload["seed_dispersion"]["suite"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
