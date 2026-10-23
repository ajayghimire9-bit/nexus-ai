#!/usr/bin/env python3
"""Execute the Equalized, Call-Metered Learned Investigation Policy benchmark v2
(`seed-learned-investigation-policy-v2`).
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

from nexus.seed.combined_investigation_engine import (
    CombinedNexusArchitecture,
    DisjointTaskV2,
    EqualizedControllerConfig,
    EqualizedInvestigationEngineV2,
    EvaluatorPrivateTaskOracle,
    InvestigationObjectiveWeights,
    MechanismBActiveEnvironment,
    build_v2_disjoint_tasks_and_real_repos,
    verify_disjoint_task_inputs,
)
from nexus.seed.local_model_runtime import PersistentLocalRuntime, RuntimeConfig


def summarize_v2_episodes(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    n = max(1, len(episodes))
    seq_eps = [e for e in episodes if e["domain"] == "sequence_pipeline"]
    repo_eps = [e for e in episodes if e["domain"] == "repo_patch"]
    solved_count = sum(1 for e in episodes if e["solved"])
    total_calls = sum(e["n_candidate_calls"] for e in episodes)
    total_questions = sum(e["n_questions"] for e in episodes)
    total_wall = round(sum(e["wall_s"] for e in episodes), 6)
    total_j = round(sum(e["objective_J_phi"] for e in episodes), 6)

    support_calls = sum(
        sum(1 for c in e["candidate_call_log"] if c["phase"] == "support_check")
        for e in episodes
    )
    probe_calls = sum(
        sum(1 for c in e["candidate_call_log"] if c["phase"] == "probe_construction")
        for e in episodes
    )

    return {
        "total_tasks": len(episodes),
        "solved_count": solved_count,
        "solve_rate": round(solved_count / n, 6),
        "sequence_tasks_solved": sum(1 for e in seq_eps if e["solved"]),
        "repo_tasks_solved": sum(1 for e in repo_eps if e["solved"]),
        "mean_assessment_loss": round(sum(e["assessment_loss"] for e in episodes) / n, 6),
        "total_candidate_calls": total_calls,
        "support_check_calls": support_calls,
        "probe_construction_calls": probe_calls,
        "mean_candidate_calls": round(total_calls / n, 4),
        "total_questions": total_questions,
        "mean_questions": round(total_questions / n, 4),
        "total_wall_s": total_wall,
        "mean_objective_J_phi": round(total_j / n, 6),
        "total_objective_J_phi": total_j,
        "compositional_prefix_reuses": sum(1 for e in episodes if e.get("compositional_prefix_reused")),
    }


def run_live_local_gguf_repo_probe(repo_task: DisjointTaskV2) -> dict[str, Any]:
    """Run a live local GGUF model probe (`qwen2.5-0.5b-instruct-q4_k_m.gguf`) on
    `repo17_billing_adjustment` to measure real local neural proposal latency and
    compare one-shot LLM guessing on ambiguous tickets against NEXUS active probing.
    """
    cfg = RuntimeConfig.from_environment()
    model_file = Path(cfg.model_path)
    if not model_file.is_file():
        return {
            "available": False,
            "reason": f"model_not_found:{model_file}",
        }
    rt = PersistentLocalRuntime(cfg)
    t0 = time.perf_counter()
    try:
        rt.start()
        prompt = (
            f"Repository ticket: {repo_task.ticket_request}\n"
            f"Files:\n{json.dumps(repo_task.repo_files, indent=2)}\n"
            "Propose a concise Python fix for norm_extra(extra) when extra is negative: "
            "should it use max(0, extra) or abs(extra)?"
        )
        resp = rt.complete(prompt, None)
        wall_s = round(time.perf_counter() - t0, 6)
        text = resp.get("content", "")
        return {
            "available": True,
            "model_path": str(model_file),
            "wall_s": wall_s,
            "telemetry": resp.get("telemetry"),
            "completion_excerpt": text[:240],
            "note": (
                "Without querying the environment on a negative-extra probe, the ticket text alone "
                "does not state whether negative adjustments are clamped at 0 or reflected via abs()."
            ),
        }
    except Exception as exc:
        return {
            "available": False,
            "reason": f"{type(exc).__name__}:{exc}",
        }
    finally:
        rt.close()


def run_v2_benchmark() -> dict[str, Any]:
    t0 = time.perf_counter()
    r0 = resource.getrusage(resource.RUSAGE_SELF)

    cfg_path = ROOT / "configs" / "seed_learned_investigation_policy_v2.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out_dir = ROOT / "artifacts" / "seed_learned_investigation_policy_v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    weights = InvestigationObjectiveWeights(**cfg["objective_weights"])
    engine = EqualizedInvestigationEngineV2(objective_weights=weights)
    equal_ctrl = EqualizedControllerConfig(**cfg["equalized_controller"])
    passive_ctrl = EqualizedControllerConfig(
        shortlist_limit=equal_ctrl.shortlist_limit,
        allow_questions=False,
        max_questions_per_task=0,
        probe_min_disagreement_ratio=equal_ctrl.probe_min_disagreement_ratio,
    )

    training_pool, source_tasks, excluded_tasks = build_v2_disjoint_tasks_and_real_repos()

    # Verify pairwise disjointness of support, probe pool, and assessment inputs across all 64 tasks
    disjoint_checks = [verify_disjoint_task_inputs(t) for t in (training_pool + source_tasks + excluded_tasks)]
    assert all(c["pairwise_disjoint"] for c in disjoint_checks)

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

    records: list[dict[str, Any]] = []
    records.append({
        "kind": "startup_v2",
        "study_id": cfg["study_id"],
        "equalized_controller": asdict_ctrl(equal_ctrl),
        "objective_weights": cfg["objective_weights"],
        "all_64_tasks_pairwise_disjoint_inputs": True,
    })

    # -----------------------------------------------------------------------
    # 1. Outer Training: CurriculumGenerator vs Random Sampling (Full Call Metering)
    # -----------------------------------------------------------------------
    curr_params, train_curr_report = engine.select_and_train_v2(
        training_pool, budget_tasks=cfg["training_budget_tasks"], mode="curriculum"
    )
    rand_params, train_rand_report = engine.select_and_train_v2(
        training_pool, budget_tasks=cfg["training_budget_tasks"], mode="random_sampling"
    )
    records.append({
        "kind": "outer_training_v2",
        "curriculum": train_curr_report,
        "random_sampling": train_rand_report,
    })

    # -----------------------------------------------------------------------
    # 2. Equalized Active Comparison (Capsules Cleared, Identical Controller Rules)
    # -----------------------------------------------------------------------
    equalized_active_summaries: dict[str, dict[str, Any]] = {}
    active_specs = [
        ("untrained_default_active", "untrained_default_active", None),
        ("simple_frequency_active", "simple_frequency_active", curr_params),
        ("fixed_infogain_active", "fixed_infogain_active", curr_params),
        ("learned_ranker_only_active", "learned_ranker_only_active", curr_params),
        ("learned_policy_random_curr_active", "learned_policy_random_curr_active", rand_params),
        ("learned_policy_curriculum_active", "learned_policy_curriculum_active", curr_params),
        ("strategy_reset_active", "learned_policy_curriculum_active", "RESET_STRATEGY"),
    ]

    for label, mode_str, p_obj in active_specs:
        engine.reset_skills()
        assert len(engine.knowledge.skills.active_capsules()) == 0
        if p_obj is None:
            engine.reset_strategy()
        elif p_obj == "RESET_STRATEGY":
            engine.set_strategy_params(curr_params)
            engine.reset_strategy()
        else:
            engine.set_strategy_params(p_obj)

        env = MechanismBActiveEnvironment(all_oracles)
        eps: list[dict[str, Any]] = []
        for task in excluded_tasks:
            ep = engine.investigate_v2(
                task,
                env,
                equal_ctrl,
                policy_mode=mode_str,
                allow_compositional_capsules=False,
                consolidate_on_solve=False,
            )
            ev = engine.evaluate_v2_episode(
                task,
                ep,
                verify_in_bounded_worker=(task.domain == "repo_patch" and label == "learned_policy_curriculum_active"),
            )
            ev["configuration"] = label
            ev["experiment"] = "equalized_active_capsules_cleared"
            ev["controller_shortlist_limit"] = equal_ctrl.shortlist_limit
            ev["controller_allow_questions"] = equal_ctrl.allow_questions
            ev["active_capsules_during_run"] = len(engine.knowledge.skills.active_capsules())
            eps.append(ev)
            records.append({"kind": "episode_v2", **ev})

        equalized_active_summaries[label] = summarize_v2_episodes(eps)

    # -----------------------------------------------------------------------
    # 3. Separate Passive Factorial Controls (`allow_questions = False`)
    # -----------------------------------------------------------------------
    passive_summaries: dict[str, dict[str, Any]] = {}
    for label, mode_str, p_obj in [
        ("untrained_passive_no_questions", "untrained_passive_no_questions", None),
        ("learned_ranker_passive_no_questions", "learned_ranker_only_active", curr_params),
    ]:
        engine.reset_skills()
        if p_obj is None:
            engine.reset_strategy()
        else:
            engine.set_strategy_params(p_obj)
        env = MechanismBActiveEnvironment(all_oracles)
        eps = []
        for task in excluded_tasks:
            ep = engine.investigate_v2(
                task,
                env,
                passive_ctrl,
                policy_mode=mode_str,
                allow_compositional_capsules=False,
                consolidate_on_solve=False,
            )
            ev = engine.evaluate_v2_episode(task, ep, verify_in_bounded_worker=False)
            ev["configuration"] = label
            ev["experiment"] = "passive_factorial_control"
            ev["controller_shortlist_limit"] = passive_ctrl.shortlist_limit
            ev["controller_allow_questions"] = passive_ctrl.allow_questions
            ev["active_capsules_during_run"] = 0
            eps.append(ev)
            records.append({"kind": "episode_v2", **ev})
        passive_summaries[label] = summarize_v2_episodes(eps)

    # -----------------------------------------------------------------------
    # 4. Autonomous Source Skill Acquisition (`src01..src08`) -> Compositional Prefix Transfer
    # -----------------------------------------------------------------------
    engine.reset_skills()
    engine.set_strategy_params(curr_params)
    env_src = MechanismBActiveEnvironment(all_oracles)
    source_acquisition_eps: list[dict[str, Any]] = []
    for stask in source_tasks:
        ep_s = engine.investigate_v2(
            stask,
            env_src,
            equal_ctrl,
            policy_mode="learned_policy_curriculum_active",
            allow_compositional_capsules=False,
            consolidate_on_solve=True,
        )
        ev_s = engine.evaluate_v2_episode(stask, ep_s, verify_in_bounded_worker=False)
        ev_s["configuration"] = "autonomous_source_acquisition"
        ev_s["experiment"] = "source_skill_acquisition"
        ev_s["controller_shortlist_limit"] = equal_ctrl.shortlist_limit
        ev_s["controller_allow_questions"] = equal_ctrl.allow_questions
        ev_s["active_capsules_during_run"] = len(engine.knowledge.skills.active_capsules())
        source_acquisition_eps.append(ev_s)
        records.append({"kind": "source_acquisition_episode_v2", **ev_s})

    acquired_capsules_snapshot = copy.deepcopy(engine.knowledge.skills.capsules)
    source_acquisition_summary = summarize_v2_episodes(source_acquisition_eps)
    source_acquisition_summary["acquired_capsule_count"] = len(acquired_capsules_snapshot)

    compositional_transfer_summaries: dict[str, dict[str, Any]] = {}
    for label, retain_skills, retain_strategy in [
        ("skills_only_untrained_active", True, False),
        ("strategy_only_capsules_cleared_active", False, True),
        ("combined_dual_engine_compositional_prefix_active", True, True),
    ]:
        engine.reset_skills()
        if retain_skills:
            engine.knowledge.skills.capsules = copy.deepcopy(acquired_capsules_snapshot)
        if retain_strategy:
            engine.set_strategy_params(curr_params)
        else:
            engine.reset_strategy()

        env = MechanismBActiveEnvironment(all_oracles)
        eps = []
        mode_str = "learned_policy_curriculum_active" if retain_strategy else "untrained_default_active"
        for task in excluded_tasks:
            ep = engine.investigate_v2(
                task,
                env,
                equal_ctrl,
                policy_mode=mode_str,
                allow_compositional_capsules=retain_skills,
                consolidate_on_solve=False,
            )
            ev = engine.evaluate_v2_episode(task, ep, verify_in_bounded_worker=False)
            ev["configuration"] = label
            ev["experiment"] = "compositional_transfer_experiment"
            ev["controller_shortlist_limit"] = equal_ctrl.shortlist_limit
            ev["controller_allow_questions"] = equal_ctrl.allow_questions
            ev["active_capsules_during_run"] = len(engine.knowledge.skills.active_capsules())
            eps.append(ev)
            records.append({"kind": "episode_v2", **ev})
        compositional_transfer_summaries[label] = summarize_v2_episodes(eps)

    # -----------------------------------------------------------------------
    # 5. Live Local GGUF Model Probe & Five Engineering Replacements
    # -----------------------------------------------------------------------
    repo17 = [t for t in excluded_tasks if t.task_id == "repo17_billing_adjustment"][0]
    live_llm_probe = run_live_local_gguf_repo_probe(repo17)
    base_arch = CombinedNexusArchitecture()
    replacements_report = base_arch.run_engineering_replacements_suite()

    r1 = resource.getrusage(resource.RUSAGE_SELF)
    wall_s = round(time.perf_counter() - t0, 6)
    cpu_s = round((r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime), 6)
    peak_rss_mb = round(r1.ru_maxrss / (1024 * 1024), 3)

    payload = {
        "study_id": cfg["study_id"],
        "supersedes_confounded_study": cfg["supersedes_confounded_study"],
        "v1_learning_to_learn_withdrawn": True,
        "agi": False,
        "equalized_controller": asdict_ctrl(equal_ctrl),
        "objective_weights": cfg["objective_weights"],
        "disjoint_input_verification": {
            "total_tasks_checked": len(disjoint_checks),
            "all_pairwise_disjoint": all(c["pairwise_disjoint"] for c in disjoint_checks),
        },
        "outer_training": {
            "curriculum": train_curr_report,
            "random_sampling": train_rand_report,
        },
        "equalized_active_comparison": equalized_active_summaries,
        "passive_factorial_controls": passive_summaries,
        "source_skill_acquisition": source_acquisition_summary,
        "compositional_transfer_experiment": compositional_transfer_summaries,
        "live_local_gguf_probe": live_llm_probe,
        "engineering_replacements": replacements_report,
        "resources": {
            "total_wall_s": wall_s,
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


def asdict_ctrl(ctrl: EqualizedControllerConfig) -> dict[str, Any]:
    return {
        "shortlist_limit": ctrl.shortlist_limit,
        "allow_questions": ctrl.allow_questions,
        "max_questions_per_task": ctrl.max_questions_per_task,
        "probe_min_disagreement_ratio": ctrl.probe_min_disagreement_ratio,
    }


if __name__ == "__main__":
    out = run_v2_benchmark()
    print(json.dumps({
        "study_id": out["study_id"],
        "v1_learning_to_learn_withdrawn": out["v1_learning_to_learn_withdrawn"],
        "equalized_active_comparison": out["equalized_active_comparison"],
        "passive_factorial_controls": out["passive_factorial_controls"],
        "source_skill_acquisition": out["source_skill_acquisition"],
        "compositional_transfer_experiment": out["compositional_transfer_experiment"],
        "live_local_gguf_probe": out["live_local_gguf_probe"],
        "resources": out["resources"],
    }, indent=2))
