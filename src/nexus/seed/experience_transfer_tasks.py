"""Source / development / locked target splits for acquired experience.

Closed selective-reuse and capability-map IDs unused. Targets were chosen
for structural roles before any scratch outcome. Fresh IDs are not enough:
overlap is recorded.
"""
from __future__ import annotations

from typing import Any

from .extraction_contract import make_contract

CLOSED = {
    "py_width_ok", "py_keep_exclusive", "py_pair_label", "py_cutoff_ambiguous",
    "py_hi_inclusive_src", "code_bug", "coord_rt_over", "api_id_floor",
}


def _contract(symbol: str, fields: list[str]) -> dict[str, Any]:
    return make_contract(
        symbol, [dict(name=name, type="int") for name in fields],
        "boolean gate", output_type="bool",
    )


def source_tasks() -> list[dict[str, Any]]:
    return [
        dict(
            task_id="src_allow_limit", split="source", family="comparison_boundary",
            reuse_role="source",
            request="Allow score equal to the limit in accept(item).",
            files={"hold.py": "def accept(item):\n    return item['score'] < item['limit']\n"},
            contract=_contract("accept", ["score", "limit"]),
            public=[{"entry": "hold.accept", "input": {"score": 5, "limit": 5}, "expected": True}],
            private=[
                {"entry": "hold.accept", "input": {"score": 5, "limit": 5}, "expected": True},
                {"entry": "hold.accept", "input": {"score": 6, "limit": 5}, "expected": False},
                {"entry": "hold.accept", "input": {"score": 4, "limit": 5}, "expected": True},
            ],
            overlap=dict(family="comparison_boundary", repair="Lt_to_LtE", exact=False),
        ),
        dict(
            task_id="src_null_tag", split="source", family="null_default",
            reuse_role="irrelevant_source",
            request="Keep an empty tag; only replace a missing tag.",
            files={"tag.py": "def tag_of(item):\n    return item.get('tag') or 'missing'\n"},
            contract=make_contract(
                "tag_of", [dict(name="tag", type="str", presence="optional")],
                "empty stays empty", output_type="str"),
            public=[
                {"entry": "tag.tag_of", "input": {"tag": "ok"}, "expected": "ok"},
                {"entry": "tag.tag_of", "input": {"tag": ""}, "expected": ""},
            ],
            private=[{"entry": "tag.tag_of", "input": {}, "expected": "missing"}],
            overlap=dict(family="null_default", repair="or_to_none", exact=False),
        ),
    ]


def development_tasks() -> list[dict[str, Any]]:
    """Used only to freeze representation. Not scored as targets."""
    return [
        dict(
            task_id="dev_capture_lt", split="development", family="comparison_boundary",
            request="Allow n equal to the bound in keep(item).",
            files={"dev.py": "def keep(item):\n    return item['n'] < item['bound']\n"},
            public=[{"entry": "dev.keep", "input": {"n": 2, "bound": 2}, "expected": True}],
        ),
    ]


def target_tasks() -> list[dict[str, Any]]:
    return [
        dict(
            task_id="tgt_rename_layout", split="target", family="comparison_boundary",
            reuse_role="related_rename", reuse_appropriate=True,
            request="Allow width equal to the max in fit(item).",
            files={"gate.py": "def fit(item):\n    return item['width'] < item['max']\n"},
            contract=_contract("fit", ["width", "max"]),
            public=[{"entry": "gate.fit", "input": {"width": 3, "max": 3}, "expected": True}],
            private=[
                {"entry": "gate.fit", "input": {"width": 3, "max": 3}, "expected": True},
                {"entry": "gate.fit", "input": {"width": 4, "max": 3}, "expected": False},
                {"entry": "gate.fit", "input": {"width": 2, "max": 3}, "expected": True},
            ],
            overlap=dict(family="comparison_boundary", repair="Lt_to_LtE",
                         renamed_identifiers=True, different_path=True, exact=False),
        ),
        dict(
            task_id="tgt_gt_floor", split="target", family="comparison_boundary",
            reuse_role="related_rebound", reuse_appropriate=True,
            request="Allow height equal to the floor in rise(item).",
            files={"rise.py": "def rise(item):\n    return item['height'] > item['floor']\n"},
            contract=_contract("rise", ["height", "floor"]),
            public=[{"entry": "rise.rise", "input": {"height": 4, "floor": 4}, "expected": True}],
            private=[
                {"entry": "rise.rise", "input": {"height": 4, "floor": 4}, "expected": True},
                {"entry": "rise.rise", "input": {"height": 3, "floor": 4}, "expected": False},
                {"entry": "rise.rise", "input": {"height": 5, "floor": 4}, "expected": True},
            ],
            overlap=dict(family="comparison_boundary", repair="Gt_to_GtE",
                         operator_held_out=True, exact=False),
        ),
        dict(
            task_id="tgt_strict_cut", split="target", family="comparison_boundary",
            reuse_role="harmful_if_applied", reuse_appropriate=False,
            request="Keep values strictly below the cutoff in clip(item).",
            files={"clip.py": "def clip(item):\n    return item['n'] < item['cut']\n"},
            contract=_contract("clip", ["n", "cut"]),
            public=[{"entry": "clip.clip", "input": {"n": 5, "cut": 5}, "expected": False}],
            private=[
                {"entry": "clip.clip", "input": {"n": 5, "cut": 5}, "expected": False},
                {"entry": "clip.clip", "input": {"n": 4, "cut": 5}, "expected": True},
                {"entry": "clip.clip", "input": {"n": 6, "cut": 5}, "expected": False},
            ],
            overlap=dict(family="comparison_boundary", repair="would_harm",
                         starter_already_correct=True, exact=False),
        ),
        dict(
            task_id="tgt_join_parts", split="target", family="missing_function",
            reuse_role="unrelated_abstain", reuse_appropriate=False,
            request="Create function label_of(item) that joins left and right with a dash.",
            files={"lab.py": "def echo(text):\n    return text\n"},
            contract=make_contract(
                "label_of",
                [dict(name="left", type="str"), dict(name="right", type="str")],
                "join with dash", output_type="str"),
            public=[{"entry": "lab.label_of", "input": {"left": "a", "right": "b"}, "expected": "a-b"}],
            private=[{"entry": "lab.label_of", "input": {"left": "x", "right": "y"}, "expected": "x-y"}],
            overlap=dict(family="missing_function", repair=None, exact=False),
        ),
        dict(
            task_id="tgt_near_bound", split="target", family="comparison_boundary",
            reuse_role="ambiguous_ask", reuse_appropriate=False,
            request="Keep values near the bound in stay(item).",
            files={"stay.py": "def stay(item):\n    return item['n'] < item['bound']\n"},
            contract=_contract("stay", ["n", "bound"]),
            public=[{"entry": "stay.stay", "input": {"n": 1, "bound": 3}, "expected": True}],
            private=[{"entry": "stay.stay", "input": {"n": 3, "bound": 3}, "expected": True}],
            overlap=dict(family="comparison_boundary", repair="ambiguous", exact=False),
        ),
        dict(
            task_id="tgt_exact_limit", split="target", family="comparison_boundary",
            reuse_role="exact_repeat", reuse_appropriate=True,
            request="Allow score equal to the limit in accept(item).",
            files={"hold.py": "def accept(item):\n    return item['score'] < item['limit']\n"},
            contract=_contract("accept", ["score", "limit"]),
            public=[{"entry": "hold.accept", "input": {"score": 5, "limit": 5}, "expected": True}],
            private=[
                {"entry": "hold.accept", "input": {"score": 5, "limit": 5}, "expected": True},
                {"entry": "hold.accept", "input": {"score": 6, "limit": 5}, "expected": False},
                {"entry": "hold.accept", "input": {"score": 4, "limit": 5}, "expected": True},
            ],
            overlap=dict(family="comparison_boundary", repair="Lt_to_LtE", exact=True),
        ),
    ]


def all_declared() -> list[dict[str, Any]]:
    rows = source_tasks() + development_tasks() + target_tasks()
    ids = [row["task_id"] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) & CLOSED:
        raise ValueError("experience_ids")
    return rows
