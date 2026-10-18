"""Source-only v2-pilot worksheet. Does not collect or rewrite v2."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import pendulum_acrobot_protocol_v2_pilot as m


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_pilot_files_match_frozen_hashes_and_remain_unauthorized():
    assert m.file_sha256(m.CONFIG) == m.LOCKED_CONFIG
    assert m.file_sha256(m.PROTOCOL) == m.LOCKED_PROTOCOL
    assert m.file_sha256(m.ALLOCATION) == m.LOCKED_ALLOCATION
    record = m.allocation_record()
    assert record["authorized"] is False
    assert record["runs"] == 0
    assert record["hold_named"] is False
    assert record["locked_target"] is None
    assert record["does_not_rewrite"] == "v2"
    lock = m.public_lock()
    assert lock["authorized"] is False
    assert lock["collection"] is False
    assert lock["does_not_rewrite"] == "v2"
    with pytest.raises(RuntimeError, match="unauthorized"):
        m.require_scientific()


def test_v2_hashes_are_not_rewritten():
    assert m.v2_hashes_frozen()
    assert v2.file_sha256(v2.CONFIG) == v2.LOCKED_CONFIG
    assert v2.file_sha256(v2.PROTOCOL) == v2.LOCKED_PROTOCOL
    assert v2.file_sha256(v2.ALLOCATION) == v2.LOCKED_ALLOCATION
    sheet_v2 = v2.worksheet()
    assert sheet_v2["first_screen_total_steps"] == 97600
    assert sheet_v2["first_screen_imagined_upper_bound"] == 110592000


def test_pilot_keeps_n_ten_and_five_bonferroni_controls():
    sheet = m.worksheet()
    assert sheet["independent_bundles"] == 10
    assert sheet["bonferroni_comparisons"] == 5
    assert sheet["practical_margin"] == 0.05
    assert list(m.public_lock()["primary_controls"]) == ["B", "C", "E", "A1", "A2"]
    assert v2.PRIMARY_CONTROLS == ("B", "C", "E", "A1", "A2")
    assert v2.N_BUNDLES == 10


def test_pilot_worksheet_charges_six_revealed_rows_and_two_conditions():
    sheet = m.worksheet()
    assert sheet["revealed_variants_per_family"] == 6
    assert sheet["development_conditions"] == 2
    assert sheet["source_collection_steps"] == 25600
    assert sheet["revealed_training_steps"] == 24000
    assert sheet["development_evaluation_steps"] == 8000
    assert sheet["first_screen_total_steps"] == 57600
    assert sheet["first_screen_imagined_upper_bound"] == 49152000
    assert sheet["first_screen_total_steps"] < sheet["v2_first_screen_total_steps"]
    assert (
        sheet["first_screen_imagined_upper_bound"]
        < sheet["v2_first_screen_imagined_upper_bound"]
    )
    assert sheet["authorized_env_cap"] == 0
    assert sheet["first_screen_total_steps"] <= sheet["standing_env_cap"]
    assert abs(sheet["historical_planning_s"] - 271.76) < 0.1
    assert m.wall_clock_risk() == "more_plausible_than_v2_still_unproven"


def test_revealed_cache_is_shared_and_hits_are_still_charged():
    revealed = v2.anchors()
    caches = m.equal_information_cache(revealed)
    names = [row["name"] for row in v2.METHODS]
    shared = caches[names[0]]
    assert all(caches[name] is shared for name in names)
    first = shared.evaluate("persist", revealed[0])
    second = shared.evaluate("reset", revealed[0])
    assert first == second == 1.0
    assert shared.charged == 2
    assert shared.cached == 1
    assert shared.physical == 1
    with pytest.raises(RuntimeError, match="score_substitution_forbidden"):
        shared.reveal("persist", revealed[0], 9.9)
    unused = next(v for v in v2.legal_mutants(revealed[0]) if v not in revealed)
    assert unused not in revealed
    with pytest.raises(RuntimeError, match="unused_variant_not_revealed"):
        shared.evaluate("persist", unused)
    assert m.charge_imagined(2) == 2 * v2.IMAGINED_CAP_PER_DECISION


def test_pilot_source_stays_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "nexus.evolution1.adapters" not in imported
    assert "nexus.tasks.spec" not in imported
    text = Path(m.__file__).read_text()
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
