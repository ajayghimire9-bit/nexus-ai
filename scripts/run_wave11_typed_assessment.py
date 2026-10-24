#!/usr/bin/env python3
"""Run the Wave-11 typed program enumerator & direct AST interpreter assessment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.mechanism_wave11c_fresh_assessment import run_wave11c_typed_assessment


def main() -> int:
    out_dir = ROOT / "artifacts"
    payload = run_wave11c_typed_assessment(out_dir)
    summary = {
        "kind": payload["kind"],
        "gates": payload["gates"],
        "suite_totals": payload["totals"]["suite"],
        "hash": payload["hash"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if payload["gates"].get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
