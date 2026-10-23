"""High-headroom investigation benchmark v3.

Reuses EventMeter / digest / EpisodeCallLedger. Does not edit
``apply_primitive_op``, reopen Depth 1–2 v1/v2 grids, or index φ by
operator name. Closed capability-audit and conversation-capability
results stay historical.

Cluster tags on the first cell mark the specialist regime. Operators
are identity on a foreign tag, so a Cluster-1 probe has zero
disagreement on Cluster 2/3/4 programs. That is the property that
makes balanced ``simple_frequency`` walk four regimes while
query-conditioned selection walks one.
"""
from __future__ import annotations

import hashlib
import itertools
from collections import Counter
from dataclasses import dataclass
from typing import Callable

from .capability_evidence import digest


CALL_BUDGET = 35
MIN_HYPOTHESES = 2500
PROGRAM_LENGTHS = (3, 4)
CLUSTER_IDS = ("filter", "mod", "order", "group")
CLUSTER_TAG = {"filter": 1, "mod": 2, "order": 3, "group": 4}
SIGNATURE_CLASS = {
    "filter": "length_contracting_select",
    "mod": "length_preserving_residue",
    "order": "length_preserving_permute",
    "group": "structure_grouping",
}

# Specialist probes: first cell is the regime tag.
SPECIALIST_PROBES: dict[str, list[int]] = {
    "filter": [1, 0, 2, -1, 4, 0, 3],
    "mod": [2, 1, 4, 3, 6, 5],
    "order": [3, 1, 4, 2],
    "group": [4, -2, 2, -3, 3, 0],
}


def _keep_pos(xs: list[int]) -> list[int]:
    return [x for x in xs if x > 0]


def _keep_even(xs: list[int]) -> list[int]:
    return [x for x in xs if x % 2 == 0]


def _take_prefix_half(xs: list[int]) -> list[int]:
    return xs[: max(1, len(xs) // 2)] if xs else []


def _keep_neg(xs: list[int]) -> list[int]:
    return [x for x in xs if x < 0]


def _keep_odd(xs: list[int]) -> list[int]:
    return [x for x in xs if x % 2 != 0]


def _drop_suffix_half(xs: list[int]) -> list[int]:
    return xs[: (len(xs) + 1) // 2] if xs else []


def _res_mod3(xs: list[int]) -> list[int]:
    return [x % 3 for x in xs]


def _add2_mod5(xs: list[int]) -> list[int]:
    return [(x + 2) % 5 for x in xs]


def _mul2_mod7(xs: list[int]) -> list[int]:
    return [(x * 2) % 7 for x in xs]


def _res_mod4(xs: list[int]) -> list[int]:
    return [x % 4 for x in xs]


def _add3_mod8(xs: list[int]) -> list[int]:
    return [(x + 3) % 8 for x in xs]


def _mul3_mod5(xs: list[int]) -> list[int]:
    return [(x * 3) % 5 for x in xs]


def _rev(xs: list[int]) -> list[int]:
    return list(reversed(xs))


def _rot_l(xs: list[int]) -> list[int]:
    return xs[1:] + xs[:1] if xs else []


def _sort_up(xs: list[int]) -> list[int]:
    return sorted(xs)


def _swap_halves(xs: list[int]) -> list[int]:
    mid = len(xs) // 2
    return xs[mid:] + xs[:mid]


def _rot_r(xs: list[int]) -> list[int]:
    return xs[-1:] + xs[:-1] if xs else []


def _sort_down(xs: list[int]) -> list[int]:
    return sorted(xs, reverse=True)


def _sum_by_parity(xs: list[int]) -> list[int]:
    return [sum(x for x in xs if x % 2 == 0), sum(x for x in xs if x % 2 != 0)]


def _count_by_sign(xs: list[int]) -> list[int]:
    return [
        sum(1 for x in xs if x > 0),
        sum(1 for x in xs if x < 0),
        sum(1 for x in xs if x == 0),
    ]


def _first_per_mod2(xs: list[int]) -> list[int]:
    seen: dict[int, int] = {}
    for x in xs:
        seen.setdefault(x % 2, x)
    return [seen[k] for k in sorted(seen)]


def _sum_by_mod3(xs: list[int]) -> list[int]:
    return [sum(x for x in xs if x % 3 == r) for r in range(3)]


def _count_by_parity(xs: list[int]) -> list[int]:
    return [sum(1 for x in xs if x % 2 == 0), sum(1 for x in xs if x % 2 != 0)]


def _last_per_mod2(xs: list[int]) -> list[int]:
    seen: dict[int, int] = {}
    for x in xs:
        seen[x % 2] = x
    return [seen[k] for k in sorted(seen)]


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    cluster: str
    set_id: str
    fn: Callable[[list[int]], list[int]]

    @property
    def tag(self) -> int:
        return CLUSTER_TAG[self.cluster]

    @property
    def signature_class(self) -> str:
        return SIGNATURE_CLASS[self.cluster]


SET_A: tuple[OperatorSpec, ...] = (
    OperatorSpec("keep_pos", "filter", "A", _keep_pos),
    OperatorSpec("keep_even", "filter", "A", _keep_even),
    OperatorSpec("take_prefix_half", "filter", "A", _take_prefix_half),
    OperatorSpec("res_mod3", "mod", "A", _res_mod3),
    OperatorSpec("add2_mod5", "mod", "A", _add2_mod5),
    OperatorSpec("mul2_mod7", "mod", "A", _mul2_mod7),
    OperatorSpec("rev", "order", "A", _rev),
    OperatorSpec("rot_l", "order", "A", _rot_l),
    OperatorSpec("sort_up", "order", "A", _sort_up),
    OperatorSpec("sum_by_parity", "group", "A", _sum_by_parity),
    OperatorSpec("count_by_sign", "group", "A", _count_by_sign),
    OperatorSpec("first_per_mod2", "group", "A", _first_per_mod2),
)
SET_B: tuple[OperatorSpec, ...] = (
    OperatorSpec("keep_neg", "filter", "B", _keep_neg),
    OperatorSpec("keep_odd", "filter", "B", _keep_odd),
    OperatorSpec("drop_suffix_half", "filter", "B", _drop_suffix_half),
    OperatorSpec("res_mod4", "mod", "B", _res_mod4),
    OperatorSpec("add3_mod8", "mod", "B", _add3_mod8),
    OperatorSpec("mul3_mod5", "mod", "B", _mul3_mod5),
    OperatorSpec("swap_halves", "order", "B", _swap_halves),
    OperatorSpec("rot_r", "order", "B", _rot_r),
    OperatorSpec("sort_down", "order", "B", _sort_down),
    OperatorSpec("sum_by_mod3", "group", "B", _sum_by_mod3),
    OperatorSpec("count_by_parity", "group", "B", _count_by_parity),
    OperatorSpec("last_per_mod2", "group", "B", _last_per_mod2),
)
ALL_SPECS: dict[str, OperatorSpec] = {spec.name: spec for spec in SET_A + SET_B}
TEMPLATE_FILTER_THEN_MAP = "filter(P) -> map(F)"


def apply_v3(op: str, xs: list[int]) -> list[int]:
    spec = ALL_SPECS[op]
    if not xs or xs[0] != spec.tag:
        return list(xs)
    return [xs[0]] + spec.fn(list(xs[1:]))


def execute_v3(ops: tuple[str, ...], xs: list[int]) -> list[int]:
    cur = list(xs)
    for op in ops:
        cur = apply_v3(op, cur)
    return cur


def names(set_id: str) -> tuple[str, ...]:
    specs = SET_A if set_id == "A" else SET_B
    return tuple(spec.name for spec in specs)


def hypothesis_space(set_id: str, lengths: tuple[int, ...] = PROGRAM_LENGTHS) -> list[tuple[str, ...]]:
    ops = names(set_id)
    return [seq for n in lengths for seq in itertools.product(ops, repeat=n)]


def hypothesis_count(set_id: str, lengths: tuple[int, ...] = PROGRAM_LENGTHS) -> int:
    n = len(names(set_id))
    return sum(n ** length for length in lengths)


def interleaved_catalogue(set_id: str) -> list[tuple[str, ...]]:
    """Zip programs across the four clusters, then append mixed leftovers.

    Balanced ``simple_frequency`` ties break in this order, so a C1 target
    is reached only after walking the other three specialist slices.
    """
    space = hypothesis_space(set_id)
    buckets = {cluster: [] for cluster in CLUSTER_IDS}
    mixed: list[tuple[str, ...]] = []
    for prog in space:
        clusters = {ALL_SPECS[op].cluster for op in prog}
        if len(clusters) == 1:
            buckets[next(iter(clusters))].append(prog)
        else:
            mixed.append(prog)
    zipped: list[tuple[str, ...]] = []
    for row in itertools.zip_longest(*[buckets[c] for c in CLUSTER_IDS]):
        zipped.extend(prog for prog in row if prog is not None)
    return zipped + mixed


def program_signature(ops: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(automatic_signature(op) for op in ops)


def automatic_signature(op: str) -> str:
    """Classify an operator from tagged specialist I/O only. No op_name key."""
    changed: dict[str, bool] = {}
    contracted: dict[str, bool] = {}
    for cluster, probe in SPECIALIST_PROBES.items():
        out = apply_v3(op, probe)
        changed[cluster] = out != probe
        contracted[cluster] = len(out) < len(probe)
    native = [cluster for cluster, flag in changed.items() if flag]
    if native == ["filter"] and contracted["filter"]:
        return SIGNATURE_CLASS["filter"]
    if native == ["mod"] and not contracted["mod"]:
        return SIGNATURE_CLASS["mod"]
    if native == ["order"] and not contracted["order"]:
        return SIGNATURE_CLASS["order"]
    if native == ["group"]:
        return SIGNATURE_CLASS["group"]
    return "unknown:" + digest(changed)


def support_io_invariant(examples: list[tuple[list[int], list[int]]]) -> str:
    """Support-only I/O invariant. Does not read operator names or tags as IDs."""
    if not examples:
        return "empty"
    shrink = sum(1 for inp, out in examples if len(out) < len(inp)) / len(examples)
    same = sum(1 for inp, out in examples if len(out) == len(inp)) / len(examples)
    permuted = 0.0
    residue = 0.0
    for inp, out in examples:
        if len(inp) == len(out) and len(inp) > 1:
            if sorted(out) == sorted(inp) and out != inp:
                permuted += 1.0 / len(examples)
            elif out != inp:
                residue += 1.0 / len(examples)
    if shrink >= 0.5:
        return "length_contracting"
    if permuted >= 0.5:
        return "order_changed"
    if same >= 0.5 and residue >= 0.5:
        return "residue_or_map"
    if shrink > 0 or same < 1:
        return "structure_changed"
    return "identity_or_unknown"


def phi_key(invariant: str, signature: str) -> tuple[str, str]:
    if signature in ALL_SPECS:
        raise ValueError("phi_key_must_not_be_operator_name:" + signature)
    return (invariant, signature)


def train_phi(tasks: list[dict]) -> dict[tuple[str, str], float]:
    """Credit (support invariant, automatic signature), never op_name."""
    weights: dict[tuple[str, str], float] = {}
    for task in tasks:
        invariant = support_io_invariant(task["support"])
        consistent = task["consistent_ops"]
        for op in consistent:
            key = phi_key(invariant, automatic_signature(op))
            weights[key] = weights.get(key, 0.0) + 1.0 / max(1, len(consistent))
    return weights


def score_program(ops: tuple[str, ...], invariant: str, weights: dict[tuple[str, str], float]) -> float:
    sigs = program_signature(ops)
    return sum(weights.get(phi_key(invariant, sig), 0.0) for sig in sigs) / max(1, len(sigs))


def _target_signature(invariant: str) -> str:
    return {
        "length_contracting": SIGNATURE_CLASS["filter"],
        "residue_or_map": SIGNATURE_CLASS["mod"],
        "order_changed": SIGNATURE_CLASS["order"],
        "structure_changed": SIGNATURE_CLASS["group"],
    }.get(invariant, "")


def conditioned_order(set_id: str, invariant: str, weights: dict[tuple[str, str], float] | None = None) -> list[tuple[str, ...]]:
    space = hypothesis_space(set_id)
    weights = weights or {}
    target = _target_signature(invariant)

    def key(prog: tuple[str, ...]):
        sigs = program_signature(prog)
        all_match = bool(target) and all(sig == target for sig in sigs)
        if weights:
            return (-float(all_match), -score_program(prog, invariant, weights), prog)
        matched = sum(1 for sig in sigs if sig == target)
        return (-float(all_match), -matched, prog)

    return sorted(space, key=key)


def disagreement(probe: list[int], programs: list[tuple[str, ...]]) -> int:
    return len({tuple(execute_v3(prog, probe)) for prog in programs})


def cluster_programs(set_id: str, cluster: str, lengths: tuple[int, ...] = PROGRAM_LENGTHS) -> list[tuple[str, ...]]:
    ops = tuple(spec.name for spec in (SET_A if set_id == "A" else SET_B) if spec.cluster == cluster)
    return [seq for n in lengths for seq in itertools.product(ops, repeat=n)]


def orthogonality_report(set_id: str = "A") -> dict:
    rows = []
    for native, probe in SPECIALIST_PROBES.items():
        native_n = disagreement(probe, cluster_programs(set_id, native))
        foreign = {
            cluster: disagreement(probe, cluster_programs(set_id, cluster))
            for cluster in CLUSTER_IDS if cluster != native
        }
        rows.append({
            "probe_cluster": native,
            "probe": probe,
            "native_partitions": native_n,
            "foreign_partitions": foreign,
            "zero_foreign_disagreement": all(part == 1 for part in foreign.values()),
        })
    return {
        "set_id": set_id,
        "rows": rows,
        "all_specialists_orthogonal": all(row["zero_foreign_disagreement"] and row["native_partitions"] > 1 for row in rows),
    }


def calls_to_cover_cluster(order: list[tuple[str, ...]], cluster: str, set_id: str) -> int:
    target = set(cluster_programs(set_id, cluster))
    seen = 0
    hit = 0
    for prog in order:
        seen += 1
        if prog in target:
            hit += 1
            if hit == len(target):
                return seen
    return seen


def frequency_waste_ratio(set_id: str = "A", cluster: str = "filter") -> dict:
    freq_order = interleaved_catalogue(set_id)
    cond_order = conditioned_order(set_id, "length_contracting")
    freq_calls = calls_to_cover_cluster(freq_order, cluster, set_id)
    cond_calls = calls_to_cover_cluster(cond_order, cluster, set_id)
    return {
        "cluster": cluster,
        "simple_frequency_calls": freq_calls,
        "query_conditioned_calls": cond_calls,
        "ratio": freq_calls / cond_calls if cond_calls else None,
        "extra_factor": (freq_calls / cond_calls - 1) if cond_calls else None,
        # Four interleaved slices; the last zip row stops once the native
        # slice is covered, so the ratio is 429/108 ≈ 3.97, not exactly 4.
        "guarantees_3x_more": bool(cond_calls and freq_calls / cond_calls >= 3.9),
    }


def disjoint_operator_sets() -> dict:
    a = set(names("A"))
    b = set(names("B"))
    return {
        "a_count": len(a),
        "b_count": len(b),
        "name_overlap": sorted(a & b),
        "disjoint": a.isdisjoint(b),
        "a_signatures": sorted({automatic_signature(op) for op in a}),
        "b_signatures": sorted({automatic_signature(op) for op in b}),
        "signature_classes_match": {automatic_signature(op) for op in a} == {automatic_signature(op) for op in b},
    }


def brute_force_coverage() -> dict:
    size = hypothesis_count("A")
    return {
        "hypothesis_count": size,
        "min_required": MIN_HYPOTHESES,
        "above_floor": size > MIN_HYPOTHESES,
        "call_budget": CALL_BUDGET,
        "brute_force_fraction": CALL_BUDGET / size,
        "below_30pct_if_one_call_per_program": CALL_BUDGET / size < 0.30,
        "templates_required_for_widening": [TEMPLATE_FILTER_THEN_MAP],
    }


def structural_certificate() -> dict:
    ortho_a = orthogonality_report("A")
    ortho_b = orthogonality_report("B")
    waste = frequency_waste_ratio("A", "filter")
    sets = disjoint_operator_sets()
    coverage = brute_force_coverage()
    sample_key = phi_key("length_contracting", automatic_signature("keep_pos"))
    return {
        "benchmark": "v3_headroom",
        "default_investigation_policy": "fixed_boundary",
        "learned_ranking_promoted": False,
        "learning_to_learn_established": False,
        "historical_depth12_rescoring": False,
        "orthogonal": ortho_a["all_specialists_orthogonal"] and ortho_b["all_specialists_orthogonal"],
        "orthogonality_a": ortho_a,
        "orthogonality_b": ortho_b,
        "frequency_waste": waste,
        "operator_sets": sets,
        "coverage": coverage,
        "phi_key_example": sample_key,
        "phi_key_uses_operator_name": sample_key[1] in ALL_SPECS,
        "ready_for_transfer_experiment": False,
        "transfer_gate": "set_B_calls <= 0.5 * untrained_default_calls",
        "config_hash": digest({
            "a": names("A"), "b": names("B"), "lengths": PROGRAM_LENGTHS,
            "budget": CALL_BUDGET, "probes": SPECIALIST_PROBES,
        }),
    }
