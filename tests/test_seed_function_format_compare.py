"""Development checks for function formats and placeholder rejection."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.function_format import (
    assemble_format_proposal, choose_best_format, placeholder_diagnostic,
    prompt_for_format, schema_for_format,
)
from nexus.seed.constrained_edit import plan_constrained_edit


ROOT = Path(__file__).resolve().parents[1]


def test_config_uses_fresh_ids_and_installed_coder():
    config = json.loads((ROOT / "configs/seed_function_format_compare.json").read_text())
    from nexus.seed.function_format_study import CLOSED_TASK_IDS
    assert not {row["id"] for row in config["tasks"]} & CLOSED_TASK_IDS
    assert config["learning_research_resumed"] is False
    assert config["models"]["coder15"]["sha256"].startswith("cc324af0")
    assert config["target_discovery"] == "not_implemented"


def test_prompts_require_executable_python_and_share_task_facts():
    files = {"level.py": "def ok(item):\n    return item['level'] < item['cap']\n"}
    request = "Allow level equal to the cap."
    public = [{"entry": "level.ok", "input": {"level": 2, "cap": 2}, "expected": True}]
    plan = plan_constrained_edit(request, files, public)
    task = type("T", (), {"files": files, "request": request, "public_tests": public, "docs": []})()
    plain = prompt_for_format("plain_code", task, plan)
    js = prompt_for_format("json_function", task, plan)
    body = prompt_for_format("json_body", task, plan)
    for text in (plain, js, body):
        assert "executable Python" in text
        assert "Allow level equal to the cap." in text
        assert "level.py" in text
        assert plan.source_sha256 in text
    assert "Do not return JSON" in plain
    assert schema_for_format("plain_code") is None
    assert schema_for_format("json_function")["required"] == ["function"]
    assert schema_for_format("json_body")["required"] == ["body"]


def test_placeholder_rejects_identifier_and_allows_return_none():
    assert placeholder_diagnostic("def ok(item):\n    ok\n", "ok") == "placeholder_body:bare_identifier:ok"
    assert placeholder_diagnostic("def ok(item):\n    pass\n", "ok") == "placeholder_body:pass"
    assert placeholder_diagnostic("def ok(item):\n    return None\n", "ok") is None
    assert placeholder_diagnostic("def ok(item):\n    return item['level'] <= item['cap']\n", "ok") is None
    assembled = assemble_format_proposal(
        "json_function",
        '{"function": "ok"}',
        "Allow level equal to the cap.",
        {"level.py": "def ok(item):\n    return item['level'] < item['cap']\n"},
        [{"entry": "level.ok", "input": {"level": 2, "cap": 2}, "expected": True}],
    )
    assert assembled["placeholder"] == "placeholder_body:bare_identifier:ok"
    assert assembled["structurally_valid"] is False
    broken = assemble_format_proposal(
        "json_body",
        '{"body": "ok(item)."}',
        "Allow level equal to the cap.",
        {"level.py": "def ok(item):\n    return item['level'] < item['cap']\n"},
        [{"entry": "level.ok", "input": {"level": 2, "cap": 2}, "expected": True}],
    )
    assert broken["structurally_valid"] is False
    assert broken["syntax_valid"] is False


def test_best_format_uses_predeclared_tie_break():
    rows = [
        dict(format="plain_code", syntax_valid=True, placeholder=None, executed=True,
             public_passed=False, semantic_correct=False),
        dict(format="json_function", syntax_valid=True, placeholder=None, executed=True,
             public_passed=False, semantic_correct=False),
        dict(format="json_body", syntax_valid=False, placeholder="placeholder_body:empty",
             executed=False, public_passed=False, semantic_correct=False),
    ]
    assert choose_best_format(rows) == "json_function"
