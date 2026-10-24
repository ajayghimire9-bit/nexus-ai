"""Wave-12 typed subtree invention and dual opcode accounting.

Static grammar constants are only INT (0, 1, 2) and the empty SEQ ().
Task tokens and extra integer thresholds are extracted from public
observations. The interpreter charges one primitive step per PrimOpNode,
including walks inside nested EvolvedMacroNode bodies. lambda_count == 0.
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

WAVE12_METHODS: Tuple[str, ...] = (
    "equal_typed_scratch",
    "ordinary_persistent_memoization",
    "nexus_whole_macro_only",
    "nexus_typed_without_pruning",
    "nexus_typed_full",
)

WORK_KEYS: Tuple[str, ...] = (
    "probe_work",
    "role_probe_work",
    "const_extraction_work",
    "gate_evals",
    "archive_lookup_evals",
    "synthesis_evals",
    "compression_evals",
    "compile_cost",
    "schema_distill_cost",
)

PRIMITIVE_KEYS: Tuple[str, ...] = (
    "synth_primitive_op_steps",
    "gate_primitive_op_steps",
    "archive_primitive_op_steps",
    "probe_primitive_op_steps",
    "compression_primitive_op_steps",
)


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
    "PREPEND_TOK",
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

STATIC_INT_CONSTANTS: Tuple[int, ...] = (0, 1, 2)
STATIC_SEQ_CONSTANTS: Tuple[Seq, ...] = ((),)
STATIC_TOK_CONSTANTS: Tuple[str, ...] = ()


@dataclass
class OpCounter:
    steps: int = 0


@dataclass(frozen=True)
class VarNode:
    out_type: TypeTag = TypeTag.SEQ

    def ast_nodes(self) -> int:
        return 1

    def node_count(self) -> int:
        return 1

    def canonical_key(self) -> str:
        return "x"

    def to_dict(self) -> Dict[str, Any]:
        return {"node_kind": "VarNode", "out_type": self.out_type.value}


@dataclass(frozen=True)
class ConstNode:
    value: Union[str, int, bool, Tuple[str, ...]]
    out_type: TypeTag

    def ast_nodes(self) -> int:
        return 1

    def node_count(self) -> int:
        return 1

    def canonical_key(self) -> str:
        return "const({0}:{1})".format(self.out_type.value, repr(self.value))

    def to_dict(self) -> Dict[str, Any]:
        stored: Any = list(self.value) if self.out_type == TypeTag.SEQ else self.value
        return {
            "node_kind": "ConstNode",
            "value": stored,
            "out_type": self.out_type.value,
        }


@dataclass(frozen=True)
class PrimOpNode:
    op_name: str
    args: Tuple["ExprAST", ...]
    out_type: TypeTag

    def __post_init__(self) -> None:
        if self.op_name not in ALLOWED_PRIM_OPCODES:
            raise ValueError("Disallowed primitive opcode: {0}".format(self.op_name))

    def ast_nodes(self) -> int:
        return 1 + sum(arg.ast_nodes() for arg in self.args)

    def node_count(self) -> int:
        return self.ast_nodes()

    def canonical_key(self) -> str:
        inner = ", ".join(arg.canonical_key() for arg in self.args)
        return "{0}({1})".format(self.op_name, inner)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_kind": "PrimOpNode",
            "op_name": self.op_name,
            "args": [arg.to_dict() for arg in self.args],
            "out_type": self.out_type.value,
        }


@dataclass(frozen=True)
class EvolvedMacroNode:
    macro_id: str
    body_ast: "ExprAST"
    args: Tuple["ExprAST", ...]
    out_type: TypeTag
    layer: int = 1

    def ast_nodes(self) -> int:
        return self.body_ast.ast_nodes()

    def node_count(self) -> int:
        return 1

    def canonical_key(self) -> str:
        return "macro:{0}[{1}]".format(self.macro_id, self.body_ast.canonical_key())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_kind": "EvolvedMacroNode",
            "macro_id": self.macro_id,
            "body_ast": self.body_ast.to_dict(),
            "args": [arg.to_dict() for arg in self.args],
            "out_type": self.out_type.value,
            "layer": int(self.layer),
        }


ExprAST = Union[VarNode, ConstNode, PrimOpNode, EvolvedMacroNode]


@dataclass(frozen=True)
class PiecewiseBranch:
    guard: ExprAST
    transform: ExprAST

    def to_dict(self) -> Dict[str, Any]:
        return {"guard": self.guard.to_dict(), "transform": self.transform.to_dict()}


@dataclass(frozen=True)
class PiecewiseProgramAST:
    branches: Tuple[PiecewiseBranch, ...]
    default: ExprAST

    def ast_nodes(self) -> int:
        total = self.default.ast_nodes()
        for branch in self.branches:
            total += branch.guard.ast_nodes() + branch.transform.ast_nodes()
        return total

    def node_count(self) -> int:
        return self.ast_nodes()

    def canonical_key(self) -> str:
        parts = [
            "{0}->{1}".format(branch.guard.canonical_key(), branch.transform.canonical_key())
            for branch in self.branches
        ]
        return "piecewise[{0}|else {1}]".format(
            ";".join(parts), self.default.canonical_key()
        )

    def to_dict(self) -> Dict[str, Any]:
        kind = "abstain" if not self.branches else "piecewise"
        return {
            "kind": kind,
            "domain_kind": "sequence",
            "branches": [branch.to_dict() for branch in self.branches],
            "default": self.default.to_dict(),
            "canonical_key": self.canonical_key(),
            "ast_nodes": self.ast_nodes(),
        }


def expr_ast_from_dict(data: Mapping[str, Any]) -> ExprAST:
    node_kind = str(data.get("node_kind", "VarNode"))
    out_type = TypeTag(str(data.get("out_type", "SEQ")))
    if node_kind == "VarNode":
        return VarNode(out_type=out_type)
    if node_kind == "ConstNode":
        raw = data["value"]
        if out_type == TypeTag.INT:
            value: Union[str, int, bool, Tuple[str, ...]] = int(raw)
        elif out_type == TypeTag.BOOL:
            value = bool(raw)
        elif out_type == TypeTag.SEQ:
            value = tuple(str(part) for part in (raw or ()))
        else:
            value = str(raw)
        return ConstNode(value=value, out_type=out_type)
    if node_kind == "PrimOpNode":
        return PrimOpNode(
            op_name=str(data["op_name"]),
            args=tuple(expr_ast_from_dict(arg) for arg in data.get("args", ())),
            out_type=out_type,
        )
    if node_kind == "EvolvedMacroNode":
        return EvolvedMacroNode(
            macro_id=str(data["macro_id"]),
            body_ast=expr_ast_from_dict(data["body_ast"]),
            args=tuple(expr_ast_from_dict(arg) for arg in data.get("args", ())),
            out_type=out_type,
            layer=int(data.get("layer") or 1),
        )
    raise ValueError("Unknown ExprAST node_kind: {0}".format(node_kind))


def piecewise_from_dict(data: Mapping[str, Any]) -> PiecewiseProgramAST:
    if str(data.get("kind", "abstain")) == "abstain" and not data.get("branches"):
        return PiecewiseProgramAST((), VarNode())
    branches = []
    for row in data.get("branches") or ():
        branches.append(
            PiecewiseBranch(
                expr_ast_from_dict(row["guard"]),
                expr_ast_from_dict(row["transform"]),
            )
        )
    default_raw = data.get("default") or VarNode().to_dict()
    return PiecewiseProgramAST(tuple(branches), expr_ast_from_dict(default_raw))


def eval_expr_ast(node: ExprAST, x: Seq, op_counter: Optional[OpCounter] = None) -> Any:
    seq_x = as_seq(x)
    if isinstance(node, VarNode):
        return seq_x
    if isinstance(node, ConstNode):
        if node.out_type == TypeTag.INT:
            return int(node.value)
        if node.out_type == TypeTag.BOOL:
            return bool(node.value)
        if node.out_type == TypeTag.SEQ:
            return as_seq(node.value)
        return str(node.value)
    if isinstance(node, EvolvedMacroNode):
        if len(node.args) == 1:
            bound = as_seq(eval_expr_ast(node.args[0], seq_x, op_counter))
            return eval_expr_ast(node.body_ast, bound, op_counter)
        return eval_expr_ast(node.body_ast, seq_x, op_counter)
    if isinstance(node, PrimOpNode):
        if op_counter is not None:
            op_counter.steps += 1
        op_name = node.op_name
        if op_name == "IF_THEN_ELSE":
            cond = bool(eval_expr_ast(node.args[0], seq_x, op_counter))
            chosen = node.args[1] if cond else node.args[2]
            return as_seq(eval_expr_ast(chosen, seq_x, op_counter))
        if op_name == "HEAD":
            seq_val = as_seq(eval_expr_ast(node.args[0], seq_x, op_counter))
            return seq_val[0] if seq_val else ""
        if op_name == "TAIL":
            return as_seq(eval_expr_ast(node.args[0], seq_x, op_counter))[1:]
        if op_name == "INIT":
            return as_seq(eval_expr_ast(node.args[0], seq_x, op_counter))[:-1]
        if op_name == "LAST":
            seq_val = as_seq(eval_expr_ast(node.args[0], seq_x, op_counter))
            return seq_val[-1] if seq_val else ""
        if op_name == "REVERSE":
            return as_seq(eval_expr_ast(node.args[0], seq_x, op_counter))[::-1]
        if op_name == "CONCAT":
            left = as_seq(eval_expr_ast(node.args[0], seq_x, op_counter))
            right = as_seq(eval_expr_ast(node.args[1], seq_x, op_counter))
            return left + right
        if op_name == "APPEND_TOK":
            left = as_seq(eval_expr_ast(node.args[0], seq_x, op_counter))
            token = str(eval_expr_ast(node.args[1], seq_x, op_counter))
            return left + (token,) if token != "" else left
        if op_name == "PREPEND_TOK":
            token = str(eval_expr_ast(node.args[0], seq_x, op_counter))
            right = as_seq(eval_expr_ast(node.args[1], seq_x, op_counter))
            return ((token,) + right) if token != "" else right
        if op_name == "LEN":
            return len(as_seq(eval_expr_ast(node.args[0], seq_x, op_counter)))
        if op_name == "MOD2":
            return int(eval_expr_ast(node.args[0], seq_x, op_counter)) % 2
        if op_name == "TOK_EQ":
            left_t = str(eval_expr_ast(node.args[0], seq_x, op_counter))
            right_t = str(eval_expr_ast(node.args[1], seq_x, op_counter))
            return bool(left_t != "" and right_t != "" and left_t == right_t)
        if op_name == "SEQ_EQ":
            return as_seq(eval_expr_ast(node.args[0], seq_x, op_counter)) == as_seq(
                eval_expr_ast(node.args[1], seq_x, op_counter)
            )
        if op_name == "INT_EQ":
            return int(eval_expr_ast(node.args[0], seq_x, op_counter)) == int(
                eval_expr_ast(node.args[1], seq_x, op_counter)
            )
        if op_name == "INT_GE":
            return int(eval_expr_ast(node.args[0], seq_x, op_counter)) >= int(
                eval_expr_ast(node.args[1], seq_x, op_counter)
            )
        raise ValueError("Unhandled primitive opcode: {0}".format(op_name))
    raise TypeError("Unsupported ExprAST node: {0}".format(type(node)))


def eval_piecewise(
    program: PiecewiseProgramAST, x: Seq, op_counter: Optional[OpCounter] = None
) -> Seq:
    for branch in program.branches:
        if bool(eval_expr_ast(branch.guard, x, op_counter)):
            return as_seq(eval_expr_ast(branch.transform, x, op_counter))
    return as_seq(eval_expr_ast(program.default, x, op_counter))


def execute_wave12_program_ast(
    program_ast: Mapping[str, Any],
    value: Any,
    op_counter: Optional[OpCounter] = None,
) -> Seq:
    seq_val = as_seq(value)
    if str(program_ast.get("kind", "abstain")) == "abstain":
        return seq_val
    if program_ast.get("branches") is not None or program_ast.get("default") is not None:
        return eval_piecewise(piecewise_from_dict(program_ast), seq_val, op_counter)
    root = program_ast.get("root_ast")
    if isinstance(root, Mapping):
        return as_seq(eval_expr_ast(expr_ast_from_dict(root), seq_val, op_counter))
    return seq_val


def make_abstain_program_dict() -> Dict[str, Any]:
    return PiecewiseProgramAST((), VarNode()).to_dict()


def typed_catalog_manifest() -> Dict[str, Any]:
    return {
        "type_tags": [tag.value for tag in TypeTag],
        "sequence_opcodes": list(PRIM_SEQUENCE_OPS),
        "scalar_relational_opcodes": list(PRIM_SCALAR_REL_OPS),
        "branch_opcodes": list(PRIM_BRANCH_OPS),
        "static_int_constants": list(STATIC_INT_CONSTANTS),
        "static_seq_constants": [list(item) for item in STATIC_SEQ_CONSTANTS],
        "static_tok_constants": list(STATIC_TOK_CONSTANTS),
    }


@dataclass
class ExtractedConstants:
    tokens: Tuple[str, ...]
    ints: Tuple[int, ...]
    work: int


def extract_task_constants(public_observations: Sequence[Mapping[str, Any]]) -> ExtractedConstants:
    pairs: List[Tuple[Seq, Seq]] = []
    for row in public_observations:
        src = as_seq(row.get("input") or row.get("x") or ())
        dst = as_seq(row.get("observed_output") or row.get("output") or row.get("y") or ())
        pairs.append((src, dst))
    tokens: List[str] = []
    for src, dst in pairs:
        src_set = set(src)
        for token in dst:
            if token not in src_set and token not in tokens:
                tokens.append(token)
    residual = [src for src, dst in pairs if src != dst]
    if residual:
        heads = {src[0] for src in residual if src}
        lasts = {src[-1] for src in residual if src}
        if len(heads) == 1:
            token = next(iter(heads))
            if token not in tokens:
                tokens.append(token)
        if len(lasts) == 1:
            token = next(iter(lasts))
            if token not in tokens:
                tokens.append(token)
    by_len: Dict[int, List[bool]] = {}
    for src, dst in pairs:
        by_len.setdefault(len(src), []).append(src != dst)
    residual_lens = sorted(length for length, flags in by_len.items() if any(flags))
    identity_lens = sorted(length for length, flags in by_len.items() if flags and not any(flags))
    thresholds: List[int] = []
    for length in residual_lens + identity_lens:
        if length not in STATIC_INT_CONSTANTS and length not in thresholds:
            neighbor_id = (length - 1) in identity_lens or (length + 1) in identity_lens
            neighbor_res = (length - 1) in residual_lens or (length + 1) in residual_lens
            if neighbor_id or neighbor_res or length not in STATIC_INT_CONSTANTS:
                thresholds.append(length)
        if len(thresholds) >= 2:
            break
    return ExtractedConstants(tuple(tokens), tuple(thresholds[:2]), len(list(public_observations)))


def iter_internal_subtrees(node: Any) -> List[ExprAST]:
    found: List[ExprAST] = []

    def walk(item: Any, is_root: bool) -> None:
        if isinstance(item, PiecewiseProgramAST):
            for branch in item.branches:
                walk(branch.guard, False)
                walk(branch.transform, False)
            walk(item.default, False)
            return
        if not isinstance(item, (VarNode, ConstNode, PrimOpNode, EvolvedMacroNode)):
            return
        size = item.ast_nodes()
        if (not is_root) and 3 <= size <= 6 and isinstance(item, (PrimOpNode, EvolvedMacroNode)):
            found.append(item)
        if isinstance(item, PrimOpNode):
            for arg in item.args:
                walk(arg, False)
        elif isinstance(item, EvolvedMacroNode):
            walk(item.body_ast, False)
            for arg in item.args:
                walk(arg, False)

    walk(node, True)
    return found


def _contains_macro(node: ExprAST) -> bool:
    if isinstance(node, EvolvedMacroNode):
        return True
    if isinstance(node, PrimOpNode):
        return any(_contains_macro(arg) for arg in node.args)
    return False


def mdl_gain(occurrences: int, node_count: int) -> int:
    return (occurrences - 1) * (node_count - 1) - node_count


@dataclass
class EvolvedTypedOperator:
    name: str
    kind: str
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
    program: PiecewiseProgramAST
    uses: int = 1
    created_step: int = 0
    last_used_step: int = 0


def _alphabet_closed(
    pairs: Sequence[Tuple[Seq, Seq]], extra_tokens: Sequence[str]
) -> bool:
    allowed = set(extra_tokens)
    for src, dst in pairs:
        incoming = set(src) | allowed
        if not set(dst) <= incoming:
            return False
    return True


@dataclass
class TypedMacroLibrary:
    use_macro_evolution: bool = True
    use_internal_subtree: bool = True
    use_pruning: bool = True
    use_cold_archive: bool = True
    use_memoization: bool = False
    use_schemas: bool = True
    step: int = 0
    schemas_distilled: bool = False
    operators: Dict[str, EvolvedTypedOperator] = field(default_factory=dict)
    cold_archive: Dict[str, EvolvedTypedOperator] = field(default_factory=dict)
    mdl_pinned_names: set[str] = field(default_factory=set)
    solved_program_history: List[PiecewiseProgramAST] = field(default_factory=list)
    memoized_programs: Dict[str, MemoizedTypedProgramEntry] = field(default_factory=dict)
    pruned_names: List[str] = field(default_factory=list)
    reactivated_names: List[str] = field(default_factory=list)
    macro_counter: int = 0

    def ensure_schemas(self) -> int:
        if not self.use_schemas or self.schemas_distilled:
            return 0
        _, cost = distill_source_schemas_with_cost()
        self.schemas_distilled = True
        return cost

    def empirical_roi_gate_policy(
        self,
        pairs: Sequence[Tuple[Seq, Seq]],
        extra_tokens: Sequence[str],
        gate_counter: OpCounter,
    ) -> Tuple[Dict[str, bool], int]:
        _ = gate_counter
        if not self.operators:
            return {}, 0
        names = {op.prerequisite_name for op in self.operators.values()}
        results: Dict[str, bool] = {}
        gate_evals = 0
        for name in names:
            gate_evals += 1
            if name == "alphabet_closed":
                results[name] = _alphabet_closed(pairs, extra_tokens)
            else:
                results[name] = True
        return results, gate_evals

    def active_view(
        self,
        pairs: Sequence[Tuple[Seq, Seq]],
        extra_tokens: Sequence[str],
        gate_counter: OpCounter,
    ) -> Tuple[Dict[str, List[EvolvedTypedOperator]], int]:
        empty: Dict[str, List[EvolvedTypedOperator]] = {
            "bool_macros": [],
            "seq_macros": [],
            "program_macros": [],
        }
        if not self.use_macro_evolution or not self.operators:
            return empty, 0
        invariant, gate_evals = self.empirical_roi_gate_policy(pairs, extra_tokens, gate_counter)
        view = {"bool_macros": [], "seq_macros": [], "program_macros": []}
        for op in self.operators.values():
            if not invariant.get(op.prerequisite_name, True):
                continue
            view[op.kind + "s" if op.kind.endswith("macro") else op.kind].append(op) if False else None
            if op.kind == "bool_macro":
                view["bool_macros"].append(op)
            elif op.kind == "seq_macro":
                view["seq_macros"].append(op)
            elif op.kind == "program_macro":
                view["program_macros"].append(op)
        return view, gate_evals

    def promote_ast_subtree(
        self, subtree_ast: ExprAST, kind: str, layer: int = 1
    ) -> Tuple[Optional[EvolvedTypedOperator], int]:
        if not self.use_macro_evolution:
            return None, 0
        body = subtree_ast.body_ast if isinstance(subtree_ast, EvolvedMacroNode) else subtree_ast
        if body.ast_nodes() < 2:
            return None, 0
        canon = body.canonical_key()
        for existing in self.operators.values():
            if existing.macro_node.body_ast.canonical_key() == canon:
                existing.uses += 1
                existing.last_used_step = self.step
                if existing.uses >= 2:
                    self.mdl_pinned_names.add(existing.name)
                return existing, 0
        for archive_name, archived in list(self.cold_archive.items()):
            if archived.macro_node.body_ast.canonical_key() == canon:
                restored = self.cold_archive.pop(archive_name)
                restored.uses += 1
                restored.last_used_step = self.step
                self.operators[archive_name] = restored
                self.mdl_pinned_names.add(archive_name)
                return restored, 0
        self.macro_counter += 1
        out_type = TypeTag.BOOL if kind == "bool_macro" else TypeTag.SEQ
        macro_id = "{0}_{1}".format(kind, self.macro_counter)
        macro_node = EvolvedMacroNode(
            macro_id=macro_id,
            body_ast=body,
            args=(VarNode(),),
            out_type=out_type,
            layer=layer,
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
        if kind == "program_macro" or new_op.uses >= 2:
            self.mdl_pinned_names.add(macro_id)
        return new_op, len(UNIVERSAL_PROBES)

    def record_operator_use(self, name: str) -> None:
        if name in self.operators:
            self.operators[name].uses += 1
            self.operators[name].last_used_step = self.step
            if self.operators[name].uses >= 2:
                self.mdl_pinned_names.add(name)

    def register_memoized_program(self, program: PiecewiseProgramAST) -> None:
        if not self.use_memoization:
            return
        key = program.canonical_key()
        if key not in self.memoized_programs:
            self.memoized_programs[key] = MemoizedTypedProgramEntry(
                signature_name=key,
                program=program,
                uses=1,
                created_step=self.step,
                last_used_step=self.step,
            )
        else:
            self.memoized_programs[key].uses += 1
            self.memoized_programs[key].last_used_step = self.step

    def compress_solved_programs_mdl(
        self,
        latest: PiecewiseProgramAST,
        structure_discovered: bool,
        compression_counter: OpCounter,
    ) -> Tuple[int, Tuple[str, ...]]:
        if not self.use_macro_evolution or not structure_discovered:
            return 0, ()
        self.solved_program_history.append(latest)
        invented: List[str] = []
        evals = 0
        if latest.ast_nodes() < 4 and not self.use_internal_subtree:
            return 0, ()
        counts: Dict[str, Dict[str, Any]] = {}
        for program in self.solved_program_history:
            roots: List[ExprAST] = []
            internals: List[ExprAST] = []
            for branch in program.branches:
                roots.extend([branch.guard, branch.transform])
                if self.use_internal_subtree:
                    internals.extend(iter_internal_subtrees(branch.guard))
                    internals.extend(iter_internal_subtrees(branch.transform))
            pool = roots + internals if self.use_internal_subtree else roots
            seen_here = set()
            for subtree in pool:
                evals += 1
                compression_counter.steps += 0
                size = subtree.ast_nodes()
                if size < 2:
                    continue
                if self.use_internal_subtree and subtree in internals and not (3 <= size <= 6):
                    continue
                key = subtree.canonical_key()
                row = counts.setdefault(
                    key, {"count": 0, "tasks": 0, "node": subtree, "size": size}
                )
                row["count"] += 1
                if key not in seen_here:
                    row["tasks"] += 1
                    seen_here.add(key)
        if self.use_internal_subtree or True:
            for row in counts.values():
                subtree = row["node"]
                size = int(row["size"])
                occ = int(row["count"])
                tasks = int(row["tasks"])
                gain = mdl_gain(occ, size)
                recurring = occ >= 2 and (gain > 0 or tasks >= 2)
                if not recurring:
                    continue
                if not self.use_internal_subtree:
                    if subtree not in [
                        branch.guard for program in self.solved_program_history for branch in program.branches
                    ] and subtree not in [
                        branch.transform
                        for program in self.solved_program_history
                        for branch in program.branches
                    ]:
                        continue
                kind = "bool_macro" if getattr(subtree, "out_type", TypeTag.SEQ) == TypeTag.BOOL else "seq_macro"
                layer = 2 if _contains_macro(subtree) else 1
                promoted, _ = self.promote_ast_subtree(subtree, kind, layer=layer)
                if promoted is not None and promoted.uses == 1:
                    invented.append(promoted.name)
                    self.mdl_pinned_names.add(promoted.name)
        return evals, tuple(invented)

    def usage_age_prune(self, min_age: int = 2, min_uses: int = 2) -> List[str]:
        if not self.use_pruning:
            return []
        demoted: List[str] = []
        for name, op in list(self.operators.items()):
            if name in self.mdl_pinned_names or op.kind == "program_macro":
                continue
            if self.step - op.created_step >= min_age and op.uses < min_uses:
                demoted.append(name)
                self.pruned_names.append(name)
                if self.use_cold_archive:
                    self.cold_archive[name] = op
                del self.operators[name]
        return demoted


class TypedProgramEnumerator:
    def __init__(
        self,
        max_guard_size: int = 6,
        max_transform_size: int = 7,
        public_budget: int = 10,
    ) -> None:
        self.max_guard_size = int(max_guard_size)
        self.max_transform_size = int(max_transform_size)
        self.public_budget = int(public_budget)

    def token_nodes(self, extracted: ExtractedConstants) -> List[ExprAST]:
        return [ConstNode(token, TypeTag.TOK) for token in extracted.tokens]

    def int_nodes(self, extracted: ExtractedConstants) -> List[ExprAST]:
        values = list(STATIC_INT_CONSTANTS)
        for extra in extracted.ints:
            if extra not in values:
                values.append(extra)
        return [ConstNode(value, TypeTag.INT) for value in values]

    def enumerate_tier0_base_guards(self, extracted: ExtractedConstants) -> List[ExprAST]:
        x_node = VarNode()
        len_x = PrimOpNode("LEN", (x_node,), TypeTag.INT)
        mod2 = PrimOpNode("MOD2", (len_x,), TypeTag.INT)
        guards = [
            PrimOpNode("INT_EQ", (mod2, ConstNode(0, TypeTag.INT)), TypeTag.BOOL),
            PrimOpNode("INT_EQ", (mod2, ConstNode(1, TypeTag.INT)), TypeTag.BOOL),
            PrimOpNode("INT_EQ", (len_x, ConstNode(0, TypeTag.INT)), TypeTag.BOOL),
            PrimOpNode("INT_EQ", (len_x, ConstNode(1, TypeTag.INT)), TypeTag.BOOL),
            PrimOpNode("INT_EQ", (len_x, ConstNode(2, TypeTag.INT)), TypeTag.BOOL),
        ]
        for extra in extracted.ints:
            guards.append(
                PrimOpNode("INT_EQ", (len_x, ConstNode(extra, TypeTag.INT)), TypeTag.BOOL)
            )
            guards.append(
                PrimOpNode("INT_GE", (len_x, ConstNode(extra, TypeTag.INT)), TypeTag.BOOL)
            )
        return guards

    def enumerate_tier0_base_transforms(self, extracted: ExtractedConstants) -> List[ExprAST]:
        x_node = VarNode()
        transforms: List[ExprAST] = [
            PrimOpNode("REVERSE", (x_node,), TypeTag.SEQ),
            PrimOpNode("CONCAT", (x_node, x_node), TypeTag.SEQ),
            PrimOpNode("TAIL", (x_node,), TypeTag.SEQ),
            PrimOpNode("INIT", (x_node,), TypeTag.SEQ),
        ]
        for token in extracted.tokens:
            tok = ConstNode(token, TypeTag.TOK)
            transforms.append(PrimOpNode("APPEND_TOK", (x_node, tok), TypeTag.SEQ))
            transforms.append(PrimOpNode("PREPEND_TOK", (tok, x_node), TypeTag.SEQ))
        return transforms


def _eval_pairs(
    program: PiecewiseProgramAST,
    pairs: Sequence[Tuple[Seq, Seq]],
    counter: OpCounter,
) -> Tuple[bool, int]:
    evals = 0
    for src, dst in pairs:
        evals += 1
        if eval_piecewise(program, src, counter) != dst:
            return False, evals
    return True, evals


def _eval_expr_pairs(
    node: ExprAST, pairs: Sequence[Tuple[Seq, Seq]], counter: OpCounter
) -> Tuple[bool, int]:
    evals = 0
    for src, dst in pairs:
        evals += 1
        if as_seq(eval_expr_ast(node, src, counter)) != dst:
            return False, evals
    return True, evals


def _guard_mask(
    guard: ExprAST, pairs: Sequence[Tuple[Seq, Seq]], counter: OpCounter
) -> Tuple[Tuple[bool, ...], int]:
    flags: List[bool] = []
    evals = 0
    for src, _dst in pairs:
        evals += 1
        flags.append(bool(eval_expr_ast(guard, src, counter)))
    return tuple(flags), evals


def _transform_hits(
    transform: ExprAST, pairs: Sequence[Tuple[Seq, Seq]], counter: OpCounter
) -> Tuple[Tuple[bool, ...], int]:
    flags: List[bool] = []
    evals = 0
    for src, dst in pairs:
        evals += 1
        flags.append(as_seq(eval_expr_ast(transform, src, counter)) == dst)
    return tuple(flags), evals


@dataclass
class Wave12SynthesisResult:
    program: PiecewiseProgramAST
    program_ast_dict: Dict[str, Any]
    synthesis_evals: int
    archive_lookup_evals: int
    compression_evals: int
    gate_evals: int
    schema_distill_cost: int
    compile_cost: int
    role_probe_work: int
    synth_primitive_op_steps: int
    gate_primitive_op_steps: int
    archive_primitive_op_steps: int
    compression_primitive_op_steps: int
    schema_distilled: bool
    used_operators: Tuple[str, ...]
    invented_macros: Tuple[str, ...]
    sub_macro_reused: bool
    full_program_macro_reused: bool
    memoized_program_reused: bool
    cold_archive_reactivated: bool
    abstained: bool
    pruned_this_step: Tuple[str, ...]
    subtree_macro_invented: bool


def _finish(
    program: PiecewiseProgramAST,
    lib: TypedMacroLibrary,
    synth_evals: int,
    archive_evals: int,
    compression_evals: int,
    gate_evals: int,
    schema_cost: int,
    compile_cost: int,
    role_probe: int,
    synth_c: OpCounter,
    gate_c: OpCounter,
    arch_c: OpCounter,
    comp_c: OpCounter,
    used: Tuple[str, ...],
    invented: Tuple[str, ...],
    flags: Mapping[str, bool],
) -> Wave12SynthesisResult:
    pruned = tuple(lib.usage_age_prune())
    return Wave12SynthesisResult(
        program=program,
        program_ast_dict=program.to_dict(),
        synthesis_evals=synth_evals,
        archive_lookup_evals=archive_evals,
        compression_evals=compression_evals,
        gate_evals=gate_evals,
        schema_distill_cost=schema_cost,
        compile_cost=compile_cost,
        role_probe_work=role_probe,
        synth_primitive_op_steps=synth_c.steps,
        gate_primitive_op_steps=gate_c.steps,
        archive_primitive_op_steps=arch_c.steps,
        compression_primitive_op_steps=comp_c.steps,
        schema_distilled=schema_cost > 0 or lib.schemas_distilled,
        used_operators=used,
        invented_macros=invented,
        sub_macro_reused=bool(flags.get("sub_macro_reused")),
        full_program_macro_reused=bool(flags.get("full_program_macro_reused")),
        memoized_program_reused=bool(flags.get("memoized_program_reused")),
        cold_archive_reactivated=bool(flags.get("cold_archive_reactivated")),
        abstained=bool(flags.get("abstained")),
        pruned_this_step=pruned,
        subtree_macro_invented=bool(flags.get("subtree_macro_invented")),
    )


class TypedProgramEnumeratorSearch:
    """Size-bounded SEQ/BOOL expansion using only static + extracted constants."""

    def __init__(self, enumerator: TypedProgramEnumerator) -> None:
        self.enumerator = enumerator

    def expand(
        self,
        extracted: ExtractedConstants,
        all_inputs: Sequence[Seq],
        seq_macros: Sequence[EvolvedTypedOperator],
        synth_c: OpCounter,
    ) -> Tuple[List[ExprAST], List[ExprAST], int]:
        evals = 0
        x_node = VarNode()
        tok_nodes = [
            ConstNode(token, TypeTag.TOK) for token in extracted.tokens
        ] + [
            PrimOpNode("HEAD", (x_node,), TypeTag.TOK),
            PrimOpNode("LAST", (x_node,), TypeTag.TOK),
        ]
        seq_by_size: Dict[int, List[ExprAST]] = {
            1: [x_node, ConstNode((), TypeTag.SEQ)],
        }
        seen: Dict[Tuple[Seq, ...], ExprAST] = {}

        def register(size: int, cands: Sequence[ExprAST]) -> int:
            local = 0
            bucket: List[ExprAST] = list(seq_by_size.get(size, []))
            for cand in cands:
                sig_list: List[Seq] = []
                for inp in all_inputs:
                    local += 1
                    sig_list.append(as_seq(eval_expr_ast(cand, inp, synth_c)))
                sig = tuple(sig_list)
                if sig not in seen:
                    seen[sig] = cand
                    bucket.append(cand)
            seq_by_size[size] = bucket
            return local

        evals += register(
            2,
            [
                PrimOpNode("TAIL", (x_node,), TypeTag.SEQ),
                PrimOpNode("INIT", (x_node,), TypeTag.SEQ),
                PrimOpNode("REVERSE", (x_node,), TypeTag.SEQ),
            ],
        )
        for macro in seq_macros:
            evals += register(2, [macro.macro_node])
        cands3: List[ExprAST] = [PrimOpNode("CONCAT", (x_node, x_node), TypeTag.SEQ)]
        for tok in [ConstNode(token, TypeTag.TOK) for token in extracted.tokens]:
            cands3.append(PrimOpNode("APPEND_TOK", (x_node, tok), TypeTag.SEQ))
            cands3.append(PrimOpNode("PREPEND_TOK", (tok, x_node), TypeTag.SEQ))
        evals += register(3, cands3)
        max_level = self.enumerator.max_transform_size
        for level in range(4, max_level + 1):
            cands: List[ExprAST] = []
            for seq_size in range(1, level):
                tok_size_guess = 1
                if seq_size + tok_size_guess + 1 == level:
                    for seq_node in seq_by_size.get(seq_size, ()):
                        for tok in [ConstNode(token, TypeTag.TOK) for token in extracted.tokens]:
                            cands.append(PrimOpNode("APPEND_TOK", (seq_node, tok), TypeTag.SEQ))
                            cands.append(PrimOpNode("PREPEND_TOK", (tok, seq_node), TypeTag.SEQ))
                        for tok_op in tok_nodes[len(extracted.tokens):]:
                            if tok_op.ast_nodes() + seq_size + 1 == level:
                                cands.append(
                                    PrimOpNode("APPEND_TOK", (seq_node, tok_op), TypeTag.SEQ)
                                )
                                cands.append(
                                    PrimOpNode("PREPEND_TOK", (tok_op, seq_node), TypeTag.SEQ)
                                )
            if level == 4:
                for seq2 in seq_by_size.get(2, ()):
                    cands.append(PrimOpNode("CONCAT", (seq2, x_node), TypeTag.SEQ))
                    cands.append(PrimOpNode("CONCAT", (x_node, seq2), TypeTag.SEQ))
            evals += register(level, cands)
        all_seq: List[ExprAST] = []
        for size in sorted(seq_by_size):
            all_seq.extend(seq_by_size[size])
        bools = [
            PrimOpNode("SEQ_EQ", (x_node, PrimOpNode("REVERSE", (x_node,), TypeTag.SEQ)), TypeTag.BOOL),
            PrimOpNode(
                "TOK_EQ",
                (
                    PrimOpNode("HEAD", (x_node,), TypeTag.TOK),
                    PrimOpNode("LAST", (x_node,), TypeTag.TOK),
                ),
                TypeTag.BOOL,
            ),
        ]
        for inp in all_inputs:
            evals += 1
            eval_expr_ast(bools[0], inp, synth_c)
            evals += 1
            eval_expr_ast(bools[1], inp, synth_c)
        return all_seq, bools, evals


def synthesize_wave12(
    core_pairs: Sequence[Tuple[Seq, Seq]],
    all_pairs: Sequence[Tuple[Seq, Seq]],
    lib: TypedMacroLibrary,
    enumerator: TypedProgramEnumerator,
    extracted: ExtractedConstants,
) -> Wave12SynthesisResult:
    lib.step += 1
    schema_cost = lib.ensure_schemas()
    role_probe = 0
    if schema_cost or lib.schemas_distilled:
        role_probe = len(UNIVERSAL_PROBES) * 3 if lib.use_schemas else 0
    synth_c = OpCounter()
    gate_c = OpCounter()
    arch_c = OpCounter()
    comp_c = OpCounter()
    synth_evals = 0
    archive_evals = 0
    compile_cost = 0
    x_node = VarNode()
    default = x_node

    if lib.use_memoization and lib.memoized_programs:
        for entry in lib.memoized_programs.values():
            ok, ev = _eval_pairs(entry.program, all_pairs, synth_c)
            synth_evals += ev
            if ok:
                entry.uses += 1
                entry.last_used_step = lib.step
                return _finish(
                    entry.program, lib, synth_evals, 0, 0, 0, schema_cost, 0, role_probe,
                    synth_c, gate_c, arch_c, comp_c, (entry.signature_name,), (),
                    {"memoized_program_reused": True},
                )

    tier0_g = enumerator.enumerate_tier0_base_guards(extracted)
    tier0_t = enumerator.enumerate_tier0_base_transforms(extracted)

    def try_single(guards: Sequence[ExprAST], transforms: Sequence[ExprAST]) -> Optional[PiecewiseProgramAST]:
        nonlocal synth_evals
        for guard in guards:
            mask, ev = _guard_mask(guard, core_pairs, synth_c)
            synth_evals += ev
            residual = tuple(src != dst for src, dst in core_pairs)
            if mask != residual:
                continue
            for transform in transforms:
                program = PiecewiseProgramAST((PiecewiseBranch(guard, transform),), default)
                ok, ev2 = _eval_pairs(program, all_pairs, synth_c)
                synth_evals += ev2
                if ok:
                    return program
        return None

    hit = try_single(tier0_g, tier0_t)
    if hit is not None:
        lib.register_memoized_program(hit)
        return _finish(
            hit, lib, synth_evals, 0, 0, 0, schema_cost, 0, role_probe,
            synth_c, gate_c, arch_c, comp_c, (), (), {},
        )

    view, gate_evals = lib.active_view(all_pairs, extracted.tokens, gate_c)
    for prog_op in view["program_macros"]:
        wrapped = PiecewiseProgramAST(
            (PiecewiseBranch(ConstNode(True, TypeTag.BOOL), prog_op.macro_node),),
            default,
        )
        # program macros store whole piecewise bodies as SEQ macros over IF; try body directly
        ok, ev = _eval_expr_pairs(prog_op.macro_node, all_pairs, synth_c)
        synth_evals += ev
        if ok:
            rebuilt = PiecewiseProgramAST(
                (PiecewiseBranch(ConstNode(True, TypeTag.BOOL), prog_op.macro_node),),
                default,
            )
            lib.record_operator_use(prog_op.name)
            return _finish(
                rebuilt, lib, synth_evals, 0, 0, gate_evals, schema_cost, 0, role_probe,
                synth_c, gate_c, arch_c, comp_c, (prog_op.name,), (),
                {"sub_macro_reused": True, "full_program_macro_reused": True},
            )
        _ = wrapped

    active_bools = [op.macro_node for op in view["bool_macros"]]
    active_seqs = [op.macro_node for op in view["seq_macros"]]
    named_seqs = [(op.macro_node, op.name) for op in view["seq_macros"]]
    extended_t: List[Tuple[ExprAST, Optional[str]]] = [(node, None) for node in tier0_t]
    for seq_node, name in named_seqs:
        extended_t.append((seq_node, name))
        for token in extracted.tokens:
            tok = ConstNode(token, TypeTag.TOK)
            extended_t.append((PrimOpNode("APPEND_TOK", (seq_node, tok), TypeTag.SEQ), name))
            extended_t.append((PrimOpNode("PREPEND_TOK", (tok, seq_node), TypeTag.SEQ), name))

    hit = try_single(list(active_bools) + tier0_g, [item[0] for item in extended_t])
    if hit is not None:
        used: List[str] = []
        invented: List[str] = []
        for branch in hit.branches:
            for op in list(lib.operators.values()):
                if op.macro_node.canonical_key() in {
                    branch.guard.canonical_key(),
                    branch.transform.canonical_key(),
                } or op.macro_node.body_ast.canonical_key() in {
                    branch.guard.canonical_key() if not isinstance(branch.guard, EvolvedMacroNode) else branch.guard.body_ast.canonical_key(),
                    branch.transform.canonical_key() if not isinstance(branch.transform, EvolvedMacroNode) else branch.transform.body_ast.canonical_key(),
                }:
                    lib.record_operator_use(op.name)
                    used.append(op.name)
        for branch in hit.branches:
            if branch.transform.ast_nodes() >= 2:
                kind = "seq_macro"
                layer = 2 if _contains_macro(branch.transform) else 1
                promoted, cost = lib.promote_ast_subtree(branch.transform, kind, layer)
                compile_cost += cost
                if promoted is not None:
                    used.append(promoted.name)
                    if promoted.uses == 1:
                        invented.append(promoted.name)
            if branch.guard.ast_nodes() >= 2:
                promoted, cost = lib.promote_ast_subtree(branch.guard, "bool_macro", 1)
                compile_cost += cost
                if promoted is not None:
                    used.append(promoted.name)
                    if promoted.uses == 1:
                        invented.append(promoted.name)
        lib.register_memoized_program(hit)
        comp_ev, extra = lib.compress_solved_programs_mdl(hit, True, comp_c)
        invented.extend(extra)
        return _finish(
            hit, lib, synth_evals, 0, comp_ev, gate_evals, schema_cost, compile_cost, role_probe,
            synth_c, gate_c, arch_c, comp_c, tuple(used), tuple(invented),
            {
                "sub_macro_reused": bool(used),
                "subtree_macro_invented": bool(extra),
            },
        )

    if lib.use_cold_archive and lib.cold_archive and _alphabet_closed(all_pairs, extracted.tokens):
        archive_evals += 1
        archived_bools = [op for op in lib.cold_archive.values() if op.kind == "bool_macro"]
        archived_seqs = [op for op in lib.cold_archive.values() if op.kind == "seq_macro"]
        for bool_op in archived_bools:
            mask, ev = _guard_mask(bool_op.macro_node, core_pairs, arch_c)
            archive_evals += ev
            residual = tuple(src != dst for src, dst in core_pairs)
            if mask != residual:
                continue
            cand_t = list(tier0_t) + [op.macro_node for op in archived_seqs] + active_seqs
            for transform in cand_t:
                program = PiecewiseProgramAST(
                    (PiecewiseBranch(bool_op.macro_node, transform),), default
                )
                ok, ev2 = _eval_pairs(program, all_pairs, synth_c)
                synth_evals += ev2
                if ok:
                    restored = lib.cold_archive.pop(bool_op.name)
                    restored.uses += 1
                    restored.last_used_step = lib.step
                    lib.operators[bool_op.name] = restored
                    lib.mdl_pinned_names.add(bool_op.name)
                    lib.reactivated_names.append(bool_op.name)
                    return _finish(
                        program, lib, synth_evals, archive_evals, 0, gate_evals, schema_cost, 0, role_probe,
                        synth_c, gate_c, arch_c, comp_c, (bool_op.name,), (),
                        {"sub_macro_reused": True, "cold_archive_reactivated": True},
                    )

    search = TypedProgramEnumeratorSearch(enumerator)
    all_seq, extra_bools, ev = search.expand(
        extracted, [src for src, _dst in all_pairs], view["seq_macros"], synth_c
    )
    synth_evals += ev
    all_guards = tier0_g + extra_bools + active_bools
    all_transforms = tier0_t + [node for node in all_seq if node.ast_nodes() >= 2] + active_seqs

    hit = try_single(all_guards, all_transforms)
    if hit is None:
        hit = _synthesize_two_branch(
            core_pairs, all_pairs, all_guards, all_transforms, default, synth_c
        )
        if hit is not None:
            synth_evals += hit[1]
            hit = hit[0]
    if hit is not None:
        used = []
        invented = []
        for branch in hit.branches:
            if branch.guard.ast_nodes() >= 2:
                promoted, cost = lib.promote_ast_subtree(branch.guard, "bool_macro", 1)
                compile_cost += cost
                if promoted is not None:
                    used.append(promoted.name)
                    if promoted.uses == 1:
                        invented.append(promoted.name)
            if branch.transform.ast_nodes() >= 2:
                layer = 2 if _contains_macro(branch.transform) else 1
                promoted, cost = lib.promote_ast_subtree(branch.transform, "seq_macro", layer)
                compile_cost += cost
                if promoted is not None:
                    used.append(promoted.name)
                    if promoted.uses == 1:
                        invented.append(promoted.name)
        lib.register_memoized_program(hit)
        comp_ev, extra = lib.compress_solved_programs_mdl(hit, True, comp_c)
        invented.extend(extra)
        return _finish(
            hit, lib, synth_evals, archive_evals, comp_ev, gate_evals, schema_cost, compile_cost, role_probe,
            synth_c, gate_c, arch_c, comp_c, tuple(used), tuple(invented),
            {"subtree_macro_invented": bool(extra), "sub_macro_reused": bool(used)},
        )

    return _finish(
        PiecewiseProgramAST((), default),
        lib, synth_evals, archive_evals, 0, gate_evals, schema_cost, 0, role_probe,
        synth_c, gate_c, arch_c, comp_c, (), (), {"abstained": True},
    )


def _synthesize_two_branch(
    core_pairs: Sequence[Tuple[Seq, Seq]],
    all_pairs: Sequence[Tuple[Seq, Seq]],
    guards: Sequence[ExprAST],
    transforms: Sequence[ExprAST],
    default: ExprAST,
    synth_c: OpCounter,
) -> Optional[Tuple[PiecewiseProgramAST, int]]:
    evals = 0
    residual_idx = [i for i, (src, dst) in enumerate(core_pairs) if src != dst]
    if len(residual_idx) < 2:
        return None
    for transform in transforms:
        hits, ev = _transform_hits(transform, core_pairs, synth_c)
        evals += ev
        explained = [i for i in residual_idx if hits[i]]
        if not explained or len(explained) == len(residual_idx):
            continue
        target = tuple(i in explained for i in range(len(core_pairs)))
        for guard in guards:
            mask, ev2 = _guard_mask(guard, core_pairs, synth_c)
            evals += ev2
            if mask != target:
                continue
            remain = [i for i in residual_idx if i not in explained]
            remain_target = tuple(i in remain for i in range(len(core_pairs)))
            for transform2 in transforms:
                hits2, ev3 = _transform_hits(transform2, core_pairs, synth_c)
                evals += ev3
                if not all(hits2[i] for i in remain):
                    continue
                for guard2 in guards:
                    mask2, ev4 = _guard_mask(guard2, core_pairs, synth_c)
                    evals += ev4
                    if mask2 != remain_target:
                        continue
                    program = PiecewiseProgramAST(
                        (
                            PiecewiseBranch(guard, transform),
                            PiecewiseBranch(guard2, transform2),
                        ),
                        default,
                    )
                    ok, ev5 = _eval_pairs(program, all_pairs, synth_c)
                    evals += ev5
                    if ok:
                        return program, evals
    return None


@dataclass
class Wave12TaskExecutionReport:
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
    probe_work: int
    role_probe_work: int
    const_extraction_work: int
    schema_distill_cost: int
    gate_evals: int
    archive_lookup_evals: int
    compression_evals: int
    synthesis_evals: int
    compile_cost: int
    codegen_plus_synthesis: int
    total_work: int
    synth_primitive_op_steps: int
    gate_primitive_op_steps: int
    archive_primitive_op_steps: int
    probe_primitive_op_steps: int
    compression_primitive_op_steps: int
    total_primitive_op_steps: int
    schema_distilled: bool
    used_operators: Tuple[str, ...]
    invented_macros: Tuple[str, ...]
    sub_macro_reused: bool
    full_program_macro_reused: bool
    memoized_program_reused: bool
    cold_archive_reactivated: bool
    subtree_macro_invented: bool
    pruned_operators: Tuple[str, ...]
    active_library_size: int
    cold_archive_size: int
    catalog_audit: Dict[str, int]
    trace: List[Dict[str, Any]]
    extracted_tokens: Tuple[str, ...]
    extracted_ints: Tuple[int, ...]


def empty_cost_report(
    method: str,
    status: str,
    probe_work_parts: Tuple[int, int, int],
    catalog_audit: Dict[str, int],
    trace: List[Dict[str, Any]],
    lib: TypedMacroLibrary,
) -> Wave12TaskExecutionReport:
    pub_env, pub_val, chan = probe_work_parts
    probe_work = pub_env + pub_val + chan
    return Wave12TaskExecutionReport(
        method=method,
        status=status,
        admitted_field=None,
        chosen_slots=tuple(PUBLIC_SLOTS),
        public_observations=[],
        program_ast=make_abstain_program_dict(),
        public_consistent=False,
        ambiguous=status == "ambiguous",
        oog_abstained=status == "abstain",
        public_env_probes=pub_env,
        public_validation_probes=pub_val,
        channel_invariance_evals=chan,
        probe_work=probe_work,
        role_probe_work=0,
        const_extraction_work=0,
        schema_distill_cost=0,
        gate_evals=0,
        archive_lookup_evals=0,
        compression_evals=0,
        synthesis_evals=0,
        compile_cost=0,
        codegen_plus_synthesis=0,
        total_work=probe_work,
        synth_primitive_op_steps=0,
        gate_primitive_op_steps=0,
        archive_primitive_op_steps=0,
        probe_primitive_op_steps=0,
        compression_primitive_op_steps=0,
        total_primitive_op_steps=0,
        schema_distilled=lib.schemas_distilled,
        used_operators=(),
        invented_macros=(),
        sub_macro_reused=False,
        full_program_macro_reused=False,
        memoized_program_reused=False,
        cold_archive_reactivated=False,
        subtree_macro_invented=False,
        pruned_operators=tuple(lib.pruned_names),
        active_library_size=len(lib.operators),
        cold_archive_size=len(lib.cold_archive),
        catalog_audit=catalog_audit,
        trace=trace,
        extracted_tokens=(),
        extracted_ints=(),
    )


class TypedEqualCapabilityLearner:
    def __init__(self, method: str, max_guard_size: int = 6, max_transform_size: int = 7) -> None:
        if method not in WAVE12_METHODS:
            raise ValueError("Unknown Wave-12 method: {0}".format(method))
        self.method = method
        self.enumerator = TypedProgramEnumerator(max_guard_size, max_transform_size, 10)
        self.library = self._make_library(method)

    @staticmethod
    def _make_library(method: str) -> TypedMacroLibrary:
        if method == "equal_typed_scratch":
            return TypedMacroLibrary(False, False, False, False, False, False)
        if method == "ordinary_persistent_memoization":
            return TypedMacroLibrary(False, False, False, False, True, False)
        if method == "nexus_whole_macro_only":
            return TypedMacroLibrary(True, False, True, True, False, True)
        if method == "nexus_typed_without_pruning":
            return TypedMacroLibrary(True, True, False, False, False, True)
        return TypedMacroLibrary(True, True, True, True, False, True)

    def solve_unfamiliar_task(self, env: Any, public_budget: int = 10) -> Wave12TaskExecutionReport:
        if self.method == "equal_typed_scratch":
            self.library = self._make_library("equal_typed_scratch")
        manifest = typed_catalog_manifest()
        catalog_audit = {
            "sequence_opcodes_count": len(manifest["sequence_opcodes"]),
            "scalar_relational_opcodes_count": len(manifest["scalar_relational_opcodes"]),
            "branch_opcodes_count": len(manifest["branch_opcodes"]),
            "static_int_constants_count": len(manifest["static_int_constants"]),
            "static_tok_constants_count": len(manifest["static_tok_constants"]),
            "max_guard_size": self.enumerator.max_guard_size,
            "max_transform_size": self.enumerator.max_transform_size,
        }
        probed = _probe_environment_label_blind(env, public_budget)
        status = str(probed["status"])
        admitted_field = probed["field"]
        pub_env = int(probed["public_env_probes"])
        pub_val = int(probed["public_validation_probes"])
        chan = int(probed["channel_invariance_evals"])
        trace = list(probed["trace"])
        if status != "unique" or not admitted_field:
            return empty_cost_report(
                self.method, status, (pub_env, pub_val, chan), catalog_audit, trace, self.library
            )
        initial_records = list(probed["initial"])
        validation_rec = probed["validation"]
        core_pairs = [
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
            pair = (as_seq(validation_rec["payload"]), as_seq(validation_rec[admitted_field]))
            all_pairs.append(pair)
            public_obs.append(
                {
                    "slot": str(validation_rec.get("slot", "epsilon")),
                    "input": list(pair[0]),
                    "observed_output": list(pair[1]),
                }
            )
        extracted = extract_task_constants(public_obs)
        syn = synthesize_wave12(core_pairs, all_pairs, self.library, self.enumerator, extracted)
        verify_c = OpCounter()
        public_ok = not syn.abstained and all(
            execute_wave12_program_ast(syn.program_ast_dict, src, verify_c) == dst
            for src, dst in all_pairs
        )
        probe_work = pub_env + pub_val + chan
        total_work = (
            probe_work
            + syn.role_probe_work
            + extracted.work
            + syn.gate_evals
            + syn.archive_lookup_evals
            + syn.synthesis_evals
            + syn.compression_evals
            + syn.compile_cost
            + syn.schema_distill_cost
        )
        primitive_total = (
            syn.synth_primitive_op_steps
            + syn.gate_primitive_op_steps
            + syn.archive_primitive_op_steps
            + syn.compression_primitive_op_steps
        )
        return Wave12TaskExecutionReport(
            method=self.method,
            status="abstain" if syn.abstained else "unique",
            admitted_field=None if syn.abstained else admitted_field,
            chosen_slots=tuple(PUBLIC_SLOTS),
            public_observations=public_obs,
            program_ast=syn.program_ast_dict,
            public_consistent=public_ok,
            ambiguous=False,
            oog_abstained=syn.abstained,
            public_env_probes=pub_env,
            public_validation_probes=pub_val,
            channel_invariance_evals=chan,
            probe_work=probe_work,
            role_probe_work=syn.role_probe_work,
            const_extraction_work=extracted.work,
            schema_distill_cost=syn.schema_distill_cost,
            gate_evals=syn.gate_evals,
            archive_lookup_evals=syn.archive_lookup_evals,
            compression_evals=syn.compression_evals,
            synthesis_evals=syn.synthesis_evals,
            compile_cost=syn.compile_cost,
            codegen_plus_synthesis=syn.synthesis_evals + syn.archive_lookup_evals,
            total_work=total_work,
            synth_primitive_op_steps=syn.synth_primitive_op_steps,
            gate_primitive_op_steps=syn.gate_primitive_op_steps,
            archive_primitive_op_steps=syn.archive_primitive_op_steps,
            probe_primitive_op_steps=0,
            compression_primitive_op_steps=syn.compression_primitive_op_steps,
            total_primitive_op_steps=primitive_total,
            schema_distilled=syn.schema_distilled,
            used_operators=syn.used_operators,
            invented_macros=syn.invented_macros,
            sub_macro_reused=syn.sub_macro_reused,
            full_program_macro_reused=syn.full_program_macro_reused,
            memoized_program_reused=syn.memoized_program_reused,
            cold_archive_reactivated=syn.cold_archive_reactivated,
            subtree_macro_invented=syn.subtree_macro_invented,
            pruned_operators=tuple(self.library.pruned_names),
            active_library_size=len(self.library.operators),
            cold_archive_size=len(self.library.cold_archive),
            catalog_audit=catalog_audit,
            trace=trace,
            extracted_tokens=extracted.tokens,
            extracted_ints=extracted.ints,
        )


def report_to_row(report: Wave12TaskExecutionReport) -> Dict[str, Any]:
    return {
        "method": report.method,
        "status": report.status,
        "admitted_field": report.admitted_field,
        "program_ast": report.program_ast,
        "public_observations": report.public_observations,
        "public_consistent": report.public_consistent,
        "ambiguous": report.ambiguous,
        "oog_abstained": report.oog_abstained,
        "public_env_probes": report.public_env_probes,
        "public_validation_probes": report.public_validation_probes,
        "channel_invariance_evals": report.channel_invariance_evals,
        "probe_work": report.probe_work,
        "role_probe_work": report.role_probe_work,
        "const_extraction_work": report.const_extraction_work,
        "schema_distill_cost": report.schema_distill_cost,
        "gate_evals": report.gate_evals,
        "archive_lookup_evals": report.archive_lookup_evals,
        "compression_evals": report.compression_evals,
        "synthesis_evals": report.synthesis_evals,
        "compile_cost": report.compile_cost,
        "codegen_plus_synthesis": report.codegen_plus_synthesis,
        "total_work": report.total_work,
        "synth_primitive_op_steps": report.synth_primitive_op_steps,
        "gate_primitive_op_steps": report.gate_primitive_op_steps,
        "archive_primitive_op_steps": report.archive_primitive_op_steps,
        "probe_primitive_op_steps": report.probe_primitive_op_steps,
        "compression_primitive_op_steps": report.compression_primitive_op_steps,
        "total_primitive_op_steps": report.total_primitive_op_steps,
        "used_operators": list(report.used_operators),
        "invented_macros": list(report.invented_macros),
        "sub_macro_reused": report.sub_macro_reused,
        "full_program_macro_reused": report.full_program_macro_reused,
        "memoized_program_reused": report.memoized_program_reused,
        "cold_archive_reactivated": report.cold_archive_reactivated,
        "subtree_macro_invented": report.subtree_macro_invented,
        "pruned_operators": list(report.pruned_operators),
        "active_library_size": report.active_library_size,
        "cold_archive_size": report.cold_archive_size,
        "catalog_audit": dict(report.catalog_audit),
        "trace": list(report.trace),
        "extracted_tokens": list(report.extracted_tokens),
        "extracted_ints": list(report.extracted_ints),
    }


def reconstruct_total_work(row: Mapping[str, Any]) -> int:
    return sum(int(row.get(key) or 0) for key in WORK_KEYS)


def reconstruct_primitive_steps(row: Mapping[str, Any]) -> int:
    return sum(int(row.get(key) or 0) for key in PRIMITIVE_KEYS)


def format_runner_summary(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "kind": payload.get("kind"),
        "gates": payload.get("gates"),
        "suite_totals": (payload.get("totals") or {}).get("suite"),
        "hash": payload.get("hash"),
    }
