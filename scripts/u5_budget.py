"""u5-track carried-budget tally (NOT LOCKED). Unit: wall seconds of ledger rows. Allowance = 53,990 s (unchanged:
GRANT-NEXUS-UNIFIED-AGI-36000S is the same allocation as GRANT-NEXUS-DE-OOP-36000S, artifacts/u5_grant.json).
Debits = every w41*, de-*, de2-*, r1-*, r2-*, oop-* and u5-* ledger row.  python scripts/u5_budget.py [needed_s]"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
G = json.loads((ROOT / "artifacts/u5_grant.json").read_text())
START = float(G["cumulative_s"])
PREFIXES = ("w41", "de-", "de2-", "r1-", "r2-", "oop-", "u5-")


def left():
    rows = [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]
    used = {p: sum(r.get("wall_s", 0) for r in rows if r.get("run", "").startswith(p)) for p in PREFIXES}
    return START - sum(used.values()), used


if __name__ == "__main__":
    rem, used = left()
    print(f"allowance {START:.0f}s ({G['id']} = same allocation) | " + " | ".join(f"{p} {v:.0f}s" for p, v in used.items()) + f" | remaining {rem:.0f}s")
    if len(sys.argv) > 1 and rem < float(sys.argv[1]):
        raise SystemExit("insufficient budget")
