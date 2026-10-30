"""Phase 11 budget guard (NOT LOCKED).  python scripts/agi11_budget.py
Debits: every ledger row whose run id starts with 'a11-' (charged by scripts/agi11_exec.py), against the Phase 11 pool
(artifacts/agi11_grant.json: the NEW 1,800 s grant only; hard cap 1,800 charged seconds) and the stage ceilings
(artifacts/agi11_allocation.json: s1 300, s2 450, s3 450, s4 450, s5 150; no transfers).
Charged = wall seconds of each metered process (concurrent processes each charge their own wall); child CPU recorded separately.
Source editing and read-only inspection (reading files, git) are not experiments and are not charged; EVERY execution of Phase 11
code (tests, conformance, timing, generation, search, learning, evaluation, scoring) runs through scripts/agi11_exec.py."""

import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
STAGES = {"s1": "a11-s1-", "s2": "a11-s2-", "s3": "a11-s3-", "s4": "a11-s4-", "s5": "a11-s5-"}


def alloc():
    return json.loads((ROOT / "artifacts/agi11_allocation.json").read_text())


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
    raise SystemExit(f"run id {run} has no Phase 11 stage prefix")


def rows():
    return [json.loads(l) for l in (ROOT / "runs/experimental/wave24-agi/ledger.jsonl").read_text().splitlines() if l.strip()]


def used():
    rs = [r for r in rows() if r.get("run", "").startswith("a11-")]
    u = {s: sum(r.get("wall_s", 0) for r in rs if r["run"].startswith(p)) for s, p in STAGES.items()}
    cpu = {s: sum(r.get("child_cpu_s", 0) for r in rs if r["run"].startswith(p)) for s, p in STAGES.items()}
    return u, sum(u.values()), cpu


def remaining():
    g = json.loads((ROOT / "artifacts/agi11_grant.json").read_text())["pool_s"]
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
