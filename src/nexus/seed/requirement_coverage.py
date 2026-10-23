"""Coverage of functions, files and API calls named in the public request.

Only the request text creates requirements. Behavioral words such as
“any” do not require a specific builtin. Historical artifacts are not
rewritten; this layer interprets them.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

ADD_FN = re.compile(
    r"\badd\s+(\w+)\s*\(([^)]*)\)\s+to\s+([A-Za-z0-9_./]+\.py)",
    re.I,
)
CREATE_IN = re.compile(
    r"\bcreate function\s+(\w+)\s*\(([^)]*)\)\s+in\s+([A-Za-z0-9_./]+\.py)",
    re.I,
)
USE_FROM = re.compile(
    r"\b(?:use|using)\s+(\w+)(?:\s+from\s+([A-Za-z0-9_]+))?",
    re.I,
)
NAMED_CALL = re.compile(
    r"\b(?:sum of|call|via|returns)\s+(\w+)(?:\s+on\b)?",
    re.I,
)
SKIP_NAMES = {
    "function", "item", "create", "return", "returns", "yes", "no",
    "any", "all", "sum", "len", "list", "int", "str", "the", "that", "when",
}


def public_requirements(request: str) -> dict[str, Any]:
    text = request or ""
    functions: list[dict[str, str]] = []
    files: list[str] = []
    apis: list[dict[str, str]] = []
    for match in ADD_FN.finditer(text):
        functions.append(dict(symbol=match.group(1), file=match.group(3), args=match.group(2)))
        files.append(match.group(3))
        apis.append(dict(name=match.group(1), module=Path(match.group(3)).stem, source="add"))
    for match in CREATE_IN.finditer(text):
        functions.append(dict(symbol=match.group(1), file=match.group(3), args=match.group(2)))
        files.append(match.group(3))
    for match in USE_FROM.finditer(text):
        apis.append(dict(name=match.group(1), module=match.group(2) or "", source="use"))
    for match in NAMED_CALL.finditer(text):
        name = match.group(1)
        if name.lower() not in SKIP_NAMES and not any(row["name"] == name for row in apis):
            apis.append(dict(name=name, module="", source="named"))
    seen_files = []
    for path in files:
        if path not in seen_files:
            seen_files.append(path)
    return dict(
        functions=functions,
        files=seen_files,
        apis=apis,
        imposed_implementation=False,
    )


def _has_def(source: str, symbol: str) -> bool:
    try:
        tree = ast.parse(source or "")
    except SyntaxError:
        return f"def {symbol}" in (source or "")
    return any(
        isinstance(node, ast.FunctionDef) and node.name == symbol
        for node in ast.walk(tree)
    )


def _calls_name(source: str, name: str) -> bool:
    try:
        tree = ast.parse(source or "")
    except SyntaxError:
        return name in (source or "")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == name:
                return True
            if isinstance(func, ast.Attribute) and func.attr == name:
                return True
    return False


def score_requirement_coverage(request: str, files: dict[str, str]) -> dict[str, Any]:
    required = public_requirements(request)
    missing_files = [path for path in required["files"] if path not in files]
    missing_functions = [
        row for row in required["functions"]
        if not _has_def(files.get(row["file"], ""), row["symbol"])
    ]
    missing_apis = []
    joined = "\n".join(files.values())
    for api in required["apis"]:
        if api["source"] == "add":
            continue
        if not _calls_name(joined, api["name"]):
            missing_apis.append(api)
    passed = not missing_files and not missing_functions and not missing_apis
    return dict(
        passed=passed,
        required=required,
        missing_files=missing_files,
        missing_functions=missing_functions,
        missing_apis=missing_apis,
        imposed_implementation=False,
    )
