#!/usr/bin/env python3
"""Frozen-dynamics context diagnostic. Source prediction only. No confirmation."""

from __future__ import annotations

import json
import sys

from nexus.world.frozen_dynamics import run_frozen_dynamics


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if phase not in ("dev", "smoke"):
        raise SystemExit("phase must be dev or smoke")
    smoke = phase == "smoke"
    suffix = "_smoke" if smoke else ""
    out = run_frozen_dynamics(
        smoke=smoke,
        selection_path=f"artifacts/frozen_dynamics_selection{suffix}.json",
        audit_path=f"artifacts/frozen_dynamics_audit{suffix}.json",
        plot_path=f"artifacts/frozen_dynamics_prediction{suffix}.svg",
    )
    selection = out["selection"]["selection_record"]
    audit = out["audit"] or {}
    print(json.dumps({
        "smoke": smoke,
        "selection_recorded": selection.get("selection_recorded"),
        "history_updates": selection.get("history_updates"),
        "constant_updates": selection.get("constant_updates"),
        "history_scores": selection.get("history_scores_angvel_mae"),
        "constant_scores": selection.get("constant_scores_angvel_mae"),
        "audit_declared_complete": None if out["audit"] is None else audit.get("declared_complete"),
        "screen": None if out["audit"] is None else audit.get("screen"),
        "classification": None if out["audit"] is None else audit.get("classification"),
        "confirm_evaluated": False,
        "control_evaluated": False,
        "wall_clock_s": out["selection"]["wall_clock_s"],
    }, indent=2))


if __name__ == "__main__":
    main()
