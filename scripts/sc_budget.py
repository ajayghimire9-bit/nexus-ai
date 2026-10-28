"""sc track carried-budget tally (NOT LOCKED). No new grant: allowance = 82,790 s (artifacts/ba_grant.json, already recorded);
debits = every w41*, de-*, de2-*, r1-*, r2-*, oop-*, u5-*, t7-*, oc-*, ba-* and sc-* ledger row."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
START = float(json.loads((ROOT / "artifacts/ba_grant.json").read_text())["cumulative_s"])
PREFIXES = ("w41", "de-", "de2-", "r1-", "r2-", "oop-", "u5-", "t7-", "oc-", "ba-", "sc-")


def left():
    rows = [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]
    used = {p: sum(r.get("wall_s", 0) for r in rows if r.get("run", "").startswith(p)) for p in PREFIXES}
    return START - sum(used.values()), used


if __name__ == "__main__":
    rem, used = left()
    print(f"allowance {START:.0f}s | " + " | ".join(f"{p} {v:.0f}s" for p, v in used.items()) + f" | remaining {rem:.0f}s")
