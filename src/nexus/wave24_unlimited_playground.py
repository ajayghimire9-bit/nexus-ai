"""Persistent stdlib playground; finite source play, not an unbounded AGI loop."""
from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path
import time

from nexus.evolution1.catalogue import digest
from nexus.wave24_auto_laws import (AutoOperatorFingerprinter, JOB_TAGS, universal_job_tags,
                                   AtomicFieldProjector, AtomicForceClassifier)
from nexus.wave24_open_world_arena import ConditionalPatchCombinator, OpenWorldTwinFuzzer, guarded, EXEC_ERR
from nexus.wave24_quotient_core import (
    Grammar, Operator, WorkMeter, apply, eval_expr, freeze, primitive_cost, variable,
    NoetherConservationGate, unfold_workspace_expr,
)
from nexus.wave24_self_evolving_loop import (
    HomeostaticMetabolicController, PublicTask, ScratchpadWorkspaceEngine,
    SymptomToActionDoctor, ast_nodes,
)


SAFE_MODULES = (
    "math", "statistics", "itertools", "collections", "re", "json", "string",
    "operator", "difflib", "fractions", "datetime",
)
PROBES = (-2, -1, 0, 1, 2, 3, 7)
from nexus.wave24_auto_laws import ATOMIC_FORCES  # five universal atomic forces
NOETHER_LAWS = ("MASS_PRESERVING", "MASS_CONTRACTIVE", "MULTISET_PRESERVING_PERMUTATION")


def render_teacher_python(name, teacher, qualnames):
    """Compile a real apply-tree into a standalone skill_* function."""
    imports = set()

    def call(qual, arg):
        if qual.startswith("skill_"):
            return f"{qual}({arg})"
        if "_" in qual:
            module, func = qual.split("_", 1)
            if module in SAFE_MODULES:
                imports.add(f"import {module}")
                return f"_apply({module}.{func}, {arg})"
        if qual in {"abs"} or qual.endswith("_abs") or qual.endswith("_fabs"):
            return f"abs({arg})"
        if "neg" in qual:
            return f"(-{arg})"
        raise ValueError("playground compiler cannot emit " + qual)

    def render(expr):
        if expr.kind == "var":
            return "x"
        if expr.kind != "apply":
            raise ValueError("playground compiler accepts only apply/var trees")
        return call(qualnames.get(expr.value, expr.value), render(expr.children[0]))

    body = render(teacher)
    header = "\n".join(sorted(imports))
    source = (
        (header + "\n\n" if header else "")
        + "def _apply(fn, value):\n"
        + "    try:\n"
        + "        out = fn(value)\n"
        + "    except Exception:\n"
        + "        return value\n"
        + "    if type(out) is bool:\n"
        + "        return int(out)\n"
        + "    if type(out) is float and out == int(out) and abs(out) < 10 ** 6:\n"
        + "        return int(out)\n"
        + "    if type(out) is int and abs(out) < 10 ** 6:\n"
        + "        return out\n"
        + "    return value\n\n"
        + f"def {name}(x):\n"
        + "    if not isinstance(x, int):\n"
        + "        return x\n"
        + f"    return {body}\n"
    )
    ast.parse(source)
    return source



MESSY_EXCEPTIONS = ("ValueError", "KeyError", "ZeroDivisionError", "TypeError", "OverflowError")
INT_GUARDS = {
    "is_negative": lambda x: x < 0,
    "is_zero": lambda x: x == 0,
}
_GUARD_AST = {
    "is_negative": lambda arg: ast.Compare(arg, [ast.Lt()], [ast.Constant(0)]),
    "is_zero": lambda arg: ast.Compare(arg, [ast.Eq()], [ast.Constant(0)]),
}


def plan_steps(plan):
    """All step names referenced by a plan, in order."""
    if plan["kind"] == "chain":
        return list(plan["steps"])
    if plan["kind"] == "if":
        return plan_steps(plan["then"]) + plan_steps(plan["else"])
    if plan["kind"] == "try":
        return plan_steps(plan["body"]) + plan_steps(plan["fallback"])
    if plan["kind"] == "seq":
        return [step for part in plan["parts"] for step in plan_steps(part)]
    raise ValueError("unknown skill plan kind")


def plan_kinds(plan):
    kinds = {plan["kind"]}
    for key in ("then", "else", "body", "fallback"):
        if key in plan:
            kinds |= plan_kinds(plan[key])
    return kinds


def unfold_plan_to_primitives(plan, lineage):
    """Recursively replace every skill_* step by its stored plan (pure stdlib steps only)."""
    if plan["kind"] == "chain":
        parts = []
        for step in plan["steps"]:
            if step.startswith("skill_"):
                if step not in lineage:
                    raise ValueError("skill lineage missing for " + step)
                parts.append(unfold_plan_to_primitives(lineage[step]["plan"], lineage))
            else:
                parts.append(dict(kind="chain", steps=[step]))
        if all(p["kind"] == "chain" for p in parts):
            return dict(kind="chain", steps=[s for p in parts for s in p["steps"]])
        return dict(kind="seq", parts=parts)
    if plan["kind"] == "if":
        return dict(kind="if", guard=plan["guard"], then=unfold_plan_to_primitives(plan["then"], lineage),
                    **{"else": unfold_plan_to_primitives(plan["else"], lineage)})
    if plan["kind"] == "try":
        return dict(kind="try", body=unfold_plan_to_primitives(plan["body"], lineage),
                    fallback=unfold_plan_to_primitives(plan["fallback"], lineage))
    if plan["kind"] == "seq":
        return dict(kind="seq", parts=[unfold_plan_to_primitives(p, lineage) for p in plan["parts"]])
    raise ValueError("unknown skill plan kind")


def plan_primitive_cost(pure):
    if pure["kind"] == "chain":
        return len(pure["steps"])
    if pure["kind"] == "seq":
        return sum(plan_primitive_cost(p) for p in pure["parts"])
    if pure["kind"] == "if":
        return 1 + plan_primitive_cost(pure["then"]) + plan_primitive_cost(pure["else"])
    return 1 + plan_primitive_cost(pure["body"]) + plan_primitive_cost(pure["fallback"])


def eval_plan(pure, x, primitives):
    """Reference semantics of a pure primitive plan (the witness the verifier trusts)."""
    if not isinstance(x, int) or isinstance(x, bool):
        return x
    if pure["kind"] == "chain":
        for step in pure["steps"]:
            x = primitives[step](x)
        return x
    if pure["kind"] == "seq":
        for part in pure["parts"]:
            x = eval_plan(part, x, primitives)
        return x
    if pure["kind"] == "if":
        return eval_plan(pure["then"] if INT_GUARDS[pure["guard"]](x) else pure["else"], x, primitives)
    try:
        return eval_plan(pure["body"], x, primitives)
    except (ValueError, KeyError, ZeroDivisionError, TypeError, OverflowError):
        return eval_plan(pure["fallback"], x, primitives)


def _step_call(step, arg, imports):
    if step.startswith("skill_"):
        return ast.Call(ast.Name(step, ast.Load()), [arg], [])
    module, func = step.split("_", 1)
    if module not in SAFE_MODULES:
        raise ValueError("playground compiler cannot emit " + step)
    imports.add(module)
    target = ast.Attribute(ast.Name(module, ast.Load()), func, ast.Load())
    return ast.Call(ast.Name("_apply", ast.Load()), [target, arg], [])


def _plan_body(plan, imports, counter):
    """Statements computing the plan on x into local stepping-stone variables, ending in return."""
    if plan["kind"] == "chain":
        stmts, current = [], ast.Name("x", ast.Load())
        for step in plan["steps"]:
            counter[0] += 1
            name = f"v_{counter[0]}"
            stmts.append(ast.Assign([ast.Name(name, ast.Store())], _step_call(step, current, imports)))
            current = ast.Name(name, ast.Load())
        return stmts + [ast.Return(current)]
    if plan["kind"] == "if":
        if plan["guard"] not in _GUARD_AST:
            raise ValueError("unknown guard")
        return [ast.If(_GUARD_AST[plan["guard"]](ast.Name("x", ast.Load())),
                       _plan_body(plan["then"], imports, counter), _plan_body(plan["else"], imports, counter))]
    if plan["kind"] == "try":
        exc = ast.Tuple([ast.Name(e, ast.Load()) for e in MESSY_EXCEPTIONS], ast.Load())
        return [ast.Try(_plan_body(plan["body"], imports, counter),
                        [ast.ExceptHandler(exc, None, _plan_body(plan["fallback"], imports, counter))], [], [])]
    raise ValueError("compiler accepts chain / if / try plans")


# Partial-domain primitives RAISE (no silent identity fallback), so compiled
# try/except and if/else guards genuinely fire on fault inputs.
_APPLY_SOURCE = (
    "def _apply(fn, value):\n"
    "    out = fn(value)\n"
    "    if type(out) is bool:\n"
    "        return int(out)\n"
    "    if type(out) is float and out == out and abs(out) < 10 ** 6 and out == int(out):\n"
    "        return int(out)\n"
    "    if type(out) is int and abs(out) < 10 ** 6:\n"
    "        return out\n"
    "    raise ValueError('non-integer result outside the int domain')\n"
)


def outcome(fn, x):
    """('ok', frozen value) or ('raise', exception class) -- compared exactly."""
    try:
        return ("ok", freeze(fn(x)))
    except (ValueError, KeyError, ZeroDivisionError, TypeError, OverflowError) as exc:
        return ("raise", type(exc).__name__ if not isinstance(exc, ValueError) else "ValueError")


def compile_verified_skill_ast(name, plan, *, lineage, primitives, checks, callables=None):
    """White-box AST compilation of a multi-statement / conditional / exception-safe skill.

    Returns (source, fn, record). Raises ValueError unless the compiled bytecode
    agrees with the plan's fully unfolded primitive expansion on every check input.
    """
    if not name.isidentifier() or not name.startswith("skill_"):
        raise ValueError("evolved helper must be skill_*")
    imports, counter = set(), [0]
    body = [ast.If(ast.UnaryOp(ast.Not(), ast.Call(ast.Name("isinstance", ast.Load()),
                   [ast.Name("x", ast.Load()), ast.Name("int", ast.Load())], [])), [ast.Return(ast.Name("x", ast.Load()))], [])]
    body += _plan_body(plan, imports, counter)
    fn_def = ast.FunctionDef(name=name, args=ast.arguments(posonlyargs=[], args=[ast.arg("x")], kwonlyargs=[],
                             kw_defaults=[], defaults=[]), body=body, decorator_list=[], returns=None,
                             **({"type_params": []} if sys.version_info >= (3, 12) else {}))
    module = ast.Module([ast.Import([ast.alias(m)]) for m in sorted(imports)] + [fn_def], [])
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n\n" + _APPLY_SOURCE
    tree = ast.parse(source)
    if any(not isinstance(n, (ast.FunctionDef, ast.Import)) for n in tree.body):
        raise ValueError("compiled skill must be pure function definitions")
    namespace = {"__builtins__": {"isinstance": isinstance, "int": int, "abs": abs, "type": type, "bool": bool,
                                  "float": float, "Exception": Exception, "ValueError": ValueError,
                                  "KeyError": KeyError, "ZeroDivisionError": ZeroDivisionError,
                                  "TypeError": TypeError, "OverflowError": OverflowError,
                                  "__import__": __import__}}
    namespace.update(callables or {})
    exec(compile(tree, f"<evolved:{name}>", "exec"), namespace)
    fn = namespace[name]
    pure = unfold_plan_to_primitives(plan, lineage)
    for x in checks:
        if outcome(fn, x) != outcome(lambda v: eval_plan(pure, v, primitives), x):
            raise ValueError("compiled skill disagrees with its unfolded primitive expansion")
    except_fired = tuple(x for x in checks if plan["kind"] == "try"
                         and outcome(lambda v: eval_plan(unfold_plan_to_primitives(plan["body"], lineage), v, primitives), x)[0] == "raise"
                         and outcome(fn, x)[0] == "ok")
    callees = sorted({s for s in plan_steps(plan) if s.startswith("skill_")})
    layer = 1 + max((lineage[c]["layer"] for c in callees), default=0)
    statements = sum(1 for n in ast.walk(fn_def) if isinstance(n, (ast.Assign, ast.Return, ast.If, ast.Try)))
    record = dict(layer=layer, plan=plan, pure_plan=pure, callees=callees,
                  primitive_cost=plan_primitive_cost(pure), statements=statements,
                  constructs=sorted(plan_kinds(plan)),
                  source_sha256=digest(source), except_fired_on=list(except_fired))
    return source, fn, record


class PersistentNexusBrain:
    """Disk-backed toolbox, universal meta-recipes, doctor weights and ATP ledger."""

    def __init__(self, brain_dir, *, meter=None):
        self.root = Path(brain_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.meter = meter if meter is not None else WorkMeter(limit=1_000_000, wall_limit=2.)
        self.metabolic = HomeostaticMetabolicController()
        self.doctor = SymptomToActionDoctor()
        self.recipes = []
        self.toolbox_names = []
        self.lineage = {}
        self.load()

    @property
    def toolbox_path(self):
        return self.root / "evolved_toolbox.py"

    def _recipe_path(self):
        modern = self.root / "universal_meta_recipes.json"
        legacy = self.root / "job_tag_recipes.json"
        return modern if modern.exists() or not legacy.exists() else legacy

    def _doctor_path(self):
        modern = self.root / "symptom_doctor_state.json"
        legacy = self.root / "doctor_state.json"
        return modern if modern.exists() or not legacy.exists() else legacy

    def _archive_incompatible_semantics(self):
        """A toolbox compiled under an older _apply would silently rebind new skills to it."""
        if not self.toolbox_path.exists():
            return None
        text = self.toolbox_path.read_text()
        if "def _apply(" not in text or _APPLY_SOURCE in text:
            return None
        legacy = self.root / ("legacy_" + digest(text)[:8])
        legacy.mkdir(exist_ok=True)
        for name in ("evolved_toolbox.py", "skill_lineage.json", "universal_meta_recipes.json",
                     "symptom_doctor_state.json", "job_tag_recipes.json", "doctor_state.json"):
            if (self.root / name).exists():
                (self.root / name).replace(legacy / name)
        return legacy

    def load(self):
        self.archived_legacy = self._archive_incompatible_semantics()
        recipes = self._recipe_path()
        doctor = self._doctor_path()
        if recipes.exists():
            body = json.loads(recipes.read_text())
            self.recipes = body.get("recipes", body) if isinstance(body, dict) else body
        if doctor.exists():
            body = json.loads(doctor.read_text())
            self.metabolic.delta_w = {k: float(v) for k, v in body.get("delta_w", {}).items()}
            self.metabolic.rebalance()
            self.doctor.rows = list(body.get("doctor_rows") or [])
            self.doctor.last_agenda = tuple(body.get("last_agenda") or ())
        if (self.root / "skill_lineage.json").exists():
            self.lineage = json.loads((self.root / "skill_lineage.json").read_text())
        if not self.toolbox_path.exists():
            self.toolbox_path.write_text("# nexus evolved toolbox\n")
        self.toolbox_names = self._safe_toolbox_names()
        self.metabolic.assert_stable()

    def save(self):
        snap = self.metabolic.assert_stable()
        (self.root / "universal_meta_recipes.json").write_text(json.dumps({
            "atomic_forces": list(ATOMIC_FORCES),
            "noether_laws": list(NOETHER_LAWS),
            "recipes": self.recipes,
            "universal_force_functors": sorted({tuple(f) for r in self.recipes
                                                for f in r.get("universal_force_functors", ())}),
        }, indent=2, sort_keys=True))
        (self.root / "symptom_doctor_state.json").write_text(json.dumps({
            "delta_w": self.metabolic.delta_w,
            "metabolic": snap,
            "critic_fingerprint": self.doctor.critic.fingerprint(),
            "rows": len(self.doctor.rows),
            "doctor_rows": self.doctor.rows,
            "last_agenda": list(self.doctor.last_agenda),
            "atp_total_sum": snap["atp_total_sum"],
        }, indent=2, sort_keys=True))
        (self.root / "skill_lineage.json").write_text(json.dumps(self.lineage, indent=2, sort_keys=True))
        if not self.toolbox_path.exists():
            self.toolbox_path.write_text("# nexus evolved toolbox\n")
        return snap

    def _safe_toolbox_names(self):
        if not self.toolbox_path.exists():
            return []
        tree = ast.parse(self.toolbox_path.read_text())
        names = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("skill_"):
                names.append(node.name)
        return names

    def load_toolbox_callables(self):
        names = self._safe_toolbox_names()
        if not names:
            return []
        spec = importlib.util.spec_from_file_location("nexus_evolved_toolbox", self.toolbox_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return [(name, getattr(module, name)) for name in names if callable(getattr(module, name, None))]

    def unfold_to_primitives(self, name):
        """Pure stdlib plan for any stored skill_* (recursively through its callees)."""
        return unfold_plan_to_primitives(self.lineage[name]["plan"], self.lineage)

    def admit_to_nursery(self, name, source, record):
        """Cold nursery: on disk and callable, but no ATP mass until it graduates."""
        if not self.promote_python(name, source, delta_w=None):
            return False
        self.lineage[name] = dict(record, status="nursery", uses=[], delta_w_total=0.0)
        self.save()
        return True

    def record_use(self, name, *, delta_w, task_digest):
        entry = self.lineage[name]
        if any(u["task"] == task_digest for u in entry["uses"]):
            return False
        entry["uses"].append(dict(task=task_digest, delta_w=float(delta_w)))
        entry["delta_w_total"] = sum(u["delta_w"] for u in entry["uses"])
        if entry["status"] == "nursery" and len(entry["uses"]) >= 2 and entry["delta_w_total"] > 0 \
                and all(u["delta_w"] > 0 for u in entry["uses"]):
            entry["status"] = "graduated"
            entry["graduated_after_uses"] = len(entry["uses"])
            self.metabolic.observe(name, entry["delta_w_total"])
        elif entry["status"] == "graduated":
            # Live counterfactual utility keeps flowing; cumulative < 0 evicts.
            self.metabolic.observe(name, float(delta_w))
            if name not in self.metabolic.delta_w:
                entry["status"] = "evicted"
        self.save()
        return True

    def promote_python(self, name, source, *, delta_w):
        if not name.isidentifier() or not name.startswith("skill_"):
            raise ValueError("evolved helper must be skill_*")
        tree = ast.parse(source)
        if any(not isinstance(node, (ast.FunctionDef, ast.Import, ast.ImportFrom)) for node in tree.body):
            raise ValueError("evolved helper must be a pure function definition")
        existing = self.toolbox_path.read_text() if self.toolbox_path.exists() else "# nexus evolved toolbox\n"
        if f"def {name}(" in existing:
            return False
        tree = ast.parse(source)
        keep = []
        have_apply = "def _apply(" in existing
        have_imports = set()
        if self.toolbox_path.exists():
            for node in ast.parse(existing).body:
                if isinstance(node, ast.Import):
                    have_imports.update(alias.name for alias in node.names)
        for node in tree.body:
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names if alias.name not in have_imports]
                if names:
                    keep.append("import " + ", ".join(names))
            elif isinstance(node, ast.FunctionDef) and node.name == "_apply":
                if not have_apply:
                    keep.append(ast.get_source_segment(source, node) or "")
            elif isinstance(node, ast.FunctionDef) and node.name == name:
                keep.append(ast.get_source_segment(source, node) or "")
        chunk = "\n\n".join(part for part in keep if part).strip()
        if not chunk:
            raise ValueError("compiled playground skill emitted no function")
        self.toolbox_path.write_text(existing.rstrip() + "\n\n" + chunk + "\n")
        self.toolbox_names.append(name)
        if delta_w is not None:
            self.metabolic.observe(name, delta_w)
        self.save()
        return True


CHECK_INPUTS = (-7, -3, -2, -1, 0, 1, 2, 3, 5, 7, 11)
PUBLIC_INPUTS = (-2, -1, 0, 1, 3, 7)


def _behavior(fn, inputs=CHECK_INPUTS):
    return tuple(outcome(fn, x) for x in inputs)


def _total_on(fn, inputs):
    return all(outcome(fn, x)[0] == "ok" for x in inputs)


class _Callable:
    """Duck-typed operator for the piecewise combinator (name + fn only)."""

    def __init__(self, name, fn):
        self.name, self.fn = name, fn


class UnlimitedPythonGround:
    """Introspect vetted stdlib modules and the growing evolved toolbox."""

    def crawl(self, brain, *, meter, max_ops=24):
        started = time.perf_counter()
        identity = _behavior(lambda x: x, PROBES)
        per_module, seen, scanned = {}, {identity}, {}
        for module_name in SAFE_MODULES:
            module = importlib.import_module(module_name)
            per_module[module_name] = []
            scanned[module_name] = 0
            for name, fn in inspect.getmembers(module, callable):
                if name.startswith("_") or name in {"eval", "exec", "open"}:
                    continue
                wrapped = self._unary(fn)
                if wrapped is None:
                    continue
                scanned[module_name] += 1
                meter.charge("playground_crawl_work_units", len(PROBES))
                sig = _behavior(wrapped, PROBES)
                if sig in seen or sum(o[0] == "ok" for o in sig) < 2:
                    continue  # identity, a behavioral duplicate, or (almost) nowhere defined
                seen.add(sig)
                per_module[module_name].append((f"{module_name}_{name}", wrapped))
        # Round-robin across modules so one module cannot monopolise the budget.
        callables, queues = [], [list(v) for v in per_module.values()]
        while len(callables) < max_ops and any(queues):
            for queue in queues:
                if queue and len(callables) < max_ops:
                    callables.append(queue.pop(0))
        primitives = dict(callables)
        skills = {}
        for name, fn in brain.load_toolbox_callables():
            if name in brain.lineage:
                skills[name] = fn
                callables.append((name, fn))
        operators, qualnames = [], {}
        for index, (name, fn) in enumerate(callables):
            op_name = f"op_{index}"
            # The search grammar sees faults as the EXEC_ERR token; compiled
            # skills and plan semantics see the raising primitive.
            operators.append(Operator(op_name, ("INT",), "INT", guarded(fn)))
            qualnames[op_name] = name
        grammar = Grammar("INT", tuple(operators))
        finger = AutoOperatorFingerprinter()
        t0 = time.perf_counter()
        roles = finger.fingerprint_roles(grammar.operators, {"INT": PROBES}, meter=meter)
        gate = NoetherConservationGate()
        gate.fingerprint_operators(grammar.operators, PROBES, meter=meter)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        meter.charge("playground_crawl_work_units", len(operators))
        jobs = {op.name: universal_job_tags(roles[op.name]) for op in grammar.operators if op.name in roles}
        forces = {q: AtomicForceClassifier().classify(fn, PROBES).force for q, fn in primitives.items()}
        return dict(grammar=grammar, roles=roles, noether=gate.tags, qualnames=qualnames,
                    job_tags=jobs, crawl_ms=(time.perf_counter() - started) * 1000,
                    fingerprint_ms=elapsed_ms, operator_count=len(operators),
                    primitives=primitives, skills=skills, forces=forces,
                    module_selected={m: sum(1 for q in primitives if q.startswith(m + "_")) for m in per_module},
                    module_scanned=scanned)

    @staticmethod
    def _unary(fn):
        try:
            inspect.signature(fn).bind(0)
        except Exception:
            return None
        def wrapped(value):
            try:
                out = fn(value)
            except Exception as exc:  # any stdlib fault becomes one explicit domain error
                raise ValueError(f"domain fault: {type(exc).__name__}") from None
            if type(out) is bool:
                return int(out)
            if type(out) is float and out == out and abs(out) < 10**6 and out == int(out):
                return int(out)
            if type(out) is int and abs(out) < 10**6:
                return out
            raise ValueError("non-integer result outside the int domain")
        wrapped.__name__ = getattr(fn, "__name__", "wrapped")
        return wrapped


class OpenEndedCuriosityLoop:
    """Explore / compound / phase-boundary probe over a persistent brain.

    Every task is self-proposed from crawled tools (AZR-style), solved from
    public IO only, then graded against the proposer's teacher. Compiled
    skills are verified against their fully unfolded primitive expansion.
    """

    def __init__(self, brain, *, meter=None):
        self.brain = brain
        self.meter = meter if meter is not None else brain.meter
        self.ground = UnlimitedPythonGround()
        self.fuzzer = OpenWorldTwinFuzzer()
        self.patch = ConditionalPatchCombinator()
        self.false_certificates = 0

    # -- helpers -----------------------------------------------------------
    def _all_fns(self, crawled, local):
        return {**crawled["primitives"], **crawled["skills"], **local}

    def _known_behaviors(self, crawled, local):
        return {_behavior(fn) for fn in self._all_fns(crawled, local).values()}

    @staticmethod
    def _proposable(teacher, query):
        """The proposer only poses tasks its own teacher answers on all public inputs and the query."""
        if not _total_on(teacher, (*PUBLIC_INPUTS, query)):
            return False
        return len({freeze(teacher(x)) for x in PUBLIC_INPUTS}) >= 2

    def _task(self, teacher, query):
        public = tuple((x, teacher(x)) for x in PUBLIC_INPUTS)
        return PublicTask(public, query, "INT"), teacher(query)

    def _checks(self, task):
        fuzz = tuple(v for v in self.fuzzer.suite(task.query) if isinstance(v, int) and not isinstance(v, bool))
        return tuple(dict.fromkeys((*CHECK_INPUTS, *(x for x, _ in task.public_io), task.query, *fuzz)))

    def _admit(self, name, plan, task, query_value, crawled, local):
        """Compile, verify against unfolded primitives + certified query, admit to nursery."""
        fns = self._all_fns(crawled, local)
        source, fn, record = compile_verified_skill_ast(name, plan, lineage=self.brain.lineage,
            primitives=crawled["primitives"], checks=self._checks(task),
            callables={k: v for k, v in fns.items() if k.startswith("skill_")})
        if any(freeze(fn(x)) != freeze(y) for x, y in task.public_io) or freeze(fn(task.query)) != freeze(query_value):
            self.false_certificates += 1
            raise ValueError("compiled skill disagrees with its certificate")
        pure_digest = digest(record["pure_plan"])
        if any(v.get("pure_digest") == pure_digest for v in self.brain.lineage.values()):
            return None
        record["pure_digest"] = pure_digest
        record["force_signature"] = self._force_signature(fn)
        if not self.brain.admit_to_nursery(name, source, record):
            return None
        local[name] = fn
        return record

    @staticmethod
    def _force_signature(fn):
        projector = AtomicFieldProjector()
        deltas = []
        for x in PROBES:
            if outcome(fn, x)[0] != "ok":
                continue
            a, b = projector.project(x), projector.project(fn(x))
            deltas.append((b.mass - a.mass, int(b.locus_mask != a.locus_mask),
                           int(b.quantum_multiset_hash != a.quantum_multiset_hash)))
        return dict(delta_mass=sum(d[0] for d in deltas), locus_changes=sum(d[1] for d in deltas),
                    quantum_changes=sum(d[2] for d in deltas), defined_probes=len(deltas),
                    force=AtomicForceClassifier().classify(fn, PROBES).force)

    def _counterfactual_work(self, grammar, task, exclude, crawled, limit=4000):
        """Work for the same task with the reused skills removed from the grammar."""
        ops = tuple(op for op in grammar.operators if crawled["qualnames"][op.name] not in exclude)
        local = WorkMeter(limit=limit, wall_limit=1.)
        try:
            ScratchpadWorkspaceEngine(2, roles={}, meter=local, max_hops=3, max_task_work_budget=limit,
                use_noether=True, spine_first=True).run(Grammar("INT", ops), task)
        except Exception:
            return limit
        return local.total

    def _recipe(self, crawled, plan, epoch, name):
        from nexus.wave24_self_evolving_loop import UniversalForceFunctor
        names = {v: k for k, v in crawled["qualnames"].items()}
        steps = plan_steps(plan)
        def force(step):
            if step in self.brain.lineage:
                return "COMPOSITE_LAYER_" + str(self.brain.lineage[step]["layer"])
            jobs = crawled["job_tags"].get(names.get(step), ())
            return jobs[0] if jobs else "EMPIRICAL"
        pure = unfold_plan_to_primitives(plan, self.brain.lineage)
        pure_steps = plan_steps(pure) if "if" not in plan_kinds(pure) and "try" not in plan_kinds(pure) else []
        functors = UniversalForceFunctor.lift_chain(tuple(pure_steps), crawled["forces"], source_skill=name,
                                                    source_domain="PLAYGROUND_INT")
        self.brain.recipes.append(dict(epoch=epoch, skill=name, kind=plan["kind"],
            outer_job_tag=force(steps[-1]), inner_job_tag=force(steps[0]),
            atomic_force=crawled["forces"].get(steps[-1], self.brain.lineage.get(steps[-1], {}).get(
                "force_signature", {}).get("force", "F_BRANCH")),
            operator=steps[-1],
            universal_force_functors=[[f.outer_force, f.inner_force] for f in functors],
            noether=[str(t) for t in crawled["noether"].get(names.get(steps[-1]), ())]))
        jobs = crawled["job_tags"].get(names.get(steps[-1]), ())
        self.brain.doctor.rows.append(dict(
            features=(1., 0., 0., 0., 0.) + tuple(float(j in jobs) for j in JOB_TAGS),
            J_fit=1, J_disagree=0, purpose="training", label_semantics="source_symptom_job_v1"))

    # -- phase A: explore primitive depth-2 compositions --------------------
    def explore(self, epoch, crawled, local, *, attempts=3):
        """Propose up to `attempts` novel depth-2 tasks; stop at the first certified solve."""
        tried = []
        for attempt in range(attempts):
            out = self._explore_once(epoch, crawled, local, skip=len(tried), tried=tried)
            if not out.get("proposed") or out.get("compiled"):
                break
        out["attempts"] = len(tried)
        out["tried"] = tried
        return out

    def _explore_once(self, epoch, crawled, local, *, skip, tried):
        grammar = crawled["grammar"]
        prims = [(q, f) for q, f in crawled["primitives"].items()]
        known = self._known_behaviors(crawled, local)
        pairs = [(a, b) for a in prims for b in prims if a[0] != b[0]]
        if not pairs:
            return dict(phase="explore", proposed=False)
        found = 0
        for k in range(len(pairs)):
            (qa, fa), (qb, fb) = pairs[(epoch * 7 + k) % len(pairs)]
            teacher = lambda x, fa=fa, fb=fb: fb(fa(x))
            if _behavior(teacher) in known or not self._proposable(teacher, 2):
                continue
            if found == skip:
                break
            found += 1
        else:
            return dict(phase="explore", proposed=False)
        tried.append([qa, qb])
        task, expected = self._task(teacher, 2)
        result = ScratchpadWorkspaceEngine(3, roles=crawled["roles"], meter=self.meter, max_hops=4,
            use_noether=True, spine_first=True).run(grammar, task)
        out = dict(phase="explore", proposed=True, teacher=[qa, qb], status=result.status, solved=False, compiled=None)
        if not (result.status.startswith("UNIQUE") and result.witnesses):
            return out
        out["solved"] = freeze(result.query_values[0]) == freeze(expected)
        pure = unfold_workspace_expr(result.witnesses[0])
        steps = []
        node = pure
        while node.kind == "apply":
            steps.append(crawled["qualnames"][node.value])
            node = node.children[0]
        if node.kind != "var" or not steps or not out["solved"]:
            return out
        plan = dict(kind="chain", steps=list(reversed(steps)))
        name = f"skill_{epoch}_chain_{digest(plan)[:8]}"
        record = self._admit(name, plan, task, result.query_values[0], crawled, local)
        if record is not None:
            out.update(compiled=name, layer=record["layer"])
            self._recipe(crawled, plan, epoch, name)
        return out

    # -- phase B: compound existing skills into a higher layer ---------------
    def compound(self, epoch, crawled, local):
        fns = self._all_fns(crawled, local)
        lib = sorted(n for n in fns if n.startswith("skill_") and n in self.brain.lineage)
        if len(lib) < 2:
            return dict(phase="compound", proposed=False)
        known = self._known_behaviors(crawled, local)
        pairs = [(a, b) for a in lib for b in lib if a != b]
        for k in range(len(pairs)):
            a, b = pairs[(epoch * 5 + k) % len(pairs)]
            teacher = lambda x, fa=fns[a], fb=fns[b]: fb(fa(x))
            if _behavior(teacher) not in known and self._proposable(teacher, 5):
                break
        else:
            return dict(phase="compound", proposed=False)
        task, expected = self._task(teacher, 5)
        before = self.meter.total
        # Library-level search: every skill single and ordered skill pair, plus stdlib singles.
        candidates = [((n,), fns[n]) for n in fns]
        candidates += [((s, t), (lambda x, fs=fns[s], ft=fns[t]: ft(fs(x)))) for s in lib for t in lib if s != t]
        fits = []
        for steps, fn in candidates:
            ok = True
            for x, y in task.public_io:
                self.meter.charge("playground_library_search_work_units")
                if outcome(fn, x) != ("ok", freeze(y)):
                    ok = False
                    break
            if ok:
                self.meter.charge("playground_library_search_work_units")
                got = outcome(fn, task.query)
                fits.append((steps, fn(task.query) if got[0] == "ok" else EXEC_ERR))
        with_work = self.meter.total - before
        out = dict(phase="compound", proposed=True, teacher=[a, b], fitting=len(fits), solved=False, compiled=None)
        values = {freeze(v) for _, v in fits}
        if len(values) != 1 or EXEC_ERR in {v for _, v in fits}:
            out["status"] = "AMBIGUOUS_WITNESS_FOUND" if fits else "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
            return out
        steps, value = min(fits, key=lambda f: len(f[0]))
        out.update(status="UNIQUE_QUERY_OUTPUT_IN_DECLARED_LIBRARY_SPACE", solved=freeze(value) == freeze(expected))
        if not out["solved"] or not all(s.startswith("skill_") for s in steps):
            return out
        without = self._counterfactual_work(crawled["grammar"], task, set(steps), crawled)
        out.update(work_with=with_work, work_without=without)
        plan = dict(kind="chain", steps=list(steps))
        name = f"skill_{epoch}_compound_{digest(plan)[:8]}"
        record = self._admit(name, plan, task, value, crawled, local)
        task_key = digest((task.public_io, task.query))
        for used in steps:
            self.brain.record_use(used, delta_w=without - with_work, task_digest=task_key)
        if record is not None:
            out.update(compiled=name, layer=record["layer"])
            self._recipe(crawled, plan, epoch, name)
        return out

    # -- phase C: rogue phase-boundary probing -> conditional skill ---------
    def phase_boundary(self, epoch, crawled, local):
        fns = self._all_fns(crawled, local)
        lib = sorted((n for n in fns if n.startswith("skill_") and n in self.brain.lineage),
                     key=lambda n: (-self.brain.lineage[n]["layer"], n))
        prims = sorted(crawled["primitives"])
        if not lib or not prims:
            return dict(phase="phase_boundary", proposed=False)
        base = lib[0]
        known = self._known_behaviors(crawled, local)
        # Perturb single atoms (sign flips) of the probe inputs to find a
        # primitive that diverges from the base skill only on one phase.
        for k in range(len(prims)):
            q = prims[(epoch * 3 + k) % len(prims)]
            diverge = [x for x in CHECK_INPUTS if x < 0 and outcome(fns[q], x) != outcome(fns[base], x)]
            teacher = lambda x, fq=fns[q], fs=fns[base]: fq(x) if x < 0 else fs(x)
            query = -3 if epoch % 2 else 4
            if diverge and _behavior(teacher) not in known and self._proposable(teacher, query):
                break
        else:
            return dict(phase="phase_boundary", proposed=False)
        task, expected = self._task(teacher, query)
        ops = [_Callable(n, fns[n]) for n in sorted(fns)]
        # Declared tie-break among programs that agree on the certified query:
        # reuse library skills (higher layer first) over raw primitives.
        piece = self.patch.synthesize(ops, task.public_io, task.query, meter=self.meter,
            prefer=tuple(lib))
        out = dict(phase="phase_boundary", proposed=True, base=base, perturbed_with=q, diverging_inputs=diverge,
                   status=piece["status"], fitting=piece.get("fitting", 0), solved=False, compiled=None)
        if piece["status"] != self.patch.STATUS_UNIQUE:
            return out
        out["solved"] = freeze(piece["query_value"]) == freeze(expected)
        guard, then, other = piece["witness"]
        if not out["solved"] or guard not in INT_GUARDS:
            return out
        plan = dict(kind="if", guard=guard, then=dict(kind="chain", steps=[then]),
                    **{"else": dict(kind="chain", steps=[other])})
        name = f"skill_{epoch}_branch_{digest(plan)[:8]}"
        record = self._admit(name, plan, task, piece["query_value"], crawled, local)
        if record is not None:
            out.update(compiled=name, layer=record["layer"])
            self._recipe(crawled, plan, epoch, name)
        return out

    # -- phase D: fault recovery -> try/except skill that really fires -------
    def fault_recovery(self, epoch, crawled, local):
        fns = self._all_fns(crawled, local)
        names = sorted(fns, key=lambda n: (not n.startswith("skill_"), n))
        known = self._known_behaviors(crawled, local)
        partial = [n for n in names if not _total_on(fns[n], CHECK_INPUTS)
                   and sum(outcome(fns[n], x)[0] == "ok" for x in PUBLIC_INPUTS) >= 3
                   and not _total_on(fns[n], PUBLIC_INPUTS)]
        total = [n for n in names if _total_on(fns[n], CHECK_INPUTS)]
        pairs = [(a, b) for a in partial for b in total if a != b]
        for k in range(len(pairs)):
            body, fallback = pairs[(epoch * 11 + k) % len(pairs)]
            fault_inputs = [x for x in CHECK_INPUTS if outcome(fns[body], x)[0] == "raise"]
            query = next((x for x in fault_inputs if x not in PUBLIC_INPUTS), fault_inputs[0])
            def teacher(x, fa=fns[body], fb=fns[fallback]):
                try:
                    return fa(x)
                except (ValueError, KeyError, ZeroDivisionError, TypeError, OverflowError):
                    return fb(x)
            if _behavior(teacher) not in known and self._proposable(teacher, query):
                break
        else:
            return dict(phase="fault_recovery", proposed=False)
        task, expected = self._task(teacher, query)
        ops = [_Callable(n, fns[n]) for n in names]
        piece = self.patch.synthesize(ops, task.public_io, task.query, meter=self.meter, prefer=tuple(names))
        out = dict(phase="fault_recovery", proposed=True, body=body, fallback=fallback, fault_inputs=fault_inputs,
                   status=piece["status"], fitting=piece.get("fitting", 0), solved=False, compiled=None)
        if piece["status"] != self.patch.STATUS_UNIQUE:
            return out
        out["solved"] = freeze(piece["query_value"]) == freeze(expected)
        guard, then, other = piece["witness"]
        if not out["solved"]:
            return out
        if guard == f"ok[{then}]":
            plan = dict(kind="try", body=dict(kind="chain", steps=[then]), fallback=dict(kind="chain", steps=[other]))
        elif guard in INT_GUARDS:
            plan = dict(kind="if", guard=guard, then=dict(kind="chain", steps=[then]),
                        **{"else": dict(kind="chain", steps=[other])})
        else:
            return out
        name = f"skill_{epoch}_recover_{digest(plan)[:8]}"
        record = self._admit(name, plan, task, piece["query_value"], crawled, local)
        if record is not None:
            out.update(compiled=name, layer=record["layer"], except_fired_on=record["except_fired_on"])
            self._recipe(crawled, plan, epoch, name)
        return out

    def play_epoch(self, epoch):
        crawled = self.ground.crawl(self.brain, meter=self.meter)
        local = {}
        phases = [self.explore(epoch, crawled, local), self.compound(epoch, crawled, local),
                  self.phase_boundary(epoch, crawled, local), self.fault_recovery(epoch, crawled, local)]
        self.brain.save()
        snap = self.brain.metabolic.assert_stable()
        return dict(epoch=epoch, solved=any(p.get("solved") for p in phases), phases=phases,
                    compiled=[p["compiled"] for p in phases if p.get("compiled")],
                    operators=crawled["operator_count"], fingerprint_ms=crawled["fingerprint_ms"],
                    module_scanned=crawled["module_scanned"], metabolic=snap)

    def run(self, epochs):
        reports = [self.play_epoch(i) for i in range(int(epochs))]
        snap = self.brain.save()
        lineage = self.brain.lineage
        return dict(schema="wave24_unlimited_playground_v2", epochs=len(reports), reports=reports,
                    toolbox=self.brain.toolbox_names, atp_total_sum=snap["atp_total_sum"],
                    normalized_atp_entropy=snap["normalized_atp_entropy"],
                    recipes=len(self.brain.recipes),
                    max_hierarchy_layer=max((v["layer"] for v in lineage.values()), default=0),
                    constructs=sorted({c for v in lineage.values() for c in v["constructs"]}),
                    max_primitive_cost=max((v["primitive_cost"] for v in lineage.values()), default=0),
                    nursery=sorted(k for k, v in lineage.items() if v["status"] == "nursery"),
                    graduated=sorted(k for k, v in lineage.items() if v["status"] == "graduated"),
                    evicted=sorted(k for k, v in lineage.items() if v["status"] == "evicted"),
                    except_fired_skills=sorted(k for k, v in lineage.items() if v.get("except_fired_on")),
                    false_certificate_count=self.false_certificates)


def run_playground(brain_dir, epochs=3, *, meter=None):
    meter = meter if meter is not None else WorkMeter(limit=500_000, wall_limit=1.)
    brain = PersistentNexusBrain(brain_dir, meter=meter)
    return OpenEndedCuriosityLoop(brain, meter=meter).run(epochs)
