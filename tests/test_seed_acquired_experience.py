from nexus.seed.api_id_bindings import (
    assemble_validated_id, score_binding_tracks, validate_id_bindings,
)
from nexus.seed.coordinated_stage import passing_receipt, publish_ready
from nexus.seed.experience_transfer import (
    acquire_from_source, freeze_representation, record_episode, run_memory_cell,
    verdict,
)
from nexus.seed.experience_transfer_tasks import (
    CLOSED, all_declared, source_tasks, target_tasks,
)
from nexus.seed.capability_evidence import EventMeter
from nexus.seed.repair_schema_memory import (
    OrdinaryExactCache, RepairSchemaStore, propose_guarded_template,
    propose_retrieved_repair,
)


def _ids():
    return {
        "apis": [{
            "id": "span.floor_cut", "name": "floor_cut", "module": "span",
            "params": [
                {"name": "nums", "type": "list"},
                {"name": "lo", "type": "scalar"},
            ],
        }],
        "fields": [
            {"id": "field.nums", "kind": "field", "type": "list", "name": "nums",
             "access": 'item["nums"]'},
            {"id": "field.lo", "kind": "field", "type": "int", "name": "lo",
             "access": 'item["lo"]'},
            {"id": "elem.nums", "kind": "elem", "type": "int", "name": "nums",
             "access": "element"},
        ],
    }


def test_extra_and_elem_bindings_never_assemble():
    ids = _ids()
    extra = dict(api_id="span.floor_cut",
                 bindings=["field.nums", "elem.nums", "field.lo"])
    checked = validate_id_bindings(extra, ids)
    assembled = assemble_validated_id(extra, ids, {
        "transform_symbol": "_go_transform", "fields": [{"name": "item"}],
    })
    assert checked["ok"] is False
    assert checked["executable"] is False
    assert assembled["ok"] is False
    assert assembled["source"] == ""
    assert assembled["executable"] is False
    named_extra = dict(api_id="span.floor_cut",
                       bindings={"nums": "field.nums", "lo": "field.lo", "hi": "field.lo"})
    assert validate_id_bindings(named_extra, ids)["error"] == "extra_bindings"
    unknown = validate_id_bindings(dict(api_id="no.such", bindings=["field.nums"]), ids)
    assert unknown["error"] == "unknown_api_id"


def test_named_bindings_and_tracks():
    ids = _ids()
    gold = dict(api_id="span.floor_cut",
                bindings={"nums": "field.nums", "lo": "field.lo"})
    assembled = assemble_validated_id(gold, ids, {
        "transform_symbol": "_go_transform",
        "fields": [{"name": "item", "type": "int"}],
    })
    assert assembled["ok"] is True
    assert assembled["executable"] is True
    tracks = score_binding_tracks(gold, gold, assembled)
    assert tracks["selection_correct"] is True
    assert tracks["binding_valid"] is True
    assert tracks["bindings_correct"] is True
    assert tracks["assembly_valid"] is True
    assert tracks["selection_not_generally_solved"] is True


def test_publish_receipt_and_constant_not_banned():
    from nexus.seed.function_contracts import bind_function_contract
    task = dict(
        request="Create function over(value, limit) and ready(item) using over.",
        files={
            "util.py": "def over(value, limit):\n    return value > limit\n",
            "app.py": "def ready(item):\n    return True\n",
        },
        public=[
            {"entry": "util.over", "input": {"value": 3, "limit": 1},
             "expected": True, "kwargs_input": True},
            {"entry": "app.ready", "input": {"n": 1}, "expected": True},
        ],
        private=[],
        contract={"symbol": "ready"},
        function_contracts={
            "util.over": bind_function_contract(
                "util.over", "over", ["value", "limit"], "bool"),
            "app.ready": bind_function_contract(
                "app.ready", "ready", ["item"], "bool"),
        },
        function_stages=[
            dict(role="helper", path="util.py", symbol="over", entry="util.over",
                 args=["value", "limit"], output_type="bool"),
            dict(role="caller", path="app.py", symbol="ready", entry="app.ready",
                 args=["item"], output_type="bool"),
        ],
    )
    gate = publish_ready(task, task["files"])
    assert gate["required_call"] is False
    assert gate["ready"] is False
    bound = passing_receipt(task["files"], dict(
        helper_present=gate.get("helper_present"),
        caller_present=gate.get("caller_present"),
        required_call=gate.get("required_call"),
        helper_behavior=gate.get("helper_behavior"),
        caller_behavior=gate.get("caller_behavior"),
        public_passed=(gate.get("scored") or {}).get("public_passed"),
    ))
    assert gate["receipt"] == bound
    calling = dict(task["files"], **{
        "app.py": "from util import over\ndef ready(item):\n    return over(2, 1)\n",
    })
    ok = publish_ready(task, calling)
    assert ok["required_call"] is True
    assert ok["ready"] is True


def test_splits_and_closed_ids():
    ids = [row["task_id"] for row in all_declared()]
    assert len(ids) == len(set(ids))
    assert not (set(ids) & CLOSED)
    roles = {row["reuse_role"] for row in target_tasks()}
    assert roles == {
        "related_rename", "related_rebound", "harmful_if_applied",
        "unrelated_abstain", "ambiguous_ask", "exact_repeat",
    }
    frozen = freeze_representation()
    assert frozen["collapse_c_and_d"] is False
    assert frozen["chosen_before_target_outcomes"] is True


def test_acquisition_and_c_versus_d():
    events = []
    meter = EventMeter(events.append)
    source = [row for row in source_tasks() if row["reuse_role"] == "source"][0]
    acquired = acquire_from_source(source, meter)
    assert acquired["usable"] is True
    assert acquired["schema"].transformation == "compare_op_swap"
    assert acquired["episode"]["private_tests_used"] is False
    assert acquired["episode"]["task_id_features"] is False
    store = RepairSchemaStore()
    store.remember(acquired["schema"])
    cache = OrdinaryExactCache()
    cache.put(source["request"], source["files"], acquired["files"])
    tasks = {row["task_id"]: row for row in target_tasks()}
    rename = run_memory_cell(tasks["tgt_rename_layout"], "acquired", store, cache, meter)
    template = run_memory_cell(tasks["tgt_rename_layout"], "ordinary_template", store, cache, meter)
    rebound = run_memory_cell(tasks["tgt_gt_floor"], "acquired", store, cache, meter)
    template_gt = run_memory_cell(tasks["tgt_gt_floor"], "ordinary_template", store, cache, meter)
    harmful = run_memory_cell(tasks["tgt_strict_cut"], "acquired", store, cache, meter)
    abstain = run_memory_cell(tasks["tgt_join_parts"], "acquired", store, cache, meter)
    ask = run_memory_cell(tasks["tgt_near_bound"], "acquired", store, cache, meter)
    exact = run_memory_cell(tasks["tgt_exact_limit"], "exact_cache", store, cache, meter)
    assert rename["private_passed"] is True
    assert template["private_passed"] is True
    assert rebound["private_passed"] is True
    assert rebound["decision"] == "apply"
    assert template_gt["decision"] in {"abstain", "refuse"}
    assert template_gt["private_passed"] is False
    assert harmful["decision"] == "refuse"
    assert harmful["harmful_transfer"] is False
    assert harmful["private_passed"] is True
    assert abstain["decision"] in {"abstain", "refuse"}
    assert ask["decision"] == "ask"
    assert exact["decision"] == "apply"
    empty = RepairSchemaStore()
    reset = run_memory_cell(tasks["tgt_rename_layout"], "acquired", empty, OrdinaryExactCache(), meter)
    assert reset["decision"] == "abstain"
    irr = RepairSchemaStore()
    null = [row for row in source_tasks() if row["family"] == "null_default"][0]
    null_row = acquire_from_source(null, meter)
    if null_row["schema"]:
        irr.remember(null_row["schema"])
    irrelevant = run_memory_cell(tasks["tgt_gt_floor"], "irrelevant_memory", irr, cache, meter)
    assert irrelevant["decision"] in {"abstain", "refuse"}
    assert irrelevant["private_passed"] is False


def test_episode_excludes_private_and_verdict_rules():
    episode = record_episode(
        dict(request="Allow score equal to the limit in accept(item).", contract={}),
        {"hold.py": "x"},
        None, ["apply_make_inclusive"], {"hold.py": "y"},
        {"public_passed": True}, {"wall_s": 0.01, "model_calls": 0},
    )
    dumped = str(episode)
    assert "private" not in dumped or episode["private_tests_used"] is False
    assert episode["handwritten_answer"] is False
    summary = {
        "scratch": {"later_private": 1, "harmful": 0},
        "ordinary_template": {"later_private": 3, "harmful": 0},
        "acquired": {"later_private": 3, "harmful": 0},
        "acquired_reset": {"later_private": 1, "harmful": 0},
        "irrelevant_memory": {"later_private": 1, "harmful": 0},
    }
    assert verdict(summary, []) == "ordinary_template_tie"
    summary["acquired"]["later_private"] = 4
    assert verdict(summary, []) == "useful_transfer"
    summary["acquired"]["harmful"] = 1
    assert verdict(summary, []) == "negative"
