"""NEXUS-planned function replace/insert. The model supplies only the function body."""
from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from .local_model_patch_proposer import (
    apply_patch, locate_symbol, node_source, parse_model_patch, source_sha256,
    validate_patch,
)
from .symbiotic_agent_loop import PythonASTMutationSynthesizer


CONSTRAINED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "function": {"type": "string", "minLength": 1, "maxLength": 4000},
        "assumptions": {
            "type": "array",
            "maxItems": 6,
            "items": {"type": "string"},
        },
    },
    "required": ["function"],
}

_REQUESTED_FN = re.compile(
    r"\b(?:add|create|implement|insert|write)\s+(?:a\s+)?(?:function\s+)?"
    r"([a-z_][a-z0-9_]*)\s*\(([^)]*)\)",
    re.I,
)
_NAMED_FN = re.compile(r"\b([a-z_][a-z0-9_]*)\s*\(([a-z_][a-z0-9_,\s]*)\)", re.I)


@dataclass(frozen=True)
class ConstrainedPlan:
    action: str
    path: str
    symbol: str
    args: str
    source_sha256: str
    existing_source: str


def existing_definitions(files: dict[str, str]) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for path, source in sorted(files.items()):
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = ", ".join(arg.arg for arg in node.args.args) or "item"
                found.append((path, node.name, args))
    return found


def requested_functions(request: str) -> list[tuple[str, str]]:
    text = request or ""
    found: list[tuple[str, str]] = []
    for match in _REQUESTED_FN.finditer(text):
        found.append((match.group(1), match.group(2).strip() or "item"))
    if not found:
        for match in _NAMED_FN.finditer(text):
            name = match.group(1)
            if name in {"if", "for", "while", "return", "max", "min", "len", "print", "allow"}:
                continue
            found.append((name, match.group(2).strip() or "item"))
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name, args in found:
        if name in seen:
            continue
        seen.add(name)
        unique.append((name, args))
    return unique


def _entry_symbol(public_tests: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    for case in public_tests or []:
        entry = str(case.get("entry") or "")
        if "." not in entry:
            continue
        module, name = entry.split(".", 1)
        if module and name:
            return module + ".py", name
    return None, None


def plan_constrained_edit(
    request: str,
    files: dict[str, str],
    public_tests: list[dict[str, Any]] | None = None,
) -> ConstrainedPlan:
    """Choose path, symbol and replace-versus-insert. The model does not choose these."""
    existing = existing_definitions(files)
    by_name = {name: (path, args) for path, name, args in existing}
    entry_path, entry_name = _entry_symbol(public_tests or [])
    requested = requested_functions(request)
    if requested:
        name, args = requested[0]
        if name in by_name:
            path, existing_args = by_name[name]
            source = files[path]
            return ConstrainedPlan(
                "replace_function", path, name, existing_args or args,
                source_sha256(source), node_source(source, locate_symbol(source, name)),
            )
        path = entry_path if entry_path in files else next(
            (p for p in sorted(files) if p.endswith(".py")), None
        )
        if path is None:
            raise ValueError("no_python_target")
        return ConstrainedPlan("insert_function", path, name, args, source_sha256(files[path]), "")
    if entry_name and entry_name in by_name:
        path, args = by_name[entry_name]
        source = files[path]
        return ConstrainedPlan(
            "replace_function", path, entry_name, args,
            source_sha256(source), node_source(source, locate_symbol(source, entry_name)),
        )
    if len(existing) == 1:
        path, name, args = existing[0]
        source = files[path]
        return ConstrainedPlan(
            "replace_function", path, name, args,
            source_sha256(source), node_source(source, locate_symbol(source, name)),
        )
    raise ValueError("ambiguous_constrained_target")


def extract_function_text(content: str) -> tuple[str, bool, str]:
    """Return (text, raw_valid, reason). raw_valid is pre-normalization."""
    if type(content) is not str or not content.strip():
        return "", False, "empty_function"
    text = content.strip()
    payload = None
    if "{" in text:
        try:
            payload = parse_model_patch(text)
        except Exception:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                try:
                    payload = json.loads(text[start:end + 1])
                except Exception:
                    payload = None
    if type(payload) is dict and payload.get("function"):
        text = str(payload["function"])
    elif type(payload) is dict and payload.get("edits"):
        first = payload["edits"][0]
        text = str((first or {}).get("new_text") or "")
    text = text.strip()
    if not text:
        return "", False, "empty_function"
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, bool(text.strip()), "body_not_module"
    defs = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if len(defs) == 1:
        return text, True, "single_function"
    if not defs and tree.body:
        return text, True, "body_only"
    return text, False, "not_single_function"


def normalize_function(text: str, symbol: str, args: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty_function")
    try:
        tree = ast.parse(raw)
        defs = [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if len(defs) == 1 and len(tree.body) == 1:
            if defs[0].name != symbol:
                defs[0].name = symbol
                notes.append("renamed_definition")
            out = ast.unparse(tree)
            return out if out.endswith("\n") else out + "\n", notes
        if defs:
            raise ValueError("not_single_function")
    except SyntaxError:
        notes.append("wrapped_body")
    except ValueError:
        raise
    else:
        notes.append("wrapped_body")
    body_lines = [line for line in raw.splitlines()]
    indented = "\n".join(("    " + line) if line.strip() else "" for line in body_lines)
    out = f"def {symbol}({args or 'item'}):\n{indented or '    pass'}\n"
    ast.parse(out)
    return out, notes


def wrap_constrained_edit(plan: ConstrainedPlan, function_text: str) -> dict[str, Any]:
    block = function_text if function_text.endswith("\n") else function_text + "\n"
    if plan.action == "replace_function":
        return {
            "path": plan.path,
            "action": "replace",
            "old_text": plan.existing_source,
            "new_text": block,
            "symbol": plan.symbol,
            "scope": "module",
            "source_sha256": plan.source_sha256,
        }
    return {
        "path": plan.path,
        "action": "insert_function",
        "old_text": "",
        "new_text": block,
        "symbol": plan.symbol,
        "scope": "module",
        "source_sha256": plan.source_sha256,
    }


def preview_constrained_edit(plan: ConstrainedPlan, function_text: str) -> dict[str, Any]:
    return {
        "action": plan.action,
        "path": plan.path,
        "symbol": plan.symbol,
        "source_sha256": plan.source_sha256,
        "old_excerpt": (plan.existing_source or "")[:400],
        "new_excerpt": (function_text or "")[:400],
        "supplied_by": "nexus_plan",
        "model_chooses": ["function_text"],
    }


def assemble_constrained_proposal(
    content: str,
    request: str,
    files: dict[str, str],
    public_tests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    plan = plan_constrained_edit(request, files, public_tests)
    raw_text, raw_valid, raw_reason = extract_function_text(content)
    notes: list[str] = []
    function_text = ""
    if raw_valid:
        function_text, notes = normalize_function(raw_text, plan.symbol, plan.args)
    edit = wrap_constrained_edit(plan, function_text) if function_text else None
    validated = None
    patched = None
    if edit is not None:
        validated = validate_patch({"edits": [edit], "assumptions": []}, files, interface="symbol")
        patched = apply_patch(files, validated)
    return {
        "plan": asdict(plan),
        "raw_valid": raw_valid,
        "raw_reason": raw_reason,
        "raw_excerpt": (raw_text or "")[:400],
        "normalized": notes,
        "preview": preview_constrained_edit(plan, function_text),
        "validated": validated,
        "patched_files": patched,
        "structurally_valid": bool(validated and validated.get("structurally_valid")),
    }


def catalogue_cannot_complete(spec: dict[str, Any], timeout_s: int = 10) -> dict[str, Any]:
    """Confirm the existing AST catalogue cannot pass the public tests."""
    from .agent_loop_worker import run_worker_subprocess
    files = spec["files"]
    candidates = PythonASTMutationSynthesizer.generate_candidates(
        files, set(), spec["request"], {},
    )
    passing: list[str] = []
    for desc, patched in candidates:
        result = run_worker_subprocess({
            "language": spec["language"],
            "files": patched,
            "cases": spec.get("public") or [],
        }, timeout_s)
        if result.get("all_passed"):
            passing.append(desc)
    return {
        "cannot_complete": not passing,
        "candidate_count": len(candidates),
        "passing_operators": passing,
        "operators": [desc for desc, _ in candidates],
    }


def constrained_prompt(task, plan: ConstrainedPlan, public_feedback: dict[str, Any] | None = None) -> str:
    files = getattr(task, "files", {})
    source = files.get(plan.path, "")
    tests = __import__("json").dumps(list(getattr(task, "public_tests", []) or [])[:6], allow_nan=False)[:1200]
    docs = []
    for doc in list(getattr(task, "docs", []) or [])[:4]:
        docs.append(f"{doc.get('title', '')}: {str(doc.get('content', ''))[:400]}")
    feedback = __import__("json").dumps(public_feedback or {}, allow_nan=False)[:800]
    verb = "Replace the existing function. Do not choose a different file, name or action."
    if plan.action == "insert_function":
        verb = "Write a new function to insert. Do not choose a different file, name or action."
    return (
        "Return JSON with a single key function. NEXUS already chose the target.\n"
        f"{verb}\n"
        f"File: {plan.path}\n"
        f"Symbol: {plan.symbol}\n"
        f"Arguments: {plan.args}\n"
        f"Action: {plan.action}\n"
        f"source_sha256: {plan.source_sha256}\n"
        f"Request: {getattr(task, 'request', '')}\n"
        f"Docs: {' | '.join(docs) or 'none'}\n"
        f"Public tests: {tests}\n"
        f"Public execution feedback: {feedback}\n"
        f"Current function:\n```\n{(plan.existing_source or source)[:1800]}\n```\n"
    )
