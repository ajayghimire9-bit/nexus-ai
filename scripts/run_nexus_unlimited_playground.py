#!/usr/bin/env python3
"""Bounded curiosity daemon over the persistent Wave24 playground."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from nexus.wave24_unlimited_playground import PersistentNexusBrain, run_playground


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--brain-dir", default=str(ROOT / "artifacts" / "wave24_living_brain"))
    p.add_argument("--dev-sandbox", action="store_true")
    args = p.parse_args(argv)
    if args.epochs < 1:
        raise SystemExit("--epochs must be positive")
    brain_dir = args.brain_dir
    if args.dev_sandbox:
        brain_dir = str(Path(args.brain_dir).parent / "wave24_living_brain_sandbox")
        Path(brain_dir).mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    report = run_playground(brain_dir, epochs=args.epochs)
    report["wall_s"] = time.perf_counter() - started
    print(json.dumps({
        "epochs": report["epochs"],
        "toolbox": report["toolbox"],
        "atp_total_sum": report["atp_total_sum"],
        "normalized_atp_entropy": report["normalized_atp_entropy"],
        "recipes": report["recipes"],
        "solved": [row["solved"] for row in report["reports"]],
        "max_hierarchy_layer": report["max_hierarchy_layer"],
        "constructs": report["constructs"],
        "max_primitive_cost": report["max_primitive_cost"],
        "nursery": report["nursery"],
        "graduated": report["graduated"],
        "false_certificate_count": report["false_certificate_count"],
        "wall_s": report["wall_s"],
        "brain_dir": brain_dir,
    }, indent=2, sort_keys=True))
    PersistentNexusBrain(brain_dir).metabolic.assert_stable()
    if report["false_certificate_count"]:
        raise SystemExit("playground produced a false certificate")
    if args.dev_sandbox and report["wall_s"] >= 0.5:
        raise SystemExit("dev-sandbox playground exceeded 0.5s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
