#!/usr/bin/env python3
"""Receding-horizon diagnostic. No architecture change and no control claim."""

from __future__ import annotations

import json

from nexus.world.receding_horizon import run_receding_horizon


def main() -> None:
    out = run_receding_horizon()
    print(json.dumps({
        "decision_recorded": out.get("decision_recorded"),
        "diagnostic_complete": out.get("diagnostic_complete"),
        "reproduction_ok": out.get("reproduction_ok"),
        "primary_decision": out.get("primary_decision"),
        "replication_decision": out.get("replication_decision"),
        "recommendation": out.get("recommendation"),
        "timed_out": out.get("timed_out"),
        "wall_clock_s": out.get("wall_clock_s"),
        "control_claim": False,
        "is_agi": False,
        "is_learning_to_learn": False,
    }, indent=2))


if __name__ == "__main__":
    main()
