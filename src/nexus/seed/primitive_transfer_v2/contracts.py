"""Closed JSON capabilities. Private payloads have no learner transport method.

These checks enforce structure, not semantic noninterference: a permitted string
could contain a secret. Only the public environment produces public source and
visible observations; private evaluator replies cannot enter that channel.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

MAX_MESSAGE_BYTES = 65536
FORBIDDEN = frozenset({
    "private_hidden_tests", "hidden_inputs", "hidden_outputs", "hidden_tests",
    "target_implementation", "correct_helper", "correct_helper_identity",
    "correct_post_operation", "correct_post_op", "correct_patch", "post_op",
    "patched_target_body", "semantic_class_id", "semantic_class_ids",
    "evaluator_labels", "oracle_scores", "oracle_score", "oracle_information",
    "ground_truth_callable", "target_ast_hash", "target_ast_sha256",
    "target_composition", "target_ops", "unqueried_outputs", "acceptance_labels",
    "protected_assessment_inputs_and_outputs", "hidden_semantic_equivalence_class",
})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fields(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError("exact message fields required")


def public(value, depth=0):
    if depth > 16:
        raise ValueError("JSON nesting limit")
    if value is None or type(value) is bool:
        return
    if type(value) in (int, float):
        if not math.isfinite(value) or abs(value) > 1e12:
            raise ValueError("finite bounded JSON number required")
    elif type(value) is str:
        if len(value.encode()) > 16384:
            raise ValueError("string limit")
    elif type(value) is list:
        if len(value) > 256:
            raise ValueError("list limit")
        for item in value:
            public(item, depth + 1)
    elif type(value) is dict:
        if len(value) > 64:
            raise ValueError("dictionary limit")
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("string keys required")
            normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
            normalized = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")
            if normalized in FORBIDDEN:
                raise ValueError("private field forbidden: " + key)
            public(item, depth + 1)
    else:
        raise ValueError("JSON values only; no Python objects or callables")


def encode(value):
    public(value)
    raw = canonical(value).encode()
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError("message byte limit")
    return raw


def decode(raw):
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError("message byte limit")

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out

    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    public(value)
    return value


ACTIONS = frozenset({"INSPECT", "CALL", "APPLY_AST_PATCH", "RUN_VISIBLE_TESTS", "STOP"})
OPCODES = ("OBSERVE", "GENERATE_TYPED_HYPOTHESES", "PREDICT_EFFECTS",
           "FILTER_INCONSISTENT", "COMPOSE_AST_PATCH", "RUN_VALIDATION", "STOP")


def action(value):
    fields(value, {"kind", "payload"})
    public(value)
    kind, p = value["kind"], value["payload"]
    if kind not in ACTIONS:
        raise ValueError("unsupported action")
    expected = {"INSPECT": set(), "CALL": {"name", "input"},
                "APPLY_AST_PATCH": {"source"}, "RUN_VISIBLE_TESTS": set(), "STOP": set()}
    fields(p, expected[kind])
    if kind == "CALL" and (type(p["name"]) is not str or not p["name"].isidentifier()):
        raise ValueError("function identifier required")
    if kind == "APPLY_AST_PATCH" and type(p["source"]) is not str:
        raise ValueError("source string required")
    return value


def task(value):
    fields(value, {"task_id", "source", "signature", "examples", "action_budget"})
    public(value)
    if any(type(value[k]) is not str for k in ("task_id", "source", "signature")):
        raise ValueError("public task strings required")
    if type(value["action_budget"]) is not int or not 1 <= value["action_budget"] <= 64:
        raise ValueError("bounded action budget required")
    if type(value["examples"]) is not list or not 2 <= len(value["examples"]) <= 4:
        raise ValueError("two to four visible examples required")
    for example in value["examples"]:
        fields(example, {"input", "output"})
    return value


def rule(value):
    fields(value, {"instructions"})
    ops = value["instructions"]
    if type(ops) is not list or not 1 <= len(ops) <= 64 or ops[-1] != "STOP":
        raise ValueError("bounded terminating rule required")
    if any(op not in OPCODES for op in ops):
        raise ValueError("unsupported DSL opcode")
    return value


def request(role, value):
    fields(value, {"id", "command", "payload"})
    public(value)
    if type(value["id"]) is not int or value["id"] < 0:
        raise ValueError("nonnegative message id required")
    p, cmd = value["payload"], value["command"]
    if role == "learner":
        if cmd == "start":
            fields(p, {"task", "rule"}); task(p["task"]); rule(p["rule"])
        elif cmd == "next":
            fields(p, {"receipt"})
            if p["receipt"] is not None:
                receipt(p["receipt"])
        else:
            raise ValueError("learner capability denied")
    elif role == "environment":
        if cmd == "start":
            task(p)
        elif cmd == "execute":
            action(p)
        else:
            raise ValueError("environment capability denied")
    elif role == "evaluator":
        if cmd not in ("fingerprint", "status"):
            raise ValueError("scientific evaluator capabilities not implemented")
        fields(p, set())
    else:
        raise ValueError("unknown role")
    return value


COUNTERS = ("source_bytes", "ast_nodes", "function_calls", "candidate_executions",
            "visible_tests", "patches", "sandbox_actions")


def receipt(value):
    fields(value, {"sequence", "action", "observation", "costs", "wall_ns", "cpu_ns",
                   "previous_sha256", "sha256"})
    public(value)
    action(value["action"])
    fields(value["costs"], COUNTERS)
    for x in list(value["costs"].values()) + [value["sequence"], value["wall_ns"], value["cpu_ns"]]:
        if type(x) is not int or x < 0:
            raise ValueError("nonnegative integer receipt counters required")
    for key in ("previous_sha256", "sha256"):
        if type(value[key]) is not str or not re.fullmatch(r"[0-9a-f]{64}", value[key]):
            raise ValueError("receipt hash required")
    body = {k: v for k, v in value.items() if k != "sha256"}
    if digest(body) != value["sha256"]:
        raise ValueError("receipt digest mismatch")
    return value


def response(role, value):
    fields(value, {"id", "ok", "payload"})
    public(value)
    if type(value["id"]) is not int or type(value["ok"]) is not bool:
        raise ValueError("typed response required")
    if not value["ok"]:
        fields(value["payload"], {"error"})
        if value["payload"]["error"] != "rejected":
            raise ValueError("exception details must not cross process boundary")
    elif role == "learner":
        fields(value["payload"], {"instruction", "action"})
        if value["payload"]["instruction"] not in OPCODES:
            raise ValueError("DSL instruction required")
        action(value["payload"]["action"])
    elif role == "environment":
        receipt(value["payload"])
    elif role == "evaluator":
        fields(value["payload"], {"state", "fingerprint"})
        if value["payload"]["state"] != "UNAUTHORIZED_IMPLEMENTATION_INCOMPLETE":
            raise ValueError("private evaluator declassification denied")
        if not re.fullmatch(r"[0-9a-f]{64}", value["payload"]["fingerprint"]):
            raise ValueError("kernel fingerprint required")
    else:
        raise ValueError("unknown role")
    return value
