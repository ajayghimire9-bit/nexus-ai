#!/usr/bin/env python3
"""Fresh-physics return split. No architecture change and no control claim."""

from __future__ import annotations

import json

from nexus.world.return_phase import run_return_phase


def main() -> None:
    out = run_return_phase()
    print(json.dumps({
        "diagnostic_complete": out.get("diagnostic_complete"),
        "primary_label": out.get("primary_label"),
        "percentages_reported": out.get("percentages_reported"),
        "identity_ok": out.get("identity_ok"),
        "timed_out": out.get("timed_out"),
        "wall_clock_s": out.get("wall_clock_s"),
        "control_claim": False,
        "is_agi": False,
        "is_learning_to_learn": False,
    }, indent=2))


if __name__ == "__main__":
    main()
