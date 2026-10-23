"""Frozen-recipe confirmation after compact sum-row TypeError repair."""
from __future__ import annotations

import time
from typing import Any

from .capability_evidence import EventMeter, digest
from .contract_revision_study import FORMAT, STYLE, propose_cell
from .function_format import decoding_record, schema_for_format
from .input_contract import FROZEN_RECIPE, MAX_COMPLETIONS
from .process_memory import sample_process_memory
from .revision_feedback_audit import audit_saved_harder_revisions
from .sum_row_repair import compact_supplied_contract
from .target_discovery import discover_edit_target, plan_from_discovery
from .worker_div_confirm_study import (
    CLOSED_TASK_IDS as DIV_CLOSED,
    public_covers_required_edges,
)


CLOSED_TASK_IDS = set(DIV_CLOSED) | {
    "py_bag_total", "py_flag_absent", "py_rate_div", "py_enter_both",
}
HISTORICAL_HARDER_SHA256 = "31713e4d04ef63ca296ef4c78797ca11e4c87203ddce845ea82c3956646dbdc2"
HISTORICAL_DIV_CONFIRM_SHA256 = "490ab00"
AUDIT_IDS = ("py_rows_sum", "py_mark_absent", "py_inside_span")
WORKER_PROMPT_FREEZE = dict(
    FROZEN_RECIPE,
    worker_allows_div=True,
    numeric_compare="compare_python_result",
    compact_sum_row_repair=True,
    worker_allows_keyword=True,
)


def _plan(spec):
    discovered = discover_edit_target(spec["request"], spec["files"], spec.get("docs") or [])
    return plan_from_discovery(discovered)


def _bodies(row: dict[str, Any]) -> list[str]:
    out = []
    for trace in row.get("traces") or []:
        preview = (trace.get("preview") or {})
        out.append(str(preview.get("new_excerpt") or trace.get("raw_excerpt") or ""))
    return out


def begin(config, emit, historical_records=None):
    meter = EventMeter(emit)
    first = config["tasks"][0]
    plan = _plan(first)
    emit(dict(
        kind="audit_manifest", config_hash=digest(config),
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learned_policy_promoted=False,
        learning_research_resumed=False,
        frozen_recipe=WORKER_PROMPT_FREEZE,
        historical_harder_sha256=HISTORICAL_HARDER_SHA256,
        historical_div_confirm_sha256=config.get("historical_div_confirm_sha256"),
        historical_supplied_private_correct=1,
        historical_rescoring=False,
        gemini=config.get("gemini", "NOT_RUN"),
        result_label="authored_source_development_pilot_not_confirmation",
        decoding=decoding_record(schema_for_format(FORMAT), int(config.get("model_max_tokens", 128))),
    ))
    emit(dict(
        kind="request_inspect", category="inspect", id=first["id"],
        frozen_recipe=WORKER_PROMPT_FREEZE,
        supplied_contract=compact_supplied_contract(plan, first.get("public") or []),
        public_includes_missing_or_empty=all(
            public_covers_required_edges(spec) for spec in config["tasks"]
        ),
        format=FORMAT,
        prompt_style=STYLE,
        max_completions=MAX_COMPLETIONS,
        worker_allows_div=True,
        compact_sum_row_repair=True,
    ))
    if historical_records is not None:
        emit(dict(
            kind="revision_audit", category="audit",
            tasks=audit_saved_harder_revisions(historical_records, AUDIT_IDS),
        ))
    return meter


def record_model(config, emit, meter, runtime):
    max_tokens = int(config.get("model_max_tokens", 128))
    started = time.perf_counter()
    memory_before = sample_process_memory(runtime)
    rows = []
    for spec in config["tasks"]:
        if spec["id"] in CLOSED_TASK_IDS:
            raise ValueError("closed_task_id_reused:" + spec["id"])
        plan = _plan(spec)
        result = propose_cell(
            runtime, spec, "contract", meter, "coder15:supplied:" + spec["id"],
            wire_discovery=True, max_tokens=max_tokens,
            contract_block=compact_supplied_contract(plan, spec.get("public") or []),
            contract_origin="supplied", asked=False, compact_prompts=False,
        )
        bodies = _bodies(result)
        row = dict(
            kind="capability", area="sum_row_repair_confirm", id=spec["id"],
            category="confirm", method="supplied", model="coder15",
            family=spec.get("family"), role=spec.get("role"),
            used_private_to_accept=False, complete_correctness=False,
            attempt_bodies=bodies,
            **result,
        )
        emit(row)
        rows.append(row)
    emit(dict(
        kind="model_resources", category="resources", model="coder15",
        block="confirm", wall_s=round(time.perf_counter() - started, 6),
        memory_before=memory_before, memory_after=sample_process_memory(runtime),
        per_task=[{
            "id": row["id"], "cell_wall_s": row.get("cell_wall_s"),
            "calls_charged": row.get("calls_charged"),
            "combined_rss_mib": (row.get("memory") or {}).get("combined_rss_mib"),
            "attempt_bodies": row.get("attempt_bodies"),
        } for row in rows],
        model_bytes=config["models"]["coder15"]["bytes"],
        weight_file_is_not_memory=True,
    ))
    return rows


def summarize(records, config):
    inspect = next((row for row in records if row.get("category") == "inspect"), {})
    audit = next((row for row in records if row.get("category") == "audit"), {})
    confirm = [row for row in records if row.get("category") == "confirm"]
    resources = [row for row in records if row.get("category") == "resources"]
    return dict(
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learning_research_resumed=False,
        historical_supplied_private_correct=1,
        historical_rescoring=False,
        frozen_recipe=inspect.get("frozen_recipe") or WORKER_PROMPT_FREEZE,
        revision_audit=audit.get("tasks") or [],
        confirm_rows=[{
            "id": row["id"],
            "target_correct": (row.get("discovery") or {}).get("target_correct"),
            "executable_code": row.get("executable_code"),
            "behavioral_revision_attempted": row.get("behavioral_revision_attempted"),
            "public_passed": row.get("public_passed"),
            "semantic_correct": row.get("semantic_correct"),
            "calls_charged": row.get("calls_charged"),
            "cell_wall_s": row.get("cell_wall_s"),
            "combined_rss_mib": (row.get("memory") or {}).get("combined_rss_mib"),
            "attempt_bodies": row.get("attempt_bodies"),
        } for row in confirm],
        resources=[{
            "model": row.get("model"), "block": row.get("block"),
            "wall_s": row.get("wall_s"),
            "combined_rss_mib_after": (row.get("memory_after") or {}).get("combined_rss_mib"),
            "model_bytes": row.get("model_bytes"),
            "weight_file_is_not_memory": True,
        } for row in resources],
        learning_to_learn_established=False,
        verdict="DEVELOPMENT_PILOT_ONLY",
    )
