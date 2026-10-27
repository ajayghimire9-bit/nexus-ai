"""Wave 41 budget tally: 3,590 s carried from Wave 40 (46c3e53) + 14,400 s owner-authorised local M4 compute (Wave 41 prompt,
checkpointed stages) = 17,990 s, minus every w41 ledger row."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
START = 3590.0 + 14400.0
used = sum(json.loads(l).get("wall_s", 0) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines()
           if json.loads(l).get("run", "").startswith("w41"))
print(f"wave41 used {used:.0f}s  remaining {START - used:.0f}s")
if len(sys.argv) > 1 and START - used < float(sys.argv[1]):
    raise SystemExit("insufficient budget for this stage")
