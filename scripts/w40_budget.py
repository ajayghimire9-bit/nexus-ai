"""Wave 40 budget tally: the owner grant carried from Wave 39 (12,924 s remaining at 199a7bf) minus every w40 ledger row."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
START = 12924.0
used = sum(json.loads(l).get("wall_s", 0) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines()
           if json.loads(l).get("run", "").startswith("w40"))
print(f"wave40 used {used:.0f}s  remaining {START - used:.0f}s")
if len(sys.argv) > 1 and START - used < float(sys.argv[1]):
    raise SystemExit("insufficient budget for this stage")
