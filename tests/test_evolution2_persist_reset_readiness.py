"""Pre-authorization persist-versus-reset audit. Not a scientific experiment."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import persist_reset_dry_run as dry
from nexus.evolution2 import persist_reset_planner_audit as planner
from nexus.evolution2 import persist_reset_readiness as ready
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_runner as runner
from nexus.evolution2.pendulum_acrobot_protocol_v2 import bundle_family_order


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_locked_request_hashes_and_refusal_are_unchanged():
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
    assert lock.file_sha256(lock.PROTOCOL) == lock.LOCKED_PROTOCOL
    assert lock.file_sha256(lock.ALLOCATION) == lock.LOCKED_ALLOCATION
    assert lock.allocation_record()["authorized"] is False
    assert lock.allocation_record()["env_cap"] == 0
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(17280)
    with pytest.raises(Exception, match="unnamed|holdout"):
        runner.dispatch(17280)


def test_fresh_total_is_17280_and_7680_is_not_credit():
    sheet = ready.step_worksheet()
    assert sheet["occupied_default_persist_steps"] == 7680
    assert sheet["n3_revealed_development_worksheet"] == 9600
    assert sheet["fresh_source_steps_required"] == 7680
    assert sheet["fresh_total_environment_steps"] == 17280
    assert sheet["occupied_defaults_are_not_credit"] is True
    with pytest.raises(RuntimeError, match="occupied_default_persist"):
        ready.refuse_source_reuse(7680)
    with pytest.raises(RuntimeError, match="omits_fresh_matched_source"):
        ready.refuse_source_reuse(9600)
    with pytest.raises(RuntimeError, match="17280"):
        ready.refuse_source_reuse(25600)
    ready.refuse_source_reuse(17280)
    report = ready.scientific_readiness(17280)
    assert report["status"] == "BLOCKED"
    assert report["holdout_integrity"] == "BLOCKED"
    assert report["real_source_fitting_path"] == "BLOCKED"
    assert report["scientific_execution_readiness"] == "BLOCKED"
    assert "holdout_unnamed" in report["blockers"]
    assert "unauthorized" in report["blockers"]


def test_bonferroni_threshold_stays_low_power_and_not_n10():
    note = ready.bonferroni_lock()
    assert note["t_crit"] == 9.924843200918293
    assert note["df"] == 2
    assert note["comparisons_locked"] == 5
    assert note["not_n10_confirmation"] is True
    assert "low-power" in note["low_power"]
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG


def test_independent_dry_run_audit_confirms_four_methods_and_isolation():
    payload = dry.run_development_dry_run(seed=7)
    audit = ready.audit_development_dry_run()
    assert payload["dry_run"] == "PASS"
    assert audit["status"] == "PASS"
    assert audit["four_methods_exercised"] is True
    assert audit["persist_retained"] is True
    assert audit["reset_discarded"] is True
    assert audit["equal_budget"] is True
    assert audit["development_not_training_feedback"] is True
    assert audit["scientific"] is False


def test_real_planner_binding_covers_twelve_variants():
    result = planner.audit_real_planner()
    assert result["status"] == "PASS"
    assert result["n_bound"] == 24
    assert result["n_real_planner_rows"] == 24
    assert result["physical_decisions"] == 24
    assert result["cached_replays"] == 2
    assert result["scientific_dispatch"] == "BLOCKED"
    assert result["checkpoint_compatible"] is True
    assert result["gymnasium"] is False


def test_refuse_only_runner_preserves_design_without_science():
    schedule = runner.bundle_schedule()
    assert [row["family_order"] for row in schedule] == [
        list(bundle_family_order(0)),
        list(bundle_family_order(1)),
        list(bundle_family_order(2)),
    ]
    with pytest.raises(RuntimeError, match="blocked_until_independent_authorization"):
        runner.collect_fresh_source()
    with pytest.raises(RuntimeError, match="blocked_until_independent_authorization"):
        runner.fit_source_models()
    with pytest.raises(RuntimeError, match="blocked_until_independent_authorization"):
        runner.reveal_training_feedback()
    with pytest.raises(RuntimeError, match="blocked_until_independent_authorization"):
        runner.hidden_development_evaluation()
    with pytest.raises(RuntimeError, match="blocked_until_independent_authorization"):
        runner.run_scientific()
    imported = _imports(Path(runner.__file__)) | _imports(Path(ready.__file__))
    assert "gymnasium" not in imported
    assert "torch" not in imported
    yaml_text = Path("configs/evolution2_persist_reset_request.yaml").read_text()
    assert "authorized: false" in yaml_text
    assert lock.allocation_record()["authorized"] is False
    payload = ready.write_artifact()
    assert payload["scientific"] is False
    assert payload["worksheet"]["fresh_total_environment_steps"] == 17280
    costs = Path(ready.__file__).read_text()
    assert "collect_transitions" not in costs
    assert "from nexus.world.train" not in Path(runner.__file__).read_text()
