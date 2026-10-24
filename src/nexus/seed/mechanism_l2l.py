"""Source-trained investigation policy versus equal-access fixed strategies.

IG traces used for training are labeled supervision. Assessment never sees
those answers as features. Task memory resets every episode.
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
    FEATURE_NAMES, HIDDEN, choose_diagnostic, choose_frequency, choose_information_gain,
    choose_random, filter_language, run_episode,
)
from .mechanism_policy import (
    fit_source, frequency_order, policy_hash, reset_weights, select_action,
    shuffle_weights, training_rows, zero_weights,
)
from .mechanism_tasks import assessment_tasks, catalogue, split_lock, tasks_for
from .mechanism_world import LANGUAGE, MAX_STEPS, language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_mechanism_l2l"
HEADROOM_RATIO = 1.15
TRAIN_SEEDS = (0, 1, 2)
FIXED_METHODS = ("information_gain", "fixed_diagnostic", "source_frequency", "random")
ASSESS_METHODS = (
    "trained", "reset_policy", "shuffled_policy",
    "strongest_fixed", "source_frequency", "information_gain",
)


def _chooser(method: str, weights: dict[str, list[float]], order: list[str]) -> Callable:
    def choose(ctx: dict[str, Any]) -> dict[str, Any]:
        remaining, transcript, available, rng = (
            ctx["remaining"], ctx["transcript"], ctx["available"], ctx["rng"],
        )
        if method == "information_gain":
            return choose_information_gain(remaining, transcript, available, rng)
        if method == "fixed_diagnostic":
            return choose_diagnostic(remaining, transcript, available)
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


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, dict[str, Any]] = {}
    for row in rows:
        cell = by.setdefault(row["method"], dict(
            n=0, success=0, correct_id=0, correct_unresolved=0, premature=0,
            wrong_id=0, unresolved=0, oracle=0, action_steps=0, score_work=0,
            total_work=0,
        ))
        cell["n"] += 1
        for key in ("success", "correct_id", "correct_unresolved", "premature",
                    "wrong_id", "unresolved"):
            cell[key] += int(bool(row.get(key)))
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
    best_acc = max(dev_summary[name]["success"] for name in FIXED_METHODS)
    contenders = [name for name in FIXED_METHODS if dev_summary[name]["success"] == best_acc]
    works = {name: dev_summary[name]["mean_work"] for name in contenders}
    cheapest = min(works, key=works.get)
    dearest = max(works, key=works.get)
    spread = works[dearest] / works[cheapest] if works[cheapest] else 1.0
    ig_best = "information_gain" in contenders
    exists = (spread >= HEADROOM_RATIO) or (len({dev_summary[n]["success"] for n in FIXED_METHODS}) > 1)
    return dict(
        exists=exists,
        best_accuracy=best_acc,
        contenders=contenders,
        cheapest_at_best=cheapest,
        work_spread=round(spread, 4),
        ig_among_best=ig_best,
        reason="query_choice_changes_cost_or_accuracy" if exists else "fixed_near_minimum",
    )


def select_strongest_fixed(dev_summary: dict[str, Any]) -> str:
    ranked = sorted(
        [name for name in FIXED_METHODS if name != "information_gain"],
        key=lambda name: (-dev_summary[name]["success"], dev_summary[name]["mean_work"], name),
    )
    return ranked[0]


def verdict(assess: dict[str, Any], gate: dict[str, Any], strongest: str) -> str:
    if not gate["exists"]:
        return "inconclusive / insufficient headroom"
    trained = assess.get("trained") or {}
    strong = assess.get(strongest) or assess.get("strongest_fixed") or {}
    reset = assess.get("reset_policy") or {}
    shuffled = assess.get("shuffled_policy") or {}
    ig = assess.get("information_gain") or {}
    within = assess
    if trained.get("success", 0) < strong.get("success", 0):
        return "negative"
    if trained.get("success", 0) == strong.get("success", 0) and trained.get("mean_work", 0) >= 0.99 * strong.get("mean_work", 1):
        return "fixed-baseline tie"
    if trained.get("success", 0) <= reset.get("success", 0) and trained.get("mean_work", 1) >= reset.get("mean_work", 0):
        return "inconclusive / insufficient headroom"
    if trained.get("success", 0) <= shuffled.get("success", 0) and trained.get("mean_work", 1) >= shuffled.get("mean_work", 0):
        return "inconclusive / insufficient headroom"
    if trained.get("success", 0) < ig.get("success", 0):
        return "negative"
    return "useful learned investigation advantage"


def split_verdicts(rows: list[dict[str, Any]], strongest: str, gate: dict[str, Any]) -> dict[str, str]:
    out = {}
    for split in ("within_family", "composition", "excluded_family"):
        subset = [row for row in rows if row["split"] == split]
        out[split] = verdict(summarize(subset), gate, strongest)
    return out


def run_study(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source = tasks_for("source")
    development = tasks_for("development")
    assessment = assessment_tasks()
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
    assess_rows = []
    retention = []
    seeds_used: list[dict[str, Any]] = []
    supervised_by_seed: list[dict[str, Any]] = []
    trained_anyway = False
    if gate["exists"]:
        trained_anyway = True
        for seed in TRAIN_SEEDS:
            source_run = run_method(source, "information_gain", zero_weights(), list(LANGUAGE), seed=5 + seed)
            supervised = []
            for episode in source_run:
                supervised.extend(training_rows(episode))
            weights = fit_source(supervised)
            frozen = policy_hash(weights)
            if frozen == policy_hash(zero_weights()):
                raise ValueError("source_fit_did_not_update")
            seeds_used.append(dict(seed=seed, policy_hash=frozen, n_supervised=len(supervised)))
            supervised_by_seed.append(dict(seed=seed, rows=supervised, policy_hash=frozen))
            for method, used in (
                ("trained", weights),
                ("reset_policy", reset_weights(weights)),
                ("shuffled_policy", shuffle_weights(weights, 100 + seed)),
                ("strongest_fixed", zero_weights()),
                ("source_frequency", zero_weights()),
                ("information_gain", zero_weights()),
            ):
                alias = strongest if method == "strongest_fixed" else method
                chunk = run_method(assessment, alias, used, order, seed=20 + seed)
                if method == "strongest_fixed":
                    for row in chunk:
                        row["method"] = "strongest_fixed"
                        row["selected_fixed"] = strongest
                assess_rows.extend(chunk)
            retention.extend(run_method(source[:4], "trained", weights, order, seed=40 + seed))
            retention.extend(run_method(source[:4], "information_gain", zero_weights(), order, seed=50 + seed))
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
    assess_summary = summarize(assess_rows) if assess_rows else {}
    payload = dict(
        kind=KIND,
        confirmation=False,
        learning_to_learn_established=False,
        ranking_paused=True,
        coding_interface_paused=True,
        opened_api_grids_not_rescored=True,
        language=list(LANGUAGE),
        language_hash=language_hash(),
        splits=split_lock(),
        feature_names=list(FEATURE_NAMES),
        max_steps=MAX_STEPS,
        source_ig=source_ig,
        supervised_rows=frequency_rows,
        supervised_by_seed=supervised_by_seed,
        frequency_order=order,
        development=headroom_rows,
        development_summary=dev_summary,
        headroom=gate,
        strongest_fixed=strongest,
        trained=trained_anyway,
        policy_seeds=seeds_used,
        assessment=assess_rows,
        assessment_summary=assess_summary,
        assessment_by_split=summarize_split(assess_rows) if assess_rows else {},
        retention=retention,
        retention_summary=summarize(retention) if retention else {},
        split_verdicts=split_verdicts(assess_rows, strongest, gate) if assess_rows else {},
        verdict=verdict(assess_summary, gate, "strongest_fixed") if assess_rows else gate["reason"],
        usage=usage,
        claim_boundaries=dict(
            learning_to_learn=False,
            ig_is_training_supervision=True,
            programmer_supplied_language=True,
            hypothesis_may_exclude_truth=True,
        ),
    )
    payload["hash"] = digest({
        "headroom": gate,
        "development": {name: dict(success=cell["success"], work=cell["total_work"])
                        for name, cell in dev_summary.items()},
        "assessment": {name: dict(success=cell["success"], work=cell["total_work"])
                       for name, cell in assess_summary.items()},
        "verdict": payload["verdict"],
    })
    (directory / "seed_mechanism_l2l.json").write_text(
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
    if payload.get("trained"):
        if not payload.get("supervised_by_seed"):
            ok = False
            notes.append("missing_per_seed_supervision")
        for block in payload.get("supervised_by_seed") or []:
            reconstructed = fit_source(block.get("rows") or [])
            if policy_hash(reconstructed) != block.get("policy_hash"):
                ok = False
                notes.append("policy_update_mismatch")
            if policy_hash(reconstructed) == policy_hash(zero_weights()):
                ok = False
                notes.append("no_parameter_update")
        assess_hashes = {row.get("policy_seed") for row in payload.get("assessment") or [] if row["method"] == "trained"}
        if not assess_hashes:
            ok = False
            notes.append("assessment_missing_trained")
    for row in (payload.get("development") or []) + (payload.get("assessment") or []):
        task = tasks.get(row["task_id"])
        if task is None:
            ok = False
            notes.append("unknown_task:" + row["task_id"])
            continue
        replay = filter_language(row["transcript"])
        if replay != row["remaining"]:
            ok = False
            notes.append("vs_replay:" + row["task_id"] + ":" + row["method"])
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
    return dict(valid=ok, notes=notes, n=len(payload.get("development") or []) + len(payload.get("assessment") or []))
