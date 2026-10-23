"""Run raw-vs-ChatML, equality revision, fresh functions, and discovery."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_config():
    return json.loads((ROOT / "configs/seed_chat_template_repair.json").read_text())


def start_runtime(spec):
    from nexus.seed.local_model_runtime import PersistentLocalRuntime, RuntimeConfig, file_hash
    model = Path(spec["path"])
    if not model.is_file():
        return None, "BLOCKED_MISSING_MODEL", None
    if file_hash(model) != spec["sha256"]:
        raise ValueError("frozen_model_hash_mismatch:" + spec["label"])
    runtime = PersistentLocalRuntime(RuntimeConfig(
        str(model), max_tokens=128, application_cache=False, request_timeout_s=20,
    ))
    return runtime, None, runtime.start()


def main(directory: Path, *, include_live_model=False):
    from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
    from nexus.seed.chat_template_study import begin, record_model, run_discovery, summarize

    config = load_config()
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    started = time.perf_counter()
    blocked = None
    metas = {}
    meter = begin(config, records.append)
    run_discovery(config, records.append)
    if include_live_model:
        qwen, blocked, meta = start_runtime(config["models"]["qwen05"])
        metas["qwen05"] = meta
        best = None
        try:
            if qwen is not None:
                best = record_model(config, records.append, meter, qwen, "qwen05")
        finally:
            if qwen is not None:
                qwen.close()
        if blocked is None:
            coder, blocked_coder, coder_meta = start_runtime(config["models"]["coder15"])
            metas["coder15"] = coder_meta
            if blocked_coder:
                blocked = blocked_coder
            try:
                if coder is not None:
                    record_model(
                        config, records.append, meter, coder, "coder15", best_style=best,
                    )
            finally:
                if coder is not None:
                    coder.close()
    summary = summarize(records, config)
    payload = dict(
        study_id=config["id"],
        scientific=False,
        kind="source_development_evaluation_not_confirmation",
        blocked_step=blocked,
        model_metadata=metas,
        historical_fingerprints=historical_artifact_fingerprints(ROOT),
        resources=dict(wall_s=round(time.perf_counter() - started, 6)),
        records=records,
        summary=summary,
        learning_to_learn=False,
        agi=False,
        gemini="NOT_RUN",
    )
    artifact = directory / "seed_chat_template_repair.json"
    raw = directory / "seed_chat_template_repair_raw.jsonl"
    artifact.write_text(json.dumps(payload, allow_nan=False, indent=2, default=str), encoding="utf-8")
    raw.write_text("\n".join(json.dumps(r, allow_nan=False, default=str) for r in records) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    print("wrote", artifact)
    return artifact


if __name__ == "__main__":
    args = sys.argv[1:]
    target = Path(args[0]) if args and not args[0].startswith("--") else ROOT / "artifacts" / "seed_chat_template_repair"
    main(target, include_live_model="--live-model" in args)
