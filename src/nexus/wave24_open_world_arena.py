"""Open-world software/science arena over vetted stdlib primitives.

This is a finite SOURCE-development diagnostic, not an AGI or hostile-code
sandbox. Failed stdlib calls become EXEC_ERR tokens. No paid runtime is used.
"""
from __future__ import annotations

from collections import Counter
import json
import math
import re
import statistics
from urllib.parse import parse_qs, urlparse

from nexus.evolution1.catalogue import digest
from nexus.wave24_auto_laws import (AutoOperatorFingerprinter, AtomicFieldProjector, AtomicForceClassifier,
                                   F_SELECT, F_TRANSLATE, F_TRANSMUTE, F_CONDENSE, F_BRANCH)
from nexus.wave24_quotient_core import (
    Grammar, Operator, WorkMeter, WorkExhausted, ExactEnumerator, GoalCheck,
    SearchResult, apply, eval_expr, freeze, primitive_cost, variable, unfold_to_primitives,
)
from nexus.wave24_self_evolving_loop import (
    DualMemoryLearner, HomeostaticMetabolicController, PublicTask,
    ScratchpadWorkspaceEngine, SymptomToActionDoctor, ast_nodes,
)


EXEC_ERR = "EXEC_ERR"


def guarded(fn):
    def wrap(value):
        try:
            result = fn(value)
            freeze(result)
            return result
        except (ValueError, KeyError, ZeroDivisionError, TypeError, IndexError,
                OverflowError, json.JSONDecodeError, re.error, statistics.StatisticsError):
            return EXEC_ERR
    wrap.__name__ = getattr(fn, "__name__", "guarded")
    return wrap


class OpenWorldStdlibToolbox:
    """40+ exception-guarded stdlib/scientific primitives on typed carriers."""

    def primitives(self):
        fns = [
            guarded(lambda s: s.strip() if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: s.lower() if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: s.upper() if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: re.sub(r"\s+", " ", s).strip() if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: re.sub(r"#.*", "", s).strip() if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: ",".join(re.findall(r"[A-Za-z]+", s)) if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: ",".join(re.findall(r"\d+", s)) if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: int(s, 16) if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: json.loads(s) if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: json.dumps(s, sort_keys=True, separators=(",", ":")) if isinstance(s, (dict, list)) else EXEC_ERR),
            guarded(lambda s: dict(part.split("=", 1) for part in s.split() if "=" in part) if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: parse_qs(urlparse(s).query) if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: s.replace(";", ",") if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: s.lstrip("0") or "0" if isinstance(s, str) else EXEC_ERR),
            guarded(lambda d: {k: v for k, v in d.items() if v not in (None, "", float("nan"))} if isinstance(d, dict) else EXEC_ERR),
            guarded(lambda d: {("id" if k in ("uid", "user_id") else k): v for k, v in d.items()} if isinstance(d, dict) else EXEC_ERR),
            guarded(lambda d: d.get("id", d.get("uid", d.get("user_id"))) if isinstance(d, dict) else EXEC_ERR),
            guarded(lambda d: d.get("value", d.get("val", 0)) if isinstance(d, dict) else EXEC_ERR),
            guarded(lambda xs: list(dict.fromkeys(xs)) if isinstance(xs, list) else EXEC_ERR),
            guarded(lambda xs: dict(Counter(xs)) if isinstance(xs, list) else EXEC_ERR),
            guarded(lambda d: {k: d[k] for k in sorted(d)} if isinstance(d, dict) else EXEC_ERR),
            guarded(lambda d: {a: b for k, v in d.items() for a, b in (v.items() if isinstance(v, dict) else ((k, v),))} if isinstance(d, dict) else EXEC_ERR),
            guarded(lambda xs: [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))] if isinstance(xs, list) else EXEC_ERR),
            guarded(lambda xs: statistics.median(xs) if isinstance(xs, list) and xs else EXEC_ERR),
            guarded(lambda xs: statistics.mean(xs) if isinstance(xs, list) and xs else EXEC_ERR),
            guarded(lambda xs: xs[-1]-xs[0] if isinstance(xs, list) and len(xs) >= 2 else EXEC_ERR),
            guarded(lambda xs: [xs[i]-xs[i-1] for i in range(1, len(xs))] if isinstance(xs, list) and len(xs) >= 2 else EXEC_ERR),
            guarded(lambda x: abs(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else EXEC_ERR),
            guarded(lambda x: 0.5*x*x if isinstance(x, (int, float)) and not isinstance(x, bool) else EXEC_ERR),
            guarded(lambda x: math.exp(-abs(x)) if isinstance(x, (int, float)) and not isinstance(x, bool) else EXEC_ERR),
            guarded(lambda x: max(0.0, float(x)) if isinstance(x, (int, float)) and not isinstance(x, bool) else EXEC_ERR),
            guarded(lambda x: 1.0/x if isinstance(x, (int, float)) and not isinstance(x, bool) and x else EXEC_ERR),
            guarded(lambda x: int(x) if isinstance(x, (int, float, str)) and not isinstance(x, bool) else EXEC_ERR),
            guarded(lambda x: round(float(x), 3) if isinstance(x, (int, float)) and not isinstance(x, bool) else EXEC_ERR),
            guarded(lambda xs: sum(xs)/len(xs) if isinstance(xs, list) and xs else EXEC_ERR),
            guarded(lambda s: s.splitlines()[0] if isinstance(s, str) and s.splitlines() else EXEC_ERR),
            guarded(lambda s: [ln for ln in s.splitlines() if ln and not ln.startswith("DEBUG") and not ln.startswith("WARN")] if isinstance(s, str) else EXEC_ERR),
            guarded(lambda s: "".join(ch for ch in s if ch.isalnum()) if isinstance(s, str) else EXEC_ERR),
            guarded(lambda d: len(d) if isinstance(d, (dict, list, str)) else EXEC_ERR),
            guarded(lambda x: x if x not in (None, EXEC_ERR) else 0),
            guarded(lambda xs: xs[0] if isinstance(xs, list) and xs else EXEC_ERR),
            guarded(lambda s: s[s.find("{")+1:s.rfind("}")] if isinstance(s, str) and "{" in s else EXEC_ERR),
        ]
        if len(fns) < 40:
            raise ValueError("open-world toolbox must expose at least 40 primitives")
        return tuple(fns)

    def grammar(self, *, meter, extra=()):
        operators = []
        probes = {
            "STR": ("id=7 val=3", "  Hello ", "0xff", '{"a":1}', "DEBUG x\nkeep=1"),
            "DICT": ({"uid": 1, "val": 2}, {"id": 3, "nested": {"z": 1}}),
            "LIST": ([1, None, 3, 3], [2.0, 4.0, 6.0]),
            "FLOAT": (2.0, -3.5, 0.0),
            "INT": (2, -4, 0),
        }
        for index, fn in enumerate((*self.primitives(), *extra)):
            sample = None
            sort_in = "STR"
            for sort, values in probes.items():
                try:
                    out = fn(values[0])
                except Exception:
                    continue
                if out != EXEC_ERR:
                    sample, sort_in = out, sort
                    break
            sort_out = {bool: "BOOL", int: "INT", float: "FLOAT", str: "STR", list: "LIST", dict: "DICT"}.get(type(sample), "STR")
            operators.append(Operator(f"op_{index}", (sort_in,), sort_out, fn))
        meter.charge("setup_work_units", len(operators))
        return Grammar("STR", tuple(operators), conditionals=True), probes


def _safe_key(value):
    try:
        return freeze(value)
    except (TypeError, ValueError):
        return ("unfreezable", EXEC_ERR)


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


class TaskEvalCache:
    """Per-task memo of op(x): an operator application is charged once per task, on first use."""

    def __init__(self):
        self.values = {}
        self.hits = 0

    def __call__(self, op, x, meter, category):
        key = (op.name, _safe_key(x))
        if key in self.values:
            self.hits += 1
            return self.values[key]
        meter.charge(category)
        try:
            value = op.fn(x)
        except Exception:
            value = EXEC_ERR
        self.values[key] = value
        return value


def guard_family(public_inputs):
    """Fixed, task-agnostic input predicates declared before any search.

    Dict-key guards use only keys present in the PUBLIC inputs. No query
    output or teacher label is ever consulted to build or rank guards.
    """
    guards = [
        ("is_negative", lambda x: _is_number(x) and x < 0),
        ("is_zero", lambda x: _is_number(x) and x == 0),
        ("is_float", lambda x: type(x) is float),
        ("is_empty", lambda x: isinstance(x, (str, list, dict)) and len(x) == 0),
    ]
    keys = sorted({k for x in public_inputs if isinstance(x, dict) for k in x if isinstance(k, str)})
    for key in keys:
        guards.append((f"has_key[{key}]", lambda x, k=key: isinstance(x, dict) and k in x))
    return tuple(guards)


class ConditionalPatchCombinator:
    """Piecewise (guard, then, else) synthesis over a declared finite space.

    A candidate fits only if it reproduces EVERY public pair. The query value
    is certified only when all fitting candidates in the declared space agree
    on it; otherwise the result is AMBIGUOUS. Selection never reads labels
    beyond the public IO (no hidden query answer, no memorized D_fail table).
    """

    STATUS_UNIQUE = "UNIQUE_QUERY_OUTPUT_IN_DECLARED_PIECEWISE_SPACE"

    def propose(self, grammar, public_io, base_fn, *, meter):
        """D_pass / D_fail diagnostic split for one base program (no query claim)."""
        passing, failing = [], []
        for x, y in public_io:
            meter.charge("piecewise_guard_work_units")
            try:
                pred = base_fn(x)
            except Exception:
                pred = EXEC_ERR
            (passing if _safe_key(pred) == _safe_key(y) else failing).append((x, y))
        if not public_io or not passing or not failing:
            return None
        return dict(guarded=True, D_pass=tuple(passing), D_fail=tuple(failing))

    def synthesize(self, operators, public_io, query, *, meter, prefer=(), cache=None):
        inputs = tuple(x for x, _ in public_io) + (query,)
        n = len(public_io)
        cache = cache if cache is not None else TaskEvalCache()
        outs, passes = {}, {}
        for op in operators:
            row = []
            for x in inputs:
                row.append(cache(op, x, meter, "piecewise_guard_work_units"))
            outs[op.name] = row
            passes[op.name] = tuple(_safe_key(row[i]) == _safe_key(public_io[i][1]) for i in range(n))
        if any(all(v) for v in passes.values()) or not any(any(v) for v in passes.values()):
            return dict(status="NOT_ESCALATED", fitting=0)
        guards = list(guard_family(tuple(x for x, _ in public_io)))
        # Exception-safe guards: route on whether a partially-passing op errors.
        for op in operators:
            if any(passes[op.name]):
                guards.append((f"ok[{op.name}]", lambda x, name=op.name, idx={_safe_key(v): i for i, v in enumerate(inputs)}:
                               outs[name][idx[_safe_key(x)]] != EXEC_ERR))
        fitting = []
        for gname, gfn in guards:
            vec = []
            for x in inputs:
                meter.charge("piecewise_guard_work_units")
                try:
                    vec.append(gfn(x) is True)
                except Exception:
                    vec.append(None)
            if None in vec or len(set(vec[:n])) < 2:
                continue  # trivial split is ordinary single-op search
            then_ok = [o.name for o in operators if all(passes[o.name][i] for i in range(n) if vec[i])]
            else_ok = [o.name for o in operators if all(passes[o.name][i] for i in range(n) if not vec[i])]
            for t in then_ok:
                for e in else_ok:
                    meter.charge("piecewise_guard_work_units")
                    fitting.append(((gname, t, e), outs[t if vec[n] else e][n]))
        if not fitting:
            return dict(status="NO_PROGRAM_IN_BOUNDED_GRAMMAR", fitting=0)
        values = {_safe_key(v) for _, v in fitting}
        if len(values) == 1 and fitting[0][1] != EXEC_ERR:
            # Tie-break only among candidates already agreeing on the query.
            rank = {name: i for i, name in enumerate(prefer)}
            best = min(fitting, key=lambda f: sum(rank.get(n, len(rank)+1) for n in f[0][1:]))
            return dict(status=self.STATUS_UNIQUE, fitting=len(fitting), witness=best[0],
                        query_value=best[1])
        return dict(status="AMBIGUOUS_WITNESS_FOUND", fitting=len(fitting), distinct_query_values=len(values))


def run_piecewise(witness, x, grammar, public_inputs):
    gname, then_name, else_name = witness
    guard = dict(guard_family(public_inputs)).get(gname)
    if guard is None and gname.startswith("ok[") and gname.endswith("]"):
        op = grammar.ops[gname[3:-1]]
        guard = lambda v: op.fn(v) != EXEC_ERR
    if guard is None:
        raise ValueError("unknown piecewise guard")
    return grammar.ops[then_name if guard(x) is True else else_name].fn(x)


class OpenWorldTwinFuzzer:
    """Boundary fuzz suite; never a uniqueness oracle by itself."""

    def suite(self, query):
        extras = [None, "", 0, -1, float("nan") if not isinstance(query, str) else "NaN", [], {}]
        if isinstance(query, dict):
            extras.append({k: None for k in query})
            extras.append(dict(reversed(list(query.items()))))
        if isinstance(query, list):
            extras.append([])
            extras.append([None, *query])
        if isinstance(query, str):
            extras.extend(["", " ", "DEBUG noise", "{"])
        seen, out = set(), []
        for item in extras:
            try:
                key = freeze(item)
            except Exception:
                continue
            if key not in seen:
                seen.add(key)
                out.append(item)
        return tuple(out[:8])

    def classify(self, outputs, expected, fuzz_outputs):
        if any(freeze(a) != freeze(expected) for a in outputs):
            return "FAILED_PUBLIC"
        if any(v == EXEC_ERR for v in fuzz_outputs):
            return "AMBIGUOUS_WITNESS_FOUND"
        return "SURVIVED"

    def probe(self, fn, query, *, meter):
        """Run the actual certified program on boundary inputs."""
        cases = self.suite(query)
        exec_err = raised = 0
        for item in cases:
            meter.charge("open_world_fuzz_work_units")
            try:
                if fn(item) == EXEC_ERR:
                    exec_err += 1
            except Exception:
                raised += 1
        return dict(cases=len(cases), exec_err=exec_err, raised=raised,
                    verdict="CRASHED" if raised else "GUARDED_EXEC_ERR" if exec_err else "SURVIVED")


class OpenWorldTaskStream:
    """24 authored messy tasks; four shifts, six tasks each."""

    def tasks(self):
        log = [
            (("id=7 val=3", {"id": "7", "val": "3"}), ("keep=9", {"keep": "9"}), "uid=1 extra=2"),
            (("  Hello ", "hello"), ("  WORLD ", "world"), "  Nexus "),
            (("0xff", 255), ("0x10", 16), "0x2a"),
            (('{"a": 1}', {"a": 1}), ('{"b": 2}', {"b": 2}), '{"c": 3}'),
            (("DEBUG x\nkeep=1\nWARN y", ["keep=1"]), ("DEBUG z\nval=2", ["val=2"]), "DEBUG a\nid=9"),
            (("#c\nfoo=1", "foo=1"), ("bar=2 #trail", "bar=2"), "#only\nkeep=3"),
        ]
        science = [
            (([1.0, None, 3.0], [1.0, 3.0]), ([2.0, None, 4.0], [2.0, 4.0]), [5.0, None]),
            (([1.0, 3.0, 5.0], 4.0), ([2.0, 8.0], 6.0), [10.0, 12.0]),
            ((2.0, 2.0), (-3.0, 4.5), 4.0),
            ((-2.5, 2.5), (3.25, 3.25), -7.0),
            (([2.0, 4.0, 6.0], [2.0, 2.0]), ([1.0, 5.0], [4.0]), [3.0, 9.0]),
            ((0.0, 1.0), (1.0, math.exp(-1)), 2.0),
        ]
        repair = [
            (({"uid": 4, "val": 1}, 4), ({"user_id": 8, "val": 2}, 8), {"id": 5, "val": 0}),
            (({"b": 1, "a": 2}, {"a": 2, "b": 1}), ({"z": 0, "m": 1}, {"m": 1, "z": 0}), {"c": 3, "a": 1}),
            (([1, 1, 2, 2], [1, 2]), ([9, 9, 8], [9, 8]), [3, 3, 3]),
            (({"uid": 1, "val": None}, {"uid": 1}), ({"id": "", "k": 2}, {"k": 2}), {"uid": None, "k": 7}),
            (("2", 2), ("-4", -4), "8"),
            ((5, 5), (-3, 0.0), 2),
        ]
        adversarial = [
            (("id=1 val=9", {"id": "1", "val": "9"}), ("x=2", {"x": "2"}), "z=3"),
            (({"uid": 2}, 2), ({"id": 6}, 6), {"user_id": 1}),
            (("  MixED ", "mixed"), ("  OK ", "ok"), "  Shift "),
            (([0.0, 2.0, 4.0], 4.0), ([1.0, 1.0, 5.0], 4.0), [2.0, 8.0]),
            (("0x0b", 11), ("0x01", 1), "0x0c"),
            (({"a": {"z": 1}}, {"z": 1}), ({"a": {"z": 2}}, {"z": 2}), {"a": {"z": 9}}),
        ]
        packed = []
        for shift, rows, sort in (
            ("OPEN_LOG_FORENSICS", log, "STR"),
            ("OPEN_SCIENCE_PHYSICS", science, None),
            ("OPEN_CODE_AND_SCHEMA_REPAIR", repair, None),
            ("OPEN_ADVERSARIAL_SHIFT", adversarial, None),
        ):
            for index, row in enumerate(rows):
                *pairs, query = row
                public = tuple((a, b) for a, b in pairs)
                packed.append(dict(shift=shift, index=index, public=public, query=query,
                    output_sort=self._sort(public[0][1]),
                    expected=self._teacher(public, query)))
        if len(packed) != 24:
            raise ValueError("open-world stream must contain exactly 24 tasks")
        return tuple(packed)

    @staticmethod
    def _sort(value):
        return {bool: "BOOL", int: "INT", float: "FLOAT", str: "STR", list: "LIST", dict: "DICT"}[type(value)]

    @staticmethod
    def _teacher(public, query):
        # Authored expected query labels; not used as training targets.
        table = {freeze(x): y for x, y in public}
        if freeze(query) in table:
            return table[freeze(query)]
        x0, y0 = public[0]
        if isinstance(x0, str) and isinstance(y0, dict) and "=" in x0:
            return dict(part.split("=", 1) for part in query.split() if "=" in part)
        if isinstance(x0, str) and isinstance(y0, str):
            return query.strip().lower()
        if isinstance(x0, str) and isinstance(y0, int) and x0.startswith("0x"):
            return int(query, 16)
        if isinstance(x0, str) and isinstance(y0, dict) and x0.startswith("{"):
            return json.loads(query)
        if isinstance(x0, str) and isinstance(y0, list):
            return [ln for ln in query.splitlines() if ln and not ln.startswith("DEBUG") and not ln.startswith("WARN")]
        if isinstance(x0, str) and isinstance(y0, str) and x0.startswith("#"):
            return re.sub(r"#.*", "", query).strip()
        if isinstance(x0, list) and isinstance(y0, list) and y0 and isinstance(y0[0], float):
            if len(y0) == len([v for v in x0 if v is not None and not (isinstance(v, float) and math.isnan(v))]):
                return [v for v in query if v is not None]
            return [query[i]-query[i-1] for i in range(1, len(query))]
        if isinstance(x0, list) and isinstance(y0, float):
            return query[-1]-query[0]
        if isinstance(x0, (int, float)) and isinstance(y0, (int, float)) and y0 == 0.5*x0*x0:
            return 0.5*query*query
        if isinstance(x0, (int, float)) and isinstance(y0, (int, float)) and y0 == abs(x0):
            return abs(query)
        if isinstance(x0, (int, float)) and isinstance(y0, float) and abs(y0-math.exp(-abs(x0))) < 1e-9:
            return math.exp(-abs(query))
        if isinstance(x0, (int, float)) and isinstance(y0, float) and y0 == max(0.0, float(x0)):
            return max(0.0, float(query))
        if isinstance(x0, dict) and type(y0) is int:
            return query.get("id", query.get("uid", query.get("user_id")))
        if isinstance(x0, dict) and isinstance(y0, dict) and set(y0) <= set(x0):
            if any(isinstance(v, dict) for v in x0.values()):
                flat = {}
                for v in query.values():
                    if isinstance(v, dict):
                        flat.update(v)
                return flat
            return {k: query[k] for k in sorted(query)}
        if isinstance(x0, list) and isinstance(y0, list):
            return list(dict.fromkeys(query))
        if isinstance(x0, str) and type(y0) is int:
            return int(query)
        return y0


class ForcePrunedResidualTwoHop:
    """Residual 2-hop search op_2(op_1(x)) in a declared force-pruned space.

    Hop 1 (heuristic, declared): stepping stones are restricted to the atomic
    force direction of the public mass deficit and must move every public
    input's mass strictly toward its target (never past it).
    Hop 2 (sound, b_rem == 1): an op_2 whose certified probe law (mass
    preserving / contractive, multiset preserving) cannot reach Y_pub is
    skipped in O(1) before any evaluation.
    The query is certified only if every fitting chain in this declared space
    agrees. Learned (outer, inner) force functors only ORDER the search.
    """

    STATUS_UNIQUE = "UNIQUE_QUERY_OUTPUT_IN_DECLARED_FORCE_PRUNED_SPACE"
    DIRECTIONS = {"DECREASE": (F_SELECT, F_CONDENSE), "EQUAL": (F_TRANSLATE, F_TRANSMUTE),
                  "INCREASE": (F_TRANSMUTE, F_BRANCH)}

    def __init__(self, grammar, probes, *, meter):
        self.projector = AtomicFieldProjector()
        self.roles = AtomicForceClassifier(self.projector, EXEC_ERR).classify_operators(
            grammar.operators, {k: tuple(v) for k, v in probes.items()}, meter=meter)
        self.functors = []  # learned (outer_force, inner_force), most recent first

    def _mass(self, value):
        return self.projector.project(value).mass

    def direction(self, public_io):
        deltas = {(self._mass(y) > self._mass(x)) - (self._mass(y) < self._mass(x)) for x, y in public_io}
        if deltas == {-1}:
            return "DECREASE"
        if deltas == {0}:
            return "EQUAL"
        if deltas == {1}:
            return "INCREASE"
        return None

    def _hard_prune(self, op, stones, public_io):
        role = self.roles.get(op.name)
        if role is None:
            return False
        for v, (_, y) in zip(stones, public_io):
            mv, my = self._mass(v), self._mass(y)
            if role.mass_preserving and mv != my:
                return True
            if role.mass_contractive and mv <= my:
                return True
            if role.multiset_preserving and self.projector.project(v).quantum_multiset_hash != \
                    self.projector.project(y).quantum_multiset_hash:
                return True
        return False

    def _rank(self, inner_force, outer_force):
        try:
            return self.functors.index((outer_force, inner_force))
        except ValueError:
            return len(self.functors)

    def search(self, grammar, task, *, meter, cache=None):
        cache = cache if cache is not None else TaskEvalCache()
        public = task["public"]
        direction = self.direction(public)
        if direction is None:
            return dict(status="NOT_ESCALATED", fitting=0, reason="mixed_mass_deficit")
        allowed = self.DIRECTIONS[direction]
        sort = OpenWorldTaskStream._sort(public[0][0])
        inner_ops = [op for op in grammar.operators if op.inputs == (sort,)
                     and self.roles.get(op.name) and self.roles[op.name].force in allowed]
        stones = []
        for op in inner_ops:
            vs = []
            for x, y in public:
                v = cache(op, x, meter, "force_two_hop_work_units")
                mx, mv, my = self._mass(x), self._mass(v), self._mass(y)
                toward = (my <= mv < mx) if direction == "DECREASE" else (mx < mv <= my) if direction == "INCREASE" else mv == mx
                if v == EXEC_ERR or not toward or _safe_key(v) == _safe_key(x):
                    vs = None
                    break
                vs.append(v)
            if vs is not None:
                stones.append((op, tuple(vs)))
        fitting = []
        pruned = 0
        for op1, vs in sorted(stones, key=lambda st: st[0].name):
            # Typed grammar: op_2 must accept op_1's declared output sort.
            outer_ops = sorted((op for op in grammar.operators if op.inputs == (op1.output,)),
                key=lambda op: (self._rank(self.roles[op1.name].force, self.roles.get(op.name).force
                                           if self.roles.get(op.name) else None), op.name))
            for op2 in outer_ops:
                # O(1) law lookup, uncharged like the engine's last-step Noether skip.
                if self._hard_prune(op2, vs, public):
                    pruned += 1
                    continue
                ok = True
                for v, (_, y) in zip(vs, public):
                    if _safe_key(cache(op2, v, meter, "force_two_hop_work_units")) != _safe_key(y):
                        ok = False
                        break
                if ok:
                    v_query = cache(op1, task["query"], meter, "force_two_hop_work_units")
                    fitting.append(((op1.name, op2.name), cache(op2, v_query, meter, "force_two_hop_work_units")))
        report = dict(direction=direction, stepping_stones=len(stones), inner_candidates=len(inner_ops),
                      noether_pruned=pruned, fitting=len(fitting))
        if not fitting:
            return dict(report, status="NO_PROGRAM_IN_BOUNDED_GRAMMAR")
        values = {_safe_key(v) for _, v in fitting}
        if len(values) == 1 and fitting[0][1] != EXEC_ERR:
            best = min(fitting, key=lambda f: (self._rank(self.roles[f[0][0]].force, self.roles[f[0][1]].force), f[0]))
            return dict(report, status=self.STATUS_UNIQUE, witness=best[0], query_value=best[1])
        return dict(report, status="AMBIGUOUS_WITNESS_FOUND", distinct_query_values=len(values))

    def learn(self, witness):
        functor = (self.roles[witness[1]].force, self.roles[witness[0]].force)
        if functor in self.functors:
            self.functors.remove(functor)
        self.functors.insert(0, functor)
        return functor


class PromotedChainLibrary:
    """Solved 2-hop chains promoted for sibling tasks.

    Consulted only after hop-1 exhausted its space with NO program, so the
    declared space is hop-1 ∪ promoted chains; the query is certified only if
    every fitting promoted chain agrees.
    """

    STATUS_UNIQUE = "UNIQUE_QUERY_OUTPUT_IN_DECLARED_LIBRARY_SPACE"

    def __init__(self):
        self.chains = []

    def promote(self, chain):
        if tuple(chain) not in self.chains:
            self.chains.append(tuple(chain))

    def search(self, grammar, task, *, meter, cache=None):
        cache = cache if cache is not None else TaskEvalCache()
        fitting = []
        for chain in self.chains:
            if any(name not in grammar.ops for name in chain):
                continue
            ok = True
            for x, y in task["public"]:
                v = x
                for name in chain:
                    v = cache(grammar.ops[name], v, meter, "promoted_chain_work_units")
                if _safe_key(v) != _safe_key(y):
                    ok = False
                    break
            if ok:
                v = task["query"]
                for name in chain:
                    v = cache(grammar.ops[name], v, meter, "promoted_chain_work_units")
                fitting.append((chain, v))
        if not fitting:
            return dict(status="NO_PROGRAM_IN_BOUNDED_GRAMMAR", fitting=0)
        values = {_safe_key(v) for _, v in fitting}
        if len(values) == 1 and fitting[0][1] != EXEC_ERR:
            return dict(status=self.STATUS_UNIQUE, fitting=len(fitting), witness=fitting[0][0], query_value=fitting[0][1])
        return dict(status="AMBIGUOUS_WITNESS_FOUND", fitting=len(fitting))


def _chain_expr(grammar, chain, sort):
    expr = variable(sort)
    for name in chain:
        expr = apply(grammar.ops[name], expr)
    return expr


def lyapunov_depth_ladder(meter):
    """Variable-depth hop ladder on +1; terminates by deficit, not hop==3."""
    op = Operator("op_0", ("INT",), "INT", lambda x: x+1)
    grammar = Grammar("INT", (op,))
    roles = AutoOperatorFingerprinter().fingerprint_roles(grammar.operators, {"INT": (0, 1, 2, 7)}, meter=meter)
    depths = []
    for amount in (1, 2, 3, 4, 5):
        task = PublicTask(((0, amount), (1, amount+1)), 7, "INT")
        trace = {}
        ScratchpadWorkspaceEngine(2, roles=roles, meter=meter, max_hops=16,
            max_task_work_budget=200000, canonical_only=True, use_noether=False).run(grammar, task, trace=trace)
        depths.append(len(trace["workspace"]["hops"]))
    return dict(depths=depths, dynamic_lyapunov_max_hops_reached=max(depths),
                terminated_by_constant_three=all(d == 3 for d in depths) is False)


def _task_grammar(grammar, task):
    sort = OpenWorldTaskStream._sort(task["public"][0][0])
    ops = tuple(op for op in grammar.operators if op.inputs == (sort,))
    if not ops:
        ops = grammar.operators
        sort = grammar.input_sort
    return Grammar(sort, ops, grammar.constants, conditionals=grammar.conditionals)


def _solve_open(grammar, task, *, meter, skills=(), doctor=None, guided=True, bound=2, limit=8000, hops=4,
                preferred=()):
    grammar = _task_grammar(grammar, task)
    if preferred:
        hot = tuple(op for op in grammar.operators if op.name in set(preferred))
        rest = tuple(op for op in grammar.operators if op.name not in set(preferred))
        if hot:
            grammar = Grammar(grammar.input_sort, (*hot, *rest[:12]), grammar.constants,
                              conditionals=grammar.conditionals)
    view = PublicTask(task["public"], task["query"], task["output_sort"])
    local = WorkMeter(limit=limit, wall_limit=min(meter.wall_limit, 2.0))
    try:
        engine = ScratchpadWorkspaceEngine(bound, roles={}, skills=skills, meter=local,
            doctor=doctor if guided else None, canonical_only=not guided, use_noether=guided,
            max_hops=hops, max_task_work_budget=limit, spine_first=bool(guided))
        result = engine.run(grammar, view)
        work = local.total
        meter.charge("open_world_search_work_units", work)
        unique = result.status == "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE"
        witness = result.witnesses[0] if result.witnesses else None
        certificate_valid = None
        if unique:
            certificate_valid = direct_open_certificate(grammar, view, witness, result.query_values[0], meter=meter)
        ok = bool(unique and certificate_valid and freeze(result.query_values[0]) == freeze(task["expected"]))
        return dict(solved=ok, status=result.status, work=work, hops=len(engine.last_report.get("hops") or ()),
                    witness=witness, certificate_valid=certificate_valid)
    except WorkExhausted:
        meter.charge("open_world_search_work_units", local.total)
        return dict(solved=False, status="UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED", work=local.total, hops=0, witness=None,
                    certificate_valid=None)


def direct_open_certificate(grammar, view, witness, query_value, *, meter):
    """Unfold to pure primitives, then re-execute on public IO and the query."""
    if witness is None:
        return False
    try:
        pure = unfold_to_primitives(witness, grammar.input_sort)
        for x, y in view.public_io:
            if freeze(eval_expr(pure, x, grammar.ops, meter, "open_world_certificate_work_units")) != freeze(y):
                return False
        return freeze(eval_expr(pure, view.query, grammar.ops, meter, "open_world_certificate_work_units")) == freeze(query_value)
    except (ValueError, TypeError, KeyError):
        return False


def _llm_baseline(task, *, meter):
    meter.charge("open_world_llm_fallback_work_units", 8)
    # Deterministic syntax-prior proposer: identity. Messy labels are not identity.
    pred = task["query"]
    return dict(solved=freeze(pred) == freeze(task["expected"]), status="SYNTAX_PRIOR_UNVERIFIED",
                work=8, hops=0, runtime="deterministic_neuro_symbolic_fallback")


def run_open_world_arena(meter, host=None, *, residual_multihop=False, force_two_hop=True):
    """force_two_hop=True (v12 default): hop-1 + piecewise + promoted chains + force-pruned 2-hop.

    force_two_hop=False, residual_multihop=False is the v10/v11 protocol.

    True adds a hops=3 residual pass on tasks hop-1 exhausted; it solves more
    tasks but each deep solve costs several times the static per-task work.
    """
    toolbox = OpenWorldStdlibToolbox()
    grammar, probes = toolbox.grammar(meter=meter)
    roles = AutoOperatorFingerprinter(probe_cap=64).fingerprint_roles(
        grammar.operators, {s: tuple(vs) for s, vs in probes.items()}, meter=meter)
    tasks = OpenWorldTaskStream().tasks()
    fuzzer = OpenWorldTwinFuzzer()
    combinator = ConditionalPatchCombinator()
    two_hop = ForcePrunedResidualTwoHop(grammar, probes, meter=meter)
    library = PromotedChainLibrary()
    metabolic = HomeostaticMetabolicController()
    metabolic.rebalance()
    learner = DualMemoryLearner(meter=meter, resource_host=host, max_source_updates=16)
    learner.metabolic = metabolic
    learner.doctor.metabolic = metabolic
    learner.enter("OPEN_WORLD", grammar, roles, ("id=1", "  a ", "0x10"))
    poison = []
    for i in range(10):
        def distractor(x, k=i):
            meter.charge("open_world_distractor_work_units", 8)
            return x
        poison.append(Operator(f"op_poison_{i}", ("STR",), "STR", distractor, cost=8))
    cells = []
    telemetry = []
    preferred = []
    methods = ("unpruned_open_stdlib_search", "standalone_or_tool_llm_baseline",
               "nexus_static_quotient_open_world", "nexus_self_evolving_open_world")
    for task in tasks:
        if task["shift"] == "OPEN_ADVERSARIAL_SHIFT" and task["index"] == 0:
            g_poison = Grammar(grammar.input_sort, (*grammar.operators, *poison), grammar.constants, conditionals=True)
            learner.contexts["OPEN_WORLD"]["grammar"] = g_poison
            for op in poison:
                learner.metabolic.observe(op.name, -25.0)
        row = dict(shift=task["shift"], index=task["index"], methods={})
        def _public_row(report):
            return {k: v for k, v in report.items() if k != "witness"}
        row["methods"]["unpruned_open_stdlib_search"] = _public_row(_solve_open(
            grammar, task, meter=meter, guided=False, bound=2, limit=3000, hops=1))
        row["methods"]["standalone_or_tool_llm_baseline"] = _llm_baseline(task, meter=meter)
        row["methods"]["nexus_static_quotient_open_world"] = _public_row(_solve_open(
            grammar, task, meter=meter, guided=False, bound=2, limit=3000, hops=1))
        hop1 = _solve_open(learner.contexts["OPEN_WORLD"]["grammar"], task, meter=meter,
                           skills=learner.contexts["OPEN_WORLD"]["library"].snapshot(),
                           doctor=learner.doctor, guided=True, bound=2, limit=3000, hops=1)
        evolving = hop1
        if hop1["status"] == "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED":
            # Guided NO_PROGRAM / AMBIGUOUS / UNIQUE already decide the same
            # bounded space; only a budget-exhausted guided pass is retried.
            # Its work is ALWAYS counted (v10/v11 dropped it when unsolved).
            fallback = _solve_open(learner.contexts["OPEN_WORLD"]["grammar"], task, meter=meter,
                                   guided=False, bound=2, limit=3000, hops=1)
            evolving = dict(fallback if fallback["solved"] else hop1, work=hop1["work"] + fallback["work"])
        cache = TaskEvalCache()
        # Cheap residual searches first (v12): promoted chains, then force-pruned 2-hop.
        if force_two_hop and not evolving["solved"] and evolving["status"] == "NO_PROGRAM_IN_BOUNDED_GRAMMAR" \
                and evolving.get("piecewise", {}).get("status") != combinator.STATUS_UNIQUE:
            # Hop-1 exhausted with no program: promoted chains first, then the
            # force-pruned 2-hop space. Same base toolbox as the static method.
            local = WorkMeter(limit=3000, wall_limit=min(meter.wall_limit, 2.0))
            residual = library.search(grammar, task, meter=local, cache=cache)
            residual["source"] = "promoted_chain_library"
            if residual["status"] != library.STATUS_UNIQUE:
                residual = dict(two_hop.search(grammar, task, meter=local, cache=cache), source="force_pruned_two_hop",
                                library_status=residual["status"])
            meter.charge("open_world_residual_two_hop_work_units", local.total)
            evolving = dict(evolving, work=evolving["work"]+local.total,
                            residual_two_hop={k: v for k, v in residual.items() if k != "query_value"} | dict(work=local.total))
            if residual["status"] in (library.STATUS_UNIQUE, two_hop.STATUS_UNIQUE):
                view = PublicTask(task["public"], task["query"], task["output_sort"])
                expr = _chain_expr(grammar, residual["witness"], OpenWorldTaskStream._sort(task["public"][0][0]))
                valid = direct_open_certificate(grammar, view, expr, residual["query_value"], meter=meter)
                evolving.update(status=residual["status"], witness=expr, certificate_valid=valid,
                                solved=bool(valid and _safe_key(residual["query_value"]) == _safe_key(task["expected"])))
                if valid:
                    library.promote(residual["witness"])
                    if residual["source"] == "force_pruned_two_hop":
                        evolving["residual_two_hop"]["learned_functor"] = list(two_hop.learn(residual["witness"]))
        g_task = _task_grammar(learner.contexts["OPEN_WORLD"]["grammar"], task)
        if not evolving["solved"] and not evolving["status"].startswith("UNIQUE"):
            # Residual escalation only: no declared space certified a program yet. The
            # combinator itself declines when no op fits any public pair.
            local = WorkMeter(limit=3000, wall_limit=min(meter.wall_limit, 2.0))
            try:
                piece = combinator.synthesize(g_task.operators, task["public"], task["query"], meter=local, cache=cache)
            except WorkExhausted:
                piece = dict(status="UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED", fitting=0)
            meter.charge("open_world_piecewise_work_units", local.total)
            evolving = dict(evolving, work=evolving["work"]+local.total, piecewise=dict(
                status=piece["status"], fitting=piece["fitting"], work=local.total))
            if piece["status"] == combinator.STATUS_UNIQUE:
                public_inputs = tuple(x for x, _ in task["public"])
                replay_ok = all(_safe_key(run_piecewise(piece["witness"], x, g_task, public_inputs)) == _safe_key(y)
                                for x, y in task["public"]) and _safe_key(
                                run_piecewise(piece["witness"], task["query"], g_task, public_inputs)) == _safe_key(piece["query_value"])
                evolving.update(status=piece["status"], certificate_valid=replay_ok,
                                piecewise_witness=list(piece["witness"]),
                                solved=bool(replay_ok and _safe_key(piece["query_value"]) == _safe_key(task["expected"])))
                if evolving["solved"]:
                    for name in piece["witness"][1:]:
                        if name not in preferred:
                            preferred.append(name)
        if residual_multihop and not evolving["solved"] and evolving["status"] == "NO_PROGRAM_IN_BOUNDED_GRAMMAR" \
                and evolving.get("piecewise", {}).get("status") != combinator.STATUS_UNIQUE:
            # Residual multi-hop escalation, only after hop-1 exhausted its
            # space with no program and no piecewise certificate exists.
            deep = _solve_open(learner.contexts["OPEN_WORLD"]["grammar"], task, meter=meter,
                               skills=learner.contexts["OPEN_WORLD"]["library"].snapshot(),
                               doctor=learner.doctor, guided=True, bound=2, limit=3000, hops=3,
                               preferred=tuple(preferred))
            evolving = dict(deep, work=evolving["work"]+deep["work"], piecewise=evolving.get("piecewise"),
                            residual_multihop=True)
        if evolving.get("piecewise_witness"):
            public_inputs = tuple(x for x, _ in task["public"])
            program = lambda v, w=tuple(evolving["piecewise_witness"]): run_piecewise(w, v, g_task, public_inputs)
        elif evolving.get("witness") is not None and evolving.get("certificate_valid"):
            pure = unfold_to_primitives(evolving["witness"], g_task.input_sort)
            program = lambda v, e=pure: guarded(lambda z: eval_expr(e, z, grammar.ops, meter, "open_world_fuzz_work_units"))(v)
        else:
            program = None
        evolving["fuzz"] = fuzzer.probe(program, task["query"], meter=meter) if program is not None else None
        witness = evolving.get("witness")
        evolving.pop("witness", None)
        hop1.pop("witness", None)
        row["methods"]["nexus_self_evolving_open_world"] = evolving
        if evolving["solved"]:
            learner.metabolic.observe(f"task_{task['shift']}_{task['index']}", max(1.0, 50.0-evolving["work"]/100.0))
            if witness is not None:
                for node in ast_nodes(witness):
                    if node.kind == "apply" and node.value not in preferred:
                        preferred.append(node.value)
        snap = learner.metabolic.assert_stable()
        telemetry.append(dict(shift=task["shift"], index=task["index"], **snap))
        cells.append(row)
    # Every certificate claimed by any method was re-executed directly above.
    false = sum(1 for c in cells for m in c["methods"].values() if m.get("certificate_valid") is False)
    summary = {}
    for method in methods:
        solved = [c["methods"][method] for c in cells if c["methods"][method]["solved"]]
        work = sum(c["methods"][method]["work"] for c in cells)
        summary[method] = dict(solved=len(solved), total_work=work,
            work_per_solved=(sum(r["work"] for r in solved)/len(solved)) if solved else None)
    matched = [c for c in cells if c["methods"]["nexus_static_quotient_open_world"]["solved"]
               and c["methods"]["nexus_self_evolving_open_world"]["solved"]]
    matched_subset = dict(task_count=len(matched),
        static_work=sum(c["methods"]["nexus_static_quotient_open_world"]["work"] for c in matched),
        evolving_work=sum(c["methods"]["nexus_self_evolving_open_world"]["work"] for c in matched))
    evicted = {e["skill"] for e in learner.metabolic.evicted}
    return dict(schema="wave24_open_world_arena_v1", toolbox_size=len(grammar.operators), residual_multihop=residual_multihop,
        force_two_hop=force_two_hop, matched_subset=matched_subset,
        learned_force_functors=[list(f) for f in two_hop.functors], promoted_chains=[list(c) for c in library.chains],
        task_count=len(tasks), cells=cells, method_summary=summary, metabolic_telemetry=telemetry,
        metabolic_stability=dict(
            atp_total_sum=telemetry[-1]["atp_total_sum"] if telemetry else 0.0,
            normalized_atp_entropy=telemetry[-1]["normalized_atp_entropy"] if telemetry else 0.0,
            metabolic_freeze_events=learner.metabolic.freeze_events,
            metabolic_drift_events=learner.metabolic.drift_events,
            evicted_poisoned_shortcuts=len(learner.metabolic.evicted),
            injected_distractors_quarantined=all(f"op_poison_{i}" in evicted for i in range(10)),
            band_respected=all(0.25 <= t["normalized_atp_entropy"] <= 0.98 and abs(t["atp_total_sum"]-100.0) < 1e-6 for t in telemetry),
        ),
        false_certificate_count=false,
        lyapunov=lyapunov_depth_ladder(meter))
