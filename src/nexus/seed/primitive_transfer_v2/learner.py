"""Public-only DSL boundary prototype; no evaluator import or outcome access.

The restricted interpreter can find a public helper and construct an AST patch
on authored fixtures. Primitive proposal, information-gain probes, composition,
and evolution are NOT implemented here and cannot be claimed as demonstrated.
"""
from __future__ import annotations

import ast

from .contracts import action, rule, task


class Learner:
    def start(self, public_task, frozen_rule):
        self.task = task(public_task)
        self.rule = rule(frozen_rule)
        self.pc = 0
        self.names = []
        self.index = 0
        self.pending = False
        self.observed = None
        self.chosen = None
        self.source = public_task["source"]

    def next(self, receipt):
        if self.pending:
            self.pending = False
            self.observed = receipt["observation"]
        # A DSL instruction controls every emitted action, including STOP.
        # No instruction may silently invoke an environment action internally.
        if self.pc >= len(self.rule["instructions"]):
            op = "STOP"
        else:
            op = self.rule["instructions"][self.pc]
            self.pc += 1
        kind, p = "INSPECT", {}
        if op == "FILTER_INCONSISTENT" and self.observed is not None:
            observed, self.observed = self.observed, None
            expected = self.task["examples"][self.index]["output"]
            if observed.get("status") != "ok" or observed.get("output") != expected:
                self.names = self.names[1:]
                self.index = 0
            else:
                self.index += 1
                if self.index == len(self.task["examples"]):
                    self.chosen = self.names[0]
        if op == "GENERATE_TYPED_HYPOTHESES":
            tree = ast.parse(self.source)
            self.names = sorted(n.name for n in tree.body
                                if type(n) is ast.FunctionDef and n.name != "entry")
            self.index = 0
            self.chosen = None
        elif op == "PREDICT_EFFECTS" and self.names and self.chosen is None:
            kind, p = "CALL", {"name": self.names[0],
                               "input": self.task["examples"][self.index]["input"]}
            self.pending = True
        elif op == "COMPOSE_AST_PATCH" and self.chosen:
            tree = ast.parse(self.source)
            for n in tree.body:
                if n.name == "entry":
                    arg = n.args.args[0].arg
                    n.body = [ast.Return(ast.Call(ast.Name(self.chosen, ast.Load()),
                                                  [ast.Name(arg, ast.Load())], []))]
            kind, p = "APPLY_AST_PATCH", {"source": ast.unparse(ast.fix_missing_locations(tree))}
        elif op == "RUN_VALIDATION":
            kind = "RUN_VISIBLE_TESTS"
        elif op == "STOP":
            kind = "STOP"
        return {"instruction": op, "action": action({"kind": kind, "payload": p})}
