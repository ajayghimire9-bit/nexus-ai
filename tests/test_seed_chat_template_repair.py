"""Development checks for ChatML, equality revision, and target discovery."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.chat_template import (
    apply_qwen25_chatml, choose_best_style, extract_chatml_user, gguf_has_chatml_tokens,
    gguf_metadata_string, render_prompt,
)
from nexus.seed.chat_template_study import CLOSED_TASK_IDS
from nexus.seed.function_format import prompt_for_format
from nexus.seed.constrained_edit import plan_constrained_edit
from nexus.seed.public_failure import EQUALITY_FAILURE, comparison_ops, operator_hint_present, public_revision_feedback
from nexus.seed.target_discovery import discover_edit_target, score_discovery


ROOT = Path(__file__).resolve().parents[1]


def test_config_uses_fresh_ids_and_separate_discovery():
    config = json.loads((ROOT / "configs/seed_chat_template_repair.json").read_text())
    assert not {row["id"] for row in config["tasks"]} & CLOSED_TASK_IDS
    assert config["learning_research_resumed"] is False
    assert config["target_discovery"] == "measured_separately_not_wired_to_assembler"
    assert config["models"]["coder15"]["sha256"].startswith("cc324af0")
    assert {row["phase"] for row in config["tasks"]} >= {"template", "fresh", "discovery"}


def test_chatml_user_equals_raw_and_adds_tokens():
    files = {"score.py": "def fit(item):\n    return item['score'] < item['limit']\n"}
    request = "Allow score equal to the limit."
    public = [{"entry": "score.fit", "input": {"score": 2, "limit": 2}, "expected": True}]
    plan = plan_constrained_edit(request, files, public)
    task = type("T", (), {"files": files, "request": request, "public_tests": public, "docs": []})()
    user = prompt_for_format("json_body", task, plan)
    raw, raw_meta = render_prompt("raw", user)
    chat, chat_meta = render_prompt("chatml", user)
    assert raw == user
    assert raw_meta["chat_template"] is None
    assert "<|im_start|>" not in raw
    assert chat.startswith("<|im_start|>system\n")
    assert chat_meta["user_equals_raw"] is True
    assert extract_chatml_user(chat) == user
    assert apply_qwen25_chatml(user) == chat
    assert "Alibaba Cloud" in chat


def test_equality_revision_names_failure_not_operator():
    public = {
        "results": [
            {"actual": True, "expected": True, "passed": True},
            {"actual": False, "expected": True, "passed": False},
            {"actual": False, "expected": False, "passed": True},
        ]
    }
    tests = [
        {"entry": "score.fit", "input": {"score": 1, "limit": 2}, "expected": True},
        {"entry": "score.fit", "input": {"score": 2, "limit": 2}, "expected": True},
        {"entry": "score.fit", "input": {"score": 3, "limit": 2}, "expected": False},
    ]
    feedback = public_revision_feedback(public, tests)
    assert feedback["concrete_failure"] == EQUALITY_FAILURE
    assert EQUALITY_FAILURE in feedback["instruction"]
    assert feedback["operator_supplied"] is False
    assert operator_hint_present(feedback["instruction"]) is False
    files = {"score.py": "def fit(item):\n    return item['score'] < item['limit']\n"}
    request = "Allow score equal to the limit."
    plan = plan_constrained_edit(request, files, tests)
    task = type("T", (), {"files": files, "request": request, "public_tests": tests, "docs": []})()
    revision = prompt_for_format("json_body", task, plan, feedback)
    assert EQUALITY_FAILURE in revision
    assert operator_hint_present(revision) is False
    assert comparison_ops("def fit(item):\n    return item['score'] < item['limit']\n") == ["Lt"]
    assert comparison_ops("def fit(item):\n    return item['score'] <= item['limit']\n") == ["LtE"]


def test_discovery_ignores_misleading_public_entry():
    files = {
        "alpha.py": "def keep(item):\n    return item['n'] < item['cap']\n",
        "beta.py": "def hold(item):\n    return item['n'] < item['cap']\n",
    }
    request = "Allow hold equal to the cap."
    discovered = discover_edit_target(request, files)
    gold = {"path": "beta.py", "symbol": "hold", "action": "replace_function"}
    scored = score_discovery(discovered, gold)
    assert discovered["used_public_tests"] is False
    assert scored["target_correct"] is True
    insert = discover_edit_target(
        "Create function mark(item) that returns the kind.",
        {"echo.py": "def echo(text):\n    return text\n"},
    )
    assert insert["action"] == "insert_function"
    assert insert["symbol"] == "mark"
    assert insert["used_public_tests"] is False


def test_installed_qwen_gguf_declares_chatml():
    config = json.loads((ROOT / "configs/seed_chat_template_repair.json").read_text())
    path = Path(config["models"]["qwen05"]["path"])
    if not path.is_file():
        return
    template = gguf_metadata_string(path) or ""
    assert gguf_has_chatml_tokens(path)
    assert "<|im_start|>" in template
    assert "You are Qwen, created by Alibaba Cloud" in template


def test_best_style_prefers_chatml_on_a_tie():
    rows = [
        dict(prompt_style="raw", syntax_valid=True, placeholder=None, executed=True,
             public_passed=False, semantic_correct=False),
        dict(prompt_style="chatml", syntax_valid=True, placeholder=None, executed=True,
             public_passed=False, semantic_correct=False),
    ]
    assert choose_best_style(rows) == "chatml"
