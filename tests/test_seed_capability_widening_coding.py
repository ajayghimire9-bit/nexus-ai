"""Development checks for the widening/coding pilot runner and verifier."""
from __future__ import annotations

import json
from pathlib import Path

import sys

from nexus.seed.capability_widening_coding import historical_artifact_fingerprints, summarize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_seed_capability_widening_coding import digest, verify  # noqa: E402


def test_historical_audit_artifacts_still_present():
    root = Path(__file__).resolve().parents[1]
    fps = historical_artifact_fingerprints(root)
    assert fps["artifacts/seed_capability_audit_verified_v2.json"]
    assert fps["artifacts/seed_capability_audit_raw.jsonl"]


def test_verifier_rejects_forged_summary(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configs/seed_capability_widening_coding.json").read_text())
    records = [
        dict(kind="audit_manifest", config_hash=digest(config), gemini="NOT_RUN",
             result_label="authored_source_development_pilot_not_confirmation",
             historical_replay_is_not_confirmation=True,
             catalogue_hash="0"),
    ]
    # Minimal valid empty investigation still has manifest-only chain.
    payload = dict(records=records, summary=summarize(records, config),
                   historical_fingerprints=historical_artifact_fingerprints(root))
    out = verify(payload, config, root=root)
    assert out["valid"] is True
    payload["summary"]["methods"] = {"no_widening": {"identified": 99}}
    try:
        verify(payload, config, root=root)
        raise AssertionError("forged summary accepted")
    except ValueError:
        pass
