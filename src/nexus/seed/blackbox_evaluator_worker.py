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


def _ground_truth_mechanism(family_name: str, xs: list[int], param_a: int, param_b: int) -> list[int]:
    """Ground-truth target pipeline behavior (true helper followed by family post-step)."""
    mid = _ground_truth_helper_only(family_name, xs, param_a, param_b)
    if family_name == "ulib_window_checksum":
        return list(reversed(mid))
    if family_name == "ulib_runlength_bucket":
        return [v + 1 for v in mid]
    if family_name == "ulib_zigzag_interleave":
        seen: set[int] = set()
        dedup: list[int] = []
        for v in mid:
            if v not in seen:
                seen.add(v)
                dedup.append(v)
        return dedup
    raise ValueError(f"unknown_family:{family_name}")


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
    """Generates the multi-file unseen library workspace after rule freeze."""
    seed = int(payload["seed"])
    family_name = str(payload["family_name"])
    freeze_sha = str(payload.get("freeze_journal_sha256", ""))
    if not freeze_sha:
        raise ValueError("stage_b_requires_frozen_rule_journal_sha256")

    param_a, param_b, slot_perm_idx = _private_parameters(seed, family_name)
    true_body, decoy_1, decoy_2 = _build_helper_bodies(family_name, param_a, param_b)

    # Permute which candidate function name gets the true helper vs the 2 decoys
    permutations = [
        (true_body, decoy_1, decoy_2),
        (decoy_1, true_body, decoy_2),
        (decoy_1, decoy_2, true_body),
    ]
    b_alpha_1, b_alpha_2, b_beta_1 = permutations[slot_perm_idx]

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

    visible_inputs = [
        [3, 3, 6, 1, 4, 2],
        [2, 5, 5, 8, 1, 7],
        [4, 1, 9, 2, 2, 5],
    ]
    visible_tests = [
        dict(
            input=list(inp),
            expected_output=_ground_truth_mechanism(family_name, list(inp), param_a, param_b),
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


def evaluate_blackbox_submission(payload: dict[str, Any]) -> dict[str, Any]:
    seed = int(payload["seed"])
    family_name = str(payload["family_name"])
    patched_module_source = str(payload.get("patched_module_source", ""))
    promoted_primitive_source = str(payload.get("promoted_primitive_source", ""))
    promoted_primitive_name = str(payload.get("promoted_primitive_name", ""))
    cross_lab_coding_enabled = bool(payload.get("cross_lab_coding_enabled", False))
    cross_lab_reasoning_enabled = bool(payload.get("cross_lab_reasoning_enabled", False))

    param_a, param_b, _ = _private_parameters(seed, family_name)
    private_inputs = _generate_private_test_inputs(seed, family_name)

    hidden_hits = 0
    if patched_module_source.strip():
        try:
            env = compile_safe_module(patched_module_source)
            target_fn = env.get("solve_pipeline")
            if callable(target_fn):
                for inp in private_inputs:
                    expected = _ground_truth_mechanism(family_name, list(inp), param_a, param_b)
                    got = target_fn(list(inp))
                    if got == expected:
                        hidden_hits += 1
        except Exception:
            hidden_hits = 0

    hidden_accuracy = float(hidden_hits / len(private_inputs))

    coding_hits = 0
    reasoning_hits = 0
    if promoted_primitive_source.strip() and promoted_primitive_name:
        try:
            prim_env = compile_safe_module(promoted_primitive_source)
            prim_fn = prim_env.get(promoted_primitive_name)
            if callable(prim_fn):
                for inp in private_inputs:
                    expected_prim = _ground_truth_helper_only(family_name, list(inp), param_a, param_b)
                    if cross_lab_coding_enabled:
                        got_coding = sorted(prim_fn(list(inp)))
                        if got_coding == sorted(expected_prim):
                            coding_hits += 1
                    if cross_lab_reasoning_enabled:
                        got_prim = prim_fn(list(inp))
                        if (
                            isinstance(got_prim, list)
                            and len(got_prim) == len(expected_prim)
                            and (
                                not got_prim
                                or (got_prim[0] % 2 == expected_prim[0] % 2 and got_prim[-1] == expected_prim[-1])
                            )
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
    else:
        result = evaluate_blackbox_submission(payload)
    sys.stdout.write(json.dumps(result, sort_keys=True))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
