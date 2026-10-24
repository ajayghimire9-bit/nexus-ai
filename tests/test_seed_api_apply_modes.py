from nexus.seed.api_apply import caller_path, with_shared_interface
from nexus.seed.api_apply_tasks import CLOSED, all_declared, apply_api_tasks
from nexus.seed.api_id_bindings import (
    apply_binding_schema, assemble_apply_proposal, compatible_field_ids,
    parse_apply_selection, request_satisfies_apply_schema, type_validity,
    validate_id_bindings,
)
from nexus.seed.extraction_api_wiring import contract_ids
from nexus.seed.recovery_actions import run_cases


def _by_id():
    return {row["task_id"]: row for row in apply_api_tasks()}


def test_balanced_roles_and_closed_ids():
    rows = all_declared()
    assert len(rows) == 9
    assert not {row["task_id"] for row in rows} & CLOSED
    roles = [row["role"] for row in rows]
    assert roles.count("optional_omitted") == 2
    assert roles.count("optional_supplied") == 2
    assert roles.count("whole_list") == 2
    assert roles.count("element_wise") == 2
    assert roles.count("ambiguous_ask") == 1
    apis = []
    for row in rows:
        if row["gold_selection"].get("api_id"):
            apis.append(row["gold_selection"]["api_id"])
    assert len(set(apis)) == len(apis)


def test_gold_non_ask_executes():
    for task in apply_api_tasks():
        if task["gold_selection"].get("ask"):
            continue
        applied = assemble_apply_proposal(task, task["gold_selection"], caller_path(task))
        assert applied["assembled"].get("executable") is True
        assert run_cases(applied["files"], task["private"])["status"] == "passed"


def test_optional_may_be_absent_and_must_not_be_forced():
    task = _by_id()["api_ap_omit_badge"]
    ids = contract_ids(task, task["files"])
    omitted = validate_id_bindings(dict(api_id="labels.badge", bindings={"name": "field.name"}), ids)
    assert omitted["ok"] is True
    typed = type_validity(dict(api_id="labels.badge", bindings={"name": "field.name"}, apply="direct"), ids)
    assert typed["type_valid"] is True
    supplied = assemble_apply_proposal(
        task,
        dict(api_id="labels.badge", bindings={"name": "field.name", "tag": "field.title"}, apply="direct"),
        caller_path(task),
    )
    assert supplied["assembled"].get("executable") is True
    assert run_cases(supplied["files"], task["private"])["status"] != "passed"


def test_type_validity_separate_from_structure():
    task = _by_id()["api_ap_elem_tall"]
    ids = contract_ids(task, task["files"])
    schema = apply_binding_schema(ids)
    wrong = dict(api_id="gate.over", bindings={"n": "field.heights", "bar": "field.bar"}, apply="element")
    assert request_satisfies_apply_schema(wrong, schema) is True
    typed = type_validity(wrong, ids)
    assert typed["type_valid"] is False
    assert typed["error"] == "type_mismatch"
    applied = assemble_apply_proposal(task, wrong, caller_path(task))
    assert applied["assembled"].get("executable") is not True


def test_apply_mode_and_compatible_limits():
    tall = _by_id()["api_ap_elem_tall"]
    ids = contract_ids(tall, tall["files"])
    whole = type_validity(
        dict(api_id="gate.over", bindings={"n": "elem.heights", "bar": "field.bar"}, apply="whole_list"),
        ids,
    )
    assert whole["type_valid"] is False
    ask = _by_id()["api_ap_ask_limit"]
    ask_ids = contract_ids(ask, ask["files"])
    bar = next(row for row in ask_ids["apis"] if row["id"] == "gate.over")["params"][1]
    compatible = compatible_field_ids(bar, ask_ids)
    assert "field.loft" in compatible and "field.width" in compatible
    parsed = parse_apply_selection('{"ask":true,"question":"Which limit, loft or width?"}')
    assert parsed["ask"] is True
    applied = assemble_apply_proposal(ask, parsed, caller_path(ask))
    assert applied["assembled"]["error"] == "asked"


def test_shared_interface_mentions_apply_and_decoys():
    task = _by_id()["api_ap_list_stretch"]
    shared = with_shared_interface(task)
    assert "whole_list" in shared["request"]
    assert "field.alts" in shared["request"]
    assert "stats.stretch" in shared["request"]
