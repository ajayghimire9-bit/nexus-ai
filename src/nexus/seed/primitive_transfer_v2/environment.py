"""Public-only environment using the existing adapter/receipt interfaces.

Does not initialize the legacy adapter (which owns private tests). This subclass
never holds a target implementation, hidden examples, or private evaluator.
"""
from __future__ import annotations

import ast
import time

from nexus.seed.open_primitive_transfer import CommonEnvironmentAdapter, TransitionReceipt
from .bounded import Program
from .contracts import COUNTERS, action, digest, receipt, task


class PublicEnvironment(CommonEnvironmentAdapter):
    def __init__(self, public_task):
        self.public_task = task(public_task)
        self.program = Program(public_task["source"])
        if "entry" not in self.program.functions:
            raise ValueError("public entry function required")
        self.actions = 0
        self.stopped = False
        self.previous = "0" * 64
        self.last_transition = None

    def snapshot(self):
        return {"source": self.public_task["source"],
                "remaining": self.public_task["action_budget"] - self.actions}

    def evaluate(self):
        raise PermissionError("private evaluation is not an environment capability")

    def restore(self, snapshot):
        raise PermissionError("resource counts cannot be reset through public actions")

    def execute(self, typed_action):
        action(typed_action)
        if self.stopped or self.actions >= self.public_task["action_budget"]:
            raise ValueError("stopped or action budget exhausted")
        start, cpu = time.monotonic_ns(), time.process_time_ns()
        before = self.snapshot()
        self.actions += 1
        costs = dict.fromkeys(COUNTERS, 0)
        costs["sandbox_actions"] = 1
        kind, p = typed_action["kind"], typed_action["payload"]
        obs = {"status": "ok"}
        try:
            if kind == "INSPECT":
                obs["source"] = self.public_task["source"]
                costs["source_bytes"] = len(obs["source"].encode())
                costs["ast_nodes"] = sum(1 for _ in ast.walk(self.program.tree))
            elif kind == "CALL":
                costs["candidate_executions"] = 1
                try:
                    obs["output"] = self.program.call(p["name"], p["input"])
                finally:
                    costs["function_calls"] = self.program.calls
            elif kind == "APPLY_AST_PATCH":
                costs["patches"] = 1
                candidate = Program(p["source"])
                if "entry" not in candidate.functions:
                    raise ValueError("entry missing")
                self.program = candidate
                self.public_task = dict(self.public_task, source=p["source"])
            elif kind == "RUN_VISIBLE_TESTS":
                passed = 0
                for ex in self.public_task["examples"]:
                    costs["visible_tests"] += 1
                    costs["candidate_executions"] += 1
                    try:
                        passed += self.program.call("entry", ex["input"]) == ex["output"]
                    finally:
                        costs["function_calls"] += self.program.calls
                obs["passed"] = passed
                obs["total"] = len(self.public_task["examples"])
            elif kind == "STOP":
                self.stopped = True
        except (ValueError, KeyError, IndexError, TypeError, ZeroDivisionError):
            # No exception object/stack/local variables cross the boundary.
            obs = {"status": "rejected"}
        elapsed, cpu_elapsed = time.monotonic_ns() - start, time.process_time_ns() - cpu
        self.last_transition = TransitionReceipt(
            observation_before=before, typed_action=typed_action, observation_after=obs,
            state_diff={"actions": 1}, stdout="", stderr="", exit_status=int(obs["status"] != "ok"),
            execution_time=elapsed / 1e9, resource_use=costs, provenance={"schema": "public_boundary_fixture_v2"})
        body = {"sequence": self.actions - 1, "action": typed_action,
                "observation": obs, "costs": costs, "wall_ns": elapsed,
                "cpu_ns": cpu_elapsed, "previous_sha256": self.previous}
        out = dict(body, sha256=digest(body))
        self.previous = out["sha256"]
        return receipt(out)
