"""Corrected carried-budget tally (NOT LOCKED). Same 17,990 s grant as scripts/de_budget.py (a protected Stages 1-3 file,
left unchanged), which sums only 'w41' and 'de-' rows and therefore omitted every Stages 4-6 'de2-' row. This sums
w41*, de-*, de2-* and r1-* rows.  python scripts/r1_budget.py [needed_s]"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
START = 3590.0 + 14400.0
rows = [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]
used = {p: sum(r.get("wall_s", 0) for r in rows if r.get("run", "").startswith(p)) for p in ("w41", "de-", "de2-", "r1-")}
left = START - sum(used.values())
print(f"grant {START:.0f}s | " + " | ".join(f"{p} {v:.0f}s" for p, v in used.items()) + f" | remaining {left:.0f}s")
if len(sys.argv) > 1 and left < float(sys.argv[1]):
    raise SystemExit("insufficient budget")
