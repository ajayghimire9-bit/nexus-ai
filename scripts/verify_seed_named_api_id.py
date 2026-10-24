"""Replay saved programs. Do not trust success flags."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.named_api_id import verify_payload


def main(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    checked = verify_payload(payload)
    print(json.dumps(checked, indent=2))
    if not checked.get("valid"):
        raise SystemExit(1)
    return checked


if __name__ == "__main__":
    main(Path(sys.argv[1]))
