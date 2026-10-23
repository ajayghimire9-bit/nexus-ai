"""Run the 4-bottleneck architecture & live-model benchmark (seed-bottleneck-breaker-1)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_config() -> dict:
    return json.loads((ROOT / "configs/seed_bottleneck_breaker.json").read_text(encoding="utf-8"))


def main(directory: Path, *, include_live_model: bool = False) -> Path:
    from nexus.seed.bottleneck_breaker import run, summarize
    from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
    from nexus.seed.local_model_runtime import file_hash

    config = load_config()
    directory.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    blocked = None
    started = time.perf_counter()

    if include_live_model:
        for key, mspec in (config.get("models") or {}).items():
            mpath = Path(mspec["model_path"]).expanduser()
            if not mpath.is_file():
                fallback = ROOT / ".models" / mpath.name
                if fallback.is_file():
                    mpath = fallback
            if not mpath.is_file():
                blocked = f"BLOCKED_MISSING_MODEL:{key}"
                break
            if file_hash(mpath) != mspec["sha256"]:
                raise ValueError(f"frozen_model_hash_mismatch:{key}")

    run(config, records.append, live_mode=include_live_model and blocked is None)
    summary = summarize(records, config)
    wall_s = round(time.perf_counter() - started, 6)
    carried_s = float(config.get("carried_used_s", 2433.667484455996))
    cumulative_s = round(carried_s + wall_s, 12)
    remaining_s = round(3600.0 - cumulative_s, 12)

    payload = dict(
        study_id=config["id"],
        scientific=False,
        kind="source_development_evaluation_not_confirmation",
        live_mode=bool(include_live_model and blocked is None),
        blocked_step=blocked,
        historical_fingerprints=historical_artifact_fingerprints(ROOT),
        resources=dict(
            carried_used_s=carried_s,
            wall_s=wall_s,
            cumulative_used_s=cumulative_s,
            remaining_budget_s=remaining_s,
        ),
        records=records,
        summary=summary,
        process_level_learning_to_learn=bool(
            summary["diagnostic_meta_learning"]["process_level_learning_to_learn_established"]
        ),
        agi=False,
        gemini="NOT_RUN",
    )
    artifact = directory / "seed_bottleneck_breaker.json"
    raw = directory / "seed_bottleneck_breaker_raw.jsonl"
    artifact.write_text(json.dumps(payload, allow_nan=False, indent=2, default=str), encoding="utf-8")
    raw.write_text(
        "\n".join(json.dumps(r, allow_nan=False, default=str) for r in records) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, default=str))
    print("wrote", artifact)
    return artifact


if __name__ == "__main__":
    args = sys.argv[1:]
    target = (
        Path(args[0])
        if args and not args[0].startswith("--")
        else ROOT / "artifacts" / "seed_bottleneck_breaker"
    )
    main(target, include_live_model="--live-model" in args)
