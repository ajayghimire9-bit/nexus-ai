from nexus.seed.api_id_bindings import (
    apply_validated_proposal, interface_brief, named_binding_schema,
    parse_named_selection, request_satisfies_schema, validate_id_bindings,
)
from nexus.seed.capability_routes import apply_id_proposal
from nexus.seed.extraction_api_wiring import contract_ids
from nexus.seed.named_api_id import caller_path, with_shared_interface
from nexus.seed.named_api_id_tasks import CLOSED, all_declared, named_api_tasks
from nexus.seed.recovery_actions import run_cases


def test_fresh_ids_and_closed_unused():
    ids = [row["task_id"] for row in all_declared()]
    assert len(ids) == 4
    assert not (set(ids) & CLOSED)


def test_gold_named_bindings_satisfy_schema_and_task():
    for task in named_api_tasks():
        ids = contract_ids(task, task["files"])
        schema = named_binding_schema(ids)
        gold = task["gold_selection"]
        assert request_satisfies_schema(gold, schema) is True
        applied = apply_validated_proposal(task, gold, caller_path(task))
        assert applied["assembled"]["ok"] is True
        assert applied["assembled"]["executable"] is True
        assert run_cases(applied["files"], task["private"])["status"] == "passed"
        assert run_cases(applied["files"], task["public"])["status"] == "passed"


def test_schema_rejects_positional_and_unknown_fields():
    task = named_api_tasks()[0]
    ids = contract_ids(task, task["files"])
    schema = named_binding_schema(ids)
    assert request_satisfies_schema(
        dict(api_id="clip.clip_band", bindings=["field.vals", "field.lo", "field.hi"]),
        schema,
    ) is False
    assert request_satisfies_schema(
        dict(api_id="clip.clip_band", bindings={"vals": "no.such"}),
        schema,
    ) is False


def test_optional_omit_and_extra_and_elem_mismatch():
    tasks = {row["task_id"]: row for row in named_api_tasks()}
    stamp = tasks["api_nb_stamp"]
    ids = contract_ids(stamp, stamp["files"])
    omitted = validate_id_bindings(dict(api_id="labels.stamp", bindings={"text": "field.text"}), ids)
    assert omitted["ok"] is True
    extra = validate_id_bindings(
        dict(api_id="labels.stamp", bindings={"text": "field.text", "glue": "field.text"}),
        ids,
    )
    assert extra["ok"] is False
    assert extra["error"] == "extra_bindings"
    scale = tasks["api_nb_scale"]
    scale_ids = contract_ids(scale, scale["files"])
    elem = validate_id_bindings(
        dict(api_id="mathx.scale", bindings={"vals": "elem.vals", "factor": "field.factor"}),
        scale_ids,
    )
    assert elem["ok"] is False
    band = tasks["api_nb_band"]
    band_ids = contract_ids(band, band["files"])
    missing = validate_id_bindings(
        dict(api_id="clip.clip_band", bindings={"vals": "field.vals", "lo": "field.lo"}),
        band_ids,
    )
    assert missing["ok"] is False
    assert missing["error"] == "missing_required"


def test_shared_interface_reaches_direct_and_named():
    task = named_api_tasks()[0]
    brief = interface_brief(task, task["files"])
    assert "clip.clip_band" in brief
    assert "field.vals" in brief
    assert "elem.vals" in brief
    assert "lo:scalar" in brief
    shared = with_shared_interface(task)
    assert brief in shared["request"]
    parsed = parse_named_selection(
        '{"api_id":"clip.clip_band","bindings":{"vals":"field.vals","lo":"field.lo","hi":"field.hi"}}'
    )
    assert parsed["bindings"]["hi"] == "field.hi"


def test_opened_positional_cells_still_assemble():
    from nexus.seed.capability_routes_tasks import api_id_tasks
    task = api_id_tasks()[0]
    valid = apply_id_proposal(task, task["gold_selection"])
    assert valid["assembled"]["ok"] is True
