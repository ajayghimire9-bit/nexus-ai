"""OOP-track carried-budget tally (NOT LOCKED). Unit: wall seconds of ledger rows. Allowance = original 17,990 s +
GRANT-NEXUS-DE-OOP-36000S (artifacts/de_oop_grant.json, recorded once; it subsumes GRANT-R2-14400S) = 53,990 s.
Debits = every w41*, de-*, de2-*, r1-*, r2-* and oop-* ledger row.  python scripts/oop_budget.py [needed_s]"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
G = json.loads((ROOT / "artifacts/de_oop_grant.json").read_text())
START = 3590.0 + 14400.0 + G["amount_s"]
rows = [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]
used = {p: sum(r.get("wall_s", 0) for r in rows if r.get("run", "").startswith(p)) for p in ("w41", "de-", "de2-", "r1-", "r2-", "oop-")}
left = START - sum(used.values())
print(f"allowance {START:.0f}s ({G['id']} included) | " + " | ".join(f"{p} {v:.0f}s" for p, v in used.items()) + f" | remaining {left:.0f}s")
if len(sys.argv) > 1 and left < float(sys.argv[1]):
    raise SystemExit("insufficient budget")
