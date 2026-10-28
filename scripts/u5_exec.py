"""Run one u5 exploratory / experiment command under the carried budget and charge its wall time to the ledger
(NOT LOCKED).  python scripts/u5_exec.py RUN_ID CAP_S -- python args...   Refuses if the remaining budget < CAP_S;
kills the child at min(CAP_S, 900 s); records COMPLETE / FAILED / TIMEOUT."""
import subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import u5_budget  # noqa: E402
from nexus.wave31_evaluator import ledger_append  # noqa: E402


def main():
    run, cap = sys.argv[1], min(900.0, float(sys.argv[2]))
    assert run.startswith("u5-") and sys.argv[3] == "--"
    rem, _ = u5_budget.left()
    if rem < cap:
        raise SystemExit(f"insufficient budget: {rem:.0f}s left < cap {cap:.0f}s")
    t0 = time.perf_counter()
    try:
        p = subprocess.run([sys.executable] + sys.argv[4:], cwd=ROOT, timeout=cap, env=dict(__import__("os").environ, PYTHONPATH=str(ROOT / "src")))
        status = "COMPLETE" if p.returncode == 0 else "CRASHED" if p.returncode == 3 else "FAILED"
    except subprocess.TimeoutExpired:
        status = "TIMEOUT"
    w = time.perf_counter() - t0
    ledger_append(dict(run=run, wall_s=round(w, 3), status=status, cap_s=cap))
    print(f"[{run}] {status} wall {w:.1f}s | remaining {u5_budget.left()[0]:.0f}s")


if __name__ == "__main__":
    main()
