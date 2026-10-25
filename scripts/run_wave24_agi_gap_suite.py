#!/usr/bin/env python3
"""Run the predeclared Wave 24 eight-gap suite on the locked evaluation seeds (one launch).

Protocol: docs/NEXUS_WAVE24_AGI_GAP_PROTOCOL.md. Standing local CPU grant
(<= 900 s per experiment). Raw rows are written; gates are recomputed by
scripts/verify_wave24_agi_gap_suite.py. Refuses to overwrite a recorded result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from nexus.wave24_agi_benchmarks import (  # noqa: E402
    gap1_full_cost, gap2_zero_shot, gap3_meta, gap4_closed_loop, gap5_robustness,
    gap7_world_model, gap8_grounding_planning, gap8_intrinsic_goals,
)
from nexus.wave24_open_world_arena import run_open_world_arena  # noqa: E402
from nexus.wave24_quotient_core import WorkMeter  # noqa: E402

EVAL_SEEDS = (101, 102, 103, 104, 105)
EVAL_SEEDS_V2 = (201, 202, 203, 204, 205)
SOURCES = ("src/nexus/wave24_domains.py", "src/nexus/wave24_agi_suite.py", "src/nexus/wave24_agi_benchmarks.py",
           "src/nexus/wave24_auto_laws.py", "src/nexus/wave24_open_world_arena.py",
           "scripts/run_wave24_agi_gap_suite.py", "scripts/verify_wave24_agi_gap_suite.py",
           "docs/NEXUS_WAVE24_AGI_GAP_PROTOCOL.md", "src/nexus/wave24_skeletons.py", "src/nexus/wave24_wake_sleep.py",
           "src/nexus/wave24_semantic_spec.py", "src/nexus/wave24_code_repair.py", "src/nexus/wave24_agi_benchmarks_v2.py",
           "fixtures/quixbugs/split.json")
WALL_CAP_S = 900.0


def source_hashes():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "wave24_agi_gap_suite.json"))
    ap.add_argument("--seeds", type=int, nargs="*")
    ap.add_argument("--suite", choices=("v1", "v2", "v3"), default="v1")
    ap.add_argument("--mbpp-n", type=int, default=None)
    args = ap.parse_args(argv)
    if args.suite == "v3":
        return main_v3(args)
    if args.seeds is None:
        args.seeds = list(EVAL_SEEDS_V2 if args.suite == "v2" else EVAL_SEEDS)
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"{out} already recorded; the locked evaluation is one-use")
    started, cpu0 = time.perf_counter(), time.process_time()
    hashes = source_hashes()
    payload = dict(schema="wave24_agi_gap_suite_v1", seeds=args.seeds, source_hashes=hashes,
                   python=sys.version, platform=platform.platform(), gaps={})
    gaps = dict(gap1=gap1_full_cost, gap2=gap2_zero_shot, gap3=gap3_meta, gap4=gap4_closed_loop,
                gap5=gap5_robustness, gap7=gap7_world_model, gap8_grounding=gap8_grounding_planning,
                gap8_goals=gap8_intrinsic_goals)
    for name, fn in gaps.items():
        payload["gaps"][name] = []
        for seed in args.seeds:
            if time.perf_counter() - started > WALL_CAP_S:
                payload["execution_status"] = "INCOMPLETE_WALL_CAP"
                break
            payload["gaps"][name].append(fn(seed))
    if args.suite == "v2":
        from nexus.wave24_agi_benchmarks_v2 import GAPS_V2
        payload["suite"] = "v2"
        payload["gaps_v2"] = {}
        for name, fn in GAPS_V2.items():
            payload["gaps_v2"][name] = []
            for seed in args.seeds:
                if time.perf_counter() - started > WALL_CAP_S:
                    payload["execution_status"] = "INCOMPLETE_WALL_CAP"
                    break
                payload["gaps_v2"][name].append(fn(seed))
    payload["open_world_arena"] = run_open_world_arena(WorkMeter(limit=8_000_000, wall_limit=8.))
    payload.setdefault("execution_status", "COMPLETE")
    payload["wall_s"] = time.perf_counter() - started
    payload["cpu_s"] = time.process_time() - cpu0
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, default=_json_default, sort_keys=True)
    out.write_text(text)
    ledger = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(json.dumps(dict(run="wave24-agi-gap-suite", seeds=args.seeds, wall_s=payload["wall_s"],
                                cpu_s=payload["cpu_s"], output_sha256=hashlib.sha256(text.encode()).hexdigest(),
                                status=payload["execution_status"])) + "\n")
    print(json.dumps(dict(status=payload["execution_status"], wall_s=payload["wall_s"], out=str(out),
                          sha256=hashlib.sha256(text.encode()).hexdigest()), indent=2))
    return 0 if payload["execution_status"] == "COMPLETE" else 2


SOURCES_V3 = ("src/nexus/wave24_v3_suite.py", "src/nexus/wave24_v3_procedural.py", "src/nexus/wave24_mbpp.py",
              "src/nexus/wave24_helpers.py", "src/nexus/wave24_mbpp_evolve.py", "src/nexus/wave24_llm_repair.py",
              "src/nexus/wave24_qwen_engine.py", "src/nexus/wave24_code_repair.py", "src/nexus/wave24_agi_suite.py",
              "src/nexus/wave24_domains.py", "src/nexus/wave24_auto_laws.py", "fixtures/mbpp/split.json",
              "fixtures/mbpp/mbpp.jsonl", "fixtures/quixbugs/split.json", "artifacts/wave24_mbpp_dev_library.json",
              "scripts/run_wave24_agi_gap_suite.py", "scripts/verify_wave24_agi_gap_suite.py",
              "scripts/train_wave24_mbpp_library.py", "docs/NEXUS_WAVE24_AGI_GAP_PROTOCOL.md")
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"
SESSION_CAP_S = 3600.0


def session_remaining():
    if not LEDGER.exists():
        return SESSION_CAP_S
    used = sum(float(json.loads(l).get("wall_s") or 0) for l in LEDGER.read_text().splitlines() if l.strip())
    return SESSION_CAP_S - used


def main_v3(args):
    from nexus.wave24_v3_suite import MBPP_N, SEEDS_V3, run_v3
    seeds = args.seeds or list(SEEDS_V3)
    out = Path(args.out if args.out != str(ROOT / "artifacts" / "wave24_agi_gap_suite.json")
               else ROOT / "artifacts" / "wave24_agi_gap_suite_v3.json")
    if out.exists():
        raise SystemExit(f"{out} already recorded; the locked evaluation is one-use")
    transcript = out.with_name(out.stem + "_llm_transcript.jsonl")
    if transcript.exists():
        raise SystemExit(f"{transcript} exists; refusing to reuse cached completions in a locked run")
    remaining = session_remaining()
    cap = min(WALL_CAP_S, remaining - 15.0)
    if cap < 60:
        raise SystemExit(f"session experiment allowance exhausted (remaining {remaining:.0f}s)")
    started, cpu0 = time.perf_counter(), time.process_time()
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES_V3}
    payload = dict(schema="wave24_suite_v3", source_hashes=hashes, python=sys.version, platform=platform.platform(),
                   wall_cap_s=cap, session_remaining_at_start_s=remaining)
    status = "FAILED"
    try:
        res = run_v3(seeds=seeds, mbpp_n=args.mbpp_n or MBPP_N, wall_cap_s=cap, started=started,
                     transcript_path=str(transcript), log=lambda m: print(m, flush=True))
        payload.update(res)
        status = res["execution_status"]
    finally:
        payload["execution_status"] = status
        payload["wall_s"] = time.perf_counter() - started
        payload["cpu_s"] = time.process_time() - cpu0
        if transcript.exists():
            payload["llm_transcript_sha256"] = hashlib.sha256(transcript.read_bytes()).hexdigest()
        out.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, default=_json_default, sort_keys=True)
        out.write_text(text)
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run="wave24-agi-gap-suite-v3", seeds=seeds, wall_s=payload["wall_s"],
                                    cpu_s=payload["cpu_s"], output_sha256=hashlib.sha256(text.encode()).hexdigest(),
                                    status=status)) + "\n")
    print(json.dumps(dict(status=status, wall_s=payload["wall_s"], out=str(out),
                          sha256=hashlib.sha256(text.encode()).hexdigest()), indent=2))
    return 0 if status == "COMPLETE" else 2


def _json_default(value):
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    if isinstance(value, bytes):
        return value.decode("latin-1")
    return repr(value)


if __name__ == "__main__":
    raise SystemExit(main())
