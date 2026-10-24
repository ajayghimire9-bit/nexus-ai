"""Wave-9 frozen-fresh comparison and self-adaptive evaluation runner.

Evaluates:
1. The 4 frozen ``bf66447`` methods from ``deconfounded_equal_capability.py``
   (verified untouched via SHA-256 digest):
   - ``equal_scratch``
   - ``ordinary_persistent_memoization``
   - ``persistent_nexus_pruning_disabled``
   - ``persistent_nexus_full``
2. The pre-registered Wave-9 self-adaptive learner from
   ``wave9_learned_abstraction_meta_control.py``:
   - ``wave9_self_adaptive_nexus``

All 5 methods are evaluated on a genuinely fresh 14-task holdout suite
(``w9f_*``, disjoint from ``OPENED_IDS`` and ``w8d_*``) across 3 distinct
permuted task arrival orderings (``210`` cells total = ``3 seeds x 5 methods x 14 tasks``).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .capability_evidence import digest
from .correspondence_env import PUBLIC_SLOTS, RecordWorld, integer_rows
from .cross_domain_analogy import SEQUENCE_MECHANISMS, Seq, as_seq
from .deconfounded_equal_capability import (
    EqualCapabilityLearner,
    execute_serialized_program_ast,
    universal_catalog_manifest,
)
from .hierarchical_gated_evolution import Wave8World
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_wave8_deconfounded import (
    L2_PUBLIC_MAP,
    OPENED_IDS as W8D_PRIOR_OPENED,
    WAVE8_DECONFOUNDED_TASKS,
)
from .mechanism_world import language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S
from .wave9_learned_abstraction_meta_control import (
    WAVE9_SELF_ADAPTIVE_METHOD,
    Wave9SelfAdaptiveLearner,
)

KIND = "seed_wave9_frozen_fresh_and_adaptive"
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
)
OPENED_IDS = set(W8D_PRIOR_OPENED) | {row["task_id"] for row in WAVE8_DECONFOUNDED_TASKS}

FROZEN_BF66447_METHODS: Tuple[str, ...] = (
    "equal_scratch",
    "ordinary_persistent_memoization",
    "persistent_nexus_pruning_disabled",
    "persistent_nexus_full",
)
WAVE9_COMPARISON_METHODS: Tuple[str, ...] = FROZEN_BF66447_METHODS + (
    WAVE9_SELF_ADAPTIVE_METHOD,
)

SPLIT_G1 = "w9f_g1_analogous"
SPLIT_G2 = "w9f_g2_lookalike"
SPLIT_L1 = "w9f_l1_invention_reuse"
SPLIT_L2 = "w9f_l2_composition_reuse"
SPLIT_DELAYED = "w9f_delayed_post_prune"
SPLIT_AMB = "w9f_ambiguous"
SPLIT_OOG = "w9f_oog"
SPLIT_RETAIN = "w9f_retain_domain_a"

# Register fresh holdout sequence mechanisms in SEQUENCE_MECHANISMS
def seq_len2_append_q(seq: Seq) -> Seq:
    return seq + ("q",) if len(seq) == 2 else seq


def seq_len0_append_hash(seq: Seq) -> Seq:
    return seq + ("#",) if len(seq) == 0 else seq


def seq_palindrome_z(seq: Seq) -> Seq:
    return seq + ("z",) if seq == seq[::-1] else seq


def seq_palindrome_m(seq: Seq) -> Seq:
    return seq + ("m",) if seq == seq[::-1] else seq


def seq_len_ge3_z(seq: Seq) -> Seq:
    return seq + ("z",) if len(seq) >= 3 else seq


def seq_len_ge3_hash(seq: Seq) -> Seq:
    return seq + ("#",) if len(seq) >= 3 else seq


def seq_pal_drop_head_bang(seq: Seq) -> Seq:
    if seq == seq[::-1]:
        return (seq[1:] + ("!",)) if len(seq) > 1 else seq + ("!",)
    return seq


def seq_pal_swap_bang(seq: Seq) -> Seq:
    if seq == seq[::-1]:
        return (
            (seq[-1:] + seq[1:-1] + seq[:1] + ("!",))
            if len(seq) > 1
            else seq + ("!",)
        )
    return seq


def seq_vowel_shift(seq: Seq) -> Seq:
    shifted = []
    for token in seq:
        if len(token) == 1 and "a" <= token <= "z":
            shifted.append(chr((ord(token) - 97 + 2) % 26 + 97))
        else:
            shifted.append(token)
    return tuple(shifted)


SEQUENCE_MECHANISMS["seq_len2_append_q"] = seq_len2_append_q
SEQUENCE_MECHANISMS["seq_len0_append_hash"] = seq_len0_append_hash
SEQUENCE_MECHANISMS["seq_palindrome_z"] = seq_palindrome_z
SEQUENCE_MECHANISMS["seq_palindrome_m"] = seq_palindrome_m
SEQUENCE_MECHANISMS["seq_len_ge3_z"] = seq_len_ge3_z
SEQUENCE_MECHANISMS["seq_len_ge3_hash"] = seq_len_ge3_hash
SEQUENCE_MECHANISMS["seq_pal_drop_head_bang"] = seq_pal_drop_head_bang
SEQUENCE_MECHANISMS["seq_pal_swap_bang"] = seq_pal_swap_bang
SEQUENCE_MECHANISMS["seq_vowel_shift"] = seq_vowel_shift

LEN_GE3_PUBLIC_MAP: Dict[str, Tuple[str, ...]] = {
    "alpha": (),
    "beta": ("a",),
    "gamma": ("a", "b", "c"),
    "delta": ("a", "b"),
}

WAVE9_FRESH_HOLDOUT_TASKS: Tuple[Dict[str, Any], ...] = (
    dict(
        task_id="w9f_g1_even_append",
        split=SPLIT_G1,
        domain="B",
        mechanism="seq_even_append",
        instance_seed=2401,
        gold_status="unique",
        gold_field="result",
        epsilon=("m", "n", "p", "q"),
        private={
            "alpha": ("d",),
            "beta": ("u", "v"),
            "gamma": (),
            "delta": ("a", "b", "c", "d"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w9f_g1_odd_dup",
        split=SPLIT_G1,
        domain="B",
        mechanism="seq_odd_dup",
        instance_seed=2402,
        gold_status="unique",
        gold_field="result",
        epsilon=("k", "l", "m"),
        private={
            "alpha": ("d",),
            "beta": ("u", "v"),
            "gamma": ("w",),
            "delta": ("a", "b", "c"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w9f_g2_len2_append_q",
        split=SPLIT_G2,
        domain="B",
        mechanism="seq_len2_append_q",
        instance_seed=2411,
        gold_status="unique",
        gold_field="result",
        epsilon=("p", "q", "r", "s"),
        private={
            "alpha": ("d",),
            "beta": ("u", "v"),
            "gamma": (),
            "delta": ("a", "b", "c", "d"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w9f_g2_len0_append_hash",
        split=SPLIT_G2,
        domain="B",
        mechanism="seq_len0_append_hash",
        instance_seed=2412,
        gold_status="unique",
        gold_field="result",
        epsilon=("p", "q", "r", "s"),
        private={
            "alpha": ("d",),
            "beta": ("u", "v"),
            "gamma": (),
            "delta": ("a", "b", "c", "d"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w9f_l1_inv_palindrome_z",
        split=SPLIT_L1,
        domain="B",
        mechanism="seq_palindrome_z",
        instance_seed=2421,
        gold_status="unique",
        gold_field="result",
        epsilon=("k", "o", "k"),
        private={
            "alpha": ("n", "n"),
            "beta": ("u", "v"),
            "gamma": (),
            "delta": ("c", "d", "c"),
        },
        record_mode="stamp_trap",
        public_map=L2_PUBLIC_MAP,
    ),
    dict(
        task_id="w9f_l1_reuse_palindrome_m",
        split=SPLIT_L1,
        domain="B",
        mechanism="seq_palindrome_m",
        instance_seed=2422,
        gold_status="unique",
        gold_field="result",
        epsilon=("c", "d", "c"),
        private={
            "alpha": ("n", "n"),
            "beta": ("u", "v"),
            "gamma": (),
            "delta": ("p", "q", "p"),
        },
        record_mode="stamp_trap",
        public_map=L2_PUBLIC_MAP,
    ),
    dict(
        task_id="w9f_l1_spurious_len_ge3_z",
        split=SPLIT_L1,
        domain="B",
        mechanism="seq_len_ge3_z",
        instance_seed=2423,
        gold_status="unique",
        gold_field="result",
        epsilon=("p", "q", "r", "s"),
        private={
            "alpha": ("a", "b", "c"),
            "beta": ("u", "v"),
            "gamma": (),
            "delta": ("k", "l", "m", "n"),
        },
        record_mode="stamp_trap",
        public_map=LEN_GE3_PUBLIC_MAP,
    ),
    dict(
        task_id="w9f_l2_inv_pal_drop_head_bang",
        split=SPLIT_L2,
        domain="B",
        mechanism="seq_pal_drop_head_bang",
        instance_seed=2431,
        gold_status="unique",
        gold_field="result",
        epsilon=("k", "o", "k"),
        private={
            "alpha": ("n", "n"),
            "beta": ("u", "v"),
            "gamma": ("r", "a", "r"),
            "delta": (),
        },
        record_mode="stamp_trap",
        public_map=L2_PUBLIC_MAP,
    ),
    dict(
        task_id="w9f_l2_reuse_full_drop_head_bang",
        split=SPLIT_L2,
        domain="B",
        mechanism="seq_pal_drop_head_bang",
        instance_seed=2432,
        gold_status="unique",
        gold_field="result",
        epsilon=("m", "n", "m"),
        private={
            "alpha": ("p", "q", "p"),
            "beta": ("u", "v"),
            "gamma": ("b",),
            "delta": ("c", "d", "c"),
        },
        record_mode="stamp_trap",
        public_map=L2_PUBLIC_MAP,
    ),
    dict(
        task_id="w9f_l2_compose_pal_swap_bang",
        split=SPLIT_L2,
        domain="B",
        mechanism="seq_pal_swap_bang",
        instance_seed=2433,
        gold_status="unique",
        gold_field="result",
        epsilon=("c", "d", "c"),
        private={
            "alpha": ("n", "n"),
            "beta": ("u", "v"),
            "gamma": ("r", "a", "r"),
            "delta": (),
        },
        record_mode="stamp_trap",
        public_map=L2_PUBLIC_MAP,
    ),
    dict(
        task_id="w9f_delayed_len_ge3_hash",
        split=SPLIT_DELAYED,
        domain="B",
        mechanism="seq_len_ge3_hash",
        instance_seed=2434,
        gold_status="unique",
        gold_field="result",
        epsilon=("w", "x", "y", "z"),
        private={
            "alpha": ("a", "b", "c", "d"),
            "beta": ("u", "v"),
            "gamma": (),
            "delta": ("m", "n", "p"),
        },
        record_mode="stamp_trap",
        public_map=LEN_GE3_PUBLIC_MAP,
    ),
    dict(
        task_id="w9f_amb_alias_odd",
        split=SPLIT_AMB,
        domain="B",
        mechanism="seq_odd_dup",
        instance_seed=2441,
        gold_status="ambiguous",
        gold_field="ambiguous",
        epsilon=("k", "l", "m"),
        private={
            "alpha": ("d",),
            "beta": ("u", "v"),
            "gamma": (),
            "delta": ("p", "q"),
        },
        record_mode="alias_ambiguous",
    ),
    dict(
        task_id="w9f_oog_vowel_shift",
        split=SPLIT_OOG,
        domain="B",
        mechanism="seq_vowel_shift",
        instance_seed=2442,
        gold_status="abstain",
        gold_field=None,
        epsilon=("m", "n", "p", "q"),
        private={
            "alpha": ("d",),
            "beta": ("u", "v"),
            "gamma": (),
            "delta": ("p", "q"),
        },
        record_mode="stamp_trap",
        unknown_kind="oog",
    ),
    dict(
        task_id="w9f_retain_domain_a_even3",
        split=SPLIT_RETAIN,
        domain="A",
        mechanism="w5_even_add3",
        instance_seed=2451,
        gold_status="unique",
        gold_field="result",
        record_mode="stamp_trap",
        retain_wave="wave5",
    ),
)

TASK_ORDERS_BY_SEED: Dict[int, Tuple[str, ...]] = {
    0: (
        "w9f_g1_even_append",
        "w9f_g1_odd_dup",
        "w9f_g2_len2_append_q",
        "w9f_g2_len0_append_hash",
        "w9f_l1_inv_palindrome_z",
        "w9f_l1_reuse_palindrome_m",
        "w9f_l1_spurious_len_ge3_z",
        "w9f_l2_inv_pal_drop_head_bang",
        "w9f_l2_reuse_full_drop_head_bang",
        "w9f_l2_compose_pal_swap_bang",
        "w9f_delayed_len_ge3_hash",
        "w9f_amb_alias_odd",
        "w9f_oog_vowel_shift",
        "w9f_retain_domain_a_even3",
    ),
    1: (
        "w9f_l1_inv_palindrome_z",
        "w9f_l1_reuse_palindrome_m",
        "w9f_l1_spurious_len_ge3_z",
        "w9f_delayed_len_ge3_hash",
        "w9f_l2_inv_pal_drop_head_bang",
        "w9f_l2_reuse_full_drop_head_bang",
        "w9f_l2_compose_pal_swap_bang",
        "w9f_g1_even_append",
        "w9f_g1_odd_dup",
        "w9f_g2_len2_append_q",
        "w9f_g2_len0_append_hash",
        "w9f_oog_vowel_shift",
        "w9f_amb_alias_odd",
        "w9f_retain_domain_a_even3",
    ),
    2: (
        "w9f_g2_len2_append_q",
        "w9f_g2_len0_append_hash",
        "w9f_l1_spurious_len_ge3_z",
        "w9f_l1_inv_palindrome_z",
        "w9f_g1_even_append",
        "w9f_g1_odd_dup",
        "w9f_l2_inv_pal_drop_head_bang",
        "w9f_l2_compose_pal_swap_bang",
        "w9f_l2_reuse_full_drop_head_bang",
        "w9f_l1_reuse_palindrome_m",
        "w9f_oog_vowel_shift",
        "w9f_delayed_len_ge3_hash",
        "w9f_amb_alias_odd",
        "w9f_retain_domain_a_even3",
    ),
}


def ordered_tasks_for_seed(seed: int) -> List[Dict[str, Any]]:
    by_id = {row["task_id"]: dict(row) for row in WAVE9_FRESH_HOLDOUT_TASKS}
    order = TASK_ORDERS_BY_SEED.get(seed, TASK_ORDERS_BY_SEED[0])
    return [by_id[tid] for tid in order]


def _build_world_for_task(task: Mapping[str, Any]) -> Any:
    if task["domain"] == "A":
        return RecordWorld(
            str(task["mechanism"]),
            int(task["instance_seed"]),
            str(task.get("record_mode") or "stamp_trap"),
        )
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
    pred_id = str(program_ast.get("predicate_id") or "")
    if task["mechanism"] in {"seq_len2_append_q", "seq_len0_append_hash"}:
        return pred_id == "len_even"
    return False


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
    if task["domain"] == "A":
        for slot in PUBLIC_SLOTS:
            rec = world.private_read(slot)
            trace.append(
                {"phase": "private", "kind": "private_eval", "slot": slot, "before_lock": False}
            )
            rows = integer_rows(
                [rec], dict(alpha=0, beta=1, gamma=2, delta=-1, output_field="result")
            )
            inp = int(rows[0]["x"])
            gt = int(rows[0]["observation"])
            pred = int(execute_serialized_program_ast(program_ast, inp))
            match = pred == gt
            if not match:
                all_ok = False
            private_evals.append(
                {
                    "slot": slot,
                    "input": inp,
                    "predicted_output": pred,
                    "ground_truth_output": gt,
                    "match": match,
                }
            )
        return all_ok, private_evals

    for slot in PUBLIC_SLOTS:
        rec = world.private_read(slot)
        trace.append(
            {"phase": "private", "kind": "private_eval", "slot": slot, "before_lock": False}
        )
        inp_seq = as_seq(rec["payload"])
        gt_seq = as_seq(rec["result"])
        pred_seq = as_seq(execute_serialized_program_ast(program_ast, inp_seq))
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


def _make_learner(method: str) -> Any:
    if method == WAVE9_SELF_ADAPTIVE_METHOD:
        return Wave9SelfAdaptiveLearner()
    return EqualCapabilityLearner(method)


def run_episode(
    task: Mapping[str, Any],
    learner: Any,
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

    archive_evals = int(getattr(report, "archive_lookup_evals", 0))
    comp_evals = int(getattr(report, "compression_evals", 0))
    cold_react = bool(getattr(report, "cold_archive_reactivated", False))
    cold_size = int(getattr(report, "cold_archive_size", 0))

    return dict(
        source_seed=seed,
        arrival_index=arrival_index,
        task_id=task["task_id"],
        split=task["split"],
        domain=task["domain"],
        mechanism=task["mechanism"],
        method=learner.method,
        is_frozen_bf66447=(learner.method in FROZEN_BF66447_METHODS),
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
        false_analogy_lock=_false_analogy_lock(task, report.program_ast, report.status),
        false_unique=bool(task.get("gold_status") == "ambiguous" and report.status == "unique"),
        private_before_lock=private_before_lock,
        locked=bool(world.locked),
        public_env_probes=int(report.public_env_probes),
        public_validation_probes=int(report.public_validation_probes),
        channel_invariance_evals=int(report.channel_invariance_evals),
        schema_distill_cost=int(report.schema_distill_cost),
        role_probe_cost=int(report.role_probe_cost),
        gate_evals=int(report.gate_evals),
        archive_lookup_evals=archive_evals,
        compression_evals=comp_evals,
        synthesis_evals=int(report.synthesis_evals),
        micro_codegen_evals=int(report.micro_codegen_evals),
        operator_compile_cost=int(report.operator_compile_cost),
        codegen_plus_synthesis=int(report.codegen_plus_synthesis),
        total_work=int(report.total_work),
        schema_distilled=bool(report.schema_distilled),
        used_operators=list(report.used_operators),
        invented_l1=list(report.invented_l1),
        invented_l2=list(report.invented_l2),
        l1_sub_predicate_reused=bool(report.l1_sub_predicate_reused),
        l2_full_skill_reused=bool(report.l2_full_skill_reused),
        memoized_program_reused=bool(report.memoized_program_reused),
        cold_archive_reactivated=cold_react,
        pruned_operators=list(report.pruned_operators),
        active_library_size=int(report.active_library_size),
        cold_archive_size=cold_size,
        catalog_audit=dict(report.catalog_audit),
        trace=trace,
    )


COST_KEYS: Tuple[str, ...] = (
    "public_env_probes",
    "public_validation_probes",
    "channel_invariance_evals",
    "schema_distill_cost",
    "role_probe_cost",
    "gate_evals",
    "archive_lookup_evals",
    "compression_evals",
    "synthesis_evals",
    "micro_codegen_evals",
    "operator_compile_cost",
)


def _totals(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for method in WAVE9_COMPARISON_METHODS:
        subset = [r for r in rows if r["method"] == method]
        out[method] = dict(
            n=len(subset),
            is_frozen_bf66447=(method in FROZEN_BF66447_METHODS),
            mapping_correct=sum(int(bool(r.get("mapping_correct"))) for r in subset),
            private_correct=sum(int(bool(r.get("private_correct"))) for r in subset),
            false_analogy_lock=sum(int(bool(r.get("false_analogy_lock"))) for r in subset),
            false_unique=sum(int(bool(r.get("false_unique"))) for r in subset),
            ambiguous=sum(int(r.get("status") == "ambiguous") for r in subset),
            abstain=sum(int(r.get("status") == "abstain") for r in subset),
            schema_distill_cost=sum(int(r.get("schema_distill_cost") or 0) for r in subset),
            role_probe_cost=sum(int(r.get("role_probe_cost") or 0) for r in subset),
            gate_evals=sum(int(r.get("gate_evals") or 0) for r in subset),
            archive_lookup_evals=sum(
                int(r.get("archive_lookup_evals") or 0) for r in subset
            ),
            compression_evals=sum(int(r.get("compression_evals") or 0) for r in subset),
            synthesis_evals=sum(int(r.get("synthesis_evals") or 0) for r in subset),
            micro_codegen_evals=sum(int(r.get("micro_codegen_evals") or 0) for r in subset),
            operator_compile_cost=sum(int(r.get("operator_compile_cost") or 0) for r in subset),
            codegen_plus_synthesis=sum(int(r.get("codegen_plus_synthesis") or 0) for r in subset),
            total_work=sum(int(r.get("total_work") or 0) for r in subset),
            l1_sub_predicate_reused=sum(
                int(bool(r.get("l1_sub_predicate_reused"))) for r in subset
            ),
            l2_full_skill_reused=sum(int(bool(r.get("l2_full_skill_reused"))) for r in subset),
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
    for method in WAVE9_COMPARISON_METHODS:
        work_vals = [int(b[group_key][method]["total_work"]) for b in seed_blocks]
        code_vals = [int(b[group_key][method]["codegen_plus_synthesis"]) for b in seed_blocks]
        priv_vals = [int(b[group_key][method]["private_correct"]) for b in seed_blocks]
        summary[method] = dict(
            private_correct_per_seed=priv_vals,
            total_work_mean=round(sum(work_vals) / max(len(work_vals), 1), 2),
            total_work_min=min(work_vals),
            total_work_max=max(work_vals),
            codegen_plus_synthesis_mean=round(sum(code_vals) / max(len(code_vals), 1), 2),
            codegen_plus_synthesis_min=min(code_vals),
            codegen_plus_synthesis_max=max(code_vals),
        )
    return summary


def evaluate_gates(payload: Mapping[str, Any]) -> Dict[str, Any]:
    notes: List[str] = []
    ok = True
    rows = list(payload.get("assessment") or [])

    if any(r.get("private_before_lock") for r in rows):
        ok = False
        notes.append("private_before_lock")
    if any(r.get("false_analogy_lock") for r in rows):
        ok = False
        notes.append("false_analogy_lock")
    if any(not r.get("mapping_correct") or not r.get("private_correct") for r in rows):
        ok = False
        notes.append("solve_mismatch")

    for m in (
        "persistent_nexus_pruning_disabled",
        "persistent_nexus_full",
        WAVE9_SELF_ADAPTIVE_METHOD,
    ):
        m_schema = sum(
            int(r.get("schema_distill_cost") or 0) for r in rows if r["method"] == m
        )
        if m_schema <= 0:
            ok = False
            notes.append(f"missing_schema_cost:{m}")

    # Verify cold archive reactivation occurs on delayed reuse tasks for wave9_self_adaptive_nexus
    w9_rows = [r for r in rows if r["method"] == WAVE9_SELF_ADAPTIVE_METHOD]
    if not any(r.get("cold_archive_reactivated") for r in w9_rows):
        ok = False
        notes.append("no_cold_archive_reactivation")

    return dict(
        gate1_isolation_and_safety=all(
            t not in notes for t in ("private_before_lock", "false_analogy_lock", "solve_mismatch")
        ),
        gate2_honest_schema_cost=not any(n.startswith("missing_schema_cost") for n in notes),
        gate3_cold_archive_reactivation="no_cold_archive_reactivation" not in notes,
        passed=ok,
        notes=notes,
    )


def run_wave9_frozen_fresh(directory: Path) -> Dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    if any(row["task_id"] in OPENED_IDS for row in WAVE9_FRESH_HOLDOUT_TASKS):
        raise ValueError("opened_id_in_challenge")

    assessment: List[Dict[str, Any]] = []
    seed_blocks: List[Dict[str, Any]] = []

    for seed in TRAIN_SEEDS:
        ordered_tasks = ordered_tasks_for_seed(seed)
        seed_rows: List[Dict[str, Any]] = []
        for method in WAVE9_COMPARISON_METHODS:
            learner = _make_learner(method)
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
                g12=_totals([r for r in seed_rows if r["split"] in {SPLIT_G1, SPLIT_G2}]),
                l1=_totals([r for r in seed_rows if r["split"] == SPLIT_L1]),
                l2=_totals([r for r in seed_rows if r["split"] == SPLIT_L2]),
                l12=_totals([r for r in seed_rows if r["split"] in {SPLIT_L1, SPLIT_L2}]),
                delayed=_totals([r for r in seed_rows if r["split"] == SPLIT_DELAYED]),
                amb=_totals([r for r in seed_rows if r["split"] == SPLIT_AMB]),
                oog=_totals([r for r in seed_rows if r["split"] == SPLIT_OOG]),
                retain=_totals([r for r in seed_rows if r["split"] == SPLIT_RETAIN]),
                suite=_totals(seed_rows),
            )
        )

    totals = dict(
        g1=_totals([r for r in assessment if r["split"] == SPLIT_G1]),
        g2=_totals([r for r in assessment if r["split"] == SPLIT_G2]),
        g12=_totals([r for r in assessment if r["split"] in {SPLIT_G1, SPLIT_G2}]),
        l1=_totals([r for r in assessment if r["split"] == SPLIT_L1]),
        l2=_totals([r for r in assessment if r["split"] == SPLIT_L2]),
        l12=_totals([r for r in assessment if r["split"] in {SPLIT_L1, SPLIT_L2}]),
        delayed=_totals([r for r in assessment if r["split"] == SPLIT_DELAYED]),
        amb=_totals([r for r in assessment if r["split"] == SPLIT_AMB]),
        oog=_totals([r for r in assessment if r["split"] == SPLIT_OOG]),
        retain=_totals([r for r in assessment if r["split"] == SPLIT_RETAIN]),
        suite=_totals(assessment),
    )

    seed_dispersion = {
        group_key: _seed_dispersion(seed_blocks, group_key)
        for group_key in (
            "g1",
            "g2",
            "g12",
            "l1",
            "l2",
            "l12",
            "delayed",
            "amb",
            "oog",
            "retain",
            "suite",
        )
    }

    payload: Dict[str, Any] = dict(
        kind=KIND,
        prior_closed=list(PRIOR_CLOSED),
        frozen_bf66447_commit="bf66447",
        frozen_bf66447_methods=list(FROZEN_BF66447_METHODS),
        methods=list(WAVE9_COMPARISON_METHODS),
        confirmation=False,
        learning_to_learn_established=False,
        track_b_closed=True,
        grammar_prior_retrained=False,
        seeds=list(TRAIN_SEEDS),
        task_orders_by_seed={str(k): list(v) for k, v in TASK_ORDERS_BY_SEED.items()},
        universal_catalog={
            k: list(v) for k, v in universal_catalog_manifest().items()
        },
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
    (directory / "seed_wave9_frozen_fresh_and_adaptive.json").write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    return payload
