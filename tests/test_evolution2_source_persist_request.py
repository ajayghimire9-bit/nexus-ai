"""Source-only persist request. Does not collect."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import pendulum_acrobot_protocol_n3_micro as n3
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import source_persist_request as m


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_persist_request_is_hash_locked_and_unauthorized():
    assert m.file_sha256(m.CONFIG) == m.LOCKED_CONFIG
    assert m.file_sha256(m.PROTOCOL) == m.LOCKED_PROTOCOL
    assert m.file_sha256(m.ALLOCATION) == m.LOCKED_ALLOCATION
    record = m.allocation_record()
    assert record["authorized"] is True
    assert record["env_cap"] == 7680
    assert record["time_cap_s"] == 300
    assert record["config_sha256"] == "325cd42b99bd4ff03d7a993bda71272933bd9ed0644103cd55274ab2303a9c76"
    assert record["scientific_status"] == "development_pilot_not_confirmation"
    assert record["v2_source_steps"] == 25600
    assert record["n3_source_steps"] == 7680
    lock = m.public_lock()
    assert lock["authorized"] is True
    assert lock["env_cap"] == 7680
    assert lock["collection"] is False
    assert lock["status"] == "development_pilot_not_confirmation"
    with pytest.raises(RuntimeError, match="blocked"):
        m.require_scientific()


def test_persist_request_does_not_rewrite_or_write_arrays():
    assert m.prior_hashes_frozen() is True
    assert v2.worksheet()["source_collection_steps"] == 25600
    assert m.V2_SOURCE_STEPS == 25600
    assert m.N3_SOURCE_STEPS == 7680
    assert len(m.planned_files(10)) == 40
    assert len(m.planned_files(3)) == 12
    target = m.target_status()
    assert target["found"] == []
    assert target["empty"] is True
    payload = m.write_artifact()
    assert payload["collection"] is False
    assert payload["ledger_debit_s"] == 0
    assert n3.file_sha256(n3.CONFIG) == n3.LOCKED_CONFIG


def test_gated_dispatch_grants_only_7680_and_not_n_ten():
    assert m.option_for_cap(7680) == 3
    assert m.option_for_cap(25600) == 10
    with pytest.raises(RuntimeError, match="env_cap_must_be_7680_or_25600"):
        m.option_for_cap(900)
    assert m.persist_authorized(7680) is True
    assert m.persist_authorized(25600) is False
    with pytest.raises(RuntimeError, match="unauthorized"):
        m.dispatch(25600)
    runner = Path("scripts/run_evolution2_source_persist.py").read_text()
    assert "lock.dispatch" in runner
    assert "collect_transitions" not in runner
    assert "import gymnasium" not in runner


def test_persist_request_stays_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "torch" not in imported
    assert "numpy" not in imported
    assert "nexus.tasks.spec" not in imported
    assert "nexus.world.data" not in imported
    assert "nexus.evolution1.adapters" not in imported
    text = Path(m.__file__).read_text()
    assert "collect_transitions" not in text
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
