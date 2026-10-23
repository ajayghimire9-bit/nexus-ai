#!/usr/bin/env python3
r"""Independent Reconstructing & Tamper-Rejecting Verifier for
`seed-learned-investigation-policy-v2`.

Addresses every verification gap identified in the v1 audit:
1. Verifies pairwise disjointness of `support_examples`, `probe_pool_inputs`,
   and `assessment_inputs` across all 64 tasks, and verifies zero task/target
   overlap between 2-step source acquisition tasks (`src01..src08`) and 3-step/repo
   assessment tasks (`ex01..ex16`, `repo17..repo24`).
2. Reconstructs every episode's `n_candidate_calls` and `n_questions` directly
   from `candidate_call_log` and `oracle_question_log`, re-executes every logged
   candidate call and oracle answer to verify input-output authenticity, AND
   re-simulates the deterministic controller to verify that calls/questions
   could not have been omitted or zeroed out.
3. Recomputes all summary tables (`equalized_active_comparison`,
   `passive_factorial_controls`, `compositional_transfer_experiment`) from raw
   episode records and rejects any discrepancy.
4. Runs three adversarial tamper self-tests:
   - Tamper Test A (the exact v1 exploit): Set an episode's `n_candidate_calls = 0`,
     `n_questions = 0`, `wall_s = 0.0`, and update `objective_J_phi` arithmetic
     to match. Must be REJECTED.
   - Tamper Test B: Modify a summary table's `total_candidate_calls` without
     modifying episode records. Must be REJECTED.
   - Tamper Test C: Flip an episode's `solved` status. Must be REJECTED.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.combined_investigation_engine import (
    EqualizedControllerConfig,
    EqualizedInvestigationEngineV2,
    EvaluatorPrivateTaskOracle,
    InvestigationObjectiveWeights,
    MechanismBActiveEnvironment,
    build_v2_disjoint_tasks_and_real_repos,
    verify_disjoint_task_inputs,
)
from scripts.run_seed_learned_investigation_policy_v2 import summarize_v2_episodes


def verify_v2_payload(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    locked = json.loads((ROOT/'configs/seed_learned_investigation_policy_v2.json').read_text())
    if payload.get('equalized_controller') != locked['equalized_controller']:
        return False, ['controller_not_locked_configuration']
    if payload.get('objective_weights') != locked['objective_weights']:
        return False, ['weights_not_locked_configuration']
    expected_groups = {
        'equalized_active_capsules_cleared': locked['equalized_active_policies'],
        'passive_factorial_control': locked['passive_factorial_controls'],
        'compositional_transfer_experiment': locked['compositional_transfer_modes'],
    }
    # Do not derive the expected grid from produced records or saved summaries.
    _, _, locked_tasks = build_v2_disjoint_tasks_and_real_repos()
    expected = {(group, method, task.task_id) for group, methods in expected_groups.items()
                for method in methods for task in locked_tasks}
    cells = [(row.get('experiment'), row.get('configuration'), row.get('task_id'))
             for row in payload.get('records', []) if row.get('kind') == 'episode_v2']
    if len(cells) != len(set(cells)) or set(cells) != expected:
        return False, ['missing_duplicate_or_unexpected_grid_cell']
    for key, group in [('equalized_active_comparison','equalized_active_capsules_cleared'),
                       ('passive_factorial_controls','passive_factorial_control'),
                       ('compositional_transfer_experiment','compositional_transfer_experiment')]:
        if set(payload.get(key, {})) != set(expected_groups[group]):
            return False, ['missing_or_unexpected_summary_configuration']

    if payload.get("study_id") != "seed-learned-investigation-policy-v2":
        mismatches.append("invalid_study_id")
    if payload.get("v1_learning_to_learn_withdrawn") is not True:
        mismatches.append("v1_withdrawal_flag_must_be_true")
    if payload.get("agi") is not False:
        mismatches.append("agi_must_be_false")

    training_pool, source_tasks, excluded_tasks = build_v2_disjoint_tasks_and_real_repos()
    tasks_by_id = {t.task_id: t for t in (training_pool + source_tasks + excluded_tasks)}

    # 1. Verify pairwise disjointness of support, probe pool, and assessment inputs
    for t in (training_pool + source_tasks + excluded_tasks):
        chk = verify_disjoint_task_inputs(t)
        if not chk["pairwise_disjoint"]:
            mismatches.append(f"non_disjoint_inputs:{t.task_id}")

    # Verify zero overlap between 2-step source tasks and 3-step/repo assessment tasks
    if {t.task_id for t in source_tasks} & {t.task_id for t in excluded_tasks}:
        mismatches.append("source_and_excluded_task_ids_overlap")
    if {t.target_ops for t in source_tasks} & {t.target_ops for t in excluded_tasks if t.domain == "sequence_pipeline"}:
        mismatches.append("source_and_excluded_sequence_targets_overlap")

    weights = InvestigationObjectiveWeights(**payload["objective_weights"])
    equal_ctrl = EqualizedControllerConfig(**payload["equalized_controller"])
    passive_ctrl = EqualizedControllerConfig(
        shortlist_limit=equal_ctrl.shortlist_limit,
        allow_questions=False,
        max_questions_per_task=0,
        probe_min_disagreement_ratio=equal_ctrl.probe_min_disagreement_ratio,
    )

    # Re-run deterministic training to obtain reference parameters for controller replay
    ref_engine = EqualizedInvestigationEngineV2(objective_weights=weights)
    curr_params, _ = ref_engine.select_and_train_v2(training_pool, budget_tasks=8, mode="curriculum")
    rand_params, _ = ref_engine.select_and_train_v2(training_pool, budget_tasks=8, mode="random_sampling")
    all_oracles = {
        t.task_id: EvaluatorPrivateTaskOracle(
            task_id=t.task_id,
            target_ops=t.target_ops,
            oracle_fn=t.oracle_fn,
            assessment_inputs=t.assessment_inputs,
            candidate_pool=t.candidate_pool,
        )
        for t in (source_tasks + excluded_tasks)
    }

    # Acquire reference 2-step source capsules for compositional transfer replay
    ref_engine.reset_skills()
    ref_engine.set_strategy_params(curr_params)
    env_src = MechanismBActiveEnvironment(all_oracles)
    for st in source_tasks:
        ref_engine.investigate_v2(
            st, env_src, equal_ctrl, policy_mode="learned_policy_curriculum_active", consolidate_on_solve=True
        )
    ref_acquired_capsules = copy.deepcopy(ref_engine.knowledge.skills.capsules)

    episodes = [r for r in payload.get("records", []) if r.get("kind") == "episode_v2"]
    if len(episodes) != 24 * (7 + 2 + 3):
        mismatches.append(f"expected_288_episodes_got_{len(episodes)}")
        return False, mismatches

    episodes_by_exp_cfg: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for ep in episodes:
        tid = ep["task_id"]
        cfg_name = ep["configuration"]
        exp_name = ep["experiment"]
        episodes_by_exp_cfg.setdefault((exp_name, cfg_name), []).append(ep)

        if tid not in tasks_by_id:
            mismatches.append(f"unknown_task_id:{tid}")
            continue
        task = tasks_by_id[tid]
        cand_map = {cid: (ops, fn) for cid, ops, fn in task.candidate_pool}

        # Verify equalized controller rules on all active experiments
        if exp_name in ("equalized_active_capsules_cleared", "compositional_transfer_experiment"):
            if ep.get("controller_shortlist_limit") != equal_ctrl.shortlist_limit:
                mismatches.append(f"unequal_shortlist_limit:{tid}:{cfg_name}")
            if ep.get("controller_allow_questions") is not True:
                mismatches.append(f"questions_disabled_in_active_experiment:{tid}:{cfg_name}")

        # Verify call log & question log lengths match reported counts
        call_log = ep.get("candidate_call_log", [])
        q_log = ep.get("oracle_question_log", [])
        if ep.get("n_candidate_calls") != len(call_log):
            mismatches.append(f"n_candidate_calls_mismatch_log_len:{tid}:{cfg_name}")
        if ep.get("n_questions") != len(q_log):
            mismatches.append(f"n_questions_mismatch_log_len:{tid}:{cfg_name}")
        if len(call_log) == 0:
            mismatches.append(f"zero_candidate_calls_impossible:{tid}:{cfg_name}")

        # Replay every logged candidate call and oracle question
        for c_entry in call_log:
            cid = c_entry["candidate_id"]
            if cid not in cand_map:
                mismatches.append(f"unknown_candidate_in_call_log:{tid}:{cid}")
                break
            actual_out = cand_map[cid][1](copy.deepcopy(c_entry["input"]))
            if actual_out != c_entry["output"]:
                mismatches.append(f"call_log_output_mismatch:{tid}:{cid}")
                break

        for q_entry in q_log:
            expected_ans = task.oracle_fn(copy.deepcopy(q_entry["probe_input"]))
            if expected_ans != q_entry["oracle_answer"]:
                mismatches.append(f"oracle_log_answer_mismatch:{tid}:{cfg_name}")
                break

        # Independently re-simulate controller to verify exact call count and question count!
        sim_engine = EqualizedInvestigationEngineV2(objective_weights=weights)
        allow_caps = False
        ctrl_to_use = equal_ctrl
        if exp_name == "passive_factorial_control":
            ctrl_to_use = passive_ctrl
            if cfg_name == "untrained_passive_no_questions":
                sim_engine.reset_strategy()
            else:
                sim_engine.set_strategy_params(curr_params)
        elif exp_name == "equalized_active_capsules_cleared":
            if cfg_name in ("untrained_default_active", "strategy_reset_active"):
                sim_engine.reset_strategy()
            elif cfg_name == "learned_policy_random_curr_active":
                sim_engine.set_strategy_params(rand_params)
            else:
                sim_engine.set_strategy_params(curr_params)
        elif exp_name == "compositional_transfer_experiment":
            allow_caps = cfg_name in ("skills_only_untrained_active", "combined_dual_engine_compositional_prefix_active")
            if allow_caps:
                sim_engine.knowledge.skills.capsules = copy.deepcopy(ref_acquired_capsules)
            if cfg_name == "skills_only_untrained_active":
                sim_engine.reset_strategy()
            else:
                sim_engine.set_strategy_params(curr_params)

        sim_ep = sim_engine.investigate_v2(
            task,
            MechanismBActiveEnvironment(all_oracles),
            ctrl_to_use,
            policy_mode=ep["policy_mode"],
            allow_compositional_capsules=allow_caps,
            consolidate_on_solve=False,
        )
        for field in ('candidate_call_log', 'oracle_question_log', 'selected_candidate_id', 'selected_ops'):
            if ep.get(field) != sim_ep[field]:
                mismatches.append(f'controller_trace_mismatch:{tid}:{cfg_name}:{field}')
        if type(ep.get('wall_s')) not in (int, float) or not 0 < ep['wall_s'] < 900:
            mismatches.append(f'invalid_wall_time:{tid}:{cfg_name}')
        if ep.get("n_candidate_calls") != sim_ep["n_candidate_calls"]:
            mismatches.append(
                f"forged_or_mismatched_call_count:{tid}:{cfg_name}:saved={ep.get('n_candidate_calls')}!=sim={sim_ep['n_candidate_calls']}"
            )
        if ep.get("n_questions") != sim_ep["n_questions"]:
            mismatches.append(
                f"forged_or_mismatched_question_count:{tid}:{cfg_name}:saved={ep.get('n_questions')}!=sim={sim_ep['n_questions']}"
            )

        # Replay held-out assessment accuracy and objective J(phi)
        sel_cid = ep["selected_candidate_id"]
        if sel_cid not in cand_map:
            mismatches.append(f"unknown_selected_candidate:{tid}:{sel_cid}")
            continue
        sel_fn = cand_map[sel_cid][1]
        passed = sum(
            1 for inp in task.assessment_inputs
            if sel_fn(copy.deepcopy(inp)) == task.oracle_fn(copy.deepcopy(inp))
        )
        acc = round(passed / len(task.assessment_inputs), 6)
        loss = round(1.0 - acc, 6)
        solved = (passed == len(task.assessment_inputs))
        if solved != ep.get("solved") or abs(loss - ep.get("assessment_loss", -1.0)) > 1e-5:
            mismatches.append(f"assessment_outcome_mismatch:{tid}:{cfg_name}")

        expected_j = weights.compute_episode_objective(
            assessment_loss=loss,
            n_questions=ep["n_questions"],
            n_executions=ep["n_candidate_calls"],
            wall_s=ep["wall_s"],
        )
        if abs(expected_j - ep.get("objective_J_phi", -1.0)) > 1e-5:
            mismatches.append(f"objective_j_mismatch:{tid}:{cfg_name}")

    # Reconstruct summary tables from raw episode records and verify exact match
    table_map = [
        ("equalized_active_capsules_cleared", payload.get("equalized_active_comparison", {})),
        ("passive_factorial_control", payload.get("passive_factorial_controls", {})),
        ("compositional_transfer_experiment", payload.get("compositional_transfer_experiment", {})),
    ]
    for exp_key, saved_table in table_map:
        for cfg_name, saved_summary in saved_table.items():
            raw_eps = episodes_by_exp_cfg.get((exp_key, cfg_name), [])
            recomputed = summarize_v2_episodes(raw_eps)
            for k, v in recomputed.items():
                if saved_summary.get(k) != v:
                    mismatches.append(f"summary_table_mismatch:{exp_key}:{cfg_name}:{k}:saved={saved_summary.get(k)}!=recomputed={v}")

    # Verify scientific gates on equalized active comparison
    eq_table = payload.get("equalized_active_comparison", {})
    curr_row = eq_table.get("learned_policy_curriculum_active", {})
    untrained_row = eq_table.get("untrained_default_active", {})
    infogain_row = eq_table.get("fixed_infogain_active", {})
    freq_row = eq_table.get("simple_frequency_active", {})
    rank_only_row = eq_table.get("learned_ranker_only_active", {})
    rand_curr_row = eq_table.get("learned_policy_random_curr_active", {})
    reset_row = eq_table.get("strategy_reset_active", {})

    if not (curr_row.get("total_candidate_calls", 9999) < untrained_row.get("total_candidate_calls", 0)):
        mismatches.append("learned_curriculum_did_not_beat_untrained_calls")
    if not (curr_row.get("total_candidate_calls", 9999) < infogain_row.get("total_candidate_calls", 0)):
        mismatches.append("learned_curriculum_did_not_beat_fixed_infogain_calls")
    if not (curr_row.get("total_candidate_calls", 9999) < freq_row.get("total_candidate_calls", 0)):
        mismatches.append("learned_curriculum_did_not_beat_frequency_calls")
    if not (curr_row.get("total_candidate_calls", 9999) < rank_only_row.get("total_candidate_calls", 0)):
        mismatches.append("learned_curriculum_did_not_beat_ranker_only_calls")
    if not (curr_row.get("total_candidate_calls", 9999) < rand_curr_row.get("total_candidate_calls", 0)):
        mismatches.append("learned_curriculum_did_not_beat_random_curriculum_calls")
    if reset_row.get("total_candidate_calls") != untrained_row.get("total_candidate_calls"):
        mismatches.append("strategy_reset_active_did_not_revert_to_untrained_active_calls")

    return len(mismatches) == 0, mismatches


def main() -> int:
    artifact_path = ROOT / "artifacts" / "seed_learned_investigation_policy_v2" / "seed_learned_investigation_policy_v2.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    valid, mismatches = verify_v2_payload(payload)

    # Tamper Test A (the exact v1 exploit: set episode calls=0, questions=0, wall_s=0 and update J(phi) arithmetic)
    tampered_a = copy.deepcopy(payload)
    for r in tampered_a["records"]:
        if r.get("kind") == "episode_v2":
            r["n_candidate_calls"] = 0
            r["n_questions"] = 0
            r["wall_s"] = 0.0
            r["candidate_call_log"] = []
            r["oracle_question_log"] = []
            r["objective_J_phi"] = r["assessment_loss"]
            break
    valid_a, _ = verify_v2_payload(tampered_a)

    # Tamper Test B (modify summary table without changing episodes)
    tampered_b = copy.deepcopy(payload)
    tampered_b["equalized_active_comparison"]["learned_policy_curriculum_active"]["total_candidate_calls"] = 100
    valid_b, _ = verify_v2_payload(tampered_b)

    # Tamper Test C (forge solved status)
    tampered_c = copy.deepcopy(payload)
    for r in tampered_c["records"]:
        if r.get("kind") == "episode_v2":
            r["solved"] = not r["solved"]
            break
    valid_c, _ = verify_v2_payload(tampered_c)

    all_tamper_rejected = (not valid_a) and (not valid_b) and (not valid_c)
    report = {
        "study_id": "seed-learned-investigation-policy-v2",
        "valid": bool(valid and all_tamper_rejected),
        "mismatches": mismatches,
        "tamper_self_tests": {
            "v1_zero_cost_exploit_rejected": not valid_a,
            "summary_table_tamper_rejected": not valid_b,
            "outcome_flip_tamper_rejected": not valid_c,
        },
    }
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
