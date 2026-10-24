from nexus.seed.api_id_bindings import assemble_validated_id, validate_id_bindings
from nexus.seed.capability_evidence import EventMeter
from nexus.seed.capability_routes import apply_id_proposal, score_id_cell
from nexus.seed.equal_inclusive import (
    retrieve, freeze_representation, verdict,
)
from nexus.seed.equal_inclusive_tasks import (
    CLOSED, all_declared, api_id_tasks, source_tasks, target_tasks,
)
from nexus.seed.experience_transfer import acquire_from_source
from nexus.seed.extraction_api_wiring import contract_ids
from nexus.seed.recovery_actions import run_cases
from nexus.seed.repair_schema_memory import (
    OrdinaryExactCache, RepairSchemaStore, propose_inclusive_tool,
    propose_guarded_template,
)


def test_fresh_ids_and_closed_unused():
    ids = [row["task_id"] for row in all_declared()]
    assert len(ids) == len(set(ids))
    assert not (set(ids) & CLOSED)
    frozen = freeze_representation()
    assert frozen["learning_to_learn"] is False
    assert frozen["ranking_paused"] is True


def test_inclusive_tool_matches_acquired_on_lt_and_gt():
    events = []
    meter = EventMeter(events.append)
    source = [row for row in source_tasks() if row["reuse_role"] == "source"][0]
    acquired = acquire_from_source(source, meter)
    assert acquired["usable"] is True
    store = RepairSchemaStore()
    store.remember(acquired["schema"])
    cache = OrdinaryExactCache()
    cache.put(source["request"], source["files"], acquired["files"])
    tasks = {row["task_id"]: row for row in target_tasks()}
    for task_id in ("tgt_eq_rename", "tgt_eq_gt"):
        tool = retrieve(tasks[task_id], "inclusive_tool", store, cache, meter)
        mem = retrieve(tasks[task_id], "acquired", store, cache, meter)
        assert tool["decision"] == "apply"
        assert mem["decision"] == "apply"
        assert tool["files"] == mem["files"]
    exclusive = retrieve(tasks["tgt_eq_exclusive"], "inclusive_tool", store, cache, meter)
    assert exclusive["decision"] == "refuse"
    ask = retrieve(tasks["tgt_eq_ask"], "inclusive_tool", store, cache, meter)
    assert ask["decision"] == "ask"
    unrelated = retrieve(tasks["tgt_eq_unrelated"], "inclusive_tool", store, cache, meter)
    assert unrelated["decision"] == "abstain"
    old_gt = propose_guarded_template(
        "comparison_boundary", tasks["tgt_eq_gt"]["request"],
        tasks["tgt_eq_gt"]["files"], tasks["tgt_eq_gt"]["public"], None,
    )
    assert old_gt.decision in {"abstain", "refuse"}
    equal = propose_inclusive_tool(
        tasks["tgt_eq_gt"]["request"], tasks["tgt_eq_gt"]["files"],
        tasks["tgt_eq_gt"]["public"], None,
    )
    assert equal.decision == "apply"


def test_fresh_api_gold_executes_and_extra_elem_rejected():
    task = api_id_tasks()[0]
    valid = apply_id_proposal(task, task["gold_selection"])
    assert valid["assembled"]["ok"] is True
    assert valid["assembled"]["executable"] is True
    assert run_cases(valid["files"], task["private"])["status"] == "passed"
    scored = score_id_cell(task, task["gold_selection"], valid["files"], valid["assembled"])
    assert scored["selection_correct"] is True
    assert scored["bindings_correct"] is True
    assert scored["assembled_ok"] is True
    ids = contract_ids(task, task["files"])
    extra = dict(api_id="clip.cap_high",
                 bindings=["field.vals", "elem.vals", "field.hi"])
    checked = validate_id_bindings(extra, ids)
    assembled = assemble_validated_id(extra, ids, task["contract"])
    assert checked["ok"] is False
    assert assembled["source"] == ""
    assert assembled["executable"] is False
    glue = api_id_tasks()[1]
    gold = apply_id_proposal(glue, glue["gold_selection"])
    assert gold["assembled"]["ok"] is True
    assert run_cases(gold["files"], glue["private"])["status"] == "passed"


def test_verdict_tool_tie_and_beyond():
    base = dict(correct_solutions=3, correct_clarification_or_refusal=2,
                harmful_changes=0)
    summary = {
        "scratch": dict(base, correct_solutions=2),
        "inclusive_tool": dict(base),
        "acquired": dict(base),
        "acquired_reset": dict(base, correct_solutions=2),
        "irrelevant_memory": dict(base, correct_solutions=1),
        "exact_cache": dict(base, correct_solutions=1),
    }
    assert verdict(summary) == "tool_tie"
    summary["acquired"] = dict(base, correct_solutions=4)
    assert verdict(summary) == "useful_acquired_beyond_tool"
    summary["acquired"] = dict(base, harmful_changes=1)
    assert verdict(summary) == "negative"
