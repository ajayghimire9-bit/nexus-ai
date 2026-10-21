"""Readiness entry point. Scientific execution is deliberately unavailable."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nexus.seed.primitive_transfer_v2.readiness import require_execution_ready, review


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--readiness", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = review(root)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not args.readiness:
        require_execution_ready(root)
    return 2  # An incomplete implementation must not exit as a successful run.


if __name__ == "__main__":
    raise SystemExit(main())
