"""Reconstruct competence metrics. No new inference."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.mechanism_l2l import verify_payload


def tamper_tests(payload: dict) -> dict:
    out = {}
    flipped = deepcopy(payload)
    if flipped.get("development"):
        flipped["development"][0]["remaining"] = ["forged"]
        flipped["development"][0]["success"] = not flipped["development"][0]["success"]
    out["success_flag_tamper_rejected"] = verify_payload(flipped).get("valid") is False
    opened = deepcopy(payload)
    if opened.get("assessment_closed"):
        opened["assessment"] = [{"task_id": "forged", "method": "trained", "transcript": [],
                                 "remaining": [], "split": "within_family"}]
        out["closed_assessment_tamper_rejected"] = verify_payload(opened).get("valid") is False
    else:
        out["closed_assessment_tamper_rejected"] = True
    debit = deepcopy(payload)
    debit.setdefault("usage", {})["frozen_debit_s"] = 1
    out["frozen_debit_rejected"] = verify_payload(debit).get("valid") is False
    return out


def main(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    checked = verify_payload(payload)
    tampers = tamper_tests(payload)
    report = dict(checked, tampers=tampers)
    print(json.dumps(report, indent=2))
    if not checked.get("valid") or not all(tampers.values()):
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    main(Path(sys.argv[1]))
