"""Wave-13 unit tests: purity, disambiguation, subtree reuse, OOG, schema."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping

from nexus.seed.capability_evidence import digest
from nexus.seed.wave13_bounded_subtree_learner import (
    ALLOWED_PRIM_OPCODES,
    STATIC_INT_CONSTANTS,
    STATIC_TOK_CONSTANTS,
    ConstNode,
    EvolvedMacroNode,
    OpCounter,
    PrimOpNode,
    TypedEqualCapabilityLearner,
    TypeTag,
    VarNode,
    eval_expr_ast,
    execute_wave13_program_ast,
    extract_task_constants,
    format_runner_summary,
    iter_internal_subtrees,
    max_hierarchy_depth,
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
        extra_public_slots: Dict[str, tuple] | None = None,
    ) -> None:
        extras = dict(extra_public_slots or {})
        self.mechanism = mechanism
        self.public_map = dict(public_map)
        self.public_map.update(extras)
        self.extra_public_slots = extras
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
        if slot == "epsilon":
            payload = self.epsilon
        elif slot in self.public_map:
            payload = self.public_map[slot]
        else:
            payload = self.extra_public_slots[slot]
        return self._compose(payload, slot)

    def private_read(self, slot: str) -> Dict[str, Any]:
        if not self.locked:
            raise RuntimeError("private_eval_before_lock")
        self.private_opened = True
        return self._compose(self.private_map[slot], slot)

    def lock(self) -> None:
        self.locked = True


def _rot_right(seq: tuple) -> tuple:
    return (seq[-1],) + seq[:-1] if seq else seq


def _even_percent(seq: tuple) -> tuple:
    return seq + ("%",) if len(seq) % 2 == 0 else seq


def _even_reverse(seq: tuple) -> tuple:
    return seq[::-1] if len(seq) % 2 == 0 else seq


def _even_rot_at(seq: tuple) -> tuple:
    return (("@",) + _rot_right(seq)) if len(seq) % 2 == 0 else seq


def _even_rot_dollar(seq: tuple) -> tuple:
    return (_rot_right(seq) + ("$",)) if len(seq) % 2 == 0 else seq


def _even_rot_plus(seq: tuple) -> tuple:
    return (_rot_right(seq) + ("+",)) if len(seq) % 2 == 0 else seq


def _even_rot_plus_amp(seq: tuple) -> tuple:
    body = _rot_right(seq) + ("+",)
    return (("&",) + body) if len(seq) % 2 == 0 else seq


def _elementwise_dup(seq: tuple) -> tuple:
    out = []
    for token in seq:
        out.extend([token, token])
    return tuple(out)


BASE_PUBLIC = {"alpha": (), "beta": ("a",), "gamma": ("a", "b"), "delta": ("b",)}
LEN_EXTRAS = {
    "bank0": ("k", "l"),
    "bank1": ("k", "l", "m"),
    "bank2": ("k", "l", "m", "n"),
    "bank3": ("k", "l", "m", "n", "p"),
    "bank4": ("k", "l", "m", "n", "p", "q"),
}
SUBTREE_PUBLIC = {
    "alpha": (),
    "beta": ("a", "b", "c", "d"),
    "gamma": ("w", "x"),
    "delta": ("z",),
}
SUBTREE_EXTRAS = {
    "bank0": ("e", "f"),
    "bank1": ("r", "s", "t", "u"),
    "bank2": ("g",),
    "hold0": ("m", "n", "p", "q"),
}
SUBTREE_PRIVATE = {
    "alpha": ("z",),
    "beta": ("k", "l"),
    "gamma": (),
    "delta": ("m", "n", "p", "q"),
}


def test_wave13_zero_lambda_and_static_purity() -> None:
    path = ROOT / "src" / "nexus" / "seed" / "wave13_bounded_subtree_learner.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Lambda)]
    assert STATIC_TOK_CONSTANTS == ()
    assert STATIC_INT_CONSTANTS == (0, 1, 2)
    assert "PREPEND_TOK" in ALLOWED_PRIM_OPCODES
    assert "DROP_LAST" in ALLOWED_PRIM_OPCODES


def test_extract_task_constants_novel_tokens() -> None:
    obs = [
        {"input": [], "observed_output": ["%"]},
        {"input": ["a"], "observed_output": ["a"]},
        {"input": ["a", "b"], "observed_output": ["a", "b", "&"]},
        {"input": ["b"], "observed_output": ["b"]},
    ]
    extracted = extract_task_constants(obs)
    assert extracted.work == 4
    assert "%" in extracted.tokens
    assert "&" in extracted.tokens
    assert "#" not in extracted.tokens


def test_eval_expr_ast_counts_nested_macro_primitives() -> None:
    x_node = VarNode()
    rot = PrimOpNode(
        "PREPEND_TOK",
        (
            PrimOpNode("LAST", (x_node,), TypeTag.TOK),
            PrimOpNode("DROP_LAST", (x_node,), TypeTag.SEQ),
        ),
        TypeTag.SEQ,
    )
    macro = EvolvedMacroNode("seq_macro_1", rot, (x_node,), TypeTag.SEQ, layer=1)
    wrapped = PrimOpNode(
        "APPEND_TOK",
        (macro, ConstNode("%", TypeTag.TOK)),
        TypeTag.SEQ,
    )
    counter = OpCounter()
    out = eval_expr_ast(wrapped, ("r", "a", "r"), counter)
    assert out == ("r", "r", "a", "%")
    assert counter.steps == 4
    assert rot.canonical_key() in {item.canonical_key() for item in iter_internal_subtrees(wrapped)}
    assert mdl_gain(3, 5) > 0


def test_active_guard_disambiguation_even_vs_threshold() -> None:
    learner = TypedEqualCapabilityLearner("equal_typed_scratch")
    env = MiniEnv(
        _even_reverse,
        BASE_PUBLIC,
        ("u", "v"),
        {
            "alpha": ("z", "y"),
            "beta": ("k",),
            "gamma": (),
            "delta": ("m", "n", "p", "q"),
        },
        LEN_EXTRAS,
    )
    report = learner.solve_unfamiliar_task(env, 10)
    assert report.status == "unique", report.status
    assert reconstruct_total_work(report_to_row(report)) == report.total_work
    assert reconstruct_primitive_steps(report_to_row(report)) == report.total_primitive_op_steps
    program = report.program_ast
    assert execute_wave13_program_ast(program, ("a", "b")) == ("b", "a")
    assert execute_wave13_program_ast(program, ("a",)) == ("a",)
    assert execute_wave13_program_ast(program, ("m", "n", "p", "q")) == ("q", "p", "n", "m")
    env.lock()
    for slot, payload in env.private_map.items():
        rec = env.private_read(slot)
        pred = execute_wave13_program_ast(program, rec["payload"])
        assert pred == rec["result"], (slot, payload, pred, rec["result"])


def test_unassisted_subtree_full_beats_whole_macro_and_scratch() -> None:
    methods = (
        "equal_typed_scratch",
        "nexus_whole_macro_only",
        "nexus_typed_full",
    )
    tasks = (
        ("mini_rot_at", _even_rot_at),
        ("mini_rot_dollar", _even_rot_dollar),
        ("mini_rot_plus", _even_rot_plus),
        ("mini_rot_l2", _even_rot_plus_amp),
    )
    totals: Dict[str, Dict[str, int]] = {}
    depths: Dict[str, int] = {}
    invented: Dict[str, int] = {}
    for method in methods:
        learner = TypedEqualCapabilityLearner(method)
        work = 0
        prims = 0
        inv = 0
        depth = 0
        for _task_id, mech in tasks:
            env = MiniEnv(
                mech,
                SUBTREE_PUBLIC,
                ("u", "v"),
                SUBTREE_PRIVATE,
                SUBTREE_EXTRAS,
            )
            report = learner.solve_unfamiliar_task(env, 10)
            # Size-9 L2 wrap is in-grammar only after a macro exists.
            if _task_id != "mini_rot_l2" or method != "equal_typed_scratch":
                assert report.status == "unique", (method, _task_id, report.status)
            work += report.total_work
            prims += report.total_primitive_op_steps
            inv += int(report.subtree_macro_invented)
            depth = max(depth, report.max_hierarchy_depth)
            if method == "nexus_typed_full" and _task_id == "mini_rot_l2":
                assert report.status == "unique"
                assert report.max_hierarchy_depth >= 2
        totals[method] = {"work": work, "prims": prims}
        depths[method] = depth
        invented[method] = inv
    assert invented["nexus_typed_full"] >= 1
    assert invented["nexus_whole_macro_only"] == 0
    assert depths["nexus_typed_full"] >= 1
    assert totals["nexus_typed_full"]["work"] < totals["nexus_whole_macro_only"]["work"]
    assert totals["nexus_typed_full"]["work"] < totals["equal_typed_scratch"]["work"]
    assert totals["nexus_typed_full"]["prims"] < totals["nexus_whole_macro_only"]["prims"]
    assert totals["nexus_typed_full"]["prims"] < totals["equal_typed_scratch"]["prims"]


def test_oog_elementwise_dup_abstains() -> None:
    learner = TypedEqualCapabilityLearner("nexus_typed_full")
    env = MiniEnv(
        _elementwise_dup,
        BASE_PUBLIC,
        ("a", "b", "c"),
        {"alpha": ("x", "y"), "beta": ("k",), "gamma": (), "delta": ("p", "q", "r")},
        {
            "bank0": ("a", "b", "c"),
            "bank1": ("w", "x", "y", "z"),
            "hold0": ("m", "n", "p"),
        },
    )
    report = learner.solve_unfamiliar_task(env, 10)
    assert report.status == "abstain"
    assert report.program_ast.get("kind") == "abstain"


def _private_evals(env: MiniEnv, program: Dict[str, Any]) -> List[Dict[str, Any]]:
    env.lock()
    rows = []
    for slot in ("alpha", "beta", "gamma", "delta"):
        rec = env.private_read(slot)
        pred = execute_wave13_program_ast(program, rec["payload"])
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
    from verify_wave13_bounded_subtree_enumerator import (
        inspect_wave13_learner_ast,
        verify_commit1_blindness,
        verify_payload,
    )

    ast_check = inspect_wave13_learner_ast(
        ROOT / "src" / "nexus" / "seed" / "wave13_bounded_subtree_learner.py"
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
        for task_id, mech, split, extras in (
            ("mini_even_percent", _even_percent, "w13_mini_base", LEN_EXTRAS),
            ("mini_rot_at", _even_rot_at, "w13_mini_subtree", SUBTREE_EXTRAS),
        ):
            public = SUBTREE_PUBLIC if "rot" in task_id else BASE_PUBLIC
            env = MiniEnv(
                mech,
                public,
                ("c", "d"),
                SUBTREE_PRIVATE,
                extras,
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
        "kind": "seed_wave13_bounded_subtree_enumerator",
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
    assert "output" not in list(obs0.keys())
    checked = verify_payload(payload, "wave13_mini")
    assert checked["valid"] is True, checked
    assert checked["replayed_rows"] == 10
