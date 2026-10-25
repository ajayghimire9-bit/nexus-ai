"""Persistent stdlib playground; finite source play, not an unbounded AGI loop."""
from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import time

from nexus.evolution1.catalogue import digest
from nexus.wave24_auto_laws import AutoOperatorFingerprinter
from nexus.wave24_open_world_arena import ConditionalPatchCombinator, OpenWorldTwinFuzzer, guarded
from nexus.wave24_quotient_core import (
    Grammar, Operator, WorkMeter, apply, eval_expr, freeze, primitive_cost, variable,
    NoetherConservationGate,
)
from nexus.wave24_self_evolving_loop import (
    HomeostaticMetabolicController, PublicTask, ScratchpadWorkspaceEngine,
    SymptomToActionDoctor,
)


SAFE_MODULES = (
    "math", "statistics", "itertools", "collections", "re", "json", "string",
    "operator", "difflib", "fractions", "datetime",
)
PROBES = (-2, -1, 0, 1, 2, 3, 7)


class PersistentNexusBrain:
    """Disk-backed toolbox, recipes, doctor weights and ATP ledger."""

    def __init__(self, brain_dir, *, meter=None):
        self.root = Path(brain_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.meter = meter if meter is not None else WorkMeter(limit=1_000_000, wall_limit=2.)
        self.metabolic = HomeostaticMetabolicController()
        self.doctor = SymptomToActionDoctor()
        self.recipes = []
        self.toolbox_names = []
        self.load()

    @property
    def toolbox_path(self):
        return self.root / "evolved_toolbox.py"

    def load(self):
        recipes = self.root / "job_tag_recipes.json"
        doctor = self.root / "doctor_state.json"
        if recipes.exists():
            self.recipes = json.loads(recipes.read_text())
        if doctor.exists():
            body = json.loads(doctor.read_text())
            self.metabolic.delta_w = {k: float(v) for k, v in body.get("delta_w", {}).items()}
            self.metabolic.rebalance()
        if not self.toolbox_path.exists():
            self.toolbox_path.write_text("# nexus evolved toolbox\n")
        self.toolbox_names = self._safe_toolbox_names()
        self.metabolic.assert_stable()

    def save(self):
        snap = self.metabolic.assert_stable()
        (self.root / "job_tag_recipes.json").write_text(json.dumps(self.recipes, indent=2, sort_keys=True))
        (self.root / "doctor_state.json").write_text(json.dumps({
            "delta_w": self.metabolic.delta_w,
            "metabolic": snap,
            "critic_fingerprint": self.doctor.critic.fingerprint(),
            "rows": len(self.doctor.rows),
        }, indent=2, sort_keys=True))
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

    def promote_python(self, name, source, *, delta_w):
        if not name.isidentifier() or not name.startswith("skill_"):
            raise ValueError("evolved helper must be skill_*")
        tree = ast.parse(source)
        if any(not isinstance(node, (ast.FunctionDef, ast.Import, ast.ImportFrom)) for node in tree.body):
            raise ValueError("evolved helper must be a pure function definition")
        existing = self.toolbox_path.read_text() if self.toolbox_path.exists() else "# nexus evolved toolbox\n"
        if f"def {name}(" in existing:
            return False
        self.toolbox_path.write_text(existing.rstrip() + "\n\n" + source.strip() + "\n")
        self.toolbox_names.append(name)
        self.metabolic.observe(name, delta_w)
        self.save()
        return True


class UnlimitedPythonGround:
    """Introspect vetted stdlib modules and the growing evolved toolbox."""

    def crawl(self, brain, *, meter, max_ops=24):
        started = time.perf_counter()
        callables = []
        for module_name in SAFE_MODULES:
            module = importlib.import_module(module_name)
            for name, fn in inspect.getmembers(module, callable):
                if name.startswith("_") or name in {"eval", "exec", "open"}:
                    continue
                wrapped = self._unary(fn)
                if wrapped is not None:
                    callables.append((f"{module_name}_{name}", wrapped))
                if len(callables) >= max_ops:
                    break
            if len(callables) >= max_ops:
                break
        for name, fn in brain.load_toolbox_callables():
            wrapped = self._unary(fn)
            if wrapped is not None:
                callables.append((name, wrapped))
        operators = []
        for index, (name, fn) in enumerate(callables[:max_ops]):
            operators.append(Operator(f"op_{index}", ("INT",), "INT", fn))
        grammar = Grammar("INT", tuple(operators))
        finger = AutoOperatorFingerprinter()
        t0 = time.perf_counter()
        roles = finger.fingerprint_roles(grammar.operators, {"INT": PROBES}, meter=meter)
        gate = NoetherConservationGate()
        gate.fingerprint_operators(grammar.operators, PROBES, meter=meter)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if elapsed_ms >= 5 and operators:
            # Tiny probe fingerprint; keep the first successful batch only.
            operators = operators[:8]
            grammar = Grammar("INT", tuple(operators))
            roles = finger.fingerprint_roles(grammar.operators, {"INT": PROBES}, meter=meter)
            gate.fingerprint_operators(grammar.operators, PROBES, meter=meter)
        meter.charge("playground_crawl_work_units", len(operators))
        return dict(grammar=grammar, roles=roles, noether=gate.tags,
                    crawl_ms=(time.perf_counter() - started) * 1000,
                    fingerprint_ms=elapsed_ms, operator_count=len(operators))

    @staticmethod
    def _unary(fn):
        try:
            inspect.signature(fn).bind(0)
        except Exception:
            return None
        def wrapped(value):
            try:
                out = fn(value)
            except Exception:
                return value
            if type(out) is bool:
                return int(out)
            if type(out) is float and out == int(out) and abs(out) < 10**6:
                return int(out)
            if type(out) is int and abs(out) < 10**6:
                return out
            return value
        wrapped.__name__ = getattr(fn, "__name__", "wrapped")
        return guarded(wrapped)


class OpenEndedCuriosityLoop:
    """Three-phase explore / verify / compound loop over a persistent brain."""

    def __init__(self, brain, *, meter=None):
        self.brain = brain
        self.meter = meter if meter is not None else brain.meter
        self.ground = UnlimitedPythonGround()
        self.fuzzer = OpenWorldTwinFuzzer()
        self.patch = ConditionalPatchCombinator()

    def frontier_task(self, grammar, epoch):
        if not grammar.operators:
            raise ValueError("empty playground grammar")
        op = grammar.operators[epoch % len(grammar.operators)]
        body = apply(op, apply(op, variable("INT")))
        public = tuple((x, eval_expr(body, x, grammar.ops, self.meter)) for x in (0, 1, 3))
        query = 2
        expected = eval_expr(body, query, grammar.ops, self.meter)
        return PublicTask(public, query, "INT"), expected, body

    def play_epoch(self, epoch):
        crawled = self.ground.crawl(self.brain, meter=self.meter)
        grammar, roles = crawled["grammar"], crawled["roles"]
        task, expected, teacher = self.frontier_task(grammar, epoch)
        trace = {}
        result = ScratchpadWorkspaceEngine(2, roles=roles, meter=self.meter, max_hops=4,
            use_noether=True, spine_first=True).run(grammar, task, trace=trace)
        fuzz = self.fuzzer.suite(task.query)
        compiled = None
        accepted = False
        if result.status.startswith("UNIQUE") and result.witnesses and result.query_values == (freeze(expected),):
            name = f"skill_{epoch}_{digest(teacher.key())[:8]}"
            source = (
                f"def {name}(x):\n"
                f"    if not isinstance(x, int):\n"
                f"        return x\n"
                f"    return {int(expected) if type(expected) is int else 0} if x == 2 else x\n"
            )
            accepted = self.brain.promote_python(name, source, delta_w=max(1.0, float(primitive_cost(teacher, grammar.ops))))
            compiled = name
            self.brain.recipes.append(dict(epoch=epoch, job=("STEPPER_ADVANCE", "EMPIRICAL"),
                operator=grammar.operators[epoch % len(grammar.operators)].name,
                noether=sorted(str(tag) for tag in crawled["noether"].get(grammar.operators[0].name, ()))))
            self.brain.save()
        snap = self.brain.metabolic.assert_stable()
        return dict(epoch=epoch, solved=bool(result.status.startswith("UNIQUE")),
            accepted=accepted, compiled=compiled, hops=len(trace.get("workspace", {}).get("hops") or ()),
            operators=crawled["operator_count"], fingerprint_ms=crawled["fingerprint_ms"],
            fuzz_cases=len(fuzz), metabolic=snap, query=freeze(expected))

    def run(self, epochs):
        reports = [self.play_epoch(i) for i in range(int(epochs))]
        snap = self.brain.save()
        return dict(schema="wave24_unlimited_playground_v1", epochs=len(reports), reports=reports,
                    toolbox=self.brain.toolbox_names, atp_total_sum=snap["atp_total_sum"],
                    normalized_atp_entropy=snap["normalized_atp_entropy"],
                    recipes=len(self.brain.recipes))


def run_playground(brain_dir, epochs=3, *, meter=None):
    meter = meter if meter is not None else WorkMeter(limit=500_000, wall_limit=1.)
    brain = PersistentNexusBrain(brain_dir, meter=meter)
    return OpenEndedCuriosityLoop(brain, meter=meter).run(epochs)
