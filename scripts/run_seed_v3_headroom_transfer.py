"""Run the locked Set A → Set B v3_headroom transfer. No live model."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_config():
    return json.loads((ROOT / "configs/seed_v3_headroom_transfer.json").read_text())


def main(directory: Path, *, live_model=False):
    from nexus.seed.capability_evidence import digest
    from nexus.seed.v3_headroom_transfer import begin, record_set_b, summarize

    if live_model:
        raise ValueError("live_model_forbidden_for_this_study")
    config = load_config()
    if config.get("live_neural_calls", 0) != 0:
        raise ValueError("neural_calls_must_be_zero")
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    started = time.perf_counter()
    state = begin(config, records.append)
    record_set_b(config, records.append, state)
    wall = time.perf_counter() - started
    if wall > float(config.get("max_runner_wall_s", 15)):
        raise ValueError(f"runner_wall_exceeded:{wall}")
    summary = summarize(records, config)
    payload = dict(
        study_id=config["id"],
        scientific=False,
        kind="source_development_evaluation_not_confirmation",
        live_neural_calls=0,
        config_hash=digest(config),
        resources=dict(wall_s=round(wall, 6)),
        records=records,
        summary=summary,
        learning_to_learn=False,
        agi=False,
        gemini="NOT_RUN",
    )
    artifact = directory / "seed_v3_headroom_transfer.json"
    raw = directory / "seed_v3_headroom_transfer_raw.jsonl"
    artifact.write_text(json.dumps(payload, allow_nan=False, indent=2, default=str), encoding="utf-8")
    raw.write_text("\n".join(json.dumps(r, allow_nan=False, default=str) for r in records) + "\n", encoding="utf-8")
    print(json.dumps({
        "wall_s": payload["resources"]["wall_s"],
        "gate1": summary["gate1_specialist_separation"],
        "gate2": summary["gate2_primary_transfer"],
        "phi_mean": summary["gate2_phi_mean"],
        "untrained_mean": summary["gate2_untrained_mean"],
        "verdict": summary["verdict"],
        "live_neural_calls": 0,
    }, indent=2))
    print("wrote", artifact)
    return artifact


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--live-model" in args:
        raise SystemExit("this study forbids --live-model")
    target = Path(args[0]) if args and not args[0].startswith("--") else ROOT / "artifacts" / "seed_v3_headroom_transfer"
    main(target, live_model=False)
