"""Offline envelope, sum diagnostic, schema, f-string, budget, and verifier checks."""
from __future__ import annotations

import json
import time
from pathlib import Path

from nexus.seed.agent_loop_worker import compile_check, evaluate_python_payload
from nexus.seed.execution_feedback import (
    SUM_SIGNATURE, layered_public_feedback, public_list_schema, sum_api_diagnostic,
)
from nexus.seed.function_format import assemble_format_proposal
from nexus.seed.hard_deadline import HardDeadline
from nexus.seed.response_envelope import unwrap_extracted
from nexus.seed.sum_row_repair_study import CLOSED_TASK_IDS as REPAIR_CLOSED


ROOT = Path(__file__).resolve().parents[1]
PLAN = type("P", (), {
    "action": "insert_function", "path": "kit.py", "symbol": "total",
    "args": "item", "source_sha256": "0" * 64, "existing_source": "",
})()


def test_valid_nested_envelope_unwraps_to_code():
    raw = json.dumps({"body": json.dumps({"body": "return 1"})})
    assembled = assemble_format_proposal("json_body", raw, "Create total(item)", {"kit.py": "def echo(t):\n    return t\n"}, plan=PLAN)
    assert assembled["raw_valid"] is True
    assert "unwrap_body" in assembled["envelope_ops"]
    assert "return 1" in assembled["raw_excerpt"]
    assert assembled["placeholder"] is None


def test_nested_ellipsis_envelope_is_rejected():
    raw = json.dumps({"body": "{'body': '...'}"})
    assembled = assemble_format_proposal("json_body", raw, "Create total(item)", {"kit.py": "def echo(t):\n    return t\n"}, plan=PLAN)
    assert assembled["placeholder"] == "placeholder_body:ellipsis" or assembled["raw_reason"] == "placeholder_after_unwrap"
    assert assembled["structurally_valid"] is not True


def test_legitimate_dict_return_is_preserved():
    raw = json.dumps({"body": "return {'total': 0}"})
    assembled = assemble_format_proposal("json_body", raw, "Create total(item)", {"kit.py": "def echo(t):\n    return t\n"}, plan=PLAN)
    assert assembled["envelope_ops"] == []
    assert "return {'total': 0}" in assembled["raw_excerpt"] or "return {'total': 0}" in (assembled.get("extracted_text") or "")
    out = unwrap_extracted("return {'total': 0}")
    assert out["reject"] is None
    assert out["ops"] == []
    assert out["text"] == "return {'total': 0}"


def test_malformed_and_excessively_nested_envelopes():
    deep = {"body": "x"}
    for _ in range(5):
        deep = {"body": json.dumps(deep)}
    assembled = assemble_format_proposal(
        "json_body", json.dumps(deep), "Create total(item)",
        {"kit.py": "def echo(t):\n    return t\n"}, plan=PLAN,
    )
    assert assembled["raw_reason"] in {"envelope_too_deep", "body_unparsed"} or assembled["raw_valid"] is False
    broken = unwrap_extracted("{")
    assert broken["reject"] is None
    assert broken["ops"] == []


def test_sum_default_diagnostic_and_valid_start():
    default_err = "TypeError:sum() got an unexpected keyword argument 'default'"
    assert SUM_SIGNATURE in (sum_api_diagnostic(default_err) or "")
    assert "default=" in (sum_api_diagnostic(default_err) or "")
    start_files = {"bag.py": "def total(item):\n    return sum((0,), start=0)\n"}
    compile_check(start_files)
    ok = evaluate_python_payload({
        "language": "python", "files": start_files,
        "cases": [{"entry": "bag.total", "input": {}, "expected": 0}],
    })
    assert ok["compilation_passed"] is True
    assert ok["all_passed"] is True
    default_files = {"bag.py": "def total(item):\n    return sum(item['rows'], default=0)\n"}
    compile_check(default_files)
    bad = evaluate_python_payload({
        "language": "python", "files": default_files,
        "cases": [{"entry": "bag.total", "input": {"rows": [{"qty": 1}]}, "expected": 1}],
    })
    assert bad["compilation_passed"] is True
    assert "default" in str(bad["results"][0]["error"])
    fb = layered_public_feedback(bad, [{"input": {"rows": [{"qty": 1}]}, "expected": 1}], "sums qty. Missing qty is 0.")
    assert fb["api_diagnostic"]
    assert "start=0" in fb["instruction"]
    assert "r.get" not in fb["instruction"]
    assert "for r in" not in fb["instruction"]


def test_schema_feedback_empty_nonempty_heterogeneous():
    tests = [
        {"input": {"bins": [{"qty": 1}, {"qty": 2}]}, "expected": 3},
        {"input": {"bins": []}, "expected": 0},
        {"input": {"bins": [{"qty": 1}, {"note": "x"}]}, "expected": 1},
    ]
    schema = public_list_schema(tests)
    assert schema["has_list_of_dicts"] is True
    assert schema["has_empty_list"] is True
    assert any(row.get("heterogeneous_keys") for row in schema["list_paths"])
    fb = layered_public_feedback(
        {"results": [{"passed": False, "error": "TypeError: int and dict"}]},
        tests, "Missing qty is 0. Empty bins is 0.",
    )
    assert fb["schema_observation"]["has_list_of_dicts"] is True
    assert "qty" in fb["instruction"]
    assert fb["task_requirement"]
    assert "private" not in fb["instruction"].lower()


def test_fstring_compile_and_execute_match():
    files = {"mark.py": "def mark(item):\n    return f\"{item.get('role', '')}:{item.get('title', '')}\"\n"}
    compile_check(files)
    result = evaluate_python_payload({
        "language": "python", "files": files,
        "cases": [
            {"entry": "mark.mark", "input": {"role": "Lab", "title": "One"}, "expected": "Lab:One"},
            {"entry": "mark.mark", "input": {"title": "One"}, "expected": ":One"},
        ],
    })
    assert result["compilation_passed"] is True
    assert result["all_passed"] is True
    fb = layered_public_feedback(result, [{"input": {"role": "Lab"}, "expected": "lab:"}], "Missing role is empty.")
    assert "syntax" not in (fb.get("task_requirement") or "")


def test_deadline_budget_and_cleanup():
    class Fake:
        def __init__(self):
            self.closed = False
            self.process = type("P", (), {"poll": lambda self: None})()

        def close(self):
            self.closed = True

    deadline = HardDeadline(0.05)
    fake = Fake()
    deadline.arm(fake)
    time.sleep(0.08)
    assert deadline.expired() is True
    assert fake.closed is True
    deadline.disarm()
    try:
        deadline.check()
        raised = False
    except TimeoutError:
        raised = True
    assert raised is True


def test_fresh_ids_closed_against_prior_and_varied():
    config = json.loads((ROOT / "configs/seed_interface_repair_confirm.json").read_text())
    from nexus.seed.interface_repair_study import CLOSED_TASK_IDS

    ids = {row["id"] for row in config["tasks"]}
    assert not ids & CLOSED_TASK_IDS
    assert not ids & REPAIR_CLOSED
    assert ids == {"py_bin_tally", "py_role_dash", "py_split_num", "py_years_bar"}
    assert "py_kit_sum" in CLOSED_TASK_IDS
    families = {row["family"] for row in config["tasks"]}
    assert families >= {"list_records", "missing_fields", "arithmetic", "interacting_predicates"}
    tally = next(row for row in config["tasks"] if row["id"] == "py_bin_tally")
    assert "bins" in str(tally["public"])
    assert "qty" in str(tally["public"])
    assert "amount" not in str(tally["public"])


def test_replay_rejects_tampered_success_flag():
    from nexus.seed.interface_repair_study import replay_final

    spec = {
        "language": "python",
        "files": {"crate.py": "def echo(text):\n    return text\n"},
        "public": [{"entry": "crate.tally", "input": {"bins": []}, "expected": 0}],
        "assessment": [{"entry": "crate.tally", "input": {"bins": [{"qty": 1}]}, "expected": 1}],
    }
    lying = {
        "final_files": {"crate.py": "def tally(item):\n    return 0\n"},
        "public_passed": True,
        "semantic_correct": True,
    }
    replayed = replay_final(lying, spec)
    assert replayed["public_all_passed"] is True
    assert replayed["private_all_passed"] is False
    assert lying["semantic_correct"] is True
    assert lying["semantic_correct"] != replayed["private_all_passed"]
