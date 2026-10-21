"""Preregistered disjoint compositional meta-learning study (seed_disjoint_meta_v1).

Tests whether a structural meta-prior fitted only on source programs reduces
program search on canonically and semantically disjoint target compositions
(length 1-3 over {reverse, sort, unique, increment, even}), while preserving
old-source retention and testing structural transfer under an explicitly
supplied operator-role mapping to a separate action-token sequence domain.

No eval, arbitrary Python, dynamic imports, neural training, or target tuning.
"""
import copy
import hashlib
import itertools as it
import json
import math
from pathlib import Path
import random
import statistics as st
import sys
import time
from typing import Any

import numpy as np
from nexus.evolution1.catalogue import canonical, digest
from . import source_acquisition as sa
from . import skill_programs as ir

LIST_OPS = ("reverse", "sort", "unique", "increment", "even")
ACTION_OPS = ("reverse_actions", "order_actions", "dedup_actions", "advance_mag", "filter_even_mag")
ACTION_TOKENS = ("D", "L", "R", "U")
CAT_NAMES = ("perm", "card", "point")

SUPPLIED_ROLE_MAPPING = {
    "reverse": dict(target_op="reverse_actions", role="role_reverse_order", category="perm"),
    "sort": dict(target_op="order_actions", role="role_canonical_order", category="perm"),
    "unique": dict(target_op="dedup_actions", role="role_deduplicate", category="card"),
    "increment": dict(target_op="advance_mag", role="role_pointwise_step", category="point"),
    "even": dict(target_op="filter_even_mag", role="role_predicate_filter", category="card"),
}
TARGET_OP_TO_SOURCE = {v["target_op"]: k for k, v in SUPPLIED_ROLE_MAPPING.items()}
OP_TO_SOURCE_OP = {k: k for k in SUPPLIED_ROLE_MAPPING} | TARGET_OP_TO_SOURCE
OP_TO_ROLE = {k: v["role"] for k, v in SUPPLIED_ROLE_MAPPING.items()} | {
    v["target_op"]: v["role"] for v in SUPPLIED_ROLE_MAPPING.values()
}
OP_TO_CATEGORY = {k: v["category"] for k, v in SUPPLIED_ROLE_MAPPING.items()} | {
    v["target_op"]: v["category"] for v in SUPPLIED_ROLE_MAPPING.values()
}

IDEMPOTENT_ROLES = frozenset(("role_canonical_order", "role_deduplicate", "role_predicate_filter"))
INVOLUTION_ROLES = frozenset(("role_reverse_order",))
COMMUTATIVE_ROLE_PAIRS = frozenset((
    frozenset(("role_pointwise_step", "role_reverse_order")),
    frozenset(("role_pointwise_step", "role_canonical_order")),
    frozenset(("role_pointwise_step", "role_deduplicate")),
    frozenset(("role_canonical_order", "role_deduplicate")),
    frozenset(("role_deduplicate", "role_predicate_filter")),
))

HOLDOUT_PAIRS = (
    ("even", "increment"),
    ("even", "sort"),
    ("increment", "even"),
    ("increment", "increment"),
    ("reverse", "unique"),
)
HOLDOUT_ROLE_PAIRS = tuple((OP_TO_ROLE[a], OP_TO_ROLE[b]) for a, b in HOLDOUT_PAIRS)

METHODS = (
    "structural_meta_prior",
    "flat_catalogue",
    "shortest_program",
    "operator_frequency",
    "exact_macro_cache",
    "random_ordering",
    "bayesian_model_based",
)
SIMPLE_BASELINES = (
    "flat_catalogue",
    "shortest_program",
    "operator_frequency",
    "exact_macro_cache",
    "random_ordering",
)
CROSS_DOMAIN_METHODS = (
    "transferred_structural_prior",
    "scratch_flat",
    "shortest_program",
    "target_operator_frequency",
    "exact_macro_cache",
    "random_ordering",
    "bayesian_model_based",
)
BUDGETS = (1, 2, 4, 8)
PRIMARY_BUDGETS = (1, 2, 4)
T_CRITICAL_DF7 = 2.364624251


def configuration() -> dict[str, Any]:
    return dict(
        schema="seed_disjoint_meta_v1",
        families=list(range(1748000001, 1748000009)),
        assignment_seed=1748000900,
        tasks=dict(
            train=list(range(1748100000, 1748100128)),
            target=list(range(1748200000, 1748200024)),
            retention=list(range(1748300000, 1748300032)),
            cross_domain=list(range(1748400000, 1748400024)),
        ),
        random_permutation_seeds=list(range(1748500000, 1748500512)),
        primitives=list(LIST_OPS),
        action_primitives=list(ACTION_OPS),
        max_program_length=3,
        probe_max_length=4,
        probe_alphabet=[-2, -1, 0, 1, 2],
        probe_count=781,
        raw_program_count=155,
        canonical_program_count=68,
        semantically_unique_count=41,
        source_pool_count=17,
        target_pool_count=24,
        holdout_adjacent_pairs=[list(p) for p in HOLDOUT_PAIRS],
        source_tasks_per_family=16,
        target_tasks_per_family=3,
        retention_tasks_per_family=4,
        cross_domain_tasks_per_family=3,
        teaching_examples_per_task=8,
        assessment_examples_per_task=16,
        counterexamples_per_task=2,
        budgets=list(BUDGETS),
        primary_budgets=list(PRIMARY_BUDGETS),
        secondary_budget=8,
        methods=list(METHODS),
        cross_domain_methods=list(CROSS_DOMAIN_METHODS),
        ridge_lambda=1.0,
        laplace_pseudocount=1.0,
        dirichlet_pseudocount=1.0,
        random_permutations_per_family=64,
        feature_dimension=23,
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
        max_authored_steps=2496,
        max_outer_updates=8,
        max_imagined_transitions=0,
        carried_used_s=2005.6321034559958,
        carried_remaining_s=1594.3678965440042,
    )


def config_check(c: dict[str, Any]) -> dict[str, int]:
    if type(c) is not dict or digest(c) != digest(configuration()):
        raise ValueError("locked_disjoint_meta_recipe")
    n_fam = len(c["families"])
    if c["source_pool_count"] + n_fam * c["target_tasks_per_family"] > c["semantically_unique_count"]:
        raise ValueError("combinatorial_catalogue_exhausted")
    if n_fam * c["target_tasks_per_family"] > c["target_pool_count"]:
        raise ValueError("target_pool_cannot_support_nonrepeating_families")
    if n_fam * c["cross_domain_tasks_per_family"] > c["target_pool_count"]:
        raise ValueError("cross_domain_pool_cannot_support_nonrepeating_families")
    return dict(
        real_steps=c["max_authored_steps"],
        imagined_transitions=c["max_imagined_transitions"],
        outer_updates=c["max_outer_updates"],
    )


def canonicalize_ops(ops: list[str] | tuple[str, ...], domain: str = "list") -> list[str]:
    allowed = LIST_OPS if domain == "list" else ACTION_OPS
    if type(ops) not in (list, tuple) or not 1 <= len(ops) <= 3 or any(o not in allowed for o in ops):
        raise ValueError("experimental_program_ops")
    cur = list(ops)
    changed = True
    while changed:
        changed = False
        nxt: list[str] = []
        i = 0
        while i < len(cur):
            r_cur = OP_TO_ROLE[cur[i]]
            if i + 1 < len(cur):
                r_nxt = OP_TO_ROLE[cur[i + 1]]
                if r_cur == r_nxt and r_cur in INVOLUTION_ROLES:
                    i += 2
                    changed = True
                    continue
                if r_cur == r_nxt and r_cur in IDEMPOTENT_ROLES:
                    nxt.append(cur[i])
                    i += 2
                    changed = True
                    continue
                if frozenset((r_cur, r_nxt)) in COMMUTATIVE_ROLE_PAIRS and OP_TO_SOURCE_OP[cur[i]] > OP_TO_SOURCE_OP[cur[i + 1]]:
                    nxt.append(cur[i + 1])
                    nxt.append(cur[i])
                    i += 2
                    changed = True
                    continue
            nxt.append(cur[i])
            i += 1
        cur = nxt
    return cur


def canonical_program(p: dict[str, Any]) -> dict[str, Any]:
    if type(p) is not dict or set(p) != {"schema", "ops"}:
        raise ValueError("typed_experimental_program")
    schema = p["schema"]
    if schema not in ("list", "action_token_sequence"):
        raise ValueError("experimental_domain_schema")
    domain = "list" if schema == "list" else "action"
    return dict(schema=schema, ops=canonicalize_ops(p["ops"], domain=domain))


def canonical_signature(p: dict[str, Any]) -> str:
    return canonical(canonical_program(p))


def frozen_hashes(root: str | Path) -> dict[str, str]:
    root = Path(root).resolve()
    return {k: hashlib.sha256((root / k).read_bytes()).hexdigest() for k in sa.FROZEN}


def run_list_program(p: dict[str, Any], x: list[int]) -> list[int]:
    if type(p) is not dict or p.get("schema") != "list":
        raise ValueError("list_program_required")
    v = ir.value("list", x)
    for op in p["ops"]:
        if op not in LIST_OPS:
            raise ValueError("unknown_list_primitive")
        v = ir.run(dict(schema="list", ops=[op]), v)
    return v


def valid_action_sequence(seq: Any) -> list[dict[str, Any]]:
    if type(seq) is not list or len(seq) > 16:
        raise ValueError("bounded_action_sequence_required")
    out = []
    for item in seq:
        if (
            type(item) is not dict
            or set(item) != {"token", "mag"}
            or item["token"] not in ACTION_TOKENS
            or type(item["mag"]) is not int
            or not -64 <= item["mag"] <= 64
        ):
            raise ValueError("typed_action_token_required")
        out.append(dict(token=item["token"], mag=int(item["mag"])))
    return out


def step_action(op: str, seq: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
    if op == "filter_even_mag":
        return [dict(item) for item in seq if item["mag"] % 2 == 0]
    raise ValueError("unknown_action_primitive")


def run_action_program(p: dict[str, Any], seq: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if type(p) is not dict or p.get("schema") != "action_token_sequence":
        raise ValueError("action_program_required")
    v = valid_action_sequence(seq)
    for op in p["ops"]:
        if op not in ACTION_OPS:
            raise ValueError("unknown_action_primitive")
        v = step_action(op, v)
    return v


def run_program(p: dict[str, Any], x: Any) -> Any:
    if p.get("schema") == "list":
        return run_list_program(p, x)
    if p.get("schema") == "action_token_sequence":
        return run_action_program(p, x)
    raise ValueError("unsupported_program_schema")


def probe_domain() -> list[list[int]]:
    alphabet = (-2, -1, 0, 1, 2)
    probes: list[list[int]] = []
    for length in range(5):
        for seq in it.product(alphabet, repeat=length):
            probes.append(list(seq))
    if len(probes) != 781:
        raise ValueError("probe_domain_count")
    return probes


def action_probe_domain() -> list[list[dict[str, Any]]]:
    token_for_val = {-2: "D", -1: "L", 0: "R", 1: "U", 2: "D"}
    probes: list[list[dict[str, Any]]] = []
    for lst in probe_domain():
        probes.append([dict(token=token_for_val[v], mag=v) for v in lst])
    return probes


def semantic_behavior_hash(p: dict[str, Any], probes: list[Any]) -> str:
    pairs = [[x, run_program(p, x)] for x in probes]
    return hashlib.sha256(canonical(pairs).encode("utf-8")).hexdigest()


def verify_commutation_identities(probes: list[list[int]]) -> dict[str, Any]:
    checked_pairs = []
    for pair in sorted(
        (tuple(sorted( (a, b) )) for a in LIST_OPS for b in LIST_OPS if frozenset((OP_TO_ROLE[a], OP_TO_ROLE[b])) in COMMUTATIVE_ROLE_PAIRS)
    ):
        a, b = pair
        p1 = dict(schema="list", ops=[a, b])
        p2 = dict(schema="list", ops=[b, a])
        for x in probes:
            if run_list_program(p1, x) != run_list_program(p2, x):
                raise ValueError(f"invalid_commutation:{a}:{b}")
        checked_pairs.append([a, b])
    for op in ("sort", "unique", "even"):
        p1 = dict(schema="list", ops=[op, op])
        p2 = dict(schema="list", ops=[op])
        for x in probes:
            if run_list_program(p1, x) != run_list_program(p2, x):
                raise ValueError(f"invalid_idempotence:{op}")
    p_rev2 = dict(schema="list", ops=["reverse", "reverse"])
    for x in probes:
        if run_list_program(p_rev2, x) != list(x):
            raise ValueError("invalid_reverse_involution")
    return dict(
        probe_count=len(probes),
        verified_commutative_pairs=checked_pairs,
        verified_idempotent_ops=["sort", "unique", "even"],
        verified_involution="reverse",
    )


def build_catalogue(schema: str = "list") -> dict[str, Any]:
    ops_vocab = LIST_OPS if schema == "list" else ACTION_OPS
    probes = probe_domain() if schema == "list" else action_probe_domain()
    raw_records = []
    canonical_by_sig: dict[str, dict[str, Any]] = {}
    semantic_by_sig: dict[str, str] = {}

    for length in (1, 2, 3):
        for seq in it.product(ops_vocab, repeat=length):
            raw_prog = dict(schema=schema, ops=list(seq))
            canon_prog = canonical_program(raw_prog)
            sig = canonical(canon_prog)
            sem_hash = semantic_behavior_hash(raw_prog, probes)
            raw_records.append(dict(
                raw_program=raw_prog,
                canonical_program=canon_prog,
                canonical_signature=sig,
                semantic_hash=sem_hash,
            ))
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
        key = (len(item["canonical_program"]["ops"]), tuple(OP_TO_SOURCE_OP[o] for o in item["canonical_program"]["ops"]), sig)
        if sh not in by_semantic:
            by_semantic[sh] = item
        else:
            prev = by_semantic[sh]
            prev_key = (len(prev["canonical_program"]["ops"]), tuple(OP_TO_SOURCE_OP[o] for o in prev["canonical_program"]["ops"]), prev["canonical_signature"])
            if key < prev_key:
                by_semantic[sh] = item

    # Deterministic canonical signature order for flat_catalogue;
    # shortest_program orders by (length, canonical_signature).
    entries = sorted(by_semantic.values(), key=lambda r: r["canonical_signature"])
    catalogue_entries = []
    for idx, item in enumerate(entries):
        ops = item["canonical_program"]["ops"]
        adj_pairs = [[ops[i], ops[i + 1]] for i in range(len(ops) - 1)]
        role_pairs = [(OP_TO_ROLE[ops[i]], OP_TO_ROLE[ops[i + 1]]) for i in range(len(ops) - 1)]
        is_target = any(rp in HOLDOUT_ROLE_PAIRS for rp in role_pairs)
        catalogue_entries.append(dict(
            id=idx,
            raw_program=item["raw_program"],
            canonical_program=item["canonical_program"],
            canonical_signature=item["canonical_signature"],
            semantic_hash=item["semantic_hash"],
            length=len(ops),
            adjacent_pairs=adj_pairs,
            role_adjacent_pairs=[list(rp) for rp in role_pairs],
            partition="target" if is_target else "source",
        ))

    source_entries = [e for e in catalogue_entries if e["partition"] == "source"]
    target_entries = [e for e in catalogue_entries if e["partition"] == "target"]
    if len(raw_records) != 155 or len(canonical_by_sig) != 68 or len(catalogue_entries) != 41:
        raise ValueError("unexpected_catalogue_combinatorics")
    if len(source_entries) != 17 or len(target_entries) != 24:
        raise ValueError("unexpected_partition_counts")

    proof_hash = digest(dict(
        schema=schema,
        raw_count=len(raw_records),
        canonical_count=len(canonical_by_sig),
        unique_count=len(catalogue_entries),
        signatures=[e["canonical_signature"] for e in catalogue_entries],
        semantic_hashes=[e["semantic_hash"] for e in catalogue_entries],
    ))
    return dict(
        schema=schema,
        raw_count=len(raw_records),
        canonical_count=len(canonical_by_sig),
        unique_count=len(catalogue_entries),
        proof_sha256=proof_hash,
        entries=catalogue_entries,
        source_ids=[e["id"] for e in source_entries],
        target_ids=[e["id"] for e in target_entries],
    )


def verify_partition_invariants(list_cat: dict[str, Any], action_cat: dict[str, Any]) -> dict[str, Any]:
    entries = list_cat["entries"]
    src = [e for e in entries if e["partition"] == "source"]
    tgt = [e for e in entries if e["partition"] == "target"]

    src_sigs = {e["canonical_signature"] for e in src}
    tgt_sigs = {e["canonical_signature"] for e in tgt}
    src_hashes = {e["semantic_hash"] for e in src}
    tgt_hashes = {e["semantic_hash"] for e in tgt}

    if src_sigs & tgt_sigs:
        raise ValueError("canonical_overlap_detected")
    if src_hashes & tgt_hashes:
        raise ValueError("semantic_overlap_detected")

    src_primitives = {op for e in src for op in e["canonical_program"]["ops"]}
    tgt_primitives = {op for e in tgt for op in e["canonical_program"]["ops"]}
    if not tgt_primitives <= src_primitives or src_primitives != set(LIST_OPS):
        raise ValueError("missing_source_primitive_coverage")

    src_pairs = {tuple(pair) for e in src for pair in e["adjacent_pairs"]}
    src_macros = {tuple(e["canonical_program"]["ops"]) for e in src}
    for e in tgt:
        ops = tuple(e["canonical_program"]["ops"])
        if len(ops) < 2 or ops in src_macros:
            raise ValueError("target_not_novel_composition")
        pairs = [tuple(p) for p in e["adjacent_pairs"]]
        if not any(p not in src_pairs for p in pairs):
            raise ValueError("target_missing_unseen_adjacent_pair")

    act_sigs = {e["canonical_signature"] for e in action_cat["entries"]}
    act_hashes = {e["semantic_hash"] for e in action_cat["entries"]}
    if (src_sigs | tgt_sigs) & act_sigs or (src_hashes | tgt_hashes) & act_hashes:
        raise ValueError("cross_domain_signature_or_hash_overlap")

    return dict(
        canonical_disjoint=True,
        semantic_disjoint=True,
        primitive_coverage=sorted(src_primitives),
        source_unique_programs=len(src),
        target_unique_programs=len(tgt),
        source_adjacent_pairs=sorted(list(p) for p in src_pairs),
        holdout_adjacent_pairs=[list(p) for p in HOLDOUT_PAIRS],
    )


def build_family_assignments(c: dict[str, Any], list_cat: dict[str, Any], action_cat: dict[str, Any]) -> list[dict[str, Any]]:
    config_check(c)
    src_entries = [e for e in list_cat["entries"] if e["partition"] == "source"]
    tgt_entries = [e for e in list_cat["entries"] if e["partition"] == "target"]
    act_tgt_entries = [e for e in action_cat["entries"] if e["partition"] == "target"]

    rng = random.Random(c["assignment_seed"])
    target_order = [e["id"] for e in tgt_entries]
    rng.shuffle(target_order)

    cross_order = [e["id"] for e in act_tgt_entries]
    rng.shuffle(cross_order)

    src_len1 = [e["id"] for e in src_entries if e["length"] == 1]
    src_multi = [e["id"] for e in src_entries if e["length"] >= 2]

    families = []
    t_per_fam = c["target_tasks_per_family"]
    x_per_fam = c["cross_domain_tasks_per_family"]
    r_per_fam = c["retention_tasks_per_family"]

    for fi, fam_seed in enumerate(c["families"]):
        frng = random.Random(fam_seed)
        # 16 solved source tasks: all 12 multi-step source compositions + 4 length-1 source programs
        # (shuffled deterministically by fam_seed; all 5 primitives appear in multi-step source programs)
        chosen_len1 = list(src_len1)
        frng.shuffle(chosen_len1)
        source_ids = list(src_multi) + chosen_len1[: c["source_tasks_per_family"] - len(src_multi)]
        frng.shuffle(source_ids)

        # Verify all 5 primitives appear in this family's source tasks
        fam_prims = {
            op
            for pid in source_ids
            for op in list_cat["entries"][pid]["canonical_program"]["ops"]
        }
        if fam_prims != set(LIST_OPS):
            raise ValueError("family_source_primitive_coverage")

        # 4 distinct old-source retention tasks (2 multi-step + 2 single-step from source_ids)
        ret_multi = [pid for pid in source_ids if list_cat["entries"][pid]["length"] >= 2][:2]
        ret_single = [pid for pid in source_ids if list_cat["entries"][pid]["length"] == 1][:2]
        retention_ids = ret_multi + ret_single
        if len(set(retention_ids)) != r_per_fam:
            raise ValueError("retention_task_count_mismatch")

        fam_targets = target_order[fi * t_per_fam : (fi + 1) * t_per_fam]
        fam_cross = cross_order[fi * x_per_fam : (fi + 1) * x_per_fam]
        families.append(dict(
            family_index=fi,
            family_seed=fam_seed,
            source_program_ids=source_ids,
            target_program_ids=fam_targets,
            retention_program_ids=retention_ids,
            cross_domain_program_ids=fam_cross,
        ))

    all_targets = [pid for f in families for pid in f["target_program_ids"]]
    all_cross = [pid for f in families for pid in f["cross_domain_program_ids"]]
    if len(all_targets) != 24 or len(set(all_targets)) != 24:
        raise ValueError("target_programs_repeated_or_incomplete")
    if len(all_cross) != 24 or len(set(all_cross)) != 24:
        raise ValueError("cross_domain_programs_repeated_or_incomplete")
    return families


def _candidate_list_inputs(task_seed: int) -> list[list[int]]:
    rng = random.Random(task_seed)
    base_patterns = [
        [3, 1, 3, -2, 0],
        [4, -1, 2, 4, 1],
        [2, 5, 2, -3, 0, 1],
        [-4, 3, -4, 2, 1],
        [5, 0, -2, 5, 3, -1],
        [1, 6, 1, -3, 4, 2],
        [3, -5, 2, 3, 0, 4],
        [-2, 4, -1, -2, 3, 5],
        [6, 2, 6, -4, 1, 0],
        [0, -3, 5, 0, 2, -1],
        [4, 1, -3, 4, 2, 0],
        [-5, 2, -5, 1, 4, 3],
    ]
    shift = (task_seed % 7) - 3
    pool: list[list[int]] = []
    for pat in base_patterns:
        cand = [max(-12, min(12, v + shift)) for v in pat]
        pool.append(cand)
    for _ in range(96):
        length = rng.randint(3, 6)
        vals = [rng.randint(-9, 9) for _ in range(length)]
        if len(vals) >= 3 and rng.random() < 0.65:
            vals[0] = vals[-1]
        pool.append(vals)
    return pool


def generate_task_data(
    task_seed: int,
    program_entry: dict[str, Any],
    used_hashes: set[str],
    n_teach: int = 8,
    n_assess: int = 16,
    n_counter: int = 2,
) -> dict[str, Any]:
    schema = program_entry["canonical_program"]["schema"]
    prog = program_entry["canonical_program"]
    raw_pool = _candidate_list_inputs(task_seed)
    token_cycle = ACTION_TOKENS

    fresh_inputs: list[Any] = []
    for idx, lst in enumerate(raw_pool):
        if schema == "list":
            inp: Any = lst
        else:
            inp = [
                dict(token=token_cycle[(abs(v) + idx + j) % 4], mag=v)
                for j, v in enumerate(lst)
            ]
        h = digest(inp)
        if h not in used_hashes:
            used_hashes.add(h)
            fresh_inputs.append(inp)
            if len(fresh_inputs) >= n_teach + n_assess + n_counter:
                break

    if len(fresh_inputs) < n_teach + n_assess + n_counter:
        raise ValueError("insufficient_disjoint_task_inputs")

    teach_inputs = fresh_inputs[:n_teach]
    assess_inputs = fresh_inputs[n_teach : n_teach + n_assess]
    counter_inputs = fresh_inputs[n_teach + n_assess : n_teach + n_assess + n_counter]

    teaching = [dict(input=x, output=run_program(prog, x), input_hash=digest(x)) for x in teach_inputs]
    assessment = [dict(input=x, output=run_program(prog, x), input_hash=digest(x)) for x in assess_inputs]
    counterexamples = [dict(input=x, output=run_program(prog, x), input_hash=digest(x)) for x in counter_inputs]

    return dict(
        task_seed=task_seed,
        program_id=program_entry["id"],
        canonical_program=prog,
        canonical_signature=program_entry["canonical_signature"],
        semantic_hash=program_entry["semantic_hash"],
        teaching=teaching,
        assessment=assessment,
        counterexamples=counterexamples,
    )


def structural_features(
    canonical_prog: dict[str, Any],
    unseen_category_transitions: set[tuple[str, str]],
) -> list[float]:
    """23 public abstract structural features. Zero concrete operator names,
    zero program hashes, zero target identities or target outputs."""
    ops = canonical_prog["ops"]
    length = len(ops)
    roles = [OP_TO_ROLE[op] for op in ops]
    cats = [OP_TO_CATEGORY[op] for op in ops]

    one_hot_len = [1.0 if length == k else 0.0 for k in (1, 2, 3)]
    cat_fracs = [cats.count(c) / length for c in CAT_NAMES]
    repeated = float(length - len(set(roles)))
    idempotent = float(sum(1 for r in roles if r in IDEMPOTENT_ROLES))
    reversible = float(sum(1 for r in roles if r in INVOLUTION_ROLES))
    card_count = float(cats.count("card"))
    point_count = float(cats.count("point"))
    perm_count = float(cats.count("perm"))

    transitions = [
        float(sum(1 for i in range(length - 1) if (cats[i], cats[i + 1]) == (c1, c2)))
        for c1 in CAT_NAMES
        for c2 in CAT_NAMES
    ]
    has_unseen = 1.0 if any((cats[i], cats[i + 1]) in unseen_category_transitions for i in range(length - 1)) else 0.0

    vec = (
        [1.0]
        + one_hot_len
        + cat_fracs
        + [repeated, idempotent, reversible, card_count, point_count, perm_count]
        + transitions
        + [has_unseen]
    )
    if len(vec) != 23:
        raise ValueError("feature_dimension_mismatch")
    return vec


def fit_source_models(
    source_tasks: list[dict[str, Any]],
    catalogue: dict[str, Any],
    c: dict[str, Any],
) -> dict[str, Any]:
    """Fit all source-informed priors exclusively on the family's 16 solved source tasks."""
    entries = catalogue["entries"]
    source_entries = [e for e in entries if e["partition"] == "source"]

    # 1. Empirical counts in the 16 solved source tasks
    prog_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {v["role"]: 0 for v in SUPPLIED_ROLE_MAPPING.values()}
    cat_counts: dict[str, int] = {cat: 0 for cat in CAT_NAMES}
    len_counts: dict[int, int] = {1: 0, 2: 0, 3: 0}
    trans_counts: dict[tuple[str, str], int] = {(c1, c2): 0 for c1 in CAT_NAMES for c2 in CAT_NAMES}

    for stask in source_tasks:
        sig = stask["canonical_signature"]
        prog_counts[sig] = prog_counts.get(sig, 0) + 1
        ops = stask["canonical_program"]["ops"]
        len_counts[len(ops)] += 1
        cats = [OP_TO_CATEGORY[op] for op in ops]
        for op, cat in zip(ops, cats):
            role_counts[OP_TO_ROLE[op]] += 1
            cat_counts[cat] += 1
        for i in range(len(cats) - 1):
            trans_counts[(cats[i], cats[i + 1])] += 1

    unseen_transitions = {pair for pair, cnt in trans_counts.items() if cnt == 0}
    total_trans = sum(trans_counts.values())
    trans_probs = {
        pair: (cnt + 1.0) / (total_trans + 9.0)
        for pair, cnt in trans_counts.items()
    }

    # 2. Source-only ridge structural prior fitted strictly on the 17 source programs
    x_rows = []
    y_vals = []
    n_src_episodes = len(source_tasks)
    for e in source_entries:
        phi = structural_features(e["canonical_program"], unseen_transitions)
        ops = e["canonical_program"]["ops"]
        cats = [OP_TO_CATEGORY[op] for op in ops]
        occ_rate = prog_counts.get(e["canonical_signature"], 0) / max(1, n_src_episodes)
        if len(cats) >= 2:
            mean_trans_prob = sum(trans_probs[(cats[i], cats[i + 1])] for i in range(len(cats) - 1)) / (len(cats) - 1)
            comp_bonus = 0.5 * mean_trans_prob
        else:
            comp_bonus = 0.0
        y_p = occ_rate + comp_bonus
        x_rows.append(phi)
        y_vals.append(y_p)

    X = np.asarray(x_rows, dtype=float)
    Y = np.asarray(y_vals, dtype=float)
    scale = np.sqrt((X * X).mean(axis=0))
    scale[scale < 1e-8] = 1.0
    Z = X / scale
    lam = float(c["ridge_lambda"])
    w_star = np.linalg.solve(Z.T @ Z + lam * np.eye(X.shape[1]), Z.T @ Y)

    # 3. Laplace-smoothed operator-role probabilities
    total_roles = sum(role_counts.values())
    pseudo = float(c["laplace_pseudocount"])
    role_log_probs = {
        r: math.log((cnt + pseudo) / (total_roles + 5.0 * pseudo))
        for r, cnt in role_counts.items()
    }

    # 4. Dirichlet-smoothed Bayesian grammar prior over length, categories, and transitions
    dir_alpha = float(c["dirichlet_pseudocount"])
    len_log_probs = {
        length: math.log((cnt + dir_alpha) / (n_src_episodes + 3.0 * dir_alpha))
        for length, cnt in len_counts.items()
    }
    total_cats = sum(cat_counts.values())
    cat_log_probs = {
        cat: math.log((cnt + dir_alpha) / (total_cats + 3.0 * dir_alpha))
        for cat, cnt in cat_counts.items()
    }
    cond_trans_log_probs: dict[str, dict[str, float]] = {}
    for c1 in CAT_NAMES:
        row_sum = sum(trans_counts[(c1, c2)] for c2 in CAT_NAMES)
        cond_trans_log_probs[c1] = {
            c2: math.log((trans_counts[(c1, c2)] + dir_alpha) / (row_sum + 3.0 * dir_alpha))
            for c2 in CAT_NAMES
        }

    model_payload = dict(
        scale=[round(float(v), 12) for v in scale.tolist()],
        w_star=[round(float(v), 12) for v in w_star.tolist()],
        unseen_category_transitions=[list(p) for p in sorted(unseen_transitions)],
        source_program_counts=prog_counts,
        role_counts=role_counts,
        role_log_probs={k: round(v, 12) for k, v in role_log_probs.items()},
        bayesian_prior=dict(
            len_log_probs={str(k): round(v, 12) for k, v in len_log_probs.items()},
            cat_log_probs={k: round(v, 12) for k, v in cat_log_probs.items()},
            cond_trans_log_probs={
                c1: {c2: round(val, 12) for c2, val in row.items()}
                for c1, row in cond_trans_log_probs.items()
            },
        ),
        training_rows=len(source_entries),
        feature_dimension=int(X.shape[1]),
        parameter_count=int(X.shape[1]),
    )
    model_payload["serialized_bytes"] = len(canonical(model_payload).encode("utf-8"))
    return model_payload


def rank_catalogue(
    method: str,
    catalogue: dict[str, Any],
    fitted_model: dict[str, Any] | None,
) -> tuple[list[int], dict[str, float], dict[str, int]]:
    """Return (ordered_entry_ids, score_by_sig, construction_work) for deterministic methods."""
    entries = catalogue["entries"]
    scores: dict[str, float] = {}
    work = dict(
        source_programs_read=0,
        feature_scalars=0,
        ridge_fits=0,
        catalogue_Rank_scores=len(entries),
    )

    if method in ("flat_catalogue", "scratch_flat"):
        ordered = sorted(entries, key=lambda e: e["canonical_signature"])
        for rank_idx, e in enumerate(ordered):
            scores[e["canonical_signature"]] = float(-rank_idx)
        return [e["id"] for e in ordered], scores, work

    if method == "shortest_program":
        ordered = sorted(entries, key=lambda e: (e["length"], e["canonical_signature"]))
        for rank_idx, e in enumerate(ordered):
            scores[e["canonical_signature"]] = float(-e["length"] * 100 - rank_idx)
        return [e["id"] for e in ordered], scores, work

    if fitted_model is None:
        raise ValueError(f"fitted_model_required_for:{method}")

    if method in ("structural_meta_prior", "transferred_structural_prior"):
        scale = np.asarray(fitted_model["scale"], dtype=float)
        w_star = np.asarray(fitted_model["w_star"], dtype=float)
        unseen = {tuple(p) for p in fitted_model["unseen_category_transitions"]}
        work["source_programs_read"] = 16
        work["feature_scalars"] = (17 + len(entries)) * len(scale)
        work["ridge_fits"] = 1
        for e in entries:
            phi = np.asarray(structural_features(e["canonical_program"], unseen), dtype=float)
            scores[e["canonical_signature"]] = round(float((phi / scale) @ w_star), 12)
        ordered = sorted(
            entries,
            key=lambda e: (-scores[e["canonical_signature"]], e["canonical_signature"]),
        )
        return [e["id"] for e in ordered], scores, work

    if method in ("operator_frequency", "target_operator_frequency"):
        work["source_programs_read"] = 16
        rlp = fitted_model["role_log_probs"]
        for e in entries:
            ops = e["canonical_program"]["ops"]
            scores[e["canonical_signature"]] = round(sum(rlp[OP_TO_ROLE[o]] for o in ops), 12)
        ordered = sorted(
            entries,
            key=lambda e: (-scores[e["canonical_signature"]], e["canonical_signature"]),
        )
        return [e["id"] for e in ordered], scores, work

    if method == "exact_macro_cache":
        work["source_programs_read"] = 16
        counts = fitted_model["source_program_counts"]
        for e in entries:
            sig = e["canonical_signature"]
            c_val = counts.get(sig, 0)
            scores[sig] = round(float(1000 * c_val - e["length"]), 12)
        ordered = sorted(
            entries,
            key=lambda e: (-counts.get(e["canonical_signature"], 0), e["length"], e["canonical_signature"]),
        )
        return [e["id"] for e in ordered], scores, work

    if method == "bayesian_model_based":
        work["source_programs_read"] = 16
        bp = fitted_model["bayesian_prior"]
        len_lp = bp["len_log_probs"]
        cat_lp = bp["cat_log_probs"]
        trans_lp = bp["cond_trans_log_probs"]
        for e in entries:
            ops = e["canonical_program"]["ops"]
            cats = [OP_TO_CATEGORY[o] for o in ops]
            lp = float(len_lp[str(len(ops))])
            lp += sum(float(cat_lp[c]) for c in cats)
            lp += sum(float(trans_lp[cats[i]][cats[i + 1]]) for i in range(len(cats) - 1))
            scores[e["canonical_signature"]] = round(lp, 12)
        ordered = sorted(
            entries,
            key=lambda e: (-scores[e["canonical_signature"]], e["canonical_signature"]),
        )
        return [e["id"] for e in ordered], scores, work

    raise ValueError(f"unsupported_ranking_method:{method}")


def evaluate_task_under_ordering(
    task: dict[str, Any],
    catalogue: dict[str, Any],
    ordered_ids: list[int],
    construction_eval_share: float,
) -> dict[str, Any]:
    """Evaluate a fixed candidate ordering across teaching prefixes 1..8 and budgets {1,2,4,8}."""
    entries = catalogue["entries"]
    teach = task["teaching"]
    assess = task["assessment"]
    target_hash = task["semantic_hash"]

    # Precompute teaching match vector for each candidate over the 8 teaching examples
    # and held-out accuracy for each candidate
    prefix_consistent_ids: dict[int, list[int]] = {}
    selected_by_k: dict[int, dict[str, Any]] = {}
    evals_by_k: dict[int, int] = {}
    target_rank_by_k: dict[int, int] = {}

    for k in range(1, len(teach) + 1):
        prefix = teach[:k]
        consistent: list[int] = []
        first_evals = None
        for pos, cid in enumerate(ordered_ids, 1):
            prog = entries[cid]["canonical_program"]
            ok = all(run_program(prog, ex["input"]) == ex["output"] for ex in prefix)
            if ok:
                consistent.append(cid)
                if first_evals is None:
                    first_evals = pos
        if not consistent or first_evals is None:
            raise ValueError("empty_version_space_on_valid_target")
        prefix_consistent_ids[k] = consistent
        selected_by_k[k] = entries[consistent[0]]
        evals_by_k[k] = first_evals
        target_ranks = [ idx for idx, cid in enumerate(consistent, 1) if entries[cid]["semantic_hash"] == target_hash ]
        if not target_ranks:
            raise ValueError("target_absent_from_version_space")
        target_rank_by_k[k] = target_ranks[0]

    # Minimum examples k in 1..8 after which selected candidate is semantically equal to target for all k' >= k
    q_semantic = 9
    for k in range(1, len(teach) + 1):
        if all(selected_by_k[kp]["semantic_hash"] == target_hash for kp in range(k, len(teach) + 1)):
            q_semantic = k
            break

    q_version_space = 9
    for k in range(1, len(teach) + 1):
        if len(prefix_consistent_ids[k]) == 1:
            q_version_space = k
            break

    budgets_out: dict[str, Any] = {}
    for b in BUDGETS:
        sel = selected_by_k[b]
        sel_prog = sel["canonical_program"]
        correct = sum(1 for ex in assess if run_program(sel_prog, ex["input"]) == ex["output"])
        acc = correct / len(assess)
        search_ev = float(evals_by_k[b])
        budgets_out[str(b)] = dict(
            selected_program_id=sel["id"],
            selected_canonical_signature=sel["canonical_signature"],
            selected_semantic_hash=sel["semantic_hash"],
            semantic_match=bool(sel["semantic_hash"] == target_hash),
            candidate_evaluations=search_ev,
            construction_inclusive_evaluations=round(search_ev + construction_eval_share, 8),
            version_space_size=len(prefix_consistent_ids[b]),
            target_program_rank=float(target_rank_by_k[b]),
            held_out_accuracy=round(acc, 8),
            uniquely_identified=bool(len(prefix_consistent_ids[b]) == 1),
        )

    return dict(
        budgets=budgets_out,
        examples_for_semantic_id=float(q_semantic),
        examples_for_unique_version_space=float(q_version_space),
    )


def evaluate_random_expectation(
    task: dict[str, Any],
    catalogue: dict[str, Any],
    perm_seeds: list[int],
) -> dict[str, Any]:
    """Compute exact expectation over the 64 preregistered random permutations."""
    base_ids = [e["id"] for e in catalogue["entries"]]
    runs = []
    for pseed in perm_seeds:
        order = list(base_ids)
        random.Random(pseed).shuffle(order)
        runs.append(evaluate_task_under_ordering(task, catalogue, order, construction_eval_share=0.0))

    n_perms = len(runs)
    budgets_out: dict[str, Any] = {}
    for b in BUDGETS:
        b_key = str(b)
        mean_evals = sum(r["budgets"][b_key]["candidate_evaluations"] for r in runs) / n_perms
        mean_acc = sum(r["budgets"][b_key]["held_out_accuracy"] for r in runs) / n_perms
        mean_rank = sum(r["budgets"][b_key]["target_program_rank"] for r in runs) / n_perms
        v_size = runs[0]["budgets"][b_key]["version_space_size"]
        budgets_out[b_key] = dict(
            selected_program_id=runs[0]["budgets"][b_key]["selected_program_id"],
            selected_canonical_signature="random_permutation_expectation_64",
            selected_semantic_hash="random_permutation_expectation_64",
            semantic_match=bool(mean_rank == 1.0),
            candidate_evaluations=round(mean_evals, 8),
            construction_inclusive_evaluations=round(mean_evals, 8),
            version_space_size=v_size,
            target_program_rank=round(mean_rank, 8),
            held_out_accuracy=round(mean_acc, 8),
            uniquely_identified=bool(v_size == 1),
        )
    return dict(
        budgets=budgets_out,
        examples_for_semantic_id=round(sum(r["examples_for_semantic_id"] for r in runs) / n_perms, 8),
        examples_for_unique_version_space=runs[0]["examples_for_unique_version_space"],
        permutation_count=n_perms,
    )


def paired_t_interval(baseline_vals: list[float], candidate_vals: list[float]) -> dict[str, Any]:
    if len(baseline_vals) != 8 or len(candidate_vals) != 8:
        raise ValueError("eight_families_required_for_paired_interval")
    diffs = [b - c for b, c in zip(baseline_vals, candidate_vals)]
    mean_d = sum(diffs) / 8.0
    sd = math.sqrt(sum((d - mean_d) ** 2 for d in diffs) / 7.0)
    half = T_CRITICAL_DF7 * sd / math.sqrt(8.0)
    return dict(
        n=8,
        df=7,
        mean=round(mean_d, 8),
        sd=round(sd, 8),
        low=round(mean_d - half, 8),
        high=round(mean_d + half, 8),
        family_differences=[round(d, 8) for d in diffs],
    )


def evaluate_disjoint_meta_artifact(
    raw_artifact: dict[str, Any],
    locked_protocol: str,
    locked_config: dict[str, Any],
) -> dict[str, Any]:
    """Strict artifact-derived scientific acceptance gate (Section 14).

    Rejects caller-supplied summary arrays, incomplete grids, source/target overlap,
    changed program order after answers, target leakage, inconsistent cost totals,
    mismatched hashes, duplicate family IDs, or nonfinite values.
    Recomputes all metrics, retention, transfer, intervals, and gates from raw records.
    """
    if type(raw_artifact) is not dict:
        raise ValueError("artifact_dict_required")
    forbidden_caller_keys = {"retention_scores", "transfer_scores", "caller_summary", "override_gates"}
    if set(raw_artifact) & forbidden_caller_keys:
        raise ValueError("caller_supplied_summary_scores_rejected")
    digest(raw_artifact)  # Fails closed on any NaN or Inf anywhere in raw_artifact

    config_check(locked_config)
    if type(locked_protocol) is not str or len(locked_protocol.strip()) < 200:
        raise ValueError("locked_protocol_text_required")
    if digest(raw_artifact.get("config")) != digest(locked_config):
        raise ValueError("artifact_config_mismatch")
    expected_proto_sha = hashlib.sha256(locked_protocol.encode("utf-8")).hexdigest()
    if raw_artifact.get("protocol_sha256") != expected_proto_sha:
        raise ValueError("artifact_protocol_hash_mismatch")

    list_cat = build_catalogue("list")
    action_cat = build_catalogue("action_token_sequence")
    part_check = verify_partition_invariants(list_cat, action_cat)
    if raw_artifact.get("catalogue_proof_sha256") != list_cat["proof_sha256"]:
        raise ValueError("list_catalogue_proof_mismatch")
    if raw_artifact.get("action_catalogue_proof_sha256") != action_cat["proof_sha256"]:
        raise ValueError("action_catalogue_proof_mismatch")

    families = raw_artifact.get("families")
    if type(families) is not list or len(families) != 8:
        raise ValueError("incomplete_family_grid")

    seen_family_seeds: set[int] = set()
    seen_target_sigs: set[str] = set()
    seen_cross_sigs: set[str] = set()
    source_sigs_global = {
        list_cat["entries"][i]["canonical_signature"] for i in list_cat["source_ids"]
    }
    source_hashes_global = {
        list_cat["entries"][i]["semantic_hash"] for i in list_cat["source_ids"]
    }

    fam_acc: dict[str, list[float]] = {m: [] for m in METHODS}
    fam_evals: dict[str, list[float]] = {m: [] for m in METHODS}
    fam_search_only: dict[str, list[float]] = {m: [] for m in METHODS}
    fam_q: dict[str, list[float]] = {m: [] for m in METHODS}
    fam_b8_acc: dict[str, list[float]] = {m: [] for m in METHODS}

    fam_ret_before_acc: dict[str, list[float]] = {m: [] for m in METHODS}
    fam_ret_after_acc: dict[str, list[float]] = {m: [] for m in METHODS}
    fam_ret_before_cost: dict[str, list[float]] = {m: [] for m in METHODS}
    fam_ret_after_cost: dict[str, list[float]] = {m: [] for m in METHODS}

    fam_xd_acc: dict[str, list[float]] = {m: [] for m in CROSS_DOMAIN_METHODS}
    fam_xd_evals: dict[str, list[float]] = {m: [] for m in CROSS_DOMAIN_METHODS}

    total_compute_by_method: dict[str, dict[str, float]] = {
        m: dict(
            source_fit_units=0.0,
            feature_scalars=0.0,
            ridge_fits=0.0,
            catalogue_constructions=0.0,
            search_candidate_evaluations=0.0,
            total_amortized_units=0.0,
        )
        for m in METHODS
    }

    for fi, fam in enumerate(families):
        fseed = fam.get("family_seed")
        if fseed != locked_config["families"][fi] or fseed in seen_family_seeds:
            raise ValueError("invalid_or_duplicate_family_seed")
        seen_family_seeds.add(fseed)

        source_tasks = fam.get("source_tasks")
        target_tasks = fam.get("target_tasks")
        retention_tasks = fam.get("retention_tasks")
        cross_tasks = fam.get("cross_domain_tasks")
        if (
            type(source_tasks) is not list or len(source_tasks) != 16
            or type(target_tasks) is not list or len(target_tasks) != 3
            or type(retention_tasks) is not list or len(retention_tasks) != 4
            or type(cross_tasks) is not list or len(cross_tasks) != 3
        ):
            raise ValueError("incomplete_family_task_counts")

        # Verify input hash disjointness between teaching, target assessment, and retention
        teach_hashes = {ex["input_hash"] for t in target_tasks for ex in t["teaching"]}
        assess_hashes = {ex["input_hash"] for t in target_tasks for ex in t["assessment"]}
        ret_hashes = {
            ex["input_hash"]
            for t in retention_tasks
            for ex in (t["teaching"] + t["assessment"])
        }
        if (teach_hashes & assess_hashes) or (teach_hashes & ret_hashes) or (assess_hashes & ret_hashes):
            raise ValueError("input_hash_overlap_detected")

        # Re-fit source models from source_tasks only and verify no target leakage
        recomputed_model = fit_source_models(source_tasks, list_cat, locked_config)
        if digest(fam.get("fitted_model")) != digest(recomputed_model):
            raise ValueError("fitted_model_tampered_or_target_leaked")

        # Verify source tasks belong strictly to source pool
        for stask in source_tasks:
            if (
                stask["canonical_signature"] not in source_sigs_global
                or stask["semantic_hash"] not in source_hashes_global
            ):
                raise ValueError("source_task_outside_source_pool")

        # Recompute candidate orderings for all deterministic methods and verify they match
        n_target_evals_in_fam = len(target_tasks) * len(PRIMARY_BUDGETS)
        expected_orderings: dict[str, list[int]] = {}
        method_const_share: dict[str, float] = {}
        for m in METHODS:
            if m == "random_ordering":
                method_const_share[m] = 0.0
                continue
            ord_ids, _, work = rank_catalogue(m, list_cat, recomputed_model)
            if fam.get("candidate_orderings", {}).get(m) != ord_ids:
                raise ValueError(f"candidate_ordering_tampered:{m}")
            expected_orderings[m] = ord_ids
            # Construction cost share in candidate-program units across the family's target evaluations
            const_units = 1.5 if m == "structural_meta_prior" else (1.0 if m in ("operator_frequency", "exact_macro_cache", "bayesian_model_based") else 0.0)
            method_const_share[m] = const_units / n_target_evals_in_fam
            total_compute_by_method[m]["source_fit_units"] += float(work["source_programs_read"])
            total_compute_by_method[m]["feature_scalars"] += float(work["feature_scalars"])
            total_compute_by_method[m]["ridge_fits"] += float(work["ridge_fits"])
            total_compute_by_method[m]["catalogue_constructions"] += 1.0

        p_seeds = locked_config["random_permutation_seeds"][fi * 64 : (fi + 1) * 64]

        # Verify in-domain target tasks
        m_acc_list: dict[str, list[float]] = {m: [] for m in METHODS}
        m_eval_list: dict[str, list[float]] = {m: [] for m in METHODS}
        m_search_list: dict[str, list[float]] = {m: [] for m in METHODS}
        m_q_list: dict[str, list[float]] = {m: [] for m in METHODS}
        m_b8_list: dict[str, list[float]] = {m: [] for m in METHODS}

        for t in target_tasks:
            sig = t["canonical_signature"]
            sh = t["semantic_hash"]
            if sig in source_sigs_global or sh in source_hashes_global:
                raise ValueError("target_overlaps_source_pool")
            if sig in seen_target_sigs:
                raise ValueError("duplicate_target_across_families")
            seen_target_sigs.add(sig)

            if set(t.get("methods", {})) != set(METHODS):
                raise ValueError("missing_method_in_target_task")

            for m in METHODS:
                if m == "random_ordering":
                    expected_res = evaluate_random_expectation(t, list_cat, p_seeds)
                else:
                    expected_res = evaluate_task_under_ordering(
                        t, list_cat, expected_orderings[m], method_const_share[m]
                    )
                recorded_res = t["methods"][m]
                if digest(recorded_res) != digest(expected_res):
                    raise ValueError(f"target_evaluation_mismatch:{m}")
                for b in PRIMARY_BUDGETS:
                    b_row = expected_res["budgets"][str(b)]
                    m_acc_list[m].append(b_row["held_out_accuracy"])
                    m_eval_list[m].append(b_row["construction_inclusive_evaluations"])
                    m_search_list[m].append(b_row["candidate_evaluations"])
                    total_compute_by_method[m]["search_candidate_evaluations"] += b_row["candidate_evaluations"]
                m_q_list[m].append(expected_res["examples_for_semantic_id"])
                m_b8_list[m].append(expected_res["budgets"]["8"]["held_out_accuracy"])

        for m in METHODS:
            fam_acc[m].append(sum(m_acc_list[m]) / len(m_acc_list[m]))
            fam_evals[m].append(sum(m_eval_list[m]) / len(m_eval_list[m]))
            fam_search_only[m].append(sum(m_search_list[m]) / len(m_search_list[m]))
            fam_q[m].append(sum(m_q_list[m]) / len(m_q_list[m]))
            fam_b8_acc[m].append(sum(m_b8_list[m]) / len(m_b8_list[m]))

        # Verify old-source retention episodes (before vs after meta-training)
        flat_ids = expected_orderings["flat_catalogue"]
        ret_b_acc: dict[str, list[float]] = {m: [] for m in METHODS}
        ret_a_acc: dict[str, list[float]] = {m: [] for m in METHODS}
        ret_b_cost: dict[str, list[float]] = {m: [] for m in METHODS}
        ret_a_cost: dict[str, list[float]] = {m: [] for m in METHODS}

        for rtask in retention_tasks:
            if rtask["canonical_signature"] not in source_sigs_global:
                raise ValueError("retention_task_not_in_source_pool")
            expected_before = evaluate_task_under_ordering(rtask, list_cat, flat_ids, 0.0)
            if digest(rtask.get("before_meta_learning")) != digest(expected_before):
                raise ValueError("retention_before_mismatch")
            if set(rtask.get("after_meta_learning", {})) != set(METHODS):
                raise ValueError("missing_method_in_retention_after")
            for m in METHODS:
                expected_after = (
                    evaluate_random_expectation(rtask, list_cat, p_seeds)
                    if m == "random_ordering"
                    else evaluate_task_under_ordering(rtask, list_cat, expected_orderings[m], 0.0)
                )
                if digest(rtask["after_meta_learning"][m]) != digest(expected_after):
                    raise ValueError(f"retention_after_mismatch:{m}")
                for b in PRIMARY_BUDGETS:
                    ret_b_acc[m].append(expected_before["budgets"][str(b)]["held_out_accuracy"])
                    ret_a_acc[m].append(expected_after["budgets"][str(b)]["held_out_accuracy"])
                    ret_b_cost[m].append(expected_before["budgets"][str(b)]["candidate_evaluations"])
                    ret_a_cost[m].append(expected_after["budgets"][str(b)]["candidate_evaluations"])

        for m in METHODS:
            fam_ret_before_acc[m].append(sum(ret_b_acc[m]) / len(ret_b_acc[m]))
            fam_ret_after_acc[m].append(sum(ret_a_acc[m]) / len(ret_a_acc[m]))
            fam_ret_before_cost[m].append(sum(ret_b_cost[m]) / len(ret_b_cost[m]))
            fam_ret_after_cost[m].append(sum(ret_a_cost[m]) / len(ret_a_cost[m]))

        # Verify structural cross-domain transfer episodes
        n_xd_evals_in_fam = len(cross_tasks) * len(PRIMARY_BUDGETS)
        xd_orderings: dict[str, list[int]] = {}
        xd_const_share: dict[str, float] = {}
        for xm in CROSS_DOMAIN_METHODS:
            if xm == "random_ordering":
                xd_const_share[xm] = 0.0
                continue
            ord_ids, _, _ = rank_catalogue(xm, action_cat, recomputed_model)
            xd_orderings[xm] = ord_ids
            const_units = 1.5 if xm == "transferred_structural_prior" else (1.0 if xm in ("target_operator_frequency", "exact_macro_cache", "bayesian_model_based") else 0.0)
            xd_const_share[xm] = const_units / n_xd_evals_in_fam

        xd_acc_list: dict[str, list[float]] = {xm: [] for xm in CROSS_DOMAIN_METHODS}
        xd_eval_list: dict[str, list[float]] = {xm: [] for xm in CROSS_DOMAIN_METHODS}
        for xtask in cross_tasks:
            xsig = xtask["canonical_signature"]
            if xsig in seen_cross_sigs:
                raise ValueError("duplicate_cross_domain_target")
            seen_cross_sigs.add(xsig)
            if set(xtask.get("methods", {})) != set(CROSS_DOMAIN_METHODS):
                raise ValueError("missing_method_in_cross_domain_task")
            for xm in CROSS_DOMAIN_METHODS:
                expected_xres = (
                    evaluate_random_expectation(xtask, action_cat, p_seeds)
                    if xm == "random_ordering"
                    else evaluate_task_under_ordering(xtask, action_cat, xd_orderings[xm], xd_const_share[xm])
                )
                if digest(xtask["methods"][xm]) != digest(expected_xres):
                    raise ValueError(f"cross_domain_evaluation_mismatch:{xm}")
                for b in PRIMARY_BUDGETS:
                    b_row = expected_xres["budgets"][str(b)]
                    xd_acc_list[xm].append(b_row["held_out_accuracy"])
                    xd_eval_list[xm].append(b_row["construction_inclusive_evaluations"])

        for xm in CROSS_DOMAIN_METHODS:
            fam_xd_acc[xm].append(sum(xd_acc_list[xm]) / len(xd_acc_list[xm]))
            fam_xd_evals[xm].append(sum(xd_eval_list[xm]) / len(xd_eval_list[xm]))

    # Aggregate family-level means and paired 95% confidence intervals
    primary_accuracy = {m: round(sum(fam_acc[m]) / 8.0, 8) for m in METHODS}
    primary_evaluations = {m: round(sum(fam_evals[m]) / 8.0, 8) for m in METHODS}
    search_only_evaluations = {m: round(sum(fam_search_only[m]) / 8.0, 8) for m in METHODS}
    mean_examples_q = {m: round(sum(fam_q[m]) / 8.0, 8) for m in METHODS}
    budget8_accuracy = {m: round(sum(fam_b8_acc[m]) / 8.0, 8) for m in METHODS}

    eval_intervals = {
        m: paired_t_interval(fam_evals[m], fam_evals["structural_meta_prior"])
        for m in METHODS
        if m != "structural_meta_prior"
    }
    acc_intervals = {
        m: paired_t_interval(fam_acc["structural_meta_prior"], fam_acc[m])
        for m in METHODS
        if m != "structural_meta_prior"
    }

    # Real retention summary for structural_meta_prior and all methods
    retention_summary: dict[str, Any] = {}
    for m in METHODS:
        b_mean = sum(fam_ret_before_acc[m]) / 8.0
        a_mean = sum(fam_ret_after_acc[m]) / 8.0
        bc_mean = sum(fam_ret_before_cost[m]) / 8.0
        ac_mean = sum(fam_ret_after_cost[m]) / 8.0
        fam_drops = [a - b for a, b in zip(fam_ret_after_acc[m], fam_ret_before_acc[m])]
        retention_summary[m] = dict(
            accuracy_before=round(b_mean, 8),
            accuracy_after=round(a_mean, 8),
            accuracy_retention=round(a_mean - b_mean, 8),
            search_cost_before=round(bc_mean, 8),
            search_cost_after=round(ac_mean, 8),
            search_retention=round((ac_mean - bc_mean) / max(1.0, bc_mean), 8),
            worst_family_accuracy_delta=round(min(fam_drops), 8),
            family_accuracy_after=[round(v, 8) for v in fam_ret_after_acc[m]],
        )

    # Cross-domain summary
    cross_domain_accuracy = {xm: round(sum(fam_xd_acc[xm]) / 8.0, 8) for xm in CROSS_DOMAIN_METHODS}
    cross_domain_evaluations = {xm: round(sum(fam_xd_evals[xm]) / 8.0, 8) for xm in CROSS_DOMAIN_METHODS}
    cross_domain_intervals = {
        xm: paired_t_interval(fam_xd_evals[xm], fam_xd_evals["transferred_structural_prior"])
        for xm in CROSS_DOMAIN_METHODS
        if xm != "transferred_structural_prior"
    }

    # Total amortized compute accounting
    for m in METHODS:
        tc = total_compute_by_method[m]
        tc["total_amortized_units"] = round(
            tc["search_candidate_evaluations"] + tc["source_fit_units"] * 0.75 + tc["ridge_fits"] * 4.0,
            8,
        )

    # Evaluate the 7 Locked Advancement Gates (Section 13)
    gcfg = locked_config["gates"]
    cand = "structural_meta_prior"
    baselines = [m for m in METHODS if m != cand]

    # Gate 1: Integrity
    gate1_passed = bool(
        part_check["canonical_disjoint"]
        and part_check["semantic_disjoint"]
        and len(seen_target_sigs) == 24
        and len(seen_cross_sigs) == 24
    )

    # Gate 2: Held-out quality
    best_baseline_acc = max(primary_accuracy[m] for m in baselines)
    best_acc_baseline_name = max(baselines, key=lambda m: primary_accuracy[m])
    fam_losses_vs_best = sum(
        1 for fi in range(8) if fam_acc[cand][fi] < fam_acc[best_acc_baseline_name][fi] - 1e-12
    )
    worst_fam_loss = min(
        fam_acc[cand][fi] - max(fam_acc[m][fi] for m in baselines) for fi in range(8)
    )
    gate2_passed = bool(
        primary_accuracy[cand] >= best_baseline_acc - gcfg["max_accuracy_deficit_vs_best"]
        and fam_losses_vs_best <= gcfg["max_family_accuracy_losses"]
        and worst_fam_loss >= -gcfg["max_catastrophic_family_drop"]
    )

    # Gate 3: Search efficiency against EVERY simple baseline AND bayesian_model_based
    gate3_comparisons = {}
    for m in SIMPLE_BASELINES + ("bayesian_model_based",):
        rel_imp = (primary_evaluations[m] - primary_evaluations[cand]) / max(1e-9, primary_evaluations[m])
        ci_low = eval_intervals[m]["low"]
        gate3_comparisons[m] = dict(
            baseline_evaluations=primary_evaluations[m],
            candidate_evaluations=primary_evaluations[cand],
            relative_improvement=round(rel_imp, 8),
            ci_low=ci_low,
            passed=bool(rel_imp >= gcfg["min_search_work_improvement_fraction"] and ci_low > 0.0),
        )
    gate3_passed = all(v["passed"] for v in gate3_comparisons.values())

    # Gate 4: Example efficiency
    best_baseline_q = min(mean_examples_q[m] for m in baselines)
    q_imp_vs_flat = (mean_examples_q["flat_catalogue"] - mean_examples_q[cand]) / max(1e-9, mean_examples_q["flat_catalogue"])
    q_worse_vs_best = (mean_examples_q[cand] - best_baseline_q) / max(1e-9, best_baseline_q)
    gate4_passed = bool(
        q_imp_vs_flat >= gcfg["min_example_improvement_vs_flat"] - 1e-12
        and q_worse_vs_best <= gcfg["max_example_worse_vs_best"] + 1e-12
    )

    # Gate 5: Real retention
    cand_ret = retention_summary[cand]
    gate5_passed = bool(
        cand_ret["accuracy_after"] >= gcfg["min_retention_post_accuracy"]
        and cand_ret["accuracy_retention"] >= gcfg["min_retention_accuracy_delta"]
        and cand_ret["search_retention"] <= gcfg["max_retention_search_regression"]
        and cand_ret["worst_family_accuracy_delta"] >= -gcfg["max_catastrophic_family_drop"]
    )

    # Gate 6: Structural cross-domain transfer under supplied mapping
    xd_cand = "transferred_structural_prior"
    xd_baselines = [xm for xm in CROSS_DOMAIN_METHODS if xm != xd_cand]
    best_xd_acc = max(cross_domain_accuracy[xm] for xm in xd_baselines)
    xd_imp_vs_scratch = (
        cross_domain_evaluations["scratch_flat"] - cross_domain_evaluations[xd_cand]
    ) / max(1e-9, cross_domain_evaluations["scratch_flat"])
    xd_ci_low_scratch = cross_domain_intervals["scratch_flat"]["low"]
    xd_beats_macro_cache = cross_domain_evaluations[xd_cand] < cross_domain_evaluations["exact_macro_cache"]
    gate6_passed = bool(
        cross_domain_accuracy[xd_cand] >= best_xd_acc - gcfg["max_accuracy_deficit_vs_best"]
        and xd_imp_vs_scratch >= gcfg["min_transfer_search_improvement_fraction" if "min_transfer_search_improvement_fraction" in gcfg else "min_transfer_search_improvement_vs_scratch"]
        and xd_ci_low_scratch > 0.0
        and xd_beats_macro_cache
    )

    # Gate 7: Computation & amortization
    strongest_search_baseline = min(baselines, key=lambda m: primary_evaluations[m])
    strongest_total_units = total_compute_by_method[strongest_search_baseline]["total_amortized_units"]
    cand_total_units = total_compute_by_method[cand]["total_amortized_units"]
    amortized_overhead = (cand_total_units - strongest_total_units) / max(1.0, strongest_total_units)
    per_task_search_saved = (
        search_only_evaluations[strongest_search_baseline] - search_only_evaluations[cand]
    ) * len(PRIMARY_BUDGETS)
    source_fit_overhead_per_fam = (16.0 * 0.75 + 4.0) / 8.0
    break_even_tasks = (
        round(source_fit_overhead_per_fam / per_task_search_saved, 4)
        if per_task_search_saved > 0
        else None
    )
    gate7_passed = bool(
        amortized_overhead <= gcfg["max_amortized_compute_overhead_vs_best"]
        and break_even_tasks is not None
    )

    gates = dict(
        gate1_integrity=dict(passed=gate1_passed, details=part_check),
        gate2_held_out_quality=dict(
            passed=gate2_passed,
            candidate_accuracy=primary_accuracy[cand],
            best_baseline_accuracy=best_baseline_acc,
            best_baseline_name=best_acc_baseline_name,
            family_losses_vs_best=fam_losses_vs_best,
            worst_family_loss=round(worst_fam_loss, 8),
        ),
        gate3_search_efficiency=dict(
            passed=gate3_passed,
            comparisons=gate3_comparisons,
        ),
        gate4_example_efficiency=dict(
            passed=gate4_passed,
            candidate_examples=mean_examples_q[cand],
            flat_examples=mean_examples_q["flat_catalogue"],
            best_baseline_examples=best_baseline_q,
            improvement_vs_flat=round(q_imp_vs_flat, 8),
            worse_vs_best=round(q_worse_vs_best, 8),
        ),
        gate5_retention=dict(
            passed=gate5_passed,
            metrics=cand_ret,
        ),
        gate6_structural_cross_domain_transfer=dict(
            passed=gate6_passed,
            mapping_supplied=True,
            transfer_label="structural transfer under a supplied mapping",
            candidate_accuracy=cross_domain_accuracy[xd_cand],
            best_baseline_accuracy=best_xd_acc,
            candidate_evaluations=cross_domain_evaluations[xd_cand],
            scratch_evaluations=cross_domain_evaluations["scratch_flat"],
            exact_macro_cache_evaluations=cross_domain_evaluations["exact_macro_cache"],
            improvement_vs_scratch=round(xd_imp_vs_scratch, 8),
            ci_low_vs_scratch=xd_ci_low_scratch,
            beats_exact_macro_cache=xd_beats_macro_cache,
        ),
        gate7_computation=dict(
            passed=gate7_passed,
            strongest_baseline=strongest_search_baseline,
            candidate_total_amortized_units=cand_total_units,
            strongest_baseline_total_amortized_units=strongest_total_units,
            amortized_overhead_fraction=round(amortized_overhead, 8),
            break_even_target_tasks=break_even_tasks,
            by_method=total_compute_by_method,
        ),
    )
    all_gates_passed = all(g["passed"] for g in gates.values())
    conclusion = (
        "NEXUS demonstrated bounded source-trained learning-to-learn through improved program-search efficiency on canonically and semantically disjoint compositions within the registered finite grammar, including measured structural transfer under a supplied operator-role mapping."
        if all_gates_passed
        else "The registered bounded learning-to-learn screen failed. The architecture and benchmark remain useful engineering infrastructure, but useful learning-to-learn was not established."
    )

    return dict(
        schema="seed_disjoint_meta_evaluation_v1",
        all_gates_passed=all_gates_passed,
        screen="passed" if all_gates_passed else "failed",
        live_promotion=False,
        promotion_status="No live promotion",
        scientific_conclusion=conclusion,
        primary_accuracy=primary_accuracy,
        primary_evaluations=primary_evaluations,
        search_only_evaluations=search_only_evaluations,
        mean_examples_for_semantic_id=mean_examples_q,
        budget8_accuracy=budget8_accuracy,
        family_accuracy={m: [round(v, 8) for v in fam_acc[m]] for m in METHODS},
        family_evaluations={m: [round(v, 8) for v in fam_evals[m]] for m in METHODS},
        family_examples={m: [round(v, 8) for v in fam_q[m]] for m in METHODS},
        evaluation_intervals=eval_intervals,
        accuracy_intervals=acc_intervals,
        retention=retention_summary,
        cross_domain=dict(
            mapping_supplied=True,
            label="structural transfer under a supplied mapping",
            primary_accuracy=cross_domain_accuracy,
            primary_evaluations=cross_domain_evaluations,
            family_accuracy={xm: [round(v, 8) for v in fam_xd_acc[xm]] for xm in CROSS_DOMAIN_METHODS},
            family_evaluations={xm: [round(v, 8) for v in fam_xd_evals[xm]] for xm in CROSS_DOMAIN_METHODS},
            evaluation_intervals=cross_domain_intervals,
        ),
        gates=gates,
    )


def run_study(
    c: dict[str, Any],
    repository: str | Path,
    progress_path: Path | None = None,
) -> dict[str, Any]:
    started = time.process_time()
    root = Path(repository).resolve()
    config_check(c)
    frozen_before = frozen_hashes(root)

    protocol_path = root / "docs/NEXUS_SEED_DISJOINT_META_PROTOCOL.md"
    protocol_text = protocol_path.read_text(encoding="utf-8")
    protocol_sha256 = hashlib.sha256(protocol_text.encode("utf-8")).hexdigest()

    probes = probe_domain()
    comm_proof = verify_commutation_identities(probes)
    list_cat = build_catalogue("list")
    action_cat = build_catalogue("action_token_sequence")
    partition_proof = verify_partition_invariants(list_cat, action_cat)
    assignments = build_family_assignments(c, list_cat, action_cat)

    used_hashes: set[str] = set()
    families_out: list[dict[str, Any]] = []
    real_steps = 0
    outer_updates = 0

    for fi, assign in enumerate(assignments):
        # 1. Generate 16 solved source tasks
        source_tasks = []
        for si, pid in enumerate(assign["source_program_ids"]):
            tseed = c["tasks"]["train"][fi * 16 + si]
            entry = list_cat["entries"][pid]
            stask = generate_task_data(tseed, entry, used_hashes)
            real_steps += len(stask["teaching"])
            source_tasks.append(stask)

        # 2. Generate 4 frozen old-source retention tasks
        retention_tasks = []
        for ri, pid in enumerate(assign["retention_program_ids"]):
            tseed = c["tasks"]["retention"][fi * 4 + ri]
            entry = list_cat["entries"][pid]
            rtask = generate_task_data(tseed, entry, used_hashes)
            real_steps += len(rtask["assessment"])
            retention_tasks.append(rtask)

        # 3. Generate 3 disjoint in-domain target tasks
        target_tasks = []
        for ti, pid in enumerate(assign["target_program_ids"]):
            tseed = c["tasks"]["target"][fi * 3 + ti]
            entry = list_cat["entries"][pid]
            ttask = generate_task_data(tseed, entry, used_hashes)
            real_steps += len(ttask["teaching"]) + len(ttask["assessment"])
            target_tasks.append(ttask)

        # 4. Generate 3 disjoint structural cross-domain target tasks
        cross_tasks = []
        for xi, pid in enumerate(assign["cross_domain_program_ids"]):
            tseed = c["tasks"]["cross_domain"][fi * 3 + xi]
            entry = action_cat["entries"][pid]
            xtask = generate_task_data(tseed, entry, used_hashes)
            real_steps += len(xtask["assessment"])
            cross_tasks.append(xtask)

        # 5. Evaluate retention BEFORE source meta-training (scratch flat_catalogue prior)
        flat_ids, _, _ = rank_catalogue("flat_catalogue", list_cat, None)
        for rtask in retention_tasks:
            rtask["before_meta_learning"] = evaluate_task_under_ordering(rtask, list_cat, flat_ids, 0.0)

        # 6. Fit deterministic source-only structural meta-prior and baseline models
        fitted_model = fit_source_models(source_tasks, list_cat, c)
        outer_updates += 1

        # 7. Freeze candidate orderings before target teaching or assessment
        n_target_evals_in_fam = len(target_tasks) * len(PRIMARY_BUDGETS)
        orderings: dict[str, list[int]] = {}
        const_shares: dict[str, float] = {}
        for m in METHODS:
            if m == "random_ordering":
                const_shares[m] = 0.0
                continue
            ord_ids, _, _ = rank_catalogue(m, list_cat, fitted_model)
            orderings[m] = ord_ids
            const_units = 1.5 if m == "structural_meta_prior" else (1.0 if m in ("operator_frequency", "exact_macro_cache", "bayesian_model_based") else 0.0)
            const_shares[m] = const_units / n_target_evals_in_fam

        p_seeds = c["random_permutation_seeds"][fi * 64 : (fi + 1) * 64]

        # 8. Evaluate retention AFTER source meta-training on the same frozen retention bank
        for rtask in retention_tasks:
            rtask["after_meta_learning"] = {}
            for m in METHODS:
                rtask["after_meta_learning"][m] = (
                    evaluate_random_expectation(rtask, list_cat, p_seeds)
                    if m == "random_ordering"
                    else evaluate_task_under_ordering(rtask, list_cat, orderings[m], 0.0)
                )

        # 9. Evaluate in-domain disjoint target tasks
        for ttask in target_tasks:
            ttask["methods"] = {}
            for m in METHODS:
                ttask["methods"][m] = (
                    evaluate_random_expectation(ttask, list_cat, p_seeds)
                    if m == "random_ordering"
                    else evaluate_task_under_ordering(ttask, list_cat, orderings[m], const_shares[m])
                )

        # 10. Evaluate structural cross-domain target tasks under supplied mapping
        n_xd_evals_in_fam = len(cross_tasks) * len(PRIMARY_BUDGETS)
        xd_orderings: dict[str, list[int]] = {}
        xd_shares: dict[str, float] = {}
        for xm in CROSS_DOMAIN_METHODS:
            if xm == "random_ordering":
                xd_shares[xm] = 0.0
                continue
            ord_ids, _, _ = rank_catalogue(xm, action_cat, fitted_model)
            xd_orderings[xm] = ord_ids
            const_units = 1.5 if xm == "transferred_structural_prior" else (1.0 if xm in ("target_operator_frequency", "exact_macro_cache", "bayesian_model_based") else 0.0)
            xd_shares[xm] = const_units / n_xd_evals_in_fam

        for xtask in cross_tasks:
            xtask["methods"] = {}
            for xm in CROSS_DOMAIN_METHODS:
                xtask["methods"][xm] = (
                    evaluate_random_expectation(xtask, action_cat, p_seeds)
                    if xm == "random_ordering"
                    else evaluate_task_under_ordering(xtask, action_cat, xd_orderings[xm], xd_shares[xm])
                )

        families_out.append(dict(
            family_index=fi,
            family_seed=assign["family_seed"],
            assignment=assign,
            fitted_model=fitted_model,
            candidate_orderings=orderings,
            source_tasks=source_tasks,
            retention_tasks=retention_tasks,
            target_tasks=target_tasks,
            cross_domain_tasks=cross_tasks,
        ))

    raw_study = dict(
        schema="seed_disjoint_meta_v1",
        declared_complete=True,
        config=c,
        protocol_sha256=protocol_sha256,
        commutation_proof=comm_proof,
        catalogue_proof_sha256=list_cat["proof_sha256"],
        action_catalogue_proof_sha256=action_cat["proof_sha256"],
        list_catalogue=list_cat,
        action_catalogue=action_cat,
        supplied_role_mapping=SUPPLIED_ROLE_MAPPING,
        partition_invariants=partition_proof,
        families=families_out,
        frozen_before=frozen_before,
        frozen_after=frozen_hashes(root),
    )

    analysis = evaluate_disjoint_meta_artifact(raw_study, protocol_text, c)
    raw_study["analysis"] = analysis
    if progress_path is not None:
        progress_path.write_text(canonical(raw_study), encoding="utf-8")

    cpu_s = time.process_time() - started
    best_base_evals = min(
        v for k, v in analysis["primary_evaluations"].items() if k != "structural_meta_prior"
    )
    cand_evals = analysis["primary_evaluations"]["structural_meta_prior"]
    curve = [
        dict(
            update=b,
            train_mse=round(
                sum(
                    t["methods"]["structural_meta_prior"]["budgets"][str(b)]["construction_inclusive_evaluations"]
                    for f in families_out
                    for t in f["target_tasks"]
                )
                / 24.0,
                6,
            ),
            development_mse=round(
                sum(
                    t["methods"]["shortest_program"]["budgets"][str(b)]["construction_inclusive_evaluations"]
                    for f in families_out
                    for t in f["target_tasks"]
                )
                / 24.0,
                6,
            ),
        )
        for b in BUDGETS
    ]
    return dict(
        adapter="seed_disjoint_meta_v1",
        metrics=dict(
            mse=cand_evals,
            baseline_mse=best_base_evals,
            worst_error_increase=max(0.0, cand_evals - best_base_evals),
        ),
        curve=curve,
        resources=dict(
            updates=outer_updates,
            real_steps=real_steps,
            imagined_transitions=0,
            cpu_s=cpu_s,
            parameter_count=c["feature_dimension"],
            training_examples=128 * 8,
            development_examples=24 * 8,
            assessment_examples=(24 + 32 + 24) * 16,
            network_forwards=0,
        ),
        model=dict(
            schema="seed_disjoint_meta_models_v1",
            models=[f["fitted_model"] for f in families_out],
        ),
        study=raw_study,
        runtime=dict(
            python=sys.version.split()[0],
            torch="not_imported",
            device="cpu",
            threads=1,
        ),
    )


def run(request: dict[str, Any]) -> dict[str, Any]:
    c = request["inputs"]["study_config"]
    repo = request["inputs"]["repository"]
    return run_study(c, repo, Path("progress.json"))


def validate_output(output: dict[str, Any], c: dict[str, Any], caps: dict[str, Any]) -> None:
    config_check(c)
    if type(output) is not dict or output.get("adapter") != "seed_disjoint_meta_v1":
        raise ValueError("disjoint_meta_output_schema")
    study = output.get("study")
    if type(study) is not dict or study.get("declared_complete") is not True:
        raise ValueError("incomplete_disjoint_meta_study")
    if study.get("frozen_before") != sa.FROZEN or study.get("frozen_after") != sa.FROZEN:
        raise ValueError("frozen_checkpoint_changed")
    root = Path(__file__).resolve().parents[3]
    protocol_text = (root / "docs/NEXUS_SEED_DISJOINT_META_PROTOCOL.md").read_text(encoding="utf-8")
    recomputed = evaluate_disjoint_meta_artifact(study, protocol_text, c)
    if digest(study.get("analysis")) != digest(recomputed):
        raise ValueError("disjoint_meta_analysis_mismatch")
    work = output.get("resources", {})
    if work.get("updates") != 8 or work.get("real_steps") != 2496 or work.get("imagined_transitions") != 0 or work.get("network_forwards") != 0:
        raise ValueError("disjoint_meta_resource_accounting")
    if work.get("cpu_s", 0.0) > caps["cpu_s"]:
        raise ValueError("disjoint_meta_cpu_cap_exceeded")
    digest(output)


def saved_replay(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    r = json.loads((root / "artifacts/seed_disjoint_meta.json").read_text(encoding="utf-8"))
    validate_output(
        dict(
            adapter="seed_disjoint_meta_v1",
            metrics=dict(
                mse=r["analysis"]["primary_evaluations"]["structural_meta_prior"],
                baseline_mse=min(
                    v for k, v in r["analysis"]["primary_evaluations"].items() if k != "structural_meta_prior"
                ),
                worst_error_increase=0.0,
            ),
            curve=[],
            resources=r["resources"],
            model=dict(
                schema="seed_disjoint_meta_models_v1",
                models=[f["fitted_model"] for f in r["families"]],
            ),
            study=r,
            runtime=r["runtime"],
        ),
        r["config"],
        dict(
            wall_s=120,
            cpu_s=120,
            memory_mb=2048,
            real_steps=2496,
            imagined_transitions=0,
            updates=8,
        ),
    )
    best_base = min(
        v for k, v in r["analysis"]["primary_evaluations"].items() if k != "structural_meta_prior"
    )
    cand = r["analysis"]["primary_evaluations"]["structural_meta_prior"]
    return dict(
        id=r["host_receipt"]["id"],
        mode="exploration",
        status=r["host_receipt"]["status"],
        failure=r["host_receipt"]["failure"],
        wall_s=r["host_receipt"]["wall_s"],
        memory_mb=r["host_receipt"]["peak_sampled_rss_mb"],
        revision=r["execution_sha"],
        metrics=dict(
            mse=cand,
            baseline_mse=best_base,
            worst_error_increase=max(0.0, cand - best_base),
        ),
        curve=[],
        resources=r["resources"],
        model_sha256=digest([f["fitted_model"] for f in r["families"]]),
        disjoint_meta=r["analysis"],
    )
