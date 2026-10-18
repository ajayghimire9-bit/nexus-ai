"""Source-only Pendulum→Acrobot protocol lock. No Gymnasium, no collection."""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from nexus.evolution2 import pendulum_acrobot_protocol as m

ROOT = Path(__file__).resolve().parents[1]


def _source_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_lock_files_match_frozen_hashes():
    assert m.file_sha256(m.CONFIG) == m.LOCKED_CONFIG
    assert m.file_sha256(m.PROTOCOL) == m.LOCKED_PROTOCOL
    assert m.file_sha256(m.ALLOCATION) == m.LOCKED_ALLOCATION
    record = m.allocation_record()
    assert record["authorized"] is False
    assert record["runs"] == 0
    assert record["consumed"] is False
    assert record["hold_named"] is False
    assert record["locked_target"] is None
    assert record["time_cap_s"] == 0
    assert record["env_cap"] == 0
    assert record["config_sha256"] == m.LOCKED_CONFIG
    assert record["protocol_sha256"] == m.LOCKED_PROTOCOL
    assert record["claims_learning_to_learn"] is False
    assert record["cross_family_weights"] is False


def test_public_lock_is_unauthorized_and_unnamed():
    lock = m.public_lock()
    assert lock["authorized"] is False
    assert lock["runs"] == 0
    assert lock["hold_named"] is False
    assert lock["locked_target"] is None
    assert m.live_named_holdout() is None
    assert lock["methods"] == [
        "fixed",
        "random",
        "reset",
        "persist",
        "evolution",
        "retrieval",
    ]
    assert lock["primary"] == "persist_minus_reset"
    assert lock["label_blocked"] == "persist_beats_reset_blocked"
    assert lock["collection"] is False
    assert lock["train_family"] == "pendulum"
    assert lock["eval_family"] == "acrobot"
    assert lock["train_physics"] == [10.0, 1.0, 1.0]


def test_methods_and_estimands_are_locked():
    assert [row["id"] for row in m.METHODS] == list("ABCDEF")
    assert [row["name"] for row in m.METHODS] == [
        "fixed",
        "random",
        "reset",
        "persist",
        "evolution",
        "retrieval",
    ]
    roles = {row["name"]: row["role"] for row in m.METHODS}
    assert roles["persist"] == "treatment"
    assert roles["reset"] == "baseline"
    assert m.PRIMARY["treatment"] == "D"
    assert m.PRIMARY["baseline"] == "C"
    assert m.PRIMARY["n"] == 10
    assert m.PRIMARY["df"] == 9
    assert m.PRIMARY["interval"] == "student_t_95"
    assert m.PRIMARY["replication_unit"] == "independent_source_training_seed"
    assert m.PRIMARY["not_learning_to_learn"] is True
    secondary = {row["estimand"] for row in m.SECONDARY}
    assert secondary == {
        "persist_minus_random",
        "persist_minus_evolution",
        "persist_minus_retrieval",
        "persist_minus_fixed",
    }


def test_budget_stays_inside_standing_and_is_currently_zero():
    assert 0 == m.AUTHORIZED_TIME_CAP_S == m.AUTHORIZED_ENV_CAP
    assert m.PROPOSED_TIME_CAP_S <= m.STANDING_TIME_CAP_S
    assert m.PROPOSED_ENV_CAP <= m.STANDING_ENV_CAP
    assert m.PROPOSED_TIME_CAP_S == 300
    assert m.PROPOSED_ENV_CAP == 40_000
    assert m.PROPOSED_IMAGINED_CAP == 0
    assert m.SESSION_LEDGER_USED_S == 305.842
    assert m.SESSION_LEDGER_REMAINING_S == 3294.158


def test_occupied_lists_exclude_historical_pendulum_and_acrobot():
    pendulum = m.occupied_pendulum()
    acrobot = m.occupied_acrobot()
    assert m.physics_key((10.0, 1.0, 1.0)) in pendulum
    assert m.physics_key((8.3, 1.0, 1.0)) in pendulum
    assert m.physics_key((17.1, 1.5, 0.8)) in pendulum
    assert m.physics_key((4.2, 3.2, 1.7)) in pendulum
    assert m.physics_key((1.0, 1.0, 1.0)) in acrobot
    assert m.physics_key((0.95, 1.2, 0.8)) in acrobot
    assert m.physics_key((1.15, 0.85, 0.6)) in acrobot
    assert m.reject_reason("pendulum", (10.0, 1.0, 1.0)) == (
        "occupied_train_source_not_a_holdout"
    )
    assert m.reject_reason("acrobot", (1.0, 1.0, 1.0)) == "occupied_acrobot"
    assert m.reject_reason("mountaincar_continuous", (0.0025, 0.0015, 0.07)) == (
        "forbidden_family"
    )
    assert m.family_allowed("pendulum")
    assert m.family_allowed("acrobot")
    assert not m.family_allowed("mountaincar")
    assert not m.family_allowed("cartpole")
    for name in m.FORBIDDEN_HYPOTHESES:
        assert name in {"H12", "H13", "H14", "H15", "H16", "H17"}


def test_unused_instance_rule_is_deterministic_without_naming_live_holdout():
    occupied = frozenset({(0.6, 0.6, 0.6), (0.65, 0.65, 0.65)})
    grid = ((0.6, 0.6, 0.6), (0.65, 0.65, 0.65), (0.7, 0.7, 0.7))
    first = m.unused_instance_from_rule(occupied=occupied, grid=grid, counter=0)
    second = m.unused_instance_from_rule(occupied=occupied, grid=grid, counter=0)
    assert first == second
    assert first not in occupied
    assert first in {m.physics_key(row) for row in grid}
    with pytest.raises(RuntimeError, match="no unused instance"):
        m.unused_instance_from_rule(occupied=frozenset(grid), grid=grid)
    assert m.HOLD_NAMED is False
    assert m.LOCKED_TARGET is None
    with pytest.raises(RuntimeError, match="unnamed"):
        m.require_named_holdout()


def test_scientific_dispatch_and_forbidden_imports_are_blocked():
    with pytest.raises(RuntimeError, match="unauthorized"):
        m.require_scientific()
    source = inspect.getsource(m)
    imported = _source_imports(Path(m.__file__))
    for name in m.FORBIDDEN_IMPORTS:
        assert name not in imported
        assert f"import {name}" not in source
    assert "make_task_env" not in source
    assert "from nexus.evolution1" not in source
    docs = (ROOT / "docs" / "NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL.md").read_text()
    assert "COLLECTION UNAUTHORIZED" in docs
    assert "unnamed" in docs.lower()
    assert "H17" in docs
