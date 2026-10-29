"""Phase 10B metered executor (NOT LOCKED; scripts/mi_exec.py with the Phase 10B grant and stage ceilings).
  python scripts/agi10b_exec.py RUN_ID CAP_S -- python args...   (RUN_ID starts with a10b-)
Refuses if the Phase 10B grant / cap / STAGE CEILING cannot cover CAP_S; kills the child at min(CAP_S, 900 s); charges wall time to the ledger with
status COMPLETE / FAILED / CRASHED (exit 3) / TIMEOUT, child CPU (user + sys) and peak RSS; the child's COMPLETE stdout and
stderr are saved to artifacts/mi_logs/<RUN_ID>.log (and echoed)."""
import os, resource, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import agi10b_budget as B  # noqa: E402
from nexus.wave31_evaluator import ledger_append  # noqa: E402


def main():
    run, cap = sys.argv[1], min(900.0, float(sys.argv[2]))
    assert run.startswith("a10b-") and sys.argv[3] == "--"
    ok, info = B.allow(run, cap)
    if not ok:
        raise SystemExit(f"refused by the Phase 10B budget guard: {info}")
    log = ROOT / "artifacts/mi_logs" / f"{run}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.perf_counter()
    with open(log, "w") as fh:
        try:
            p = subprocess.run([sys.executable] + sys.argv[4:], cwd=ROOT, timeout=cap, stdout=fh, stderr=subprocess.STDOUT,
                               env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
            status = "COMPLETE" if p.returncode == 0 else "CRASHED" if p.returncode == 3 else "FAILED"
        except subprocess.TimeoutExpired:
            status = "TIMEOUT"
    w = time.perf_counter() - t0
    r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
    ledger_append(dict(run=run, wall_s=round(w, 3), status=status, cap_s=cap, child_cpu_s=round(cpu, 3),
                       child_maxrss_mb=round(r1.ru_maxrss / 2 ** 20, 1)))
    sys.stdout.write(log.read_text()[-4000:])
    print(f"[{run}] {status} wall {w:.1f}s cpu {cpu:.1f}s | grant remaining {B.remaining():.0f}s")


if __name__ == "__main__":
    main()
