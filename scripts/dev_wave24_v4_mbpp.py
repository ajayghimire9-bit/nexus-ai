"""Dev-only check of the v4 Track B pipeline on DEV tasks disjoint from v3 training and the v4 val slice."""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"


def main(n=6, out=None):
    from nexus.wave24_mbpp import load_tasks, ordered
    from nexus.wave24_v4_code import V3_TRAIN_N, V3_TRAIN_SALT, val_tasks
    from nexus.wave24_v4_suite import N_VAL, run_v4
    used = {t.task_id for t in ordered(load_tasks("dev"), V3_TRAIN_SALT)[:V3_TRAIN_N]}
    used |= {t.task_id for t in val_tasks(N_VAL)}
    tasks = ordered([t for t in load_tasks("dev") if t.task_id not in used], "mbpp-v4-devcheck")[:n]
    t0, c0 = time.perf_counter(), time.process_time()
    status = "FAILED"
    try:
        res = run_v4(seeds=(), mbpp_tasks=tasks, log=lambda m: print(m, flush=True))
        status = res["execution_status"]
        tel = res.get("llm_telemetry", {})
        print(json.dumps({k: tel.get(k) for k in ("backend", "calls", "fresh_calls", "generated_tokens",
                                                   "input_tokens", "wall_s", "metal_session_remaining_s")}))
        if out:
            Path(out).write_text(json.dumps(res, default=repr))
    finally:
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run="wave24-v4-dev:mbpp", split="dev", task_ids=[t.task_id for t in tasks],
                                    wall_s=time.perf_counter() - t0, cpu_s=time.process_time() - c0,
                                    status=status)) + "\n")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6, sys.argv[2] if len(sys.argv) > 2 else None)
