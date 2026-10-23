"""Emit the v3_headroom structural certificate. No transfer training."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(directory: Path):
    from nexus.seed.capability_evidence import digest
    from nexus.seed.v3_headroom import structural_certificate

    config = json.loads((ROOT / "configs/seed_v3_headroom.json").read_text())
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    cert = structural_certificate()
    payload = dict(
        study_id=config["id"],
        scientific=False,
        kind="source_design_lock_not_confirmation",
        config_hash=digest(config),
        certificate=cert,
        transfer_run="NOT_RUN",
        learning_to_learn=False,
        agi=False,
        resources=dict(wall_s=round(time.perf_counter() - started, 6)),
    )
    artifact = directory / "seed_v3_headroom.json"
    artifact.write_text(json.dumps(payload, allow_nan=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "orthogonal": cert["orthogonal"],
        "hypothesis_count": cert["coverage"]["hypothesis_count"],
        "frequency_ratio": cert["frequency_waste"]["ratio"],
        "transfer_run": "NOT_RUN",
        "learning_to_learn": False,
    }, indent=2))
    print("wrote", artifact)
    return artifact


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts" / "seed_v3_headroom"
    main(target)
