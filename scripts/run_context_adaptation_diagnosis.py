#!/usr/bin/env python3
"""Context-adaptation diagnosis. Development only. Does not evaluate confirmation physics."""

from __future__ import annotations

import json
import sys

from nexus.world.context_diagnosis import run_context_diagnosis


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if phase not in ("dev", "smoke"):
        raise SystemExit("phase must be dev or smoke; confirmation is not part of this milestone")
    smoke = phase == "smoke"
    out = run_context_diagnosis(
        smoke=smoke,
        artifact_path="artifacts/context_adaptation_diagnosis_smoke.json" if smoke else "artifacts/context_adaptation_diagnosis.json",
        plot_prediction="artifacts/context_adaptation_diagnosis_prediction_smoke.svg" if smoke else "artifacts/context_adaptation_diagnosis_prediction.svg",
        plot_control="artifacts/context_adaptation_diagnosis_control_smoke.svg" if smoke else "artifacts/context_adaptation_diagnosis_control.svg",
    )
    summary = out.get("summary", {})
    print(json.dumps({
        "smoke": out["smoke"],
        "incomplete": out["incomplete"],
        "declared_complete": out["declared_complete"],
        "wall_clock_s": out["wall_clock_s"],
        "confirm_evaluated": out["protocol"]["confirm_evaluated"],
        "implementation_sha": out["protocol"]["implementation_sha"],
        "control_auc": summary.get("control_auc_0_128"),
        "deltas": summary.get("deltas"),
        "interpretation": summary.get("interpretation"),
        "resources": out["resources"],
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
