"""Fresh model-mismatch challenge. Opened E/C/D cells are not rescored.

Catalogue singleton is not identification. Every method may falsify or
report uncertainty. DAgger/IG stopping is audited on saved records.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .mechanism_investigate import (
    FEATURE_NAMES, HIDDEN, identification_supported, filter_language,
)
from .mechanism_l2l import (
    FIXED_METHODS, TRAIN_SEEDS, _chooser, competence_gate, fit_source,
    dagger_rows, frequency_order, headroom_gate, policy_hash, reset_weights,
    run_method, select_strongest_fixed, shuffle_weights, summarize,
    training_rows, zero_weights,
)
from .mechanism_tasks import catalogue, mismatch_tasks, split_lock, tasks_for
from .mechanism_world import LANGUAGE, language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_mechanism_mismatch"
PRIOR_CLOSED = ("92d6f19", "ff26a18")
OPENED_IDS = {
    "c_add4", "c_count2", "d_add_mul", "d_count_add", "e_delay", "e_threshold",
}


def diagnose_excluded(payload: dict[str, Any]) -> dict[str, Any]:
    """Development analysis of saved competence records. No rescoring."""
    rows = [
        row for row in payload.get("assessment") or []
        if row.get("split") == "excluded_family"
    ]
    cases = []
    for task_id in ("e_delay", "e_threshold"):
        by = {row["method"]: row for row in rows if row["task_id"] == task_id and row.get("policy_seed") == 20}
        diag = by.get("strongest_fixed") or by.get("fixed_diagnostic")
        trained = by.get("trained")
        ig = by.get("information_gain")
        if not diag or not trained or not ig:
            continue
        first_gap = None
        diag_acts = [(s["action"], s.get("observation")) for s in diag["transcript"] if not str(s["action"]).startswith("STOP")]
        train_acts = [(s["action"], s.get("observation")) for s in trained["transcript"] if not str(s["action"]).startswith("STOP")]
        for index, pair in enumerate(diag_acts):
            if index >= len(train_acts) or train_acts[index] != pair:
                first_gap = dict(
                    step=index, diagnostic=pair,
                    trained=train_acts[index] if index < len(train_acts) else None,
                    ig=[(s["action"], s.get("observation")) for s in ig["transcript"]
                        if not str(s["action"]).startswith("STOP")],
                )
                break
        env = [s for s in trained["transcript"] if not str(s["action"]).startswith("STOP")]
        singleton_stop = bool(
            trained.get("identified")
            and not identification_supported(trained.get("remaining") or [], env)
        )
        cases.append(dict(
            task_id=task_id,
            diagnostic_success=diag.get("success"),
            trained_success=trained.get("success"),
            trained_identified=trained.get("identified"),
            ig_identified=ig.get("identified"),
            diagnostic_queries=diag_acts,
            trained_queries=train_acts,
            first_evidence_gap=first_gap,
            trained_stopped_on_unsupported_singleton=singleton_stop,
        ))
    return dict(
        origin="saved_competence_records",
        rescoring=False,
        finding=(
            "diagnostic ACT_1=0 empties the language on threshold; "
            "trained/IG never ask ACT_1 and stop on catalogue singleton toggle"
        ),
        cases=cases,
    )


def score_columns(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        cell = out.setdefault(row["method"], dict(
            n=0, correct_solutions=0, false_identification=0,
            unresolved=0, correct_unresolved=0, failed_unresolved=0,
            total_work=0, oracle=0,
        ))
        cell["n"] += 1
        cell["correct_solutions"] += int(bool(row.get("correct_id")))
        cell["false_identification"] += int(bool(row.get("wrong_id")))
        unresolved = bool(row.get("unresolved"))
        cell["unresolved"] += int(unresolved)
        cell["correct_unresolved"] += int(bool(row.get("correct_unresolved")))
        cell["failed_unresolved"] += int(unresolved and row.get("gold_in_language"))
        cell["total_work"] += int(row.get("total_work") or 0)
        cell["oracle"] += int(row.get("oracle") or 0)
    for cell in out.values():
        n = max(cell["n"], 1)
        cell["mean_work"] = cell["total_work"] / n
    return out


def run_mismatch(directory: Path, prior_path: Path | None = None) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    diagnosis = {}
    if prior_path and Path(prior_path).is_file():
        diagnosis = diagnose_excluded(json.loads(Path(prior_path).read_text(encoding="utf-8")))
    source = tasks_for("source")
    development = tasks_for("development")
    challenge = mismatch_tasks()
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
                ("strongest_fixed", zero_weights()),
                ("source_frequency", zero_weights()),
                ("information_gain", zero_weights()),
            ):
                alias = strongest if method == "strongest_fixed" else method
                chunk = run_method(challenge, alias, used, order, seed=20 + seed)
                if method == "strongest_fixed":
                    for row in chunk:
                        row["method"] = "strongest_fixed"
                        row["selected_fixed"] = strongest
                assess_rows.extend(chunk)
    columns = score_columns(assess_rows)
    trained = columns.get("trained") or {}
    strong = columns.get("strongest_fixed") or {}
    if closed:
        verdict = "training_failure"
    elif trained.get("false_identification", 0) > strong.get("false_identification", 0):
        verdict = "negative"
    elif trained.get("correct_solutions", 0) < strong.get("correct_solutions", 0):
        verdict = "negative"
    elif trained.get("correct_solutions", 0) == strong.get("correct_solutions", 0) and trained.get("false_identification", 0) == strong.get("false_identification", 0):
        verdict = "fixed-baseline tie"
    else:
        verdict = "useful learned investigation advantage"
    payload = dict(
        kind=KIND,
        confirmation=False,
        learning_to_learn_established=False,
        ranking_paused=True,
        prior_assessments_closed=list(PRIOR_CLOSED),
        opened_ids_not_rescored=sorted(OPENED_IDS),
        assessment_closed=closed,
        diagnosis=diagnosis,
        language=list(LANGUAGE),
        language_hash=language_hash(),
        splits=split_lock(),
        feature_names=list(FEATURE_NAMES),
        support_rule="post_singleton_probe",
        development=headroom_rows,
        development_summary=summarize(headroom_rows),
        headroom=headroom_gate(summarize(headroom_rows)),
        strongest_fixed=strongest,
        competence=competence,
        competence_episodes=competence_rows,
        policy_seeds=seeds_used,
        supervised_by_seed=supervised_by_seed,
        assessment=assess_rows,
        columns=columns,
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
            catalogue_singleton_is_not_identification=True,
            mismatch_truth_outside_language=True,
        ),
    )
    payload["hash"] = digest({
        "diagnosis": diagnosis.get("finding"),
        "columns": columns,
        "verdict": verdict,
        "assessment_closed": closed,
    })
    (directory / "seed_mechanism_mismatch.json").write_text(
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
    for row in payload.get("assessment") or []:
        if row["task_id"] in OPENED_IDS:
            ok = False
            notes.append("rescored_opened:" + row["task_id"])
        if set((row.get("transcript") or [{}])[0].get("features") or {}) & HIDDEN:
            ok = False
            notes.append("hidden_feature")
        replay = filter_language(row["transcript"])
        if replay != row["remaining"]:
            ok = False
            notes.append("vs_replay:" + row["task_id"])
        if row["split"] == "mismatch" and row.get("correct_id"):
            ok = False
            notes.append("mismatch_identified:" + row["task_id"])
    if payload.get("assessment_closed") and payload.get("assessment"):
        ok = False
        notes.append("closed_but_assessed")
    rebuilt = score_columns(payload.get("assessment") or [])
    if rebuilt != (payload.get("columns") or {}) and (payload.get("assessment") or payload.get("columns")):
        for name, cell in rebuilt.items():
            other = (payload.get("columns") or {}).get(name) or {}
            for key in ("correct_solutions", "false_identification", "unresolved", "total_work"):
                if cell.get(key) != other.get(key):
                    ok = False
                    notes.append("column:" + name + ":" + key)
    return dict(valid=ok, notes=notes, n=len(payload.get("assessment") or []))
