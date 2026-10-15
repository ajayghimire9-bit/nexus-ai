"""Explicit checkpoint audit. A missing or altered weight file is a failure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class CheckpointIntegrityError(RuntimeError):
    """Raised when an explicitly requested checkpoint audit cannot verify a file."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pt_records(payload: object, found: list[tuple[str, str]]) -> None:
    if isinstance(payload, dict):
        for path_key, hash_key in (
            ("path", "sha256"),
            ("model_path", "model_sha256"),
            ("global_path", "global_sha256"),
        ):
            path = payload.get(path_key)
            digest = payload.get(hash_key)
            if isinstance(path, str) and path.endswith(".pt") and isinstance(digest, str):
                found.append((path, digest))
        for value in payload.values():
            _pt_records(value, found)
    elif isinstance(payload, list):
        for value in payload:
            _pt_records(value, found)


def recorded_checkpoint_hashes(root: Path | None = None) -> dict[str, str]:
    """Hashes named by the committed confirmation artifact, replication manifest, and parent configs."""
    base = Path(".") if root is None else Path(root)
    found: list[tuple[str, str]] = []
    confirmation = json.loads((base / "artifacts" / "latent_generalization_confirmation.json").read_text())
    manifest = json.loads((base / "artifacts" / "control_replication_checkpoints" / "manifest.json").read_text())
    _pt_records(confirmation, found)
    _pt_records(manifest, found)
    config = yaml.safe_load((base / "configs" / "control_replication.yaml").read_text())
    for key in ("parent_checkpoints", "mlp_checkpoints"):
        for row in config[key]:
            found.append((str(row["path"]), str(row["sha256"])))
    records: dict[str, str] = {}
    for path, digest in found:
        previous = records.get(path)
        if previous is not None and previous != digest:
            raise CheckpointIntegrityError(f"conflicting recorded hashes for {path}")
        records[path] = digest
    if len(records) != 120:
        raise CheckpointIntegrityError(f"expected 120 recorded weight files, found {len(records)}")
    return records


def verify_checkpoint_integrity(
    records: dict[str, str] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Verify every requested file. Missing and mismatched files both fail; nothing is skipped."""
    base = Path(".") if root is None else Path(root)
    checked = recorded_checkpoint_hashes(base) if records is None else dict(records)
    if not checked:
        raise CheckpointIntegrityError("checkpoint audit was requested with an empty file list")
    missing: list[str] = []
    mismatched: list[str] = []
    for path, digest in sorted(checked.items()):
        fp = base / path
        if not fp.is_file():
            missing.append(path)
            continue
        if _sha256(fp) != digest:
            mismatched.append(path)
    if missing or mismatched:
        parts = [f"{len(missing)} missing", f"{len(mismatched)} mismatched"]
        if missing:
            parts.append("missing " + ", ".join(missing[:8]))
        if mismatched:
            parts.append("mismatched " + ", ".join(mismatched[:8]))
        raise CheckpointIntegrityError("checkpoint integrity failed: " + "; ".join(parts))
    return {"verified": len(checked), "missing": 0, "mismatched": 0}
