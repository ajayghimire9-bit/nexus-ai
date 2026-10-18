"""Approval-text gate. Vague authorization is not science."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import persist_reset_approval as gate
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_runner as runner
from nexus.evolution2.pendulum_acrobot_instance_rules import ROLE_DIGESTS, ROLE_ORDER


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_continue_i_authorised_you_is_insufficient():
    payload = gate.write_artifact("continue i authrosed you")
    parsed = payload["parsed"]
    assert parsed["status"] == "INSUFFICIENT"
    assert parsed["authorized"] is False
    assert parsed["vague_authorization"] is True
    assert parsed["hash_cited"] is False
    assert parsed["env_cap"] is None
    assert parsed["hold_named"] is False
    assert "config_hash_8e90b74a" in parsed["missing"]
    assert "named_four_role_unused_holdout" in parsed["missing"]
    assert "env_cap_17280" in parsed["missing"]
    assert payload["granted_7680"] is False
    assert parsed["yaml_unchanged"] is True
    with pytest.raises(RuntimeError, match="approval_insufficient"):
        gate.refuse_vague_authorization("continue i authorised you")
    with pytest.raises(RuntimeError, match="occupied_default"):
        gate.refuse_vague_authorization(
            f"cite {lock.LOCKED_CONFIG} env_cap=17280 holdout (10,1,1)"
        )
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(17280)
    with pytest.raises(Exception, match="unnamed|holdout"):
        runner.dispatch(7680)
    imported = _imports(Path(gate.__file__))
    assert "gymnasium" not in imported
    assert lock.allocation_record()["authorized"] is False
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG


def test_generic_holdout_word_is_not_four_role_validation():
    parsed = gate.parse_approval(
        f"cite {lock.LOCKED_CONFIG} env_cap=17280 named unused four-role holdout"
    )
    assert parsed["status"] == "INSUFFICIENT"
    assert parsed["four_role_valid"] is False
    assert "named_four_role_unused_holdout" in parsed["missing"]
    assert parsed["authorized"] is False
    assert parsed["hold_named"] is False


def test_exact_four_role_digests_are_text_complete_but_still_unauthorized():
    named = " ".join(f"{role}={digest}" for role, digest in ROLE_DIGESTS.items())
    text = f"cite {lock.LOCKED_CONFIG} env_cap=17280 {named}"
    parsed = gate.parse_approval(text)
    assert set(gate.extract_named_roles(text)) == set(ROLE_ORDER)
    assert parsed["status"] == "COMPLETE_TEXT_ONLY"
    assert parsed["four_role_valid"] is True
    assert parsed["authorized"] is False
    assert parsed["hold_named"] is False
    assert parsed["collection"] is False
    with pytest.raises(RuntimeError, match="allocation_still_unauthorized"):
        gate.refuse_vague_authorization(text)
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(17280)
    with pytest.raises(Exception, match="unnamed|holdout"):
        runner.dispatch(17280)
