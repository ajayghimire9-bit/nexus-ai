"""Wave-12 fresh assessment suite. Created only after Commit 1 freeze."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .capability_evidence import digest
from .correspondence_env import PUBLIC_SLOTS
from .cross_domain_analogy import PUBLIC_SEQ, SEQUENCE_MECHANISMS, Seq, as_seq
from .hierarchical_gated_evolution import Wave8World
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_wave11c_fresh_assessment import OPENED_IDS as W11C_OPENED
from .mechanism_world import language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .wave12_subtree_opcode_learner import (
    PRIMITIVE_KEYS,
    WAVE12_METHODS,
    WORK_KEYS,
    TypedEqualCapabilityLearner,
    execute_wave12_program_ast,
    format_runner_summary,
    reconstruct_primitive_steps,
    reconstruct_total_work,
)

KIND = "seed_wave12_subtree_opcode_enumerator"
PRIOR_CLOSED = (
    "5777ea2",
    "4353a0c",
    "1d6a946",
    "e940b82",
)
OPENED_IDS = set(W11C_OPENED)

SPLIT_BASE = "w12f_base_and_dynamic_consts"
SPLIT_ANALOGY = "w12f_cross_domain_analogy"
SPLIT_SUBTREE = "w12f_unassisted_subtree_invention"
SPLIT_PIECE = "w12f_piecewise_multibranch"
SPLIT_ARCHIVE = "w12f_spurious_distractor_and_delayed_archive"
SPLIT_OOG = "w12f_true_oog_abstention"

ROT_PUBLIC = {
    "alpha": (),
    "beta": ("a", "b"),
    "gamma": ("c", "d", "e", "f"),
    "delta": ("x",),
}
PAL_PUBLIC = {
    "alpha": (),
    "beta": ("a",),
    "gamma": ("r", "a", "r"),
    "delta": ("a", "b"),
}


def seq_even_dollar(seq: Seq) -> Seq:
    return seq + ("$",) if len(seq) % 2 == 0 else seq


def seq_odd_at(seq: Seq) -> Seq:
    return (("@",) + seq) if len(seq) % 2 == 1 else seq


def seq_even_reverse(seq: Seq) -> Seq:
    return seq[::-1] if len(seq) % 2 == 0 else seq


def seq_even_dup(seq: Seq) -> Seq:
    return seq + seq if len(seq) % 2 == 0 else seq


def seq_odd_reverse(seq: Seq) -> Seq:
    return seq[::-1] if len(seq) % 2 == 1 else seq


def _rot_left(seq: Seq) -> Seq:
    return seq[1:] + seq[:1] if seq else seq


def seq_even_rot_at(seq: Seq) -> Seq:
    if len(seq) % 2 == 0:
        return ("@",) + _rot_left(seq)
    return seq


def seq_even_rot_dollar(seq: Seq) -> Seq:
    if len(seq) % 2 == 0:
        return _rot_left(seq) + ("$",)
    return seq


def seq_even_rot(seq: Seq) -> Seq:
    return _rot_left(seq) if len(seq) % 2 == 0 else seq


def seq_even_rot_wrap(seq: Seq) -> Seq:
    if len(seq) % 2 == 0:
        return ("@",) + _rot_left(seq) + ("$",)
    return seq


def seq_even_dollar_odd_at(seq: Seq) -> Seq:
    if len(seq) % 2 == 0:
        return seq + ("$",)
    return ("@",) + seq


def seq_len0_dollar_odd_at(seq: Seq) -> Seq:
    if len(seq) == 0:
        return seq + ("$",)
    if len(seq) % 2 == 1:
        return ("@",) + seq
    return seq


def seq_even_rot_odd_dollar(seq: Seq) -> Seq:
    if len(seq) % 2 == 0:
        return _rot_left(seq)
    return seq + ("$",)


def seq_pal_percent(seq: Seq) -> Seq:
    return seq + ("%",) if seq == seq[::-1] else seq


def seq_pal_at(seq: Seq) -> Seq:
    return (("@",) + seq) if seq == seq[::-1] else seq


def seq_caesar_w12(seq: Seq) -> Seq:
    out = []
    for token in seq:
        if len(token) == 1 and "a" <= token <= "z":
            out.append(chr((ord(token) - 97 + 1) % 26 + 97))
        else:
            out.append(token)
    return tuple(out)


def seq_interleave_rev_w12(seq: Seq) -> Seq:
    return tuple(token for pair in zip(seq, seq[::-1]) for token in pair)


SEQUENCE_MECHANISMS.update(
    {
        "seq_even_dollar": seq_even_dollar,
        "seq_odd_at": seq_odd_at,
        "seq_even_reverse": seq_even_reverse,
        "seq_even_dup": seq_even_dup,
        "seq_odd_reverse": seq_odd_reverse,
        "seq_even_rot_at": seq_even_rot_at,
        "seq_even_rot_dollar": seq_even_rot_dollar,
        "seq_even_rot": seq_even_rot,
        "seq_even_rot_wrap": seq_even_rot_wrap,
        "seq_even_dollar_odd_at": seq_even_dollar_odd_at,
        "seq_len0_dollar_odd_at": seq_len0_dollar_odd_at,
        "seq_even_rot_odd_dollar": seq_even_rot_odd_dollar,
        "seq_pal_percent": seq_pal_percent,
        "seq_pal_at": seq_pal_at,
        "seq_caesar_w12": seq_caesar_w12,
        "seq_interleave_rev_w12": seq_interleave_rev_w12,
    }
)


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


WAVE12_FRESH_TASKS: Tuple[Dict[str, Any], ...] = (
    _task("w12f_base_even_dollar", SPLIT_BASE, "seq_even_dollar", 7001, "unique",
          ("c", "d", "e", "f"), {"alpha": ("z",), "beta": ("k", "l"), "gamma": (), "delta": ("m",)}),
    _task("w12f_base_odd_at", SPLIT_BASE, "seq_odd_at", 7002, "unique",
          ("q",), {"alpha": ("z",), "beta": ("k", "l"), "gamma": ("r",), "delta": ()}),
    _task("w12f_base_even_reverse", SPLIT_BASE, "seq_even_reverse", 7003, "unique",
          ("c", "d"), {"alpha": ("z", "y"), "beta": ("k",), "gamma": (), "delta": ("m", "n", "p", "q")}),
    _task("w12f_ana_even_dup", SPLIT_ANALOGY, "seq_even_dup", 7011, "unique",
          ("c", "d"), {"alpha": (), "beta": ("k",), "gamma": ("a", "b"), "delta": ("m", "n", "p", "q")}),
    _task("w12f_ana_odd_rev", SPLIT_ANALOGY, "seq_odd_reverse", 7012, "unique",
          ("q",), {"alpha": ("z",), "beta": ("k", "l"), "gamma": ("r",), "delta": ()}),
    _task("w12f_sub_rot_at", SPLIT_SUBTREE, "seq_even_rot_at", 7021, "unique",
          ("u", "v"), {"alpha": (), "beta": ("k", "l"), "gamma": ("a", "b", "c", "d"), "delta": ("x",)},
          ROT_PUBLIC),
    _task("w12f_sub_rot_dollar", SPLIT_SUBTREE, "seq_even_rot_dollar", 7022, "unique",
          ("u", "v"), {"alpha": (), "beta": ("k", "l"), "gamma": ("a", "b", "c", "d"), "delta": ("x",)},
          ROT_PUBLIC),
    _task("w12f_sub_rot_reuse", SPLIT_SUBTREE, "seq_even_rot", 7023, "unique",
          ("u", "v"), {"alpha": (), "beta": ("k", "l"), "gamma": ("a", "b", "c", "d"), "delta": ("x",)},
          ROT_PUBLIC),
    _task("w12f_sub_rot_l2", SPLIT_SUBTREE, "seq_even_rot_wrap", 7024, "unique",
          ("u", "v"), {"alpha": (), "beta": ("k", "l"), "gamma": ("a", "b", "c", "d"), "delta": ("x",)},
          ROT_PUBLIC),
    _task("w12f_piece_even_odd", SPLIT_PIECE, "seq_even_dollar_odd_at", 7031, "unique",
          ("q", "r"), {"alpha": (), "beta": ("k",), "gamma": ("a", "b"), "delta": ("r",)}),
    _task("w12f_piece_len0_odd", SPLIT_PIECE, "seq_len0_dollar_odd_at", 7032, "unique",
          ("q", "r"), {"alpha": (), "beta": ("k",), "gamma": ("a", "b"), "delta": ("r",)}),
    _task("w12f_piece_rot_odd", SPLIT_PIECE, "seq_even_rot_odd_dollar", 7033, "unique",
          ("u", "v"), {"alpha": (), "beta": ("k",), "gamma": ("a", "b"), "delta": ("r",)}, ROT_PUBLIC),
    _task("w12f_arc_pal_once", SPLIT_ARCHIVE, "seq_pal_percent", 7041, "unique",
          ("x", "y", "z"), {"alpha": ("a",), "beta": ("k", "l"), "gamma": ("r", "a", "r"), "delta": ()},
          PAL_PUBLIC),
    _task("w12f_arc_distract_even", SPLIT_ARCHIVE, "seq_even_dollar", 7042, "unique",
          ("c", "d"), {"alpha": ("z",), "beta": ("k", "l"), "gamma": (), "delta": ("m",)}),
    _task("w12f_arc_distract_odd", SPLIT_ARCHIVE, "seq_odd_at", 7043, "unique",
          ("q",), {"alpha": ("z",), "beta": ("k", "l"), "gamma": ("r",), "delta": ()}),
    _task("w12f_arc_delayed_pal", SPLIT_ARCHIVE, "seq_pal_at", 7044, "unique",
          ("x", "y", "z"), {"alpha": ("a",), "beta": ("k", "l"), "gamma": ("r", "a", "r"), "delta": ()},
          PAL_PUBLIC),
    _task("w12f_oog_caesar", SPLIT_OOG, "seq_caesar_w12", 7051, "abstain",
          ("w", "x", "y", "z"), {"alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p", "q")},
          None, "oog"),
    _task("w12f_oog_interleave", SPLIT_OOG, "seq_interleave_rev_w12", 7052, "abstain",
          ("a", "b"), {"alpha": ("c", "d"), "beta": ("x",), "gamma": (), "delta": ("p", "q", "r")},
          None, "oog"),
)

assert len(WAVE12_FRESH_TASKS) == 18
assert {row["task_id"] for row in WAVE12_FRESH_TASKS}.isdisjoint(OPENED_IDS)

SEED_ORDERS = {
    0: list(range(18)),
    1: [3, 4, 0, 1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
    2: [9, 10, 11, 0, 1, 2, 5, 6, 7, 8, 12, 13, 14, 15, 3, 4, 16, 17],
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
    if gold == "abstain" or task.get("unknown_kind") == "oog":
        return status == "abstain"
    return status == "unique" and field == task.get("gold_field")


def _false_unique(task: Mapping[str, Any], status: str) -> bool:
    return bool(task.get("gold_status") == "abstain" and status == "unique")


def _evaluate_private(
    task: Mapping[str, Any],
    status: str,
    program_ast: Mapping[str, Any],
    world: Any,
    trace: List[Dict[str, Any]],
) -> Tuple[bool, List[Dict[str, Any]]]:
    private_evals: List[Dict[str, Any]] = []
    if task.get("gold_status") == "abstain" or task.get("unknown_kind") == "oog":
        return status == "abstain", private_evals
    if status != "unique" or program_ast.get("kind") == "abstain":
        return False, private_evals
    all_ok = True
    for slot in PUBLIC_SLOTS:
        rec = world.private_read(slot)
        trace.append({"phase": "private", "kind": "private_eval", "slot": slot, "before_lock": False})
        inp = as_seq(rec["payload"])
        gt = as_seq(rec["result"])
        pred = as_seq(execute_wave12_program_ast(program_ast, inp))
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
        catalog_audit=dict(report.catalog_audit),
        trace=trace,
    )


def _totals(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for method in WAVE12_METHODS:
        subset = [row for row in rows if row["method"] == method]
        out[method] = dict(
            n=len(subset),
            mapping_correct=sum(int(bool(row.get("mapping_correct"))) for row in subset),
            private_correct=sum(int(bool(row.get("private_correct"))) for row in subset),
            false_unique=sum(int(bool(row.get("false_unique"))) for row in subset),
            abstain=sum(int(row.get("status") == "abstain") for row in subset),
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
    oog = [row for row in rows if row.get("split") == SPLIT_OOG]
    if oog and any(row.get("status") != "abstain" for row in oog):
        ok = False
        notes.append("oog_not_abstain")
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
    for name in WAVE12_METHODS:
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
    return {
        "gate1_isolation_and_oog": all(
            token not in "".join(notes) for token in ("private", "false_unique", "oog")
        ),
        "gate2_identities": "work_identity" not in notes and "primitive_identity" not in notes,
        "gate3_full_accuracy": "full_accuracy" not in notes,
        "gate4_full_dominates": all("suite_" not in note and "subtree_" not in note for note in notes),
        "passed": ok,
        "notes": notes,
    }


def run_wave12_fresh_assessment(directory: Path) -> Dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    tasks = [dict(row) for row in WAVE12_FRESH_TASKS]
    if any(row["task_id"] in OPENED_IDS for row in tasks):
        raise ValueError("opened_id_in_challenge")
    assessment: List[Dict[str, Any]] = []
    seed_blocks: List[Dict[str, Any]] = []
    for seed in TRAIN_SEEDS:
        order = SEED_ORDERS[int(seed)]
        seed_rows: List[Dict[str, Any]] = []
        for method in WAVE12_METHODS:
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
        methods=list(WAVE12_METHODS),
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
    (directory / "seed_wave12_subtree_opcode_enumerator.json").write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    return payload
