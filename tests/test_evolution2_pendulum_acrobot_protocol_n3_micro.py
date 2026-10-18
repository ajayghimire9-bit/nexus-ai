"""Source-only n=3 micro contracts. Does not collect or rewrite v2."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import nofit_inventory as nofit
from nexus.evolution2 import pendulum_acrobot_protocol_n3_micro as m
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_n3_files_match_frozen_hashes_and_remain_unauthorized():
    assert m.file_sha256(m.CONFIG) == m.LOCKED_CONFIG
    assert m.file_sha256(m.PROTOCOL) == m.LOCKED_PROTOCOL
    assert m.file_sha256(m.ALLOCATION) == m.LOCKED_ALLOCATION
    record = m.allocation_record()
    assert record["authorized"] is False
    assert record["runs"] == 0
    assert record["hold_named"] is False
    assert record["recipe_matched"] is False
    assert record["n_bundles"] == 3
    assert record["df"] == 2
    lock = m.public_lock()
    assert lock["authorized"] is False
    assert lock["collection"] is False
    assert lock["status"] == "not_v2_not_ready"
    with pytest.raises(RuntimeError, match="unauthorized"):
        m.require_scientific()


def test_n3_does_not_rewrite_v2_or_pilot():
    assert m.prior_hashes_frozen() is True
    assert v2.N_BUNDLES == 10
    assert v2.CI_DF == 9
    assert list(m.DOES_NOT_REWRITE) == ["v2", "v2-pilot"]
    sheet = m.worksheet()
    assert sheet["first_screen_total_steps"] == 9600
    assert sheet["first_screen_imagined_upper_bound"] == 14745600
    assert sheet["source_collection_steps"] == 0
    assert sheet["source_fitting_s"] == 0
    assert sheet["first_screen_total_steps"] < sheet["pilot_first_screen_total_steps"]
    assert sheet["first_screen_total_steps"] < sheet["v2_first_screen_total_steps"]
    assert nofit.nofit_worksheets()["micro_feasibility"] == "NOT_V2"


def test_n3_binds_six_hash_locked_unmatched_files():
    rows = m.bound_files()
    assert [row["id"] for row in rows] == list(m.BOUND_IDS)
    assert all(row["matches"] for row in rows)
    assert {row["family"] for row in rows} == {"pendulum", "acrobot"}
    assert m.RECIPE_MATCHED is False


def test_n3_gate_rejects_v2_sample_size_and_df9_crit():
    with pytest.raises(m.ContractError, match="invalid_replication"):
        m.student_t_interval([0.1] * 10, m.BONFERRONI_T_CRIT_DF2)
    with pytest.raises(m.ContractError, match="v2_df9_crit_forbidden"):
        m.student_t_interval([0.2, 0.2, 0.2], v2.BONFERRONI_T_CRIT_DF9)
    mean, lo, hi = m.student_t_interval([0.2, 0.2, 0.2], m.BONFERRONI_T_CRIT_DF2)
    assert mean == pytest.approx(0.2)
    assert lo == pytest.approx(0.2)
    assert hi == pytest.approx(0.2)
    controls = {key: [0.2, 0.2, 0.2] for key in v2.PRIMARY_CONTROLS}
    assert m.hypothetical_gate(controls, 1.0) == "transfer_screen_passed"
    assert m.primary_gate(controls, 1.0) == "not_ready_recipe_mismatch"
    weak = {key: [0.01, 0.0, -0.01] for key in v2.PRIMARY_CONTROLS}
    assert m.hypothetical_gate(weak, 1.0) == "inconclusive"
    harm = {key: [-0.4, -0.4, -0.4] for key in v2.PRIMARY_CONTROLS}
    assert m.hypothetical_gate(harm, 1.0) == "negative_transfer"


def test_n3_source_stays_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "torch" not in imported
    assert "nexus.tasks.spec" not in imported
    assert "nexus.evolution1.adapters" not in imported
    text = Path(m.__file__).read_text()
    assert "collect_transitions" not in text
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
