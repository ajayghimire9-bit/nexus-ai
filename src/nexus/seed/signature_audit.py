"""Source-only input-output signature audit (seed_signature_audit_v1).

Audits whether observed teaching examples D_B = {(x_i, y_i)} expose useful
input-output clues across 6 categories:
  1. Output length change (preserved, decreased, mean ratio)
  2. Sorting or reversal (ascending, descending, direct reversal)
  3. Duplicates removed (dedup rate, first-appearance, reversed-first, last-appearance-reversed)
  4. Even/odd filtering (all-even output, all-odd output, pre-shift odd origin)
  5. Constant value shift (positive shift, negative shift, zero shift indicator)
  6. Preservation of order and cardinality

Strict leakage rule: reads ONLY the 17 source programs and 128 source tasks from
artifacts/seed_disjoint_meta.json. Never accesses target_tasks, target_ids, or
cross_domain_tasks.
"""
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from nexus.evolution1.catalogue import canonical, digest
from . import disjoint_meta as dm

SIGNATURE_FEATURE_NAMES = (
    # 1. Output length change
    "len_preserved_rate",
    "len_decreased_rate",
    "mean_len_ratio",
    # 2. Sorting or reversal
    "sorted_asc_rate",
    "sorted_desc_rate",
    "direct_reversal_rate",
    # 3. Duplicates removed & relative order of unique elements
    "duplicates_removed_rate",
    "first_appearance_order_rate",
    "reversed_first_appearance_rate",
    "last_appearance_reversed_rate",
    # 4. Even/odd filtering
    "all_even_output_rate",
    "all_odd_output_rate",
    "pre_shift_odd_origin_rate",
    # 5. Constant value shift
    "positive_shift_norm",
    "negative_shift_norm",
    "zero_shift_indicator",
    # 6. Preservation of order and cardinality
    "order_and_cardinality_preserved_rate",
)

CLUE_GROUPS = {
    "output_length_change": [0, 1, 2],
    "sorting_or_reversal": [3, 4, 5],
    "duplicates_removed": [6, 7, 8, 9],
    "even_odd_filtering": [10, 11, 12],
    "constant_value_shift": [13, 14, 15],
    "order_and_cardinality_preservation": [16],
}


def _dedup_preserve(xs: list[int]) -> list[int]:
    out: list[int] = []
    for v in xs:
        if v not in out:
            out.append(v)
    return out


def _to_int_list(seq: list[Any]) -> list[int]:
    if not seq:
        return []
    first = seq[0]
    if type(first) is dict and "mag" in first:
        return [int(item["mag"]) for item in seq]
    return [int(v) for v in seq]


def normalize_pairs(pairs: list[Any]) -> list[tuple[list[int], list[int]]]:
    out: list[tuple[list[int], list[int]]] = []
    for row in pairs:
        if type(row) is dict:
            x, y = row["input"], row["output"]
        else:
            x, y = row[0], row[1]
        out.append((_to_int_list(x), _to_int_list(y)))
    return out


def infer_constant_shift(norm_pairs: list[tuple[list[int], list[int]]]) -> int:
    """Infer integer shift c in {-3, -2, -1, 0, 1, 2, 3} from input-output pairs alone."""
    if not norm_pairs:
        return 0
    # If all outputs are empty, default shift is 0
    if all(len(y) == 0 for _, y in norm_pairs):
        return 0

    best_c = 0
    best_score = (-1, -1, 0)
    for c in (0, 1, -1, 2, -2, 3, -3):
        subset_matches = 0
        projection_matches = 0
        for x, y in norm_pairs:
            sx = [v + c for v in x]
            if all(u in sx for u in y):
                subset_matches += 1
            sy = sorted(y)
            ev_after = [u for u in sx if u % 2 == 0]
            ev_before = [v + c for v in x if v % 2 == 0]
            od_before = [v + c for v in x if v % 2 != 0]
            if (
                sy == sorted(sx)
                or sy == sorted(set(sx))
                or sy == sorted(ev_after)
                or sy == sorted(set(ev_after))
                or sy == sorted(ev_before)
                or sy == sorted(set(ev_before))
                or sy == sorted(od_before)
                or sy == sorted(set(od_before))
            ):
                projection_matches += 1
        score = (subset_matches, projection_matches, -abs(c))
        if score > best_score:
            best_score = score
            best_c = c
    return best_c


def compute_io_signature(pairs: list[Any]) -> list[float]:
    """Compute the 17-dimensional deterministic input-output signature in [0, 1]^17."""
    norm = normalize_pairs(pairs)
    n = len(norm)
    if n == 0:
        return [0.0] * len(SIGNATURE_FEATURE_NAMES)

    c = infer_constant_shift(norm)

    # 1. Output length change
    len_preserved = sum(1 for x, y in norm if len(y) == len(x)) / n
    len_decreased = sum(1 for x, y in norm if len(y) < len(x)) / n
    mean_len_ratio = sum((len(y) / len(x)) if len(x) > 0 else 1.0 for x, y in norm) / n

    # 2. Sorting or reversal
    sort_cases = [(x, y) for x, y in norm if len(y) >= 2]
    sorted_asc = (
        sum(1 for _, y in sort_cases if y == sorted(y)) / len(sort_cases)
        if sort_cases
        else 0.0
    )
    sorted_desc = (
        sum(1 for _, y in sort_cases if y == list(reversed(sorted(y)))) / len(sort_cases)
        if sort_cases
        else 0.0
    )

    rev_cases = [(x, y) for x, y in norm if len(y) >= 2]
    rev_direct = 0
    for x, y in rev_cases:
        sx = [v + c for v in x]
        ev_after = [u for u in sx if u % 2 == 0]
        ev_before = [v + c for v in x if v % 2 == 0]
        od_before = [v + c for v in x if v % 2 != 0]
        if (
            y == list(reversed(sx))
            or y == list(reversed(ev_after))
            or y == list(reversed(ev_before))
            or y == list(reversed(od_before))
        ):
            rev_direct += 1
    direct_reversal_rate = (rev_direct / len(rev_cases)) if rev_cases else 0.0

    # 3. Duplicates removed & relative order of unique elements
    dup_cases = [(x, y) for x, y in norm if len(x) > len(set(x))]
    duplicates_removed_rate = (
        sum(1 for x, y in dup_cases if len(y) == len(set(y)) and len(y) < len(x)) / len(dup_cases)
        if dup_cases
        else 0.0
    )

    order_cases = [(x, y) for x, y in norm if len(set(y)) >= 2]
    first_app = 0
    rev_first_app = 0
    last_app_rev = 0
    for x, y in order_cases:
        sx = [v + c for v in x]
        sub = [u for u in sx if u in y]
        dedup_sub = _dedup_preserve(sub)
        rev_dedup_sub = _dedup_preserve(list(reversed(sub)))
        dy = _dedup_preserve(y)
        if dy == dedup_sub:
            first_app += 1
        if dy == list(reversed(dedup_sub)):
            rev_first_app += 1
        if dy == rev_dedup_sub and dy != list(reversed(dedup_sub)):
            last_app_rev += 1
        elif dy == rev_dedup_sub and len(sub) > len(dedup_sub):
            last_app_rev += 1
    first_appearance_order_rate = (first_app / len(order_cases)) if order_cases else 0.0
    reversed_first_appearance_rate = (rev_first_app / len(order_cases)) if order_cases else 0.0
    last_appearance_reversed_rate = (last_app_rev / len(order_cases)) if order_cases else 0.0

    # 4. Even/odd filtering
    mixed_parity = [
        (x, y)
        for x, y in norm
        if any(v % 2 != 0 for v in x) and any(v % 2 == 0 for v in x)
    ]
    all_even_output_rate = (
        sum(1 for x, y in mixed_parity if len(y) < len(x) and all(u % 2 == 0 for u in y))
        / len(mixed_parity)
        if mixed_parity
        else 0.0
    )
    all_odd_output_rate = (
        sum(
            1
            for x, y in mixed_parity
            if len(y) < len(x) and len(y) > 0 and all(u % 2 != 0 for u in y)
        )
        / len(mixed_parity)
        if mixed_parity
        else 0.0
    )
    pre_shift_odd_origin_rate = (
        sum(
            1
            for x, y in mixed_parity
            if len(y) < len(x) and len(y) > 0 and all((u - c) % 2 != 0 for u in y)
        )
        / len(mixed_parity)
        if mixed_parity
        else 0.0
    )

    # 5. Constant value shift
    positive_shift_norm = max(0, c) / 3.0
    negative_shift_norm = max(0, -c) / 3.0
    zero_shift_indicator = 1.0 if c == 0 else 0.0

    # 6. Preservation of order and cardinality
    order_and_cardinality_preserved_rate = (
        sum(1 for x, y in norm if len(y) == len(x) and y == [v + c for v in x]) / n
    )

    return [
        round(len_preserved, 8),
        round(len_decreased, 8),
        round(mean_len_ratio, 8),
        round(sorted_asc, 8),
        round(sorted_desc, 8),
        round(direct_reversal_rate, 8),
        round(duplicates_removed_rate, 8),
        round(first_appearance_order_rate, 8),
        round(reversed_first_appearance_rate, 8),
        round(last_appearance_reversed_rate, 8),
        round(all_even_output_rate, 8),
        round(all_odd_output_rate, 8),
        round(pre_shift_odd_origin_rate, 8),
        round(positive_shift_norm, 8),
        round(negative_shift_norm, 8),
        round(zero_shift_indicator, 8),
        round(order_and_cardinality_preserved_rate, 8),
    ]


def calibration_inputs() -> list[list[int]]:
    """8 fixed public calibration inputs containing non-endpoint duplicates, mixed parity, and non-sorted order."""
    return [
        [3, -2, 3, 1, 0, -4],
        [4, 1, -1, 4, 2, -3],
        [-3, 2, 5, 2, 0, 1],
        [5, -4, 3, -4, 2, 1],
        [0, 5, -2, 5, 3, -1],
        [6, 1, -3, 1, 4, 2],
        [-2, 3, -5, 3, 0, 4],
        [2, -1, 4, -1, -2, 5],
    ]


def signature_l1_distance(sig_a: list[float], sig_b: list[float]) -> float:
    return sum(abs(a - b) for a, b in zip(sig_a, sig_b))


def run_source_only_signature_audit(root: str | Path) -> dict[str, Any]:
    """Run the Step 1 source-only input-output signature audit on saved source tasks."""
    root = Path(root).resolve()
    raw = json.loads((root / "artifacts/seed_disjoint_meta.json").read_text(encoding="utf-8"))

    # Explicitly strip target fields before analysis to guarantee zero target access
    list_cat = raw["list_catalogue"]
    source_ids = list(list_cat["source_ids"])
    source_entries = [list_cat["entries"][pid] for pid in source_ids]
    source_families = [
        dict(
            family_index=f["family_index"],
            family_seed=f["family_seed"],
            source_tasks=f["source_tasks"],
            fitted_model=f["fitted_model"],
        )
        for f in raw["families"]
    ]

    calib = calibration_inputs()
    source_signatures: dict[int, list[float]] = {}
    for entry in source_entries:
        pid = entry["id"]
        c_prog = entry["canonical_program"]
        pairs = [[x, dm.run_list_program(c_prog, x)] for x in calib]
        source_signatures[pid] = compute_io_signature(pairs)

    unique_sig_count = len({tuple(v) for v in source_signatures.values()})

    # Measure clue group variance and pairwise separation across the 17 source programs
    clue_group_stats: dict[str, dict[str, float]] = {}
    for gname, idxs in CLUE_GROUPS.items():
        vals = [
            abs(source_signatures[a][k] - source_signatures[b][k])
            for i, a in enumerate(source_ids)
            for b in source_ids[i + 1 :]
            for k in idxs
        ]
        active_progs = sum(
            1
            for pid in source_ids
            if any(source_signatures[pid][k] > 0.0 for k in idxs)
        )
        clue_group_stats[gname] = dict(
            feature_count=len(idxs),
            mean_pairwise_l1_contribution=round(sum(vals) * len(idxs) / max(1, len(vals)), 6),
            active_source_programs=active_progs,
        )

    # Evaluate leave-one-source-program-out ranking across the 128 saved source tasks (B in 1, 2, 4)
    # Candidate pool is the 17 source programs, where the true program is held out from the prior fit.
    loso_evals = {
        "deterministic_signature": [],
        "structural_meta_prior_loso": [],
        "flat_catalogue": [],
        "shortest_program": [],
    }
    loso_acc = {k: [] for k in loso_evals}

    alpha = 0.05
    beta = 0.05

    for fam in source_families:
        for stask in fam["source_tasks"]:
            true_pid = stask["program_id"]
            # Fit source structural prior on the OTHER source tasks in this family (excluding true_pid)
            other_tasks = [t for t in fam["source_tasks"] if t["program_id"] != true_pid]
            loso_model = dm.fit_source_models(other_tasks, list_cat, raw["config"])
            _, all_struct_scores, _ = dm.rank_catalogue("structural_meta_prior", list_cat, loso_model)
            struct_scores = {
                pid: all_struct_scores[list_cat["entries"][pid]["canonical_signature"]]
                for pid in source_ids
            }

            for b in (1, 2, 4):
                d_b = stask["teaching"][:b]
                sig_d = compute_io_signature(d_b)

                # 1. Task-conditioned deterministic signature ranking:
                # S(p|D) = -d(sig(D), sig(p)) + alpha * S_structural(p) - beta * complexity(p)
                det_order = sorted(
                    source_ids,
                    key=lambda pid: (
                        -(
                            -signature_l1_distance(sig_d, source_signatures[pid])
                            + alpha * struct_scores[pid]
                            - beta * (list_cat["entries"][pid]["length"] / 3.0)
                        ),
                        list_cat["entries"][pid]["canonical_signature"],
                    ),
                )
                # 2. Leave-one-source-program-out structural prior (task-independent)
                struct_order = sorted(
                    source_ids,
                    key=lambda pid: (-struct_scores[pid], list_cat["entries"][pid]["canonical_signature"]),
                )
                # 3. Flat catalogue order
                flat_order = sorted(
                    source_ids,
                    key=lambda pid: list_cat["entries"][pid]["canonical_signature"],
                )
                # 4. Shortest program order
                short_order = sorted(
                    source_ids,
                    key=lambda pid: (
                        list_cat["entries"][pid]["length"],
                        list_cat["entries"][pid]["canonical_signature"],
                    ),
                )

                for mname, order in (
                    ("deterministic_signature", det_order),
                    ("structural_meta_prior_loso", struct_order),
                    ("flat_catalogue", flat_order),
                    ("shortest_program", short_order),
                ):
                    eval_count = 0
                    selected_prog = None
                    for pid in order:
                        eval_count += 1
                        cand_prog = list_cat["entries"][pid]["canonical_program"]
                        if all(dm.run_list_program(cand_prog, r["input"]) == r["output"] for r in d_b):
                            selected_prog = cand_prog
                            break
                    loso_evals[mname].append(eval_count)
                    if selected_prog is None:
                        loso_acc[mname].append(0.0)
                    else:
                        acc = sum(
                            1
                            for r in stask["assessment"]
                            if dm.run_list_program(selected_prog, r["input"]) == r["output"]
                        ) / len(stask["assessment"])
                        loso_acc[mname].append(acc)

    summary_evals = {k: round(sum(v) / len(v), 8) for k, v in loso_evals.items()}
    summary_acc = {k: round(sum(v) / len(v), 8) for k, v in loso_acc.items()}
    reduction_vs_flat = round(
        (summary_evals["flat_catalogue"] - summary_evals["deterministic_signature"])
        / summary_evals["flat_catalogue"],
        8,
    )
    reduction_vs_struct = round(
        (summary_evals["structural_meta_prior_loso"] - summary_evals["deterministic_signature"])
        / summary_evals["structural_meta_prior_loso"],
        8,
    )

    audit_passed = (
        unique_sig_count == len(source_ids)
        and summary_evals["deterministic_signature"] <= 2.0
        and reduction_vs_flat >= 0.75
        and reduction_vs_struct >= 0.75
    )

    return dict(
        schema="seed_signature_audit_v1",
        source_artifact="artifacts/seed_disjoint_meta.json",
        source_artifact_sha256=hashlib.sha256(
            (root / "artifacts/seed_disjoint_meta.json").read_bytes()
        ).hexdigest(),
        target_outcomes_accessed=False,
        source_program_count=len(source_ids),
        unique_source_signature_count=unique_sig_count,
        signature_dimension=len(SIGNATURE_FEATURE_NAMES),
        signature_feature_names=list(SIGNATURE_FEATURE_NAMES),
        clue_group_statistics=clue_group_stats,
        locked_hyperparameters=dict(alpha=alpha, beta=beta, ridge_lambda=1.0),
        loso_source_evaluations=summary_evals,
        loso_source_accuracy=summary_acc,
        search_reduction_vs_flat=reduction_vs_flat,
        search_reduction_vs_structural_loso=reduction_vs_struct,
        source_program_signatures=[
            dict(
                program_id=pid,
                ops=list_cat["entries"][pid]["canonical_program"]["ops"],
                signature=source_signatures[pid],
            )
            for pid in source_ids
        ],
        audit_passed=audit_passed,
    )
