"""Fresh route-study tasks. Closed map and follow-up IDs unused."""
from __future__ import annotations

from typing import Any

from .extraction_contract import make_contract
from .function_contracts import bind_function_contract
from .knowledge_provenance import ProvenanceRecord, UNRESOLVED_CONFLICT

CLOSED = {
    "know_prov_update", "know_prov_unrelated", "know_prov_ambiguous",
    "math_int_units", "math_int_algebra", "math_int_word", "math_int_percent",
    "math_int_trap", "math_int_under",
    "api_clip_hi", "api_glue_parts", "coord_under", "coord_stamp",
    "harbor-v1", "harbor-v2", "weather-new", "pilot-dawn", "pilot-dusk",
}


def _echo() -> str:
    return "def echo(text):\n    return text\n"


def provenance_corpus() -> list[ProvenanceRecord]:
    return [
        ProvenanceRecord(
            doc_id="quay-note-a", subject="quay_hours",
            content="The east quay gate opens at 05:15.",
            ingested_at="2026-10-19T10:00:00+00:00",
        ),
        ProvenanceRecord(
            doc_id="quay-note-b", subject="quay_hours",
            content="The east quay gate opens at 08:45.",
            ingested_at="2026-10-23T16:00:00+00:00",
        ),
        ProvenanceRecord(
            doc_id="tide-auth-east", subject="tide_gauge",
            content="The official gauge reads 1.2 m at noon.",
            ingested_at="2026-10-20T08:00:00+00:00",
            authority=True, source_version=1, effective_date="2026-10-20",
        ),
        ProvenanceRecord(
            doc_id="tide-auth-west", subject="tide_gauge",
            content="The official gauge reads 2.4 m at noon.",
            ingested_at="2026-10-21T08:00:00+00:00",
            authority=True, source_version=1, effective_date="2026-10-20",
        ),
        ProvenanceRecord(
            doc_id="sheet-old", subject="berth_color",
            content="Berth 4 is unmarked.",
            ingested_at="2026-10-10T08:00:00+00:00",
            source_version=1, effective_date="2026-01-01",
        ),
        ProvenanceRecord(
            doc_id="sheet-red", subject="berth_color",
            content="Berth 4 is red.",
            ingested_at="2026-10-12T08:00:00+00:00",
            source_version=2, effective_date="2026-10-12",
            supersedes="sheet-old",
        ),
        ProvenanceRecord(
            doc_id="sheet-blue", subject="berth_color",
            content="Berth 4 is blue.",
            ingested_at="2026-10-13T08:00:00+00:00",
            source_version=2, effective_date="2026-10-12",
            supersedes="sheet-old",
        ),
        ProvenanceRecord(
            doc_id="crane-v1", subject="crane_limit",
            content="The yard crane limit is 8 tonnes.",
            ingested_at="2026-10-22T12:00:00+00:00",
            source_version=1, effective_date="2025-01-01",
        ),
        ProvenanceRecord(
            doc_id="crane-v3", subject="crane_limit",
            content="The yard crane limit is 11 tonnes.",
            ingested_at="2026-10-18T08:00:00+00:00",
            source_version=3, effective_date="2026-09-01",
            supersedes="crane-v1",
        ),
    ]


def knowledge_tasks() -> list[dict[str, Any]]:
    return [
        dict(
            task_id="know_rt_missing_meta", track="knowledge", family="missing_version",
            subject="quay_hours",
            must_select=[], must_not_select=["quay-note-a", "quay-note-b"],
            must_conflict=True, expected_outcome=UNRESOLVED_CONFLICT,
            expected_fact="unresolved conflict",
        ),
        dict(
            task_id="know_rt_dual_authority", track="knowledge", family="conflicting_authority",
            subject="tide_gauge",
            must_select=[], must_not_select=["tide-auth-east", "tide-auth-west"],
            must_conflict=True, expected_outcome=UNRESOLVED_CONFLICT,
            expected_fact="unresolved conflict",
        ),
        dict(
            task_id="know_rt_ambiguous_super", track="knowledge", family="ambiguous_supersession",
            subject="berth_color",
            must_select=[], must_not_select=["sheet-red", "sheet-blue"],
            must_conflict=True, expected_outcome=UNRESOLVED_CONFLICT,
            expected_fact="unresolved conflict",
        ),
        dict(
            task_id="know_rt_clear_update", track="knowledge", family="clear_replacement",
            subject="crane_limit",
            must_select=["crane-v3"], must_not_select=["crane-v1"],
            must_conflict=False, expected_outcome="selected",
            expected_fact="11 tonnes", forbidden_fact="8 tonnes",
        ),
    ]


def mathematics_tasks() -> list[dict[str, Any]]:
    return [
        dict(task_id="math_rt_units", track="mathematics", family="straightforward",
             request="A sack holds 4.5 kg of grain. How many grams is that?",
             answer=4500, unit="g", expression="4.5 * 1000",
             has_unknown=False, route="calculator"),
        dict(task_id="math_rt_percent", track="mathematics", family="straightforward",
             request="What is 10 percent of 90?",
             answer=9, unit=None, expression="90 * 10 / 100",
             has_unknown=False, route="calculator"),
        dict(task_id="math_rt_algebra", track="mathematics", family="unknown_variable",
             request="Solve for n: 5n + 2 = 27.",
             answer=5, unit=None, expression="(27 - 2) / 5",
             has_unknown=True, route="interpret"),
        dict(task_id="math_rt_under", track="mathematics", family="underspecified",
             request="How far will the barge travel at that current?",
             answer=None, unit=None, must_clarify=True,
             has_unknown=False, route="calculator"),
    ]


def api_id_tasks() -> list[dict[str, Any]]:
    echo = _echo()
    return [
        dict(
            task_id="api_id_floor", track="coding_api", family="id_assembly",
            request="Create function low_cut(item) in work.py using floor_cut from span.",
            files={
                "work.py": echo,
                "span.py": "def floor_cut(nums, lo):\n    return [lo if n < lo else n for n in nums]\n",
            },
            contract=make_contract(
                "low_cut",
                [dict(name="nums", type="list", path=["crate", "nums"]),
                 dict(name="lo", type="int", path=["crate", "lo"])],
                "return floor_cut on nums using lo", output_type="list"),
            docs=[{"title": "span notes", "content": "Use floor_cut from span. crate.nums is a list."}],
            public=[{"entry": "work.low_cut", "input": {"crate": {"nums": [1, 4, 0], "lo": 2}}, "expected": [2, 4, 2]}],
            private=[{"entry": "work.low_cut", "input": {"crate": {"nums": [2, 3], "lo": 2}}, "expected": [2, 3]}],
            gold_selection=dict(api_id="span.floor_cut", bindings=["field.nums", "field.lo"]),
            required_api="floor_cut",
        ),
        dict(
            task_id="api_id_stitch", track="coding_api", family="id_assembly",
            request="Create function note_of(item) in work.py using stitch from marks.",
            files={
                "work.py": echo,
                "marks.py": (
                    "def stitch(parts, glue):\n"
                    "    text = ''\n"
                    "    first = True\n"
                    "    for part in parts:\n"
                    "        text = part if first else text + glue + part\n"
                    "        first = False\n"
                    "    return text\n"
                ),
            },
            contract=make_contract(
                "note_of",
                [dict(name="parts", type="list", path=["note", "parts"]),
                 dict(name="glue", type="str", path=["note", "glue"])],
                "return stitch on parts using glue", output_type="str"),
            docs=[{"title": "mark notes", "content": "Use stitch from marks. note.parts is a list of strings."}],
            public=[{"entry": "work.note_of", "input": {"note": {"parts": ["a", "c"], "glue": "/"}}, "expected": "a/c"}],
            private=[{"entry": "work.note_of", "input": {"note": {"parts": ["z"], "glue": "."}}, "expected": "z"}],
            gold_selection=dict(api_id="marks.stitch", bindings=["field.parts", "field.glue"]),
            required_api="stitch",
        ),
    ]


def coordinated_tasks() -> list[dict[str, Any]]:
    echo = _echo()
    return [
        dict(
            task_id="coord_rt_over", track="coding_coord", family="staged_pair",
            request="Add over(value, floor) to util.py. Create function hold_ok(item) in app.py using over.",
            files={"app.py": echo, "util.py": echo},
            contract=make_contract(
                "hold_ok",
                [dict(name="loads", type="list", path=["bin", "loads"]),
                 dict(name="floor", type="int", path=["bin", "floor"])],
                "return yes if every load is over the floor using over, otherwise no",
                output_type="str", allowed_values=["yes", "no"]),
            public=[
                {"entry": "app.hold_ok", "input": {"bin": {"loads": [6, 7], "floor": 5}}, "expected": "yes"},
                {"entry": "app.hold_ok", "input": {"bin": {"loads": [5], "floor": 5}}, "expected": "no"},
                {"entry": "util.over", "input": {"value": 6, "floor": 5}, "kwargs_input": True, "expected": True},
            ],
            private=[
                {"entry": "app.hold_ok", "input": {"bin": {"loads": [9], "floor": 8}}, "expected": "yes"},
                {"entry": "util.over", "input": {"value": 8, "floor": 8}, "kwargs_input": True, "expected": False},
            ],
            function_contracts={
                "app.hold_ok": bind_function_contract(
                    "app.hold_ok", "hold_ok", ["item"], "str", allowed_values=["yes", "no"],
                ),
                "util.over": bind_function_contract("util.over", "over", ["value", "floor"], "bool"),
            },
            function_stages=[
                dict(role="helper", entry="util.over", path="util.py", symbol="over",
                     args=["value", "floor"], output_type="bool",
                     behavior="return True if value is greater than floor"),
                dict(role="caller", entry="app.hold_ok", path="app.py", symbol="hold_ok",
                     args=["item"], output_type="str", allowed_values=["yes", "no"],
                     behavior="return yes if every load is over the floor using over"),
            ],
        ),
        dict(
            task_id="coord_rt_mark", track="coding_coord", family="staged_pair",
            request="Add mark(name) to util.py. Create function card_of(item) in app.py using mark.",
            files={"app.py": echo, "util.py": echo},
            contract=make_contract(
                "card_of",
                [dict(name="name", type="str", path=["card", "name"])],
                "return mark of name using mark", output_type="str"),
            public=[
                {"entry": "app.card_of", "input": {"card": {"name": "ada"}}, "expected": "*ada"},
                {"entry": "util.mark", "input": {"name": "bo"}, "kwargs_input": True, "expected": "*bo"},
            ],
            private=[
                {"entry": "app.card_of", "input": {"card": {"name": "cy"}}, "expected": "*cy"},
                {"entry": "util.mark", "input": {"name": "d"}, "kwargs_input": True, "expected": "*d"},
            ],
            function_contracts={
                "app.card_of": bind_function_contract("app.card_of", "card_of", ["item"], "str"),
                "util.mark": bind_function_contract("util.mark", "mark", ["name"], "str"),
            },
            function_stages=[
                dict(role="helper", entry="util.mark", path="util.py", symbol="mark",
                     args=["name"], arg_types={"name": "str"}, output_type="str",
                     behavior="return the name with a * prefix"),
                dict(role="caller", entry="app.card_of", path="app.py", symbol="card_of",
                     args=["item"], output_type="str",
                     behavior="return mark of card.name using mark"),
            ],
        ),
    ]


def all_live_tasks() -> list[dict[str, Any]]:
    rows = mathematics_tasks() + api_id_tasks() + coordinated_tasks()
    ids = [row["task_id"] for row in rows]
    if len(ids) != 8 or set(ids) & CLOSED:
        raise ValueError("routes_live_ids")
    return rows
