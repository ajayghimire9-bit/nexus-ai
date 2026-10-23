"""Raw vs ChatML prompts, equality-failure revision, fresh functions, discovery."""
from __future__ import annotations

import time
from typing import Any

from .agent_loop_worker import run_worker_subprocess
from .capability_evidence import EventMeter, digest
from .chat_template import (
    PROMPT_STYLES, choose_best_style, gguf_has_chatml_tokens, gguf_metadata_string,
    render_prompt, style_score,
)
from .constrained_edit import plan_constrained_edit
from .function_format import (
    assemble_format_proposal, decoding_record, prompt_for_format, revision_feedback,
    schema_for_format,
)
from .interrupt_transfer import _assess
from .process_memory import sample_process_memory
from .public_failure import comparison_ops, operator_hint_present, public_revision_feedback
from .target_discovery import discover_edit_target, score_discovery


CLOSED_TASK_IDS = {
    "py_width_ok", "py_keep_exclusive", "py_pair_label", "py_cutoff_ambiguous",
    "py_hi_inclusive_src", "py_slug_join", "py_levy_then_credit", "py_retry_last",
    "py_cap_inclusive_src", "py_span_ok", "py_floor_ok", "py_reject_floor",
    "py_note_join", "py_threshold_fix", "py_mix_span", "py_doc_lie", "py_two_bugs",
    "py_src_cap_ok", "py_src_title_ok", "py_mark_join", "py_invoice_slug_feature",
    "py_span_three_point", "py_span_equal_only", "py_width_three_point_dev",
    "py_height_three_point_fresh", "py_depth_three_point", "py_tag_colon_feature",
    "py_level_three_point", "py_code_colon",
}

FORMAT = "json_body"


def _task(spec):
    return type("T", (), {
        "files": spec["files"],
        "request": spec["request"],
        "public_tests": spec.get("public") or [],
        "docs": spec.get("docs") or [],
        "language": spec["language"],
    })()


def _complete(runtime, prompt, schema, meter, scope, identity):
    return meter.call(scope, "complete", identity, lambda _: runtime.complete(prompt, schema), None)


def _eval_public(meter, scope, spec, files):
    return meter.call(
        scope, "worker", spec["id"],
        lambda payload: run_worker_subprocess(payload, 10),
        dict(language=spec["language"], files=files, cases=spec.get("public") or []),
    )


def _body_excerpt(assembled: dict[str, Any]) -> str:
    preview = assembled.get("preview") or {}
    return str(preview.get("new_excerpt") or assembled.get("raw_excerpt") or "")


def propose_cell(runtime, spec, style, meter, scope, max_tokens=128):
    started = time.perf_counter()
    task = _task(spec)
    plan = plan_constrained_edit(spec["request"], spec["files"], spec.get("public") or [])
    schema = schema_for_format(FORMAT)
    decoding = decoding_record(schema, max_tokens)
    user_prompt = prompt_for_format(FORMAT, task, plan)
    prompt, render = render_prompt(style, user_prompt)
    raw = _complete(runtime, prompt, schema, meter, scope, spec["id"] + ":0")
    if type(raw) is not dict:
        raw = {"content": "", "telemetry": {}, "status": "error", "reason": str(raw)}
    assembled = assemble_format_proposal(
        FORMAT, raw.get("content") or "", spec["request"], spec["files"], spec.get("public") or [],
    )
    traces = [dict(
        round=1, user_prompt=user_prompt, prompt_reached_model=prompt, render=render,
        decoding=decoding, raw_content=(raw.get("content") or "")[:800],
        telemetry=raw.get("telemetry"), comparison_ops=comparison_ops(_body_excerpt(assembled)),
        **{k: assembled[k] for k in (
            "raw_valid", "raw_reason", "raw_excerpt", "normalized", "placeholder",
            "syntax_valid", "structurally_valid", "preview",
        )},
    )]
    public = None
    if assembled.get("placeholder"):
        feedback = revision_feedback(assembled["placeholder"])
        user2 = prompt_for_format(FORMAT, task, plan, feedback)
        prompt2, render2 = render_prompt(style, user2)
        raw2 = _complete(runtime, prompt2, schema, meter, scope, spec["id"] + ":1")
        if type(raw2) is not dict:
            raw2 = {"content": "", "telemetry": {}}
        assembled = assemble_format_proposal(
            FORMAT, raw2.get("content") or "", spec["request"], spec["files"], spec.get("public") or [],
        )
        traces.append(dict(
            round=2, user_prompt=user2, prompt_reached_model=prompt2, render=render2,
            decoding=decoding, raw_content=(raw2.get("content") or "")[:800],
            telemetry=raw2.get("telemetry"), revision_of="placeholder",
            comparison_ops=comparison_ops(_body_excerpt(assembled)),
            equality_failure_in_revision=False,
            operator_hint_in_revision=operator_hint_present(user2),
            **{k: assembled[k] for k in (
                "raw_valid", "raw_reason", "raw_excerpt", "normalized", "placeholder",
                "syntax_valid", "structurally_valid", "preview",
            )},
        ))
    executed = False
    public_passed = False
    equality_in_revision = False
    operator_in_revision = False
    if assembled.get("structurally_valid") and assembled.get("patched_files"):
        public = _eval_public(meter, scope, spec, assembled["patched_files"])
        if public.get("status") not in {"blocked_missing_runtime", "rejected"}:
            executed = True
        public_passed = bool(public.get("all_passed"))
        if not public_passed and assembled.get("placeholder") is None and len(traces) < 2:
            feedback = public_revision_feedback(public, spec.get("public") or [])
            user3 = prompt_for_format(FORMAT, task, plan, feedback)
            prompt3, render3 = render_prompt(style, user3)
            equality_in_revision = bool(feedback.get("concrete_failure")) and (
                feedback["concrete_failure"] in user3
            )
            operator_in_revision = operator_hint_present(user3)
            raw3 = _complete(runtime, prompt3, schema, meter, scope, spec["id"] + ":rev")
            if type(raw3) is not dict:
                raw3 = {"content": "", "telemetry": {}}
            assembled = assemble_format_proposal(
                FORMAT, raw3.get("content") or "", spec["request"], spec["files"],
                spec.get("public") or [],
            )
            traces.append(dict(
                round=len(traces) + 1, user_prompt=user3, prompt_reached_model=prompt3,
                render=render3, decoding=decoding,
                raw_content=(raw3.get("content") or "")[:800],
                telemetry=raw3.get("telemetry"), revision_of="public_failure",
                concrete_failure=feedback.get("concrete_failure"),
                equality_failure_in_revision=equality_in_revision,
                operator_hint_in_revision=operator_in_revision,
                operator_supplied=feedback.get("operator_supplied"),
                comparison_ops=comparison_ops(_body_excerpt(assembled)),
                **{k: assembled[k] for k in (
                    "raw_valid", "raw_reason", "raw_excerpt", "normalized",
                    "placeholder", "syntax_valid", "structurally_valid", "preview",
                )},
            ))
            if assembled.get("structurally_valid") and assembled.get("patched_files"):
                public = _eval_public(meter, scope + ":rev", spec, assembled["patched_files"])
                executed = True
                public_passed = bool(public.get("all_passed"))
    private = _assess(meter, scope, spec, assembled.get("patched_files") or spec["files"])
    first_ops = (traces[0].get("comparison_ops") or [])
    last_ops = (traces[-1].get("comparison_ops") or [])
    complete_wall = sum(
        float((trace.get("telemetry") or {}).get("request_wall_s") or 0) for trace in traces
    )
    return dict(
        format=FORMAT,
        prompt_style=style,
        plan=assembled.get("plan"),
        traces=traces,
        decoding=decoding,
        render=render,
        placeholder=assembled.get("placeholder"),
        syntax_valid=assembled.get("syntax_valid"),
        executed=executed,
        public_passed=public_passed,
        public=public,
        private=private,
        semantic_correct=bool((private or {}).get("all_passed")),
        structurally_valid=assembled.get("structurally_valid"),
        final_files=assembled.get("patched_files") or spec["files"],
        raw_valid=assembled.get("raw_valid"),
        normalized=assembled.get("normalized"),
        completions=len(traces),
        equality_failure_in_revision=equality_in_revision,
        operator_hint_in_revision=operator_in_revision,
        comparison_ops_first=first_ops,
        comparison_ops_last=last_ops,
        comparison_changed=first_ops != last_ops,
        still_exclusive_lt=last_ops == ["Lt"] or last_ops == first_ops == ["Lt"],
        cell_wall_s=round(time.perf_counter() - started, 6),
        complete_wall_s=round(complete_wall, 6),
        memory=sample_process_memory(runtime),
    )


def _emit_discovery(emit, spec):
    discovered = discover_edit_target(spec["request"], spec["files"], spec.get("docs") or [])
    scored = score_discovery(discovered, spec["gold_target"])
    emit(dict(
        kind="capability", area="target_discovery", id=spec["id"],
        category="discovery", family=spec.get("family"), role=spec.get("role"),
        used_private_to_accept=False, complete_correctness=False,
        inventory=discovered.get("inventory"),
        **scored,
    ))
    return scored


def begin(config, emit):
    meter = EventMeter(emit)
    first = next(spec for spec in config["tasks"] if spec.get("role") != "discovery_only")
    plan = plan_constrained_edit(first["request"], first["files"], first.get("public") or [])
    user_prompt = prompt_for_format(FORMAT, _task(first), plan)
    raw_prompt, raw_meta = render_prompt("raw", user_prompt)
    chat_prompt, chat_meta = render_prompt("chatml", user_prompt)
    model_path = config["models"]["qwen05"]["path"]
    gguf_template = gguf_metadata_string(model_path)
    decoding = decoding_record(schema_for_format(FORMAT), int(config.get("model_max_tokens", 128)))
    decoding = dict(decoding, target_discovery="measured_separately_not_wired_to_assembler")
    emit(dict(
        kind="audit_manifest", config_hash=digest(config),
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learned_policy_promoted=False,
        learning_research_resumed=False,
        target_discovery="measured_separately_not_wired_to_assembler",
        gemini=config.get("gemini", "NOT_RUN"),
        result_label="authored_source_development_pilot_not_confirmation",
        decoding=decoding,
    ))
    emit(dict(
        kind="request_inspect", category="inspect", id=first["id"],
        decoding=decoding,
        raw_prompt=raw_prompt,
        chatml_prompt=chat_prompt,
        raw_meta=raw_meta,
        chatml_meta=chat_meta,
        user_equals_raw=chat_meta.get("user_equals_raw"),
        gguf_has_chatml_tokens=gguf_has_chatml_tokens(model_path),
        gguf_chat_template_excerpt=(gguf_template or "")[:400],
        gguf_template_has_default_system=bool(
            gguf_template and "You are Qwen, created by Alibaba Cloud" in gguf_template
        ),
        function_described_as="executable_python_source",
        format=FORMAT,
        stop=None,
        target_from="public_test_entry_or_existing_symbol",
        target_discovery="measured_separately_not_wired_to_assembler",
        equality_failure=(
            "For value equal to limit, expected True, received False."
        ),
        operator_supplied=False,
    ))
    return meter


def run_task_block(config, emit, meter, runtime, model_label, tasks, styles, category):
    max_tokens = int(config.get("model_max_tokens", 128))
    started = time.perf_counter()
    memory_before = sample_process_memory(runtime)
    rows = []
    for spec in tasks:
        if spec["id"] in CLOSED_TASK_IDS:
            raise ValueError("closed_task_id_reused:" + spec["id"])
        if spec.get("role") == "discovery_only":
            continue
        for style in styles:
            scope = f"{model_label}:{style}:{spec['id']}"
            result = propose_cell(runtime, spec, style, meter, scope, max_tokens)
            row = dict(
                kind="capability", area="chat_template", id=spec["id"],
                category=category, method=style, model=model_label,
                family=spec.get("family"), role=spec.get("role"),
                used_private_to_accept=False, complete_correctness=False,
                **result,
            )
            emit(row)
            rows.append(row)
    memory_after = sample_process_memory(runtime)
    emit(dict(
        kind="model_resources", category="resources", model=model_label,
        block=category, styles=list(styles),
        wall_s=round(time.perf_counter() - started, 6),
        memory_before=memory_before, memory_after=memory_after,
        per_task=[{
            "id": row["id"], "prompt_style": row.get("prompt_style"),
            "cell_wall_s": row.get("cell_wall_s"),
            "complete_wall_s": row.get("complete_wall_s"),
            "completions": row.get("completions"),
            "combined_rss_mib": (row.get("memory") or {}).get("combined_rss_mib"),
            "server_rss_mib": (row.get("memory") or {}).get("server_rss_mib"),
            "parent_rss_mib": (row.get("memory") or {}).get("parent_rss_mib"),
        } for row in rows],
        model_bytes=config["models"][model_label]["bytes"],
        weight_file_is_not_memory=True,
    ))
    return rows


def record_model(config, emit, meter, runtime, model_label, *, best_style=None):
    matched = [spec for spec in config["tasks"] if spec.get("phase") == "template"]
    fresh = [spec for spec in config["tasks"] if spec.get("phase") == "fresh"]
    template_rows = run_task_block(
        config, emit, meter, runtime, model_label, matched, PROMPT_STYLES, "template",
    )
    chosen = best_style
    if model_label == "qwen05":
        chosen = choose_best_style(template_rows)
        emit(dict(
            kind="style_choice", category="choice", best_style=chosen,
            scores={
                style: sum(style_score(row) for row in template_rows if row.get("prompt_style") == style)
                for style in PROMPT_STYLES
            },
        ))
    if chosen is None:
        chosen = "chatml"
    run_task_block(config, emit, meter, runtime, model_label, fresh, (chosen,), "fresh")
    return chosen


def run_discovery(config, emit):
    rows = []
    for spec in config["tasks"]:
        rows.append(_emit_discovery(emit, spec))
    return rows


def run(config, emit, runtime, *, model_label, best_style=None, meter=None):
    if meter is None:
        meter = begin(config, emit)
        run_discovery(config, emit)
    chosen = record_model(config, emit, meter, runtime, model_label, best_style=best_style)
    return meter, chosen


def summarize(records, config):
    inspect = next((row for row in records if row.get("category") == "inspect"), {})
    choice = next((row for row in records if row.get("category") == "choice"), {})
    template = [row for row in records if row.get("category") == "template"]
    fresh = [row for row in records if row.get("category") == "fresh"]
    discovery = [row for row in records if row.get("category") == "discovery"]
    resources = [row for row in records if row.get("category") == "resources"]

    def compact(row):
        return {
            "id": row["id"], "model": row.get("model"),
            "prompt_style": row.get("prompt_style"),
            "raw_valid": row.get("raw_valid"),
            "placeholder": row.get("placeholder"),
            "syntax_valid": row.get("syntax_valid"),
            "executed": row.get("executed"),
            "public_passed": row.get("public_passed"),
            "semantic_correct": row.get("semantic_correct"),
            "completions": row.get("completions"),
            "equality_failure_in_revision": row.get("equality_failure_in_revision"),
            "operator_hint_in_revision": row.get("operator_hint_in_revision"),
            "comparison_changed": row.get("comparison_changed"),
            "comparison_ops_first": row.get("comparison_ops_first"),
            "comparison_ops_last": row.get("comparison_ops_last"),
            "cell_wall_s": row.get("cell_wall_s"),
            "combined_rss_mib": (row.get("memory") or {}).get("combined_rss_mib"),
            "server_rss_mib": (row.get("memory") or {}).get("server_rss_mib"),
        }

    return dict(
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learning_research_resumed=False,
        target_discovery="measured_separately_not_wired_to_assembler",
        inspect=dict(
            user_equals_raw=inspect.get("user_equals_raw"),
            gguf_has_chatml_tokens=inspect.get("gguf_has_chatml_tokens"),
            gguf_template_has_default_system=inspect.get("gguf_template_has_default_system"),
            chatml_has_im_start=(inspect.get("chatml_meta") or {}).get("rendered_has_im_start"),
            raw_has_im_start=(inspect.get("raw_meta") or {}).get("rendered_has_im_start"),
            format=inspect.get("format"),
            equality_failure=inspect.get("equality_failure"),
            operator_supplied=inspect.get("operator_supplied"),
            decoding=inspect.get("decoding"),
        ),
        best_style=choice.get("best_style"),
        template_rows=[compact(row) for row in template],
        fresh_rows=[compact(row) for row in fresh],
        discovery_rows=[{
            "id": row["id"],
            "path_correct": row.get("path_correct"),
            "symbol_correct": row.get("symbol_correct"),
            "action_correct": row.get("action_correct"),
            "target_correct": row.get("target_correct"),
            "used_public_tests": row.get("used_public_tests"),
            "reason": row.get("reason"),
        } for row in discovery],
        resources=[{
            "model": row.get("model"), "block": row.get("block"),
            "wall_s": row.get("wall_s"), "styles": row.get("styles"),
            "per_task": row.get("per_task"),
            "combined_rss_mib_after": (row.get("memory_after") or {}).get("combined_rss_mib"),
            "server_rss_mib_after": (row.get("memory_after") or {}).get("server_rss_mib"),
            "parent_rss_mib_after": (row.get("memory_after") or {}).get("parent_rss_mib"),
            "model_bytes": row.get("model_bytes"),
            "weight_file_is_not_memory": True,
        } for row in resources],
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )
