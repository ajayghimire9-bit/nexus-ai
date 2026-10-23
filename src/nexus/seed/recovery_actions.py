"""Equal-access recovery tools over existing workers, contracts and vault.

Actions have real implementations and measured cost. Teacher outputs require
the explicit reference interface. Hidden family labels never enter features.
"""
from __future__ import annotations

import ast
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from .agent_loop_worker import evaluate_python_payload
from .capability_evidence import digest
from .constrained_edit import plan_constrained_edit
from .input_contract import describe_input_contract, fields_from_source, input_structure
from .lexicon_vault import KnowledgeVault
from .public_failure import public_revision_feedback
from .unified_chat import retrieve_for_question

ACTIONS = (
    "INSPECT_SCHEMA",
    "RETRIEVE_DOCS",
    "REQUEST_DISTINGUISHING_EXAMPLE",
    "REVISE",
    "STOP_UNRESOLVED",
)
FEATURE_NAMES = (
    "exc_type_error", "exc_key_error", "exc_attr_error", "exc_assert",
    "exc_value", "exc_other", "mismatch_rate", "n_public_failed",
    "input_is_dict", "docs_available", "teacher_available", "inspected",
    "retrieved", "distinguished", "revised_count", "remaining_frac",
    "last_inspect", "last_retrieve", "last_distinguish", "last_revise",
    "last_stop", "disagreement",
)
MAX_ACTIONS = 4
MAX_REVISES = 2


def run_cases(files: dict[str, str], cases: list[dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    out = evaluate_python_payload(dict(language="python", files=files, cases=cases, trace=False))
    out["wall_s"] = time.perf_counter() - started
    out["tool_executions"] = 1
    return out


def exception_category(public: dict[str, Any]) -> str:
    for row in public.get("results") or []:
        err = str(row.get("error") or "")
        name = err.split(":", 1)[0]
        if name in ("TypeError", "KeyError", "AttributeError", "AssertionError", "ValueError"):
            return name
    return "other" if any(not row.get("passed") for row in public.get("results") or []) else "none"


def public_observation(task: dict[str, Any], files: dict[str, str], public: dict[str, Any],
                       evidence: dict[str, Any], remaining: int) -> dict[str, Any]:
    category = exception_category(public)
    failed = sum(1 for row in public.get("results") or [] if not row.get("passed"))
    total = max(1, len(public.get("results") or []))
    last = evidence.get("last_action")
    feats = dict(
        exc_type_error=float(category == "TypeError"),
        exc_key_error=float(category == "KeyError"),
        exc_attr_error=float(category == "AttributeError"),
        exc_assert=float(category == "AssertionError"),
        exc_value=float(category == "ValueError"),
        exc_other=float(category == "other"),
        mismatch_rate=failed / total,
        n_public_failed=float(failed),
        input_is_dict=float(any(type((case.get("input"))) is dict for case in task["public"])),
        docs_available=float(bool(task.get("docs"))),
        teacher_available=float(bool(task.get("teacher_available"))),
        inspected=float(bool(evidence.get("inspected"))),
        retrieved=float(bool(evidence.get("retrieved"))),
        distinguished=float(bool(evidence.get("distinguished"))),
        revised_count=float(evidence.get("revised_count") or 0),
        remaining_frac=remaining / MAX_ACTIONS,
        last_inspect=float(last == "INSPECT_SCHEMA"),
        last_retrieve=float(last == "RETRIEVE_DOCS"),
        last_distinguish=float(last == "REQUEST_DISTINGUISHING_EXAMPLE"),
        last_revise=float(last == "REVISE"),
        last_stop=float(last == "STOP_UNRESOLVED"),
        disagreement=float(bool(evidence.get("disagreement"))),
    )
    if set(feats) != set(FEATURE_NAMES):
        raise ValueError("feature_name_mismatch")
    return feats


def feature_vector(feats: dict[str, float]) -> list[float]:
    return [float(feats[name]) for name in FEATURE_NAMES]


def available_actions(task: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    out = []
    if not evidence.get("inspected"):
        out.append("INSPECT_SCHEMA")
    if task.get("docs") and not evidence.get("retrieved"):
        out.append("RETRIEVE_DOCS")
    if task.get("teacher_available") and not evidence.get("distinguished"):
        out.append("REQUEST_DISTINGUISHING_EXAMPLE")
    if int(evidence.get("revised_count") or 0) < MAX_REVISES:
        out.append("REVISE")
    out.append("STOP_UNRESOLVED")
    return out


def inspect_schema(task: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    started = time.perf_counter()
    plan = plan_constrained_edit(task["request"], files, task["public"])
    contract = describe_input_contract(plan, task["public"])
    fields = input_structure(task["public"])
    source_fields = []
    for text in files.values():
        source_fields.extend(fields_from_source(text))
    return dict(
        action="INSPECT_SCHEMA",
        available=True,
        contract=contract,
        fields=fields,
        source_fields=sorted(set(source_fields)),
        wall_s=time.perf_counter() - started,
        tool_executions=1,
        model_calls=0,
        teacher_queries=0,
    )


def retrieve_docs(task: dict[str, Any], directory: str | Path) -> dict[str, Any]:
    started = time.perf_counter()
    if not task.get("docs"):
        return dict(action="RETRIEVE_DOCS", available=False, reason="no_docs",
                    texts=[], wall_s=time.perf_counter() - started,
                    tool_executions=0, model_calls=0, teacher_queries=0)
    path = Path(directory) / "recovery_vault.sqlite"
    vault = KnowledgeVault(path)
    try:
        for doc in task["docs"]:
            vault.ingest_document(doc["doc_id"], doc["title"], doc["content"])
        rows = retrieve_for_question(vault, task["request"], top_k=3)
        texts = [row.content for row in rows]
    finally:
        vault.close()
    return dict(
        action="RETRIEVE_DOCS",
        available=True,
        texts=texts,
        cited=[row.doc_id for row in rows],
        wall_s=time.perf_counter() - started,
        tool_executions=1,
        model_calls=0,
        teacher_queries=0,
    )


def _probe_inputs(task: dict[str, Any]) -> list[Any]:
    probes = []
    for case in task["public"]:
        inp = case.get("input")
        if type(inp) is dict:
            probes.append(dict(inp))
            for key in list(inp):
                dropped = dict(inp)
                dropped.pop(key, None)
                probes.append(dropped)
            if "score" in inp and "limit" in inp:
                equal = dict(inp)
                equal["score"] = equal["limit"]
                probes.append(equal)
    return probes[:8]


def request_distinguishing(task: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    started = time.perf_counter()
    if not task.get("teacher_available") or task.get("reference") is None:
        return dict(action="REQUEST_DISTINGUISHING_EXAMPLE", available=False,
                    reason="teacher_unavailable", wall_s=time.perf_counter() - started,
                    tool_executions=0, model_calls=0, teacher_queries=0)
    known = {json.dumps(case.get("input"), sort_keys=True, allow_nan=False) for case in task["public"]}
    chosen = None
    disagreement = False
    for probe in _probe_inputs(task):
        if json.dumps(probe, sort_keys=True, allow_nan=False) in known:
            continue
        case = dict(task["public"][0])
        case["input"] = probe
        current = run_cases(files, [case])
        try:
            expected = task["reference"](probe)
        except Exception:
            continue
        actual = (current.get("results") or [{}])[0].get("actual")
        if actual != expected:
            chosen = dict(input=probe, expected=expected)
            disagreement = True
            break
    if chosen is None:
        for probe in _probe_inputs(task):
            if json.dumps(probe, sort_keys=True, allow_nan=False) in known:
                continue
            try:
                chosen = dict(input=probe, expected=task["reference"](probe))
                break
            except Exception:
                continue
        if chosen is None:
            return dict(action="REQUEST_DISTINGUISHING_EXAMPLE", available=False,
                        reason="no_valid_probe", wall_s=time.perf_counter() - started,
                        tool_executions=1, model_calls=0, teacher_queries=0)
    return dict(
        action="REQUEST_DISTINGUISHING_EXAMPLE",
        available=True,
        example=chosen,
        disagreement=disagreement,
        wall_s=time.perf_counter() - started,
        tool_executions=1,
        model_calls=0,
        teacher_queries=1,
    )


def _lookup_source(fn: str, examples: list[dict[str, Any]]) -> str:
    table = {json.dumps(row["input"], sort_keys=True, allow_nan=False): row["expected"] for row in examples}
    return (
        f"def {fn}(item):\n"
        f"    table = {json.dumps(table, allow_nan=False)}\n"
        "    key = __import__('json').dumps(item, sort_keys=True, allow_nan=False)\n"
        "    return table.get(key)\n"
    )


def _increment_source(fn: str) -> str:
    return f"def {fn}(item):\n    return int(item['n']) + 1\n"


def _ready_source(fn: str) -> str:
    return f"def {fn}(item):\n    return item['score'] >= item['limit']\n"


def _join_source(fn: str, left: str, right: str, helper: bool) -> str:
    if helper:
        return (
            f"def {fn}(item):\n"
            f"    return join_parts(str(item.get({left!r}) or '').lower(), "
            f"str(item.get({right!r}) or '').lower())\n"
        )
    return (
        f"def {fn}(item):\n"
        f"    return str(item.get({left!r}) or '').lower() + '/' + "
        f"str(item.get({right!r}) or '').lower()\n"
    )


def _field_source(fn: str, field: str) -> str:
    return f"def {fn}(item):\n    return str(item.get({field!r}) or '').lower()\n"


def _entry(task: dict[str, Any]) -> tuple[str, str]:
    entry = task["public"][0]["entry"]
    mod, fn = entry.split(".", 1)
    return mod + ".py", fn


def apply_public_repair(task: dict[str, Any], evidence: dict[str, Any]) -> dict[str, str]:
    """Deterministic public-evidence repair. Same operator for every method."""
    filename, fn = _entry(task)
    files = dict(task["files"])
    examples = [{"input": c["input"], "expected": c["expected"]} for c in task["public"]]
    examples.extend(evidence.get("teacher_examples") or [])
    retrieved = " ".join(evidence.get("retrieved_texts") or []).lower()
    fields = dict(evidence.get("fields") or {})
    helper = "join_parts" in retrieved
    if any(type(row["input"]) is dict and row["input"].get("score") == row["input"].get("limit")
           and row["expected"] is True for row in examples):
        files[filename] = _keep_helpers(files.get(filename, ""), _ready_source(fn))
        return files
    if examples and all(type(row["input"]) is dict and "n" in row["input"]
                        and row["expected"] == int(row["input"]["n"]) + 1 for row in examples):
        files[filename] = _keep_helpers(files.get(filename, ""), _increment_source(fn))
        return files
    keys = [key for key in fields] or _public_keys(task)
    if helper and len(keys) >= 2:
        files[filename] = _keep_helpers(files.get(filename, ""), _join_source(fn, keys[0], keys[1], True))
        return files
    if evidence.get("inspected") and len(keys) == 1 and all(
        type(row["expected"]) is str for row in examples
    ):
        files[filename] = _keep_helpers(files.get(filename, ""), _field_source(fn, keys[0]))
        return files
    if evidence.get("inspected") and len(keys) >= 2 and all(type(row["expected"]) is str for row in examples):
        files[filename] = _keep_helpers(files.get(filename, ""), _join_source(fn, keys[0], keys[1], False))
        return files
    files[filename] = _keep_helpers(files.get(filename, ""), _lookup_source(fn, examples))
    return files


def _public_keys(task: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for case in task["public"]:
        inp = case.get("input")
        if type(inp) is dict:
            for key in inp:
                if key not in keys:
                    keys.append(key)
    return keys


def _keep_helpers(source: str, replacement: str) -> str:
    kept = []
    try:
        tree = ast.parse(source or "")
    except SyntaxError:
        return replacement
    replace_name = ast.parse(replacement).body[0].name
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name != replace_name:
            kept.append(ast.get_source_segment(source, node) or "")
    return "\n\n".join([text for text in kept if text] + [replacement])


def revise(task: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    files = apply_public_repair(task, evidence)
    public = run_cases(files, task["public"])
    feedback = public_revision_feedback(public, task["public"])
    return dict(
        action="REVISE",
        available=True,
        files=files,
        public=public,
        feedback=feedback["instruction"],
        wall_s=time.perf_counter() - started,
        tool_executions=1 + int(public.get("tool_executions") or 0),
        model_calls=0,
        teacher_queries=0,
    )


def execute_action(action: str, task: dict[str, Any], files: dict[str, str],
                   evidence: dict[str, Any], directory: str | Path) -> dict[str, Any]:
    if action == "INSPECT_SCHEMA":
        return inspect_schema(task, files)
    if action == "RETRIEVE_DOCS":
        return retrieve_docs(task, directory)
    if action == "REQUEST_DISTINGUISHING_EXAMPLE":
        return request_distinguishing(task, files)
    if action == "REVISE":
        return revise(task, evidence)
    if action == "STOP_UNRESOLVED":
        return dict(action=action, available=True, wall_s=0.0,
                    tool_executions=0, model_calls=0, teacher_queries=0)
    raise ValueError("unknown_recovery_action")


def apply_evidence(evidence: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    row = dict(evidence)
    row["last_action"] = result["action"]
    if result["action"] == "INSPECT_SCHEMA" and result.get("available"):
        row["inspected"] = True
        row["fields"] = result.get("fields") or {}
        row["contract"] = result.get("contract")
    if result["action"] == "RETRIEVE_DOCS" and result.get("available"):
        row["retrieved"] = True
        row["retrieved_texts"] = result.get("texts") or []
    if result["action"] == "REQUEST_DISTINGUISHING_EXAMPLE" and result.get("available"):
        row["distinguished"] = True
        row["disagreement"] = bool(result.get("disagreement"))
        example = result.get("example")
        if example:
            row.setdefault("teacher_examples", []).append(example)
    if result["action"] == "REVISE":
        row["revised_count"] = int(row.get("revised_count") or 0) + 1
        row["files"] = result.get("files")
        row["public"] = result.get("public")
    return row


def blank_evidence(files: dict[str, str], public: dict[str, Any]) -> dict[str, Any]:
    return dict(
        inspected=False, retrieved=False, distinguished=False, disagreement=False,
        revised_count=0, files=files, public=public, teacher_examples=[],
        fields={}, retrieved_texts=[], last_action=None,
    )


def episode_digest(payload: dict[str, Any]) -> str:
    return digest(payload)
