"""Wave-8 deconfounded equal-capability runner and independent evaluator.

Addresses all 4 confounds identified in commit ``4cac886``:
1. Strictly label-blind learner interface: the runner passes ONLY
   ``(world, public_budget)`` to ``learner.solve_unfamiliar_task(world, 10)``.
   Task metadata (``task_id``, ``split``, ``gold_status``, ``private``) remains
   exclusively in the evaluator for post-lock private scoring and reporting.
2. Identical primitive & extension catalogs + full L2 composition depth across
   all 6 methods on every task.
3. Honest cost accounting (``schema_distill_cost > 0`` in raw rows when schemas
   are distilled, metered ``synthesis_evals`` and ``micro_codegen_evals``,
   ``usage_age_prune`` heuristic naming) and explicit separation of
   ``l1_sub_predicate_reused`` vs ``l2_full_skill_reused``.
4. Permuted task arrival orders across seeds ``(0, 1, 2)`` (reporting
   ``mean / min / max`` across seeds) plus a ``delayed_reuse`` task that arrives
   after ``usage_age_prune`` drops a once-used operator in Seeds 0 and 2.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .capability_evidence import digest
from .correspondence_env import PUBLIC_SLOTS, RecordWorld, integer_rows
from .cross_domain_analogy import as_seq
from .deconfounded_equal_capability import (
    EQUAL_CAPABILITY_METHODS,
    EqualCapabilityLearner,
    execute_serialized_program_ast,
    universal_catalog_manifest,
)
from .hierarchical_gated_evolution import Wave8World
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_wave8_hierarchical import OPENED_IDS as W8_PRIOR_OPENED, WAVE8_TASKS
from .mechanism_world import language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_wave8_deconfounded_equal_capability"
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
)
OPENED_IDS = set(W8_PRIOR_OPENED) | {row["task_id"] for row in WAVE8_TASKS}

SPLIT_G1 = "w8d_g1_analogous"
SPLIT_G2 = "w8d_g2_lookalike"
SPLIT_L1 = "w8d_l1_invention_reuse"
SPLIT_L2 = "w8d_l2_composition_reuse"
SPLIT_DELAYED = "w8d_delayed_post_prune"
SPLIT_AMB = "w8d_ambiguous"
SPLIT_OOG = "w8d_oog"
SPLIT_RETAIN = "w8d_retain_domain_a"

# Public observation maps that make L1 first_eq_last and L2 palindrome+rotate
# identifiable from public input/output pairs alone (with ZERO stage labels):
# - L2_PUBLIC includes both a multi-token palindrome ("r", "a", "r") and a
#   non-palindrome ("a", "b") so palindrome_pred partitions changed vs unchanged
#   and rotate_bang_tf / rotate_q_tf are uniquely identified.
# - FIRST_LAST_PUBLIC includes empty tuple () (unchanged under first_eq_last,
#   changed under palindrome_pred) plus ("a", "b", "a") and ("a", "b").
L2_PUBLIC_MAP: Dict[str, Tuple[str, ...]] = {
    "alpha": (),
    "beta": ("a",),
    "gamma": ("r", "a", "r"),
    "delta": ("a", "b"),
}
FIRST_LAST_PUBLIC_MAP: Dict[str, Tuple[str, ...]] = {
    "alpha": (),
    "beta": ("a",),
    "gamma": ("a", "b", "a"),
    "delta": ("a", "b"),
}

WAVE8_DECONFOUNDED_TASKS: Tuple[Dict[str, Any], ...] = (
    dict(
        task_id="w8d_g1_even_append",
        split=SPLIT_G1,
        domain="B",
        mechanism="seq_even_append",
        instance_seed=1401,
        gold_status="unique",
        gold_field="result",
        epsilon=("w", "x", "y", "z"),
        private={
            "alpha": ("c",),
            "beta": ("x", "y"),
            "gamma": (),
            "delta": ("p", "q", "r", "s"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w8d_g1_odd_dup",
        split=SPLIT_G1,
        domain="B",
        mechanism="seq_odd_dup",
        instance_seed=1402,
        gold_status="unique",
        gold_field="result",
        epsilon=("x", "y", "z"),
        private={
            "alpha": ("c",),
            "beta": ("x", "y"),
            "gamma": ("q",),
            "delta": ("p", "q", "r"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w8d_g2_len02_append",
        split=SPLIT_G2,
        domain="B",
        mechanism="seq_len02_append",
        instance_seed=1411,
        gold_status="unique",
        gold_field="result",
        epsilon=("w", "x", "y", "z"),
        private={
            "alpha": ("c",),
            "beta": ("x", "y"),
            "gamma": (),
            "delta": ("p", "q", "r", "s"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w8d_g2_len1_dup",
        split=SPLIT_G2,
        domain="B",
        mechanism="seq_len1_dup",
        instance_seed=1412,
        gold_status="unique",
        gold_field="result",
        epsilon=("x", "y", "z"),
        private={
            "alpha": ("c",),
            "beta": ("x", "y"),
            "gamma": ("q",),
            "delta": ("p", "q", "r"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w8d_l1_inv_palindrome_hash",
        split=SPLIT_L1,
        domain="B",
        mechanism="seq_palindrome_hash",
        instance_seed=1421,
        gold_status="unique",
        gold_field="result",
        epsilon=("x", "y", "z"),
        private={
            "alpha": ("x", "x"),
            "beta": ("x", "y"),
            "gamma": (),
            "delta": ("a", "b", "a"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w8d_l1_reuse_palindrome_q",
        split=SPLIT_L1,
        domain="B",
        mechanism="seq_palindrome_q",
        instance_seed=1422,
        gold_status="unique",
        gold_field="result",
        epsilon=("r", "a", "r"),
        private={
            "alpha": ("x", "x"),
            "beta": ("x", "y"),
            "gamma": (),
            "delta": ("a", "b", "a"),
        },
        record_mode="stamp_trap",
    ),
    dict(
        task_id="w8d_l1_spurious_first_last_z",
        split=SPLIT_L1,
        domain="B",
        mechanism="seq_first_last_z",
        instance_seed=1423,
        gold_status="unique",
        gold_field="result",
        epsilon=("x", "y", "z"),
        private={
            "alpha": ("x", "x"),
            "beta": ("x", "y"),
            "gamma": ("z",),
            "delta": ("a", "b", "a"),
        },
        record_mode="stamp_trap",
        public_map=FIRST_LAST_PUBLIC_MAP,
    ),
    dict(
        task_id="w8d_l2_inv_pal_rotate_bang",
        split=SPLIT_L2,
        domain="B",
        mechanism="seq_pal_rotate_bang",
        instance_seed=1431,
        gold_status="unique",
        gold_field="result",
        epsilon=("x", "y", "z"),
        private={
            "alpha": ("x", "x"),
            "beta": ("x", "y"),
            "gamma": ("r", "a", "r"),
            "delta": (),
        },
        record_mode="stamp_trap",
        public_map=L2_PUBLIC_MAP,
    ),
    dict(
        task_id="w8d_l2_reuse_full_rotate_bang",
        split=SPLIT_L2,
        domain="B",
        mechanism="seq_pal_rotate_bang",
        instance_seed=1432,
        gold_status="unique",
        gold_field="result",
        epsilon=("m", "n", "p"),
        private={
            "alpha": ("k", "o", "k"),
            "beta": ("m", "n"),
            "gamma": ("b",),
            "delta": ("p", "q", "p"),
        },
        record_mode="stamp_trap",
        public_map=L2_PUBLIC_MAP,
    ),
    dict(
        task_id="w8d_l2_compose_pal_rotate_q",
        split=SPLIT_L2,
        domain="B",
        mechanism="seq_pal_rotate_q",
        instance_seed=1433,
        gold_status="unique",
        gold_field="result",
        epsilon=("x", "y", "z"),
        private={
            "alpha": ("x", "x"),
            "beta": ("x", "y"),
            "gamma": ("r", "a", "r"),
            "delta": (),
        },
        record_mode="stamp_trap",
        public_map=L2_PUBLIC_MAP,
    ),
    dict(
        task_id="w8d_delayed_first_last_hash",
        split=SPLIT_DELAYED,
        domain="B",
        mechanism="seq_first_last_hash",
        instance_seed=1434,
        gold_status="unique",
        gold_field="result",
        epsilon=("x", "y", "z"),
        private={
            "alpha": ("m", "m"),
            "beta": ("x", "y"),
            "gamma": (),
            "delta": ("c", "d", "c"),
        },
        record_mode="stamp_trap",
        public_map=FIRST_LAST_PUBLIC_MAP,
    ),
    dict(
        task_id="w8d_amb_alias",
        split=SPLIT_AMB,
        domain="B",
        mechanism="seq_even_append",
        instance_seed=1441,
        gold_status="ambiguous",
        gold_field="ambiguous",
        epsilon=("w", "x", "y", "z"),
        private={
            "alpha": ("c",),
            "beta": ("x", "y"),
            "gamma": (),
            "delta": ("p", "q"),
        },
        record_mode="alias_ambiguous",
    ),
    dict(
        task_id="w8d_oog_caesar",
        split=SPLIT_OOG,
        domain="B",
        mechanism="seq_caesar",
        instance_seed=1442,
        gold_status="abstain",
        gold_field=None,
        epsilon=("w", "x", "y", "z"),
        private={
            "alpha": ("c",),
            "beta": ("x", "y"),
            "gamma": (),
            "delta": ("p", "q"),
        },
        record_mode="stamp_trap",
        unknown_kind="oog",
    ),
    dict(
        task_id="w8d_retain_domain_a_even",
        split=SPLIT_RETAIN,
        domain="A",
        mechanism="oob_even_add2",
        instance_seed=1451,
        gold_status="unique",
        gold_field="result",
        record_mode="stamp_trap",
        retain_wave="wave2",
    ),
)

# Distinct task arrival orders per seed to measure sensitivity to curriculum order
# and delayed reuse before vs after usage_age_prune.
TASK_ORDERS_BY_SEED: Dict[int, Tuple[str, ...]] = {
    0: (
        "w8d_g1_even_append",
        "w8d_g1_odd_dup",
        "w8d_g2_len02_append",
        "w8d_g2_len1_dup",
        "w8d_l1_inv_palindrome_hash",
        "w8d_l1_reuse_palindrome_q",
        "w8d_l1_spurious_first_last_z",
        "w8d_l2_inv_pal_rotate_bang",
        "w8d_l2_reuse_full_rotate_bang",
        "w8d_l2_compose_pal_rotate_q",
        "w8d_delayed_first_last_hash",
        "w8d_amb_alias",
        "w8d_oog_caesar",
        "w8d_retain_domain_a_even",
    ),
    1: (
        "w8d_l1_inv_palindrome_hash",
        "w8d_l1_reuse_palindrome_q",
        "w8d_l1_spurious_first_last_z",
        "w8d_delayed_first_last_hash",
        "w8d_l2_inv_pal_rotate_bang",
        "w8d_l2_reuse_full_rotate_bang",
        "w8d_l2_compose_pal_rotate_q",
        "w8d_g1_even_append",
        "w8d_g1_odd_dup",
        "w8d_g2_len02_append",
        "w8d_g2_len1_dup",
        "w8d_oog_caesar",
        "w8d_amb_alias",
        "w8d_retain_domain_a_even",
    ),
    2: (
        "w8d_g2_len02_append",
        "w8d_g2_len1_dup",
        "w8d_l1_spurious_first_last_z",
        "w8d_l1_inv_palindrome_hash",
        "w8d_g1_even_append",
        "w8d_g1_odd_dup",
        "w8d_l2_inv_pal_rotate_bang",
        "w8d_l2_compose_pal_rotate_q",
        "w8d_l2_reuse_full_rotate_bang",
        "w8d_l1_reuse_palindrome_q",
        "w8d_oog_caesar",
        "w8d_delayed_first_last_hash",
        "w8d_amb_alias",
        "w8d_retain_domain_a_even",
    ),
}


def ordered_tasks_for_seed(seed: int) -> List[Dict[str, Any]]:
    by_id = {row["task_id"]: dict(row) for row in WAVE8_DECONFOUNDED_TASKS}
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
    if task["mechanism"] == "seq_len02_append":
        return pred_id == "len_even"
    if task["mechanism"] == "seq_len1_dup":
        return pred_id == "len_odd"
    return False


def _evaluate_private_post_lock(
    task: Mapping[str, Any],
    status: str,
    program_ast: Mapping[str, Any],
    world: Any,
    trace: List[Dict[str, Any]],
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Lock ``world`` and evaluate ``program_ast`` on private test inputs."""
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


def run_episode(
    task: Mapping[str, Any],
    learner: EqualCapabilityLearner,
    arrival_index: int,
    seed: int,
) -> Dict[str, Any]:
    """Run one task episode by passing ONLY ``(world, 10)`` to the learner."""
    world = _build_world_for_task(task)

    # STRICT LABEL-BLIND CALL: learner receives ONLY (world, public_budget)
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
        pruned_operators=list(report.pruned_operators),
        active_library_size=int(report.active_library_size),
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
    "synthesis_evals",
    "micro_codegen_evals",
    "operator_compile_cost",
)


def _totals(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for method in EQUAL_CAPABILITY_METHODS:
        subset = [r for r in rows if r["method"] == method]
        out[method] = dict(
            n=len(subset),
            mapping_correct=sum(int(bool(r.get("mapping_correct"))) for r in subset),
            private_correct=sum(int(bool(r.get("private_correct"))) for r in subset),
            false_analogy_lock=sum(int(bool(r.get("false_analogy_lock"))) for r in subset),
            false_unique=sum(int(bool(r.get("false_unique"))) for r in subset),
            ambiguous=sum(int(r.get("status") == "ambiguous") for r in subset),
            abstain=sum(int(r.get("status") == "abstain") for r in subset),
            schema_distill_cost=sum(int(r.get("schema_distill_cost") or 0) for r in subset),
            role_probe_cost=sum(int(r.get("role_probe_cost") or 0) for r in subset),
            gate_evals=sum(int(r.get("gate_evals") or 0) for r in subset),
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
        )
    return out


def _seed_dispersion(seed_blocks: Sequence[Mapping[str, Any]], group_key: str) -> Dict[str, Any]:
    """Compute mean / min / max across seeds (0, 1, 2) for each method."""
    summary: Dict[str, Any] = {}
    for method in EQUAL_CAPABILITY_METHODS:
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

    # Gate 1: Zero private-before-lock, zero false analogy locks, 100% equal-capability solve rate
    if any(r.get("private_before_lock") for r in rows):
        ok = False
        notes.append("private_before_lock")
    if any(r.get("false_analogy_lock") for r in rows):
        ok = False
        notes.append("false_analogy_lock")
    if any(not r.get("mapping_correct") or not r.get("private_correct") for r in rows):
        ok = False
        notes.append("equal_capability_solve_mismatch")

    # Gate 2: Honest schema distillation cost (> 0 for all schema-using methods)
    schema_methods = (
        "persistent_nexus_hierarchy_disabled",
        "persistent_nexus_gate_disabled",
        "persistent_nexus_pruning_disabled",
        "persistent_nexus_full",
    )
    for m in schema_methods:
        m_schema = sum(int(r.get("schema_distill_cost") or 0) for r in rows if r["method"] == m)
        if m_schema <= 0:
            ok = False
            notes.append(f"missing_schema_cost:{m}")

    # Gate 3: Both L1 sub-predicate reuse and complete L2 skill reuse occur in persistent_nexus_full
    nexus_rows = [r for r in rows if r["method"] == "persistent_nexus_full"]
    if not any(r.get("l1_sub_predicate_reused") for r in nexus_rows):
        ok = False
        notes.append("no_l1_sub_predicate_reuse")
    if not any(r.get("l2_full_skill_reused") for r in nexus_rows):
        ok = False
        notes.append("no_l2_full_skill_reuse")

    # Gate 4: Prerequisite gate reduces OOG search cost vs gate_disabled on every seed
    for seed in TRAIN_SEEDS:
        oog_rows = [
            r for r in rows if int(r["source_seed"]) == seed and r["split"] == SPLIT_OOG
        ]
        full_oog = sum(
            int(r["total_work"]) for r in oog_rows if r["method"] == "persistent_nexus_full"
        )
        ungated_oog = sum(
            int(r["total_work"])
            for r in oog_rows
            if r["method"] == "persistent_nexus_gate_disabled"
        )
        if full_oog >= ungated_oog:
            ok = False
            notes.append(f"oog_gate_not_cheaper:{seed}")

    # Gate 5: Hierarchy reduces L1+L2 search cost vs equal_scratch, ordinary_memoization, and hierarchy_disabled
    for compare_m in (
        "equal_scratch",
        "ordinary_persistent_memoization",
        "persistent_nexus_hierarchy_disabled",
    ):
        l12_full = sum(
            int(r["codegen_plus_synthesis"])
            for r in rows
            if r["method"] == "persistent_nexus_full" and r["split"] in {SPLIT_L1, SPLIT_L2}
        )
        l12_other = sum(
            int(r["codegen_plus_synthesis"])
            for r in rows
            if r["method"] == compare_m and r["split"] in {SPLIT_L1, SPLIT_L2}
        )
        if l12_full >= l12_other:
            ok = False
            notes.append(f"hierarchy_l12_not_cheaper:{compare_m}")

    # Gate 6: Delayed reuse after pruning shows genuine tradeoff (pruning_disabled < full on Seed 0 delayed task)
    seed0_delayed = [
        r for r in rows if int(r["source_seed"]) == 0 and r["split"] == SPLIT_DELAYED
    ]
    full_delayed_s0 = sum(
        int(r["codegen_plus_synthesis"])
        for r in seed0_delayed
        if r["method"] == "persistent_nexus_full"
    )
    noprune_delayed_s0 = sum(
        int(r["codegen_plus_synthesis"])
        for r in seed0_delayed
        if r["method"] == "persistent_nexus_pruning_disabled"
    )
    if noprune_delayed_s0 >= full_delayed_s0:
        ok = False
        notes.append("delayed_post_prune_tradeoff_missing_seed0")

    return dict(
        gate1_equal_capability_and_safety=all(
            t not in notes
            for t in (
                "private_before_lock",
                "false_analogy_lock",
                "equal_capability_solve_mismatch",
            )
        ),
        gate2_honest_schema_cost=not any(n.startswith("missing_schema_cost") for n in notes),
        gate3_l1_and_full_l2_reuse=(
            "no_l1_sub_predicate_reuse" not in notes and "no_l2_full_skill_reuse" not in notes
        ),
        gate4_oog_prerequisite_gate=not any(n.startswith("oog_gate_not_cheaper") for n in notes),
        gate5_hierarchical_l12_advantage=not any(
            n.startswith("hierarchy_l12_not_cheaper") for n in notes
        ),
        gate6_honest_pruning_tradeoff="delayed_post_prune_tradeoff_missing_seed0" not in notes,
        passed=ok,
        notes=notes,
    )


def run_wave8_deconfounded(directory: Path) -> Dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    if any(row["task_id"] in OPENED_IDS for row in WAVE8_DECONFOUNDED_TASKS):
        raise ValueError("opened_id_in_challenge")

    assessment: List[Dict[str, Any]] = []
    seed_blocks: List[Dict[str, Any]] = []

    for seed in TRAIN_SEEDS:
        ordered_tasks = ordered_tasks_for_seed(seed)
        seed_rows: List[Dict[str, Any]] = []
        for method in EQUAL_CAPABILITY_METHODS:
            learner = EqualCapabilityLearner(method)
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
        deconfounds_commit="4cac886",
        confirmation=False,
        learning_to_learn_established=False,
        track_b_closed=True,
        grammar_prior_retrained=False,
        methods=list(EQUAL_CAPABILITY_METHODS),
        seeds=list(TRAIN_SEEDS),
        task_orders_by_seed={str(k): list(v) for k, v in TASK_ORDERS_BY_SEED.items()},
        universal_catalog= {
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
    (directory / "seed_wave8_deconfounded_equal_capability.json").write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    return payload
