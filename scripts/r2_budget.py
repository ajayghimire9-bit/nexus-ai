"""R2 carried-budget tally (NOT LOCKED). Unit: wall seconds of ledger rows (the grant's accounting unit; CPU figures in results
are performance measurements, not debits). Allowance = the original 17,990 s grant + GRANT-R2-14400S (artifacts/r2_grant.json,
recorded once) = 32,390 s. Debits = every w41*, de-*, de2-*, r1-* and r2-* ledger row (development, learning, validation,
confirmation, analysis).  python scripts/r2_budget.py [needed_s]"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
G = json.loads((ROOT / "artifacts/r2_grant.json").read_text())
START = 3590.0 + 14400.0 + G["amount_s"]
rows = [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]
used = {p: sum(r.get("wall_s", 0) for r in rows if r.get("run", "").startswith(p)) for p in ("w41", "de-", "de2-", "r1-", "r2-")}
left = START - sum(used.values())
print(f"allowance {START:.0f}s ({G['id']} included) | " + " | ".join(f"{p} {v:.0f}s" for p, v in used.items()) + f" | remaining {left:.0f}s")
if len(sys.argv) > 1 and left < float(sys.argv[1]):
    raise SystemExit("insufficient budget")
