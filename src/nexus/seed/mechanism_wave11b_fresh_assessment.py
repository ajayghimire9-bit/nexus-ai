"""Wave-11b fresh assessment suite and runner for the Bounded Typed Program Enumerator.

Constructed pursuant to the Wave-11 Part 3 Unconditional No-Amend Rule after
the initial Wave-11a runner wrapper script (`scripts/run_wave11_typed_assessment.py`)
encountered a dictionary key mismatch (`suite_totals` vs `totals["suite"]`) and
`c72a690 -> ffa43de` (`mechanism_wave11_fresh_assessment.py`, `w11f_*`) was
closed in Git history without amending `c72a690`.

Evaluates the exact same frozen `TypedProgramEnumerator`, `eval_expr_ast`, and
`TypedEqualCapabilityLearner` (`src/nexus/seed/wave11_typed_program_enumerator.py`,
SHA-256 `70076ef08dc310399878372710387da9833ba295d0374a2a031249e2987ae86a`)
across 16 brand-new unseen `w11b_*` tasks and 3 distinct permuted task arrival
orderings (`192` cells total = `3 seeds x 4 methods x 16 tasks`):

1. `equal_typed_scratch`
2. `ordinary_persistent_memoization`
3. `nexus_typed_without_pruning`
4. `nexus_typed_full`
"""

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
from .mechanism_wave8_deconfounded import L2_PUBLIC_MAP
from .mechanism_wave9_fresh_holdout import LEN_GE3_PUBLIC_MAP
from .mechanism_wave10_atomic_evolution import (
    HEAD_EQ_LAST_PUBLIC_MAP,
    NONEMPTY_PAL_PUBLIC_MAP,
    ODD_DROP_PUBLIC_MAP,
)
from .mechanism_wave11_fresh_assessment import (
    NONEMPTY_EVEN_PUBLIC_MAP,
    OPENED_IDS as W11A_PRIOR_OPENED,
    WAVE11_FRESH_TASKS,
)
from .mechanism_world import language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .wave11_typed_program_enumerator import (
    WAVE11_TYPED_METHODS,
    TypedEqualCapabilityLearner,
    execute_wave11_program_ast,
    typed_catalog_manifest,
)

KIND = "seed_wave11b_typed_program_enumerator"
PRIOR_CLOSED = (
    "f2e8942",
    "6e0df3a",
    "0d4596e",
    "c8bc5ad",
    "25cd50e",
    "f66ae34",
    "d2c0105",
    "10f579d",
    "aa34924",
    "b590ca2",
    "c3a4b40",
    "907db66",
    "561a563",
    "4cac886",
    "4a5a5f8",
    "bf66447",
    "f5741a6",
    "d0a8bb1",
    "9afb110",
    "16bb044",
    "f253be1",
    "c72a690",
    "ffa43de",
)
OPENED_IDS = set(W11A_PRIOR_OPENED) | {
    row["task_id"] for row in WAVE11_FRESH_TASKS
}

SPLIT_G1 = "w11b_g1_base"
SPLIT_G2 = "w11b_g2_lookalike"
SPLIT_STEP_PRED = "w11b_step_predicate_evolution"
SPLIT_STEP_TF = "w11b_step_transform_evolution"
SPLIT_DEEP = "w11b_deep_compositional"
SPLIT_SPURIOUS = "w11b_spurious_once_used"
SPLIT_DELAYED = "w11b_delayed_post_prune"
SPLIT_AMB = "w11b_ambiguous"
SPLIT_OOG = "w11b_oog"


# Register Wave-11b ground-truth environment mechanisms in SEQUENCE_MECHANISMS
def seq_even_question_w11b(seq: Seq) -> Seq:
    return seq + ("?",) if len(seq) % 2 == 0 else seq


def seq_odd_bang_w11b(seq: Seq) -> Seq:
    return seq + ("!",) if len(seq) % 2 == 1 else seq


def seq_len2_hash_w11b(seq: Seq) -> Seq:
    return seq + ("#",) if len(seq) == 2 else seq


def seq_len0_bang_w11b(seq: Seq) -> Seq:
    return seq + ("!",) if len(seq) == 0 else seq


def seq_head_eq_last_bang_w11b(seq: Seq) -> Seq:
    return seq + ("!",) if (len(seq) > 0 and seq[0] == seq[-1]) else seq


def seq_len_ge3_question_w11b(seq: Seq) -> Seq:
    return seq + ("?",) if len(seq) >= 3 else seq


def seq_len_ge3_hash_w11b(seq: Seq) -> Seq:
    return seq + ("#",) if len(seq) >= 3 else seq


def seq_pal_bang_w11b(seq: Seq) -> Seq:
    return seq + ("!",) if seq == seq[::-1] else seq


def seq_even_rotate_left_w11b(seq: Seq) -> Seq:
    if len(seq) % 2 == 0:
        return (seq[1:] + seq[:1]) if seq else ()
    return seq


def seq_odd_tail_question_w11b(seq: Seq) -> Seq:
    if len(seq) % 2 == 1:
        return seq[1:] + ("?",)
    return seq


def seq_pal_rot_hash_w11b(seq: Seq) -> Seq:
    if seq == seq[::-1]:
        return (seq[1:] + seq[:1] + ("#",)) if seq else ("#",)
    return seq


def seq_pal_rot_bang_w11b(seq: Seq) -> Seq:
    if seq == seq[::-1]:
        return (seq[1:] + seq[:1] + ("!",)) if seq else ("!",)
    return seq


def seq_pal_tail_question_w11b(seq: Seq) -> Seq:
    if seq == seq[::-1]:
        return seq[1:] + ("?",)
    return seq


SEQUENCE_MECHANISMS["seq_even_question_w11b"] = seq_even_question_w11b
SEQUENCE_MECHANISMS["seq_odd_bang_w11b"] = seq_odd_bang_w11b
SEQUENCE_MECHANISMS["seq_len2_hash_w11b"] = seq_len2_hash_w11b
SEQUENCE_MECHANISMS["seq_len0_bang_w11b"] = seq_len0_bang_w11b
SEQUENCE_MECHANISMS["seq_head_eq_last_bang_w11b"] = seq_head_eq_last_bang_w11b
SEQUENCE_MECHANISMS["seq_len_ge3_question_w11b"] = seq_len_ge3_question_w11b
SEQUENCE_MECHANISMS["seq_len_ge3_hash_w11b"] = seq_len_ge3_hash_w11b
SEQUENCE_MECHANISMS["seq_pal_bang_w11b"] = seq_pal_bang_w11b
SEQUENCE_MECHANISMS["seq_even_rotate_left_w11b"] = seq_even_rotate_left_w11b
SEQUENCE_MECHANISMS["seq_odd_tail_question_w11b"] = seq_odd_tail_question_w11b
SEQUENCE_MECHANISMS["seq_pal_rot_hash_w11b"] = seq_pal_rot_hash_w11b
SEQUENCE_MECHANISMS["seq_pal_rot_bang_w11b"] = seq_pal_rot_bang_w11b
SEQUENCE_MECHANISMS["seq_pal_tail_question_w11b"] = seq_pal_tail_question_w11b


WAVE11B_FRESH_TASKS: Tuple[Dict[str, Any], ...] = (
    # 2 Base Tasks (G1)
    dict(
        task_id="w11b_g1_even_q",
        split=SPLIT_G1,
        domain="B",
        mechanism="seq_even_question_w11b",
        instance_seed=5001,
        gold_status="unique",
        gold_field="result",
        epsilon=("g", "h", "i", "j"),
        private={
            "alpha": ("k",),
            "beta": ("p", "q"),
            "gamma": (),
            "delta": ("r", "s", "t", "u"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w11b_g1_odd_bang",
        split=SPLIT_G1,
        domain="B",
        mechanism="seq_odd_bang_w11b",
        instance_seed=5002,
        gold_status="unique",
        gold_field="result",
        epsilon=("x", "y", "z"),
        private={
            "alpha": ("m",),
            "beta": ("p", "q"),
            "gamma": ("n",),
            "delta": ("d", "e", "f"),
        },
        record_mode="stamp_trap",
    ),
    # 2 Lookalike Tasks (G2)
    dict(
        task_id="w11b_g2_len2_hash",
        split=SPLIT_G2,
        domain="B",
        mechanism="seq_len2_hash_w11b",
        instance_seed=5011,
        gold_status="unique",
        gold_field="result",
        epsilon=("e", "f", "g", "h"),
        private={
            "alpha": ("k",),
            "beta": ("p", "q"),
            "gamma": (),
            "delta": ("r", "s", "t", "u"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w11b_g2_len0_bang",
        split=SPLIT_G2,
        domain="B",
        mechanism="seq_len0_bang_w11b",
        instance_seed=5012,
        gold_status="unique",
        gold_field="result",
        epsilon=("e", "f", "g", "h"),
        private={
            "alpha": ("k",),
            "beta": ("p", "q"),
            "gamma": (),
            "delta": ("r", "s", "t", "u"),
        },
        record_mode="stamp_trap",
    ),
    # 2 Spurious Once-Used Tasks
    dict(
        task_id="w11b_spurious_head_eq_last_bang",
        split=SPLIT_SPURIOUS,
        domain="B",
        mechanism="seq_head_eq_last_bang_w11b",
        instance_seed=5021,
        gold_status="unique",
        gold_field="result",
        epsilon=("p", "q", "r", "p"),
        private={
            "alpha": ("c", "d", "c"),
            "beta": ("p", "q"),
            "gamma": (),
            "delta": ("u", "v", "w", "u"),
        },
        record_mode="stamp_trap",
        public_map=HEAD_EQ_LAST_PUBLIC_MAP,
    ),
    dict(
        task_id="w11b_spurious_len_ge3_q",
        split=SPLIT_SPURIOUS,
        domain="B",
        mechanism="seq_len_ge3_question_w11b",
        instance_seed=5022,
        gold_status="unique",
        gold_field="result",
        epsilon=("e", "f", "g", "h"),
        private={
            "alpha": ("c", "d", "e"),
            "beta": ("p", "q"),
            "gamma": (),
            "delta": ("r", "s", "t", "u"),
        },
        record_mode="stamp_trap",
        public_map=LEN_GE3_PUBLIC_MAP,
    ),
    # 3 Stepwise Operator-Evolution Tasks (1 Predicate, 2 Transform)
    dict(
        task_id="w11b_step_pred_pal_bang",
        split=SPLIT_STEP_PRED,
        domain="B",
        mechanism="seq_pal_bang_w11b",
        instance_seed=5031,
        gold_status="unique",
        gold_field="result",
        epsilon=("m", "o", "m"),
        private={
            "alpha": ("t", "t"),
            "beta": ("p", "q"),
            "gamma": (),
            "delta": ("f", "g", "f"),
        },
        record_mode="stamp_trap",
        public_map=L2_PUBLIC_MAP,
    ),
    dict(
        task_id="w11b_step_tf_even_rot",
        split=SPLIT_STEP_TF,
        domain="B",
        mechanism="seq_even_rotate_left_w11b",
        instance_seed=5032,
        gold_status="unique",
        gold_field="result",
        epsilon=("g", "h", "i", "j"),
        private={
            "alpha": ("k",),
            "beta": ("p", "q"),
            "gamma": ("d", "e", "f"),
            "delta": ("r", "s", "t", "u"),
        },
        record_mode="stamp_trap",
        public_map=NONEMPTY_EVEN_PUBLIC_MAP,
    ),
    dict(
        task_id="w11b_step_tf_odd_drop_q",
        split=SPLIT_STEP_TF,
        domain="B",
        mechanism="seq_odd_tail_question_w11b",
        instance_seed=5033,
        gold_status="unique",
        gold_field="result",
        epsilon=("x", "y", "z"),
        private={
            "alpha": ("k",),
            "beta": ("p", "q"),
            "gamma": ("d", "e", "f"),
            "delta": (),
        },
        record_mode="stamp_trap",
        public_map=ODD_DROP_PUBLIC_MAP,
    ),
    # 4 Deep Multi-Operator Compositional Tasks
    dict(
        task_id="w11b_deep_pal_rot_hash",
        split=SPLIT_DEEP,
        domain="B",
        mechanism="seq_pal_rot_hash_w11b",
        instance_seed=5041,
        gold_status="unique",
        gold_field="result",
        epsilon=("d", "e", "f", "d"),
        private={
            "alpha": ("t", "t"),
            "beta": ("p", "q"),
            "gamma": ("m", "a", "m"),
            "delta": ("z",),
        },
        record_mode="stamp_trap",
        public_map=NONEMPTY_PAL_PUBLIC_MAP,
    ),
    dict(
        task_id="w11b_deep_pal_rot_hash_reuse",
        split=SPLIT_DEEP,
        domain="B",
        mechanism="seq_pal_rot_hash_w11b",
        instance_seed=5042,
        gold_status="unique",
        gold_field="result",
        epsilon=("d", "e", "f", "d"),
        private={
            "alpha": ("u", "v", "u"),
            "beta": ("p", "q"),
            "gamma": ("h",),
            "delta": ("f", "g", "f"),
        },
        record_mode="stamp_trap",
        public_map=NONEMPTY_PAL_PUBLIC_MAP,
    ),
    dict(
        task_id="w11b_deep_pal_rot_bang",
        split=SPLIT_DEEP,
        domain="B",
        mechanism="seq_pal_rot_bang_w11b",
        instance_seed=5043,
        gold_status="unique",
        gold_field="result",
        epsilon=("d", "e", "f", "d"),
        private={
            "alpha": ("t", "t"),
            "beta": ("p", "q"),
            "gamma": ("m", "a", "m"),
            "delta": ("y",),
        },
        record_mode="stamp_trap",
        public_map=NONEMPTY_PAL_PUBLIC_MAP,
    ),
    dict(
        task_id="w11b_deep_pal_drop_q",
        split=SPLIT_DEEP,
        domain="B",
        mechanism="seq_pal_tail_question_w11b",
        instance_seed=5044,
        gold_status="unique",
        gold_field="result",
        epsilon=("d", "e", "f", "d"),
        private={
            "alpha": ("t", "t"),
            "beta": ("p", "q"),
            "gamma": ("m", "a", "m"),
            "delta": ("s",),
        },
        record_mode="stamp_trap",
        public_map=NONEMPTY_PAL_PUBLIC_MAP,
    ),
    # 1 Delayed Post-Prune Reuse Task
    dict(
        task_id="w11b_delayed_len_ge3_hash",
        split=SPLIT_DELAYED,
        domain="B",
        mechanism="seq_len_ge3_hash_w11b",
        instance_seed=5051,
        gold_status="unique",
        gold_field="result",
        epsilon=("r", "s", "t", "u"),
        private={
            "alpha": ("d", "e", "f", "g"),
            "beta": ("p", "q"),
            "gamma": (),
            "delta": ("h", "i", "j"),
        },
        record_mode="stamp_trap",
        public_map=LEN_GE3_PUBLIC_MAP,
    ),
    # 2 Safety Tasks (Ambiguous + OOG)
    dict(
        task_id="w11b_amb_alias_even",
        split=SPLIT_AMB,
        domain="B",
        mechanism="seq_even_question_w11b",
        instance_seed=5061,
        gold_status="ambiguous",
        gold_field="ambiguous",
        epsilon=("g", "h", "i", "j"),
        private={
            "alpha": ("k",),
            "beta": ("p", "q"),
            "gamma": (),
            "delta": ("r", "s"),
        },
        record_mode="alias_ambiguous",
    ),
    dict(
        task_id="w11b_oog_vowel_shift",
        split=SPLIT_OOG,
        domain="B",
        mechanism="seq_vowel_shift",
        instance_seed=5062,
        gold_status="abstain",
        gold_field=None,
        epsilon=("g", "h", "i", "j"),
        private={
            "alpha": ("k",),
            "beta": ("p", "q"),
            "gamma": (),
            "delta": ("r", "s"),
        },
        record_mode="stamp_trap",
        unknown_kind="oog",
    ),
)

TASK_ORDERS_BY_SEED: Dict[int, Tuple[str, ...]] = {
    0: (
        "w11b_g1_even_q",
        "w11b_spurious_head_eq_last_bang",
        "w11b_g1_odd_bang",
        "w11b_g2_len2_hash",
        "w11b_g2_len0_bang",
        "w11b_step_pred_pal_bang",
        "w11b_step_tf_even_rot",
        "w11b_deep_pal_rot_hash",
        "w11b_deep_pal_rot_hash_reuse",
        "w11b_deep_pal_rot_bang",
        "w11b_spurious_len_ge3_q",
        "w11b_step_tf_odd_drop_q",
        "w11b_deep_pal_drop_q",
        "w11b_delayed_len_ge3_hash",
        "w11b_amb_alias_even",
        "w11b_oog_vowel_shift",
    ),
    1: (
        "w11b_spurious_head_eq_last_bang",
        "w11b_g2_len2_hash",
        "w11b_g2_len0_bang",
        "w11b_spurious_len_ge3_q",
        "w11b_step_pred_pal_bang",
        "w11b_step_tf_odd_drop_q",
        "w11b_deep_pal_drop_q",
        "w11b_step_tf_even_rot",
        "w11b_deep_pal_rot_hash",
        "w11b_deep_pal_rot_bang",
        "w11b_deep_pal_rot_hash_reuse",
        "w11b_delayed_len_ge3_hash",
        "w11b_g1_even_q",
        "w11b_g1_odd_bang",
        "w11b_oog_vowel_shift",
        "w11b_amb_alias_even",
    ),
    2: (
        "w11b_spurious_head_eq_last_bang",
        "w11b_spurious_len_ge3_q",
        "w11b_g1_even_q",
        "w11b_g1_odd_bang",
        "w11b_step_pred_pal_bang",
        "w11b_step_tf_even_rot",
        "w11b_deep_pal_rot_hash",
        "w11b_deep_pal_rot_bang",
        "w11b_step_tf_odd_drop_q",
        "w11b_deep_pal_drop_q",
        "w11b_deep_pal_rot_hash_reuse",
        "w11b_delayed_len_ge3_hash",
        "w11b_g2_len2_hash",
        "w11b_g2_len0_bang",
        "w11b_amb_alias_even",
        "w11b_oog_vowel_shift",
    ),
}


def ordered_tasks_for_seed(seed: int) -> List[Dict[str, Any]]:
    by_id = {row["task_id"]: dict(row) for row in WAVE11B_FRESH_TASKS}
    order = TASK_ORDERS_BY_SEED.get(seed, TASK_ORDERS_BY_SEED[0])
    return [by_id[tid] for tid in order]


def _build_world_for_task(task: Mapping[str, Any]) -> Any:
    return Wave8World(
        str(task["mechanism"]),
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


def _false_analogy_lock(
    task: Mapping[str, Any], program_ast: Mapping[str, Any], status: str
) -> bool:
    if task.get("split") != SPLIT_G2 or status != "unique":
        return False
    ck = str(program_ast.get("canonical_key") or "")
    return "MOD2(" in ck


def _evaluate_private_post_lock(
    task: Mapping[str, Any],
    status: str,
    program_ast: Mapping[str, Any],
    world: Any,
    trace: List[Dict[str, Any]],
) -> Tuple[bool, List[Dict[str, Any]]]:
    gold = task.get("gold_status")
    private_evals: List[Dict[str, Any]] = []
    if gold in {"ambiguous", "abstain"}:
        return (status == gold), private_evals
    if status != "unique" or program_ast.get("kind") == "abstain":
        return False, private_evals

    all_ok = True
    for slot in PUBLIC_SLOTS:
        rec = world.private_read(slot)
        trace.append(
            {
                "phase": "private",
                "kind": "private_eval",
                "slot": slot,
                "before_lock": False,
            }
        )
        inp_seq = as_seq(rec["payload"])
        gt_seq = as_seq(rec["result"])
        pred_seq = as_seq(execute_wave11_program_ast(program_ast, inp_seq))
        match = pred_seq == gt_seq
        if not match:
            all_ok = False
        private_evals.append(
            {
                "slot": slot,
                "input": list(inp_seq),
                "predicted_output": list(pred_seq),
                "ground_truth_output": list(gt_seq),
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
    """Run one task episode by passing ONLY ``(world, 10)`` to the learner."""
    world = _build_world_for_task(task)
    report = learner.solve_unfamiliar_task(world, 10)

    private_before_lock = bool(world.private_opened and not world.locked)
    world.lock()
    trace = list(report.trace)
    private_ok, private_evals = _evaluate_private_post_lock(
        task, report.status, report.program_ast, world, trace
    )

    return dict(
        source_seed=seed,
        arrival_index=arrival_index,
        task_id=task["task_id"],
        split=task["split"],
        domain=task["domain"],
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
        ambiguous=bool(report.ambiguous),
        oog_abstained=bool(report.oog_abstained),
        false_analogy_lock=_false_analogy_lock(
            task, report.program_ast, report.status
        ),
        false_unique=bool(
            task.get("gold_status") == "ambiguous" and report.status == "unique"
        ),
        private_before_lock=private_before_lock,
        locked=bool(world.locked),
        public_env_probes=int(report.public_env_probes),
        public_validation_probes=int(report.public_validation_probes),
        channel_invariance_evals=int(report.channel_invariance_evals),
        schema_distill_cost=int(report.schema_distill_cost),
        gate_evals=int(report.gate_evals),
        archive_lookup_evals=int(report.archive_lookup_evals),
        compression_evals=int(report.compression_evals),
        synthesis_evals=int(report.synthesis_evals),
        operator_compile_cost=int(report.operator_compile_cost),
        codegen_plus_synthesis=int(report.codegen_plus_synthesis),
        total_work=int(report.total_work),
        schema_distilled=bool(report.schema_distilled),
        used_operators=list(report.used_operators),
        invented_macros=list(report.invented_macros),
        sub_macro_reused=bool(report.sub_macro_reused),
        full_program_macro_reused=bool(report.full_program_macro_reused),
        memoized_program_reused=bool(report.memoized_program_reused),
        cold_archive_reactivated=bool(report.cold_archive_reactivated),
        pruned_operators=list(report.pruned_operators),
        active_library_size=int(report.active_library_size),
        cold_archive_size=int(report.cold_archive_size),
        catalog_audit=dict(report.catalog_audit),
        trace=trace,
    )


COST_KEYS: Tuple[str, ...] = (
    "public_env_probes",
    "public_validation_probes",
    "channel_invariance_evals",
    "schema_distill_cost",
    "gate_evals",
    "archive_lookup_evals",
    "compression_evals",
    "synthesis_evals",
    "operator_compile_cost",
)


def _totals(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for method in WAVE11_TYPED_METHODS:
        subset = [r for r in rows if r["method"] == method]
        out[method] = dict(
            n=len(subset),
            mapping_correct=sum(int(bool(r.get("mapping_correct"))) for r in subset),
            private_correct=sum(int(bool(r.get("private_correct"))) for r in subset),
            false_analogy_lock=sum(
                int(bool(r.get("false_analogy_lock"))) for r in subset
            ),
            false_unique=sum(int(bool(r.get("false_unique"))) for r in subset),
            ambiguous=sum(int(r.get("status") == "ambiguous") for r in subset),
            abstain=sum(int(r.get("status") == "abstain") for r in subset),
            schema_distill_cost=sum(
                int(r.get("schema_distill_cost") or 0) for r in subset
            ),
            gate_evals=sum(int(r.get("gate_evals") or 0) for r in subset),
            archive_lookup_evals=sum(
                int(r.get("archive_lookup_evals") or 0) for r in subset
            ),
            compression_evals=sum(
                int(r.get("compression_evals") or 0) for r in subset
            ),
            synthesis_evals=sum(int(r.get("synthesis_evals") or 0) for r in subset),
            operator_compile_cost=sum(
                int(r.get("operator_compile_cost") or 0) for r in subset
            ),
            codegen_plus_synthesis=sum(
                int(r.get("codegen_plus_synthesis") or 0) for r in subset
            ),
            total_work=sum(int(r.get("total_work") or 0) for r in subset),
            sub_macro_reused=sum(
                int(bool(r.get("sub_macro_reused"))) for r in subset
            ),
            full_program_macro_reused=sum(
                int(bool(r.get("full_program_macro_reused"))) for r in subset
            ),
            memoized_program_reused=sum(
                int(bool(r.get("memoized_program_reused"))) for r in subset
            ),
            cold_archive_reactivated=sum(
                int(bool(r.get("cold_archive_reactivated"))) for r in subset
            ),
        )
    return out


def _seed_dispersion(
    seed_blocks: Sequence[Mapping[str, Any]], group_key: str
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for method in WAVE11_TYPED_METHODS:
        work_vals = [int(b[group_key][method]["total_work"]) for b in seed_blocks]
        code_vals = [
            int(b[group_key][method]["codegen_plus_synthesis"]) for b in seed_blocks
        ]
        priv_vals = [int(b[group_key][method]["private_correct"]) for b in seed_blocks]
        summary[method] = dict(
            private_correct_per_seed=priv_vals,
            total_work_mean=round(sum(work_vals) / max(len(work_vals), 1), 2),
            total_work_min=min(work_vals),
            total_work_max=max(work_vals),
            codegen_plus_synthesis_mean=round(
                sum(code_vals) / max(len(code_vals), 1), 2
            ),
            codegen_plus_synthesis_min=min(code_vals),
            codegen_plus_synthesis_max=max(code_vals),
        )
    return summary


def evaluate_gates(payload: Mapping[str, Any]) -> Dict[str, Any]:
    notes: List[str] = []
    ok = True
    rows = list(payload.get("assessment") or [])
    totals = payload.get("totals") or {}

    if any(r.get("private_before_lock") for r in rows):
        ok = False
        notes.append("private_before_lock")
    if any(r.get("false_analogy_lock") for r in rows):
        ok = False
        notes.append("false_analogy_lock")
    if any(r.get("false_unique") for r in rows):
        ok = False
        notes.append("false_unique")
    if any(not r.get("mapping_correct") or not r.get("private_correct") for r in rows):
        ok = False
        notes.append("solve_mismatch")

    suite_totals = totals.get("suite") or {}
    delayed_totals = totals.get("delayed") or {}

    w11_react = int(
        (delayed_totals.get("nexus_typed_full") or {}).get(
            "cold_archive_reactivated", 0
        )
    )
    if w11_react < 3:
        ok = False
        notes.append(f"delayed_reactivation_missing:{w11_react}")

    w11_code = int(
        (suite_totals.get("nexus_typed_full") or {}).get(
            "codegen_plus_synthesis", 999999
        )
    )
    w11_work = int(
        (suite_totals.get("nexus_typed_full") or {}).get("total_work", 999999)
    )
    for other_m in WAVE11_TYPED_METHODS:
        if other_m == "nexus_typed_full":
            continue
        other_code = int(
            (suite_totals.get(other_m) or {}).get("codegen_plus_synthesis", 0)
        )
        other_work = int((suite_totals.get(other_m) or {}).get("total_work", 0))
        if w11_code >= other_code:
            ok = False
            notes.append(
                f"not_lowest_codegen_plus_synthesis_vs_{other_m}:{w11_code}>={other_code}"
            )
        if w11_work >= other_work:
            ok = False
            notes.append(
                f"not_lowest_total_work_vs_{other_m}:{w11_work}>={other_work}"
            )

    gate1_ok = all(
        t not in notes
        for t in (
            "private_before_lock",
            "false_analogy_lock",
            "false_unique",
            "solve_mismatch",
        )
    )
    gate2_ok = "delayed_reactivation_missing" not in ":".join(notes)
    gate3_ok = not any(
        n.startswith(
            ("not_lowest_codegen_plus_synthesis_vs_", "not_lowest_total_work_vs_")
        )
        for n in notes
    )

    return dict(
        gate1_equal_typed_enumerator_and_label_blind=gate1_ok,
        gate2_cold_archive_reactivation=gate2_ok,
        gate3_typed_self_evolving_pareto_win=gate3_ok,
        passed=ok,
        notes=notes,
    )


def run_wave11b_typed_assessment(directory: Path) -> Dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    if any(row["task_id"] in OPENED_IDS for row in WAVE11B_FRESH_TASKS):
        raise ValueError("opened_id_in_challenge")

    assessment: List[Dict[str, Any]] = []
    seed_blocks: List[Dict[str, Any]] = []

    for seed in TRAIN_SEEDS:
        ordered_tasks = ordered_tasks_for_seed(seed)
        seed_rows: List[Dict[str, Any]] = []
        for method in WAVE11_TYPED_METHODS:
            learner = TypedEqualCapabilityLearner(method)
            for idx, task in enumerate(ordered_tasks):
                episode = run_episode(task, learner, idx, seed)
                seed_rows.append(episode)
        assessment.extend(seed_rows)
        seed_blocks.append(
            dict(
                seed=seed,
                task_order=[t["task_id"] for t in ordered_tasks],
                g1=_totals([r for r in seed_rows if r["split"] == SPLIT_G1]),
                g2=_totals([r for r in seed_rows if r["split"] == SPLIT_G2]),
                g12=_totals(
                    [r for r in seed_rows if r["split"] in {SPLIT_G1, SPLIT_G2}]
                ),
                step_pred=_totals(
                    [r for r in seed_rows if r["split"] == SPLIT_STEP_PRED]
                ),
                step_tf=_totals(
                    [r for r in seed_rows if r["split"] == SPLIT_STEP_TF]
                ),
                deep=_totals([r for r in seed_rows if r["split"] == SPLIT_DEEP]),
                spurious=_totals(
                    [r for r in seed_rows if r["split"] == SPLIT_SPURIOUS]
                ),
                delayed=_totals(
                    [r for r in seed_rows if r["split"] == SPLIT_DELAYED]
                ),
                amb=_totals([r for r in seed_rows if r["split"] == SPLIT_AMB]),
                oog=_totals([r for r in seed_rows if r["split"] == SPLIT_OOG]),
                suite=_totals(seed_rows),
            )
        )

    totals = dict(
        g1=_totals([r for r in assessment if r["split"] == SPLIT_G1]),
        g2=_totals([r for r in assessment if r["split"] == SPLIT_G2]),
        g12=_totals([r for r in assessment if r["split"] in {SPLIT_G1, SPLIT_G2}]),
        step_pred=_totals([r for r in assessment if r["split"] == SPLIT_STEP_PRED]),
        step_tf=_totals([r for r in assessment if r["split"] == SPLIT_STEP_TF]),
        deep=_totals([r for r in assessment if r["split"] == SPLIT_DEEP]),
        spurious=_totals([r for r in assessment if r["split"] == SPLIT_SPURIOUS]),
        delayed=_totals([r for r in assessment if r["split"] == SPLIT_DELAYED]),
        amb=_totals([r for r in assessment if r["split"] == SPLIT_AMB]),
        oog=_totals([r for r in assessment if r["split"] == SPLIT_OOG]),
        suite=_totals(assessment),
    )

    seed_dispersion = {
        group_key: _seed_dispersion(seed_blocks, group_key)
        for group_key in (
            "g1",
            "g2",
            "g12",
            "step_pred",
            "step_tf",
            "deep",
            "spurious",
            "delayed",
            "amb",
            "oog",
            "suite",
        )
    }

    payload: Dict[str, Any] = dict(
        kind=KIND,
        prior_closed=list(PRIOR_CLOSED),
        methods=list(WAVE11_TYPED_METHODS),
        confirmation=False,
        learning_to_learn_established=False,
        track_b_closed=True,
        grammar_prior_retrained=False,
        seeds=list(TRAIN_SEEDS),
        task_orders_by_seed={str(k): list(v) for k, v in TASK_ORDERS_BY_SEED.items()},
        typed_catalog=typed_catalog_manifest(),
        assessment=assessment,
        seed_blocks=seed_blocks,
        seed_dispersion=seed_dispersion,
        totals=totals,
        gates={},
        usage=dict(
            kind=KIND,
            elapsed_s=0.0,
            model_calls=0,
            metal_used=False,
            frozen_debit_s=0,
            research_cpu_ledger_debit_s=0,
            ledger_class="symbolic_standing_grant_cpu_not_frozen_1p5b",
            frozen_cpu_used_s=FROZEN_CPU_USED_S,
            frozen_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
            wall_time_s=0.0,
            rss=sample_process_memory(),
        ),
        language_hash=language_hash(),
    )
    payload["gates"] = evaluate_gates(payload)
    elapsed = time.perf_counter() - started
    payload["usage"]["elapsed_s"] = elapsed
    payload["usage"]["wall_time_s"] = elapsed
    payload["hash"] = digest(
        {key: payload[key] for key in ("kind", "assessment", "totals", "gates")}
    )
    (directory / "seed_wave11b_typed_program_enumerator.json").write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    return payload
