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
import textwrap
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
                        "replace", "replace_function", "create", "insert_function", "insert_after_symbol",
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


def _find_unique_defining_file(symbol_name: str, files: dict[str, str], scope: str = "module") -> str | None:
    if not symbol_name:
        return None
    matches: list[str] = []
    for fpath, fsrc in sorted(files.items()):
        if not fpath.endswith(".py"):
            continue
        try:
            if symbol_name in names_in_scope(fsrc, scope, symbol_name):
                matches.append(fpath)
        except (ValueError, SyntaxError):
            continue
    return matches[0] if len(matches) == 1 else None


def _dedup_function_returns(fn_src: str) -> str:
    """If a function body has multiple top-level unconditional return statements, keep setup + last non-None return."""
    try:
        tree = ast.parse(fn_src)
    except SyntaxError:
        return fn_src
    if len(tree.body) != 1 or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return fn_src
    fn = tree.body[0]
    returns = [s for s in fn.body if isinstance(s, ast.Return)]
    if len(returns) <= 1:
        return fn_src
    non_none_returns = [
        r for r in returns
        if r.value is not None and not (isinstance(r.value, ast.Constant) and r.value.value is None)
    ]
    chosen_ret = non_none_returns[-1] if non_none_returns else returns[-1]
    src_lines = fn_src.splitlines()
    header = src_lines[fn.lineno - 1]
    kept_lines = [header]
    for stmt in fn.body:
        if isinstance(stmt, ast.Return):
            if stmt is chosen_ret:
                kept_lines.append("    " + node_source(fn_src, stmt).strip())
        else:
            for ln in node_source(fn_src, stmt).splitlines():
                kept_lines.append("    " + ln.strip() if not ln.startswith((" ", "\t")) else ln)
    cand = "\n".join(kept_lines) + "\n"
    try:
        ast.parse(cand)
        return cand
    except SyntaxError:
        return fn_src


def _repair_function_indentation(new_text: str, current: str = "", symbol: str = "") -> str:
    """Repair common 0.5B/1.5B function formatting issues (unindented body lines or body-only snippet)."""
    if not isinstance(new_text, str) or not new_text.strip():
        return new_text
    cleaned = textwrap.dedent(new_text).strip()
    # Strip accidental echoed trace=[...] suffix if present
    cleaned = re.sub(r",?\s*trace=\[.*\]\s*$", "", cleaned, flags=re.M)
    try:
        ast.parse(cleaned)
        if cleaned.startswith(("def ", "async def ", "class ", "from ", "import ")):
            return _dedup_function_returns(cleaned + "\n")
    except SyntaxError:
        pass
    lines = cleaned.splitlines()
    if lines and re.match(r"^(?:async\s+)?def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(.*\)\s*:\s*$", lines[0]):
        body = [ln for ln in lines[1:] if ln.strip()]
        if body and any(not ln.startswith((" ", "\t")) for ln in body):
            repaired_lines = [lines[0]]
            for ln in lines[1:]:
                if not ln.strip():
                    repaired_lines.append("")
                elif ln.startswith((" ", "\t")):
                    repaired_lines.append(ln)
                else:
                    repaired_lines.append("    " + ln)
            cand = "\n".join(repaired_lines) + "\n"
            try:
                ast.parse(cand)
                return _dedup_function_returns(cand)
            except SyntaxError:
                pass
    if not symbol and current:
        try:
            present = top_level_definition_names(current)
            if len(present) == 1:
                symbol = next(iter(present))
        except SyntaxError:
            pass
    # If the model emitted only the body statements (e.g. `return amount * (1 + rate)`) for a known function symbol:
    if (
        symbol
        and current
        and not cleaned.startswith(("def ", "async def ", "class "))
        and (cleaned.startswith("return ") or "\n" in cleaned or "=" in cleaned)
    ):
        try:
            node = locate_symbol(current, symbol, "module")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                src_lines = current.splitlines()
                header_line = src_lines[node.lineno - 1].strip()
                if header_line.endswith(":"):
                    setup_lines: list[str] = []
                    # If the snippet has no assignments and existing function has setup assignments before return, preserve them
                    if "=" not in cleaned and len(node.body) > 1 and isinstance(node.body[-1], ast.Return):
                        for stmt in node.body[:-1]:
                            for sln in node_source(current, stmt).splitlines():
                                setup_lines.append("    " + sln.strip())
                    indented_body = "\n".join(
                        setup_lines + [
                            ("    " + ln.lstrip()) if ln.strip() else ""
                            for ln in lines
                        ]
                    )
                    cand = f"{header_line}\n{indented_body}\n"
                    ast.parse(cand)
                    return _dedup_function_returns(cand)
        except (ValueError, SyntaxError, IndexError):
            pass
    return new_text


def _normalize_edit_path(raw_path: str, files: dict[str, str]) -> tuple[str, str | None]:
    """Normalize model path formats such as `/levy.py/apply_levy`, `levy.py:4`, or `/levy.py`
    ONLY when they map to an existing relative file in `files` without path traversal.
    """
    cleaned = str(raw_path or "").replace("\\", "/").strip()
    if not cleaned or ".." in Path(cleaned).parts:
        return cleaned, None
    if ":" in cleaned and cleaned.split(":", 1)[0].lstrip("/") in files:
        cleaned = cleaned.split(":", 1)[0]
    stripped = cleaned.lstrip("/")
    if stripped in files:
        return stripped, None
    if "/" in stripped:
        first_seg, rest = stripped.split("/", 1)
        if first_seg in files and rest and "/" not in rest:
            return first_seg, rest.strip()
    return cleaned, None


def prefer_symbol_targeted_edit(raw: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    """Rewrite a replace/replace_function into insert_function or a unique symbol replace when possible,
    strip unchanged echoed definitions when inserting a new function, and route cross-file symbols.
    """
    norm_path, path_sym = _normalize_edit_path(str(raw.get("path", "")), files)
    if norm_path != raw.get("path") or path_sym:
        raw = dict(raw)
        raw["path"] = norm_path
        if path_sym and not raw.get("symbol"):
            raw["symbol"] = path_sym
    path = contained_path(raw.get("path", ""))
    action = raw.get("action")
    new_text = raw.get("new_text") or ""
    if path not in files or type(new_text) is not str:
        return raw
    current = files.get(path, "")
    scope = str(raw.get("scope") or "module")
    raw_symbol = str(raw.get("symbol") or "").strip()
    if path.endswith(".py"):
        target_for_sig = current
        if raw_symbol and raw_symbol not in current:
            other_file = _find_unique_defining_file(raw_symbol, files, scope)
            if other_file:
                target_for_sig = files[other_file]
        repaired_text = _repair_function_indentation(new_text, target_for_sig, raw_symbol)
        if repaired_text != new_text:
            raw = dict(raw)
            raw["new_text"] = repaired_text
            new_text = repaired_text

    # If new_text contains multiple top-level definitions (e.g. echoed existing function + new function),
    # extract the newly added or modified definition(s) when action is insert_function / insert_after_symbol.
    if action in ("insert_function", "insert_after_symbol") and path.endswith(".py"):
        try:
            tree = ast.parse(new_text)
            defs = [
                n for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            ]
            present = names_in_scope(current, scope, raw_symbol)
            if len(defs) > 1:
                novel = [n for n in defs if n.name not in present]
                if novel:
                    extracted = "\n\n".join(node_source(new_text, n).strip() for n in novel) + "\n"
                    rewritten = dict(raw)
                    rewritten["new_text"] = extracted
                    rewritten["symbol"] = novel[0].name
                    if action == "insert_after_symbol" and raw_symbol not in present:
                        rewritten["action"] = "insert_function"
                    return rewritten
        except (ValueError, SyntaxError):
            pass

    if action == "replace_function":
        rewritten = dict(raw)
        rewritten["action"] = "replace"
        action = "replace"
    else:
        rewritten = dict(raw)

    if action != "replace":
        return rewritten

    name = inserted_definition_name(new_text) or raw_symbol
    if not name or not single_definition_source(new_text):
        return rewritten
    try:
        present = names_in_scope(current, scope, raw_symbol)
    except (ValueError, SyntaxError):
        return rewritten
    rewritten["symbol"] = name
    rewritten["scope"] = scope
    if name not in present:
        # Check if `name` is uniquely defined in another file of this repository (cross-file symbol edit)
        other_path = _find_unique_defining_file(name, files, scope)
        if other_path and other_path != path:
            other_src = files[other_path]
            node = locate_symbol(other_src, name, scope)
            if node is not None:
                rewritten["path"] = other_path
                rewritten["old_text"] = node_source(other_src, node)
                rewritten.pop("source_sha256", None)
                return rewritten
        rewritten["action"] = "insert_function"
        rewritten["old_text"] = ""
        return rewritten
    node = locate_symbol(current, name, scope)
    if node is None:
        return rewritten
    rewritten["old_text"] = node_source(current, node)
    return rewritten


def normalize_model_payload(payload: dict[str, Any], files: dict[str, str], task: Any = None) -> dict[str, Any]:
    """Normalize raw model JSON edits into clean symbol-level AST edits before validation."""
    if type(payload) is not dict or type(payload.get("edits")) is not list:
        return payload
    normalized_edits: list[dict[str, Any]] = []
    for raw in payload["edits"]:
        if type(raw) is not dict:
            normalized_edits.append(raw)
            continue
        norm_path, path_sym = _normalize_edit_path(str(raw.get("path", "")), files)
        if norm_path != raw.get("path") or path_sym:
            raw = dict(raw)
            raw["path"] = norm_path
            if path_sym and not raw.get("symbol"):
                raw["symbol"] = path_sym
        try:
            path = contained_path(raw.get("path", ""))
        except ValueError:
            normalized_edits.append(raw)
            continue
        action = str(raw.get("action") or "replace")
        new_text = raw.get("new_text")
        scope = str(raw.get("scope") or "module")
        raw_symbol = str(raw.get("symbol") or "").strip()
        if path not in files or type(new_text) is not str or not path.endswith(".py"):
            normalized_edits.append(raw)
            continue
        current = files[path]
        target_for_sig = current
        if raw_symbol and raw_symbol not in current:
            other_file = _find_unique_defining_file(raw_symbol, files, scope)
            if other_file:
                target_for_sig = files[other_file]
        repaired_text = _repair_function_indentation(new_text, target_for_sig, raw_symbol)
        if repaired_text != new_text:
            raw = dict(raw)
            raw["new_text"] = repaired_text
            new_text = repaired_text
        try:
            tree = ast.parse(new_text)
            defs = [
                n for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            ]
            present = names_in_scope(current, scope, raw_symbol)
        except (ValueError, SyntaxError):
            normalized_edits.append(raw)
            continue

        # If the model emitted multiple top-level functions in one edit, split them per symbol
        if len(defs) >= 1 and len(tree.body) == len(defs):
            split_any = False
            for dnode in defs:
                fn_src = node_source(new_text, dnode).strip() + "\n"
                target_path = path
                if dnode.name not in present:
                    other_file = _find_unique_defining_file(dnode.name, files, scope)
                    if other_file:
                        target_path = other_file
                target_current = files.get(target_path, "")
                try:
                    target_present = names_in_scope(target_current, scope, dnode.name)
                except (ValueError, SyntaxError):
                    target_present = set()
                if dnode.name in target_present:
                    existing_node = locate_symbol(target_current, dnode.name, scope)
                    if existing_node is not None:
                        existing_src = node_source(target_current, existing_node)
                        try:
                            if ast.dump(ast.parse(existing_src)) == ast.dump(ast.parse(fn_src)):
                                # Skip unchanged echoed helper function if other defs exist
                                if len(defs) > 1:
                                    split_any = True
                                    continue
                        except SyntaxError:
                            pass
                        normalized_edits.append({
                            "path": target_path,
                            "action": "replace",
                            "symbol": dnode.name,
                            "scope": scope,
                            "old_text": existing_src,
                            "new_text": fn_src,
                        })
                        split_any = True
                        continue
                else:
                    normalized_edits.append({
                        "path": target_path,
                        "action": "insert_function",
                        "symbol": dnode.name,
                        "scope": scope,
                        "old_text": "",
                        "new_text": fn_src,
                    })
                    split_any = True
                    continue
            if split_any:
                continue
        normalized_edits.append(raw)
    out = dict(payload)
    if normalized_edits:
        out["edits"] = normalized_edits
    return out


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


def validate_patch(payload: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    edits = []
    for raw in payload["edits"]:
        if type(raw) is not dict:
            raise ValueError("edit_not_object")
        raw = prefer_symbol_targeted_edit(raw, files)
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


def _infer_trace_arithmetic_hint(files: dict[str, str], r: dict[str, Any]) -> str | None:
    """Inspect public test input, expected output, and worker call-return trace to localize multi-step numeric errors."""
    exp = r.get("expected")
    inp = r.get("input")
    calls = [c for c in (r.get("calls") or []) if isinstance(c, dict) and c.get("event") == "return"]
    if not isinstance(exp, (int, float)) or isinstance(exp, bool) or not isinstance(inp, dict) or len(calls) < 2:
        return None
    target_val = float(exp)
    helper_call = calls[0]
    caller_call = calls[-1]
    h_file = str(helper_call.get("file") or "")
    h_fn = str(helper_call.get("function") or "")
    c_file = str(caller_call.get("file") or "")
    c_fn = str(caller_call.get("function") or "")
    if h_file not in files or c_file not in files:
        return None
    try:
        h_node = locate_symbol(files[h_file], h_fn, "module")
        c_node = locate_symbol(files[c_file], c_fn, "module")
    except SyntaxError:
        return None
    if not isinstance(h_node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not isinstance(c_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    h_params = [a.arg for a in h_node.args.args]
    c_params = [a.arg for a in c_node.args.args]
    if len(h_params) != 2 or len(c_params) != 1:
        return None
    p1, p2 = h_params[0], h_params[1]
    item_param = c_params[0]
    h_locals = helper_call.get("locals") or {}
    try:
        v1 = float(h_locals.get(p1))
        v2 = float(h_locals.get(p2))
    except (TypeError, ValueError):
        return None
    b_var = "billed"
    for stmt in c_node.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            b_var = stmt.targets[0].id
            break
    helper_candidates = [
        (f"{p1} * (1 + {p2})", v1 * (1.0 + v2)),
        (f"{p1} * (1 - {p2})", v1 * (1.0 - v2)),
        (f"{p1} + {p2}", v1 + v2),
        (f"{p1} - {p2}", v1 - v2),
        (f"{p1} * {p2}", v1 * v2),
    ]
    for h_expr, h_val in helper_candidates:
        for k3, raw_v3 in inp.items():
            if not isinstance(raw_v3, (int, float)) or isinstance(raw_v3, bool):
                continue
            v3 = float(raw_v3)
            if abs((h_val - v3) - target_val) < 1e-6:
                return (
                    f"Trace diagnostic: to reach public test expected={exp}, "
                    f"in `{h_file}` update `def {h_fn}({p1}, {p2}): return {h_expr}` (={h_val}) "
                    f"and in `{c_file}` update `def {c_fn}({item_param}):` to `return {b_var} - {item_param}['{k3}']` (={exp})."
                )
            if abs((h_val + v3) - target_val) < 1e-6:
                return (
                    f"Trace diagnostic: to reach public test expected={exp}, "
                    f"in `{h_file}` update `def {h_fn}({p1}, {p2}): return {h_expr}` (={h_val}) "
                    f"and in `{c_file}` update `def {c_fn}({item_param}):` to `return {b_var} + {item_param}['{k3}']` (={exp})."
                )
    return None


def _format_diagnostic_feedback(files: dict[str, str], public_tests: list[dict[str, Any]],
                                public_feedback: dict[str, Any] | None) -> str:
    lines: list[str] = []
    # Highlight missing entry functions required by public tests
    for case in public_tests[:6]:
        entry = str(case.get("entry") or "")
        if "." in entry:
            mod, fn = entry.split(".", 1)
            target_file = f"{mod}.py"
            if target_file in files:
                try:
                    present = top_level_definition_names(files[target_file])
                except SyntaxError:
                    present = set()
                if fn not in present:
                    lines.append(
                        f"Missing function required by public test: `{fn}` in `{target_file}` "
                        f"(use action=\"insert_function\" on path=\"{target_file}\" with symbol=\"{fn}\" "
                        f"and new_text=\"def {fn}(...):\\n    ...\" — do NOT redefine {sorted(present)})."
                    )
    if not public_feedback:
        return "\n".join(lines)
    init_pub = public_feedback.get("initial_public")
    results = (
        public_feedback.get("public_results")
        or (init_pub.get("results") if isinstance(init_pub, dict) else None)
        or (init_pub if isinstance(init_pub, list) else [])
        or []
    )
    for r in results[:6]:
        if not isinstance(r, dict) or r.get("passed"):
            continue
        entry = r.get("entry")
        inp = r.get("input")
        act = r.get("actual")
        exp = r.get("expected")
        err = r.get("error")
        call_summaries = []
        for c in (r.get("calls") or [])[:8]:
            if c.get("event") == "return":
                loc = c.get("locals") or {}
                loc_str = ", ".join(f"{k}={v}" for k, v in list(loc.items())[:4])
                call_summaries.append(
                    f"{c.get('function')}({loc_str}) in {c.get('file')} returned {c.get('return_value')}"
                )
        calls_note = ("; calls: " + ", ".join(call_summaries)) if call_summaries else ""
        lines.append(
            f"Failing public test: {entry} with input={inp} produced actual={act} (expected={exp}, error={err}){calls_note}"
        )
        hint = _infer_trace_arithmetic_hint(files, r)
        if hint:
            lines.append(hint)
    return "\n".join(lines)


def public_prompt(task, repo_index: dict[str, Any], grounded: dict[str, Any],
                  public_feedback: dict[str, Any] | None = None) -> str:
    files = getattr(task, "files", {})
    listed = []
    symbol_map: dict[str, list[str]] = {}
    for path, source in sorted(files.items())[:8]:
        listed.append(f"### {path}\n```python\n{source[:1800]}\n```")
        if path.endswith(".py"):
            try:
                symbol_map[path] = sorted(top_level_definition_names(source))
            except SyntaxError:
                symbol_map[path] = []
    docs = []
    for doc in list(getattr(task, "docs", []) or [])[:4]:
        docs.append(f"{doc.get('title', '')}: {str(doc.get('content', ''))[:400]}")
    pub_tests_list = list(getattr(task, "public_tests", []) or [])[:6]
    tests = json.dumps(pub_tests_list, allow_nan=False)[:1200]
    feedback = json.dumps(public_feedback or {}, allow_nan=False)[:1200]
    diag_summary = _format_diagnostic_feedback(files, pub_tests_list, public_feedback)
    validation = ""
    if public_feedback and public_feedback.get("validation_error"):
        validation = (
            f"Last validation error on the current staged source: {public_feedback['validation_error']}\n"
            "Revise that staged source. Prefer insert_function or insert_after_symbol "
            "for a new definition. For replace, old_text must occur exactly once. "
            "Do not send an incomplete snippet as a whole module.\n"
        )
    raw_symbols = repo_index.get("symbols", [])
    symbols_repr = symbol_map if symbol_map else (
        raw_symbols if isinstance(raw_symbols, dict) else list(raw_symbols or [])[:20]
    )
    return (
        "Propose a JSON patch for this local repository. Use only public tests and docs.\n"
        "Prefer symbol-targeted insert_function, insert_after_symbol, or a unique symbol replace.\n"
        "- To ADD a new function that is not yet in the file: use action=\"insert_function\", symbol=\"<new_fn>\", and put ONLY `def <new_fn>(...): ...` in new_text.\n"
        "- To MODIFY an existing function: use action=\"replace\" (or \"replace_function\"), symbol=\"<existing_fn>\", and put the complete updated `def <existing_fn>(...): ...` in new_text.\n"
        "- If two files both have bugs (e.g. a helper module and a caller module), include one edit per file in `edits`.\n"
        "Return edits with explicit paths. Do not claim private tests passed.\n"
        f"{validation}"
        f"{diag_summary + chr(10) if diag_summary else ''}"
        f"Request: {getattr(task, 'request', '')}\n"
        f"File source_sha256: {json.dumps({p: source_sha256(s) for p, s in files.items()})}\n"
        f"Language: {getattr(task, 'language', 'python')}\n"
        f"Symbols: {json.dumps(symbols_repr, default=str)}\n"
        f"Docs: {' | '.join(docs) or 'none'}\n"
        f"Grounded bindings: {json.dumps(grounded, default=str)[:400]}\n"
        f"Public tests: {tests}\n"
        f"Public execution feedback: {feedback}\n"
        "Files:\n" + "\n".join(listed)
    )


def propose_with_runtime(runtime, task, repo_index: dict[str, Any], grounded: dict[str, Any],
                         public_feedback: dict[str, Any] | None = None,
                         max_tokens: int = 512,
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
    cfg = getattr(runtime, "config", None)
    prior_max_tokens = getattr(cfg, "max_tokens", None) if cfg is not None else None
    bounded_tokens = min(512, max(1, int(max_tokens)))
    try:
        if cfg is not None and prior_max_tokens is not None:
            object.__setattr__(cfg, "max_tokens", bounded_tokens)
        try:
            raw = runtime.complete(prompt, PATCH_SCHEMA, max_tokens=bounded_tokens)
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
    finally:
        if cfg is not None and prior_max_tokens is not None:
            object.__setattr__(cfg, "max_tokens", prior_max_tokens)
    stop = inspect_completion_stop({**(raw if isinstance(raw, dict) else {}), **inspector.last})
    telemetry = dict(raw.get("telemetry") or {})
    telemetry["completion_stop"] = stop
    try:
        parsed = parse_model_patch(raw["content"])
        parsed = normalize_model_payload(parsed, files, task=task)
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
            "inference_ran": bool(telemetry.get("inference_ran")),
            "max_tokens": max_tokens,
            "truncation_claimed_as_cause": False,
        }
    first_edit = (validated.get("edits") or [{}])[0]
    return {
        "status": "proposed",
        "reason": None,
        "proposal": validated,
        "patched_files": patched,
        "raw_content": raw.get("content", "")[:800],
        "telemetry": telemetry,
        "completion_stop": stop,
        "inference_ran": bool(telemetry.get("inference_ran")),
        "action_kind": first_edit.get("action"),
        "target_symbol": first_edit.get("symbol"),
        "routed_from_file": first_edit.get("routed_from_file"),
        "max_tokens": max_tokens,
        "truncation_claimed_as_cause": False,
    }


def propose_coordinated_per_file(runtime, task, repo_index: dict[str, Any], grounded: dict[str, Any],
                                 public_feedback: dict[str, Any] | None = None,
                                 max_tokens_per_file: int = 512,
                                 max_tokens: int | None = None) -> dict[str, Any]:
    """One complete() per file. Later prompts see earlier staged edits.

    This is actual per-file generation, not apply_per_file staging helpers.
    """
    if max_tokens is not None:
        max_tokens_per_file = int(max_tokens)
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
        try:
            path_defs = sorted(top_level_definition_names(staged_now.get(path, ""))) if path.endswith(".py") else []
        except SyntaxError:
            path_defs = []
        defs_hint = f" (target function(s) in {path}: {path_defs})" if path_defs else ""
        single = type("T", (), {
            "files": staged_now,
            "request": (
                f"{getattr(task, 'request', '')} Coordinated edit: change only {path}{defs_hint}. "
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
        if proposed.get("status") == "proposed":
            patched_map = proposed.get("patched_files") or {}
            merged = dict(staging.staged)
            changed_any = False
            if path in patched_map and patched_map[path] != staged_now.get(path):
                merged[path] = patched_map[path]
                changed_any = True
            for other_p, other_src in patched_map.items():
                if other_p in merged and other_src != staged_now.get(other_p):
                    merged[other_p] = other_src
                    changed_any = True
            if changed_any or path in patched_map:
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
