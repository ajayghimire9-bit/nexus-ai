"""Fresh splits for the equal inclusive-repair baseline and API-ID retest.

Opened acquired-experience and routes API IDs are closed. Structural
roles match the prior study; surface names and paths are new.
"""
from __future__ import annotations

from typing import Any

from .extraction_contract import make_contract

CLOSED = {
    "py_width_ok", "py_keep_exclusive", "py_pair_label", "py_cutoff_ambiguous",
    "py_hi_inclusive_src", "code_bug", "coord_rt_over",
    "api_id_floor", "api_id_stitch",
    "src_allow_limit", "src_null_tag", "dev_capture_lt",
    "tgt_rename_layout", "tgt_gt_floor", "tgt_strict_cut",
    "tgt_join_parts", "tgt_near_bound", "tgt_exact_limit",
}


def _contract(symbol: str, fields: list[str]) -> dict[str, Any]:
    return make_contract(
        symbol, [dict(name=name, type="int") for name in fields],
        "boolean gate", output_type="bool",
    )


def _echo() -> str:
    return "def echo(text):\n    return text\n"


def source_tasks() -> list[dict[str, Any]]:
    return [
        dict(
            task_id="src_eq_span", split="source", family="comparison_boundary",
            reuse_role="source",
            request="Allow span equal to the cap in hold(item).",
            files={"bin.py": "def hold(item):\n    return item['span'] < item['cap']\n"},
            contract=_contract("hold", ["span", "cap"]),
            public=[{"entry": "bin.hold", "input": {"span": 7, "cap": 7}, "expected": True}],
            private=[
                {"entry": "bin.hold", "input": {"span": 7, "cap": 7}, "expected": True},
                {"entry": "bin.hold", "input": {"span": 8, "cap": 7}, "expected": False},
                {"entry": "bin.hold", "input": {"span": 6, "cap": 7}, "expected": True},
            ],
            overlap=dict(family="comparison_boundary", repair="Lt_to_LtE", exact=False),
        ),
        dict(
            task_id="src_eq_null", split="source", family="null_default",
            reuse_role="irrelevant_source",
            request="Keep an empty mark; only replace a missing mark.",
            files={"mark.py": "def mark_of(item):\n    return item.get('mark') or 'none'\n"},
            contract=make_contract(
                "mark_of", [dict(name="mark", type="str", presence="optional")],
                "empty stays empty", output_type="str"),
            public=[
                {"entry": "mark.mark_of", "input": {"mark": "ok"}, "expected": "ok"},
                {"entry": "mark.mark_of", "input": {"mark": ""}, "expected": ""},
            ],
            private=[{"entry": "mark.mark_of", "input": {}, "expected": "none"}],
            overlap=dict(family="null_default", repair="or_to_none", exact=False),
        ),
    ]


def development_tasks() -> list[dict[str, Any]]:
    return [
        dict(
            task_id="dev_eq_lt", split="development", family="comparison_boundary",
            request="Allow n equal to the bound in keep(item).",
            files={"dev.py": "def keep(item):\n    return item['n'] < item['bound']\n"},
            public=[{"entry": "dev.keep", "input": {"n": 2, "bound": 2}, "expected": True}],
        ),
    ]


def target_tasks() -> list[dict[str, Any]]:
    return [
        dict(
            task_id="tgt_eq_rename", split="target", family="comparison_boundary",
            reuse_role="related_rename", reuse_appropriate=True,
            request="Allow depth equal to the max in pack(item).",
            files={"case.py": "def pack(item):\n    return item['depth'] < item['max']\n"},
            contract=_contract("pack", ["depth", "max"]),
            public=[{"entry": "case.pack", "input": {"depth": 4, "max": 4}, "expected": True}],
            private=[
                {"entry": "case.pack", "input": {"depth": 4, "max": 4}, "expected": True},
                {"entry": "case.pack", "input": {"depth": 5, "max": 4}, "expected": False},
                {"entry": "case.pack", "input": {"depth": 3, "max": 4}, "expected": True},
            ],
            overlap=dict(family="comparison_boundary", repair="Lt_to_LtE",
                         renamed_identifiers=True, different_path=True, exact=False),
        ),
        dict(
            task_id="tgt_eq_gt", split="target", family="comparison_boundary",
            reuse_role="related_rebound", reuse_appropriate=True,
            request="Allow level equal to the floor in lift(item).",
            files={"lift.py": "def lift(item):\n    return item['level'] > item['floor']\n"},
            contract=_contract("lift", ["level", "floor"]),
            public=[{"entry": "lift.lift", "input": {"level": 6, "floor": 6}, "expected": True}],
            private=[
                {"entry": "lift.lift", "input": {"level": 6, "floor": 6}, "expected": True},
                {"entry": "lift.lift", "input": {"level": 5, "floor": 6}, "expected": False},
                {"entry": "lift.lift", "input": {"level": 7, "floor": 6}, "expected": True},
            ],
            overlap=dict(family="comparison_boundary", repair="Gt_to_GtE",
                         operator_held_out=True, exact=False),
        ),
        dict(
            task_id="tgt_eq_exclusive", split="target", family="comparison_boundary",
            reuse_role="harmful_if_applied", reuse_appropriate=False,
            request="Keep values strictly below the cutoff in trim(item).",
            files={"trim.py": "def trim(item):\n    return item['n'] < item['cut']\n"},
            contract=_contract("trim", ["n", "cut"]),
            public=[{"entry": "trim.trim", "input": {"n": 8, "cut": 8}, "expected": False}],
            private=[
                {"entry": "trim.trim", "input": {"n": 8, "cut": 8}, "expected": False},
                {"entry": "trim.trim", "input": {"n": 7, "cut": 8}, "expected": True},
                {"entry": "trim.trim", "input": {"n": 9, "cut": 8}, "expected": False},
            ],
            overlap=dict(family="comparison_boundary", repair="would_harm",
                         starter_already_correct=True, exact=False),
        ),
        dict(
            task_id="tgt_eq_unrelated", split="target", family="missing_function",
            reuse_role="unrelated_abstain", reuse_appropriate=False,
            request="Create function pair_of(item) that joins head and tail with a colon.",
            files={"pair.py": "def echo(text):\n    return text\n"},
            contract=make_contract(
                "pair_of",
                [dict(name="head", type="str"), dict(name="tail", type="str")],
                "join with colon", output_type="str"),
            public=[{"entry": "pair.pair_of", "input": {"head": "a", "tail": "b"}, "expected": "a:b"}],
            private=[{"entry": "pair.pair_of", "input": {"head": "x", "tail": "y"}, "expected": "x:y"}],
            overlap=dict(family="missing_function", repair=None, exact=False),
        ),
        dict(
            task_id="tgt_eq_ask", split="target", family="comparison_boundary",
            reuse_role="ambiguous_ask", reuse_appropriate=False,
            request="Keep values near the edge in rest(item).",
            files={"rest.py": "def rest(item):\n    return item['n'] < item['edge']\n"},
            contract=_contract("rest", ["n", "edge"]),
            public=[{"entry": "rest.rest", "input": {"n": 1, "edge": 4}, "expected": True}],
            private=[{"entry": "rest.rest", "input": {"n": 4, "edge": 4}, "expected": True}],
            overlap=dict(family="comparison_boundary", repair="ambiguous", exact=False),
        ),
        dict(
            task_id="tgt_eq_repeat", split="target", family="comparison_boundary",
            reuse_role="exact_repeat", reuse_appropriate=True,
            request="Allow span equal to the cap in hold(item).",
            files={"bin.py": "def hold(item):\n    return item['span'] < item['cap']\n"},
            contract=_contract("hold", ["span", "cap"]),
            public=[{"entry": "bin.hold", "input": {"span": 7, "cap": 7}, "expected": True}],
            private=[
                {"entry": "bin.hold", "input": {"span": 7, "cap": 7}, "expected": True},
                {"entry": "bin.hold", "input": {"span": 8, "cap": 7}, "expected": False},
                {"entry": "bin.hold", "input": {"span": 6, "cap": 7}, "expected": True},
            ],
            overlap=dict(family="comparison_boundary", repair="Lt_to_LtE", exact=True),
        ),
    ]


def api_id_tasks() -> list[dict[str, Any]]:
    echo = _echo()
    return [
        dict(
            task_id="api_eq_ceil", track="coding_api", family="id_assembly",
            request="Create function high_cut(item) in work.py using cap_high from clip.",
            files={
                "work.py": echo,
                "clip.py": "def cap_high(vals, hi):\n    return [hi if n > hi else n for n in vals]\n",
                "other.py": "def dump(vals):\n    return list(vals)\n",
            },
            contract=make_contract(
                "high_cut",
                [dict(name="vals", type="list", path=["box", "vals"]),
                 dict(name="hi", type="int", path=["box", "hi"])],
                "return cap_high on vals using hi", output_type="list"),
            docs=[{"title": "clip notes", "content": "Use cap_high from clip. box.vals is a list."}],
            public=[{"entry": "work.high_cut", "input": {"box": {"vals": [1, 9, 4], "hi": 5}}, "expected": [1, 5, 4]}],
            private=[{"entry": "work.high_cut", "input": {"box": {"vals": [5, 6], "hi": 5}}, "expected": [5, 5]}],
            gold_selection=dict(api_id="clip.cap_high", bindings=["field.vals", "field.hi"]),
            required_api="cap_high",
        ),
        dict(
            task_id="api_eq_glue", track="coding_api", family="id_assembly",
            request="Create function tape_of(item) in work.py using glue_bits from tape.",
            files={
                "work.py": echo,
                "tape.py": (
                    "def glue_bits(bits, mark):\n"
                    "    text = ''\n"
                    "    first = True\n"
                    "    for bit in bits:\n"
                    "        text = bit if first else text + mark + bit\n"
                    "        first = False\n"
                    "    return text\n"
                ),
                "other.py": "def dump(bits):\n    return list(bits)\n",
            },
            contract=make_contract(
                "tape_of",
                [dict(name="bits", type="list", path=["roll", "bits"]),
                 dict(name="mark", type="str", path=["roll", "mark"])],
                "return glue_bits on bits using mark", output_type="str"),
            docs=[{"title": "tape notes", "content": "Use glue_bits from tape. roll.bits is a list of strings."}],
            public=[{"entry": "work.tape_of", "input": {"roll": {"bits": ["p", "q"], "mark": "-"}}, "expected": "p-q"}],
            private=[{"entry": "work.tape_of", "input": {"roll": {"bits": ["z"], "mark": ":"}}, "expected": "z"}],
            gold_selection=dict(api_id="tape.glue_bits", bindings=["field.bits", "field.mark"]),
            required_api="glue_bits",
        ),
    ]


def all_declared() -> list[dict[str, Any]]:
    rows = source_tasks() + development_tasks() + target_tasks() + api_id_tasks()
    ids = [row["task_id"] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) & CLOSED:
        raise ValueError("equal_inclusive_ids")
    return rows
