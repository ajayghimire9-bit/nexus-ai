"""Explicit input contract, two-stage revision, and discovery-wired end-to-end."""
from __future__ import annotations

import time
from typing import Any

from .agent_loop_worker import run_worker_subprocess
from .capability_evidence import EventMeter, digest
from .chat_template import render_prompt
from .constrained_edit import plan_constrained_edit
from .function_format import (
    assemble_format_proposal, decoding_record, revision_feedback, schema_for_format,
)
from .input_contract import (
    MAX_COMPLETIONS, PROMPT_VARIANTS, build_user_prompt, choose_best_variant,
    describe_input_contract, uses_dict_fields, variant_score,
)
from .interrupt_transfer import _assess
from .process_memory import sample_process_memory
from .public_failure import behavioral_feedback, comparison_ops, operator_hint_present
from .sum_row_repair import (
    compact_behavioral_feedback,
    compact_initial_prompt,
    compact_revision_prompt,
    needs_compact_sum_repair,
    reject_unprojected_sum,
)
from .target_discovery import discover_edit_target, plan_from_discovery, score_discovery


CLOSED_TASK_IDS = {
    "py_width_ok", "py_keep_exclusive", "py_pair_label", "py_cutoff_ambiguous",
    "py_hi_inclusive_src", "py_slug_join", "py_levy_then_credit", "py_retry_last",
    "py_cap_inclusive_src", "py_span_ok", "py_floor_ok", "py_reject_floor",
    "py_note_join", "py_threshold_fix", "py_mix_span", "py_doc_lie", "py_two_bugs",
    "py_src_cap_ok", "py_src_title_ok", "py_mark_join", "py_invoice_slug_feature",
    "py_span_three_point", "py_span_equal_only", "py_width_three_point_dev",
    "py_height_three_point_fresh", "py_depth_three_point", "py_tag_colon_feature",
    "py_level_three_point", "py_code_colon", "py_score_three_point", "py_mark_dash",
    "py_slug_space", "py_ready_status", "py_pair_slash", "py_discover_two_files",
}

FORMAT = "json_body"
STYLE = "chatml"


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


def _eval_public(meter, scope, spec, files, identity=None):
    return meter.call(
        scope, "worker", identity or spec["id"],
        lambda payload: run_worker_subprocess(payload, 10),
        dict(language=spec["language"], files=files, cases=spec.get("public") or []),
    )


def _body_excerpt(assembled: dict[str, Any]) -> str:
    preview = assembled.get("preview") or {}
    return str(preview.get("new_excerpt") or assembled.get("raw_excerpt") or "")


def _assemble(content, spec, plan):
    return assemble_format_proposal(
        FORMAT, content, spec["request"], spec["files"], spec.get("public") or [], plan=plan,
    )


def _trace(assembled, **extra):
    row = {k: assembled[k] for k in (
        "raw_valid", "raw_reason", "raw_excerpt", "normalized", "placeholder",
        "syntax_valid", "structurally_valid", "preview",
    )}
    row["comparison_ops"] = comparison_ops(_body_excerpt(assembled))
    row.update(extra)
    return row


def propose_cell(
    runtime, spec, variant, meter, scope, *, wire_discovery, max_tokens=128,
    contract_block=None, contract_origin=None, asked=False, compact_prompts=False,
):
    started = time.perf_counter()
    task = _task(spec)
    discovered = discover_edit_target(spec["request"], spec["files"], spec.get("docs") or [])
    discovery = score_discovery(discovered, spec["gold_target"])
    if wire_discovery:
        plan = plan_from_discovery(discovered)
        target_from = "discovery"
    else:
        plan = plan_constrained_edit(spec["request"], spec["files"], spec.get("public") or [])
        target_from = "public_test_entry_or_existing_symbol"
    if plan is None:
        return dict(
            format=FORMAT, prompt_style=STYLE, prompt_variant=variant,
            contract_origin=contract_origin, asked=asked,
            target_from=target_from, wire_discovery=wire_discovery,
            discovery=discovery, plan=None, traces=[],
            placeholder="discovery_abstain", syntax_valid=False, executed=False,
            public_passed=False, semantic_correct=False, structurally_valid=False,
            executable_code=False, completions=0, calls_charged=0,
            format_repair_attempted=False, format_repair_success=False,
            behavioral_revision_attempted=False, behavioral_revision_success=False,
            uses_dict_fields=False, cell_wall_s=round(time.perf_counter() - started, 6),
            complete_wall_s=0, memory=sample_process_memory(runtime),
            discovery_blocked=True,
        )
    schema = schema_for_format(FORMAT)
    decoding = decoding_record(schema, max_tokens)
    if compact_prompts:
        user_prompt = compact_initial_prompt(plan, spec)
    else:
        user_prompt = build_user_prompt(variant, task, plan, contract_block=contract_block)
    prompt, render = render_prompt(STYLE, user_prompt)
    raw = _complete(runtime, prompt, schema, meter, scope, spec["id"] + ":0")
    if type(raw) is not dict:
        raw = {"content": "", "telemetry": {}}
    assembled = _assemble(raw.get("content") or "", spec, plan)
    traces = [_trace(
        assembled, round=1, stage="initial", user_prompt=user_prompt,
        prompt_reached_model=prompt, render=render, decoding=decoding,
        raw_content=(raw.get("content") or "")[:800], telemetry=raw.get("telemetry"),
    )]
    format_attempted = False
    format_success = False
    if (assembled.get("placeholder") or not assembled.get("syntax_valid")) and len(traces) < MAX_COMPLETIONS:
        format_attempted = True
        feedback = revision_feedback(assembled.get("placeholder") or assembled.get("raw_reason") or "malformed")
        if compact_prompts:
            user2 = compact_revision_prompt(plan, "", {
                "instruction": "JSON body was empty or invalid. Return {\"body\": \"...\"} only.",
                "failed_cases": [],
            })
        else:
            user2 = build_user_prompt(variant, task, plan, feedback, contract_block=contract_block)
        prompt2, render2 = render_prompt(STYLE, user2)
        raw2 = _complete(runtime, prompt2, schema, meter, scope, spec["id"] + ":format")
        if type(raw2) is not dict:
            raw2 = {"content": "", "telemetry": {}}
        assembled = _assemble(raw2.get("content") or "", spec, plan)
        format_success = bool(assembled.get("syntax_valid") and assembled.get("placeholder") is None)
        traces.append(_trace(
            assembled, round=2, stage="format", revision_of="format",
            user_prompt=user2, prompt_reached_model=prompt2, render=render2,
            decoding=decoding, raw_content=(raw2.get("content") or "")[:800],
            telemetry=raw2.get("telemetry"),
            operator_hint_in_revision=operator_hint_present(user2),
        ))
    elif assembled.get("syntax_valid") and assembled.get("placeholder") is None:
        format_success = True
    public = None
    executed = False
    public_passed = False
    behavior_attempted = False
    behavior_success = False
    three_point = False
    if assembled.get("structurally_valid") and assembled.get("patched_files"):
        public = _eval_public(meter, scope, spec, assembled["patched_files"])
        executed = public.get("status") not in {"blocked_missing_runtime", "rejected"}
        public_passed = bool(public.get("all_passed"))
        if public_passed:
            behavior_success = True
        elif len(traces) < MAX_COMPLETIONS:
            behavior_attempted = True
            prior_body = _body_excerpt(assembled)
            if compact_prompts or needs_compact_sum_repair(public, prior_body):
                feedback = compact_behavioral_feedback(
                    public, spec.get("public") or [], prior_body,
                )
                user3 = compact_revision_prompt(plan, prior_body, feedback)
            else:
                feedback = behavioral_feedback(public, spec.get("public") or [])
                user3 = build_user_prompt(
                    variant, task, plan, feedback, contract_block=contract_block,
                )
            three_point = bool(feedback.get("three_point_evidence"))
            prompt3, render3 = render_prompt(STYLE, user3)
            raw3 = _complete(runtime, prompt3, schema, meter, scope, spec["id"] + ":behavior")
            if type(raw3) is not dict:
                raw3 = {"content": "", "telemetry": {}}
            assembled = _assemble(raw3.get("content") or "", spec, plan)
            traces.append(_trace(
                assembled, round=len(traces) + 1, stage="behavior",
                revision_of="public_failure", user_prompt=user3,
                prompt_reached_model=prompt3, render=render3, decoding=decoding,
                raw_content=(raw3.get("content") or "")[:800],
                telemetry=raw3.get("telemetry"),
                three_point_evidence=three_point,
                bands_present=feedback.get("bands_present"),
                operator_hint_in_revision=operator_hint_present(user3),
                operator_supplied=feedback.get("operator_supplied"),
                failed_cases=feedback.get("failed_cases"),
                compact_revision=compact_prompts or needs_compact_sum_repair(public, prior_body),
            ))
            reject = reject_unprojected_sum(prior_body, _body_excerpt(assembled), public)
            traces[-1]["unprojected_sum_rejected"] = bool(reject)
            traces[-1]["reject_reason"] = reject
            if reject and len(traces) < MAX_COMPLETIONS:
                feedback2 = {
                    "validation_error": "unprojected_sum",
                    "instruction": reject,
                    "failed_expression": prior_body.replace("\n", " ").strip()[:200],
                    "failed_cases": feedback.get("failed_cases") or [],
                }
                user4 = compact_revision_prompt(plan, _body_excerpt(assembled), feedback2)
                prompt4, render4 = render_prompt(STYLE, user4)
                raw4 = _complete(
                    runtime, prompt4, schema, meter, scope, spec["id"] + ":behavior_reject",
                )
                if type(raw4) is not dict:
                    raw4 = {"content": "", "telemetry": {}}
                assembled = _assemble(raw4.get("content") or "", spec, plan)
                traces.append(_trace(
                    assembled, round=len(traces) + 1, stage="behavior_reject",
                    revision_of="unprojected_sum", user_prompt=user4,
                    prompt_reached_model=prompt4, render=render4, decoding=decoding,
                    raw_content=(raw4.get("content") or "")[:800],
                    telemetry=raw4.get("telemetry"),
                    operator_hint_in_revision=operator_hint_present(user4),
                    failed_cases=feedback2.get("failed_cases"),
                    compact_revision=True,
                ))
                reject = reject_unprojected_sum(prior_body, _body_excerpt(assembled), public)
                traces[-1]["unprojected_sum_rejected"] = bool(reject)
                traces[-1]["reject_reason"] = reject
            if (
                not reject
                and assembled.get("structurally_valid")
                and assembled.get("patched_files")
            ):
                public = _eval_public(
                    meter, scope + ":rev", spec, assembled["patched_files"], spec["id"] + ":rev",
                )
                executed = True
                public_passed = bool(public.get("all_passed"))
                behavior_success = public_passed
    private = _assess(meter, scope, spec, assembled.get("patched_files") or spec["files"])
    keys = list((spec.get("public") or [{}])[0].get("input") or {})
    body = _body_excerpt(assembled)
    complete_wall = sum(
        float((trace.get("telemetry") or {}).get("request_wall_s") or 0) for trace in traces
    )
    return dict(
        format=FORMAT,
        prompt_style=STYLE,
        prompt_variant=variant,
        contract_origin=contract_origin or ("supplied" if variant == "contract" else None),
        asked=asked,
        target_from=target_from,
        wire_discovery=wire_discovery,
        discovery=discovery,
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
        executable_code=bool(
            assembled.get("syntax_valid") and assembled.get("placeholder") is None
            and assembled.get("structurally_valid")
        ),
        final_files=assembled.get("patched_files") or spec["files"],
        raw_valid=assembled.get("raw_valid"),
        normalized=assembled.get("normalized"),
        completions=len(traces),
        calls_charged=len(traces),
        format_repair_attempted=format_attempted,
        format_repair_success=format_success,
        behavioral_revision_attempted=behavior_attempted,
        behavioral_revision_success=behavior_success,
        three_point_in_revision=three_point,
        operator_hint_in_revision=any(trace.get("operator_hint_in_revision") for trace in traces),
        uses_dict_fields=uses_dict_fields(body, keys),
        comparison_ops_first=traces[0].get("comparison_ops") if traces else [],
        comparison_ops_last=traces[-1].get("comparison_ops") if traces else [],
        comparison_changed=bool(traces) and traces[0].get("comparison_ops") != traces[-1].get("comparison_ops"),
        cell_wall_s=round(time.perf_counter() - started, 6),
        complete_wall_s=round(complete_wall, 6),
        memory=sample_process_memory(runtime),
        discovery_blocked=False,
    )


def begin(config, emit):
    meter = EventMeter(emit)
    first = next(spec for spec in config["tasks"] if spec.get("phase") == "contract")
    plan = plan_constrained_edit(first["request"], first["files"], first.get("public") or [])
    task = _task(first)
    existing = build_user_prompt("existing", task, plan)
    contract = build_user_prompt("contract", task, plan)
    emit(dict(
        kind="audit_manifest", config_hash=digest(config),
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learned_policy_promoted=False,
        learning_research_resumed=False,
        target_discovery="wired_on_e2e_only",
        gemini=config.get("gemini", "NOT_RUN"),
        result_label="authored_source_development_pilot_not_confirmation",
        max_completions=MAX_COMPLETIONS,
        decoding=decoding_record(schema_for_format(FORMAT), int(config.get("model_max_tokens", 128))),
    ))
    emit(dict(
        kind="request_inspect", category="inspect", id=first["id"],
        existing_prompt=existing,
        contract_prompt=contract,
        contract_block=describe_input_contract(plan, first.get("public") or []),
        contract_has_signature="Signature: def " in contract,
        existing_has_signature="Signature: def " not in existing,
        user_equal_except_contract=contract.endswith(existing) or existing in contract,
        format=FORMAT,
        prompt_style=STYLE,
        max_completions=MAX_COMPLETIONS,
        operator_supplied=False,
    ))
    return meter


def run_task_block(config, emit, meter, runtime, model_label, tasks, variants, category, *, wire_discovery):
    max_tokens = int(config.get("model_max_tokens", 128))
    started = time.perf_counter()
    memory_before = sample_process_memory(runtime)
    rows = []
    for spec in tasks:
        if spec["id"] in CLOSED_TASK_IDS:
            raise ValueError("closed_task_id_reused:" + spec["id"])
        for variant in variants:
            scope = f"{model_label}:{variant}:{spec['id']}"
            result = propose_cell(
                runtime, spec, variant, meter, scope,
                wire_discovery=wire_discovery, max_tokens=max_tokens,
            )
            row = dict(
                kind="capability", area="contract_revision", id=spec["id"],
                category=category, method=variant, model=model_label,
                family=spec.get("family"), role=spec.get("role"),
                used_private_to_accept=False, complete_correctness=False,
                **result,
            )
            emit(row)
            rows.append(row)
    memory_after = sample_process_memory(runtime)
    emit(dict(
        kind="model_resources", category="resources", model=model_label,
        block=category, variants=list(variants), wire_discovery=wire_discovery,
        wall_s=round(time.perf_counter() - started, 6),
        memory_before=memory_before, memory_after=memory_after,
        per_task=[{
            "id": row["id"], "prompt_variant": row.get("prompt_variant"),
            "cell_wall_s": row.get("cell_wall_s"),
            "complete_wall_s": row.get("complete_wall_s"),
            "calls_charged": row.get("calls_charged"),
            "combined_rss_mib": (row.get("memory") or {}).get("combined_rss_mib"),
            "server_rss_mib": (row.get("memory") or {}).get("server_rss_mib"),
            "parent_rss_mib": (row.get("memory") or {}).get("parent_rss_mib"),
        } for row in rows],
        model_bytes=config["models"][model_label]["bytes"],
        weight_file_is_not_memory=True,
    ))
    return rows


def record_model(config, emit, meter, runtime, model_label, *, best_variant=None):
    contract_tasks = [spec for spec in config["tasks"] if spec.get("phase") == "contract"]
    e2e_tasks = [spec for spec in config["tasks"] if spec.get("phase") == "e2e"]
    contract_rows = run_task_block(
        config, emit, meter, runtime, model_label, contract_tasks, PROMPT_VARIANTS,
        "contract", wire_discovery=False,
    )
    chosen = best_variant
    if model_label == "qwen05":
        chosen = choose_best_variant(contract_rows)
        emit(dict(
            kind="variant_choice", category="choice", best_variant=chosen,
            scores={
                variant: sum(variant_score(row) for row in contract_rows if row.get("prompt_variant") == variant)
                for variant in PROMPT_VARIANTS
            },
        ))
    if chosen is None:
        chosen = "contract"
    run_task_block(
        config, emit, meter, runtime, model_label, e2e_tasks, (chosen,),
        "e2e", wire_discovery=True,
    )
    return chosen


def summarize(records, config):
    inspect = next((row for row in records if row.get("category") == "inspect"), {})
    choice = next((row for row in records if row.get("category") == "choice"), {})
    contract = [row for row in records if row.get("category") == "contract"]
    e2e = [row for row in records if row.get("category") == "e2e"]
    resources = [row for row in records if row.get("category") == "resources"]

    def compact(row):
        discovery = row.get("discovery") or {}
        return {
            "id": row["id"], "model": row.get("model"),
            "prompt_variant": row.get("prompt_variant"),
            "wire_discovery": row.get("wire_discovery"),
            "target_correct": discovery.get("target_correct"),
            "executable_code": row.get("executable_code"),
            "format_repair_attempted": row.get("format_repair_attempted"),
            "format_repair_success": row.get("format_repair_success"),
            "behavioral_revision_attempted": row.get("behavioral_revision_attempted"),
            "behavioral_revision_success": row.get("behavioral_revision_success"),
            "public_passed": row.get("public_passed"),
            "semantic_correct": row.get("semantic_correct"),
            "uses_dict_fields": row.get("uses_dict_fields"),
            "calls_charged": row.get("calls_charged"),
            "three_point_in_revision": row.get("three_point_in_revision"),
            "operator_hint_in_revision": row.get("operator_hint_in_revision"),
            "cell_wall_s": row.get("cell_wall_s"),
            "combined_rss_mib": (row.get("memory") or {}).get("combined_rss_mib"),
        }

    return dict(
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learning_research_resumed=False,
        target_discovery="wired_on_e2e_only",
        inspect=dict(
            contract_has_signature=inspect.get("contract_has_signature"),
            existing_has_signature=inspect.get("existing_has_signature"),
            user_equal_except_contract=inspect.get("user_equal_except_contract"),
            format=inspect.get("format"),
            prompt_style=inspect.get("prompt_style"),
            max_completions=inspect.get("max_completions"),
        ),
        best_variant=choice.get("best_variant"),
        contract_rows=[compact(row) for row in contract],
        e2e_rows=[compact(row) for row in e2e],
        resources=[{
            "model": row.get("model"), "block": row.get("block"),
            "wall_s": row.get("wall_s"), "variants": row.get("variants"),
            "wire_discovery": row.get("wire_discovery"),
            "per_task": row.get("per_task"),
            "combined_rss_mib_after": (row.get("memory_after") or {}).get("combined_rss_mib"),
            "server_rss_mib_after": (row.get("memory_after") or {}).get("server_rss_mib"),
            "model_bytes": row.get("model_bytes"),
            "weight_file_is_not_memory": True,
        } for row in resources],
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )
