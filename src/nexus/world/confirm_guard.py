"""Fail-closed gate for the original context-adaptation confirmation.

Confirmation stays locked unless a completed, non-smoke development artifact
matches the frozen protocol and its implementation revision still matches the
source tree. Artifact and document commits may follow that revision. Source
changes may not. This module does not step confirmation environments.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

from nexus.cl.serialize import dumps_strict

SOURCE_ROOTS = ("src", "tests", "scripts", "configs")
PROTOCOL_ID = "context_adaptation_v1"


class ConfirmationRejected(RuntimeError):
    pass


def _split_hashes() -> dict[str, str]:
    from nexus.tasks.pendulum_family import (
        pendulum_context_confirmation,
        pendulum_context_development,
        pendulum_context_train,
    )
    from nexus.world.context_pilot import _split_hash

    return {
        "train_hash": _split_hash(pendulum_context_train()),
        "dev_hash": _split_hash(pendulum_context_development()),
        "confirm_hash": _split_hash(pendulum_context_confirmation()),
    }


def pilot_config_fingerprint() -> str:
    from nexus.world.context_pilot import (
        BUDGETS,
        FT_LR,
        PRIMARY_HI,
        SOURCE_EPOCHS,
        SOURCE_PER_TASK,
    )
    from nexus.world.planning import PENDULUM_PLAN_CANDIDATES, PENDULUM_PLAN_HORIZON

    payload = {
        "protocol_id": PROTOCOL_ID,
        "conditioning": "film",
        "context_dim": 8,
        "encoder_hidden": 32,
        "trunk_hidden": [48, 48],
        "max_context": 128,
        "budgets": list(BUDGETS),
        "primary_hi": PRIMARY_HI,
        "primary_metric": "trapz_return_auc_0_to_256_divided_by_256",
        "ft_lr": FT_LR,
        "ft_target_validation": False,
        "source_per_task": SOURCE_PER_TASK,
        "source_epochs": SOURCE_EPOCHS,
        "horizon": PENDULUM_PLAN_HORIZON,
        "candidates": PENDULUM_PLAN_CANDIDATES,
        **_split_hashes(),
    }
    return hashlib.sha256(dumps_strict(payload).encode()).hexdigest()[:16]


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], check=False, capture_output=True, text=True)


def inspect_source_tree(recorded_sha: str) -> dict[str, Any]:
    """Compare source paths to `recorded_sha`. Docs and artifacts are ignored."""
    if not isinstance(recorded_sha, str) or len(recorded_sha) < 7:
        return {"error": "recorded implementation revision is missing", "source_dirty": True, "source_changed": True}
    verify = _git(["rev-parse", "--verify", "--quiet", recorded_sha])
    if verify.returncode != 0 or not verify.stdout.strip():
        return {"error": "recorded implementation revision is not in this repository", "source_dirty": True, "source_changed": True}
    diff = _git(["diff", "--name-only", recorded_sha, "--", *SOURCE_ROOTS])
    if diff.returncode != 0:
        return {"error": "could not compare the implementation revision", "source_dirty": True, "source_changed": True}
    changed = [line.strip() for line in diff.stdout.splitlines() if line.strip()]
    status = _git(["status", "--porcelain", "--", *SOURCE_ROOTS])
    dirty = [line.strip() for line in status.stdout.splitlines() if line.strip()] if status.returncode == 0 else ["status-failed"]
    return {
        "error": None,
        "source_dirty": bool(dirty),
        "source_changed": bool(changed or dirty),
        "changed_paths": changed,
        "dirty_paths": dirty,
    }


def provenance_fields() -> dict[str, Any]:
    head = _git(["rev-parse", "HEAD"])
    sha = head.stdout.strip() if head.returncode == 0 else ""
    status = inspect_source_tree(sha) if sha else {"source_dirty": True, "source_changed": True}
    return {
        "protocol_id": PROTOCOL_ID,
        "config_fingerprint": pilot_config_fingerprint(),
        "implementation_sha": sha if sha and not status.get("source_dirty") else None,
        "source_dirty": bool(status.get("source_dirty", True)),
    }


def assert_confirmation_allowed(dev: Mapping[str, Any] | None, *, source_status: dict[str, Any] | None = None) -> None:
    """Raise unless `dev` is a finished passing development run tied to this protocol.

    `source_status` lets tests reject stale trees without stepping an environment.
    """
    if not isinstance(dev, Mapping) or not dev:
        raise ConfirmationRejected("missing development artifact")
    if dev.get("incomplete") is not False:
        raise ConfirmationRejected("development run is incomplete or unmarked")
    proto = dev.get("protocol")
    if not isinstance(proto, Mapping):
        raise ConfirmationRejected("development artifact has no protocol")
    if proto.get("code_version") != "context_adaptation_pilot":
        raise ConfirmationRejected("artifact is not the context-adaptation development protocol")
    if proto.get("phase") != "dev" or proto.get("quick") is True:
        raise ConfirmationRejected("confirmation requires a completed non-smoke development run")
    if proto.get("confirm_evaluated") is True:
        raise ConfirmationRejected("artifact already claims confirmation was evaluated")
    gate = dev.get("gate")
    if not isinstance(gate, Mapping) or gate.get("pass") is not True:
        raise ConfirmationRejected("development gate did not pass")
    if proto.get("protocol_id") != PROTOCOL_ID:
        raise ConfirmationRejected("development evidence is not tied to the frozen protocol id")
    hashes = _split_hashes()
    for key, live in hashes.items():
        if proto.get(key) != live:
            raise ConfirmationRejected(f"split hash mismatch for {key}")
    if proto.get("config_fingerprint") != pilot_config_fingerprint():
        raise ConfirmationRejected("frozen experiment configuration does not match the artifact")
    sha = proto.get("implementation_sha")
    if not isinstance(sha, str) or len(sha) != 40:
        raise ConfirmationRejected("missing clean implementation revision")
    if proto.get("source_dirty") is not False:
        raise ConfirmationRejected("recorded implementation revision was dirty")
    status = source_status if source_status is not None else inspect_source_tree(sha)
    if not isinstance(status, Mapping) or status.get("error"):
        raise ConfirmationRejected(str((status or {}).get("error") or "implementation provenance is unavailable"))
    if status.get("source_dirty") or status.get("source_changed"):
        raise ConfirmationRejected("source changed after the recorded implementation revision")


def load_dev_artifact(path: str | Path | None) -> dict[str, Any]:
    target = Path(path) if path is not None else Path("artifacts/context_adaptation_dev.json")
    if not target.is_file():
        raise ConfirmationRejected(f"missing development artifact: {target}")
    try:
        payload = json.loads(target.read_text())
    except json.JSONDecodeError as exc:
        raise ConfirmationRejected("development artifact is not readable JSON") from exc
    if not isinstance(payload, dict):
        raise ConfirmationRejected("development artifact is not an object")
    return payload
