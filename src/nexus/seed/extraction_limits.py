"""Broader fresh limits of frozen extraction, with honest shared-candidate costs.

Optional, heterogeneous lists, interacting conditions, unfamiliar APIs
and multi-file edits. 5/5 on an earlier list split does not establish
broad coding reliability. Acquisition is programmed inspection.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .extraction_acquire import acquire_extraction_contract, ensure_requirement_equality
from .extraction_contract import (
    describe_output_contract, extraction_eligible, make_contract,
    yes_no_assembly_eligible,
)
from .extraction_path import (
    CALL_CAP, WALL_CAP_S, generate_direct, generate_extract, with_output_docs,
)
from .extraction_pipelines import generate_extract_assemble
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

PIPELINES = ("direct", "extract", "extract_assemble")
YES_NO = ("yes", "no")
OPENED = (
    "assess_place", "assess_order", "assess_arith", "assess_cond",
    "assess_list", "assess_nested", "assess_label", "assess_remainder",
    "assess_all_ok", "assess_has_city", "dev_spread", "dev_any_hot",
    "dev_has_tag", "dev_at_least", "dev_box", "dev_note",
    "inform_at_least", "inform_nested", "inform_note",
    "dev_mark_ok", "dev_any_tall", "dev_all_wide", "dev_count_over",
    "dev_sum_parts", "assess_span_ok", "assess_any_deep", "assess_all_long",
    "assess_count_meet", "assess_sum_fees",
)


def _echo_files(mapping: dict[str, str]) -> dict[str, str]:
    files = {}
    for name, source in mapping.items():
        files[name] = source if source else "def echo(text):\n    return text\n"
    return files


def _task(task_id: str, split: str, family: str, request: str, files: dict[str, str],
          symbol: str, entry: str, fields: list[dict[str, Any]], behavior: str,
          public: list[tuple[Any, Any]], private: list[tuple[Any, Any]],
          reference, *, docs: list[dict[str, str]] | None = None,
          output_type: str | None = None, allowed_values: list[Any] | None = None,
          supporting: dict[str, str] | None = None) -> dict[str, Any]:
    contract = make_contract(symbol, fields, behavior, output_type, allowed_values)
    notes = list(docs or [])
    notes.append({"title": "output contract", "content": describe_output_contract(contract)})
    return dict(
        task_id=task_id,
        split=split,
        family=family,
        request=request,
        files=_echo_files(files),
        public=[dict(entry=entry, input=inp, expected=exp) for inp, exp in public],
        private=[dict(entry=entry, input=inp, expected=exp) for inp, exp in private],
        contract=contract,
        docs=notes,
        reference=reference,
        supporting=supporting or {},
        origin="authored_extraction_limits",
    )


def limits_catalogue() -> list[dict[str, Any]]:
    echo = "def echo(text):\n    return text\n"
    scale = (
        "def scale_points(nums):\n"
        "    return [n * 2 for n in nums]\n"
    )
    shift = (
        "def shift_points(nums):\n"
        "    return [n + 1 for n in nums]\n"
    )
    return [
        _task(
            "dev_opt_tag", "development", "optional",
            "Create function tag(item) that returns the code field in lowercase.",
            {"tag.py": echo}, "tag", "tag.tag",
            [dict(name="code", type="str", presence="required"),
             dict(name="note", type="str", presence="optional")],
            "return the code in lowercase",
            [({"code": "Ok", "note": "x"}, "ok"), ({"code": "Go"}, "go")],
            [({"code": "Hi"}, "hi")],
            lambda item: str(item["code"]).lower(),
            output_type="str",
        ),
        _task(
            "dev_any_kind", "development", "heterogeneous_list",
            "Create function any_kind(item) that returns yes if any row kind matches need and n is at least the floor, otherwise no.",
            {"kind.py": echo}, "any_kind", "kind.any_kind",
            [dict(name="rows", type="list", path=["bag", "rows"]),
             dict(name="need", type="str", path=["bag", "need"]),
             dict(name="floor", type="int", path=["bag", "floor"])],
            "return yes if any row kind matches need and n is at least the floor, otherwise no",
            [({"bag": {"rows": [{"kind": "a", "n": 1}, {"kind": "b", "n": 4}], "need": "b", "floor": 3}}, "yes"),
             ({"bag": {"rows": [{"kind": "a", "n": 9}], "need": "b", "floor": 3}}, "no")],
            [({"bag": {"rows": [{"kind": "b", "n": 3}], "need": "b", "floor": 3}}, "yes")],
            lambda item: "yes" if any(
                str(row.get("kind")) == item["bag"]["need"] and row.get("n") >= item["bag"]["floor"]
                for row in item["bag"]["rows"]
            ) else "no",
            docs=[{"title": "field notes",
                   "content": "bag.rows is a list. bag.need is a str. bag.floor is a int."}],
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "dev_and_gate", "development", "interacting_conditions",
            "Create function and_gate(item) that returns yes if score is at least the mark and ready is on, otherwise no.",
            {"gate.py": echo}, "and_gate", "gate.and_gate",
            [dict(name="score", type="int"), dict(name="mark", type="int"),
             dict(name="ready", type="str")],
            "return yes if score is at least the mark and ready is on, otherwise no",
            [({"score": 5, "mark": 5, "ready": "on"}, "yes"),
             ({"score": 9, "mark": 5, "ready": "off"}, "no"),
             ({"score": 3, "mark": 5, "ready": "on"}, "no")],
            [({"score": 6, "mark": 6, "ready": "on"}, "yes")],
            lambda item: "yes" if item["score"] >= item["mark"] and item["ready"] == "on" else "no",
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "dev_use_scale", "development", "unfamiliar_api",
            "Create function total_scaled(item) that returns the sum of scale_points on kit.parts.",
            {"app.py": echo, "util.py": scale}, "total_scaled", "app.total_scaled",
            [dict(name="parts", type="list", path=["kit", "parts"])],
            "return the sum of scale_points on parts",
            [({"kit": {"parts": [1, 2, 3]}}, 12)],
            [({"kit": {"parts": [4]}}, 8)],
            lambda item: sum(n * 2 for n in item["kit"]["parts"]),
            docs=[{"title": "field notes", "content": "kit.parts is a list. Use scale_points from util."}],
            output_type="int",
            supporting={"util.py": "scale_points"},
        ),
        _task(
            "dev_two_file", "development", "multi_file",
            "Add tall_enough(value, limit) to util.py. Create function ready(item) in app.py that returns yes if any height is at least the floor using tall_enough, otherwise no.",
            {"app.py": echo, "util.py": echo}, "ready", "app.ready",
            [dict(name="heights", type="list", path=["pole", "heights"]),
             dict(name="floor", type="int", path=["pole", "floor"])],
            "return yes if any height is at least the floor, otherwise no",
            [({"pole": {"heights": [1, 6], "floor": 5}}, "yes"),
             ({"pole": {"heights": [1, 2], "floor": 5}}, "no")],
            [({"pole": {"heights": [5], "floor": 5}}, "yes")],
            lambda item: "yes" if any(value >= item["pole"]["floor"] for value in item["pole"]["heights"]) else "no",
            docs=[{"title": "field notes",
                   "content": "pole.heights is a list. pole.floor is a int."}],
            output_type="str", allowed_values=list(YES_NO),
            supporting={"util.py": "tall_enough"},
        ),
        _task(
            "assess_opt_mark", "assessment", "optional",
            "Create function stamp(item) that returns the mark field in lowercase.",
            {"stamp.py": echo}, "stamp", "stamp.stamp",
            [dict(name="mark", type="str", presence="required"),
             dict(name="hint", type="str", presence="optional")],
            "return the mark in lowercase",
            [({"mark": "Ok", "hint": "x"}, "ok"), ({"mark": "Go"}, "go")],
            [({"mark": "Hi"}, "hi")],
            lambda item: str(item["mark"]).lower(),
            output_type="str",
        ),
        _task(
            "assess_any_role", "assessment", "heterogeneous_list",
            "Create function any_role(item) that returns yes if any row role matches want and n is at least the bar, otherwise no.",
            {"role.py": echo}, "any_role", "role.any_role",
            [dict(name="rows", type="list", path=["crew", "rows"]),
             dict(name="want", type="str", path=["crew", "want"]),
             dict(name="bar", type="int", path=["crew", "bar"])],
            "return yes if any row role matches want and n is at least the bar, otherwise no",
            [({"crew": {"rows": [{"role": "lead", "n": 2}, {"role": "aid", "n": 8}], "want": "aid", "bar": 5}}, "yes"),
             ({"crew": {"rows": [{"role": "lead", "n": 9}], "want": "aid", "bar": 5}}, "no")],
            [({"crew": {"rows": [{"role": "aid", "n": 5}], "want": "aid", "bar": 5}}, "yes")],
            lambda item: "yes" if any(
                str(row.get("role")) == item["crew"]["want"] and row.get("n") >= item["crew"]["bar"]
                for row in item["crew"]["rows"]
            ) else "no",
            docs=[{"title": "field notes",
                   "content": "crew.rows is a list. crew.want is a str. crew.bar is a int."}],
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "assess_and_span", "assessment", "interacting_conditions",
            "Create function and_span(item) that returns yes if span is at least the need and live is on, otherwise no.",
            {"span.py": echo}, "and_span", "span.and_span",
            [dict(name="span", type="int"), dict(name="need", type="int"),
             dict(name="live", type="str")],
            "return yes if span is at least the need and live is on, otherwise no",
            [({"span": 4, "need": 4, "live": "on"}, "yes"),
             ({"span": 9, "need": 4, "live": "off"}, "no")],
            [({"span": 5, "need": 5, "live": "on"}, "yes")],
            lambda item: "yes" if item["span"] >= item["need"] and item["live"] == "on" else "no",
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "assess_use_shift", "assessment", "unfamiliar_api",
            "Create function total_shifted(item) that returns the sum of shift_points on kit.parts.",
            {"app.py": echo, "util.py": shift}, "total_shifted", "app.total_shifted",
            [dict(name="parts", type="list", path=["kit", "parts"])],
            "return the sum of shift_points on parts",
            [({"kit": {"parts": [1, 2, 3]}}, 9)],
            [({"kit": {"parts": [4]}}, 5)],
            lambda item: sum(n + 1 for n in item["kit"]["parts"]),
            docs=[{"title": "field notes", "content": "kit.parts is a list. Use shift_points from util."}],
            output_type="int",
            supporting={"util.py": "shift_points"},
        ),
        _task(
            "assess_two_file", "assessment", "multi_file",
            "Add wide_enough(value, limit) to util.py. Create function fit(item) in app.py that returns yes if any width is at least the bar using wide_enough, otherwise no.",
            {"app.py": echo, "util.py": echo}, "fit", "app.fit",
            [dict(name="widths", type="list", path=["plank", "widths"]),
             dict(name="bar", type="int", path=["plank", "bar"])],
            "return yes if any width is at least the bar, otherwise no",
            [({"plank": {"widths": [2, 9], "bar": 8}}, "yes"),
             ({"plank": {"widths": [1, 2], "bar": 8}}, "no")],
            [({"plank": {"widths": [8], "bar": 8}}, "yes")],
            lambda item: "yes" if any(value >= item["plank"]["bar"] for value in item["plank"]["widths"]) else "no",
            docs=[{"title": "field notes",
                   "content": "plank.widths is a list. plank.bar is a int."}],
            output_type="str", allowed_values=list(YES_NO),
            supporting={"util.py": "wide_enough"},
        ),
    ]


def tasks_for(split: str) -> list[dict[str, Any]]:
    return [row for row in limits_catalogue() if row["split"] == split]


def _share(cell: dict[str, Any], path: str, billed_to: str) -> dict[str, Any]:
    copy = dict(cell)
    copy["path"] = path
    copy["shared_extract"] = billed_to == "extract"
    copy["shared_from"] = billed_to
    copy["unique_generation"] = False
    cost = dict(copy.get("cost") or {})
    cost["model_calls"] = 0
    cost["generation_s"] = 0.0
    cost["shared_from"] = billed_to
    cost["note"] = f"shared candidate billed to {billed_to}"
    copy["cost"] = cost
    return copy


def supporting_present(task: dict[str, Any], files: dict[str, str]) -> bool:
    wanted = task.get("supporting") or {}
    if not wanted:
        return True
    for path, symbol in wanted.items():
        if f"def {symbol}" not in (files.get(path) or ""):
            return False
    return True


def run_task(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    prepared = ensure_requirement_equality(task)
    started = time.perf_counter()
    acquired = acquire_extraction_contract(prepared)
    acquisition_s = round(time.perf_counter() - started, 6)
    working = with_output_docs(dict(prepared, contract=prepared["contract"]))
    eligible = extraction_eligible(working["contract"])
    assemble = yes_no_assembly_eligible(working["request"], working["contract"])
    pipelines: dict[str, Any] = {}
    shared: list[dict[str, Any]] = []
    direct = generate_direct(runtime, working, clock)
    direct["unique_generation"] = True
    pipelines["direct"] = direct
    if not eligible:
        pipelines["extract"] = _share(direct, "extract", "direct")
        pipelines["extract_assemble"] = _share(direct, "extract_assemble", "direct")
        shared.append(dict(
            task_id=prepared["task_id"],
            shared_pipelines=["direct", "extract", "extract_assemble"],
            billed_to="direct",
            reason="ineligible_optional_or_nullable",
            model_calls=1,
        ))
    else:
        extract = generate_extract(runtime, working, clock)
        extract["unique_generation"] = True
        pipelines["extract"] = extract
        if assemble:
            assembled = generate_extract_assemble(runtime, working, clock)
            assembled["unique_generation"] = True
            pipelines["extract_assemble"] = assembled
        else:
            pipelines["extract_assemble"] = _share(extract, "extract_assemble", "extract")
            shared.append(dict(
                task_id=prepared["task_id"],
                shared_pipelines=["extract", "extract_assemble"],
                billed_to="extract",
                reason="assembly_ineligible",
                model_calls=1,
            ))
    for name, cell in pipelines.items():
        cost = dict(cell.get("cost") or {})
        cost["acquisition_s"] = acquisition_s
        cost["inspection_s"] = acquisition_s
        cost["contract_acquisition_measured"] = True
        cell["cost"] = cost
        cell["supporting_present"] = supporting_present(prepared, cell.get("files") or prepared["files"])
    return dict(
        task_id=prepared["task_id"],
        split=prepared["split"],
        family=prepared["family"],
        eligible=eligible,
        assemble=assemble,
        equality=prepared.get("equality"),
        acquisition=dict(acquired, wall_s=acquisition_s, learned_acquisition=False),
        pipelines=pipelines,
        shared_candidates=shared,
        confirmation=False,
    )


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_family: dict[str, dict[str, Any]] = {}
    for row in rows:
        family = row["family"]
        bucket = by_family.setdefault(family, {name: {"n": 0, "private": 0, "public": 0} for name in PIPELINES})
        for name in PIPELINES:
            cell = row["pipelines"][name]
            bucket[name]["n"] += 1
            bucket[name]["private"] += int(cell["private_passed"])
            bucket[name]["public"] += int(cell["public_passed"])
    pipelines = {}
    for name in PIPELINES:
        cells = [row["pipelines"][name] for row in rows]
        unique = [cell for cell in cells if cell.get("unique_generation")]
        pipelines[name] = dict(
            n=len(cells),
            first_attempt_public=sum(int(cell["public_passed"]) for cell in cells),
            first_attempt_private=sum(int(cell["private_passed"]) for cell in cells),
            unique_model_calls=sum(int((cell.get("cost") or {}).get("model_calls") or 0) for cell in unique),
            unique_generation_s=round(sum(float((cell.get("cost") or {}).get("generation_s") or 0) for cell in unique), 6),
            shared_count=sum(int(not cell.get("unique_generation")) for cell in cells),
            supporting_present=sum(int(cell.get("supporting_present")) for cell in cells),
        )
    shared = []
    for row in rows:
        shared.extend(row.get("shared_candidates") or [])
    return dict(
        pipelines=pipelines,
        by_family=by_family,
        shared_candidates=shared,
        contracts_exact=sum(int(row["acquisition"]["accuracy"]["paths_exact"]) for row in rows),
        questions=sum(int(row["acquisition"]["teacher_queries"]) for row in rows),
        inspections=sum(int(row["acquisition"]["inspections"]) for row in rows),
        learned_acquisition=False,
    )


def run_limits(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    development = [run_task(runtime, task, clock) for task in tasks_for("development")]
    assessment = [run_task(runtime, task, clock) for task in tasks_for("assessment")]
    usage = dict(
        kind="extraction_limits_cpu_usage",
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
        learned_acquisition=False,
        trusted_output_assembly=True,
    )
    payload = dict(
        kind="seed_extraction_limits",
        confirmation=False,
        development_evidence=True,
        five_of_five_not_broad_reliability=True,
        learning_to_learn_established=False,
        learned_schema_understanding_claimed=False,
        learned_acquisition=False,
        frozen_baseline="eligible_always_extract",
        opened_unused=list(OPENED),
        historical_outcomes_unchanged=True,
        development=development,
        assessment=assessment,
        development_summary=summarize(development),
        assessment_summary=summarize(assessment),
        usage=usage,
    )
    payload["hash"] = digest({k: payload[k] for k in (
        "kind", "development_summary", "assessment_summary", "usage",
    )})
    (directory / "recovery_live_usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return payload
