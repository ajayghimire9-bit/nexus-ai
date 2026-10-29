"""Multi-world campaign PHASE 4 budget guard (NOT LOCKED).  python scripts/agi3_budget.py
Phase 4 cap 1,800 charged s (ledger wall_s of every mi-agi4-* row, charged by scripts/mi_exec.py) out of the carried
mi-track balance (scripts/mi_budget.py). Child CPU seconds are recorded separately in every ledger row. Stage ceilings and
any roll-forward come from artifacts/agi4_allocation.json (a transfer is recorded and committed before the later stage's
outcomes are observed). Stage of a run id: mi-agi-s1-* worlds/substrate/dev checks, mi-agi-src-* source learning,
mi-agi-meta-* improver-vs-improver, mi-agi-eval-* frozen target evaluation, mi-agi-rep-* analysis / protection / report."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mi_budget  # noqa: E402
TOTAL = 1800.0
STAGES = {"s1": ("mi-agi4-s1-",), "src": ("mi-agi4-src-",), "meta": ("mi-agi4-meta-",), "eval": ("mi-agi4-eval-",),
          "rep": ("mi-agi4-rep-",)}


def ceilings():
    a = json.loads((ROOT / "artifacts/agi4_allocation.json").read_text())
    c = dict(a["ceilings"])
    for t in a.get("transfers", []):
        c[t["from"]] -= t["s"]
        c[t["to"]] += t["s"]
    return c


def stage_of(run):
    for s, ps in STAGES.items():
        if run.startswith(ps):
            return s
    raise SystemExit(f"run id {run} has no campaign stage prefix")


def rows():
    return [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]


def used():
    rs = rows()
    u = {s: sum(r.get("wall_s", 0) for r in rs if r.get("run", "").startswith(ps)) for s, ps in STAGES.items()}
    cpu = {s: sum(r.get("child_cpu_s", 0) for r in rs if r.get("run", "").startswith(ps)) for s, ps in STAGES.items()}
    return u, sum(u.values()), cpu


def allow(run, cap, reserved=0.0, reserved_stage=0.0):
    """True iff launching RUN with CAP keeps its stage ceiling and the 1,800 s total (counting caps still running)."""
    s = stage_of(run)
    u, tot, _ = used()
    c = ceilings()
    rem = mi_budget.left()[0]
    return (u[s] + reserved_stage + cap <= c[s] + 1e-6 and tot + reserved + cap <= TOTAL + 1e-6 and rem >= cap + reserved), \
        dict(stage=s, stage_used=round(u[s], 1), stage_ceiling=c[s], campaign_used=round(tot, 1), carried_remaining=round(rem, 1))


if __name__ == "__main__":
    u, tot, cpu = used()
    c = ceilings()
    print(" | ".join(f"{s} {u[s]:.0f}/{c[s]:.0f}s (cpu {cpu[s]:.0f})" for s in STAGES) +
          f" | campaign {tot:.0f}/{TOTAL:.0f}s | carried remaining {mi_budget.left()[0]:.0f}s")
