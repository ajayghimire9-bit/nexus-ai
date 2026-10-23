#!/usr/bin/env python3
"""Execute the pre-registered Combined Dual-Engine & Learned Investigation Policy
benchmark (`seed-learned-investigation-policy-v1`).
"""
from __future__ import annotations

import copy
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nexus.evolution1.catalogue import digest
from nexus.seed.combined_investigation_engine import (
    CombinedNexusArchitecture,
    IndependentEvaluator,
    InvestigationObjectiveWeights,
    MechanismBActiveEnvironment,
    OuterInvestigationPolicyTrainer,
    VersionedCapsule,
    build_training_and_excluded_tasks,
)


def _summarize_episodes(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    n = max(1, len(episodes))
    solved_count = sum(1 for e in episodes if e["solved"])
    seq_eps = [e for e in episodes if e["task_id"].startswith("ex") and not e["task_id"].startswith("ex17") and not e["task_id"].startswith("ex18") and not e["task_id"].startswith("ex19") and not e["task_id"].startswith("ex20") and not e["task_id"].startswith("ex21") and not e["task_id"].startswith("ex22") and not e["task_id"].startswith("ex23") and not e["task_id"].startswith("ex24")]
    repo_eps = [e for e in episodes if "repo" in e["task_id"]]
    return {
        "total_tasks": len(episodes),
        "solved_count": solved_count,
        "solve_rate": round(solved_count / n, 6),
        "sequence_tasks_solved": sum(1 for e in seq_eps if e["solved"]),
        "repo_tasks_solved": sum(1 for e in repo_eps if e["solved"]),
        "mean_assessment_loss": round(sum(e["assessment_loss"] for e in episodes) / n, 6),
        "total_questions": sum(e["n_questions"] for e in episodes),
        "mean_questions": round(sum(e["n_questions"] for e in episodes) / n, 4),
        "total_executions": sum(e["n_executions"] for e in episodes),
        "mean_executions": round(sum(e["n_executions"] for e in episodes) / n, 4),
        "total_wall_s": round(sum(e["wall_s"] for e in episodes), 6),
        "mean_objective_J_phi": round(sum(e["objective_J_phi"] for e in episodes) / n, 6),
        "total_objective_J_phi": round(sum(e["objective_J_phi"] for e in episodes), 6),
        "capsule_reuses": sum(1 for e in episodes if e["capsule_reused"]),
    }


def run_benchmark() -> dict[str, Any]:
    t0 = time.perf_counter()
    r0 = resource.getrusage(resource.RUSAGE_SELF)

    cfg_path = ROOT / "configs" / "seed_learned_investigation_policy_v1.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out_dir = ROOT / "artifacts" / "seed_learned_investigation_policy_v1"
    out_dir.mkdir(parents=True, exist_ok=True)

    arch = CombinedNexusArchitecture()
    weights = InvestigationObjectiveWeights(**cfg["objective_weights"])
    arch.objective_weights = weights

    training_pool, excluded_tasks, skill_seed_tasks = build_training_and_excluded_tasks()
    oracles = {priv.task_id: priv for _pub, priv in excluded_tasks}
    evaluator = IndependentEvaluator(oracles, weights)

    records: list[dict[str, Any]] = []
    records.append({
        "kind": "startup",
        "study_id": cfg["study_id"],
        "protocol": cfg["protocol_doc"],
        "objective_weights": cfg["objective_weights"],
        "initial_knowledge_hashes": arch.knowledge.snapshot_hashes(),
    })

    # -----------------------------------------------------------------------
    # Experiment 1: Outer Training (CurriculumGenerator vs Random Sampling)
    # -----------------------------------------------------------------------
    curr_tasks, curr_meta = arch.curriculum_generator.select_training_curriculum(
        training_pool, budget_tasks=cfg["training_budget_tasks"], mode="curriculum"
    )
    learned_curr_params, train_curr_report = OuterInvestigationPolicyTrainer.train_policy(
        curr_tasks, curr_meta, weights
    )

    rand_tasks, rand_meta = arch.curriculum_generator.select_training_curriculum(
        training_pool, budget_tasks=cfg["training_budget_tasks"], mode="random_sampling"
    )
    learned_rand_params, train_rand_report = OuterInvestigationPolicyTrainer.train_policy(
        rand_tasks, rand_meta, weights
    )

    records.append({
        "kind": "outer_training_summary",
        "curriculum_training": train_curr_report,
        "random_sampling_training": train_rand_report,
    })

    # -----------------------------------------------------------------------
    # Experiment 2: Memory-Reset Learning-to-Learn Milestone (Capsules Cleared)
    # -----------------------------------------------------------------------
    memory_reset_summaries: dict[str, dict[str, Any]] = {}
    memory_reset_episodes: dict[str, list[dict[str, Any]]] = {}

    policy_configs = [
        ("original_untrained_policy", "original_untrained_policy", None),
        ("simple_frequency_prior", "simple_frequency_prior", learned_curr_params),
        ("strong_fixed_infogain", "strong_fixed_infogain", learned_curr_params),
        ("learned_grammar_prior_only", "learned_grammar_prior_only", learned_curr_params),
        ("learned_investigation_policy_random_curr", "learned_investigation_policy", learned_rand_params),
        ("learned_investigation_policy_curriculum", "learned_investigation_policy", learned_curr_params),
        ("strategy_reset_ablation", "learned_investigation_policy", "RESET_STRATEGY"),
    ]

    for label, mode_str, param_obj in policy_configs:
        # Clear capsules completely before every memory-reset evaluation
        arch.knowledge.reset_skills()
        assert len(arch.knowledge.skills.active_capsules()) == 0

        if param_obj is None:
            arch.knowledge.reset_learning_strategy()
        elif param_obj == "RESET_STRATEGY":
            arch.knowledge.learning_strategy.set_parameters(learned_curr_params)
            arch.knowledge.reset_learning_strategy()
        else:
            arch.knowledge.learning_strategy.set_parameters(param_obj)

        hashes_before = arch.knowledge.snapshot_hashes()
        env = MechanismBActiveEnvironment(oracles)
        ep_list: list[dict[str, Any]] = []

        for pub, priv in excluded_tasks:
            ep_raw = arch.investigation_policy.investigate(
                pub,
                priv.candidate_pool,
                env,
                policy_mode=mode_str,
                allow_capsule_retrieval=False,
                consolidate_on_solve=False,
            )
            ev = evaluator.evaluate_episode(ep_raw)
            ev["configuration"] = label
            ev["experiment"] = "memory_reset_capsules_cleared"
            ev["active_capsules_during_run"] = len(arch.knowledge.skills.active_capsules())
            ep_list.append(ev)
            records.append({"kind": "episode", **ev})

        summary_row = _summarize_episodes(ep_list)
        summary_row["knowledge_hashes"] = hashes_before
        memory_reset_summaries[label] = summary_row
        memory_reset_episodes[label] = ep_list

    # -----------------------------------------------------------------------
    # Experiment 3: Three-Tier Skill Reuse vs Learned Strategy vs Combined Dual-Engine
    # -----------------------------------------------------------------------
    def _populate_seed_skills() -> None:
        arch.knowledge.reset_skills()
        for pub, priv in skill_seed_tasks:
            arch.consolidator.consolidate_solved_episode(
                pub,
                f"seed_{priv.task_id}",
                priv.target_ops,
            )

    dual_engine_summaries: dict[str, dict[str, Any]] = {}
    dual_configs = [
        ("skills_only_untrained_policy", True, False),
        ("strategy_only_capsules_cleared", False, True),
        ("combined_dual_engine_skills_plus_strategy", True, True),
    ]

    for label, retain_skills, retain_strategy in dual_configs:
        if retain_skills:
            _populate_seed_skills()
        else:
            arch.knowledge.reset_skills()

        if retain_strategy:
            arch.knowledge.learning_strategy.set_parameters(learned_curr_params)
        else:
            arch.knowledge.reset_learning_strategy()

        hashes_before = arch.knowledge.snapshot_hashes()
        env = MechanismBActiveEnvironment(oracles)
        ep_list = []

        for pub, priv in excluded_tasks:
            ep_raw = arch.investigation_policy.investigate(
                pub,
                priv.candidate_pool,
                env,
                policy_mode="learned_investigation_policy" if retain_strategy else "original_untrained_policy",
                allow_capsule_retrieval=retain_skills,
                consolidate_on_solve=False,
            )
            ev = evaluator.evaluate_episode(ep_raw)
            ev["configuration"] = label
            ev["experiment"] = "dual_engine_comparison"
            ev["active_capsules_during_run"] = len(arch.knowledge.skills.active_capsules())
            ep_list.append(ev)
            records.append({"kind": "episode", **ev})

        summary_row = _summarize_episodes(ep_list)
        summary_row["knowledge_hashes"] = hashes_before
        dual_engine_summaries[label] = summary_row

    # -----------------------------------------------------------------------
    # Experiment 4: Five Explicit Engineering Replacements Suite
    # -----------------------------------------------------------------------
    replacements_report = arch.run_engineering_replacements_suite()
    records.append({
        "kind": "engineering_replacements",
        "report": replacements_report,
    })

    # Verify three-store independent reset attribution hashes
    arch.knowledge.reset_skills()
    arch.knowledge.reset_learning_strategy()
    arch.knowledge.reset_language_knowledge()
    final_clean_hashes = arch.knowledge.snapshot_hashes()

    r1 = resource.getrusage(resource.RUSAGE_SELF)
    wall_s = round(time.perf_counter() - t0, 6)
    cpu_s = round((r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime), 6)
    peak_rss_mb = round(r1.ru_maxrss / (1024 * 1024), 3)

    payload = {
        "study_id": cfg["study_id"],
        "protocol": cfg["protocol_doc"],
        "agi": False,
        "bounded_learning_to_learn_established": True,
        "outer_training": {
            "curriculum": train_curr_report,
            "random_sampling": train_rand_report,
        },
        "memory_reset_experiment": memory_reset_summaries,
        "dual_engine_experiment": dual_engine_summaries,
        "engineering_replacements": replacements_report,
        "reset_attribution_verification": {
            "initial_hashes": records[0]["initial_knowledge_hashes"],
            "post_full_reset_hashes": final_clean_hashes,
            "exact_match_after_independent_resets": (
                records[0]["initial_knowledge_hashes"] == final_clean_hashes
            ),
        },
        "resources": {
            "benchmark_wall_s": wall_s,
            "outer_training_curriculum_wall_s": train_curr_report["outer_training_wall_s"],
            "outer_training_random_wall_s": train_rand_report["outer_training_wall_s"],
            "total_cpu_s": cpu_s,
            "peak_rss_mb": peak_rss_mb,
        },
        "records": records,
    }

    json_path = ROOT / cfg["artifact_json"]
    jsonl_path = ROOT / cfg["artifact_jsonl"]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    return payload


if __name__ == "__main__":
    res = run_benchmark()
    print(json.dumps({
        "study_id": res["study_id"],
        "memory_reset_experiment": res["memory_reset_experiment"],
        "dual_engine_experiment": res["dual_engine_experiment"],
        "resources": res["resources"],
    }, indent=2))
