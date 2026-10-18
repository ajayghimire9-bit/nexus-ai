"""Source-only residual-MLP timing-probe contracts. No env collection."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import residual_timing_probe as m
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_probe_lock_is_env_free_and_hash_frozen():
    assert m.file_sha256(m.CONFIG) == m.LOCKED_CONFIG
    assert m.file_sha256(m.PROTOCOL) == m.LOCKED_PROTOCOL
    assert m.file_sha256(m.ALLOCATION) == m.LOCKED_ALLOCATION
    record = m.allocation_record()
    assert record["authorized"] is True
    assert record["env_cap"] == 0
    assert record["time_cap_s"] == 60
    assert record["imagined_cap"] == 200000
    assert record["hold_named"] is False
    assert record["collection"] is False
    lock = m.public_lock()
    assert lock["authorized"] is True
    assert lock["authorized_env_cap"] == 0
    assert lock["collection"] is False
    assert lock["modifies_checkpoints"] is False
    with pytest.raises(RuntimeError, match="unauthorized"):
        m.require_scientific()
    with pytest.raises(RuntimeError, match="unnamed"):
        m.require_named_holdout()


def test_prior_protocol_hashes_stay_frozen():
    lock = m.public_lock()
    assert lock["v2_hashes_frozen"] is True
    assert lock["pilot_hashes_frozen"] is True
    assert v2.worksheet()["first_screen_imagined_upper_bound"] == 110592000
    assert pilot.worksheet()["first_screen_imagined_upper_bound"] == 49152000


def test_checkpoint_list_is_identity_locked():
    rows = m.checkpoint_status()
    assert [row["id"] for row in rows] == [
        "pendulum_frozen_decoder",
        "pendulum_residual_mlp",
        "acrobot_lookahead_seed0",
    ]
    for row, spec in zip(rows, m.REQUIRED_CHECKPOINTS, strict=True):
        assert row["expected_sha256"] == spec["sha256"]
        if row["present"]:
            assert row["matches"] is True


def test_committed_probe_result_has_zero_env_steps():
    payload = __import__("json").loads(m.RESULTS.read_text())
    assert payload["outcome"] == "probe_complete"
    assert payload["env_steps"] == 0
    assert payload["checkpoint_writes"] == 0
    assert payload["collection"] is False
    assert payload["hold_named"] is False
    assert len(payload["models"]) == 3


def test_feasibility_uses_measured_rates_not_fake_model():
    report = m.feasibility_from_measured()
    assert report["status"] == "MEASURED"
    assert report["fake_model_not_used"] is True
    assert report["new_ledger_debit"] is False
    assert report["source_fitting"] == "unmeasured"
    assert report["v2_feasibility"] == "NO-GO"
    assert report["pilot_feasibility"] == "UNKNOWN"
    assert report["v2_conservative_planning_s"] > 600


def test_probe_source_stays_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "torch" not in imported
    assert "nexus.tasks.spec" not in imported
    assert "nexus.evolution1.adapters" not in imported
    text = Path(m.__file__).read_text()
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
    assert "NO ENV COLLECTION" in m.PROTOCOL.read_text()
