"""Run the equal-inclusive baseline and fresh API-ID retest."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.capability_map import start_map_runtime
from nexus.seed.equal_inclusive import run_equal_inclusive


def main(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    runtime, status = start_map_runtime()
    if runtime is None:
        payload = dict(kind="seed_equal_inclusive", status="unavailable", **status)
        (directory / "seed_equal_inclusive.json").write_text(json.dumps(payload, indent=2))
        print(json.dumps(payload, indent=2))
        return payload
    try:
        payload = run_equal_inclusive(directory, runtime)
        payload["startup"] = status
        (directory / "seed_equal_inclusive.json").write_text(
            json.dumps(payload, indent=2, allow_nan=False, default=str), encoding="utf-8")
        print(json.dumps(dict(
            summary=payload["summary"],
            api_summary=payload["api_summary"],
            verdict=payload["verdict"],
            usage=payload["usage"],
            hash=payload["hash"],
        ), indent=2, default=str))
        return payload
    finally:
        runtime.close()
        leftover = runtime.process
        print(json.dumps(dict(process_cleanup=dict(
            process_is_none=leftover is None,
            process_alive=leftover is not None and leftover.poll() is None,
        ))))


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts" / "seed_equal_inclusive"
    main(target)
