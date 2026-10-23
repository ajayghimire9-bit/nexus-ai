"""Offline slot-3 duplicate-AST / KeyError subscript checks. 0 model calls."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

from nexus.seed.capability_evidence import EventMeter
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.contract_revision_study import propose_cell
from nexus.seed.structural_revision import (
    DUPLICATE_AST_REASON,
    UNCHANGED_SUBSCRIPT_REASON,
    structural_reject_detail,
)


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "artifacts/seed_harder_features/seed_harder_features.json"
PLAN = type("P", (), {"symbol": "tag", "args": "item", "action": "insert_function"})()
BARE = "return item['job'].lower() + '/' + item['unit'].lower()"
SAFE = "return (item.get('job') or '').lower() + '/' + (item.get('unit') or '').lower()"
TAG_SPEC = {
    "id": "py_post_slash_mock",
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
        {"entry": "job.tag", "input": {"unit": "West"}, "expected": "/west"},
        {"entry": "job.tag", "input": {"job": "Mix"}, "expected": "mix/"},
        {"entry": "job.tag", "input": {"job": "Q", "unit": "w"}, "expected": "q/w"},
    ],
}


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


def test_duplicate_keyerror_copy_consumes_slot3():
    runtime = ScriptedRuntime([
        json.dumps({"body": BARE}),
        json.dumps({"body": BARE}),
        json.dumps({"body": SAFE}),
    ])
    records = []
    result = propose_cell(
        runtime, TAG_SPEC, "contract", EventMeter(records.append),
        "mock:" + TAG_SPEC["id"], wire_discovery=True, max_tokens=128, asked=False,
    )
    assert result["calls_charged"] == 3
    assert result["structural_slot3_attempted"] is True
    codes = set(result.get("structural_codes") or [])
    assert "duplicate_ast" in codes
    assert "unchanged_subscript_on_keyerror" in codes
    prompt = result["traces"][2]["user_prompt"]
    assert DUPLICATE_AST_REASON in prompt
    assert UNCHANGED_SUBSCRIPT_REASON in prompt
    assert "KeyError" in prompt
    assert "get('job')" not in DUPLICATE_AST_REASON
    assert "get('job')" not in UNCHANGED_SUBSCRIPT_REASON
    completes = [
        row for row in records
        if row.get("kind") == "execution" and row.get("operation") == "complete"
    ]
    assert [row["identity"] for row in completes] == [
        TAG_SPEC["id"] + ":0",
        TAG_SPEC["id"] + ":behavior",
        TAG_SPEC["id"] + ":structural",
    ]
    assert result["public_passed"] is True
    assert result["semantic_correct"] is True


def test_structural_detail_codes_for_copy_and_get():
    public = {
        "all_passed": False,
        "results": [
            {"passed": False, "error": "KeyError:'job'"},
            {"passed": False, "error": "KeyError:'unit'"},
        ],
    }
    copy_row = {
        "placeholder": None,
        "raw_reason": None,
        "syntax_valid": True,
        "preview": {"new_excerpt": BARE},
        "patched_files": {"job.py": "def tag(item):\n    " + BARE + "\n"},
    }
    detail = structural_reject_detail(copy_row, PLAN, prior_body=BARE, public=public)
    assert detail is not None
    assert "duplicate_ast" in detail["codes"]
    assert "unchanged_subscript_on_keyerror" in detail["codes"]
    safe = dict(copy_row, preview={"new_excerpt": SAFE})
    after = structural_reject_detail(safe, PLAN, prior_body=BARE, public=public)
    assert after is None


def test_fresh_ids_and_private_missing_key_parity():
    from nexus.seed.slot3_copy_study import (
        CLOSED_TASK_IDS, covers_varied, private_covers_missing_keys,
    )
    from nexus.seed.slot3_repair_study import CLOSED_TASK_IDS as SLOT3_CLOSED

    config = json.loads((ROOT / "configs/seed_slot3_copy_confirm.json").read_text())
    ids = {row["id"] for row in config["tasks"]}
    assert not ids & CLOSED_TASK_IDS
    assert "py_job_slash" in CLOSED_TASK_IDS
    assert "py_lot_count" in CLOSED_TASK_IDS
    assert ids == {"py_crate_tally", "py_post_slash", "py_ratio_div", "py_clear_pair"}
    assert ids.isdisjoint(SLOT3_CLOSED)
    for spec in config["tasks"]:
        assert covers_varied(spec)
    tag = next(row for row in config["tasks"] if row["id"] == "py_post_slash")
    assert private_covers_missing_keys(tag)
    public_inputs = [case["input"] for case in tag["public"]]
    private_inputs = [case["input"] for case in tag["assessment"]]
    assert all(inp not in public_inputs for inp in private_inputs)
    assert any("post" not in inp for inp in private_inputs)
    assert any("desk" not in inp for inp in private_inputs)
    unguarded = {
        "post.py": (
            "def tag(item):\n"
            "    return item['post'].lower() + '/' + item['desk'].lower()\n"
        )
    }
    from nexus.seed.agent_loop_worker import evaluate_python_payload
    private = evaluate_python_payload({
        "language": "python", "files": unguarded, "cases": tag["assessment"],
    })
    assert private["all_passed"] is False
    assert config["hard_deadline_s"] == 70
    assert config["carried_used_s"] == 3379.081862455996


def test_verifier_reconstructs_three_completion_chain_and_parity():
    from nexus.seed.interface_repair_study import replay_final
    from nexus.seed.slot3_copy_study import (
        CLOSED_TASK_IDS, HISTORICAL_HARDER_SHA256, WORKER_PROMPT_FREEZE,
        begin, covers_varied, record_model, summarize,
    )

    verify_mod = _verifier()
    config = json.loads((ROOT / "configs/seed_slot3_copy_confirm.json").read_text())
    spec = copy.deepcopy(TAG_SPEC)
    spec["id"] = "py_slot3_copy_chain"
    config = dict(config)
    config["tasks"] = [spec]
    config["expected_grid"] = dict(config["expected_grid"], confirm_cells=1)
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    records = []
    meter = begin(config, records.append, historical["records"])
    runtime = ScriptedRuntime([
        json.dumps({"body": BARE}),
        json.dumps({"body": BARE}),
        json.dumps({"body": SAFE}),
    ])
    record_model(config, records.append, meter, runtime)
    payload = dict(
        study_id="seed-slot3-copy-confirm-1",
        scientific=False,
        kind="source_development_evaluation_not_confirmation",
        blocked_step=None,
        historical_fingerprints=historical_artifact_fingerprints(ROOT),
        historical_harder_sha256=HISTORICAL_HARDER_SHA256,
        historical_supplied_private_correct=1,
        records=records,
        summary=summarize(records, config),
        learning_to_learn=False,
        agi=False,
        gemini="NOT_RUN",
    )
    extras = dict(
        closed=CLOSED_TASK_IDS,
        freeze=WORKER_PROMPT_FREEZE,
        cover=covers_varied,
        summarize_fn=summarize,
        replay_fn=replay_final,
    )
    out = verify_mod.verify(payload, config, **extras)
    assert out["valid"] is True
    confirm = next(row for row in records if row.get("category") == "confirm")
    assert confirm["calls_charged"] == 3
    assert confirm["public_passed"] is True
    assert confirm["semantic_correct"] is True
    replayed = replay_final(confirm, spec)
    assert replayed["public_all_passed"] is True
    assert replayed["private_all_passed"] is True
