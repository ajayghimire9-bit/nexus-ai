#!/usr/bin/env python3
"""Train the v3 MBPP helper library by wake-sleep on the DEV split only (never on eval tasks).

The resulting library (verified solutions, auxiliary helpers, anti-unified helper_k abstractions,
layers, provenance) is written to a JSON artifact with its SHA-256 and is loaded FROZEN-at-start by
the locked v3 evaluation (which then keeps evolving online on the eval stream using public tests
only). Every LLM call and every executed line event of training is charged and reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.wave24_mbpp import load_tasks, ordered  # noqa: E402
from nexus.wave24_mbpp_evolve import MbppWakeSleep  # noqa: E402
from nexus.wave24_qwen_engine import QwenEngine  # noqa: E402

LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"
TRAIN_SALT = "mbpp-v3-train"


def train(n_train, *, k=2, sleep_every=10, engine=None, cache_path=None):
    tasks = ordered(load_tasks("dev"), TRAIN_SALT)[:n_train]
    own = engine is None
    engine = engine or QwenEngine(max_tokens=320, cache_path=cache_path)
    ws = MbppWakeSleep(engine, sleep_every=sleep_every, k=k, admit="all", explore=True)
    try:
        for t in tasks:
            r = ws.wake(t)
            print(f"[train] task {t.task_id}: stage={r['stage']} correct={r['correct']} work={r['work']} "
                  f"library={len(ws.library.helpers)}", flush=True)
        if len(ws.rows) % sleep_every:
            ws.sleep()
        tel = engine.telemetry()
    finally:
        if own:
            engine.close()
    rep = ws.report()
    return dict(split="dev", salt=TRAIN_SALT, n_train=n_train, k=k, sleep_every=sleep_every,
                task_ids=[t.task_id for t in tasks], report=rep, rows=ws.rows, llm=tel,
                library=ws.library.to_json(), allocator=ws.allocator.to_json())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-train", type=int, default=58)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "wave24_mbpp_dev_library.json"))
    ap.add_argument("--cache", default=None)
    a = ap.parse_args(argv)
    t0, c0 = time.perf_counter(), time.process_time()
    status = "FAILED"
    try:
        payload = train(a.n_train, k=a.k, cache_path=a.cache)
        blob = json.dumps(payload, indent=1, sort_keys=True, default=str)
        Path(a.out).write_text(blob)
        digest = hashlib.sha256(blob.encode()).hexdigest()
        print(json.dumps(dict(out=a.out, sha256=digest, report={k: v for k, v in payload["report"].items()
                                                              if k not in ("sleeps", "bridges")}), default=str))
        status = "COMPLETE"
    finally:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(LEDGER, "a") as fh:
            fh.write(json.dumps(dict(run="wave24-v3-train:mbpp-library", split="dev", n_train=a.n_train,
                                     wall_s=time.perf_counter() - t0, cpu_s=time.process_time() - c0,
                                     status=status)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
