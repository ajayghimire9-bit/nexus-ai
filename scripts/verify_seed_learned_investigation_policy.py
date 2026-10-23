#!/usr/bin/env python3
r"""Independent Replay & Tamper-Rejecting Verifier for
`seed-learned-investigation-policy-v1`.

Re-executes every saved episode in `artifacts/seed_learned_investigation_policy_v1/`
against the independent evaluator's private task oracles, checks objective
$J(\phi)$ arithmetic, verifies capsule-reset invariants, verifies all 5
engineering replacements, and runs a tamper self-test.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.combined_investigation_engine import (
    InvestigationObjectiveWeights,
    build_training_and_excluded_tasks,
)


def verify_payload(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    mismatches: list[str] = []

    if payload.get("study_id") != "seed-learned-investigation-policy-v1":
        mismatches.append("invalid_study_id")
    if payload.get("agi") is not False:
        mismatches.append("agi_claim_must_be_false")

    _, excluded_tasks, _ = build_training_and_excluded_tasks()
    oracles = {priv.task_id: priv for _pub, priv in excluded_tasks}
    weights = InvestigationObjectiveWeights(lambda_q=0.08, lambda_e=0.02, lambda_t=0.10)

    episodes = [r for r in payload.get("records", []) if r.get("kind") == "episode"]
    if len(episodes) != 24 * (7 + 3):
        mismatches.append(f"expected_240_episodes_got_{len(episodes)}")

    for ep in episodes:
        tid = ep["task_id"]
        if tid not in oracles:
            mismatches.append(f"unknown_task_id:{tid}")
            continue
        oracle = oracles[tid]

        # Verify capsule reset invariant in memory_reset_capsules_cleared
        if ep["experiment"] == "memory_reset_capsules_cleared":
            if ep.get("active_capsules_during_run") != 0:
                mismatches.append(f"non_zero_capsules_in_memory_reset:{tid}:{ep['configuration']}")
            if ep.get("capsule_reused") is not False:
                mismatches.append(f"capsule_reused_in_memory_reset:{tid}:{ep['configuration']}")

        # Reconstruct selected candidate function from candidate_pool and replay on assessment inputs
        cand_map = {cid: (ops, fn) for cid, ops, fn in oracle.candidate_pool}
        sel_cid = ep["selected_candidate_id"]
        # For Tier-1/2/3 capsule hits, match by selected_ops if candidate id was a seed capsule
        sel_ops = tuple(ep["selected_ops"])
        fn = None
        if sel_cid in cand_map:
            fn = cand_map[sel_cid][1]
        else:
            for _cid, ops, cand_fn in oracle.candidate_pool:
                if ops == sel_ops:
                    fn = cand_fn
                    break
        if fn is None:
            mismatches.append(f"cannot_reconstruct_candidate:{tid}:{sel_cid}")
            continue

        passed = 0
        for inp in oracle.assessment_inputs:
            expected = oracle.oracle_fn(copy.deepcopy(inp))
            actual = fn(copy.deepcopy(inp))
            if actual == expected:
                passed += 1
        replayed_acc = round(passed / len(oracle.assessment_inputs), 6)
        replayed_loss = round(1.0 - replayed_acc, 6)
        replayed_solved = (passed == len(oracle.assessment_inputs))

        if replayed_solved != ep["solved"] or abs(replayed_loss - ep["assessment_loss"]) > 1e-5:
            mismatches.append(f"replay_outcome_mismatch:{tid}:{ep['configuration']}")

        expected_j = weights.compute_episode_objective(
            assessment_loss=replayed_loss,
            n_questions=ep["n_questions"],
            n_executions=ep["n_executions"],
            wall_s=ep["wall_s"],
        )
        if abs(expected_j - ep["objective_J_phi"]) > 1e-5:
            mismatches.append(f"objective_j_mismatch:{tid}:{ep['configuration']}")

    # Verify memory-reset milestone gates
    mem = payload.get("memory_reset_experiment", {})
    curr = mem.get("learned_investigation_policy_curriculum", {})
    untrained = mem.get("original_untrained_policy", {})
    freq = mem.get("simple_frequency_prior", {})
    infogain = mem.get("strong_fixed_infogain", {})
    rand_curr = mem.get("learned_investigation_policy_random_curr", {})
    reset_abl = mem.get("strategy_reset_ablation", {})

    if not (curr.get("solved_count", 0) > untrained.get("solved_count", 24)):
        mismatches.append("learned_policy_did_not_beat_untrained_solve_count")
    if not (curr.get("mean_objective_J_phi", 99.0) < untrained.get("mean_objective_J_phi", 0.0)):
        mismatches.append("learned_policy_did_not_beat_untrained_objective")
    if not (curr.get("mean_objective_J_phi", 99.0) < freq.get("mean_objective_J_phi", 0.0)):
        mismatches.append("learned_policy_did_not_beat_frequency_prior_objective")
    if not (curr.get("mean_objective_J_phi", 99.0) < infogain.get("mean_objective_J_phi", 0.0)):
        mismatches.append("learned_policy_did_not_beat_fixed_infogain_objective")
    if not (curr.get("mean_objective_J_phi", 99.0) < rand_curr.get("mean_objective_J_phi", 0.0)):
        mismatches.append("curriculum_did_not_beat_random_sampling_objective")
    if reset_abl.get("solved_count") != untrained.get("solved_count"):
        mismatches.append("strategy_reset_ablation_did_not_revert_to_untrained")

    # Verify engineering replacements
    rep = payload.get("engineering_replacements", {})
    if rep.get("conformal_calibration", {}).get("top5_guarantees_95_percent") is not False:
        mismatches.append("conformal_top5_false_guarantee_not_refuted")
    if rep.get("egraph_organization", {}).get("sound_rule_check", {}).get("universal_proof_claimed") is not False:
        mismatches.append("egraph_universal_proof_must_not_be_claimed")
    if rep.get("contract_counterexample_search", {}).get("buggy_function_result", {}).get("status") != "counterexample_found":
        mismatches.append("contract_searcher_missed_counterexample")
    if rep.get("attributed_claims", {}).get("overlapping_dates_query", {}).get("verified_fact") is not False:
        mismatches.append("extracted_claims_must_not_be_marked_verified_fact")
    if rep.get("versioned_artifact_monitoring", {}).get("changed_assumption_invalidation", {}).get("status") != "invalidated_on_assumption_change":
        mismatches.append("versioned_artifact_not_invalidated_on_assumption_change")

    return len(mismatches) == 0, mismatches


def main() -> int:
    artifact_path = ROOT / "artifacts" / "seed_learned_investigation_policy_v1" / "seed_learned_investigation_policy_v1.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    valid, mismatches = verify_payload(payload)

    # Tamper self-test: forge a solved outcome and verify detection
    tampered = copy.deepcopy(payload)
    for r in tampered["records"]:
        if r.get("kind") == "episode":
            r["objective_J_phi"] = 0.00001
            break
    tamper_valid, _ = verify_payload(tampered)
    tamper_self_test_passed = (not tamper_valid)

    report = {
        "study_id": "seed-learned-investigation-policy-v1",
        "valid": bool(valid and tamper_self_test_passed),
        "mismatches": mismatches,
        "tamper_self_test_passed": tamper_self_test_passed,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
