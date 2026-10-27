"""Wave 39 budget tally: the owner grant carried from Wave 38 (21,637 s remaining at 68f0036) minus every w39 ledger row."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
START = 21637.0
used = sum(json.loads(l).get("wall_s", 0) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines()
           if json.loads(l).get("run", "").startswith("w39"))
print(f"wave39 used {used:.0f}s  remaining {START - used:.0f}s")
if len(sys.argv) > 1 and START - used < float(sys.argv[1]):
    raise SystemExit("insufficient budget for this stage")
