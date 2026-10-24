"""Wave-14 tests: piecewise seed invariance, cold archive, subtree, schema."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

from nexus.seed.capability_evidence import digest
from nexus.seed.wave14_piecewise_archive_learner import (
    ALLOWED_PRIM_OPCODES,
    STATIC_INT_CONSTANTS,
    STATIC_TOK_CONSTANTS,
    TypedEqualCapabilityLearner,
    TypedProgramEnumerator,
    execute_wave14_program_ast,
    extract_task_constants,
    format_runner_summary,
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


def _even_rot(seq: tuple) -> tuple:
    return _rot_right(seq) if len(seq) % 2 == 0 else seq


def _even_rot_tilde(seq: tuple) -> tuple:
    return (_rot_right(seq) + ("~",)) if len(seq) % 2 == 0 else seq


def _even_rot_caret(seq: tuple) -> tuple:
    return (("^",) + _rot_right(seq)) if len(seq) % 2 == 0 else seq


def _even_rot_plus(seq: tuple) -> tuple:
    return (_rot_right(seq) + ("+",)) if len(seq) % 2 == 0 else seq


def _even_rot_plus_wrap(seq: tuple) -> tuple:
    body = _rot_right(seq) + ("+",)
    return (("~",) + body) if len(seq) % 2 == 0 else seq


def _even_rot_odd_rev(seq: tuple) -> tuple:
    if len(seq) % 2 == 0:
        return _rot_right(seq)
    return seq[::-1]


def _pal_tilde(seq: tuple) -> tuple:
    return seq + ("~",) if seq == seq[::-1] else seq


def _pal_caret(seq: tuple) -> tuple:
    return (("^",) + seq) if seq == seq[::-1] else seq


def _even_rev(seq: tuple) -> tuple:
    return seq[::-1] if len(seq) % 2 == 0 else seq


def _odd_rev(seq: tuple) -> tuple:
    return seq[::-1] if len(seq) % 2 == 1 else seq


def _even_tail(seq: tuple) -> tuple:
    return seq[1:] if len(seq) % 2 == 0 else seq


ROT_PUBLIC = {
    "alpha": (),
    "beta": ("a", "b", "c", "d"),
    "gamma": ("w", "x"),
    "delta": ("z", "y", "x"),
}
ROT_EXTRAS = {
    "bank0": ("e", "f"),
    "bank1": ("r", "s", "t", "u"),
    "bank2": ("g", "h", "i"),
    "bank3": ("p", "q"),
    "hold0": ("m", "n", "p", "q"),
    "hold1": ("i", "j", "k"),
}
ROT_PRIVATE = {
    "alpha": ("k", "l"),
    "beta": ("a", "b", "c"),
    "gamma": (),
    "delta": ("m", "n", "p", "q"),
}
PAL_PUBLIC = {
    "alpha": (),
    "beta": ("a",),
    "gamma": ("r", "a", "r"),
    "delta": ("a", "b"),
}
PAL_EXTRAS = {
    "bank0": ("k", "k"),
    "bank1": ("x", "y"),
    "hold0": ("m", "n", "m"),
}


def test_wave14_zero_lambda_and_tier0_purity() -> None:
    path = ROOT / "src" / "nexus" / "seed" / "wave14_piecewise_archive_learner.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Lambda)]
    assert STATIC_TOK_CONSTANTS == ()
    assert STATIC_INT_CONSTANTS == (0, 1, 2)
    assert "PREPEND_TOK" in ALLOWED_PRIM_OPCODES
    en = TypedProgramEnumerator()
    extracted = extract_task_constants(
        [{"input": [], "observed_output": ["~"]}, {"input": ["a"], "observed_output": ["a"]}]
    )
    assert "~" in extracted.tokens
    t0g = [g.canonical_key() for g in en.enumerate_tier0_base_guards(extracted)]
    assert any("MOD2" in key for key in t0g)
    assert not any("SEQ_EQ" in key for key in t0g)
    assert not any("INT_GE" in key for key in t0g)
    assert not any("TOK_EQ" in key for key in t0g)
    t0t = [t.canonical_key() for t in en.enumerate_tier0_base_transforms(extracted)]
    assert all(node.ast_nodes() <= 2 for node in en.enumerate_tier0_base_transforms(extracted))
    assert not any("APPEND_TOK" in key for key in t0t)
    t3g = [g.canonical_key() for g in en.enumerate_tier3_guards(extracted)]
    assert any("SEQ_EQ" in key for key in t3g)


def test_piecewise_macro_collision_ten_seeds() -> None:
    private_ok = 0
    for seed in range(10):
        learner = TypedEqualCapabilityLearner("nexus_typed_full")
        extras = dict(ROT_EXTRAS)
        if seed % 2 == 1:
            extras = dict(reversed(list(extras.items())))
        env0 = MiniEnv(_even_rot_tilde, ROT_PUBLIC, ("u", "v"), ROT_PRIVATE, extras)
        first = learner.solve_unfamiliar_task(env0, 10)
        assert first.status == "unique", (seed, first.status)
        env = MiniEnv(_even_rot_odd_rev, ROT_PUBLIC, ("u", "v", "w"), ROT_PRIVATE, extras)
        report = learner.solve_unfamiliar_task(env, 10)
        assert report.status == "unique", (seed, report.status)
        env.lock()
        ok = True
        for slot, payload in ROT_PRIVATE.items():
            rec = env.private_read(slot)
            pred = execute_wave14_program_ast(report.program_ast, rec["payload"])
            if pred != rec["result"]:
                ok = False
        assert execute_wave14_program_ast(report.program_ast, ("w", "x")) == ("x", "w")
        assert execute_wave14_program_ast(report.program_ast, ("a", "b", "c")) == ("c", "b", "a")
        private_ok += int(ok)
    assert private_ok == 10


def test_cold_archive_eviction_and_reactivation_five_seeds() -> None:
    for seed in range(5):
        learner = TypedEqualCapabilityLearner("nexus_typed_full")
        env1 = MiniEnv(_pal_tilde, PAL_PUBLIC, ("x", "y", "z"), ROT_PRIVATE, PAL_EXTRAS)
        r1 = learner.solve_unfamiliar_task(env1, 10)
        assert r1.status == "unique", (seed, r1.status)
        assert r1.cold_archive_size == 0 or r1.active_library_size >= 1
        for mech in (_even_rev, _odd_rev, _even_tail):
            env_d = MiniEnv(mech, ROT_PUBLIC, ("c", "d"), ROT_PRIVATE, ROT_EXTRAS)
            rd = learner.solve_unfamiliar_task(env_d, 10)
            assert rd.status == "unique", (seed, mech, rd.status)
        assert learner.library.cold_archive, (seed, learner.library.operators.keys())
        env5 = MiniEnv(_pal_caret, PAL_PUBLIC, ("x", "y", "z"), ROT_PRIVATE, PAL_EXTRAS)
        r5 = learner.solve_unfamiliar_task(env5, 10)
        assert r5.status == "unique", (seed, r5.status)
        assert r5.cold_archive_reactivated is True, (seed, r5.used_operators, r5.pruned_operators)


def test_unassisted_subtree_full_beats_baselines() -> None:
    methods = ("equal_typed_scratch", "nexus_whole_macro_only", "nexus_typed_full")
    tasks = (
        ("wrap_tilde", _even_rot_tilde),
        ("wrap_caret", _even_rot_caret),
        ("reuse_plus", _even_rot_plus),
        ("l2_wrap", _even_rot_plus_wrap),
    )
    totals: Dict[str, Dict[str, int]] = {}
    invented = {}
    depth = {}
    for method in methods:
        learner = TypedEqualCapabilityLearner(method)
        work = 0
        prims = 0
        inv = 0
        max_d = 0
        for task_id, mech in tasks:
            env = MiniEnv(mech, ROT_PUBLIC, ("u", "v"), ROT_PRIVATE, ROT_EXTRAS)
            report = learner.solve_unfamiliar_task(env, 10)
            if task_id != "l2_wrap" or method != "equal_typed_scratch":
                assert report.status == "unique", (method, task_id, report.status)
            work += report.total_work
            prims += report.total_primitive_op_steps
            inv += int(report.subtree_macro_invented)
            max_d = max(max_d, report.max_hierarchy_depth)
        totals[method] = {"work": work, "prims": prims}
        invented[method] = inv
        depth[method] = max_d
    assert invented["nexus_typed_full"] >= 1
    assert invented["nexus_whole_macro_only"] == 0
    assert depth["nexus_typed_full"] >= 2
    assert totals["nexus_typed_full"]["work"] < totals["nexus_whole_macro_only"]["work"]
    assert totals["nexus_typed_full"]["work"] < totals["equal_typed_scratch"]["work"]
    assert totals["nexus_typed_full"]["prims"] < totals["nexus_whole_macro_only"]["prims"]
    assert totals["nexus_typed_full"]["prims"] < totals["equal_typed_scratch"]["prims"]


def _private_evals(env: MiniEnv, program: Dict[str, Any]) -> List[Dict[str, Any]]:
    env.lock()
    rows = []
    for slot in ("alpha", "beta", "gamma", "delta"):
        rec = env.private_read(slot)
        pred = execute_wave14_program_ast(program, rec["payload"])
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
    from verify_wave14_piecewise_archive_enumerator import (
        inspect_wave14_learner_ast,
        verify_commit1_blindness,
        verify_payload,
    )

    ast_check = inspect_wave14_learner_ast(
        ROOT / "src" / "nexus" / "seed" / "wave14_piecewise_archive_learner.py"
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
            ("mini_even_rev", _even_rev, "w14_mini_base"),
            ("mini_rot_tilde", _even_rot_tilde, "w14_mini_subtree"),
        ):
            env = MiniEnv(mech, ROT_PUBLIC, ("c", "d"), ROT_PRIVATE, ROT_EXTRAS)
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
        for method in {row["method"] for row in rows}:
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
        "kind": "seed_wave14_piecewise_archive_enumerator",
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
    checked = verify_payload(payload, "wave14_mini")
    assert checked["valid"] is True, checked
    assert checked["replayed_rows"] == 10
