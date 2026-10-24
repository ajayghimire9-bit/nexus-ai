"""Source-trained investigation policy with a development competence gate.

Opened 92d6f19 assessment stays closed. Transfer assessment stays closed
unless the learned policy completes its own development trajectories.
"""
from __future__ import annotations

import json
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from .capability_evidence import digest
from .mechanism_investigate import (
    FEATURE_NAMES, HIDDEN, REDUNDANT_MASK_ORIGIN, available_actions,
    choose_cost_aware_ig, choose_diagnostic, choose_diagnostic_measure,
    choose_frequency, choose_information_gain, choose_random,
    filter_language, run_episode,
)
from .mechanism_policy import (
    fit_source, frequency_order, policy_hash, reset_weights, select_action,
    shuffle_weights, training_rows, zero_weights,
)
from .mechanism_tasks import assessment_tasks, catalogue, split_lock, tasks_for
from .mechanism_world import ACTIONS, LANGUAGE, MAX_STEPS, language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_mechanism_competence"
HEADROOM_RATIO = 1.15
TRAIN_SEEDS = (0, 1, 2)
FIXED_METHODS = ("information_gain", "fixed_diagnostic", "source_frequency", "random")
PRIOR_ASSESSMENT_CLOSED = "92d6f19"


def _chooser(method: str, weights: dict[str, list[float]], order: list[str]) -> Callable:
    def choose(ctx: dict[str, Any]) -> dict[str, Any]:
        remaining, transcript, available, rng = (
            ctx["remaining"], ctx["transcript"], ctx["available"], ctx["rng"],
        )
        if method == "information_gain":
            return choose_information_gain(remaining, transcript, available, rng)
        if method == "cost_aware_ig":
            return choose_cost_aware_ig(remaining, transcript, available, rng)
        if method == "fixed_diagnostic":
            return choose_diagnostic(remaining, transcript, available)
        if method == "fixed_diagnostic_measure":
            return choose_diagnostic_measure(remaining, transcript, available)
        if method == "source_frequency":
            return choose_frequency(remaining, available, order, transcript)
        if method == "random":
            return choose_random(remaining, available, rng)
        picked = select_action(weights, ctx["features"], available, rng)
        return dict(action=picked["selected"], score_work=0, reason=picked["reason"])
    return choose


def run_method(tasks: list[dict[str, Any]], method: str, weights: dict[str, list[float]],
               order: list[str], seed: int) -> list[dict[str, Any]]:
    rows = []
    for index, task in enumerate(tasks):
        rng = random.Random(seed * 1009 + index * 17 + 3)
        episode = run_episode(task, _chooser(method, weights, order), rng)
        episode["method"] = method
        episode["policy_seed"] = seed
        rows.append(episode)
    return rows


def dagger_rows(episode: dict[str, Any], rng: random.Random) -> list[dict[str, Any]]:
    """Relabel the policy's own prefixes with the IG expert. Source only."""
    rows = []
    prefix: list[dict[str, Any]] = []
    for step in episode.get("transcript") or []:
        remaining = filter_language(prefix)
        avail = available_actions({}, prefix, remaining)
        expert = choose_information_gain(remaining, prefix, avail["actions"], rng)
        for action in ACTIONS:
            rows.append(dict(
                action=action,
                features=dict(step["features"]),
                label=1.0 if action == expert["action"] else 0.0,
                first_query=not prefix and not expert["action"].startswith("STOP"),
                chosen=expert["action"],
                supervision="dagger_information_gain",
            ))
        prefix.append(step)
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, dict[str, Any]] = {}
    for row in rows:
        cell = by.setdefault(row["method"], dict(
            n=0, success=0, correct_id=0, correct_unresolved=0, premature=0,
            wrong_id=0, unresolved=0, budget_stop=0, redundant_taken=0,
            oracle=0, action_steps=0, score_work=0, total_work=0,
        ))
        cell["n"] += 1
        for key in ("success", "correct_id", "correct_unresolved", "premature",
                    "wrong_id", "unresolved"):
            cell[key] += int(bool(row.get(key)))
        cell["budget_stop"] += int(row.get("stopped") == "budget")
        cell["redundant_taken"] += int(row.get("redundant_taken") or 0)
        for key in ("oracle", "action_steps", "score_work", "total_work"):
            cell[key] += int(row.get(key) or 0)
    for cell in by.values():
        n = max(cell["n"], 1)
        cell["success_rate"] = cell["success"] / n
        cell["mean_work"] = cell["total_work"] / n
        cell["mean_oracle"] = cell["oracle"] / n
        cell["mean_score_work"] = cell["score_work"] / n
    return by


def summarize_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["split"]].append(row)
    return {split: summarize(group) for split, group in grouped.items()}


def headroom_gate(dev_summary: dict[str, Any]) -> dict[str, Any]:
    env = {}
    for name in FIXED_METHODS:
        cell = dev_summary[name]
        n = max(int(cell.get("n") or 1), 1)
        env[name] = (int(cell.get("oracle") or 0) + int(cell.get("action_steps") or 0)) / n
    best_acc = max(dev_summary[name]["success"] for name in FIXED_METHODS)
    accs = {dev_summary[n]["success"] for n in FIXED_METHODS}
    cheapest = min(env, key=env.get)
    dearest = max(env, key=env.get)
    spread = env[dearest] / env[cheapest] if env[cheapest] else 1.0
    exists = (len(accs) > 1) or (spread >= HEADROOM_RATIO)
    return dict(
        exists=exists,
        best_accuracy=best_acc,
        cheapest_env=cheapest,
        env_work=env,
        work_spread=round(spread, 4),
        reason="query_choice_changes_cost_or_accuracy" if exists else "fixed_near_minimum",
    )


def competence_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    identifiable = [row for row in rows if row.get("gold_in_language")]
    outside = [row for row in rows if not row.get("gold_in_language")]
    report = dict(
        n=len(rows),
        success=sum(int(row["success"]) for row in rows),
        correct_id=sum(int(row["correct_id"]) for row in rows),
        correct_unresolved=sum(int(row["correct_unresolved"]) for row in rows),
        budget_stop=sum(int(row.get("stopped") == "budget") for row in rows),
        premature=sum(int(row["premature"]) for row in rows),
        redundant_taken=sum(int(row.get("redundant_taken") or 0) for row in rows),
        identifiable=len(identifiable),
        outside=len(outside),
    )
    report["passed"] = bool(
        rows
        and report["success"] == report["n"]
        and report["budget_stop"] == 0
        and report["premature"] == 0
        and report["redundant_taken"] == 0
        and all(row["correct_id"] for row in identifiable)
        and all(row["correct_unresolved"] for row in outside)
    )
    report["reason"] = "source_competence" if report["passed"] else "training_failure"
    return report


def select_strongest_fixed(dev_summary: dict[str, Any]) -> str:
    ranked = sorted(
        [name for name in FIXED_METHODS if name != "information_gain"],
        key=lambda name: (-dev_summary[name]["success"],
                          dev_summary[name]["oracle"] + dev_summary[name]["action_steps"],
                          name),
    )
    return ranked[0]


def run_study(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source = tasks_for("source")
    development = tasks_for("development")
    source_ig = run_method(source, "information_gain", zero_weights(), list(LANGUAGE), seed=5)
    frequency_rows = []
    for episode in source_ig:
        frequency_rows.extend(training_rows(episode))
    order = frequency_order(frequency_rows)
    headroom_rows = []
    for method in FIXED_METHODS:
        headroom_rows.extend(run_method(development, method, zero_weights(), order, seed=7))
    dev_summary = summarize(headroom_rows)
    gate = headroom_gate(dev_summary)
    strongest = select_strongest_fixed(dev_summary)
    competence_rows = []
    competence_reports = []
    seeds_used: list[dict[str, Any]] = []
    supervised_by_seed: list[dict[str, Any]] = []
    passed_seeds = []
    for seed in TRAIN_SEEDS:
        source_run = run_method(source, "information_gain", zero_weights(), list(LANGUAGE), seed=5 + seed)
        supervised = []
        for episode in source_run:
            supervised.extend(training_rows(episode, source="information_gain"))
        weights = fit_source(supervised)
        own_source = run_method(source, "trained", weights, order, seed=30 + seed)
        for episode in own_source:
            supervised.extend(dagger_rows(episode, random.Random(90 + seed)))
        weights = fit_source(supervised)
        frozen = policy_hash(weights)
        if frozen == policy_hash(zero_weights()):
            raise ValueError("source_fit_did_not_update")
        own_dev = run_method(development, "trained", weights, order, seed=11 + seed)
        for row in own_dev:
            row["method"] = "trained_own_dev"
        report = competence_gate(own_dev)
        report["seed"] = seed
        report["policy_hash"] = frozen
        competence_rows.extend(own_dev)
        competence_reports.append(report)
        seeds_used.append(dict(seed=seed, policy_hash=frozen, n_supervised=len(supervised),
                               competence=report["passed"]))
        supervised_by_seed.append(dict(seed=seed, rows=supervised, policy_hash=frozen))
        if report["passed"]:
            passed_seeds.append(dict(seed=seed, weights=weights, hash=frozen))
    competence = dict(
        reports=competence_reports,
        passed=bool(passed_seeds) and all(row["passed"] for row in competence_reports),
        n_seeds=len(competence_reports),
        n_passed=len(passed_seeds),
    )
    assess_rows: list[dict[str, Any]] = []
    assessment_closed = not competence["passed"]
    if not assessment_closed:
        for block in passed_seeds:
            seed = next(row["seed"] for row in seeds_used if row["policy_hash"] == block["hash"])
            for method, used in (
                ("trained", block["weights"]),
                ("reset_policy", reset_weights(block["weights"])),
                ("shuffled_policy", shuffle_weights(block["weights"], 100 + seed)),
                ("strongest_fixed", zero_weights()),
                ("source_frequency", zero_weights()),
                ("information_gain", zero_weights()),
            ):
                alias = strongest if method == "strongest_fixed" else method
                chunk = run_method(assessment_tasks(), alias, used, order, seed=20 + seed)
                if method == "strongest_fixed":
                    for row in chunk:
                        row["method"] = "strongest_fixed"
                        row["selected_fixed"] = strongest
                assess_rows.extend(chunk)
    usage = dict(
        wall_s=round(time.perf_counter() - started, 6),
        rss=sample_process_memory(),
        frozen_cpu_used_s=FROZEN_CPU_USED_S,
        frozen_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
        frozen_debit_s=0,
        product_chat_unused=True,
        metal_unused=True,
        model_calls=0,
        ledger="standing_local_cpu_grant",
        neural_unused=True,
    )
    verdict = (
        "training_failure" if assessment_closed else
        "useful learned investigation advantage"
    )
    payload = dict(
        kind=KIND,
        confirmation=False,
        learning_to_learn_established=False,
        ranking_paused=True,
        coding_interface_paused=True,
        opened_api_grids_not_rescored=True,
        prior_assessment_closed=PRIOR_ASSESSMENT_CLOSED,
        assessment_closed=assessment_closed,
        language=list(LANGUAGE),
        language_hash=language_hash(),
        splits=split_lock(),
        feature_names=list(FEATURE_NAMES),
        max_steps=MAX_STEPS,
        redundant_mask=REDUNDANT_MASK_ORIGIN,
        source_ig=source_ig,
        supervised_rows=frequency_rows,
        supervised_by_seed=supervised_by_seed,
        frequency_order=order,
        development=headroom_rows,
        development_summary=dev_summary,
        headroom=gate,
        strongest_fixed=strongest,
        trained=True,
        competence=competence,
        competence_episodes=competence_rows,
        policy_seeds=seeds_used,
        assessment=assess_rows,
        assessment_summary=summarize(assess_rows) if assess_rows else {},
        assessment_by_split=summarize_split(assess_rows) if assess_rows else {},
        verdict=verdict if assessment_closed else "assessed",
        usage=usage,
        claim_boundaries=dict(
            learning_to_learn=False,
            ig_is_training_supervision=True,
            dagger_is_source_only=True,
            programmer_supplied_language=True,
            programmer_supplied_redundant_mask=True,
            hypothesis_may_exclude_truth=True,
        ),
    )
    payload["hash"] = digest({
        "competence": competence,
        "assessment_closed": assessment_closed,
        "development": {name: dict(success=cell["success"], work=cell["total_work"])
                        for name, cell in dev_summary.items()},
        "verdict": payload["verdict"],
    })
    (directory / "seed_mechanism_competence.json").write_text(
        json.dumps(payload, default=str), encoding="utf-8")
    return payload


def verify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    ok = True
    tasks = {row["task_id"]: row for row in catalogue()}
    if payload.get("usage", {}).get("frozen_debit_s") != 0:
        ok = False
        notes.append("frozen_debit")
    if payload.get("learning_to_learn_established"):
        ok = False
        notes.append("claimed_l2l")
    if payload.get("usage", {}).get("model_calls"):
        ok = False
        notes.append("model_calls")
    if payload.get("redundant_mask") != REDUNDANT_MASK_ORIGIN:
        ok = False
        notes.append("mask_origin")
    for block in payload.get("supervised_by_seed") or []:
        reconstructed = fit_source(block.get("rows") or [])
        if policy_hash(reconstructed) != block.get("policy_hash"):
            ok = False
            notes.append("policy_update_mismatch")
        if policy_hash(reconstructed) == policy_hash(zero_weights()):
            ok = False
            notes.append("no_parameter_update")
        stops = {row.get("chosen") for row in block.get("rows") or []}
        if "STOP_IDENTIFY" not in stops:
            ok = False
            notes.append("training_missing_stop_identify")
        if "STOP_UNRESOLVED" not in stops:
            ok = False
            notes.append("training_missing_stop_unresolved")
    if payload.get("assessment_closed"):
        if payload.get("assessment"):
            ok = False
            notes.append("assessment_should_be_closed")
        if payload.get("competence", {}).get("passed"):
            ok = False
            notes.append("closed_despite_competence")
    else:
        if not payload.get("assessment"):
            ok = False
            notes.append("assessment_missing_after_competence")
    for row in (payload.get("development") or []) + (payload.get("competence_episodes") or []) + (payload.get("assessment") or []):
        task = tasks.get(row["task_id"])
        if task is None:
            ok = False
            notes.append("unknown_task:" + row["task_id"])
            continue
        replay = filter_language(row["transcript"])
        if replay != row["remaining"]:
            ok = False
            notes.append("vs_replay:" + row["task_id"] + ":" + str(row.get("method")))
        for step in row["transcript"]:
            if set(step["features"]) != set(FEATURE_NAMES):
                ok = False
                notes.append("feature_set")
            if set(step["features"]) & HIDDEN:
                ok = False
                notes.append("hidden_feature")
        if row["split"] == "excluded_family" and row.get("correct_id"):
            ok = False
            notes.append("excluded_identified:" + row["task_id"])
    rebuilt = summarize(payload.get("development") or [])
    saved = payload.get("development_summary") or {}
    for name, cell in rebuilt.items():
        other = saved.get(name) or {}
        if cell.get("success") != other.get("success") or cell.get("total_work") != other.get("total_work"):
            ok = False
            notes.append("dev_summary:" + name)
    return dict(valid=ok, notes=notes,
                n=len(payload.get("development") or []) + len(payload.get("competence_episodes") or []) + len(payload.get("assessment") or []))
