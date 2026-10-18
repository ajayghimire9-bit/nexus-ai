"""Gated persist-versus-reset executor. Development verify only. Not science."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import persist_reset_budget as budget
from nexus.evolution2 import persist_reset_executor as exe
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_roles as roles
from nexus.evolution2 import persist_reset_runner as runner
from nexus.evolution2.pendulum_acrobot_instance_rules import ROLE_DIGESTS


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_development_executor_plans_17280_six_fits_and_four_methods():
    payload = exe.write_artifact()
    assert payload["status"] == "DEVELOPMENT_PASS_SCIENCE_BLOCKED"
    assert payload["runner_readiness"] == "DEVELOPMENT_READY_SCIENCE_BLOCKED"
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["fitting"] is False
    assert payload["fits_executed"] == 0
    assert payload["env_steps"] == 0
    assert payload["granted_7680"] is False
    assert payload["hold_named"] is False
    assert payload["h17"] == "blocked"
    assert payload["budget"]["fresh_total"] == 17_280
    assert payload["budget"]["fits"] == 6
    assert payload["budget"]["methods"] == ["persist", "reset", "random", "evolution"]
    assert payload["budget"]["equal_budget"] is True
    assert sum(row["real_steps"] for row in payload["step_accounts"]) == 17_280
    assert len(payload["fits_planned"]) == 6
    assert all(row["status"] == "planned_not_executed" for row in payload["fits_planned"])
    assert {row["family"] for row in payload["fits_planned"]} == {"pendulum", "acrobot"}
    assert payload["path"]["methods_exercised"] == ["persist", "reset", "random", "evolution"]
    assert payload["path"]["hidden_development_blocked"] is True
    assert payload["path"]["reset_discarded"] is True
    assert len(set(payload["path"]["lookups_per_method"].values())) == 1
    assert payload["interruption"]["planned_real_steps"] == 17_280
    assert payload["interruption"]["env_steps_collected"] == 0
    assert payload["interruption"]["physical_unknown"]["real_steps"] >= 1
    assert payload["roles"]["status"] == "PASS"
    assert payload["roles"]["digests"] == dict(ROLE_DIGESTS)
    assert payload["readiness"]["status"] == "BLOCKED"
    assert payload["cited_config_sha256"] == lock.LOCKED_CONFIG
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
    assert lock.file_sha256(roles.H16) == roles.H16_SHA
    imported = _imports(Path(exe.__file__))
    assert "gymnasium" not in imported


def test_scientific_executor_and_dispatch_stay_blocked():
    with pytest.raises(Exception, match="unnamed|holdout"):
        exe.execute_scientific(17_280)
    with pytest.raises(Exception, match="unnamed|holdout"):
        exe.dispatch(17_280)
    with pytest.raises(Exception, match="unnamed|holdout"):
        runner.dispatch(17_280)
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(17_280)
    with pytest.raises(RuntimeError, match="blocked_until_independent_authorization"):
        runner.collect_fresh_source()
    with pytest.raises(RuntimeError, match="blocked_until_independent_authorization"):
        runner.fit_source_models()
    with pytest.raises(RuntimeError, match="occupied_default_persist"):
        budget.ready.refuse_source_reuse(7680)
    assert lock.allocation_record()["authorized"] is False
    assert lock.allocation_record()["env_cap"] == 0
