"""Independent four-role digest and exclusion audit. No new selection."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import pendulum_acrobot_holdout_review as review
from nexus.evolution2 import pendulum_acrobot_instance_rules as rules
from nexus.evolution2 import pendulum_acrobot_protocol as v1
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_roles as roles


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_locked_four_roles_match_digests_and_exclusions():
    payload = roles.write_artifact()
    assigned = roles.independent_assign()
    official = rules.assign_roles()
    assert payload["status"] == "PASS"
    assert payload["new_selection"] is False
    assert payload["hold_named"] is False
    assert payload["locked_target"] is None
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["digests"] == dict(rules.ROLE_DIGESTS)
    assert payload["digests"] == roles.digest_roles(official)
    assert payload["historical_exclusion_clean"] is True
    assert payload["h17"] == "blocked"
    assert assigned == official
    assert assigned["acrobot_development"] not in v1.occupied_acrobot()
    assert assigned["acrobot_source"] not in v1.occupied_acrobot()
    assert assigned["pendulum_source"] not in v1.occupied_pendulum()
    assert assigned["pendulum_development"] not in v1.occupied_pendulum()
    assert assigned["pendulum_source"] != (10.0, 1.0, 1.0)
    assert assigned["acrobot_source"] != (1.0, 1.0, 1.0)
    assert payload["digests"]["acrobot_development"] == review.ACROBOT_UNUSED_SHA256
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
    assert lock.file_sha256(roles.H16) == roles.H16_SHA
    assert "H17" in v1.FORBIDDEN_HYPOTHESES
    imported = _imports(Path(roles.__file__))
    assert "gymnasium" not in imported


def test_named_role_validation_requires_all_four_locked_digests():
    assigned = roles.independent_assign()
    digests = roles.digest_roles(assigned)
    assert roles.validate_named_roles(digests)["valid"] is True
    assert roles.validate_named_roles({"pendulum_source": digests["pendulum_source"]})["valid"] is False
    wrong = dict(digests)
    wrong["pendulum_source"] = "0" * 64
    assert roles.validate_named_roles(wrong)["valid"] is False
    assert roles.validate_named_roles(assigned)["valid"] is True
    with pytest.raises(RuntimeError, match="unnamed"):
        lock.require_named_holdout()
