"""Parameterized repair-schema memory. One success is not a 100% success rate.

Store the trigger, AST transformation, bindings, preconditions, supporting
tests, counterexamples and failure-to-fix traces. Acquisition is charged.
Families are chosen before scoring. Persist to JSON. Compare with ordinary
exact caches and templates. Do not select assessment tasks because a baseline
already failed them.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PREDECLARED_FAMILIES = (
    "comparison_boundary",
    "missing_function",
    "null_default",
)

COMPARE_OPS = {
    "Lt": ast.Lt,
    "LtE": ast.LtE,
    "Gt": ast.Gt,
    "GtE": ast.GtE,
    "Eq": ast.Eq,
    "NotEq": ast.NotEq,
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


INCLUSIVE_CUES = (
    "allow n equal",
    "allow width equal",
    "allow equality",
    "inclusive",
    "at least",
    "or equal",
    "including the",
    "still allowed",
    "equal to the maximum",
    "equal to the bound",
    "equal to the limit",
)
EXCLUSIVE_CUES = (
    "strictly smaller",
    "strictly less",
    "strictly below",
    "exclusive",
    "reject values equal",
    "only strictly",
    "not including",
    "below the cutoff",
)


@dataclass
class RepairProposal:
    """A retrieved repair is a proposal. Applying it is a later decision."""

    decision: str
    reason: str
    requirement: str
    schema_id: str | None = None
    files: dict[str, str] | None = None
    question: str | None = None
    used_private_tests: bool = False


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
    bindings: dict[str, Any] = field(default_factory=dict)
    preconditions: dict[str, Any] = field(default_factory=dict)


class RepairSchemaStore:
    def __init__(self) -> None:
        self.schemas: dict[str, RepairSchema] = {}
        self.acquisition_events: list[dict[str, Any]] = []

    def remember(self, schema: RepairSchema, charged: bool = True) -> None:
        if schema.family not in PREDECLARED_FAMILIES:
            raise ValueError(f"undeclared_family:{schema.family}")
        self.schemas[schema.schema_id] = copy.deepcopy(schema)
        if charged:
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
        for schema in self.schemas.values():
            if schema.family == family and schema.transformation not in {"none", "single_file_replace"}:
                return copy.deepcopy(schema)
        return None

    def apply(self, schema: RepairSchema, files: dict[str, str]) -> dict[str, str] | None:
        if schema.transformation == "compare_op_swap":
            return apply_compare_op_swap(files, schema)
        if schema.transformation == "or_to_explicit_none":
            return apply_or_to_explicit_none(files, schema)
        return apply_exact_text(files, schema)

    def save(self, directory: Path) -> Path:
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        for schema in self.schemas.values():
            (root / f"{schema.schema_id}.json").write_text(
                json.dumps(asdict(schema), indent=2, default=str), encoding="utf-8",
            )
        return root

    @classmethod
    def load(cls, directory: Path) -> "RepairSchemaStore":
        store = cls()
        root = Path(directory)
        if not root.is_dir():
            return store
        for path in sorted(root.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            store.remember(RepairSchema(**data), charged=False)
        return store


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


def public_equality_signal(public_tests: list[dict[str, Any]]) -> str | None:
    """Use public tests only. Equal numeric fields plus expected True/False."""
    for case in public_tests or []:
        inp = case.get("input")
        if type(inp) is not dict:
            continue
        nums = [
            value for value in inp.values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        if len(nums) >= 2 and len(set(nums)) == 1:
            if case.get("expected") is True:
                return "inclusive"
            if case.get("expected") is False:
                return "exclusive"
    return None


def classify_boundary_requirement(
    request: str,
    public_tests: list[dict[str, Any]],
    private_tests: list[dict[str, Any]] | None = None,
) -> str:
    """Inclusive and exclusive must differ. Private tests are ignored."""
    del private_tests
    text = (request or "").lower()
    from_text = None
    if any(cue in text for cue in EXCLUSIVE_CUES):
        from_text = "exclusive"
    elif any(cue in text for cue in INCLUSIVE_CUES):
        from_text = "inclusive"
    from_public = public_equality_signal(public_tests)
    if from_text and from_public and from_text != from_public:
        return "ambiguous"
    return from_text or from_public or "ambiguous"


def propose_retrieved_repair(
    schema: RepairSchema | None,
    request: str,
    files: dict[str, str],
    public_tests: list[dict[str, Any]],
    private_tests: list[dict[str, Any]] | None = None,
) -> RepairProposal:
    """Check the current requirement and public tests before applying."""
    del private_tests
    if schema is None:
        return RepairProposal("abstain", "no_schema", "other")
    family = infer_family(request, public_tests)
    if family and family != schema.family:
        return RepairProposal(
            "abstain", "family_mismatch", "other", schema.schema_id,
        )
    if schema.transformation == "compare_op_swap":
        requirement = classify_boundary_requirement(request, public_tests)
        from_op = schema.applicability.get("from_op") or schema.bindings.get("from_op")
        to_op = schema.applicability.get("to_op") or schema.bindings.get("to_op")
        inclusive_transform = from_op == "Lt" and to_op == "LtE"
        if requirement == "inclusive":
            if not inclusive_transform:
                return RepairProposal(
                    "refuse", "schema_direction_mismatch", requirement, schema.schema_id,
                )
            patched = apply_compare_op_swap(files, schema)
            if patched is None:
                return RepairProposal(
                    "abstain", "transform_not_applicable", requirement, schema.schema_id,
                )
            return RepairProposal(
                "apply", "requirement_inclusive", requirement, schema.schema_id, patched,
            )
        if requirement == "exclusive":
            return RepairProposal(
                "refuse", "requirement_exclusive_blocks_inclusive_repair",
                requirement, schema.schema_id,
            )
        return RepairProposal(
            "ask", "requirement_ambiguous", "ambiguous", schema.schema_id,
            question="Should values equal to the bound pass (inclusive) or fail (exclusive)?",
        )
    patched = RepairSchemaStore().apply(schema, files)
    if patched is None:
        return RepairProposal(
            "abstain", "transform_not_applicable", family or "other", schema.schema_id,
        )
    return RepairProposal(
        "apply", "family_matched", family or "other", schema.schema_id, patched,
    )


def infer_family(request: str, public_tests: list[dict[str, Any]]) -> str | None:
    text = request.lower()
    if any(word in text for word in ("create function", "add function", "implement ", "write function")):
        return "missing_function"
    if any(word in text for word in ("equal to", "inclusive", "at least", "greater or equal", "window", "boundary")):
        return "comparison_boundary"
    if any(word in text for word in ("none", "null", "missing", "default")):
        return "null_default"
    entries = " ".join(str(c.get("entry", "")) for c in public_tests)
    if "midpoint" in entries or "label" in entries or "title" in entries:
        return "missing_function"
    return None


def _compare_ops(tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            found.append(type(node.ops[0]).__name__)
    return found


def infer_ast_transform(original: dict[str, str], patched: dict[str, str]) -> dict[str, Any] | None:
    for path in sorted(set(original) | set(patched)):
        if not path.endswith(".py"):
            continue
        try:
            old_tree = ast.parse(original.get(path, ""))
            new_tree = ast.parse(patched.get(path, ""))
        except SyntaxError:
            continue
        old_ops, new_ops = _compare_ops(old_tree), _compare_ops(new_tree)
        if len(old_ops) == 1 and len(new_ops) == 1 and old_ops[0] != new_ops[0]:
            return {
                "kind": "compare_op_swap",
                "from_op": old_ops[0],
                "to_op": new_ops[0],
                "require_unique_matching_compare": True,
            }
        if _has_or_default(old_tree) and _has_explicit_none(new_tree):
            return {"kind": "or_to_explicit_none", "require_unique_or": True}
    return None


def _has_or_default(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and len(node.values) == 2:
            return True
    return False


def _has_explicit_none(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.IfExp) and isinstance(node.test, ast.Compare):
            if any(isinstance(op, ast.Is) for op in node.test.ops):
                return True
    return False


def apply_compare_op_swap(files: dict[str, str], schema: RepairSchema) -> dict[str, str] | None:
    from_op = schema.applicability.get("from_op") or schema.bindings.get("from_op")
    to_op = schema.applicability.get("to_op") or schema.bindings.get("to_op")
    target = COMPARE_OPS.get(str(to_op))
    if from_op not in COMPARE_OPS or target is None:
        return None
    require_unique = schema.preconditions.get(
        "require_unique_matching_compare",
        schema.applicability.get("require_unique_matching_compare", True),
    )
    patched = dict(files)
    applied = 0
    for path, source in list(patched.items()):
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        matches = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Compare) and len(node.ops) == 1
            and type(node.ops[0]).__name__ == from_op
        ]
        if require_unique and len(matches) != 1:
            continue
        if not matches:
            continue
        for node in matches:
            node.ops = [target()]
        ast.fix_missing_locations(tree)
        patched[path] = ast.unparse(tree) + "\n"
        applied += 1
    return patched if applied else None


def apply_or_to_explicit_none(files: dict[str, str], schema: RepairSchema) -> dict[str, str] | None:
    patched = dict(files)
    applied = 0
    for path, source in list(patched.items()):
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        changed = False
        for node in ast.walk(tree):
            if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and len(node.values) == 2):
                continue
            if schema.preconditions.get("require_unique_or", True):
                ors = [n for n in ast.walk(tree) if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)]
                if len(ors) != 1:
                    continue
            replacement = ast.IfExp(
                test=ast.Compare(left=copy.deepcopy(node.values[0]), ops=[ast.Is()],
                                 comparators=[ast.Constant(value=None)]),
                body=copy.deepcopy(node.values[1]),
                orelse=copy.deepcopy(node.values[0]),
            )
            for parent in ast.walk(tree):
                for field_name, field_val in ast.iter_fields(parent):
                    if field_val is node:
                        setattr(parent, field_name, replacement)
                        changed = True
                    elif isinstance(field_val, list):
                        for idx, item in enumerate(field_val):
                            if item is node:
                                field_val[idx] = replacement
                                changed = True
        if changed:
            ast.fix_missing_locations(tree)
            patched[path] = ast.unparse(tree) + "\n"
            applied += 1
    return patched if applied else None


def apply_exact_text(files: dict[str, str], schema: RepairSchema) -> dict[str, str] | None:
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


def capture_from_success(
    family: str,
    request: str,
    original: dict[str, str],
    patched: dict[str, str],
    public_tests: list[dict[str, Any]],
    cost: dict[str, Any],
) -> RepairSchema | None:
    inferred = infer_ast_transform(original, patched)
    if inferred is not None:
        return RepairSchema(
            schema_id=digest([family, inferred])[:16],
            family=family,
            trigger=request,
            transformation=inferred["kind"],
            applicability=dict(inferred),
            bindings={k: inferred[k] for k in inferred if k.endswith("_op") or k == "kind"},
            preconditions={k: inferred[k] for k in inferred if k.startswith("require_")},
            supporting_tests=list(public_tests),
            counterexamples=[],
            acquisition_cost=dict(cost),
        )
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


def ordinary_template_apply(family: str, files: dict[str, str]) -> dict[str, str] | None:
    """Strong simple baseline: a generic family template, no source acquisition."""
    if family == "comparison_boundary":
        schema = RepairSchema(
            schema_id="template_lt_to_lte",
            family=family,
            trigger="ordinary_template",
            transformation="compare_op_swap",
            applicability={"from_op": "Lt", "to_op": "LtE", "require_unique_matching_compare": True},
            bindings={"from_op": "Lt", "to_op": "LtE"},
            preconditions={"require_unique_matching_compare": True},
        )
        return apply_compare_op_swap(files, schema)
    if family == "null_default":
        schema = RepairSchema(
            schema_id="template_or_to_none",
            family=family,
            trigger="ordinary_template",
            transformation="or_to_explicit_none",
            applicability={"kind": "or_to_explicit_none"},
            preconditions={"require_unique_or": True},
        )
        return apply_or_to_explicit_none(files, schema)
    return None


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
