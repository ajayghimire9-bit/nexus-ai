"""Apply-mode API-ID versus equally informed direct.

Scores: structural validity, type validity, correct bindings, final behavior.
Opened named and positional cells are not rescored. Ranking stays paused.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .api_id_bindings import (
    apply_binding_schema, apply_generation_schema, apply_selection_prompt,
    assemble_apply_proposal, interface_brief, parse_apply_selection,
    score_apply_tracks,
)
from .api_apply_tasks import all_declared, apply_api_tasks
from .capability_evidence import digest
from .capability_map import score_coding
from .chat_template import render_prompt
from .extraction_api_wiring import complete_with_schema, contract_ids
from .extraction_path import generate_direct
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

WALL_CAP_S = 900.0
CALL_CAP = 80
KIND = "seed_api_apply_modes"
CALLS_PER_CELL = 1
APPLY_RULES = (
    "apply=direct: no list iteration. "
    "apply=whole_list: pass a list field to a list parameter. "
    "apply=element: bind a scalar parameter to elem.LIST and iterate. "
    "Omit optional parameters to keep documented defaults. "
    "If two type-compatible fields fit and the request does not say which, ask."
)


def caller_path(task: dict[str, Any]) -> str:
    symbol = task["contract"]["symbol"]
    for case in task["public"]:
        entry = str(case.get("entry") or "")
        if entry.endswith("." + symbol):
            return entry.split(".", 1)[0] + ".py"
    return "work.py"


def with_shared_interface(task: dict[str, Any]) -> dict[str, Any]:
    brief = APPLY_RULES + "\n" + interface_brief(task, task["files"])
    return dict(task, request=task["request"].rstrip() + "\n" + brief)


def run_direct_cell(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    shared = with_shared_interface(task)
    cell = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    result = generate_direct(runtime, shared, cell)
    clock["calls"] += cell["calls"]
    clock["inference_ran"] += cell.get("inference_ran") or 0
    files = result.get("files") or dict(task["files"])
    scored = score_coding(task, files)
    asked = "?" in (result.get("raw") or "") and task.get("role") == "ambiguous_ask"
    return dict(
        structural_ok=None,
        type_valid=None,
        bindings_correct=None,
        task_satisfied=bool(asked if task.get("gold_selection", {}).get("ask") else scored.get("private_passed")),
        asked=asked,
        public_passed=scored.get("public_passed"),
        private_passed=scored.get("private_passed"),
        files=files,
        raw=(result.get("raw") or "")[:400],
        route="direct",
        same_interface=True,
        same_call_budget=CALLS_PER_CELL,
        model_calls=cell["calls"],
        selection_not_generally_solved=True,
    )


def run_named_cell(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    shared = with_shared_interface(task)
    ids = contract_ids(shared, shared["files"])
    schema = apply_binding_schema(ids)
    user = apply_selection_prompt(shared, shared["files"])
    prompt, _meta = render_prompt("chatml", user)
    raw = complete_with_schema(runtime, prompt, apply_generation_schema(ids))
    clock["calls"] += 1
    clock["inference_ran"] += int(raw["inference_ran"])
    proposal = parse_apply_selection(raw["content"])
    applied = assemble_apply_proposal(task, proposal, caller_path(task))
    coded = score_coding(task, applied["files"])
    tracks = score_apply_tracks(
        proposal, task["gold_selection"], applied["assembled"], schema, ids,
        bool(coded.get("private_passed")),
    )
    return dict(
        **tracks,
        public_passed=coded.get("public_passed"),
        private_passed=coded.get("private_passed"),
        files=applied["files"],
        proposal=proposal,
        assembled=applied["assembled"],
        raw=(raw.get("content") or "")[:400],
        route="named_id",
        same_interface=True,
        same_call_budget=CALLS_PER_CELL,
        model_calls=1,
    )


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        method = row["method"]
        cell = out.setdefault(method, dict(
            n=0, structural_ok=0, type_valid=0, bindings_correct=0,
            task_satisfied=0, model_calls=0,
        ))
        scored = row.get("scored") or {}
        cell["n"] += 1
        cell["structural_ok"] += int(bool(scored.get("structural_ok")))
        cell["type_valid"] += int(bool(scored.get("type_valid")))
        cell["bindings_correct"] += int(bool(scored.get("bindings_correct")))
        cell["task_satisfied"] += int(bool(scored.get("task_satisfied")))
        cell["model_calls"] += int(scored.get("model_calls") or 0)
    by_role: dict[str, dict[str, int]] = {}
    for row in rows:
        if row["method"] != "named_id":
            continue
        role = row.get("role") or ""
        cell = by_role.setdefault(role, dict(n=0, structural_ok=0, type_valid=0,
                                             bindings_correct=0, task_satisfied=0))
        scored = row.get("scored") or {}
        cell["n"] += 1
        cell["structural_ok"] += int(bool(scored.get("structural_ok")))
        cell["type_valid"] += int(bool(scored.get("type_valid")))
        cell["bindings_correct"] += int(bool(scored.get("bindings_correct")))
        cell["task_satisfied"] += int(bool(scored.get("task_satisfied")))
    return dict(methods=out, roles=by_role)


def run_api_apply(directory: Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    rows = []
    partial = False
    for task in apply_api_tasks():
        for method, runner in (("direct", run_direct_cell), ("named_id", run_named_cell)):
            if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
                partial = True
                break
            scored = runner(runtime, task, clock)
            rows.append(dict(
                task_id=task["task_id"], role=task["role"], method=method,
                scored=scored, live=True,
            ))
            (directory / "seed_api_apply_modes_partial.json").write_text(
                json.dumps(dict(rows=rows, partial=True), default=str), encoding="utf-8")
        if partial:
            break
    usage = dict(
        calls=clock["calls"],
        inference_ran=clock["inference_ran"],
        wall_s=round(time.perf_counter() - clock["started"], 6),
        rss=sample_process_memory(),
        frozen_cpu_used_s=FROZEN_CPU_USED_S,
        frozen_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
        frozen_debit_s=0,
        product_chat_unused=True,
        metal_unused=True,
        ledger="standing_local_cpu_grant",
        partial=partial,
        calls_per_cell=CALLS_PER_CELL,
    )
    payload = dict(
        kind=KIND,
        confirmation=False,
        learning_to_learn_established=False,
        ranking_paused=True,
        broader_learning_paused=True,
        selection_not_generally_solved=True,
        opened_prior_not_rescored=True,
        declared_ids=[row["task_id"] for row in all_declared()],
        rows=rows,
        summary=summarize(rows),
        usage=usage,
        claim_boundaries=dict(
            learning_to_learn=False,
            apply_mode_is_programmer_supplied=True,
        ),
    )
    payload["hash"] = digest({
        "rows": [
            dict(task_id=row["task_id"], method=row["method"],
                 structural_ok=(row.get("scored") or {}).get("structural_ok"),
                 type_valid=(row.get("scored") or {}).get("type_valid"),
                 bindings_correct=(row.get("scored") or {}).get("bindings_correct"),
                 task_satisfied=(row.get("scored") or {}).get("task_satisfied"))
            for row in rows
        ],
    })
    return payload


def verify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from .recovery_actions import run_cases
    notes = []
    ok = True
    tasks = {row["task_id"]: row for row in apply_api_tasks()}
    for row in payload.get("rows") or []:
        task = tasks.get(row["task_id"])
        files = (row.get("scored") or {}).get("files")
        if task is None or not files:
            continue
        if task.get("gold_selection", {}).get("ask"):
            continue
        replay = run_cases(files, task["private"])
        saved = bool((row.get("scored") or {}).get("private_passed"))
        if (replay.get("status") == "passed") != saved:
            ok = False
            notes.append(f"flag_mismatch:{row['task_id']}:{row['method']}")
    if payload.get("usage", {}).get("frozen_debit_s") != 0:
        ok = False
        notes.append("frozen_debit")
    if payload.get("learning_to_learn_established"):
        ok = False
        notes.append("claimed_l2l")
    return dict(valid=ok, notes=notes, n=len(payload.get("rows") or []))
