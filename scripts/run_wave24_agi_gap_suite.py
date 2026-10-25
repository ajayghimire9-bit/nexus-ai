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
SOURCES = ("src/nexus/wave24_domains.py", "src/nexus/wave24_agi_suite.py", "src/nexus/wave24_agi_benchmarks.py",
           "src/nexus/wave24_auto_laws.py", "src/nexus/wave24_open_world_arena.py",
           "scripts/run_wave24_agi_gap_suite.py", "scripts/verify_wave24_agi_gap_suite.py",
           "docs/NEXUS_WAVE24_AGI_GAP_PROTOCOL.md")
WALL_CAP_S = 900.0


def source_hashes():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "wave24_agi_gap_suite.json"))
    ap.add_argument("--seeds", type=int, nargs="*", default=list(EVAL_SEEDS))
    args = ap.parse_args(argv)
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


def _json_default(value):
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    if isinstance(value, bytes):
        return value.decode("latin-1")
    return repr(value)


if __name__ == "__main__":
    raise SystemExit(main())
