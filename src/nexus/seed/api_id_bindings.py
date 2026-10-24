"""Validate API-ID bindings before any assembly.

An invalid binding never becomes an executable call. Extra bindings are
rejected, not dropped. Named parameter-to-ID bindings are preferred.
Programmer-supplied. Not schema learning. Selection is not generally solved.
"""
from __future__ import annotations

from typing import Any

import json
from .extraction_api_wiring import assemble_id_wiring, available_interfaces, contract_ids
from .extraction_contract import wrap_transform


def _api(ids: dict[str, Any], api_id: str | None) -> dict[str, Any] | None:
    return next((row for row in ids.get("apis") or [] if row["id"] == api_id), None)


def _field(ids: dict[str, Any], field_id: str | None) -> dict[str, Any] | None:
    return next((row for row in ids.get("fields") or [] if row["id"] == field_id), None)


def field_shape(field: dict[str, Any]) -> str:
    if field.get("kind") == "elem":
        return "scalar"
    if field.get("type") == "list":
        return "list"
    return "scalar"


def normalize_named_bindings(proposal: dict[str, Any], api: dict[str, Any]) -> dict[str, Any]:
    raw = proposal.get("bindings")
    params = list(api.get("params") or [])
    required = [row["name"] for row in params if not row.get("optional")]
    if isinstance(raw, dict):
        extra = sorted(set(raw) - {row["name"] for row in params})
        missing = [name for name in required if name not in raw or not raw.get(name)]
        ordered = [raw.get(row["name"]) for row in params if raw.get(row["name"])]
        return dict(
            form="named",
            ordered=[str(item) for item in ordered],
            extra=extra,
            missing=missing,
            names=list(raw),
        )
    items = [str(item) for item in (raw or [])]
    return dict(
        form="positional",
        ordered=items,
        extra=items[len(params):],
        missing=required[len(items):],
        names=[],
    )


def validate_id_bindings(proposal: dict[str, Any] | None, ids: dict[str, Any]) -> dict[str, Any]:
    """Binding validity only. Gold match is scored elsewhere."""
    if not proposal:
        return dict(ok=False, error="missing_proposal", binding_valid=False, executable=False)
    api = _api(ids, proposal.get("api_id"))
    if api is None:
        return dict(ok=False, error="unknown_api_id", binding_valid=False, executable=False)
    mapped = normalize_named_bindings(proposal, api)
    if mapped["extra"]:
        return dict(
            ok=False, error="extra_bindings", extra=mapped["extra"],
            binding_valid=False, executable=False,
        )
    if mapped["missing"]:
        return dict(
            ok=False, error="missing_required", missing=mapped["missing"],
            binding_valid=False, executable=False,
        )
    uses_elem = False
    for index, field_id in enumerate(mapped["ordered"]):
        field = _field(ids, field_id)
        if field is None:
            return dict(ok=False, error="unknown_field_id", binding_valid=False, executable=False)
        param = api["params"][index]
        got = field_shape(field)
        if param["type"] != got:
            return dict(
                ok=False, error="type_mismatch", expected=param["type"], actual=got,
                binding_valid=False, executable=False,
            )
        if field.get("kind") == "elem":
            uses_elem = True
            if param["type"] == "list":
                return dict(
                    ok=False, error="elem_on_list_param",
                    binding_valid=False, executable=False,
                )
    if uses_elem and len(mapped["ordered"]) != len(api["params"]):
        return dict(ok=False, error="elem_arity", binding_valid=False, executable=False)
    return dict(
        ok=True, error=None, binding_valid=True, executable=False,
        ordered=mapped["ordered"], form=mapped["form"],
        api_exists=True,
    )


def assemble_validated_id(proposal: dict[str, Any] | None, ids: dict[str, Any],
                          contract: dict[str, Any]) -> dict[str, Any]:
    checked = validate_id_bindings(proposal, ids)
    if not checked.get("ok"):
        return dict(
            ok=False, source="", error=checked.get("error"),
            programmer_supplied=True, executable=False,
            binding_valid=False, invented_arguments=False, extras_dropped=False,
        )
    positional = dict(proposal or {}, bindings=checked["ordered"])
    assembled = assemble_id_wiring(positional, ids, contract)
    if assembled.get("ok") and assembled.get("source"):
        assembled = dict(assembled, executable=True, binding_valid=True)
    else:
        assembled = dict(assembled or {}, executable=False, binding_valid=True)
    assembled["programmer_supplied"] = True
    assembled["learned_assembly"] = False
    return assembled


def apply_validated_proposal(task: dict[str, Any], proposal: dict[str, Any] | None,
                             caller: str) -> dict[str, Any]:
    from .extraction_api_wiring import contract_ids
    ids = contract_ids(task, task["files"])
    assembled = assemble_validated_id(proposal, ids, task["contract"])
    files = dict(task["files"])
    if assembled.get("ok") and assembled.get("source"):
        files[caller] = wrap_transform(task["contract"], assembled["source"])
    else:
        assembled = dict(assembled, ok=False, source="", executable=False)
    return dict(assembled=assembled, files=files, ids=ids)


def score_binding_tracks(proposal: dict[str, Any] | None, gold: dict[str, Any],
                         assembled: dict[str, Any]) -> dict[str, Any]:
    gold_bind = gold.get("bindings")
    proposed = (proposal or {}).get("bindings")
    if isinstance(gold_bind, dict) and isinstance(proposed, dict):
        bindings_correct = proposed == gold_bind
    else:
        bindings_correct = list(proposed or []) == list(gold_bind or [])
    return dict(
        selection_correct=bool(proposal) and proposal.get("api_id") == gold.get("api_id"),
        binding_valid=bool(assembled.get("binding_valid") or assembled.get("ok")),
        bindings_correct=bindings_correct,
        assembly_valid=bool(assembled.get("ok") and assembled.get("source")),
        selection_not_generally_solved=True,
    )


def named_binding_schema(ids: dict[str, Any]) -> dict[str, Any]:
    """Parameter-name → field-ID object. Programmer-supplied. Not schema learning."""
    api_enum = [row["id"] for row in ids.get("apis") or []] or ["none"]
    field_enum = [row["id"] for row in ids.get("fields") or []] or ["none"]
    return {
        "type": "object",
        "properties": {
            "api_id": {"type": "string", "enum": api_enum},
            "bindings": {
                "type": "object",
                "additionalProperties": {"type": "string", "enum": field_enum},
                "minProperties": 1,
                "maxProperties": 8,
            },
        },
        "required": ["api_id", "bindings"],
        "additionalProperties": False,
    }


def parse_named_selection(content: str) -> dict[str, Any] | None:
    raw = (content or "").strip()
    if "{" not in raw or "}" not in raw:
        return None
    try:
        payload = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        return None
    if type(payload) is not dict or type(payload.get("api_id")) is not str:
        return None
    bindings = payload.get("bindings")
    if type(bindings) is not dict:
        return None
    if not all(type(key) is str and type(value) is str for key, value in bindings.items()):
        return None
    return dict(api_id=payload["api_id"].strip(),
                bindings={key.strip(): value.strip() for key, value in bindings.items()})


def request_satisfies_schema(payload: dict[str, Any] | None, schema: dict[str, Any]) -> bool:
    """Structural schema check only. Not binding correctness."""
    if not payload or type(payload) is not dict:
        return False
    extra = set(payload) - set(schema.get("properties") or {})
    if extra:
        return False
    for key in schema.get("required") or []:
        if key not in payload:
            return False
    api_enum = ((schema.get("properties") or {}).get("api_id") or {}).get("enum") or []
    if payload.get("api_id") not in api_enum:
        return False
    bindings = payload.get("bindings")
    if type(bindings) is not dict or not bindings:
        return False
    field_enum = (((schema.get("properties") or {}).get("bindings") or {}).get(
        "additionalProperties") or {}).get("enum") or []
    return all(type(key) is str and value in field_enum for key, value in bindings.items())


def interface_brief(task: dict[str, Any], files: dict[str, str]) -> str:
    """Shared interface text for named-ID and direct generation."""
    from .extraction_api_context import derive_compact_interface as compact_fn
    ids = contract_ids(task, files)
    compact = compact_fn(task.get("docs") or [], files, task["request"])
    if "sum(" in compact:
        raise ValueError("interface_brief_leaked_sum")
    interfaces = available_interfaces(files)
    if "sum(" in interfaces:
        raise ValueError("interface_brief_leaked_sum")
    api_lines = []
    for row in ids.get("apis") or []:
        parts = []
        for param in row.get("params") or []:
            note = param["name"] + ":" + param["type"]
            if param.get("optional"):
                note += "=optional"
            parts.append(note)
        api_lines.append(f"{row['id']}({', '.join(parts)})")
    field_ids = ", ".join(row["id"] for row in ids.get("fields") or []) or "none"
    return (
        "Use only the listed APIs and field IDs.\n"
        "field.X is the extracted field. elem.X is one element of a list field.\n"
        f"Valid API IDs: {', '.join(row['id'] for row in ids.get('apis') or []) or 'none'}\n"
        f"API parameters: {'; '.join(api_lines) or 'none'}\n"
        f"Valid field IDs: {field_ids}\n"
        f"Available interfaces: {interfaces}\n"
        f"Compact interface: {compact}\n"
    )


def named_selection_prompt(task: dict[str, Any], files: dict[str, str]) -> str:
    return (
        "Choose an API and bind each parameter name to one field ID. "
        "Do not write the function body. Do not write the completed program.\n"
        'Return JSON {"api_id": "...", "bindings": {"param": "field...." }}.\n'
        "Required parameters must be present. Extra parameter names are rejected. "
        "Omit an optional parameter to keep its default. "
        "Do not add elem.* unless that parameter is a scalar over a list.\n"
        f"Request: {task['request']}\n"
        + interface_brief(task, files)
    )


def score_named_tracks(proposal: dict[str, Any] | None, gold: dict[str, Any],
                       assembled: dict[str, Any], schema: dict[str, Any],
                       private_passed: bool) -> dict[str, Any]:
    tracks = score_binding_tracks(proposal, gold, assembled)
    schema_ok = request_satisfies_schema(proposal, schema)
    return dict(
        schema_ok=schema_ok,
        bindings_correct=tracks["bindings_correct"],
        task_satisfied=bool(private_passed and assembled.get("executable")),
        selection_correct=tracks["selection_correct"],
        binding_valid=tracks["binding_valid"],
        assembly_valid=tracks["assembly_valid"],
        selection_not_generally_solved=True,
    )
