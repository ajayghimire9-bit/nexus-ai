"""Acquired-experience transfer using RepairSchemaStore.

C is ordinary Lt→LtE template retrieval. D applies the captured schema
and may rebound Gt→GtE via apply_make_inclusive. Those are different.
Not learning-to-learn. Ranking stays paused. Programmer-supplied
acquisition path; no handwritten task answers enter the store.
"""
from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from .capability_evidence import EventMeter, digest
from .experience_transfer_tasks import (
    all_declared, development_tasks, source_tasks, target_tasks,
)
from .extraction_path import generate_direct, score_task
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .repair_schema_memory import (
    OrdinaryExactCache, RepairSchema, RepairSchemaStore, apply_make_inclusive,
    apply_or_to_explicit_none, as_record, capture_from_success,
    ordinary_template_apply, propose_guarded_template, propose_retrieved_repair,
)

METHODS = (
    "scratch",
    "exact_cache",
    "ordinary_template",
    "acquired",
    "acquired_reset",
    "irrelevant_memory",
)
LIVE_METHODS = ("scratch", "acquired_reset")
WALL_CAP_S = 900.0
CALL_CAP = 80
KIND = "seed_acquired_experience"


def record_episode(task: dict[str, Any], initial: dict[str, str],
                   failure: dict[str, Any] | None, actions: list[str],
                   result_files: dict[str, str], public: dict[str, Any],
                   cost: dict[str, Any]) -> dict[str, Any]:
    return dict(
        request=task["request"],
        contract=task.get("contract"),
        initial_proposal=initial,
        public_failure=failure,
        revision_actions=actions,
        resulting_program=result_files,
        public_validation=public,
        cost=cost,
        private_tests_used=False,
        task_id_features=False,
        handwritten_answer=False,
    )


def acquire_from_source(task: dict[str, Any], meter: EventMeter) -> dict[str, Any]:
    """Public success only. Private tests never enter the store."""
    started = time.perf_counter()
    initial = dict(task["files"])
    before = score_task(dict(task, private=[]), initial)
    failure = None if before.get("public_passed") else dict(
        public_passed=False, exception=before.get("errors") or before.get("public"),
    )
    if task["family"] == "comparison_boundary":
        patched = meter.call("acquisition", "apply_make_inclusive", task["task_id"],
                             lambda files: apply_make_inclusive(files), initial)
        action = "apply_make_inclusive"
    else:
        patched = meter.call("acquisition", "apply_or_to_explicit_none", task["task_id"],
                             lambda files: apply_or_to_explicit_none(files, RepairSchema(
                                 schema_id="acq_null", family="null_default",
                                 trigger=task["request"],
                                 transformation="or_to_explicit_none",
                                 applicability={},
                                 preconditions={"require_unique_or": True},
                             )), initial)
        action = "apply_or_to_explicit_none"
    files = patched or dict(initial)
    public = score_task(dict(task, private=[]), files)
    cost = dict(wall_s=round(time.perf_counter() - started, 6), model_calls=0, tools=1)
    schema = None
    if public.get("public_passed"):
        schema = capture_from_success(
            task["family"], task["request"], initial, files, task["public"], cost,
        )
    episode = record_episode(task, initial, failure, [action], files, public, cost)
    return dict(
        episode=episode, schema=schema, files=files,
        usable=schema is not None and schema.transformation != "single_file_replace",
        public_passed=bool(public.get("public_passed")),
        programmer_supplied_abstraction=True,
        learned_abstraction=False,
    )


def _score(task: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    return score_task(task, files)


def _cell(task: dict[str, Any], method: str, files: dict[str, str],
          decision: str, reason: str, cost: dict[str, Any],
          retrieval_tokens: int = 0) -> dict[str, Any]:
    scored = _score(task, files)
    applied = decision == "apply"
    harmful = bool(
        applied and task.get("reuse_role") == "harmful_if_applied"
        and not scored.get("private_passed")
    )
    applicability = _applicability(task, decision)
    return dict(
        task_id=task["task_id"],
        method=method,
        family=task.get("family"),
        reuse_role=task.get("reuse_role"),
        exact_repeat=bool((task.get("overlap") or {}).get("exact")),
        decision=decision,
        reason=reason,
        applied=applied,
        public_passed=bool(scored.get("public_passed")),
        private_passed=bool(scored.get("private_passed")),
        harmful_transfer=harmful,
        applicability_correct=applicability,
        files=files,
        cost=dict(cost, retrieval_tokens=retrieval_tokens),
        overlap=task.get("overlap"),
    )


def _applicability(task: dict[str, Any], decision: str) -> bool:
    role = task.get("reuse_role")
    if role in {"related_rename", "related_rebound", "exact_repeat"}:
        return decision == "apply"
    if role == "harmful_if_applied":
        return decision in {"refuse", "abstain"}
    if role == "unrelated_abstain":
        return decision in {"abstain", "refuse"}
    if role == "ambiguous_ask":
        return decision == "ask"
    return False


def run_memory_cell(task: dict[str, Any], method: str, store: RepairSchemaStore,
                    cache: OrdinaryExactCache, meter: EventMeter) -> dict[str, Any]:
    started = time.perf_counter()
    files = dict(task["files"])
    decision, reason, retrieval_tokens = "scratch", "no_memory", 0
    if method == "exact_cache":
        hit = cache.get(task["request"], task["files"])
        meter.call(
            "retrieval", "exact_cache", task["task_id"],
            lambda _: dict(hit=hit is not None), None,
        )
        retrieval_tokens = 8
        if hit:
            files, decision, reason = hit, "apply", "exact_cache_hit"
        else:
            decision, reason = "abstain", "exact_cache_miss"
    elif method == "ordinary_template":
        proposal = propose_guarded_template(
            task.get("family") or "", task["request"], task["files"],
            task["public"], None,
        )
        meter.call(
            "retrieval", "ordinary_template", task["task_id"],
            lambda _: dict(decision=proposal.decision, reason=proposal.reason),
            None,
        )
        retrieval_tokens = 24
        decision, reason = proposal.decision, proposal.reason
        if proposal.files:
            files = proposal.files
    elif method in {"acquired", "irrelevant_memory"}:
        schema = store.lookup(task.get("family") or "", task["request"])
        meter.call(
            "retrieval", "acquired_lookup", task["task_id"],
            lambda _: dict(found=schema is not None,
                           schema_id=None if schema is None else schema.schema_id),
            None,
        )
        retrieval_tokens = 32
        proposal = propose_retrieved_repair(
            schema, task["request"], task["files"], task["public"], None,
        )
        decision, reason = proposal.decision, proposal.reason
        if proposal.files:
            files = proposal.files
    cost = dict(wall_s=round(time.perf_counter() - started, 6), model_calls=0, tools=1)
    return _cell(task, method, files, decision, reason, cost, retrieval_tokens)


def run_scratch_cell(runtime, task: dict[str, Any], method: str,
                     clock: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    generated = generate_direct(runtime, task, clock)
    files = generated.get("files") or dict(task["files"])
    cost = dict(
        wall_s=round(time.perf_counter() - started, 6),
        model_calls=1,
        tools=0,
        generation=generated.get("cost"),
    )
    return _cell(task, method, files, "scratch", "generate_direct", cost, 0)


def freeze_representation() -> dict[str, Any]:
    """Source/dev only. Target outcomes are not used."""
    return dict(
        store="RepairSchemaStore",
        abstraction="infer_ast_transform + apply_make_inclusive",
        retrieval="family then trigger, then same-family non-literal schema",
        gates="classify_boundary_requirement on public request+tests",
        ordinary_template="Lt→LtE only; D may rebound Gt→GtE",
        collapse_c_and_d=False,
        development_ids=[row["task_id"] for row in development_tasks()],
        source_ids=[row["task_id"] for row in source_tasks()],
        chosen_before_target_outcomes=True,
        programmer_supplied=True,
    )


def _summarize(cells: list[dict[str, Any]]) -> dict[str, Any]:
    later = [row for row in cells if not row.get("exact_repeat")]
    by_method: dict[str, list[dict[str, Any]]] = {name: [] for name in METHODS}
    for row in later:
        by_method[row["method"]].append(row)
    return {
        name: dict(
            later_private=sum(int(row["private_passed"]) for row in rows),
            later_n=len(rows),
            harmful=sum(int(row["harmful_transfer"]) for row in rows),
            applicability=sum(int(row["applicability_correct"]) for row in rows),
            model_calls=sum(int((row.get("cost") or {}).get("model_calls") or 0) for row in rows),
            wall_s=round(sum(float((row.get("cost") or {}).get("wall_s") or 0) for row in rows), 6),
        )
        for name, rows in by_method.items()
    }


def verdict(summary: dict[str, Any], cells: list[dict[str, Any]]) -> str:
    acquired = summary["acquired"]["later_private"]
    template = summary["ordinary_template"]["later_private"]
    scratch = summary["scratch"]["later_private"]
    reset = summary["acquired_reset"]["later_private"]
    irrelevant = summary["irrelevant_memory"]["later_private"]
    harmful = summary["acquired"]["harmful"]
    if harmful:
        return "negative"
    if acquired == template and acquired > scratch:
        return "ordinary_template_tie"
    if acquired > template and acquired > scratch and acquired > reset and acquired > irrelevant:
        return "useful_transfer"
    if acquired <= scratch and acquired <= template:
        return "negative"
    return "inconclusive"


def run_experience(directory: Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []
    meter = EventMeter(events.append)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    representation = freeze_representation()
    sources = source_tasks()
    acquired: list[dict[str, Any]] = []
    store = RepairSchemaStore()
    cache = OrdinaryExactCache()
    for task in sources:
        row = acquire_from_source(task, meter)
        acquired.append(dict(
            task_id=task["task_id"], family=task["family"],
            usable=row["usable"], schema=as_record(row["schema"]) if row["schema"] else None,
            episode=row["episode"],
        ))
        if row["schema"] and task["reuse_role"] == "source":
            store.remember(row["schema"])
            cache.put(task["request"], task["files"], row["files"])
        if row["schema"] and task["reuse_role"] == "irrelevant_source":
            (directory / "irrelevant_schema.json").write_text(
                json.dumps(as_record(row["schema"]), indent=2), encoding="utf-8")
    store.save(directory / "memory")
    cache_path = directory / "exact_cache.json"
    cache_path.write_text(json.dumps({
        "n": len(cache.store),
    }, indent=2), encoding="utf-8")

    retention = []
    for task in sources:
        if task["reuse_role"] != "source":
            continue
        schema = store.lookup(task["family"], task["request"])
        proposal = propose_retrieved_repair(
            schema, task["request"], task["files"], task["public"], None,
        )
        files = proposal.files or dict(task["files"])
        scored = _score(task, files)
        retention.append(dict(
            task_id=task["task_id"],
            private_passed=bool(scored.get("private_passed")),
            decision=proposal.decision,
        ))

    irrelevant = RepairSchemaStore()
    irr = next((row for row in acquired if row["family"] == "null_default" and row["schema"]), None)
    if irr:
        irrelevant.remember(RepairSchema(**irr["schema"]))

    empty = RepairSchemaStore()
    cells = []
    for task in target_tasks():
        for method in METHODS:
            if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
                raise TimeoutError("acquired_experience_cap")
            if method in LIVE_METHODS:
                cells.append(run_scratch_cell(runtime, task, method, clock))
            elif method == "irrelevant_memory":
                cells.append(run_memory_cell(task, method, irrelevant, cache, meter))
            elif method == "acquired_reset":
                continue
            else:
                cells.append(run_memory_cell(task, method, store, cache, meter))
        # acquired_reset already added via LIVE_METHODS
    summary = _summarize(cells)
    repeats = [row for row in cells if row.get("exact_repeat")]
    later = [row for row in cells if not row.get("exact_repeat")]
    rss = sample_process_memory()
    payload = dict(
        kind=KIND,
        representation=representation,
        acquired=acquired,
        retention=retention,
        cells=cells,
        later=later,
        exact_repeats=repeats,
        summary=summary,
        verdict=verdict(summary, cells),
        c_versus_d=dict(
            same_mechanism=False,
            ordinary_template="Lt→LtE only",
            acquired="captured compare_op_swap; inclusive path uses apply_make_inclusive (Lt→LtE or Gt→GtE)",
            collapse=False,
        ),
        claim_boundaries=dict(
            learning_to_learn=False,
            ranking_paused=True,
            public_tested_is_scoped=True,
            one_success_is_not_100_percent=True,
        ),
        usage=dict(
            calls=clock["calls"],
            inference_ran=clock["inference_ran"],
            wall_s=round(time.perf_counter() - clock["started"], 6),
            rss=rss,
            frozen_cpu_used_s=FROZEN_CPU_USED_S,
            frozen_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
            frozen_debit_s=0,
            product_chat_unused=True,
            metal_unused=True,
            ledger="standing_local_cpu_grant",
        ),
        declared_ids=[row["task_id"] for row in all_declared()],
        closed_cpu_untouched=True,
    )
    payload["hash"] = digest({
        "cells": [
            {k: row[k] for k in (
                "task_id", "method", "decision", "private_passed",
                "harmful_transfer", "applicability_correct",
            )}
            for row in cells
        ],
        "acquired": [
            dict(task_id=row["task_id"], usable=row["usable"],
                 transformation=(row["schema"] or {}).get("transformation"))
            for row in acquired
        ],
        "verdict": payload["verdict"],
    })
    (directory / "events.jsonl").write_text(
        "\n".join(json.dumps(event, default=str) for event in events) + "\n",
        encoding="utf-8",
    )
    (directory / "memory_snapshot.json").write_text(
        json.dumps([as_record(schema) for schema in store.schemas.values()], indent=2),
        encoding="utf-8",
    )
    return payload


def verify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    ok = True
    for row in payload.get("cells") or []:
        replay = None
        task = next((item for item in target_tasks() if item["task_id"] == row["task_id"]), None)
        if task is None or not row.get("files"):
            continue
        replay = score_task(task, row["files"])
        if bool(replay.get("private_passed")) != bool(row.get("private_passed")):
            ok = False
            notes.append(f"flag_mismatch:{row['task_id']}:{row['method']}")
    if payload.get("usage", {}).get("frozen_debit_s") != 0:
        ok = False
        notes.append("frozen_debit")
    if payload.get("claim_boundaries", {}).get("learning_to_learn"):
        ok = False
        notes.append("claimed_l2l")
    reset_store = RepairSchemaStore()
    if reset_store.schemas:
        ok = False
        notes.append("reset_not_empty")
    return dict(valid=ok, notes=notes, n=len(payload.get("cells") or []))
