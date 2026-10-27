"""Data-engineering programme budget tally (NOT LOCKED). The owner's data-engineering directive restates the same authorisation
as the Wave 41 directive ("in addition to the remaining ~3,590 s grant, ... up to 14,400 s"). An increase is never inferred
(AGENTS.md), so this is the SAME 17,990 s grant, carried: every w41 ledger row and every de- ledger row is charged to it."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
START = 3590.0 + 14400.0
rows = [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]
w41 = sum(r.get("wall_s", 0) for r in rows if r.get("run", "").startswith("w41"))
de = sum(r.get("wall_s", 0) for r in rows if r.get("run", "").startswith("de-"))
print(f"grant {START:.0f}s | wave41 (paused) used {w41:.0f}s | data-engineering used {de:.0f}s | remaining {START - w41 - de:.0f}s")
if len(sys.argv) > 1 and START - w41 - de < float(sys.argv[1]):
    raise SystemExit("insufficient budget for this stage")
