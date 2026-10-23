"""Division, numeric comparison, zero-division, and saved due-patch replay."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.agent_loop_worker import compare_python_result, evaluate_python_payload, run_worker_subprocess


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "artifacts/seed_harder_features/seed_harder_features.json"
HISTORICAL_SHA256 = "31713e4d04ef63ca296ef4c78797ca11e4c87203ddce845ea82c3956646dbdc2"


def test_compare_python_result_types_and_tolerance():
    assert compare_python_result(2.5, 2.5) is True
    assert compare_python_result(5 / 2, 2.5) is True
    assert compare_python_result(2, 2.0) is True
    assert compare_python_result(2.0, 2) is False
    assert compare_python_result(True, 1) is False
    assert compare_python_result(1, True) is False
    assert compare_python_result(True, True) is True


def test_worker_allows_true_division_and_reports_zero_division():
    files = {"quote.py": "def due(item):\n    return item['cents'] / item['unit']\n"}
    ok = evaluate_python_payload({
        "language": "python",
        "files": files,
        "cases": [{"entry": "quote.due", "input": {"cents": 250, "unit": 100}, "expected": 2.5}],
    })
    assert ok["compilation_passed"] is True
    assert ok["all_passed"] is True
    zero = evaluate_python_payload({
        "language": "python",
        "files": files,
        "cases": [{"entry": "quote.due", "input": {"cents": 1, "unit": 0}, "expected": 0.0}],
    })
    assert zero["compilation_passed"] is True
    assert zero["all_passed"] is False
    assert zero["results"][0]["error"].startswith("ZeroDivisionError")


def test_replay_saved_due_patch_without_inference():
    payload = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    import hashlib
    digest = hashlib.sha256(HISTORICAL.read_bytes()).hexdigest()
    assert digest == HISTORICAL_SHA256
    row = next(
        item for item in payload["records"]
        if item.get("category") == "supplied" and item.get("id") == "py_due_quote"
    )
    assert row.get("semantic_correct") is False
    assert "forbidden_ast_node" in str((row.get("public") or {}).get("reason"))
    files = row["final_files"]
    assert "/ 100" in files["quote.py"]
    replayed = run_worker_subprocess({
        "language": "python",
        "files": files,
        "cases": [
            {"entry": "quote.due", "input": {"cents": 250}, "expected": 2.5},
            {"entry": "quote.due", "input": {"cents": 0}, "expected": 0.0},
            {"entry": "quote.due", "input": {"cents": 100}, "expected": 1.0},
        ],
    }, 10)
    assert replayed.get("compilation_passed") is True
    assert replayed.get("all_passed") is True
    assert replayed.get("status") == "passed"
