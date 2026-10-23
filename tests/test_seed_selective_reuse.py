"""Development checks for selective reuse and structured edits."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.local_model_patch_proposer import (
    looks_complete_source, prefer_symbol_targeted_edit, public_prompt, validate_patch,
)
from nexus.seed.repair_schema_memory import (
    RepairSchema, classify_boundary_requirement, propose_retrieved_repair,
)
from nexus.seed.selective_reuse import reuse_label, valid_edit_stats


ROOT = Path(__file__).resolve().parents[1]


def _schema():
    return RepairSchema(
        schema_id="cmp",
        family="comparison_boundary",
        trigger="Allow n equal to the maximum.",
        transformation="compare_op_swap",
        applicability={"from_op": "Lt", "to_op": "LtE", "require_unique_matching_compare": True},
        bindings={"from_op": "Lt", "to_op": "LtE"},
        preconditions={"require_unique_matching_compare": True},
    )


def test_config_predeclares_four_reuse_roles_and_fixed_policy():
    config = json.loads((ROOT / "configs/seed_selective_reuse.json").read_text())
    assert config["default_investigation_policy"] == "fixed_boundary"
    assert config["learned_policy_promoted"] is False
    roles = {row["id"]: row["reuse_role"] for row in config["transfer"]["later"]}
    assert roles == {
        "py_width_ok": "same_repair",
        "py_keep_exclusive": "opposite",
        "py_pair_label": "unrelated",
        "py_cutoff_ambiguous": "clarification",
    }
    assert config["expected_grid"]["transfer_cells"] == 12


def test_inclusive_and_exclusive_are_different_decisions():
    schema = _schema()
    files = {"w.py": "def ok(item):\n    return item['width'] < item['bound']\n"}
    inclusive = propose_retrieved_repair(
        schema, "Allow width equal to the bound.", files,
        [{"entry": "w.ok", "input": {"width": 6, "bound": 6}, "expected": True}],
    )
    exclusive = propose_retrieved_repair(
        schema, "Reject values equal to the cutoff; only strictly smaller values pass.",
        {"c.py": "def pass_(item):\n    return item['v'] < item['cut']\n"},
        [{"entry": "c.pass_", "input": {"v": 5, "cut": 5}, "expected": False}],
    )
    assert inclusive.decision == "apply"
    assert exclusive.decision == "refuse"
    assert inclusive.requirement != exclusive.requirement
    assert inclusive.files is not None and "<=" in inclusive.files["w.py"]
    assert exclusive.files is None


def test_ambiguous_requirement_asks_and_ignores_private_tests():
    schema = _schema()
    files = {"a.py": "def keep(item):\n    return item['n'] < item['max']\n"}
    public = [{"entry": "a.keep", "input": {"n": 2, "max": 5}, "expected": True}]
    private = [{"entry": "a.keep", "input": {"n": 5, "max": 5}, "expected": True}]
    assert classify_boundary_requirement("Fix the cutoff check.", public, private) == "ambiguous"
    proposal = propose_retrieved_repair(
        schema, "Fix the cutoff check.", files, public, private_tests=private,
    )
    assert proposal.decision == "ask"
    assert proposal.files is None
    assert proposal.used_private_tests is False
    assert "inclusive" in (proposal.question or "")


def test_unrelated_family_abstains():
    schema = _schema()
    proposal = propose_retrieved_repair(
        schema, "Create function pair(a, b) that joins the two strings with a colon.",
        {"lab.py": "def echo(text):\n    return text\n"},
        [{"entry": "lab.pair", "input": ["x", "y"], "unpack_args": True, "expected": "x:y"}],
    )
    assert proposal.decision == "abstain"
    assert proposal.reason == "family_mismatch"


def test_reuse_labels_and_separate_valid_edit_rate():
    assert reuse_label("same_repair", "apply", True, True) == "correct_reuse"
    assert reuse_label("same_repair", "abstain", False, None) == "unnecessary_abstention"
    assert reuse_label("opposite", "apply", True, False) == "harmful_reuse"
    assert reuse_label("clarification", "ask", False, None) == "correct_hold"
    stats = valid_edit_stats([
        {"status": "invalid_proposal"},
        {"status": "proposed"},
        {"status": "BLOCKED"},
    ])
    assert stats["proposals"] == 2
    assert stats["structurally_valid"] == 1
    assert stats["valid_edit_rate"] == 0.5
    assert stats["functional_correctness_separate"] is True


def test_symbol_rewrite_and_incomplete_snippet_rejected():
    files = {"levy.py": "def apply_levy(amount, rate):\n    return amount\n"}
    rewritten = prefer_symbol_targeted_edit({
        "path": "levy.py", "action": "replace",
        "old_text": "amount",
        "new_text": "def apply_levy(amount, rate):\n    return amount + rate\n",
    }, files)
    assert rewritten["old_text"].count("amount") >= 1
    assert files["levy.py"].count(rewritten["old_text"]) == 1
    validated = validate_patch({"edits": [{
        "path": "text.py", "action": "replace",
        "old_text": "echo",
        "new_text": "def slug(left, right):\n    return left.lower() + '-' + right.lower()\n",
    }]}, {"text.py": "def echo(text):\n    return text\n"})
    assert validated["edits"][0]["action"] == "insert_function"
    assert "def slug" in validated["edits"][0]["new_text"]
    try:
        validate_patch({"edits": [{
            "path": "levy.py", "action": "replace",
            "old_text": "amount",
            "new_text": "amount + rate",
        }]}, files)
        raise AssertionError("snippet accepted")
    except ValueError as exc:
        assert "old_text_not_unique" in str(exc)
    assert looks_complete_source(
        "def other(x):\n    return x\n", "levy.py", files["levy.py"],
    ) is False


def test_revision_prompt_includes_staged_source_and_validation_error():
    task = type("T", (), {
        "files": {"levy.py": "def apply_levy(amount, rate):\n    return amount\n"},
        "request": "Add the levy.",
        "public_tests": [],
        "docs": [],
        "language": "python",
    })()
    prompt = public_prompt(
        task, {"symbols": ["apply_levy"]}, {},
        {"validation_error": "ValueError: old_text_not_unique:levy.py"},
    )
    assert "old_text_not_unique:levy.py" in prompt
    assert "def apply_levy" in prompt
    assert "insert_function" in prompt
