"""Execution-induced laws over explicitly complete, finite typed carriers.

Anonymous identifiers, not family names, drive discovery. A sampled probe pass
is a hypothesis only: it never authorizes grammar pruning on an infinite type.
Certified rewrite use also checks membership of actual contextual operands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
import inspect
import hashlib
from itertools import product, islice
from typing import Any

from nexus.evolution1.catalogue import digest
from nexus.wave24_quotient_core import eval_expr, freeze, WorkMeter, Grammar, Operator


def structural_measure(value):
    """A type-independent ordering feature, never a proof of semantics."""
    if isinstance(value, (str, tuple, list, dict)):
        return len(value)
    if type(value) in (int, float):
        return abs(value)
    return 1


_MASK64 = (1 << 64) - 1


def splitmix64(value):
    """Deterministic 64-bit finalizer (Steele et al.); value is reduced mod 2^64."""
    z = (value + 0x9E3779B97F4A7C15) & _MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
    return z ^ (z >> 31)


def _atom_hash(token):
    """Stable 64-bit seed for one locus/quantum (process-independent, unlike hash())."""
    return splitmix64(int.from_bytes(hashlib.blake2b(repr(token).encode(), digest_size=8).digest(), "big"))


@dataclass(frozen=True)
class AtomicSignature:
    mass: int
    locus_mask: int
    quantum_multiset_hash: int
    quantum_bloom_64: int
    bond_bitmap: int
    # XOR over (locus, quantum) pairs. locus_mask alone is permutation-invariant
    # (XOR of coordinates), so arrangement changes are only visible here.
    binding_hash: int = 0


BOND_NONEMPTY, BOND_NONDECREASING, BOND_STRICT_INCREASING, BOND_ADJACENT_EQUAL, BOND_HOMOGENEOUS = 1, 2, 4, 8, 16


class AtomicFieldProjector:
    """One O(N) pass from any value to (locus, quantum) atoms and a 64-bit signature.

    str/list/tuple: locus = index, quantum = element. dict: locus = key,
    quantum = (key, value). set/frozenset: locus = quantum = element (order-free).
    int: locus = bit index, quantum = (index, bit) plus a sign atom; mass = bit width.
    Scalars (float, bool, None, other): one atom. Equal multiset hashes are
    necessary, not sufficient, for permutation equality (64-bit hash).
    """

    def atoms(self, value):
        if type(value) is int:
            n = abs(value)
            bits = [(i, (n >> i) & 1) for i in range(n.bit_length())]
            return [(("bit", i), ("bit", i, b)) for i, b in bits] + [(("sign",), ("sign", value < 0))]
        if isinstance(value, str):
            return [(("i", i), ("c", ch)) for i, ch in enumerate(value)]
        if isinstance(value, (list, tuple)):
            return [(("i", i), ("v", freeze(v) if _freezable(v) else repr(v))) for i, v in enumerate(value)]
        if isinstance(value, dict):
            return [(("k", repr(k)), ("kv", repr(k), freeze(v) if _freezable(v) else repr(v))) for k, v in value.items()]
        if isinstance(value, (set, frozenset)):
            return [(("e", repr(v)), ("e", repr(v))) for v in sorted(value, key=repr)]
        return [(("scalar",), ("s", freeze(value) if _freezable(value) else repr(value)))]

    def project(self, value):
        atoms = self.atoms(value)
        locus = quantum = bloom = binding = 0
        for loc, q in atoms:
            locus ^= _atom_hash(loc)
            binding ^= _atom_hash((loc, q))
            h = _atom_hash(q)
            quantum = (quantum + h) & _MASK64
            bloom |= 1 << (h % 64)
        bond = 0
        quanta = [q for _, q in atoms]
        if quanta:
            bond |= BOND_NONEMPTY
            if len({type(q[-1]) for q in quanta}) == 1:
                bond |= BOND_HOMOGENEOUS
            pairs = list(zip(quanta, quanta[1:]))
            try:
                if pairs and all(a[-1] <= b[-1] for a, b in pairs):
                    bond |= BOND_NONDECREASING
                if pairs and all(a[-1] < b[-1] for a, b in pairs):
                    bond |= BOND_STRICT_INCREASING
            except TypeError:
                pass
            if any(a == b for a, b in pairs):
                bond |= BOND_ADJACENT_EQUAL
        mass = abs(value).bit_length() if type(value) is int else len(atoms)
        return AtomicSignature(mass, locus, quantum, bloom, bond, binding)


def _is_container(value):
    return isinstance(value, (str, list, tuple, dict, set, frozenset))


def _freezable(value):
    try:
        freeze(value)
        return True
    except (TypeError, ValueError):
        return False


F_SELECT, F_TRANSLATE, F_TRANSMUTE, F_CONDENSE, F_BRANCH = (
    "F_SELECT", "F_TRANSLATE", "F_TRANSMUTE", "F_CONDENSE", "F_BRANCH")
ATOMIC_FORCES = (F_SELECT, F_TRANSLATE, F_TRANSMUTE, F_CONDENSE, F_BRANCH)


@dataclass(frozen=True)
class AtomicForceRole:
    """Empirical force role from probes; a search-ordering prior, never a soundness proof."""
    force: str
    probes_used: int
    identity_probes: int
    mass_preserving: bool
    mass_contractive: bool
    multiset_preserving: bool
    locus_preserving: bool
    local_forces: tuple


def local_force(before, after):
    """Force of one observed transition between two AtomicSignatures (None = identity)."""
    if before == after:
        return None
    if after.mass == before.mass:
        if after.quantum_multiset_hash == before.quantum_multiset_hash and (
                after.locus_mask != before.locus_mask or after.binding_hash != before.binding_hash):
            return F_TRANSLATE
        if after.locus_mask == before.locus_mask and after.quantum_multiset_hash != before.quantum_multiset_hash:
            return F_TRANSMUTE
    subset = (after.quantum_bloom_64 & ~before.quantum_bloom_64) == 0
    if after.mass <= before.mass and subset:
        return F_SELECT
    if after.mass < before.mass:
        return F_CONDENSE
    return F_TRANSMUTE  # non-conservative re-encoding (parse, type change, growth)


class AtomicForceClassifier:
    """Fingerprint a callable into one of the five universal atomic forces."""

    def __init__(self, projector=None, error_token="EXEC_ERR"):
        self.projector = projector or AtomicFieldProjector()
        self.error_token = error_token

    def classify(self, fn, probes, *, meter=None):
        rows = []
        for x in probes:
            if meter is not None:
                meter.charge("atomic_force_probe_work_units")
            try:
                y = fn(x)
            except Exception:
                continue
            if isinstance(y, str) and y == self.error_token:
                continue
            rows.append((self.projector.project(x), self.projector.project(y), _is_container(x) and not _is_container(y)))
        # Container -> scalar is aggregation regardless of the (incomparable) masses.
        forces = [F_CONDENSE if fused else local_force(a, b) for a, b, fused in rows]
        rows = [(a, b) for a, b, _ in rows]
        active = sorted({f for f in forces if f is not None})
        if not active:
            force = F_SELECT  # identity on every defined probe: trivially selective
        elif len(active) == 1:
            force = active[0]
        else:
            force = F_BRANCH  # different forces on different phases of the domain
        return AtomicForceRole(force=force, probes_used=len(rows), identity_probes=forces.count(None),
            mass_preserving=bool(rows) and all(a.mass == b.mass for a, b in rows),
            mass_contractive=bool(rows) and all(b.mass < a.mass for a, b in rows),
            multiset_preserving=bool(rows) and all(a.quantum_multiset_hash == b.quantum_multiset_hash for a, b in rows),
            locus_preserving=bool(rows) and all(a.locus_mask == b.locus_mask for a, b in rows),
            local_forces=tuple(forces))

    def classify_operators(self, operators, probes_by_sort, *, meter=None):
        return {op.name: self.classify(op.fn, probes_by_sort.get(op.inputs[0], ()), meter=meter)
                for op in operators if len(op.inputs) == 1}


@dataclass(frozen=True)
class AlgebraicRoleSignature:
    primary: str
    shift: str
    stabilizing: bool
    probes: int
    probe_digest: str
    non_idempotent: bool = False
    # Roles are always empirical. Only LawBundle's separately certified laws
    # may eliminate a class from a uniqueness proof.
    evidence: str = "empirical_ordering_and_transfer_only"

    def transfer_key(self):
        # Different native measures (length, magnitude, record size) must not
        # accidentally turn the role schema into a hidden family identifier.
        return (self.primary, self.shift if self.primary == "MONOTONE_STEP" else "ANY")

    def transfer_roles(self):
        """Roles can overlap: an involution can also be a preserving step."""
        result = {self.transfer_key()}
        if self.non_idempotent and self.shift != "VARIABLE_STEP":
            result.add(("MONOTONE_STEP", self.shift))
        if self.stabilizing:
            result.add(("STABILIZING_GUARD", "ANY"))
        return tuple(sorted(result))


JOB_TAGS = ("CLEANER_IDEMPOTENT", "FILTER_CONTRACTIVE", "FLIPPER_INVOLUTION",
            "STEPPER_ADVANCE", "GUARD_STABILIZER")


def universal_job_tags(role):
    """Empirical behavioral descriptors; never certified elimination rules."""
    result = []
    if role.primary == "PROJ_IDEMPOTENT":
        result.append(JOB_TAGS[0])
    if role.shift == "CONTRACTIVE_STEP":
        result.append(JOB_TAGS[1])
    if role.primary == "INVOLUTION_DUAL":
        result.append(JOB_TAGS[2])
    if role.non_idempotent and role.shift in ("PRESERVING_STEP", "EXPANSIVE_STEP"):
        result.append(JOB_TAGS[3])
    if role.stabilizing:
        result.append(JOB_TAGS[4])
    return tuple(result)


def role_signature(op, probes, meter):
    if len(op.inputs) != 1 or op.inputs[0] != op.output:
        return AlgebraicRoleSignature("UNCLASSIFIED", "UNKNOWN", False, 0, digest(()))
    rows = []
    for value in probes:
        y = op.call((value,), meter, "setup_work_units")
        repeat = op.call((value,), meter, "setup_work_units")
        yy = op.call((y,), meter, "setup_work_units")
        if freeze(y) != freeze(repeat):
            raise ValueError("nondeterministic tool cannot receive a role")
        rows.append((value, y, yy))
    if not rows:
        raise ValueError("nonempty role probes required")
    identity = all(freeze(x) == freeze(y) for x, y, _ in rows)
    idempotent = all(freeze(y) == freeze(yy) for _, y, yy in rows)
    involution = not identity and all(freeze(x) == freeze(yy) for x, _, yy in rows)
    shifts = [structural_measure(y)-structural_measure(x) for x, y, _ in rows]
    shift = ("PRESERVING_STEP" if all(v == 0 for v in shifts) else
             "CONTRACTIVE_STEP" if all(v <= 0 for v in shifts) else
             "EXPANSIVE_STEP" if all(v >= 0 for v in shifts) else "VARIABLE_STEP")
    stabilizing = not identity and len({freeze(y) for _, y, _ in rows}) < len({freeze(x) for x, _, _ in rows})
    primary = ("PROJ_IDEMPOTENT" if idempotent and all(v <= 0 for v in shifts) else
               "INVOLUTION_DUAL" if involution else
               "MONOTONE_STEP" if not idempotent and shift != "VARIABLE_STEP" else
               "STABILIZING_GUARD" if stabilizing else "UNCLASSIFIED")
    return AlgebraicRoleSignature(primary, shift, stabilizing, len(rows),
        digest([(freeze(x), freeze(y), freeze(yy)) for x, y, yy in rows]), not idempotent)


@dataclass(frozen=True)
class OpenToolbox:
    grammar: Grammar
    seed_inputs: tuple
    roles: dict
    probe_log: tuple
    callable_count: int


class OpenPythonToolboxAdapter:
    """Probe owner-supplied PURE trusted callables; infer typed overloads.

    This is not an in-process sandbox for hostile Python. The existing host
    enforces time/RSS for bounded jobs; Python side effects outside arguments
    cannot be certified away by probing. Unsupported/partial overloads are
    reported, never silently certified as total functions on unseen inputs.
    """
    SAFE_MODULES = {"math", "operator", "string"}

    def __init__(self, *, max_inputs=16, max_callables=32, max_arity=2):
        if not 2 <= max_inputs <= 128 or not 1 <= max_callables <= 64 or max_arity not in (1, 2):
            raise ValueError("bounded toolbox probe configuration required")
        self.max_inputs, self.max_callables, self.max_arity = max_inputs, max_callables, max_arity

    @classmethod
    def safe_import(cls, module, names):
        if module not in cls.SAFE_MODULES or not names or any(n.startswith("_") for n in names):
            raise ValueError("only explicitly named tools in the vetted pure-module allowlist")
        import importlib
        imported = importlib.import_module(module)
        result = tuple(getattr(imported, name) for name in names)
        if not all(callable(f) for f in result):
            raise ValueError("requested module attributes must be callables")
        return result

    @staticmethod
    def sort_of(value):
        freeze(value)  # reject opaque classes and unsafe/unreplayable values
        return {bool:"BOOL", int:"INT", float:"FLOAT", str:"STR", tuple:"TUPLE", list:"LIST", dict:"DICT", type(None):"NONE"}[type(value)]

    @staticmethod
    def callable_provenance(fn):
        try:
            source = inspect.getsource(fn)
        except (OSError, TypeError):
            source = None
        return dict(module=getattr(fn, "__module__", None), qualname=getattr(fn, "__qualname__", type(fn).__qualname__),
                    source_sha256=None if source is None else hashlib.sha256(source.encode()).hexdigest(),
                    builtin_source_unavailable=source is None,
                    limitation="source/probe fingerprint is not a proof of external-state purity")

    def ingest(self, callables, seed_input_generator, *, meter, constants=(), conditionals=False):
        functions = tuple(islice(iter(callables), self.max_callables+1))
        if not functions or len(functions) > self.max_callables or not all(callable(f) for f in functions):
            raise ValueError("bounded raw callable collection required")
        iterator = iter(seed_input_generator() if callable(seed_input_generator) else seed_input_generator)
        inputs, seen = [], set()
        for _ in range(self.max_inputs):
            try:
                value = next(iterator)
            except StopIteration:
                break
            meter.charge("setup_work_units")
            key = freeze(value)
            if key not in seen:
                inputs.append(deepcopy(value))
                seen.add(key)
        if len(inputs) < 2:
            raise ValueError("at least two distinct seed inputs required")
        by_sort = {}
        for value in inputs:
            by_sort.setdefault(self.sort_of(value), []).append(value)
        operators, log = [], []
        for index, fn in enumerate(functions):
            meter.charge("setup_work_units")
            provenance = self.callable_provenance(fn)
            try:
                signature = inspect.signature(fn)
                arity = sum(p.default is inspect.Parameter.empty and p.kind in
                    (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) for p in signature.parameters.values())
            except (ValueError, TypeError):
                arity = 1
            if not 1 <= arity <= self.max_arity:
                log.append(dict(callable_index=index, status="unsupported_arity", arity=arity))
                continue
            for sorts in product(sorted(by_sort), repeat=arity):
                outputs, errors = [], []
                # Bound binary cartesian probes as well as the input generator.
                for n, args in enumerate(product(*(by_sort[t] for t in sorts))):
                    if n >= self.max_inputs:
                        break
                    before = freeze(args)
                    try:
                        first, second = [], []
                        for result_list in (first, second):
                            copied = deepcopy(args)
                            meter.charge("setup_work_units")
                            value = fn(*copied)
                            if freeze(copied) != before:
                                raise ValueError("tool mutated a supplied argument")
                            result_list.append(value)
                        if freeze(first[0]) != freeze(second[0]):
                            raise ValueError("tool is nondeterministic")
                        outputs.append(self.sort_of(first[0]))
                    except Exception as exc:
                        errors.append(type(exc).__name__+": "+str(exc))
                if errors or not outputs or len(set(outputs)) != 1:
                    log.append(dict(callable_index=index, inputs=sorts, status="rejected_overload", errors=errors))
                    continue
                name = "op_"+str(len(operators))
                operators.append(Operator(name, sorts, outputs[0], fn))
                log.append(dict(callable_index=index, inputs=sorts, output=outputs[0], status="probed_only", operator=name, provenance=provenance))
        if not operators:
            raise ValueError("no deterministic typed overload survived supplied probes")
        input_sort = self.sort_of(inputs[0])
        grammar = Grammar(input_sort, tuple(operators), tuple(constants), conditionals=conditionals)
        roles = AutoOperatorFingerprinter().fingerprint_roles(operators, by_sort, meter=meter)
        return OpenToolbox(grammar, tuple(v for v in inputs if self.sort_of(v) == input_sort), roles, tuple(log), len(functions))


class OpenPythonToolboxSandbox:
    """Bounded typed orchestration for owner-supplied TRUSTED PURE tools.

    A Python function is not made safe by its name or finite probes. This API
    rejects unsupported values/arity and uses a vetted AST child-process gate
    for invented helpers. The outer Wave24 host supplies CPU/wall/RSS limits.
    It is NOT a hostile arbitrary-Python security sandbox or a totality proof.
    """
    @classmethod
    def from_callables(cls, callables, seed_inputs, *, meter=None, frozen=False, resource_host=None):
        from nexus.wave24_self_evolving_loop import DualMemoryLearner
        result = cls()
        result.meter = meter if meter is not None else WorkMeter()
        result.toolbox = OpenPythonToolboxAdapter().ingest(callables, seed_inputs, meter=result.meter)
        result.frozen = bool(frozen)
        result.domain = "OPEN_PYTHON_TARGET" if frozen else "OPEN_PYTHON_SOURCE"
        result.learner = DualMemoryLearner(meter=result.meter, resource_host=resource_host)
        result.learner.enter(result.domain, result.toolbox.grammar, result.toolbox.roles, result.toolbox.seed_inputs,
                             frozen=frozen)
        return result

    def solve(self, public_io, query, *, output_sort=None, invent=False):
        from nexus.wave24_self_evolving_loop import PublicTask
        task = PublicTask(tuple(public_io), query, output_sort or OpenPythonToolboxAdapter.sort_of(public_io[0][1]))
        return self.learner.solve_task(self.domain, task, invent=invent)

    def learn_revealed_source(self, *, observed_query):
        if self.frozen:
            raise ValueError("target sandbox cannot learn from assessment outcomes")
        return self.learner.learn_last_source(self.domain, observed_query=observed_query)


def measures(value):
    result = {}
    if isinstance(value, (str, tuple, list, dict)):
        result["len"] = len(value)
    if type(value) is int:
        result["abs_max"] = abs(value)
        result["bit_popcount"] = abs(value).bit_count()
    if type(value) in (tuple, list) and all(type(v) is int for v in value):
        result["abs_max"] = max((abs(v) for v in value), default=0)
        if all(v in (0, 1) for v in value):
            result["bit_popcount"] = sum(value)
    if type(value) is dict:
        result["key_set"] = frozenset(freeze(k) for k in value)
    if type(value) is str:
        result["char_set"] = frozenset(value)
    return result


@dataclass(frozen=True)
class Law:
    operator: str
    kind: str
    constant_key: Any = None
    measure: str | None = None


@dataclass
class LawBundle:
    laws: tuple[Law, ...]
    certified: bool
    carriers: dict
    operators: dict
    probe_digest: str
    hypotheses: tuple[Law, ...] = ()
    pruned: int = 0

    @property
    def certified_structural_laws(self):
        return self.laws if self.certified else ()

    @property
    def empirical_probe_priors(self):
        return self.hypotheses

    def priority(self, expr):
        """Ordering only. A prior is never a discard or completeness proof."""
        if expr.kind != "apply":
            return (0, repr(expr.key()))
        penalty = 0
        for law in self.empirical_probe_priors:
            if law.operator != expr.value:
                continue
            if law.kind == "commutative" and len(expr.children) == 2:
                penalty += repr(expr.children[0].key()) > repr(expr.children[1].key())
            if law.kind in ("idempotent", "involution"):
                child = expr.children[0]
                penalty += child.kind == "apply" and child.value == expr.value
        return (penalty, repr(expr.key()))

    def _inside(self, sort, values):
        allowed = {freeze(v) for v in self.carriers.get(sort, ())}
        return all(freeze(v) in allowed for v in values)

    def redundant(self, expr, inputs, grammar, meter, *, outputs_for=None):
        """Only local, cost-nonincreasing rewrites; no target-family heuristics."""
        if not self.certified or expr.kind != "apply":
            return False
        op = grammar.ops[expr.value]
        if self.operators.get(op.name) is not op:
            return False
        applicable = [l for l in self.laws if l.operator == op.name]
        if not applicable:
            return False
        values = outputs_for or (lambda e: [eval_expr(e, x, grammar.ops, meter) for x in inputs])
        args = [values(c) for c in expr.children]
        if not all(self._inside(sort, vs) for sort, vs in zip(op.inputs, args)):
            return False
        for law in applicable:
            remove = False
            if law.kind == "commutative":
                remove = repr(expr.children[0].key()) > repr(expr.children[1].key())
            elif law.kind in ("idempotent", "involution"):
                child = expr.children[0]
                remove = child.kind == "apply" and child.value == op.name
                if remove:
                    original = values(child.children[0])
                    remove = self._inside(op.inputs[0], original)
            elif law.kind.startswith(("identity_", "annihilator_")):
                side = 1 if law.kind.endswith("right") else 0
                remove = expr.children[side].kind == "const" and freeze(expr.children[side].value) == law.constant_key
            if remove:
                self.pruned += 1
                meter.charge("law_prune_work_units")
                return True
        return False

    def root_measure_possible(self, operator, args, target, meter):
        """Necessary conditions for THIS root application, never its ancestors.

        The caller must supply exact operands. Local length contraction must not
        be misused as a bound on a later expanding parent.
        """
        meter.charge("law_check_work_units")
        op = self.operators[operator]
        if not self.certified or len(args) != 1 or not self._inside(op.inputs[0], args):
            return True
        source_m, target_m = measures(args[0]), measures(target)
        for law in self.laws:
            if law.operator != operator or law.measure not in target_m or law.measure not in source_m:
                continue
            a, b = source_m[law.measure], target_m[law.measure]
            if law.kind == "measure_equal" and a != b:
                return False
            if law.kind == "measure_contract" and not b <= a:
                return False
        return True


class AutoOperatorFingerprinter:
    def __init__(self, *, probe_cap=10_000):
        if type(probe_cap) is not int or probe_cap < 1:
            raise ValueError("positive bounded probe cap")
        self.probe_cap = probe_cap

    def fingerprint_jobs(self, operators, carriers, *, meter=None):
        roles = self.fingerprint_roles(operators, carriers, meter=meter)
        return {name: universal_job_tags(role) for name, role in roles.items()}

    def fingerprint_roles(self, operators, carriers, *, meter=None):
        meter = meter if meter is not None else WorkMeter()
        operators = tuple(operators)
        budget, result = self.probe_cap, {}
        for op in operators:
            probes = tuple(carriers.get(op.inputs[0], ()))[:max(0, budget//3)]
            if not probes or len(op.inputs) != 1 or op.inputs[0] != op.output:
                result[op.name] = AlgebraicRoleSignature("UNCLASSIFIED", "UNKNOWN", False, 0, digest(()))
                continue
            result[op.name] = role_signature(op, probes, meter)
            budget -= 3*len(probes)
        return result

    def discover(self, operators, carriers, *, complete_carriers=False, meter=None):
        meter = meter if meter is not None else WorkMeter()
        operators = tuple(operators)
        if len({o.name for o in operators}) != len(operators):
            raise ValueError("duplicate anonymous operator")
        carriers = {k: tuple(v) for k, v in carriers.items()}
        if any(not v or len({freeze(x) for x in v}) != len(v) for v in carriers.values()):
            raise ValueError("nonempty distinct carriers required")
        required = sum(2 * math_product(len(carriers.get(t, ())) for t in o.inputs) for o in operators)
        complete = bool(complete_carriers and required <= self.probe_cap)
        tables, raw = {}, []
        remaining = self.probe_cap
        for op in operators:
            if any(t not in carriers for t in (*op.inputs, op.output)):
                complete = False
                continue
            table = {}
            allowed = {freeze(v) for v in carriers[op.output]}
            for args in product(*(carriers[t] for t in op.inputs)):
                if remaining < 2:
                    complete = False
                    break
                first = op.call(args, meter, "setup_work_units")
                second = op.call(args, meter, "setup_work_units")
                remaining -= 2
                if freeze(first) != freeze(second):
                    raise ValueError("nondeterministic operator cannot be certified")
                if freeze(first) not in allowed:
                    complete = False
                key = tuple(freeze(a) for a in args)
                table[key] = first
                raw.append((op.name, key, freeze(first)))
            tables[op.name] = table
        found = []
        for op in operators:
            table = tables.get(op.name, {})
            if not table:
                continue
            if len(op.inputs) == 1 and op.inputs[0] == op.output:
                rows = [(key[0], value) for key, value in table.items()]
                if all((freeze(y),) in table and freeze(table[(freeze(y),)]) == freeze(y) for _, y in rows):
                    found.append(Law(op.name, "idempotent"))
                if all((freeze(y),) in table and freeze(table[(freeze(y),)]) == x for x, y in rows):
                    found.append(Law(op.name, "involution"))
                # Reconstruct inputs using the complete typed carrier, not tags.
                source = {freeze(v): v for v in carriers[op.inputs[0]]}
                common = set.intersection(*(set(measures(source[x])) & set(measures(y)) for x, y in rows))
                for measure in sorted(common):
                    pairs = [(measures(source[x])[measure], measures(y)[measure]) for x, y in rows]
                    if all(a == b for a, b in pairs):
                        found.append(Law(op.name, "measure_equal", measure=measure))
                    elif all(b <= a for a, b in pairs):
                        found.append(Law(op.name, "measure_contract", measure=measure))
            if len(op.inputs) == 2 and op.inputs[0] == op.inputs[1]:
                if all((b, a) in table and freeze(v) == freeze(table[(b, a)]) for (a, b), v in table.items()):
                    found.append(Law(op.name, "commutative"))
                if op.output != op.inputs[0]:
                    continue
                keys = {freeze(v) for v in carriers[op.output]}
                for c in sorted(keys, key=repr):
                    for side in ("left", "right"):
                        pairs = [(k, freeze(table[(c, k) if side == "left" else (k, c)]))
                                 for k in keys if ((c, k) if side == "left" else (k, c)) in table]
                        if len(pairs) != len(keys):
                            continue
                        if all(k == result for k, result in pairs):
                            found.append(Law(op.name, "identity_" + side, c))
                        if all(result == c for _, result in pairs):
                            found.append(Law(op.name, "annihilator_" + side, c))
        fingerprint = digest(raw)
        return LawBundle(tuple(found) if complete else (), complete, carriers,
                         {o.name: o for o in operators}, fingerprint,
                         () if complete else tuple(found))


def math_product(values):
    result = 1
    for value in values:
        result *= value
    return result
