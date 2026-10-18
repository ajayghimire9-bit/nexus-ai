"""Locked n=3 persist-versus-reset science helpers. No collection."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import persist_reset_executor as exe
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_science as science
from nexus.evolution2.pendulum_acrobot_protocol_n3_micro import (
    DEVELOPMENT_CONDITIONS,
    REVEALED_VARIANTS_PER_FAMILY,
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_locked_split_keeps_anchors_revealed_and_two_hidden():
    split = science.locked_split()
    assert len(split["revealed"]) == REVEALED_VARIANTS_PER_FAMILY
    assert len(split["hidden"]) == DEVELOPMENT_CONDITIONS
    assert split["anchors"][0] in split["revealed"]
    assert split["anchors"][1] in split["revealed"]
    assert set(split["revealed"]).isdisjoint(split["hidden"])
    assert {v.generator.value for v in split["revealed"]} == {"iid"}


def test_occupied_defaults_are_refused_as_new_physics():
    with pytest.raises(RuntimeError, match="occupied_default_reuse_forbidden"):
        science.refuse_occupied_defaults("pendulum", (10.0, 1.0, 1.0))
    with pytest.raises(RuntimeError, match="occupied_default_reuse_forbidden"):
        science.refuse_occupied_defaults("acrobot", (1.0, 1.0, 1.0))


def test_classify_and_meter_respect_caps():
    assert science.classify(0.2, 0.1, 0.3) == "persist_supported"
    assert science.classify(-0.2, -0.4, -0.1) == "persist_worse"
    assert science.classify(0.02, -0.1, 0.1) == "inconclusive"
    meter = science.BudgetMeter(2, 900)
    meter.charge(2)
    with pytest.raises(RuntimeError, match="env_cap"):
        meter.charge(1)
    assert meter.interrupt == "env_cap"


def test_dispatch_and_empty_scientific_entry_stay_refused():
    with pytest.raises(Exception, match="unnamed|holdout"):
        exe.execute_scientific(17280)
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(17280)
    imported = _imports(Path(science.__file__))
    assert "nexus.evolution3" not in imported
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
    assert lock.allocation_record()["authorized"] is False
