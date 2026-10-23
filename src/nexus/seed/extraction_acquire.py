"""Eligible-always-extract baseline with measured contract acquisition.

The baseline is frozen: extract when every acquired or supplied field is
required, otherwise direct. Fresh tasks only. Assessment informs the next
version and is not confirmation. Historical artifacts are not edited.
"""
from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path
from typing import Any

from .boundary_evidence import infer_bound_polarity, teacher_boundary_labels
from .capability_evidence import digest
from .constrained_edit import plan_constrained_edit
from .extraction_contract import (
    describe_output_contract, extraction_eligible, field_spec, make_contract,
)
from .extraction_path import CALL_CAP, WALL_CAP_S, _echo, generate_on_path
from .input_contract import fields_from_source
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

CANDIDATE_BASELINE = "eligible_always_extract"
AT_LEAST_CUES = ("at least",)
OPENED = (
    "assess_place", "assess_order", "assess_arith", "assess_cond",
    "assess_list", "assess_nested", "assess_label", "assess_remainder",
    "assess_all_ok", "assess_has_city", "dev_spread", "dev_any_hot",
    "dev_has_tag",
)
YES_NO = ("yes", "no")
_DOC_FIELD = re.compile(
    r"\b([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*)\s+is a (list|int|str|dict)\b",
    re.I,
)


def baseline_path(contract: dict[str, Any]) -> str:
    return "extract" if extraction_eligible(contract) else "direct"


def requirement_says_at_least(request: str) -> bool:
    text = (request or "").lower()
    return any(cue in text for cue in AT_LEAST_CUES)


def teacher_equality_expected(request: str, allowed: list[Any] | None) -> Any:
    polarity = infer_bound_polarity(request)
    labels = teacher_boundary_labels("inclusive", polarity)
    if labels is None:
        raise ValueError("teacher_equality_unlabeled")
    if allowed == list(YES_NO):
        return "yes" if labels["equal"] else "no"
    return labels["equal"]


def _equality_input(sample: Any) -> Any:
    if type(sample) is not dict:
        return None
    ints = [key for key, value in sample.items()
            if type(value) in (int, float) and type(value) is not bool]
    if len(ints) >= 2:
        out = dict(sample)
        out[ints[0]] = out[ints[1]]
        return out
    lists = [key for key, value in sample.items()
             if type(value) is list and value and type(value[0]) in (int, float)]
    nums = [key for key, value in sample.items()
            if type(value) in (int, float) and type(value) is not bool]
    if lists and nums:
        out = dict(sample)
        seq = list(out[lists[0]])
        seq[0] = out[nums[0]]
        out[lists[0]] = seq
        return out
    for key, value in sample.items():
        nested = _equality_input(value)
        if nested is not None:
            out = dict(sample)
            out[key] = nested
            return out
    return None


def public_has_numeric_equality(public: list[dict[str, Any]]) -> bool:
    for case in public or []:
        found = _contains_equal_pair(case.get("input"))
        if found:
            return True
    return False


def _contains_equal_pair(sample: Any) -> bool:
    if type(sample) is not dict:
        return False
    ints = [value for value in sample.values()
            if type(value) in (int, float) and type(value) is not bool]
    if len(ints) >= 2 and any(ints[0] == other for other in ints[1:]):
        return True
    lists = [value for value in sample.values()
             if type(value) is list and value and type(value[0]) in (int, float)]
    nums = [value for value in sample.values()
            if type(value) in (int, float) and type(value) is not bool]
    if lists and nums and any(num in lists[0] for num in nums):
        return True
    return any(_contains_equal_pair(value) for value in sample.values() if type(value) is dict)


def ensure_requirement_equality(task: dict[str, Any]) -> dict[str, Any]:
    """Add an equality public case from the requirement or teacher, never private."""
    public = [dict(case) for case in task["public"]]
    record = dict(
        required=requirement_says_at_least(task["request"]),
        used_private_tests=False,
        used_candidate=False,
        source=None,
        added=False,
    )
    if not record["required"]:
        return dict(task, public=public, equality=record)
    if public_has_numeric_equality(public):
        record["source"] = "requirement_public_already_had_equal"
        return dict(task, public=public, equality=record)
    sample = next((case.get("input") for case in public if type(case.get("input")) is dict), None)
    built = _equality_input(copy.deepcopy(sample)) if sample is not None else None
    expected = teacher_equality_expected(task["request"], task["contract"].get("allowed_values"))
    if built is None:
        gold = task.get("teacher_equality_case")
        if gold is None:
            record["source"] = "teacher_unavailable"
            return dict(task, public=public, equality=record)
        built = gold["input"]
        expected = gold["expected"]
        record["source"] = "teacher"
        record["teacher_queries"] = 1
    else:
        record["source"] = "requirement"
    public.append(dict(entry=public[0]["entry"], input=built, expected=expected))
    record["added"] = True
    return dict(task, public=public, equality=record)


def _walk_paths(value: Any, prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], str]]:
    if type(value) is dict:
        rows = []
        for key, inner in value.items():
            rows.extend(_walk_paths(inner, prefix + (str(key),)))
        return rows
    kind = "list" if type(value) is list else type(value).__name__
    return [(prefix, kind)] if prefix else []


def propose_from_examples(public: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, ...], int] = {}
    kinds: dict[tuple[str, ...], str] = {}
    total = 0
    for case in public or []:
        inp = case.get("input")
        if type(inp) is not dict:
            continue
        total += 1
        seen = set()
        for path, kind in _walk_paths(inp):
            counts[path] = counts.get(path, 0) + 1
            kinds[path] = kind
            seen.add(path)
    if total == 0:
        return []
    fields = []
    for path in sorted(counts):
        presence = "required" if counts[path] == total else "optional"
        fields.append(field_spec(path[-1], kinds[path], presence, list(path)))
    return fields


def propose_from_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = []
    for doc in docs or []:
        text = str(doc.get("content") or "")
        for match in _DOC_FIELD.finditer(text):
            route = match.group(1).split(".")
            fields.append(field_spec(route[-1], match.group(2).lower(), "required", route))
    return fields


def propose_from_source(files: dict[str, str], request: str,
                        public: list[dict[str, Any]]) -> list[str]:
    plan = plan_constrained_edit(request, files, public)
    return fields_from_source(plan.existing_source or files.get(plan.path, ""))


def acquire_extraction_contract(task: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    inspections = 0
    questions = 0
    source_keys = propose_from_source(task["files"], task["request"], task["public"])
    inspections += 1
    doc_fields = propose_from_docs(task.get("docs") or [])
    if task.get("docs"):
        inspections += 1
    example_fields = propose_from_examples(task["public"])
    inspections += 1
    merged: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in doc_fields + example_fields:
        merged[tuple(row["path"])] = row
    gold = task["contract"]
    proposed = make_contract(
        gold["symbol"], list(merged.values()), gold["behavior"],
        gold.get("output_type"), gold.get("allowed_values"),
    )
    proposed_accuracy = score_contract(proposed, gold)
    asked = False
    question = None
    if _evidence_insufficient(list(merged.values()), source_keys):
        asked = True
        questions += 1
        question = (
            f"What field paths, types and presence does item have for {gold['symbol']}?"
        )
        for row in gold["fields"]:
            merged[tuple(row["path"])] = dict(row)
    acquired = make_contract(
        gold["symbol"], list(merged.values()), gold["behavior"],
        gold.get("output_type"), gold.get("allowed_values"),
    )
    acquired["contract_source"] = "acquired"
    acquired["programmer_supplied_extraction"] = True
    accuracy = score_contract(acquired, gold)
    return dict(
        contract=acquired,
        proposed=proposed,
        proposed_accuracy=proposed_accuracy,
        accuracy=accuracy,
        asked=asked,
        question=question,
        inspections=inspections,
        teacher_queries=questions,
        source_keys=source_keys,
        from_docs=doc_fields,
        from_examples=example_fields,
        complete=proposed_accuracy["paths_exact"] and proposed_accuracy["presence_match"] and not asked,
        wall_s=round(time.perf_counter() - started, 6),
        used_private_tests=False,
    )


def infer_output_contract(public: list[dict[str, Any]]) -> tuple[str | None, list[Any] | None]:
    values = [case.get("expected") for case in public or []]
    if values and all(value in YES_NO for value in values):
        return "str", list(YES_NO)
    kinds = {type(value).__name__ for value in values if value is not None}
    if kinds == {"int"}:
        return "int", None
    if kinds == {"str"}:
        return "str", None
    return None, None


def behavior_from_request(request: str, symbol: str) -> str:
    text = request or ""
    lower = text.lower()
    marker = " that "
    if marker in lower:
        return text[lower.index(marker) + len(marker):].rstrip(".")
    return text or symbol


def acquire_public_contract(request: str, files: dict[str, str],
                            public: list[dict[str, Any]],
                            docs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Programmed inspection. Not a learned acquisition method."""
    started = time.perf_counter()
    inspections = 1
    try:
        plan = plan_constrained_edit(request, files, public)
        source_keys = fields_from_source(plan.existing_source or files.get(plan.path, ""))
        symbol = plan.symbol
    except ValueError as exc:
        return dict(
            contract=None,
            asked=True,
            question="Which function should I implement, and what are its field paths, types and presence?",
            inspections=inspections,
            teacher_queries=1,
            complete=False,
            learned_acquisition=False,
            reason=str(exc),
            wall_s=round(time.perf_counter() - started, 6),
            used_private_tests=False,
        )
    doc_fields = propose_from_docs(docs or [])
    if docs:
        inspections += 1
    example_fields = propose_from_examples(public)
    inspections += 1
    merged: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in doc_fields + example_fields:
        merged[tuple(row["path"])] = row
    asked = _evidence_insufficient(list(merged.values()), source_keys)
    if asked:
        return dict(
            contract=None,
            asked=True,
            question=f"What field paths, types and presence does item have for {symbol}?",
            inspections=inspections,
            teacher_queries=1,
            complete=False,
            learned_acquisition=False,
            source_keys=source_keys,
            from_docs=doc_fields,
            from_examples=example_fields,
            wall_s=round(time.perf_counter() - started, 6),
            used_private_tests=False,
        )
    output_type, allowed = infer_output_contract(public)
    contract = make_contract(
        symbol, list(merged.values()), behavior_from_request(request, symbol),
        output_type, allowed,
    )
    contract["contract_source"] = "acquired"
    return dict(
        contract=contract,
        asked=False,
        question=None,
        inspections=inspections,
        teacher_queries=0,
        complete=True,
        learned_acquisition=False,
        source_keys=source_keys,
        from_docs=doc_fields,
        from_examples=example_fields,
        wall_s=round(time.perf_counter() - started, 6),
        used_private_tests=False,
    )


def _evidence_insufficient(fields: list[dict[str, Any]], source_keys: list[str]) -> bool:
    if not fields:
        return True
    if any(row.get("type") == "dict" for row in fields):
        return True
    tops = {row["path"][0] for row in fields if row.get("path")}
    names = {row["name"] for row in fields}
    return any(key not in names and key not in tops for key in source_keys)


def score_contract(acquired: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    got = {tuple(row["path"]): row for row in acquired.get("fields") or []}
    want = {tuple(row["path"]): row for row in gold.get("fields") or []}
    return dict(
        paths_exact=set(got) == set(want),
        extra_paths=[list(path) for path in got if path not in want],
        missing_paths=[list(path) for path in want if path not in got],
        type_match=all(got[path]["type"] == want[path]["type"] for path in got if path in want),
        presence_match=all(
            got[path]["presence"] == want[path]["presence"] for path in got if path in want
        ),
    )


def _task(task_id: str, split: str, family: str, request: str, filename: str,
          symbol: str, fields: list[dict[str, Any]], behavior: str,
          public: list[tuple[dict[str, Any], Any]],
          private: list[tuple[dict[str, Any], Any]],
          reference, *, docs: list[dict[str, str]] | None = None,
          output_type: str | None = None, allowed_values: list[Any] | None = None,
          teacher_equality_case: dict[str, Any] | None = None) -> dict[str, Any]:
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
        teacher_equality_case=teacher_equality_case,
        origin="authored_extraction_acquire",
    )


def acquire_catalogue() -> list[dict[str, Any]]:
    return [
        _task(
            "dev_at_least", "development", "boundary",
            "Create function floor_ok(item) that returns yes if score is at least the limit, otherwise no.",
            "floor.py", "floor_ok",
            [dict(name="score", type="int"), dict(name="limit", type="int")],
            "return yes if score is at least the limit, otherwise no",
            [({"score": 3, "limit": 5}, "no"), ({"score": 7, "limit": 5}, "yes")],
            [({"score": 5, "limit": 5}, "yes"), ({"score": 4, "limit": 5}, "no")],
            lambda item: "yes" if item["score"] >= item["limit"] else "no",
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "dev_box", "development", "composition",
            "Create function box_ready(item) that returns yes if any box level is at least the floor, otherwise no.",
            "box.py", "box_ready",
            [dict(name="level", type="list", path=["box", "level"]),
             dict(name="floor", type="int", path=["box", "floor"])],
            "return yes if any level is at least the floor, otherwise no",
            [({"box": {"level": [1, 4], "floor": 5}}, "no"),
             ({"box": {"level": [6], "floor": 5}}, "yes")],
            [({"box": {"level": [5], "floor": 5}}, "yes")],
            lambda item: "yes" if any(value >= item["box"]["floor"] for value in item["box"]["level"]) else "no",
            docs=[{"title": "field notes",
                   "content": "box.level is a list. box.floor is a int."}],
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "dev_note", "development", "optional",
            "Create function stamp(item) that returns the code field in lowercase.",
            "stamp.py", "stamp",
            [dict(name="code", type="str", presence="required"),
             dict(name="note", type="str", presence="optional")],
            "return the code in lowercase",
            [({"code": "Ok", "note": "x"}, "ok"), ({"code": "Go"}, "go")],
            [({"code": "Hi"}, "hi")],
            lambda item: str(item["code"]).lower(),
            output_type="str",
        ),
        _task(
            "inform_at_least", "inform_next", "boundary",
            "Create function weight_ok(item) that returns yes if weight is at least the minimum, otherwise no.",
            "wgt.py", "weight_ok",
            [dict(name="weight", type="int"), dict(name="minimum", type="int")],
            "return yes if weight is at least the minimum, otherwise no",
            [({"weight": 2, "minimum": 4}, "no"), ({"weight": 9, "minimum": 4}, "yes")],
            [({"weight": 4, "minimum": 4}, "yes")],
            lambda item: "yes" if item["weight"] >= item["minimum"] else "no",
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "inform_nested", "inform_next", "composition",
            "Create function crate_has(item) that returns yes if any crate mark matches need in lowercase, otherwise no.",
            "crate.py", "crate_has",
            [dict(name="marks", type="list", path=["crate", "marks"]),
             dict(name="need", type="str", path=["crate", "need"])],
            "return yes if any mark matches need in lowercase, otherwise no",
            [({"crate": {"marks": ["Oak", "Elm"], "need": "oak"}}, "yes"),
             ({"crate": {"marks": ["Elm"], "need": "oak"}}, "no")],
            [({"crate": {"marks": ["Ash"], "need": "ash"}}, "yes")],
            lambda item: "yes" if any(str(mark).lower() == str(item["crate"]["need"]).lower()
                                      for mark in item["crate"]["marks"]) else "no",
            docs=[{"title": "field notes",
                   "content": "crate.marks is a list. crate.need is a str."}],
            output_type="str", allowed_values=list(YES_NO),
        ),
        _task(
            "inform_note", "inform_next", "optional",
            "Create function label(item) that returns the mark field in lowercase.",
            "label.py", "label",
            [dict(name="mark", type="str", presence="required"),
             dict(name="hint", type="str", presence="optional")],
            "return the mark in lowercase",
            [({"mark": "Ok", "hint": "x"}, "ok"), ({"mark": "Go"}, "go")],
            [({"mark": "Hi"}, "hi")],
            lambda item: str(item["mark"]).lower(),
            output_type="str",
        ),
    ]


def tasks_for(split: str) -> list[dict[str, Any]]:
    return [row for row in acquire_catalogue() if row["split"] == split]


def run_arm(runtime, task: dict[str, Any], contract: dict[str, Any],
            clock: dict[str, Any]) -> dict[str, Any]:
    working = dict(task)
    working["contract"] = contract
    path = baseline_path(contract)
    result = generate_on_path(runtime, working, path, clock)
    source = contract.get("contract_source") or "benchmark_supplied"
    cost = dict(result.get("cost") or {})
    cost["contract_source"] = source
    cost["contract_acquisition_measured"] = source == "acquired"
    result["cost"] = cost
    result["baseline_path"] = path
    result["eligible"] = extraction_eligible(contract)
    result["contract_source"] = source
    return result


def run_task(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    prepared = ensure_requirement_equality(task)
    started = time.perf_counter()
    acquired = acquire_extraction_contract(prepared)
    acquisition_s = round(time.perf_counter() - started, 6)
    supplied = run_arm(runtime, prepared, prepared["contract"], clock)
    measured = run_arm(runtime, prepared, acquired["contract"], clock)
    return dict(
        task_id=prepared["task_id"],
        split=prepared["split"],
        family=prepared["family"],
        equality=prepared["equality"],
        acquisition=dict(acquired, wall_s=acquisition_s),
        supplied=supplied,
        acquired=measured,
        confirmation=False,
        informs_next=prepared["split"] == "inform_next",
    )


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def arm(name: str) -> dict[str, Any]:
        cells = [row[name] for row in rows]
        return dict(
            n=len(cells),
            first_attempt_private=sum(int(cell["private_passed"]) for cell in cells),
            first_attempt_public=sum(int(cell["public_passed"]) for cell in cells),
            extract_paths=sum(int(cell["baseline_path"] == "extract") for cell in cells),
            direct_paths=sum(int(cell["baseline_path"] == "direct") for cell in cells),
        )
    return dict(
        supplied=arm("supplied"),
        acquired=arm("acquired"),
        contracts_exact=sum(int(row["acquisition"]["accuracy"]["paths_exact"]) for row in rows),
        proposed_exact=sum(int(row["acquisition"]["proposed_accuracy"]["paths_exact"]
                               and row["acquisition"]["proposed_accuracy"]["presence_match"])
                           for row in rows),
        questions=sum(int(row["acquisition"]["teacher_queries"]) for row in rows),
        inspections=sum(int(row["acquisition"]["inspections"]) for row in rows),
        equality_added=sum(int(row["equality"]["added"]) for row in rows),
        used_private_for_equality=any(row["equality"]["used_private_tests"] for row in rows),
        used_candidate_for_equality=any(row["equality"]["used_candidate"] for row in rows),
    )


def run_acquire(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    development = [run_task(runtime, task, clock) for task in tasks_for("development")]
    inform = [run_task(runtime, task, clock) for task in tasks_for("inform_next")]
    usage = dict(
        kind="extraction_acquire_cpu_usage",
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
        inspections=sum(row["acquisition"]["inspections"] for row in development + inform),
        teacher_queries=sum(row["acquisition"]["teacher_queries"] for row in development + inform),
        contract_acquisition_measured=True,
    )
    payload = dict(
        kind="seed_extraction_acquire",
        confirmation=False,
        informs_next_not_confirmation=True,
        learning_to_learn_established=False,
        learned_schema_understanding_claimed=False,
        candidate_baseline=CANDIDATE_BASELINE,
        opened_unused=list(OPENED),
        historical_outcomes_unchanged=True,
        development=development,
        inform_next=inform,
        development_summary=summarize(development),
        inform_summary=summarize(inform),
        usage=usage,
    )
    payload["hash"] = digest({k: payload[k] for k in (
        "kind", "candidate_baseline", "development_summary", "inform_summary", "usage",
    )})
    (directory / "recovery_live_usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return payload
