"""Resource budget and real-path verification. Not a scientific experiment."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import persist_reset_budget as budget
from nexus.evolution2 import persist_reset_path as path
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_runner as runner


def _imports(path_name: Path) -> set[str]:
    tree = ast.parse(path_name.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_full_budget_is_17280_and_does_not_grant_7680():
    sheet = budget.resource_budget()
    assert sheet["do_not_grant_7680"] is True
    assert sheet["authorized_env_cap"] == 0
    assert sheet["real_environment"]["fresh_total"] == 17280
    assert sheet["real_environment"]["occupied_default_credit"] == 0
    assert sheet["imagined"]["screen_upper_bound"] == 14_745_600
    assert sheet["fits"]["n3_required"] == 6
    assert sheet["fits"]["twenty_measured"] is False
    assert sheet["standing"]["fresh_total_fits_standing_env"] is True
    with pytest.raises(RuntimeError, match="do_not_grant_7680"):
        budget.refuse_premature_7680(7680)
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(7680)
    with pytest.raises(Exception, match="unnamed|holdout"):
        runner.dispatch(17280)


def test_budget_module_stays_off_the_scientific_stack():
    imported = _imports(Path(budget.__file__))
    assert "gymnasium" not in imported
    assert "torch" not in imported
    text = Path(budget.__file__).read_text()
    assert "collect_transitions" not in text
    assert "from nexus.world.train" not in text
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
    assert lock.allocation_record()["authorized"] is False
    assert lock.allocation_record()["env_cap"] == 0


def test_real_execution_path_uses_planner_and_stays_blocked():
    payload = path.run_budget_verification()
    clocked = payload["clock"]
    verified = payload["execution_path"]
    assert payload["granted_7680"] is False
    assert payload["scientific"] is False
    assert clocked["n_decisions"] == 24
    assert clocked["env_steps"] == 0
    assert clocked["do_not_treat_as_scientific_clock"] is True
    assert verified["status"] == "PASS"
    assert verified["methods_exercised"] == ["persist", "reset", "random", "evolution"]
    assert set(verified["lookups_per_method"].values()) == {8}
    assert verified["persist_cross_family"] is True
    assert verified["reset_discarded"] is True
    assert verified["hidden_development_blocked"] is True
    assert verified["physical_planner_decisions"] == 24
    assert verified["twelve_arm_scientific"] == "BLOCKED"
    assert verified["gymnasium"] is False
    assert payload["readiness"]["scientific_execution_readiness"] == "BLOCKED"
    assert payload["h16_scientific_ledger_untouched"] is True
    imported = _imports(Path(path.__file__))
    assert "gymnasium" not in imported
    assert "collect_transitions" not in Path(path.__file__).read_text()
