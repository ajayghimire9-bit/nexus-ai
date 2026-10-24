"""Wave-12 unit tests: schema freeze, dual cost identities, and synthetic replay."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

from nexus.seed.capability_evidence import digest
from nexus.seed.wave12_subtree_opcode_learner import (
    ALLOWED_PRIM_OPCODES,
    STATIC_INT_CONSTANTS,
    STATIC_TOK_CONSTANTS,
    ConstNode,
    EvolvedMacroNode,
    OpCounter,
    PiecewiseBranch,
    PiecewiseProgramAST,
    PrimOpNode,
    TypedEqualCapabilityLearner,
    TypeTag,
    VarNode,
    eval_expr_ast,
    execute_wave12_program_ast,
    extract_task_constants,
    format_runner_summary,
    iter_internal_subtrees,
    mdl_gain,
    reconstruct_primitive_steps,
    reconstruct_total_work,
    report_to_row,
)

ROOT = Path(__file__).resolve().parents[1]


class MiniEnv:
    def __init__(
        self,
        mechanism: Callable,
        public_map: Dict[str, tuple],
        epsilon: tuple,
        private_map: Dict[str, tuple],
    ) -> None:
        self.mechanism = mechanism
        self.public_map = public_map
        self.epsilon = epsilon
        self.private_map = private_map
        self.stamp = 0
        self.tick = 0
        self.locked = False
        self.private_opened = False

    def _compose(self, payload: tuple, slot: str) -> Dict[str, Any]:
        result = self.mechanism(payload)
        self.stamp += 1
        self.tick += 1
        return {
            "kind": "event",
            "payload": payload,
            "result": result,
            "echo": payload,
            "stamp": self.stamp,
            "tick": self.tick,
            "slot": slot,
        }

    def public_read(self, slot: str) -> Dict[str, Any]:
        payload = self.epsilon if slot == "epsilon" else self.public_map[slot]
        return self._compose(payload, slot)

    def private_read(self, slot: str) -> Dict[str, Any]:
        if not self.locked:
            raise RuntimeError("private_eval_before_lock")
        self.private_opened = True
        return self._compose(self.private_map[slot], slot)

    def lock(self) -> None:
        self.locked = True


def _even_dollar(seq: tuple) -> tuple:
    return seq + ("$",) if len(seq) % 2 == 0 else seq


def _rot_then_at(seq: tuple) -> tuple:
    rotated = seq[1:] + seq[:1] if seq else seq
    return ("@",) + rotated


PUBLIC_MAP = {"alpha": (), "beta": ("a",), "gamma": ("a", "b"), "delta": ("b",)}


def test_wave12_zero_lambda_and_static_purity() -> None:
    path = ROOT / "src" / "nexus" / "seed" / "wave12_subtree_opcode_learner.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Lambda)]
    assert STATIC_TOK_CONSTANTS == ()
    assert STATIC_INT_CONSTANTS == (0, 1, 2)
    assert "PREPEND_TOK" in ALLOWED_PRIM_OPCODES


def test_extract_task_constants_differential_tokens_and_length_boundaries() -> None:
    obs = [
        {"input": [], "observed_output": ["$"]},
        {"input": ["a"], "observed_output": ["a"]},
        {"input": ["a", "b"], "observed_output": ["a", "b", "$"]},
        {"input": ["b"], "observed_output": ["b"]},
    ]
    extracted = extract_task_constants(obs)
    assert extracted.work == 4
    assert "$" in extracted.tokens
    assert "#" not in extracted.tokens


def test_eval_expr_ast_counts_nested_macro_primitives() -> None:
    x_node = VarNode()
    rot = PrimOpNode(
        "APPEND_TOK",
        (
            PrimOpNode("TAIL", (x_node,), TypeTag.SEQ),
            PrimOpNode("HEAD", (x_node,), TypeTag.TOK),
        ),
        TypeTag.SEQ,
    )
    macro = EvolvedMacroNode("seq_macro_1", rot, (x_node,), TypeTag.SEQ, layer=1)
    wrapped = PrimOpNode(
        "PREPEND_TOK",
        (ConstNode("@", TypeTag.TOK), macro),
        TypeTag.SEQ,
    )
    counter = OpCounter()
    out = eval_expr_ast(wrapped, ("r", "a", "r"), counter)
    assert out == ("@", "a", "r", "r")
    assert counter.steps == 4


def test_internal_subtree_enumeration_and_mdl_gain() -> None:
    x_node = VarNode()
    rot = PrimOpNode(
        "APPEND_TOK",
        (
            PrimOpNode("TAIL", (x_node,), TypeTag.SEQ),
            PrimOpNode("HEAD", (x_node,), TypeTag.TOK),
        ),
        TypeTag.SEQ,
    )
    outer = PrimOpNode(
        "PREPEND_TOK",
        (ConstNode("@", TypeTag.TOK), rot),
        TypeTag.SEQ,
    )
    subs = iter_internal_subtrees(outer)
    keys = {item.canonical_key() for item in subs}
    assert rot.canonical_key() in keys
    assert mdl_gain(3, 5) > 0
    assert mdl_gain(2, 5) <= 0


def test_solve_unfamiliar_task_signature_and_dynamic_const_task() -> None:
    learner = TypedEqualCapabilityLearner("equal_typed_scratch")
    env = MiniEnv(_even_dollar, PUBLIC_MAP, ("c", "d", "e", "f"), {
        "alpha": ("z",),
        "beta": ("k", "l"),
        "gamma": (),
        "delta": ("m", "n"),
    })
    report = learner.solve_unfamiliar_task(env, 10)
    assert report.status == "unique"
    assert "$" in report.extracted_tokens
    assert reconstruct_total_work(report_to_row(report)) == report.total_work
    assert reconstruct_primitive_steps(report_to_row(report)) == report.total_primitive_op_steps
    assert execute_wave12_program_ast(report.program_ast, ("u", "v")) == ("u", "v", "$")


def test_piecewise_two_branch_synthesis() -> None:
    def mech(seq: tuple) -> tuple:
        if len(seq) % 2 == 0:
            return seq + ("$",)
        if seq:
            return ("@",) + seq
        return seq

    public = {"alpha": (), "beta": ("a",), "gamma": ("x", "y"), "delta": ("b",)}
    learner = TypedEqualCapabilityLearner("equal_typed_scratch")
    env = MiniEnv(mech, public, ("q", "r"), {
        "alpha": (),
        "beta": ("r",),
        "gamma": ("s", "t"),
        "delta": ("u", "v", "w", "x"),
    })
    report = learner.solve_unfamiliar_task(env, 10)
    assert report.status == "unique"
    program = report.program_ast
    assert len(program.get("branches") or []) >= 1
    assert execute_wave12_program_ast(program, ()) == ("$",)
    assert execute_wave12_program_ast(program, ("r",)) == ("@", "r")
    assert execute_wave12_program_ast(program, ("s", "t")) == ("s", "t", "$")


def _private_evals(env: MiniEnv, program: Dict[str, Any]) -> List[Dict[str, Any]]:
    env.lock()
    rows = []
    for slot in ("alpha", "beta", "gamma", "delta"):
        rec = env.private_read(slot)
        pred = execute_wave12_program_ast(program, rec["payload"])
        rows.append(
            {
                "slot": slot,
                "input": list(rec["payload"]),
                "predicted_output": list(pred),
                "ground_truth_output": list(rec["result"]),
            }
        )
    return rows


def test_synthetic_payload_matches_runner_and_verifier_schema() -> None:
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    from verify_wave12_subtree_opcode_enumerator import (
        inspect_wave12_learner_ast,
        verify_commit1_blindness,
        verify_payload,
    )

    ast_check = inspect_wave12_learner_ast(
        ROOT / "src" / "nexus" / "seed" / "wave12_subtree_opcode_learner.py"
    )
    assert ast_check["valid"] is True, ast_check
    assert ast_check["lambda_count"] == 0
    blindness = verify_commit1_blindness(None)
    assert blindness["valid"] is True, blindness

    assessment = []
    for method in (
        "equal_typed_scratch",
        "ordinary_persistent_memoization",
        "nexus_whole_macro_only",
        "nexus_typed_without_pruning",
        "nexus_typed_full",
    ):
        learner = TypedEqualCapabilityLearner(method)
        for task_id, mech, split in (
            ("mini_even_dollar", _even_dollar, "w12_mini_base"),
            ("mini_rot_at", _rot_then_at, "w12_mini_subtree"),
        ):
            env = MiniEnv(
                mech,
                PUBLIC_MAP,
                ("c", "d"),
                {"alpha": ("z",), "beta": ("k", "l"), "gamma": (), "delta": ("m", "n", "p")},
            )
            report = learner.solve_unfamiliar_task(env, 10)
            row = report_to_row(report)
            row.update(
                source_seed=0,
                task_id=task_id,
                split=split,
                mapping_correct=report.status == "unique",
                private_correct=True,
                false_analogy_lock=False,
                false_unique=False,
                private_evaluations=_private_evals(env, report.program_ast),
                private_before_lock=False,
            )
            for pev in row["private_evaluations"]:
                if tuple(pev["predicted_output"]) != tuple(pev["ground_truth_output"]):
                    row["private_correct"] = False
            assessment.append(row)

    def _totals(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        out = {}
        methods = {row["method"] for row in rows}
        for method in methods:
            subset = [row for row in rows if row["method"] == method]
            out[method] = {
                "n": len(subset),
                "mapping_correct": sum(int(row["mapping_correct"]) for row in subset),
                "private_correct": sum(int(row["private_correct"]) for row in subset),
                "total_work": sum(int(row["total_work"]) for row in subset),
                "total_primitive_op_steps": sum(
                    int(row["total_primitive_op_steps"]) for row in subset
                ),
            }
        return out

    payload = {
        "kind": "seed_wave12_subtree_opcode_enumerator",
        "assessment": assessment,
        "totals": {"suite": _totals(assessment)},
        "gates": {"passed": True},
        "usage": {"model_calls": 0, "frozen_debit_s": 0},
    }
    payload["hash"] = digest(
        {key: payload[key] for key in ("kind", "assessment", "totals", "gates")}
    )
    summary = format_runner_summary(payload)
    assert "suite_totals" in summary
    assert summary["suite_totals"] is payload["totals"]["suite"]
    obs0 = payload["assessment"][0]["public_observations"][0]
    assert "observed_output" in obs0
    assert "output" not in obs0
    checked = verify_payload(payload, "wave12_mini")
    assert checked["valid"] is True, checked
    assert checked["replayed_rows"] == 10
