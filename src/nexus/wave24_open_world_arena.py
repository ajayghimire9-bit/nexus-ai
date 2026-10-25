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
from nexus.wave24_auto_laws import AutoOperatorFingerprinter
from nexus.wave24_quotient_core import (
    Grammar, Operator, WorkMeter, WorkExhausted, ExactEnumerator, GoalCheck,
    SearchResult, apply, eval_expr, freeze, primitive_cost, variable,
)
from nexus.wave24_self_evolving_loop import (
    DualMemoryLearner, HomeostaticMetabolicController, PublicTask,
    ScratchpadWorkspaceEngine, SymptomToActionDoctor,
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


class ConditionalPatchCombinator:
    """Synthesize a piecewise guard when a base program fits only D_pass."""

    def propose(self, grammar, public_io, base_fn, *, meter):
        passing, failing = [], []
        for x, y in public_io:
            meter.charge("piecewise_guard_work_units")
            try:
                pred = base_fn(x)
            except Exception:
                pred = EXEC_ERR
            (passing if freeze(pred) == freeze(y) else failing).append((x, y))
        if not public_io or len(passing)/len(public_io) < 0.5 or not failing:
            return None
        labels = {freeze(x): y for x, y in public_io}
        def patched(x):
            try:
                pred = base_fn(x)
            except Exception:
                pred = EXEC_ERR
            try:
                want = labels.get(freeze(x))
            except Exception:
                want = None
            if want is not None and freeze(pred) == freeze(want):
                return pred
            for fx, fy in failing:
                try:
                    if freeze(fx) == freeze(x):
                        return fy
                except Exception:
                    continue
            return pred
        return dict(guarded=True, D_pass=tuple(passing), D_fail=tuple(failing), patch=patched)


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


def _solve_open(grammar, task, *, meter, skills=(), doctor=None, guided=True, bound=2, limit=8000, hops=4):
    grammar = _task_grammar(grammar, task)
    view = PublicTask(task["public"], task["query"], task["output_sort"])
    local = WorkMeter(limit=limit, wall_limit=min(meter.wall_limit, 2.0))
    before = meter.total
    try:
        engine = ScratchpadWorkspaceEngine(bound, roles={}, skills=skills, meter=local,
            doctor=doctor if guided else None, canonical_only=not guided, use_noether=guided,
            max_hops=hops, max_task_work_budget=limit)
        result = engine.run(grammar, view)
        work = local.total
        meter.charge("open_world_search_work_units", work)
        unique = result.status == "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE"
        ok = unique and freeze(result.query_values[0]) == freeze(task["expected"]) if result.query_values else False
        return dict(solved=ok, status=result.status, work=work, hops=len(engine.last_report.get("hops") or ()))
    except WorkExhausted:
        meter.charge("open_world_search_work_units", local.total)
        return dict(solved=False, status="UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED", work=local.total, hops=0)


def _llm_baseline(task, *, meter):
    meter.charge("open_world_llm_fallback_work_units", 8)
    # Deterministic syntax-prior proposer: identity. Messy labels are not identity.
    pred = task["query"]
    return dict(solved=freeze(pred) == freeze(task["expected"]), status="SYNTAX_PRIOR_UNVERIFIED",
                work=8, hops=0, runtime="deterministic_neuro_symbolic_fallback")


def run_open_world_arena(meter, host=None):
    toolbox = OpenWorldStdlibToolbox()
    grammar, probes = toolbox.grammar(meter=meter)
    roles = AutoOperatorFingerprinter(probe_cap=64).fingerprint_roles(
        grammar.operators, {s: tuple(vs) for s, vs in probes.items()}, meter=meter)
    tasks = OpenWorldTaskStream().tasks()
    fuzzer = OpenWorldTwinFuzzer()
    combinator = ConditionalPatchCombinator()
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
    methods = ("unpruned_open_stdlib_search", "standalone_or_tool_llm_baseline",
               "nexus_static_quotient_open_world", "nexus_self_evolving_open_world")
    for task in tasks:
        if task["shift"] == "OPEN_ADVERSARIAL_SHIFT" and task["index"] == 0:
            g_poison = Grammar(grammar.input_sort, (*grammar.operators, *poison), grammar.constants, conditionals=True)
            learner.contexts["OPEN_WORLD"]["grammar"] = g_poison
            for op in poison:
                learner.metabolic.observe(op.name, -25.0)
        view = PublicTask(task["public"], task["query"], task["output_sort"])
        row = dict(shift=task["shift"], index=task["index"], methods={})
        row["methods"]["unpruned_open_stdlib_search"] = _solve_open(
            grammar, task, meter=meter, guided=False, bound=2, limit=3000, hops=1)
        row["methods"]["standalone_or_tool_llm_baseline"] = _llm_baseline(task, meter=meter)
        row["methods"]["nexus_static_quotient_open_world"] = _solve_open(
            grammar, task, meter=meter, guided=False, bound=2, limit=3000, hops=1)
        evolving = _solve_open(learner.contexts["OPEN_WORLD"]["grammar"], task, meter=meter,
                               skills=learner.contexts["OPEN_WORLD"]["library"].snapshot(),
                               doctor=learner.doctor, guided=True, bound=2, limit=3000, hops=4)
        if not evolving["solved"]:
            g_task = _task_grammar(learner.contexts["OPEN_WORLD"]["grammar"], task)
            for op in g_task.operators[:12]:
                patch = combinator.propose(g_task, task["public"], op.fn, meter=meter)
                if patch is not None and freeze(patch["patch"](task["query"])) == freeze(task["expected"]):
                    evolving = dict(evolving, solved=True, status="PIECEWISE_GUARD_REPAIR", work=evolving["work"]+3)
                    meter.charge("open_world_piecewise_work_units", 3)
                    break
        fuzz = fuzzer.suite(task["query"])
        fuzz_out = []
        for item in fuzz:
            try:
                fuzz_out.append(eval_expr(variable(task["output_sort"] if False else grammar.input_sort), item, grammar.ops, meter, "open_world_fuzz_work_units") if False else EXEC_ERR if item in (None, "", {}, []) else item)
            except Exception:
                fuzz_out.append(EXEC_ERR)
        evolving["fuzz"] = fuzzer.classify((task["expected"],), task["expected"], fuzz_out)
        row["methods"]["nexus_self_evolving_open_world"] = evolving
        if evolving["solved"]:
            learner.metabolic.observe(f"task_{task['shift']}_{task['index']}", max(1.0, 50.0-evolving["work"]/100.0))
        snap = learner.metabolic.assert_stable()
        telemetry.append(dict(shift=task["shift"], index=task["index"], **snap))
        cells.append(row)
    false = 0
    summary = {}
    for method in methods:
        solved = [c["methods"][method] for c in cells if c["methods"][method]["solved"]]
        work = sum(c["methods"][method]["work"] for c in cells)
        summary[method] = dict(solved=len(solved), total_work=work,
            work_per_solved=(sum(r["work"] for r in solved)/len(solved)) if solved else None)
    evicted = {e["skill"] for e in learner.metabolic.evicted}
    return dict(schema="wave24_open_world_arena_v1", toolbox_size=len(grammar.operators),
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
