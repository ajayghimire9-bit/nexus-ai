"""Route study: provenance, selective math, API-ID assembly, staged pairs.

Does not rescore the capability map or the previous follow-up. API
selection, bindings and assembled execution stay separate scores.
Selection is not treated as generally solved. Frozen debit 0.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .capability_evidence import EventMeter, digest
from .capability_map import complete_text, start_map_runtime
from .capability_routes_tasks import (
    api_id_tasks, coordinated_tasks, knowledge_tasks, mathematics_tasks,
    provenance_corpus,
)
from .coordinated_stage import stage_pair
from .chat_template import render_prompt
from .api_id_bindings import apply_validated_proposal, score_binding_tracks
from .extraction_api_wiring import (
    complete_with_schema, contract_ids, parse_id_selection,
    selection_id_schema, selection_prompt,
)
from .extraction_path import generate_direct
from .function_contracts import score_bound_task
from .knowledge_provenance import (
    provenance_resolve, render_resolution, score_knowledge_resolution, timestamp_sort,
)
from .math_interpretation import (
    compile_statement, extract_expression, parse_statement, score_direct_calculator,
    score_interpreted,
)
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

WALL_CAP_S = 900.0
CALL_CAP = 80
CONFIG_PATH = Path("configs/seed_capability_routes.json")


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def caller_path(task: dict[str, Any]) -> str:
    symbol = task["contract"]["symbol"]
    for case in task["public"]:
        entry = str(case.get("entry") or "")
        if entry.endswith("." + symbol):
            return entry.split(".", 1)[0] + ".py"
    return "work.py"


def apply_id_proposal(task: dict[str, Any], proposal: dict[str, Any] | None) -> dict[str, Any]:
    return apply_validated_proposal(task, proposal, caller_path(task))


def score_id_cell(task: dict[str, Any], proposal: dict[str, Any] | None,
                  files: dict[str, str], assembled: dict[str, Any]) -> dict[str, Any]:
    gold = task["gold_selection"]
    tracks = score_binding_tracks(proposal, gold, assembled)
    scored = score_bound_task(task, files) if task.get("function_contracts") else None
    if scored is None:
        from .capability_map import score_coding
        scored = score_coding(task, files)
    return dict(
        **tracks,
        assembled_ok=tracks["assembly_valid"],
        public_passed=scored.get("public_passed"),
        private_passed=scored.get("private_passed"),
        required_call=scored.get("required_call"),
        passed=bool(scored.get("private_passed") and tracks["assembly_valid"]),
        files=files,
        proposal=proposal,
        assembled=assembled,
    )


def run_knowledge_track() -> list[dict[str, Any]]:
    rows = provenance_corpus()
    out = []
    for task in knowledge_tasks():
        for method, resolved in (
            ("timestamp_sort", timestamp_sort(rows, task["subject"])),
            ("provenance", provenance_resolve(rows, task["subject"])),
        ):
            text = render_resolution(rows, resolved)
            scored = score_knowledge_resolution(task, resolved, text)
            out.append(dict(
                task_id=task["task_id"], track="knowledge", family=task["family"],
                method=method, scored=scored, live=False,
            ))
    return out


def run_math_cell(runtime, task: dict[str, Any], method: str, clock: dict[str, Any]) -> dict[str, Any]:
    use_interpret = method == "routed" and task.get("route") == "interpret"
    if not use_interpret:
        raw = complete_text(
            runtime,
            task["request"] + '\nReturn JSON {"expression": "...", "unit": "...", "clarification": "..."}.',
            clock,
        )
        scored = score_direct_calculator(task, raw["content"], extract_expression(raw["content"]))
        scored["raw"] = raw["content"]
        scored["route"] = "calculator"
        return scored
    raw = complete_text(
        runtime,
        task["request"] + (
            "\nReturn JSON with quantities, relationships, unknown, unit, missing "
            "and expression. Include unknown only if the problem names a variable. "
            "Leave expression empty and list missing names when underspecified."
        ),
        clock,
    )
    statement = parse_statement(raw["content"])
    compiled = compile_statement(statement, task) if statement else None
    scored = score_interpreted(task, statement, compiled, raw["content"])
    scored["raw"] = raw["content"]
    scored["route"] = "interpret"
    return scored


def run_api_cell(runtime, task: dict[str, Any], method: str, clock: dict[str, Any]) -> dict[str, Any]:
    cell = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    if method == "direct":
        result = generate_direct(runtime, dict(task), cell)
        files = result.get("files") or task["files"]
        clock["calls"] += cell["calls"]
        clock["inference_ran"] += cell.get("inference_ran") or 0
        from .capability_map import score_coding
        scored = score_coding(task, files)
        scored["selection_correct"] = None
        scored["bindings_correct"] = None
        scored["assembled_ok"] = False
        scored["route"] = "direct"
        scored["selection_not_generally_solved"] = True
        return scored
    files = dict(task["files"])
    ids = contract_ids(task, files)
    user = selection_prompt(task, files)
    prompt, _meta = render_prompt("chatml", user)
    raw = complete_with_schema(runtime, prompt, selection_id_schema(ids))
    cell["calls"] += 1
    cell["inference_ran"] += int(raw["inference_ran"])
    clock["calls"] += cell["calls"]
    clock["inference_ran"] += cell["inference_ran"]
    proposal = parse_id_selection(raw["content"])
    applied = apply_id_proposal(task, proposal)
    scored = score_id_cell(task, proposal, applied["files"], applied["assembled"])
    scored["route"] = "id_select_assemble"
    scored["raw"] = raw["content"][:400]
    scored["learned_schema_discovery"] = False
    return scored


def run_coord_cell(runtime, task: dict[str, Any], method: str, clock: dict[str, Any]) -> dict[str, Any]:
    cell = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    if method == "direct":
        result = generate_direct(runtime, dict(task), cell)
        files = result.get("files") or task["files"]
        clock["calls"] += cell["calls"]
        clock["inference_ran"] += cell.get("inference_ran") or 0
        from .capability_map import score_coding
        scored = score_coding(task, files)
        scored["published"] = False
        scored["route"] = "direct"
        return scored
    staged = stage_pair(runtime, task, cell)
    clock["calls"] += cell["calls"]
    clock["inference_ran"] += cell.get("inference_ran") or 0
    return staged


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        track = row["track"]
        method = row["method"]
        cell = out.setdefault(track, {}).setdefault(method, dict(n=0, passed=0))
        cell["n"] += 1
        cell["passed"] += int(bool((row.get("scored") or {}).get("passed")))
        scored = row.get("scored") or {}
        if track == "coding_api" and method == "id_select_assemble":
            extras = cell.setdefault("separate", dict(selection=0, bindings=0, assembled=0, execution=0))
            extras["selection"] += int(bool(scored.get("selection_correct")))
            extras["bindings"] += int(bool(scored.get("bindings_correct")))
            extras["assembled"] += int(bool(scored.get("assembled_ok")))
            extras["execution"] += int(bool(scored.get("private_passed")))
        if track == "mathematics":
            split = cell.setdefault("separate", dict(interpretation=0, execution=0, answer=0))
            split["interpretation"] += int(bool(scored.get("interpretation_ok")))
            split["execution"] += int(bool(scored.get("execution_ok")))
            split["answer"] += int(bool(scored.get("answer_ok")))
    return out


def run_routes(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    config = load_config()
    raw_path = directory / "seed_capability_routes_raw.jsonl"
    if raw_path.exists():
        raw_path.unlink()
    events: list[dict[str, Any]] = []
    meter = EventMeter(lambda event: events.append(event) or raw_path.open("a", encoding="utf-8").write(
        json.dumps(event, default=str) + "\n"
    ))
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    rows = run_knowledge_track()
    live_plan = []
    for task in mathematics_tasks():
        for method in ("calculator_direct", "routed"):
            live_plan.append((task, method, run_math_cell))
    for task in api_id_tasks():
        for method in ("direct", "id_select_assemble"):
            live_plan.append((task, method, run_api_cell))
    for task in coordinated_tasks():
        for method in ("direct", "staged_pair"):
            live_plan.append((task, method, run_coord_cell))
    partial = False
    for task, method, runner in live_plan:
        if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
            partial = True
            break
        cell = meter.call(
            f"{task['task_id']}:{method}", "routes_cell", task["task_id"],
            lambda _, t=task, m=method, r=runner: dict(
                task_id=t["task_id"], track=t["track"], family=t.get("family"),
                method=m, scored=r(runtime, t, m, clock), live=True,
            ),
            dict(task_id=task["task_id"], method=method),
        )
        if isinstance(cell, dict) and cell.get("task_id"):
            rows.append(cell)
            (directory / "seed_capability_routes_partial.json").write_text(
                json.dumps(dict(rows=rows, partial=True), default=str), encoding="utf-8")
    usage = dict(
        kind="capability_routes_cpu_usage",
        backend="cpu",
        gpu_used=False,
        metal_used=False,
        product_chat_usage_used=False,
        research_cpu_ledger_frozen_s=FROZEN_CPU_USED_S,
        research_cpu_ledger_remaining_s=FROZEN_CPU_REMAINING_S,
        research_cpu_ledger_debit_s=0.0,
        model_calls=clock["calls"],
        inference_ran=clock["inference_ran"],
        wall_s=round(time.perf_counter() - clock["started"], 3),
        cap_s=WALL_CAP_S,
        call_cap=CALL_CAP,
        memory=sample_process_memory(runtime) if runtime is not None else None,
        acquired_solution_memory=False,
        ranking_policy_resumed=False,
        learning_to_learn_established=False,
        original_map_rescored=False,
        followup_rescored=False,
        api_selection_generally_solved=False,
        partial=partial,
    )
    payload = dict(
        kind="seed_capability_routes",
        confirmation=False,
        aggregate_score=False,
        learning_to_learn_established=False,
        api_selection_generally_solved=False,
        config=config,
        rows=rows,
        summary=summarize(rows),
        usage=usage,
        events=len(events),
        api_audit_preserved=True,
    )
    payload["hash"] = digest({k: payload[k] for k in ("kind", "summary", "usage")})
    (directory / "recovery_live_usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return payload
