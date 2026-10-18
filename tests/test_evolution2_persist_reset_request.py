"""Source-only persist-versus-reset request. Does not collect."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import persist_reset_request as m
from nexus.evolution2 import pendulum_acrobot_protocol_n3_micro as n3
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2.methods import make_methods


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_persist_reset_request_is_hash_locked_and_unauthorized():
    assert m.file_sha256(m.CONFIG) == m.LOCKED_CONFIG
    assert m.file_sha256(m.PROTOCOL) == m.LOCKED_PROTOCOL
    assert m.file_sha256(m.ALLOCATION) == m.LOCKED_ALLOCATION
    record = m.allocation_record()
    assert record["authorized"] is False
    assert record["env_cap"] == 0
    assert record["hold_named"] is False
    assert record["config_sha256"] == m.LOCKED_CONFIG
    lock = m.public_lock()
    assert lock["authorized"] is False
    assert lock["hold_named"] is False
    assert lock["collection"] is False
    assert lock["twenty_fit_measured"] is False
    assert lock["methods"] == ["persist", "reset", "random", "evolution"]
    with pytest.raises(RuntimeError, match="unauthorized|unnamed"):
        m.require_scientific()
    with pytest.raises(Exception, match="unnamed|holdout"):
        m.require_named_holdout()


def test_persist_reset_does_not_rewrite_or_name_a_holdout():
    assert m.prior_hashes_frozen() is True
    assert v2.worksheet()["source_collection_steps"] == 25600
    assert n3.file_sha256(n3.CONFIG) == n3.LOCKED_CONFIG
    assert n3.CI_DF == 2
    sheet = m.worksheet()
    assert sheet["df"] == 2
    assert sheet["bonferroni_t_crit"] == n3.BONFERRONI_T_CRIT_DF2
    assert sheet["occupied_defaults_are_not_holdout"] is True
    assert sheet["disposable_weights_are_not_confirmation"] is True
    assert sheet["twenty_fit_measured"] is False
    payload = m.write_artifact()
    assert payload["collection"] is False
    assert payload["holdout_review"] == "NAMING_BLOCKED"
    assert payload["ledger_debit_s"] == 0
    assert m.persist_reset_authorized(7680) is False
    with pytest.raises(Exception, match="unnamed|holdout"):
        m.dispatch(7680)


def test_equal_budget_methods_already_exist():
    methods = make_methods(seed=7)
    assert set(methods) >= {"random", "reset_adaptive", "persistent_adaptive", "evolutionary"}
    runner = Path("scripts/run_evolution2_persist_reset.py").read_text()
    assert "lock.dispatch" in runner
    assert "collect_transitions" not in runner


def test_persist_reset_request_stays_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "torch" not in imported
    assert "numpy" not in imported
    text = Path(m.__file__).read_text()
    assert "collect_transitions" not in text
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
