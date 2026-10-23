"""Four-track capability follow-up. Not a rescore of the 90-cell map.

Knowledge provenance is offline. Conversation review is offline on the
frozen map. Mathematics and the split coding tracks may use the same
1.5B CPU runtime. Frozen ledger debit stays 0. Ranking stays paused.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .capability_evidence import EventMeter, digest
from .capability_followup_tasks import (
    all_live_tasks, api_tasks, clarify_cases, coordinated_tasks,
    knowledge_tasks, mathematics_tasks, provenance_corpus,
)
from .capability_map import complete_text, score_coding, start_map_runtime
from .conversation_review import (
    agent_review_packet, load_frozen_conversation, score_clarify_case,
    summarize_review,
)
from .knowledge_provenance import (
    dump_all, provenance_resolve, render_resolution, score_knowledge_resolution,
    timestamp_sort,
)
from .math_interpretation import (
    compile_statement, extract_expression, parse_statement, score_direct_calculator,
    score_interpreted,
)
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .unresolved_referent import unresolved_referent

WALL_CAP_S = 900.0
CALL_CAP = 80
CONFIG_PATH = Path("configs/seed_capability_followup.json")
FROZEN_MAP = Path("artifacts/seed_capability_map/seed_capability_map.json")
KNOWLEDGE_METHODS = ("dump_all", "timestamp_sort", "provenance")
MATH_METHODS = ("calculator_direct", "interpret_compile")
CODING_METHODS = ("direct", "nexus")


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def run_knowledge_track() -> list[dict[str, Any]]:
    rows = provenance_corpus()
    out = []
    for task in knowledge_tasks():
        resolutions = {
            "dump_all": dump_all(rows),
            "timestamp_sort": timestamp_sort(rows, task["subject"]),
            "provenance": provenance_resolve(rows, task["subject"]),
        }
        for method, resolved in resolutions.items():
            text = render_resolution(rows, resolved)
            if task.get("must_conflict") and resolved.get("conflict"):
                text = "conflict: " + text
            scored = score_knowledge_resolution(task, resolved, text)
            out.append(dict(
                task_id=task["task_id"], track="knowledge", family=task["family"],
                method=method, scored=scored, live=False,
            ))
    return out


def run_conversation_track() -> dict[str, Any]:
    packet = []
    if FROZEN_MAP.is_file():
        packet = agent_review_packet(load_frozen_conversation(FROZEN_MAP))
    clarify = []
    for case in clarify_cases():
        scored = score_clarify_case(case["text"], case.get("history"))
        expected_ask = bool(case["must_ask"])
        scored["passed"] = bool(scored["detector"]["needed"]) == expected_ask
        if expected_ask:
            scored["passed"] = bool(scored["clarification"] and not scored.get("booked"))
        clarify.append(dict(
            task_id=case["task_id"], track="conversation_clarify",
            method="unresolved_referent", scored=scored, live=False,
        ))
    frozen_clarify = None
    if FROZEN_MAP.is_file():
        payload = json.loads(FROZEN_MAP.read_text(encoding="utf-8"))
        for row in payload.get("rows") or []:
            if row.get("task_id") == "conv_clarify":
                reply = ((row.get("scored") or {}).get("replies") or [""])[0]
                frozen_clarify = dict(
                    task_id="conv_clarify_frozen",
                    track="conversation_clarify",
                    method="model_alone_frozen",
                    scored=dict(
                        passed=False,
                        clarification="?" in reply,
                        booking_keyword_sufficient=False,
                        reply=reply,
                        detector=unresolved_referent("Book the later one.", []),
                    ),
                    live=False,
                )
                break
    if frozen_clarify:
        clarify.append(frozen_clarify)
    return dict(review=packet, review_summary=summarize_review(packet), clarify=clarify)


def run_math_cell(runtime, task: dict[str, Any], method: str, clock: dict[str, Any]) -> dict[str, Any]:
    if method == "calculator_direct":
        raw = complete_text(
            runtime,
            task["request"] + '\nReturn JSON {"expression": "...", "unit": "...", "clarification": "..."}.',
            clock,
        )
        expr = extract_expression(raw["content"])
        scored = score_direct_calculator(task, raw["content"], expr)
        scored["raw"] = raw["content"]
        scored["route"] = "calculator_direct"
        return scored
    raw = complete_text(
        runtime,
        task["request"] + (
            "\nReturn JSON with quantities (name, value, unit), relationships, "
            "unknown, unit, missing, and expression. Put missing names in missing "
            "and leave expression empty when the problem is underspecified. "
            "The expression may use only stated quantities."
        ),
        clock,
    )
    statement = parse_statement(raw["content"])
    compiled = compile_statement(statement, task) if statement else None
    scored = score_interpreted(task, statement, compiled, raw["content"])
    scored["raw"] = raw["content"]
    scored["route"] = "interpret_compile"
    return scored


def run_coding_cell(runtime, task: dict[str, Any], method: str, clock: dict[str, Any]) -> dict[str, Any]:
    from .extraction_path import generate_direct
    from .extraction_workspace import decide_workspace_extraction, run_workspace_extraction

    cell = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    working = dict(task)
    if method == "direct":
        result = generate_direct(runtime, working, cell)
        files = result.get("files") or task["files"]
        route = "direct"
    else:
        decision = decide_workspace_extraction(
            task["request"], task["files"], task["public"], task.get("docs"), "python",
        )
        if decision.get("action") == "extract":
            payload = run_workspace_extraction(
                runtime, task["request"], task["files"], task["public"], task.get("docs"), decision,
            )
            files = payload.get("files") or task["files"]
            route = "eligible_always_extract"
            cell["calls"] = payload.get("cost", {}).get("model_calls") or 1
        else:
            result = generate_direct(runtime, working, cell)
            files = result.get("files") or task["files"]
            route = "direct_fallback:" + str(decision.get("reason"))
    clock["calls"] += cell["calls"]
    clock["inference_ran"] += cell.get("inference_ran") or 0
    scored = score_coding(task, files)
    scored["route"] = route
    scored["track"] = task["track"]
    if task["track"] == "coding_api":
        scored["family_score"] = dict(
            required_call=scored.get("required_call"),
            public_passed=scored.get("public_passed"),
            private_passed=scored.get("private_passed"),
            helper_not_required=True,
        )
    else:
        scored["family_score"] = dict(
            helper_present=scored.get("helper_present"),
            caller_present=scored.get("caller_present"),
            required_call=scored.get("required_call"),
            public_passed=scored.get("public_passed"),
            private_passed=scored.get("private_passed"),
        )
    return scored


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        track = row["track"]
        method = row["method"]
        bucket = out.setdefault(track, {})
        cell = bucket.setdefault(method, dict(n=0, passed=0))
        cell["n"] += 1
        cell["passed"] += int(bool((row.get("scored") or {}).get("passed")))
    return out


def run_followup(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    config = load_config()
    raw_path = directory / "seed_capability_followup_raw.jsonl"
    if raw_path.exists():
        raw_path.unlink()
    events: list[dict[str, Any]] = []
    meter = EventMeter(lambda event: events.append(event) or raw_path.open("a", encoding="utf-8").write(
        json.dumps(event, default=str) + "\n"
    ))
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    rows = run_knowledge_track()
    conversation = run_conversation_track()
    rows.extend(conversation["clarify"])
    partial = False
    live_plan = []
    for task in mathematics_tasks():
        for method in MATH_METHODS:
            live_plan.append((task, method, run_math_cell))
    for task in api_tasks():
        for method in CODING_METHODS:
            live_plan.append((task, method, run_coding_cell))
    for task in coordinated_tasks():
        for method in CODING_METHODS:
            live_plan.append((task, method, run_coding_cell))
    for task, method, runner in live_plan:
        if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
            partial = True
            break
        cell = meter.call(
            f"{task['task_id']}:{method}", "followup_cell", task["task_id"],
            lambda _, t=task, m=method, r=runner: dict(
                task_id=t["task_id"], track=t["track"], family=t.get("family"),
                method=m, scored=r(runtime, t, m, clock), live=True,
            ),
            dict(task_id=task["task_id"], method=method),
        )
        if isinstance(cell, dict) and cell.get("task_id"):
            rows.append(cell)
            (directory / "seed_capability_followup_partial.json").write_text(
                json.dumps(dict(rows=rows, partial=True), default=str), encoding="utf-8")
    usage = dict(
        kind="capability_followup_cpu_usage",
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
        partial=partial,
    )
    payload = dict(
        kind="seed_capability_followup",
        confirmation=False,
        aggregate_score=False,
        learning_to_learn_established=False,
        original_map_artifact="f3b2d0e8a66832154f19f5ade8ab2c02b34fc393a44eaedb42a95e417d305edc",
        config=config,
        rows=rows,
        conversation_review=conversation["review"],
        conversation_review_summary=conversation["review_summary"],
        summary=summarize(rows),
        usage=usage,
        events=len(events),
        api_audit_preserved=True,
    )
    payload["hash"] = digest({k: payload[k] for k in ("kind", "summary", "usage")})
    (directory / "recovery_live_usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return payload


__all__ = ["run_followup", "start_map_runtime", "load_config", "all_live_tasks"]
