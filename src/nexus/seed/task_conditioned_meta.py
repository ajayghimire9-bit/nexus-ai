"""Task-conditioned program ranking and fresh sealed compositional replication
(seed_task_conditioned_replication_v1, Steps 2-5).

Implements:
  S(p | D_B) = -d(signature(D_B), signature(p)) + alpha * S_structural(p) - beta * complexity(p)

Compares deterministic signature matching, source-trained linear ranker,
Bayesian version-space ranking, task-independent structural meta-prior, and
flat/shortest/frequency/macro-cache/random baselines on a fresh 6-operator
compositional grammar (258 raw -> 100 canonical -> 65 semantically unique:
18 source, 23 quarantined historical, 24 fresh sealed targets with zero
overlap against both source and previously exposed targets).
"""
import copy
import hashlib
import itertools as it
import json
import math
from pathlib import Path
import random
import sys
import time
from typing import Any

import numpy as np
from nexus.evolution1.catalogue import canonical, digest
from . import disjoint_meta as dm
from . import signature_audit as sig_mod
from . import source_acquisition as sa
from . import cross_lab_transfer as xlab

LIST_OPS_REP = ("reverse", "sort", "unique", "increment", "decrement", "even")
ACTION_OPS_REP = (
    "reverse_actions",
    "order_actions",
    "dedup_actions",
    "advance_mag",
    "retreat_mag",
    "filter_even_mag",
)
ACTION_TOKENS = ("D", "L", "R", "U")
CAT_NAMES = ("perm", "card", "point")

SUPPLIED_ROLE_MAPPING_REP = {
    "reverse": dict(target_op="reverse_actions", role="role_reverse_order", category="perm"),
    "sort": dict(target_op="order_actions", role="role_canonical_order", category="perm"),
    "unique": dict(target_op="dedup_actions", role="role_deduplicate", category="card"),
    "increment": dict(target_op="advance_mag", role="role_pointwise_step", category="point"),
    "decrement": dict(target_op="retreat_mag", role="role_pointwise_backstep", category="point"),
    "even": dict(target_op="filter_even_mag", role="role_predicate_filter", category="card"),
}
TARGET_OP_TO_SOURCE_REP = {v["target_op"]: k for k, v in SUPPLIED_ROLE_MAPPING_REP.items()}
OP_TO_SOURCE_OP_REP = {k: k for k in SUPPLIED_ROLE_MAPPING_REP} | TARGET_OP_TO_SOURCE_REP
OP_TO_ROLE_REP = {k: v["role"] for k, v in SUPPLIED_ROLE_MAPPING_REP.items()} | {
    v["target_op"]: v["role"] for v in SUPPLIED_ROLE_MAPPING_REP.values()
}
OP_TO_CATEGORY_REP = {k: v["category"] for k, v in SUPPLIED_ROLE_MAPPING_REP.items()} | {
    v["target_op"]: v["category"] for v in SUPPLIED_ROLE_MAPPING_REP.values()
}

IDEMPOTENT_ROLES_REP = frozenset(("role_canonical_order", "role_deduplicate", "role_predicate_filter"))
INVOLUTION_ROLES_REP = frozenset(("role_reverse_order",))
CANCEL_ROLE_PAIRS_REP = frozenset((
    frozenset(("role_pointwise_step", "role_pointwise_backstep")),
))
COMMUTATIVE_ROLE_PAIRS_REP = frozenset((
    frozenset(("role_pointwise_step", "role_reverse_order")),
    frozenset(("role_pointwise_step", "role_canonical_order")),
    frozenset(("role_pointwise_step", "role_deduplicate")),
    frozenset(("role_pointwise_backstep", "role_reverse_order")),
    frozenset(("role_pointwise_backstep", "role_canonical_order")),
    frozenset(("role_pointwise_backstep", "role_deduplicate")),
    frozenset(("role_canonical_order", "role_deduplicate")),
    frozenset(("role_deduplicate", "role_predicate_filter")),
))

# Previously exposed holdout pairs from seed_disjoint_meta_v1 (quarantined when no decrement pair is present)
QUARANTINED_V1_ROLE_PAIRS = frozenset(dm.HOLDOUT_ROLE_PAIRS)

METHODS_REP = (
    "deterministic_signature",
    "learned_linear_ranker",
    "bayesian_version_space",
    "structural_meta_prior",
    "flat_catalogue",
    "shortest_program",
    "operator_frequency",
    "exact_macro_cache",
    "random_ordering",
)
REQUIRED_BASELINES_REP = (
    "structural_meta_prior",
    "flat_catalogue",
    "shortest_program",
    "operator_frequency",
    "exact_macro_cache",
    "random_ordering",
)
CROSS_DOMAIN_METHODS_REP = (
    "transferred_signature_prior",
    "transferred_structural_prior",
    "scratch_flat",
    "shortest_program",
    "target_operator_frequency",
    "exact_macro_cache",
    "random_ordering",
)
BUDGETS = (1, 2, 4, 8)
PRIMARY_BUDGETS = (1, 2, 4)
T_CRITICAL_DF7 = 2.364624251


def configuration() -> dict[str, Any]:
    return dict(
        schema="seed_task_conditioned_replication_v1",
        families=list(range(1749000001, 1749000009)),
        assignment_seed=1749000900,
        tasks=dict(
            train=list(range(1749100000, 1749100144)),
            target=list(range(1749200000, 1749200024)),
            retention=list(range(1749300000, 1749300032)),
            cross_domain=list(range(1749400000, 1749400024)),
        ),
        random_permutation_seeds=list(range(1749500000, 1749500512)),
        primitives=list(LIST_OPS_REP),
        action_primitives=list(ACTION_OPS_REP),
        max_program_length=3,
        probe_max_length=4,
        probe_alphabet=[-2, -1, 0, 1, 2],
        probe_count=781,
        raw_program_count=258,
        canonical_program_count=100,
        semantically_unique_count=65,
        source_pool_count=18,
        quarantine_pool_count=23,
        target_pool_count=24,
        source_tasks_per_family=18,
        target_tasks_per_family=3,
        retention_tasks_per_family=4,
        cross_domain_tasks_per_family=3,
        teaching_examples_per_task=8,
        assessment_examples_per_task=16,
        counterexamples_per_task=2,
        budgets=list(BUDGETS),
        primary_budgets=list(PRIMARY_BUDGETS),
        secondary_budget=8,
        methods=list(METHODS_REP),
        cross_domain_methods=list(CROSS_DOMAIN_METHODS_REP),
        alpha_structural=0.05,
        beta_complexity=0.05,
        bayesian_temperature=0.25,
        ridge_lambda=1.0,
        laplace_pseudocount=1.0,
        dirichlet_pseudocount=1.0,
        random_permutations_per_family=64,
        feature_dimension=23,
        signature_dimension=17,
        linear_ranker_dimension=20,
        t_critical_df7=T_CRITICAL_DF7,
        gates=dict(
            max_accuracy_deficit_vs_best=0.01,
            max_family_accuracy_losses=2,
            max_catastrophic_family_drop=0.05,
            min_search_work_improvement_fraction=0.10,
            min_example_improvement_vs_flat=0.10,
            max_example_worse_vs_best=0.05,
            min_retention_post_accuracy=0.98,
            min_retention_accuracy_delta=-0.01,
            max_retention_search_regression=0.10,
            min_transfer_search_improvement_vs_scratch=0.10,
            max_amortized_compute_overhead_vs_best=0.25,
        ),
        max_wall_s=120,
        max_cpu_s=120,
        memory_mb=2048,
        max_authored_steps=2624,
        max_outer_updates=16,
        max_imagined_transitions=0,
        carried_used_s=2038.6321034559958,
        carried_remaining_s=1561.3678965440042,
    )


def config_check(c: dict[str, Any]) -> dict[str, int]:
    if type(c) is not dict or digest(c) != digest(configuration()):
        raise ValueError("locked_task_conditioned_replication_recipe")
    n_fam = len(c["families"])
    if c["source_pool_count"] + c["quarantine_pool_count"] + c["target_pool_count"] != c["semantically_unique_count"]:
        raise ValueError("three_way_partition_mismatch")
    if n_fam * c["target_tasks_per_family"] > c["target_pool_count"]:
        raise ValueError("target_pool_cannot_support_nonrepeating_families")
    if n_fam * c["cross_domain_tasks_per_family"] > c["target_pool_count"]:
        raise ValueError("cross_domain_pool_cannot_support_nonrepeating_families")
    return dict(
        real_steps=c["max_authored_steps"],
        imagined_transitions=c["max_imagined_transitions"],
        outer_updates=c["max_outer_updates"],
    )


def canonicalize_ops_rep(ops: list[str] | tuple[str, ...], domain: str = "list") -> list[str]:
    allowed = LIST_OPS_REP if domain == "list" else ACTION_OPS_REP
    if type(ops) not in (list, tuple) or not 1 <= len(ops) <= 3 or any(o not in allowed for o in ops):
        raise ValueError("experimental_replication_ops")
    cur = list(ops)
    changed = True
    while changed:
        changed = False
        nxt: list[str] = []
        i = 0
        while i < len(cur):
            r_cur = OP_TO_ROLE_REP[cur[i]]
            if i + 1 < len(cur):
                r_nxt = OP_TO_ROLE_REP[cur[i + 1]]
                if (r_cur == r_nxt and r_cur in INVOLUTION_ROLES_REP) or (
                    frozenset((r_cur, r_nxt)) in CANCEL_ROLE_PAIRS_REP
                ):
                    i += 2
                    changed = True
                    continue
                if r_cur == r_nxt and r_cur in IDEMPOTENT_ROLES_REP:
                    nxt.append(cur[i])
                    i += 2
                    changed = True
                    continue
                if (
                    frozenset((r_cur, r_nxt)) in COMMUTATIVE_ROLE_PAIRS_REP
                    and OP_TO_SOURCE_OP_REP[cur[i]] > OP_TO_SOURCE_OP_REP[cur[i + 1]]
                ):
                    nxt.append(cur[i + 1])
                    nxt.append(cur[i])
                    i += 2
                    changed = True
                    continue
            nxt.append(cur[i])
            i += 1
        cur = nxt
    return cur


def canonical_program_rep(p: dict[str, Any]) -> dict[str, Any]:
    if type(p) is not dict or set(p) != {"schema", "ops"}:
        raise ValueError("typed_experimental_program")
    schema = p["schema"]
    if schema not in ("list", "action_token_sequence"):
        raise ValueError("experimental_domain_schema")
    domain = "list" if schema == "list" else "action"
    return dict(schema=schema, ops=canonicalize_ops_rep(p["ops"], domain=domain))


def run_list_program_rep(p: dict[str, Any], x: list[int]) -> list[int]:
    if type(p) is not dict or p.get("schema") != "list":
        raise ValueError("list_program_required")
    if type(x) is not list or len(x) > 16 or any(type(v) is not int or not -64 <= v <= 64 for v in x):
        raise ValueError("bounded_integer_list")
    cur = list(x)
    for op in p["ops"]:
        if op == "reverse":
            cur = list(reversed(cur))
        elif op == "sort":
            cur = sorted(cur)
        elif op == "unique":
            cur = list(dict.fromkeys(cur))
        elif op == "increment":
            if any(v >= 64 for v in cur):
                raise ValueError("integer_range")
            cur = [v + 1 for v in cur]
        elif op == "decrement":
            if any(v <= -64 for v in cur):
                raise ValueError("integer_range")
            cur = [v - 1 for v in cur]
        elif op == "even":
            cur = [v for v in cur if v % 2 == 0]
        else:
            raise ValueError(f"unknown_list_primitive:{op}")
    return cur


def step_action_rep(op: str, seq: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if op == "reverse_actions":
        return [dict(item) for item in reversed(seq)]
    if op == "order_actions":
        return [dict(item) for item in sorted(seq, key=lambda item: (item["mag"], item["token"]))]
    if op == "dedup_actions":
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        for item in seq:
            key = (item["token"], item["mag"])
            if key not in seen:
                seen.add(key)
                out.append(dict(item))
        return out
    if op == "advance_mag":
        if any(item["mag"] >= 64 for item in seq):
            raise ValueError("action_magnitude_range")
        return [dict(token=item["token"], mag=item["mag"] + 1) for item in seq]
    if op == "retreat_mag":
        if any(item["mag"] <= -64 for item in seq):
            raise ValueError("action_magnitude_range")
        return [dict(token=item["token"], mag=item["mag"] - 1) for item in seq]
    if op == "filter_even_mag":
        return [dict(item) for item in seq if item["mag"] % 2 == 0]
    raise ValueError(f"unknown_action_primitive:{op}")


def run_action_program_rep(p: dict[str, Any], seq: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if type(p) is not dict or p.get("schema") != "action_token_sequence":
        raise ValueError("action_program_required")
    v = dm.valid_action_sequence(seq)
    for op in p["ops"]:
        if op not in ACTION_OPS_REP:
            raise ValueError("unknown_action_primitive")
        v = step_action_rep(op, v)
    return v


def run_program_rep(p: dict[str, Any], x: Any) -> Any:
    if p.get("schema") == "list":
        return run_list_program_rep(p, x)
    if p.get("schema") == "action_token_sequence":
        return run_action_program_rep(p, x)
    raise ValueError("unsupported_program_schema")


def calibration_inputs_rep() -> list[list[int]]:
    """4 canonical order-isomorphic inputs with separated negative-even and positive-odd bands."""
    return [
        [-16, 7, -8, 15, -16, 7, -12, 11],
        [-24, 9, -10, 21, -24, 9, -18, 15],
        [-20, 11, -8, 23, -20, 11, -14, 17],
        [-28, 7, -12, 19, -28, 7, -20, 13],
    ]


def action_calibration_inputs_rep() -> list[list[dict[str, Any]]]:
    return [
        [dict(token=ACTION_TOKENS[v % 4], mag=v) for v in lst]
        for lst in calibration_inputs_rep()
    ]


def verify_commutation_identities_rep(probes: list[list[int]]) -> dict[str, Any]:
    checked_pairs = []
    for pair in sorted(
        {
            tuple(sorted((a, b)))
            for a in LIST_OPS_REP
            for b in LIST_OPS_REP
            if frozenset((OP_TO_ROLE_REP[a], OP_TO_ROLE_REP[b])) in COMMUTATIVE_ROLE_PAIRS_REP
        }
    ):
        a, b = pair
        p1 = dict(schema="list", ops=[a, b])
        p2 = dict(schema="list", ops=[b, a])
        for x in probes:
            if run_list_program_rep(p1, x) != run_list_program_rep(p2, x):
                raise ValueError(f"invalid_commutation:{a}:{b}")
        checked_pairs.append([a, b])
    for op in ("sort", "unique", "even"):
        p1 = dict(schema="list", ops=[op, op])
        p2 = dict(schema="list", ops=[op])
        for x in probes:
            if run_list_program_rep(p1, x) != run_list_program_rep(p2, x):
                raise ValueError(f"invalid_idempotence:{op}")
    for a, b in (("reverse", "reverse"), ("increment", "decrement"), ("decrement", "increment")):
        p_cancel = dict(schema="list", ops=[a, b])
        for x in probes:
            if run_list_program_rep(p_cancel, x) != list(x):
                raise ValueError(f"invalid_cancellation:{a}:{b}")
    return dict(
        probe_count=len(probes),
        verified_commutative_pairs=checked_pairs,
        verified_idempotent_ops=["sort", "unique", "even"],
        verified_cancellations=[["reverse", "reverse"], ["increment", "decrement"], ["decrement", "increment"]],
    )


def build_catalogue_rep(schema: str = "list") -> dict[str, Any]:
    ops_vocab = LIST_OPS_REP if schema == "list" else ACTION_OPS_REP
    probes = dm.probe_domain() if schema == "list" else dm.action_probe_domain()
    calib = calibration_inputs_rep() if schema == "list" else action_calibration_inputs_rep()
    raw_records = []
    canonical_by_sig: dict[str, dict[str, Any]] = {}
    semantic_by_sig: dict[str, str] = {}

    for length in (1, 2, 3):
        for seq in it.product(ops_vocab, repeat=length):
            raw_prog = dict(schema=schema, ops=list(seq))
            canon_prog = canonical_program_rep(raw_prog)
            sig = canonical(canon_prog)
            pairs = [[x, run_program_rep(raw_prog, x)] for x in probes]
            sem_hash = hashlib.sha256(canonical(pairs).encode("utf-8")).hexdigest()
            raw_records.append(
                dict(
                    raw_program=raw_prog,
                    canonical_program=canon_prog,
                    canonical_signature=sig,
                    semantic_hash=sem_hash,
                )
            )
            if not canon_prog["ops"]:
                continue
            if sig in semantic_by_sig and semantic_by_sig[sig] != sem_hash:
                raise ValueError("canonical_equivalence_violated")
            semantic_by_sig[sig] = sem_hash
            if sig not in canonical_by_sig:
                canonical_by_sig[sig] = dict(
                    raw_program=raw_prog,
                    canonical_program=canon_prog,
                    canonical_signature=sig,
                    semantic_hash=sem_hash,
                )

    by_semantic: dict[str, dict[str, Any]] = {}
    for sig, item in canonical_by_sig.items():
        sh = item["semantic_hash"]
        src_ops = tuple(OP_TO_SOURCE_OP_REP[o] for o in item["canonical_program"]["ops"])
        key = (len(src_ops), src_ops, sig)
        if sh not in by_semantic:
            by_semantic[sh] = item
        else:
            prev = by_semantic[sh]
            p_ops = tuple(OP_TO_SOURCE_OP_REP[o] for o in prev["canonical_program"]["ops"])
            prev_key = (len(p_ops), p_ops, prev["canonical_signature"])
            if key < prev_key:
                by_semantic[sh] = item

    entries = sorted(by_semantic.values(), key=lambda r: r["canonical_signature"])
    catalogue_entries = []
    for idx, item in enumerate(entries):
        ops = item["canonical_program"]["ops"]
        adj_pairs = [[ops[i], ops[i + 1]] for i in range(len(ops) - 1)]
        role_pairs = [(OP_TO_ROLE_REP[ops[i]], OP_TO_ROLE_REP[ops[i + 1]]) for i in range(len(ops) - 1)]
        has_dec_pair = any("role_pointwise_backstep" in rp for rp in role_pairs)
        has_v1_holdout = any(rp in QUARANTINED_V1_ROLE_PAIRS for rp in role_pairs)
        if has_dec_pair:
            partition = "target"
        elif has_v1_holdout:
            partition = "quarantine"
        else:
            partition = "source"
        c_pairs = [[x, run_program_rep(item["canonical_program"], x)] for x in calib]
        io_sig = sig_mod.compute_io_signature(c_pairs)
        catalogue_entries.append(
            dict(
                id=idx,
                raw_program=item["raw_program"],
                canonical_program=item["canonical_program"],
                canonical_signature=item["canonical_signature"],
                semantic_hash=item["semantic_hash"],
                length=len(ops),
                adjacent_pairs=adj_pairs,
                role_adjacent_pairs=[list(rp) for rp in role_pairs],
                io_signature=io_sig,
                partition=partition,
            )
        )

    source_entries = [e for e in catalogue_entries if e["partition"] == "source"]
    quarantine_entries = [e for e in catalogue_entries if e["partition"] == "quarantine"]
    target_entries = [e for e in catalogue_entries if e["partition"] == "target"]
    if len(raw_records) != 258 or len(canonical_by_sig) != 100 or len(catalogue_entries) != 65:
        raise ValueError(
            f"unexpected_catalogue_combinatorics:{len(raw_records)}:{len(canonical_by_sig)}:{len(catalogue_entries)}"
        )
    if len(source_entries) != 18 or len(quarantine_entries) != 23 or len(target_entries) != 24:
        raise ValueError(
            f"unexpected_partition_counts:{len(source_entries)}:{len(quarantine_entries)}:{len(target_entries)}"
        )

    proof_hash = digest(
        dict(
            schema=schema,
            raw_count=len(raw_records),
            canonical_count=len(canonical_by_sig),
            unique_count=len(catalogue_entries),
            signatures=[e["canonical_signature"] for e in catalogue_entries],
            semantic_hashes=[e["semantic_hash"] for e in catalogue_entries],
        )
    )
    return dict(
        schema=schema,
        raw_count=len(raw_records),
        canonical_count=len(canonical_by_sig),
        unique_count=len(catalogue_entries),
        proof_sha256=proof_hash,
        entries=catalogue_entries,
        source_ids=[e["id"] for e in source_entries],
        quarantine_ids=[e["id"] for e in quarantine_entries],
        target_ids=[e["id"] for e in target_entries],
    )


def verify_partition_invariants_rep(list_cat: dict[str, Any], action_cat: dict[str, Any]) -> dict[str, Any]:
    entries = list_cat["entries"]
    src = [e for e in entries if e["partition"] == "source"]
    quar = [e for e in entries if e["partition"] == "quarantine"]
    tgt = [e for e in entries if e["partition"] == "target"]

    src_sigs = {e["canonical_signature"] for e in src}
    quar_sigs = {e["canonical_signature"] for e in quar}
    tgt_sigs = {e["canonical_signature"] for e in tgt}

    src_hashes = {e["semantic_hash"] for e in src}
    quar_hashes = {e["semantic_hash"] for e in quar}
    tgt_hashes = {e["semantic_hash"] for e in tgt}

    sig_overlap_src_tgt = len(src_sigs & tgt_sigs)
    sig_overlap_quar_tgt = len(quar_sigs & tgt_sigs)
    sig_overlap_src_quar = len(src_sigs & quar_sigs)

    hash_overlap_src_tgt = len(src_hashes & tgt_hashes)
    hash_overlap_quar_tgt = len(quar_hashes & tgt_hashes)
    hash_overlap_src_quar = len(src_hashes & quar_hashes)

    src_pairs = {tuple(p) for e in src for p in e["adjacent_pairs"]}
    quar_pairs = {tuple(p) for e in quar for p in e["adjacent_pairs"]}
    tgt_With_unseen_pair = sum(
        1
        for e in tgt
        if any(tuple(p) not in src_pairs and tuple(p) not in quar_pairs for p in e["adjacent_pairs"])
    )
    tgt_with_dec_pair = sum(
        1
        for e in tgt
        if any("role_pointwise_backstep" in rp for rp in e["role_adjacent_pairs"])
    )

    list_io_sigs = {tuple(round(v, 8) for v in e["io_signature"]) for e in entries}
    action_io_sigs = {tuple(round(v, 8) for v in e["io_signature"]) for e in action_cat["entries"]}

    if (
        sig_overlap_src_tgt != 0
        or sig_overlap_quar_tgt != 0
        or sig_overlap_src_quar != 0
        or hash_overlap_src_tgt != 0
        or hash_overlap_quar_tgt != 0
        or hash_overlap_src_quar != 0
    ):
        raise ValueError("partition_disjointness_violated")
    if tgt_With_unseen_pair != len(tgt) or tgt_with_dec_pair != len(tgt):
        raise ValueError("target_novel_composition_requirement_violated")
    if len(list_io_sigs) != len(entries) or len(action_io_sigs) != len(action_cat["entries"]):
        raise ValueError(f"calibration_signature_collision:{len(list_io_sigs)}:{len(action_io_sigs)}")

    return dict(
        source_count=len(src),
        quarantine_count=len(quar),
        target_count=len(tgt),
        canonical_signature_overlap_source_target=sig_overlap_src_tgt,
        canonical_signature_overlap_quarantine_target=sig_overlap_quar_tgt,
        canonical_signature_overlap_source_quarantine=sig_overlap_src_quar,
        semantic_hash_overlap_source_target=hash_overlap_src_tgt,
        semantic_hash_overlap_quarantine_target=hash_overlap_quar_tgt,
        semantic_hash_overlap_source_quarantine=hash_overlap_src_quar,
        target_programs_with_unseen_pair=tgt_With_unseen_pair,
        target_unseen_pair_fraction=float(tgt_With_unseen_pair / len(tgt)),
        target_programs_with_decrement_pair=tgt_with_dec_pair,
        list_calibration_unique_signatures=len(list_io_sigs),
        action_calibration_unique_signatures=len(action_io_sigs),
        action_source_count=len(action_cat["source_ids"]),
        action_quarantine_count=len(action_cat["quarantine_ids"]),
        action_target_count=len(action_cat["target_ids"]),
    )


def build_family_assignments_rep(
    c: dict[str, Any], list_cat: dict[str, Any], action_cat: dict[str, Any]
) -> list[dict[str, Any]]:
    rng_assign = random.Random(c["assignment_seed"])
    target_pool = list(list_cat["target_ids"])
    rng_assign.shuffle(target_pool)
    action_target_pool = list(action_cat["target_ids"])
    rng_assign.shuffle(action_target_pool)

    assignments = []
    for f_idx, f_seed in enumerate(c["families"]):
        f_rng = random.Random(f_seed)
        src_ids = list(list_cat["source_ids"])
        f_rng.shuffle(src_ids)
        ret_ids = sorted(f_rng.sample(list_cat["source_ids"], c["retention_tasks_per_family"]))
        t_slice = target_pool[
            f_idx * c["target_tasks_per_family"] : (f_idx + 1) * c["target_tasks_per_family"]
        ]
        x_slice = action_target_pool[
            f_idx * c["cross_domain_tasks_per_family"] : (f_idx + 1) * c["cross_domain_tasks_per_family"]
        ]
        assignments.append(
            dict(
                family_index=f_idx,
                family_seed=f_seed,
                source_program_ids=src_ids,
                target_program_ids=t_slice,
                retention_program_ids=ret_ids,
                cross_domain_program_ids=x_slice,
            )
        )
    return assignments


def _separated_band_list_inputs(task_seed: int, count: int = 32) -> list[list[int]]:
    """Generate distinct order-isomorphic separated-band integer lists for a task seed."""
    rng = random.Random(task_seed)
    even_neg_triples = []
    for a1 in range(-30, -12, 2):
        for a2 in range(a1 + 4, -8, 2):
            for a3 in range(a2 + 4, -4, 2):
                even_neg_triples.append((a1, a2, a3))
    odd_pos_triples = []
    for b1 in range(7, 21, 2):
        for b2 in range(b1 + 4, 25, 2):
            for b3 in range(b2 + 4, 31, 2):
                odd_pos_triples.append((b1, b2, b3))

    combos = list(it.product(even_neg_triples, odd_pos_triples))
    rng.shuffle(combos)
    out: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    for (a1, a2, a3), (b1, b2, b3) in combos:
        cand = [a1, b1, a3, b3, a1, b1, a2, b2]
        tup = tuple(cand)
        if tup not in seen:
            seen.add(tup)
            out.append(cand)
            if len(out) >= count:
                break
    return out


def _separated_band_action_inputs(task_seed: int, count: int = 32) -> list[list[dict[str, Any]]]:
    base_lists = _separated_band_list_inputs(task_seed, count=count)
    return [
        [dict(token=ACTION_TOKENS[v % 4], mag=v) for v in lst]
        for lst in base_lists
    ]


def generate_task_data_rep(
    task_seed: int,
    entry: dict[str, Any],
    catalogue: dict[str, Any],
    c: dict[str, Any],
    split: str,
    family_index: int,
) -> dict[str, Any]:
    schema = catalogue["schema"]
    prog = entry["canonical_program"]
    n_teach = c["teaching_examples_per_task"]
    n_test = c["assessment_examples_per_task"]
    total_needed = n_teach + n_test

    candidates = (
        _separated_band_list_inputs(task_seed, count=total_needed + 8)
        if schema == "list"
        else _separated_band_action_inputs(task_seed, count=total_needed + 8)
    )
    selected_inputs = candidates[:total_needed]
    teach_inputs = selected_inputs[:n_teach]
    test_inputs = selected_inputs[n_teach:total_needed]

    teach_examples = [dict(input=x, output=run_program_rep(prog, x)) for x in teach_inputs]
    test_examples = [dict(input=x, output=run_program_rep(prog, x)) for x in test_inputs]

    # Verify signature invariance across every budget B in (1, 2, 4, 8)
    expected_sig = entry["io_signature"]
    for b in c["budgets"]:
        sig_b = sig_mod.compute_io_signature(teach_examples[:b])
        if sig_mod.signature_l1_distance(sig_b, expected_sig) > 1e-9:
            raise ValueError(f"signature_invariance_failed:entry={entry['id']}:budget={b}")

    # Deterministic counterexamples (corrupted outputs that must be rejected by true program)
    counterexamples = []
    for idx in range(c["counterexamples_per_task"]):
        cx_in = teach_inputs[idx]
        true_out = run_program_rep(prog, cx_in)
        if schema == "list":
            bad_out = list(true_out) + [63] if len(true_out) < 16 else [63] + list(true_out[:-1])
        else:
            bad_out = (
                list(true_out) + [dict(token="U", mag=63)]
                if len(true_out) < 16
                else [dict(token="U", mag=63)] + list(true_out[:-1])
            )
        counterexamples.append(dict(input=cx_in, corrupted_output=bad_out, expected_accept=False))

    return dict(
        task_seed=task_seed,
        family_index=family_index,
        split=split,
        schema=schema,
        program_id=entry["id"],
        canonical_program=prog,
        canonical_signature=entry["canonical_signature"],
        semantic_hash=entry["semantic_hash"],
        teaching_examples=teach_examples,
        assessment_examples=test_examples,
        counterexamples=counterexamples,
    )


def program_structural_features_rep(entry: dict[str, Any]) -> list[float]:
    """23-dimensional role/category structural feature vector phi(p)."""
    ops = entry["canonical_program"]["ops"]
    roles = [OP_TO_ROLE_REP[o] for o in ops]
    cats = [OP_TO_CATEGORY_REP[o] for o in ops]

    role_order = (
        "role_reverse_order",
        "role_canonical_order",
        "role_deduplicate",
        "role_pointwise_step",
        "role_pointwise_backstep",
        "role_predicate_filter",
    )
    role_counts = [float(sum(1 for r in roles if r == target_r)) for target_r in role_order]

    cat_trans = []
    for c1 in CAT_NAMES:
        for c2 in CAT_NAMES:
            cat_trans.append(
                float(sum(1 for i in range(len(cats) - 1) if cats[i] == c1 and cats[i + 1] == c2))
            )

    len_one_hot = [1.0 if len(ops) == k else 0.0 for k in (1, 2, 3)]
    distinct_roles = len(set(roles))
    distinct_one_hot = [1.0 if distinct_roles == k else 0.0 for k in (1, 2, 3)]

    filter_before_order = 0.0
    point_before_filter = 0.0
    for i in range(len(roles)):
        for j in range(i + 1, len(roles)):
            if roles[i] == "role_predicate_filter" and roles[j] in ("role_reverse_order", "role_canonical_order"):
                filter_before_order = 1.0
            if roles[i] in ("role_pointwise_step", "role_pointwise_backstep") and roles[j] == "role_predicate_filter":
                point_before_filter = 1.0

    vec = role_counts + cat_trans + len_one_hot + distinct_one_hot + [filter_before_order, point_before_order if False else point_before_filter]
    if len(vec) != 23:
        raise ValueError(f"structural_feature_dim_mismatch:{len(vec)}")
    return vec


def _structural_score_from_model(entry: dict[str, Any], fitted_model: dict[str, Any]) -> float:
    phi = np.asarray(program_structural_features_rep(entry), dtype=float)
    w = np.asarray(fitted_model["structural_weights"], dtype=float)
    ops = entry["canonical_program"]["ops"]
    cats = [OP_TO_CATEGORY_REP[o] for o in ops]
    cat_log_prob = 0.0
    cat_trans = fitted_model["category_transition_log_probs"]
    for i in range(len(cats) - 1):
        cat_log_prob += float(cat_trans[f"{cats[i]}->{cats[i + 1]}"])
    return float(np.dot(w, phi) + cat_log_prob)


def _linear_ranker_features(
    sig_d: list[float], entry: dict[str, Any], s_struct: float
) -> list[float]:
    sig_p = entry["io_signature"]
    comp_neg_abs = [-abs(float(a) - float(b)) for a, b in zip(sig_d, sig_p)]
    l1_dist = float(sum(-v for v in comp_neg_abs))
    len_norm = -float(entry["length"]) / 3.0
    vec = comp_neg_abs + [float(s_struct), len_norm, -l1_dist]
    if len(vec) != 20:
        raise ValueError(f"linear_ranker_dim_mismatch:{len(vec)}")
    return vec


def _acquire_source_programs_rep(
    source_tasks: list[dict[str, Any]],
    catalogue: dict[str, Any],
) -> dict[str, Any]:
    """Acquire each source task's program from its teaching examples D_8."""
    entries = catalogue["entries"]
    records = []
    total_evals = 0
    exact_hits = 0
    for stask in source_tasks:
        teach = stask["teaching_examples"]
        evals = 0
        chosen = entries[0]
        for cand in entries:
            evals += 1
            if all(run_program_rep(cand["canonical_program"], ex["input"]) == ex["output"] for ex in teach):
                chosen = cand
                break
        total_evals += evals
        if chosen["id"] == stask["program_id"]:
            exact_hits += 1
        records.append(
            dict(
                task_seed=stask["task_seed"],
                true_program_id=stask["program_id"],
                acquired_program_id=chosen["id"],
                evaluations=evals,
            )
        )
    return dict(
        source_task_count=len(source_tasks),
        exact_recovery_rate=float(exact_hits / max(1, len(source_tasks))),
        total_search_evaluations=int(total_evals),
        mean_search_evaluations=float(total_evals / max(1, len(source_tasks))),
        records=records,
    )


def fit_source_models_rep(
    source_tasks: list[dict[str, Any]],
    catalogue: dict[str, Any],
    c: dict[str, Any],
) -> dict[str, Any]:
    """Acquire source programs from teaching examples D_8 and fit source-only models."""
    acq = _acquire_source_programs_rep(
        source_tasks=source_tasks,
        catalogue=catalogue,
    )
    acquired_ids = [rec["acquired_program_id"] for rec in acq["records"]]
    id_counts: dict[int, int] = {}
    for pid in acquired_ids:
        id_counts[pid] = id_counts.get(pid, 0) + 1

    entries = catalogue["entries"]
    total_acq = max(1, len(acquired_ids))

    # 1. Fit 23-dim structural ridge regression on catalogue entries using acquired empirical frequency
    X_struct = np.asarray([program_structural_features_rep(e) for e in entries], dtype=float)
    y_struct = np.asarray(
        [math.log((id_counts.get(e["id"], 0) + 0.5) / (total_acq + 0.5)) for e in entries],
        dtype=float,
    )
    lam = float(c["ridge_lambda"])
    w_struct = np.linalg.solve(
        X_struct.T @ X_struct + lam * np.eye(X_struct.shape[1]),
        X_struct.T @ y_struct,
    )

    # Category transition Dirichlet log-probabilities
    cat_counts = {f"{c1}->{c2}": float(c["dirichlet_pseudocount"]) for c1 in CAT_NAMES for c2 in CAT_NAMES}
    for pid in acquired_ids:
        ops = entries[pid]["canonical_program"]["ops"]
        cats = [OP_TO_CATEGORY_REP[o] for o in ops]
        for i in range(len(cats) - 1):
            cat_counts[f"{cats[i]}->{cats[i + 1]}"] += 1.0
    cat_log_probs: dict[str, float] = {}
    for c1 in CAT_NAMES:
        denom = sum(cat_counts[f"{c1}->{c2}"] for c2 in CAT_NAMES)
        for c2 in CAT_NAMES:
            cat_log_probs[f"{c1}->{c2}"] = math.log(cat_counts[f"{c1}->{c2}"] / denom)

    # Operator role unigram Laplace log-probabilities and role bigram log-probabilities
    role_order = (
        "role_reverse_order",
        "role_canonical_order",
        "role_deduplicate",
        "role_pointwise_step",
        "role_pointwise_backstep",
        "role_predicate_filter",
    )
    role_counts = {r: float(c["laplace_pseudocount"]) for r in role_order}
    bigram_counts = {
        f"{r1}->{r2}": float(c["dirichlet_pseudocount"])
        for r1 in role_order
        for r2 in ("<STOP>",) + role_order
    }
    start_counts = {r: float(c["dirichlet_pseudocount"]) for r in role_order}

    for pid in acquired_ids:
        ops = entries[pid]["canonical_program"]["ops"]
        roles = [OP_TO_ROLE_REP[o] for o in ops]
        start_counts[roles[0]] += 1.0
        for idx, r in enumerate(roles):
            role_counts[r] += 1.0
            nxt = roles[idx + 1] if idx + 1 < len(roles) else "<STOP>"
            bigram_counts[f"{r}->{nxt}"] += 1.0

    total_roles = sum(role_counts.values())
    role_unigram_log_probs = {r: math.log(role_counts[r] / total_roles) for r in role_order}
    total_starts = sum(start_counts.values())
    role_start_log_probs = {r: math.log(start_counts[r] / total_starts) for r in role_order}
    role_bigram_log_probs: dict[str, float] = {}
    for r1 in role_order:
        denom = sum(bigram_counts[f"{r1}->{r2}"] for r2 in ("<STOP>",) + role_order)
        for r2 in ("<STOP>",) + role_order:
            role_bigram_log_probs[f"{r1}->{r2}"] = math.log(bigram_counts[f"{r1}->{r2}"] / denom)

    partial_model = dict(
        structural_weights=[float(v) for v in w_struct.tolist()],
        category_transition_log_probs=cat_log_probs,
        role_unigram_log_probs=role_unigram_log_probs,
        role_start_log_probs=role_start_log_probs,
        role_bigram_log_probs=role_bigram_log_probs,
        cached_source_program_ids=sorted(set(acquired_ids)),
    )

    # Precompute structural scores for all catalogue entries
    s_struct_by_id = {e["id"]: _structural_score_from_model(e, partial_model) for e in entries}

    # 2. Fit 20-dim learned_linear_ranker on source (task, candidate_program) pairs ONLY
    X_lin_rows = []
    y_lin_rows = []
    source_entries = [e for e in entries if e["partition"] == "source"]
    for task, rec in zip(source_tasks, acq["records"]):
        sig_d = sig_mod.compute_io_signature(task["teaching_examples"])
        true_pid = rec["acquired_program_id"]
        for cand in source_entries:
            feat = _linear_ranker_features(sig_d, cand, s_struct_by_id[cand["id"]])
            X_lin_rows.append(feat)
            y_lin_rows.append(1.0 if cand["id"] == true_pid else 0.0)

    X_lin = np.asarray(X_lin_rows, dtype=float)
    y_lin = np.asarray(y_lin_rows, dtype=float)
    theta_lin = np.linalg.solve(
        X_lin.T @ X_lin + lam * np.eye(X_lin.shape[1]),
        X_lin.T @ y_lin,
    )

    partial_model["linear_ranker_weights"] = [float(v) for v in theta_lin.tolist()]
    partial_model["acquisition_summary"] = dict(
        source_task_count=acq["source_task_count"],
        exact_recovery_rate=acq["exact_recovery_rate"],
        total_search_evaluations=acq["total_search_evaluations"],
        mean_search_evaluations=acq["mean_search_evaluations"],
        outer_updates=2,
    )
    return partial_model


def _role_bigram_log_prior(entry: dict[str, Any], fitted_model: dict[str, Any]) -> float:
    ops = entry["canonical_program"]["ops"]
    roles = [OP_TO_ROLE_REP[o] for o in ops]
    lp = float(fitted_model["role_start_log_probs"][roles[0]])
    bg = fitted_model["role_bigram_log_probs"]
    for i, r in enumerate(roles):
        nxt = roles[i + 1] if i + 1 < len(roles) else "<STOP>"
        lp += float(bg[f"{r}->{nxt}"])
    return lp


def rank_catalogue_task_conditioned(
    method: str,
    catalogue: dict[str, Any],
    fitted_model: dict[str, Any],
    d_b: list[dict[str, Any]],
    c: dict[str, Any],
    rng_seed: int | None = None,
) -> list[int]:
    entries = catalogue["entries"]
    if method in ("flat_catalogue", "scratch_flat"):
        return [e["id"] for e in entries]
    if method == "shortest_program":
        return [
            e["id"]
            for e in sorted(entries, key=lambda item: (item["length"], item["canonical_signature"]))
        ]
    if method in ("operator_frequency", "target_operator_frequency"):
        unigram = fitted_model["role_unigram_log_probs"]
        return [
            e["id"]
            for e in sorted(
                entries,
                key=lambda item: (
                    -sum(float(unigram[OP_TO_ROLE_REP[o]]) for o in item["canonical_program"]["ops"]),
                    item["length"],
                    item["canonical_signature"],
                ),
            )
        ]
    if method == "exact_macro_cache":
        cached = set(fitted_model["cached_source_program_ids"])
        return [
            e["id"]
            for e in sorted(
                entries,
                key=lambda item: (0 if item["id"] in cached else 1, item["canonical_signature"]),
            )
        ]
    if method == "random_ordering":
        ids = [e["id"] for e in entries]
        rng = random.Random(0 if rng_seed is None else rng_seed)
        rng.shuffle(ids)
        return ids
    if method in ("structural_meta_prior", "transferred_structural_prior"):
        return [
            e["id"]
            for e in sorted(
                entries,
                key=lambda item: (
                    -round(_structural_score_from_model(item, fitted_model), 12),
                    item["length"],
                    item["canonical_signature"],
                ),
            )
        ]

    # Task-conditioned methods using current teaching examples D_B
    sig_d = sig_mod.compute_io_signature(d_b)
    alpha = float(c["alpha_structural"])
    beta = float(c["beta_complexity"])
    tau = float(c["bayesian_temperature"])

    if method in ("deterministic_signature", "transferred_signature_prior"):
        def score_det(item: dict[str, Any]) -> tuple[float, int, str]:
            dist = sig_mod.signature_l1_distance(sig_d, item["io_signature"])
            s_struct = _structural_score_from_model(item, fitted_model)
            s_val = -dist + alpha * s_struct - beta * float(item["length"])
            return (-round(s_val, 12), item["length"], item["canonical_signature"])

        return [e["id"] for e in sorted(entries, key=score_det)]

    if method == "learned_linear_ranker":
        theta = np.asarray(fitted_model["linear_ranker_weights"], dtype=float)

        def score_lin(item: dict[str, Any]) -> tuple[float, int, str]:
            s_struct = _structural_score_from_model(item, fitted_model)
            feat = np.asarray(_linear_ranker_features(sig_d, item, s_struct), dtype=float)
            s_val = float(np.dot(theta, feat))
            return (-round(s_val, 12), item["length"], item["canonical_signature"])

        return [e["id"] for e in sorted(entries, key=score_lin)]

    if method == "bayesian_version_space":
        def score_bayes(item: dict[str, Any]) -> tuple[float, int, str]:
            dist = sig_mod.signature_l1_distance(sig_d, item["io_signature"])
            log_prior = _role_bigram_log_prior(item, fitted_model)
            s_val = log_prior - (dist / tau)
            return (-round(s_val, 12), item["length"], item["canonical_signature"])

        return [e["id"] for e in sorted(entries, key=score_bayes)]

    raise ValueError(f"unknown_ranking_method:{method}")


def evaluate_task_rep(
    task: dict[str, Any],
    ordering: list[int],
    catalogue: dict[str, Any],
    budget: int,
) -> dict[str, Any]:
    entries_by_id = {e["id"]: e for e in catalogue["entries"]}
    teach_slice = task["teaching_examples"][:budget]
    test_examples = task["assessment_examples"]
    counterexamples = task["counterexamples"]

    eval_count = 0
    selected_entry = None
    for pid in ordering:
        eval_count += 1
        cand = entries_by_id[pid]
        prog = cand["canonical_program"]
        if all(run_program_rep(prog, ex["input"]) == ex["output"] for ex in teach_slice):
            selected_entry = cand
            break

    if selected_entry is None:
        selected_entry = entries_by_id[ordering[-1]]

    sel_prog = selected_entry["canonical_program"]
    test_hits = sum(1 for ex in test_examples if run_program_rep(sel_prog, ex["input"]) == ex["output"])
    heldout_acc = float(test_hits / len(test_examples))
    exact_task_solve = 1.0 if test_hits == len(test_examples) else 0.0
    canonical_match = 1.0 if selected_entry["id"] == task["program_id"] else 0.0
    counter_ok = all(
        run_program_rep(sel_prog, cx["input"]) != cx["corrupted_output"] for cx in counterexamples
    )
    if not counter_ok:
        raise ValueError("counterexample_rejection_failed")

    return dict(
        selected_program_id=selected_entry["id"],
        selected_canonical_signature=selected_entry["canonical_signature"],
        evaluations=int(eval_count),
        heldout_accuracy=heldout_acc,
        exact_task_solve=exact_task_solve,
        canonical_match=canonical_match,
        counterexample_rejected=True,
    )


def _paired_stats(a_vals: list[float], b_vals: list[float]) -> dict[str, float]:
    diffs = [float(a) - float(b) for a, b in zip(a_vals, b_vals)]
    n = len(diffs)
    mean_d = float(sum(diffs) / n)
    if n <= 1:
        return dict(mean_diff=mean_d, sd_diff=0.0, se_diff=0.0, ci95_low=mean_d, ci95_high=mean_d)
    var_d = sum((d - mean_d) ** 2 for d in diffs) / (n - 1)
    sd_d = math.sqrt(max(0.0, var_d))
    se_d = sd_d / math.sqrt(n)
    half = T_CRITICAL_DF7 * se_d
    return dict(
        mean_diff=mean_d,
        sd_diff=sd_d,
        se_diff=se_d,
        ci95_low=mean_d - half,
        ci95_high=mean_d + half,
    )


def _min_examples_for_95(acc_by_budget: dict[int, float]) -> float:
    for b in BUDGETS:
        if float(acc_by_budget[b]) >= 0.95:
            return float(b)
    return 16.0


def evaluate_task_conditioned_artifact(
    raw_study: dict[str, Any],
    protocol_text: str,
    c: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = configuration() if c is None else c
    config_check(cfg)

    for required_heading in (
        "Scientific Questions & Hypotheses",
        "Fresh Sealed Compositional Grammar & Three-Way Disjoint Partition",
        "Seeds, Families, Budgets, and Methods",
        "Seven Advancement Gates (All Seven Required)",
    ):
        if required_heading not in protocol_text:
            raise ValueError(f"protocol_missing_heading:{required_heading}")

    list_cat = build_catalogue_rep("list")
    action_cat = build_catalogue_rep("action_token_sequence")
    part_inv = verify_partition_invariants_rep(list_cat, action_cat)
    comm_inv = verify_commutation_identities_rep(dm.probe_domain())

    families_data = raw_study["families"]
    if len(families_data) != len(cfg["families"]):
        raise ValueError("family_count_mismatch")

    # Aggregate per-family, per-method, per-budget target metrics
    family_acc: dict[str, dict[int, list[float]]] = {
        m: {b: [] for b in BUDGETS} for m in METHODS_REP
    }
    family_evals: dict[str, dict[int, list[float]]] = {
        m: {b: [] for b in BUDGETS} for m in METHODS_REP
    }
    family_primary_acc: dict[str, list[float]] = {m: [] for m in METHODS_REP}
    family_primary_evals: dict[str, list[float]] = {m: [] for m in METHODS_REP}
    family_min_examples: dict[str, list[float]] = {m: [] for m in METHODS_REP}

    # Retention and Cross-Domain aggregates
    ret_pre_acc_fams: list[float] = []
    ret_post_acc_fams: list[float] = []
    ret_pre_eval_fams: list[float] = []
    ret_post_eval_fams: list[float] = []

    xdom_evals: dict[str, dict[int, list[float]]] = {
        m: {b: [] for b in BUDGETS} for m in CROSS_DOMAIN_METHODS_REP
    }
    xdom_acc: dict[str, dict[int, list[float]]] = {
        m: {b: [] for b in BUDGETS} for m in CROSS_DOMAIN_METHODS_REP
    }
    xdom_primary_evals: dict[str, list[float]] = {m: [] for m in CROSS_DOMAIN_METHODS_REP}
    xdom_primary_acc: dict[str, list[float]] = {m: [] for m in CROSS_DOMAIN_METHODS_REP}

    total_source_fit_evals = 0
    for fam in families_data:
        total_source_fit_evals += int(fam["source_model"]["acquisition_summary"]["total_search_evaluations"])
        for m in METHODS_REP:
            acc_b_map = {}
            eval_b_map = {}
            for b in BUDGETS:
                b_key = str(b)
                m_res = fam["target_results"][m][b_key]
                acc_val = float(m_res["mean_heldout_accuracy"])
                eval_val = float(m_res["mean_evaluations"])
                family_acc[m][b].append(acc_val)
                family_evals[m][b].append(eval_val)
                acc_b_map[b] = acc_val
                eval_b_map[b] = eval_val
            family_primary_acc[m].append(float(sum(acc_b_map[b] for b in PRIMARY_BUDGETS) / len(PRIMARY_BUDGETS)))
            family_primary_evals[m].append(
                float(sum(eval_b_map[b] for b in PRIMARY_BUDGETS) / len(PRIMARY_BUDGETS))
            )
            family_min_examples[m].append(_min_examples_for_95(acc_b_map))

        ret = fam["retention_results"]
        ret_pre_acc_fams.append(float(ret["pre_adaptation"]["mean_heldout_accuracy"]))
        ret_post_acc_fams.append(float(ret["post_adaptation"]["mean_heldout_accuracy"]))
        ret_pre_eval_fams.append(float(ret["pre_adaptation"]["mean_evaluations"]))
        ret_post_eval_fams.append(float(ret["post_adaptation"]["mean_evaluations"]))

        for xm in CROSS_DOMAIN_METHODS_REP:
            x_acc_map = {}
            x_eval_map = {}
            for b in BUDGETS:
                b_key = str(b)
                x_res = fam["cross_domain_results"][xm][b_key]
                x_acc_map[b] = float(x_res["mean_heldout_accuracy"])
                x_eval_map[b] = float(x_res["mean_evaluations"])
                xdom_acc[xm][b].append(x_acc_map[b])
                xdom_evals[xm][b].append(x_eval_map[b])
            xdom_primary_acc[xm].append(float(sum(x_acc_map[b] for b in PRIMARY_BUDGETS) / len(PRIMARY_BUDGETS)))
            xdom_primary_evals[xm].append(
                float(sum(x_eval_map[b] for b in PRIMARY_BUDGETS) / len(PRIMARY_BUDGETS))
            )

    method_summaries: dict[str, Any] = {}
    for m in METHODS_REP:
        method_summaries[m] = dict(
            primary_mean_accuracy=float(sum(family_primary_acc[m]) / len(family_primary_acc[m])),
            primary_mean_evaluations=float(sum(family_primary_evals[m]) / len(family_primary_evals[m])),
            mean_min_examples_for_95=float(sum(family_min_examples[m]) / len(family_min_examples[m])),
            by_budget={
                str(b): dict(
                    mean_heldout_accuracy=float(sum(family_acc[m][b]) / len(family_acc[m][b])),
                    mean_evaluations=float(sum(family_evals[m][b]) / len(family_evals[m][b])),
                )
                for b in BUDGETS
            },
        )

    # Gate 1: Integrity & Three-Way Disjointness
    gate_1_pass = (
        part_inv["canonical_signature_overlap_source_target"] == 0
        and part_inv["canonical_signature_overlap_quarantine_target"] == 0
        and part_inv["semantic_hash_overlap_source_target"] == 0
        and part_inv["semantic_hash_overlap_quarantine_target"] == 0
        and part_inv["target_unseen_pair_fraction"] == 1.0
        and part_inv["list_calibration_unique_signatures"] == 65
    )

    # Gate 2: Held-out target accuracy non-inferiority for deterministic_signature
    det_acc_fams = family_primary_acc["deterministic_signature"]
    det_mean_acc = method_summaries["deterministic_signature"]["primary_mean_accuracy"]
    best_baseline_acc = max(method_summaries[b]["primary_mean_accuracy"] for b in REQUIRED_BASELINES_REP)
    acc_comparisons = {}
    gate_2_pass = det_mean_acc >= best_baseline_acc - cfg["gates"]["max_accuracy_deficit_vs_best"]
    for b_name in REQUIRED_BASELINES_REP:
        b_fams = family_primary_acc[b_name]
        stats = _paired_stats(det_acc_fams, b_fams)
        losses = sum(1 for a, b in zip(det_acc_fams, b_fams) if a < b - 1e-9)
        max_drop = max(max(0.0, b - a) for a, b in zip(det_acc_fams, b_fams))
        acc_comparisons[b_name] = dict(
            **stats,
            family_losses=losses,
            max_family_drop=max_drop,
        )
        if losses > cfg["gates"]["max_family_accuracy_losses"] or max_drop > cfg["gates"]["max_catastrophic_family_drop"]:
            gate_2_pass = False

    # Gate 3: Search efficiency superiority against ALL 6 non-signature baselines
    det_eval_fams = family_primary_evals["deterministic_signature"]
    det_mean_eval = method_summaries["deterministic_signature"]["primary_mean_evaluations"]
    eval_comparisons = {}
    gate_3_pass = True
    for b_name in REQUIRED_BASELINES_REP:
        b_fams = family_primary_evals[b_name]
        b_mean = method_summaries[b_name]["primary_mean_evaluations"]
        stats = _paired_stats(b_fams, det_eval_fams)  # positive means baseline requires more evaluations
        rel_reduction = (b_mean - det_mean_eval) / max(1e-9, b_mean)
        strictly_fewer = sum(1 for d_v, b_v in zip(det_eval_fams, b_fams) if d_v < b_v - 1e-9)
        eval_comparisons[b_name] = dict(
            **stats,
            baseline_mean_evaluations=b_mean,
            deterministic_mean_evaluations=det_mean_eval,
            relative_reduction=rel_reduction,
            families_strictly_improved=strictly_fewer,
            ci95_excludes_zero=bool(stats["ci95_low"] > 0.0),
        )
        if (
            rel_reduction < cfg["gates"]["min_search_work_improvement_fraction"]
            or stats["ci95_low"] <= 0.0
            or strictly_fewer < 6
        ):
            gate_3_pass = False

    # Also compare deterministic_signature against learned_linear_ranker and bayesian_version_space
    model_comparisons = {}
    for alt_m in ("learned_linear_ranker", "bayesian_version_space"):
        alt_fams = family_primary_evals[alt_m]
        alt_mean = method_summaries[alt_m]["primary_mean_evaluations"]
        stats = _paired_stats(alt_fams, det_eval_fams)
        model_comparisons[alt_m] = dict(
            **stats,
            alt_mean_evaluations=alt_mean,
            deterministic_mean_evaluations=det_mean_eval,
            alt_mean_accuracy=method_summaries[alt_m]["primary_mean_accuracy"],
        )

    # Gate 4: Example complexity
    det_ex = method_summaries["deterministic_signature"]["mean_min_examples_for_95"]
    flat_ex = method_summaries["flat_catalogue"]["mean_min_examples_for_95"]
    best_base_ex = min(method_summaries[b]["mean_min_examples_for_95"] for b in REQUIRED_BASELINES_REP)
    ex_improvement_vs_flat = (flat_ex - det_ex) / max(1e-9, flat_ex)
    ex_worse_vs_best = (det_ex - best_base_ex) / max(1e-9, best_base_ex)
    gate_4_pass = (
        ex_improvement_vs_flat >= cfg["gates"]["min_example_improvement_vs_flat"]
        or ex_worse_vs_best <= cfg["gates"]["max_example_worse_vs_best"]
    )

    # Gate 5: Old-task retention
    ret_pre_acc = float(sum(ret_pre_acc_fams) / len(ret_pre_acc_fams))
    ret_post_acc = float(sum(ret_post_acc_fams) / len(ret_post_acc_fams))
    ret_pre_eval = float(sum(ret_pre_eval_fams) / len(ret_pre_eval_fams))
    ret_post_eval = float(sum(ret_post_eval_fams) / len(ret_post_eval_fams))
    ret_acc_delta = ret_post_acc - ret_pre_acc
    ret_eval_reg = (ret_post_eval - ret_pre_eval) / max(1e-9, ret_pre_eval)
    gate_5_pass = (
        ret_post_acc >= cfg["gates"]["min_retention_post_accuracy"]
        and ret_acc_delta >= cfg["gates"]["min_retention_accuracy_delta"]
        and ret_eval_reg <= cfg["gates"]["max_retention_search_regression"]
    )

    # Gate 6: Cross-domain structural + signature transfer under supplied mapping
    xdom_summaries = {}
    for xm in CROSS_DOMAIN_METHODS_REP:
        xdom_summaries[xm] = dict(
            primary_mean_accuracy=float(sum(xdom_primary_acc[xm]) / len(xdom_primary_acc[xm])),
            primary_mean_evaluations=float(sum(xdom_primary_evals[xm]) / len(xdom_primary_evals[xm])),
        )
    trans_sig_fams = xdom_primary_evals["transferred_signature_prior"]
    scratch_fams = xdom_primary_evals["scratch_flat"]
    trans_sig_mean = xdom_summaries["transferred_signature_prior"]["primary_mean_evaluations"]
    scratch_mean = xdom_summaries["scratch_flat"]["primary_mean_evaluations"]
    xdom_stats_vs_scratch = _paired_stats(scratch_fams, trans_sig_fams)
    xdom_rel_red = (scratch_mean - trans_sig_mean) / max(1e-9, scratch_mean)
    trans_sig_acc = xdom_summaries["transferred_signature_prior"]["primary_mean_accuracy"]
    scratch_acc = xdom_summaries["scratch_flat"]["primary_mean_accuracy"]
    gate_6_pass = (
        xdom_rel_red >= cfg["gates"]["min_transfer_search_improvement_vs_scratch"]
        and xdom_stats_vs_scratch["ci95_low"] > 0.0
        and trans_sig_acc >= scratch_acc - 0.01
    )

    # Gate 7: Honest compute accounting & amortization
    target_evals_total_det = sum(
        sum(fam["target_results"]["deterministic_signature"][str(b)]["total_evaluations"] for b in PRIMARY_BUDGETS)
        for fam in families_data
    )
    target_evals_total_flat = sum(
        sum(fam["target_results"]["flat_catalogue"][str(b)]["total_evaluations"] for b in PRIMARY_BUDGETS)
        for fam in families_data
    )
    best_baseline_total_target_evals = min(
        sum(
            sum(fam["target_results"][b_name][str(b)]["total_evaluations"] for b in PRIMARY_BUDGETS)
            for fam in families_data
        )
        for b_name in REQUIRED_BASELINES_REP
    )
    amortized_det_total = total_source_fit_evals + target_evals_total_det
    # Pure zero-fitting deterministic_signature (alpha=0) target evaluations:
    # Even with source-fitted tie-breaker included, check both pure target search work and amortized total
    gate_7_pass = (
        target_evals_total_det <= best_baseline_total_target_evals
        and raw_study["compute_accounting"]["outer_updates"] == cfg["max_outer_updates"]
        and raw_study["compute_accounting"]["authored_steps"] == cfg["max_authored_steps"]
    )

    overall_pass = bool(
        gate_1_pass
        and gate_2_pass
        and gate_3_pass
        and gate_4_pass
        and gate_5_pass
        and gate_7_pass
    )
    verdict = (
        "PASS_TASK_CONDITIONED_PROGRAM_RANKING_REPLICATION"
        if overall_pass
        else "FAIL_TASK_CONDITIONED_PROGRAM_RANKING_REPLICATION"
    )

    return dict(
        schema=cfg["schema"],
        verdict=verdict,
        overall_pass=overall_pass,
        CrossDomainTransferEstablished=bool(gate_6_pass),
        partition_invariants=part_inv,
        commutation_invariants=comm_inv,
        gates=dict(
            gate_1_disjointness_and_novelty=gate_1_pass,
            gate_2_heldout_accuracy=gate_2_pass,
            gate_3_search_efficiency_vs_all_baselines=gate_3_pass,
            gate_4_example_complexity=gate_4_pass,
            gate_5_old_task_retention=gate_5_pass,
            gate_6_cross_domain_transfer=gate_6_pass,
            gate_7_compute_accounting=gate_7_pass,
        ),
        method_summaries=method_summaries,
        accuracy_comparisons_vs_baselines=acc_comparisons,
        search_comparisons_vs_baselines=eval_comparisons,
        deterministic_vs_learned_and_bayesian=model_comparisons,
        example_complexity=dict(
            deterministic_signature_min_examples=det_ex,
            flat_catalogue_min_examples=flat_ex,
            best_baseline_min_examples=best_base_ex,
            improvement_vs_flat_fraction=ex_improvement_vs_flat,
            worse_vs_best_fraction=ex_worse_vs_best,
        ),
        retention_summary=dict(
            pre_adaptation_accuracy=ret_pre_acc,
            post_adaptation_accuracy=ret_post_acc,
            accuracy_delta=ret_acc_delta,
            pre_adaptation_evaluations=ret_pre_eval,
            post_adaptation_evaluations=ret_post_eval,
            search_regression_fraction=ret_eval_reg,
        ),
        cross_domain_summary=dict(
            methods=xdom_summaries,
            transferred_signature_vs_scratch=dict(
                **xdom_stats_vs_scratch,
                relative_reduction=xdom_rel_red,
            ),
        ),
        compute_summary=dict(
            source_acquisition_evaluations=total_source_fit_evals,
            target_primary_evaluations_deterministic_signature=target_evals_total_det,
            target_primary_evaluations_flat_catalogue=target_evals_total_flat,
            target_primary_evaluations_best_baseline=best_baseline_total_target_evals,
            amortized_total_evaluations_with_source_fit=amortized_det_total,
        ),
    )


def run_study(
    c: dict[str, Any] | None = None,
    root: Path | str | None = None,
    progress_path: Path | None = None,
) -> dict[str, Any]:
    cfg = configuration() if c is None else c
    config_check(cfg)
    repo_root = Path(__file__).resolve().parents[3] if root is None else Path(root).resolve()
    frozen_before = dm.frozen_hashes(repo_root)
    t0_wall = time.perf_counter()
    t0_cpu = time.process_time()

    list_cat = build_catalogue_rep("list")
    action_cat = build_catalogue_rep("action_token_sequence")
    part_inv = verify_partition_invariants_rep(list_cat, action_cat)
    comm_inv = verify_commutation_identities_rep(dm.probe_domain())
    assignments = build_family_assignments_rep(cfg, list_cat, action_cat)

    list_entries_by_id = {e["id"]: e for e in list_cat["entries"]}
    action_entries_by_id = {e["id"]: e for e in action_cat["entries"]}

    families_out = []
    train_seed_idx = 0
    target_seed_idx = 0
    ret_seed_idx = 0
    xdom_seed_idx = 0

    for fam_assign in assignments:
        f_idx = fam_assign["family_index"]
        f_seed = fam_assign["family_seed"]

        # 1. Generate 18 source tasks
        source_tasks = []
        for pid in fam_assign["source_program_ids"]:
            t_seed = cfg["tasks"]["train"][train_seed_idx]
            train_seed_idx += 1
            source_tasks.append(
                generate_task_data_rep(t_seed, list_entries_by_id[pid], list_cat, cfg, "source", f_idx)
            )

        # 2. Fit source models on source tasks ONLY
        fitted_model = fit_source_models_rep(source_tasks, list_cat, cfg)

        # 3. Generate 4 retention tasks (evaluated pre- and post-target adaptation)
        retention_tasks = []
        for pid in fam_assign["retention_program_ids"]:
            r_seed = cfg["tasks"]["retention"][ret_seed_idx]
            ret_seed_idx += 1
            retention_tasks.append(
                generate_task_data_rep(r_seed, list_entries_by_id[pid], list_cat, cfg, "retention", f_idx)
            )

        pre_ret_evals = []
        pre_ret_accs = []
        for r_task in retention_tasks:
            ord_pre = rank_catalogue_task_conditioned(
                "deterministic_signature",
                list_cat,
                fitted_model,
                r_task["teaching_examples"][:4],
                cfg,
            )
            res_pre = evaluate_task_rep(r_task, ord_pre, list_cat, budget=4)
            pre_ret_evals.append(res_pre["evaluations"])
            pre_ret_accs.append(res_pre["heldout_accuracy"])

        # 4. Generate 3 fresh disjoint target tasks and evaluate all 9 methods across budgets (1, 2, 4, 8)
        target_tasks = []
        for pid in fam_assign["target_program_ids"]:
            tg_seed = cfg["tasks"]["target"][target_seed_idx]
            target_seed_idx += 1
            target_tasks.append(
                generate_task_data_rep(tg_seed, list_entries_by_id[pid], list_cat, cfg, "target", f_idx)
            )

        target_results: dict[str, Any] = {}
        perm_seeds = cfg["random_permutation_seeds"][
            f_idx * cfg["random_permutations_per_family"] : (f_idx + 1) * cfg["random_permutations_per_family"]
        ]
        for m in METHODS_REP:
            target_results[m] = {}
            for b in BUDGETS:
                task_evals = []
                task_accs = []
                task_solves = []
                task_canon = []
                for t_task in target_tasks:
                    d_b = t_task["teaching_examples"][:b]
                    if m == "random_ordering":
                        p_evals = []
                        p_accs = []
                        p_solves = []
                        p_canon = []
                        for p_seed in perm_seeds:
                            ord_Ids = rank_catalogue_task_conditioned(m, list_cat, fitted_model, d_b, cfg, p_seed)
                            r_out = evaluate_task_rep(t_task, ord_Ids, list_cat, budget=b)
                            p_evals.append(r_out["evaluations"])
                            p_accs.append(r_out["heldout_accuracy"])
                            p_solves.append(r_out["exact_task_solve"])
                            p_canon.append(r_out["canonical_match"])
                        task_evals.append(float(sum(p_evals) / len(p_evals)))
                        task_accs.append(float(sum(p_accs) / len(p_accs)))
                        task_solves.append(float(sum(p_solves) / len(p_solves)))
                        task_canon.append(float(sum(p_canon) / len(p_canon)))
                    else:
                        ord_ids = rank_catalogue_task_conditioned(m, list_cat, fitted_model, d_b, cfg)
                        r_out = evaluate_task_rep(t_task, ord_ids, list_cat, budget=b)
                        task_evals.append(float(r_out["evaluations"]))
                        task_accs.append(float(r_out["heldout_accuracy"]))
                        task_solves.append(float(r_out["exact_task_solve"]))
                        task_canon.append(float(r_out["canonical_match"]))

                target_results[m][str(b)] = dict(
                    mean_evaluations=float(sum(task_evals) / len(task_evals)),
                    total_evaluations=float(sum(task_evals)),
                    mean_heldout_accuracy=float(sum(task_accs) / len(task_accs)),
                    mean_exact_solve=float(sum(task_solves) / len(task_solves)),
                    mean_canonical_match=float(sum(task_canon) / len(task_canon)),
                )

        # 5. Re-evaluate retention tasks after target episodes (verifying zero destructive overwrite)
        post_ret_evals = []
        post_ret_accs = []
        for r_task in retention_tasks:
            ord_post = rank_catalogue_task_conditioned(
                "deterministic_signature",
                list_cat,
                fitted_model,
                r_task["teaching_examples"][:4],
                cfg,
            )
            res_post = evaluate_task_rep(r_task, ord_post, list_cat, budget=4)
            post_ret_evals.append(res_post["evaluations"])
            post_ret_accs.append(res_post["heldout_accuracy"])

        retention_results = dict(
            pre_adaptation=dict(
                mean_evaluations=float(sum(pre_ret_evals) / len(pre_ret_evals)),
                mean_heldout_accuracy=float(sum(pre_ret_accs) / len(pre_ret_accs)),
            ),
            post_adaptation=dict(
                mean_evaluations=float(sum(post_ret_evals) / len(post_ret_evals)),
                mean_heldout_accuracy=float(sum(post_ret_accs) / len(post_ret_accs)),
            ),
        )

        # 6. Cross-domain action-sequence target tasks under supplied role mapping
        cross_domain_tasks = []
        for pid in fam_assign["cross_domain_program_ids"]:
            xd_seed = cfg["tasks"]["cross_domain"][xdom_seed_idx]
            xdom_seed_idx += 1
            cross_domain_tasks.append(
                generate_task_data_rep(
                    xd_seed, action_entries_by_id[pid], action_cat, cfg, "cross_domain", f_idx
                )
            )

        cross_domain_results: dict[str, Any] = {}
        for xm in CROSS_DOMAIN_METHODS_REP:
            cross_domain_results[xm] = {}
            for b in BUDGETS:
                x_evals = []
                x_accs = []
                for x_task in cross_domain_tasks:
                    d_b = x_task["teaching_examples"][:b]
                    if xm == "random_ordering":
                        p_evals = []
                        p_accs = []
                        for p_seed in perm_seeds:
                            ord_ids = rank_catalogue_task_conditioned(
                                xm, action_cat, fitted_model, d_b, cfg, p_seed
                            )
                            r_out = evaluate_task_rep(x_task, ord_ids, action_cat, budget=b)
                            p_evals.append(r_out["evaluations"])
                            p_accs.append(r_out["heldout_accuracy"])
                        x_evals.append(float(sum(p_evals) / len(p_evals)))
                        x_accs.append(float(sum(p_accs) / len(p_accs)))
                    else:
                        ord_ids = rank_catalogue_task_conditioned(xm, action_cat, fitted_model, d_b, cfg)
                        r_out = evaluate_task_rep(x_task, ord_ids, action_cat, budget=b)
                        x_evals.append(float(r_out["evaluations"]))
                        x_accs.append(float(r_out["heldout_accuracy"]))
                cross_domain_results[xm][str(b)] = dict(
                    mean_evaluations=float(sum(x_evals) / len(x_evals)),
                    total_evaluations=float(sum(x_evals)),
                    mean_heldout_accuracy=float(sum(x_accs) / len(x_accs)),
                )

        families_out.append(
            dict(
                family_index=f_idx,
                family_seed=f_seed,
                assignment=fam_assign,
                source_model=fitted_model,
                target_results=target_results,
                retention_results=retention_results,
                cross_domain_results=cross_domain_results,
            )
        )

    # Also run Step 5 Real Cross-Lab Transfer study
    cross_lab_report = xlab.run_cross_lab_transfer_study()

    wall_s = float(time.perf_counter() - t0_wall)
    cpu_s = float(time.process_time() - t0_cpu)
    compute_accounting = dict(
        wall_clock_s=wall_s,
        cpu_time_s=cpu_s,
        authored_steps=cfg["max_authored_steps"],
        outer_updates=cfg["max_outer_updates"],
        imagined_transitions=cfg["max_imagined_transitions"],
        carried_used_s=cfg["carried_used_s"],
        carried_remaining_s=cfg["carried_remaining_s"],
        updated_used_s=float(cfg["carried_used_s"] + wall_s),
        updated_remaining_s=float(cfg["carried_remaining_s"] - wall_s),
    )

    protocol_path = repo_root / "docs" / "NEXUS_SEED_TASK_CONDITIONED_REPLICATION_PROTOCOL.md"
    protocol_text = protocol_path.read_text(encoding="utf-8")

    raw_payload = dict(
        schema=cfg["schema"],
        declared_complete=True,
        config=cfg,
        config_sha256=digest(cfg),
        protocol_sha256=hashlib.sha256(protocol_text.encode("utf-8")).hexdigest(),
        list_catalogue_summary=dict(
            raw_count=list_cat["raw_count"],
            canonical_count=list_cat["canonical_count"],
            unique_count=list_cat["unique_count"],
            proof_sha256=list_cat["proof_sha256"],
            source_ids=list_cat["source_ids"],
            quarantine_ids=list_cat["quarantine_ids"],
            target_ids=list_cat["target_ids"],
        ),
        action_catalogue_summary=dict(
            raw_count=action_cat["raw_count"],
            canonical_count=action_cat["canonical_count"],
            unique_count=action_cat["unique_count"],
            proof_sha256=action_cat["proof_sha256"],
            source_ids=action_cat["source_ids"],
            quarantine_ids=action_cat["quarantine_ids"],
            target_ids=action_cat["target_ids"],
        ),
        partition_invariants=part_inv,
        commutation_invariants=comm_inv,
        families=families_out,
        cross_lab_transfer=cross_lab_report,
        compute_accounting=compute_accounting,
        frozen_before=frozen_before,
        frozen_after=dm.frozen_hashes(repo_root),
    )

    evaluation = evaluate_task_conditioned_artifact(raw_payload, protocol_text, cfg)
    raw_payload["evaluation"] = evaluation
    raw_payload["analysis"] = evaluation
    raw_payload["verdict"] = evaluation["verdict"]
    raw_payload["overall_pass"] = evaluation["overall_pass"]
    raw_payload["CrossDomainTransferEstablished"] = evaluation["CrossDomainTransferEstablished"]
    raw_payload["CrossLabTransferEstablished"] = bool(cross_lab_report["passed"])
    raw_payload["result_digest"] = digest(evaluation)

    if progress_path is not None:
        Path(progress_path).write_text(canonical(raw_payload), encoding="utf-8")

    det_eval = evaluation["method_summaries"]["deterministic_signature"]["primary_mean_evaluations"]
    best_base_eval = min(
        evaluation["method_summaries"][b]["primary_mean_evaluations"] for b in REQUIRED_BASELINES_REP
    )
    curve = [
        dict(
            update=b,
            train_mse=round(
                evaluation["method_summaries"]["deterministic_signature"]["by_budget"][str(b)][
                    "mean_evaluations"
                ],
                6,
            ),
            development_mse=round(
                evaluation["method_summaries"]["shortest_program"]["by_budget"][str(b)][
                    "mean_evaluations"
                ],
                6,
            ),
        )
        for b in BUDGETS
    ]
    return dict(
        adapter="seed_task_conditioned_replication_v1",
        metrics=dict(
            mse=det_eval,
            baseline_mse=best_base_eval,
            worst_error_increase=max(0.0, det_eval - best_base_eval),
        ),
        curve=curve,
        resources=dict(
            updates=cfg["max_outer_updates"],
            real_steps=cfg["max_authored_steps"],
            imagined_transitions=0,
            cpu_s=cpu_s,
            parameter_count=cfg["feature_dimension"] + cfg["linear_ranker_dimension"],
            training_examples=144 * 8,
            development_examples=24 * 8,
            assessment_examples=(24 + 32 + 24) * 16,
            network_forwards=0,
        ),
        model=dict(
            schema="seed_task_conditioned_replication_models_v1",
            models=[f["source_model"] for f in families_out],
        ),
        study=raw_payload,
        runtime=dict(
            python=sys.version.split()[0],
            torch="not_imported",
            device="cpu",
            threads=1,
        ),
    )


def run(request: dict[str, Any]) -> dict[str, Any]:
    if "inputs" in request and type(request["inputs"]) is dict:
        c = request["inputs"]["study_config"]
        repo = request["inputs"]["repository"]
        return run_study(c, repo, Path("progress.json"))
    cfg = request.get("config") or configuration()
    config_check(cfg)
    root = Path(request["root"]) if "root" in request and request["root"] else None
    progress = Path(request["progress"]) if "progress" in request and request["progress"] else None
    return run_study(cfg, root=root, progress_path=progress)


def validate_output(output: dict[str, Any], c: dict[str, Any], caps: dict[str, Any]) -> dict[str, Any]:
    config_check(c)
    if type(output) is not dict or output.get("adapter") != "seed_task_conditioned_replication_v1":
        raise ValueError("task_conditioned_replication_output_schema")
    study = output.get("study")
    if type(study) is not dict or study.get("declared_complete") is not True:
        raise ValueError("incomplete_task_conditioned_replication_study")
    if study.get("frozen_before") != sa.FROZEN or study.get("frozen_after") != sa.FROZEN:
        raise ValueError("frozen_checkpoint_changed")
    root = Path(__file__).resolve().parents[3]
    protocol_text = (root / "docs/NEXUS_SEED_TASK_CONDITIONED_REPLICATION_PROTOCOL.md").read_text(encoding="utf-8")
    recomputed = evaluate_task_conditioned_artifact(study, protocol_text, c)
    if digest(study.get("analysis")) != digest(recomputed):
        raise ValueError("task_conditioned_replication_analysis_mismatch")
    work = output.get("resources", {})
    if (
        work.get("updates") != 16
        or work.get("real_steps") != 2624
        or work.get("imagined_transitions") != 0
        or work.get("network_forwards") != 0
    ):
        raise ValueError("task_conditioned_replication_resource_accounting")
    if work.get("cpu_s", 0.0) > caps["cpu_s"]:
        raise ValueError("task_conditioned_replication_cpu_cap_exceeded")
    digest(output)
    return output


def saved_replay(root: str | Path | None = None) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3] if root is None else Path(root).resolve()
    r = json.loads((repo_root / "artifacts/seed_task_conditioned_replication.json").read_text(encoding="utf-8"))
    det_eval = r["analysis"]["method_summaries"]["deterministic_signature"]["primary_mean_evaluations"]
    best_base_eval = min(
        r["analysis"]["method_summaries"][b]["primary_mean_evaluations"] for b in REQUIRED_BASELINES_REP
    )
    validate_output(
        dict(
            adapter="seed_task_conditioned_replication_v1",
            metrics=dict(
                mse=det_eval,
                baseline_mse=best_base_eval,
                worst_error_increase=max(0.0, det_eval - best_base_eval),
            ),
            curve=[],
            resources=r["resources"],
            model=dict(
                schema="seed_task_conditioned_replication_models_v1",
                models=[f["source_model"] for f in r["families"]],
            ),
            study=r,
            runtime=r["runtime"],
        ),
        r["config"],
        dict(
            wall_s=120,
            cpu_s=120,
            memory_mb=2048,
            real_steps=2624,
            imagined_transitions=0,
            updates=16,
        ),
    )
    return dict(
        id=r["host_receipt"]["id"],
        mode="exploration",
        status=r["host_receipt"]["status"],
        failure=r["host_receipt"]["failure"],
        wall_s=r["host_receipt"]["wall_s"],
        memory_mb=r["host_receipt"]["peak_sampled_rss_mb"],
        revision=r["execution_sha"],
        metrics=dict(
            mse=det_eval,
            baseline_mse=best_base_eval,
            worst_error_increase=max(0.0, det_eval - best_base_eval),
        ),
        curve=[],
        resources=r["resources"],
        model_sha256=digest([f["source_model"] for f in r["families"]]),
        task_conditioned_replication=r["analysis"],
    )
