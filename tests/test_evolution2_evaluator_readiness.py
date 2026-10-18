"""Source-only Evolution-2.10 readiness. No training or collection."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution2 import evaluator_readiness as m
from nexus.evolution2 import fit_clock as clock
from nexus.evolution2 import source_persist_request as persist


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_six_fit_clock_is_observed_not_extrapolated():
    report = m.verify_six_fit_clock()
    assert report["n_fits_observed"] == 6
    assert report["twenty_fit_measured"] is False
    assert report["do_not_extrapolate"] is True
    assert report["arrays_match"] is True
    assert report["weights_match"] is True
    assert report["repeat_write"] == "duplicate_or_partial_fit_clock"


def test_ledgers_stay_distinct_and_h16_untouched():
    records = m.ledger_records()
    assert records["distinct"] is True
    assert records["silently_merged"] is False
    assert records["h16_scientific"]["consumed_s"] == 305.842
    assert records["h16_scientific"]["debit"] is False
    assert records["source_persist_7680"]["env_steps"] == 7680
    assert records["source_persist_7680"]["h16_untouched"] is True
    assert records["fit_clock"]["n_fits"] == 6
    assert records["fit_clock"]["h16_untouched"] is True
    assert records["inference_probe"]["distinct_from_h16_file"] is True
    assert persist.file_sha256(persist.CONFIG) == persist.LOCKED_CONFIG
    assert clock.file_sha256(clock.CONFIG) == clock.LOCKED_CONFIG


def test_all_twelve_variants_bind_and_science_stays_blocked():
    bound = m.development_bindings()
    assert bound["n"] == 24
    assert bound["all_bound"] is True
    assert bound["scientific"] is False
    with pytest.raises(RuntimeError, match="blocked"):
        m.require_scientific()
    matrix = {row["id"]: row["status"] for row in m.readiness_matrix()}
    assert matrix["development_twelve_arm_binding"] == "PASS"
    assert matrix["scientific_experiment_authorization"] == "BLOCKED"
    assert matrix["twenty_fit_v2_clock"] == "UNAVAILABLE"
    assert matrix["holdout_named"] == "BLOCKED"
    payload = m.write_artifact()
    assert payload["enabled_dispatch"] is False
    assert payload["v2_hashes_rewritten"] is False
    assert payload["smallest_scientific_experiment"]["authorized"] is False
    assert payload["smallest_scientific_experiment"]["complete"] is False


def test_readiness_stays_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert imported.isdisjoint({"gymnasium", "torch", "numpy"})
    text = Path(m.__file__).read_text()
    assert "collect_transitions" not in text
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
