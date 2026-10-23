"""Development checks for input contract, two-stage slots, and wired discovery."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.constrained_edit import plan_constrained_edit
from nexus.seed.contract_revision_study import CLOSED_TASK_IDS
from nexus.seed.input_contract import (
    MAX_COMPLETIONS, build_user_prompt, choose_best_variant, describe_input_contract,
    uses_dict_fields,
)
from nexus.seed.public_failure import behavioral_feedback, operator_hint_present
from nexus.seed.target_discovery import discover_edit_target, plan_from_discovery, score_discovery


ROOT = Path(__file__).resolve().parents[1]


def test_config_fresh_ids_and_e2e_includes_non_string_tasks():
    config = json.loads((ROOT / "configs/seed_contract_two_stage.json").read_text())
    assert not {row["id"] for row in config["tasks"]} & CLOSED_TASK_IDS
    assert config["learning_research_resumed"] is False
    assert config["target_discovery"] == "wired_on_e2e_only"
    families = {row["family"] for row in config["tasks"] if row["phase"] == "e2e"}
    assert "count_nonempty" in families
    assert "numeric_clamp" in families


def test_contract_adds_signature_and_keeps_existing_request():
    files = {"note.py": "def echo(text):\n    return text\n"}
    request = "Create function title(item) that lowercases text."
    public = [{"entry": "note.title", "input": {"text": "Hello World"}, "expected": "hello_world"}]
    plan = plan_constrained_edit(request, files, public)
    task = type("T", (), {"files": files, "request": request, "public_tests": public, "docs": []})()
    existing = build_user_prompt("existing", task, plan)
    contract = build_user_prompt("contract", task, plan)
    block = describe_input_contract(plan, public)
    assert "Signature: def title(item)" in block
    assert 'item: {"text": str}' in block
    assert "Hello World" in block
    assert block in contract
    assert "Signature: def " not in existing
    assert request in existing and request in contract
    assert existing in contract
    assert MAX_COMPLETIONS == 3


def test_behavioral_feedback_lists_cases_and_three_point_without_operator():
    public = {
        "results": [
            {"actual": True, "expected": True, "passed": True, "error": None},
            {"actual": False, "expected": True, "passed": False, "error": None},
            {"actual": False, "expected": False, "passed": True, "error": None},
        ]
    }
    tests = [
        {"input": {"mass": 1, "limit": 2}, "expected": True},
        {"input": {"mass": 2, "limit": 2}, "expected": True},
        {"input": {"mass": 3, "limit": 2}, "expected": False},
    ]
    feedback = behavioral_feedback(public, tests)
    assert feedback["three_point_evidence"] is True
    assert feedback["bands_present"] == ["above", "below", "equal"]
    failed = feedback["failed_cases"]
    assert failed[0]["input"] == {"mass": 2, "limit": 2}
    assert failed[0]["expected"] is True
    assert failed[0]["actual"] is False
    assert failed[0]["exception"] is None
    assert feedback["operator_supplied"] is False
    assert operator_hint_present(feedback["instruction"]) is False
    crashed = behavioral_feedback(
        {"results": [{"actual": None, "expected": "a", "passed": False, "error": "TypeError: x"}]},
        [{"input": {"text": "Hi"}, "expected": "hi"}],
    )
    assert crashed["failed_cases"][0]["exception"] == "TypeError: x"
    assert crashed["failed_cases"][0]["actual"] is None


def test_format_slot_does_not_block_behavior_budget():
    assert MAX_COMPLETIONS >= 1 + 1 + 1


def test_wired_discovery_ignores_decoy_entry():
    files = {
        "alpha.py": "def keep(item):\n    return item['n'] < item['cap']\n",
        "beta.py": "def hold(item):\n    return item['n'] < item['cap']\n",
    }
    discovered = discover_edit_target("Allow hold equal to the cap.", files)
    gold = {"path": "beta.py", "symbol": "hold", "action": "replace_function"}
    assert score_discovery(discovered, gold)["target_correct"] is True
    plan = plan_from_discovery(discovered)
    assert plan is not None
    assert plan.path == "beta.py" and plan.symbol == "hold"
    assert uses_dict_fields("def title(item):\n    return item['text'].lower()\n", ["text"])
    assert not uses_dict_fields("def title(item):\n    return item.lower()\n", ["text"])


def test_best_variant_prefers_contract_on_a_tie():
    rows = [
        dict(prompt_variant="existing", syntax_valid=True, placeholder=None, executed=True,
             public_passed=False, semantic_correct=False),
        dict(prompt_variant="contract", syntax_valid=True, placeholder=None, executed=True,
             public_passed=False, semantic_correct=False),
    ]
    assert choose_best_variant(rows) == "contract"
