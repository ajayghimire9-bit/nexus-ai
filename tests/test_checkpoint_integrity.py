"""Checkpoint audits fail closed. The full local audit is explicit."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexus.world.checkpoint_integrity import CheckpointIntegrityError, verify_checkpoint_integrity


def test_a_missing_checkpoint_fails_the_audit(tmp_path: Path) -> None:
    with pytest.raises(CheckpointIntegrityError, match="missing"):
        verify_checkpoint_integrity({"weights/missing.pt": "abc"}, root=tmp_path)


def test_a_wrong_hash_fails_the_audit(tmp_path: Path) -> None:
    path = tmp_path / "weights.pt"
    path.write_bytes(b"not-the-recorded-bytes")
    with pytest.raises(CheckpointIntegrityError, match="mismatched"):
        verify_checkpoint_integrity({"weights.pt": "0" * 64}, root=tmp_path)


def test_an_empty_audit_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(CheckpointIntegrityError, match="empty"):
        verify_checkpoint_integrity({}, root=tmp_path)


@pytest.mark.checkpoint_integrity
def test_recorded_local_checkpoints_match() -> None:
    report = verify_checkpoint_integrity()
    assert report["verified"] == 120
    assert report["missing"] == 0
    assert report["mismatched"] == 0
