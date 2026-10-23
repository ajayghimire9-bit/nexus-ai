"""Optional extract-path generation versus direct item generation.

Harder families are scored separately from missing-value rules. First
attempt only. Cost includes contract, extraction, generation and
validation. Keep direct when accuracy is equal.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .chat_template import render_prompt
from .constrained_edit import plan_constrained_edit
from .extraction_contract import (
    apply_output_contract, apply_trusted_assembly, describe_output_contract,
    extraction_eligible, make_contract, preview_extraction, scalar_public,
    select_generation_path, wrap_transform, wrapper_uses_silent_default,
)
from .function_format import assemble_format_proposal, prompt_for_format
from .recovery_actions import run_cases
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S, score_files
from .recovery_failure_bank import classify_failure, public_errors, target_source
from .recovery_live import _prompt_task, model_complete

CALL_CAP = 32
WALL_CAP_S = 240.0
OPENED_ASSESSMENT = ("assess_place", "assess_order")


def _echo(name: str) -> dict[str, str]:
    return {name: "def echo(text):\n    return text\n"}


def _task(task_id: str, split: str, family: str, request: str, filename: str,
          symbol: str, fields: list[dict[str, Any]], behavior: str,
          public: list[tuple[dict[str, Any], Any]],
          private: list[tuple[dict[str, Any], Any]],
          reference) -> dict[str, Any]:
    entry = filename.removesuffix(".py") + "." + symbol
    contract = make_contract(symbol, fields, behavior)
    cases = lambda rows: [dict(entry=entry, input=inp, expected=exp) for inp, exp in rows]
    return dict(
        task_id=task_id,
        split=split,
        family=family,
        request=request,
        files=_echo(filename),
        public=cases(public),
        private=cases(private),
        contract=contract,
        selected_path=select_generation_path(contract),
        reference=reference,
        origin="authored_extraction_path",
    )


def catalogue() -> list[dict[str, Any]]:
    return [
        _task(
            "dev_arith", "development", "arithmetic",
            "Create function total(item) that returns score plus bonus minus fee.",
            "arith.py", "total",
            [dict(name="score", type="int"), dict(name="bonus", type="int"), dict(name="fee", type="int")],
            "return score plus bonus minus fee",
            [({"score": 10, "bonus": 3, "fee": 2}, 11)],
            [({"score": 8, "bonus": 1, "fee": 4}, 5)],
            lambda item: item["score"] + item["bonus"] - item["fee"],
        ),
        _task(
            "dev_cond", "development", "conditional",
            "Create function grade(item) that returns pass when score meets the limit, otherwise hold.",
            "grade.py", "grade",
            [dict(name="score", type="int"), dict(name="limit", type="int")],
            "return pass when score meets the limit, otherwise hold",
            [({"score": 5, "limit": 4}, "pass"), ({"score": 3, "limit": 4}, "hold")],
            [({"score": 6, "limit": 6}, "pass"), ({"score": 1, "limit": 2}, "hold")],
            lambda item: "pass" if item["score"] >= item["limit"] else "hold",
        ),
        _task(
            "dev_list", "development", "list_processing",
            "Create function sorted_nums(item) that returns nums sorted ascending.",
            "nums.py", "sorted_nums",
            [dict(name="nums", type="list")],
            "return nums sorted ascending",
            [({"nums": [3, 1, 2]}, [1, 2, 3])],
            [({"nums": [9, 0, 4]}, [0, 4, 9])],
            lambda item: sorted(item["nums"]),
        ),
        _task(
            "dev_nested", "development", "nested_record",
            "Create function tag_name(item) that returns the nested tag name in lowercase.",
            "nest.py", "tag_name",
            [dict(name="name", type="str", path=["tag", "name"])],
            "return the name in lowercase",
            [({"tag": {"name": "Ada"}}, "ada")],
            [({"tag": {"name": "Lin"}}, "lin")],
            lambda item: str(item["tag"]["name"]).lower(),
        ),
        _task(
            "assess_arith", "assessment", "arithmetic",
            "Create function net(item) that returns amount minus tax minus fee.",
            "net.py", "net",
            [dict(name="amount", type="int"), dict(name="tax", type="int"), dict(name="fee", type="int")],
            "return amount minus tax minus fee",
            [({"amount": 20, "tax": 3, "fee": 1}, 16)],
            [({"amount": 15, "tax": 2, "fee": 5}, 8)],
            lambda item: item["amount"] - item["tax"] - item["fee"],
        ),
        _task(
            "assess_cond", "assessment", "conditional",
            "Create function gate(item) that returns yes when level meets the cap, otherwise no.",
            "gate.py", "gate",
            [dict(name="level", type="int"), dict(name="cap", type="int")],
            "return yes when level meets the cap, otherwise no",
            [({"level": 5, "cap": 4}, "yes"), ({"level": 2, "cap": 4}, "no")],
            [({"level": 7, "cap": 7}, "yes"), ({"level": 0, "cap": 1}, "no")],
            lambda item: "yes" if item["level"] >= item["cap"] else "no",
        ),
        _task(
            "assess_list", "assessment", "list_processing",
            "Create function rev_vals(item) that returns values reversed.",
            "rev.py", "rev_vals",
            [dict(name="values", type="list")],
            "return values reversed",
            [({"values": [1, 2, 3]}, [3, 2, 1])],
            [({"values": [8, 0]}, [0, 8])],
            lambda item: list(reversed(item["values"])),
        ),
        _task(
            "assess_nested", "assessment", "nested_record",
            "Create function city_of(item) that returns the nested address city in lowercase.",
            "city.py", "city_of",
            [dict(name="city", type="str", path=["addr", "city"])],
            "return the city in lowercase",
            [({"addr": {"city": "Oslo"}}, "oslo")],
            [({"addr": {"city": "Berne"}}, "berne")],
            lambda item: str(item["addr"]["city"]).lower(),
        ),
        _task(
            "dev_missing", "missing_value", "missing_optional",
            "Create function mark(item) that returns room and shelf in lowercase joined by one slash.",
            "mark.py", "mark",
            [dict(name="room", type="str", presence="optional"),
             dict(name="shelf", type="str", presence="optional")],
            "join room and shelf; do not invent defaults",
            [({"room": "East", "shelf": "B2"}, "east/b2"), ({"shelf": "B2"}, "/b2")],
            [({"room": "West", "shelf": "C9"}, "west/c9"), ({"room": "West"}, "west/")],
            lambda item: str(item.get("room") or "").lower() + "/" + str(item.get("shelf") or "").lower(),
        ),
    ]


def tasks_for(split: str) -> list[dict[str, Any]]:
    return [row for row in catalogue() if row["split"] == split]


def with_output_docs(task: dict[str, Any]) -> dict[str, Any]:
    row = dict(task)
    docs = list(task.get("docs") or [])
    text = describe_output_contract(task["contract"])
    if text and not any(doc.get("title") == "output contract" for doc in docs):
        docs.append({"title": "output contract", "content": text})
    row["docs"] = docs
    return row


def score_task(task: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    scored = score_files(task, files)
    public = apply_output_contract(scored["public"], task["contract"])
    private = apply_output_contract(scored["private"], task["contract"])
    return dict(
        public_passed=public.get("status") == "passed",
        private_passed=private.get("status") == "passed",
        public=public,
        private=private,
        output_contract_violations=list(public.get("output_contract_violations") or [])
        + list(private.get("output_contract_violations") or []),
    )


def score_assembled_task(task: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    """Score the wrapped item function, then apply host-side yes/no labels."""
    scored = score_files(task, files)
    public = apply_trusted_assembly(scored["public"], task["public"], task["contract"])
    private = apply_trusted_assembly(scored["private"], task["private"], task["contract"])
    public = apply_output_contract(public, task["contract"])
    private = apply_output_contract(private, task["contract"])
    errors = list(public.get("output_assembly_errors") or []) + list(
        private.get("output_assembly_errors") or []
    )
    return dict(
        public_passed=public.get("status") == "passed",
        private_passed=private.get("status") == "passed",
        public=public,
        private=private,
        output_contract_violations=list(public.get("output_contract_violations") or [])
        + list(private.get("output_contract_violations") or []),
        output_assembly_errors=errors,
        trusted_output_assembly=True,
    )


def cost_block(contract_s: float, extraction_s: float, generation_s: float,
               validation_s: float, total_s: float, model_calls: int) -> dict[str, Any]:
    return dict(
        contract_source="benchmark_supplied",
        contract_acquisition_measured=False,
        contract_construction_s=round(contract_s, 6),
        contract_s=round(contract_s, 6),
        extraction_s=round(extraction_s, 6),
        generation_s=round(generation_s, 6),
        validation_s=round(validation_s, 6),
        total_s=round(total_s, 6),
        model_calls=model_calls,
        note="wrapper and construction time do not measure obtaining the contract",
    )


def scalar_request(task: dict[str, Any]) -> str:
    contract = task["contract"]
    args = ", ".join(row["name"] for row in contract["fields"])
    return f"Create function {contract['transform_symbol']}({args}) that {contract['behavior']}."


def generate_direct(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    contract_s = time.perf_counter()
    path = select_generation_path(task["contract"])
    contract_s = time.perf_counter() - contract_s
    if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
        raise TimeoutError("extraction_path_cap")
    task = with_output_docs(task)
    plan = plan_constrained_edit(task["request"], task["files"], task["public"])
    user = prompt_for_format("json_body", _prompt_task(task, task["files"]), plan, None)
    prompt, _meta = render_prompt("chatml", user)
    raw = model_complete(runtime, prompt)
    clock["calls"] += 1
    clock["inference_ran"] += int(raw["inference_ran"])
    assembled = assemble_format_proposal(
        "json_body", raw["content"], task["request"], task["files"], task["public"], plan=plan,
    )
    files = assembled.get("patched_files") or dict(task["files"])
    validate_started = time.perf_counter()
    scored = score_task(task, files)
    validation_s = time.perf_counter() - validate_started
    return dict(
        path="direct",
        selected_path=path,
        files=files,
        preview=assembled.get("preview"),
        public_passed=scored["public_passed"],
        private_passed=scored["private_passed"],
        failed=not scored["public_passed"],
        failure_type=classify_failure(scored["public"]),
        errors=public_errors(scored["public"]),
        output_contract_violations=scored["output_contract_violations"],
        current_function=target_source(files, task["public"][0]["entry"]),
        tested_symbol=task["contract"]["symbol"],
        silent_default=wrapper_uses_silent_default(files.get(plan.path, "")),
        cost=cost_block(contract_s, 0.0, raw["wall_s"], validation_s,
                        time.perf_counter() - started, 1),
        raw=raw["content"][:400],
        structurally_valid=bool(assembled.get("structurally_valid")),
    )


def generate_extract(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    contract_started = time.perf_counter()
    contract = task["contract"]
    if not extraction_eligible(contract):
        raise ValueError("extract_path_requires_required_fields")
    path = select_generation_path(contract)
    scalar_cases = scalar_public(contract, task["public"])
    contract_s = time.perf_counter() - contract_started
    if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
        raise TimeoutError("extraction_path_cap")
    task = with_output_docs(task)
    request = scalar_request(task)
    plan = plan_constrained_edit(request, task["files"], scalar_cases)
    user = prompt_for_format("json_body", _prompt_task(
        dict(task, request=request, public=scalar_cases), task["files"],
    ), plan, None)
    prompt, _meta = render_prompt("chatml", user)
    raw = model_complete(runtime, prompt)
    clock["calls"] += 1
    clock["inference_ran"] += int(raw["inference_ran"])
    assembled = assemble_format_proposal(
        "json_body", raw["content"], request, task["files"], scalar_cases, plan=plan,
    )
    transform_files = assembled.get("patched_files") or dict(task["files"])
    extract_started = time.perf_counter()
    transform_source = transform_files.get(plan.path, "")
    wrapper_source = wrap_transform(contract, transform_source)
    wrapped_files = dict(task["files"])
    wrapped_files[plan.path] = wrapper_source
    extraction_s = time.perf_counter() - extract_started
    validate_started = time.perf_counter()
    scored = score_task(task, wrapped_files)
    validation_s = time.perf_counter() - validate_started
    preview = preview_extraction(plan, transform_source, contract, wrapper_source)
    return dict(
        path="extract",
        selected_path=path,
        files=wrapped_files,
        preview=preview,
        public_passed=scored["public_passed"],
        private_passed=scored["private_passed"],
        failed=not scored["public_passed"],
        failure_type=classify_failure(scored["public"]),
        errors=public_errors(scored["public"]),
        output_contract_violations=scored["output_contract_violations"],
        current_function=wrapper_source,
        tested_symbol=contract["symbol"],
        transform_symbol=contract["transform_symbol"],
        silent_default=wrapper_uses_silent_default(wrapper_source),
        cost=cost_block(contract_s, extraction_s, raw["wall_s"], validation_s,
                        time.perf_counter() - started, 1),
        raw=raw["content"][:400],
        structurally_valid=bool(assembled.get("structurally_valid")),
    )


def generate_on_path(runtime, task: dict[str, Any], path: str, clock: dict[str, Any]) -> dict[str, Any]:
    if path == "extract":
        return generate_extract(runtime, task, clock)
    return generate_direct(runtime, task, clock)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("direct", "extract"):
        cells = [row[name] for row in rows]
        out[name] = dict(
            n=len(cells),
            first_attempt_public=sum(int(cell["public_passed"]) for cell in cells),
            first_attempt_private=sum(int(cell["private_passed"]) for cell in cells),
            silent_default=sum(int(cell["silent_default"]) for cell in cells),
            model_calls=sum(cell["cost"]["model_calls"] for cell in cells),
            total_s=round(sum(cell["cost"]["total_s"] for cell in cells), 6),
            generation_s=round(sum(cell["cost"]["generation_s"] for cell in cells), 6),
            contract_s=round(sum(cell["cost"]["contract_s"] for cell in cells), 6),
            extraction_s=round(sum(cell["cost"]["extraction_s"] for cell in cells), 6),
            validation_s=round(sum(cell["cost"]["validation_s"] for cell in cells), 6),
        )
    wins = dict(extract=0, direct=0, tie=0)
    for row in rows:
        e = int(row["extract"]["private_passed"])
        d = int(row["direct"]["private_passed"])
        if e > d:
            wins["extract"] += 1
        elif d > e:
            wins["direct"] += 1
        else:
            wins["tie"] += 1
    out["first_attempt_pair_wins"] = wins
    return out


def lock_path(dev_rows: list[dict[str, Any]]) -> str:
    summary = summarize(dev_rows)
    wins = summary["first_attempt_pair_wins"]
    if wins["extract"] > wins["direct"]:
        return "extract"
    if wins["direct"] > wins["extract"]:
        return "direct"
    return "direct"


def run_split(runtime, split: str, clock: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for task in tasks_for(split):
        if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
            break
        rows.append(dict(
            task_id=task["task_id"],
            family=task["family"],
            selected_path=task["selected_path"],
            contract=task["contract"],
            direct=generate_on_path(runtime, task, "direct", clock),
            extract=generate_on_path(runtime, task, "extract", clock),
        ))
    return rows


def run_extraction_path(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    development = run_split(runtime, "development", clock)
    winner = lock_path(development)
    assessment = None
    assessment_opened = False
    if winner == "extract":
        assessment_opened = True
        assessment = run_split(runtime, "assessment", clock)
    missing = [row for row in catalogue() if row["split"] == "missing_value"]
    usage = dict(
        kind="extraction_path_cpu_usage",
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
    import json
    payload = dict(
        kind="seed_extraction_path",
        confirmation=False,
        development_evidence=True,
        fresh_confirmation=False,
        learning_to_learn_established=False,
        learned_schema_understanding_claimed=False,
        opened_assessment_unused=list(OPENED_ASSESSMENT),
        locked_procedure=winner,
        assessment_opened=assessment_opened,
        keep_direct_when_tied=True,
        development=development,
        assessment=assessment,
        missing_value=dict(
            task_ids=[row["task_id"] for row in missing],
            selected_path=[row["selected_path"] for row in missing],
            extraction_eligible=[extraction_eligible(row["contract"]) for row in missing],
            note="optional fields keep the direct path; wrappers must not default missing keys",
        ),
        development_summary=summarize(development),
        assessment_summary=summarize(assessment) if assessment else None,
        usage=usage,
    )
    payload["hash"] = digest({k: payload[k] for k in (
        "kind", "locked_procedure", "development_summary", "usage", "assessment_opened",
    )})
    (directory / "recovery_live_usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return payload
