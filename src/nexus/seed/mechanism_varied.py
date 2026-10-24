"""Varied-probe challenge. Diagnostic+MEASURE is a charged baseline.

Opened mismatch/C/D/E cells are not rescored. MEASURE, sequences and
twins are different evidence problems. Not learning-to-learn.
"""
from __future__ import annotations

import json
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .mechanism_investigate import FEATURE_NAMES, HIDDEN, filter_language
from .mechanism_l2l import (
    FIXED_METHODS, TRAIN_SEEDS, competence_gate, dagger_rows, fit_source,
    frequency_order, headroom_gate, policy_hash, reset_weights, run_method,
    select_strongest_fixed, shuffle_weights, summarize, training_rows,
    zero_weights,
)
from .mechanism_tasks import catalogue, split_lock, tasks_for, varied_tasks
from .mechanism_world import LANGUAGE, language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_mechanism_varied"
PRIOR_CLOSED = ("92d6f19", "ff26a18", "5575762")
OPENED_IDS = {
    "c_add4", "c_count2", "d_add_mul", "d_count_add", "e_delay", "e_threshold",
    "mm_abs", "mm_mod3", "mm_clip0", "mm_prev", "ctl_neg", "ctl_toggle",
}
ASSESS_METHODS = (
    "trained",
    "reset_policy",
    "shuffled_policy",
    "fixed_diagnostic",
    "fixed_diagnostic_measure",
    "cost_aware_ig",
    "information_gain",
)
COMPARE_FIXED = (
    "fixed_diagnostic",
    "fixed_diagnostic_measure",
    "cost_aware_ig",
)


def score_columns(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        cell = out.setdefault(row["method"], dict(
            n=0, correct_solutions=0, false_identification=0,
            demonstrated_inconsistency=0, unresolved_uncertainty=0,
            unresolved=0, correct_unresolved=0, failed_unresolved=0,
            total_work=0, oracle=0, measured=0,
            ordinary_n=0, ordinary_correct=0, ordinary_measured=0, ordinary_oracle=0,
        ))
        cell["n"] += 1
        cell["correct_solutions"] += int(bool(row.get("correct_id")))
        cell["false_identification"] += int(bool(row.get("wrong_id")))
        cell["demonstrated_inconsistency"] += int(bool(row.get("demonstrated_inconsistency")))
        cell["unresolved_uncertainty"] += int(bool(row.get("unresolved_uncertainty")))
        unresolved = bool(row.get("unresolved"))
        cell["unresolved"] += int(unresolved)
        cell["correct_unresolved"] += int(bool(row.get("correct_unresolved")))
        cell["failed_unresolved"] += int(unresolved and row.get("gold_in_language"))
        cell["total_work"] += int(row.get("total_work") or 0)
        cell["oracle"] += int(row.get("oracle") or 0)
        cell["measured"] += int(bool(row.get("measured")))
        if row.get("split") == "varied_ordinary":
            cell["ordinary_n"] += 1
            cell["ordinary_correct"] += int(bool(row.get("correct_id")))
            cell["ordinary_measured"] += int(bool(row.get("measured")))
            cell["ordinary_oracle"] += int(row.get("oracle") or 0)
    for cell in out.values():
        n = max(cell["n"], 1)
        cell["mean_work"] = cell["total_work"] / n
        cell["mean_oracle"] = cell["oracle"] / n
        on = max(cell["ordinary_n"], 1)
        cell["ordinary_mean_oracle"] = cell["ordinary_oracle"] / on
    return out


def score_by_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["split"]].append(row)
    return {split: score_columns(group) for split, group in grouped.items()}


def _best_fixed(columns: dict[str, Any]) -> dict[str, Any]:
    ranked = []
    for name in COMPARE_FIXED:
        cell = columns.get(name) or {}
        ranked.append((
            -int(cell.get("correct_solutions") or 0),
            int(cell.get("false_identification") or 0),
            -int(cell.get("demonstrated_inconsistency") or 0),
            int(cell.get("oracle") or 0),
            name,
        ))
    ranked.sort()
    name = ranked[0][-1]
    return dict(name=name, **dict(columns.get(name) or {}))


def _verdict(closed: bool, columns: dict[str, Any]) -> str:
    if closed:
        return "training_failure"
    trained = columns.get("trained") or {}
    best = _best_fixed(columns)
    if int(trained.get("false_identification") or 0) > int(best.get("false_identification") or 0):
        return "negative"
    if int(trained.get("correct_solutions") or 0) < int(best.get("correct_solutions") or 0):
        return "negative"
    same_sol = int(trained.get("correct_solutions") or 0) == int(best.get("correct_solutions") or 0)
    same_false = int(trained.get("false_identification") or 0) == int(best.get("false_identification") or 0)
    same_incons = (
        int(trained.get("demonstrated_inconsistency") or 0)
        == int(best.get("demonstrated_inconsistency") or 0)
    )
    cheaper_ordinary = (
        float(trained.get("ordinary_mean_oracle") or 0)
        + 1e-9 < float(best.get("ordinary_mean_oracle") or 0)
    )
    if same_sol and same_false and same_incons and not cheaper_ordinary:
        return "fixed-baseline tie"
    return "useful learned investigation advantage"


def run_varied(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source = tasks_for("source")
    development = tasks_for("development")
    challenge = varied_tasks()
    if any(row["task_id"] in OPENED_IDS for row in challenge):
        raise ValueError("opened_id_in_challenge")
    source_ig = run_method(source, "information_gain", zero_weights(), list(LANGUAGE), seed=5)
    supervised0 = []
    for episode in source_ig:
        supervised0.extend(training_rows(episode))
    order = frequency_order(supervised0)
    headroom_rows = []
    for method in FIXED_METHODS:
        headroom_rows.extend(run_method(development, method, zero_weights(), order, seed=7))
    assess_rows: list[dict[str, Any]] = []
    competence_rows = []
    reports = []
    supervised_by_seed = []
    seeds_used = []
    strongest = select_strongest_fixed(summarize(headroom_rows))
    passed = []
    for seed in TRAIN_SEEDS:
        source_run = run_method(source, "information_gain", zero_weights(), list(LANGUAGE), seed=5 + seed)
        supervised = []
        for episode in source_run:
            supervised.extend(training_rows(episode))
        weights = fit_source(supervised)
        own = run_method(source, "trained", weights, order, seed=30 + seed)
        for episode in own:
            supervised.extend(dagger_rows(episode, random.Random(90 + seed)))
        weights = fit_source(supervised)
        frozen = policy_hash(weights)
        own_dev = run_method(development, "trained", weights, order, seed=11 + seed)
        for row in own_dev:
            row["method"] = "trained_own_dev"
        report = competence_gate(own_dev)
        report["seed"] = seed
        report["policy_hash"] = frozen
        reports.append(report)
        competence_rows.extend(own_dev)
        seeds_used.append(dict(seed=seed, policy_hash=frozen, competence=report["passed"]))
        supervised_by_seed.append(dict(seed=seed, rows=supervised, policy_hash=frozen))
        if report["passed"]:
            passed.append(dict(seed=seed, weights=weights, hash=frozen))
    competence = dict(
        reports=reports, passed=bool(passed) and all(row["passed"] for row in reports),
        n_passed=len(passed),
    )
    closed = not competence["passed"]
    if not closed:
        for block in passed:
            seed = block["seed"]
            for method, used in (
                ("trained", block["weights"]),
                ("reset_policy", reset_weights(block["weights"])),
                ("shuffled_policy", shuffle_weights(block["weights"], 100 + seed)),
                ("fixed_diagnostic", zero_weights()),
                ("fixed_diagnostic_measure", zero_weights()),
                ("cost_aware_ig", zero_weights()),
                ("information_gain", zero_weights()),
            ):
                chunk = run_method(challenge, method, used, order, seed=20 + seed)
                assess_rows.extend(chunk)
    columns = score_columns(assess_rows)
    verdict = _verdict(closed, columns)
    payload = dict(
        kind=KIND,
        confirmation=False,
        learning_to_learn_established=False,
        ranking_paused=True,
        prior_assessments_closed=list(PRIOR_CLOSED),
        opened_ids_not_rescored=sorted(OPENED_IDS),
        assessment_closed=closed,
        language=list(LANGUAGE),
        language_hash=language_hash(),
        splits=split_lock(),
        feature_names=list(FEATURE_NAMES),
        support_rule="post_singleton_probe",
        confirm_measure_charged=True,
        development=headroom_rows,
        development_summary=summarize(headroom_rows),
        headroom=headroom_gate(summarize(headroom_rows)),
        strongest_dev_fixed=strongest,
        competence=competence,
        competence_episodes=competence_rows,
        policy_seeds=seeds_used,
        supervised_by_seed=supervised_by_seed,
        assessment=assess_rows,
        columns=columns,
        columns_by_split=score_by_split(assess_rows),
        compared_fixed=list(COMPARE_FIXED),
        best_fixed=_best_fixed(columns) if assess_rows else {},
        verdict=verdict,
        usage=dict(
            wall_s=round(time.perf_counter() - started, 6),
            rss=sample_process_memory(),
            frozen_cpu_used_s=FROZEN_CPU_USED_S,
            frozen_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
            frozen_debit_s=0,
            product_chat_unused=True,
            metal_unused=True,
            model_calls=0,
            ledger="standing_local_cpu_grant",
        ),
        claim_boundaries=dict(
            learning_to_learn=False,
            diagnostic_measure_is_fixed_baseline=True,
            cost_aware_ig_is_not_learned=True,
            twins_are_observationally_identical=True,
            ordinary_tasks_measure_unnecessary_checking=True,
        ),
    )
    payload["hash"] = digest({
        "columns": columns,
        "verdict": verdict,
        "assessment_closed": closed,
    })
    (directory / "seed_mechanism_varied.json").write_text(
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
    for row in payload.get("assessment") or []:
        if row["task_id"] in OPENED_IDS:
            ok = False
            notes.append("rescored_opened:" + row["task_id"])
        if row["method"] not in ASSESS_METHODS:
            ok = False
            notes.append("unexpected_method:" + str(row.get("method")))
        if set((row.get("transcript") or [{}])[0].get("features") or {}) & HIDDEN:
            ok = False
            notes.append("hidden_feature")
        replay = filter_language(row["transcript"])
        if replay != row["remaining"]:
            ok = False
            notes.append("vs_replay:" + row["task_id"])
        if row["split"] in ("varied_measure", "varied_sequence", "varied_indistinct") and row.get("correct_id"):
            ok = False
            notes.append("outside_identified:" + row["task_id"])
        task = tasks.get(row["task_id"])
        if task and task["split"] != row["split"]:
            ok = False
            notes.append("split_mismatch:" + row["task_id"])
    if payload.get("assessment_closed") and payload.get("assessment"):
        ok = False
        notes.append("closed_but_assessed")
    rebuilt = score_columns(payload.get("assessment") or [])
    saved = payload.get("columns") or {}
    if rebuilt and saved:
        for name, cell in rebuilt.items():
            other = saved.get(name) or {}
            for key in (
                "correct_solutions", "false_identification",
                "demonstrated_inconsistency", "unresolved_uncertainty", "oracle",
            ):
                if cell.get(key) != other.get(key):
                    ok = False
                    notes.append("column:" + name + ":" + key)
    return dict(valid=ok, notes=notes, n=len(payload.get("assessment") or []))
