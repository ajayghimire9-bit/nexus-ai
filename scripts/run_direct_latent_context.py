#!/usr/bin/env python3
"""Direct latent-context diagnostic. Source prediction only. No confirmation."""

from __future__ import annotations

import json
import sys

from nexus.world.direct_latent import run_direct_latent


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if phase not in ("dev", "smoke"):
        raise SystemExit("phase must be dev or smoke")
    smoke = phase == "smoke"
    suffix = "_smoke" if smoke else ""
    out = run_direct_latent(
        smoke=smoke,
        selection_path=f"artifacts/direct_latent_selection{suffix}.json",
        audit_path=f"artifacts/direct_latent_audit{suffix}.json",
        plot_path=f"artifacts/direct_latent_curves{suffix}.svg",
    )
    selection = out["selection"]["selection_record"]
    audit = out["audit"] or {}
    print(json.dumps({
        "smoke": smoke,
        "selection_recorded": selection.get("selection_recorded"),
        "chosen_lr": selection.get("chosen_lr"),
        "chosen_updates": selection.get("chosen_updates"),
        "scores": selection.get("scores_angvel_mae"),
        "audit_declared_complete": None if out["audit"] is None else audit.get("declared_complete"),
        "screen": None if out["audit"] is None else audit.get("screen"),
        "classification": None if out["audit"] is None else audit.get("classification"),
        "support_loss_before": None if out["audit"] is None else audit.get("support_loss_before"),
        "support_loss_after": None if out["audit"] is None else audit.get("support_loss_after"),
        "confirm_evaluated": False,
        "control_evaluated": False,
        "wall_clock_s": out["selection"]["wall_clock_s"],
    }, indent=2))


if __name__ == "__main__":
    main()
