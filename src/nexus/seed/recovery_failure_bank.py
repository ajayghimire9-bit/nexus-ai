"""Frozen genuine-failure bank and equal-budget revise-versus-fresh compare.

Collects every predeclared task. Does not drop inconvenient failures.
Development chooses the simple procedure; assessment is scored after lock.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .chat_template import render_prompt
from .constrained_edit import plan_constrained_edit
from .function_format import JSON_BODY_SCHEMA, assemble_format_proposal, prompt_for_format
from .input_contract import describe_input_contract
from .public_failure import public_revision_feedback
from .recovery_actions import apply_evidence, blank_evidence, exception_category, inspect_schema, run_cases
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S, score_files
from .recovery_live import _prompt_task, live_compare_tasks, model_complete, start_cpu_runtime
from .recovery_tasks import _add1, _combo, _mark, _name, _pair, _ready, _task

CALL_CAP = 80
STEP_CALLS = 2
MAX_TOKENS = 128
WALL_CAP_S = 360.0


def _echo(name: str) -> dict[str, str]:
    return {name: "def echo(text):\n    return text\n"}


def collection_catalogue() -> list[dict[str, Any]]:
    return [
        _task("dev_name_of", "development", "schema_key",
              "Create function name_of(item) that returns the name field in lowercase.",
              _echo("tag.py"),
              [{"entry": "tag.name_of", "input": {"name": "Ada"}, "expected": "ada"}],
              [{"entry": "tag.name_of", "input": {"name": "Lin"}, "expected": "lin"}],
              reference=_name),
        _task("dev_pair", "development", "api_docs",
              "Create function pair(item) that joins left and right in lowercase using the project helper.",
              {"pair.py": "def join_parts(left, right):\n    return left + '/' + right\n"},
              [{"entry": "pair.pair", "input": {"left": "On", "right": "Off"}, "expected": "on/off"}],
              [{"entry": "pair.pair", "input": {"left": "In", "right": "Out"}, "expected": "in/out"}],
              docs=[{"doc_id": "join-api", "title": "join_parts",
                     "content": "Call join_parts(left, right). It inserts one slash. Lowercase both sides first."}],
              reference=_pair),
        _task("dev_ready", "development", "wrong_assumption",
              "Create function ready(item) that is true when score meets the limit.",
              _echo("gate.py"),
              [{"entry": "gate.ready", "input": {"score": 4, "limit": 2}, "expected": True}],
              [{"entry": "gate.ready", "input": {"score": 3, "limit": 3}, "expected": True}],
              teacher_available=True, reference=_ready),
        _task("dev_add1", "development", "immediate_ok",
              "Create function add1(item) that returns n plus one.",
              _echo("inc.py"),
              [{"entry": "inc.add1", "input": {"n": 3}, "expected": 4}],
              [{"entry": "inc.add1", "input": {"n": 10}, "expected": 11}],
              reference=_add1),
        _task("dev_mark", "development", "missing_value",
              "Create function mark(item) that returns room and shelf in lowercase joined by one slash.",
              _echo("shelf.py"),
              [{"entry": "shelf.mark", "input": {"room": "East", "shelf": "B2"}, "expected": "east/b2"},
               {"entry": "shelf.mark", "input": {"shelf": "B2"}, "expected": "/b2"}],
              [{"entry": "shelf.mark", "input": {"room": "West", "shelf": "C9"}, "expected": "west/c9"},
               {"entry": "shelf.mark", "input": {"room": "West"}, "expected": "west/"}],
              reference=_mark),
        _task("dev_title", "development", "schema_key",
              "Create function title_of(item) that returns the title field in lowercase.",
              _echo("book.py"),
              [{"entry": "book.title_of", "input": {"title": "Seed"}, "expected": "seed"}],
              [{"entry": "book.title_of", "input": {"title": "Nexus"}, "expected": "nexus"}],
              reference=lambda item: str(item.get("title") or "").lower()),
        _task("dev_glue", "development", "api_docs",
              "Create function glue(item) that joins first and second in lowercase using the project helper.",
              {"glue.py": "def join_parts(left, right):\n    return left + '/' + right\n"},
              [{"entry": "glue.glue", "input": {"first": "Hi", "second": "Lo"}, "expected": "hi/lo"}],
              [{"entry": "glue.glue", "input": {"first": "Old", "second": "New"}, "expected": "old/new"}],
              docs=[{"doc_id": "glue-api", "title": "join_parts",
                     "content": "Call join_parts(first, second) after lowercasing. The helper inserts a slash."}],
              reference=lambda item: str(item.get("first") or "").lower() + "/" + str(item.get("second") or "").lower()),
        _task("dev_combo", "development", "multistep",
              "Create function combo(item) that lowercases left and right and joins them with the helper.",
              {"mix.py": "def join_parts(left, right):\n    return left + '/' + right\n"},
              [{"entry": "mix.combo", "input": {"left": "Up", "right": "Down"}, "expected": "up/down"}],
              [{"entry": "mix.combo", "input": {"left": "Yes", "right": "No"}, "expected": "yes/no"}],
              docs=[{"doc_id": "combo-api", "title": "join_parts",
                     "content": "Use join_parts on the left and right fields after lowercasing."}],
              reference=_combo),
        _task("assess_label", "assessment", "schema_key",
              "Create function label_of(item) that returns the label field in lowercase.",
              _echo("lab.py"),
              [{"entry": "lab.label_of", "input": {"label": "Red"}, "expected": "red"}],
              [{"entry": "lab.label_of", "input": {"label": "Blue"}, "expected": "blue"}],
              reference=lambda item: str(item.get("label") or "").lower()),
        _task("assess_place", "assessment", "missing_value",
              "Create function place(item) that returns hall and bin in lowercase joined by one slash.",
              _echo("bin.py"),
              [{"entry": "bin.place", "input": {"hall": "North", "bin": "A1"}, "expected": "north/a1"},
               {"entry": "bin.place", "input": {"bin": "A1"}, "expected": "/a1"}],
              [{"entry": "bin.place", "input": {"hall": "South", "bin": "D4"}, "expected": "south/d4"},
               {"entry": "bin.place", "input": {"hall": "South"}, "expected": "south/"}],
              reference=lambda item: str(item.get("hall") or "").lower() + "/" + str(item.get("bin") or "").lower()),
        _task("assess_order", "assessment", "excluded_family",
              "Create function order(item) that returns values sorted ascending.",
              _echo("ord.py"),
              [{"entry": "ord.order", "input": {"values": [3, 1, 2]}, "expected": [1, 2, 3]}],
              [{"entry": "ord.order", "input": {"values": [9, 0, 4]}, "expected": [0, 4, 9]}],
              reference=lambda item: sorted(item["values"])),
        _task("assess_ready", "assessment", "wrong_assumption",
              "Create function ready(item) that is true when score meets the limit.",
              _echo("gate2.py"),
              [{"entry": "gate2.ready", "input": {"score": 8, "limit": 3}, "expected": True}],
              [{"entry": "gate2.ready", "input": {"score": 5, "limit": 5}, "expected": True}],
              teacher_available=True, reference=_ready),
        _task("assess_stamp", "assessment", "excluded_composition",
              "Create function stamp(item) that lowercases code and mark and joins them with the helper.",
              {"stamp.py": "def join_parts(left, right):\n    return left + '/' + right\n"},
              [{"entry": "stamp.stamp", "input": {"code": "Ok", "mark": "Go"}, "expected": "ok/go"}],
              [{"entry": "stamp.stamp", "input": {"code": "No", "mark": "Yes"}, "expected": "no/yes"}],
              docs=[{"doc_id": "stamp-api", "title": "join_parts",
                     "content": "Use join_parts on the code and mark fields after lowercasing."}],
              reference=lambda item: str(item.get("code") or "").lower() + "/" + str(item.get("mark") or "").lower()),
        _task("assess_bundle", "assessment", "multistep",
              "Create function bundle(item) that lowercases head and tail and joins them with the helper.",
              {"bun.py": "def join_parts(left, right):\n    return left + '/' + right\n"},
              [{"entry": "bun.bundle", "input": {"head": "Sun", "tail": "Moon"}, "expected": "sun/moon"}],
              [{"entry": "bun.bundle", "input": {"head": "Day", "tail": "Night"}, "expected": "day/night"}],
              docs=[{"doc_id": "bun-api", "title": "join_parts",
                     "content": "Use join_parts on the head and tail fields after lowercasing."}],
              reference=lambda item: str(item.get("head") or "").lower() + "/" + str(item.get("tail") or "").lower()),
    ]


def target_source(files: dict[str, str], entry: str) -> str:
    filename = entry.split(".", 1)[0] + ".py"
    return files.get(filename, "")


def classify_failure(public: dict[str, Any]) -> str:
    rows = public.get("results") or []
    if any(str(row.get("error") or "").startswith("missing_entry") for row in rows):
        return "missing_entry"
    category = exception_category(public)
    if category not in ("none", "other"):
        return category
    if public.get("status") != "passed":
        return "wrong_value"
    return "none"


def public_errors(public: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for row in public.get("results") or []:
        out.append(dict(
            entry=row.get("entry"),
            passed=row.get("passed"),
            actual=row.get("actual"),
            expected=row.get("expected"),
            error=row.get("error"),
        ))
    return out


def analyze_step(before: dict[str, str], after: dict[str, str], entry: str,
                 before_public: dict[str, Any], after_public: dict[str, Any],
                 generated_tokens: Any, raw: str) -> dict[str, Any]:
    old = target_source(before, entry)
    new = target_source(after, entry)
    tokens = generated_tokens if type(generated_tokens) in (int, float) else None
    return dict(
        repeated_code=old == new,
        ignored_feedback=public_errors(before_public) == public_errors(after_public),
        hit_token_cap=tokens is not None and tokens >= MAX_TOKENS,
        generated_tokens=tokens,
        raw_len=len(raw or ""),
        structurally_empty=not (new or "").strip() or new == old and "def echo" in new,
    )


def describe_trace(task: dict[str, Any], files: dict[str, str], public: dict[str, Any]) -> dict[str, Any]:
    plan = plan_constrained_edit(task["request"], files, task["public"])
    return dict(
        request=task["request"],
        input_contract=describe_input_contract(plan, task["public"]),
        current_function=plan.existing_source,
        failure_type=classify_failure(public),
        errors=public_errors(public),
    )


def generate(runtime, task: dict[str, Any], files: dict[str, str],
             feedback: dict[str, Any] | None, clock: dict[str, Any],
             evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
        raise TimeoutError("failure_bank_cap")
    plan = plan_constrained_edit(task["request"], files, task["public"])
    user = prompt_for_format("json_body", _prompt_task(task, files, evidence), plan, feedback)
    prompt, _meta = render_prompt("chatml", user)
    raw = model_complete(runtime, prompt)
    clock["calls"] += 1
    clock["inference_ran"] += int(raw["inference_ran"])
    assembled = assemble_format_proposal(
        "json_body", raw["content"], task["request"], files, task["public"], plan=plan,
    )
    new_files = assembled.get("patched_files") or dict(files)
    public = run_cases(new_files, task["public"])
    return dict(
        files=new_files,
        public=public,
        raw=raw["content"],
        generated_tokens=raw.get("generated_tokens"),
        inference_ran=raw["inference_ran"],
        wall_s=raw["wall_s"],
        structurally_valid=bool(assembled.get("structurally_valid")),
        prompt_has_failed_body=bool(plan.existing_source and plan.symbol in (plan.existing_source or "")
                                    and plan.existing_source != "def echo(text):\n    return text\n"),
        current_function=plan.existing_source,
        user_prompt=user[:1200],
    )


def _record_step(task, files, before, before_public, step) -> dict[str, Any]:
    analysis = analyze_step(
        before, files, task["public"][0]["entry"],
        before_public, step["public"], step["generated_tokens"], step["raw"],
    )
    return dict(
        current_function_before=step["current_function"],
        current_function_after=target_source(files, task["public"][0]["entry"]),
        errors=public_errors(step["public"]),
        public=step["public"],
        public_status=step["public"].get("status"),
        prompt_has_failed_body=step["prompt_has_failed_body"],
        user_prompt=step["user_prompt"],
        raw=step["raw"][:800],
        **analysis,
    )


def reconstruct_prior_live(runtime, clock: dict[str, Any]) -> list[dict[str, Any]]:
    """Replay live_schema and live_add1 with full request/code/error traces."""
    wanted = {row["task_id"]: row for row in live_compare_tasks()
              if row["task_id"] in ("live_schema", "live_add1")}
    traces = []
    for task_id in ("live_schema", "live_add1"):
        task = wanted[task_id]
        initial = generate(runtime, task, task["files"], None, clock)
        frozen = dict(
            starter_files=task["files"],
            files=initial["files"],
            public=initial["public"],
        )
        inspect = inspect_schema(task, initial["files"])
        methods = {}
        for mode, use_inspect in (("immediate_revise", False), ("all_cheap_first", True)):
            files = dict(initial["files"])
            evidence = blank_evidence(files, initial["public"])
            if use_inspect:
                evidence = apply_evidence(evidence, inspect)
            feedback = public_revision_feedback(initial["public"], task["public"])
            steps = []
            before_public = initial["public"]
            for _ in range(STEP_CALLS):
                before = dict(files)
                step = generate(runtime, task, files, feedback, clock, evidence)
                files = step["files"]
                evidence["files"] = files
                evidence["public"] = step["public"]
                steps.append(_record_step(task, files, before, before_public, step))
                before_public = step["public"]
                feedback = public_revision_feedback(step["public"], task["public"])
                if step["public"].get("status") == "passed":
                    break
            scored = score_files(task, files)
            methods[mode] = dict(
                public_passed=scored["public_passed"],
                private_passed=scored["private_passed"],
                steps=steps,
                used_inspect=use_inspect,
                inspect_contract=inspect["contract"] if use_inspect else None,
            )
        traces.append(dict(
            task_id=task_id,
            request=task["request"],
            inspect=describe_trace(task, initial["files"], initial["public"]),
            initial=dict(
                files=initial["files"],
                current_function=target_source(initial["files"], task["public"][0]["entry"]),
                errors=public_errors(initial["public"]),
                failure_type=classify_failure(initial["public"]),
                raw=initial["raw"][:800],
                generated_tokens=initial["generated_tokens"],
                hit_token_cap=type(initial["generated_tokens"]) in (int, float)
                and initial["generated_tokens"] >= MAX_TOKENS,
                structurally_valid=initial["structurally_valid"],
            ),
            methods=methods,
        ))
    return traces


def collect_initial(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    step = generate(runtime, task, task["files"], None, clock)
    scored = score_files(task, step["files"])
    return dict(
        task_id=task["task_id"],
        split=task["split"],
        origin="model_generated_initial",
        failed=step["public"].get("status") != "passed",
        failure_type=classify_failure(step["public"]),
        starter_files=task["files"],
        files=step["files"],
        public=step["public"],
        private_passed=scored["private_passed"],
        public_passed=scored["public_passed"],
        current_function=target_source(step["files"], task["public"][0]["entry"]),
        contract=describe_input_contract(
            plan_constrained_edit(task["request"], step["files"], task["public"]), task["public"],
        ),
        request=task["request"],
        errors=public_errors(step["public"]),
        raw=step["raw"][:800],
        generated_tokens=step["generated_tokens"],
        hit_token_cap=type(step["generated_tokens"]) in (int, float) and step["generated_tokens"] >= MAX_TOKENS,
        structurally_valid=step["structurally_valid"],
        inference_ran=step["inference_ran"],
        wall_s=step["wall_s"],
    )


def run_equal_budget(runtime, task: dict[str, Any], frozen: dict[str, Any],
                     mode: str, clock: dict[str, Any]) -> dict[str, Any]:
    """mode=revise uses the failed draft; mode=fresh uses the original starter."""
    files = dict(frozen["files"] if mode == "revise" else frozen["starter_files"])
    feedback = public_revision_feedback(frozen["public"], task["public"])
    steps = []
    for _ in range(STEP_CALLS):
        before = dict(files)
        before_public = steps[-1]["public"] if steps else frozen["public"]
        step = generate(runtime, task, files, feedback, clock)
        files = step["files"]
        steps.append(_record_step(task, files, before, before_public, step))
        feedback = public_revision_feedback(step["public"], task["public"])
        if step["public"].get("status") == "passed":
            break
    scored = score_files(task, files)
    return dict(
        mode=mode,
        calls=len(steps),
        public_passed=scored["public_passed"],
        private_passed=scored["private_passed"],
        steps=steps,
        cannot_revise=mode == "revise" and not scored["public_passed"] and any(s["repeated_code"] or s["ignored_feedback"] for s in steps),
        cannot_solve=not scored["public_passed"],
    )


def summarize_by_type(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        kind = row["failure_type"]
        bucket = out.setdefault(kind, dict(n=0, revise_public=0, fresh_public=0, revise_private=0, fresh_private=0))
        bucket["n"] += 1
        bucket["revise_public"] += int(row["revise"]["public_passed"])
        bucket["fresh_public"] += int(row["fresh"]["public_passed"])
        bucket["revise_private"] += int(row["revise"]["private_passed"])
        bucket["fresh_private"] += int(row["fresh"]["private_passed"])
    return out


def lock_procedure(dev_rows: list[dict[str, Any]]) -> str:
    revise = sum(int(row["revise"]["private_passed"]) for row in dev_rows)
    fresh = sum(int(row["fresh"]["private_passed"]) for row in dev_rows)
    if fresh > revise:
        return "fresh"
    if revise > fresh:
        return "revise"
    r_pub = sum(int(row["revise"]["public_passed"]) for row in dev_rows)
    f_pub = sum(int(row["fresh"]["public_passed"]) for row in dev_rows)
    if f_pub > r_pub:
        return "fresh"
    if r_pub > f_pub:
        return "revise"
    return "neither"


def run_bank(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    prior_traces = reconstruct_prior_live(runtime, clock)
    tasks = {row["task_id"]: row for row in collection_catalogue()}
    collected = []
    for task in collection_catalogue():
        collected.append(collect_initial(runtime, task, clock))
    failures = [row for row in collected if row["failed"]]
    development = []
    for frozen in failures:
        if frozen["split"] != "development":
            continue
        task = tasks[frozen["task_id"]]
        development.append(dict(
            task_id=frozen["task_id"],
            failure_type=frozen["failure_type"],
            inspect=describe_trace(task, frozen["files"], frozen["public"]),
            revise=run_equal_budget(runtime, task, frozen, "revise", clock),
            fresh=run_equal_budget(runtime, task, frozen, "fresh", clock),
        ))
    winner = lock_procedure(development)
    assessment = []
    for frozen in failures:
        if frozen["split"] != "assessment":
            continue
        task = tasks[frozen["task_id"]]
        if winner in ("revise", "fresh"):
            result = run_equal_budget(runtime, task, frozen, winner, clock)
        else:
            result = dict(mode="neither", calls=0, public_passed=False, private_passed=False, steps=[])
        assessment.append(dict(
            task_id=frozen["task_id"],
            failure_type=frozen["failure_type"],
            inspect=describe_trace(task, frozen["files"], frozen["public"]),
            locked_mode=winner,
            result=result,
        ))
    usage = dict(
        kind="recovery_failure_bank_cpu_usage",
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
    )
    payload = dict(
        kind="seed_recovery_failure_bank",
        confirmation=False,
        learning_to_learn_established=False,
        prior_live_traces=prior_traces,
        collected=collected,
        development=development,
        assessment=assessment,
        by_type=summarize_by_type(development),
        locked_procedure=winner,
        usage=usage,
        collected_n=len(collected),
        failure_n=len(failures),
        development_failure_n=len(development),
        assessment_failure_n=sum(1 for row in failures if row["split"] == "assessment"),
    )
    payload["hash"] = digest({k: payload[k] for k in (
        "kind", "locked_procedure", "by_type", "usage", "failure_n",
    )})
    (directory / "recovery_live_usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return payload
