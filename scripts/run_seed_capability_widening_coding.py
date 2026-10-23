"""Run the frozen widening/coding development pilot."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_config():
    return json.loads((ROOT / "configs/seed_capability_widening_coding.json").read_text())


def main(directory: Path, *, include_live_model=False, include_coding=True, include_conversation=True):
    from nexus.seed.capability_widening_coding import (
        historical_artifact_fingerprints, run, summarize,
    )
    from nexus.seed.local_model_runtime import PersistentLocalRuntime, RuntimeConfig, file_hash

    config = load_config()
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    runtime = None
    blocked = None
    started = time.perf_counter()
    model_meta = None
    try:
        if include_live_model:
            model = Path(config["model_path"])
            if not model.is_file():
                blocked = "BLOCKED_MISSING_MODEL"
            elif file_hash(model) != config["model_sha256"]:
                raise ValueError("frozen_model_hash_mismatch")
            else:
                runtime = PersistentLocalRuntime(RuntimeConfig(
                    str(model), max_tokens=128, application_cache=False, request_timeout_s=20,
                ))
                model_meta = runtime.start()
        run(config, records.append, live_runtime=runtime,
            include_coding=include_coding, include_conversation=include_conversation)
    finally:
        if runtime is not None:
            runtime.close()
    summary = summarize(records, config)
    payload = dict(
        study_id=config["id"],
        scientific=False,
        kind="source_development_evaluation_not_confirmation",
        blocked_step=blocked,
        model_metadata=model_meta,
        historical_fingerprints=historical_artifact_fingerprints(ROOT),
        resources=dict(wall_s=round(time.perf_counter() - started, 6)),
        records=records,
        summary=summary,
        learning_to_learn=False,
        agi=False,
        gemini="NOT_RUN",
    )
    artifact = directory / "seed_capability_widening_coding.json"
    raw = directory / "seed_capability_widening_coding_raw.jsonl"
    artifact.write_text(json.dumps(payload, allow_nan=False, indent=2, default=str), encoding="utf-8")
    raw.write_text("\n".join(json.dumps(r, allow_nan=False, default=str) for r in records) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    print("wrote", artifact)
    return artifact


if __name__ == "__main__":
    args = sys.argv[1:]
    target = Path(args[0]) if args and not args[0].startswith("--") else ROOT / "artifacts" / "seed_capability_widening_coding"
    live = "--live-model" in args
    coding = "--skip-coding" not in args
    conversation = "--skip-conversation" not in args
    main(target, include_live_model=live, include_coding=coding, include_conversation=conversation)
