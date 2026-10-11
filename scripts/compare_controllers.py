#!/usr/bin/env python3
"""Equal-budget controller comparison. Prints measured JSON; does not claim a winner."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.config import load_config
from nexus.meta.loop import compare_controllers


def main() -> None:
    cfg = load_config("configs/meta.yaml")
    result = compare_controllers(cfg)
    out = Path("runs") / "controller_compare.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
