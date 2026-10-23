"""Small live comparison: immediate revise vs all-cheap-first on 1.5B failures.

Does not debit the frozen 3564.568 s ledger or product chat_usage.json.
Learned selection is not re-tested here. Fixture repair stays separate.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .capability_evidence import digest
from .chat_template import render_prompt
from .constrained_edit import plan_constrained_edit
from .function_format import JSON_BODY_SCHEMA, assemble_format_proposal, prompt_for_format
from .public_failure import public_revision_feedback
from .recovery_actions import apply_evidence, blank_evidence, run_cases
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S, run_episode, score_files
from .recovery_policy import zero_weights
from .recovery_tasks import _add1, _name, _pair, _ready, _task

PREFERRED = Path(".models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
LIVE_METHODS = ("immediate_revise", "all_cheap_first")
WALL_CAP_S = 180.0
CALL_CAP = 24


def live_compare_tasks() -> list[dict[str, Any]]:
    """Four public tasks whose useful information sources differ. Starters omit the target."""
    return [
        _task(
            "live_schema", "live", "schema_key",
            "Create function name_of(item) that returns the name field in lowercase.",
            {"tag.py": "def echo(text):\n    return text\n"},
            [{"entry": "tag.name_of", "input": {"name": "Ada"}, "expected": "ada"}],
            [{"entry": "tag.name_of", "input": {"name": "Lin"}, "expected": "lin"}],
            reference=_name,
        ),
        _task(
            "live_api", "live", "api_docs",
            "Create function pair(item) that joins left and right in lowercase using the project helper.",
            {"pair.py": "def join_parts(left, right):\n    return left + '/' + right\n"},
            [{"entry": "pair.pair", "input": {"left": "On", "right": "Off"}, "expected": "on/off"}],
            [{"entry": "pair.pair", "input": {"left": "In", "right": "Out"}, "expected": "in/out"}],
            docs=[{"doc_id": "join-api", "title": "join_parts",
                   "content": "Call join_parts(left, right). It inserts one slash. Lowercase both sides first."}],
            reference=_pair,
        ),
        _task(
            "live_assume", "live", "wrong_assumption",
            "Create function ready(item) that is true when score meets the limit.",
            {"gate.py": "def echo(text):\n    return text\n"},
            [{"entry": "gate.ready", "input": {"score": 4, "limit": 2}, "expected": True}],
            [{"entry": "gate.ready", "input": {"score": 3, "limit": 3}, "expected": True}],
            teacher_available=True,
            reference=_ready,
        ),
        _task(
            "live_add1", "live", "immediate_ok",
            "Create function add1(item) that returns n plus one.",
            {"inc.py": "def echo(text):\n    return text\n"},
            [{"entry": "inc.add1", "input": {"n": 3}, "expected": 4}],
            [{"entry": "inc.add1", "input": {"n": 10}, "expected": 11}],
            reference=_add1,
        ),
    ]


def _prompt_task(task: dict[str, Any], files: dict[str, str], evidence: dict[str, Any] | None = None):
    docs = list(task.get("docs") or [])
    extra = []
    if evidence:
        if evidence.get("contract"):
            extra.append({"title": "inspected schema", "content": str(evidence["contract"])[:400]})
        for text in evidence.get("retrieved_texts") or []:
            extra.append({"title": "retrieved", "content": str(text)[:400]})
        for example in evidence.get("teacher_examples") or []:
            extra.append({"title": "distinguishing example",
                          "content": json.dumps(example, allow_nan=False)[:400]})
    return SimpleNamespace(
        request=task["request"],
        public_tests=task["public"],
        docs=docs + extra,
        files=files,
    )


def model_complete(runtime, prompt: str) -> dict[str, Any]:
    reply = runtime.complete(prompt, JSON_BODY_SCHEMA)
    tel = reply.get("telemetry") or {}
    return dict(
        content=reply.get("content") or "",
        inference_ran=bool(tel.get("inference_ran")),
        wall_s=float(tel.get("request_wall_s") or 0.0),
        input_tokens=tel.get("input_tokens"),
        generated_tokens=tel.get("generated_tokens"),
    )


def propose_initial(runtime, task: dict[str, Any]) -> dict[str, Any]:
    plan = plan_constrained_edit(task["request"], task["files"], task["public"])
    user = prompt_for_format("json_body", _prompt_task(task, task["files"]), plan, None)
    prompt, _meta = render_prompt("chatml", user)
    raw = model_complete(runtime, prompt)
    assembled = assemble_format_proposal(
        "json_body", raw["content"], task["request"], task["files"], task["public"], plan=plan,
    )
    files = assembled.get("patched_files") or dict(task["files"])
    public = run_cases(files, task["public"])
    return dict(
        files=files,
        public=public,
        failed=public.get("status") != "passed",
        structurally_valid=bool(assembled.get("structurally_valid")),
        model_calls=1,
        inference_ran=raw["inference_ran"],
        wall_s=raw["wall_s"] + float(public.get("wall_s") or 0.0),
        raw=raw["content"][:400],
        origin="model_generated_initial",
    )


def make_reviser(runtime, clock: dict[str, Any]):
    def reviser(task: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
            raise TimeoutError("live_recovery_cap")
        files = dict(evidence.get("files") or task["files"])
        plan = plan_constrained_edit(task["request"], files, task["public"])
        feedback = public_revision_feedback(evidence.get("public"), task["public"])
        user = prompt_for_format("json_body", _prompt_task(task, files, evidence), plan, feedback)
        prompt, _meta = render_prompt("chatml", user)
        raw = model_complete(runtime, prompt)
        clock["calls"] += 1
        clock["inference_ran"] += int(raw["inference_ran"])
        assembled = assemble_format_proposal(
            "json_body", raw["content"], task["request"], files, task["public"], plan=plan,
        )
        new_files = assembled.get("patched_files") or files
        public = run_cases(new_files, task["public"])
        return dict(
            action="REVISE",
            available=True,
            files=new_files,
            public=public,
            feedback=feedback["instruction"],
            wall_s=raw["wall_s"] + float(public.get("wall_s") or 0.0),
            tool_executions=1 + int(public.get("tool_executions") or 0),
            model_calls=1,
            teacher_queries=0,
            inference_ran=raw["inference_ran"],
            structurally_valid=bool(assembled.get("structurally_valid")),
        )
    return reviser


def compare_live(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    clock = dict(started=started, calls=0, inference_ran=0)
    reviser = make_reviser(runtime, clock)
    records = []
    for task in live_compare_tasks():
        if clock["calls"] >= CALL_CAP or time.perf_counter() - started >= WALL_CAP_S:
            break
        initial = propose_initial(runtime, task)
        clock["calls"] += 1
        clock["inference_ran"] += int(initial["inference_ran"])
        row = dict(
            task_id=task["task_id"],
            family_hidden=True,
            initial_failed=initial["failed"],
            initial_structurally_valid=initial["structurally_valid"],
            initial_inference_ran=initial["inference_ran"],
            initial_wall_s=initial["wall_s"],
            methods={},
        )
        if not initial["failed"]:
            scored = score_files(task, initial["files"])
            row["passed_without_recovery"] = True
            row["private_passed"] = scored["private_passed"]
            records.append(row)
            continue
        shared_public = initial["public"]
        working = dict(task)
        working["files"] = initial["files"]
        for method in LIVE_METHODS:
            episode = run_episode(
                working, method, zero_weights(), [], directory,
                initial=shared_public, reviser=reviser,
            )
            row["methods"][method] = dict(
                actions=episode["actions"],
                public_passed=episode["public_passed"],
                private_passed=episode["private_passed"],
                model_calls=episode["model_calls"],
                teacher_queries=episode["teacher_queries"],
                tool_executions=episode["tool_executions"],
                wall_s=episode["wall_s"],
                unnecessary_diagnostics=episode["unnecessary_diagnostics"],
            )
        records.append(row)
    usage = dict(
        kind="recovery_live_cpu_usage",
        backend="cpu",
        gpu_used=False,
        ngl=0,
        metal_used=False,
        product_chat_usage_used=False,
        research_cpu_ledger_frozen_s=FROZEN_CPU_USED_S,
        research_cpu_ledger_remaining_s=FROZEN_CPU_REMAINING_S,
        research_cpu_ledger_debit_s=0.0,
        model_calls=clock["calls"],
        inference_ran=clock["inference_ran"],
        wall_s=round(time.perf_counter() - started, 3),
        cap_s=WALL_CAP_S,
        call_cap=CALL_CAP,
    )
    (directory / "recovery_live_usage.json").write_text(
        json.dumps(usage, indent=2, allow_nan=False), encoding="utf-8",
    )
    failed = [row for row in records if row.get("initial_failed")]
    summary = {}
    for method in LIVE_METHODS:
        rows = [row["methods"][method] for row in failed if method in row.get("methods", {})]
        summary[method] = dict(
            recovery_episodes=len(rows),
            public_correct=sum(int(r["public_passed"]) for r in rows),
            private_correct=sum(int(r["private_passed"]) for r in rows),
            model_calls=sum(r["model_calls"] for r in rows),
            tool_executions=sum(r["tool_executions"] for r in rows),
        )
    helped = summary.get("all_cheap_first", {}).get("private_correct", 0) > summary.get("immediate_revise", {}).get("private_correct", 0)
    payload = dict(
        kind="seed_recovery_live_compare",
        confirmation=False,
        learning_to_learn_established=False,
        learned_selection_tested=False,
        provisional_baseline="all_cheap_first",
        model=str(PREFERRED),
        records=records,
        summary=summary,
        usage=usage,
        recovery_helped_1p5b=helped,
        verdict=(
            "all_cheap_first_helped_live_failures" if helped else
            "no_live_advantage_or_insufficient_failures"
        ),
    )
    payload["hash"] = digest({k: v for k, v in payload.items() if k != "hash"})
    return payload


def start_cpu_runtime():
    from .local_model_runtime import PersistentLocalRuntime, RuntimeConfig
    model = PREFERRED if PREFERRED.is_file() else Path(os.environ.get("NEXUS_MODEL_PATH") or "")
    executable = os.environ.get("NEXUS_LLAMA_SERVER", "llama-server")
    if not model.is_file() or shutil.which(executable) is None:
        return None, dict(status="unavailable", reason="local_model_or_server_missing")
    cfg = replace(
        RuntimeConfig.from_environment(),
        model_path=str(model.resolve()),
        executable=executable,
        application_cache=False,
        max_tokens=128,
        request_timeout_s=25,
        startup_timeout_s=45,
        threads=2,
    )
    runtime = PersistentLocalRuntime(cfg)
    runtime.start()
    return runtime, dict(status="started", model=str(model), ngl=0, device="none")
