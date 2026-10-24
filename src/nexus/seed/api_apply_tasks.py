"""Balanced apply-mode API grid. Opened named and positional cells stay closed.

Two different APIs in each role. Fresh fields and layouts; renamed IDs
alone are not independence. One ask cell has two type-compatible limits.
"""
from __future__ import annotations

from typing import Any

from .extraction_contract import make_contract

CLOSED = {
    "api_id_floor", "api_id_stitch", "api_eq_ceil", "api_eq_glue",
    "api_nb_band", "api_nb_stamp", "api_nb_over", "api_nb_scale",
    "api_clip_hi", "api_glue_parts",
}


def _echo() -> str:
    return "def echo(text):\n    return text\n"


def apply_api_tasks() -> list[dict[str, Any]]:
    echo = _echo()
    return [
        dict(
            task_id="api_ap_omit_badge", role="optional_omitted",
            request="Create function badge_of(item) in work.py using badge from labels. Keep the documented tag default.",
            files={
                "work.py": echo,
                "labels.py": "def badge(name, tag=''):\n    return tag + name\n",
                "other.py": "def dump(name):\n    return name\n",
            },
            contract=make_contract(
                "badge_of",
                [dict(name="name", type="str", path=["card", "name"]),
                 dict(name="title", type="str", path=["card", "title"])],
                "return badge on name using the default tag", output_type="str"),
            docs=[{"title": "labels",
                   "content": "badge(name, tag=''). Omit tag to keep ''. title is a different string."}],
            public=[{"entry": "work.badge_of",
                     "input": {"card": {"name": "ada", "title": "x"}}, "expected": "ada"}],
            private=[{"entry": "work.badge_of",
                      "input": {"card": {"name": "bo", "title": "y"}}, "expected": "bo"}],
            gold_selection=dict(api_id="labels.badge", bindings={"name": "field.name"}, apply="direct"),
        ),
        dict(
            task_id="api_ap_omit_wrap", role="optional_omitted",
            request="Create function wrap_of(item) in work.py using wrap from notes. Keep the documented pad default.",
            files={
                "work.py": echo,
                "notes.py": "def wrap(body, pad='.'):\n    return pad + body + pad\n",
                "other.py": "def dump(body):\n    return body\n",
            },
            contract=make_contract(
                "wrap_of",
                [dict(name="body", type="str", path=["note", "body"]),
                 dict(name="head", type="str", path=["note", "head"])],
                "return wrap on body using the default pad", output_type="str"),
            docs=[{"title": "notes",
                   "content": "wrap(body, pad='.'). Omit pad to keep '.'. head is a different string."}],
            public=[{"entry": "work.wrap_of",
                     "input": {"note": {"body": "ada", "head": "-"}}, "expected": ".ada."}],
            private=[{"entry": "work.wrap_of",
                      "input": {"note": {"body": "bo", "head": "*"}}, "expected": ".bo."}],
            gold_selection=dict(api_id="notes.wrap", bindings={"body": "field.body"}, apply="direct"),
        ),
        dict(
            task_id="api_ap_use_tone", role="optional_supplied",
            request="Create function tint_of(item) in work.py using tint from paint. Use the tone field, not the shade.",
            files={
                "work.py": echo,
                "paint.py": "def tint(text, tone='grey'):\n    return tone + ':' + text\n",
                "other.py": "def dump(text):\n    return text\n",
            },
            contract=make_contract(
                "tint_of",
                [dict(name="title", type="str", path=["card", "title"]),
                 dict(name="tone", type="str", path=["card", "tone"]),
                 dict(name="shade", type="str", path=["card", "shade"])],
                "return tint of title using tone", output_type="str"),
            docs=[{"title": "paint",
                   "content": "tint(text, tone='grey'). Binding tone is required here. shade is a decoy."}],
            public=[{"entry": "work.tint_of",
                     "input": {"card": {"title": "ada", "tone": "red", "shade": "blue"}},
                     "expected": "red:ada"}],
            private=[{"entry": "work.tint_of",
                      "input": {"card": {"title": "bo", "tone": "ink", "shade": "ash"}},
                      "expected": "ink:bo"}],
            gold_selection=dict(
                api_id="paint.tint",
                bindings={"text": "field.title", "tone": "field.tone"},
                apply="direct",
            ),
        ),
        dict(
            task_id="api_ap_use_bonus", role="optional_supplied",
            request="Create function lift_of(item) in work.py using shift from mathx. Add the bonus, not the fee.",
            files={
                "work.py": echo,
                "mathx.py": "def shift(n, extra=0):\n    return n + extra\n",
                "other.py": "def dump(n):\n    return n\n",
            },
            contract=make_contract(
                "lift_of",
                [dict(name="count", type="int", path=["bin", "count"]),
                 dict(name="bonus", type="int", path=["bin", "bonus"]),
                 dict(name="fee", type="int", path=["bin", "fee"])],
                "return shift of count by bonus", output_type="int"),
            docs=[{"title": "mathx",
                   "content": "shift(n, extra=0). Binding extra is required here. fee is a decoy."}],
            public=[{"entry": "work.lift_of",
                     "input": {"bin": {"count": 4, "bonus": 3, "fee": 1}}, "expected": 7}],
            private=[{"entry": "work.lift_of",
                      "input": {"bin": {"count": 5, "bonus": 2, "fee": 9}}, "expected": 7}],
            gold_selection=dict(
                api_id="mathx.shift",
                bindings={"n": "field.count", "extra": "field.bonus"},
                apply="direct",
            ),
        ),
        dict(
            task_id="api_ap_list_stretch", role="whole_list",
            request="Create function grow(item) in work.py using stretch from stats on the nums list, not alts. Use gain, not loss.",
            files={
                "work.py": echo,
                "stats.py": "def stretch(nums, gain):\n    return [n * gain for n in nums]\n",
                "other.py": "def dump(nums):\n    return list(nums)\n",
            },
            contract=make_contract(
                "grow",
                [dict(name="nums", type="list", path=["bag", "nums"]),
                 dict(name="alts", type="list", path=["bag", "alts"]),
                 dict(name="gain", type="int", path=["bag", "gain"]),
                 dict(name="loss", type="int", path=["bag", "loss"])],
                "return stretch on the whole nums list using gain", output_type="list"),
            docs=[{"title": "stats",
                   "content": "stretch(nums, gain) takes the list. alts and loss are decoys."}],
            public=[{"entry": "work.grow",
                     "input": {"bag": {"nums": [2, 3], "alts": [9], "gain": 4, "loss": 1}},
                     "expected": [8, 12]}],
            private=[{"entry": "work.grow",
                      "input": {"bag": {"nums": [1], "alts": [8], "gain": 5, "loss": 2}},
                      "expected": [5]}],
            gold_selection=dict(
                api_id="stats.stretch",
                bindings={"nums": "field.nums", "gain": "field.gain"},
                apply="whole_list",
            ),
        ),
        dict(
            task_id="api_ap_list_join", role="whole_list",
            request="Create function tape_of(item) in work.py using join_all from bags on the parts list, not bits. Use glue, not mark.",
            files={
                "work.py": echo,
                "bags.py": (
                    "def join_all(parts, glue):\n"
                    "    text = ''\n"
                    "    first = True\n"
                    "    for part in parts:\n"
                    "        text = part if first else text + glue + part\n"
                    "        first = False\n"
                    "    return text\n"
                ),
                "other.py": "def dump(parts):\n    return list(parts)\n",
            },
            contract=make_contract(
                "tape_of",
                [dict(name="parts", type="list", path=["roll", "parts"]),
                 dict(name="bits", type="list", path=["roll", "bits"]),
                 dict(name="glue", type="str", path=["roll", "glue"]),
                 dict(name="mark", type="str", path=["roll", "mark"])],
                "return join_all on the whole parts list using glue", output_type="str"),
            docs=[{"title": "bags",
                   "content": "join_all(parts, glue) takes the list. bits and mark are decoys."}],
            public=[{"entry": "work.tape_of",
                     "input": {"roll": {"parts": ["p", "q"], "bits": ["z"], "glue": "-", "mark": ":"}},
                     "expected": "p-q"}],
            private=[{"entry": "work.tape_of",
                      "input": {"roll": {"parts": ["a"], "bits": ["b"], "glue": "/", "mark": "."}},
                      "expected": "a"}],
            gold_selection=dict(
                api_id="bags.join_all",
                bindings={"parts": "field.parts", "glue": "field.glue"},
                apply="whole_list",
            ),
        ),
        dict(
            task_id="api_ap_elem_tall", role="element_wise",
            request="Create function tall_ok(item) in work.py using over from gate on each height, not widths. Compare to bar, not cap.",
            files={
                "work.py": echo,
                "gate.py": "def over(n, bar):\n    return n > bar\n",
                "other.py": "def dump(n):\n    return n\n",
            },
            contract=make_contract(
                "tall_ok",
                [dict(name="heights", type="list", path=["bin", "heights"]),
                 dict(name="widths", type="list", path=["bin", "widths"]),
                 dict(name="bar", type="int", path=["bin", "bar"]),
                 dict(name="cap", type="int", path=["bin", "cap"])],
                "return whether every height is over the bar", output_type="bool"),
            docs=[{"title": "gate",
                   "content": "over(n, bar) takes one number. Iterate heights. widths and cap are decoys."}],
            public=[{"entry": "work.tall_ok",
                     "input": {"bin": {"heights": [6, 7], "widths": [1], "bar": 5, "cap": 9}},
                     "expected": True}],
            private=[{"entry": "work.tall_ok",
                      "input": {"bin": {"heights": [5], "widths": [9], "bar": 5, "cap": 1}},
                      "expected": False}],
            gold_selection=dict(
                api_id="gate.over",
                bindings={"n": "elem.heights", "bar": "field.bar"},
                apply="element",
            ),
        ),
        dict(
            task_id="api_ap_elem_wide", role="element_wise",
            request="Create function wide_ok(item) in work.py using wide from check on each plank, not rods. Compare to need, not min.",
            files={
                "work.py": echo,
                "check.py": "def wide(span, need):\n    return span >= need\n",
                "other.py": "def dump(span):\n    return span\n",
            },
            contract=make_contract(
                "wide_ok",
                [dict(name="planks", type="list", path=["kit", "planks"]),
                 dict(name="rods", type="list", path=["kit", "rods"]),
                 dict(name="need", type="int", path=["kit", "need"]),
                 dict(name="min", type="int", path=["kit", "min"])],
                "return whether every plank is at least need", output_type="bool"),
            docs=[{"title": "check",
                   "content": "wide(span, need) takes one number. Iterate planks. rods and min are decoys."}],
            public=[{"entry": "work.wide_ok",
                     "input": {"kit": {"planks": [4, 5], "rods": [1], "need": 4, "min": 9}},
                     "expected": True}],
            private=[{"entry": "work.wide_ok",
                      "input": {"kit": {"planks": [3], "rods": [8], "need": 4, "min": 1}},
                      "expected": False}],
            gold_selection=dict(
                api_id="check.wide",
                bindings={"span": "elem.planks", "need": "field.need"},
                apply="element",
            ),
        ),
        dict(
            task_id="api_ap_ask_limit", role="ambiguous_ask",
            request="Create function ok(item) in work.py using over from gate on each score against a limit.",
            files={
                "work.py": echo,
                "gate.py": "def over(n, bar):\n    return n > bar\n",
                "other.py": "def dump(n):\n    return n\n",
            },
            contract=make_contract(
                "ok",
                [dict(name="scores", type="list", path=["row", "scores"]),
                 dict(name="loft", type="int", path=["row", "loft"]),
                 dict(name="width", type="int", path=["row", "width"])],
                "ask which limit; do not guess loft or width", output_type="bool"),
            docs=[{"title": "gate",
                   "content": "over(n, bar) takes one number. loft and width are both numeric limits."}],
            public=[{"entry": "work.ok",
                     "input": {"row": {"scores": [6, 7], "loft": 5, "width": 8}},
                     "expected": True}],
            private=[{"entry": "work.ok",
                      "input": {"row": {"scores": [6], "loft": 5, "width": 8}},
                      "expected": True}],
            gold_selection=dict(ask=True, question="Which limit, loft or width?"),
        ),
    ]


def all_declared() -> list[dict[str, Any]]:
    rows = apply_api_tasks()
    ids = [row["task_id"] for row in rows]
    roles = {row["role"] for row in rows}
    if len(ids) != 9 or set(ids) & CLOSED:
        raise ValueError("apply_api_ids")
    if roles != {
        "optional_omitted", "optional_supplied", "whole_list",
        "element_wise", "ambiguous_ask",
    }:
        raise ValueError("apply_api_roles")
    return rows
