"""Compare function-output formats, reject placeholders, and retest the 1.5B coder."""
from __future__ import annotations

import resource
import time
from typing import Any

from .agent_loop_worker import run_worker_subprocess
from .capability_evidence import EventMeter, digest
from .constrained_edit import plan_constrained_edit
from .function_format import (
    FORMATS, choose_best_format, decoding_record, prompt_for_format,
    revision_feedback, schema_for_format, assemble_format_proposal,
)
from .interrupt_transfer import _assess


CLOSED_TASK_IDS = {
    "py_width_ok", "py_keep_exclusive", "py_pair_label", "py_cutoff_ambiguous",
    "py_hi_inclusive_src", "py_slug_join", "py_levy_then_credit", "py_retry_last",
    "py_cap_inclusive_src", "py_span_ok", "py_floor_ok", "py_reject_floor",
    "py_note_join", "py_threshold_fix", "py_mix_span", "py_doc_lie", "py_two_bugs",
    "py_src_cap_ok", "py_src_title_ok", "py_mark_join", "py_invoice_slug_feature",
    "py_span_three_point", "py_span_equal_only", "py_width_three_point_dev",
    "py_height_three_point_fresh", "py_depth_three_point", "py_tag_colon_feature",
}


def _rss_mib() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024), 3)


def _task(spec):
    return type("T", (), {
        "files": spec["files"],
        "request": spec["request"],
        "public_tests": spec.get("public") or [],
        "docs": spec.get("docs") or [],
        "language": spec["language"],
    })()


def _complete(runtime, prompt, schema, max_tokens, meter, scope, identity):
    def call(_):
        try:
            return runtime.complete(prompt, schema)
        except TypeError:
            return runtime.complete(prompt, schema)
    return meter.call(scope, "complete", identity, call, None)


def _eval_public(meter, scope, spec, files):
    return meter.call(scope, "worker", spec["id"],
                      lambda payload: run_worker_subprocess(payload, 10),
                      dict(language=spec["language"], files=files, cases=spec.get("public") or []))


def propose_format(runtime, spec, fmt, meter, scope, max_tokens=128):
    task = _task(spec)
    plan = plan_constrained_edit(spec["request"], spec["files"], spec.get("public") or [])
    schema = schema_for_format(fmt)
    decoding = decoding_record(schema, max_tokens)
    prompt = prompt_for_format(fmt, task, plan)
    raw = _complete(runtime, prompt, schema, max_tokens, meter, scope, spec["id"] + ":0")
    if type(raw) is not dict:
        raw = {"content": "", "telemetry": {}, "status": "error", "reason": str(raw)}
    assembled = assemble_format_proposal(
        fmt, raw.get("content") or "", spec["request"], spec["files"], spec.get("public") or [],
    )
    traces = [dict(
        round=1, prompt=prompt, decoding=decoding,
        raw_content=(raw.get("content") or "")[:800],
        telemetry=raw.get("telemetry"),
        **{k: assembled[k] for k in (
            "raw_valid", "raw_reason", "raw_excerpt", "normalized", "placeholder",
            "syntax_valid", "structurally_valid", "preview",
        )},
    )]
    public = None
    if assembled.get("placeholder"):
        feedback = revision_feedback(assembled["placeholder"])
        prompt2 = prompt_for_format(fmt, task, plan, feedback)
        raw2 = _complete(runtime, prompt2, schema, max_tokens, meter, scope, spec["id"] + ":1")
        if type(raw2) is not dict:
            raw2 = {"content": "", "telemetry": {}}
        assembled = assemble_format_proposal(
            fmt, raw2.get("content") or "", spec["request"], spec["files"], spec.get("public") or [],
        )
        traces.append(dict(
            round=2, prompt=prompt2, decoding=decoding,
            raw_content=(raw2.get("content") or "")[:800],
            telemetry=raw2.get("telemetry"),
            revision_of="placeholder",
            **{k: assembled[k] for k in (
                "raw_valid", "raw_reason", "raw_excerpt", "normalized", "placeholder",
                "syntax_valid", "structurally_valid", "preview",
            )},
        ))
    executed = False
    public_passed = False
    if assembled.get("structurally_valid") and assembled.get("patched_files"):
        public = _eval_public(meter, scope, spec, assembled["patched_files"])
        executed = public.get("status") in {"ok", "passed", None} or "results" in public
        if public.get("status") not in {"blocked_missing_runtime", "rejected"}:
            executed = True
        public_passed = bool(public.get("all_passed"))
        if not public_passed and assembled.get("placeholder") is None:
            feedback = revision_feedback(
                "public_tests_failed",
                public,
            )
            prompt3 = prompt_for_format(fmt, task, plan, feedback)
            if len(traces) < 2:
                raw3 = _complete(runtime, prompt3, schema, max_tokens, meter, scope, spec["id"] + ":rev")
                if type(raw3) is not dict:
                    raw3 = {"content": "", "telemetry": {}}
                assembled = assemble_format_proposal(
                    fmt, raw3.get("content") or "", spec["request"], spec["files"],
                    spec.get("public") or [],
                )
                traces.append(dict(
                    round=len(traces) + 1, prompt=prompt3, decoding=decoding,
                    raw_content=(raw3.get("content") or "")[:800],
                    telemetry=raw3.get("telemetry"),
                    revision_of="public_failure",
                    **{k: assembled[k] for k in (
                        "raw_valid", "raw_reason", "raw_excerpt", "normalized",
                        "placeholder", "syntax_valid", "structurally_valid", "preview",
                    )},
                ))
                if assembled.get("structurally_valid") and assembled.get("patched_files"):
                    public = _eval_public(meter, scope + ":rev", spec, assembled["patched_files"])
                    executed = True
                    public_passed = bool(public.get("all_passed"))
    private = _assess(
        meter, scope, spec,
        assembled.get("patched_files") or spec["files"],
    )
    return dict(
        format=fmt,
        plan=assembled.get("plan"),
        traces=traces,
        decoding=decoding,
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
    )


def run_formats(config, emit, meter, runtime, model_label, formats=FORMATS):
    max_tokens = int(config.get("model_max_tokens", 128))
    started = time.perf_counter()
    rss_before = _rss_mib()
    rows = []
    for spec in config["tasks"]:
        if spec["id"] in CLOSED_TASK_IDS:
            raise ValueError("closed_task_id_reused:" + spec["id"])
        for fmt in formats:
            scope = f"{model_label}:{fmt}:{spec['id']}"
            result = propose_format(runtime, spec, fmt, meter, scope, max_tokens)
            row = dict(
                kind="capability", area="function_format", id=spec["id"],
                category="format", method=fmt, model=model_label,
                family=spec.get("family"), role=spec.get("role"),
                used_private_to_accept=False, complete_correctness=False,
                **result,
            )
            emit(row)
            rows.append(row)
    return dict(
        rows=rows,
        wall_s=round(time.perf_counter() - started, 6),
        rss_mib_after=_rss_mib(),
        rss_mib_before=rss_before,
    )


def begin(config, emit):
    meter = EventMeter(emit)
    emit(dict(
        kind="audit_manifest", config_hash=digest(config),
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learned_policy_promoted=False,
        learning_research_resumed=False,
        target_discovery="not_implemented",
        gemini=config.get("gemini", "NOT_RUN"),
        result_label="authored_source_development_pilot_not_confirmation",
        decoding=decoding_record(None, int(config.get("model_max_tokens", 128))),
    ))
    inspect_task = config["tasks"][0]
    plan = plan_constrained_edit(
        inspect_task["request"], inspect_task["files"], inspect_task.get("public") or [],
    )
    emit(dict(
        kind="request_inspect", category="inspect", id=inspect_task["id"],
        decoding=decoding_record(schema_for_format("json_function"), int(config.get("model_max_tokens", 128))),
        prompts={fmt: prompt_for_format(fmt, _task(inspect_task), plan) for fmt in FORMATS},
        schemas={fmt: schema_for_format(fmt) for fmt in FORMATS},
        function_described_as="executable_python_source",
        chat_template=None,
        stop=None,
        target_from="public_test_entry_or_existing_symbol",
    ))
    return meter


def record_model_block(config, emit, meter, runtime, model_label, formats=FORMATS, best_format=None):
    from .function_format import format_score
    block = run_formats(config, emit, meter, runtime, model_label, formats=formats)
    emit(dict(
        kind="model_resources", category="resources", model=model_label, **block,
        model_bytes=config["models"][model_label]["bytes"], best_format=best_format,
    ))
    if model_label == "qwen05":
        best = choose_best_format(block["rows"])
        emit(dict(
            kind="format_choice", category="choice", best_format=best,
            scores={
                fmt: sum(format_score(row) for row in block["rows"] if row.get("format") == fmt)
                for fmt in FORMATS
            },
        ))
        return best
    return best_format


def run(config, emit, runtime, *, model_label, formats=None, best_format=None, meter=None):
    if meter is None:
        meter = begin(config, emit)
    chosen = record_model_block(
        config, emit, meter, runtime, model_label,
        formats=formats or FORMATS, best_format=best_format,
    )
    return meter, chosen


def summarize(records, config):
    formats = [row for row in records if row.get("category") == "format"]
    resources = [row for row in records if row.get("category") == "resources"]
    choice = next((row for row in records if row.get("category") == "choice"), {})
    inspect = next((row for row in records if row.get("category") == "inspect"), {})
    return dict(
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learning_research_resumed=False,
        target_discovery="not_implemented",
        inspect=dict(
            chat_template=inspect.get("chat_template"),
            stop=inspect.get("stop"),
            function_described_as=inspect.get("function_described_as"),
            decoding=inspect.get("decoding"),
        ),
        best_format=choice.get("best_format"),
        format_rows=[{
            "id": row["id"], "model": row.get("model"), "format": row.get("format"),
            "raw_valid": row.get("raw_valid"),
            "placeholder": row.get("placeholder"),
            "syntax_valid": row.get("syntax_valid"),
            "executed": row.get("executed"),
            "public_passed": row.get("public_passed"),
            "semantic_correct": row.get("semantic_correct"),
            "completions": row.get("completions"),
        } for row in formats],
        resources=[{
            "model": row.get("model"), "wall_s": row.get("wall_s"),
            "rss_mib_before": row.get("rss_mib_before"),
            "rss_mib_after": row.get("rss_mib_after"),
            "model_bytes": row.get("model_bytes"),
            "best_format": row.get("best_format"),
        } for row in resources],
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )
