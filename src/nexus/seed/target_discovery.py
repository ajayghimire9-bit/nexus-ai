"""Select an edit target from request text and repository symbols.

Does not read public-test entries. Discovery failures must not be used as
coding scores; this module is measured separately from the assembler.
"""
from __future__ import annotations

from typing import Any

from .constrained_edit import existing_definitions, requested_functions
from .local_model_patch_proposer import locate_symbol, node_source, source_sha256


def inventory(files: dict[str, str]) -> list[dict[str, str]]:
    rows = []
    for path, name, args in existing_definitions(files):
        rows.append({"path": path, "symbol": name, "args": args})
    return rows


def discover_edit_target(
    request: str,
    files: dict[str, str],
    docs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    symbols = inventory(files)
    by_name = {row["symbol"]: row for row in symbols}
    mentioned = requested_functions(request)
    text = " ".join(
        [request or ""]
        + [str(doc.get("title", "")) + " " + str(doc.get("content", "")) for doc in (docs or [])]
    )
    reason = "no_symbol"
    action = "abstain"
    path = ""
    symbol = ""
    args = "item"
    if mentioned:
        name, req_args = mentioned[0]
        symbol, args = name, req_args or "item"
        if name in by_name:
            path = by_name[name]["path"]
            args = by_name[name]["args"] or args
            action = "replace_function"
            reason = "request_names_existing_symbol"
        else:
            stems = [p for p in sorted(files) if p.endswith(".py") and p[:-3] in text]
            path = stems[0] if stems else next((p for p in sorted(files) if p.endswith(".py")), "")
            action = "insert_function"
            reason = "request_names_missing_symbol"
    elif len(symbols) == 1:
        path, symbol, args = symbols[0]["path"], symbols[0]["symbol"], symbols[0]["args"]
        action = "replace_function"
        reason = "single_existing_symbol"
    elif symbols:
        scored = []
        for row in symbols:
            score = (row["symbol"] in text) + (row["path"][:-3] in text if row["path"].endswith(".py") else 0)
            scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1]["path"], item[1]["symbol"]))
        if scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
            row = scored[0][1]
            path, symbol, args = row["path"], row["symbol"], row["args"]
            action = "replace_function"
            reason = "unique_name_or_file_mention"
        else:
            reason = "ambiguous_symbols"
    existing = ""
    digest = ""
    if path and symbol and path in files and action == "replace_function":
        source = files[path]
        digest = source_sha256(source)
        try:
            existing = node_source(source, locate_symbol(source, symbol))
        except Exception:
            existing = ""
    elif path in files:
        digest = source_sha256(files[path])
    return {
        "action": action,
        "path": path,
        "symbol": symbol,
        "args": args,
        "source_sha256": digest,
        "existing_source": existing,
        "reason": reason,
        "inventory": symbols,
        "used_public_tests": False,
    }


def score_discovery(discovered: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    return {
        "path_correct": discovered.get("path") == gold.get("path"),
        "symbol_correct": discovered.get("symbol") == gold.get("symbol"),
        "action_correct": discovered.get("action") == gold.get("action"),
        "target_correct": (
            discovered.get("path") == gold.get("path")
            and discovered.get("symbol") == gold.get("symbol")
            and discovered.get("action") == gold.get("action")
        ),
        "used_public_tests": bool(discovered.get("used_public_tests")),
        "reason": discovered.get("reason"),
        "discovered": {
            "path": discovered.get("path"),
            "symbol": discovered.get("symbol"),
            "action": discovered.get("action"),
        },
        "gold": {
            "path": gold.get("path"),
            "symbol": gold.get("symbol"),
            "action": gold.get("action"),
        },
    }
