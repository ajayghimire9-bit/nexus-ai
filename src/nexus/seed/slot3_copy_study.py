"""Development evaluation of slot-3 after a duplicated KeyError subscript."""
from __future__ import annotations

import time
from typing import Any

from .capability_evidence import EventMeter, digest
from .contract_revision_study import FORMAT, STYLE, propose_cell
from .function_format import decoding_record, schema_for_format
from .input_contract import FROZEN_RECIPE, MAX_COMPLETIONS, acquire_contract
from .interface_repair_study import (
    AUDIT_IDS, HISTORICAL_HARDER_SHA256, _bodies, _plan, replay_final,
)
from .process_memory import sample_process_memory
from .revision_feedback_audit import audit_saved_harder_revisions
from .slot3_repair_study import CLOSED_TASK_IDS as SLOT3_CLOSED
from .slot3_repair_study import public_covers_varied as _slot3_public_cover
from .worker_div_confirm_study import spec_requires_missing_or_empty


CLOSED_TASK_IDS = set(SLOT3_CLOSED) | {
    "py_lot_count", "py_job_slash", "py_part_div", "py_ok_pair",
}
WORKER_PROMPT_FREEZE = dict(
    FROZEN_RECIPE,
    worker_allows_div=True,
    worker_allows_keyword=True,
    worker_allows_fstring=True,
    numeric_compare="compare_python_result",
    envelope_unwrap=True,
    layered_public_feedback=True,
    structural_slot3=True,
    structural_slot3_copy=True,
)
TAG_FIELDS = ("post", "desk", "job", "unit", "role", "title", "kind", "name")


def _inputs(spec: dict[str, Any], field: str) -> list[dict[str, Any]]:
    return [case.get("input") or {} for case in spec.get(field) or []]


def public_covers_varied(spec: dict[str, Any]) -> bool:
    if not _slot3_public_cover(spec):
        return False
    req = (spec.get("requirement") or "").lower()
    inputs = _inputs(spec, "public")
    if "empty crates" in req and not any(inp.get("crates") == [] for inp in inputs):
        return False
    if "missing n" in req:
        if not any(
            any(isinstance(row, dict) and "n" not in row for row in (inp.get("crates") or []))
            for inp in inputs
        ):
            return False
    for field in ("post", "desk"):
        if f"missing {field}" in req and not any(field not in inp for inp in inputs):
            return False
    return True


def private_covers_missing_keys(spec: dict[str, Any]) -> bool:
    """Tag/join private tests must include a missing key disjoint from public."""
    if not spec_requires_missing_or_empty(spec):
        return True
    req = (spec.get("requirement") or "").lower()
    family = spec.get("family") or ""
    if family not in {"missing_fields"} and "slash" not in req and "joined" not in req:
        return True
    public = _inputs(spec, "public")
    private = _inputs(spec, "assessment")
    if not private:
        return False
    if any(inp in public for inp in private):
        return False
    named = [field for field in TAG_FIELDS if f"missing {field}" in req]
    if not named:
        return True
    return all(any(field not in inp for inp in private) for field in named)


def covers_varied(spec: dict[str, Any]) -> bool:
    return public_covers_varied(spec) and private_covers_missing_keys(spec)


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
        historical_supplied_private_correct=1,
        historical_rescoring=False,
        gemini=config.get("gemini", "NOT_RUN"),
        result_label="authored_source_development_pilot_not_confirmation",
        hard_deadline_s=config.get("hard_deadline_s"),
        decoding=decoding_record(schema_for_format(FORMAT), int(config.get("model_max_tokens", 128))),
    ))
    emit(dict(
        kind="request_inspect", category="inspect", id=first["id"],
        frozen_recipe=WORKER_PROMPT_FREEZE,
        public_includes_missing_or_empty=all(covers_varied(spec) for spec in config["tasks"]),
        format=FORMAT,
        prompt_style=STYLE,
        max_completions=MAX_COMPLETIONS,
        plan_symbol=plan.symbol,
        structural_slot3=True,
        structural_slot3_copy=True,
    ))
    if historical_records is not None:
        emit(dict(
            kind="revision_audit", category="audit",
            tasks=audit_saved_harder_revisions(historical_records, AUDIT_IDS),
        ))
    return meter


def record_model(config, emit, meter, runtime, deadline=None):
    max_tokens = int(config.get("model_max_tokens", 128))
    started = time.perf_counter()
    memory_before = sample_process_memory(runtime)
    rows = []
    blocked = None
    for spec in config["tasks"]:
        if deadline is not None and deadline.expired():
            blocked = "hard_deadline"
            break
        if spec["id"] in CLOSED_TASK_IDS:
            raise ValueError("closed_task_id_reused:" + spec["id"])
        plan = _plan(spec)
        acquired = acquire_contract("supplied", plan, spec["files"], spec.get("public") or [])
        result = propose_cell(
            runtime, spec, "contract", meter, "coder15:supplied:" + spec["id"],
            wire_discovery=True, max_tokens=max_tokens,
            contract_block=acquired["block"], contract_origin="supplied", asked=False,
        )
        row = dict(
            kind="capability", area="slot3_copy_confirm", id=spec["id"],
            category="confirm", method="supplied", model="coder15",
            family=spec.get("family"), role=spec.get("role"),
            used_private_to_accept=False, complete_correctness=False,
            attempt_bodies=_bodies(result),
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
            "structural_slot3_attempted": row.get("structural_slot3_attempted"),
            "structural_codes": row.get("structural_codes"),
        } for row in rows],
        model_bytes=config["models"]["coder15"]["bytes"],
        weight_file_is_not_memory=True,
        blocked_step=blocked,
    ))
    return rows, blocked


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
            "structural_slot3_attempted": row.get("structural_slot3_attempted"),
            "structural_codes": row.get("structural_codes"),
            "public_passed": row.get("public_passed"),
            "semantic_correct": row.get("semantic_correct"),
            "calls_charged": row.get("calls_charged"),
            "cell_wall_s": row.get("cell_wall_s"),
            "combined_rss_mib": (row.get("memory") or {}).get("combined_rss_mib"),
            "attempt_bodies": row.get("attempt_bodies"),
            "stages": [trace.get("stage") for trace in (row.get("traces") or [])],
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
