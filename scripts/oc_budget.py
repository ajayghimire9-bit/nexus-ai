"""ocean-track carried-budget tally (NOT LOCKED). Allowance = 53,990 s + GRANT-NEXUS-OCEAN-META-14400S (artifacts/oc_grant.json,
recorded once) = 68,390 s. Debits = every w41*, de-*, de2-*, r1-*, r2-*, oop-*, u5-*, t7-* and oc-* ledger row."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
G = json.loads((ROOT / "artifacts/oc_grant.json").read_text())
START = float(G["cumulative_s"])
PREFIXES = ("w41", "de-", "de2-", "r1-", "r2-", "oop-", "u5-", "t7-", "oc-")


def left():
    rows = [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]
    used = {p: sum(r.get("wall_s", 0) for r in rows if r.get("run", "").startswith(p)) for p in PREFIXES}
    return START - sum(used.values()), used


if __name__ == "__main__":
    rem, used = left()
    print(f"allowance {START:.0f}s | " + " | ".join(f"{p} {v:.0f}s" for p, v in used.items()) + f" | remaining {rem:.0f}s")
