"""MI-3 budget guard (NOT LOCKED).  python scripts/mi3_budget.py   (prints the MI-3 tally)
Total MI-3 cap 8,000 charged s (ledger wall_s of every mi-3-* row) out of the carried balance; stage ceilings and any recorded
reallocations come from artifacts/mi3_allocation.json (committed before the later stage's outcomes are observed).
Stage of a run id: mi-3-s1-* / mi-3-diag-* -> s1, mi-3-audit-* -> audit, mi-3-cal-* -> cal, mi-3-disc-* -> disc,
mi-3-win-* -> win, mi-3-rep-* -> rep."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mi_budget  # noqa: E402
TOTAL = 8000.0
STAGES = {"s1": ("mi-3-s1-", "mi-3-diag-"), "audit": ("mi-3-audit-",), "cal": ("mi-3-cal-",), "disc": ("mi-3-disc-",),
          "win": ("mi-3-win-",), "rep": ("mi-3-rep-",)}


def ceilings():
    a = json.loads((ROOT / "artifacts/mi3_allocation.json").read_text())
    c = dict(a["ceilings"])
    for t in a.get("transfers", []):
        c[t["from"]] -= t["s"]
        c[t["to"]] += t["s"]
    return c


def stage_of(run):
    for s, ps in STAGES.items():
        if run.startswith(ps):
            return s
    raise SystemExit(f"run id {run} has no MI-3 stage prefix")


def used():
    rows = [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]
    u = {s: sum(r.get("wall_s", 0) for r in rows if r.get("run", "").startswith(ps)) for s, ps in STAGES.items()}
    return u, sum(u.values())


def allow(run, cap, reserved=0.0, reserved_stage=0.0):
    """True iff launching RUN with CAP keeps the stage ceiling and the 8,000 s MI-3 total (counting caps still running)."""
    s = stage_of(run)
    u, tot = used()
    c = ceilings()
    rem = mi_budget.left()[0]
    return (u[s] + reserved_stage + cap <= c[s] + 1e-6 and tot + reserved + cap <= TOTAL + 1e-6 and rem >= cap + reserved), \
        dict(stage=s, stage_used=round(u[s], 1), stage_ceiling=c[s], mi3_used=round(tot, 1), carried_remaining=round(rem, 1))


if __name__ == "__main__":
    u, tot = used()
    c = ceilings()
    print(" | ".join(f"{s} {u[s]:.0f}/{c[s]:.0f}s" for s in STAGES) + f" | MI-3 total {tot:.0f}/{TOTAL:.0f}s | carried remaining "
          f"{mi_budget.left()[0]:.0f}s")
