#!/usr/bin/env python3
"""Fail if a recorded weight file is missing or has the wrong hash."""

from __future__ import annotations

import json

from nexus.world.checkpoint_integrity import verify_checkpoint_integrity


def main() -> None:
    report = verify_checkpoint_integrity()
    print(json.dumps(report))


if __name__ == "__main__":
    main()
