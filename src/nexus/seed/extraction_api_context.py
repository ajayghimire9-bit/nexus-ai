"""Diagnose API prompt context and compare docs with a compact interface.

Coverage follows the public request only. Compact interface is derived
from the same public docs and library source. It does not include the
target composition. Fresh libraries wait until the context is frozen.
"""
from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .constrained_edit import plan_constrained_edit
from .extraction_contract import describe_output_contract, make_contract
from .extraction_limits import limits_catalogue
from .extraction_path import (
    CALL_CAP, WALL_CAP_S, generate_direct, generate_extract, scalar_request,
    with_output_docs,
)
from .function_format import prompt_for_format
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .recovery_live import _prompt_task
from .requirement_coverage import public_requirements, score_requirement_coverage

CONTEXTS = ("existing_docs", "compact_interface")
OPENED = (
    "dev_use_scale", "assess_use_shift", "dev_two_file", "assess_two_file",
    "dev_opt_tag", "dev_any_kind", "dev_and_gate", "assess_opt_mark",
    "assess_any_role", "assess_and_span",
)
YES_NO = ("yes", "no")


def _echo() -> str:
    return "def echo(text):\n    return text\n"


def library_source(name: str) -> str:
    if name == "clip_span":
        return (
            "def clip_span(nums, lo, hi):\n"
            "    return [lo if n < lo else hi if n > hi else n for n in nums]\n"
        )
    if name == "join_marks":
        return (
            "def join_marks(parts, sep):\n"
            "    return sep.join(str(part).lower() for part in parts)\n"
        )
    if name == "fold_span":
        return (
            "def fold_span(nums, width):\n"
            "    return [n % width for n in nums]\n"
        )
    raise ValueError("unknown_library")


def derive_compact_interface(docs: list[dict[str, Any]], files: dict[str, str],
                             request: str) -> str:
    """Import, signature, types and semantics. Not the target composition."""
    required = public_requirements(request)
    names = []
    for api in required["apis"]:
        if api["name"] not in names:
            names.append(api["name"])
    for doc in docs or []:
        text = str(doc.get("content") or "")
        for token in text.replace(".", " ").split():
            if token in files or token.endswith(".py"):
                continue
    blocks = []
    for name in names:
        path = next((p for p, src in files.items() if f"def {name}" in src), None)
        if path is None:
            continue
        source = files[path]
        module = Path(path).stem
        try:
            tree = ast.parse(source)
        except SyntaxError:
            tree = None
        args = []
        returns = "unspecified"
        body_note = ""
        if tree is not None:
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name == name:
                    args = [arg.arg for arg in node.args.args]
                    if node.returns is not None:
                        returns = ast.unparse(node.returns)
                    if node.body:
                        body_note = ast.unparse(node.body[0])[:160]
        blocks.append(
            f"Import: from {module} import {name}. "
            f"Signature: {name}({', '.join(args)}). "
            f"Return: {returns}. "
            f"Semantics: {body_note}."
        )
    extra = []
    for doc in docs or []:
        text = str(doc.get("content") or "")
        if "is a " in text:
            extra.append(text)
    if extra:
        blocks.append("Fields: " + " ".join(extra))
    return " ".join(blocks) if blocks else "Interface: none derived."


def prompt_view(task: dict[str, Any], path: str) -> dict[str, Any]:
    working = with_output_docs(dict(task))
    if path == "extract":
        request = scalar_request(working)
        cases = working["public"]
        from .extraction_contract import scalar_public
        cases = scalar_public(working["contract"], working["public"])
        plan = plan_constrained_edit(request, working["files"], cases)
        user = prompt_for_format("json_body", _prompt_task(
            dict(working, request=request, public=cases), working["files"],
        ), plan, None)
    else:
        plan = plan_constrained_edit(working["request"], working["files"], working["public"])
        user = prompt_for_format("json_body", _prompt_task(working, working["files"]), plan, None)
        request = working["request"]
    sibling = [name for name in working["files"] if name != plan.path]
    compact = derive_compact_interface(working.get("docs") or [], working["files"], working["request"])
    return dict(
        path=path,
        plan_path=plan.path,
        plan_symbol=plan.symbol,
        request_sent=request,
        sibling_files=sibling,
        sibling_source_in_prompt=any(
            working["files"][name] in user and name != plan.path for name in sibling
        ),
        docs_in_prompt=[doc.get("content") for doc in (working.get("docs") or [])],
        mentions_import="import" in user.lower(),
        mentions_signature=any(
            f"def {api['name']}" in user for api in public_requirements(working["request"])["apis"]
        ),
        compact_interface=compact,
        prompt_excerpt=user[:1200],
        extraction_rewrote_request=path == "extract" and request != working["request"],
    )


def diagnose_opened_api() -> dict[str, Any]:
    rows = []
    for task in limits_catalogue():
        if task["family"] != "unfamiliar_api" or task["split"] != "development":
            continue
        direct = prompt_view(task, "direct")
        extract = prompt_view(task, "extract")
        rows.append(dict(
            task_id=task["task_id"],
            request=task["request"],
            files=sorted(task["files"]),
            library_source=task["files"].get("util.py", "")[:200],
            requirements=public_requirements(task["request"]),
            direct=direct,
            extract=extract,
            extraction_removed_docs=not any(
                "scale_points" in str(text) for text in extract["docs_in_prompt"]
            ),
            model_saw_library_source=direct["sibling_source_in_prompt"] or extract["sibling_source_in_prompt"],
        ))
    return dict(
        kind="api_prompt_diagnosis",
        learned_acquisition=False,
        rows=rows,
    )


def _task(task_id: str, split: str, family: str, request: str, files: dict[str, str],
          symbol: str, entry: str, fields: list[dict[str, Any]], behavior: str,
          public: list[tuple[Any, Any]], private: list[tuple[Any, Any]],
          reference, *, docs: list[dict[str, str]], output_type: str | None = None,
          allowed_values: list[Any] | None = None,
          extra_public: list[dict[str, Any]] | None = None,
          extra_private: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    contract = make_contract(symbol, fields, behavior, output_type, allowed_values)
    notes = list(docs)
    notes.append({"title": "output contract", "content": describe_output_contract(contract)})
    cases = [dict(entry=entry, input=inp, expected=exp) for inp, exp in public]
    hidden = [dict(entry=entry, input=inp, expected=exp) for inp, exp in private]
    cases.extend(extra_public or [])
    hidden.extend(extra_private or [])
    return dict(
        task_id=task_id,
        split=split,
        family=family,
        request=request,
        files=files,
        public=cases,
        private=hidden,
        contract=contract,
        docs=notes,
        reference=reference,
        origin="authored_extraction_api_context",
    )


def context_catalogue() -> list[dict[str, Any]]:
    return [
        _task(
            "dev_clip_span", "development", "api_context",
            "Create function total_clip(item) that returns the sum of clip_span on bin.vals.",
            {"app.py": _echo(), "measures.py": library_source("clip_span")},
            "total_clip", "app.total_clip",
            [dict(name="vals", type="list", path=["bin", "vals"]),
             dict(name="lo", type="int", path=["bin", "lo"]),
             dict(name="hi", type="int", path=["bin", "hi"])],
            "return the sum of clip_span on vals using lo and hi",
            [({"bin": {"vals": [0, 5, 12], "lo": 2, "hi": 8}}, 15)],
            [({"bin": {"vals": [2, 8], "lo": 2, "hi": 8}}, 10)],
            lambda item: sum(
                item["bin"]["lo"] if n < item["bin"]["lo"] else item["bin"]["hi"] if n > item["bin"]["hi"] else n
                for n in item["bin"]["vals"]
            ),
            docs=[{"title": "field notes",
                   "content": "bin.vals is a list. bin.lo is a int. bin.hi is a int. Use clip_span from measures."}],
            output_type="int",
        ),
        _task(
            "dev_join_marks", "development", "api_context",
            "Create function label_of(item) that returns join_marks on bag.parts.",
            {"app.py": _echo(), "labels.py": library_source("join_marks")},
            "label_of", "app.label_of",
            [dict(name="parts", type="list", path=["bag", "parts"]),
             dict(name="sep", type="str", path=["bag", "sep"])],
            "return join_marks on parts using sep",
            [({"bag": {"parts": ["Oak", "Elm"], "sep": "-"}}, "oak-elm")],
            [({"bag": {"parts": ["Ash"], "sep": "/"}}, "ash")],
            lambda item: str(item["bag"]["sep"]).join(
                str(part).lower() for part in item["bag"]["parts"]
            ),
            docs=[{"title": "field notes",
                   "content": "bag.parts is a list. bag.sep is a str. Use join_marks from labels."}],
            output_type="str",
        ),
        _task(
            "inform_fold_span", "inform_next", "api_context",
            "Create function total_fold(item) that returns the sum of fold_span on bin.vals.",
            {"app.py": _echo(), "measures.py": library_source("fold_span")},
            "total_fold", "app.total_fold",
            [dict(name="vals", type="list", path=["bin", "vals"]),
             dict(name="width", type="int", path=["bin", "width"])],
            "return the sum of fold_span on vals using width",
            [({"bin": {"vals": [5, 7], "width": 4}}, 4)],
            [({"bin": {"vals": [4], "width": 4}}, 0)],
            lambda item: sum(n % item["bin"]["width"] for n in item["bin"]["vals"]),
            docs=[{"title": "field notes",
                   "content": "bin.vals is a list. bin.width is a int. Use fold_span from measures."}],
            output_type="int",
        ),
        _task(
            "dev_coord_within", "development", "coordinated_edit",
            "Add within(value, limit) to util.py. Create function accept(item) in app.py that returns yes if every load is at least the need using within, otherwise no.",
            {"app.py": _echo(), "util.py": _echo()},
            "accept", "app.accept",
            [dict(name="loads", type="list", path=["pack", "loads"]),
             dict(name="need", type="int", path=["pack", "need"])],
            "return yes if every load is at least the need using within, otherwise no",
            [({"pack": {"loads": [5, 6], "need": 5}}, "yes"),
             ({"pack": {"loads": [5, 4], "need": 5}}, "no")],
            [({"pack": {"loads": [7], "need": 7}}, "yes")],
            lambda item: "yes" if all(value >= item["pack"]["need"] for value in item["pack"]["loads"]) else "no",
            docs=[{"title": "field notes",
                   "content": "pack.loads is a list. pack.need is a int."}],
            output_type="str", allowed_values=list(YES_NO),
            extra_public=[
                {"entry": "util.within", "input": {"value": 5, "limit": 5}, "kwargs_input": True, "expected": True},
                {"entry": "util.within", "input": {"value": 4, "limit": 5}, "kwargs_input": True, "expected": False},
            ],
            extra_private=[
                {"entry": "util.within", "input": {"value": 9, "limit": 9}, "kwargs_input": True, "expected": True},
            ],
        ),
    ]


def tasks_for(split: str) -> list[dict[str, Any]]:
    return [row for row in context_catalogue() if row["split"] == split]


def with_context(task: dict[str, Any], context: str) -> dict[str, Any]:
    row = dict(task)
    docs = [doc for doc in list(task.get("docs") or []) if doc.get("title") != "compact interface"]
    if context == "compact_interface":
        compact = derive_compact_interface(docs, task["files"], task["request"])
        if "sum(" in compact or "return the sum" in compact.lower():
            raise ValueError("compact_interface_leaked_composition")
        docs.append({"title": "compact interface", "content": compact})
    row["docs"] = docs
    row["context"] = context
    return row


def item_only(task: dict[str, Any]) -> dict[str, Any]:
    symbol = task["contract"]["symbol"]
    row = dict(task)
    row["public"] = [case for case in task["public"] if str(case.get("entry", "")).endswith("." + symbol)]
    row["private"] = [case for case in task["private"] if str(case.get("entry", "")).endswith("." + symbol)]
    return row


def stamp_coverage(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    coverage = score_requirement_coverage(task["request"], result.get("files") or task["files"])
    result["requirement_coverage"] = coverage
    result["behavior_private"] = bool(result.get("private_passed"))
    result["coverage_passed"] = bool(coverage["passed"])
    result["complete_private"] = bool(result.get("private_passed") and coverage["passed"])
    return result


def generate_coordinated(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    """Two billed calls: required helper file, then extract of the item function."""
    started = time.perf_counter()
    required = public_requirements(task["request"])
    files = dict(task["files"])
    helper_calls = 0
    for row in required["functions"]:
        if row["symbol"] == task["contract"]["symbol"]:
            continue
        helper_request = (
            f"Create function {row['symbol']}({row['args']}) that returns True "
            f"if value is at least limit, otherwise False."
        )
        helper_cases = [case for case in task["public"] if str(case.get("entry", "")).endswith("." + row["symbol"])]
        helper_task = dict(task, request=helper_request, files=files, public=helper_cases or task["public"])
        step = generate_direct(runtime, helper_task, clock)
        helper_calls += 1
        files = dict(step.get("files") or files)
    extracted = generate_extract(runtime, dict(item_only(task), files=files), clock)
    merged = dict(extracted.get("files") or {})
    for path, source in files.items():
        if path.endswith("util.py") or path not in merged:
            merged[path] = source if path.endswith("util.py") else merged.get(path, source)
    extracted["files"] = merged
    from .extraction_path import score_task
    scored = score_task(task, merged)
    extracted["public_passed"] = scored["public_passed"]
    extracted["private_passed"] = scored["private_passed"]
    extracted["public"] = scored["public"]
    extracted["private"] = scored["private"]
    extracted["path"] = "coordinated"
    extracted["helper_model_calls"] = helper_calls
    extracted["unique_generation"] = True
    cost = dict(extracted.get("cost") or {})
    cost["model_calls"] = helper_calls + 1
    cost["total_s"] = round(time.perf_counter() - started, 6)
    extracted["cost"] = cost
    return stamp_coverage(task, extracted)


def run_context_task(runtime, task: dict[str, Any], clock: dict[str, Any]) -> dict[str, Any]:
    arms = {}
    for context in CONTEXTS:
        working = with_output_docs(with_context(task, context))
        result = generate_extract(runtime, working, clock)
        result["unique_generation"] = True
        result["context"] = context
        arms[context] = stamp_coverage(working, result)
    return dict(
        task_id=task["task_id"],
        split=task["split"],
        family=task["family"],
        compact=derive_compact_interface(task["docs"], task["files"], task["request"]),
        leaked_composition="sum(" in derive_compact_interface(task["docs"], task["files"], task["request"])
        and "clip_span" in task["request"],
        arms=arms,
        confirmation=False,
    )


def lock_context(dev_rows: list[dict[str, Any]]) -> str:
    scores = {name: 0 for name in CONTEXTS}
    for row in dev_rows:
        for name in CONTEXTS:
            scores[name] += int(row["arms"][name]["complete_private"])
    if scores["compact_interface"] > scores["existing_docs"]:
        return "compact_interface"
    if scores["existing_docs"] > scores["compact_interface"]:
        return "existing_docs"
    return "existing_docs"


def interpret_limits_artifact(path: str | Path | None = None) -> dict[str, Any]:
    rows = []
    for task in limits_catalogue():
        if task["family"] not in {"unfamiliar_api", "multi_file"}:
            continue
        artifact = None
        if path and Path(path).is_file():
            artifact = json.loads(Path(path).read_text(encoding="utf-8"))
        saved = None
        if artifact:
            for split in ("development", "assessment"):
                for row in artifact.get(split) or []:
                    if row.get("task_id") == task["task_id"]:
                        saved = row
        if saved is None:
            continue
        for name, cell in (saved.get("pipelines") or {}).items():
            if not cell.get("unique_generation") and name != "direct":
                continue
            coverage = score_requirement_coverage(task["request"], cell.get("files") or {})
            rows.append(dict(
                task_id=task["task_id"],
                pipeline=name,
                behavior_private=bool(cell.get("private_passed")),
                coverage_passed=coverage["passed"],
                missing_functions=coverage["missing_functions"],
                missing_apis=coverage["missing_apis"],
                historical_private_unchanged=True,
            ))
    return dict(
        kind="limits_coverage_reinterpretation",
        historical_outcomes_unchanged=True,
        rows=rows,
    )


def summarize_contexts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for name in CONTEXTS:
        cells = [row["arms"][name] for row in rows]
        out[name] = dict(
            n=len(cells),
            behavior_private=sum(int(cell["behavior_private"]) for cell in cells),
            coverage_passed=sum(int(cell["coverage_passed"]) for cell in cells),
            complete_private=sum(int(cell["complete_private"]) for cell in cells),
            unique_model_calls=sum(int((cell.get("cost") or {}).get("model_calls") or 0) for cell in cells),
        )
    return out


def run_api_context(directory: str | Path, runtime) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    clock = dict(started=time.perf_counter(), calls=0, inference_ran=0)
    diagnosis = diagnose_opened_api()
    reinterpret = interpret_limits_artifact(
        Path("artifacts/seed_extraction_limits/seed_extraction_limits.json")
    )
    development = [run_context_task(runtime, task, clock) for task in tasks_for("development")
                   if task["family"] == "api_context"]
    locked = lock_context(development)
    inform = []
    inform_opened = False
    if any(row["arms"][locked]["complete_private"] for row in development):
        inform_opened = True
        fresh = [task for task in tasks_for("inform_next") if task["family"] == "api_context"][0]
        working = with_output_docs(with_context(fresh, locked))
        result = stamp_coverage(working, generate_extract(runtime, working, clock))
        inform.append(dict(task_id=fresh["task_id"], context=locked, result=result))
    coord_task = [task for task in tasks_for("development") if task["family"] == "coordinated_edit"][0]
    coord_extract = generate_extract(runtime, with_output_docs(item_only(coord_task)), clock)
    from .extraction_path import score_task as _score_task
    scored = _score_task(coord_task, coord_extract.get("files") or coord_task["files"])
    coord_extract["public_passed"] = scored["public_passed"]
    coord_extract["private_passed"] = scored["private_passed"]
    coord_extract["public"] = scored["public"]
    coord_extract["private"] = scored["private"]
    coord_extract = stamp_coverage(coord_task, coord_extract)
    coord_two = generate_coordinated(runtime, with_output_docs(coord_task), clock)
    usage = dict(
        kind="extraction_api_context_cpu_usage",
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
        learned_acquisition=False,
    )
    payload = dict(
        kind="seed_extraction_api_context",
        confirmation=False,
        informs_next_not_confirmation=True,
        learning_to_learn_established=False,
        historical_outcomes_unchanged=True,
        diagnosis=diagnosis,
        limits_reinterpretation=reinterpret,
        development=development,
        development_summary=summarize_contexts(development),
        locked_context=locked,
        inform_opened=inform_opened,
        inform_next=inform,
        coordinated=dict(
            task_id=coord_task["task_id"],
            extract=coord_extract,
            two_step=coord_two,
            two_step_calls=int((coord_two.get("cost") or {}).get("model_calls") or 0),
            extract_calls=1,
            unequal_compute_disclosed=True,
        ),
        opened_unused=list(OPENED),
        usage=usage,
    )
    payload["hash"] = digest({k: payload[k] for k in (
        "kind", "locked_context", "development_summary", "usage", "inform_opened",
    )})
    (directory / "recovery_live_usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    return payload
