"""Stage a helper and its caller as a genuine multi-file edit.

Each function has its own destination, signature and output contract.
The pair is published only after helper behavior, caller behavior and
the required call all pass. Programmer-supplied route. Not extract
eligibility and not learned coordination.
"""
from __future__ import annotations

import time
from typing import Any

from .capability_evidence import digest
from .extraction_contract import make_contract
from .extraction_path import generate_direct
from .function_contracts import function_source, helper_import_path, score_bound_task
from .requirement_coverage import _calls_name, score_requirement_coverage


def helper_specs(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in task.get("function_stages") or [] if row.get("role") == "helper"]


def caller_spec(task: dict[str, Any]) -> dict[str, Any]:
    for row in task.get("function_stages") or []:
        if row.get("role") == "caller":
            return row
    raise KeyError("caller_stage_required")


def _scoped_helper_task(task: dict[str, Any], spec: dict[str, Any],
                        files: dict[str, str]) -> dict[str, Any]:
    args = ", ".join(spec["args"])
    request = (
        f"Add {spec['symbol']}({args}) to {spec['path']}. "
        f"{spec.get('behavior') or ''}"
    ).strip()
    fields = [dict(name=name, type=spec.get("arg_types", {}).get(name, "int")) for name in spec["args"]]
    contract = make_contract(
        spec["symbol"], fields, spec.get("behavior") or "",
        output_type=spec.get("output_type"),
        allowed_values=spec.get("allowed_values"),
    )
    public = [case for case in task["public"] if str(case.get("entry")) == spec["entry"]]
    private = [case for case in task.get("private") or [] if str(case.get("entry")) == spec["entry"]]
    return dict(
        task,
        request=request,
        files=files,
        contract=contract,
        public=public or task["public"],
        private=private or [],
        docs=task.get("docs"),
    )


def _scoped_caller_task(task: dict[str, Any], spec: dict[str, Any],
                        files: dict[str, str]) -> dict[str, Any]:
    helpers = helper_specs(task)
    helper = helpers[0]["symbol"] if helpers else ""
    helper_entry = helpers[0]["entry"] if helpers else ""
    interface = ""
    if helper_entry:
        interface = (
            "\nHelper interface (actual staged source):\n"
            + function_source(files, helper_entry)
            + "\n"
            + helper_import_path(helper_entry)
            + "\nCall this helper. Do not replace it with a constant unless the "
            "public request allows a constant."
        )
    request = (
        f"Create function {spec['symbol']}(item) in {spec['path']} using {helper}."
        + interface
    )
    return dict(
        task,
        request=request,
        files=files,
        contract=task["contract"],
        public=[case for case in task["public"] if str(case.get("entry")) == spec["entry"]],
        private=[],
        docs=task.get("docs"),
    )


def publish_ready(task: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    scored = score_bound_task(task, files)
    coverage = score_requirement_coverage(task["request"], files)
    helper_behavior = all(
        (scored.get("functions") or {}).get(spec["entry"], {}).get("behavior_public")
        for spec in helper_specs(task)
    ) if helper_specs(task) else True
    caller = caller_spec(task)
    caller_behavior = bool(
        (scored.get("functions") or {}).get(caller["entry"], {}).get("behavior_public")
    )
    helper_name = helper_specs(task)[0]["symbol"] if helper_specs(task) else ""
    caller_calls = bool(helper_name) and _calls_name(files.get(caller["path"], ""), helper_name)
    required_call = (not coverage.get("missing_apis")) and caller_calls
    ready = bool(
        scored.get("helper_present")
        and scored.get("caller_present")
        and required_call
        and helper_behavior
        and caller_behavior
    )
    receipt = passing_receipt(files, dict(
        helper_present=scored.get("helper_present"),
        caller_present=scored.get("caller_present"),
        required_call=required_call,
        helper_behavior=helper_behavior,
        caller_behavior=caller_behavior,
        public_passed=scored.get("public_passed"),
    ))
    return dict(
        ready=ready,
        helper_present=scored.get("helper_present"),
        caller_present=scored.get("caller_present"),
        required_call=required_call,
        helper_behavior=helper_behavior,
        caller_behavior=caller_behavior,
        private_passed=scored.get("private_passed"),
        receipt=receipt,
        scored=scored,
    )


def passing_receipt(files: dict[str, str], evidence: dict[str, Any]) -> str:
    return digest({
        "evidence": evidence,
        "files": {path: digest(source) for path, source in sorted(files.items())},
    })


def stage_pair(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    baseline = dict(task["files"])
    staged = dict(baseline)
    steps = []
    for spec in helper_specs(task):
        result = generate_direct(runtime, _scoped_helper_task(task, spec, staged), clock)
        staged[spec["path"]] = (result.get("files") or staged).get(spec["path"], staged[spec["path"]])
        steps.append(dict(role="helper", path=spec["path"], symbol=spec["symbol"]))
    caller = caller_spec(task)
    result = generate_direct(runtime, _scoped_caller_task(task, caller, staged), clock)
    staged[caller["path"]] = (result.get("files") or staged).get(caller["path"], staged[caller["path"]])
    steps.append(dict(role="caller", path=caller["path"], symbol=caller["symbol"]))
    gate = publish_ready(task, staged)
    bound = passing_receipt(staged, dict(
        helper_present=gate.get("helper_present"),
        caller_present=gate.get("caller_present"),
        required_call=gate.get("required_call"),
        helper_behavior=gate.get("helper_behavior"),
        caller_behavior=gate.get("caller_behavior"),
        public_passed=(gate.get("scored") or {}).get("public_passed"),
    ))
    publish = bool(gate["ready"] and gate.get("receipt") == bound)
    published = dict(staged) if publish else dict(baseline)
    final = score_bound_task(task, published)
    return dict(
        route="staged_pair",
        programmer_supplied_staging=True,
        published=gate["ready"],
        publish_gate=gate,
        steps=steps,
        staged_files=staged,
        files=published,
        helper_present=final.get("helper_present"),
        caller_present=final.get("caller_present"),
        required_call=final.get("required_call"),
        public_passed=final.get("public_passed"),
        private_passed=final.get("private_passed"),
        functions=final.get("functions") or {},
        passed=bool(gate["ready"] and final.get("private_passed")),
        wall_s=round(time.perf_counter() - started, 6),
    )
