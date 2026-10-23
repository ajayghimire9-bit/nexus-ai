"""Offline harness checks for the five-area capability screen. No live model."""
import json
from pathlib import Path

from nexus.seed.capability_map import (
    METHODS, eval_arithmetic, score_coding, score_conversation, score_knowledge,
    score_logic, score_math, summarize,
)
from nexus.seed.capability_map_tasks import CLOSED, all_tasks, conversation_tasks


def test_thirty_fresh_tasks_and_closed_ids_unused():
    rows = all_tasks()
    assert len(rows) == 30
    areas = {row["area"] for row in rows}
    assert areas == {"conversation", "mathematics", "logic", "coding", "knowledge"}
    assert all(sum(1 for row in rows if row["area"] == area) == 6 for area in areas)
    assert not {row["task_id"] for row in rows} & CLOSED
    config = json.loads(Path("configs/seed_capability_map.json").read_text())
    assert config["expected_grid"]["cells"] == 90
    assert config["acquired_solution_memory"] is False
    assert config["learning_to_learn_established"] is False
    assert set(config["methods"]) == set(METHODS)


def test_calculator_and_area_scorers():
    assert eval_arithmetic("(22-7)/3")["value"] == 5
    assert eval_arithmetic("__import__('os')")["ok"] is False
    conv = score_conversation(conversation_tasks()[5], ["Which one do you mean?"])
    assert conv["passed"] is True
    assert conv["pending_human_review"] is True
    assert conv["keyword_quality_score"] is False
    math = score_math(
        dict(answer=12, unit=None, expression="80 * 15 / 100"),
        "12",
        eval_arithmetic("80 * 15 / 100"),
    )
    assert math["passed"] is True
    assert math["tool_assisted"] is True
    unclear = score_math(dict(must_clarify=True, answer=None), "How fast is the boat?", None)
    assert unclear["passed"] is True
    logic = score_logic(dict(must_not_claim=True), "There is not enough evidence.")
    assert logic["passed"] is True
    claimed = score_logic(dict(must_not_claim=True), "It is heavier, definitely.")
    assert claimed["passed"] is False


def test_coding_coverage_and_knowledge_are_independent():
    from nexus.seed.capability_map_tasks import coding_tasks
    coord = [row for row in coding_tasks() if row["task_id"] == "code_coord"][0]
    files = {
        "util.py": "def above(value, floor):\n    return value > floor\n",
        "app.py": "def echo(text):\n    return text\n",
    }
    scored = score_coding(coord, files)
    assert scored["helper_present"] is True
    assert scored["caller_present"] is False
    assert scored["required_call"] is False
    know = score_knowledge(
        dict(expected_fact="07:00", must_cite="harbor-current", allowed_docs=["harbor-current"]),
        "Opens at 07:00 [harbor-current]",
        ["harbor-current"],
        [],
    )
    assert know["passed"] is True
    assert know["token_overlap_score"] is False
    unknown = score_knowledge(dict(must_uncertain=True), "I do not have relevant stored evidence.", [], [])
    assert unknown["passed"] is True
    summary = summarize([
        dict(area="mathematics", method="model_alone", scored=dict(passed=True)),
        dict(area="mathematics", method="tools_cache", scored=dict(passed=False)),
        dict(area="mathematics", method="nexus", scored=dict(passed=False)),
    ])
    assert summary["mathematics"]["model_alone"] == dict(n=1, passed=1, pending_human_review=False)
