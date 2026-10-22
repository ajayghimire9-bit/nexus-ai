"""Isolated black-box evaluator process for Stage B (Open Primitive Code Transfer).

This module is executed in a separate subprocess (`python3 -m nexus.seed.blackbox_evaluator_worker`).
It holds the private unseen library generators, private test inputs (never exposed to the
learner process), and ground-truth reference implementations.

Supported subprocess modes:
  1. `init_workspace`:
     Given `(seed, family_name, freeze_journal_sha256)`, generates an unseen multi-file library
     workspace after rule freeze containing:
       - `helpers_alpha.py` (2 candidate helpers: `_cand_alpha_1`, `_cand_alpha_2`)
       - `helpers_beta.py` (1 candidate helper: `_cand_beta_1`)
       - `target_pipeline.py` (3 plausible post-step functions `_post_reverse`, `_post_inc`,
         `_post_dedup` and multiple call sites `stage_pre_filter`, `stage_core_transform`,
         `solve_pipeline`)
       - 3 public `visible_tests` (input/expected_output pairs for `solve_pipeline`)
       - 1 public `teaching_example` for cross-lab invented-word binding
     Crucially, `patched_target_body`, `post_op`, `correct_helper`, and private test inputs
     are NEVER included in the workspace payload.
  2. `evaluate_helper_proposal`:
     Evaluates a learner's proposed primitive (`source_code`, `proposed_name`) on private
     held-out test inputs inside the isolated evaluator process, returning only scalar pass
     counts without exposing private inputs or outputs.
  3. `evaluate_submission`:
     Evaluates a learner's synthesized AST-patched module (`bundle_source`) and cross-lab
     invented-word binding on 12 private test inputs inside the isolated evaluator process,
     returning only scalar metrics and a cryptographic receipt digest.
"""
from __future__ import annotations

import ast
import hashlib
import json
import random
import sys
import textwrap
from typing import Any


SAFE_AST_NODES = (
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.Assign,
    ast.AugAssign,
    ast.AnnAssign,
    ast.For,
    ast.While,
    ast.If,
    ast.Expr,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,
    ast.Attribute,
    ast.IfExp,
    ast.Subscript,
    ast.Index,
    ast.Slice,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    ast.ListComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.FloorDiv,
    ast.Mod,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.USub,
    ast.UAdd,
    ast.Pass,
    ast.Break,
    ast.Continue,
)

SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

INVENTED_WORDS = {
    "ulib_window_checksum": "krelv",
    "ulib_runlength_bucket": "voux",
    "ulib_zigzag_interleave": "zarn",
}


def compile_safe_module(source_code: str) -> dict[str, Any]:
    tree = ast.parse(source_code, mode="exec")
    for node in ast.walk(tree):
        if not isinstance(node, SAFE_AST_NODES):
            raise ValueError(f"forbidden_ast_node:{type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("dunder_access_forbidden")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("dunder_attribute_forbidden")
    env: dict[str, Any] = {"__builtins__": dict(SAFE_BUILTINS)}
    code_obj = compile(tree, filename="<blackbox_eval>", mode="exec")
    exec(code_obj, env, env)
    return env


def _private_parameters(seed: int, family_name: str) -> tuple[int, int, int]:
    """Deterministically derives `(param_a, param_b, slot_perm_idx)` from `(seed, family_name)`."""
    fam_idx = {
        "ulib_window_checksum": 101,
        "ulib_runlength_bucket": 202,
        "ulib_zigzag_interleave": 303,
    }[family_name]
    rng = random.Random(seed * 31 + fam_idx)
    param_a = rng.choice((2, 3, 4))
    param_b = rng.choice((1, 2, 3))
    slot_perm_idx = rng.randint(0, 2)
    return param_a, param_b, slot_perm_idx


def _ground_truth_helper_only(family_name: str, xs: list[int], param_a: int, param_b: int) -> list[int]:
    """Ground-truth behavior of the true unseen helper primitive alone."""
    if family_name == "ulib_window_checksum":
        if not xs:
            return []
        n = len(xs)
        return [((xs[i] + param_a * xs[(i + 1) % n] + param_b) % 11) - 5 for i in range(n)]
    if family_name == "ulib_runlength_bucket":
        if not xs:
            return []
        out = []
        run_len = 1
        for i in range(1, len(xs) + 1):
            if i < len(xs) and (xs[i] % 2) == (xs[i - 1] % 2):
                run_len += 1
            else:
                out.append((xs[i - 1] + param_a * run_len) - param_b)
                run_len = 1
        return out
    if family_name == "ulib_zigzag_interleave":
        if not xs:
            return []
        left = 0
        right = len(xs) - 1
        toggle = 1
        out = []
        while left <= right:
            if toggle == 1:
                out.append(xs[left] + param_a)
                left += 1
            else:
                out.append(xs[right] - param_b)
                right -= 1
            toggle = -toggle
        return out
    raise ValueError(f"unknown_family:{family_name}")


def _ground_truth_mechanism(
    family_name: str,
    xs: list[int],
    param_a: int,
    param_b: int,
    task_index: int = 0,
) -> list[int]:
    """Ground-truth target pipeline behavior (true helper followed by task post-step).
    For `task_index == 0`, uses the default family post-step; for sequential fresh tasks
    `task_index > 0`, rotates across the 3 candidate post-steps (`_post_reverse`,
    `_post_inc`, `_post_dedup`)."""
    mid = _ground_truth_helper_only(family_name, xs, param_a, param_b)
    if family_name == "ulib_window_checksum":
        base_post_idx = 0
    elif family_name == "ulib_runlength_bucket":
        base_post_idx = 1
    elif family_name == "ulib_zigzag_interleave":
        base_post_idx = 2
    else:
        raise ValueError(f"unknown_family:{family_name}")

    post_idx = (base_post_idx + int(task_index)) % 3
    if post_idx == 0:
        return list(reversed(mid))
    if post_idx == 1:
        return [v + 1 for v in mid]
    seen: set[int] = set()
    dedup: list[int] = []
    for v in mid:
        if v not in seen:
            seen.add(v)
            dedup.append(v)
    return dedup


def _build_helper_bodies(family_name: str, param_a: int, param_b: int) -> tuple[str, str, str]:
    """Returns `(true_body, decoy_1_body, decoy_2_body)` as indented function bodies."""
    if family_name == "ulib_window_checksum":
        true_body = textwrap.dedent(
            f"""\
            if not seq:
                return []
            n = len(seq)
            return [((seq[i] + {param_a} * seq[(i + 1) % n] + {param_b}) % 11) - 5 for i in range(n)]
            """
        )
        decoy_1 = textwrap.dedent(
            f"""\
            if not seq:
                return []
            n = len(seq)
            return [((seq[i] - {param_a} * seq[(i + 1) % n] + {param_b}) % 9) - 3 for i in range(n)]
            """
        )
        decoy_2 = textwrap.dedent(
            f"""\
            if len(seq) < 2:
                return list(seq)
            return [((seq[i] + seq[i + 1] + {param_b}) % 7) for i in range(len(seq) - 1)]
            """
        )
        return true_body, decoy_1, decoy_2

    if family_name == "ulib_runlength_bucket":
        true_body = textwrap.dedent(
            f"""\
            if not seq:
                return []
            out = []
            run_len = 1
            for i in range(1, len(seq) + 1):
                if i < len(seq) and (seq[i] % 2) == (seq[i - 1] % 2):
                    run_len += 1
                else:
                    out.append((seq[i - 1] + {param_a} * run_len) - {param_b})
                    run_len = 1
            return out
            """
        )
        decoy_1 = textwrap.dedent(
            f"""\
            if not seq:
                return []
            out = []
            run_len = 1
            for i in range(1, len(seq) + 1):
                if i < len(seq) and seq[i] == seq[i - 1]:
                    run_len += 1
                else:
                    out.append((seq[i - 1] * run_len) + {param_b})
                    run_len = 1
            return out
            """
        )
        decoy_2 = textwrap.dedent(
            f"""\
            return [(x + {param_a}) - {param_b} for x in seq[::2]]
            """
        )
        return true_body, decoy_1, decoy_2

    if family_name == "ulib_zigzag_interleave":
        true_body = textwrap.dedent(
            f"""\
            if not seq:
                return []
            left = 0
            right = len(seq) - 1
            toggle = 1
            out = []
            while left <= right:
                if toggle == 1:
                    out.append(seq[left] + {param_a})
                    left += 1
                else:
                    out.append(seq[right] - {param_b})
                    right -= 1
                toggle = -toggle
            return out
            """
        )
        decoy_1 = textwrap.dedent(
            f"""\
            if not seq:
                return []
            return [seq[i] - {param_a} if i % 2 == 0 else seq[i] + {param_b} for i in range(len(seq))]
            """
        )
        decoy_2 = textwrap.dedent(
            f"""\
            n = len(seq)
            half = n // 2
            if half == 0:
                return list(seq)
            return [seq[i] + seq[n - 1 - i] + {param_a} for i in range(half)]
            """
        )
        return true_body, decoy_1, decoy_2

    raise ValueError(f"unknown_family:{family_name}")


def _generate_private_test_inputs(seed: int, family_name: str) -> list[list[int]]:
    """Generates 12 private test inputs that are NEVER exposed to the learner process."""
    rng = random.Random(seed * 997 + sum(ord(c) for c in family_name))
    private_inputs: list[list[int]] = [
        [-4, -1, 0, 2, 2, 7],
        [5, -3, -3, 8, 1, 0, -2],
        [0, 0, 1, 1, 2, 2],
        [-7, 4, -5, 6, -3, 2],
    ]
    for _ in range(8):
        length = rng.randint(4, 8)
        private_inputs.append([rng.randint(-8, 9) for _ in range(length)])
    return private_inputs


def init_workspace(payload: dict[str, Any]) -> dict[str, Any]:
    """Generates the multi-file unseen library workspace after rule freeze.
    Supports `task_index` (0, 1, 2, 3) for sequential multi-task evaluation where each
    fresh task permutes the candidate helper slots (`_cand_alpha_1`, `_cand_alpha_2`,
    `_cand_beta_1`), rotates the target post-step composition, and uses fresh visible
    and private test inputs while keeping the family's true helper semantics invariant."""
    seed = int(payload["seed"])
    family_name = str(payload["family_name"])
    task_index = int(payload.get("task_index", 0))
    freeze_sha = str(payload.get("freeze_journal_sha256", ""))
    if not freeze_sha:
        raise ValueError("stage_b_requires_frozen_rule_journal_sha256")

    param_a, param_b, slot_perm_idx = _private_parameters(seed, family_name)
    true_body, decoy_1, decoy_2 = _build_helper_bodies(family_name, param_a, param_b)
    if task_index > 0:
        _, decoy_1, decoy_2 = _build_helper_bodies(
            family_name, param_a + task_index, param_b + task_index
        )
    eff_slot_perm_idx = (slot_perm_idx + task_index) % 3

    # Permute which candidate function name gets the true helper vs the 2 decoys
    permutations = [
        (true_body, decoy_1, decoy_2),
        (decoy_1, true_body, decoy_2),
        (decoy_1, decoy_2, true_body),
    ]
    b_alpha_1, b_alpha_2, b_beta_1 = permutations[eff_slot_perm_idx]

    def _wrap_fn(fn_name: str, body: str) -> str:
        indented = textwrap.indent(body.rstrip() + "\n", "    ")
        return f"def {fn_name}(seq):\n{indented}"

    helpers_alpha_src = (
        _wrap_fn("_cand_alpha_1", b_alpha_1)
        + "\n"
        + _wrap_fn("_cand_alpha_2", b_alpha_2)
    )
    helpers_beta_src = _wrap_fn("_cand_beta_1", b_beta_1)

    target_pipeline_src = textwrap.dedent(
        """\
        def _post_reverse(seq):
            return list(reversed(seq))

        def _post_inc(seq):
            return [v + 1 for v in seq]

        def _post_dedup(seq):
            seen = set()
            out = []
            for v in seq:
                if v not in seen:
                    seen.add(v)
                    out.append(v)
            return out

        def stage_pre_filter(seq):
            return list(seq)

        def stage_core_transform(seq):
            return _cand_alpha_1(seq)

        def solve_pipeline(seq):
            return stage_pre_filter(seq)
        """
    )

    task_visible_input_sets = [
        [
            [3, 3, 6, 1, 4, 2],
            [2, 5, 5, 8, 1, 7],
            [4, 1, 9, 2, 2, 5],
        ],
        [
            [2, 5, 5, 8, 1, 7],
            [4, 1, 9, 2, 2, 5],
            [3, 3, 6, 1, 4, 2],
        ],
        [
            [4, 1, 9, 2, 2, 5],
            [3, 3, 6, 1, 4, 2],
            [2, 5, 5, 8, 1, 7],
        ],
        [
            [3, 5, 5, 2, 6, 1],
            [2, 5, 5, 8, 1, 7],
            [4, 1, 9, 2, 2, 5],
        ],
    ]
    visible_inputs = task_visible_input_sets[task_index % len(task_visible_input_sets)]
    visible_tests = [
        dict(
            input=list(inp),
            expected_output=_ground_truth_mechanism(
                family_name, list(inp), param_a, param_b, task_index=task_index
            ),
        )
        for inp in visible_inputs
    ]

    teaching_probe = [4, 1, 6, 2, 5, 3]
    teaching_example = dict(
        invented_word=INVENTED_WORDS[family_name],
        input=list(teaching_probe),
        expected_output=_ground_truth_helper_only(family_name, list(teaching_probe), param_a, param_b),
    )

    return dict(
        family_name=family_name,
        seed=seed,
        task_index=task_index,
        freeze_journal_sha256=freeze_sha,
        files={
            "helpers_alpha.py": helpers_alpha_src,
            "helpers_beta.py": helpers_beta_src,
            "target_pipeline.py": target_pipeline_src,
        },
        target_file="target_pipeline.py",
        target_function="solve_pipeline",
        candidate_call_sites=[
            "stage_pre_filter(seq)",
            "stage_core_transform(seq)",
            "solve_pipeline(seq)",
        ],
        type_signature="list[int] -> list[int]",
        invented_word=INVENTED_WORDS[family_name],
        visible_tests=visible_tests,
        teaching_example=teaching_example,
    )


def evaluate_helper_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluates a candidate helper primitive on private held-out inputs inside the evaluator process."""
    seed = int(payload["seed"])
    family_name = str(payload["family_name"])
    source_code = str(payload.get("source_code", ""))
    proposed_name = str(payload.get("proposed_name", ""))

    param_a, param_b, _ = _private_parameters(seed, family_name)
    private_inputs = _generate_private_test_inputs(seed, family_name)[:4]

    passed = 0
    if source_code.strip() and proposed_name:
        try:
            env = compile_safe_module(source_code)
            fn = env.get(proposed_name)
            if callable(fn):
                for inp in private_inputs:
                    expected = _ground_truth_helper_only(family_name, list(inp), param_a, param_b)
                    got = fn(list(inp))
                    if got == expected:
                        passed += 1
        except Exception:
            passed = 0

    total = len(private_inputs)
    return dict(
        family_name=family_name,
        proposed_name=proposed_name,
        heldout_total=total,
        heldout_passed=passed,
        heldout_accuracy=float(passed / max(1, total)),
        heldout_all_passed=bool(passed == total),
    )


def _build_four_lab_ground_truth(seed: int, family_name: str) -> dict[str, Any]:
    """Constructs the ground-truth instances and answers for the 4 distinct downstream labs:
      1. Language Lab (compositional utterance interpretation under learned invented-word binding)
      2. Coding Lab (multi-batch Python function synthesis composing the primitive with filtering & aggregation)
      3. Reasoning Lab (abductive inversion, counterfactual intervention, and relational ordering)
      4. World Lab (5x5 locked-door gridworld navigation & keypad code derivation)."""
    param_a, param_b, _ = _private_parameters(seed, family_name)
    inv_word = INVENTED_WORDS[family_name]
    rng = random.Random(seed * 613 + sum(ord(c) for c in family_name))

    def gt_prim(xs: list[int]) -> list[int]:
        return _ground_truth_helper_only(family_name, list(xs), param_a, param_b)

    # 1. Language Lab: 4 compositional natural-language queries with unfamiliar phrasing
    lang_inputs = [
        [4, -2, 5, 1, 3],
        [2, 6, -1, 4, 2, 5],
        [-3, 1, 4, 0, 2],
        [5, 3, -2, 4, 1],
    ]
    lang_queries = [
        dict(
            query_id="lang_q0_reverse",
            utterance=f"Please {inv_word} the sequence {lang_inputs[0]} and then reverse the order of the result.",
            expected=list(reversed(gt_prim(lang_inputs[0]))),
        ),
        dict(
            query_id="lang_q1_nonneg",
            utterance=f"First apply {inv_word} on {lang_inputs[1]}, then keep only non-negative values.",
            expected=[v for v in gt_prim(lang_inputs[1]) if v >= 0],
        ),
        dict(
            query_id="lang_q2_shift_plus2",
            utterance=f"Compute {inv_word} for {lang_inputs[2]} and add 2 to each resulting element.",
            expected=[v + 2 for v in gt_prim(lang_inputs[2])],
        ),
        dict(
            query_id="lang_q3_scalar_sum",
            utterance=f"What is the scalar sum after you {inv_word} the list {lang_inputs[3]}?",
            expected=int(sum(gt_prim(lang_inputs[3]))),
        ),
    ]

    # 2. Coding Lab: multi-batch filtering & accumulation synthesis task
    public_batches = [[3, 1, 4, 2], [-2, 5, 0, 3], [-4, -1, 6, -3, 2]]
    public_coding_expected = [sum(v for v in gt_prim(row) if v >= 0) for row in public_batches]
    private_coding_test_batches: list[list[list[int]]] = []
    private_coding_expected: list[list[int]] = []
    for _ in range(6):
        batch = [[rng.randint(-6, 8) for _ in range(rng.randint(4, 6))] for _ in range(3)]
        private_coding_test_batches.append(batch)
        private_coding_expected.append([sum(v for v in gt_prim(row) if v >= 0) for row in batch])

    # Public calibration support examples for autonomous cross-domain adapter induction
    lang_support_seq = [-4, -3, 2, -5]
    lang_support_base = gt_prim(lang_support_seq)
    language_support_examples = [
        dict(
            utterance=f"Apply {inv_word} to {lang_support_seq}.",
            input_seq=lang_support_seq,
            expected_output=list(lang_support_base),
        ),
        dict(
            utterance=f"Please {inv_word} the sequence {lang_support_seq} and reverse the order.",
            input_seq=lang_support_seq,
            expected_output=list(reversed(lang_support_base)),
        ),
        dict(
            utterance=f"First apply {inv_word} on {lang_support_seq} and keep non-negative values.",
            input_seq=lang_support_seq,
            expected_output=[v for v in lang_support_base if v >= 0],
        ),
        dict(
            utterance=f"Compute {inv_word} for {lang_support_seq} and add 2 to each element.",
            input_seq=lang_support_seq,
            expected_output=[v + 2 for v in lang_support_base],
        ),
        dict(
            utterance=f"What is the scalar sum after you {inv_word} the list {lang_support_seq}?",
            input_seq=lang_support_seq,
            expected_output=int(sum(lang_support_base)),
        ),
    ]

    reas_sup_abd_cands = [[1, 3, 2, 4], [5, -2, 3, 1], [2, 4, -1, 5]]
    reas_sup_abd_y = gt_prim(reas_sup_abd_cands[1])
    reas_sup_abd_exp = next(i for i, c in enumerate(reas_sup_abd_cands) if gt_prim(c) == reas_sup_abd_y)
    reas_sup_cf_base = [2, -1, 3, 4]
    reas_sup_cf_deltas = [-2, 1, 4]
    reas_sup_cf_exp = max(
        reas_sup_cf_deltas,
        key=lambda d: (sum(gt_prim([reas_sup_cf_base[0] + d] + reas_sup_cf_base[1:])), -abs(d)),
    )
    reas_sup_ents = {"X": [1, 1, 2], "Y": [7, -6, 8, -5], "Z": [3, -2, 4]}
    reas_sup_ord_exp = sorted(
        reas_sup_ents.keys(),
        key=lambda k: (sum(abs(v) for v in gt_prim(reas_sup_ents[k])), k),
    )
    reas_sup_span_cands = [[2, 2, 2, 2], [8, -7, 9, -6], [4, -2, 5, -1]]
    reas_sup_span_exp = min(
        range(len(reas_sup_span_cands)),
        key=lambda idx: (
            (max(gt_prim(reas_sup_span_cands[idx])) - min(gt_prim(reas_sup_span_cands[idx])))
            if gt_prim(reas_sup_span_cands[idx])
            else 0,
            idx,
        ),
    )
    reasoning_support_examples = dict(
        abductive_inversion=dict(
            candidates=reas_sup_abd_cands,
            target_output=reas_sup_abd_y,
            expected=reas_sup_abd_exp,
        ),
        counterfactual_intervention=dict(
            base_input=reas_sup_cf_base,
            candidate_deltas=reas_sup_cf_deltas,
            expected=reas_sup_cf_exp,
        ),
        relational_ordering=dict(
            entities=reas_sup_ents,
            expected=reas_sup_ord_exp,
        ),
        invariant_min_span=dict(
            candidates=reas_sup_span_cands,
            expected=reas_sup_span_exp,
        ),
    )

    world_support_beacons = [[2, -1, 4, 3], [5, 0, -3, 2, 4], [-2, 6, 1, 3, 5]]
    world_support_examples = []
    for wb in world_support_beacons:
        yb = gt_prim(wb)
        world_support_examples.append(
            dict(
                beacon_sequence=wb,
                expected_pad=sum(abs(v) for v in yb) % 3,
                expected_unlock_code=(yb[0] + yb[-1]) if yb else 0,
            )
        )

    # 3. Reasoning Lab: 4 abductive, counterfactual, and relational deduction problems
    # Problem 0: Abductive state inversion — identify which candidate input produces target_y
    abductive_candidates = [
        [2, 5, 1, 4, 3],
        [6, -1, 3, 2, 4],
        [1, 4, 4, -2, 5],
        [5, 2, -3, 1, 6],
        [3, 3, 2, 7, -1],
    ]
    true_abd_idx = (seed + len(family_name)) % len(abductive_candidates)
    abductive_target_y = gt_prim(abductive_candidates[true_abd_idx])
    # Ensure unique match index (first matching index is canonical)
    canonical_abd_idx = next(
        i for i, c in enumerate(abductive_candidates) if gt_prim(c) == abductive_target_y
    )

    # Problem 1: Counterfactual single-index intervention at index 0
    cf_base_input = [3, -1, 4, 2, 5]
    cf_deltas = [-3, -1, 1, 3]
    best_delta = max(
        cf_deltas,
        key=lambda d: (sum(gt_prim([cf_base_input[0] + d] + cf_base_input[1:])), -abs(d)),
    )

    # Problem 2: Relational ordering of 4 entities by L1 norm of transformed output
    entities = {
        "A": [1, 2, 1, 2],
        "B": [6, -5, 7, -4, 6],
        "C": [3, 0, -2, 4],
        "D": [8, 7, -6, 5, -4, 9],
    }
    ordered_entities = sorted(
        entities.keys(),
        key=lambda k: (sum(abs(v) for v in gt_prim(entities[k])), k),
    )

    # Problem 3: Span minimization selection across 4 candidates
    span_candidates = [
        [1, 1, 2, 1],
        [7, -6, 8, -5, 4],
        [4, -3, 5, -2, 6],
        [-5, 7, -4, 8, -3],
    ]
    best_span_idx = min(
        range(len(span_candidates)),
        key=lambda idx: (
            (max(gt_prim(span_candidates[idx])) - min(gt_prim(span_candidates[idx])))
            if gt_prim(span_candidates[idx])
            else 0,
            idx,
        ),
    )

    reasoning_problems = [
        dict(
            problem_id="reas_p0_abductive_inversion",
            kind="abductive_inversion",
            candidates=abductive_candidates,
            target_output=abductive_target_y,
            expected=canonical_abd_idx,
        ),
        dict(
            problem_id="reas_p1_counterfactual_intervention",
            kind="counterfactual_intervention",
            base_input=cf_base_input,
            candidate_deltas=cf_deltas,
            expected=best_delta,
        ),
        dict(
            problem_id="reas_p2_relational_ordering",
            kind="relational_ordering",
            entities=entities,
            expected=ordered_entities,
        ),
        dict(
            problem_id="reas_p3_invariant_min_span",
            kind="invariant_min_span",
            candidates=span_candidates,
            expected=best_span_idx,
        ),
    ]

    # 4. World Lab: 4 locked-door 5x5 gridworld episodes with distinct beacon sequences
    beacon_sequences = [
        [3, -2, 5, 1, 4],
        [6, 1, -3, 2, 5],
        [-1, 4, 2, 7, 3],
        [5, 2, 2, -4, 6],
    ]
    world_episodes = []
    for ep_idx, b_seq in enumerate(beacon_sequences):
        y_b = gt_prim(b_seq)
        target_pad = sum(abs(v) for v in y_b) % 3
        unlock_code = (y_b[0] + y_b[-1]) if y_b else 0
        world_episodes.append(
            dict(
                episode_id=f"world_ep_{ep_idx}",
                beacon_sequence=b_seq,
                start_pos=[0, 0],
                beacon_pos=[0, 2],
                pad_positions={"0": [2, 0], "1": [2, 2], "2": [2, 4]},
                door_pos=[3, 2],
                goal_pos=[4, 2],
                walls=[[3, 0], [3, 1], [3, 3], [3, 4]],
                step_budget=16,
                expected_pad=target_pad,
                expected_unlock_code=unlock_code,
            )
        )

    return dict(
        invented_word=inv_word,
        language_queries=lang_queries,
        language_support_examples=language_support_examples,
        coding_public_example=dict(batches=public_batches, expected=public_coding_expected),
        coding_private_batches=private_coding_test_batches,
        coding_private_expected=private_coding_expected,
        reasoning_problems=reasoning_problems,
        reasoning_support_examples=reasoning_support_examples,
        world_episodes=world_episodes,
        world_support_examples=world_support_examples,
    )


def _simulate_world_episode(ep_spec: dict[str, Any], actions: list[dict[str, Any]]) -> bool:
    """Simulates a 5x5 locked-door gridworld episode in the isolated evaluator worker."""
    x, y = ep_spec["start_pos"]
    beacon_pos = tuple(ep_spec["beacon_pos"])
    pad_positions = {int(k): tuple(v) for k, v in ep_spec["pad_positions"].items()}
    door_pos = tuple(ep_spec["door_pos"])
    goal_pos = tuple(ep_spec["goal_pos"])
    walls = {tuple(w) for w in ep_spec["walls"]}
    budget = int(ep_spec["step_budget"])

    inspected_beacon = False
    door_unlocked = False
    move_deltas = {"UP": (0, 1), "DOWN": (0, -1), "LEFT": (-1, 0), "RIGHT": (1, 0)}

    if len(actions) > budget:
        return False

    for step_act in actions:
        kind = str(step_act.get("action", ""))
        if kind in move_deltas:
            dx, dy = move_deltas[kind]
            nx, ny = x + dx, y + dy
            if not (0 <= nx <= 4 and 0 <= ny <= 4):
                return False
            if (nx, ny) in walls:
                return False
            if (nx, ny) == door_pos and not door_unlocked:
                return False
            x, y = nx, ny
        elif kind == "INSPECT_BEACON":
            if (x, y) != beacon_pos:
                return False
            inspected_beacon = True
        elif kind == "UNLOCK_DOOR":
            if not inspected_beacon:
                return False
            req_pad = int(ep_spec["expected_pad"])
            req_code = int(ep_spec["expected_unlock_code"])
            if (x, y) != pad_positions[req_pad]:
                return False
            if int(step_act.get("code", -999999)) != req_code:
                return False
            door_unlocked = True
        else:
            return False

    return bool(door_unlocked and (x, y) == goal_pos)


def init_four_lab_tasks(payload: dict[str, Any]) -> dict[str, Any]:
    """Returns the learner-visible problem specifications for Language, Coding,
    Reasoning, and World Labs without exposing ground-truth private answers."""
    seed = int(payload["seed"])
    family_name = str(payload["family_name"])
    param_a, param_b, _ = _private_parameters(seed, family_name)
    gt = _build_four_lab_ground_truth(seed, family_name)

    teaching_probe = [4, 1, 6, 2, 5, 3]
    teaching_out = _ground_truth_helper_only(family_name, list(teaching_probe), param_a, param_b)

    public_lang = [
        dict(query_id=q["query_id"], utterance=q["utterance"])
        for q in gt["language_queries"]
    ]
    public_reasoning = []
    for p in gt["reasoning_problems"]:
        pub_p = {k: v for k, v in p.items() if k != "expected"}
        public_reasoning.append(pub_p)

    public_world = []
    for ep in gt["world_episodes"]:
        pub_ep = {
            k: v
            for k, v in ep.items()
            if k not in ("expected_pad", "expected_unlock_code")
        }
        public_world.append(pub_ep)

    return dict(
        seed=seed,
        family_name=family_name,
        invented_word=gt["invented_word"],
        dialogue_teaching_utterance=(
            f"Dialogue note: '{gt['invented_word']}' denotes the transformation that maps "
            f"{teaching_probe} to {teaching_out}."
        ),
        teaching_example=dict(
            invented_word=gt["invented_word"],
            input=teaching_probe,
            expected_output=teaching_out,
        ),
        language_lab_queries=public_lang,
        language_support_examples=gt["language_support_examples"],
        coding_lab_spec=dict(
            target_function_name="filter_and_accumulate_records",
            description="Apply the bound primitive to each batch row, filter values >= 0, and return the list of per-row sums.",
            public_example=gt["coding_public_example"],
        ),
        reasoning_lab_problems=public_reasoning,
        reasoning_support_examples=gt["reasoning_support_examples"],
        world_lab_episodes=public_world,
        world_support_examples=gt["world_support_examples"],
    )


def evaluate_four_lab_transfer(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluates learner submissions across all 4 distinct downstream labs (Language,
    Coding, Reasoning, World) plus pre/post old-skill retention inside the isolated
    evaluator process."""
    seed = int(payload["seed"])
    family_name = str(payload["family_name"])
    gt = _build_four_lab_ground_truth(seed, family_name)

    # 1. Language Lab evaluation
    lang_sub: dict[str, Any] = payload.get("language_lab_answers", {})
    lang_hits = 0
    for q in gt["language_queries"]:
        qid = q["query_id"]
        if qid in lang_sub and lang_sub[qid] == q["expected"]:
            lang_hits += 1
    lang_acc = float(lang_hits / len(gt["language_queries"]))

    # 2. Coding Lab evaluation on 6 private unseen multi-batch inputs
    coding_src = str(payload.get("coding_lab_program_source", ""))
    coding_hits = 0
    if coding_src.strip():
        try:
            c_env = compile_safe_module(coding_src)
            c_fn = c_env.get("filter_and_accumulate_records")
            if callable(c_fn):
                for batch_in, batch_exp in zip(
                    gt["coding_private_batches"], gt["coding_private_expected"]
                ):
                    got = c_fn([list(r) for r in batch_in])
                    if got == batch_exp:
                        coding_hits += 1
        except Exception:
            coding_hits = 0
    coding_acc = float(coding_hits / len(gt["coding_private_batches"]))

    # 3. Reasoning Lab evaluation
    reas_sub: dict[str, Any] = payload.get("reasoning_lab_answers", {})
    reas_hits = 0
    for p in gt["reasoning_problems"]:
        pid = p["problem_id"]
        if pid in reas_sub and reas_sub[pid] == p["expected"]:
            reas_hits += 1
    reas_acc = float(reas_hits / len(gt["reasoning_problems"]))

    # 4. World Lab evaluation (simulating 5x5 locked-door gridworld physics)
    world_sub: dict[str, list[dict[str, Any]]] = payload.get("world_lab_trajectories", {})
    world_hits = 0
    for ep in gt["world_episodes"]:
        epid = ep["episode_id"]
        traj = world_sub.get(epid, [])
        if isinstance(traj, list) and _simulate_world_episode(ep, traj):
            world_hits += 1
    world_acc = float(world_hits / len(gt["world_episodes"]))

    # 5. Old-skill retention across all 4 labs
    old_sub: dict[str, Any] = payload.get("old_skills_answers", {})
    old_hits = 0
    old_total = 4
    if old_sub.get("old_lang_reverse") == [4, 3, 2, 1]:
        old_hits += 1
    if old_sub.get("old_coding_even_sum") == 12:
        old_hits += 1
    if old_sub.get("old_reasoning_argmax") == 2:
        old_hits += 1
    if old_sub.get("old_world_unlocked_goal") == [2, 2]:
        old_hits += 1
    old_retention_acc = float(old_hits / old_total)

    overall_four_lab_acc = float((lang_acc + coding_acc + reas_acc + world_acc) / 4.0)
    res = dict(
        seed=seed,
        family_name=family_name,
        invented_word=gt["invented_word"],
        language_lab_accuracy=lang_acc,
        coding_lab_accuracy=coding_acc,
        reasoning_lab_accuracy=reas_acc,
        world_lab_accuracy=world_acc,
        overall_four_lab_accuracy=overall_four_lab_acc,
        old_skill_retention_accuracy=old_retention_acc,
        private_inputs_exposed_to_learner=False,
        separate_evaluator_process=True,
    )
    res["evaluator_receipt_sha256"] = hashlib.sha256(
        json.dumps(res, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return res


def evaluate_blackbox_submission(payload: dict[str, Any]) -> dict[str, Any]:
    seed = int(payload["seed"])
    family_name = str(payload["family_name"])
    task_index = int(payload.get("task_index", 0))
    patched_module_source = str(payload.get("patched_module_source", ""))
    promoted_primitive_source = str(payload.get("promoted_primitive_source", ""))
    promoted_primitive_name = str(payload.get("promoted_primitive_name", ""))
    cross_lab_coding_enabled = bool(payload.get("cross_lab_coding_enabled", False))
    cross_lab_reasoning_enabled = bool(payload.get("cross_lab_reasoning_enabled", False))

    param_a, param_b, _ = _private_parameters(seed, family_name)
    private_inputs = _generate_private_test_inputs(seed + 1009 * task_index, family_name)

    hidden_hits = 0
    if patched_module_source.strip():
        try:
            env = compile_safe_module(patched_module_source)
            target_fn = env.get("solve_pipeline")
            if callable(target_fn):
                for inp in private_inputs:
                    expected = _ground_truth_mechanism(
                        family_name, list(inp), param_a, param_b, task_index=task_index
                    )
                    got = target_fn(list(inp))
                    if got == expected:
                        hidden_hits += 1
        except Exception:
            hidden_hits = 0

    hidden_accuracy = float(hidden_hits / len(private_inputs))

    # If full 4-lab submission payload is included, evaluate all 4 labs directly
    four_lab_result: dict[str, Any] | None = None
    if "four_lab_submission" in payload and isinstance(payload["four_lab_submission"], dict):
        fl_payload = dict(payload["four_lab_submission"])
        fl_payload["seed"] = seed
        fl_payload["family_name"] = family_name
        four_lab_result = evaluate_four_lab_transfer(fl_payload)

    coding_hits = 0
    reasoning_hits = 0
    if four_lab_result is not None:
        coding_acc = float(four_lab_result["coding_lab_accuracy"]) if cross_lab_coding_enabled else 0.0
        reasoning_acc = float(four_lab_result["reasoning_lab_accuracy"]) if cross_lab_reasoning_enabled else 0.0
    else:
        if promoted_primitive_source.strip() and promoted_primitive_name:
            try:
                prim_env = compile_safe_module(promoted_primitive_source)
                prim_fn = prim_env.get(promoted_primitive_name)
                if callable(prim_fn):
                    for inp in private_inputs:
                        expected_prim = _ground_truth_helper_only(family_name, list(inp), param_a, param_b)
                        if cross_lab_coding_enabled:
                            got_coding = [v for v in prim_fn(list(inp)) if v >= 0]
                            if got_coding == [v for v in expected_prim if v >= 0]:
                                coding_hits += 1
                        if cross_lab_reasoning_enabled:
                            got_prim = prim_fn(list(inp))
                            if (
                                isinstance(got_prim, list)
                                and sum(abs(v) for v in got_prim) == sum(abs(v) for v in expected_prim)
                                and got_prim == expected_prim
                            ):
                                reasoning_hits += 1
            except Exception:
                coding_hits = 0
                reasoning_hits = 0

        coding_acc = float(coding_hits / len(private_inputs)) if cross_lab_coding_enabled else 0.0
        reasoning_acc = float(reasoning_hits / len(private_inputs)) if cross_lab_reasoning_enabled else 0.0

    receipt_payload = dict(
        seed=seed,
        family_name=family_name,
        hidden_tests_total=len(private_inputs),
        hidden_tests_passed=hidden_hits,
        hidden_accuracy=hidden_accuracy,
        cross_lab_coding_accuracy=coding_acc,
        cross_lab_reasoning_accuracy=reasoning_acc,
        private_inputs_exposed_to_learner=False,
        separate_evaluator_process=True,
    )
    if four_lab_result is not None:
        receipt_payload["four_lab_transfer"] = four_lab_result
    receipt_sha256 = hashlib.sha256(
        json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    receipt_payload["evaluator_receipt_sha256"] = receipt_sha256
    return receipt_payload


def main() -> None:
    raw = sys.stdin.read()
    payload = json.loads(raw)
    mode = str(payload.get("mode", "evaluate_submission"))
    if mode == "init_workspace":
        result = init_workspace(payload)
    elif mode == "evaluate_helper_proposal":
        result = evaluate_helper_proposal(payload)
    elif mode == "init_four_lab_tasks":
        result = init_four_lab_tasks(payload)
    elif mode == "evaluate_four_lab_transfer":
        result = evaluate_four_lab_transfer(payload)
    else:
        result = evaluate_blackbox_submission(payload)
    sys.stdout.write(json.dumps(result, sort_keys=True))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
