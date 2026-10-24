"""Fresh named API-ID grid. Opened positional API cells stay closed."""
from __future__ import annotations

from typing import Any

from .extraction_contract import make_contract

CLOSED = {
    "api_id_floor", "api_id_stitch", "api_eq_ceil", "api_eq_glue",
    "api_clip_hi", "api_glue_parts",
}


def _echo() -> str:
    return "def echo(text):\n    return text\n"


def named_api_tasks() -> list[dict[str, Any]]:
    echo = _echo()
    return [
        dict(
            task_id="api_nb_band", family="multi_numeric",
            request="Create function band_of(item) in work.py using clip_band from clip.",
            files={
                "work.py": echo,
                "clip.py": (
                    "def clip_band(vals, lo, hi):\n"
                    "    return [lo if n < lo else hi if n > hi else n for n in vals]\n"
                ),
                "other.py": "def dump(vals):\n    return list(vals)\n",
            },
            contract=make_contract(
                "band_of",
                [dict(name="vals", type="list", path=["pack", "vals"]),
                 dict(name="lo", type="int", path=["pack", "lo"]),
                 dict(name="hi", type="int", path=["pack", "hi"])],
                "return clip_band on vals using lo and hi", output_type="list"),
            docs=[{"title": "clip notes",
                   "content": "Use clip_band from clip. pack.vals is a list. lo and hi are numbers."}],
            public=[{"entry": "work.band_of",
                     "input": {"pack": {"vals": [1, 5, 9], "lo": 2, "hi": 8}},
                     "expected": [2, 5, 8]}],
            private=[{"entry": "work.band_of",
                      "input": {"pack": {"vals": [2, 8], "lo": 2, "hi": 8}},
                      "expected": [2, 8]}],
            gold_selection=dict(
                api_id="clip.clip_band",
                bindings={"vals": "field.vals", "lo": "field.lo", "hi": "field.hi"},
            ),
        ),
        dict(
            task_id="api_nb_stamp", family="optional_param",
            request="Create function card_of(item) in work.py using stamp from labels. mark is optional.",
            files={
                "work.py": echo,
                "labels.py": "def stamp(text, mark=''):\n    return mark + text\n",
                "other.py": "def dump(text):\n    return text\n",
            },
            contract=make_contract(
                "card_of",
                [dict(name="text", type="str", path=["card", "text"])],
                "return stamp on text using the default mark", output_type="str"),
            docs=[{"title": "label notes",
                   "content": "Use stamp from labels. stamp(text, mark='') . Omit mark to keep the default."}],
            public=[{"entry": "work.card_of",
                     "input": {"card": {"text": "ada"}}, "expected": "ada"}],
            private=[{"entry": "work.card_of",
                      "input": {"card": {"text": "bo"}}, "expected": "bo"}],
            gold_selection=dict(
                api_id="labels.stamp",
                bindings={"text": "field.text"},
            ),
        ),
        dict(
            task_id="api_nb_over", family="elem_vs_list",
            request="Create function hold_ok(item) in work.py using above from util on each load.",
            files={
                "work.py": echo,
                "util.py": "def above(value, floor):\n    return value > floor\n",
                "other.py": "def dump(value):\n    return value\n",
            },
            contract=make_contract(
                "hold_ok",
                [dict(name="loads", type="list", path=["bin", "loads"]),
                 dict(name="floor", type="int", path=["bin", "floor"])],
                "return whether every load is above the floor", output_type="bool"),
            docs=[{"title": "util notes",
                   "content": "Use above from util. bin.loads is a list. above takes one value, not the list."}],
            public=[{"entry": "work.hold_ok",
                     "input": {"bin": {"loads": [6, 7], "floor": 5}}, "expected": True}],
            private=[{"entry": "work.hold_ok",
                      "input": {"bin": {"loads": [5], "floor": 5}}, "expected": False}],
            gold_selection=dict(
                api_id="util.above",
                bindings={"value": "elem.loads", "floor": "field.floor"},
            ),
        ),
        dict(
            task_id="api_nb_scale", family="list_not_elem",
            request="Create function grow(item) in work.py using scale from mathx.",
            files={
                "work.py": echo,
                "mathx.py": "def scale(vals, factor):\n    return [n * factor for n in vals]\n",
                "other.py": "def dump(vals):\n    return list(vals)\n",
            },
            contract=make_contract(
                "grow",
                [dict(name="vals", type="list", path=["bag", "vals"]),
                 dict(name="factor", type="int", path=["bag", "factor"])],
                "return scale on the whole vals list using factor", output_type="list"),
            docs=[{"title": "mathx notes",
                   "content": "Use scale from mathx. bag.vals is a list. scale takes the list, not one element."}],
            public=[{"entry": "work.grow",
                     "input": {"bag": {"vals": [2, 3], "factor": 4}}, "expected": [8, 12]}],
            private=[{"entry": "work.grow",
                      "input": {"bag": {"vals": [1], "factor": 5}}, "expected": [5]}],
            gold_selection=dict(
                api_id="mathx.scale",
                bindings={"vals": "field.vals", "factor": "field.factor"},
            ),
        ),
    ]


def all_declared() -> list[dict[str, Any]]:
    rows = named_api_tasks()
    ids = [row["task_id"] for row in rows]
    if len(ids) != 4 or set(ids) & CLOSED:
        raise ValueError("named_api_ids")
    return rows
