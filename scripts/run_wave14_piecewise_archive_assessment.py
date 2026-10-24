#!/usr/bin/env python3
"""Run the Wave-14 piecewise-archive assessment.

The runner reads ``payload["totals"]["suite"]`` and emits it as
``suite_totals``. It does not import the fresh assessment module at
module-import time so Commit 1 can freeze this file before that module
exists.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.wave14_piecewise_archive_learner import format_runner_summary


def main() -> int:
    from nexus.seed.mechanism_wave14_fresh_assessment import run_wave14_fresh_assessment

    out_dir = ROOT / "artifacts"
    payload = run_wave14_fresh_assessment(out_dir)
    print(json.dumps(format_runner_summary(payload), indent=2, sort_keys=True))
    return 0 if (payload.get("gates") or {}).get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
