"""Bounded, pure, typed quotient synthesis; no historical experiment imports.

The older ObservationalQuotientWitnessEngine owns catalog-level quotienting.
This module adds recursive contextual signatures, not another agent/memory.
All certificates refer only to the supplied finite grammar and positive bound.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from itertools import product
import math
import time
from typing import Any, Callable, Iterable

from nexus.evolution1.catalogue import digest


MASS_PRESERVING = "MASS_PRESERVING"
MASS_CONTRACTIVE = "MASS_CONTRACTIVE"
MASS_EXPANSIVE = "MASS_EXPANSIVE"
MULTISET_PRESERVING_PERMUTATION = "MULTISET_PRESERVING_PERMUTATION"
LOCUS_PRESERVING_MAP = "LOCUS_PRESERVING_MAP"


def structural_mass(value):
    """Signed/count mass used only by last-step conservation filters."""
    if type(value) is int:
        return value
    if type(value) is bool:
        return int(value)
    if isinstance(value, (str, tuple, list, dict)):
        return len(value)
    if type(value) is float and math.isfinite(value):
        return int(value)
    return 0


def _tokens_of(value):
    if isinstance(value, dict):
        return tuple(sorted((freeze(k), freeze(v)) for k, v in value.items()))
    if isinstance(value, (tuple, list, str)):
        return tuple(freeze(v) for v in value)
    return (freeze(value),)


def quantum_multiset_hash(value):
    items = tuple(sorted(Counter(_tokens_of(value)).items(), key=repr))
    return int(digest(items)[:16], 16)


def locus_mask(value):
    tokens = _tokens_of(value)
    mask = 0
    for i, token in enumerate(tokens[:64]):
        mask |= ((int(digest(token)[:2], 16) & 1) << (i % 64))
    return mask


def quantum_bloom_64(value):
    bloom = 0
    for token in _tokens_of(value):
        h = int(digest(token)[:16], 16)
        bloom |= 1 << (h % 64)
        bloom |= 1 << ((h // 64) % 64)
    return bloom & ((1 << 64) - 1)


def atomic_signature(value):
    return (structural_mass(value), locus_mask(value), quantum_multiset_hash(value), quantum_bloom_64(value))


class NoetherConservationGate:
    """Sound last-step (`b_rem == 1`) conservation filter; never a uniqueness oracle."""

    def __init__(self):
        self.tags = {}

    def fingerprint_operators(self, operators, domain, *, meter=None):
        self.tags = {}
        values = tuple(domain)
        if meter is not None and operators:
            meter.charge("noether_fingerprint_work_units")
        for op in operators:
            if len(op.inputs) != 1:
                self.tags[op.name] = frozenset()
                continue
            pairs = []
            for value in values:
                try:
                    # O(1) classification only; last-step skips save full metered eval.
                    out = op.fn(value)
                except Exception:
                    pairs = []
                    break
                pairs.append((value, out))
            if not pairs:
                self.tags[op.name] = frozenset()
                continue
            tags = set()
            masses = [(structural_mass(a), structural_mass(b)) for a, b in pairs]
            if all(a == b for a, b in masses):
                tags.add(MASS_PRESERVING)
            if all(b < a for a, b in masses):
                tags.add(MASS_CONTRACTIVE)
            if all(b > a for a, b in masses):
                tags.add(MASS_EXPANSIVE)
            if all(quantum_multiset_hash(a) == quantum_multiset_hash(b) for a, b in pairs):
                tags.add(MULTISET_PRESERVING_PERMUTATION)
            if all(locus_mask(a) == locus_mask(b) for a, b in pairs):
                tags.add(LOCUS_PRESERVING_MAP)
            self.tags[op.name] = frozenset(tags)
        return dict(self.tags)

    def should_skip_last_step(self, op, child_public, target_public):
        if op.name not in self.tags or len(child_public) != len(target_public):
            return False
        tags = self.tags[op.name]
        for src, dst in zip(child_public, target_public):
            mv, my = structural_mass(src), structural_mass(dst)
            if MASS_PRESERVING in tags and mv != my:
                return True
            if MASS_CONTRACTIVE in tags and mv < my:
                return True
            if MASS_EXPANSIVE in tags and mv >= my:
                return True
            if (MULTISET_PRESERVING_PERMUTATION in tags
                    and quantum_multiset_hash(src) != quantum_multiset_hash(dst)):
                return True
        return False

    def last_step_operator_order(self, operators, child_public, target_public):
        def rank(op):
            permute = 0
            if MULTISET_PRESERVING_PERMUTATION in self.tags.get(op.name, ()):
                if any(quantum_multiset_hash(a) == quantum_multiset_hash(b) and freeze(a) != freeze(b)
                       for a, b in zip(child_public, target_public)):
                    permute = -1
            return (permute, op.name)
        return tuple(sorted(operators, key=rank))


class _Missing:
    def __deepcopy__(self, memo):
        return self


MISSING_KEY = _Missing()


def freeze(value):
    """Typed canonical key: in particular False != 0 and missing != None."""
    if value is MISSING_KEY:
        return ("missing",)
    if value is None:
        return ("none",)
    if type(value) in (bool, int, str):
        return (type(value).__name__, value)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("nonfinite value")
        return ("float", value.hex())
    if type(value) in (tuple, list):
        return (type(value).__name__, tuple(freeze(v) for v in value))
    if type(value) is dict:
        return ("dict", tuple(sorted(((freeze(k), freeze(v)) for k, v in value.items()), key=repr)))
    raise TypeError(f"unsupported semantic value: {type(value).__name__}")


def unfreeze(key):
    """Strict JSON-safe counterpart for replay; no pickle/eval/import payloads."""
    if not isinstance(key, (tuple, list)) or not key:
        raise ValueError("typed semantic encoding required")
    tag = key[0]
    if tag in ("missing", "none") and len(key) == 1:
        return MISSING_KEY if tag == "missing" else None
    if len(key) != 2:
        raise ValueError("invalid semantic encoding")
    data = key[1]
    if tag in ("bool", "int", "str"):
        expected = {"bool": bool, "int": int, "str": str}[tag]
        if type(data) is not expected:
            raise ValueError("semantic type mismatch")
        return data
    if tag == "float":
        result = float.fromhex(data)
        if not math.isfinite(result):
            raise ValueError("nonfinite semantic value")
        return result
    if tag in ("list", "tuple"):
        values = [unfreeze(v) for v in data]
        return values if tag == "list" else tuple(values)
    if tag == "dict":
        pairs = [(unfreeze(k), unfreeze(v)) for k, v in data]
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("duplicate dictionary key")
        return result
    raise ValueError("unknown semantic encoding")


def expression_wire(expr):
    return dict(kind=expr.kind, sort=expr.sort, value=freeze(expr.value),
                children=[expression_wire(c) for c in expr.children])


def expression_from_wire(value, *, depth=0):
    if depth > 32 or type(value) is not dict or set(value) != {"kind", "sort", "value", "children"}:
        raise ValueError("bounded typed AST encoding required")
    if type(value["kind"]) is not str or type(value["sort"]) is not str or type(value["children"]) is not list or len(value["children"]) > 8:
        raise ValueError("invalid AST fields")
    return Expr(value["kind"], value["sort"], unfreeze(value["value"]),
                tuple(expression_from_wire(c, depth=depth+1) for c in value["children"]))


class WorkExhausted(RuntimeError):
    pass


@dataclass
class WorkMeter:
    limit: int = 1_000_000
    wall_limit: float = 10.0
    counts: Counter = field(default_factory=Counter)
    started: float = field(default_factory=time.monotonic)

    def __post_init__(self):
        if type(self.limit) is not int or self.limit < 0 or not 0 < self.wall_limit <= 900:
            raise ValueError("bounded work and wall limits required")

    @property
    def total(self):
        return sum(self.counts.values())

    def charge(self, category="search_work_units", n=1):
        if type(n) is not int or n < 0:
            raise ValueError("nonnegative integral work")
        if self.total + n > self.limit or time.monotonic() - self.started > self.wall_limit:
            raise WorkExhausted("work/wall cap reached; no completeness certificate")
        self.counts[category] += n


@dataclass(frozen=True)
class Operator:
    name: str
    inputs: tuple[str, ...]
    output: str
    fn: Callable = field(compare=False, repr=False)
    cost: int = 1

    def __post_init__(self):
        if not self.name.startswith("op_") or not self.inputs or type(self.cost) is not int or self.cost <= 0:
            raise ValueError("anonymous typed positive-cost operator required")

    def call(self, args, meter, category):
        meter.charge(category, self.cost)
        copied = deepcopy(tuple(args))
        before = freeze(copied)
        result = self.fn(*copied)
        if freeze(copied) != before:
            raise ValueError("operator mutated input")
        freeze(result)
        return result


@dataclass(frozen=True)
class Expr:
    kind: str
    sort: str
    value: Any = None
    children: tuple[Expr, ...] = ()

    def key(self):
        return (self.kind, self.sort, freeze(self.value), tuple(c.key() for c in self.children))


def variable(sort):
    return Expr("var", sort)


def constant(sort, value):
    return Expr("const", sort, deepcopy(value))


def apply(op: Operator, *children):
    if tuple(c.sort for c in children) != op.inputs:
        raise ValueError("ill-typed application")
    return Expr("apply", op.output, op.name, tuple(children))


def typed_hole(sort, index=0):
    if type(index) is not int or index not in (0, 1):
        raise ValueError("one or two typed skill parameters required")
    return Expr("hole", sort, index)


def substitute_holes(body, arguments, *, meter=None):
    """Capture-free AST substitution; never executes generated Python code."""
    if meter is not None:
        meter.charge("skill_instantiation_work_units")
    def walk(node):
        if node.kind == "hole":
            if type(node.value) is not int or not 0 <= node.value < len(arguments):
                raise ValueError("unbound skill hole")
            argument = arguments[node.value]
            if argument.sort != node.sort:
                raise ValueError("skill argument type mismatch")
            return argument
        return Expr(node.kind, node.sort, node.value, tuple(walk(c) for c in node.children))
    return walk(body)


@dataclass(frozen=True)
class ParametricSkillMacro:
    """A linear, typed open AST, not a closed program renamed as an operator.

    Holes occur exactly once. Expansion cost excludes the hole/input loads;
    applying the skill adds the actual arguments' costs. This prevents a fake
    compression gain from counting the input load twice.
    """
    body: Expr
    input_sorts: tuple[str, ...]

    def __post_init__(self):
        if not 1 <= len(self.input_sorts) <= 2:
            raise ValueError("one or two typed parameters required")
        holes = []
        def walk(e):
            if e.kind == "hole":
                if type(e.value) is not int or not 0 <= e.value < len(self.input_sorts) or e.children:
                    raise ValueError("invalid typed hole")
                holes.append((e.value, e.sort))
            elif e.kind not in ("apply", "const"):
                raise ValueError("skill body must be a pure open primitive AST")
            elif e.kind == "const" and e.children:
                raise ValueError("constant skill nodes cannot have children")
            for child in e.children:
                walk(child)
        walk(self.body)
        if sorted(holes) != list(enumerate(self.input_sorts)):
            raise ValueError("each declared hole must occur exactly once")

    @property
    def sort(self):
        return self.body.sort

    def key(self):
        return ("parametric_skill", self.input_sorts, self.body.key())

    def call(self, *arguments):
        if tuple(a.sort for a in arguments) != self.input_sorts:
            raise ValueError("typed skill arguments required")
        return Expr("skill_call", self.sort, digest(self.key()), (self.body, *arguments))

    def expansion_cost(self, operators):
        def count(e):
            if e.kind == "hole":
                return 0
            return (operators[e.value].cost if e.kind == "apply" else 1) + sum(count(c) for c in e.children)
        return count(self.body)

    def validate(self, grammar):
        def check(e):
            if e.kind == "hole":
                return e.sort == self.input_sorts[e.value]
            if e.kind == "const":
                return e.key() in {c.key() for c in grammar.constants}
            op = grammar.ops.get(e.value)
            return (op is not None and e.sort == op.output
                    and tuple(c.sort for c in e.children) == op.inputs
                    and all(check(c) for c in e.children))
        if not check(self.body) or self.expansion_cost(grammar.ops) < 1:
            raise ValueError("skill template is outside the declared grammar")
        return True


def skill_wire(skill):
    if isinstance(skill, ParametricSkillMacro):
        return dict(kind="parametric_skill", input_sorts=list(skill.input_sorts), body=expression_wire(skill.body))
    return expression_wire(skill)


def skill_from_wire(value):
    if value.get("kind") == "parametric_skill":
        if set(value) != {"kind", "input_sorts", "body"} or not isinstance(value["input_sorts"], list):
            raise ValueError("invalid typed skill encoding")
        return ParametricSkillMacro(expression_from_wire(value["body"]), tuple(value["input_sorts"]))
    return expression_from_wire(value)


def expanded_skill_call(expr, meter=None):
    if expr.kind != "skill_call" or len(expr.children) not in (2, 3):
        raise ValueError("parametric skill call required")
    body, *arguments = expr.children
    skill = ParametricSkillMacro(body, tuple(a.sort for a in arguments))
    if expr.value != digest(skill.key()) or expr.sort != skill.sort:
        raise ValueError("skill call fingerprint/type mismatch")
    return substitute_holes(body, arguments, meter=meter)


def unfold_workspace_expr(expr, meter=None):
    """Return executable primitive syntax; never turn a workspace value into a constant."""
    if meter is not None:
        meter.charge("workspace_unfold_work_units")
    if expr.kind == "skill_call":
        return unfold_workspace_expr(expanded_skill_call(expr, meter), meter)
    if expr.kind in ("island", "macro"):
        return unfold_workspace_expr(expr.children[0], meter)
    return Expr(expr.kind, expr.sort, expr.value, tuple(unfold_workspace_expr(c, meter) for c in expr.children))


def workspace_leaf(expr):
    return Expr("island", expr.sort, digest(expr.key()), (expr,))


def primitive_cost(expr, operators):
    if isinstance(expr, ParametricSkillMacro):
        return expr.expansion_cost(operators) + len(expr.input_sorts)
    if expr.kind == "skill_call":
        return primitive_cost(expanded_skill_call(expr), operators)
    if expr.kind == "hole":
        raise ValueError("open hole is not an executable program")
    if expr.kind in ("var", "const"):
        return 1
    if expr.kind in ("macro", "island"):
        return primitive_cost(expr.children[0], operators)
    own = operators[expr.value].cost if expr.kind == "apply" else 1
    return own + sum(primitive_cost(c, operators) for c in expr.children)


def eval_expr(expr, x, operators, meter=None, category="search_work_units"):
    """Only evaluator for exact signatures, including bound element scopes."""
    meter = meter if meter is not None else WorkMeter()
    if expr.kind == "skill_call":
        return eval_expr(expanded_skill_call(expr, meter), x, operators, meter, category)
    if expr.kind == "if":
        meter.charge(category)
        guard = eval_expr(expr.children[0], x, operators, meter, category)
        if type(guard) is not bool:
            raise ValueError("conditional guard must be boolean")
        return eval_expr(expr.children[1 if guard else 2], x, operators, meter, category)
    if expr.kind == "var":
        meter.charge(category)
        return deepcopy(x)
    if expr.kind == "const":
        meter.charge(category)
        return deepcopy(expr.value)
    if expr.kind in ("macro", "island"):
        return eval_expr(expr.children[0], x, operators, meter, category)
    if expr.kind == "apply":
        args = [eval_expr(c, x, operators, meter, category) for c in expr.children]
        return operators[expr.value].call(args, meter, category)
    if expr.kind in ("map", "filter"):
        parent, inner = expr.children
        elements = eval_expr(parent, x, operators, meter, category)
        result = []
        for element in elements:
            meter.charge(category)
            value = eval_expr(inner, element, operators, meter, category)
            if expr.kind == "map":
                result.append(value)
            elif type(value) is not bool:
                raise ValueError("filter predicate must return bool")
            elif value:
                result.append(element)
        return tuple(result)
    raise ValueError("unknown expression")


def eval_expr_steps(expr, x, operators, meter, category="search_work_units"):
    """Cooperative evaluator: one yielded None for each charged work unit.

    Pure primitive calls themselves are atomic trusted functions. This makes
    logical work resumable; OS CPU/wall/RSS enforcement remains host-owned.
    """
    if expr.kind == "if":
        meter.charge(category)
        yield None
        guard = yield from eval_expr_steps(expr.children[0], x, operators, meter, category)
        if type(guard) is not bool:
            raise ValueError("conditional guard must be boolean")
        return (yield from eval_expr_steps(expr.children[1 if guard else 2], x, operators, meter, category))
    if expr.kind == "skill_call":
        # Substitution is real work too, yielded cooperatively for the 80/20
        # scheduler rather than hidden in an unmetered speculative turn.
        class Deferred:
            units = 0
            def charge(self, *args):
                self.units += 1
        pending = Deferred()
        expanded = expanded_skill_call(expr, pending)
        for _ in range(pending.units):
            meter.charge(category)
            yield None
        return (yield from eval_expr_steps(expanded, x, operators, meter, category))
    if expr.kind in ("var", "const"):
        meter.charge(category)
        yield None
        return deepcopy(x if expr.kind == "var" else expr.value)
    if expr.kind in ("macro", "island"):
        return (yield from eval_expr_steps(expr.children[0], x, operators, meter, category))
    if expr.kind == "apply":
        args = []
        for child in expr.children:
            args.append((yield from eval_expr_steps(child, x, operators, meter, category)))
        op = operators[expr.value]
        for _ in range(op.cost):
            meter.charge(category)
            yield None
        # Charge was prepaid one unit at a time; retain the same mutation audit.
        class Prepaid:
            def charge(self, *args):
                pass
        return op.call(args, Prepaid(), category)
    if expr.kind in ("map", "filter"):
        elements = yield from eval_expr_steps(expr.children[0], x, operators, meter, category)
        result = []
        for element in elements:
            meter.charge(category)
            yield None
            value = yield from eval_expr_steps(expr.children[1], element, operators, meter, category)
            if expr.kind == "map":
                result.append(value)
            elif type(value) is not bool:
                raise ValueError("filter predicate must return bool")
            elif value:
                result.append(element)
        return tuple(result)
    raise ValueError("unknown expression")


@dataclass(frozen=True)
class Binding:
    kind: str
    collection_sort: str
    element_sort: str
    inner_output: str

    def __post_init__(self):
        if self.kind not in ("map", "filter") or (self.kind == "filter" and self.inner_output != "BOOL"):
            raise ValueError("typed map/filter binding required")


@dataclass(frozen=True)
class Grammar:
    input_sort: str
    operators: tuple[Operator, ...]
    constants: tuple[Expr, ...] = ()
    bindings: tuple[Binding, ...] = ()
    conditionals: bool = False

    def __post_init__(self):
        if type(self.conditionals) is not bool:
            raise ValueError("explicit conditional grammar switch required")
        if len({o.name for o in self.operators}) != len(self.operators):
            raise ValueError("duplicate operator identifier")
        if any(c.kind != "const" for c in self.constants):
            raise ValueError("only typed constants in grammar")

    @property
    def ops(self):
        return {o.name: o for o in self.operators}


class FullSignatureQuotientDAG:
    """No intermediate query-value cap. Cost is an explicit search metric."""
    def __init__(self):
        self.classes = {}
        self.frontiers = {}

    @staticmethod
    def signature(expr, scope, outputs):
        return (expr.sort, scope, tuple(freeze(v) for v in outputs[:-1]), freeze(outputs[-1]))

    def retain(self, expr, scope, outputs, cost, *, primitive_expansion=None):
        if type(cost) is not int or cost < 1 or not outputs:
            raise ValueError("positive representative cost and nonempty signature")
        key = self.signature(expr, scope, outputs)
        if primitive_expansion is not None:
            if type(primitive_expansion) is not int or primitive_expansion < 1:
                raise ValueError("positive primitive expansion cost required")
            frontier = self.frontiers.setdefault(key, [])
            if any(c <= cost and p <= primitive_expansion for c, p, _ in frontier):
                return False
            frontier[:] = [(c, p, e) for c, p, e in frontier if not (cost <= c and primitive_expansion <= p)]
            frontier.append((cost, primitive_expansion, expr))
            self.classes[key] = min(((c, e) for c, _, e in frontier), key=lambda r: (r[0], repr(r[1].key())))
            return True
        previous = self.classes.get(key)
        if previous is not None and previous[0] <= cost:
            return False
        self.classes[key] = (cost, expr)
        return True


def _partitions(total, n):
    if n == 1:
        if total >= 1:
            yield (total,)
        return
    for first in range(1, total - n + 2):
        for tail in _partitions(total - first, n - 1):
            yield (first,) + tail


class ExactEnumerator:
    """Resumable cost-first generator. Quotient=false is independent AST search.

    Pure total operators and compositional cost are grammar preconditions.
    No evaluated catalog is constructed before the meter starts. Empty types
    and exceptions fail closed; exceptions are not silently dropped programs.
    """
    def __init__(self, grammar, inputs, bound, *, quotient=True, scope="root", meter=None,
                 laws=None, macros=(), mdl=False, evolved=False, primitive_cap=None, priority=None, workspace=(),
                 target_public=None, noether=None, inner_heuristics=True, operator_agenda=(),
                 leaf_macros=False):
        if not inputs or type(bound) is not int or bound < 1:
            raise ValueError("nonempty observations/query and positive bound")
        self.grammar, self.inputs, self.bound = grammar, tuple(deepcopy(inputs)), bound
        self.quotient, self.scope = quotient, scope
        self.meter = meter if meter is not None else WorkMeter()
        self.laws, self.macros, self.mdl = laws, tuple(macros), mdl
        if evolved and (type(primitive_cap) is not int or primitive_cap < bound):
            raise ValueError("ratcheted search requires an explicit primitive expansion cap")
        if evolved and any(not isinstance(m, ParametricSkillMacro) for m in self.macros):
            raise ValueError("ratchet accepts open typed skills, never ground caches")
        self.evolved, self.primitive_cap, self.priority = evolved, primitive_cap, priority
        self.target_public = None if target_public is None else tuple(target_public)
        self.noether = noether
        self.inner_heuristics = bool(inner_heuristics)
        self.operator_agenda = tuple(operator_agenda or ())
        self.leaf_macros = bool(leaf_macros)
        self.workspace = tuple(workspace)
        if self.workspace and not evolved:
            raise ValueError("workspace leaves require the explicit evolved/primitive-cap grammar")
        for island in self.workspace:
            validate_program(island, grammar)
            if primitive_cost(island, grammar.ops) > primitive_cap:
                raise ValueError("workspace island exceeds expanded primitive cap")
        self.dag = FullSignatureQuotientDAG()
        self.pool = defaultdict(list)
        self.generated = self.retained = 0
        self.complete = False
        self.output_cache = {}

    def _outputs(self, expr):
        """Exact child-output reuse within this one immutable observation scope."""
        self.meter.charge("cache_lookup_work_units")
        key = expr.key()
        if key in self.output_cache:
            return self.output_cache[key]
        if expr.kind == "apply":
            children = [self._outputs(c) for c in expr.children]
            outputs = tuple(self.grammar.ops[expr.value].call(args, self.meter, "search_work_units")
                            for args in zip(*children))
        elif expr.kind in ("macro", "island"):
            outputs = self._outputs(expr.children[0])
        elif expr.kind == "skill_call":
            outputs = self._outputs(expanded_skill_call(expr, self.meter))
        else:
            outputs = tuple(eval_expr(expr, x, self.grammar.ops, self.meter) for x in self.inputs)
        self.output_cache[key] = outputs
        return outputs

    def _output_events(self, expr):
        self.meter.charge("exact_work_units")
        yield None
        key = expr.key()
        if key in self.output_cache:
            return self.output_cache[key]
        if expr.kind == "apply":
            children = []
            for child in expr.children:
                children.append((yield from self._output_events(child)))
            outputs = []
            op = self.grammar.ops[expr.value]
            class Prepaid:
                def charge(self, *args):
                    pass
            for args in zip(*children):
                for _ in range(op.cost):
                    self.meter.charge("exact_work_units")
                    yield None
                outputs.append(op.call(args, Prepaid(), "exact_work_units"))
            outputs = tuple(outputs)
        elif expr.kind in ("macro", "island"):
            outputs = yield from self._output_events(expr.children[0])
        else:
            values = []
            for x in self.inputs:
                values.append((yield from eval_expr_steps(expr, x, self.grammar.ops, self.meter, "exact_work_units")))
            outputs = tuple(values)
        self.output_cache[key] = outputs
        return outputs

    def cost(self, expr):
        if expr.kind == "island":
            return 1
        if expr.kind == "skill_call":
            body, *arguments = expr.children
            skill = ParametricSkillMacro(body, tuple(a.sort for a in arguments))
            own = 1 if self.evolved else (1 + math.ceil(math.log2(1 + len(self.macros)))) if self.mdl else skill.expansion_cost(self.grammar.ops)
            return own + sum(self.cost(a) for a in arguments)
        if expr.kind == "macro" and self.mdl:
            return 1 + math.ceil(math.log2(1 + len(self.macros)))
        if expr.kind in ("var", "const"):
            return 1
        if expr.kind == "macro":
            return primitive_cost(expr.children[0], self.grammar.ops)
        own = self.grammar.ops[expr.value].cost if expr.kind == "apply" else 1
        return own + sum(self.cost(c) for c in expr.children)

    def description_cost(self, expr):
        """MDL remains a declared tie-breaker, not a disguised primitive bound."""
        if expr.kind == "skill_call":
            return 1+math.ceil(math.log2(1+len(self.macros)))+sum(self.description_cost(a) for a in expr.children[1:])
        if expr.kind in ("var", "const", "island"):
            return 1
        own = self.grammar.ops[expr.value].cost if expr.kind == "apply" else 1
        return own+sum(self.description_cost(c) for c in expr.children)

    def admissible(self, expr):
        return self.primitive_cap is None or primitive_cost(expr, self.grammar.ops) <= self.primitive_cap

    def _candidates(self, size):
        g = self.grammar
        if size == 1:
            yield variable(g.input_sort)
            yield from sorted(g.constants, key=lambda e: repr(e.key()))
            yield from (workspace_leaf(e) for e in self.workspace)
        for macro in self.macros:
            if isinstance(macro, ParametricSkillMacro):
                own = 1 if self.evolved else (1 + math.ceil(math.log2(1 + len(self.macros)))) if self.mdl else macro.expansion_cost(g.ops)
                for sizes in _partitions(size-own, len(macro.input_sorts)):
                    if self.leaf_macros and any(part != 1 for part in sizes):
                        continue
                    for args in product(*(self.pool[(s, t)] for s, t in zip(sizes, macro.input_sorts))):
                        yield macro.call(*args)
            else:
                wrapped = Expr("macro", macro.sort, None, (macro,))
                if self.cost(wrapped) == size:
                    yield wrapped
        ops = g.operators
        if self.operator_agenda:
            rank = {name: i for i, name in enumerate(self.operator_agenda)}
            ops = tuple(sorted(g.operators, key=lambda o: (rank.get(o.name, len(rank)), o.name)))
        if self.noether is not None and self.target_public is not None and size == self.bound:
            sample = None
            for bucket in self.pool.values():
                if bucket:
                    sample = bucket[0]
                    break
            if sample is not None:
                child_pub = self._outputs(sample)[:-1]
                ops = self.noether.last_step_operator_order(g.operators, child_pub, self.target_public)
        for op in ops:
            for sizes in _partitions(size - op.cost, len(op.inputs)):
                options = [self.pool[(s, t)] for s, t in zip(sizes, op.inputs)]
                for children in product(*options):
                    expr = apply(op, *children)
                    if (self.noether is not None and self.target_public is not None
                            and size == self.bound and len(children) == 1):
                        child_pub = self._outputs(children[0])[:-1]
                        if self.noether.should_skip_last_step(op, child_pub, self.target_public):
                            continue
                    yield expr
        if g.conditionals:
            sorts = {g.input_sort, *(op.output for op in g.operators), *(c.sort for c in g.constants)}
            for sizes in _partitions(size-1, 3):
                for sort in sorted(sorts):
                    for guard, yes, no in product(self.pool[(sizes[0], "BOOL")], self.pool[(sizes[1], sort)], self.pool[(sizes[2], sort)]):
                        yield Expr("if", sort, None, (guard, yes, no))
        for binding in g.bindings:
            for parent_size in range(1, size - 1):
                for parent in self.pool[(parent_size, binding.collection_sort)]:
                    parent_values = self._outputs(parent)
                    # This universe depends on the exact reachable parent class.
                    universe = {}
                    for collection in parent_values:
                        for element in collection:
                            universe[freeze(element)] = element
                    if not universe:
                        # No invented typed constants. For quotient search every
                        # empty binder equals its cheaper parent. Exhaustive
                        # search still emits all legal inner syntax.
                        if not self.quotient:
                            inner_g = Grammar(binding.element_sort, g.operators, g.constants, conditionals=g.conditionals)
                            for inner in syntax_programs(inner_g, size-parent_size-1):
                                expr = Expr(binding.kind, binding.collection_sort, None, (parent, inner))
                                if inner.sort == binding.inner_output and self.cost(expr) == size:
                                    yield expr
                        continue
                    inner_bound = size - parent_size - 1
                    inner_g = Grammar(binding.element_sort, g.operators, g.constants, conditionals=g.conditionals)
                    scope = digest((self.scope, parent.key(), tuple(freeze(v) for v in parent_values)))
                    inner_search = ExactEnumerator(inner_g, tuple(universe.values()), inner_bound,
                                                   quotient=self.quotient, scope=scope, meter=self.meter,
                                                   macros=self.macros, mdl=self.mdl, evolved=self.evolved,
                                                   primitive_cap=self.primitive_cap)
                    for inner, _, inner_cost in inner_search:
                        if inner_cost == inner_bound and inner.sort == binding.inner_output:
                            yield Expr(binding.kind, binding.collection_sort, None, (parent, inner))

    def __iter__(self):
        for size in range(1, self.bound + 1):
            candidates = self._candidates(size)
            if self.evolved or self.priority is not None or self.laws is not None and self.laws.empirical_probe_priors:
                # Same cost layer only; all deferred branches are exhausted.
                # Materialization is metered and may produce UNKNOWN on cap.
                # Doctor/zlib scoring is forbidden inside this inner loop.
                layer = []
                for expr in candidates:
                    self.meter.charge("prior_ordering_work_units")
                    if self.admissible(expr):
                        layer.append(expr)
                def order(expr):
                    learned = ()
                    if self.inner_heuristics and self.priority is not None:
                        learned = self.priority(expr, self._outputs(expr)[:-1], self.meter)
                    prior = self.laws.priority(expr) if self.laws is not None else ()
                    return (learned, self.description_cost(expr) if self.evolved else 0, prior, repr(expr.key()))
                candidates = sorted(layer, key=order)
            for expr in candidates:
                self.meter.charge("candidate_work_units")
                self.generated += 1
                if not self.admissible(expr):
                    continue
                if self.laws is not None and self.laws.redundant(expr, self.inputs, self.grammar, self.meter, outputs_for=self._outputs):
                    continue
                outputs = self._outputs(expr)
                self.meter.charge("signature_work_units")
                if not self.quotient or self.dag.retain(expr, self.scope, outputs, size,
                        primitive_expansion=primitive_cost(expr, self.grammar.ops) if self.evolved else None):
                    self.pool[(size, expr.sort)].append(expr)
                    self.retained += 1
                    yield expr, outputs, size
        self.complete = True

    def work_events(self):
        """Work-preemptible fixed-bound backend for the five unary worlds.

        Binder enumeration/law discovery must use their separately metered
        backend, not claim this scheduler can preempt a nested enumeration.
        """
        if self.grammar.bindings or self.grammar.conditionals or self.laws is not None or self.evolved or self.priority is not None:
            raise ValueError("work-step backend requires precompiled binders and laws")
        for size in range(1, self.bound + 1):
            for expr in self._candidates(size):
                self.meter.charge("exact_work_units")
                yield None
                self.generated += 1
                outputs = yield from self._output_events(expr)
                self.meter.charge("exact_work_units")
                yield None
                if not self.quotient or self.dag.retain(expr, self.scope, outputs, size):
                    self.pool[(size, expr.sort)].append(expr)
                    self.retained += 1
                    yield (expr, tuple(outputs), size)
        self.complete = True


class ExhaustiveASTEnumerator(ExactEnumerator):
    def __init__(self, *args, **kwargs):
        kwargs["quotient"] = False
        super().__init__(*args, **kwargs)

    def __iter__(self):
        """Separate syntactic recurrence; does not use quotient candidate pools.

        Deliberately includes duplicate meanings. Reference work/space may be
        much larger; exhaustion means unknown, never a failed equivalence test.
        """
        if self.laws is not None:
            raise ValueError("exhaustive reference cannot apply induced laws")
        cache = {}
        def programs(input_sort, size, allow_bindings):
            key = (input_sort, size, allow_bindings)
            if key in cache:
                return cache[key]
            result = []
            def add(expr):
                self.meter.charge("reference_construction_work_units")
                result.append(expr)
            if size == 1:
                add(variable(input_sort))
                for c in self.grammar.constants:
                    add(c)
                if allow_bindings and input_sort == self.grammar.input_sort:
                    for island in self.workspace:
                        add(workspace_leaf(island))
            for macro in self.macros:
                if isinstance(macro, ParametricSkillMacro):
                    own = 1 if self.evolved else (1 + math.ceil(math.log2(1 + len(self.macros)))) if self.mdl else macro.expansion_cost(self.grammar.ops)
                    for sizes in _partitions(size-own, len(macro.input_sorts)):
                        choices = [[e for e in programs(input_sort, s, allow_bindings) if e.sort == t]
                                   for s, t in zip(sizes, macro.input_sorts)]
                        for args in product(*choices):
                            add(macro.call(*args))
                else:
                    wrapped = Expr("macro", macro.sort, None, (macro,))
                    if self.cost(wrapped) == size:
                        add(wrapped)
            for op in self.grammar.operators:
                for sizes in _partitions(size-op.cost, len(op.inputs)):
                    choices = [[e for e in programs(input_sort, s, allow_bindings) if e.sort == t]
                               for s, t in zip(sizes, op.inputs)]
                    for children in product(*choices):
                        add(apply(op, *children))
            if self.grammar.conditionals:
                sorts = {input_sort, *(op.output for op in self.grammar.operators), *(c.sort for c in self.grammar.constants)}
                for sizes in _partitions(size-1, 3):
                    for sort in sorted(sorts):
                        guards = [e for e in programs(input_sort, sizes[0], allow_bindings) if e.sort == "BOOL"]
                        yes = [e for e in programs(input_sort, sizes[1], allow_bindings) if e.sort == sort]
                        no = [e for e in programs(input_sort, sizes[2], allow_bindings) if e.sort == sort]
                        for children in product(guards, yes, no):
                            add(Expr("if", sort, None, tuple(children)))
            if allow_bindings:
                for binding in self.grammar.bindings:
                    for parent_size in range(1, size-1):
                        parents = programs(input_sort, parent_size, True)
                        inners = programs(binding.element_sort, size-parent_size-1, False)
                        for parent in parents:
                            if parent.sort != binding.collection_sort:
                                continue
                            for inner in inners:
                                if inner.sort == binding.inner_output:
                                    add(Expr(binding.kind, binding.collection_sort, None, (parent, inner)))
            cache[key] = result
            return result
        for size in range(1, self.bound+1):
            for expr in programs(self.grammar.input_sort, size, True):
                self.generated += 1
                if not self.admissible(expr):
                    continue
                outputs = tuple(eval_expr(expr, x, self.grammar.ops, self.meter) for x in self.inputs)
                yield expr, outputs, size
        self.complete = True


def syntax_programs(grammar, bound):
    """Legal binder bodies when the reachable element universe is empty."""
    if grammar.bindings:
        raise ValueError("nested binder grammar needs an explicit scope")
    pool = defaultdict(list)
    for size in range(1, bound+1):
        expressions = []
        if size == 1:
            expressions = [variable(grammar.input_sort), *grammar.constants]
        for op in grammar.operators:
            for sizes in _partitions(size-op.cost, len(op.inputs)):
                for children in product(*(pool[(s, t)] for s, t in zip(sizes, op.inputs))):
                    expressions.append(apply(op, *children))
        for expr in expressions:
            pool[(size, expr.sort)].append(expr)
            yield expr


def validate_program(expr, grammar, *, macros=(), input_sort=None, workspace=()):
    """Grammar membership is part of a certificate, not just successful eval."""
    input_sort = grammar.input_sort if input_sort is None else input_sort
    if expr.kind == "var":
        valid = expr.sort == input_sort and not expr.children and expr.value is None
    elif expr.kind == "const":
        valid = not expr.children and expr.key() in {c.key() for c in grammar.constants}
    elif expr.kind == "apply":
        op = grammar.ops.get(expr.value)
        valid = op is not None and expr.sort == op.output and tuple(c.sort for c in expr.children) == op.inputs
        valid = valid and all(validate_program(c, grammar, macros=macros, input_sort=input_sort, workspace=workspace) for c in expr.children)
    elif expr.kind == "island":
        valid = (len(expr.children) == 1 and expr.sort == expr.children[0].sort
                 and expr.value == digest(expr.children[0].key())
                 and expr.children[0].key() in {e.key() for e in workspace}
                 and validate_program(expr.children[0], grammar, input_sort=input_sort))
    elif expr.kind == "macro":
        valid = len(expr.children) == 1 and expr.value is None and expr.sort == expr.children[0].sort
        valid = valid and expr.children[0].key() in {m.key() for m in macros}
        valid = valid and validate_program(expr.children[0], grammar, macros=(), input_sort=input_sort)
    elif expr.kind == "skill_call":
        valid = False
        if len(expr.children) in (2, 3):
            body, *arguments = expr.children
            try:
                skill = ParametricSkillMacro(body, tuple(a.sort for a in arguments))
                skill.validate(grammar)
                valid = (expr.value == digest(skill.key()) and expr.sort == skill.sort
                         and skill.key() in {m.key() for m in macros}
                         and all(validate_program(a, grammar, macros=macros, input_sort=input_sort, workspace=workspace) for a in arguments))
            except (ValueError, IndexError, KeyError, TypeError):
                valid = False
    elif expr.kind == "if":
        valid = (grammar.conditionals and expr.value is None and len(expr.children) == 3
                 and expr.children[0].sort == "BOOL" and expr.children[1].sort == expr.children[2].sort == expr.sort
                 and all(validate_program(c, grammar, macros=macros, input_sort=input_sort, workspace=workspace) for c in expr.children))
    elif expr.kind in ("map", "filter"):
        valid = False
        if len(expr.children) == 2:
            parent, inner = expr.children
            for binding in grammar.bindings:
                if (binding.kind, binding.collection_sort, binding.inner_output) == (expr.kind, expr.sort, inner.sort):
                    valid = parent.sort == binding.collection_sort and validate_program(parent, grammar, macros=macros, input_sort=input_sort, workspace=workspace)
                    valid = valid and validate_program(inner, grammar, input_sort=binding.element_sort)
                    if valid:
                        break
    else:
        valid = False
    if not valid:
        raise ValueError("program outside declared typed grammar/scope/library")
    return True


@dataclass(frozen=True)
class SearchResult:
    status: str
    witnesses: tuple[Expr, ...]
    query_values: tuple[Any, ...]
    complete: bool
    root_equivalence_discharges: int = 0


class GoalCheck:
    """Targeted disagreement at roots only. Never prunes intermediate classes."""
    def __init__(self, outputs, output_sort):
        self.outputs = tuple(freeze(v) for v in outputs)
        self.output_sort = output_sort
        self.first = None
        self.values = []
        self.witnesses = []
        self.discharged = 0

    def observe(self, expr, outputs):
        if expr.sort != self.output_sort or tuple(freeze(v) for v in outputs[:-1]) != self.outputs:
            return False
        value = freeze(outputs[-1])
        if self.first is not None and value == self.first:
            self.discharged += 1
            return False
        if self.first is None:
            self.first = value
        self.values.append(deepcopy(outputs[-1]))
        self.witnesses.append(expr)
        return len(self.values) == 2

    def result(self, complete):
        if len(self.values) == 2:
            status = "AMBIGUOUS_WITNESS_FOUND"
        elif not complete:
            status = "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED"
        elif self.values:
            status = "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE"
        else:
            status = "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
        return SearchResult(status, tuple(self.witnesses), tuple(self.values), complete, self.discharged)


class PopperianTwinVerifier:
    """Bounded adversarial witness proposals, NEVER a uniqueness certificate.

    One AST mutation is not O(1) runtime: traversal, public replay and every
    operator call are metered. If the neighborhood fails, the SAME resumable
    exact search must finish; exhaustion remains UNKNOWN.
    """
    def __init__(self, roles=None, *, max_mutations=16):
        if type(max_mutations) is not int or not 0 <= max_mutations <= 128:
            raise ValueError("bounded twin neighborhood required")
        self.roles, self.max_mutations = roles or {}, max_mutations
        self.last_report = {}

    def mutations(self, expr, grammar, macros, meter=None, workspace=()):
        if meter is not None:
            meter.charge("twin_work_units")
        if expr.kind == "apply":
            original = grammar.ops[expr.value]
            for op in grammar.operators:
                if op.name != original.name and op.inputs == original.inputs and op.output == original.output:
                    a, b = self.roles.get(original.name), self.roles.get(op.name)
                    shared_role = a is not None and b is not None and a.transfer_key() == b.transfer_key()
                    yield apply(op, *expr.children), shared_role
        elif expr.kind == "island":
            for alternative in workspace:
                if alternative.sort == expr.sort and alternative.key() != expr.children[0].key():
                    yield workspace_leaf(alternative), False
        elif expr.kind == "skill_call":
            body, *args = expr.children
            for skill in macros:
                if isinstance(skill, ParametricSkillMacro) and skill.sort == expr.sort and skill.input_sorts == tuple(a.sort for a in args):
                    alternative = skill.call(*args)
                    if alternative.key() != expr.key():
                        yield alternative, False  # exact public trace still required
        start = len(expr.children) if expr.kind == "island" else 1 if expr.kind == "skill_call" else 0
        for i in range(start, len(expr.children)):
            for child, role in self.mutations(expr.children[i], grammar, macros, meter, workspace):
                children = list(expr.children)
                children[i] = child
                yield Expr(expr.kind, expr.sort, expr.value, tuple(children)), role

    def search(self, first, grammar, public_io, query, enum, meter):
        attempted, role_swaps, trace_swaps = 0, 0, 0
        first_value = freeze(eval_expr(first, query, grammar.ops, meter, "twin_work_units"))
        first_public = tuple(freeze(y) for _, y in public_io)
        seen = {first.key()}
        for proposal, shared_role in self.mutations(first, grammar, enum.macros, meter, enum.workspace):
            if attempted >= self.max_mutations:
                break
            meter.charge("twin_work_units")
            attempted += 1
            if proposal.key() in seen:
                continue
            seen.add(proposal.key())
            if enum.cost(proposal) > enum.bound or not enum.admissible(proposal):
                continue
            validate_program(proposal, grammar, macros=enum.macros, workspace=enum.workspace)
            outputs = tuple(eval_expr(proposal, x, grammar.ops, meter, "twin_work_units") for x, _ in public_io)
            same_trace = tuple(freeze(y) for y in outputs) == first_public
            if not shared_role and not same_trace:
                continue
            role_swaps += shared_role
            trace_swaps += not shared_role and same_trace
            if same_trace:
                value = eval_expr(proposal, query, grammar.ops, meter, "twin_work_units")
                if freeze(value) != first_value:
                    self.last_report = dict(attempted=attempted, role_swaps=role_swaps, public_trace_swaps=trace_swaps,
                                            witness_found=True, uniqueness_certified=False)
                    return proposal, (*outputs, value)
        self.last_report = dict(attempted=attempted, role_swaps=role_swaps, public_trace_swaps=trace_swaps,
                                witness_found=False, uniqueness_certified=False)
        return None


def solve(grammar, public_io, query, output_sort, bound, *, quotient=True, meter=None, trace=None,
          twin_verifier=None, proposal_controller=None, **kwargs):
    labels = {}
    for x, y in public_io:
        key = freeze(x)
        if key in labels and labels[key] != freeze(y):
            return SearchResult("VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS", (), (), False)
        labels[key] = freeze(y)
    meter = meter if meter is not None else WorkMeter()
    goal = GoalCheck([y for _, y in public_io], output_sort)
    started_work = meter.total
    def record():
        if trace is not None:
            work = meter.total-started_work
            if goal.first is not None and trace.get("work_to_g1") is None:
                trace["work_to_g1"] = work
            if len(goal.values) == 2:
                trace["work_to_g2"] = work
    enum_cls = ExactEnumerator if quotient else ExhaustiveASTEnumerator
    enum = enum_cls(grammar, [x for x, _ in public_io] + [query], bound,
                    quotient=quotient, meter=meter, **kwargs)
    try:
        for expr, outputs, _ in enum:
            split = goal.observe(expr, outputs)
            record()
            if split:
                return goal.result(False)
            if goal.first is None and proposal_controller is not None:
                for proposal in proposal_controller.repair_proposals(expr, outputs, grammar, public_io, enum, meter):
                    validate_program(proposal, grammar, macros=enum.macros, workspace=enum.workspace)
                    proposed_outputs = tuple(eval_expr(proposal, x, grammar.ops, meter, "behavioral_proposal_work_units")
                                             for x in [x for x, _ in public_io]+[query])
                    found_split = goal.observe(proposal, proposed_outputs)
                    record()
                    if trace is not None:
                        trace["behavioral_proposals"] = proposal_controller.proposed
                    if found_split:
                        return goal.result(False)
            if twin_verifier is not None and goal.first is not None:
                twin = twin_verifier.search(goal.witnesses[0], grammar, public_io, query, enum, meter)
                if trace is not None:
                    trace["twin"] = twin_verifier.last_report
                twin_verifier = None  # one bounded neighborhood, not a restart loop
                if twin is not None:
                    goal.observe(*twin)
                    record()
                    return goal.result(False)
    except WorkExhausted:
        return goal.result(False)
    result = goal.result(True)
    if trace is not None and result.status.startswith("UNIQUE_QUERY"):
        trace["work_to_uniqueness"] = meter.total-started_work
    return result


def verify_certificate(grammar, public_io, query, output_sort, bound, result, *, meter=None, macros=(), mdl=False,
                       evolved=False, primitive_cap=None, workspace=()):
    """Independent unquotiented replay; unknown must never become a proof."""
    meter = meter if meter is not None else WorkMeter()
    for expr, value in zip(result.witnesses, result.query_values):
        validate_program(expr, grammar, macros=macros, workspace=workspace)
        enum = ExactEnumerator(grammar, [query], bound, macros=macros, mdl=mdl, meter=meter,
                               evolved=evolved, primitive_cap=primitive_cap, workspace=workspace)
        if enum.cost(expr) > bound or expr.sort != output_sort or not enum.admissible(expr):
            raise ValueError("witness exceeds declared horizon/type")
        if any(freeze(eval_expr(expr, x, grammar.ops, meter)) != freeze(y) for x, y in public_io):
            raise ValueError("witness does not fit public evidence")
        if freeze(eval_expr(expr, query, grammar.ops, meter)) != freeze(value):
            raise ValueError("witness query value differs")
    if len(result.witnesses) != len(result.query_values):
        raise ValueError("incomplete witness grid")
    if result.status == "AMBIGUOUS_WITNESS_FOUND":
        if len(result.query_values) != 2 or freeze(result.query_values[0]) == freeze(result.query_values[1]):
            raise ValueError("missing disagreement witness")
        return True
    reference = solve(grammar, public_io, query, output_sort, bound, quotient=False,
                      meter=meter, macros=macros, mdl=mdl, evolved=evolved, primitive_cap=primitive_cap, workspace=workspace)
    if result.status != reference.status:
        raise ValueError("certificate disagrees with exhaustive grammar")
    if result.complete != reference.complete:
        raise ValueError("false completeness claim")
    if tuple(map(freeze, result.query_values)) != tuple(map(freeze, reference.query_values)):
        raise ValueError("query-output certificate differs")
    return True


@dataclass(frozen=True)
class Prefix:
    steps: tuple[str, ...]
    states: tuple[Any, ...]
    cost: int


def prefix_first_trajectories(operators, initial_states, max_cost, meter, *, quotient=True):
    """Every step sees full actual S_t, never a projected or initial S_0."""
    initial = Prefix((), tuple(deepcopy(initial_states)), 0)
    by_cost = defaultdict(list, {0: [initial]})
    seen = {tuple(freeze(s) for s in initial.states): 0}
    yield initial
    for cost in range(1, max_cost + 1):
        for op in sorted(operators, key=lambda o: o.name):
            if op.inputs != (op.output,):
                raise ValueError("trajectory operators must be state endomorphisms")
            for prior in by_cost[cost - op.cost] if cost >= op.cost else ():
                states = tuple(op.call((s,), meter, "search_work_units") for s in prior.states)
                sig = tuple(freeze(s) for s in states)
                meter.charge("signature_work_units")
                if quotient and sig in seen and seen[sig] <= cost:
                    continue
                seen[sig] = cost
                candidate = Prefix(prior.steps + (op.name,), states, cost)
                by_cost[cost].append(candidate)
                yield candidate


def symkan_accounting(reports):
    counts = dict(symkan_attempted_count=0, symkan_nonempty_induced_count=0,
                  symkan_abstained_count=0, symkan_faithful_export_count=0)
    for report in reports:
        attempted = report["attempted"]
        nonempty = bool(report["induced_expression"])
        faithful = report["faithful_export"]
        if type(attempted) is not bool or type(faithful) is not bool:
            raise ValueError("boolean SymKAN flags required")
        if (nonempty and not attempted) or faithful != nonempty:
            raise ValueError("unfaithful or unattempted SymKAN export")
        counts["symkan_attempted_count"] += attempted
        counts["symkan_nonempty_induced_count"] += nonempty
        counts["symkan_abstained_count"] += attempted and not nonempty
        counts["symkan_faithful_export_count"] += faithful
    assert counts["symkan_faithful_export_count"] == counts["symkan_nonempty_induced_count"]
    return counts
