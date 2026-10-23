"""Repair-schema memory. One success is not a 100% success rate.

Store the trigger, transformation, applicability conditions, supporting tests,
counterexamples and failure-to-fix traces. Acquisition is charged. Memory may
save time or tokens when accuracy ties.

Families are chosen before scoring. Patterns are acquired on source tasks, then
assessed on new instances against ordinary templates and exact caches. Do not
select assessment tasks because a baseline already failed them.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any


PREDECLARED_FAMILIES = (
    "comparison_boundary",
    "missing_function",
    "null_default",
)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class RepairSchema:
    schema_id: str
    family: str
    trigger: str
    transformation: str
    applicability: dict[str, Any]
    supporting_tests: list[dict[str, Any]] = field(default_factory=list)
    counterexamples: list[dict[str, Any]] = field(default_factory=list)
    failure_to_fix: list[dict[str, Any]] = field(default_factory=list)
    acquisition_cost: dict[str, Any] = field(default_factory=dict)


class RepairSchemaStore:
    def __init__(self) -> None:
        self.schemas: dict[str, RepairSchema] = {}
        self.acquisition_events: list[dict[str, Any]] = []

    def remember(self, schema: RepairSchema) -> None:
        if schema.family not in PREDECLARED_FAMILIES:
            raise ValueError(f"undeclared_family:{schema.family}")
        self.schemas[schema.schema_id] = copy.deepcopy(schema)
        self.acquisition_events.append({
            "schema_id": schema.schema_id,
            "family": schema.family,
            "charged": True,
            "cost": dict(schema.acquisition_cost),
        })

    def remember_failure(self, family: str, trigger: str, trace: dict[str, Any]) -> None:
        ident = digest(["fail", family, trigger, trace])[:16]
        existing = self.schemas.get(ident)
        if existing is None:
            self.remember(RepairSchema(
                schema_id=ident,
                family=family,
                trigger=trigger,
                transformation="none",
                applicability={"source": "failure_to_fix"},
                failure_to_fix=[trace],
                acquisition_cost=trace.get("cost") or {"wall_s": 0},
            ))
            return
        existing.failure_to_fix.append(trace)

    def lookup(self, family: str, trigger: str) -> RepairSchema | None:
        for schema in self.schemas.values():
            if schema.family == family and schema.trigger == trigger and schema.transformation != "none":
                return copy.deepcopy(schema)
        return None

    def apply(self, schema: RepairSchema, files: dict[str, str]) -> dict[str, str] | None:
        """Replay a stored textual transformation. Never invent a midpoint body."""
        old = schema.applicability.get("old_text")
        new = schema.applicability.get("new_text")
        path = schema.applicability.get("path")
        if not path or path not in files or type(old) is not str or type(new) is not str:
            return None
        if files[path].count(old) != 1:
            return None
        patched = dict(files)
        patched[path] = files[path].replace(old, new, 1)
        return patched


class OrdinaryExactCache:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, str]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, request: str, files: dict[str, str]) -> dict[str, str] | None:
        key = digest([request, files])
        row = self.store.get(key)
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return copy.deepcopy(row)

    def put(self, request: str, files: dict[str, str], patched: dict[str, str]) -> None:
        self.store[digest([request, files])] = copy.deepcopy(patched)


def infer_family(request: str, public_tests: list[dict[str, Any]]) -> str | None:
    text = request.lower()
    if any(word in text for word in ("midpoint", "create function", "add function", "implement ")):
        return "missing_function"
    if any(word in text for word in ("equal to", "inclusive", "at least", "greater or equal", "window")):
        return "comparison_boundary"
    if any(word in text for word in ("none", "null", "missing", "default")):
        return "null_default"
    entries = " ".join(str(c.get("entry", "")) for c in public_tests)
    if "midpoint" in entries:
        return "missing_function"
    return None


def capture_from_success(
    family: str,
    request: str,
    original: dict[str, str],
    patched: dict[str, str],
    public_tests: list[dict[str, Any]],
    cost: dict[str, Any],
) -> RepairSchema | None:
    diffs = []
    for path in sorted(set(original) | set(patched)):
        old, new = original.get(path, ""), patched.get(path, "")
        if old != new:
            diffs.append((path, old, new))
    if len(diffs) != 1:
        return None
    path, old, new = diffs[0]
    return RepairSchema(
        schema_id=digest([family, request, path, old, new])[:16],
        family=family,
        trigger=request,
        transformation="single_file_replace",
        applicability={"path": path, "old_text": old, "new_text": new},
        supporting_tests=list(public_tests),
        acquisition_cost=dict(cost),
    )


def transfer_success_rate(outcomes: list[bool]) -> dict[str, Any]:
    """Never report 100% from a single success."""
    n = len(outcomes)
    wins = sum(1 for ok in outcomes if ok)
    return {
        "n": n,
        "successes": wins,
        "rate": None if n < 2 else wins / n,
        "one_success_is_not_100_percent": True,
    }


def timed(fn, *args, **kwargs):
    started = time.perf_counter()
    value = fn(*args, **kwargs)
    return value, {"wall_s": round(time.perf_counter() - started, 6)}


def as_record(schema: RepairSchema) -> dict[str, Any]:
    return asdict(schema)
