"""Structured local-model patch proposals for SymbioticAgentLoop.

The model sees only public requirements, repository context, documentation and
public execution feedback. Structural validity is not semantic correctness.
Model outputs are never manufactured; a missing runtime is reported BLOCKED.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any


PATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "edits": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 180},
                    "action": {"type": "string", "enum": [
                        "replace", "create", "insert_function", "insert_after_symbol",
                    ]},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                    "symbol": {"type": "string"},
                    "scope": {"type": "string"},
                    "source_sha256": {"type": "string"},
                },
                "required": ["path", "action", "new_text"],
            },
        },
        "assumptions": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string"},
        },
        "rationale": {"type": "string"},
    },
    "required": ["edits"],
}

MAX_FILE_CHARS = 12_000
MAX_NEW_TEXT = 8_000
ALLOWED_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".json", ".md")


def source_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _node_end_lineno(source: str, node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    start = max(1, getattr(node, "lineno", 1))
    if type(end) is int and end >= start:
        return end
    # Python may omit end positions. Recover the block by indentation, never
    # insert into the interior of the current definition.
    lines = source.splitlines()
    if not lines:
        return 1
    start_idx = min(len(lines), start) - 1
    header = lines[start_idx]
    indent = len(header) - len(header.lstrip())
    last = start_idx
    for idx in range(start_idx + 1, len(lines)):
        raw = lines[idx]
        if not raw.strip():
            last = idx
            continue
        current = len(raw) - len(raw.lstrip())
        if current <= indent:
            break
        last = idx
    return last + 1


def locate_symbol(source: str, symbol: str, scope: str | None = None) -> ast.AST | None:
    tree = ast.parse(source)
    name = symbol.split(".")[-1]
    class_name = None
    if scope and scope.startswith("class:"):
        class_name = scope.split(":", 1)[1]
    elif "." in symbol:
        class_name = symbol.split(".")[-2]
    for node in tree.body:
        if class_name and isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child.name == name:
                    return child
            if node.name == name:
                return node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            if not class_name:
                return node
    return None


def insert_after_node(source: str, node: ast.AST, new_text: str) -> str:
    end_line = _node_end_lineno(source, node)
    lines = source.splitlines(True)
    if not lines:
        return new_text if new_text.endswith("\n") else new_text + "\n"
    prefix = "".join(lines[:end_line])
    suffix = "".join(lines[end_line:])
    block = new_text if new_text.endswith("\n") else new_text + "\n"
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    return prefix + "\n" + block + suffix


def function_names(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def contained_path(name: str) -> str:
    raw = str(name).replace("\\", "/").strip()
    if not raw or raw.startswith("/") or raw.startswith("..") or "/../" in f"/{raw}/":
        raise ValueError("unsafe_patch_path")
    if any(part in (".", "..") for part in Path(raw).parts):
        raise ValueError("unsafe_patch_path")
    if not raw.endswith(ALLOWED_SUFFIXES):
        raise ValueError("unsupported_patch_suffix")
    return raw


def parse_model_patch(content: str) -> dict[str, Any]:
    if type(content) is not str or not content.strip():
        raise ValueError("empty_model_patch")
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model_patch_not_json")
    payload = json.loads(text[start:end + 1])
    if type(payload) is not dict or type(payload.get("edits")) is not list or not payload["edits"]:
        raise ValueError("model_patch_schema")
    return payload


def validate_patch(payload: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    edits = []
    for raw in payload["edits"]:
        if type(raw) is not dict:
            raise ValueError("edit_not_object")
        path = contained_path(raw.get("path", ""))
        action = raw.get("action")
        if action not in ("replace", "create", "insert_function", "insert_after_symbol"):
            raise ValueError("invalid_edit_action")
        new_text = raw.get("new_text")
        if type(new_text) is not str or len(new_text) > MAX_NEW_TEXT:
            raise ValueError("invalid_new_text")
        old_text = raw.get("old_text") or ""
        if type(old_text) is not str:
            raise ValueError("invalid_old_text")
        symbol = str(raw.get("symbol") or "")
        scope = str(raw.get("scope") or "module")
        claimed_hash = raw.get("source_sha256")
        current = files.get(path, "")
        if claimed_hash and path in files and claimed_hash != source_sha256(current):
            raise ValueError(f"stale_source:{path}")
        if action == "replace":
            if path not in files:
                raise ValueError(f"missing_target_file:{path}")
            if old_text:
                if files[path].count(old_text) != 1:
                    raise ValueError(f"old_text_not_unique:{path}")
            elif new_text == files[path]:
                raise ValueError("no_op_replace")
            source = new_text if not old_text else files[path].replace(old_text, new_text, 1)
        elif action == "create":
            if path in files and files[path] and not old_text:
                raise ValueError(f"create_overwrites:{path}")
            source = new_text
        else:
            if path not in files:
                raise ValueError(f"missing_target_file:{path}")
            inserted_name = None
            match = re.search(r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", new_text)
            if match:
                inserted_name = match.group(1)
            if inserted_name and inserted_name in function_names(current):
                raise ValueError(f"duplicate_definition:{inserted_name}")
            if action == "insert_after_symbol":
                if not symbol:
                    raise ValueError("missing_symbol")
                node = locate_symbol(current, symbol, scope)
                if node is None:
                    raise ValueError(f"symbol_not_found:{symbol}")
                source = insert_after_node(current, node, new_text)
            else:
                source = current.rstrip() + "\n\n" + (new_text if new_text.endswith("\n") else new_text + "\n")
        if path.endswith(".py"):
            ast.parse(source)
        edits.append({
            "path": path, "action": action, "old_text": old_text, "new_text": new_text,
            "symbol": symbol, "scope": scope, "source_sha256": claimed_hash,
        })
    assumptions = [str(item)[:240] for item in payload.get("assumptions") or [] if str(item).strip()]
    return {
        "edits": edits,
        "assumptions": assumptions[:8],
        "rationale": str(payload.get("rationale") or "")[:400],
        "structurally_valid": True,
        "semantic_correctness": "unverified",
    }


def apply_patch(files: dict[str, str], validated: dict[str, Any]) -> dict[str, str]:
    patched = dict(files)
    for edit in validated["edits"]:
        path = edit["path"]
        action = edit["action"]
        current = patched.get(path, "")
        if action == "create" and not edit["old_text"]:
            patched[path] = edit["new_text"]
        elif action == "insert_after_symbol":
            node = locate_symbol(current, edit.get("symbol") or "", edit.get("scope") or "module")
            if node is None:
                raise ValueError(f"patch_not_applicable:{path}")
            patched[path] = insert_after_node(current, node, edit["new_text"])
        elif action == "insert_function":
            patched[path] = current.rstrip() + "\n\n" + (
                edit["new_text"] if edit["new_text"].endswith("\n") else edit["new_text"] + "\n"
            )
        elif edit["old_text"]:
            if current.count(edit["old_text"]) != 1:
                raise ValueError(f"patch_not_applicable:{path}")
            patched[path] = current.replace(edit["old_text"], edit["new_text"], 1)
        else:
            patched[path] = edit["new_text"]
        if len(patched[path]) > MAX_FILE_CHARS:
            raise ValueError(f"patched_file_too_large:{path}")
    return patched


def public_prompt(task, repo_index: dict[str, Any], grounded: dict[str, Any],
                  public_feedback: dict[str, Any] | None = None) -> str:
    files = getattr(task, "files", {})
    listed = []
    for path, source in sorted(files.items())[:8]:
        listed.append(f"### {path}\n```\n{source[:1800]}\n```")
    docs = []
    for doc in list(getattr(task, "docs", []) or [])[:4]:
        docs.append(f"{doc.get('title', '')}: {str(doc.get('content', ''))[:400]}")
    tests = json.dumps(list(getattr(task, "public_tests", []) or [])[:6], allow_nan=False)[:1200]
    feedback = json.dumps(public_feedback or {}, allow_nan=False)[:1200]
    return (
        "Propose a JSON patch for this local repository. Use only public tests and docs.\n"
        "Return edits with explicit paths. Do not claim private tests passed.\n"
        f"Request: {getattr(task, 'request', '')}\n"
        f"Language: {getattr(task, 'language', 'python')}\n"
        f"Symbols: {json.dumps(list(repo_index.get('symbols', []) or [])[:20], default=str)}\n"
        f"Docs: {' | '.join(docs) or 'none'}\n"
        f"Grounded bindings: {json.dumps(grounded, default=str)[:400]}\n"
        f"Public tests: {tests}\n"
        f"Public execution feedback: {feedback}\n"
        "Files:\n" + "\n".join(listed)
    )


def propose_with_runtime(runtime, task, repo_index: dict[str, Any], grounded: dict[str, Any],
                         public_feedback: dict[str, Any] | None = None,
                         max_tokens: int = 256,
                         files_override: dict[str, str] | None = None) -> dict[str, Any]:
    if runtime is None:
        return {
            "status": "BLOCKED",
            "reason": "local_model_unavailable",
            "proposal": None,
            "telemetry": None,
        }
    from .staging_workspace import CompletionInspector, inspect_completion_stop
    files = files_override if files_override is not None else task.files
    inspector = CompletionInspector(runtime)
    prompt = public_prompt(task, repo_index, grounded, public_feedback)
    if files_override is not None:
        prompt = public_prompt(
            type("T", (), {"files": files, "request": getattr(task, "request", ""),
                           "public_tests": getattr(task, "public_tests", []),
                           "docs": getattr(task, "docs", [])})(),
            repo_index, grounded, public_feedback,
        )
    try:
        raw = runtime.complete(prompt, PATCH_SCHEMA, max_tokens=max_tokens)
    except TypeError:
        raw = runtime.complete(prompt, PATCH_SCHEMA)
    except Exception as exc:
        return {
            "status": "BLOCKED",
            "reason": type(exc).__name__ + ": " + str(exc)[:200],
            "proposal": None,
            "telemetry": None,
            "completion_stop": inspector.last or None,
        }
    stop = inspect_completion_stop({**(raw if isinstance(raw, dict) else {}), **inspector.last})
    telemetry = dict(raw.get("telemetry") or {})
    telemetry["completion_stop"] = stop
    try:
        parsed = parse_model_patch(raw["content"])
        validated = validate_patch(parsed, files)
        patched = apply_patch(files, validated)
    except Exception as exc:
        return {
            "status": "invalid_proposal",
            "reason": type(exc).__name__ + ": " + str(exc)[:200],
            "proposal": None,
            "raw_content": raw.get("content", "")[:800],
            "telemetry": telemetry,
            "completion_stop": stop,
            "truncation_claimed_as_cause": False,
        }
    return {
        "status": "proposed",
        "reason": None,
        "proposal": validated,
        "patched_files": patched,
        "raw_content": raw.get("content", "")[:800],
        "telemetry": telemetry,
        "completion_stop": stop,
        "inference_ran": bool(telemetry.get("inference_ran")),
        "truncation_claimed_as_cause": False,
    }
