#!/usr/bin/env python3
"""Context-adaptation pilot. Confirmation runs only after a passing development gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from nexus.world.confirm_guard import ConfirmationRejected
from nexus.world.context_pilot import run_context_adaptation


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if phase == "dev":
        out = run_context_adaptation(
            phase="dev",
            artifact_path="artifacts/context_adaptation_dev.json",
            plot_path="artifacts/context_adaptation_dev.svg",
        )
        print(json.dumps({"gate": out["gate"], "incomplete": out["incomplete"], "wall_clock_s": out["wall_clock_s"], "ft": out["ft_search"]}, indent=2, default=str))
        return
    if phase != "confirm":
        raise SystemExit(f"unknown phase {phase}")
    try:
        out = run_context_adaptation(
            phase="confirm",
            dev_artifact_path=Path("artifacts/context_adaptation_dev.json"),
            artifact_path="artifacts/context_adaptation_confirm.json",
            plot_path="artifacts/context_adaptation_confirm.svg",
        )
    except ConfirmationRejected as exc:
        raise SystemExit(f"confirmation rejected: {exc}") from exc
    print(json.dumps({"incomplete": out["incomplete"], "deltas": out["deltas_primary_auc"], "wall_clock_s": out["wall_clock_s"]}, indent=2, default=str))


if __name__ == "__main__":
    main()
