"""Tests for Steps 1-5:
1. Source-only Input-Output Signature Audit (seed_signature_audit_v1)
2. Task-Conditioned Program Ranking S(p | D)
3. Deterministic vs Bayesian vs Linear Ranker comparison
4. Fresh Sealed 6-Operator Compositional Replication (seed_task_conditioned_replication_v1)
5. Real Cross-Lab Transfer (seed_cross_lab_transfer_v1)
"""
import json
from pathlib import Path

from nexus.evolution1.catalogue import digest
from nexus.seed import cross_lab_transfer as xlab
from nexus.seed import disjoint_meta as dm
from nexus.seed import signature_audit as sig_mod
from nexus.seed import task_conditioned_meta as tcm

ROOT = Path(__file__).resolve().parents[1]


def test_step1_source_only_signature_audit() -> None:
    audit_path = ROOT / "artifacts" / "seed_signature_audit.json"
    assert audit_path.exists()
    report = json.loads(audit_path.read_text(encoding="utf-8"))
    assert report["schema"] == "seed_signature_audit_v1"
    assert report["target_outcomes_accessed"] is False
    assert report["source_program_count"] == 17
    assert report["unique_source_signature_count"] == 17
    assert report["signature_dimension"] == 17
    assert len(sig_mod.SIGNATURE_FEATURE_NAMES) == 17
    assert len(report["clue_group_statistics"]) == 6
    assert report["audit_passed"] is True
    assert (
        report["loso_source_evaluations"]["deterministic_signature"]
        < report["loso_source_evaluations"]["flat_catalogue"]
    )


def test_steps2_to_4_catalogue_and_three_way_disjoint_partition() -> None:
    cfg = tcm.configuration()
    caps = tcm.config_check(cfg)
    assert caps == {"real_steps": 2624, "imagined_transitions": 0, "outer_updates": 16}

    disk_cfg = json.loads((ROOT / "configs" / "seed_task_conditioned_replication.json").read_text(encoding="utf-8"))
    assert digest(cfg) == digest(disk_cfg)

    lcat = tcm.build_catalogue_rep("list")
    acat = tcm.build_catalogue_rep("action_token_sequence")
    assert lcat["raw_count"] == 258
    assert lcat["canonical_count"] == 100
    assert lcat["unique_count"] == 65
    assert len(lcat["source_ids"]) == 18
    assert len(lcat["quarantine_ids"]) == 23
    assert len(lcat["target_ids"]) == 24

    inv = tcm.verify_partition_invariants_rep(lcat, acat)
    assert inv["canonical_signature_overlap_source_target"] == 0
    assert inv["canonical_signature_overlap_quarantine_target"] == 0
    assert inv["canonical_signature_overlap_source_quarantine"] == 0
    assert inv["semantic_hash_overlap_source_target"] == 0
    assert inv["semantic_hash_overlap_quarantine_target"] == 0
    assert inv["semantic_hash_overlap_source_quarantine"] == 0
    assert inv["target_unseen_pair_fraction"] == 1.0
    assert inv["list_calibration_unique_signatures"] == 65
    assert inv["action_calibration_unique_signatures"] == 65

    comm = tcm.verify_commutation_identities_rep(dm.probe_domain())
    assert comm["probe_count"] == 781

    # Verify source-only model fitting on Family 0's 18 source tasks (zero target access)
    entries_by_id = {e["id"]: e for e in lcat["entries"]}
    source_tasks = [
        tcm.generate_task_data_rep(
            cfg["tasks"]["train"][idx],
            entries_by_id[pid],
            lcat,
            cfg,
            "source",
            0,
        )
        for idx, pid in enumerate(lcat["source_ids"])
    ]
    model = tcm.fit_source_models_rep(source_tasks, lcat, cfg)
    assert model["acquisition_summary"]["exact_recovery_rate"] == 1.0
    assert len(model["structural_weights"]) == 23
    assert len(model["linear_ranker_weights"]) == 20


def test_step5_real_cross_lab_transfer() -> None:
    res = xlab.run_cross_lab_transfer_study()
    assert res["schema"] == "seed_cross_lab_transfer_v1"
    assert len(res["episodes"]) == 8
    assert res["passed"] is True
    s_shared = res["summary"]["shared_memory_transfer"]
    s_scratch = res["summary"]["scratch_learning"]
    s_iso = res["summary"]["isolated_labs"]
    assert s_shared["mean_downstream_evaluations"] == 1.0
    assert s_shared["downstream_accuracy"] == 1.0
    assert s_shared["world_goal_completion_rate"] == 1.0
    assert s_scratch["mean_downstream_evaluations"] > 50.0
    assert s_iso["downstream_accuracy"] == 0.0
    assert s_iso["world_goal_completion_rate"] == 0.0


def test_post_run_replication_artifact_if_present() -> None:
    apath = ROOT / "artifacts" / "seed_task_conditioned_replication.json"
    if not apath.exists():
        return
    replay = tcm.saved_replay(ROOT)
    assert replay["status"] == "complete_development"
    assert replay["task_conditioned_replication"]["overall_pass"] is True
    assert replay["task_conditioned_replication"]["CrossDomainTransferEstablished"] is True

    audit_path = ROOT / "artifacts" / "seed_task_conditioned_replication_audit.json"
    assert audit_path.exists()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["valid"] is True
    assert audit["overall_pass"] is True
    assert audit["CrossDomainTransferEstablished"] is True
    assert audit["CrossLabTransferEstablished"] is True

    xlab_path = ROOT / "artifacts" / "seed_cross_lab_transfer.json"
    assert xlab_path.exists()
    xlab_art = json.loads(xlab_path.read_text(encoding="utf-8"))
    assert xlab_art["passed"] is True
