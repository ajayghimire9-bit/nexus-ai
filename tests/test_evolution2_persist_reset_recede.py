"""Receding stored-obs clock. Not a scientific experiment."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import persist_reset_budget as budget
from nexus.evolution2 import persist_reset_recede as recede
from nexus.evolution2 import persist_reset_request as lock


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_recede_clock_uses_stored_obs_and_refuses_7680():
    payload = recede.write_artifact()
    clocked = payload["recede"]
    assert payload["granted_7680"] is False
    assert payload["scientific"] is False
    assert payload["hold_named"] is False
    assert clocked["n_decisions"] == 800
    assert clocked["n_episode_equivalents"] == 4
    assert clocked["env_steps"] == 0
    assert clocked["decoded"] == 800
    assert clocked["twelve_arm_scientific"] == "BLOCKED"
    assert clocked["do_not_treat_as_scientific_clock"] is True
    assert clocked["screen_9600_prior_s"] is not None
    assert payload["budget"]["real_environment"]["fresh_total"] == 17280
    assert payload["h16_scientific_ledger_untouched"] is True
    with pytest.raises(RuntimeError, match="do_not_grant_7680"):
        budget.refuse_premature_7680(7680)
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(17280)
    imported = _imports(Path(recede.__file__))
    assert "gymnasium" not in imported
    assert "collect_transitions" not in Path(recede.__file__).read_text()
    assert lock.allocation_record()["authorized"] is False
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
