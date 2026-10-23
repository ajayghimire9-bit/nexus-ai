"""Per-function signature and return contracts, plus caller revision context.

Each entry uses its own return requirements. An item yes/no contract does
not score a helper Boolean. Caller revision includes helper source, import
path, failed coverage and execution results.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from .constrained_edit import plan_constrained_edit
from .extraction_contract import EXPECTED_BOOLEAN, apply_output_contract, trusted_assemble_result
from .function_format import prompt_for_format
from .public_failure import public_revision_feedback, serialize_revision_feedback
from .recovery_evaluate import score_files
from .recovery_live import _prompt_task
from .requirement_coverage import score_requirement_coverage

YES_NO = ("yes", "no")


def bind_function_contract(entry: str, symbol: str, args: list[str],
                           output_type: str | None, *,
                           allowed_values: list[Any] | None = None,
                           behavior: str = "") -> dict[str, Any]:
    return dict(
        entry=entry,
        symbol=symbol,
        args=list(args),
        signature=f"{symbol}({', '.join(args)})",
        output_type=output_type,
        allowed_values=list(allowed_values) if allowed_values is not None else None,
        behavior=behavior,
    )


def function_source(files: dict[str, str], entry: str) -> str:
    filename, _, symbol = entry.partition(".")
    source = files.get(filename + ".py", "")
    try:
        tree = ast.parse(source or "")
    except SyntaxError:
        return source
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == symbol:
            return ast.unparse(node)
    return source


def helper_import_path(entry: str) -> str:
    filename, _, symbol = entry.partition(".")
    return f"from {Path(filename).stem} import {symbol}"


def check_function_contract(item: dict[str, Any], contract: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Reject type mismatches. Does not convert values."""
    copy = dict(item)
    if copy.get("error") or not contract:
        return copy, []
    actual = copy.get("actual")
    kind = contract.get("output_type")
    allowed = contract.get("allowed_values")
    notes: list[str] = []
    if kind == "bool":
        if type(actual) is not bool:
            copy["passed"] = False
            copy["output_contract_error"] = EXPECTED_BOOLEAN
            notes.append(EXPECTED_BOOLEAN)
        return copy, notes
    if list(allowed or []) == list(YES_NO) and type(actual) is bool:
        message = apply_output_contract(
            {"results": [copy]},
            dict(allowed_values=list(allowed)),
        )["results"][0].get("output_contract_error")
        if message:
            copy["passed"] = False
            copy["output_contract_error"] = message
            notes.append(message)
        return copy, notes
    if kind == "int" and not (type(actual) is int and type(actual) is not bool):
        copy["passed"] = False
        copy["output_contract_error"] = "expected int"
        notes.append("expected int")
    elif kind == "str" and type(actual) is not str:
        copy["passed"] = False
        copy["output_contract_error"] = "expected str"
        notes.append("expected str")
    elif kind == "list" and type(actual) is not list:
        copy["passed"] = False
        copy["output_contract_error"] = "expected list"
        notes.append("expected list")
    return copy, notes


def apply_bound_contracts(report: dict[str, Any], cases: list[dict[str, Any]],
                          contracts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Score each result with the contract of its entry only."""
    row = dict(report)
    results = []
    notes: list[str] = []
    assembly_errors: list[str] = []
    case_list = list(cases or [])
    for index, item in enumerate(list(report.get("results") or [])):
        case = case_list[index] if index < len(case_list) else {}
        entry = str(item.get("entry") or case.get("entry") or "")
        contract = contracts.get(entry) or {}
        copy = dict(item)
        allowed = list(contract.get("allowed_values") or [])
        if allowed == list(YES_NO):
            actual = copy.get("actual")
            expected = case.get("expected", copy.get("expected"))
            if type(actual) is bool:
                verdict = trusted_assemble_result(actual, contract)
                copy["helper_actual"] = verdict["helper_actual"]
                if verdict["ok"]:
                    copy["actual"] = verdict["label"]
                    copy["passed"] = verdict["label"] == expected
                    copy["output_assembly_error"] = None
                else:
                    copy["passed"] = False
                    copy["output_assembly_error"] = verdict["error"]
                    assembly_errors.append(verdict["error"])
            elif actual in allowed:
                copy["passed"] = actual == expected
            else:
                copy["passed"] = False
                copy["output_contract_error"] = (
                    EXPECTED_BOOLEAN if type(actual) is not bool else f"expected one of {allowed}"
                )
                notes.append(copy["output_contract_error"])
        copy, extra = check_function_contract(copy, contract)
        notes.extend(extra)
        results.append(copy)
    row["results"] = results
    if results:
        row["status"] = "passed" if all(item.get("passed") for item in results) else "failed"
    row["output_contract_violations"] = notes
    row["output_assembly_errors"] = assembly_errors
    return row


def has_definition(files: dict[str, str], path: str, symbol: str) -> bool:
    source = files.get(path, "")
    try:
        tree = ast.parse(source or "")
    except SyntaxError:
        return f"def {symbol}" in source
    return any(
        isinstance(node, ast.FunctionDef) and node.name == symbol
        for node in ast.walk(tree)
    )


def _required_helpers(task: dict[str, Any], coverage: dict[str, Any]) -> list[dict[str, Any]]:
    main = (task.get("contract") or {}).get("symbol")
    return [
        row for row in (coverage.get("required") or {}).get("functions") or []
        if row.get("symbol") != main
    ]


def helper_is_present(task: dict[str, Any], coverage: dict[str, Any],
                      files: dict[str, str] | None = None) -> bool:
    helpers = _required_helpers(task, coverage)
    if not helpers:
        return True
    missing = {
        (row.get("file"), row.get("symbol"))
        for row in coverage.get("missing_functions") or []
    }
    if files is not None:
        return all(has_definition(files, row["file"], row["symbol"]) for row in helpers)
    return all((row.get("file"), row.get("symbol")) not in missing for row in helpers)


def caller_is_present(task: dict[str, Any], coverage: dict[str, Any],
                      files: dict[str, str]) -> bool:
    symbol = (task.get("contract") or {}).get("symbol") or ""
    path = "app.py"
    for case in task.get("public") or []:
        entry = str(case.get("entry") or "")
        if entry.endswith("." + symbol):
            path = entry.split(".", 1)[0] + ".py"
            break
    required = [
        row for row in (coverage.get("required") or {}).get("functions") or []
        if row.get("symbol") == symbol
    ]
    if required:
        missing = {
            (row.get("file"), row.get("symbol"))
            for row in coverage.get("missing_functions") or []
        }
        return all((row["file"], row["symbol"]) not in missing for row in required)
    return has_definition(files, path, symbol)


def function_reports(task: dict[str, Any], public: dict[str, Any],
                     private: dict[str, Any]) -> dict[str, dict[str, Any]]:
    contracts = dict(task.get("function_contracts") or {})
    main = (task.get("contract") or {}).get("symbol")
    reports = {}
    for entry, contract in contracts.items():
        pub = [row for row in public.get("results") or [] if row.get("entry") == entry]
        priv = [row for row in private.get("results") or [] if row.get("entry") == entry]
        rows = pub + priv
        present = bool(rows) and not any(
            str(row.get("error") or "").startswith("missing_entry") for row in rows
        )
        type_notes = [
            row.get("output_contract_error") for row in rows if row.get("output_contract_error")
        ]
        reports[entry] = dict(
            entry=entry,
            symbol=contract.get("symbol"),
            role="caller" if contract.get("symbol") == main else "helper",
            present=present,
            types_ok=None if not present else not type_notes,
            behavior_public=bool(pub) and all(row.get("passed") for row in pub),
            behavior_private=bool(priv) and all(row.get("passed") for row in priv),
        )
    return reports


def caller_edit_plan(task: dict[str, Any], files: dict[str, str]):
    """Plan the caller only. The full request may name the helper first."""
    symbol = (task.get("contract") or {}).get("symbol") or "item"
    cases = [
        case for case in task.get("public") or []
        if str(case.get("entry", "")).endswith("." + symbol)
    ]
    path = "app.py"
    if cases:
        path = str(cases[0]["entry"]).split(".", 1)[0] + ".py"
    request = f"Create function {symbol}(item) in {path}."
    return plan_constrained_edit(request, files, cases)


def score_bound_task(task: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    contracts = dict(task.get("function_contracts") or {})
    scored = score_files(task, files)
    public = apply_bound_contracts(scored["public"], task["public"], contracts)
    private = apply_bound_contracts(scored["private"], task["private"], contracts)
    coverage = score_requirement_coverage(task["request"], files)
    functions = function_reports(task, public, private)
    helper_ok = helper_is_present(task, coverage, files)
    caller_ok = caller_is_present(task, coverage, files)
    required_call = not coverage.get("missing_apis")
    present_types = [
        row["types_ok"] for row in functions.values() if row["present"] and row["types_ok"] is not None
    ]
    types_ok = bool(caller_ok) and all(present_types) if present_types or caller_ok else False
    return dict(
        public_passed=public.get("status") == "passed",
        private_passed=private.get("status") == "passed",
        public=public,
        private=private,
        requirement_coverage=coverage,
        coverage_passed=bool(coverage["passed"]),
        helper_present=helper_ok,
        caller_present=caller_ok,
        required_call=required_call,
        real_call=required_call,
        functions=functions,
        types_ok=types_ok,
        complete_private=bool(
            public.get("status") == "passed"
            and private.get("status") == "passed"
            and coverage["passed"]
            and types_ok
        ),
        output_contract_violations=list(public.get("output_contract_violations") or [])
        + list(private.get("output_contract_violations") or []),
        bound_contracts=True,
        independent_coverage=True,
    )


def caller_revision_feedback(task: dict[str, Any], files: dict[str, str],
                             public: dict[str, Any] | None,
                             coverage: dict[str, Any] | None) -> dict[str, Any]:
    """Revision context for the caller: helper, import, coverage, results."""
    contracts = dict(task.get("function_contracts") or {})
    main = task.get("contract") or {}
    main_entry = next(
        (entry for entry, row in contracts.items() if row.get("symbol") == main.get("symbol")),
        "",
    )
    helpers = [row for entry, row in contracts.items() if entry != main_entry]
    sources = []
    imports = []
    for row in helpers:
        sources.append(function_source(files, row["entry"]))
        imports.append(helper_import_path(row["entry"]))
    execution = public_revision_feedback(public, task.get("public") or [])
    failed = None
    if coverage and not coverage.get("passed"):
        failed = dict(
            missing_files=coverage.get("missing_files") or [],
            missing_functions=coverage.get("missing_functions") or [],
            missing_apis=coverage.get("missing_apis") or [],
        )
    instruction = (
        "The caller failed. Use the helper via its import path. "
        "Do not inline the helper. Public tests and coverage are listed."
    )
    return dict(
        validation_error="caller_revision",
        placeholder_rejected=False,
        instruction=instruction,
        helper_source="\n\n".join(sources),
        import_path="; ".join(imports),
        failed_coverage=failed,
        execution_results=execution.get("public_results") or [],
        public_results=execution.get("public_results") or [],
        caller_revision=True,
        exceptions_included=True,
        operator_supplied=False,
    )


def caller_revision_prefix(feedback: dict[str, Any]) -> str:
    parts = []
    if feedback.get("import_path"):
        parts.append("Import path: " + str(feedback["import_path"]))
    if feedback.get("helper_source"):
        parts.append("Helper source:\n" + str(feedback["helper_source"])[:800])
    if feedback.get("failed_coverage"):
        parts.append("Failed coverage: " + json.dumps(feedback["failed_coverage"], allow_nan=False)[:500])
    return "\n".join(parts)


def caller_revision_prompt(task: dict[str, Any], files: dict[str, str], plan,
                           public: dict[str, Any] | None,
                           coverage: dict[str, Any] | None) -> tuple[str, dict[str, Any], str]:
    feedback = caller_revision_feedback(task, files, public, coverage)
    user = prompt_for_format("json_body", _prompt_task(task, files), plan, feedback)
    prefix = caller_revision_prefix(feedback)
    if prefix and prefix not in user:
        user = prefix + "\n" + user
    dumped = serialize_revision_feedback(feedback)
    return user, feedback, dumped
