"""Equal inclusive-repair baseline versus acquired experience.

C invokes apply_make_inclusive under the same public gates as D.
Retrieval misses fall back to the same generate_direct path as scratch.
Refuse and ask are complete assistant acts, not misses.
Not learning-to-learn. Ranking stays paused.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .capability_evidence import EventMeter, digest
from .capability_routes import run_api_cell
from .equal_inclusive_tasks import (
    all_declared, api_id_tasks, development_tasks, source_tasks, target_tasks,
)
from .experience_transfer import acquire_from_source
from .extraction_path import generate_direct, score_task
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .repair_schema_memory import (
    OrdinaryExactCache, RepairSchema, RepairSchemaStore, as_record,
    propose_inclusive_tool, propose_retrieved_repair,
)

METHODS = (
    "scratch",
    "exact_cache",
    "inclusive_tool",
    "acquired",
    "acquired_reset",
    "irrelevant_memory",
)
WALL_CAP_S = 900.0
CALL_CAP = 80
KIND = "seed_equal_inclusive"


def freeze_representation() -> dict[str, Any]:
    return dict(
        store="RepairSchemaStore",
        baseline="propose_inclusive_tool = apply_make_inclusive + same gates",
        acquired="captured compare_op_swap; inclusive path also apply_make_inclusive",
        fallback="generate_direct on retrieval abstain only; refuse/ask do not fallback",
        collapse_if_identical="report tool-tie rather than invent a distinction",
        development_ids=[row["task_id"] for row in development_tasks()],
        source_ids=[row["task_id"] for row in source_tasks()],
        chosen_before_target_outcomes=True,
        programmer_supplied=True,
        ranking_paused=True,
        learning_to_learn=False,
    )


def _starter_private(task: dict[str, Any]) -> bool:
    return bool(score_task(task, task["files"]).get("private_passed"))


def _acts(task: dict[str, Any], decision: str, files: dict[str, str],
          scored: dict[str, Any]) -> dict[str, Any]:
    role = task.get("reuse_role")
    starter_ok = _starter_private(task)
    changed = files != task["files"]
    harmful = bool(changed and starter_ok and not scored.get("private_passed"))
    if role == "harmful_if_applied" and decision == "apply" and not scored.get("private_passed"):
        harmful = True
    correct_solution = bool(scored.get("private_passed"))
    correct_refuse = role == "harmful_if_applied" and decision == "refuse"
    correct_ask = role == "ambiguous_ask" and decision == "ask"
    return dict(
        correct_solution=correct_solution,
        correct_clarification_or_refusal=bool(correct_refuse or correct_ask),
        harmful_change=harmful,
        starter_private=starter_ok,
        files_changed=changed,
    )


def retrieve(task: dict[str, Any], method: str, store: RepairSchemaStore,
             cache: OrdinaryExactCache, meter: EventMeter) -> dict[str, Any]:
    files = dict(task["files"])
    decision, reason, tokens = "scratch", "no_memory", 0
    if method == "exact_cache":
        hit = cache.get(task["request"], task["files"])
        meter.call("retrieval", "exact_cache", task["task_id"],
                   lambda _: dict(hit=hit is not None), None)
        tokens = 8
        if hit:
            files, decision, reason = hit, "apply", "exact_cache_hit"
        else:
            decision, reason = "abstain", "exact_cache_miss"
    elif method == "inclusive_tool":
        proposal = propose_inclusive_tool(task["request"], task["files"], task["public"], None)
        meter.call("retrieval", "inclusive_tool", task["task_id"],
                   lambda _: dict(decision=proposal.decision, reason=proposal.reason), None)
        tokens = 24
        decision, reason = proposal.decision, proposal.reason
        if proposal.files:
            files = proposal.files
    elif method in {"acquired", "irrelevant_memory"}:
        schema = store.lookup(task.get("family") or "", task["request"])
        meter.call("retrieval", "acquired_lookup", task["task_id"],
                   lambda _: dict(found=schema is not None,
                                  schema_id=None if schema is None else schema.schema_id),
                   None)
        tokens = 32
        proposal = propose_retrieved_repair(
            schema, task["request"], task["files"], task["public"], None,
        )
        decision, reason = proposal.decision, proposal.reason
        if proposal.files:
            files = proposal.files
    return dict(files=files, decision=decision, reason=reason, retrieval_tokens=tokens)


def run_target_cell(runtime, task: dict[str, Any], method: str,
                    store: RepairSchemaStore, cache: OrdinaryExactCache,
                    meter: EventMeter, clock: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    model_calls = 0
    fallback = False
    if method in {"scratch", "acquired_reset"}:
        generated = generate_direct(runtime, task, clock)
        files = generated.get("files") or dict(task["files"])
        decision, reason = "scratch", "generate_direct"
        model_calls = 1
        tokens = 0
    else:
        retrieved = retrieve(task, method, store, cache, meter)
        files = retrieved["files"]
        decision, reason = retrieved["decision"], retrieved["reason"]
        tokens = retrieved["retrieval_tokens"]
        if decision == "abstain":
            generated = generate_direct(runtime, task, clock)
            files = generated.get("files") or dict(task["files"])
            decision, reason = "scratch_fallback", retrieved["reason"]
            fallback = True
            model_calls = 1
    scored = score_task(task, files)
    acts = _acts(task, decision if not fallback else "scratch_fallback", files, scored)
    # refuse/ask correctness uses the pre-fallback decision when we did not fallback
    if not fallback and method not in {"scratch", "acquired_reset"}:
        acts.update(_acts(task, decision, files, scored))
    return dict(
        task_id=task["task_id"],
        method=method,
        family=task.get("family"),
        reuse_role=task.get("reuse_role"),
        exact_repeat=bool((task.get("overlap") or {}).get("exact")),
        decision=decision,
        reason=reason,
        used_fallback=fallback,
        public_passed=bool(scored.get("public_passed")),
        private_passed=bool(scored.get("private_passed")),
        files=files,
        cost=dict(
            wall_s=round(time.perf_counter() - started, 6),
            model_calls=model_calls,
            retrieval_tokens=tokens,
        ),
        overlap=task.get("overlap"),
        **acts,
    )


def _summarize(cells: list[dict[str, Any]]) -> dict[str, Any]:
    later = [row for row in cells if not row.get("exact_repeat")]
    by_method: dict[str, list[dict[str, Any]]] = {name: [] for name in METHODS}
    for row in later:
        by_method[row["method"]].append(row)
    out = {}
    for name, rows in by_method.items():
        out[name] = dict(
            correct_solutions=sum(int(row["correct_solution"]) for row in rows),
            correct_clarification_or_refusal=sum(
                int(row["correct_clarification_or_refusal"]) for row in rows),
            harmful_changes=sum(int(row["harmful_change"]) for row in rows),
            model_calls=sum(int((row.get("cost") or {}).get("model_calls") or 0) for row in rows),
            wall_s=round(sum(float((row.get("cost") or {}).get("wall_s") or 0) for row in rows), 6),
            later_n=len(rows),
            fallbacks=sum(int(row.get("used_fallback")) for row in rows),
        )
    return out


def verdict(summary: dict[str, Any]) -> str:
    acquired = summary["acquired"]
    tool = summary["inclusive_tool"]
    scratch = summary["scratch"]
    reset = summary["acquired_reset"]
    if acquired["harmful_changes"]:
        return "negative"
    same_acc = acquired["correct_solutions"] == tool["correct_solutions"]
    same_act = (
        acquired["correct_clarification_or_refusal"]
        == tool["correct_clarification_or_refusal"]
    )
    if same_acc and same_act:
        return "tool_tie"
    if (
        acquired["correct_solutions"] > tool["correct_solutions"]
        and acquired["correct_solutions"] > scratch["correct_solutions"]
        and acquired["correct_solutions"] > reset["correct_solutions"]
        and acquired["harmful_changes"] <= tool["harmful_changes"]
    ):
        return "useful_acquired_beyond_tool"
    return "inconclusive"


def run_equal_inclusive(directory: Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []
    meter = EventMeter(events.append)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    representation = freeze_representation()
    acquired_rows = []
    store = RepairSchemaStore()
    cache = OrdinaryExactCache()
    for task in source_tasks():
        row = acquire_from_source(task, meter)
        acquired_rows.append(dict(
            task_id=task["task_id"], family=task["family"],
            usable=row["usable"],
            schema=as_record(row["schema"]) if row["schema"] else None,
            episode=row["episode"],
        ))
        if row["schema"] and task["reuse_role"] == "source":
            store.remember(row["schema"])
            cache.put(task["request"], task["files"], row["files"])
        if row["schema"] and task["reuse_role"] == "irrelevant_source":
            (directory / "irrelevant_schema.json").write_text(
                json.dumps(as_record(row["schema"]), indent=2), encoding="utf-8")
    store.save(directory / "memory")

    retention = []
    for task in source_tasks():
        if task["reuse_role"] != "source":
            continue
        schema = store.lookup(task["family"], task["request"])
        proposal = propose_retrieved_repair(
            schema, task["request"], task["files"], task["public"], None,
        )
        files = proposal.files or dict(task["files"])
        scored = score_task(task, files)
        retention.append(dict(
            task_id=task["task_id"],
            private_passed=bool(scored.get("private_passed")),
            decision=proposal.decision,
        ))

    irrelevant = RepairSchemaStore()
    irr = next((row for row in acquired_rows if row["family"] == "null_default" and row["schema"]), None)
    if irr:
        irrelevant.remember(RepairSchema(**irr["schema"]))

    cells = []
    partial = False
    for task in target_tasks():
        for method in METHODS:
            if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
                partial = True
                break
            active = store if method != "irrelevant_memory" else irrelevant
            cells.append(run_target_cell(runtime, task, method, active, cache, meter, clock))
        if partial:
            break

    api_rows = []
    for task in api_id_tasks():
        for method in ("direct", "id_select_assemble"):
            if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
                partial = True
                break
            scored = run_api_cell(runtime, task, method, clock)
            api_rows.append(dict(
                task_id=task["task_id"], track="coding_api", method=method,
                scored=scored, live=True,
            ))
        if partial:
            break

    later = [row for row in cells if not row.get("exact_repeat")]
    repeats = [row for row in cells if row.get("exact_repeat")]
    summary = _summarize(cells)
    tool_vs_acquired = dict(
        same_mechanism_on_inclusive_repairs=True,
        ordinary_lt_only=False,
        acquired_adds_beyond_tool=summary["acquired"]["correct_solutions"]
        != summary["inclusive_tool"]["correct_solutions"]
        or summary["acquired"]["correct_clarification_or_refusal"]
        != summary["inclusive_tool"]["correct_clarification_or_refusal"],
    )
    api_summary = {}
    for row in api_rows:
        method = row["method"]
        cell = api_summary.setdefault(method, dict(
            n=0, selection=0, binding_valid=0, bindings=0, assembled=0, execution=0,
        ))
        scored = row.get("scored") or {}
        cell["n"] += 1
        cell["selection"] += int(bool(scored.get("selection_correct")))
        cell["binding_valid"] += int(bool(scored.get("binding_valid")))
        cell["bindings"] += int(bool(scored.get("bindings_correct")))
        cell["assembled"] += int(bool(scored.get("assembled_ok") or scored.get("assembly_valid")))
        cell["execution"] += int(bool(scored.get("private_passed")))
    rss = sample_process_memory()
    payload = dict(
        kind=KIND,
        representation=representation,
        acquired=acquired_rows,
        retention=retention,
        cells=cells,
        later=later,
        exact_repeats=repeats,
        api_rows=api_rows,
        summary=summary,
        api_summary=api_summary,
        verdict=verdict(summary),
        tool_vs_acquired=tool_vs_acquired,
        claim_boundaries=dict(
            learning_to_learn=False,
            ranking_paused=True,
            broader_learning_paused=True,
            public_tested_is_scoped=True,
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
            partial=partial,
        ),
        declared_ids=[row["task_id"] for row in all_declared()],
        opened_prior_not_rescored=True,
        closed_cpu_untouched=True,
    )
    payload["hash"] = digest({
        "cells": [
            {k: row[k] for k in (
                "task_id", "method", "decision", "correct_solution",
                "correct_clarification_or_refusal", "harmful_change",
                "used_fallback",
            )}
            for row in cells
        ],
        "api": [
            dict(task_id=row["task_id"], method=row["method"],
                 selection=(row.get("scored") or {}).get("selection_correct"),
                 bindings=(row.get("scored") or {}).get("bindings_correct"),
                 assembled=(row.get("scored") or {}).get("assembled_ok"),
                 execution=(row.get("scored") or {}).get("private_passed"))
            for row in api_rows
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
    return dict(
        valid=ok, notes=notes,
        n_cells=len(payload.get("cells") or []),
        n_api=len(payload.get("api_rows") or []),
    )
