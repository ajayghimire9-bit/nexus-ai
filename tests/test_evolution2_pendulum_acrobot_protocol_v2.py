"""Source-only v2 fairness, operator, and resource contracts. No collection."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from nexus.evolution1.catalogue import Generator, Rule, Variant, catalogue
from nexus.evolution2 import pendulum_acrobot_protocol as v1
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as m


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_v2_files_match_frozen_hashes_and_remain_unauthorized():
    assert m.file_sha256(m.CONFIG) == m.LOCKED_CONFIG
    assert m.file_sha256(m.PROTOCOL) == m.LOCKED_PROTOCOL
    assert m.file_sha256(m.ALLOCATION) == m.LOCKED_ALLOCATION
    assert m.file_sha256(m.V1_PROTOCOL) == v1.LOCKED_PROTOCOL
    record = m.allocation_record()
    assert record["authorized"] is False
    assert record["runs"] == 0
    assert record["hold_named"] is False
    assert record["locked_target"] is None
    assert record["crossover"] is False
    lock = m.public_lock()
    assert lock["authorized"] is False
    assert lock["collection"] is False
    assert lock["supersedes"] == "v1"
    assert m.live_named_holdout() is None
    with pytest.raises(RuntimeError, match="unauthorized"):
        m.require_scientific()
    with pytest.raises(RuntimeError, match="unnamed"):
        m.require_named_holdout()


def test_methods_include_two_anchors_and_no_crossover():
    assert [row["id"] for row in m.METHODS] == ["A1", "A2", "B", "C", "D", "E"]
    assert m.PRIMARY_CONTROLS == ("B", "C", "E", "A1", "A2")
    a1, a2 = m.anchors()
    assert (a1.rule, a1.generator, a1.horizon) == (Rule.FLAT, Generator.IID, 16)
    assert (a2.rule, a2.generator, a2.horizon) == (Rule.SUCCESSOR, Generator.IID, 16)
    assert len(catalogue()) == m.N_VARIANTS == 12
    assert m.SEARCH_SLOTS == 4
    assert m.EVOLUTION_POPULATION == 4
    assert m.EVOLUTION_TOURNAMENT == 2
    assert m.existing_evolution_implements_population_tournament() is True
    with pytest.raises(m.ContractError, match="crossover"):
        m.refuse_crossover()


def test_legal_mutation_flips_one_coordinate_only():
    parent = Variant(Rule.FLAT, Generator.IID, 8)
    mutants = m.legal_mutants(parent)
    assert mutants
    for child in mutants:
        m.assert_legal_mutation(parent, child)
    illegal = Variant(Rule.SUCCESSOR, Generator.BALANCED, 8)
    with pytest.raises(m.ContractError, match="illegal_mutation"):
        m.assert_legal_mutation(parent, illegal)
    with pytest.raises(m.ContractError, match="illegal_mutation"):
        m.assert_legal_mutation(parent, parent)


def test_bundles_are_paired_and_counterbalanced():
    even = m.paired_bundle_seeds(0)
    odd = m.paired_bundle_seeds(1)
    assert m.bundle_family_order(0) == ("pendulum", "acrobot")
    assert m.bundle_family_order(1) == ("acrobot", "pendulum")
    names = [row["name"] for row in m.METHODS]
    for name in names:
        assert even[name]["model_seed"] == even[names[0]]["model_seed"]
        assert even[name]["planner_seed"] == even[names[0]]["planner_seed"]
        assert even[name]["proposal_seed"] == even[names[0]]["proposal_seed"]
    assert even["persist"]["model_seed"] != odd["persist"]["model_seed"]
    with pytest.raises(m.ContractError):
        m.bundle_family_order(10)


def test_occupied_defaults_cannot_be_new_sources():
    assert m.reject_new_instance("pendulum", (10.0, 1.0, 1.0)) == (
        "occupied_default_not_a_new_source"
    )
    assert m.reject_new_instance("acrobot", (1.0, 1.0, 1.0)) == (
        "occupied_default_not_a_new_source"
    )
    assert m.reject_new_instance("pendulum", (17.1, 1.5, 0.8)) == "occupied_pendulum"
    assert m.reject_new_instance("mountaincar_continuous", (0.0025, 0.0015, 0.07)) == (
        "forbidden_family"
    )
    with pytest.raises(m.ContractError, match="weight_transfer"):
        m.refuse_weight_transfer("pendulum", "acrobot")
    m.refuse_weight_transfer("acrobot", "acrobot")


def test_bonferroni_gate_and_undefined_range():
    win = {key: [0.2] * 10 for key in m.PRIMARY_CONTROLS}
    assert m.primary_gate(win, 1.0) == "transfer_screen_passed"
    zero = {key: [0.0] * 10 for key in m.PRIMARY_CONTROLS}
    assert m.primary_gate(zero, 1.0) == "inconclusive"
    loss = {key: [-0.2] * 10 for key in m.PRIMARY_CONTROLS}
    assert m.primary_gate(loss, 1.0) == "negative_transfer"
    with pytest.raises(m.ContractError, match="undefined_reward_range"):
        m.normalize_delta(1.0, 0.0)
    with pytest.raises(m.ContractError, match="invalid_integrity"):
        m.primary_gate({"B": [0.2] * 10}, 1.0)
    with pytest.raises(m.ContractError, match="invalid_integrity"):
        m.primary_gate({key: [float("nan")] * 10 for key in m.PRIMARY_CONTROLS}, 1.0)


def test_worksheet_matches_feasibility_and_stays_unauthorized():
    sheet = m.worksheet()
    assert sheet["source_collection_steps"] == 25600
    assert sheet["training_matrix_steps"] == 48000
    assert sheet["development_evaluation_steps"] == 24000
    assert sheet["first_screen_total_steps"] == 97600
    assert sheet["first_screen_imagined_upper_bound"] == 110592000
    assert sheet["authorized_env_cap"] == 0
    assert m.worksheet_fits_standing_interactions()
    assert m.wall_clock_risk() == "likely_incomplete_budget_under_900s"
    assert m.budget_outcome(complete=False, exhausted=True) == "incomplete_budget"
    assert m.budget_outcome(complete=True, exhausted=False) is None
    bound = m.three_action_bound(m.anchors()[0])
    assert 0 < bound.imagined_per_decision <= m.IMAGINED_CAP_PER_DECISION


def test_v2_source_stays_off_the_scientific_stack():
    imported = _imports(Path(m.__file__))
    assert "gymnasium" not in imported
    assert "nexus.evolution1.adapters" not in imported
    assert "nexus.tasks.spec" not in imported
    text = Path(m.__file__).read_text()
    assert "make_task_env" not in text
    assert "import gymnasium" not in text
    readiness = m.READINESS.read_text()
    assert "NOT_READY_FOR_SCIENTIFIC_EXECUTION" in readiness
