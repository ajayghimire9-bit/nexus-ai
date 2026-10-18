"""Source-only four-role instance rules. Does not persist tuples or collect."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import pendulum_acrobot_holdout_review as review
from nexus.evolution2 import pendulum_acrobot_instance_rules as m
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


def test_roles_stay_unnamed_and_unauthorized():
    lock = m.public_lock()
    assert lock["verdict"] == "FOUR_ROLE_RULES_LOCKED_UNNAMED"
    assert lock["hold_named"] is False
    assert lock["locked_target"] is None
    assert lock["authorized"] is False
    assert lock["collection"] is False
    assert m.live_named_holdout() is None
    assert v1.HOLD_NAMED is False
    assert v2.HOLD_NAMED is False
    assert pilot.HOLD_NAMED is False
    with pytest.raises(RuntimeError, match="unnamed"):
        m.require_named_holdout()


def test_pendulum_grid_is_regular_and_has_unused_cells():
    grid = m.pendulum_grid()
    assert len(grid) == 6069
    assert m.PENDULUM_G[0] == 5.0
    assert m.PENDULUM_G[-1] == 15.0
    assert m.PENDULUM_M[0] == 0.6
    assert m.PENDULUM_M[-1] == 1.4
    assert (10.0, 1.0, 1.0) in grid
    unused = [key for key in grid if v1.physics_key(key) not in v1.occupied_pendulum()]
    assert len(unused) >= 4


def test_four_role_digests_match_and_roles_are_disjoint():
    assigned = m.assign_roles()
    assert tuple(assigned) == m.ROLE_ORDER
    assert len(set(assigned.values())) == 4
    digests = m.role_digests()
    assert digests == m.ROLE_DIGESTS
    assert digests["acrobot_development"] == review.ACROBOT_UNUSED_SHA256
    assert assigned["pendulum_source"] not in v1.occupied_pendulum()
    assert assigned["pendulum_development"] not in v1.occupied_pendulum()
    assert assigned["acrobot_source"] not in v1.occupied_acrobot()
    assert assigned["acrobot_development"] not in v1.occupied_acrobot()
    assert assigned["pendulum_source"] != (10.0, 1.0, 1.0)
    assert assigned["acrobot_source"] != (1.0, 1.0, 1.0)
    record = m.artifact_record()
    assert record["role_digests"] == m.ROLE_DIGESTS
    assert record["locked_target"] is None


def test_plaintext_tuples_are_not_persisted():
    assigned = m.assign_roles()
    texts = [
        Path(m.__file__).read_text().replace(" ", ""),
        m.PROTOCOL.read_text().replace(" ", ""),
        m.ARTIFACT.read_text().replace(" ", ""),
    ]
    for key in assigned.values():
        plaintext = v1.canonical(key)
        for text in texts:
            assert plaintext not in text


def test_prior_protocol_hashes_stay_frozen():
    lock = m.public_lock()
    assert lock["v1_hashes_frozen"] is True
    assert lock["v2_hashes_frozen"] is True
    assert lock["pilot_hashes_frozen"] is True


def test_instance_rules_stay_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "nexus.evolution1.adapters" not in imported
    assert "nexus.tasks.spec" not in imported
    assert "nexus.tasks.pendulum_family" not in imported
    assert "nexus.tasks.acrobot_family" not in imported
    text = Path(m.__file__).read_text()
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
    assert "FOUR_ROLE_RULES_LOCKED_UNNAMED" in m.PROTOCOL.read_text()
