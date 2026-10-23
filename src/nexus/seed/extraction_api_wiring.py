"""API selection versus programmer-supplied import/call wiring.

The model chooses the API and argument shape. An assembler writes the
import and call. That assembly is not learned. Fresh libraries stay
closed until this procedure is frozen.
"""
from __future__ import annotations

import ast
import json
import re
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .chat_template import render_prompt
from .extraction_api_context import context_catalogue, derive_compact_interface
from .extraction_contract import (
    describe_helper_output_contract, make_contract, mapping_item, wrap_transform,
)
from .extraction_path import CALL_CAP, WALL_CAP_S, generate_direct, with_output_docs
from .function_contracts import (
    bind_function_contract, caller_edit_plan, caller_revision_prompt, score_bound_task,
)
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .requirement_coverage import public_requirements

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PROCEDURE = "select_then_assemble"
RESERVED_IDS = ("inform_fold_span",)
OPENED = (
    "dev_use_scale", "assess_use_shift", "dev_two_file", "assess_two_file",
    "dev_opt_tag", "dev_any_kind", "dev_and_gate", "assess_opt_mark",
    "assess_any_role", "assess_and_span",
)

SELECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "api": {"type": "string", "minLength": 1, "maxLength": 64},
        "bindings": {
            "type": "array",
            "items": {"type": "string", "minLength": 1, "maxLength": 32},
            "minItems": 1,
            "maxItems": 8,
        },
        "over": {"type": "string", "maxLength": 32},
    },
    "required": ["api", "bindings"],
    "additionalProperties": False,
}


def _echo() -> str:
    return "def echo(text):\n    return text\n"


def gold_selections() -> dict[str, dict[str, Any]]:
    return {
        "dev_clip_span": dict(api="clip_span", bindings=["vals", "lo", "hi"], over=""),
        "dev_join_marks": dict(api="join_marks", bindings=["parts", "sep"], over=""),
        "dev_coord_within": dict(api="within", bindings=["load", "need"], over="loads"),
        "inform_fold_span": dict(api="fold_span", bindings=["vals", "width"], over=""),
    }


def gold_id_selections() -> dict[str, dict[str, Any]]:
    return {
        "dev_clip_span": dict(api_id="measures.clip_span", bindings=["field.vals", "field.lo", "field.hi"]),
        "dev_join_marks": dict(api_id="labels.join_marks", bindings=["field.parts", "field.sep"]),
        "dev_coord_within": dict(api_id="util.within", bindings=["elem.loads", "field.need"]),
        "inform_fold_span": dict(api_id="measures.fold_span", bindings=["field.vals", "field.width"]),
    }


def attach_function_contracts(task: dict[str, Any]) -> dict[str, Any]:
    row = dict(task)
    contract = task["contract"]
    entry = next(
        (case["entry"] for case in task["public"] if str(case["entry"]).endswith("." + contract["symbol"])),
        "app." + contract["symbol"],
    )
    contracts = {
        entry: bind_function_contract(
            entry, contract["symbol"], ["item"], contract.get("output_type"),
            allowed_values=contract.get("allowed_values"),
            behavior=contract.get("behavior") or "",
        ),
    }
    for case in list(task["public"]) + list(task["private"]):
        other = str(case.get("entry") or "")
        if other and other not in contracts:
            symbol = other.split(".", 1)[-1]
            args = list((case.get("input") or {}).keys()) if case.get("kwargs_input") else ["item"]
            expected = case.get("expected")
            kind = "bool" if type(expected) is bool else contract.get("output_type")
            contracts[other] = bind_function_contract(
                other, symbol, args, kind,
                allowed_values=None if kind == "bool" else contract.get("allowed_values"),
            )
    row["function_contracts"] = contracts
    row["gold_selection"] = dict(gold_selections().get(task["task_id"]) or {})
    return row


def available_interfaces(files: dict[str, str]) -> str:
    blocks = []
    for path, source in files.items():
        try:
            tree = ast.parse(source or "")
        except SyntaxError:
            continue
        module = Path(path).stem
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name in {"echo"} or node.name.startswith("_"):
                continue
            args = [arg.arg for arg in node.args.args]
            note = ast.unparse(node.body[0])[:160] if node.body else ""
            blocks.append(
                f"Import: from {module} import {node.name}. "
                f"Signature: {node.name}({', '.join(args)}). "
                f"Semantics: {note}."
            )
    return " ".join(blocks) if blocks else "Interface: none derived."


def infer_param_kinds(node: ast.FunctionDef) -> dict[str, str]:
    iterated: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.For) and isinstance(child.iter, ast.Name):
            iterated.add(child.iter.id)
        if isinstance(child, ast.comprehension) and isinstance(child.iter, ast.Name):
            iterated.add(child.iter.id)
    return {arg.arg: ("list" if arg.arg in iterated else "scalar") for arg in node.args.args}


def listed_functions(files: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    for path, source in files.items():
        try:
            tree = ast.parse(source or "")
        except SyntaxError:
            continue
        module = Path(path).stem
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name in {"echo"} or node.name.startswith("_"):
                continue
            kinds = infer_param_kinds(node)
            rows.append(dict(
                id=f"{module}.{node.name}",
                module=module,
                name=node.name,
                path=path,
                params=[dict(name=arg.arg, type=kinds[arg.arg]) for arg in node.args.args],
            ))
    return rows


def contract_ids(task: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    """API and field IDs offered as constrained choices. Not schema discovery."""
    fields = []
    for row in task["contract"]["fields"]:
        field_id = "field." + row["name"]
        access = "item" + mapping_item(row)
        fields.append(dict(
            id=field_id,
            kind="field",
            name=row["name"],
            type=row["type"],
            path=list(row["path"]),
            access=access,
        ))
        if row["type"] == "list":
            fields.append(dict(
                id="elem." + row["name"],
                kind="elem",
                name=row["name"],
                type="scalar",
                path=list(row["path"]),
                access=access,
                over=field_id,
            ))
    return dict(
        apis=listed_functions(files),
        fields=fields,
        output_space_narrowed=True,
        learned_schema_discovery=False,
    )


def selection_id_schema(ids: dict[str, Any]) -> dict[str, Any]:
    api_enum = [row["id"] for row in ids["apis"]] or ["none"]
    field_enum = [row["id"] for row in ids["fields"]] or ["none"]
    return {
        "type": "object",
        "properties": {
            "api_id": {"type": "string", "enum": api_enum},
            "bindings": {
                "type": "array",
                "items": {"type": "string", "enum": field_enum},
                "minItems": 1,
                "maxItems": 8,
            },
        },
        "required": ["api_id", "bindings"],
        "additionalProperties": False,
    }


def _field_lookup(contract: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_name = {row["name"]: row for row in contract.get("fields") or []}
    by_path = {".".join(row["path"]): row for row in contract.get("fields") or []}
    return by_name, by_path


def diagnose_api(name: str, gold: dict[str, Any], files: dict[str, str],
                 caller: str) -> dict[str, Any]:
    bare = name.split(".")[-1] if name else ""
    prefix = name.rsplit(".", 1)[0] if "." in (name or "") else ""
    module, path = find_module(bare, files)
    if name == gold.get("api") or (not prefix and bare == gold.get("api")):
        return dict(value=name, diagnosis="correct", resolved=bare)
    if prefix and bare == gold.get("api") and module == prefix:
        return dict(value=name, diagnosis="qualified_api", resolved=bare)
    if name == caller or bare == caller:
        return dict(value=name, diagnosis="wrong_selection", resolved=bare)
    if module is not None and bare != gold.get("api"):
        return dict(value=name, diagnosis="wrong_selection", resolved=bare)
    return dict(value=name, diagnosis="wrong_selection", resolved=bare)


def diagnose_binding(value: str, gold_name: str, gold_over: str,
                     contract: dict[str, Any]) -> dict[str, Any]:
    by_name, by_path = _field_lookup(contract)
    last = value.split(".")[-1] if value else ""
    dotted = "." in (value or "")
    field = by_name.get(value) or by_path.get(value) or by_name.get(last)
    diagnoses: list[str] = []
    if dotted:
        diagnoses.append("unsupported_notation")
    matched = None
    if field:
        matched = field["name"]
    elif last in by_name:
        matched = last
    if matched == gold_name:
        if not diagnoses:
            diagnoses.append("correct")
        return dict(value=value, diagnoses=diagnoses, resolved=matched)
    if gold_over and matched == gold_over:
        diagnoses.append("wrong_argument_shape")
        return dict(value=value, diagnoses=diagnoses, resolved=matched)
    if matched and matched != gold_name:
        diagnoses.append("wrong_field")
        return dict(value=value, diagnoses=diagnoses, resolved=matched)
    if not diagnoses:
        diagnoses.append("wrong_field")
    return dict(value=value, diagnoses=diagnoses, resolved=matched)


def diagnose_proposal(proposal: dict[str, Any] | None, gold: dict[str, Any],
                      files: dict[str, str], contract: dict[str, Any],
                      caller: str) -> dict[str, Any]:
    row = proposal or {}
    api = diagnose_api(str(row.get("api") or ""), gold, files, caller)
    gold_bindings = list(gold.get("bindings") or [])
    gold_over = str(gold.get("over") or "")
    proposed = list(row.get("bindings") or [])
    bindings = [
        diagnose_binding(
            proposed[index] if index < len(proposed) else "",
            gold_bindings[index] if index < len(gold_bindings) else "",
            gold_over if index == 0 else "",
            contract,
        )
        for index in range(max(len(proposed), len(gold_bindings)))
    ]
    over = str(row.get("over") or "")
    over_diagnosis = "correct"
    if over != gold_over:
        over_diagnosis = "wrong_argument_shape"
    if len(proposed) != len(gold_bindings):
        for item in bindings:
            if "wrong_argument_shape" not in item["diagnoses"] and "correct" not in item["diagnoses"]:
                item["diagnoses"].append("wrong_argument_shape")
    return dict(
        api=api,
        bindings=bindings,
        over=dict(value=over, gold=gold_over, diagnosis=over_diagnosis),
        same_diagnosis_forbidden=True,
    )


def assemble_id_wiring(proposal: dict[str, Any], ids: dict[str, Any],
                       contract: dict[str, Any]) -> dict[str, Any]:
    """Validate types and build access expressions. Programmer-supplied."""
    api = next((row for row in ids["apis"] if row["id"] == proposal.get("api_id")), None)
    if api is None:
        return dict(ok=False, source="", error="unknown_api_id", programmer_supplied=True)
    raw_bindings = proposal.get("bindings")
    if isinstance(raw_bindings, dict):
        extra = sorted(set(raw_bindings) - {row["name"] for row in api["params"]})
        if extra:
            return dict(ok=False, source="", error="extra_bindings", extra=extra, programmer_supplied=True)
        bindings = [raw_bindings.get(row["name"]) for row in api["params"]]
        if any(item is None for item in bindings):
            return dict(ok=False, source="", error="missing_required", programmer_supplied=True)
    else:
        bindings = list(raw_bindings or [])
    required = [row for row in api["params"] if not row.get("optional")]
    if len(bindings) < len(required):
        return dict(ok=False, source="", error="missing_required", programmer_supplied=True)
    if len(bindings) > len(api["params"]):
        return dict(
            ok=False, source="", error="binding_count",
            expected=len(api["params"]), actual=len(bindings), programmer_supplied=True,
        )
    uses = []
    accesses = []
    over_name = ""
    for index, bid in enumerate(bindings):
        field = next((row for row in ids["fields"] if row["id"] == bid), None)
        if field is None:
            return dict(ok=False, source="", error="unknown_field_id", programmer_supplied=True)
        param = api["params"][index] if index < len(api["params"]) else None
        got = "list" if field["kind"] == "field" and field["type"] == "list" else "scalar"
        if param is not None and param["type"] != got:
            return dict(
                ok=False, source="", error="type_mismatch",
                expected=param["type"], actual=got, programmer_supplied=True,
            )
        accesses.append(field["access"])
        if field["kind"] == "elem":
            over_name = field["name"]
            uses.append("element")
        else:
            uses.append(field["name"])
    helper = contract["transform_symbol"]
    args = ", ".join(row["name"] for row in contract["fields"])
    call = f"{api['name']}({', '.join(uses)})"
    if over_name:
        body = f"return all({call} for element in {over_name})"
    else:
        body = f"return {call}"
    source = (
        f"from {api['module']} import {api['name']}\n"
        f"def {helper}({args}):\n"
        f"    {body}\n"
    )
    if "sum(" in source:
        raise ValueError("assembler_leaked_sum_composition")
    return dict(
        ok=True,
        source=source,
        error=None,
        import_line=f"from {api['module']} import {api['name']}",
        call=call,
        accesses=accesses,
        programmer_supplied=True,
        learned_assembly=False,
        learned_schema_discovery=False,
        output_space_narrowed=True,
    )


def find_module(api: str, files: dict[str, str]) -> tuple[str | None, str | None]:
    for path, source in files.items():
        try:
            tree = ast.parse(source or "")
        except SyntaxError:
            if f"def {api}(" in (source or ""):
                return Path(path).stem, path
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == api:
                return Path(path).stem, path
    return None, None


def parse_id_selection(content: str) -> dict[str, Any] | None:
    raw = (content or "").strip()
    if "{" not in raw or "}" not in raw:
        return None
    try:
        payload = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        return None
    if type(payload) is not dict:
        return None
    api_id = payload.get("api_id")
    bindings = payload.get("bindings")
    if type(api_id) is not str or type(bindings) is not list:
        return None
    if not api_id or not all(type(item) is str for item in bindings):
        return None
    return dict(api_id=api_id.strip(), bindings=[item.strip() for item in bindings])


def parse_selection(content: str) -> dict[str, Any] | None:
    raw = (content or "").strip()
    if "{" not in raw or "}" not in raw:
        return None
    try:
        payload = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        return None
    if type(payload) is not dict:
        return None
    api = payload.get("api")
    bindings = payload.get("bindings")
    if type(api) is not str or type(bindings) is not list:
        return None
    if not api or not all(type(item) is str for item in bindings):
        return None
    return dict(
        api=api.strip(),
        bindings=[item.strip() for item in bindings],
        over=str(payload.get("over") or "").strip(),
    )


def selection_matches(proposal: dict[str, Any] | None, gold: dict[str, Any]) -> dict[str, bool]:
    row = proposal or {}
    api_ok = row.get("api") == gold.get("api")
    bind_ok = list(row.get("bindings") or []) == list(gold.get("bindings") or [])
    over_ok = (row.get("over") or "") == (gold.get("over") or "")
    return dict(
        api_correct=api_ok,
        bindings_correct=bind_ok,
        over_correct=over_ok,
        selection_correct=api_ok and bind_ok and over_ok,
    )


def assemble_api_wiring(proposal: dict[str, Any], files: dict[str, str],
                        contract: dict[str, Any]) -> dict[str, Any]:
    """Write the import and call. Programmer-supplied. Not the target composition."""
    api = proposal.get("api") or ""
    bindings = list(proposal.get("bindings") or [])
    over = str(proposal.get("over") or "")
    names = [api, *bindings, *([over] if over else [])]
    if not all(IDENT.match(name or "") for name in names):
        return dict(ok=False, source="", error="invalid_identifier", programmer_supplied=True)
    module, path = find_module(api, files)
    if module is None:
        return dict(ok=False, source="", error="unknown_api", programmer_supplied=True)
    args = ", ".join(row["name"] for row in contract["fields"])
    helper = contract["transform_symbol"]
    call = f"{api}({', '.join(bindings)})"
    if over:
        elem = bindings[0] if bindings else "item"
        body = f"return all({call} for {elem} in {over})"
    else:
        body = f"return {call}"
    source = (
        f"from {module} import {api}\n"
        f"def {helper}({args}):\n"
        f"    {body}\n"
    )
    if "sum(" in source and "sum(" not in call:
        raise ValueError("assembler_leaked_sum_composition")
    return dict(
        ok=True,
        source=source,
        error=None,
        import_line=f"from {module} import {api}",
        call=call,
        module=module,
        path=path,
        programmer_supplied=True,
        learned_assembly=False,
    )


def selection_prompt(task: dict[str, Any], files: dict[str, str]) -> str:
    ids = contract_ids(task, files)
    compact = derive_compact_interface(task.get("docs") or [], files, task["request"])
    if "sum(" in compact:
        raise ValueError("selection_prompt_leaked_composition")
    interfaces = available_interfaces(files)
    if "sum(" in interfaces:
        raise ValueError("selection_prompt_leaked_composition")
    api_ids = ", ".join(row["id"] for row in ids["apis"]) or "none"
    field_ids = ", ".join(row["id"] for row in ids["fields"]) or "none"
    return (
        "Choose API and field IDs. Do not write the function body. "
        "Do not write the completed program.\n"
        'Return JSON {"api_id": "...", "bindings": ["field...."]}.\n'
        "Use only the listed IDs. field.X is the extracted field. "
        "elem.X is one element of a list field.\n"
        f"Request: {task['request']}\n"
        f"Valid API IDs: {api_ids}\n"
        f"Valid field IDs: {field_ids}\n"
        f"Available interfaces: {interfaces}\n"
        f"Compact interface: {compact}\n"
    )


def complete_with_schema(runtime, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    reply = runtime.complete(prompt, schema)
    tel = reply.get("telemetry") or {}
    return dict(
        content=reply.get("content") or "",
        inference_ran=bool(tel.get("inference_ran")),
        wall_s=float(tel.get("request_wall_s") or 0.0),
    )


def generate_selection(runtime, task: dict[str, Any], clock: dict[str, Any],
                       files: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    working = attach_function_contracts(with_output_docs(task))
    files = dict(files or working["files"])
    if clock["calls"] >= CALL_CAP or time.perf_counter() - clock["started"] >= WALL_CAP_S:
        raise TimeoutError("api_wiring_cap")
    ids = contract_ids(working, files)
    user = selection_prompt(working, files)
    prompt, _meta = render_prompt("chatml", user)
    raw = complete_with_schema(runtime, prompt, selection_id_schema(ids))
    clock["calls"] += 1
    clock["inference_ran"] += int(raw["inference_ran"])
    proposal = parse_id_selection(raw["content"])
    gold = gold_id_selections().get(working["task_id"]) or working["gold_selection"]
    match = dict(
        api_correct=bool(proposal) and proposal.get("api_id") == gold.get("api_id"),
        bindings_correct=bool(proposal) and list(proposal.get("bindings") or []) == list(gold.get("bindings") or []),
        over_correct=True,
        selection_correct=False,
    )
    match["selection_correct"] = match["api_correct"] and match["bindings_correct"]
    assembled = None
    wrapped = dict(files)
    if proposal is not None:
        assembled = assemble_id_wiring(proposal, ids, working["contract"])
        if assembled["ok"]:
            wrapped[_caller_path(working)] = wrap_transform(
                working["contract"], assembled["source"],
            )
    scored = score_bound_task(dict(working, files=files), wrapped)
    return dict(
        task_id=working["task_id"],
        path="select_then_assemble",
        programmer_supplied_api_assembly=True,
        learned_assembly=False,
        proposal=proposal,
        gold=gold,
        **match,
        assembled=assembled,
        files=wrapped,
        prompt_has_composition="sum(" in user and "clip_span" in working["request"],
        raw=raw["content"][:400],
        cost=dict(
            model_calls=1,
            generation_s=raw["wall_s"],
            total_s=round(time.perf_counter() - started, 6),
        ),
        ids=ids,
        output_space_narrowed=True,
        learned_schema_discovery=False,
        **{key: scored[key] for key in (
            "public_passed", "private_passed", "complete_private", "coverage_passed",
            "types_ok", "helper_present", "caller_present", "required_call", "real_call",
            "functions", "public", "private", "requirement_coverage",
            "output_contract_violations",
        )},
    )


def _caller_path(task: dict[str, Any]) -> str:
    symbol = task["contract"]["symbol"]
    for case in task["public"]:
        entry = str(case.get("entry") or "")
        if entry.endswith("." + symbol):
            return entry.split(".", 1)[0] + ".py"
    return "app.py"


def generate_composition(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    """Helper generation, then caller selection plus assembled wiring."""
    started = time.perf_counter()
    working = attach_function_contracts(with_output_docs(task))
    required = public_requirements(working["request"])
    files = dict(working["files"])
    helper_calls = 0
    helper_result = None
    for row in required["functions"]:
        if row["symbol"] == working["contract"]["symbol"]:
            continue
        helper_request = (
            f"Create function {row['symbol']}({row['args']}) that returns True "
            f"if value is at least limit, otherwise False."
        )
        helper_cases = [
            case for case in working["public"]
            if str(case.get("entry", "")).endswith("." + row["symbol"])
        ]
        helper_args = [part.strip() for part in row["args"].split(",") if part.strip()]
        helper_task = dict(
            working,
            request=helper_request,
            files=files,
            public=helper_cases or working["public"],
            private=[
                case for case in working["private"]
                if str(case.get("entry", "")).endswith("." + row["symbol"])
            ],
            contract=make_contract(
                row["symbol"],
                [dict(name=name, type="int") for name in helper_args],
                "return True if value is at least limit, otherwise False",
                output_type="bool",
            ),
            docs=[{"title": "helper output contract", "content": describe_helper_output_contract()}],
        )
        helper_result = generate_direct(runtime, helper_task, clock)
        helper_calls += 1
        files = dict(helper_result.get("files") or files)
    selected = generate_selection(runtime, dict(working, files=files), clock, files=files)
    merged = dict(selected.get("files") or files)
    for path, source in files.items():
        if path.endswith("util.py"):
            merged[path] = source
    scored = score_bound_task(dict(working, files=merged), merged)
    coverage = scored["requirement_coverage"]
    plan = caller_edit_plan(working, merged)
    revision_user, revision, _dumped = caller_revision_prompt(
        working, merged, plan, scored["public"], coverage,
    )
    return dict(
        task_id=working["task_id"],
        path="complete_composition",
        programmer_supplied_api_assembly=True,
        learned_assembly=False,
        helper=dict(
            files=files,
            public_passed=bool((helper_result or {}).get("public_passed")),
            model_calls=helper_calls,
        ),
        selection=selected,
        files=merged,
        revision_sees_helper="def within" in revision.get("helper_source", ""),
        revision_sees_import="from util import within" in revision.get("import_path", ""),
        revision_sees_coverage=revision.get("failed_coverage") is not None or scored["coverage_passed"],
        revision_sees_results=bool(revision.get("execution_results")),
        revision_prompt_excerpt=revision_user[:800],
        helper_present=scored["helper_present"],
        caller_present=scored["caller_present"],
        required_call=scored["required_call"],
        real_call=scored["real_call"],
        functions=scored["functions"],
        types_ok=scored["types_ok"],
        public_passed=scored["public_passed"],
        private_passed=scored["private_passed"],
        coverage_passed=scored["coverage_passed"],
        complete_private=scored["complete_private"],
        public=scored["public"],
        private=scored["private"],
        requirement_coverage=coverage,
        cost=dict(
            model_calls=helper_calls + int((selected.get("cost") or {}).get("model_calls") or 0),
            total_s=round(time.perf_counter() - started, 6),
            unequal_compute_disclosed=True,
        ),
    )


def tasks_for(split: str) -> list[dict[str, Any]]:
    return [attach_function_contracts(row) for row in context_catalogue() if row["split"] == split]


def lock_procedure(dev_rows: list[dict[str, Any]]) -> str:
    return PROCEDURE


def reserved_ready(dev_rows: list[dict[str, Any]], composition: dict[str, Any] | None) -> bool:
    selected = any(bool(row.get("selection_correct")) for row in dev_rows)
    composed = bool((composition or {}).get("complete_private"))
    return selected or composed


def audit_saved_proposals(payload: dict[str, Any]) -> dict[str, Any]:
    """Diagnose frozen free-string proposals. No new inference."""
    rows = []
    for task in context_catalogue():
        saved = None
        if task["family"] == "api_context":
            saved = next((row for row in payload.get("development") or [] if row.get("task_id") == task["task_id"]), None)
        elif task["family"] == "coordinated_edit":
            saved = (payload.get("composition") or {}).get("selection")
        if not saved:
            continue
        working = attach_function_contracts(task)
        files = saved.get("files") or working["files"]
        diagnosis = diagnose_proposal(
            saved.get("proposal"), working["gold_selection"], files,
            working["contract"], working["contract"]["symbol"],
        )
        rows.append(dict(
            task_id=task["task_id"],
            proposal=saved.get("proposal"),
            gold=working["gold_selection"],
            live_assembled_error=(saved.get("assembled") or {}).get("error"),
            diagnosis=diagnosis,
            historical_live_unchanged=True,
        ))
    return dict(
        kind="seed_extraction_api_wiring_proposal_audit",
        confirmation=False,
        new_inference=False,
        learning_to_learn_established=False,
        rows=rows,
    )


def summarize_selection(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return dict(
        n=len(rows),
        api_correct=sum(int(row.get("api_correct")) for row in rows),
        bindings_correct=sum(int(row.get("bindings_correct")) for row in rows),
        selection_correct=sum(int(row.get("selection_correct")) for row in rows),
        behavior_private=sum(int(row.get("private_passed")) for row in rows),
        coverage_passed=sum(int(row.get("coverage_passed")) for row in rows),
        complete_private=sum(int(row.get("complete_private")) for row in rows),
        unique_model_calls=sum(int((row.get("cost") or {}).get("model_calls") or 0) for row in rows),
    )


def run_api_wiring(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    development = [
        generate_selection(runtime, task, clock)
        for task in tasks_for("development")
        if task["family"] == "api_context"
    ]
    locked = lock_procedure(development)
    coord = [task for task in tasks_for("development") if task["family"] == "coordinated_edit"][0]
    composition = generate_composition(runtime, coord, clock)
    inform = []
    inform_opened = False
    if reserved_ready(development, composition):
        inform_opened = True
        fresh = [task for task in tasks_for("inform_next") if task["family"] == "api_context"][0]
        inform.append(generate_selection(runtime, fresh, clock))
    usage = dict(
        kind="extraction_api_wiring_cpu_usage",
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
        learned_assembly=False,
    )
    payload = dict(
        kind="seed_extraction_api_wiring",
        confirmation=False,
        informs_next_not_confirmation=True,
        learning_to_learn_established=False,
        historical_outcomes_unchanged=True,
        programmer_supplied_api_assembly=True,
        locked_procedure=locked,
        development=development,
        development_summary=summarize_selection(development),
        composition=composition,
        inform_opened=inform_opened,
        inform_next=inform,
        reserved_ids=list(RESERVED_IDS),
        opened_unused=list(OPENED),
        usage=usage,
    )
    payload["hash"] = digest({k: payload[k] for k in (
        "kind", "locked_procedure", "development_summary", "usage", "inform_opened",
    )})
    (directory / "recovery_live_usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return payload
