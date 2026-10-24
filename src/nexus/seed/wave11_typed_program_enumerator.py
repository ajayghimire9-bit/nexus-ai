"""Wave-11 Bounded Typed Program Enumerator and Direct Recursive AST Interpreter.

Replaces handwritten composite candidate tables and attached callables with:
1. A strongly typed algebraic expression tree (``ExprAST``) over ``TypeTag``
   (``SEQ``, ``TOK``, ``INT``, ``BOOL``):
   - ``VarNode``
   - ``ConstNode``
   - ``PrimOpNode`` (strictly over the 14 atomic primitive opcodes)
   - ``EvolvedMacroNode`` (wrapping a discovered ``ExprAST`` subtree with zero
     attached callables)
2. A pure recursive tree-walking interpreter ``eval_expr_ast(node, x)`` with
   zero ``lambda`` functions and zero composite lookup tables.
3. A shared bottom-up size-bounded ``TypedProgramEnumerator`` with observational
   equivalence pruning on the current task's collected public inputs, shared
   identically across all 4 compared methods:
   - ``equal_typed_scratch``
   - ``ordinary_persistent_memoization``
   - ``nexus_typed_without_pruning``
   - ``nexus_typed_full``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .correspondence_env import PUBLIC_SLOTS
from .cross_domain_analogy import OUTPUT_FIELDS, Seq, UNIVERSAL_PROBES, as_seq
from .deconfounded_equal_capability import (
    _probe_environment_label_blind,
    distill_source_schemas_with_cost,
)

WAVE11_TYPED_METHODS: Tuple[str, ...] = (
    "equal_typed_scratch",
    "ordinary_persistent_memoization",
    "nexus_typed_without_pruning",
    "nexus_typed_full",
)

# ---------------------------------------------------------------------------
# 1. Strongly Typed Algebraic AST & Pure Tree-Walking Interpreter
# ---------------------------------------------------------------------------


class TypeTag(str, Enum):
    SEQ = "SEQ"
    TOK = "TOK"
    INT = "INT"
    BOOL = "BOOL"


PRIM_SEQUENCE_OPS: Tuple[str, ...] = (
    "HEAD",
    "TAIL",
    "INIT",
    "LAST",
    "REVERSE",
    "CONCAT",
    "APPEND_TOK",
)

PRIM_SCALAR_REL_OPS: Tuple[str, ...] = (
    "LEN",
    "MOD2",
    "TOK_EQ",
    "SEQ_EQ",
    "INT_EQ",
    "INT_GE",
)

PRIM_BRANCH_OPS: Tuple[str, ...] = ("IF_THEN_ELSE",)

ALLOWED_PRIM_OPCODES: Tuple[str, ...] = (
    PRIM_SEQUENCE_OPS + PRIM_SCALAR_REL_OPS + PRIM_BRANCH_OPS
)

BASE_TOKEN_CONSTANTS: Tuple[str, ...] = ("!", "?", "#")
BASE_INT_CONSTANTS: Tuple[int, ...] = (0, 1, 2, 3)


@dataclass(frozen=True)
class VarNode:
    out_type: TypeTag = TypeTag.SEQ

    def ast_nodes(self) -> int:
        return 1

    def effective_step_size(self) -> int:
        return 1

    def canonical_key(self) -> str:
        return "x"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_kind": "VarNode",
            "out_type": self.out_type.value,
        }


@dataclass(frozen=True)
class ConstNode:
    value: Union[str, int, bool]
    out_type: TypeTag

    def ast_nodes(self) -> int:
        return 1

    def effective_step_size(self) -> int:
        return 1

    def canonical_key(self) -> str:
        return f"const({self.out_type.value}:{repr(self.value)})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_kind": "ConstNode",
            "value": self.value,
            "out_type": self.out_type.value,
        }


@dataclass(frozen=True)
class PrimOpNode:
    op_name: str
    args: Tuple["ExprAST", ...]
    out_type: TypeTag

    def __post_init__(self) -> None:
        if self.op_name not in ALLOWED_PRIM_OPCODES:
            raise ValueError(f"Disallowed primitive opcode: {self.op_name}")

    def ast_nodes(self) -> int:
        total = 1
        for arg in self.args:
            total += arg.ast_nodes()
        return total

    def effective_step_size(self) -> int:
        total = 1
        for arg in self.args:
            total += arg.effective_step_size()
        return total

    def canonical_key(self) -> str:
        inner = ", ".join(a.canonical_key() for a in self.args)
        return f"{self.op_name}({inner})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_kind": "PrimOpNode",
            "op_name": self.op_name,
            "args": [a.to_dict() for a in self.args],
            "out_type": self.out_type.value,
        }


@dataclass(frozen=True)
class EvolvedMacroNode:
    macro_id: str
    body_ast: "ExprAST"
    args: Tuple["ExprAST", ...]
    out_type: TypeTag

    def ast_nodes(self) -> int:
        return self.body_ast.ast_nodes()

    def effective_step_size(self) -> int:
        return 1

    def canonical_key(self) -> str:
        return f"macro:{self.macro_id}[{self.body_ast.canonical_key()}]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_kind": "EvolvedMacroNode",
            "macro_id": self.macro_id,
            "body_ast": self.body_ast.to_dict(),
            "args": [a.to_dict() for a in self.args],
            "out_type": self.out_type.value,
        }


ExprAST = Union[VarNode, ConstNode, PrimOpNode, EvolvedMacroNode]


def expr_ast_from_dict(data: Mapping[str, Any]) -> ExprAST:
    """Reconstruct an ``ExprAST`` from its serialized JSON dictionary."""
    node_kind = str(data.get("node_kind", "VarNode"))
    out_type = TypeTag(str(data.get("out_type", "SEQ")))
    if node_kind == "VarNode":
        return VarNode(out_type=out_type)
    if node_kind == "ConstNode":
        raw_val = data["value"]
        if out_type == TypeTag.INT:
            val: Union[str, int, bool] = int(raw_val)
        elif out_type == TypeTag.BOOL:
            val = bool(raw_val)
        else:
            val = str(raw_val)
        return ConstNode(value=val, out_type=out_type)
    if node_kind == "PrimOpNode":
        op_name = str(data["op_name"])
        args = tuple(expr_ast_from_dict(a) for a in data.get("args", ()))
        return PrimOpNode(op_name=op_name, args=args, out_type=out_type)
    if node_kind == "EvolvedMacroNode":
        macro_id = str(data["macro_id"])
        body_ast = expr_ast_from_dict(data["body_ast"])
        args = tuple(expr_ast_from_dict(a) for a in data.get("args", ()))
        return EvolvedMacroNode(
            macro_id=macro_id, body_ast=body_ast, args=args, out_type=out_type
        )
    raise ValueError(f"Unknown ExprAST node_kind: {node_kind}")


def eval_expr_ast(node: ExprAST, x: Seq) -> Any:
    """Pure recursive tree-walking interpreter over ``ExprAST``."""
    seq_x = as_seq(x)
    if isinstance(node, VarNode):
        return seq_x
    if isinstance(node, ConstNode):
        if node.out_type == TypeTag.INT:
            return int(node.value)
        if node.out_type == TypeTag.BOOL:
            return bool(node.value)
        return str(node.value)
    if isinstance(node, EvolvedMacroNode):
        if len(node.args) == 1:
            bound_x = as_seq(eval_expr_ast(node.args[0], seq_x))
            return eval_expr_ast(node.body_ast, bound_x)
        return eval_expr_ast(node.body_ast, seq_x)
    if isinstance(node, PrimOpNode):
        op = node.op_name
        if op == "IF_THEN_ELSE":
            cond = bool(eval_expr_ast(node.args[0], seq_x))
            if cond:
                return as_seq(eval_expr_ast(node.args[1], seq_x))
            return as_seq(eval_expr_ast(node.args[2], seq_x))

        if op == "HEAD":
            s_val = as_seq(eval_expr_ast(node.args[0], seq_x))
            return s_val[0] if len(s_val) > 0 else ""
        if op == "TAIL":
            s_val = as_seq(eval_expr_ast(node.args[0], seq_x))
            return s_val[1:]
        if op == "INIT":
            s_val = as_seq(eval_expr_ast(node.args[0], seq_x))
            return s_val[:-1]
        if op == "LAST":
            s_val = as_seq(eval_expr_ast(node.args[0], seq_x))
            return s_val[-1] if len(s_val) > 0 else ""
        if op == "REVERSE":
            s_val = as_seq(eval_expr_ast(node.args[0], seq_x))
            return s_val[::-1]
        if op == "CONCAT":
            lhs = as_seq(eval_expr_ast(node.args[0], seq_x))
            rhs = as_seq(eval_expr_ast(node.args[1], seq_x))
            return lhs + rhs
        if op == "APPEND_TOK":
            lhs = as_seq(eval_expr_ast(node.args[0], seq_x))
            tok = str(eval_expr_ast(node.args[1], seq_x))
            return lhs + (tok,) if tok != "" else lhs
        if op == "LEN":
            s_val = as_seq(eval_expr_ast(node.args[0], seq_x))
            return len(s_val)
        if op == "MOD2":
            i_val = int(eval_expr_ast(node.args[0], seq_x))
            return i_val % 2
        if op == "TOK_EQ":
            t1 = str(eval_expr_ast(node.args[0], seq_x))
            t2 = str(eval_expr_ast(node.args[1], seq_x))
            return bool(t1 != "" and t2 != "" and t1 == t2)
        if op == "SEQ_EQ":
            s1 = as_seq(eval_expr_ast(node.args[0], seq_x))
            s2 = as_seq(eval_expr_ast(node.args[1], seq_x))
            return s1 == s2
        if op == "INT_EQ":
            i1 = int(eval_expr_ast(node.args[0], seq_x))
            i2 = int(eval_expr_ast(node.args[1], seq_x))
            return i1 == i2
        if op == "INT_GE":
            i1 = int(eval_expr_ast(node.args[0], seq_x))
            i2 = int(eval_expr_ast(node.args[1], seq_x))
            return i1 >= i2
        raise ValueError(f"Unhandled primitive opcode: {op}")
    raise TypeError(f"Unsupported ExprAST node: {type(node)}")


def make_abstain_program_dict() -> Dict[str, Any]:
    return {
        "kind": "abstain",
        "domain_kind": "sequence",
        "root_ast": VarNode().to_dict(),
    }


def make_program_dict(root_ast: ExprAST, kind: str = "typed_expr") -> Dict[str, Any]:
    return {
        "kind": kind,
        "domain_kind": "sequence",
        "root_ast": root_ast.to_dict(),
        "canonical_key": root_ast.canonical_key(),
        "ast_nodes": root_ast.ast_nodes(),
        "effective_step_size": root_ast.effective_step_size(),
    }


def execute_wave11_program_ast(program_ast: Mapping[str, Any], value: Any) -> Seq:
    """Reconstruct and execute a serialized Wave-11 ``program_ast`` via ``eval_expr_ast``."""
    kind = str(program_ast.get("kind", "abstain"))
    seq_val = as_seq(value)
    if kind == "abstain":
        return seq_val
    root_dict = program_ast.get("root_ast")
    if not isinstance(root_dict, Mapping):
        return seq_val
    root_node = expr_ast_from_dict(root_dict)
    return as_seq(eval_expr_ast(root_node, seq_val))


def typed_catalog_manifest() -> Dict[str, Any]:
    """Return the canonical typed primitive grammar manifest shared by all 4 methods."""
    return {
        "type_tags": [t.value for t in TypeTag],
        "sequence_opcodes": list(PRIM_SEQUENCE_OPS),
        "scalar_relational_opcodes": list(PRIM_SCALAR_REL_OPS),
        "branch_opcodes": list(PRIM_BRANCH_OPS),
        "token_constants": list(BASE_TOKEN_CONSTANTS),
        "int_constants": list(BASE_INT_CONSTANTS),
    }


# ---------------------------------------------------------------------------
# 2. Metered Evaluation Helpers & Shared Bounded Typed Program Enumerator
# ---------------------------------------------------------------------------


def _eval_ast_on_pairs(
    program_node: ExprAST, pairs: Sequence[Tuple[Seq, Seq]]
) -> Tuple[bool, int]:
    evals = 0
    for inp, out in pairs:
        evals += 1
        if as_seq(eval_expr_ast(program_node, inp)) != out:
            return False, evals
    return True, evals


def _guard_explains_metered(
    guard_node: ExprAST, pairs: Sequence[Tuple[Seq, Seq]]
) -> Tuple[bool, int]:
    evals = 0
    changed = [inp != out for inp, out in pairs]
    if not any(changed):
        return False, 0
    for (inp, _), is_changed in zip(pairs, changed):
        evals += 1
        if bool(eval_expr_ast(guard_node, inp)) != is_changed:
            return False, evals
    return True, evals


def _prerequisite_alphabet_closed_typed(pairs: Sequence[Tuple[Seq, Seq]]) -> bool:
    allowed_markers = set(BASE_TOKEN_CONSTANTS)
    for src, dst in pairs:
        src_set = set(src)
        for tok in dst:
            if tok not in src_set and tok not in allowed_markers:
                return False
    return True


class TypedProgramEnumerator:
    """Shared bottom-up size-bounded typed AST enumerator with observational pruning.

    Enumerates well-typed ``INT``, ``TOK``, ``BOOL``, and ``SEQ`` ``ExprAST``
    trees in strict order of AST size using only the atomic primitive opcodes.
    """

    def __init__(
        self,
        max_guard_size: int = 6,
        max_transform_size: int = 7,
        public_budget: int = 10,
    ) -> None:
        self.max_guard_size = int(max_guard_size)
        self.max_transform_size = int(max_transform_size)
        self.public_budget = int(public_budget)

    @staticmethod
    def enumerate_tier0_base_guards() -> List[ExprAST]:
        """Return the canonical atomic length & parity ``BOOL`` ASTs (Tier 0)."""
        x_node = VarNode()
        len_x = PrimOpNode("LEN", (x_node,), TypeTag.INT)
        mod2_len_x = PrimOpNode("MOD2", (len_x,), TypeTag.INT)
        return [
            PrimOpNode("INT_EQ", (mod2_len_x, ConstNode(0, TypeTag.INT)), TypeTag.BOOL),
            PrimOpNode("INT_EQ", (mod2_len_x, ConstNode(1, TypeTag.INT)), TypeTag.BOOL),
            PrimOpNode("INT_EQ", (len_x, ConstNode(0, TypeTag.INT)), TypeTag.BOOL),
            PrimOpNode("INT_EQ", (len_x, ConstNode(1, TypeTag.INT)), TypeTag.BOOL),
            PrimOpNode("INT_EQ", (len_x, ConstNode(2, TypeTag.INT)), TypeTag.BOOL),
            PrimOpNode("INT_EQ", (len_x, ConstNode(3, TypeTag.INT)), TypeTag.BOOL),
        ]

    @staticmethod
    def enumerate_tier0_base_transforms() -> List[ExprAST]:
        """Return the canonical depth-1 atomic ``SEQ`` transform ASTs (Tier 0)."""
        x_node = VarNode()
        transforms: List[ExprAST] = []
        for tok in BASE_TOKEN_CONSTANTS:
            transforms.append(
                PrimOpNode(
                    "APPEND_TOK", (x_node, ConstNode(tok, TypeTag.TOK)), TypeTag.SEQ
                )
            )
        transforms.append(PrimOpNode("CONCAT", (x_node, x_node), TypeTag.SEQ))
        transforms.append(PrimOpNode("REVERSE", (x_node,), TypeTag.SEQ))
        return transforms

    def enumerate_and_search_tier3(
        self,
        core_pairs: Sequence[Tuple[Seq, Seq]],
        all_pairs: Sequence[Tuple[Seq, Seq]],
    ) -> Tuple[Optional[Tuple[ExprAST, ExprAST, PrimOpNode]], int]:
        """Bottom-up size-bounded enumeration over multi-node ``BOOL`` and ``SEQ`` ASTs.

        Expands size levels incrementally (``level = 4, 5, 6, 7``) with
        observational equivalence pruning on ``all_inputs``, charging every
        evaluation to ``synthesis_evals``.
        """
        evals = 0
        all_inputs: Tuple[Seq, ...] = tuple(inp for inp, _ in all_pairs)
        x_node = VarNode()

        # Typed size buckets: size -> list of canonical ExprAST
        int_by_size: Dict[int, List[ExprAST]] = {
            1: [ConstNode(v, TypeTag.INT) for v in BASE_INT_CONSTANTS],
            2: [PrimOpNode("LEN", (x_node,), TypeTag.INT)],
            3: [
                PrimOpNode(
                    "MOD2",
                    (PrimOpNode("LEN", (x_node,), TypeTag.INT),),
                    TypeTag.INT,
                )
            ],
        }
        tok_by_size: Dict[int, List[ExprAST]] = {
            1: [ConstNode(t, TypeTag.TOK) for t in BASE_TOKEN_CONSTANTS],
            2: [
                PrimOpNode("HEAD", (x_node,), TypeTag.TOK),
                PrimOpNode("LAST", (x_node,), TypeTag.TOK),
            ],
            3: [
                PrimOpNode(
                    "HEAD",
                    (PrimOpNode("TAIL", (x_node,), TypeTag.SEQ),),
                    TypeTag.TOK,
                ),
                PrimOpNode(
                    "LAST",
                    (PrimOpNode("INIT", (x_node,), TypeTag.SEQ),),
                    TypeTag.TOK,
                ),
            ],
        }

        seq_by_size: Dict[int, List[ExprAST]] = {1: [x_node]}
        seen_seq_sigs: Dict[Tuple[Seq, ...], ExprAST] = {}
        sig_x = tuple(as_seq(eval_expr_ast(x_node, inp)) for inp in all_inputs)
        seen_seq_sigs[sig_x] = x_node

        def _register_seq_candidates(size_k: int, cands: Sequence[ExprAST]) -> int:
            local_evals = 0
            bucket: List[ExprAST] = []
            for cand in cands:
                sig_list: List[Seq] = []
                for inp in all_inputs:
                    local_evals += 1
                    sig_list.append(as_seq(eval_expr_ast(cand, inp)))
                sig = tuple(sig_list)
                if sig not in seen_seq_sigs:
                    seen_seq_sigs[sig] = cand
                    bucket.append(cand)
            seq_by_size[size_k] = bucket
            return local_evals

        # Expand SEQ size 2 and 3 (base building blocks)
        cands_s2: List[ExprAST] = [
            PrimOpNode("TAIL", (x_node,), TypeTag.SEQ),
            PrimOpNode("INIT", (x_node,), TypeTag.SEQ),
            PrimOpNode("REVERSE", (x_node,), TypeTag.SEQ),
        ]
        evals += _register_seq_candidates(2, cands_s2)

        cands_s3: List[ExprAST] = []
        for tok_node in tok_by_size[1]:
            cands_s3.append(
                PrimOpNode("APPEND_TOK", (x_node, tok_node), TypeTag.SEQ)
            )
        cands_s3.append(PrimOpNode("CONCAT", (x_node, x_node), TypeTag.SEQ))
        for s2_node in seq_by_size[2]:
            for uop in ("REVERSE", "TAIL", "INIT"):
                cands_s3.append(PrimOpNode(uop, (s2_node,), TypeTag.SEQ))
        evals += _register_seq_candidates(3, cands_s3)

        bool_by_size: Dict[int, List[ExprAST]] = {}
        seen_bool_sigs: Dict[Tuple[bool, ...], ExprAST] = {}
        tier0_guards = self.enumerate_tier0_base_guards()
        tier0_guard_keys = {g.canonical_key() for g in tier0_guards}
        for tg in tier0_guards:
            sig_g = tuple(bool(eval_expr_ast(tg, inp)) for inp in all_inputs)
            seen_bool_sigs[sig_g] = tg

        tier0_transforms = self.enumerate_tier0_base_transforms()

        # Pre-check which Tier-0 guards explain core_pairs
        explaining_tier0_guards: List[ExprAST] = []
        for tg in tier0_guards:
            ok_g, g_ev = _guard_explains_metered(tg, core_pairs)
            evals += g_ev
            if ok_g:
                explaining_tier0_guards.append(tg)

        explaining_multi_guards: List[ExprAST] = []
        multi_transforms_accum: List[ExprAST] = []

        max_level = max(self.max_guard_size, self.max_transform_size)
        for level in range(4, max_level + 1):
            # 1. Expand BOOL guards at size == level (if level <= max_guard_size)
            new_explaining_guards: List[ExprAST] = []
            if level <= self.max_guard_size:
                bool_cands: List[ExprAST] = []
                if level == 4:
                    len_x = int_by_size[2][0]
                    for ic in int_by_size[1]:
                        if isinstance(ic, ConstNode) and int(ic.value) >= 1:
                            bool_cands.append(
                                PrimOpNode("INT_GE", (len_x, ic), TypeTag.BOOL)
                            )
                    for s2 in seq_by_size[2]:
                        bool_cands.append(
                            PrimOpNode("SEQ_EQ", (x_node, s2), TypeTag.BOOL)
                        )
                    for t2 in tok_by_size[2]:
                        for t1 in tok_by_size[1]:
                            bool_cands.append(
                                PrimOpNode("TOK_EQ", (t2, t1), TypeTag.BOOL)
                            )
                elif level == 5:
                    for i_lhs in range(len(tok_by_size[2])):
                        for i_rhs in range(i_lhs + 1, len(tok_by_size[2])):
                            bool_cands.append(
                                PrimOpNode(
                                    "TOK_EQ",
                                    (tok_by_size[2][i_lhs], tok_by_size[2][i_rhs]),
                                    TypeTag.BOOL,
                                )
                            )
                    for s2 in seq_by_size[2]:
                        for s2_other in seq_by_size[2]:
                            if s2.canonical_key() != s2_other.canonical_key():
                                bool_cands.append(
                                    PrimOpNode(
                                        "SEQ_EQ", (s2, s2_other), TypeTag.BOOL
                                    )
                                )
                elif level == 6:
                    for s2 in seq_by_size[2]:
                        for s3 in seq_by_size[3]:
                            bool_cands.append(
                                PrimOpNode("SEQ_EQ", (s2, s3), TypeTag.BOOL)
                            )
                    for t2 in tok_by_size[2]:
                        for t3 in tok_by_size[3]:
                            bool_cands.append(
                                PrimOpNode("TOK_EQ", (t2, t3), TypeTag.BOOL)
                            )

                level_bools: List[ExprAST] = []
                for bc in bool_cands:
                    if bc.canonical_key() in tier0_guard_keys:
                        continue
                    sig_b_list: List[bool] = []
                    for inp in all_inputs:
                        evals += 1
                        sig_b_list.append(bool(eval_expr_ast(bc, inp)))
                    sig_b = tuple(sig_b_list)
                    if sig_b not in seen_bool_sigs:
                        seen_bool_sigs[sig_b] = bc
                        level_bools.append(bc)
                        ok_b, b_ev = _guard_explains_metered(bc, core_pairs)
                        evals += b_ev
                        if ok_b:
                            new_explaining_guards.append(bc)
                            explaining_multi_guards.append(bc)
                bool_by_size[level] = level_bools

                # Test newly discovered explaining BOOL guards against Tier-0 base transforms
                for g_ast in new_explaining_guards:
                    for t_ast in tier0_transforms:
                        prog = PrimOpNode(
                            "IF_THEN_ELSE", (g_ast, t_ast, x_node), TypeTag.SEQ
                        )
                        ok_p, p_ev = _eval_ast_on_pairs(prog, all_pairs)
                        evals += p_ev
                        if ok_p:
                            return (g_ast, t_ast, prog), evals

            # 2. Expand SEQ transforms at size == level (if level <= max_transform_size)
            new_seq_transforms: List[ExprAST] = []
            if level <= self.max_transform_size:
                seq_cands: List[ExprAST] = []
                # APPEND_TOK(seq_arg, tok_arg) where size(seq_arg) + size(tok_arg) == level - 1
                for s_arg_size in range(1, level - 1):
                    t_arg_size = (level - 1) - s_arg_size
                    for s_node in seq_by_size.get(s_arg_size, ()):
                        for t_node in tok_by_size.get(t_arg_size, ()):
                            seq_cands.append(
                                PrimOpNode(
                                    "APPEND_TOK", (s_node, t_node), TypeTag.SEQ
                                )
                            )
                # CONCAT(seq_a, seq_b) for level == 4
                if level == 4:
                    for s2 in seq_by_size.get(2, ()):
                        seq_cands.append(
                            PrimOpNode("CONCAT", (s2, x_node), TypeTag.SEQ)
                        )
                        seq_cands.append(
                            PrimOpNode("CONCAT", (x_node, s2), TypeTag.SEQ)
                        )
                evals += _register_seq_candidates(level, seq_cands)
                new_seq_transforms = list(seq_by_size.get(level, ()))
                multi_transforms_accum.extend(new_seq_transforms)

            # 3. Test explaining Tier-0 guards against newly enumerated SEQ transforms at this level
            if explaining_tier0_guards and new_seq_transforms:
                for g_ast in explaining_tier0_guards:
                    for t_ast in new_seq_transforms:
                        prog = PrimOpNode(
                            "IF_THEN_ELSE", (g_ast, t_ast, x_node), TypeTag.SEQ
                        )
                        ok_p, p_ev = _eval_ast_on_pairs(prog, all_pairs)
                        evals += p_ev
                        if ok_p:
                            return (g_ast, t_ast, prog), evals

            # 4. Test newly discovered explaining BOOL guards against all multi-node SEQ transforms so far
            if new_explaining_guards and multi_transforms_accum:
                for g_ast in new_explaining_guards:
                    for t_ast in multi_transforms_accum:
                        prog = PrimOpNode(
                            "IF_THEN_ELSE", (g_ast, t_ast, x_node), TypeTag.SEQ
                        )
                        ok_p, p_ev = _eval_ast_on_pairs(prog, all_pairs)
                        evals += p_ev
                        if ok_p:
                            return (g_ast, t_ast, prog), evals

            # 5. Test previously discovered explaining BOOL guards against newly enumerated SEQ transforms
            if explaining_multi_guards and new_seq_transforms:
                for g_ast in explaining_multi_guards:
                    if g_ast in new_explaining_guards:
                        continue
                    for t_ast in new_seq_transforms:
                        prog = PrimOpNode(
                            "IF_THEN_ELSE", (g_ast, t_ast, x_node), TypeTag.SEQ
                        )
                        ok_p, p_ev = _eval_ast_on_pairs(prog, all_pairs)
                        evals += p_ev
                        if ok_p:
                            return (g_ast, t_ast, prog), evals

        return None, evals


# ---------------------------------------------------------------------------
# 3. Self-Evolving Typed Macro Library & Cost-Ordered Meta-Control
# ---------------------------------------------------------------------------


@dataclass
class EvolvedTypedOperator:
    name: str
    kind: str  # "bool_macro", "seq_macro", or "program_macro"
    macro_node: EvolvedMacroNode
    prerequisite_name: str = "alphabet_closed"
    uses: int = 0
    created_step: int = 0
    last_used_step: int = 0

    @property
    def ast_cost(self) -> int:
        return self.macro_node.ast_nodes()


@dataclass
class MemoizedTypedProgramEntry:
    signature_name: str
    root_ast: ExprAST
    uses: int = 1
    created_step: int = 0
    last_used_step: int = 0


@dataclass
class TypedMacroLibrary:
    use_macro_evolution: bool = True
    use_pruning: bool = True
    use_cold_archive: bool = True
    use_memoization: bool = False
    use_schemas: bool = True
    step: int = 0
    schemas_distilled: bool = False
    operators: Dict[str, EvolvedTypedOperator] = field(default_factory=dict)
    cold_archive: Dict[str, EvolvedTypedOperator] = field(default_factory=dict)
    mdl_pinned_names: set[str] = field(default_factory=set)
    solved_program_history: List[ExprAST] = field(default_factory=list)
    memoized_programs: Dict[str, MemoizedTypedProgramEntry] = field(
        default_factory=dict
    )
    pruned_names: List[str] = field(default_factory=list)
    reactivated_names: List[str] = field(default_factory=list)
    macro_counter: int = 0

    def ensure_schemas(self) -> int:
        if not self.use_schemas:
            return 0
        if not self.schemas_distilled:
            _, s_cost = distill_source_schemas_with_cost()
            self.schemas_distilled = True
            return s_cost
        return 0

    def empirical_roi_gate_policy(
        self, pairs: Sequence[Tuple[Seq, Seq]]
    ) -> Tuple[Dict[str, bool], int]:
        if not self.operators:
            return {}, 0
        unique_invariants = {
            op.prerequisite_name for op in self.operators.values()
        }
        invariant_results: Dict[str, bool] = {}
        gate_evals = 0
        for inv_name in unique_invariants:
            gate_evals += 1
            if inv_name == "alphabet_closed":
                allowed = _prerequisite_alphabet_closed_typed(pairs)
            else:
                allowed = True
            invariant_results[inv_name] = allowed
        return invariant_results, gate_evals

    def active_view(
        self, pairs: Sequence[Tuple[Seq, Seq]]
    ) -> Tuple[Dict[str, List[EvolvedTypedOperator]], int]:
        bool_macros: List[EvolvedTypedOperator] = []
        seq_macros: List[EvolvedTypedOperator] = []
        program_macros: List[EvolvedTypedOperator] = []
        if not self.use_macro_evolution or not self.operators:
            return {
                "bool_macros": bool_macros,
                "seq_macros": seq_macros,
                "program_macros": program_macros,
            }, 0

        invariant_results, gate_evals = self.empirical_roi_gate_policy(pairs)
        for op in self.operators.values():
            if not invariant_results.get(op.prerequisite_name, True):
                continue
            if op.kind == "bool_macro":
                bool_macros.append(op)
            elif op.kind == "seq_macro":
                seq_macros.append(op)
            elif op.kind == "program_macro":
                program_macros.append(op)
        return {
            "bool_macros": bool_macros,
            "seq_macros": seq_macros,
            "program_macros": program_macros,
        }, gate_evals

    def promote_ast_subtree(
        self, subtree_ast: ExprAST, kind: str
    ) -> Tuple[Optional[EvolvedTypedOperator], int]:
        """Promote a verified ``ExprAST`` subtree (`ast_nodes >= 2`) into an ``EvolvedMacroNode``."""
        if not self.use_macro_evolution:
            return None, 0
        body_ast = (
            subtree_ast.body_ast
            if isinstance(subtree_ast, EvolvedMacroNode)
            else subtree_ast
        )
        if body_ast.ast_nodes() < 2:
            return None, 0
        canon = body_ast.canonical_key()

        for existing in self.operators.values():
            if existing.macro_node.body_ast.canonical_key() == canon:
                existing.uses += 1
                existing.last_used_step = self.step
                if existing.uses >= 2:
                    self.mdl_pinned_names.add(existing.name)
                return existing, 0

        for arch_name, arch_op in list(self.cold_archive.items()):
            if arch_op.macro_node.body_ast.canonical_key() == canon:
                restored = self.cold_archive.pop(arch_name)
                restored.uses += 1
                restored.last_used_step = self.step
                self.operators[arch_name] = restored
                self.mdl_pinned_names.add(arch_name)
                return restored, 0

        self.macro_counter += 1
        out_type = (
            TypeTag.BOOL if kind == "bool_macro" else TypeTag.SEQ
        )
        macro_id = f"{kind}_{self.macro_counter}"
        macro_node = EvolvedMacroNode(
            macro_id=macro_id,
            body_ast=body_ast,
            args=(VarNode(),),
            out_type=out_type,
        )
        new_op = EvolvedTypedOperator(
            name=macro_id,
            kind=kind,
            macro_node=macro_node,
            uses=1,
            created_step=self.step,
            last_used_step=self.step,
        )
        self.operators[macro_id] = new_op
        if kind == "program_macro":
            self.mdl_pinned_names.add(macro_id)
            return new_op, 0
        return new_op, len(UNIVERSAL_PROBES)

    def record_operator_use(self, name: str) -> None:
        if name in self.operators:
            self.operators[name].uses += 1
            self.operators[name].last_used_step = self.step
            if self.operators[name].uses >= 2:
                self.mdl_pinned_names.add(name)

    def register_memoized_program(self, root_ast: ExprAST) -> None:
        if not self.use_memoization:
            return
        sig_key = root_ast.canonical_key()
        if sig_key not in self.memoized_programs:
            self.memoized_programs[sig_key] = MemoizedTypedProgramEntry(
                signature_name=sig_key,
                root_ast=root_ast,
                uses=1,
                created_step=self.step,
                last_used_step=self.step,
            )
        else:
            self.memoized_programs[sig_key].uses += 1
            self.memoized_programs[sig_key].last_used_step = self.step

    def compress_solved_programs_mdl(
        self, latest_ast: ExprAST, structure_discovered: bool
    ) -> int:
        if not self.use_macro_evolution or not structure_discovered:
            return 0
        self.solved_program_history.append(latest_ast)
        compression_evals = 0
        body_counts: Dict[str, int] = {}
        for past_ast in self.solved_program_history:
            compression_evals += 1
            if isinstance(past_ast, PrimOpNode) and past_ast.op_name == "IF_THEN_ELSE":
                for child in past_ast.args[:2]:
                    body = (
                        child.body_ast
                        if isinstance(child, EvolvedMacroNode)
                        else child
                    )
                    ck = body.canonical_key()
                    body_counts[ck] = body_counts.get(ck, 0) + 1

        for op_name, op in self.operators.items():
            ck = op.macro_node.body_ast.canonical_key()
            count = body_counts.get(ck, 0)
            if op.ast_cost + count * 1 < count * op.ast_cost:
                self.mdl_pinned_names.add(op_name)
        return compression_evals

    def usage_age_prune(self, min_age: int = 2, min_uses: int = 2) -> List[str]:
        if not self.use_pruning:
            return []
        demoted: List[str] = []
        for name, op in list(self.operators.items()):
            if name in self.mdl_pinned_names or op.kind == "program_macro":
                continue
            age = self.step - op.created_step
            if age >= min_age and op.uses < min_uses:
                demoted.append(name)
                self.pruned_names.append(name)
                if self.use_cold_archive:
                    self.cold_archive[name] = op
                del self.operators[name]
        return demoted

    def cold_archive_reactivate(
        self,
        core_pairs: Sequence[Tuple[Seq, Seq]],
        all_pairs: Sequence[Tuple[Seq, Seq]],
        tier0_transforms: Sequence[ExprAST],
        active_seq_macros: Sequence[EvolvedTypedOperator],
    ) -> Tuple[Optional[Tuple[PrimOpNode, Tuple[str, ...]]], int, int]:
        if not self.use_cold_archive or not self.cold_archive:
            return None, 0, 0
        if not _prerequisite_alphabet_closed_typed(all_pairs):
            return None, 1, 0

        archive_evals = 0
        syn_evals = 0
        x_node = VarNode()
        archived_bools = [
            op for op in self.cold_archive.values() if op.kind == "bool_macro"
        ]
        archived_seqs = [
            op for op in self.cold_archive.values() if op.kind == "seq_macro"
        ]

        for b_op in archived_bools:
            explains, p_ev = _guard_explains_metered(
                b_op.macro_node, core_pairs
            )
            archive_evals += p_ev
            if not explains:
                continue
            cand_transforms: List[Tuple[ExprAST, Optional[str]]] = [
                (t_ast, None) for t_ast in tier0_transforms
            ]
            for s_op in active_seq_macros:
                cand_transforms.append((s_op.macro_node, s_op.name))
            for s_op in archived_seqs:
                cand_transforms.append((s_op.macro_node, s_op.name))

            for t_ast, t_macro_name in cand_transforms:
                prog = PrimOpNode(
                    "IF_THEN_ELSE",
                    (b_op.macro_node, t_ast, x_node),
                    TypeTag.SEQ,
                )
                ok, c_ev = _eval_ast_on_pairs(prog, all_pairs)
                syn_evals += c_ev
                if ok:
                    restored_b = self.cold_archive.pop(b_op.name)
                    restored_b.uses += 1
                    restored_b.last_used_step = self.step
                    self.operators[b_op.name] = restored_b
                    self.mdl_pinned_names.add(b_op.name)
                    self.reactivated_names.append(b_op.name)
                    used = [b_op.name]
                    if t_macro_name is not None:
                        if t_macro_name in self.cold_archive:
                            restored_s = self.cold_archive.pop(t_macro_name)
                            restored_s.uses += 1
                            restored_s.last_used_step = self.step
                            self.operators[t_macro_name] = restored_s
                            self.mdl_pinned_names.add(t_macro_name)
                            self.reactivated_names.append(t_macro_name)
                        else:
                            self.record_operator_use(t_macro_name)
                        used.append(t_macro_name)
                    return (prog, tuple(used)), archive_evals, syn_evals

        return None, archive_evals, syn_evals


@dataclass
class Wave11SynthesisResult:
    program_ast_node: ExprAST
    program_ast_dict: Dict[str, Any]
    synthesis_evals: int
    archive_lookup_evals: int
    compression_evals: int
    gate_evals: int
    schema_distill_cost: int
    operator_compile_cost: int
    schema_distilled: bool
    used_operators: Tuple[str, ...]
    invented_macros: Tuple[str, ...]
    sub_macro_reused: bool
    full_program_macro_reused: bool
    memoized_program_reused: bool
    cold_archive_reactivated: bool
    abstained: bool
    pruned_this_step: Tuple[str, ...]


def synthesize_wave11_typed(
    core_pairs: Sequence[Tuple[Seq, Seq]],
    all_pairs: Sequence[Tuple[Seq, Seq]],
    lib: TypedMacroLibrary,
    enumerator: TypedProgramEnumerator,
) -> Wave11SynthesisResult:
    """Synthesize a typed ``ExprAST`` program under cost-ordered Tiers 0 -> 1 -> 2 -> 3."""
    lib.step += 1
    schema_cost = lib.ensure_schemas()
    schema_flag = schema_cost > 0 or lib.schemas_distilled

    synthesis_evals = 0
    archive_evals = 0
    compile_cost = 0
    gate_evals = 0
    x_node = VarNode()

    # Tier 0a: Persistent whole-program memoization lookup (for ordinary_persistent_memoization)
    if lib.use_memoization and lib.memoized_programs:
        for sig_name, entry in lib.memoized_programs.items():
            ok, c_ev = _eval_ast_on_pairs(entry.root_ast, all_pairs)
            synthesis_evals += c_ev
            if ok:
                entry.uses += 1
                entry.last_used_step = lib.step
                return Wave11SynthesisResult(
                    program_ast_node=entry.root_ast,
                    program_ast_dict=make_program_dict(entry.root_ast),
                    synthesis_evals=synthesis_evals,
                    archive_lookup_evals=0,
                    compression_evals=0,
                    gate_evals=0,
                    schema_distill_cost=schema_cost,
                    operator_compile_cost=0,
                    schema_distilled=schema_flag,
                    used_operators=(sig_name,),
                    invented_macros=(),
                    sub_macro_reused=False,
                    full_program_macro_reused=False,
                    memoized_program_reused=True,
                    cold_archive_reactivated=False,
                    abstained=False,
                    pruned_this_step=(),
                )

    tier0_guards = enumerator.enumerate_tier0_base_guards()
    tier0_transforms = enumerator.enumerate_tier0_base_transforms()
    tier0_guard_keys = {g.canonical_key() for g in tier0_guards}
    tier0_tf_keys = {t.canonical_key() for t in tier0_transforms}

    # Tier 0b: Base-First Atomic Slice (shared identically by all 4 methods)
    for g_ast in tier0_guards:
        explains, p_ev = _guard_explains_metered(g_ast, core_pairs)
        synthesis_evals += p_ev
        if not explains:
            continue
        for t_ast in tier0_transforms:
            prog = PrimOpNode("IF_THEN_ELSE", (g_ast, t_ast, x_node), TypeTag.SEQ)
            ok, c_ev = _eval_ast_on_pairs(prog, all_pairs)
            synthesis_evals += c_ev
            if ok:
                lib.register_memoized_program(prog)
                pruned = tuple(lib.usage_age_prune())
                return Wave11SynthesisResult(
                    program_ast_node=prog,
                    program_ast_dict=make_program_dict(prog),
                    synthesis_evals=synthesis_evals,
                    archive_lookup_evals=0,
                    compression_evals=0,
                    gate_evals=0,
                    schema_distill_cost=schema_cost,
                    operator_compile_cost=0,
                    schema_distilled=schema_flag,
                    used_operators=(),
                    invented_macros=(),
                    sub_macro_reused=False,
                    full_program_macro_reused=False,
                    memoized_program_reused=False,
                    cold_archive_reactivated=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # Tier 1: Active Evolved Macro Slice (gated once per task boundary by Empirical ROI Gate)
    view, g_ev = lib.active_view(all_pairs)
    gate_evals += g_ev

    # Tier 1a: Complete IF_THEN_ELSE program macros
    for p_op in view["program_macros"]:
        ok, c_ev = _eval_ast_on_pairs(p_op.macro_node, all_pairs)
        synthesis_evals += c_ev
        if ok:
            lib.record_operator_use(p_op.name)
            pruned = tuple(lib.usage_age_prune())
            return Wave11SynthesisResult(
                program_ast_node=p_op.macro_node,
                program_ast_dict=make_program_dict(p_op.macro_node, kind="macro_skill"),
                synthesis_evals=synthesis_evals,
                archive_lookup_evals=0,
                compression_evals=0,
                gate_evals=gate_evals,
                schema_distill_cost=schema_cost,
                operator_compile_cost=0,
                schema_distilled=schema_flag,
                used_operators=(p_op.name,),
                invented_macros=(),
                sub_macro_reused=True,
                full_program_macro_reused=True,
                memoized_program_reused=False,
                cold_archive_reactivated=False,
                abstained=False,
                pruned_this_step=pruned,
            )

    # Tier 1b: Active BOOL macros x (Tier-0 transforms + active SEQ macros + 1-step APPEND_TOK(M_seq, tok))
    if view["bool_macros"]:
        t1_seq_candidates: List[Tuple[ExprAST, Optional[str], bool]] = [
            (t_ast, None, False) for t_ast in tier0_transforms
        ]
        for s_op in view["seq_macros"]:
            t1_seq_candidates.append((s_op.macro_node, s_op.name, False))
            for tok in BASE_TOKEN_CONSTANTS:
                extended_ast = PrimOpNode(
                    "APPEND_TOK",
                    (s_op.macro_node, ConstNode(tok, TypeTag.TOK)),
                    TypeTag.SEQ,
                )
                t1_seq_candidates.append((extended_ast, s_op.name, True))

        for b_op in view["bool_macros"]:
            explains, p_ev = _guard_explains_metered(b_op.macro_node, core_pairs)
            synthesis_evals += p_ev
            if not explains:
                continue
            for t_ast, s_macro_name, is_extended in t1_seq_candidates:
                prog = PrimOpNode(
                    "IF_THEN_ELSE", (b_op.macro_node, t_ast, x_node), TypeTag.SEQ
                )
                ok, c_ev = _eval_ast_on_pairs(prog, all_pairs)
                synthesis_evals += c_ev
                if ok:
                    lib.record_operator_use(b_op.name)
                    used_list = [b_op.name]
                    invented_list: List[str] = []
                    new_structure = False
                    if s_macro_name is not None:
                        lib.record_operator_use(s_macro_name)
                        used_list.append(s_macro_name)
                        if is_extended:
                            ext_op, ext_c = lib.promote_ast_subtree(t_ast, "seq_macro")
                            compile_cost += ext_c
                            if ext_op is not None and ext_op.uses == 1:
                                invented_list.append(ext_op.name)
                        prog_op, _ = lib.promote_ast_subtree(prog, "program_macro")
                        if prog_op is not None:
                            used_list.append(prog_op.name)
                        new_structure = True
                    comp_ev = lib.compress_solved_programs_mdl(
                        prog, structure_discovered=new_structure
                    )
                    pruned = tuple(lib.usage_age_prune())
                    return Wave11SynthesisResult(
                        program_ast_node=prog,
                        program_ast_dict=make_program_dict(prog),
                        synthesis_evals=synthesis_evals,
                        archive_lookup_evals=0,
                        compression_evals=comp_ev,
                        gate_evals=gate_evals,
                        schema_distill_cost=schema_cost,
                        operator_compile_cost=compile_cost,
                        schema_distilled=schema_flag,
                        used_operators=tuple(used_list),
                        invented_macros=tuple(invented_list),
                        sub_macro_reused=True,
                        full_program_macro_reused=False,
                        memoized_program_reused=False,
                        cold_archive_reactivated=False,
                        abstained=False,
                        pruned_this_step=pruned,
                    )

    # Tier 2: Pre-Synthesis Cold Signature Archive Lookup
    if lib.use_cold_archive and lib.cold_archive:
        cold_hit, c_arch_ev, c_syn_ev = lib.cold_archive_reactivate(
            core_pairs, all_pairs, tier0_transforms, view["seq_macros"]
        )
        archive_evals += c_arch_ev
        synthesis_evals += c_syn_ev
        if cold_hit is not None:
            prog, used = cold_hit
            pruned = tuple(lib.usage_age_prune())
            return Wave11SynthesisResult(
                program_ast_node=prog,
                program_ast_dict=make_program_dict(prog),
                synthesis_evals=synthesis_evals,
                archive_lookup_evals=archive_evals,
                compression_evals=0,
                gate_evals=gate_evals,
                schema_distill_cost=schema_cost,
                operator_compile_cost=0,
                schema_distilled=schema_flag,
                used_operators=used,
                invented_macros=(),
                sub_macro_reused=True,
                full_program_macro_reused=False,
                memoized_program_reused=False,
                cold_archive_reactivated=True,
                abstained=False,
                pruned_this_step=pruned,
            )

    # Tier 3: Shared Bottom-Up Typed AST Enumerator
    t3_hit, t3_ev = enumerator.enumerate_and_search_tier3(core_pairs, all_pairs)
    synthesis_evals += t3_ev
    if t3_hit is not None:
        g_ast, t_ast, prog = t3_hit
        invented_list = []
        used_list = []
        if g_ast.canonical_key() not in tier0_guard_keys:
            g_op, g_c = lib.promote_ast_subtree(g_ast, "bool_macro")
            compile_cost += g_c
            if g_op is not None:
                used_list.append(g_op.name)
                if g_op.uses == 1:
                    invented_list.append(g_op.name)
        if t_ast.canonical_key() not in tier0_tf_keys:
            t_op, t_c = lib.promote_ast_subtree(t_ast, "seq_macro")
            compile_cost += t_c
            if t_op is not None:
                used_list.append(t_op.name)
                if t_op.uses == 1:
                    invented_list.append(t_op.name)
        if (
            g_ast.canonical_key() not in tier0_guard_keys
            and t_ast.canonical_key() not in tier0_tf_keys
        ):
            p_op, _ = lib.promote_ast_subtree(prog, "program_macro")
            if p_op is not None:
                used_list.append(p_op.name)

        lib.register_memoized_program(prog)
        comp_ev = lib.compress_solved_programs_mdl(prog, structure_discovered=True)
        pruned = tuple(lib.usage_age_prune())
        return Wave11SynthesisResult(
            program_ast_node=prog,
            program_ast_dict=make_program_dict(prog),
            synthesis_evals=synthesis_evals,
            archive_lookup_evals=archive_evals,
            compression_evals=comp_ev,
            gate_evals=gate_evals,
            schema_distill_cost=schema_cost,
            operator_compile_cost=compile_cost,
            schema_distilled=schema_flag,
            used_operators=tuple(used_list),
            invented_macros=tuple(invented_list),
            sub_macro_reused=False,
            full_program_macro_reused=False,
            memoized_program_reused=False,
            cold_archive_reactivated=False,
            abstained=False,
            pruned_this_step=pruned,
        )

    # Out-of-grammar -> honest abstention
    pruned = tuple(lib.usage_age_prune())
    return Wave11SynthesisResult(
        program_ast_node=x_node,
        program_ast_dict=make_abstain_program_dict(),
        synthesis_evals=synthesis_evals,
        archive_lookup_evals=archive_evals,
        compression_evals=0,
        gate_evals=gate_evals,
        schema_distill_cost=schema_cost,
        operator_compile_cost=0,
        schema_distilled=schema_flag,
        used_operators=(),
        invented_macros=(),
        sub_macro_reused=False,
        full_program_macro_reused=False,
        memoized_program_reused=False,
        cold_archive_reactivated=False,
        abstained=True,
        pruned_this_step=pruned,
    )


# ---------------------------------------------------------------------------
# 4. Label-Blind Equal-Capability Typed Learner
# ---------------------------------------------------------------------------


@dataclass
class Wave11TaskExecutionReport:
    method: str
    status: str
    admitted_field: Optional[str]
    chosen_slots: Tuple[str, ...]
    public_observations: List[Dict[str, Any]]
    program_ast: Dict[str, Any]
    public_consistent: bool
    ambiguous: bool
    oog_abstained: bool
    public_env_probes: int
    public_validation_probes: int
    channel_invariance_evals: int
    schema_distill_cost: int
    gate_evals: int
    archive_lookup_evals: int
    compression_evals: int
    synthesis_evals: int
    operator_compile_cost: int
    codegen_plus_synthesis: int
    total_work: int
    schema_distilled: bool
    used_operators: Tuple[str, ...]
    invented_macros: Tuple[str, ...]
    sub_macro_reused: bool
    full_program_macro_reused: bool
    memoized_program_reused: bool
    cold_archive_reactivated: bool
    pruned_operators: Tuple[str, ...]
    active_library_size: int
    cold_archive_size: int
    catalog_audit: Dict[str, int]
    trace: List[Dict[str, Any]]


class TypedEqualCapabilityLearner:
    """Strictly label-blind learner sharing ``TypedProgramEnumerator`` across all 4 methods."""

    def __init__(self, method: str, max_guard_size: int = 6, max_transform_size: int = 7) -> None:
        if method not in WAVE11_TYPED_METHODS:
            raise ValueError(f"Unknown Wave-11 method: {method}")
        self.method = method
        self.enumerator = TypedProgramEnumerator(
            max_guard_size=max_guard_size,
            max_transform_size=max_transform_size,
            public_budget=10,
        )
        self.library = self._make_library(method)

    @staticmethod
    def _make_library(method: str) -> TypedMacroLibrary:
        if method == "equal_typed_scratch":
            return TypedMacroLibrary(
                use_macro_evolution=False,
                use_pruning=False,
                use_cold_archive=False,
                use_memoization=False,
                use_schemas=False,
            )
        if method == "ordinary_persistent_memoization":
            return TypedMacroLibrary(
                use_macro_evolution=False,
                use_pruning=False,
                use_cold_archive=False,
                use_memoization=True,
                use_schemas=False,
            )
        if method == "nexus_typed_without_pruning":
            return TypedMacroLibrary(
                use_macro_evolution=True,
                use_pruning=False,
                use_cold_archive=False,
                use_memoization=False,
                use_schemas=True,
            )
        # nexus_typed_full
        return TypedMacroLibrary(
            use_macro_evolution=True,
            use_pruning=True,
            use_cold_archive=True,
            use_memoization=False,
            use_schemas=True,
        )

    def solve_unfamiliar_task(
        self,
        env: Any,
        public_budget: int = 10,
    ) -> Wave11TaskExecutionReport:
        """Interact with ``env`` under ``public_budget`` with ZERO label parameters."""
        if self.method == "equal_typed_scratch":
            self.library = self._make_library("equal_typed_scratch")

        manifest = typed_catalog_manifest()
        catalog_audit = {
            "sequence_opcodes_count": len(manifest["sequence_opcodes"]),
            "scalar_relational_opcodes_count": len(
                manifest["scalar_relational_opcodes"]
            ),
            "branch_opcodes_count": len(manifest["branch_opcodes"]),
            "token_constants_count": len(manifest["token_constants"]),
            "int_constants_count": len(manifest["int_constants"]),
            "max_guard_size": self.enumerator.max_guard_size,
            "max_transform_size": self.enumerator.max_transform_size,
        }

        probed = _probe_environment_label_blind(env, public_budget)
        status = str(probed["status"])
        admitted_field = probed["field"]
        pub_env = int(probed["public_env_probes"])
        pub_val = int(probed["public_validation_probes"])
        chan_inv = int(probed["channel_invariance_evals"])
        trace = list(probed["trace"])

        if status != "unique" or not admitted_field:
            total_work = pub_env + pub_val + chan_inv
            return Wave11TaskExecutionReport(
                method=self.method,
                status=status,
                admitted_field=None,
                chosen_slots=tuple(PUBLIC_SLOTS),
                public_observations=[],
                program_ast=make_abstain_program_dict(),
                public_consistent=False,
                ambiguous=(status == "ambiguous"),
                oog_abstained=(status == "abstain"),
                public_env_probes=pub_env,
                public_validation_probes=pub_val,
                channel_invariance_evals=chan_inv,
                schema_distill_cost=0,
                gate_evals=0,
                archive_lookup_evals=0,
                compression_evals=0,
                synthesis_evals=0,
                operator_compile_cost=0,
                codegen_plus_synthesis=0,
                total_work=total_work,
                schema_distilled=self.library.schemas_distilled,
                used_operators=(),
                invented_macros=(),
                sub_macro_reused=False,
                full_program_macro_reused=False,
                memoized_program_reused=False,
                cold_archive_reactivated=False,
                pruned_operators=tuple(self.library.pruned_names),
                active_library_size=len(self.library.operators),
                cold_archive_size=len(self.library.cold_archive),
                catalog_audit=catalog_audit,
                trace=trace,
            )

        initial_records = list(probed["initial"])
        validation_rec = probed["validation"]
        core_pairs: List[Tuple[Seq, Seq]] = [
            (as_seq(rec["payload"]), as_seq(rec[admitted_field]))
            for rec in initial_records
            if admitted_field in rec
        ]
        all_pairs = list(core_pairs)
        public_obs = [
            {
                "slot": str(rec.get("slot")),
                "input": list(as_seq(rec["payload"])),
                "observed_output": list(as_seq(rec[admitted_field])),
            }
            for rec in initial_records
            if admitted_field in rec
        ]
        if validation_rec is not None and admitted_field in validation_rec:
            val_pair = (
                as_seq(validation_rec["payload"]),
                as_seq(validation_rec[admitted_field]),
            )
            all_pairs.append(val_pair)
            public_obs.append(
                {
                    "slot": str(validation_rec.get("slot", "epsilon")),
                    "input": list(val_pair[0]),
                    "observed_output": list(val_pair[1]),
                }
            )

        syn = synthesize_wave11_typed(
            core_pairs, all_pairs, self.library, self.enumerator
        )
        public_ok = not syn.abstained and all(
            execute_wave11_program_ast(syn.program_ast_dict, inp) == out
            for inp, out in all_pairs
        )

        final_status = "abstain" if syn.abstained else "unique"
        final_field = None if syn.abstained else admitted_field
        codegen_plus_syn = syn.synthesis_evals + syn.archive_lookup_evals
        total_work = (
            pub_env
            + pub_val
            + chan_inv
            + syn.schema_distill_cost
            + syn.gate_evals
            + syn.archive_lookup_evals
            + syn.compression_evals
            + syn.synthesis_evals
            + syn.operator_compile_cost
        )

        return Wave11TaskExecutionReport(
            method=self.method,
            status=final_status,
            admitted_field=final_field,
            chosen_slots=tuple(PUBLIC_SLOTS),
            public_observations=public_obs,
            program_ast=syn.program_ast_dict,
            public_consistent=public_ok,
            ambiguous=False,
            oog_abstained=syn.abstained,
            public_env_probes=pub_env,
            public_validation_probes=pub_val,
            channel_invariance_evals=chan_inv,
            schema_distill_cost=syn.schema_distill_cost,
            gate_evals=syn.gate_evals,
            archive_lookup_evals=syn.archive_lookup_evals,
            compression_evals=syn.compression_evals,
            synthesis_evals=syn.synthesis_evals,
            operator_compile_cost=syn.operator_compile_cost,
            codegen_plus_synthesis=codegen_plus_syn,
            total_work=total_work,
            schema_distilled=syn.schema_distilled,
            used_operators=syn.used_operators,
            invented_macros=syn.invented_macros,
            sub_macro_reused=syn.sub_macro_reused,
            full_program_macro_reused=syn.full_program_macro_reused,
            memoized_program_reused=syn.memoized_program_reused,
            cold_archive_reactivated=syn.cold_archive_reactivated,
            pruned_operators=tuple(self.library.pruned_names),
            active_library_size=len(self.library.operators),
            cold_archive_size=len(self.library.cold_archive),
            catalog_audit=catalog_audit,
            trace=trace,
        )
