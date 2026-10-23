"""Structural proofs for the v3 high-headroom investigation benchmark."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.v3_headroom import (
    ALL_SPECS, CALL_BUDGET, MIN_HYPOTHESES, SET_A, SET_B, SPECIALIST_PROBES,
    automatic_signature, brute_force_coverage, cluster_programs, conditioned_order,
    disagreement, disjoint_operator_sets, execute_v3, frequency_waste_ratio,
    hypothesis_count, interleaved_catalogue, names, orthogonality_report, phi_key,
    structural_certificate, support_io_invariant, train_phi,
)


ROOT = Path(__file__).resolve().parents[1]


def test_depth12_grids_are_not_this_benchmark():
    config = json.loads((ROOT / "configs/seed_v3_headroom.json").read_text())
    assert config["id"] == "seed-v3-headroom-1"
    assert config["rescore_depth12"] is False
    assert config["learning_research_resumed"] is False
    assert config["learned_ranking_promoted"] is False
    assert config["call_budget"] == CALL_BUDGET == 35
    assert set(config["set_a"]) == set(names("A"))
    assert set(config["set_b"]) == set(names("B"))
    assert not set(config["set_a"]) & set(config["set_b"])


def test_four_orthogonal_specialist_probes():
    for set_id in ("A", "B"):
        report = orthogonality_report(set_id)
        assert report["all_specialists_orthogonal"] is True
        for row in report["rows"]:
            assert row["native_partitions"] > 1
            assert row["zero_foreign_disagreement"] is True
            assert set(row["foreign_partitions"].values()) == {1}


def test_cluster1_probe_has_zero_disagreement_on_other_clusters():
    probe = SPECIALIST_PROBES["filter"]
    assert disagreement(probe, cluster_programs("A", "filter")) > 1
    for cluster in ("mod", "order", "group"):
        assert disagreement(probe, cluster_programs("A", cluster)) == 1
        assert disagreement(probe, cluster_programs("B", cluster)) == 1


def test_simple_frequency_wastes_three_times_more_calls():
    waste = frequency_waste_ratio("A", "filter")
    assert waste["query_conditioned_calls"] == len(cluster_programs("A", "filter"))
    assert waste["simple_frequency_calls"] / waste["query_conditioned_calls"] >= 3.9
    assert waste["extra_factor"] >= 2.9
    assert waste["guarantees_3x_more"] is True
    order = interleaved_catalogue("A")
    assert order[0] != order[1]
    assert {ALL_SPECS[order[i][0]].cluster for i in range(4)} == {"filter", "mod", "order", "group"}


def test_hypothesis_space_is_depth_3_4_and_above_2500():
    coverage = brute_force_coverage()
    assert hypothesis_count("A") == 12 ** 3 + 12 ** 4
    assert coverage["hypothesis_count"] > MIN_HYPOTHESES
    assert coverage["call_budget"] == 35
    assert coverage["brute_force_fraction"] < 0.30
    assert coverage["below_30pct_if_one_call_per_program"] is True


def test_phi_keys_are_invariants_not_operator_ids():
    sets = disjoint_operator_sets()
    assert sets["disjoint"] is True
    assert sets["a_count"] == sets["b_count"] == 12
    assert sets["signature_classes_match"] is True
    assert "keep_pos" not in sets["a_signatures"]
    key = phi_key("length_contracting", automatic_signature("keep_pos"))
    assert key[1] == automatic_signature("keep_neg")
    assert key[1] not in ALL_SPECS
    examples = [
        (SPECIALIST_PROBES["filter"], execute_v3(("keep_pos", "keep_pos", "keep_pos"), SPECIALIST_PROBES["filter"])),
    ]
    assert support_io_invariant(examples) == "length_contracting"
    weights = train_phi([{
        "support": examples,
        "consistent_ops": ["keep_pos", "keep_even"],
    }])
    assert all(name not in key for key in weights for name in names("A") + names("B"))
    b_score = next(iter(weights.values()))
    assert weights[phi_key("length_contracting", automatic_signature("keep_neg"))] == b_score


def test_conditioned_rank_prefers_matching_signatures_on_set_b():
    order = conditioned_order("B", "length_contracting")
    first = cluster_programs("B", "filter")
    assert set(order[: len(first)]) == set(first)


def test_structural_certificate_does_not_claim_transfer():
    cert = structural_certificate()
    assert cert["orthogonal"] is True
    assert cert["learning_to_learn_established"] is False
    assert cert["learned_ranking_promoted"] is False
    assert cert["ready_for_transfer_experiment"] is False
    assert cert["phi_key_uses_operator_name"] is False
    assert cert["frequency_waste"]["guarantees_3x_more"] is True
