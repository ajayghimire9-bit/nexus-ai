"""Run the Wave-9 frozen-fresh 4-method comparison + self-adaptive learner."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.mechanism_wave9_fresh_holdout import run_wave9_frozen_fresh


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = run_wave9_frozen_fresh(root / "artifacts")
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
