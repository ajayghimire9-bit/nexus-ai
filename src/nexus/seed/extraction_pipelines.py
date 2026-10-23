"""Direct vs extract vs extract-plus-output-assembly on fresh list tasks.

Output assembly is programmer-supplied: a Boolean helper plus a
deterministic yes/no wrapper. Non-Boolean helper results are rejected
without Python truthiness. List operators are not chosen for the model.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .chat_template import render_prompt
from .constrained_edit import plan_constrained_edit
from .extraction_acquire import acquire_extraction_contract, ensure_requirement_equality
from .extraction_contract import (
    boolean_helper_public, describe_helper_output_contract, describe_output_contract,
    helper_boolean_behavior, make_contract, preview_extraction, wrap_transform_assemble,
    wrapper_uses_silent_default, yes_no_assembly_eligible,
)
from .extraction_path import (
    _echo, cost_block, generate_direct, generate_extract, score_assembled_task,
    with_output_docs,
)
from .function_format import assemble_format_proposal, prompt_for_format
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .recovery_failure_bank import classify_failure, public_errors, target_source
from .recovery_live import _prompt_task, model_complete

CALL_CAP = 36
WALL_CAP_S = 240.0
PIPELINES = ("direct", "extract", "extract_assemble")
OPERATOR_ASSISTANCE = False
YES_NO = ("yes", "no")
OPENED = (
    "assess_place", "assess_order", "assess_arith", "assess_cond",
    "assess_list", "assess_nested", "assess_label", "assess_remainder",
    "assess_all_ok", "assess_has_city", "dev_spread", "dev_any_hot",
    "dev_has_tag", "dev_at_least", "dev_box", "dev_note",
    "inform_at_least", "inform_nested", "inform_note",
)


def boolean_scalar_request(task: dict[str, Any]) -> str:
    contract = task["contract"]
    args = ", ".join(row["name"] for row in contract["fields"])
    behavior = helper_boolean_behavior(contract["behavior"])
    return f"Create function {contract['transform_symbol']}({args}) that {behavior}."


def helper_not_boolean(public: dict[str, Any]) -> bool:
    for item in public.get("results") or []:
        if item.get("output_assembly_error") == "expected Boolean":
            return True
        error = str(item.get("error") or "")
        if "expected Boolean" in error:
            return True
    return False


def generate_extract_assemble(runtime, task: dict[str, Any],
                              clock: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    contract = task["contract"]
    if not yes_no_assembly_eligible(task["request"], contract):
        raise ValueError("output_assembly_ineligible")
    bool_cases = boolean_helper_public(contract, task["public"])
    request = boolean_scalar_request(task)
    helper_task = dict(task, request=request, public=bool_cases, docs=[{
        "title": "helper output contract",
        "content": describe_helper_output_contract(),
    }])
    if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
        raise TimeoutError("extraction_pipeline_cap")
    plan = plan_constrained_edit(request, helper_task["files"], bool_cases)
    user = prompt_for_format("json_body", _prompt_task(helper_task, helper_task["files"]), plan, None)
    prompt, _meta = render_prompt("chatml", user)
    raw = model_complete(runtime, prompt)
    clock["calls"] += 1
    clock["inference_ran"] += int(raw["inference_ran"])
    assembled = assemble_format_proposal(
        "json_body", raw["content"], request, helper_task["files"], bool_cases, plan=plan,
    )
    transform_files = assembled.get("patched_files") or dict(task["files"])
    extract_started = time.perf_counter()
    transform_source = transform_files.get(plan.path, "")
    wrapper_source = wrap_transform_assemble(contract, transform_source)
    wrapped_files = dict(task["files"])
    wrapped_files[plan.path] = wrapper_source
    extraction_s = time.perf_counter() - extract_started
    validate_started = time.perf_counter()
    scored = score_assembled_task(task, wrapped_files)
    validation_s = time.perf_counter() - validate_started
    preview = preview_extraction(plan, transform_source, contract, wrapper_source)
    preview["output_assembly"] = dict(
        programmer_supplied=True,
        learned_output_mapping=False,
        helper_return_type="bool",
        labels={"True": "yes", "False": "no"},
        truthiness_conversion=False,
        trusted_host_check=True,
        operator_assistance=OPERATOR_ASSISTANCE,
    )
    cost = cost_block(0.0, extraction_s, raw["wall_s"], validation_s,
                      time.perf_counter() - started, 1)
    cost["assembly_s"] = round(extraction_s, 6)
    cost["programmer_supplied_output_assembly"] = True
    cost["operator_assistance"] = OPERATOR_ASSISTANCE
    return dict(
        path="extract_assemble",
        files=wrapped_files,
        preview=preview,
        public_passed=scored["public_passed"],
        private_passed=scored["private_passed"],
        failed=not scored["public_passed"],
        failure_type=classify_failure(scored["public"]),
        errors=public_errors(scored["public"]),
        output_contract_violations=scored["output_contract_violations"],
        helper_not_boolean=helper_not_boolean(scored["public"]) or helper_not_boolean(scored["private"]),
        current_function=wrapper_source,
        tested_symbol=contract["symbol"],
        transform_symbol=contract["transform_symbol"],
        silent_default=wrapper_uses_silent_default(wrapper_source),
        output_assembly_applied=True,
        programmer_supplied_output_assembly=True,
        operator_assistance=OPERATOR_ASSISTANCE,
        shared_extract=False,
        cost=cost,
        raw=raw["content"][:400],
        structurally_valid=bool(assembled.get("structurally_valid")),
        public=scored["public"],
        private=scored["private"],
    )


def _task(task_id: str, split: str, family: str, request: str, filename: str,
          symbol: str, fields: list[dict[str, Any]], behavior: str,
          public: list[tuple[dict[str, Any], Any]],
          private: list[tuple[dict[str, Any], Any]],
          reference, *, docs: list[dict[str, str]] | None = None,
          output_type: str | None = None, allowed_values: list[Any] | None = None) -> dict[str, Any]:
    entry = filename.removesuffix(".py") + "." + symbol
    contract = make_contract(symbol, fields, behavior, output_type, allowed_values)
    notes = list(docs or [])
    notes.append({"title": "output contract", "content": describe_output_contract(contract)})
    return dict(
        task_id=task_id,
        split=split,
        family=family,
        request=request,
        files=_echo(filename),
        public=[dict(entry=entry, input=inp, expected=exp) for inp, exp in public],
        private=[dict(entry=entry, input=inp, expected=exp) for inp, exp in private],
        contract=contract,
        docs=notes,
        reference=reference,
        origin="authored_extraction_pipelines",
        output_assembly_eligible=yes_no_assembly_eligible(request, contract),
    )


def pipeline_catalogue() -> list[dict[str, Any]]:
    return [
        _task(
            "dev_mark_ok", "development", "scalar_bound",
            "Create function mark_ok(item) that returns yes if score is at least the mark, otherwise no.",
            "mark.py", "mark_ok",
            [dict(name="score", type="int"), dict(name="mark", type="int")],
            "return yes if score is at least the mark, otherwise no",
            [({"score": 3, "mark": 5}, "no"), ({"score": 7, "mark": 5}, "yes")],
            [({"score": 5, "mark": 5}, "yes"), ({"score": 4, "mark": 5}, "no")],
            lambda item: "yes" if item["score"] >= item["mark"] else "no",
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "dev_any_tall", "development", "list_any",
            "Create function any_tall(item) that returns yes if any height is at least the floor, otherwise no.",
            "pole.py", "any_tall",
            [dict(name="heights", type="list", path=["pole", "heights"]),
             dict(name="floor", type="int", path=["pole", "floor"])],
            "return yes if any height is at least the floor, otherwise no",
            [({"pole": {"heights": [1, 4], "floor": 5}}, "no"),
             ({"pole": {"heights": [6], "floor": 5}}, "yes")],
            [({"pole": {"heights": [5], "floor": 5}}, "yes"),
             ({"pole": {"heights": [4], "floor": 5}}, "no")],
            lambda item: "yes" if any(value >= item["pole"]["floor"] for value in item["pole"]["heights"]) else "no",
            docs=[{"title": "field notes",
                   "content": "pole.heights is a list. pole.floor is a int."}],
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "dev_all_wide", "development", "list_all",
            "Create function all_wide(item) that returns yes if every width is at least the bar, otherwise no.",
            "plank.py", "all_wide",
            [dict(name="widths", type="list", path=["plank", "widths"]),
             dict(name="bar", type="int", path=["plank", "bar"])],
            "return yes if every width is at least the bar, otherwise no",
            [({"plank": {"widths": [4, 5], "bar": 4}}, "yes"),
             ({"plank": {"widths": [4, 2], "bar": 4}}, "no")],
            [({"plank": {"widths": [9], "bar": 9}}, "yes"),
             ({"plank": {"widths": [8], "bar": 9}}, "no")],
            lambda item: "yes" if all(value >= item["plank"]["bar"] for value in item["plank"]["widths"]) else "no",
            docs=[{"title": "field notes",
                   "content": "plank.widths is a list. plank.bar is a int."}],
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "dev_count_over", "development", "list_count",
            "Create function count_over(item) that returns how many scores are at least the cut.",
            "bag.py", "count_over",
            [dict(name="scores", type="list", path=["bag", "scores"]),
             dict(name="cut", type="int", path=["bag", "cut"])],
            "return how many scores are at least the cut",
            [({"bag": {"scores": [1, 5, 7], "cut": 5}}, 2),
             ({"bag": {"scores": [2, 3], "cut": 5}}, 0)],
            [({"bag": {"scores": [5, 5], "cut": 5}}, 2),
             ({"bag": {"scores": [4], "cut": 5}}, 0)],
            lambda item: sum(1 for value in item["bag"]["scores"] if value >= item["bag"]["cut"]),
            docs=[{"title": "field notes",
                   "content": "bag.scores is a list. bag.cut is a int."}],
            output_type="int",
        ),
        _task(
            "dev_sum_parts", "development", "list_sum",
            "Create function sum_parts(item) that returns the sum of parts.",
            "kit.py", "sum_parts",
            [dict(name="parts", type="list", path=["kit", "parts"])],
            "return the sum of parts",
            [({"kit": {"parts": [2, 3, 4]}}, 9)],
            [({"kit": {"parts": [1, 8]}}, 9), ({"kit": {"parts": [0, 0, 5]}}, 5)],
            lambda item: sum(item["kit"]["parts"]),
            docs=[{"title": "field notes", "content": "kit.parts is a list."}],
            output_type="int",
        ),
        _task(
            "assess_span_ok", "assessment", "scalar_bound",
            "Create function span_ok(item) that returns yes if span is at least the need, otherwise no.",
            "span.py", "span_ok",
            [dict(name="span", type="int"), dict(name="need", type="int")],
            "return yes if span is at least the need, otherwise no",
            [({"span": 2, "need": 4}, "no"), ({"span": 9, "need": 4}, "yes")],
            [({"span": 4, "need": 4}, "yes"), ({"span": 3, "need": 4}, "no")],
            lambda item: "yes" if item["span"] >= item["need"] else "no",
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "assess_any_deep", "assessment", "list_any",
            "Create function any_deep(item) that returns yes if any depth is at least the bed, otherwise no.",
            "well.py", "any_deep",
            [dict(name="depths", type="list", path=["well", "depths"]),
             dict(name="bed", type="int", path=["well", "bed"])],
            "return yes if any depth is at least the bed, otherwise no",
            [({"well": {"depths": [1, 2], "bed": 6}}, "no"),
             ({"well": {"depths": [8], "bed": 6}}, "yes")],
            [({"well": {"depths": [6], "bed": 6}}, "yes"),
             ({"well": {"depths": [5], "bed": 6}}, "no")],
            lambda item: "yes" if any(value >= item["well"]["bed"] for value in item["well"]["depths"]) else "no",
            docs=[{"title": "field notes",
                   "content": "well.depths is a list. well.bed is a int."}],
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "assess_all_long", "assessment", "list_all",
            "Create function all_long(item) that returns yes if every length is at least the rail, otherwise no.",
            "beam.py", "all_long",
            [dict(name="lengths", type="list", path=["beam", "lengths"]),
             dict(name="rail", type="int", path=["beam", "rail"])],
            "return yes if every length is at least the rail, otherwise no",
            [({"beam": {"lengths": [5, 6], "rail": 5}}, "yes"),
             ({"beam": {"lengths": [5, 3], "rail": 5}}, "no")],
            [({"beam": {"lengths": [7], "rail": 7}}, "yes"),
             ({"beam": {"lengths": [6], "rail": 7}}, "no")],
            lambda item: "yes" if all(value >= item["beam"]["rail"] for value in item["beam"]["lengths"]) else "no",
            docs=[{"title": "field notes",
                   "content": "beam.lengths is a list. beam.rail is a int."}],
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "assess_count_meet", "assessment", "list_count",
            "Create function count_meet(item) that returns how many loads are at least the need.",
            "cart.py", "count_meet",
            [dict(name="loads", type="list", path=["cart", "loads"]),
             dict(name="need", type="int", path=["cart", "need"])],
            "return how many loads are at least the need",
            [({"cart": {"loads": [1, 4, 8], "need": 4}}, 2),
             ({"cart": {"loads": [1, 2], "need": 4}}, 0)],
            [({"cart": {"loads": [4, 4], "need": 4}}, 2)],
            lambda item: sum(1 for value in item["cart"]["loads"] if value >= item["cart"]["need"]),
            docs=[{"title": "field notes",
                   "content": "cart.loads is a list. cart.need is a int."}],
            output_type="int",
        ),
        _task(
            "assess_sum_fees", "assessment", "list_sum",
            "Create function sum_fees(item) that returns the sum of fees.",
            "bill.py", "sum_fees",
            [dict(name="fees", type="list", path=["bill", "fees"])],
            "return the sum of fees",
            [({"bill": {"fees": [3, 1, 2]}}, 6)],
            [({"bill": {"fees": [10, 0]}}, 10)],
            lambda item: sum(item["bill"]["fees"]),
            docs=[{"title": "field notes", "content": "bill.fees is a list."}],
            output_type="int",
        ),
    ]


def tasks_for(split: str) -> list[dict[str, Any]]:
    return [row for row in pipeline_catalogue() if row["split"] == split]


def _stamp_cost(cell: dict[str, Any], acquisition_s: float, assembled: bool) -> dict[str, Any]:
    cost = dict(cell.get("cost") or {})
    cost["acquisition_s"] = round(acquisition_s, 6)
    cost["assembly_s"] = round(cost.get("assembly_s") or 0.0, 6)
    cost["contract_acquisition_measured"] = True
    cost["programmer_supplied_output_assembly"] = assembled
    cost["operator_assistance"] = OPERATOR_ASSISTANCE
    cost["total_s"] = round(
        float(cost.get("total_s") or 0.0) + float(acquisition_s), 6,
    )
    cell["cost"] = cost
    return cell


def run_task(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    prepared = ensure_requirement_equality(task)
    started = time.perf_counter()
    acquired = acquire_extraction_contract(prepared)
    acquisition_s = round(time.perf_counter() - started, 6)
    working = dict(prepared)
    working["contract"] = acquired["contract"] if acquired["accuracy"]["paths_exact"] else prepared["contract"]
    working = with_output_docs(working)
    pipelines: dict[str, Any] = {}
    pipelines["direct"] = _stamp_cost(generate_direct(runtime, working, clock), acquisition_s, False)
    pipelines["extract"] = _stamp_cost(generate_extract(runtime, working, clock), acquisition_s, False)
    if yes_no_assembly_eligible(working["request"], working["contract"]):
        pipelines["extract_assemble"] = _stamp_cost(
            generate_extract_assemble(runtime, working, clock), acquisition_s, True,
        )
    else:
        shared = dict(pipelines["extract"])
        shared["path"] = "extract_assemble"
        shared["output_assembly_applied"] = False
        shared["programmer_supplied_output_assembly"] = False
        shared["shared_extract"] = True
        shared["operator_assistance"] = OPERATOR_ASSISTANCE
        pipelines["extract_assemble"] = _stamp_cost(shared, 0.0, False)
        pipelines["extract_assemble"]["cost"]["acquisition_s"] = acquisition_s
        pipelines["extract_assemble"]["cost"]["model_calls"] = 0
        pipelines["extract_assemble"]["cost"]["note"] = (
            "numeric task shares extract; output assembly does not apply"
        )
    return dict(
        task_id=prepared["task_id"],
        split=prepared["split"],
        family=prepared["family"],
        output_assembly_eligible=prepared["output_assembly_eligible"],
        equality=prepared["equality"],
        acquisition=dict(acquired, wall_s=acquisition_s),
        pipelines=pipelines,
        operator_assistance=OPERATOR_ASSISTANCE,
        confirmation=False,
    )


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in PIPELINES:
        cells = [row["pipelines"][name] for row in rows]
        out[name] = dict(
            n=len(cells),
            first_attempt_public=sum(int(cell["public_passed"]) for cell in cells),
            first_attempt_private=sum(int(cell["private_passed"]) for cell in cells),
            helper_not_boolean=sum(int(cell.get("helper_not_boolean") or False) for cell in cells),
            output_assembly_applied=sum(int(cell.get("output_assembly_applied") or False) for cell in cells),
            model_calls=sum(int((cell.get("cost") or {}).get("model_calls") or 0) for cell in cells),
            generation_s=round(sum(float((cell.get("cost") or {}).get("generation_s") or 0) for cell in cells), 6),
            acquisition_s=round(sum(float((cell.get("cost") or {}).get("acquisition_s") or 0) for cell in cells), 6),
            validation_s=round(sum(float((cell.get("cost") or {}).get("validation_s") or 0) for cell in cells), 6),
            total_s=round(sum(float((cell.get("cost") or {}).get("total_s") or 0) for cell in cells), 6),
        )
    out["contracts_exact"] = sum(int(row["acquisition"]["accuracy"]["paths_exact"]) for row in rows)
    out["questions"] = sum(int(row["acquisition"]["teacher_queries"]) for row in rows)
    out["inspections"] = sum(int(row["acquisition"]["inspections"]) for row in rows)
    out["operator_assistance"] = OPERATOR_ASSISTANCE
    return out


def run_pipelines(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    development = [run_task(runtime, task, clock) for task in tasks_for("development")]
    assessment = [run_task(runtime, task, clock) for task in tasks_for("assessment")]
    usage = dict(
        kind="extraction_pipelines_cpu_usage",
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
        inspections=sum(row["acquisition"]["inspections"] for row in development + assessment),
        teacher_queries=sum(row["acquisition"]["teacher_queries"] for row in development + assessment),
        contract_acquisition_measured=True,
        programmer_supplied_output_assembly=True,
        operator_assistance=OPERATOR_ASSISTANCE,
    )
    payload = dict(
        kind="seed_extraction_pipelines",
        confirmation=False,
        development_evidence=True,
        fresh_confirmation=False,
        learning_to_learn_established=False,
        learned_schema_understanding_claimed=False,
        learned_output_mapping_claimed=False,
        programmer_supplied_output_assembly=True,
        operator_assistance=OPERATOR_ASSISTANCE,
        pipelines=list(PIPELINES),
        opened_unused=list(OPENED),
        historical_outcomes_unchanged=True,
        development=development,
        assessment=assessment,
        development_summary=summarize(development),
        assessment_summary=summarize(assessment),
        usage=usage,
    )
    payload["hash"] = digest({k: payload[k] for k in (
        "kind", "pipelines", "development_summary", "assessment_summary", "usage",
    )})
    (directory / "recovery_live_usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return payload
