"""Phase 10B budget guard (NOT LOCKED).  python scripts/agi10b_budget.py
Debits: every ledger row whose run id starts with 'a10b-' (charged by scripts/agi9_exec.py), against the Phase 9B pool (artifacts/agi10b_grant.json: +350 s owner buffer + the 862.185 s carried balance, cap 950 s) and the stage ceilings (artifacts/agi10b_allocation.json + committed transfers).
Stages: a10b-s1-* audit / sensitivity / rehearsal, a10b-src-* Stage 2 selection, a10b-eval-* Stage 3 continuation + confirmation,
a10b-rep-* scoring / report. Stage of a run id: a10b-s1-* setup / dev, a10b-src-* source learning, a10b-meta-* improver rollouts,
a10b-eval-* frozen evaluation, a10b-rep-* analysis / protection / report."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
STAGES = {"s1": "a10b-s1-", "s2": "a10b-s2-", "s3": "a10b-s3-", "s4": "a10b-s4-", "s5": "a10b-s5-"}


def alloc():
    return json.loads((ROOT / "artifacts/agi10b_allocation.json").read_text())


def ceilings():
    a = alloc()
    c = dict(a["ceilings"])
    for t in a.get("transfers", []):
        c[t["from"]] -= t["s"]
        c[t["to"]] += t["s"]
    return c


def stage_of(run):
    for s, p in STAGES.items():
        if run.startswith(p):
            return s
    raise SystemExit(f"run id {run} has no Phase 10B stage prefix")


def rows():
    return [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]


def used():
    rs = [r for r in rows() if r.get("run", "").startswith("a10b-")]
    u = {s: sum(r.get("wall_s", 0) for r in rs if r["run"].startswith(p)) for s, p in STAGES.items()}
    cpu = {s: sum(r.get("child_cpu_s", 0) for r in rs if r["run"].startswith(p)) for s, p in STAGES.items()}
    return u, sum(u.values()), cpu


def remaining():
    g = json.loads((ROOT / "artifacts/agi10b_grant.json").read_text())["pool_s"]
    return g - used()[1]


def allow(run, cap, reserved=0.0, reserved_stage=0.0):
    s = stage_of(run)
    u, tot, _ = used()
    c = ceilings()
    total = alloc()["total_cap_s"]
    return (u[s] + reserved_stage + cap <= c[s] + 1e-6 and tot + reserved + cap <= total + 1e-6 and remaining() >= cap + reserved), \
        dict(stage=s, stage_used=round(u[s], 1), stage_ceiling=c[s], phase_used=round(tot, 1), grant_remaining=round(remaining(), 1))


if __name__ == "__main__":
    u, tot, cpu = used()
    c = ceilings()
    print(" | ".join(f"{s} {u[s]:.0f}/{c[s]:.0f}s (cpu {cpu[s]:.0f})" for s in STAGES) +
          f" | phase {tot:.0f}/{alloc()['total_cap_s']}s | grant remaining {remaining():.0f}s")
