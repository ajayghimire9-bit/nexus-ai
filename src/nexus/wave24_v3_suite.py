"""Wave 24 v3 locked evaluation driver (one launch, `run_wave24_agi_gap_suite.py --suite v3`).

Order (cheapest first so a wall-cap stop truncates only the tail, never silently):
  1. procedural Pieces C + D on seeds 301-305 (no LLM);
  2. held-out QuixBugs eval programs (11), test split seed 301: qwen_standalone (unverified),
     verified_sampling (k=2), nexus_cegis (FL + CEGIS k=2 + bounded mutation fallback + twin);
  3. held-out MBPP eval tasks (first N of the outcome-blind hash order "mbpp-v3-eval"):
     standalone (unverified), verified_sampling (k=2), nexus_frozen (greedy + CEGIS, k=2),
     nexus_evolved (dev-trained library + allocator, online growth on public tests only, sleep
     every 8 tasks on the 15% metabolic allowance).
One Qwen engine serves every arm; each arm is charged for every call it uses (cache hits re-charge
the original token counts). The full LLM transcript (request hash -> text + tokens) is saved so
the verifier can re-grade every answer without the model.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEEDS_V3 = (301, 302, 303, 304, 305)
QB_SPLIT_SEED = 301
MBPP_EVAL_SALT = "mbpp-v3-eval"
MBPP_N = 32
K = 2
LIBRARY_ARTIFACT = ROOT / "artifacts" / "wave24_mbpp_dev_library.json"


def _strip(row):
    return {k: v for k, v in row.items()}


def run_v3(*, seeds=SEEDS_V3, mbpp_n=MBPP_N, wall_cap_s=900.0, started=None, engine=None,
           transcript_path=None, log=print):
    from nexus.wave24_code_repair import Program, split_names, split_tests
    from nexus.wave24_helpers import HelperLibrary
    from nexus.wave24_llm_repair import method_nexus_cegis, method_qwen_standalone_v3, method_verified_sampling
    from nexus.wave24_mbpp import (StrategyAllocator, load_tasks, method_nexus_frozen, method_standalone,
                                   method_verified_sampling as mbpp_vs, ordered)
    from nexus.wave24_mbpp_evolve import MbppWakeSleep
    from nexus.wave24_v3_procedural import run_seed

    started = started or time.perf_counter()
    status = "COMPLETE"
    out = dict(suite="v3", seeds=list(seeds), procedural=[], quixbugs=dict(rows=[]), mbpp=dict(rows=[]),
               qb_split_seed=QB_SPLIT_SEED, mbpp_eval_salt=MBPP_EVAL_SALT, k=K)

    def over(margin=0.0):
        return time.perf_counter() - started > wall_cap_s - margin

    # 1. procedural
    for s in seeds:
        if over():
            status = "INCOMPLETE_WALL_CAP"
            break
        t0 = time.perf_counter()
        out["procedural"].append(run_seed(s))
        log(f"[v3] procedural seed {s}: {time.perf_counter() - t0:.1f}s")

    own = engine is None
    if engine is None:
        from nexus.wave24_qwen_engine import QwenEngine
        engine = QwenEngine(max_tokens=384, cache_path=transcript_path)
    try:
        out["llm_backend"] = engine.start()
        # 2. QuixBugs held-out eval programs (384-token completions, as in QuixBugs dev)
        engine.max_tokens = 384
        for name in split_names("eval"):
            if status != "COMPLETE" or over(margin=60):
                status = "INCOMPLETE_WALL_CAP"
                break
            p = Program.load(name)
            pub, hid = split_tests(p, QB_SPLIT_SEED)
            t0 = time.perf_counter()
            rows = [method_qwen_standalone_v3(p, pub, hid, engine),
                    method_verified_sampling(p, pub, hid, engine, k=K),
                    method_nexus_cegis(p, pub, hid, engine, seed=QB_SPLIT_SEED, k=K)]
            for r in rows:
                r.update(program=name, n_public=len(pub), n_hidden=len(hid))
                out["quixbugs"]["rows"].append(r)
            log(f"[v3] quixbugs {name}: {time.perf_counter() - t0:.1f}s "
                + " ".join(f"{r['method']}={int(r['correct'])}/{r['work']}" for r in rows))
        # 3. MBPP held-out eval tasks (320-token completions, as in MBPP dev training)
        engine.max_tokens = 320
        lib_blob = LIBRARY_ARTIFACT.read_text()
        lib_json = json.loads(lib_blob)
        library = HelperLibrary.from_json(lib_json["library"])
        allocator = StrategyAllocator(lib_json["allocator"])
        out["mbpp"]["library_before"] = library.summary()
        ws = MbppWakeSleep(engine, library=library, allocator=allocator, sleep_every=8, k=K, admit="public")
        tasks = ordered(load_tasks("eval"), MBPP_EVAL_SALT)[:mbpp_n]
        out["mbpp"]["task_ids"] = [t.task_id for t in tasks]
        for t in tasks:
            if status != "COMPLETE" or over(margin=30):
                status = "INCOMPLETE_WALL_CAP"
                break
            t0 = time.perf_counter()
            rows = [method_standalone(t, engine), mbpp_vs(t, engine, k=K), method_nexus_frozen(t, engine, k=K)]
            rows.append(ws.wake(t))
            for r in rows:
                out["mbpp"]["rows"].append(_strip(r))
            log(f"[v3] mbpp {t.task_id}: {time.perf_counter() - t0:.1f}s "
                + " ".join(f"{r['method']}={int(r['correct'])}/{r['work']}" for r in rows))
        rep = ws.report()
        out["mbpp"]["evolution"] = dict(sleep_work=rep["sleep_work"], sleeps=rep["sleeps"], bridges=rep["bridges"],
                                        library_after=rep["library"], allocator_after=rep["allocator"])
        out["mbpp"]["library_after_json"] = library.to_json()
        out["mbpp"]["dev_training"] = dict(report={k: v for k, v in lib_json["report"].items()
                                                  if k in ("tasks", "plausible", "correct", "total_work")},
                                           llm=lib_json.get("llm", {}))
        out["llm_telemetry"] = engine.telemetry()
        out["llm_rows"] = list(engine.rows)
    finally:
        if own:
            engine.close()
    out["execution_status"] = status
    return out
