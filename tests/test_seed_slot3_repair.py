"""Offline slot-3 structural repair: placeholder / unbound name, 0 model calls."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

from nexus.seed.capability_evidence import EventMeter
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.contract_revision_study import propose_cell
from nexus.seed.function_format import prompt_for_format
from nexus.seed.structural_revision import (
    JSON_BODY_ASK,
    slot3_revision_prompt,
    structural_reject_reason,
)
from nexus.seed.sum_row_repair import compact_revision_prompt


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "artifacts/seed_harder_features/seed_harder_features.json"
PLAN = type("P", (), {"symbol": "tag", "args": "item", "action": "insert_function"})()
JOB_SPEC = {
    "id": "py_job_slash_mock",
    "role": "insert",
    "family": "missing_fields",
    "domain": "python_repo",
    "language": "python",
    "requirement": "tag(item) is job and unit lowercased, joined by one slash. Missing job or unit is an empty string.",
    "request": "Create function tag(item) that returns job and unit in lowercase joined by one slash. A missing job or unit is an empty string.",
    "docs": [{"title": "tag", "content": "tag(item) is job/unit lowercased. Missing fields are empty strings."}],
    "files": {"job.py": "def echo(text):\n    return text\n"},
    "gold_target": {"path": "job.py", "symbol": "tag", "action": "insert_function"},
    "public": [
        {"entry": "job.tag", "input": {"job": "Lab", "unit": "East"}, "expected": "lab/east"},
        {"entry": "job.tag", "input": {"unit": "East"}, "expected": "/east"},
        {"entry": "job.tag", "input": {"job": "Lab"}, "expected": "lab/"},
    ],
    "assessment": [
        {"entry": "job.tag", "input": {"job": "Q", "unit": "w"}, "expected": "q/w"},
    ],
}
VALID_TAG = "return (item.get('job') or '').lower() + '/' + (item.get('unit') or '').lower()"
ATTR_FAIL = "return (item.get('job') or []).lower()"


class ScriptedRuntime:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, prompt, schema=None):
        self.prompts.append(prompt)
        content = self.replies.pop(0) if self.replies else ""
        return {"content": content, "telemetry": {"request_wall_s": 0.001}}


def _verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_seed_interface_repair_confirm",
        ROOT / "scripts/verify_seed_interface_repair_confirm.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _propose(replies, spec=JOB_SPEC):
    runtime = ScriptedRuntime(replies)
    records = []
    meter = EventMeter(records.append)
    result = propose_cell(
        runtime, spec, "contract", meter, "mock:" + spec["id"],
        wire_discovery=True, max_tokens=128, asked=False,
    )
    return result, records, runtime


def test_prompts_do_not_write_ellipsis_json_body():
    from nexus.seed.constrained_edit import plan_constrained_edit

    plan = plan_constrained_edit(JOB_SPEC["request"], JOB_SPEC["files"], JOB_SPEC["public"])
    task = type("T", (), {
        "files": JOB_SPEC["files"],
        "request": JOB_SPEC["request"],
        "public_tests": JOB_SPEC["public"],
        "docs": JOB_SPEC["docs"],
    })()
    text = prompt_for_format("json_body", task, plan, {})
    assert '{"body": "..."}' not in text
    assert "\"body\": \"...\"" not in text
    assert "ellipsis" in JSON_BODY_ASK
    revision = compact_revision_prompt(plan, ATTR_FAIL, {
        "instruction": "Public tests failed.",
        "failed_cases": [],
    })
    assert '{"body": "..."}' not in revision
    structural = slot3_revision_prompt(
        plan, ATTR_FAIL, {"instruction": "AttributeError on list.lower", "failed_cases": []},
        "...", "Previous revision was a placeholder; return complete Python statements that use parameter 'item'.",
    )
    assert '{"body": "..."}' not in structural


def test_placeholder_completion2_consumes_slot3():
    result, records, runtime = _propose([
        json.dumps({"body": ATTR_FAIL}),
        json.dumps({"body": "..."}),
        json.dumps({"body": VALID_TAG}),
    ])
    assert result["calls_charged"] == 3
    assert result["completions"] == 3
    assert result["behavioral_revision_attempted"] is True
    assert result["structural_slot3_attempted"] is True
    stages = [trace.get("stage") for trace in result["traces"]]
    assert stages == ["initial", "behavior", "structural"]
    completes = [
        row for row in records
        if row.get("kind") == "execution" and row.get("operation") == "complete"
    ]
    assert len(completes) == 3
    assert [row["identity"] for row in completes] == [
        JOB_SPEC["id"] + ":0",
        JOB_SPEC["id"] + ":behavior",
        JOB_SPEC["id"] + ":structural",
    ]
    third = result["traces"][2]
    assert '{"body": "..."}' not in (third.get("user_prompt") or "")
    assert result["public_passed"] is True
    assert len(runtime.prompts) == 3


def test_unbound_lead_keeps_behavior_feedback_and_structural_reason():
    result, records, runtime = _propose([
        json.dumps({"body": ATTR_FAIL}),
        json.dumps({"body": "-lead"}),
        json.dumps({"body": VALID_TAG}),
    ])
    assert result["structural_slot3_attempted"] is True
    assert result["calls_charged"] == 3
    reason = result["traces"][2].get("structural_reason") or result.get("structural_reason")
    assert reason
    assert "item" in reason
    assert "lead" in reason or "did not reference" in reason
    prompt = result["traces"][2]["user_prompt"]
    assert "AttributeError" in prompt
    assert "Structural rejection" in prompt
    assert ATTR_FAIL.replace(" ", "") in prompt.replace(" ", "") or "First body" in prompt
    assert "-lead" in prompt or "Second body" in prompt
    assert '{"body": "..."}' not in prompt
    completes = [
        row for row in records
        if row.get("kind") == "execution" and row.get("operation") == "complete"
    ]
    assert [row["identity"] for row in completes] == [
        JOB_SPEC["id"] + ":0",
        JOB_SPEC["id"] + ":behavior",
        JOB_SPEC["id"] + ":structural",
    ]
    assert len(runtime.prompts) == 3


def test_structural_reject_reasons_are_non_solution():
    placeholder = {
        "placeholder": "placeholder_body:ellipsis",
        "raw_reason": "placeholder_after_unwrap",
        "syntax_valid": False,
        "preview": {"new_excerpt": "..."},
    }
    reason = structural_reject_reason(placeholder, PLAN)
    assert "placeholder" in reason
    assert "sum(" not in reason
    assert "get(" not in reason
    lead = {
        "placeholder": None,
        "raw_reason": None,
        "syntax_valid": True,
        "preview": {"new_excerpt": "return -lead"},
        "patched_files": {"job.py": "def tag(item):\n    return -lead\n"},
    }
    reason = structural_reject_reason(lead, PLAN)
    assert "lead" in reason
    assert "item" in reason
    constant = {
        "placeholder": None,
        "raw_reason": None,
        "syntax_valid": True,
        "preview": {"new_excerpt": "return 0"},
        "patched_files": {"job.py": "def tag(item):\n    return 0\n"},
    }
    reason = structural_reject_reason(constant, PLAN)
    assert "did not reference 'item'" in reason


def _slot3_mock_payload():
    from nexus.seed.slot3_repair_study import (
        CLOSED_TASK_IDS, HISTORICAL_HARDER_SHA256, WORKER_PROMPT_FREEZE,
        begin, public_covers_varied, record_model, summarize,
    )

    config = json.loads((ROOT / "configs/seed_slot3_repair_confirm.json").read_text())
    spec = copy.deepcopy(JOB_SPEC)
    spec["id"] = "py_slot3_chain"
    config = dict(config)
    config["tasks"] = [spec]
    config["expected_grid"] = dict(config["expected_grid"], confirm_cells=1)
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    records = []
    meter = begin(config, records.append, historical["records"])
    runtime = ScriptedRuntime([
        json.dumps({"body": ATTR_FAIL}),
        json.dumps({"body": "..."}),
        json.dumps({"body": VALID_TAG}),
    ])
    record_model(config, records.append, meter, runtime)
    summary = summarize(records, config)
    payload = dict(
        study_id="seed-slot3-repair-confirm-1",
        scientific=False,
        kind="source_development_evaluation_not_confirmation",
        blocked_step=None,
        historical_fingerprints=historical_artifact_fingerprints(ROOT),
        historical_harder_sha256=HISTORICAL_HARDER_SHA256,
        historical_supplied_private_correct=1,
        records=records,
        summary=summary,
        learning_to_learn=False,
        agi=False,
        gemini="NOT_RUN",
    )
    extras = dict(
        closed=CLOSED_TASK_IDS,
        freeze=WORKER_PROMPT_FREEZE,
        cover=public_covers_varied,
        summarize_fn=summarize,
    )
    return payload, config, extras


def test_verifier_reconstructs_three_completion_chain_and_rejects_tamper():
    from nexus.seed.interface_repair_study import replay_final

    verify_mod = _verifier()
    payload, config, extras = _slot3_mock_payload()
    extras["replay_fn"] = replay_final
    out = verify_mod.verify(payload, config, **extras)
    assert out["valid"] is True
    confirm = [row for row in payload["records"] if row.get("category") == "confirm"]
    assert confirm[0]["calls_charged"] == 3
    completes = [
        row for row in payload["records"]
        if row.get("kind") == "execution" and row.get("operation") == "complete"
    ]
    assert len(completes) == 3
    tampered = copy.deepcopy(payload)
    tampered["records"] = copy.deepcopy(payload["records"])
    row = next(item for item in tampered["records"] if item.get("category") == "confirm")
    row["semantic_correct"] = not bool(row.get("semantic_correct"))
    try:
        verify_mod.verify(tampered, config, **extras)
        raised = False
    except ValueError as exc:
        raised = True
        assert "replay" in str(exc) or "flag" in str(exc) or "mismatch" in str(exc)
    assert raised is True
    fingerprints = copy.deepcopy(payload)
    fingerprints["historical_fingerprints"] = dict(payload["historical_fingerprints"] or {})
    fingerprints["historical_fingerprints"]["artifacts/seed_capability_audit.json"] = "0" * 64
    try:
        verify_mod.verify(fingerprints, config, **extras)
        fp_raised = False
    except ValueError as exc:
        fp_raised = True
        assert "historical" in str(exc)
    assert fp_raised is True


def test_fresh_ids_closed_against_prior_families():
    from nexus.seed.interface_repair_study import CLOSED_TASK_IDS as IFACE_CLOSED
    from nexus.seed.slot3_repair_study import CLOSED_TASK_IDS, public_covers_varied

    config = json.loads((ROOT / "configs/seed_slot3_repair_confirm.json").read_text())
    ids = {row["id"] for row in config["tasks"]}
    assert not ids & CLOSED_TASK_IDS
    assert "py_bin_tally" in CLOSED_TASK_IDS
    assert "py_role_dash" in CLOSED_TASK_IDS
    assert ids == {"py_lot_count", "py_job_slash", "py_part_div", "py_ok_pair"}
    assert ids.isdisjoint(IFACE_CLOSED)
    for spec in config["tasks"]:
        assert public_covers_varied(spec)
    assert config["carried_used_s"] == 3314.967351455996
    assert config["hard_deadline_s"] == 150
