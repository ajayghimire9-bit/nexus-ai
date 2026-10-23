"""Offline recovery-policy evaluation. No language-model inference."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.recovery_evaluate import run_offline


def main(directory: Path) -> dict:
    payload = run_offline(directory)
    path = directory / "seed_recovery_policy.json"
    path.write_text(json.dumps(payload, indent=2, allow_nan=False, default=str), encoding="utf-8")
    print(json.dumps(dict(
        status="offline_complete",
        acceptance=payload["acceptance"],
        live=payload["live"]["status"],
        policy_hash=payload["policy_hash"],
        development_summary=payload["development_summary"],
    ), indent=2))
    return payload


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts" / "seed_recovery_policy"
    main(target)
