"""Fresh 30-task capability screen. Closed six-area and extraction IDs unused."""
from __future__ import annotations

from typing import Any

from .extraction_contract import make_contract
from .function_contracts import bind_function_contract

CLOSED = {
    "py_clip_hi_src", "py_slug_join", "py_levy_then_credit", "py_retry_last", "py_age_cap",
    "csv_easy_sum", "dev_clip_span", "dev_coord_within", "dev_use_scale", "live_schema",
}


def _echo() -> str:
    return "def echo(text):\n    return text\n"


def conversation_tasks() -> list[dict[str, Any]]:
    return [
        dict(task_id="conv_follow", area="conversation", family="follow_up",
             turns=["What is a tide pool in one sentence?", "How does that differ from a rock pool?"],
             rubric=dict(must_answer_last=True, topic="tide or rock pool"),
             pending_human_review=True),
        dict(task_id="conv_paraphrase", area="conversation", family="paraphrase",
             turns=["Say the same idea in simpler words: A estuary is where a river meets the sea."],
             rubric=dict(must_restate=True, topic="river and sea"),
             pending_human_review=True),
        dict(task_id="conv_correct", area="conversation", family="correction",
             turns=["The lighthouse is on the north cliff.", "No — I meant the south cliff. Where is it?"],
             rubric=dict(must_use="south", must_not_insist="north"),
             pending_human_review=True),
        dict(task_id="conv_return", area="conversation", family="topic_return",
             turns=["Name one harbor bird.", "What is 2+2?", "Back to the bird: what was it?"],
             rubric=dict(must_return_topic=True),
             pending_human_review=True),
        dict(task_id="conv_beginner", area="conversation", family="beginner",
             turns=["Explain what salinity means to a child who has never heard the word."],
             rubric=dict(must_explain=True, topic="salt"),
             pending_human_review=True),
        dict(task_id="conv_clarify", area="conversation", family="ambiguous",
             turns=["Book the later one."],
             rubric=dict(must_ask=True),
             pending_human_review=True),
    ]


def mathematics_tasks() -> list[dict[str, Any]]:
    return [
        dict(task_id="math_units", area="mathematics", family="arithmetic_units",
             request="A crate holds 2.5 kg of tea. What is that in grams?",
             answer=2500, unit="g", expression="2.5 * 1000"),
        dict(task_id="math_algebra", area="mathematics", family="algebra",
             request="Solve for n: 3n + 7 = 22.",
             answer=5, unit=None, expression="(22 - 7) / 3"),
        dict(task_id="math_word", area="mathematics", family="word",
             request="A ferry seats 48. 17 get off and 9 get on. How many remain if 48 were aboard?",
             answer=40, unit=None, expression="48 - 17 + 9"),
        dict(task_id="math_percent", area="mathematics", family="percent",
             request="What is 15 percent of 80?",
             answer=12, unit=None, expression="80 * 15 / 100"),
        dict(task_id="math_steps", area="mathematics", family="multi_step",
             request="Start with 12. Double it. Add 6. Divide by 5. What is the result?",
             answer=6, unit=None, expression="((12 * 2) + 6) / 5"),
        dict(task_id="math_underspec", area="mathematics", family="underspecified",
             request="How long will the crossing take at that speed?",
             answer=None, unit=None, must_clarify=True),
    ]


def logic_tasks() -> list[dict[str, Any]]:
    return [
        dict(task_id="logic_relate", area="logic", family="relation",
             request="Ada is taller than Bo. Bo is taller than Cy. Who is shortest?",
             expected="Cy", forbidden_certainty=False),
        dict(task_id="logic_order", area="logic", family="ordering",
             request="Three boats leave: Reed before Moss, Moss before Kelp. What is the order?",
             expected="Reed, Moss, Kelp", forbidden_certainty=False),
        dict(task_id="logic_counter", area="logic", family="counterexample",
             request="Claim: every even number greater than 2 is divisible by 4. Give one counterexample.",
             expected="6", forbidden_certainty=False),
        dict(task_id="logic_contradict", area="logic", family="contradiction",
             request="All lamps are off. The red lamp is on. Can both sentences be true?",
             expected="no", forbidden_certainty=False),
        dict(task_id="logic_plan", area="logic", family="resource_plan",
             request="You have 4 hours and must visit A (2h) and B (3h). Can you visit both today?",
             expected="no", forbidden_certainty=False),
        dict(task_id="logic_unknown", area="logic", family="missing_evidence",
             request="Is the hidden box heavier than 3 kg? You have not weighed it.",
             expected=None, must_not_claim=True),
    ]


def coding_tasks() -> list[dict[str, Any]]:
    echo = _echo()
    return [
        dict(
            task_id="code_new", area="coding", family="new_function",
            request="Create function net_pay(item) that returns wage minus tax.",
            files={"pay.py": echo},
            contract=make_contract("net_pay", [dict(name="wage", type="int"), dict(name="tax", type="int")],
                                   "return wage minus tax", output_type="int"),
            public=[{"entry": "pay.net_pay", "input": {"wage": 20, "tax": 3}, "expected": 17}],
            private=[{"entry": "pay.net_pay", "input": {"wage": 9, "tax": 1}, "expected": 8}],
        ),
        dict(
            task_id="code_missing", area="coding", family="missing_value",
            request="Create function shelf_of(item) that returns the shelf string, or empty if missing.",
            files={"tag.py": echo},
            contract=make_contract(
                "shelf_of", [dict(name="shelf", type="str", presence="optional")],
                "return shelf or empty", output_type="str"),
            public=[{"entry": "tag.shelf_of", "input": {"shelf": "B2"}, "expected": "B2"},
                    {"entry": "tag.shelf_of", "input": {}, "expected": ""}],
            private=[{"entry": "tag.shelf_of", "input": {"shelf": "C1"}, "expected": "C1"}],
        ),
        dict(
            task_id="code_nested", area="coding", family="nested_list",
            request="Create function low_names(item) that returns crew names in lowercase.",
            files={"crew.py": echo},
            contract=make_contract(
                "low_names", [dict(name="names", type="list", path=["crew", "names"])],
                "return names in lowercase", output_type="list"),
            public=[{"entry": "crew.low_names", "input": {"crew": {"names": ["Ada"]}}, "expected": ["ada"]}],
            private=[{"entry": "crew.low_names", "input": {"crew": {"names": ["Bo"]}}, "expected": ["bo"]}],
        ),
        dict(
            task_id="code_bug", area="coding", family="bug_repair",
            request="Fix keep(item) so n equal to the cap is allowed.",
            files={"gate.py": "def keep(item):\n    return item['n'] < item['cap']\n"},
            contract=make_contract(
                "keep", [dict(name="n", type="int"), dict(name="cap", type="int")],
                "true when n is at most cap", output_type="bool"),
            public=[{"entry": "gate.keep", "input": {"n": 5, "cap": 5}, "expected": True}],
            private=[{"entry": "gate.keep", "input": {"n": 6, "cap": 5}, "expected": False},
                     {"entry": "gate.keep", "input": {"n": 4, "cap": 5}, "expected": True}],
        ),
        dict(
            task_id="code_api", area="coding", family="documented_api",
            request="Create function total_trim(item) that returns the sum of trim_span on bin.vals.",
            files={"app.py": echo, "measures.py": "def trim_span(nums, lo, hi):\n    return [lo if n < lo else hi if n > hi else n for n in nums]\n"},
            contract=make_contract(
                "total_trim",
                [dict(name="vals", type="list", path=["bin", "vals"]),
                 dict(name="lo", type="int", path=["bin", "lo"]),
                 dict(name="hi", type="int", path=["bin", "hi"])],
                "return the sum of trim_span on vals using lo and hi", output_type="int"),
            docs=[{"title": "field notes", "content": "Use trim_span from measures. bin.vals is a list."}],
            public=[{"entry": "app.total_trim", "input": {"bin": {"vals": [0, 5, 12], "lo": 2, "hi": 8}}, "expected": 15}],
            private=[{"entry": "app.total_trim", "input": {"bin": {"vals": [2, 8], "lo": 2, "hi": 8}}, "expected": 10}],
        ),
        dict(
            task_id="code_coord", area="coding", family="coordinated_edit",
            request="Add above(value, floor) to util.py. Create function pass_gate(item) in app.py that returns yes if every load is above the floor using above, otherwise no.",
            files={"app.py": echo, "util.py": echo},
            contract=make_contract(
                "pass_gate",
                [dict(name="loads", type="list", path=["pack", "loads"]),
                 dict(name="floor", type="int", path=["pack", "floor"])],
                "return yes if every load is above the floor using above, otherwise no",
                output_type="str", allowed_values=["yes", "no"]),
            public=[
                {"entry": "app.pass_gate", "input": {"pack": {"loads": [6, 7], "floor": 5}}, "expected": "yes"},
                {"entry": "app.pass_gate", "input": {"pack": {"loads": [5, 7], "floor": 5}}, "expected": "no"},
                {"entry": "util.above", "input": {"value": 6, "floor": 5}, "kwargs_input": True, "expected": True},
            ],
            private=[
                {"entry": "app.pass_gate", "input": {"pack": {"loads": [9], "floor": 8}}, "expected": "yes"},
                {"entry": "util.above", "input": {"value": 8, "floor": 8}, "kwargs_input": True, "expected": False},
            ],
            function_contracts={
                "app.pass_gate": bind_function_contract(
                    "app.pass_gate", "pass_gate", ["item"], "str", allowed_values=["yes", "no"],
                ),
                "util.above": bind_function_contract("util.above", "above", ["value", "floor"], "bool"),
            },
        ),
    ]


def knowledge_docs() -> list[dict[str, str]]:
    return [
        dict(doc_id="harbor-current", title="Harbor hours",
             content="The inner harbor office opens at 07:00 local time.",
             timestamp="2026-10-20T08:00:00+00:00"),
        dict(doc_id="harbor-stale", title="Harbor hours old",
             content="The inner harbor office opens at 09:00 local time.",
             timestamp="2024-03-01T08:00:00+00:00"),
        dict(doc_id="buoy-red", title="Buoy color",
             content="The channel buoy named Reed is red.",
             timestamp="2026-10-21T08:00:00+00:00"),
        dict(doc_id="buoy-depth", title="Buoy depth",
             content="Reed sits in 4 metres of water.",
             timestamp="2026-10-21T09:00:00+00:00"),
        dict(doc_id="competing-a", title="Pilot A",
             content="Pilot Mora takes the dawn watch.",
             timestamp="2026-10-22T08:00:00+00:00"),
        dict(doc_id="competing-b", title="Pilot B",
             content="Pilot Mora takes the dusk watch.",
             timestamp="2026-10-22T09:00:00+00:00"),
    ]


def knowledge_tasks() -> list[dict[str, Any]]:
    return [
        dict(task_id="know_direct", area="knowledge", family="direct",
             request="What time does the inner harbor office open according to current records?",
             expected_fact="07:00", allowed_docs=["harbor-current"], stale_docs=["harbor-stale"]),
        dict(task_id="know_combine", area="knowledge", family="combine",
             request="What color is Reed and how deep is it?",
             expected_fact="red", expected_extra="4", allowed_docs=["buoy-red", "buoy-depth"]),
        dict(task_id="know_compete", area="knowledge", family="compete",
             request="According to the later pilot note, which watch does Mora take?",
             expected_fact="dusk", allowed_docs=["competing-b"], competing=["competing-a"]),
        dict(task_id="know_fresh", area="knowledge", family="freshness",
             request="Give the current inner harbor opening time, not the old one.",
             expected_fact="07:00", forbidden_fact="09:00", allowed_docs=["harbor-current"]),
        dict(task_id="know_cite", area="knowledge", family="citation",
             request="Cite the current harbor-hours document for the opening time.",
             expected_fact="07:00", must_cite="harbor-current"),
        dict(task_id="know_unknown", area="knowledge", family="unsupported",
             request="What is the tide height at midnight next Tuesday?",
             expected_fact=None, must_uncertain=True),
    ]


def all_tasks() -> list[dict[str, Any]]:
    rows = (
        conversation_tasks() + mathematics_tasks() + logic_tasks()
        + coding_tasks() + knowledge_tasks()
    )
    ids = [row["task_id"] for row in rows]
    if len(ids) != 30 or len(set(ids)) != 30:
        raise ValueError("capability_map_task_count")
    if set(ids) & CLOSED:
        raise ValueError("closed_id_reused")
    return rows
