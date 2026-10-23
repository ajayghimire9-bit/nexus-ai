"""Structured local-model patch proposals for SymbioticAgentLoop.

The model sees only public requirements, repository context, documentation and
public execution feedback. Structural validity is not semantic correctness.
Model outputs are never manufactured; a missing runtime is reported BLOCKED.
"""
from __future__ import annotations

import ast
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
                    "action": {"type": "string", "enum": ["replace", "create"]},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
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
        if action not in ("replace", "create"):
            raise ValueError("invalid_edit_action")
        new_text = raw.get("new_text")
        if type(new_text) is not str or len(new_text) > MAX_NEW_TEXT:
            raise ValueError("invalid_new_text")
        old_text = raw.get("old_text") or ""
        if type(old_text) is not str:
            raise ValueError("invalid_old_text")
        if action == "replace":
            if path not in files:
                raise ValueError(f"missing_target_file:{path}")
            if old_text:
                if files[path].count(old_text) != 1:
                    raise ValueError(f"old_text_not_unique:{path}")
            elif new_text == files[path]:
                raise ValueError("no_op_replace")
        elif action == "create" and path in files and files[path] and not old_text:
            raise ValueError(f"create_overwrites:{path}")
        if path.endswith(".py"):
            source = new_text if action == "create" or not old_text else files[path].replace(old_text, new_text, 1)
            ast.parse(source)
        edits.append({"path": path, "action": action, "old_text": old_text, "new_text": new_text})
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
        if edit["action"] == "create" and not edit["old_text"]:
            patched[path] = edit["new_text"]
            continue
        current = patched.get(path, "")
        if edit["old_text"]:
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
                         max_tokens: int = 256) -> dict[str, Any]:
    if runtime is None:
        return {
            "status": "BLOCKED",
            "reason": "local_model_unavailable",
            "proposal": None,
            "telemetry": None,
        }
    prompt = public_prompt(task, repo_index, grounded, public_feedback)
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
        }
    try:
        parsed = parse_model_patch(raw["content"])
        validated = validate_patch(parsed, task.files)
        patched = apply_patch(task.files, validated)
    except Exception as exc:
        return {
            "status": "invalid_proposal",
            "reason": type(exc).__name__ + ": " + str(exc)[:200],
            "proposal": None,
            "raw_content": raw.get("content", "")[:800],
            "telemetry": raw.get("telemetry"),
        }
    return {
        "status": "proposed",
        "reason": None,
        "proposal": validated,
        "patched_files": patched,
        "raw_content": raw.get("content", "")[:800],
        "telemetry": raw.get("telemetry"),
        "inference_ran": bool((raw.get("telemetry") or {}).get("inference_ran")),
    }
