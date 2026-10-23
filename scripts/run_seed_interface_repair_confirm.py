"""Offline inspect/audit, then at most one hard-deadline live evaluation."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
HISTORICAL = ROOT / "artifacts/seed_harder_features/seed_harder_features.json"


def load_config():
    return json.loads((ROOT / "configs/seed_interface_repair_confirm.json").read_text())


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
    from nexus.seed.hard_deadline import HardDeadline
    from nexus.seed.interface_repair_study import (
        HISTORICAL_HARDER_SHA256, begin, record_model, summarize,
    )

    config = load_config()
    directory.mkdir(parents=True, exist_ok=True)
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    if hashlib.sha256(HISTORICAL.read_bytes()).hexdigest() != HISTORICAL_HARDER_SHA256:
        raise ValueError("historical_harder_artifact_changed")
    records = []
    started = time.perf_counter()
    blocked = None
    metas = {}
    deadline = HardDeadline(float(config["hard_deadline_s"]))
    meter = begin(config, records.append, historical["records"])
    if include_live_model:
        remaining = 3600.0 - float(config["carried_used_s"])
        if float(config["hard_deadline_s"]) > remaining:
            blocked = "BLOCKED_BUDGET"
        else:
            coder, blocked, meta = start_runtime(config["models"]["coder15"])
            metas["coder15"] = meta
            try:
                if coder is not None:
                    deadline.arm(coder)
                    _, run_blocked = record_model(
                        config, records.append, meter, coder, deadline=deadline,
                    )
                    blocked = blocked or run_blocked
            except TimeoutError:
                blocked = "hard_deadline"
            finally:
                deadline.disarm()
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
        historical_harder_sha256=HISTORICAL_HARDER_SHA256,
        historical_supplied_private_correct=1,
        resources=dict(wall_s=round(time.perf_counter() - started, 6)),
        records=records,
        summary=summary,
        learning_to_learn=False,
        agi=False,
        gemini="NOT_RUN",
    )
    artifact = directory / "seed_interface_repair_confirm.json"
    raw = directory / "seed_interface_repair_confirm_raw.jsonl"
    artifact.write_text(json.dumps(payload, allow_nan=False, indent=2, default=str), encoding="utf-8")
    raw.write_text("\n".join(json.dumps(r, allow_nan=False, default=str) for r in records) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    print("wrote", artifact, "blocked", blocked)
    return artifact


if __name__ == "__main__":
    args = sys.argv[1:]
    target = Path(args[0]) if args and not args[0].startswith("--") else ROOT / "artifacts" / "seed_interface_repair_confirm"
    main(target, include_live_model="--live-model" in args)
