"""Source-only fit-clock lock. Does not train residual models."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import fit_clock as m
from nexus.evolution2 import pendulum_acrobot_protocol_n3_micro as n3
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import source_persist_request as persist


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_fit_clock_is_hash_locked_and_zero_step():
    assert m.file_sha256(m.CONFIG) == m.LOCKED_CONFIG
    assert m.file_sha256(m.PROTOCOL) == m.LOCKED_PROTOCOL
    assert m.file_sha256(m.ALLOCATION) == m.LOCKED_ALLOCATION
    record = m.allocation_record()
    assert record["authorized"] is True
    assert record["env_cap"] == 0
    assert record["time_cap_s"] == 300
    assert record["n_fits"] == 6
    assert record["config_sha256"] == m.LOCKED_CONFIG
    assert record["scientific_status"] == "development_pilot_not_confirmation"
    lock = m.public_lock()
    assert lock["authorized"] is True
    assert lock["env_cap"] == 0
    assert lock["n_fits"] == 6
    assert lock["collection"] is False
    assert lock["fitting"] is False
    with pytest.raises(RuntimeError, match="blocked"):
        m.require_scientific()


def test_fit_clock_does_not_rewrite_or_collect():
    assert m.prior_hashes_frozen() is True
    assert persist.file_sha256(persist.CONFIG) == persist.LOCKED_CONFIG
    assert v2.worksheet()["source_collection_steps"] == 25600
    assert n3.file_sha256(n3.CONFIG) == n3.LOCKED_CONFIG
    assert m.N_FITS == 6
    assert len(m.planned_fits()) == 6
    assert len(m.LOCKED_ARRAYS) == 12
    source = m.source_status()
    assert source["all_match"] is True
    payload = m.write_artifact()
    assert payload["collection"] is False
    assert payload["fitting"] is False
    assert payload["granted_env_cap"] == 0
    assert payload["granted_n_fits"] == 6
    assert payload["ledger_debit_s"] == 0


def test_gated_dispatch_grants_only_six_zero_step_fits():
    assert m.clock_authorized(0, 6) is True
    assert m.clock_authorized(7680, 6) is False
    assert m.clock_authorized(0, 20) is False
    with pytest.raises(RuntimeError, match="fit_clock_forbids_env_steps"):
        m.dispatch(25600, 6)
    with pytest.raises(RuntimeError, match="n3_fit_clock_is_not_v2_confirmation"):
        m.dispatch(0, 20)
    runner = Path("scripts/run_evolution2_fit_clock.py").read_text()
    assert "lock.dispatch" in runner
    assert "train_world_model" not in runner
    assert "import gymnasium" not in runner


def test_fit_clock_stays_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "torch" not in imported
    assert "numpy" not in imported
    assert "nexus.world.train" not in imported
    assert "nexus.world.data" not in imported
    assert "nexus.evolution1.adapters" not in imported
    text = Path(m.__file__).read_text()
    assert "collect_transitions" not in text
    assert "make_task_env" not in text
    assert "from nexus.world.train" not in text
    assert "import gymnasium" not in text
