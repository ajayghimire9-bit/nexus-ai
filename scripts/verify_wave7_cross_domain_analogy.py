"""Standalone reconstructing verifier. No new inference."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.mechanism_wave7_cross_domain import OPENED_IDS, verify_payload


def main(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    checked = verify_payload(payload)
    tampered = deepcopy(payload)
    rows = tampered.get("assessment") or []
    if rows:
        rows[0]["private_before_lock"] = True
    notes = dict(checked, private_isolation_rejected=verify_payload(tampered).get("valid") is False)
    if any(row["task_id"] in OPENED_IDS for row in payload.get("assessment") or []):
        notes["valid"] = False
    print(json.dumps(notes, indent=2))
    if not checked.get("valid"):
        raise SystemExit(1)
    return notes


if __name__ == "__main__":
    main(Path(sys.argv[1]))
