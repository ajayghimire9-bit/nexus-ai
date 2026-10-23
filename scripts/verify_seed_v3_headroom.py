"""Rebuild the v3_headroom certificate and reject a transfer claim."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.v3_headroom import structural_certificate


def verify(payload, config):
    if config.get("rescore_depth12") or config.get("learning_research_resumed"):
        raise ValueError("depth12_or_learning_resumed")
    if config.get("call_budget") != 35:
        raise ValueError("budget")
    rebuilt = structural_certificate()
    cert = payload["certificate"]
    if rebuilt["config_hash"] != cert["config_hash"]:
        raise ValueError("config_hash")
    if not cert["orthogonal"] or not cert["frequency_waste"]["guarantees_3x_more"]:
        raise ValueError("orthogonality_or_waste")
    if cert["coverage"]["hypothesis_count"] <= 2500:
        raise ValueError("hypothesis_floor")
    if cert["learning_to_learn_established"] or payload.get("learning_to_learn"):
        raise ValueError("false_l2l_claim")
    if payload.get("transfer_run") != "NOT_RUN":
        raise ValueError("transfer_should_be_not_run")
    if payload.get("config_hash") != digest(config):
        raise ValueError("payload_config")
    return dict(
        valid=True,
        orthogonal=True,
        hypothesis_count=cert["coverage"]["hypothesis_count"],
        frequency_ratio=cert["frequency_waste"]["ratio"],
        transfer_run="NOT_RUN",
        learned_ranking_promoted=False,
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_v3_headroom.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_v3_headroom/seed_v3_headroom.json"
    )
    main(target)
