"""Source-only no-fit residual inventory. No collection."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import nofit_inventory as m
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as pilot
from nexus.evolution2 import residual_timing_probe as timing


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_nofit_ten_bundle_is_unavailable_and_hash_locked():
    rows = m.inventory()
    assert len(rows) == 13
    assert all(row["matches"] for row in rows)
    counts = m.family_counts()
    assert counts == {"pendulum": 3, "acrobot": 10}
    status = m.nofit_status()
    assert status["status"] == "NO_FIT_TEN_BUNDLE_UNAVAILABLE"
    assert status["shortfall"] == {"pendulum": 7, "acrobot": 0}
    assert status["recipe_matched"] is False
    assert "checkpoints/acrobot_lookahead_confirm_h16" in status["excluded"]
    with pytest.raises(RuntimeError, match="unauthorized"):
        m.require_scientific()


def test_seed0_identities_match_timing_probe():
    by_path = {row["path"]: row for row in m.inventory()}
    for spec in timing.REQUIRED_CHECKPOINTS:
        if spec["id"] in {"pendulum_residual_mlp", "acrobot_lookahead_seed0"}:
            assert by_path[spec["path"]]["expected_sha256"] == spec["sha256"]
            assert by_path[spec["path"]]["matches"] is True


def test_nofit_worksheets_do_not_rewrite_v2_or_invent_fits():
    sheets = m.nofit_worksheets()
    assert sheets["source_fitting_s"] == 0
    assert sheets["fitting_status"] == "SOURCE_FITTING_UNAVAILABLE"
    assert sheets["rewrites_v2"] is False
    assert sheets["v2_nofit_real_steps"] == 72000
    assert sheets["v2_nofit_imagined"] == 110592000
    assert sheets["v2_nofit_feasibility"] == "NO-GO"
    assert sheets["pilot_nofit_real_steps"] == 32000
    assert sheets["pilot_nofit_imagined"] == 49152000
    assert sheets["pilot_nofit_feasibility"] == "BLOCKED"
    assert sheets["micro_n"] == 3
    assert sheets["micro_real_steps"] == 9600
    assert sheets["micro_imagined"] == 14745600
    assert sheets["micro_feasibility"] == "NOT_V2"
    assert v2.file_sha256(v2.CONFIG) == v2.LOCKED_CONFIG
    assert pilot.v2_hashes_frozen() is True


def test_artifact_preserves_ledger_and_forbids_science():
    payload = m.write_artifact()
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["modifies_checkpoints"] is False
    assert payload["ledger_debit_s"] == 0
    assert payload["scientific_ledger_preserved"] == [305.842, 3294.158]
    assert payload["v2_hashes_frozen"] is True
    assert "NO_FIT_TEN_BUNDLE_UNAVAILABLE" in payload["blockers"]


def test_inventory_stays_off_the_scientific_stack():
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
