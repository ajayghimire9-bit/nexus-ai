"""Run the locked 2-cell Metal Best-of-4 smoke. Live Metal requires --live-model."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(directory: Path, *, include_live_model: bool = False, sampler=None) -> Path:
    from nexus.seed.function_format import schema_for_format
    from nexus.seed.metal_best_of_4_smoke import (
        build_payload, grant_from_config, load_config, run_cells, start_live_runtime,
    )
    from nexus.seed.metal_model_runtime import (
        MetalGrantEnforcer, bind_live_metal_sampler, load_metal_ledger, write_metal_ledger,
    )

    config = load_config(ROOT / "configs/seed_metal_best_of_4_smoke.json")
    directory.mkdir(parents=True, exist_ok=True)
    ledger_path = directory / "metal_ledger.json"
    grant = grant_from_config(config, ledger_path=str(ledger_path))
    started = time.perf_counter()
    records = []
    blocked = None
    meta = None
    runtime = None
    if include_live_model:
        runtime, blocked, meta = start_live_runtime(config, grant)
        try:
            if runtime is not None:
                enforcer = MetalGrantEnforcer(grant, runtime=runtime)
                code_sampler = bind_live_metal_sampler(runtime, schema_for_format(config["format"]))
                sentence_sampler = bind_live_metal_sampler(runtime, None)
                records = run_cells(
                    config, directory, grant=grant,
                    code_sampler=code_sampler, sentence_sampler=sentence_sampler,
                    enforcer=enforcer,
                )
        finally:
            if runtime is not None:
                runtime.close()
    elif sampler is not None:
        enforcer = MetalGrantEnforcer(grant, hardware_probe=lambda: True, rss_reader=lambda: 128.0)
        records = run_cells(
            config, directory, grant=grant,
            code_sampler=sampler, sentence_sampler=sampler, enforcer=enforcer,
        )
    else:
        blocked = "NOT_RUN_LIVE_MODEL"
        write_metal_ledger(
            ledger_path,
            {
                "kind": "metal_session_ledger",
                "used_s": 0.0,
                "max_session_metal_seconds": grant.max_session_metal_seconds,
                "cpu_ledger_forbidden": True,
                "cpu_ledger_used_s_must_remain": 3564.568,
                "calls": [],
                "peak_rss_mib": None,
            },
        )
    ledger = load_metal_ledger(ledger_path, grant.max_session_metal_seconds)
    payload = build_payload(
        config, records, ledger,
        blocked=blocked, model_metadata=meta,
        wall_s=time.perf_counter() - started,
    )
    artifact = directory / "seed_metal_best_of_4_smoke.json"
    raw = directory / "seed_metal_best_of_4_smoke_raw.jsonl"
    artifact.write_text(json.dumps(payload, allow_nan=False, indent=2, default=str), encoding="utf-8")
    raw.write_text("\n".join(json.dumps(row, allow_nan=False, default=str) for row in records) + "\n", encoding="utf-8")
    print(json.dumps(payload.get("summary") or {}, indent=2, default=str))
    print("wrote", artifact)
    return artifact


if __name__ == "__main__":
    args = sys.argv[1:]
    target = Path(args[0]) if args and not args[0].startswith("--") else ROOT / "artifacts" / "seed_metal_best_of_4_smoke"
    main(target, include_live_model="--live-model" in args)
