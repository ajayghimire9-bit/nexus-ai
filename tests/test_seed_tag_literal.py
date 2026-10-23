"""Offline item-anchor KeyError revision and constant-literal guard. 0 model calls."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

from nexus.seed.capability_evidence import EventMeter
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.contract_revision_study import propose_cell
from nexus.seed.diagnostic_revision import is_constant_string_literal
from nexus.seed.function_format import assemble_format_proposal


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "artifacts/seed_harder_features/seed_harder_features.json"
BARE = "return item['lane'].lower() + '/' + item['bay'].lower()"
SAFE = "return (item['lane'] if 'lane' in item else '').lower() + '/' + (item['bay'] if 'bay' in item else '').lower()"
C1_FSTR = "return f\"{item['lane'].lower()}/{item['bay'].lower()}\""
LANE_SPEC = {
    "id": "py_path_slash_mock",
    "role": "insert",
    "family": "missing_fields",
    "domain": "python_repo",
    "language": "python",
    "requirement": "tag(item) is lane and bay lowercased, joined by one slash. Missing lane or bay is an empty string.",
    "request": "Create function tag(item) that returns lane and bay in lowercase joined by one slash. A missing lane or bay is an empty string.",
    "docs": [{"title": "tag", "content": "tag(item) is lane/bay lowercased."}],
    "files": {"lane.py": "def echo(text):\n    return text\n"},
    "gold_target": {"path": "lane.py", "symbol": "tag", "action": "insert_function"},
    "public": [
        {"entry": "lane.tag", "input": {"lane": "Lab", "bay": "East"}, "expected": "lab/east"},
        {"entry": "lane.tag", "input": {"bay": "East"}, "expected": "/east"},
        {"entry": "lane.tag", "input": {"lane": "Lab"}, "expected": "lab/"},
    ],
    "assessment": [
        {"entry": "lane.tag", "input": {"bay": "West"}, "expected": "/west"},
        {"entry": "lane.tag", "input": {"lane": "Mix"}, "expected": "mix/"},
        {"entry": "lane.tag", "input": {"lane": "Q", "bay": "w"}, "expected": "q/w"},
    ],
}
PLAN = type("P", (), {
    "action": "insert_function", "path": "lane.py", "symbol": "tag",
    "args": "item", "source_sha256": "0" * 64, "existing_source": "",
})()


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


def test_c2_prompt_has_prose_keys_not_c1_or_get():
    runtime = ScriptedRuntime([
        json.dumps({"body": C1_FSTR}),
        json.dumps({"body": SAFE}),
    ])
    result = propose_cell(
        runtime, LANE_SPEC, "contract", EventMeter(lambda *_: None),
        "mock:" + LANE_SPEC["id"], wire_discovery=True, max_tokens=128, asked=False,
        max_completions=2, diagnostic_revision=True,
    )
    assert result["calls_charged"] == 2
    prompt = result["traces"][1]["user_prompt"]
    c1 = result["traces"][0]["preview"]["new_excerpt"]
    assert C1_FSTR not in prompt
    assert c1 not in prompt
    assert ".get(" not in prompt
    assert "['lane', 'bay']" in prompt or '["lane", "bay"]' in prompt
    assert "KeyError" in prompt
    assert "item" in prompt
    assert "/lab/" not in prompt
    assert prompt.rstrip().endswith("constant string literal.")
    assert "Failed cases:" in prompt


def test_constant_string_literal_flagged_before_worker():
    assert is_constant_string_literal("return '/lab/'") is True
    assert is_constant_string_literal("'/lab/'") is True
    assert is_constant_string_literal("return item['lane']") is False
    assembled = assemble_format_proposal(
        "json_body", json.dumps({"body": "return '/lab/'"}),
        "Create tag(item)", {"lane.py": "def echo(t):\n    return t\n"}, plan=PLAN,
    )
    assert assembled["placeholder"] == "constant_literal_no_item"
    assert assembled["structurally_valid"] is not True
    lone = assemble_format_proposal(
        "json_body", json.dumps({"body": "/lab/"}),
        "Create tag(item)", {"lane.py": "def echo(t):\n    return t\n"}, plan=PLAN,
    )
    assert lone["placeholder"] == "constant_literal_no_item"


def test_fresh_ids_and_private_parity():
    from nexus.seed.diagnostic_revision_study import CLOSED_TASK_IDS as DIAG_CLOSED
    from nexus.seed.tag_literal_study import CLOSED_TASK_IDS, covers_varied, private_covers_missing_keys

    config = json.loads((ROOT / "configs/seed_tag_literal_confirm.json").read_text())
    ids = {row["id"] for row in config["tasks"]}
    assert not ids & CLOSED_TASK_IDS
    assert "py_lane_slash" in CLOSED_TASK_IDS
    assert ids == {"py_sack_tally", "py_path_slash", "py_load_div", "py_hold_pair"}
    assert ids.isdisjoint(DIAG_CLOSED)
    for spec in config["tasks"]:
        assert covers_varied(spec)
    tag = next(row for row in config["tasks"] if row["id"] == "py_path_slash")
    assert private_covers_missing_keys(tag)
    assert config["hard_deadline_s"] == 75
    assert config["carried_used_s"] == 3506.581022455996


def test_verifier_chain_and_tamper():
    from nexus.seed.interface_repair_study import replay_final
    from nexus.seed.tag_literal_study import (
        CLOSED_TASK_IDS, HISTORICAL_HARDER_SHA256, WORKER_PROMPT_FREEZE,
        begin, covers_varied, record_model, summarize,
    )

    verify_mod = _verifier()
    config = json.loads((ROOT / "configs/seed_tag_literal_confirm.json").read_text())
    spec = copy.deepcopy(LANE_SPEC)
    spec["id"] = "py_tag_literal_chain"
    config = dict(config)
    config["tasks"] = [spec]
    config["expected_grid"] = dict(config["expected_grid"], confirm_cells=1)
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    records = []
    meter = begin(config, records.append, historical["records"])
    record_model(config, records.append, meter, ScriptedRuntime([
        json.dumps({"body": BARE}),
        json.dumps({"body": SAFE}),
    ]))
    payload = dict(
        study_id="seed-tag-literal-confirm-1",
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
    assert confirm["calls_charged"] == 2
    tampered = copy.deepcopy(payload)
    row = next(item for item in tampered["records"] if item.get("category") == "confirm")
    row["semantic_correct"] = not bool(row.get("semantic_correct"))
    try:
        verify_mod.verify(tampered, config, **extras)
        raised = False
    except ValueError as exc:
        raised = True
        assert "replay" in str(exc) or "mismatch" in str(exc)
    assert raised is True
