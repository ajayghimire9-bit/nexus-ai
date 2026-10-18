"""Source-only unused-instance naming review. Does not name a holdout."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import pendulum_acrobot_holdout_review as m
from nexus.evolution2 import pendulum_acrobot_protocol as v1
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


def test_naming_stays_blocked_and_unnamed():
    review = m.public_review()
    assert review["verdict"] == "NAMING_BLOCKED"
    assert review["hold_named"] is False
    assert review["locked_target"] is None
    assert review["authorized"] is False
    assert review["collection"] is False
    assert m.live_named_holdout() is None
    assert v1.HOLD_NAMED is False
    assert v1.LOCKED_TARGET is None
    assert v2.HOLD_NAMED is False
    assert pilot.HOLD_NAMED is False
    with pytest.raises(RuntimeError, match="unnamed"):
        m.require_named_holdout()


def test_four_roles_and_missing_pendulum_rule_block_naming():
    assert m.REQUIRED_ROLES == (
        "pendulum_source",
        "pendulum_development",
        "acrobot_source",
        "acrobot_development",
    )
    assert m.pendulum_unused_rule_exists() is False
    assert "pendulum_unused_instance_rule_missing" in m.blockers()
    assert "one_acrobot_key_cannot_fill_four_roles" in m.blockers()
    assert m.occupied_covers_family_literals() is True
    assert m.family_declared_pendulum() <= v1.occupied_pendulum()
    assert m.family_declared_acrobot() <= v1.occupied_acrobot()
    assert v1.physics_key((10.0, 1.0, 1.0)) in v1.occupied_pendulum()
    assert v1.physics_key((1.0, 1.0, 1.0)) in v1.occupied_acrobot()


def test_acrobot_unused_digest_is_recorded_without_a_named_tuple():
    digest = m.acrobot_unused_digest()
    assert digest == m.ACROBOT_UNUSED_SHA256
    record = m.artifact_record()
    assert record["acrobot_unused_sha256"] == digest
    assert record["locked_target"] is None
    live = v1.unused_instance_from_rule(
        occupied=v1.occupied_acrobot(),
        grid=v1.acrobot_grid(),
        rule=v1.HOLD_RULE,
        counter=0,
    )
    plaintext = v1.canonical(live)
    for path in (Path(m.__file__), m.PROTOCOL, m.ARTIFACT):
        assert plaintext not in path.read_text().replace(" ", "")


def test_prior_protocol_hashes_stay_frozen():
    review = m.public_review()
    assert review["v1_hashes_frozen"] is True
    assert review["v2_hashes_frozen"] is True
    assert review["pilot_hashes_frozen"] is True


def test_review_stays_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "nexus.evolution1.adapters" not in imported
    assert "nexus.tasks.spec" not in imported
    assert "nexus.tasks.pendulum_family" not in imported
    assert "nexus.tasks.acrobot_family" not in imported
    text = Path(m.__file__).read_text()
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
    docs = m.PROTOCOL.read_text()
    assert "NAMING_BLOCKED" in docs
    assert "does **not** name a holdout" in docs
