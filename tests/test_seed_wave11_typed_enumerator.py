"""Unit tests for Wave-11 bounded typed program enumerator and recursive AST interpreter."""

from __future__ import annotations

import ast
from pathlib import Path

from nexus.seed.wave11_typed_program_enumerator import (
    ALLOWED_PRIM_OPCODES,
    ConstNode,
    EvolvedMacroNode,
    PrimOpNode,
    TypedMacroLibrary,
    TypedProgramEnumerator,
    TypeTag,
    VarNode,
    eval_expr_ast,
    execute_wave11_program_ast,
    expr_ast_from_dict,
    synthesize_wave11_typed,
)


def test_wave11_zero_lambda_and_ast_clean() -> None:
    root = Path(__file__).resolve().parents[1]
    w11_path = root / "src" / "nexus" / "seed" / "wave11_typed_program_enumerator.py"
    source = w11_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(w11_path))

    lambdas = [node for node in ast.walk(tree) if isinstance(node, ast.Lambda)]
    assert len(lambdas) == 0, f"Found forbidden lambda nodes: {lambdas}"
    assert len(ALLOWED_PRIM_OPCODES) == 14


def test_wave11_eval_expr_ast_and_serialization_roundtrip() -> None:
    x_node = VarNode()
    guard = PrimOpNode(
        "SEQ_EQ",
        (x_node, PrimOpNode("REVERSE", (x_node,), TypeTag.SEQ)),
        TypeTag.BOOL,
    )
    rot_body = PrimOpNode(
        "APPEND_TOK",
        (
            PrimOpNode("TAIL", (x_node,), TypeTag.SEQ),
            PrimOpNode("HEAD", (x_node,), TypeTag.TOK),
        ),
        TypeTag.SEQ,
    )
    rot_macro = EvolvedMacroNode(
        macro_id="seq_macro_1",
        body_ast=rot_body,
        args=(x_node,),
        out_type=TypeTag.SEQ,
    )
    then_ast = PrimOpNode(
        "APPEND_TOK",
        (rot_macro, ConstNode("!", TypeTag.TOK)),
        TypeTag.SEQ,
    )
    prog = PrimOpNode("IF_THEN_ELSE", (guard, then_ast, x_node), TypeTag.SEQ)

    serialized = prog.to_dict()
    rebuilt = expr_ast_from_dict(serialized)
    assert rebuilt.canonical_key() == prog.canonical_key()
    assert eval_expr_ast(rebuilt, ("r", "a", "r")) == ("a", "r", "r", "!")
    assert eval_expr_ast(rebuilt, ("a", "b")) == ("a", "b")


def test_wave11_synthetic_tiers_and_deep_macro_composition() -> None:
    enumerator = TypedProgramEnumerator(max_guard_size=6, max_transform_size=7)
    lib = TypedMacroLibrary()

    # 1. Synthetic Tier-0 base parity task
    core_even = [
        ((), ("!",)),
        (("a",), ("a",)),
        (("a", "b"), ("a", "b", "!")),
        (("b",), ("b",)),
    ]
    all_even = core_even + [(("c", "d", "e", "f"), ("c", "d", "e", "f", "!"))]
    res_t0 = synthesize_wave11_typed(core_even, all_even, lib, enumerator)
    assert res_t0.abstained is False
    assert res_t0.gate_evals == 0
    assert execute_wave11_program_ast(res_t0.program_ast_dict, ("u", "v")) == (
        "u",
        "v",
        "!",
    )

    # 2. Synthetic Tier-3 guard invention (palindrome -> append '#')
    core_pal = [
        ((), ("#",)),
        (("a",), ("a", "#")),
        (("r", "a", "r"), ("r", "a", "r", "#")),
        (("a", "b"), ("a", "b")),
    ]
    all_pal = core_pal + [(("k", "o", "k"), ("k", "o", "k", "#"))]
    res_pal = synthesize_wave11_typed(core_pal, all_pal, lib, enumerator)
    assert res_pal.abstained is False
    assert len(res_pal.invented_macros) == 1

    # 3. Synthetic Tier-3 transform invention (even -> rotate_left)
    core_even_rot = [
        (("a",), ("a",)),
        (("a", "b"), ("b", "a")),
        (("x", "y", "z"), ("x", "y", "z")),
        (("c", "d", "e", "f"), ("d", "e", "f", "c")),
    ]
    all_even_rot = core_even_rot + [(("m", "n", "p", "q"), ("n", "p", "q", "m"))]
    res_rot = synthesize_wave11_typed(core_even_rot, all_even_rot, lib, enumerator)
    assert res_rot.abstained is False
    assert len(res_rot.invented_macros) == 1

    # 4. Synthetic deep compositional task: palindrome -> rotate_left + '!'
    core_pal_rot_bang = [
        (("a",), ("a", "!")),
        (("b", "b"), ("b", "b", "!")),
        (("r", "a", "r"), ("a", "r", "r", "!")),
        (("a", "b"), ("a", "b")),
    ]
    all_pal_rot_bang = core_pal_rot_bang + [
        (("a", "b", "c", "a"), ("a", "b", "c", "a"))
    ]
    res_deep_nexus = synthesize_wave11_typed(
        core_pal_rot_bang, all_pal_rot_bang, lib, enumerator
    )
    assert res_deep_nexus.abstained is False
    assert res_deep_nexus.sub_macro_reused is True

    # Compare against scratch enumerator on the exact same deep compositional task
    scratch_lib = TypedMacroLibrary(
        use_macro_evolution=False,
        use_pruning=False,
        use_cold_archive=False,
        use_memoization=False,
        use_schemas=False,
    )
    res_deep_scratch = synthesize_wave11_typed(
        core_pal_rot_bang, all_pal_rot_bang, scratch_lib, enumerator
    )
    assert res_deep_scratch.abstained is False
    assert res_deep_nexus.synthesis_evals < res_deep_scratch.synthesis_evals
    assert execute_wave11_program_ast(
        res_deep_nexus.program_ast_dict, ("p", "q", "p")
    ) == ("q", "p", "p", "!")
    assert execute_wave11_program_ast(
        res_deep_scratch.program_ast_dict, ("p", "q", "p")
    ) == ("q", "p", "p", "!")

    # 5. Synthetic odd_drop_bang (stepwise transform) + pal_drop_bang + pal_rot_q
    core_odd_drop = [
        ((), ()),
        (("a", "b", "c"), ("b", "c", "!")),
        (("a", "b"), ("a", "b")),
        (("d",), ("!",)),
    ]
    all_odd_drop = core_odd_drop + [(("k", "l", "m"), ("l", "m", "!"))]
    res_odd_drop = synthesize_wave11_typed(
        core_odd_drop, all_odd_drop, lib, enumerator
    )
    assert res_odd_drop.abstained is False
    assert execute_wave11_program_ast(
        res_odd_drop.program_ast_dict, ("x", "y", "z")
    ) == ("y", "z", "!")

    core_pal_drop = [
        (("a",), ("!",)),
        (("b", "b"), ("b", "!")),
        (("r", "a", "r"), ("a", "r", "!")),
        (("a", "b"), ("a", "b")),
    ]
    all_pal_drop = core_pal_drop + [(("a", "b", "c", "a"), ("a", "b", "c", "a"))]
    res_pal_drop = synthesize_wave11_typed(
        core_pal_drop, all_pal_drop, lib, enumerator
    )
    assert res_pal_drop.abstained is False
    assert res_pal_drop.sub_macro_reused is True
    assert execute_wave11_program_ast(
        res_pal_drop.program_ast_dict, ("r", "a", "r")
    ) == ("a", "r", "!")

    core_pal_rot_q = [
        (("a",), ("a", "?")),
        (("b", "b"), ("b", "b", "?")),
        (("r", "a", "r"), ("a", "r", "r", "?")),
        (("a", "b"), ("a", "b")),
    ]
    all_pal_rot_q = core_pal_rot_q + [(("a", "b", "c", "a"), ("a", "b", "c", "a"))]
    res_pal_rot_q = synthesize_wave11_typed(
        core_pal_rot_q, all_pal_rot_q, lib, enumerator
    )
    assert res_pal_rot_q.abstained is False
    assert res_pal_rot_q.sub_macro_reused is True
    assert execute_wave11_program_ast(
        res_pal_rot_q.program_ast_dict, ("r", "a", "r")
    ) == ("a", "r", "r", "?")

    # Verify scratch_lib also solves pal_drop, pal_rot_q, head_eq_last, and len_ge3
    res_pal_drop_scratch = synthesize_wave11_typed(
        core_pal_drop, all_pal_drop, scratch_lib, enumerator
    )
    assert execute_wave11_program_ast(
        res_pal_drop_scratch.program_ast_dict, ("r", "a", "r")
    ) == ("a", "r", "!")

    res_pal_rot_q_scratch = synthesize_wave11_typed(
        core_pal_rot_q, all_pal_rot_q, scratch_lib, enumerator
    )
    assert execute_wave11_program_ast(
        res_pal_rot_q_scratch.program_ast_dict, ("r", "a", "r")
    ) == ("a", "r", "r", "?")

    core_head_last = [
        ((), ()),
        (("a",), ("a", "#")),
        (("a", "b", "c", "a"), ("a", "b", "c", "a", "#")),
        (("a", "b"), ("a", "b")),
    ]
    all_head_last = core_head_last + [
        (("x", "y", "z", "x"), ("x", "y", "z", "x", "#"))
    ]
    res_hl = synthesize_wave11_typed(
        core_head_last, all_head_last, scratch_lib, enumerator
    )
    assert execute_wave11_program_ast(
        res_hl.program_ast_dict, ("k", "l", "m", "k")
    ) == ("k", "l", "m", "k", "#")
    assert execute_wave11_program_ast(res_hl.program_ast_dict, ("k", "l")) == (
        "k",
        "l",
    )

    core_ge3 = [
        ((), ()),
        (("a",), ("a",)),
        (("a", "b", "c"), ("a", "b", "c", "#")),
        (("a", "b"), ("a", "b")),
    ]
    all_ge3 = core_ge3 + [(("p", "q", "r", "s"), ("p", "q", "r", "s", "#"))]
    res_ge3 = synthesize_wave11_typed(core_ge3, all_ge3, scratch_lib, enumerator)
    assert execute_wave11_program_ast(
        res_ge3.program_ast_dict, ("m", "n", "p")
    ) == ("m", "n", "p", "#")
    assert execute_wave11_program_ast(res_ge3.program_ast_dict, ("u", "v")) == (
        "u",
        "v",
    )


def test_wave10_pre_amend_forensic_artifact_verification() -> None:
    import sys

    root = Path(__file__).resolve().parents[1]
    if str(root / "scripts") not in sys.path:
        sys.path.insert(0, str(root / "scripts"))
    from verify_wave11_typed_enumerator import (
        inspect_wave11_learner_ast,
        verify_wave10_pre_amend_artifact,
    )

    ast_report = inspect_wave11_learner_ast(
        root / "src" / "nexus" / "seed" / "wave11_typed_program_enumerator.py"
    )
    assert ast_report["valid"] is True
    assert ast_report["lambda_count"] == 0

    w10_report = verify_wave10_pre_amend_artifact(root)
    assert w10_report["valid"] is True, f"Failed: {w10_report}"


def test_wave11_artifact_verification_when_present() -> None:
    import pytest
    import sys

    root = Path(__file__).resolve().parents[1]
    artifact_path = root / "artifacts" / "seed_wave11_typed_enumerator.json"
    if not artifact_path.exists():
        pytest.skip("Wave-11 assessment artifact not yet generated (Pre-Commit-1 freeze)")

    if str(root / "scripts") not in sys.path:
        sys.path.insert(0, str(root / "scripts"))
    from verify_wave11_typed_enumerator import verify_wave11_artifact

    report = verify_wave11_artifact(root)
    assert report["valid"] is True, f"Verification failed: {report}"
    assert report["replayed_rows"] == 192

