#!/usr/bin/env python3
"""Source-prediction optimization diagnostic. No control sweep and no confirmation physics."""

from __future__ import annotations

import json
import sys

from nexus.world.context_optimization import run_context_optimization


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if phase not in ("dev", "smoke"):
        raise SystemExit("phase must be dev or smoke")
    smoke = phase == "smoke"
    out = run_context_optimization(
        smoke=smoke,
        selection_path="artifacts/context_optimization_selection_smoke.json" if smoke else "artifacts/context_optimization_selection.json",
        audit_path="artifacts/context_optimization_audit_smoke.json" if smoke else "artifacts/context_optimization_audit.json",
        plot_path="artifacts/context_optimization_prediction_smoke.svg" if smoke else "artifacts/context_optimization_prediction.svg",
    )
    selection = out["selection"]["selection_record"]
    audit = out["audit"] or {}
    print(json.dumps({
        "smoke": smoke,
        "selection_recorded": selection.get("selection_recorded"),
        "chosen_updates": selection.get("chosen_updates"),
        "mlp_own_chosen_updates": selection.get("mlp_own_chosen_updates"),
        "scores": selection.get("scores_angvel_mae"),
        "audit_declared_complete": None if out["audit"] is None else audit.get("declared_complete"),
        "screen": None if out["audit"] is None else audit.get("screen"),
        "classification": None if out["audit"] is None else audit.get("classification"),
        "confirm_evaluated": False,
        "control_evaluated": False,
        "wall_clock_s": out["selection"]["wall_clock_s"],
    }, indent=2))


if __name__ == "__main__":
    main()
