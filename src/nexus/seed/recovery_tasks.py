"""Authored recovery fixtures. Separate from live model failures.

Family labels, reference functions and private tests stay outside the
controller interface. Do not present fixture outcomes as model competence.
"""
from __future__ import annotations

from typing import Any, Callable


def _name(item: dict) -> str:
    return str(item.get("name") or "").lower()


def _mark(item: dict) -> str:
    return str(item.get("room") or "").lower() + "/" + str(item.get("shelf") or "").lower()


def _pair(item: dict) -> str:
    return str(item.get("left") or "").lower() + "/" + str(item.get("right") or "").lower()


def _ready(item: dict) -> bool:
    return item["score"] >= item["limit"]


def _add1(item: dict) -> int:
    return int(item["n"]) + 1


def _combo(item: dict) -> str:
    return str(item.get("left") or "").lower() + "/" + str(item.get("right") or "").lower()


def _hidden_len(item: dict) -> int:
    return len(str(item.get("text") or ""))


def _task(
    task_id: str,
    split: str,
    family: str,
    request: str,
    files: dict[str, str],
    public: list[dict[str, Any]],
    private: list[dict[str, Any]],
    *,
    docs: list[dict[str, str]] | None = None,
    teacher_available: bool = False,
    reference: Callable[[Any], Any] | None = None,
    correct_stop: bool = False,
    identifiable: bool = True,
) -> dict[str, Any]:
    return dict(
        task_id=task_id,
        split=split,
        family=family,
        request=request,
        files=files,
        public=public,
        private=private,
        docs=list(docs or []),
        teacher_available=bool(teacher_available),
        reference=reference,
        correct_stop=correct_stop,
        identifiable=identifiable,
        origin="authored_fixture",
    )


def catalogue() -> list[dict[str, Any]]:
    return [
        _task(
            "src_schema_a", "source", "schema_key",
            "Create function name_of(item) that returns the name field in lowercase.",
            {"tag.py": "def name_of(item):\n    return item.lower()\n"},
            [{"entry": "tag.name_of", "input": {"name": "Ada"}, "expected": "ada"}],
            [{"entry": "tag.name_of", "input": {"name": "Lin"}, "expected": "lin"}],
            reference=_name,
        ),
        _task(
            "src_schema_b", "source", "schema_key",
            "Create function title_of(item) that returns the title field in lowercase.",
            {"book.py": "def title_of(item):\n    return item.upper()\n"},
            [{"entry": "book.title_of", "input": {"title": "Seed"}, "expected": "seed"}],
            [{"entry": "book.title_of", "input": {"title": "Nexus"}, "expected": "nexus"}],
            reference=lambda item: str(item.get("title") or "").lower(),
        ),
        _task(
            "src_missing_a", "source", "missing_value",
            "Create function mark(item) that returns room and shelf in lowercase joined by one slash.",
            {"shelf.py": "def mark(item):\n    return item['room'].lower() + '/' + item['shelf'].lower()\n"},
            [
                {"entry": "shelf.mark", "input": {"room": "East", "shelf": "B2"}, "expected": "east/b2"},
                {"entry": "shelf.mark", "input": {"shelf": "B2"}, "expected": "/b2"},
            ],
            [
                {"entry": "shelf.mark", "input": {"room": "West", "shelf": "C9"}, "expected": "west/c9"},
                {"entry": "shelf.mark", "input": {"room": "West"}, "expected": "west/"},
            ],
            reference=_mark,
        ),
        _task(
            "src_api_a", "source", "api_docs",
            "Create function pair(item) that joins left and right in lowercase using the project helper.",
            {"pair.py": "def join_parts(left, right):\n    return left + '/' + right\n\ndef pair(item):\n    return item['left'] + ':' + item['right']\n"},
            [{"entry": "pair.pair", "input": {"left": "On", "right": "Off"}, "expected": "on/off"}],
            [{"entry": "pair.pair", "input": {"left": "In", "right": "Out"}, "expected": "in/out"}],
            docs=[{"doc_id": "join-api", "title": "join_parts",
                   "content": "Call join_parts(left, right). It inserts one slash. Lowercase both sides first."}],
            reference=_pair,
        ),
        _task(
            "src_assume_a", "source", "wrong_assumption",
            "Create function ready(item) that is true when score meets the limit.",
            {"gate.py": "def ready(item):\n    return False\n"},
            [{"entry": "gate.ready", "input": {"score": 4, "limit": 2}, "expected": True}],
            [{"entry": "gate.ready", "input": {"score": 3, "limit": 3}, "expected": True}],
            teacher_available=True,
            reference=_ready,
        ),
        _task(
            "src_multi_a", "source", "multistep",
            "Create function combo(item) that lowercases left and right and joins them with the helper.",
            {"mix.py": "def join_parts(left, right):\n    return left + '/' + right\n\ndef combo(item):\n    return item.lower()\n"},
            [{"entry": "mix.combo", "input": {"left": "Up", "right": "Down"}, "expected": "up/down"}],
            [{"entry": "mix.combo", "input": {"left": "Yes", "right": "No"}, "expected": "yes/no"}],
            docs=[{"doc_id": "combo-api", "title": "join_parts",
                   "content": "Use join_parts on the left and right fields after lowercasing."}],
            reference=_combo,
        ),
        _task(
            "src_immediate_a", "source", "immediate_ok",
            "Create function add1(item) that returns n plus one.",
            {"inc.py": "def add1(item):\n    return item['n']\n"},
            [{"entry": "inc.add1", "input": {"n": 3}, "expected": 4}],
            [{"entry": "inc.add1", "input": {"n": 10}, "expected": 11}],
            reference=_add1,
        ),
        _task(
            "src_stop_a", "source", "stop_appropriate",
            "Create function hidden(item) that scores the text field.",
            {"hid.py": "def hidden(item):\n    return 0\n"},
            [{"entry": "hid.hidden", "input": {"text": "ab"}, "expected": 2}],
            [{"entry": "hid.hidden", "input": {"text": "xyz"}, "expected": 3}],
            teacher_available=False,
            reference=_hidden_len,
            correct_stop=True,
            identifiable=False,
        ),
        _task(
            "dev_schema_c", "development", "schema_key",
            "Create function label_of(item) that returns the label field in lowercase.",
            {"lab.py": "def label_of(item):\n    return str(item)\n"},
            [{"entry": "lab.label_of", "input": {"label": "Red"}, "expected": "red"}],
            [{"entry": "lab.label_of", "input": {"label": "Blue"}, "expected": "blue"}],
            reference=lambda item: str(item.get("label") or "").lower(),
        ),
        _task(
            "dev_missing_b", "development", "missing_value",
            "Create function place(item) that returns hall and bin in lowercase joined by one slash.",
            {"bin.py": "def place(item):\n    return item['hall'].lower() + '/' + item['bin'].lower()\n"},
            [
                {"entry": "bin.place", "input": {"hall": "North", "bin": "A1"}, "expected": "north/a1"},
                {"entry": "bin.place", "input": {"bin": "A1"}, "expected": "/a1"},
            ],
            [
                {"entry": "bin.place", "input": {"hall": "South", "bin": "D4"}, "expected": "south/d4"},
                {"entry": "bin.place", "input": {"hall": "South"}, "expected": "south/"},
            ],
            reference=lambda item: str(item.get("hall") or "").lower() + "/" + str(item.get("bin") or "").lower(),
        ),
        _task(
            "dev_api_b", "development", "api_docs",
            "Create function glue(item) that joins first and second in lowercase using the project helper.",
            {"glue.py": "def join_parts(left, right):\n    return left + '/' + right\n\ndef glue(item):\n    return item['first'] + '-' + item['second']\n"},
            [{"entry": "glue.glue", "input": {"first": "Hi", "second": "Lo"}, "expected": "hi/lo"}],
            [{"entry": "glue.glue", "input": {"first": "Old", "second": "New"}, "expected": "old/new"}],
            docs=[{"doc_id": "glue-api", "title": "join_parts",
                   "content": "Call join_parts(first, second) after lowercasing. The helper inserts a slash."}],
            reference=lambda item: str(item.get("first") or "").lower() + "/" + str(item.get("second") or "").lower(),
        ),
        _task(
            "dev_multi_b", "development", "multistep",
            "Create function bundle(item) that lowercases head and tail and joins them with the helper.",
            {"bun.py": "def join_parts(left, right):\n    return left + '/' + right\n\ndef bundle(item):\n    return item['head']\n"},
            [{"entry": "bun.bundle", "input": {"head": "Sun", "tail": "Moon"}, "expected": "sun/moon"}],
            [{"entry": "bun.bundle", "input": {"head": "Day", "tail": "Night"}, "expected": "day/night"}],
            docs=[{"doc_id": "bun-api", "title": "join_parts",
                   "content": "Use join_parts on the head and tail fields after lowercasing."}],
            reference=lambda item: str(item.get("head") or "").lower() + "/" + str(item.get("tail") or "").lower(),
        ),
        _task(
            "dev_immediate_b", "development", "immediate_ok",
            "Create function add1(item) that returns n plus one.",
            {"inc2.py": "def add1(item):\n    return item['n'] - 1\n"},
            [{"entry": "inc2.add1", "input": {"n": 5}, "expected": 6}],
            [{"entry": "inc2.add1", "input": {"n": 8}, "expected": 9}],
            reference=_add1,
        ),
        _task(
            "dev_misleading_a", "development", "misleading_cue",
            "Create function ready(item) that is true when score meets the limit.",
            {"cue.py": "def ready(item):\n    return False\n"},
            [{"entry": "cue.ready", "input": {"score": 9, "limit": 1}, "expected": True}],
            [{"entry": "cue.ready", "input": {"score": 2, "limit": 2}, "expected": True}],
            teacher_available=True,
            reference=_ready,
        ),
        _task(
            "ret_schema_a", "retention", "schema_key",
            "Create function name_of(item) that returns the name field in lowercase.",
            {"tag.py": "def name_of(item):\n    return item.lower()\n"},
            [{"entry": "tag.name_of", "input": {"name": "Ada"}, "expected": "ada"}],
            [{"entry": "tag.name_of", "input": {"name": "Lin"}, "expected": "lin"}],
            reference=_name,
        ),
        _task(
            "ret_immediate_a", "retention", "immediate_ok",
            "Create function add1(item) that returns n plus one.",
            {"inc.py": "def add1(item):\n    return item['n']\n"},
            [{"entry": "inc.add1", "input": {"n": 3}, "expected": 4}],
            [{"entry": "inc.add1", "input": {"n": 10}, "expected": 11}],
            reference=_add1,
        ),
        _task(
            "assess_comp_schema_api", "assessment", "excluded_composition",
            "Create function stamp(item) that lowercases code and mark and joins them with the helper.",
            {"stamp.py": "def join_parts(left, right):\n    return left + '/' + right\n\ndef stamp(item):\n    return item.lower()\n"},
            [{"entry": "stamp.stamp", "input": {"code": "Ok", "mark": "Go"}, "expected": "ok/go"}],
            [{"entry": "stamp.stamp", "input": {"code": "No", "mark": "Yes"}, "expected": "no/yes"}],
            docs=[{"doc_id": "stamp-api", "title": "join_parts",
                   "content": "Use join_parts on the code and mark fields after lowercasing."}],
            reference=lambda item: str(item.get("code") or "").lower() + "/" + str(item.get("mark") or "").lower(),
        ),
        _task(
            "assess_family_order", "assessment", "excluded_family",
            "Create function order(item) that returns values sorted ascending.",
            {"ord.py": "def order(item):\n    return item['values']\n"},
            [{"entry": "ord.order", "input": {"values": [3, 1, 2]}, "expected": [1, 2, 3]}],
            [{"entry": "ord.order", "input": {"values": [9, 0, 4]}, "expected": [0, 4, 9]}],
            reference=lambda item: sorted(item["values"]),
        ),
        _task(
            "assess_assume_b", "assessment", "wrong_assumption",
            "Create function ready(item) that is true when score meets the limit.",
            {"gate2.py": "def ready(item):\n    return False\n"},
            [{"entry": "gate2.ready", "input": {"score": 8, "limit": 3}, "expected": True}],
            [{"entry": "gate2.ready", "input": {"score": 5, "limit": 5}, "expected": True}],
            teacher_available=True,
            reference=_ready,
        ),
        _task(
            "assess_stop_b", "assessment", "stop_appropriate",
            "Create function hidden(item) that scores the text field.",
            {"hid2.py": "def hidden(item):\n    return 0\n"},
            [{"entry": "hid2.hidden", "input": {"text": "q"}, "expected": 1}],
            [{"entry": "hid2.hidden", "input": {"text": "abcd"}, "expected": 4}],
            teacher_available=False,
            reference=_hidden_len,
            correct_stop=True,
            identifiable=False,
        ),
    ]


def tasks_for(split: str) -> list[dict[str, Any]]:
    return [row for row in catalogue() if row["split"] == split]


def public_task_view(task: dict[str, Any]) -> dict[str, Any]:
    """Controller view: no family, private tests, reference, or hidden labels."""
    return dict(
        request=task["request"],
        files=dict(task["files"]),
        public=list(task["public"]),
        docs_available=bool(task.get("docs")),
        teacher_available=bool(task.get("teacher_available")),
        origin=task["origin"],
    )
