"""Frozen 1.5B recipe on harder features, with contract-acquisition records."""
from __future__ import annotations

import time
from typing import Any

from .capability_evidence import EventMeter, digest
from .constrained_edit import plan_constrained_edit
from .contract_revision_study import FORMAT, STYLE, propose_cell
from .interrupt_transfer import _assess
from .function_format import decoding_record, schema_for_format
from .input_contract import FROZEN_RECIPE, MAX_COMPLETIONS, acquire_contract, describe_input_contract
from .process_memory import sample_process_memory
from .repair_schema_memory import (
    capture_from_success, ordinary_template_apply, propose_retrieved_repair,
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
    "py_title_space", "py_mass_three_point", "py_hold_inclusive", "py_span_filled",
    "py_clip_floor",
}

REQUIRED_SUPPLIED_PASSES = ("py_rows_sum", "py_due_quote")
SUPPLIED_GATE = 4


def _task(spec):
    return type("T", (), {
        "files": spec["files"],
        "request": spec["request"],
        "public_tests": spec.get("public") or [],
        "docs": spec.get("docs") or [],
        "language": spec["language"],
    })()


def _plan(spec):
    discovered = discover_edit_target(spec["request"], spec["files"], spec.get("docs") or [])
    return plan_from_discovery(discovered), score_discovery(discovered, spec["gold_target"])


def run_frozen_cell(runtime, spec, meter, scope, acquired, max_tokens=128):
    plan, discovery = _plan(spec)
    if plan is None:
        raise ValueError("discovery_abstain:" + spec["id"])
    result = propose_cell(
        runtime, spec, "contract", meter, scope,
        wire_discovery=True, max_tokens=max_tokens,
        contract_block=acquired["block"],
        contract_origin=acquired["origin"],
        asked=acquired["asked"],
    )
    result["discovery"] = discovery
    result["acquisition"] = {
        "origin": acquired["origin"],
        "asked": acquired["asked"],
        "question": acquired.get("question"),
        "teacher": acquired.get("teacher"),
        "inferred_complete": (acquired.get("inferred") or {}).get("complete"),
        "inferred_fields": (acquired.get("inferred") or {}).get("fields"),
    }
    return result


def begin(config, emit):
    meter = EventMeter(emit)
    first = next(spec for spec in config["tasks"] if spec.get("phase") == "harder")
    plan = plan_constrained_edit(first["request"], first["files"], first.get("public") or [])
    emit(dict(
        kind="audit_manifest", config_hash=digest(config),
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learned_policy_promoted=False,
        learning_research_resumed=False,
        frozen_recipe=FROZEN_RECIPE,
        supplied_gate=SUPPLIED_GATE,
        required_supplied_passes=list(REQUIRED_SUPPLIED_PASSES),
        gemini=config.get("gemini", "NOT_RUN"),
        result_label="authored_source_development_pilot_not_confirmation",
        decoding=decoding_record(schema_for_format(FORMAT), int(config.get("model_max_tokens", 128))),
    ))
    emit(dict(
        kind="request_inspect", category="inspect", id=first["id"],
        frozen_recipe=FROZEN_RECIPE,
        supplied_contract=describe_input_contract(plan, first.get("public") or []),
        requirements=[spec["requirement"] for spec in config["tasks"] if spec.get("phase") == "harder"],
        format=FORMAT,
        prompt_style=STYLE,
        max_completions=MAX_COMPLETIONS,
    ))
    return meter


def record_harder(config, emit, meter, runtime):
    max_tokens = int(config.get("model_max_tokens", 128))
    started = time.perf_counter()
    memory_before = sample_process_memory(runtime)
    rows = []
    harder = [spec for spec in config["tasks"] if spec.get("phase") == "harder"]
    for spec in harder:
        if spec["id"] in CLOSED_TASK_IDS:
            raise ValueError("closed_task_id_reused:" + spec["id"])
        plan, _ = _plan(spec)
        for mode in ("supplied", "acquire"):
            hide = bool(spec.get("hide_examples_from_inference")) and mode == "acquire"
            source = "supplied" if mode == "supplied" else "inferred"
            acquired = acquire_contract(
                source, plan, spec["files"], spec.get("public") or [], hide_examples=hide,
            )
            scope = f"coder15:{acquired['origin']}:{spec['id']}"
            result = run_frozen_cell(runtime, spec, meter, scope, acquired, max_tokens)
            row = dict(
                kind="capability", area="harder_features", id=spec["id"],
                category=mode, method=acquired["origin"], model="coder15",
                family=spec.get("family"), role=spec.get("role"),
                used_private_to_accept=False, complete_correctness=False,
                **result,
            )
            emit(row)
            rows.append(row)
    emit(dict(
        kind="model_resources", category="resources", model="coder15",
        block="harder", wall_s=round(time.perf_counter() - started, 6),
        memory_before=memory_before, memory_after=sample_process_memory(runtime),
        per_task=[{
            "id": row["id"], "origin": row.get("contract_origin"),
            "cell_wall_s": row.get("cell_wall_s"),
            "calls_charged": row.get("calls_charged"),
            "combined_rss_mib": (row.get("memory") or {}).get("combined_rss_mib"),
        } for row in rows],
        model_bytes=config["models"]["coder15"]["bytes"],
        weight_file_is_not_memory=True,
    ))
    return rows


def gate_passed(rows: list[dict[str, Any]]) -> bool:
    supplied = [row for row in rows if row.get("category") == "supplied"]
    wins = {row["id"] for row in supplied if row.get("semantic_correct")}
    return len(wins) >= SUPPLIED_GATE and set(REQUIRED_SUPPLIED_PASSES) <= wins


def record_transfer(config, emit, meter, runtime, harder_rows):
    transfer = [spec for spec in config["tasks"] if spec.get("phase") == "transfer"]
    if not transfer:
        emit(dict(kind="memory_gate", category="gate", passed=False, ran=False, reason="no_transfer_task"))
        return []
    passed = gate_passed(harder_rows)
    emit(dict(
        kind="memory_gate", category="gate", passed=passed, ran=passed,
        supplied_private_correct=sum(
            1 for row in harder_rows if row.get("category") == "supplied" and row.get("semantic_correct")
        ),
        required=SUPPLIED_GATE,
        required_ids=list(REQUIRED_SUPPLIED_PASSES),
    ))
    if not passed:
        return []
    schemas = []
    for row in harder_rows:
        if row.get("category") != "supplied" or not row.get("semantic_correct"):
            continue
        if row.get("family") != "comparison_boundary":
            continue
        spec = next(item for item in config["tasks"] if item["id"] == row["id"])
        schema = capture_from_success(
            spec["family"], spec["request"], spec["files"],
            row.get("final_files") or spec["files"], spec.get("public") or [],
            {"calls": row.get("calls_charged"), "cell_wall_s": row.get("cell_wall_s")},
        )
        if schema is not None:
            schemas.append(schema)
    spec = transfer[0]
    started = time.perf_counter()
    retrieved = propose_retrieved_repair(
        schemas[0] if schemas else None, spec["request"], spec["files"], spec.get("public") or [],
    )
    template = ordinary_template_apply(spec.get("family") or "", spec["files"])
    experience_files = retrieved.files or spec["files"]
    experience_private = _assess(meter, "experience:" + spec["id"], spec, experience_files)
    template_private = _assess(
        meter, "template:" + spec["id"], spec, template or spec["files"],
    ) if template is not None else {"all_passed": False, "status": "no_template"}
    emit(dict(
        kind="capability", area="harder_features", id=spec["id"], category="experience",
        method="retrieved_repair", model="coder15", family=spec.get("family"),
        used_private_to_accept=False, complete_correctness=False,
        wire_discovery=True, calls_charged=0, complete_calls_saved=retrieved.decision == "apply",
        acquisition_cost=[schema.acquisition_cost for schema in schemas],
        retrieved_status=retrieved.decision, retrieved_reason=retrieved.reason,
        semantic_correct=bool(experience_private.get("all_passed")),
        template_semantic_correct=bool(template_private.get("all_passed")),
        harmful_reuse=bool(retrieved.decision == "apply" and not experience_private.get("all_passed")),
        private=experience_private,
    ))
    plan, _ = _plan(spec)
    acquired = acquire_contract("supplied", plan, spec["files"], spec.get("public") or [])
    scratch = run_frozen_cell(
        runtime, spec, meter, "scratch:" + spec["id"], acquired,
        int(config.get("model_max_tokens", 128)),
    )
    emit(dict(
        kind="capability", area="harder_features", id=spec["id"], category="scratch",
        method="frozen_recipe", model="coder15", family=spec.get("family"),
        used_private_to_accept=False, complete_correctness=False, **scratch,
    ))
    emit(dict(
        kind="model_resources", category="resources", model="coder15", block="transfer",
        wall_s=round(time.perf_counter() - started, 6),
        memory_after=sample_process_memory(runtime),
        weight_file_is_not_memory=True,
        model_bytes=config["models"]["coder15"]["bytes"],
    ))
    return [retrieved, scratch]


def record_model(config, emit, meter, runtime):
    harder = record_harder(config, emit, meter, runtime)
    record_transfer(config, emit, meter, runtime, harder)
    return harder


def summarize(records, config):
    inspect = next((row for row in records if row.get("category") == "inspect"), {})
    gate = next((row for row in records if row.get("category") == "gate"), {})
    supplied = [row for row in records if row.get("category") == "supplied"]
    acquire = [row for row in records if row.get("category") == "acquire"]
    experience = [row for row in records if row.get("category") == "experience"]
    scratch = [row for row in records if row.get("category") == "scratch"]
    resources = [row for row in records if row.get("category") == "resources"]

    def compact(row):
        discovery = row.get("discovery") or {}
        acquisition = row.get("acquisition") or {}
        return {
            "id": row["id"],
            "origin": row.get("contract_origin") or acquisition.get("origin"),
            "asked": row.get("asked") or acquisition.get("asked"),
            "target_correct": discovery.get("target_correct"),
            "executable_code": row.get("executable_code"),
            "behavioral_revision_attempted": row.get("behavioral_revision_attempted"),
            "behavioral_revision_success": row.get("behavioral_revision_success"),
            "public_passed": row.get("public_passed"),
            "semantic_correct": row.get("semantic_correct"),
            "calls_charged": row.get("calls_charged"),
            "cell_wall_s": row.get("cell_wall_s"),
            "combined_rss_mib": (row.get("memory") or {}).get("combined_rss_mib"),
        }

    return dict(
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learning_research_resumed=False,
        frozen_recipe=inspect.get("frozen_recipe") or FROZEN_RECIPE,
        supplied_rows=[compact(row) for row in supplied],
        acquire_rows=[compact(row) for row in acquire],
        gate=dict(
            passed=gate.get("passed"), ran=gate.get("ran"),
            supplied_private_correct=gate.get("supplied_private_correct"),
        ),
        experience_rows=[{
            "id": row["id"], "retrieved_status": row.get("retrieved_status"),
            "semantic_correct": row.get("semantic_correct"),
            "template_semantic_correct": row.get("template_semantic_correct"),
            "harmful_reuse": row.get("harmful_reuse"),
            "calls_charged": row.get("calls_charged"),
        } for row in experience],
        scratch_rows=[compact(row) for row in scratch],
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
