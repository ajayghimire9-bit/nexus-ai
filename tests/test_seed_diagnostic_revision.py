"""Offline diagnostic-only revision: no failed source in C2. 0 model calls."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

from nexus.seed.capability_evidence import EventMeter
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.contract_revision_study import propose_cell
from nexus.seed.diagnostic_revision import (
    diagnostic_revision_prompt, failed_source_fragments,
)


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "artifacts/seed_harder_features/seed_harder_features.json"
BARE_SUM = "return sum(item['boxes'] or [0])"
BARE_TAG = "return item['lane'].lower() + '/' + item['bay'].lower()"
SAFE_SUM = "return sum(((row.get('num') or 0) for row in (item.get('boxes') or [])))"
SAFE_TAG = "return (item.get('lane') or '').lower() + '/' + (item.get('bay') or '').lower()"
BOX_SPEC = {
    "id": "py_box_tally_mock",
    "role": "insert",
    "family": "list_records",
    "domain": "python_repo",
    "language": "python",
    "requirement": "tally(item) sums num on each box. Missing num is 0. Empty boxes is 0.",
    "request": "Create function tally(item) that sums num on each dict in boxes. Missing num counts as 0. An empty list is 0.",
    "docs": [{"title": "tally", "content": "tally(item) sums box num values."}],
    "files": {"box.py": "def echo(text):\n    return text\n"},
    "gold_target": {"path": "box.py", "symbol": "tally", "action": "insert_function"},
    "public": [
        {"entry": "box.tally", "input": {"boxes": [{"num": 2}, {"num": 7}]}, "expected": 9},
        {"entry": "box.tally", "input": {"boxes": []}, "expected": 0},
        {"entry": "box.tally", "input": {"boxes": [{"num": 4}, {}]}, "expected": 4},
    ],
    "assessment": [
        {"entry": "box.tally", "input": {"boxes": [{"num": 6}]}, "expected": 6},
    ],
}
LANE_SPEC = {
    "id": "py_lane_slash_mock",
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


def _propose(spec, replies):
    runtime = ScriptedRuntime(replies)
    records = []
    result = propose_cell(
        runtime, spec, "contract", EventMeter(records.append),
        "mock:" + spec["id"], wire_discovery=True, max_tokens=128, asked=False,
        max_completions=2, diagnostic_revision=True,
    )
    return result, records, runtime


def _assert_omits_source(prompt: str, source: str):
    assert source not in prompt
    for fragment in failed_source_fragments(source):
        assert fragment not in prompt
    assert "Failed body:" not in prompt
    assert ".get(" not in prompt


def test_sum_revision_prompt_has_diagnosis_not_c1_body():
    result, records, runtime = _propose(BOX_SPEC, [
        json.dumps({"body": BARE_SUM}),
        json.dumps({"body": SAFE_SUM}),
    ])
    assert result["calls_charged"] == 2
    assert result["max_completions"] == 2
    assert result["diagnostic_revision"] is True
    assert result["behavioral_revision_attempted"] is True
    prompt = result["traces"][1]["user_prompt"]
    _assert_omits_source(prompt, BARE_SUM)
    _assert_omits_source(prompt, result["traces"][0]["preview"]["new_excerpt"])
    assert "TypeError" in prompt
    assert "dict" in prompt
    assert "boxes" in prompt
    assert "num" in prompt
    assert "Failed cases" in prompt
    completes = [
        row for row in records
        if row.get("kind") == "execution" and row.get("operation") == "complete"
    ]
    assert len(completes) == 2
    assert result["public_passed"] is True


def test_keyerror_revision_prompt_has_diagnosis_not_c1_body():
    result, records, runtime = _propose(LANE_SPEC, [
        json.dumps({"body": BARE_TAG}),
        json.dumps({"body": SAFE_TAG}),
    ])
    assert result["calls_charged"] == 2
    prompt = result["traces"][1]["user_prompt"]
    _assert_omits_source(prompt, BARE_TAG)
    assert "KeyError" in prompt
    assert "missing key" in prompt.lower() or "KeyError" in prompt
    assert '"lane"' in prompt or "lane" in prompt
    assert result["semantic_correct"] is True
    assert [row["identity"] for row in records if row.get("operation") == "complete"] == [
        LANE_SPEC["id"] + ":0",
        LANE_SPEC["id"] + ":behavior",
    ]


def test_fresh_ids_private_parity_and_deadline():
    from nexus.seed.diagnostic_revision_study import (
        CLOSED_TASK_IDS, covers_varied, private_covers_missing_keys,
    )
    from nexus.seed.slot3_copy_study import CLOSED_TASK_IDS as COPY_CLOSED

    config = json.loads((ROOT / "configs/seed_diagnostic_revision_confirm.json").read_text())
    ids = {row["id"] for row in config["tasks"]}
    assert not ids & CLOSED_TASK_IDS
    assert "py_crate_tally" in CLOSED_TASK_IDS
    assert "py_post_slash" in CLOSED_TASK_IDS
    assert ids == {"py_box_tally", "py_lane_slash", "py_quota_div", "py_meet_pair"}
    assert ids.isdisjoint(COPY_CLOSED)
    for spec in config["tasks"]:
        assert covers_varied(spec)
    tag = next(row for row in config["tasks"] if row["id"] == "py_lane_slash")
    assert private_covers_missing_keys(tag)
    public_inputs = [case["input"] for case in tag["public"]]
    private_inputs = [case["input"] for case in tag["assessment"]]
    assert all(inp not in public_inputs for inp in private_inputs)
    assert any("lane" not in inp for inp in private_inputs)
    assert any("bay" not in inp for inp in private_inputs)
    assert config["hard_deadline_s"] == 90
    assert config["carried_used_s"] == 3451.157780455996


def test_verifier_two_completion_chain_and_parity():
    from nexus.seed.interface_repair_study import replay_final
    from nexus.seed.diagnostic_revision_study import (
        CLOSED_TASK_IDS, HISTORICAL_HARDER_SHA256, WORKER_PROMPT_FREEZE,
        begin, covers_varied, record_model, summarize,
    )

    verify_mod = _verifier()
    config = json.loads((ROOT / "configs/seed_diagnostic_revision_confirm.json").read_text())
    spec = copy.deepcopy(LANE_SPEC)
    spec["id"] = "py_diag_chain"
    config = dict(config)
    config["tasks"] = [spec]
    config["expected_grid"] = dict(config["expected_grid"], confirm_cells=1)
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    records = []
    meter = begin(config, records.append, historical["records"])
    runtime = ScriptedRuntime([
        json.dumps({"body": BARE_TAG}),
        json.dumps({"body": SAFE_TAG}),
    ])
    record_model(config, records.append, meter, runtime)
    payload = dict(
        study_id="seed-diagnostic-revision-confirm-1",
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
    prompt = confirm["traces"][1]["user_prompt"]
    assert BARE_TAG not in prompt
    replayed = replay_final(confirm, spec)
    assert replayed["public_all_passed"] == confirm["public_passed"]
    assert replayed["private_all_passed"] == confirm["semantic_correct"]
