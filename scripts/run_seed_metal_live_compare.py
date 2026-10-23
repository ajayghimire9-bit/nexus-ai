"""Run the frozen independent-vs-revision comparison. Live Metal needs --live-model."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(directory: Path, *, include_live_model: bool = False, code_sampler=None, sentence_sampler=None) -> Path:
    from nexus.seed.capability_evidence import digest
    from nexus.seed.function_format import schema_for_format
    from nexus.seed.metal_live_compare import (
        AssistantCost, grant_from_config, load_config, pull_token_counts,
        run_comparison, start_live_runtime, summarize,
    )
    from nexus.seed.metal_model_runtime import (
        MetalGrantEnforcer, bind_live_metal_sampler, load_metal_ledger, write_metal_ledger,
    )
    from nexus.seed.metal_sampling_audit import bind_audited_sampler

    config = load_config(ROOT / "configs/seed_metal_live_compare.json")
    directory.mkdir(parents=True, exist_ok=True)
    ledger_path = directory / "metal_ledger.json"
    grant = grant_from_config(config, ledger_path=str(ledger_path))
    clock = AssistantCost()
    started = time.perf_counter()
    records = []
    blocked = None
    meta = None
    runtime = None
    if include_live_model:
        begin = time.perf_counter()
        runtime, blocked, meta = start_live_runtime(config, grant)
        clock.startup_s += time.perf_counter() - begin
        try:
            if runtime is not None:
                enforcer = MetalGrantEnforcer(grant, runtime=runtime)
                code_live = bind_audited_sampler(runtime, schema_for_format(config["format"]))
                sent_live = bind_audited_sampler(runtime, None)
                records = run_comparison(
                    config, directory, grant=grant,
                    code_sampler=code_live, sentence_sampler=sent_live,
                    enforcer=enforcer, clock=clock,
                )
                inp, gen = pull_token_counts(runtime)
                clock.input_tokens = inp
                clock.generated_tokens = gen
        finally:
            begin = time.perf_counter()
            if runtime is not None:
                runtime.close()
            clock.teardown_s += time.perf_counter() - begin
    elif code_sampler is not None and sentence_sampler is not None:
        enforcer = MetalGrantEnforcer(grant, hardware_probe=lambda: True, rss_reader=lambda: 128.0)
        records = run_comparison(
            config, directory, grant=grant,
            code_sampler=code_sampler, sentence_sampler=sentence_sampler,
            enforcer=enforcer, clock=clock,
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
    wall = time.perf_counter() - started
    ledger = load_metal_ledger(ledger_path, grant.max_session_metal_seconds)
    clock.grant_charged_s = float(ledger.get("used_s") or 0.0)
    summary = summarize(records, ledger, clock, wall) if records else dict(
        cpu_ledger_used_s=3564.568,
        cpu_ledger_debit_s=0,
        stubbed_call2_vs_call4_is_not_live_advantage=True,
        live_advantage_claimed=False,
        assistant_cost=clock.as_dict(wall),
    )
    payload = dict(
        study_id=config["id"],
        scientific=False,
        kind=config["kind"],
        config_hash=digest(config),
        blocked_step=blocked,
        model_metadata=meta,
        records=records,
        metal_ledger=ledger,
        summary=summary,
        resources=dict(wall_s=round(wall, 6), assistant_cost=clock.as_dict(wall)),
        learning_to_learn=False,
        agi=False,
    )
    artifact = directory / "seed_metal_live_compare.json"
    artifact.write_text(json.dumps(payload, allow_nan=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    print("wrote", artifact)
    return artifact


if __name__ == "__main__":
    args = sys.argv[1:]
    target = Path(args[0]) if args and not args[0].startswith("--") else ROOT / "artifacts" / "seed_metal_live_compare"
    main(target, include_live_model="--live-model" in args)
