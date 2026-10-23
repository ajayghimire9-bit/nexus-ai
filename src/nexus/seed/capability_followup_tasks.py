"""Fresh follow-up tasks. Closed capability-map and extraction IDs unused."""
from __future__ import annotations

from typing import Any

from .extraction_contract import make_contract
from .function_contracts import bind_function_contract
from .knowledge_provenance import ProvenanceRecord

CLOSED = {
    "conv_follow", "conv_paraphrase", "conv_correct", "conv_return",
    "conv_beginner", "conv_clarify",
    "math_units", "math_algebra", "math_word", "math_percent",
    "math_steps", "math_underspec",
    "code_new", "code_missing", "code_nested", "code_bug", "code_api", "code_coord",
    "know_direct", "know_combine", "know_compete", "know_fresh", "know_cite", "know_unknown",
    "py_clip_hi_src", "dev_clip_span", "dev_coord_within", "dev_use_scale",
}


def _echo() -> str:
    return "def echo(text):\n    return text\n"


def provenance_corpus() -> list[ProvenanceRecord]:
    """Harbor v2 is the replacement but was ingested earlier than v1."""
    return [
        ProvenanceRecord(
            doc_id="harbor-v2", subject="harbor_hours",
            content="The inner harbor office opens at 06:30 local time.",
            ingested_at="2026-10-18T08:00:00+00:00",
            source_version=2, effective_date="2026-10-15",
            supersedes="harbor-v1",
        ),
        ProvenanceRecord(
            doc_id="harbor-v1", subject="harbor_hours",
            content="The inner harbor office opens at 09:00 local time.",
            ingested_at="2026-10-22T12:00:00+00:00",
            source_version=1, effective_date="2024-03-01",
        ),
        ProvenanceRecord(
            doc_id="weather-new", subject="weather",
            content="Fog is expected at dawn on the outer reach.",
            ingested_at="2026-10-23T18:00:00+00:00",
            source_version=1, effective_date="2026-10-23",
        ),
        ProvenanceRecord(
            doc_id="pilot-dawn", subject="pilot_mora",
            content="Pilot Mora takes the dawn watch.",
            ingested_at="2026-10-20T08:00:00+00:00",
            source_version=1, effective_date="2026-10-20",
        ),
        ProvenanceRecord(
            doc_id="pilot-dusk", subject="pilot_mora",
            content="Pilot Mora takes the dusk watch.",
            ingested_at="2026-10-21T09:00:00+00:00",
            source_version=1, effective_date="2026-10-20",
        ),
    ]


def knowledge_tasks() -> list[dict[str, Any]]:
    return [
        dict(
            task_id="know_prov_update", track="knowledge", family="explicit_update",
            subject="harbor_hours",
            request="What time does the inner harbor office currently open?",
            must_select=["harbor-v2"], must_not_select=["harbor-v1", "weather-new"],
            expected_fact="06:30", forbidden_fact="09:00", must_conflict=False,
        ),
        dict(
            task_id="know_prov_unrelated", track="knowledge", family="unrelated_newer",
            subject="harbor_hours",
            request="Harbor office opening time, ignoring weather bulletins.",
            must_select=["harbor-v2"], must_not_select=["weather-new", "harbor-v1"],
            expected_fact="06:30", forbidden_fact="Fog", must_conflict=False,
        ),
        dict(
            task_id="know_prov_ambiguous", track="knowledge", family="genuine_ambiguity",
            subject="pilot_mora",
            request="Which watch does Mora take?",
            must_select=[], must_not_select=[],
            expected_fact="conflict", forbidden_fact=None, must_conflict=True,
        ),
    ]


def mathematics_tasks() -> list[dict[str, Any]]:
    return [
        dict(task_id="math_int_units", track="mathematics", family="units",
             request="A jar holds 3.2 L of oil. How many millilitres is that?",
             answer=3200, unit="ml", expression="3.2 * 1000"),
        dict(task_id="math_int_algebra", track="mathematics", family="algebra",
             request="Solve for n: 4n - 5 = 19.",
             answer=6, unit=None, expression="(19 + 5) / 4"),
        dict(task_id="math_int_word", track="mathematics", family="word",
             request="A crate starts with 36 apples. 11 are sold and 8 are added. How many are left?",
             answer=33, unit=None, expression="36 - 11 + 8"),
        dict(task_id="math_int_percent", track="mathematics", family="percent",
             request="What is 25 percent of 64?",
             answer=16, unit=None, expression="64 * 25 / 100"),
        dict(task_id="math_int_trap", track="mathematics", family="wrong_problem",
             request="A rope is 12 m. Cut off 3 m, then cut the remainder in half. How long is each remaining piece?",
             answer=4.5, unit="m", expression="(12 - 3) / 2",
             must_use_values=[12, 3, 2]),
        dict(task_id="math_int_under", track="mathematics", family="underspecified",
             request="What is the unit price of the tea?",
             answer=None, unit=None, must_clarify=True),
    ]


def api_tasks() -> list[dict[str, Any]]:
    echo = _echo()
    return [
        dict(
            task_id="api_clip_hi", track="coding_api", family="documented_api",
            request="Create function high_cut(item) in work.py that uses clip_hi from span.",
            files={
                "work.py": echo,
                "span.py": "def clip_hi(nums, hi):\n    return [hi if n > hi else n for n in nums]\n",
            },
            contract=make_contract(
                "high_cut",
                [dict(name="nums", type="list", path=["bag", "nums"]),
                 dict(name="hi", type="int", path=["bag", "hi"])],
                "return clip_hi on nums using hi", output_type="list"),
            docs=[{"title": "span notes", "content": "Use clip_hi from span. bag.nums is a list. bag.hi is the cap."}],
            public=[{"entry": "work.high_cut", "input": {"bag": {"nums": [1, 9, 4], "hi": 5}}, "expected": [1, 5, 4]}],
            private=[{"entry": "work.high_cut", "input": {"bag": {"nums": [5, 6], "hi": 5}}, "expected": [5, 5]}],
            required_api="clip_hi",
        ),
        dict(
            task_id="api_glue_parts", track="coding_api", family="documented_api",
            request="Create function label_of(item) in work.py that uses glue from marks.",
            files={
                "work.py": echo,
                "marks.py": "def glue(parts, mark):\n    return mark.join(parts)\n",
            },
            contract=make_contract(
                "label_of",
                [dict(name="parts", type="list", path=["tag", "parts"]),
                 dict(name="mark", type="str", path=["tag", "mark"])],
                "return glue on parts using mark", output_type="str"),
            docs=[{"title": "mark notes", "content": "Use glue from marks. tag.parts is a list of strings."}],
            public=[{"entry": "work.label_of", "input": {"tag": {"parts": ["a", "b"], "mark": "-"}}, "expected": "a-b"}],
            private=[{"entry": "work.label_of", "input": {"tag": {"parts": ["x"], "mark": ":"}}, "expected": "x"}],
            required_api="glue",
        ),
    ]


def coordinated_tasks() -> list[dict[str, Any]]:
    echo = _echo()
    return [
        dict(
            task_id="coord_under", track="coding_coord", family="helper_and_caller",
            request="Add under(value, lim) to util.py. Create function pack_ok(item) in app.py that uses under.",
            files={"app.py": echo, "util.py": echo},
            contract=make_contract(
                "pack_ok",
                [dict(name="loads", type="list", path=["bin", "loads"]),
                 dict(name="lim", type="int", path=["bin", "lim"])],
                "return yes if every load is under the limit using under, otherwise no",
                output_type="str", allowed_values=["yes", "no"]),
            public=[
                {"entry": "app.pack_ok", "input": {"bin": {"loads": [1, 2], "lim": 5}}, "expected": "yes"},
                {"entry": "app.pack_ok", "input": {"bin": {"loads": [5], "lim": 5}}, "expected": "no"},
                {"entry": "util.under", "input": {"value": 2, "lim": 5}, "kwargs_input": True, "expected": True},
            ],
            private=[
                {"entry": "app.pack_ok", "input": {"bin": {"loads": [3], "lim": 4}}, "expected": "yes"},
                {"entry": "util.under", "input": {"value": 4, "lim": 4}, "kwargs_input": True, "expected": False},
            ],
            function_contracts={
                "app.pack_ok": bind_function_contract(
                    "app.pack_ok", "pack_ok", ["item"], "str", allowed_values=["yes", "no"],
                ),
                "util.under": bind_function_contract("util.under", "under", ["value", "lim"], "bool"),
            },
            required_api="under",
        ),
        dict(
            task_id="coord_stamp", track="coding_coord", family="helper_and_caller",
            request="Add stamp(name) to util.py. Create function row_tag(item) in app.py that uses stamp.",
            files={"app.py": echo, "util.py": echo},
            contract=make_contract(
                "row_tag",
                [dict(name="name", type="str", path=["card", "name"])],
                "return stamp of name using stamp", output_type="str"),
            public=[
                {"entry": "app.row_tag", "input": {"card": {"name": "ada"}}, "expected": "#ada"},
                {"entry": "util.stamp", "input": {"name": "bo"}, "kwargs_input": True, "expected": "#bo"},
            ],
            private=[
                {"entry": "app.row_tag", "input": {"card": {"name": "cy"}}, "expected": "#cy"},
                {"entry": "util.stamp", "input": {"name": "d"}, "kwargs_input": True, "expected": "#d"},
            ],
            function_contracts={
                "app.row_tag": bind_function_contract("app.row_tag", "row_tag", ["item"], "str"),
                "util.stamp": bind_function_contract("util.stamp", "stamp", ["name"], "str"),
            },
            required_api="stamp",
        ),
    ]


def clarify_cases() -> list[dict[str, Any]]:
    return [
        dict(task_id="conv_book_later", text="Book the later one.", history=[], must_ask=True),
        dict(task_id="conv_book_named", text="Book the dawn ferry.", history=[], must_ask=False),
        dict(
            task_id="conv_book_after_options",
            text="Book the later one.",
            history=["The dawn ferry is at 06:00. The dusk ferry is at 18:00."],
            must_ask=False,
        ),
    ]


def all_live_tasks() -> list[dict[str, Any]]:
    rows = mathematics_tasks() + api_tasks() + coordinated_tasks()
    ids = [row["task_id"] for row in rows]
    if len(ids) != 10 or set(ids) & CLOSED:
        raise ValueError("followup_live_ids")
    return rows
