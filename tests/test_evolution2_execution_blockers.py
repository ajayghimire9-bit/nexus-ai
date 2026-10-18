"""Source-only Evolution-2 execution-blocker matrix. No collection."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import execution_blockers as m
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_bound_checkpoint_payloads_are_weights_only():
    rows = m.payload_audit()
    assert len(rows) >= 6
    assert all(row["present"] for row in rows)
    assert all(row["zip"] for row in rows)
    assert all(row["weights_only"] for row in rows)
    assert all(row["transition_members"] == [] for row in rows)
    assert all(row["bytes"] < 40_000 for row in rows)


def test_blocker_matrix_keeps_dispatch_blocked():
    matrix = {row["id"]: row for row in m.blocker_matrix()}
    assert matrix["SOURCE_FITTING_UNAVAILABLE"]["status"] == "SOURCE_FITTING_UNAVAILABLE"
    assert matrix["WEIGHTS_ONLY_PAYLOAD"]["status"] == "confirmed"
    assert matrix["NO_FIT_TEN_BUNDLE_UNAVAILABLE"]["status"] == "NO_FIT_TEN_BUNDLE_UNAVAILABLE"
    assert matrix["N3_NOT_READY_RECIPE_MISMATCH"]["status"] == "not_v2_not_ready"
    assert matrix["FULL_V2_NO_GO"]["status"] == "NO-GO"
    assert matrix["H17_BLOCKED"]["status"] == "blocked"
    payload = m.write_artifact()
    assert payload["status"] == "E2_SCIENTIFIC_DISPATCH_BLOCKED"
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["v2_hashes_frozen"] is True
    assert payload["n3_hashes_frozen"] is True
    assert payload["ledger_debit_s"] == 0
    assert payload["scientific_ledger_preserved"] == [305.842, 3294.158]
    with pytest.raises(RuntimeError, match="blocked"):
        m.require_scientific()
    assert v2.file_sha256(v2.CONFIG) == v2.LOCKED_CONFIG


def test_blocker_module_stays_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "torch" not in imported
    assert "nexus.tasks.spec" not in imported
    assert "nexus.world.train" not in imported
    assert "nexus.evolution1.adapters" not in imported
    text = Path(m.__file__).read_text()
    assert "collect_transitions" not in text
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
