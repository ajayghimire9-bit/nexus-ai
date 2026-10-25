"""Wave 24 v4 locked evaluation driver (one launch: `run_wave24_agi_gap_suite.py --suite v4`).

Order (cheapest first so a wall-cap stop truncates only the tail, never silently):
  1. Track A procedural, seeds 401-405: source training (INT_SEQ, STR_PARSE) + six cumulative arms
     (+ frozen zero-shot row) on six target families, Popper audit (no LLM);
  2. Track B MBPP: Tycho admission of the v3 dev library on the dev-validation slice (no LLM), then on
     the fresh eval slice: standalone (unverified), verified_sampling (k=2), symbolic (no LLM),
     nexus_v4 (k=2, TwinWakeSleep, sleep every 8 on the 15% metabolic allowance).
One Qwen engine (Metal when the owner grant and Apple Silicon are present, else CPU) serves every arm;
each arm is charged for every call it uses (cache hits re-charge the original token counts).
"""
from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEEDS_V4 = (401, 402, 403, 404, 405)
MBPP_N = 32
N_VAL = 12
K = 2
LIBRARY_ARTIFACT = ROOT / "artifacts" / "wave24_mbpp_dev_library.json"


def peak_rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1024 * 1024) if sys.platform == "darwin" else r / 1024


def run_v4(*, seeds=SEEDS_V4, mbpp_n=MBPP_N, n_val=N_VAL, wall_cap_s=900.0, started=None, engine=None,
           transcript_path=None, mbpp_tasks=None, log=print):
    from nexus.wave24_helpers import HelperLibrary
    from nexus.wave24_mbpp import method_standalone, method_verified_sampling
    from nexus.wave24_v4_agents import run_seed
    from nexus.wave24_v4_code import TwinWakeSleep, eval_tasks, load_library, method_symbolic, tycho_library, val_tasks

    started = started or time.perf_counter()
    status = "COMPLETE"
    out = dict(suite="v4", seeds=list(seeds), procedural=[], mbpp=dict(rows=[]), k=K, resources={})

    def over(margin=0.0):
        return time.perf_counter() - started > wall_cap_s - margin

    # 1. Track A
    t_a = time.perf_counter()
    for s in seeds:
        if over():
            status = "INCOMPLETE_WALL_CAP"
            break
        t0 = time.perf_counter()
        out["procedural"].append(run_seed(s))
        log(f"[v4] procedural seed {s}: {time.perf_counter() - t0:.1f}s")
    out["resources"]["track_a_wall_ms"] = 1000 * (time.perf_counter() - t_a)
    out["resources"]["track_a_peak_rss_mb"] = peak_rss_mb()

    # 2. Track B
    blob = json.loads(LIBRARY_ARTIFACT.read_text())
    library, allocator = load_library(blob)
    rep = blob["report"]
    work_per_solve = rep["total_work"] / max(1, rep["correct"])
    val = val_tasks(n_val)
    gate = tycho_library(library, val, work_per_solve=work_per_solve)
    out["mbpp"]["tycho"] = dict(gate, val_task_ids=[t.task_id for t in val], work_per_solve=work_per_solve)
    out["mbpp"]["library_before"] = library.summary()
    nexus_lib = library if gate["admitted"] else HelperLibrary()
    sym_lib = HelperLibrary.from_json(blob["library"])
    log(f"[v4] tycho library gate: {gate}")
    if status != "COMPLETE":
        out["execution_status"] = status
        return out
    own = engine is None
    if engine is None:
        from nexus.wave24_qwen_engine import QwenEngine
        engine = QwenEngine(max_tokens=320, cache_path=transcript_path)
    t_b = time.perf_counter()
    try:
        out["llm_backend"] = engine.start()
        engine.max_tokens = 320
        ws = TwinWakeSleep(engine, library=nexus_lib, allocator=allocator, sleep_every=8, k=K, admit="public")
        tasks = mbpp_tasks if mbpp_tasks is not None else eval_tasks(mbpp_n)
        out["mbpp"]["task_ids"] = [t.task_id for t in tasks]
        for t in tasks:
            if status != "COMPLETE" or over(margin=30):
                status = "INCOMPLETE_WALL_CAP"
                break
            t0 = time.perf_counter()
            rows = [method_standalone(t, engine), method_verified_sampling(t, engine, k=K),
                    method_symbolic(t, sym_lib), ws.wake(t)]
            for r in rows:
                r["wall_ms"] = 1000 * (time.perf_counter() - t0)
                out["mbpp"]["rows"].append(dict(r))
            log(f"[v4] mbpp {t.task_id}: {time.perf_counter() - t0:.1f}s "
                + " ".join(f"{r['method']}={int(r['correct'])}/{r['work']}" for r in rows))
        rp = ws.report()
        out["mbpp"]["evolution"] = dict(sleep_work=rp["sleep_work"], sleeps=rp["sleeps"], bridges=rp["bridges"],
                                        library_after=rp["library"], allocator_after=rp["allocator"])
        out["mbpp"]["nexus_library_admitted"] = gate["admitted"]
        out["mbpp"]["library_after_json"] = nexus_lib.to_json()
        out["llm_telemetry"] = engine.telemetry()
        out["llm_rows"] = list(engine.rows)
    finally:
        if own:
            engine.close()
        out["resources"]["track_b_wall_ms"] = 1000 * (time.perf_counter() - t_b)
        out["resources"]["peak_rss_mb"] = peak_rss_mb()
    out["execution_status"] = status
    return out
