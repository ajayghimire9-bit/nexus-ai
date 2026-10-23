"""Offline checks for the four-track capability follow-up. No live model."""
import json
from pathlib import Path

from nexus.seed.capability_followup import run_knowledge_track, summarize
from nexus.seed.capability_followup_tasks import (
    CLOSED, all_live_tasks, api_tasks, coordinated_tasks, mathematics_tasks,
    provenance_corpus,
)
from nexus.seed.conversation_review import score_clarify_case
from nexus.seed.knowledge_provenance import (
    dump_all, provenance_resolve, timestamp_sort,
)
from nexus.seed.math_interpretation import (
    compile_statement, parse_statement, score_direct_calculator, score_interpreted,
    validate_statement,
)
from nexus.seed.unresolved_referent import unresolved_referent


def test_fresh_ids_and_closed_unused():
    rows = all_live_tasks()
    assert len(rows) == 10
    assert not {row["task_id"] for row in rows} & CLOSED
    config = json.loads(Path("configs/seed_capability_followup.json").read_text())
    assert config["original_map_rescored"] is False
    assert config["acquired_solution_memory"] is False
    assert config["learning_to_learn_established"] is False


def test_provenance_update_unrelated_and_conflict():
    rows = provenance_corpus()
    update = provenance_resolve(rows, "harbor_hours")
    assert update["selected"] == ["harbor-v2"]
    assert "harbor-v1" in update["dropped"]
    assert update["used_ingestion_timestamp_as_freshness"] is False
    naive = timestamp_sort(rows, "harbor_hours")
    assert naive["selected"] == ["harbor-v1"]
    assert naive["used_ingestion_timestamp_as_freshness"] is True
    dumped = dump_all(rows)
    assert "weather-new" in dumped["selected"]
    unrelated = provenance_resolve(rows, "harbor_hours")
    assert "weather-new" not in unrelated["selected"]
    conflict = provenance_resolve(rows, "pilot_mora")
    assert conflict["conflict"] is True
    assert set(conflict["conflict_ids"]) == {"pilot-dawn", "pilot-dusk"}
    assert conflict["selected"] == []
    grid = run_knowledge_track()
    by = {(row["task_id"], row["method"]): row["scored"]["passed"] for row in grid}
    assert by[("know_prov_update", "provenance")] is True
    assert by[("know_prov_update", "timestamp_sort")] is False
    assert by[("know_prov_unrelated", "dump_all")] is False
    assert by[("know_prov_ambiguous", "provenance")] is True
    assert by[("know_prov_ambiguous", "timestamp_sort")] is False


def test_math_statement_rejects_wrong_problem():
    trap = mathematics_tasks()[4]
    statement = parse_statement(
        '{"quantities":[{"name":"rope","value":12,"unit":"m"},{"name":"cut","value":3,"unit":"m"}],'
        '"relationships":["rope minus cut"],"unknown":"piece","unit":"m","missing":[],'
        '"expression":"12-3"}'
    )
    compiled = compile_statement(statement, trap)
    scored = score_interpreted(trap, statement, compiled, "")
    assert compiled["expression_represents_problem"] is False
    assert scored["passed"] is False
    half = parse_statement(
        '{"quantities":[{"name":"rope","value":12,"unit":"m"},{"name":"cut","value":3,"unit":"m"}],'
        '"relationships":["remainder halved"],"unknown":"piece","unit":"m","missing":[],'
        '"expression":"(12-3)/2"}'
    )
    good = compile_statement(half, trap)
    assert good["ok"] is True
    assert good["value"] == 4.5
    unclear = score_interpreted(
        dict(must_clarify=True),
        {"quantities": [], "missing": ["price"], "unknown": "unit_price",
         "relationships": [], "expression": ""},
        None,
        "",
    )
    assert unclear["passed"] is True
    direct = score_direct_calculator(trap, "", "12-3")
    assert direct["passed"] is False
    assert validate_statement(None, trap)["ok"] is False


def test_api_and_coord_are_separate_families():
    api = api_tasks()
    coord = coordinated_tasks()
    assert all(row["track"] == "coding_api" for row in api)
    assert all(row["track"] == "coding_coord" for row in coord)
    assert all("function_contracts" not in row for row in api)
    assert all("function_contracts" in row for row in coord)
    from nexus.seed.capability_map import score_coding
    helper_only = {
        "util.py": "def under(value, lim):\n    return value < lim\n",
        "app.py": "def echo(text):\n    return text\n",
    }
    scored = score_coding(coord[0], helper_only)
    assert scored["helper_present"] is True
    assert scored["caller_present"] is False
    wired = {
        "span.py": "def clip_hi(nums, hi):\n    return [hi if n > hi else n for n in nums]\n",
        "work.py": (
            "from span import clip_hi\n"
            "def high_cut(item):\n"
            "    return clip_hi(item['bag']['nums'], item['bag']['hi'])\n"
        ),
    }
    api_scored = score_coding(api[0], wired)
    assert api_scored["required_call"] is True
    assert api_scored["private_passed"] is True


def test_book_the_later_one_needs_clarification():
    later = unresolved_referent("Book the later one.", [])
    assert later["needed"] is True
    assert later["booking_keyword_sufficient"] is False
    assert "?" in later["question"]
    named = unresolved_referent("Book the dawn ferry.", [])
    assert named["needed"] is False
    after = unresolved_referent(
        "Book the later one.",
        ["The dawn ferry is at 06:00. The dusk ferry is at 18:00."],
    )
    assert after["needed"] is False
    scored = score_clarify_case("Book the later one.", [])
    assert scored["passed"] is True
    assert scored["clarification"] is True


def test_summary_keeps_tracks_apart():
    summary = summarize([
        dict(track="coding_api", method="direct", scored=dict(passed=True)),
        dict(track="coding_coord", method="direct", scored=dict(passed=False)),
        dict(track="mathematics", method="interpret_compile", scored=dict(passed=True)),
    ])
    assert summary["coding_api"]["direct"]["passed"] == 1
    assert summary["coding_coord"]["direct"]["passed"] == 0
