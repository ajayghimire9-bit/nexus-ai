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


def parse_scope(scope: str | None, symbol: str = "", source: str | None = None) -> tuple[str, str | None]:
    raw = (scope or "module").strip()
    if raw.startswith("class:"):
        return "class", raw.split(":", 1)[1].strip()
    if symbol and "." in symbol:
        return "class", symbol.split(".")[-2]
    if source and raw not in {"", "module"}:
        try:
            if locate_class(source, raw) is not None:
                return "class", raw
        except SyntaxError:
            pass
    return "module", None


def locate_class(source: str, class_name: str) -> ast.ClassDef | None:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def names_in_scope(source: str, scope: str | None, symbol: str = "") -> set[str]:
    kind, class_name = parse_scope(scope, symbol, source)
    tree = ast.parse(source)
    if kind == "module":
        return {
            n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
    cls = locate_class(source, class_name or "")
    if cls is None:
        raise ValueError(f"scope_not_found:{class_name}")
    return {
        n.name for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _dedent(text: str) -> str:
    lines = text.strip("\n").split("\n")
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    base = min(indents) if indents else 0
    return "\n".join(line[base:] if line.strip() else "" for line in lines)


def indent_block(text: str, indent: str) -> str:
    body = _dedent(text)
    return "\n".join((indent + line) if line.strip() else "" for line in body.split("\n")) + "\n"


def node_indent(source: str, node: ast.AST) -> str:
    lines = source.splitlines()
    idx = max(0, getattr(node, "lineno", 1) - 1)
    if idx >= len(lines):
        return ""
    line = lines[idx]
    return line[: len(line) - len(line.lstrip())]


def top_level_definition_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def single_definition_source(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    defs = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    return len(defs) == 1 and len(tree.body) == 1


def node_source(source: str, node: ast.AST) -> str:
    lines = source.splitlines(True)
    start = max(0, getattr(node, "lineno", 1) - 1)
    end = _node_end_lineno(source, node)
    return "".join(lines[start:end])


def looks_complete_source(text: str, path: str, original: str | None = None) -> bool:
    """True only for a whole module that keeps the original top-level names."""
    if not text or not text.strip():
        return False
    if path.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return False
        defs = [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        if not defs:
            return False
        if original:
            try:
                original_names = top_level_definition_names(original)
            except SyntaxError:
                original_names = set()
            new_names = {node.name for node in defs}
            if original_names and not original_names.issubset(new_names):
                return False
        return True
    return len(text) >= 8


def prefer_symbol_targeted_edit(raw: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    """Rewrite a replace into insert_function or a unique symbol replace when possible."""
    path = contained_path(raw.get("path", ""))
    action = raw.get("action")
    new_text = raw.get("new_text") or ""
    current = files.get(path, "")
    if action != "replace" or path not in files or type(new_text) is not str:
        return raw
    name = inserted_definition_name(new_text)
    if not name or not single_definition_source(new_text):
        return raw
    scope = str(raw.get("scope") or "module")
    try:
        present = names_in_scope(current, scope, str(raw.get("symbol") or ""))
    except (ValueError, SyntaxError):
        return raw
    rewritten = dict(raw)
    rewritten["symbol"] = name
    rewritten["scope"] = scope
    if name not in present:
        rewritten["action"] = "insert_function"
        rewritten["old_text"] = ""
        return rewritten
    node = locate_symbol(current, name, scope)
    if node is None:
        return raw
    rewritten["old_text"] = node_source(current, node)
    return rewritten


def inserted_definition_name(new_text: str) -> str | None:
    match = re.search(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", new_text, flags=re.M)
    return match.group(1) if match else None


def insert_into_class(source: str, class_name: str, new_text: str) -> str:
    cls = locate_class(source, class_name)
    if cls is None:
        raise ValueError(f"scope_not_found:{class_name}")
    target = cls.body[-1] if cls.body else cls
    indent = node_indent(source, target) if cls.body else node_indent(source, cls) + "    "
    return insert_after_node(source, target, indent_block(new_text, indent))


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


def validate_patch(payload: dict[str, Any], files: dict[str, str],
                   interface: str = "symbol") -> dict[str, Any]:
    edits = []
    for raw in payload["edits"]:
        if type(raw) is not dict:
            raise ValueError("edit_not_object")
        if interface == "symbol":
            raw = prefer_symbol_targeted_edit(raw, files)
        elif interface != "raw":
            raise ValueError("invalid_proposal_interface")
        path = contained_path(raw.get("path", ""))
        action = raw.get("action")
        if action not in ("replace", "create", "insert_function", "insert_after_symbol"):
            raise ValueError("invalid_edit_action")
        if interface == "raw" and action in {"insert_function", "insert_after_symbol"}:
            raise ValueError("raw_interface_rejects_symbol_action")
        new_text = raw.get("new_text")
        if type(new_text) is not str or len(new_text) > MAX_NEW_TEXT:
            raise ValueError("invalid_new_text")
        old_text = raw.get("old_text") or ""
        if type(old_text) is not str:
            raise ValueError("invalid_old_text")
        symbol = str(raw.get("symbol") or "")
        scope = str(raw.get("scope") or "module")
        current = files.get(path, "")
        expected_hash = source_sha256(current) if path in files else None
        claimed_hash = raw.get("source_sha256")
        if expected_hash is not None:
            if claimed_hash and claimed_hash != expected_hash:
                raise ValueError(f"stale_source:{path}")
            claimed_hash = expected_hash
        if action == "replace":
            if path not in files:
                raise ValueError(f"missing_target_file:{path}")
            if old_text:
                if files[path].count(old_text) != 1:
                    if looks_complete_source(new_text, path, files[path]) and new_text != files[path]:
                        old_text = ""
                    else:
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
            inserted_name = inserted_definition_name(new_text)
            if inserted_name and inserted_name in names_in_scope(current, scope, symbol):
                raise ValueError(f"duplicate_definition:{inserted_name}")
            kind, class_name = parse_scope(scope, symbol, current)
            if action == "insert_after_symbol":
                if not symbol:
                    raise ValueError("missing_symbol")
                node = locate_symbol(current, symbol, f"class:{class_name}" if kind == "class" else scope)
                if node is None:
                    raise ValueError(f"symbol_not_found:{symbol}")
                if isinstance(node, ast.ClassDef):
                    source = insert_into_class(current, node.name, new_text)
                else:
                    block = new_text
                    if kind == "class":
                        block = indent_block(new_text, node_indent(current, node))
                    source = insert_after_node(current, node, block)
            elif kind == "class":
                source = insert_into_class(current, class_name or "", new_text)
            else:
                block = new_text if new_text.endswith("\n") else new_text + "\n"
                source = current.rstrip() + "\n\n" + block
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
        if path in files and edit.get("source_sha256"):
            if edit["source_sha256"] != source_sha256(files[path]):
                raise ValueError(f"stale_source:{path}")
        action = edit["action"]
        current = patched.get(path, "")
        if action == "create" and not edit["old_text"]:
            patched[path] = edit["new_text"]
        elif action == "insert_after_symbol":
            node = locate_symbol(current, edit.get("symbol") or "", edit.get("scope") or "module")
            if node is None:
                raise ValueError(f"patch_not_applicable:{path}")
            if isinstance(node, ast.ClassDef):
                patched[path] = insert_into_class(current, node.name, edit["new_text"])
            else:
                block = edit["new_text"]
                if parse_scope(edit.get("scope"), edit.get("symbol") or "", current)[0] == "class":
                    block = indent_block(edit["new_text"], node_indent(current, node))
                patched[path] = insert_after_node(current, node, block)
        elif action == "insert_function":
            kind, class_name = parse_scope(edit.get("scope"), edit.get("symbol") or "", current)
            if kind == "class":
                patched[path] = insert_into_class(current, class_name or "", edit["new_text"])
            else:
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
                  public_feedback: dict[str, Any] | None = None,
                  interface: str = "symbol") -> str:
    files = getattr(task, "files", {})
    listed = []
    for path, source in sorted(files.items())[:8]:
        listed.append(f"### {path}\n```\n{source[:1800]}\n```")
    docs = []
    for doc in list(getattr(task, "docs", []) or [])[:4]:
        docs.append(f"{doc.get('title', '')}: {str(doc.get('content', ''))[:400]}")
    tests = json.dumps(list(getattr(task, "public_tests", []) or [])[:6], allow_nan=False)[:1200]
    feedback = json.dumps(public_feedback or {}, allow_nan=False)[:1200]
    validation = ""
    if public_feedback and public_feedback.get("validation_error"):
        validation = (
            f"Last validation error on the current staged source: {public_feedback['validation_error']}\n"
            "Revise that staged source. Prefer insert_function or insert_after_symbol "
            "for a new definition. For replace, old_text must occur exactly once. "
            "Do not send an incomplete snippet as a whole module.\n"
        )
    interface_line = (
        "Prefer symbol-targeted insert_function, insert_after_symbol, or a unique symbol replace.\n"
        if interface != "raw" else
        "Use only replace or create. Do not use insert_function or insert_after_symbol.\n"
    )
    return (
        "Propose a JSON patch for this local repository. Use only public tests and docs.\n"
        f"{interface_line}"
        "Return edits with explicit paths. Do not claim private tests passed.\n"
        f"{validation}"
        f"Request: {getattr(task, 'request', '')}\n"
        f"File source_sha256: {json.dumps({p: source_sha256(s) for p, s in files.items()})}\n"
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
                         files_override: dict[str, str] | None = None,
                         interface: str = "symbol") -> dict[str, Any]:
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
    schema = PATCH_SCHEMA
    if interface == "constrained":
        from .constrained_edit import CONSTRAINED_SCHEMA, constrained_prompt, plan_constrained_edit
        plan = plan_constrained_edit(
            getattr(task, "request", ""), files, list(getattr(task, "public_tests", []) or []),
        )
        prompt = constrained_prompt(task, plan, public_feedback)
        schema = CONSTRAINED_SCHEMA
    else:
        prompt = public_prompt(task, repo_index, grounded, public_feedback, interface=interface)
        if files_override is not None:
            prompt = public_prompt(
                type("T", (), {"files": files, "request": getattr(task, "request", ""),
                               "public_tests": getattr(task, "public_tests", []),
                               "docs": getattr(task, "docs", [])})(),
                repo_index, grounded, public_feedback, interface=interface,
            )
    try:
        raw = runtime.complete(prompt, schema, max_tokens=max_tokens)
    except TypeError:
        raw = runtime.complete(prompt, schema)
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
        if interface == "constrained":
            from .constrained_edit import assemble_constrained_proposal
            assembled = assemble_constrained_proposal(
                raw.get("content", ""), getattr(task, "request", ""), files,
                list(getattr(task, "public_tests", []) or []),
            )
            if not assembled.get("structurally_valid"):
                raise ValueError(assembled.get("raw_reason") or "constrained_not_structurally_valid")
            validated = assembled["validated"]
            patched = assembled["patched_files"]
        else:
            parsed = parse_model_patch(raw["content"])
            validated = validate_patch(parsed, files, interface=interface)
            patched = apply_patch(files, validated)
            assembled = None
    except Exception as exc:
        return {
            "status": "invalid_proposal",
            "reason": type(exc).__name__ + ": " + str(exc)[:200],
            "proposal": None,
            "raw_content": raw.get("content", "")[:800],
            "telemetry": telemetry,
            "completion_stop": stop,
            "inference_ran": bool(telemetry.get("inference_ran")),
            "truncation_claimed_as_cause": False,
            "raw_valid": False,
            "normalized": [],
        }
    extra = {}
    if interface == "constrained" and assembled is not None:
        extra = {
            "raw_valid": assembled.get("raw_valid"),
            "raw_reason": assembled.get("raw_reason"),
            "normalized": assembled.get("normalized") or [],
            "preview": assembled.get("preview"),
            "plan": assembled.get("plan"),
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
        **extra,
    }


def propose_coordinated_per_file(runtime, task, repo_index: dict[str, Any], grounded: dict[str, Any],
                                 public_feedback: dict[str, Any] | None = None,
                                 max_tokens_per_file: int = 128) -> dict[str, Any]:
    """One complete() per file. Later prompts see earlier staged edits.

    This is actual per-file generation, not apply_per_file staging helpers.
    """
    from .staging_workspace import StagingWorkspace, files_sha256
    files = dict(getattr(task, "files", {}))
    staging = StagingWorkspace(files)
    staging.propose_coordinated(getattr(task, "request", ""), sorted(files))
    traces = []
    generated = 0
    input_tokens = 0
    wall = 0.0
    prior: list[str] = []
    for path in sorted(files):
        staged_now = dict(staging.staged)
        single = type("T", (), {
            "files": staged_now,
            "request": (
                f"{getattr(task, 'request', '')} Coordinated edit: change only {path}. "
                f"Earlier staged files are already applied and must be kept: {prior or 'none'}."
            ),
            "public_tests": getattr(task, "public_tests", []),
            "docs": getattr(task, "docs", []),
            "language": getattr(task, "language", "python"),
        })()
        proposed = propose_with_runtime(
            runtime, single, repo_index, grounded, public_feedback,
            max_tokens=max_tokens_per_file,
        )
        tel = proposed.get("telemetry") or {}
        generated += int(tel.get("generated_tokens") or 0)
        input_tokens += int(tel.get("input_tokens") or 0)
        wall += float(tel.get("request_wall_s") or 0)
        prompt = public_prompt(single, repo_index, grounded, public_feedback)
        traces.append({
            "path": path,
            "status": proposed.get("status"),
            "reason": proposed.get("reason"),
            "completion_stop": proposed.get("completion_stop"),
            "inference_ran": proposed.get("inference_ran"),
            "prior_staged": list(prior),
            "prompt_file_count": len(staged_now),
            "prompt_excerpt": prompt[:2400],
            "prior_staged_excerpts": {p: staged_now[p][:400] for p in prior if p in staged_now},
            "staged_sha_before": files_sha256(staged_now),
            "used_prior_staged_context": bool(prior),
        })
        if proposed.get("status") == "proposed" and path in proposed.get("patched_files", {}):
            merged = dict(staging.staged)
            merged[path] = proposed["patched_files"][path]
            staging.replace_staged(merged)
            prior.append(path)
    statuses = {row["status"] for row in traces}
    status = "proposed" if "proposed" in statuses else (
        "BLOCKED" if statuses == {"BLOCKED"} or not statuses else "invalid_proposal"
    )
    used_prior = any(row.get("used_prior_staged_context") for row in traces)
    return {
        "status": status,
        "mode": "coordinated_per_file_generation",
        "model_generated_per_file": True,
        "used_prior_staged_context": used_prior,
        "completions": len(traces),
        "patched_files": dict(staging.staged),
        "traces": traces,
        "telemetry": {
            "generated_tokens": generated,
            "input_tokens": input_tokens,
            "request_wall_s": wall,
            "completions": len(traces),
        },
        "truncation_claimed_as_cause": False,
    }
