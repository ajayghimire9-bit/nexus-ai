"""Wave-13 fresh assessment suite. Created only after Commit 1 freeze."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .capability_evidence import digest
from .correspondence_env import PUBLIC_SLOTS
from .cross_domain_analogy import SEQUENCE_MECHANISMS, Seq, as_seq
from .hierarchical_gated_evolution import Wave8World
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_wave12_fresh_assessment import OPENED_IDS as W12_OPENED
from .mechanism_world import language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .wave13_bounded_subtree_learner import (
    PRIMITIVE_KEYS,
    WAVE13_METHODS,
    WORK_KEYS,
    TypedEqualCapabilityLearner,
    execute_wave13_program_ast,
    format_runner_summary,
    reconstruct_primitive_steps,
    reconstruct_total_work,
)

KIND = "seed_wave13_bounded_subtree_enumerator"
PRIOR_CLOSED = (
    "6bdf9ae",
    "e940b82",
    "5777ea2",
    "4353a0c",
    "1d6a946",
)
OPENED_IDS = set(W12_OPENED) | {
    "w12f_base_even_dollar",
    "w12f_base_odd_at",
    "w12f_base_even_reverse",
    "w12f_ana_even_dup",
    "w12f_ana_odd_rev",
    "w12f_sub_rot_at",
    "w12f_sub_rot_dollar",
    "w12f_sub_rot_reuse",
    "w12f_sub_rot_l2",
    "w12f_piece_even_odd",
    "w12f_piece_len0_odd",
    "w12f_piece_rot_odd",
    "w12f_arc_pal_once",
    "w12f_arc_distract_even",
    "w12f_arc_distract_odd",
    "w12f_arc_delayed_pal",
    "w12f_oog_caesar",
    "w12f_oog_interleave",
}

SPLIT_BASE = "w13f_base_and_dynamic_literals"
SPLIT_ANALOGY = "w13f_cross_domain_analogy"
SPLIT_SUBTREE = "w13f_unassisted_subtree_and_L2"
SPLIT_PIECE = "w13f_piecewise_multibranch"
SPLIT_ARCHIVE = "w13f_spurious_distractor_and_delayed_archive"
SPLIT_OOG = "w13f_true_oog_and_ambiguous"

LEN_PUBLIC = {
    "alpha": (),
    "beta": ("a",),
    "gamma": ("a", "b"),
    "delta": ("b",),
}
LEN_EXTRAS = {
    "bank0": ("k", "l"),
    "bank1": ("k", "l", "m"),
    "bank2": ("k", "l", "m", "n"),
    "bank3": ("k", "l", "m", "n", "p"),
    "bank4": ("k", "l", "m", "n", "p", "q"),
    "hold0": ("r", "s", "t", "u"),
}
ODD_REV_PUBLIC = {
    "alpha": ("a", "b", "c"),
    "beta": ("q",),
    "gamma": ("x", "y"),
    "delta": ("m", "n", "p"),
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
PIECE_PUBLIC = {
    "alpha": (),
    "beta": ("a",),
    "gamma": ("a", "b"),
    "delta": ("b",),
}
PIECE_EXTRAS = {
    "bank0": ("e",),
    "bank1": ("f", "g"),
    "bank2": ("h",),
    "bank3": ("i", "j"),
    "bank4": ("k",),
    "bank5": ("l", "m"),
    "bank6": ("n",),
    "bank7": ("o", "p"),
    "hold0": ("q", "r"),
    "hold1": ("s",),
    "hold2": ("t", "u"),
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
OOG_PUBLIC = {
    "alpha": (),
    "beta": ("a",),
    "gamma": ("a", "b"),
    "delta": ("b",),
}
OOG_EXTRAS = {
    "bank0": ("a", "b", "c"),
    "bank1": ("w", "x", "y", "z"),
    "hold0": ("m", "n", "p"),
}


def seq_even_percent(seq: Seq) -> Seq:
    return seq + ("%",) if len(seq) % 2 == 0 else seq


def seq_odd_amp(seq: Seq) -> Seq:
    return (("&",) + seq) if len(seq) % 2 == 1 else seq


def seq_even_reverse_w13(seq: Seq) -> Seq:
    return seq[::-1] if len(seq) % 2 == 0 else seq


def seq_even_init(seq: Seq) -> Seq:
    return seq[:-1] if len(seq) % 2 == 0 else seq


def seq_odd_reverse_w13(seq: Seq) -> Seq:
    return seq[::-1] if len(seq) % 2 == 1 else seq


def _rot_right(seq: Seq) -> Seq:
    return ((seq[-1],) + seq[:-1]) if seq else seq


def seq_even_rot_percent(seq: Seq) -> Seq:
    return (_rot_right(seq) + ("%",)) if len(seq) % 2 == 0 else seq


def seq_even_rot_amp(seq: Seq) -> Seq:
    return (("&",) + _rot_right(seq)) if len(seq) % 2 == 0 else seq


def seq_even_rot_plus(seq: Seq) -> Seq:
    return (_rot_right(seq) + ("+",)) if len(seq) % 2 == 0 else seq


def seq_even_rot_plus_caret(seq: Seq) -> Seq:
    body = _rot_right(seq) + ("+",)
    return (("^",) + body) if len(seq) % 2 == 0 else seq


def seq_even_rot_l2_amp(seq: Seq) -> Seq:
    body = (("^",) + _rot_right(seq) + ("+",)) if seq or True else seq
    return (body + ("&",)) if len(seq) % 2 == 0 else seq


def seq_even_percent_odd_amp(seq: Seq) -> Seq:
    if len(seq) % 2 == 0:
        return seq + ("%",)
    return ("&",) + seq


def seq_even_rot_odd_amp(seq: Seq) -> Seq:
    if len(seq) % 2 == 0:
        return _rot_right(seq) + ("%",)
    return ("&",) + seq


def seq_pal_caret(seq: Seq) -> Seq:
    return (("^",) + seq) if seq == seq[::-1] else seq


def seq_pal_plus(seq: Seq) -> Seq:
    return seq + ("+",) if seq == seq[::-1] else seq


def seq_elementwise_dup(seq: Seq) -> Seq:
    out: List[str] = []
    for token in seq:
        out.extend([token, token])
    return tuple(out)


def seq_identity_w13(seq: Seq) -> Seq:
    return seq


SEQUENCE_MECHANISMS.update(
    {
        "seq_even_percent": seq_even_percent,
        "seq_odd_amp": seq_odd_amp,
        "seq_even_reverse_w13": seq_even_reverse_w13,
        "seq_even_init": seq_even_init,
        "seq_odd_reverse_w13": seq_odd_reverse_w13,
        "seq_even_rot_percent": seq_even_rot_percent,
        "seq_even_rot_amp": seq_even_rot_amp,
        "seq_even_rot_plus": seq_even_rot_plus,
        "seq_even_rot_plus_caret": seq_even_rot_plus_caret,
        "seq_even_rot_l2_amp": seq_even_rot_l2_amp,
        "seq_even_percent_odd_amp": seq_even_percent_odd_amp,
        "seq_even_rot_odd_amp": seq_even_rot_odd_amp,
        "seq_pal_caret": seq_pal_caret,
        "seq_pal_plus": seq_pal_plus,
        "seq_elementwise_dup": seq_elementwise_dup,
        "seq_identity_w13": seq_identity_w13,
    }
)


def _merged(public: dict, extras: dict | None = None) -> dict:
    row = dict(public)
    if extras:
        row.update(extras)
    return row


def _task(
    task_id: str,
    split: str,
    mechanism: str,
    seed: int,
    gold: str,
    epsilon: tuple,
    private: dict,
    public_map: dict | None = None,
    unknown: str | None = None,
) -> Dict[str, Any]:
    row = dict(
        task_id=task_id,
        split=split,
        domain="B",
        mechanism=mechanism,
        instance_seed=seed,
        gold_status=gold,
        gold_field=None if gold != "unique" else "result",
        epsilon=epsilon,
        private=private,
        record_mode="stamp_trap",
    )
    if public_map is not None:
        row["public_map"] = public_map
    if unknown:
        row["unknown_kind"] = unknown
    return row


WAVE13_FRESH_TASKS: Tuple[Dict[str, Any], ...] = (
    _task(
        "w13f_base_even_percent",
        SPLIT_BASE,
        "seq_even_percent",
        8101,
        "unique",
        ("c", "d"),
        {"alpha": ("z",), "beta": ("k", "l"), "gamma": (), "delta": ("m",)},
        _merged(LEN_PUBLIC, LEN_EXTRAS),
    ),
    _task(
        "w13f_base_odd_amp",
        SPLIT_BASE,
        "seq_odd_amp",
        8102,
        "unique",
        ("q",),
        {"alpha": ("z",), "beta": ("k", "l"), "gamma": ("r",), "delta": ()},
        _merged(LEN_PUBLIC, LEN_EXTRAS),
    ),
    _task(
        "w13f_base_even_reverse",
        SPLIT_BASE,
        "seq_even_reverse_w13",
        8103,
        "unique",
        ("c", "d"),
        {"alpha": ("z", "y"), "beta": ("k",), "gamma": (), "delta": ("m", "n", "p", "q")},
        _merged(LEN_PUBLIC, LEN_EXTRAS),
    ),
    _task(
        "w13f_ana_even_init",
        SPLIT_ANALOGY,
        "seq_even_init",
        8111,
        "unique",
        ("c", "d", "e", "f"),
        {"alpha": (), "beta": ("k",), "gamma": ("a", "b"), "delta": ("m", "n", "p", "q")},
        _merged(LEN_PUBLIC, LEN_EXTRAS),
    ),
    _task(
        "w13f_ana_odd_rev",
        SPLIT_ANALOGY,
        "seq_odd_reverse_w13",
        8112,
        "unique",
        ("q", "r", "s"),
        {"alpha": ("z", "y", "x"), "beta": ("k", "l"), "gamma": ("r",), "delta": ()},
        _merged(ODD_REV_PUBLIC, {"bank0": ("u", "v", "w"), "hold0": ("i", "j", "k")}),
    ),
    _task(
        "w13f_sub_rot_percent",
        SPLIT_SUBTREE,
        "seq_even_rot_percent",
        8121,
        "unique",
        ("u", "v"),
        {"alpha": ("z",), "beta": ("k", "l"), "gamma": (), "delta": ("m", "n", "p", "q")},
        _merged(SUBTREE_PUBLIC, SUBTREE_EXTRAS),
    ),
    _task(
        "w13f_sub_rot_amp",
        SPLIT_SUBTREE,
        "seq_even_rot_amp",
        8122,
        "unique",
        ("u", "v"),
        {"alpha": ("z",), "beta": ("k", "l"), "gamma": (), "delta": ("m", "n", "p", "q")},
        _merged(SUBTREE_PUBLIC, SUBTREE_EXTRAS),
    ),
    _task(
        "w13f_sub_rot_plus",
        SPLIT_SUBTREE,
        "seq_even_rot_plus",
        8123,
        "unique",
        ("u", "v"),
        {"alpha": ("z",), "beta": ("k", "l"), "gamma": (), "delta": ("m", "n", "p", "q")},
        _merged(SUBTREE_PUBLIC, SUBTREE_EXTRAS),
    ),
    _task(
        "w13f_sub_rot_l2_caret",
        SPLIT_SUBTREE,
        "seq_even_rot_plus_caret",
        8124,
        "unique",
        ("u", "v"),
        {"alpha": ("z",), "beta": ("k", "l"), "gamma": (), "delta": ("m", "n", "p", "q")},
        _merged(SUBTREE_PUBLIC, SUBTREE_EXTRAS),
    ),
    _task(
        "w13f_sub_rot_l2_amp",
        SPLIT_SUBTREE,
        "seq_even_rot_l2_amp",
        8125,
        "unique",
        ("u", "v"),
        {"alpha": ("z",), "beta": ("k", "l"), "gamma": (), "delta": ("m", "n", "p", "q")},
        _merged(SUBTREE_PUBLIC, SUBTREE_EXTRAS),
    ),
    _task(
        "w13f_piece_even_odd",
        SPLIT_PIECE,
        "seq_even_percent_odd_amp",
        8131,
        "unique",
        ("q", "r"),
        {"alpha": (), "beta": ("k",), "gamma": ("a", "b"), "delta": ("r",)},
        _merged(PIECE_PUBLIC, PIECE_EXTRAS),
    ),
    _task(
        "w13f_piece_rot_odd",
        SPLIT_PIECE,
        "seq_even_rot_odd_amp",
        8132,
        "unique",
        ("u", "v"),
        {"alpha": (), "beta": ("k",), "gamma": ("a", "b"), "delta": ("r",)},
        _merged(SUBTREE_PUBLIC, PIECE_EXTRAS),
    ),
    _task(
        "w13f_arc_pal_once",
        SPLIT_ARCHIVE,
        "seq_pal_caret",
        8141,
        "unique",
        ("x", "y", "z"),
        {"alpha": ("a",), "beta": ("k", "l"), "gamma": ("r", "a", "r"), "delta": ()},
        _merged(PAL_PUBLIC, PAL_EXTRAS),
    ),
    _task(
        "w13f_arc_distract_even",
        SPLIT_ARCHIVE,
        "seq_even_percent",
        8142,
        "unique",
        ("c", "d"),
        {"alpha": ("z",), "beta": ("k", "l"), "gamma": (), "delta": ("m",)},
        _merged(LEN_PUBLIC, LEN_EXTRAS),
    ),
    _task(
        "w13f_arc_distract_odd",
        SPLIT_ARCHIVE,
        "seq_odd_amp",
        8143,
        "unique",
        ("q",),
        {"alpha": ("z",), "beta": ("k", "l"), "gamma": ("r",), "delta": ()},
        _merged(LEN_PUBLIC, LEN_EXTRAS),
    ),
    _task(
        "w13f_arc_delayed_pal",
        SPLIT_ARCHIVE,
        "seq_pal_plus",
        8144,
        "unique",
        ("x", "y", "z"),
        {"alpha": ("a",), "beta": ("k", "l"), "gamma": ("r", "a", "r"), "delta": ()},
        _merged(PAL_PUBLIC, PAL_EXTRAS),
    ),
    _task(
        "w13f_oog_element_dup",
        SPLIT_OOG,
        "seq_elementwise_dup",
        8151,
        "abstain",
        ("a", "b", "c"),
        {"alpha": ("c", "d"), "beta": ("x",), "gamma": (), "delta": ("p", "q", "r")},
        _merged(OOG_PUBLIC, OOG_EXTRAS),
        "oog",
    ),
    _task(
        "w13f_amb_identity_fields",
        SPLIT_OOG,
        "seq_identity_w13",
        8152,
        "ambiguous",
        ("a", "b"),
        {"alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p", "q")},
        None,
        "ambiguous",
    ),
)

assert len(WAVE13_FRESH_TASKS) == 18
assert {row["task_id"] for row in WAVE13_FRESH_TASKS}.isdisjoint(OPENED_IDS)

SEED_ORDERS = {
    0: list(range(18)),
    1: [3, 4, 0, 1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
    2: [10, 11, 0, 1, 2, 5, 6, 7, 8, 9, 12, 13, 14, 15, 3, 4, 16, 17],
}


def _build_world(task: Mapping[str, Any]) -> Wave8World:
    return Wave8World(
        task["mechanism"],
        int(task["instance_seed"]),
        str(task.get("record_mode") or "stamp_trap"),
        tuple(task["epsilon"]),
        dict(task["private"]),
        task.get("public_map"),
    )


def _mapping_correct(task: Mapping[str, Any], status: str, field: str | None) -> bool:
    gold = task.get("gold_status")
    if gold == "ambiguous":
        return status == "ambiguous"
    if gold == "abstain" or task.get("unknown_kind") == "oog":
        return status == "abstain"
    return status == "unique" and field == task.get("gold_field")


def _false_unique(task: Mapping[str, Any], status: str) -> bool:
    return bool(task.get("gold_status") in {"abstain", "ambiguous"} and status == "unique")


def _evaluate_private(
    task: Mapping[str, Any],
    status: str,
    program_ast: Mapping[str, Any],
    world: Any,
    trace: List[Dict[str, Any]],
) -> Tuple[bool, List[Dict[str, Any]]]:
    private_evals: List[Dict[str, Any]] = []
    gold = task.get("gold_status")
    if gold == "ambiguous":
        return status == "ambiguous", private_evals
    if gold == "abstain" or task.get("unknown_kind") == "oog":
        return status == "abstain", private_evals
    if status != "unique" or program_ast.get("kind") == "abstain":
        return False, private_evals
    all_ok = True
    for slot in PUBLIC_SLOTS:
        rec = world.private_read(slot)
        trace.append({"phase": "private", "kind": "private_eval", "slot": slot, "before_lock": False})
        inp = as_seq(rec["payload"])
        gt = as_seq(rec["result"])
        pred = as_seq(execute_wave13_program_ast(program_ast, inp))
        match = pred == gt
        all_ok = all_ok and match
        private_evals.append(
            {
                "slot": slot,
                "input": list(inp),
                "predicted_output": list(pred),
                "ground_truth_output": list(gt),
                "match": match,
            }
        )
    return all_ok, private_evals


def run_episode(
    task: Mapping[str, Any],
    learner: TypedEqualCapabilityLearner,
    arrival_index: int,
    seed: int,
) -> Dict[str, Any]:
    world = _build_world(task)
    report = learner.solve_unfamiliar_task(world, 10)
    private_before_lock = bool(world.private_opened and not world.locked)
    world.lock()
    trace = list(report.trace)
    private_ok, private_evals = _evaluate_private(
        task, report.status, report.program_ast, world, trace
    )
    return dict(
        source_seed=seed,
        arrival_index=arrival_index,
        task_id=task["task_id"],
        split=task["split"],
        domain="B",
        mechanism=task["mechanism"],
        method=learner.method,
        gold_status=task.get("gold_status"),
        status=report.status,
        admitted_field=report.admitted_field,
        program_ast=report.program_ast,
        public_observations=report.public_observations,
        private_evaluations=private_evals,
        public_consistent=bool(report.public_consistent),
        mapping_correct=_mapping_correct(task, report.status, report.admitted_field),
        private_correct=bool(private_ok),
        false_unique=_false_unique(task, report.status),
        false_analogy_lock=False,
        ambiguous_correctly_declared=bool(
            task.get("gold_status") == "ambiguous" and report.status == "ambiguous"
        ),
        private_before_lock=private_before_lock,
        locked=bool(world.locked),
        public_env_probes=int(report.public_env_probes),
        public_validation_probes=int(report.public_validation_probes),
        channel_invariance_evals=int(report.channel_invariance_evals),
        probe_work=int(report.probe_work),
        role_probe_work=int(report.role_probe_work),
        const_extraction_work=int(report.const_extraction_work),
        schema_distill_cost=int(report.schema_distill_cost),
        gate_evals=int(report.gate_evals),
        archive_lookup_evals=int(report.archive_lookup_evals),
        compression_evals=int(report.compression_evals),
        synthesis_evals=int(report.synthesis_evals),
        compile_cost=int(report.compile_cost),
        codegen_plus_synthesis=int(report.codegen_plus_synthesis),
        total_work=int(report.total_work),
        synth_primitive_op_steps=int(report.synth_primitive_op_steps),
        gate_primitive_op_steps=int(report.gate_primitive_op_steps),
        archive_primitive_op_steps=int(report.archive_primitive_op_steps),
        probe_primitive_op_steps=int(report.probe_primitive_op_steps),
        compression_primitive_op_steps=int(report.compression_primitive_op_steps),
        total_primitive_op_steps=int(report.total_primitive_op_steps),
        confirmatory_probe_work=int(report.confirmatory_probe_work),
        used_operators=list(report.used_operators),
        invented_macros=list(report.invented_macros),
        sub_macro_reused=bool(report.sub_macro_reused),
        subtree_macro_invented=bool(report.subtree_macro_invented),
        memoized_program_reused=bool(report.memoized_program_reused),
        cold_archive_reactivated=bool(report.cold_archive_reactivated),
        pruned_operators=list(report.pruned_operators),
        active_library_size=int(report.active_library_size),
        cold_archive_size=int(report.cold_archive_size),
        extracted_tokens=list(report.extracted_tokens),
        extracted_ints=list(report.extracted_ints),
        max_hierarchy_depth=int(report.max_hierarchy_depth),
        catalog_audit=dict(report.catalog_audit),
        trace=trace,
        final_verify_primitive_op_steps=int(report.final_verify_primitive_op_steps),
    )


def _totals(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for method in WAVE13_METHODS:
        subset = [row for row in rows if row["method"] == method]
        out[method] = dict(
            n=len(subset),
            mapping_correct=sum(int(bool(row.get("mapping_correct"))) for row in subset),
            private_correct=sum(int(bool(row.get("private_correct"))) for row in subset),
            false_unique=sum(int(bool(row.get("false_unique"))) for row in subset),
            abstain=sum(int(row.get("status") == "abstain") for row in subset),
            ambiguous_correctly_declared=sum(
                int(bool(row.get("ambiguous_correctly_declared"))) for row in subset
            ),
            total_work=sum(int(row.get("total_work") or 0) for row in subset),
            total_primitive_op_steps=sum(int(row.get("total_primitive_op_steps") or 0) for row in subset),
            synthesis_evals=sum(int(row.get("synthesis_evals") or 0) for row in subset),
            const_extraction_work=sum(int(row.get("const_extraction_work") or 0) for row in subset),
            subtree_macro_invented=sum(int(bool(row.get("subtree_macro_invented"))) for row in subset),
            cold_archive_reactivated=sum(int(bool(row.get("cold_archive_reactivated"))) for row in subset),
        )
    return out


def evaluate_gates(payload: Mapping[str, Any]) -> Dict[str, Any]:
    notes: List[str] = []
    ok = True
    rows = list(payload.get("assessment") or [])
    totals = payload.get("totals") or {}
    if any(row.get("private_before_lock") for row in rows):
        ok = False
        notes.append("private_before_lock")
    if any(row.get("false_unique") for row in rows):
        ok = False
        notes.append("false_unique")
    oog = [row for row in rows if row.get("task_id") == "w13f_oog_element_dup"]
    if oog and any(row.get("status") != "abstain" for row in oog):
        ok = False
        notes.append("oog_not_abstain")
    amb = [row for row in rows if row.get("task_id") == "w13f_amb_identity_fields"]
    if amb and sum(int(bool(row.get("ambiguous_correctly_declared"))) for row in amb) != len(amb):
        ok = False
        notes.append("ambiguous_not_declared")
    full_rows = [row for row in rows if row["method"] == "nexus_typed_full"]
    if any(not row.get("mapping_correct") or not row.get("private_correct") for row in full_rows):
        ok = False
        notes.append("full_accuracy")
    for row in rows:
        if reconstruct_total_work(row) != int(row.get("total_work") or 0):
            ok = False
            notes.append("work_identity")
            break
        if reconstruct_primitive_steps(row) != int(row.get("total_primitive_op_steps") or 0):
            ok = False
            notes.append("primitive_identity")
            break
    suite = totals.get("suite") or {}
    full = suite.get("nexus_typed_full") or {}
    for name in WAVE13_METHODS:
        if name == "nexus_typed_full":
            continue
        other = suite.get(name) or {}
        if int(full.get("total_work", 10**9)) >= int(other.get("total_work", 0)):
            ok = False
            notes.append("suite_work_{0}".format(name))
        if int(full.get("total_primitive_op_steps", 10**9)) >= int(
            other.get("total_primitive_op_steps", 0)
        ):
            ok = False
            notes.append("suite_prim_{0}".format(name))
    subtree = totals.get("subtree") or {}
    if int((subtree.get("nexus_typed_full") or {}).get("total_work", 10**9)) >= int(
        (subtree.get("nexus_whole_macro_only") or {}).get("total_work", 0)
    ):
        ok = False
        notes.append("subtree_vs_whole_macro")
    delayed = [
        row
        for row in rows
        if row.get("task_id") == "w13f_arc_delayed_pal" and row.get("method") == "nexus_typed_full"
    ]
    if delayed and sum(int(bool(row.get("cold_archive_reactivated"))) for row in delayed) != 3:
        ok = False
        notes.append("archive_reactivation")
    return {
        "gate1_isolation_and_oog": all(
            token not in "".join(notes)
            for token in ("private_before_lock", "false_unique", "oog", "ambiguous")
        ),
        "gate2_identities": "work_identity" not in notes and "primitive_identity" not in notes,
        "gate3_full_accuracy": "full_accuracy" not in notes,
        "gate4_full_dominates": all(
            "suite_" not in note and "subtree_" not in note for note in notes
        ),
        "passed": ok,
        "notes": notes,
    }


def run_wave13_fresh_assessment(directory: Path) -> Dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    tasks = [dict(row) for row in WAVE13_FRESH_TASKS]
    if any(row["task_id"] in OPENED_IDS for row in tasks):
        raise ValueError("opened_id_in_challenge")
    assessment: List[Dict[str, Any]] = []
    seed_blocks: List[Dict[str, Any]] = []
    for seed in TRAIN_SEEDS:
        order = SEED_ORDERS[int(seed)]
        seed_rows: List[Dict[str, Any]] = []
        for method in WAVE13_METHODS:
            learner = TypedEqualCapabilityLearner(method)
            for arrival, idx in enumerate(order):
                episode = run_episode(tasks[idx], learner, arrival, int(seed))
                seed_rows.append(episode)
        assessment.extend(seed_rows)
        seed_blocks.append(
            dict(
                seed=seed,
                base=_totals([row for row in seed_rows if row["split"] == SPLIT_BASE]),
                analogy=_totals([row for row in seed_rows if row["split"] == SPLIT_ANALOGY]),
                subtree=_totals([row for row in seed_rows if row["split"] == SPLIT_SUBTREE]),
                piecewise=_totals([row for row in seed_rows if row["split"] == SPLIT_PIECE]),
                archive=_totals([row for row in seed_rows if row["split"] == SPLIT_ARCHIVE]),
                oog=_totals([row for row in seed_rows if row["split"] == SPLIT_OOG]),
                suite=_totals(seed_rows),
            )
        )
    totals = dict(
        base=_totals([row for row in assessment if row["split"] == SPLIT_BASE]),
        analogy=_totals([row for row in assessment if row["split"] == SPLIT_ANALOGY]),
        subtree=_totals([row for row in assessment if row["split"] == SPLIT_SUBTREE]),
        piecewise=_totals([row for row in assessment if row["split"] == SPLIT_PIECE]),
        archive=_totals([row for row in assessment if row["split"] == SPLIT_ARCHIVE]),
        oog=_totals([row for row in assessment if row["split"] == SPLIT_OOG]),
        suite=_totals(assessment),
    )
    payload = dict(
        kind=KIND,
        prior_closed=list(PRIOR_CLOSED),
        confirmation=False,
        learning_to_learn_established=False,
        track_b_closed=True,
        methods=list(WAVE13_METHODS),
        seeds=list(TRAIN_SEEDS),
        assessment=assessment,
        seed_blocks=seed_blocks,
        totals=totals,
        gates={},
        work_keys=list(WORK_KEYS),
        primitive_keys=list(PRIMITIVE_KEYS),
        usage=dict(
            kind=KIND,
            elapsed_s=0,
            model_calls=0,
            metal_used=False,
            frozen_debit_s=0,
            research_cpu_ledger_debit_s=0,
            ledger_class="symbolic_standing_grant_cpu_not_frozen_1p5b",
            frozen_cpu_used_s=FROZEN_CPU_USED_S,
            frozen_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
            wall_time_s=0,
            rss=sample_process_memory(),
        ),
        language_hash=language_hash(),
        runner_summary_probe=format_runner_summary(
            {"kind": KIND, "gates": {}, "totals": totals, "hash": None}
        ),
    )
    payload["gates"] = evaluate_gates(payload)
    elapsed = time.perf_counter() - started
    payload["usage"]["elapsed_s"] = elapsed
    payload["usage"]["wall_time_s"] = elapsed
    payload["hash"] = digest({key: payload[key] for key in ("kind", "assessment", "totals", "gates")})
    (directory / "seed_wave13_bounded_subtree_enumerator.json").write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    return payload
