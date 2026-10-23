"""Development checks for constrained replace/insert and source-backed chat."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.constrained_edit import (
    assemble_constrained_proposal, catalogue_cannot_complete, plan_constrained_edit,
)
from nexus.seed.conversation_capability import send, write_files
from nexus.seed.lab import SeedWorkspace


ROOT = Path(__file__).resolve().parents[1]


def test_config_pauses_learning_and_uses_fresh_ids():
    config = json.loads((ROOT / "configs/seed_constrained_edit_workflow.json").read_text())
    assert config["learned_ranking_promoted"] is False
    assert config["learning_research_resumed"] is False
    from nexus.seed.constrained_workflow import CLOSED_TASK_IDS
    assert config["semantic"]["id"] not in CLOSED_TASK_IDS
    assert config["feature"]["id"] not in CLOSED_TASK_IDS
    assert len(config["semantic"]["public"]) == 3
    assert config["feature"]["family"] == "formatted_identifier"


def test_nexus_supplies_path_and_symbol_for_replace_and_insert():
    replace = plan_constrained_edit(
        "Allow depth equal to the max.",
        {"depth.py": "def ok(item):\n    return item['depth'] < item['max']\n"},
        [{"entry": "depth.ok", "input": {"depth": 2, "max": 2}, "expected": True}],
    )
    assert replace.action == "replace_function"
    assert replace.path == "depth.py"
    assert replace.symbol == "ok"
    insert = plan_constrained_edit(
        "Create function tag(item) that joins kind and name.",
        {"echo.py": "def echo(text):\n    return text\n"},
        [{"entry": "echo.tag", "input": {"kind": "A", "name": "B"}, "expected": "a:b"}],
    )
    assert insert.action == "insert_function"
    assert insert.path == "echo.py"
    assert insert.symbol == "tag"


def test_wrong_path_and_insert_on_existing_symbol_are_not_model_choices():
    files = {"height.py": "def ok(item):\n    return item['height'] < item['cap']\n"}
    assembled = assemble_constrained_proposal(
        '{"function": "def keep(item):\\n    return item[\'height\'] <= item[\'cap\']\\n"}',
        "Allow height equal to the cap.",
        files,
        [{"entry": "height.ok", "input": {"height": 2, "cap": 2}, "expected": True}],
    )
    assert assembled["plan"]["path"] == "height.py"
    assert assembled["plan"]["symbol"] == "ok"
    assert assembled["plan"]["action"] == "replace_function"
    assert assembled["raw_valid"] is True
    assert "renamed_definition" in assembled["normalized"]
    assert assembled["structurally_valid"] is True
    assert "def ok(" in assembled["patched_files"]["height.py"]
    assert "<=" in assembled["patched_files"]["height.py"]


def test_catalogue_cannot_complete_formatted_identifier():
    config = json.loads((ROOT / "configs/seed_constrained_edit_workflow.json").read_text())
    check = catalogue_cannot_complete(config["feature"])
    assert check["cannot_complete"] is True
    assert check["candidate_count"] >= 1
    assert check["passing_operators"] == []


def test_conversation_contents_operation_and_return(tmp_path):
    paths = write_files(tmp_path, [
        {"id": "notes", "key": "region", "value": "amount", "rows": [["east", 4]]},
        {"id": "fees", "key": "region", "value": "amount", "rows": [["north", 1], ["south", 3]]},
    ])
    ws = SeedWorkspace(tmp_path / "chat", attach_local_runtime=False)
    sid = ws.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]
    send(ws, sid, f'Use file "{paths["fees"]}".')
    send(ws, sid, f'Summarize totals grouped by region for "{paths["fees"]}".')
    contents = send(ws, sid, "What does the selected file contain? Name the regions and amounts.")
    assert "Source file:" in contents["text"]
    assert "north" in contents["text"] and "south" in contents["text"]
    assert "1" in contents["text"] and "3" in contents["text"]
    changed = send(ws, sid, "List the individual rows instead.")
    assert changed["chat"]["context"]["workspace"]["last_intent"]["op"] == "rows"
    send(ws, sid, "What file is selected?")
    returned = send(ws, sid, f'Go back to the file "{paths["fees"]}" and summarize totals grouped by region.')
    assert returned["chat"]["context"]["workspace"]["last_intent"]["op"] == "sum"
    assert "fees" in str(returned["chat"]["context"]["workspace"]["selected_file"])
