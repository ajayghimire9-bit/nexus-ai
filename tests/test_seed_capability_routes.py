"""Offline checks for the route study. No live model."""
import json
from pathlib import Path

from nexus.seed.capability_routes import apply_id_proposal, score_id_cell, summarize
from nexus.seed.capability_routes_tasks import (
    CLOSED, all_live_tasks, api_id_tasks, coordinated_tasks, knowledge_tasks,
    mathematics_tasks, provenance_corpus,
)
from nexus.seed.coordinated_stage import publish_ready
from nexus.seed.knowledge_provenance import UNRESOLVED_CONFLICT, provenance_resolve, timestamp_sort
from nexus.seed.math_interpretation import parse_statement, score_interpreted, validate_statement
from nexus.seed.recovery_actions import run_cases


def test_fresh_ids_and_closed_unused():
    rows = all_live_tasks()
    assert len(rows) == 8
    assert not {row["task_id"] for row in rows} & CLOSED
    config = json.loads(Path("configs/seed_capability_routes.json").read_text())
    assert config["api_selection_generally_solved"] is False
    assert config["original_map_rescored"] is False
    assert config["followup_rescored"] is False


def test_provenance_missing_authority_and_ambiguous_supersession():
    rows = provenance_corpus()
    missing = provenance_resolve(rows, "quay_hours")
    assert missing["outcome"] == UNRESOLVED_CONFLICT
    assert missing["selected"] == []
    assert "quay-note-a" in missing["conflict_ids"]
    naive = timestamp_sort(rows, "quay_hours")
    assert naive["selected"] == ["quay-note-b"]
    authority = provenance_resolve(rows, "tide_gauge")
    assert authority["outcome"] == UNRESOLVED_CONFLICT
    assert set(authority["conflict_ids"]) == {"tide-auth-east", "tide-auth-west"}
    ambiguous = provenance_resolve(rows, "berth_color")
    assert ambiguous["outcome"] == UNRESOLVED_CONFLICT
    assert "sheet-old" in ambiguous["dropped"]
    assert set(ambiguous["conflict_ids"]) == {"sheet-blue", "sheet-red"}
    clear = provenance_resolve(rows, "crane_limit")
    assert clear["outcome"] == "selected"
    assert clear["selected"] == ["crane-v3"]
    assert clear["used_ingestion_timestamp_as_freshness"] is False
    assert {row["task_id"] for row in knowledge_tasks()} == {
        "know_rt_missing_meta", "know_rt_dual_authority",
        "know_rt_ambiguous_super", "know_rt_clear_update",
    }


def test_math_unknown_only_when_needed_and_split_scores():
    units = mathematics_tasks()[0]
    algebra = mathematics_tasks()[2]
    assert units["has_unknown"] is False
    assert algebra["has_unknown"] is True
    unit_stmt = parse_statement(
        '{"quantities":[{"name":"mass","value":4.5,"unit":"kg"}],'
        '"relationships":["kg to g"],"unknown":"","unit":"g","missing":[],'
        '"expression":"4.5 * 1000"}'
    )
    assert validate_statement(unit_stmt, units)["ok"] is True
    assert validate_statement(unit_stmt, algebra)["errors"] == ["no_unknown"]
    scored = score_interpreted(units, unit_stmt, dict(
        ok=True, value=4500.0, expression_represents_problem=True,
    ), "")
    assert scored["interpretation_ok"] is True
    assert scored["execution_ok"] is True
    assert scored["answer_ok"] is True
    wrong = score_interpreted(units, unit_stmt, dict(
        ok=True, value=4.5, expression_represents_problem=True,
    ), "")
    assert wrong["execution_ok"] is True
    assert wrong["answer_ok"] is False
    assert wrong["passed"] is False


def test_valid_id_proposal_executes_and_bad_shape_is_rejected():
    task = api_id_tasks()[0]
    valid = apply_id_proposal(task, task["gold_selection"])
    assert valid["assembled"]["ok"] is True
    assert valid["assembled"]["programmer_supplied"] is True
    assert "from span import floor_cut" in valid["assembled"]["source"]
    replay = run_cases(valid["files"], task["private"])
    assert replay["status"] == "passed"
    scored = score_id_cell(task, task["gold_selection"], valid["files"], valid["assembled"])
    assert scored["selection_correct"] is True
    assert scored["bindings_correct"] is True
    assert scored["assembled_ok"] is True
    assert scored["private_passed"] is True
    swapped = apply_id_proposal(task, dict(api_id="span.floor_cut", bindings=["field.lo", "field.nums"]))
    assert swapped["assembled"]["ok"] is False
    assert swapped["assembled"]["error"] == "type_mismatch"
    bad_api = apply_id_proposal(task, dict(api_id="work.low_cut", bindings=["field.nums", "field.lo"]))
    assert bad_api["assembled"]["ok"] is False
    stitch = api_id_tasks()[1]
    gold = apply_id_proposal(stitch, stitch["gold_selection"])
    assert gold["assembled"]["ok"] is True
    assert run_cases(gold["files"], stitch["private"])["status"] == "passed"


def test_staged_pair_publishes_only_after_behavior_and_call():
    task = coordinated_tasks()[0]
    helper_only = {
        "util.py": "def over(value, floor):\n    return value > floor\n",
        "app.py": "def echo(text):\n    return text\n",
    }
    blocked = publish_ready(task, helper_only)
    assert blocked["ready"] is False
    assert blocked["helper_present"] is True
    assert blocked["caller_present"] is False
    complete = {
        "util.py": "def over(value, floor):\n    return value > floor\n",
        "app.py": (
            "from util import over\n"
            "def hold_ok(item):\n"
            "    loads = item['bin']['loads']\n"
            "    floor = item['bin']['floor']\n"
            "    return 'yes' if all(over(load, floor) for load in loads) else 'no'\n"
        ),
    }
    ready = publish_ready(task, complete)
    assert ready["ready"] is True
    assert ready["required_call"] is True
    assert ready["helper_behavior"] is True
    assert ready["caller_behavior"] is True
    inlined = {
        "util.py": "def over(value, floor):\n    return value > floor\n",
        "app.py": (
            "def hold_ok(item):\n"
            "    loads = item['bin']['loads']\n"
            "    floor = item['bin']['floor']\n"
            "    return 'yes' if all(load > floor for load in loads) else 'no'\n"
        ),
    }
    skipped = publish_ready(task, inlined)
    assert skipped["caller_behavior"] is True
    assert skipped["required_call"] is False
    assert skipped["ready"] is False


def test_summary_keeps_selection_separate():
    summary = summarize([
        dict(track="coding_api", method="id_select_assemble", scored=dict(
            passed=True, selection_correct=False, bindings_correct=True,
            assembled_ok=True, private_passed=True,
        )),
        dict(track="mathematics", method="routed", scored=dict(
            passed=False, interpretation_ok=True, execution_ok=True, answer_ok=False,
        )),
    ])
    assert summary["coding_api"]["id_select_assemble"]["separate"]["selection"] == 0
    assert summary["coding_api"]["id_select_assemble"]["separate"]["execution"] == 1
    assert summary["mathematics"]["routed"]["separate"]["interpretation"] == 1
    assert summary["mathematics"]["routed"]["separate"]["answer"] == 0
