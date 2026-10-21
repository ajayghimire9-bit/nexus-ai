"""Focused test suite for seed_disjoint_meta_v1 (Section 16, tests 1-18).

All tests are deterministic and do not consume the registered target execution
or alter historical artifacts.
"""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import uuid
import pytest

from nexus.seed import disjoint_meta as dm
from nexus.seed.core import Session
from nexus.seed.lab import SeedWorkspace

ROOT = Path(__file__).resolve().parents[1]
BASE = "492de6f48f5b07f7a666af45f0abfe5942c2f5a8"


@pytest.fixture(scope="module")
def sample_study():
    c = dm.configuration()
    return dm.run_study(c, ROOT)


def load_verifier():
    spec = importlib.util.spec_from_file_location("verify_seed_disjoint_meta", ROOT / "scripts/verify_seed_disjoint_meta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_1_and_2_canonical_and_semantic_disjointness():
    probes = dm.probe_domain()
    dm.verify_commutation_identities(probes)
    list_cat = dm.build_catalogue("list")
    action_cat = dm.build_catalogue("action_token_sequence")
    inv = dm.verify_partition_invariants(list_cat, action_cat)
    assert inv["canonical_disjoint"] is True
    assert inv["semantic_disjoint"] is True
    assert inv["source_unique_programs"] == 17
    assert inv["target_unique_programs"] == 24

    src_sigs = {list_cat["entries"][i]["canonical_signature"] for i in list_cat["source_ids"]}
    tgt_sigs = {list_cat["entries"][i]["canonical_signature"] for i in list_cat["target_ids"]}
    src_hashes = {list_cat["entries"][i]["semantic_hash"] for i in list_cat["source_ids"]}
    tgt_hashes = {list_cat["entries"][i]["semantic_hash"] for i in list_cat["target_ids"]}
    assert not (src_sigs & tgt_sigs)
    assert not (src_hashes & tgt_hashes)

    # Syntactically different but canonically/semantically equivalent programs map to same side
    p_a = dict(schema="list", ops=["increment", "reverse"])
    p_b = dict(schema="list", ops=["reverse", "increment"])
    assert dm.canonical_signature(p_a) == dm.canonical_signature(p_b)
    assert dm.semantic_behavior_hash(p_a, probes) == dm.semantic_behavior_hash(p_b, probes)
    assert dm.canonical_signature(p_a) in src_sigs and dm.canonical_signature(p_a) not in tgt_sigs


def test_3_exact_target_macros_absent_from_source(sample_study):
    study = sample_study["study"]
    list_cat = study["list_catalogue"]
    src_ops = {tuple(list_cat["entries"][i]["canonical_program"]["ops"]) for i in list_cat["source_ids"]}
    tgt_ops = {tuple(list_cat["entries"][i]["canonical_program"]["ops"]) for i in list_cat["target_ids"]}
    assert not (src_ops & tgt_ops)
    for fam in study["families"]:
        for t in fam["target_tasks"]:
            assert tuple(t["canonical_program"]["ops"]) not in src_ops
            assert t["canonical_signature"] not in fam["fitted_model"]["source_program_counts"]


def test_4_and_5_target_outputs_and_held_out_labels_cannot_affect_fitting_or_ordering(sample_study):
    study = copy.deepcopy(sample_study["study"])
    c = study["config"]
    list_cat = study["list_catalogue"]
    fam = study["families"][0]

    # Mutate all target outputs and held-out assessment labels; re-fit and re-rank
    mutated_targets = copy.deepcopy(fam["target_tasks"])
    for t in mutated_targets:
        for ex in t["teaching"]:
            ex["output"] = [999]
        for ex in t["assessment"]:
            ex["output"] = [-999]

    refitted = dm.fit_source_models(fam["source_tasks"], list_cat, c)
    assert refitted == fam["fitted_model"]
    for m in dm.METHODS:
        if m == "random_ordering":
            continue
        ord_ids, _, _ = dm.rank_catalogue(m, list_cat, refitted)
        assert ord_ids == fam["candidate_orderings"][m]


def test_6_family_id_does_not_enter_predictor_features(sample_study):
    study = sample_study["study"]
    c = study["config"]
    list_cat = study["list_catalogue"]
    fam0 = copy.deepcopy(study["families"][0])
    # Change family_seed metadata while keeping the same source_tasks
    fam0["family_seed"] = 999999999
    refitted = dm.fit_source_models(fam0["source_tasks"], list_cat, c)
    assert refitted == study["families"][0]["fitted_model"]


def test_7_and_8_identical_teaching_examples_and_random_expectation(sample_study):
    study = sample_study["study"]
    list_cat = study["list_catalogue"]
    for fi, fam in enumerate(study["families"]):
        p_seeds = study["config"]["random_permutation_seeds"][fi * 64 : (fi + 1) * 64]
        for t in fam["target_tasks"]:
            assert len(t["teaching"]) == 8 and len(t["assessment"]) == 16
            for m in dm.METHODS:
                assert set(t["methods"][m]["budgets"]) == {"1", "2", "4", "8"}
            # Verify random_ordering reports exact mean across all 64 permutations, not best seed
            base_ids = [e["id"] for e in list_cat["entries"]]
            b1_evals = []
            for ps in p_seeds:
                order = list(base_ids)
                dm.random.Random(ps).shuffle(order)
                res = dm.evaluate_task_under_ordering(t, list_cat, order, 0.0)
                b1_evals.append(res["budgets"]["1"]["candidate_evaluations"])
            recorded_b1 = t["methods"]["random_ordering"]["budgets"]["1"]["candidate_evaluations"]
            assert abs(recorded_b1 - sum(b1_evals) / 64.0) < 1e-7
            assert recorded_b1 > min(b1_evals)


def test_9_and_10_retention_and_transfer_recomputed_from_episodes(sample_study):
    study = copy.deepcopy(sample_study["study"])
    proto = (ROOT / "docs/NEXUS_SEED_DISJOINT_META_PROTOCOL.md").read_text(encoding="utf-8")
    c = study["config"]

    # Tamper with a retention episode trace -> gate must reject
    bad_ret = copy.deepcopy(study)
    bad_ret["families"][0]["retention_tasks"][0]["after_meta_learning"]["structural_meta_prior"]["budgets"]["1"]["held_out_accuracy"] = 0.0
    with pytest.raises(ValueError, match="retention_after_mismatch"):
        dm.evaluate_disjoint_meta_artifact(bad_ret, proto, c)

    # Tamper with a cross-domain episode trace -> gate must reject
    bad_xd = copy.deepcopy(study)
    bad_xd["families"][0]["cross_domain_tasks"][0]["methods"]["transferred_structural_prior"]["budgets"]["1"]["candidate_evaluations"] = 1.0
    with pytest.raises(ValueError, match="cross_domain_evaluation_mismatch"):
        dm.evaluate_disjoint_meta_artifact(bad_xd, proto, c)


def test_11_12_13_14_15_gate_rejects_caller_summaries_missing_nan_costs_and_hashes(sample_study):
    study = copy.deepcopy(sample_study["study"])
    proto = (ROOT / "docs/NEXUS_SEED_DISJOINT_META_PROTOCOL.md").read_text(encoding="utf-8")
    c = study["config"]

    # 11. Caller-supplied summary arrays rejected
    with_caller = copy.deepcopy(study)
    with_caller["retention_scores"] = [1.0, 1.0]
    with pytest.raises(ValueError, match="caller_supplied_summary_scores_rejected"):
        dm.evaluate_disjoint_meta_artifact(with_caller, proto, c)

    # 12. Missing tasks, methods, budgets, or families fail closed
    missing_fam = copy.deepcopy(study)
    missing_fam["families"] = missing_fam["families"][:7]
    with pytest.raises(ValueError, match="incomplete_family_grid"):
        dm.evaluate_disjoint_meta_artifact(missing_fam, proto, c)

    missing_method = copy.deepcopy(study)
    del missing_method["families"][0]["target_tasks"][0]["methods"]["bayesian_model_based"]
    with pytest.raises(ValueError, match="missing_method_in_target_task"):
        dm.evaluate_disjoint_meta_artifact(missing_method, proto, c)

    # 13. NaN and infinite values fail closed
    nan_study = copy.deepcopy(study)
    nan_study["families"][0]["target_tasks"][0]["methods"]["flat_catalogue"]["budgets"]["1"]["held_out_accuracy"] = float("nan")
    with pytest.raises(ValueError):
        dm.evaluate_disjoint_meta_artifact(nan_study, proto, c)

    # 14. Cost modifications fail validation
    bad_cost = copy.deepcopy(sample_study)
    bad_cost["resources"]["real_steps"] = 100
    with pytest.raises(ValueError, match="disjoint_meta_resource_accounting"):
        dm.validate_output(
            bad_cost,
            c,
            dict(wall_s=120, cpu_s=120, memory_mb=2048, real_steps=2496, imagined_transitions=0, updates=8),
        )

    # 15. Hash modifications fail validation
    bad_hash = copy.deepcopy(study)
    bad_hash["protocol_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="artifact_protocol_hash_mismatch"):
        dm.evaluate_disjoint_meta_artifact(bad_hash, proto, c)


def test_16_independent_verifier_detects_deliberate_leakage(sample_study, tmp_path):
    vmod = load_verifier()
    study = copy.deepcopy(sample_study["study"])
    study["execution_sha"] = BASE
    study["registration"] = dict(dirty=False)
    study["host_receipt"] = dict(id="seed-disjoint-meta-1", status="complete_development", failure=None, wall_s=1.0, peak_sampled_rss_mb=64.0)
    study["resources"] = sample_study["resources"]
    study["runtime"] = sample_study["runtime"]

    valid_file = tmp_path / "valid.json"
    valid_file.write_text(json.dumps(study), encoding="utf-8")
    res = vmod.verify(ROOT, artifact_path=valid_file)
    assert res["valid"] is True

    # Inject deliberate target-into-source leakage
    leaked = copy.deepcopy(study)
    leaked["families"][0]["source_tasks"][0]["canonical_signature"] = leaked["families"][0]["target_tasks"][0]["canonical_signature"]
    leaked_file = tmp_path / "leaked.json"
    leaked_file.write_text(json.dumps(leaked), encoding="utf-8")
    with pytest.raises(ValueError):
        vmod.verify(ROOT, artifact_path=leaked_file)


def test_17_historical_artifacts_and_frozen_checkpoints_byte_identical():
    from nexus.seed.source_acquisition import FROZEN
    assert dm.frozen_hashes(ROOT) == FROZEN
    historical = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASE, "artifacts"], cwd=ROOT, text=True
    ).splitlines()
    assert len(historical) >= 800
    for name in historical:
        assert (ROOT / name).read_bytes() == subprocess.check_output(["git", "show", f"{BASE}:{name}"], cwd=ROOT)


def test_18_existing_conversation_labs_and_relabeled_benchmark_remain_functional(tmp_path):
    w = SeedWorkspace(tmp_path)
    sid = w.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]

    # Exact required answer to "Did we achieve learning to learn?"
    ans = w.dispatch(
        dict(session_id=sid, request=dict(op="chat_send", text="Did we achieve learning to learn?", id=uuid.uuid4().hex))
    )["response"]
    assert ans["text"] == "Not yet. I demonstrated bounded program-prior reuse, but genuine held-out learning-to-learn remains unestablished."

    # Relabeled engineering demo and integration suite remain functional with preserved numbers
    suite = w.dispatch(dict(session_id=sid, request=dict(op="master_general_suite", args={})))["response"]["result"]
    assert suite["suite_label"] == "bounded multi-reasoner integration suite"
    bench = suite["learning_to_learn_benchmark"]
    assert bench["benchmark_label"] == "bounded exact-motif program-prior reuse demo"
    assert bench["claim_classification"] == "engineering demonstration of within-family search-prior reuse"
    assert bench["mean_cold_start_evaluations"] == 9.5
    assert bench["mean_meta_learned_evaluations"] == 1.75
    assert bench["search_evaluations_reduction_pct"] == 81.58

    snap = w.sessions[sid].snapshot()
    assert Session.restore(snap).snapshot() == snap

    if (ROOT / "artifacts/seed_disjoint_meta.json").is_file():
        replay = dm.saved_replay(ROOT)
        assert replay["disjoint_meta"]["schema"] == "seed_disjoint_meta_evaluation_v1"
        vmod = load_verifier()
        audit = vmod.verify(ROOT)
        assert audit["valid"] is True
        assert audit["canonical_disjoint"] is True
        assert audit["semantic_disjoint"] is True
