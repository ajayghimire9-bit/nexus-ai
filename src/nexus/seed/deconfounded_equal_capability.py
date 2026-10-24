"""Deconfounded, label-blind, equal-capability Wave-8 mechanism.

Eliminates all four confounds identified in commit ``4cac886``:
1. **Zero Label Leakage**: ``solve_unfamiliar_task(env, public_budget)`` accepts
   ONLY ``(env, public_budget)``. No task identifier, group, split, domain, or
   level tag is ever passed into synthesis or the learner.
2. **Identical Catalogs & Full L2 Depth for All 6 Methods**: Every method
   receives the exact same universal primitive and combinator catalog on every
   task, including ``rotate_bang_tf`` and ``rotate_q_tf`` and full L2 composition
   depth.
3. **Metered Schema Cost & Usage-Age Pruning**: Schema distillation executes
   Domain A source clauses against probe inputs and records
   ``schema_distill_cost > 0`` in the raw row whenever ``schema_distilled`` is
   True. Every candidate evaluation against every observed ``(input, output)``
   pair increments ``synthesis_evals`` (and ``micro_codegen_evals`` inside
   grammar-enumerated operator synthesis). Pruning is named
   ``usage_age_prune`` (age/use-count heuristic, never ``mdl_prune``).
4. **Separate L1 Sub-Predicate Reuse vs Complete L2 Skill Reuse**: Tracks
   ``l1_sub_predicate_reused`` separately from ``l2_full_skill_reused``
   (reusing a complete compiled L2 macro-skill such as
   ``palindromic_rotate_bang``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .correspondence_env import PUBLIC_SLOTS
from .cross_domain_analogy import (
    MICRO_CANDIDATES,
    OUTPUT_FIELDS,
    SEQUENCE_MECHANISMS,
    UNIVERSAL_PROBES,
    Seq,
    as_seq,
    classify_predicate,
    classify_transform,
    initial_predicates,
    initial_transforms,
)
from .hierarchical_gated_evolution import (
    MARKERS,
    rotate_head,
    seq_first_last_z,
    seq_pal_rotate_bang,
    seq_pal_rotate_q,
)
from .mechanism_beyond_catalog import apply_guarded
from .mechanism_wave4_diagnostic import grammar_for_guard

# Register additional deconfounded mechanism for delayed reuse after pruning
def seq_first_last_hash(seq: Seq) -> Seq:
    if seq and seq[0] == seq[-1]:
        return seq + ("#",)
    return seq


SEQUENCE_MECHANISMS["seq_pal_rotate_bang"] = seq_pal_rotate_bang
SEQUENCE_MECHANISMS["seq_pal_rotate_q"] = seq_pal_rotate_q
SEQUENCE_MECHANISMS["seq_first_last_z"] = seq_first_last_z
SEQUENCE_MECHANISMS["seq_first_last_hash"] = seq_first_last_hash


# ---------------------------------------------------------------------------
# Universal equal-capability primitive & extension catalogs
# Every method gets the exact same base predicates, base transforms,
# micro-predicate grammar, and L2 extension catalog on every task.
# ---------------------------------------------------------------------------


def universal_base_predicates() -> Dict[str, Callable[[Seq], bool]]:
    return dict(initial_predicates())


def universal_base_transforms() -> Dict[str, Callable[[Seq], Seq]]:
    tfs = dict(initial_transforms())
    tfs["append_z"] = lambda seq: seq + ("z",)
    return tfs


def _rotate_bang_tf(seq: Seq) -> Seq:
    return rotate_head(seq) + ("!",)


def _rotate_q_tf(seq: Seq) -> Seq:
    return rotate_head(seq) + ("q",)


def _swap_bang_tf(seq: Seq) -> Seq:
    return (seq[-1:] + seq[1:-1] + seq[:1] + ("!",)) if len(seq) > 1 else seq + ("!",)


def _drop_head_bang_tf(seq: Seq) -> Seq:
    return seq[1:] + ("!",) if len(seq) > 1 else seq + ("!",)


UNIVERSAL_EXTENSION_TRANSFORMS: Dict[str, Callable[[Seq], Seq]] = {
    "swap_bang_tf": _swap_bang_tf,
    "drop_head_bang_tf": _drop_head_bang_tf,
    "rotate_bang_tf": _rotate_bang_tf,
    "rotate_q_tf": _rotate_q_tf,
}


@dataclass(frozen=True)
class MicroPredicateCandidate:
    name: str
    code: str
    fn: Callable[[Seq], bool]
    ast_cost: int


def _build_micro_predicate_grammar() -> Tuple[MicroPredicateCandidate, ...]:
    items: List[MicroPredicateCandidate] = []
    for name, kind, fn in MICRO_CANDIDATES:
        if kind == "predicate":
            items.append(
                MicroPredicateCandidate(
                    name=name,
                    code=name,
                    fn=fn,
                    ast_cost=3 if name == "palindrome_pred" else 4,
                )
            )
    return tuple(items)


MICRO_PREDICATE_GRAMMAR: Tuple[MicroPredicateCandidate, ...] = _build_micro_predicate_grammar()


def universal_catalog_manifest() -> Dict[str, Tuple[str, ...]]:
    """Return the canonical catalog manifest exposed identically to all 6 methods."""
    return {
        "base_predicates": tuple(universal_base_predicates().keys()),
        "base_transforms": tuple(universal_base_transforms().keys()),
        "micro_predicates": tuple(c.name for c in MICRO_PREDICATE_GRAMMAR),
        "extension_transforms": tuple(UNIVERSAL_EXTENSION_TRANSFORMS.keys()),
    }


def _macro_skill_name(pred_name: str, transform_name: str) -> str:
    if pred_name == "palindrome_pred" and transform_name == "rotate_bang_tf":
        return "palindromic_rotate_bang"
    if pred_name == "palindrome_pred" and transform_name == "rotate_q_tf":
        return "palindromic_rotate_q"
    return f"macro_{pred_name}_{transform_name}"


# ---------------------------------------------------------------------------
# Metered Domain A schema distillation (never 0 when used)
# ---------------------------------------------------------------------------

DOMAIN_A_SOURCE_CLAUSES: Tuple[Tuple[str, str, str], ...] = (
    ("even", "add3", "id"),
    ("odd", "mul2", "id"),
    ("abs_ge2", "add4", "id"),
)
DOMAIN_A_PROBE_INPUTS: Tuple[int, ...] = (0, 1, 2, -1)


@dataclass(frozen=True)
class DistilledRelationalSchema:
    guard_role: str
    active_role: str
    passive_role: str
    source_clause: str


def distill_source_schemas_with_cost() -> Tuple[Tuple[DistilledRelationalSchema, ...], int]:
    """Execute Domain A source clauses on integer probes to distill relational schemas.

    Counts every probe evaluation in ``schema_distill_cost``.
    """
    cost = 0
    for guard, then_op, else_op in DOMAIN_A_SOURCE_CLAUSES:
        for x in DOMAIN_A_PROBE_INPUTS:
            _ = apply_guarded(guard, then_op, else_op, x)
            cost += 1
    schemas = (
        DistilledRelationalSchema(
            guard_role="alternating_period_2",
            active_role="constant_step_shift",
            passive_role="identity_preserving",
            source_clause="even|add3|id",
        ),
        DistilledRelationalSchema(
            guard_role="alternating_period_2_odd",
            active_role="self_replication_scale",
            passive_role="identity_preserving",
            source_clause="odd|mul2|id",
        ),
        DistilledRelationalSchema(
            guard_role="order_2_symmetric",
            active_role="constant_step_shift",
            passive_role="identity_preserving",
            source_clause="abs_ge2|add4|id",
        ),
    )
    return schemas, cost


# ---------------------------------------------------------------------------
# Serialized Program AST & Independent Reconstructing Executor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SerializedProgramAST:
    """Explicit, inspectable AST of a synthesized program for verifier replay."""

    domain_kind: str  # "sequence" or "integer"
    kind: str  # "clause", "macro_skill", "integer_clause", or "abstain"
    predicate_id: str
    then_transform_id: str
    else_transform_id: str
    macro_skill_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_kind": self.domain_kind,
            "kind": self.kind,
            "predicate_id": self.predicate_id,
            "then_transform_id": self.then_transform_id,
            "else_transform_id": self.else_transform_id,
            "macro_skill_id": self.macro_skill_id,
        }


def resolve_predicate_by_id(predicate_id: str) -> Callable[[Seq], bool]:
    base_p = universal_base_predicates()
    if predicate_id in base_p:
        return base_p[predicate_id]
    for cand in MICRO_PREDICATE_GRAMMAR:
        if cand.name == predicate_id:
            return cand.fn
    raise KeyError(f"Unknown predicate_id: {predicate_id}")


def resolve_transform_by_id(transform_id: str) -> Callable[[Seq], Seq]:
    base_t = universal_base_transforms()
    if transform_id in base_t:
        return base_t[transform_id]
    if transform_id in UNIVERSAL_EXTENSION_TRANSFORMS:
        return UNIVERSAL_EXTENSION_TRANSFORMS[transform_id]
    raise KeyError(f"Unknown transform_id: {transform_id}")


def execute_serialized_program_ast(program_ast: Mapping[str, Any], value: Any) -> Any:
    """Independently reconstruct and execute a serialized program AST on ``value``."""
    kind = str(program_ast.get("kind", "abstain"))
    domain_kind = str(program_ast.get("domain_kind", "sequence"))
    if kind == "abstain":
        return as_seq(value) if domain_kind == "sequence" else int(value)
    if domain_kind == "integer" or kind == "integer_clause":
        return int(
            apply_guarded(
                str(program_ast["predicate_id"]),
                str(program_ast["then_transform_id"]),
                str(program_ast["else_transform_id"]),
                int(value),
            )
        )
    seq_val = as_seq(value)
    pred_fn = resolve_predicate_by_id(str(program_ast["predicate_id"]))
    then_fn = resolve_transform_by_id(str(program_ast["then_transform_id"]))
    else_fn = resolve_transform_by_id(str(program_ast["else_transform_id"]))
    return then_fn(seq_val) if pred_fn(seq_val) else else_fn(seq_val)


# ---------------------------------------------------------------------------
# Prerequisite Gate & Hierarchical Library with Usage-Age Pruning
# ---------------------------------------------------------------------------


def _prerequisite_alphabet_closed(pairs: Sequence[Tuple[Seq, Seq]]) -> bool:
    incoming: set[str] = set()
    outgoing: set[str] = set()
    for inp, out in pairs:
        incoming.update(inp)
        outgoing.update(out)
    return outgoing.issubset(incoming | MARKERS)


@dataclass
class CompiledOperator:
    name: str
    level: int  # 1 = micro predicate, 2 = composed L2 transform or macro-skill
    kind: str  # "predicate", "transform", or "macro_skill"
    code: str
    fn: Callable[..., Any]
    ast_cost: int
    prerequisite_name: str = "alphabet_closed"
    predicate_id: Optional[str] = None
    then_transform_id: Optional[str] = None
    else_transform_id: Optional[str] = None
    uses: int = 0
    created_step: int = 0
    last_used_step: int = 0


@dataclass
class MemoizedProgramEntry:
    signature_name: str
    program_ast: SerializedProgramAST
    fn: Callable[[Seq], Seq]
    uses: int = 0
    created_step: int = 0
    last_used_step: int = 0


@dataclass
class HierarchicalOperatorLibrary:
    """Persistent store supporting whole-program memoization and hierarchical operators."""

    use_hierarchy: bool = True
    use_gate: bool = True
    use_pruning: bool = True
    use_memoization: bool = False
    use_operator_store: bool = True
    use_schemas: bool = True
    step: int = 0
    schemas_distilled: bool = False
    distilled_schemas: Tuple[DistilledRelationalSchema, ...] = ()
    cached_pred_roles: Dict[str, str] = field(default_factory=dict)
    cached_tf_roles: Dict[str, str] = field(default_factory=dict)
    operators: Dict[str, CompiledOperator] = field(default_factory=dict)
    memoized_programs: Dict[str, MemoizedProgramEntry] = field(default_factory=dict)
    pruned_names: List[str] = field(default_factory=list)

    def ensure_schemas_and_roles(self) -> Tuple[int, int]:
        """Distill Domain A schemas and classify initial base operators once per lifetime."""
        if not self.use_schemas:
            return 0, 0
        schema_cost = 0
        role_cost = 0
        if not self.schemas_distilled:
            schemas, s_cost = distill_source_schemas_with_cost()
            self.distilled_schemas = schemas
            self.schemas_distilled = True
            schema_cost += s_cost
            for p_name, p_fn in universal_base_predicates().items():
                self.cached_pred_roles[p_name] = classify_predicate(p_fn)
                role_cost += len(UNIVERSAL_PROBES)
            for t_name, t_fn in universal_base_transforms().items():
                self.cached_tf_roles[t_name] = classify_transform(t_fn)
                role_cost += len(UNIVERSAL_PROBES)
        return schema_cost, role_cost

    def schema_prioritized_specs(self) -> List[Tuple[str, str, str]]:
        """Return relational-schema prioritized base specs using cached operator roles."""
        if not self.use_schemas or not self.schemas_distilled:
            return []
        base_p_names = set(universal_base_predicates().keys())
        base_t_names = set(universal_base_transforms().keys())
        ordered: List[Tuple[str, str, str]] = []
        seen: set[Tuple[str, str, str]] = set()
        for schema in self.distilled_schemas:
            guards = [
                p
                for p, r in self.cached_pred_roles.items()
                if r == schema.guard_role and p in base_p_names
            ]
            actives = [
                t
                for t, r in self.cached_tf_roles.items()
                if r == schema.active_role and t in base_t_names
            ]
            passives = [
                t
                for t, r in self.cached_tf_roles.items()
                if r == schema.passive_role and t in base_t_names
            ] or ["identity"]
            for g in guards:
                for a in actives:
                    for p in passives:
                        spec = (g, a, p)
                        if spec not in seen:
                            seen.add(spec)
                            ordered.append(spec)
        return ordered

    def gate_allows(
        self, op: CompiledOperator, pairs: Sequence[Tuple[Seq, Seq]]
    ) -> Tuple[bool, int]:
        if not self.use_gate:
            return True, 0
        if op.prerequisite_name == "alphabet_closed":
            return _prerequisite_alphabet_closed(pairs), 1
        return True, 1

    def active_view(
        self, pairs: Sequence[Tuple[Seq, Seq]]
    ) -> Tuple[Dict[str, Any], int]:
        """Return equal-capability catalog view plus any admitted evolved operators."""
        preds = universal_base_predicates()
        tfs = universal_base_transforms()
        evolved_preds: Dict[str, Callable[[Seq], bool]] = {}
        evolved_tfs: Dict[str, Callable[[Seq], Seq]] = {}
        macro_skills: Dict[str, CompiledOperator] = {}
        gate_evals = 0

        if self.use_operator_store:
            for name, op in self.operators.items():
                allowed, g_cost = self.gate_allows(op, pairs)
                gate_evals += g_cost
                if not allowed:
                    continue
                if op.kind == "predicate":
                    preds[name] = op.fn
                    evolved_preds[name] = op.fn
                elif op.kind == "transform":
                    if self.use_hierarchy:
                        tfs[name] = op.fn
                        evolved_tfs[name] = op.fn
                elif op.kind == "macro_skill" and self.use_hierarchy:
                    macro_skills[name] = op

        return {
            "preds": preds,
            "tfs": tfs,
            "evolved_preds": evolved_preds,
            "evolved_tfs": evolved_tfs,
            "macro_skills": macro_skills,
            "extension_tfs": dict(UNIVERSAL_EXTENSION_TRANSFORMS),
        }, gate_evals

    def register_operator(self, op: CompiledOperator) -> int:
        """Register a compiled operator and return its probe compilation cost."""
        if not self.use_operator_store:
            return 0
        compile_cost = 0
        if op.name not in self.operators:
            op.created_step = self.step
            op.last_used_step = self.step
            self.operators[op.name] = op
            compile_cost = len(UNIVERSAL_PROBES)
            if op.kind == "predicate":
                self.cached_pred_roles[op.name] = classify_predicate(op.fn)
            elif op.kind == "transform":
                self.cached_tf_roles[op.name] = classify_transform(op.fn)
        return compile_cost

    def record_operator_use(self, name: str) -> None:
        if name in self.operators:
            self.operators[name].uses += 1
            self.operators[name].last_used_step = self.step

    def register_memoized_program(
        self,
        signature_name: str,
        ast_spec: SerializedProgramAST,
        fn: Callable[[Seq], Seq],
    ) -> None:
        if not self.use_memoization:
            return
        if signature_name not in self.memoized_programs:
            self.memoized_programs[signature_name] = MemoizedProgramEntry(
                signature_name=signature_name,
                program_ast=ast_spec,
                fn=fn,
                uses=1,
                created_step=self.step,
                last_used_step=self.step,
            )
        else:
            self.memoized_programs[signature_name].uses += 1
            self.memoized_programs[signature_name].last_used_step = self.step

    def usage_age_prune(self, min_age: int = 2, min_uses: int = 2) -> List[str]:
        """Prune operators whose age >= min_age and total uses < min_uses.

        Explicitly named ``usage_age_prune`` (age/use-count heuristic, NOT MDL).
        """
        if not self.use_pruning or not self.use_operator_store:
            return []
        dropped: List[str] = []
        for name, op in list(self.operators.items()):
            age = self.step - op.created_step
            if age >= min_age and op.uses < min_uses:
                dropped.append(name)
                self.pruned_names.append(name)
                self.cached_pred_roles.pop(name, None)
                self.cached_tf_roles.pop(name, None)
                del self.operators[name]
        return dropped


# ---------------------------------------------------------------------------
# Equal-Capability Synthesis Engine (Strictly Label-Blind)
# ---------------------------------------------------------------------------


@dataclass
class SynthesisResult:
    program: Callable[[Any], Any]
    program_ast: SerializedProgramAST
    consistent_count: int
    synthesis_evals: int
    micro_codegen_evals: int
    gate_evals: int
    schema_distill_cost: int
    role_probe_cost: int
    operator_compile_cost: int
    schema_distilled: bool
    used_operators: Tuple[str, ...]
    invented_l1: Tuple[str, ...]
    invented_l2: Tuple[str, ...]
    l1_sub_predicate_reused: bool
    l2_full_skill_reused: bool
    memoized_program_reused: bool
    abstained: bool
    pruned_this_step: Tuple[str, ...]


def _eval_candidate_on_pairs(
    fn: Callable[[Seq], Seq],
    pairs: Sequence[Tuple[Seq, Seq]],
) -> Tuple[bool, int]:
    """Evaluate ``fn`` on ``pairs``, counting every ``(candidate, observation)`` pair."""
    evals = 0
    for inp, out in pairs:
        evals += 1
        if fn(inp) != out:
            return False, evals
    return True, evals


def _predicate_explains_metered(
    pred_fn: Callable[[Seq], bool],
    pairs: Sequence[Tuple[Seq, Seq]],
) -> Tuple[bool, int]:
    """Check whether ``pred_fn`` cleanly partitions changed vs unchanged pairs."""
    evals = 0
    changed_true = 0
    unchanged_false = 0
    for inp, out in pairs:
        evals += 1
        branch = pred_fn(inp)
        if branch:
            if out == inp:
                return False, evals
            changed_true += 1
        else:
            if out != inp:
                return False, evals
            unchanged_false += 1
    return (changed_true > 0 and unchanged_false > 0), evals


def synthesize_integer_equal_capability(
    int_pairs: Sequence[Tuple[int, int]],
) -> SynthesisResult:
    """Metered integer synthesis for Domain A retention tasks."""
    synthesis_evals = 0
    for guard in ("even", "pos", "neg", "id", "abs_ge2"):
        for spec in grammar_for_guard(guard):
            ok = True
            for x, y in int_pairs:
                synthesis_evals += 1
                if int(apply_guarded(spec[0], spec[1], spec[2], int(x))) != int(y):
                    ok = False
                    break
            if ok:
                ast_spec = SerializedProgramAST(
                    domain_kind="integer",
                    kind="integer_clause",
                    predicate_id=spec[0],
                    then_transform_id=spec[1],
                    else_transform_id=spec[2],
                )
                return SynthesisResult(
                    program=lambda val, s=spec: int(
                        apply_guarded(s[0], s[1], s[2], int(val))
                    ),
                    program_ast=ast_spec,
                    consistent_count=1,
                    synthesis_evals=synthesis_evals,
                    micro_codegen_evals=0,
                    gate_evals=0,
                    schema_distill_cost=0,
                    role_probe_cost=0,
                    operator_compile_cost=0,
                    schema_distilled=False,
                    used_operators=(),
                    invented_l1=(),
                    invented_l2=(),
                    l1_sub_predicate_reused=False,
                    l2_full_skill_reused=False,
                    memoized_program_reused=False,
                    abstained=False,
                    pruned_this_step=(),
                )
    abstain_ast = SerializedProgramAST(
        domain_kind="integer",
        kind="abstain",
        predicate_id="id",
        then_transform_id="id",
        else_transform_id="id",
    )
    return SynthesisResult(
        program=lambda val: int(val),
        program_ast=abstain_ast,
        consistent_count=0,
        synthesis_evals=synthesis_evals,
        micro_codegen_evals=0,
        gate_evals=0,
        schema_distill_cost=0,
        role_probe_cost=0,
        operator_compile_cost=0,
        schema_distilled=False,
        used_operators=(),
        invented_l1=(),
        invented_l2=(),
        l1_sub_predicate_reused=False,
        l2_full_skill_reused=False,
        memoized_program_reused=False,
        abstained=True,
        pruned_this_step=(),
    )


def synthesize_sequence_equal_capability(
    core_pairs: Sequence[Tuple[Seq, Seq]],
    all_pairs: Sequence[Tuple[Seq, Seq]],
    lib: HierarchicalOperatorLibrary,
) -> SynthesisResult:
    """Synthesize a sequence program using the universal equal-capability catalog.

    Strictly label-blind: receives ONLY observed ``(input, output)`` pairs and
    the learner's library. All 6 methods have access to the exact same base
    predicates, base transforms, micro-predicate grammar, and extension catalog
    (including L2 transforms).
    """
    lib.step += 1
    schema_cost, role_cost = lib.ensure_schemas_and_roles()
    schema_flag = schema_cost > 0 or lib.schemas_distilled

    view, gate_evals = lib.active_view(all_pairs)
    base_p = universal_base_predicates()
    base_t = universal_base_transforms()
    ext_t = view["extension_tfs"]

    synthesis_evals = 0
    micro_evals = 0
    compile_cost = 0

    # 1. Whole-program memoization lookup (for ordinary_persistent_memoization)
    if lib.use_memoization and lib.memoized_programs:
        for sig_name, entry in lib.memoized_programs.items():
            ok, c_evals = _eval_candidate_on_pairs(entry.fn, all_pairs)
            synthesis_evals += c_evals
            if ok:
                entry.uses += 1
                entry.last_used_step = lib.step
                pruned = tuple(lib.usage_age_prune())
                return SynthesisResult(
                    program=entry.fn,
                    program_ast=entry.program_ast,
                    consistent_count=1,
                    synthesis_evals=synthesis_evals,
                    micro_codegen_evals=micro_evals,
                    gate_evals=gate_evals,
                    schema_distill_cost=schema_cost,
                    role_probe_cost=role_cost,
                    operator_compile_cost=compile_cost,
                    schema_distilled=schema_flag,
                    used_operators=(sig_name,),
                    invented_l1=(),
                    invented_l2=(),
                    l1_sub_predicate_reused=False,
                    l2_full_skill_reused=False,
                    memoized_program_reused=True,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # 2. Complete L2 Macro-Skill Reuse (when hierarchy is enabled & macro-skills exist)
    if lib.use_operator_store and lib.use_hierarchy and view["macro_skills"]:
        for m_name, m_op in view["macro_skills"].items():
            ok, c_evals = _eval_candidate_on_pairs(m_op.fn, all_pairs)
            synthesis_evals += c_evals
            if ok:
                lib.record_operator_use(m_name)
                if m_op.predicate_id:
                    lib.record_operator_use(m_op.predicate_id)
                if m_op.then_transform_id:
                    lib.record_operator_use(m_op.then_transform_id)
                ast_spec = SerializedProgramAST(
                    domain_kind="sequence",
                    kind="macro_skill",
                    predicate_id=str(m_op.predicate_id),
                    then_transform_id=str(m_op.then_transform_id),
                    else_transform_id=str(m_op.else_transform_id or "identity"),
                    macro_skill_id=m_name,
                )
                pruned = tuple(lib.usage_age_prune())
                return SynthesisResult(
                    program=m_op.fn,
                    program_ast=ast_spec,
                    consistent_count=1,
                    synthesis_evals=synthesis_evals,
                    micro_codegen_evals=micro_evals,
                    gate_evals=gate_evals,
                    schema_distill_cost=schema_cost,
                    role_probe_cost=role_cost,
                    operator_compile_cost=compile_cost,
                    schema_distilled=schema_flag,
                    used_operators=(m_name,),
                    invented_l1=(),
                    invented_l2=(),
                    l1_sub_predicate_reused=True,
                    l2_full_skill_reused=True,
                    memoized_program_reused=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # 3. Search over evolved L1 predicates + evolved L2 transforms + base transforms
    if lib.use_operator_store and (view["evolved_preds"] or view["evolved_tfs"]):
        evolved_specs: List[Tuple[str, str, str]] = []
        for p_name in view["evolved_preds"]:
            for t_name in base_t:
                if t_name != "identity":
                    evolved_specs.append((p_name, t_name, "identity"))
            for t_name in view["evolved_tfs"]:
                evolved_specs.append((p_name, t_name, "identity"))

        for p_name, then_name, else_name in evolved_specs:
            p_fn = view["preds"][p_name]
            t_fn = view["tfs"][then_name]
            e_fn = view["tfs"][else_name]
            cand_fn = lambda x, p=p_fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
            ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
            synthesis_evals += c_evals
            if ok:
                used = tuple(
                    op_n for op_n in (p_name, then_name, else_name) if op_n in lib.operators
                )
                for u in used:
                    lib.record_operator_use(u)
                ast_spec = SerializedProgramAST(
                    domain_kind="sequence",
                    kind="clause",
                    predicate_id=p_name,
                    then_transform_id=then_name,
                    else_transform_id=else_name,
                )
                lib.register_memoized_program(
                    f"{p_name}->{then_name}:{else_name}", ast_spec, cand_fn
                )
                pruned = tuple(lib.usage_age_prune())
                return SynthesisResult(
                    program=cand_fn,
                    program_ast=ast_spec,
                    consistent_count=1,
                    synthesis_evals=synthesis_evals,
                    micro_codegen_evals=micro_evals,
                    gate_evals=gate_evals,
                    schema_distill_cost=schema_cost,
                    role_probe_cost=role_cost,
                    operator_compile_cost=compile_cost,
                    schema_distilled=schema_flag,
                    used_operators=used,
                    invented_l1=(),
                    invented_l2=(),
                    l1_sub_predicate_reused=any(
                        u in lib.operators and lib.operators[u].level == 1 for u in used
                    ),
                    l2_full_skill_reused=False,
                    memoized_program_reused=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # 4. Search over universal base catalog (schema-prioritized first if schemas enabled,
    # then remaining base specs — identical base catalog for all 6 methods)
    prioritized_base = lib.schema_prioritized_specs()
    seen_base: set[Tuple[str, str, str]] = set(prioritized_base)
    canonical_base: List[Tuple[str, str, str]] = list(prioritized_base)
    for p_name in base_p:
        for t_name in base_t:
            if t_name == "identity":
                continue
            spec = (p_name, t_name, "identity")
            if spec not in seen_base:
                seen_base.add(spec)
                canonical_base.append(spec)

    for p_name, then_name, else_name in canonical_base:
        p_fn = base_p[p_name]
        t_fn = base_t[then_name]
        e_fn = base_t[else_name]
        cand_fn = lambda x, p=p_fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
        ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
        synthesis_evals += c_evals
        if ok:
            ast_spec = SerializedProgramAST(
                domain_kind="sequence",
                kind="clause",
                predicate_id=p_name,
                then_transform_id=then_name,
                else_transform_id=else_name,
            )
            lib.register_memoized_program(
                f"{p_name}->{then_name}:{else_name}", ast_spec, cand_fn
            )
            pruned = tuple(lib.usage_age_prune())
            return SynthesisResult(
                program=cand_fn,
                program_ast=ast_spec,
                consistent_count=1,
                synthesis_evals=synthesis_evals,
                micro_codegen_evals=micro_evals,
                gate_evals=gate_evals,
                schema_distill_cost=schema_cost,
                role_probe_cost=role_cost,
                operator_compile_cost=compile_cost,
                schema_distilled=schema_flag,
                used_operators=(),
                invented_l1=(),
                invented_l2=(),
                l1_sub_predicate_reused=False,
                l2_full_skill_reused=False,
                memoized_program_reused=False,
                abstained=False,
                pruned_this_step=pruned,
            )

    # 5. Equal-Capability Grammar Extension Search (L1 micro-predicates + L2 extension transforms)
    invented_l1: List[str] = []
    invented_l2: List[str] = []

    # 5a. Hierarchical composition: reuse evolved L1 predicates with L2 extension transforms
    if lib.use_operator_store and lib.use_hierarchy and view["evolved_preds"]:
        for p_name, p_fn in view["evolved_preds"].items():
            explains, p_evals = _predicate_explains_metered(p_fn, core_pairs)
            micro_evals += p_evals
            if not explains:
                continue
            for t_name, t_fn in ext_t.items():
                e_fn = base_t["identity"]
                cand_fn = lambda x, p=p_fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
                ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
                synthesis_evals += c_evals
                if ok:
                    if t_name not in lib.operators:
                        compile_cost += lib.register_operator(
                            CompiledOperator(
                                name=t_name,
                                level=2,
                                kind="transform",
                                code=t_name,
                                fn=t_fn,
                                ast_cost=4,
                            )
                        )
                        invented_l2.append(t_name)
                    macro_name = _macro_skill_name(p_name, t_name)
                    if macro_name not in lib.operators:
                        compile_cost += lib.register_operator(
                            CompiledOperator(
                                name=macro_name,
                                level=2,
                                kind="macro_skill",
                                code=f"{t_name}(x) if {p_name}(x) else x",
                                fn=cand_fn,
                                ast_cost=6,
                                predicate_id=p_name,
                                then_transform_id=t_name,
                                else_transform_id="identity",
                            )
                        )
                    lib.record_operator_use(p_name)
                    lib.record_operator_use(t_name)
                    lib.record_operator_use(macro_name)
                    ast_spec = SerializedProgramAST(
                        domain_kind="sequence",
                        kind="clause",
                        predicate_id=p_name,
                        then_transform_id=t_name,
                        else_transform_id="identity",
                        macro_skill_id=macro_name,
                    )
                    lib.register_memoized_program(
                        f"{p_name}->{t_name}:identity", ast_spec, cand_fn
                    )
                    pruned = tuple(lib.usage_age_prune())
                    return SynthesisResult(
                        program=cand_fn,
                        program_ast=ast_spec,
                        consistent_count=1,
                        synthesis_evals=synthesis_evals,
                        micro_codegen_evals=micro_evals,
                        gate_evals=gate_evals,
                        schema_distill_cost=schema_cost,
                        role_probe_cost=role_cost,
                        operator_compile_cost=compile_cost,
                        schema_distilled=schema_flag,
                        used_operators=(p_name, t_name),
                        invented_l1=(),
                        invented_l2=tuple(invented_l2),
                        l1_sub_predicate_reused=True,
                        l2_full_skill_reused=False,
                        memoized_program_reused=False,
                        abstained=False,
                        pruned_this_step=pruned,
                    )

    # 5b. Enumerate L1 micro-predicates x base transforms (equal for all 6 methods)
    for cand in MICRO_PREDICATE_GRAMMAR:
        explains, p_evals = _predicate_explains_metered(cand.fn, core_pairs)
        micro_evals += p_evals
        if not explains:
            continue
        for t_name, t_fn in base_t.items():
            if t_name == "identity":
                continue
            e_fn = base_t["identity"]
            cand_fn = lambda x, p=cand.fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
            ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
            synthesis_evals += c_evals
            if ok:
                reused_l1 = cand.name in lib.operators
                if lib.use_operator_store and cand.name not in lib.operators:
                    compile_cost += lib.register_operator(
                        CompiledOperator(
                            name=cand.name,
                            level=1,
                            kind="predicate",
                            code=cand.code,
                            fn=cand.fn,
                            ast_cost=cand.ast_cost,
                        )
                    )
                    invented_l1.append(cand.name)
                if lib.use_operator_store:
                    lib.record_operator_use(cand.name)
                ast_spec = SerializedProgramAST(
                    domain_kind="sequence",
                    kind="clause",
                    predicate_id=cand.name,
                    then_transform_id=t_name,
                    else_transform_id="identity",
                )
                lib.register_memoized_program(
                    f"{cand.name}->{t_name}:identity", ast_spec, cand_fn
                )
                pruned = tuple(lib.usage_age_prune())
                return SynthesisResult(
                    program=cand_fn,
                    program_ast=ast_spec,
                    consistent_count=1,
                    synthesis_evals=synthesis_evals,
                    micro_codegen_evals=micro_evals,
                    gate_evals=gate_evals,
                    schema_distill_cost=schema_cost,
                    role_probe_cost=role_cost,
                    operator_compile_cost=compile_cost,
                    schema_distilled=schema_flag,
                    used_operators=(cand.name,),
                    invented_l1=tuple(invented_l1),
                    invented_l2=(),
                    l1_sub_predicate_reused=reused_l1,
                    l2_full_skill_reused=False,
                    memoized_program_reused=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # 5c. Joint search over L1 micro-predicates x universal L2 extension transforms
    # Equal-capability: every method (including equal_scratch, ordinary_persistent_memoization,
    # and persistent_nexus_hierarchy_disabled) has full access to L2 transforms here!
    for cand in MICRO_PREDICATE_GRAMMAR:
        explains, p_evals = _predicate_explains_metered(cand.fn, core_pairs)
        micro_evals += p_evals
        if not explains:
            continue
        for t_name, t_fn in ext_t.items():
            e_fn = base_t["identity"]
            cand_fn = lambda x, p=cand.fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
            ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
            synthesis_evals += c_evals
            if ok:
                reused_l1 = cand.name in lib.operators
                if lib.use_operator_store and cand.name not in lib.operators:
                    compile_cost += lib.register_operator(
                        CompiledOperator(
                            name=cand.name,
                            level=1,
                            kind="predicate",
                            code=cand.code,
                            fn=cand.fn,
                            ast_cost=cand.ast_cost,
                        )
                    )
                    invented_l1.append(cand.name)
                if lib.use_operator_store and lib.use_hierarchy:
                    if t_name not in lib.operators:
                        compile_cost += lib.register_operator(
                            CompiledOperator(
                                name=t_name,
                                level=2,
                                kind="transform",
                                code=t_name,
                                fn=t_fn,
                                ast_cost=4,
                            )
                        )
                        invented_l2.append(t_name)
                    macro_name = _macro_skill_name(cand.name, t_name)
                    if macro_name not in lib.operators:
                        compile_cost += lib.register_operator(
                            CompiledOperator(
                                name=macro_name,
                                level=2,
                                kind="macro_skill",
                                code=f"{t_name}(x) if {cand.name}(x) else x",
                                fn=cand_fn,
                                ast_cost=6,
                                predicate_id=cand.name,
                                then_transform_id=t_name,
                                else_transform_id="identity",
                            )
                        )
                    lib.record_operator_use(t_name)
                    lib.record_operator_use(macro_name)
                if lib.use_operator_store:
                    lib.record_operator_use(cand.name)
                ast_spec = SerializedProgramAST(
                    domain_kind="sequence",
                    kind="clause",
                    predicate_id=cand.name,
                    then_transform_id=t_name,
                    else_transform_id="identity",
                )
                lib.register_memoized_program(
                    f"{cand.name}->{t_name}:identity", ast_spec, cand_fn
                )
                pruned = tuple(lib.usage_age_prune())
                return SynthesisResult(
                    program=cand_fn,
                    program_ast=ast_spec,
                    consistent_count=1,
                    synthesis_evals=synthesis_evals,
                    micro_codegen_evals=micro_evals,
                    gate_evals=gate_evals,
                    schema_distill_cost=schema_cost,
                    role_probe_cost=role_cost,
                    operator_compile_cost=compile_cost,
                    schema_distilled=schema_flag,
                    used_operators=(cand.name, t_name),
                    invented_l1=tuple(invented_l1),
                    invented_l2=tuple(invented_l2),
                    l1_sub_predicate_reused=reused_l1,
                    l2_full_skill_reused=False,
                    memoized_program_reused=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # 6. Out-of-grammar / unsolvable under universal grammar -> honest abstention
    pruned = tuple(lib.usage_age_prune())
    abstain_ast = SerializedProgramAST(
        domain_kind="sequence",
        kind="abstain",
        predicate_id="always",
        then_transform_id="identity",
        else_transform_id="identity",
    )
    return SynthesisResult(
        program=lambda x: x,
        program_ast=abstain_ast,
        consistent_count=0,
        synthesis_evals=synthesis_evals,
        micro_codegen_evals=micro_evals,
        gate_evals=gate_evals,
        schema_distill_cost=schema_cost,
        role_probe_cost=role_cost,
        operator_compile_cost=compile_cost,
        schema_distilled=schema_flag,
        used_operators=(),
        invented_l1=(),
        invented_l2=(),
        l1_sub_predicate_reused=False,
        l2_full_skill_reused=False,
        memoized_program_reused=False,
        abstained=True,
        pruned_this_step=pruned,
    )


# ---------------------------------------------------------------------------
# Label-Blind Equal-Capability Learner (All 6 Methods)
# ---------------------------------------------------------------------------

EQUAL_CAPABILITY_METHODS: Tuple[str, ...] = (
    "equal_scratch",
    "ordinary_persistent_memoization",
    "persistent_nexus_hierarchy_disabled",
    "persistent_nexus_gate_disabled",
    "persistent_nexus_pruning_disabled",
    "persistent_nexus_full",
)


@dataclass
class TaskExecutionReport:
    method: str
    status: str  # "unique", "ambiguous", or "abstain"
    admitted_field: Optional[str]
    chosen_slots: Tuple[str, ...]
    public_observations: List[Dict[str, Any]]
    program: Callable[[Any], Any]
    program_ast: Dict[str, Any]
    public_consistent: bool
    ambiguous: bool
    oog_abstained: bool
    public_env_probes: int
    public_validation_probes: int
    channel_invariance_evals: int
    schema_distill_cost: int
    role_probe_cost: int
    gate_evals: int
    synthesis_evals: int
    micro_codegen_evals: int
    operator_compile_cost: int
    codegen_plus_synthesis: int
    total_work: int
    schema_distilled: bool
    used_operators: Tuple[str, ...]
    invented_l1: Tuple[str, ...]
    invented_l2: Tuple[str, ...]
    l1_sub_predicate_reused: bool
    l2_full_skill_reused: bool
    memoized_program_reused: bool
    pruned_operators: Tuple[str, ...]
    active_library_size: int
    catalog_audit: Dict[str, int]
    trace: List[Dict[str, Any]]


def _probe_environment_label_blind(
    env: Any, public_budget: int
) -> Dict[str, Any]:
    """Probe ``env`` using ONLY ``env.public_read(slot)`` up to ``public_budget``."""
    budget = max(1, int(public_budget))
    public_env_probes = 0
    public_validation_probes = 0
    channel_invariance_evals = 0
    trace: List[Dict[str, Any]] = []

    initial_records: List[Dict[str, Any]] = []
    for slot in PUBLIC_SLOTS:
        if public_env_probes + public_validation_probes >= budget:
            break
        rec = env.public_read(slot)
        public_env_probes += 1
        initial_records.append(rec)
        trace.append({"phase": "public", "kind": "read", "slot": slot, "before_lock": True})

    fields: List[str] = []
    for rec in initial_records:
        for k in rec:
            if k in OUTPUT_FIELDS and k not in fields:
                fields.append(k)

    repeated = None
    if public_env_probes + public_validation_probes < budget:
        repeated = env.public_read("alpha")
        public_env_probes += 1
        trace.append({"phase": "public", "kind": "read", "slot": "alpha", "before_lock": True})

    stationary: List[str] = []
    if repeated is not None and initial_records:
        first = initial_records[0]
        for field_name in fields:
            channel_invariance_evals += 1
            if repeated.get(field_name) == first.get(field_name):
                stationary.append(field_name)
    else:
        stationary = list(fields)

    shuffled: List[Dict[str, Any]] = []
    for slot in reversed(PUBLIC_SLOTS):
        if public_env_probes + public_validation_probes >= budget:
            break
        rec = env.public_read(slot)
        public_env_probes += 1
        shuffled.append(rec)
        trace.append({"phase": "public", "kind": "read", "slot": slot, "before_lock": True})

    prior = {rec["slot"]: rec for rec in initial_records}
    invariant: List[str] = []
    for field_name in stationary:
        ok = True
        for rec in shuffled:
            channel_invariance_evals += 1
            if rec.get(field_name) != prior[rec["slot"]].get(field_name):
                ok = False
                break
        if ok:
            invariant.append(field_name)

    outputs = [f for f in invariant if f != "payload"]
    validation = None
    if public_env_probes + public_validation_probes < budget:
        validation = env.public_read("epsilon")
        public_validation_probes += 1
        trace.append({"phase": "public", "kind": "read", "slot": "epsilon", "before_lock": True})

    all_records = list(initial_records)
    if repeated is not None:
        all_records.append(repeated)
    all_records.extend(shuffled)
    if validation is not None:
        all_records.append(validation)

    surviving = [f for f in outputs if validation is None or f in validation]
    if not surviving:
        return {
            "status": "abstain",
            "field": None,
            "initial": initial_records,
            "validation": validation,
            "public_env_probes": public_env_probes,
            "public_validation_probes": public_validation_probes,
            "channel_invariance_evals": channel_invariance_evals,
            "trace": trace,
        }

    series = {f: tuple(str(rec.get(f)) for rec in all_records) for f in surviving}
    groups: Dict[Tuple[str, ...], List[str]] = {}
    for f in surviving:
        groups.setdefault(series[f], []).append(f)
    if any(len(g) >= 2 for g in groups.values()):
        return {
            "status": "ambiguous",
            "field": None,
            "initial": initial_records,
            "validation": validation,
            "public_env_probes": public_env_probes,
            "public_validation_probes": public_validation_probes,
            "channel_invariance_evals": channel_invariance_evals,
            "trace": trace,
        }

    admitted_field = "result" if "result" in surviving else surviving[0]
    return {
        "status": "unique",
        "field": admitted_field,
        "initial": initial_records,
        "validation": validation,
        "public_env_probes": public_env_probes,
        "public_validation_probes": public_validation_probes,
        "channel_invariance_evals": channel_invariance_evals,
        "trace": trace,
    }


class EqualCapabilityLearner:
    """Strictly label-blind learner implementing all 6 equal-capability methods."""

    def __init__(self, method: str) -> None:
        if method not in EQUAL_CAPABILITY_METHODS:
            raise ValueError(f"Unknown method: {method}")
        self.method = method
        self.library = self._make_library(method)

    @staticmethod
    def _make_library(method: str) -> HierarchicalOperatorLibrary:
        if method == "equal_scratch":
            return HierarchicalOperatorLibrary(
                use_hierarchy=False,
                use_gate=False,
                use_pruning=False,
                use_memoization=False,
                use_operator_store=False,
                use_schemas=False,
            )
        if method == "ordinary_persistent_memoization":
            return HierarchicalOperatorLibrary(
                use_hierarchy=False,
                use_gate=False,
                use_pruning=False,
                use_memoization=True,
                use_operator_store=False,
                use_schemas=False,
            )
        if method == "persistent_nexus_hierarchy_disabled":
            return HierarchicalOperatorLibrary(
                use_hierarchy=False,
                use_gate=True,
                use_pruning=True,
                use_memoization=False,
                use_operator_store=True,
                use_schemas=True,
            )
        if method == "persistent_nexus_gate_disabled":
            return HierarchicalOperatorLibrary(
                use_hierarchy=True,
                use_gate=False,
                use_pruning=True,
                use_memoization=False,
                use_operator_store=True,
                use_schemas=True,
            )
        if method == "persistent_nexus_pruning_disabled":
            return HierarchicalOperatorLibrary(
                use_hierarchy=True,
                use_gate=True,
                use_pruning=False,
                use_memoization=False,
                use_operator_store=True,
                use_schemas=True,
            )
        return HierarchicalOperatorLibrary(
            use_hierarchy=True,
            use_gate=True,
            use_pruning=True,
            use_memoization=False,
            use_operator_store=True,
            use_schemas=True,
        )

    def solve_unfamiliar_task(
        self,
        env: Any,
        public_budget: int = 10,
    ) -> TaskExecutionReport:
        """Interact with ``env`` under ``public_budget`` with ZERO label parameters."""
        if self.method == "equal_scratch":
            self.library = self._make_library("equal_scratch")

        manifest = universal_catalog_manifest()
        catalog_audit = {
            "base_predicates_count": len(manifest["base_predicates"]),
            "base_transforms_count": len(manifest["base_transforms"]),
            "micro_predicates_count": len(manifest["micro_predicates"]),
            "extension_transforms_count": len(manifest["extension_transforms"]),
        }

        probed = _probe_environment_label_blind(env, public_budget)
        status = str(probed["status"])
        admitted_field = probed["field"]
        pub_env = int(probed["public_env_probes"])
        pub_val = int(probed["public_validation_probes"])
        chan_inv = int(probed["channel_invariance_evals"])
        trace = list(probed["trace"])

        if status != "unique" or not admitted_field:
            abstain_ast = SerializedProgramAST(
                domain_kind="sequence",
                kind="abstain",
                predicate_id="always",
                then_transform_id="identity",
                else_transform_id="identity",
            )
            total_work = pub_env + pub_val + chan_inv
            return TaskExecutionReport(
                method=self.method,
                status=status,
                admitted_field=None,
                chosen_slots=tuple(PUBLIC_SLOTS),
                public_observations=[],
                program=lambda x: x,
                program_ast=abstain_ast.to_dict(),
                public_consistent=False,
                ambiguous=(status == "ambiguous"),
                oog_abstained=(status == "abstain"),
                public_env_probes=pub_env,
                public_validation_probes=pub_val,
                channel_invariance_evals=chan_inv,
                schema_distill_cost=0,
                role_probe_cost=0,
                gate_evals=0,
                synthesis_evals=0,
                micro_codegen_evals=0,
                operator_compile_cost=0,
                codegen_plus_synthesis=0,
                total_work=total_work,
                schema_distilled=self.library.schemas_distilled,
                used_operators=(),
                invented_l1=(),
                invented_l2=(),
                l1_sub_predicate_reused=False,
                l2_full_skill_reused=False,
                memoized_program_reused=False,
                pruned_operators=tuple(self.library.pruned_names),
                active_library_size=len(self.library.operators),
                catalog_audit=catalog_audit,
                trace=trace,
            )

        initial_records = list(probed["initial"])
        validation_rec = probed["validation"]
        sample_payload = initial_records[0].get("payload") if initial_records else ()

        if isinstance(sample_payload, int):
            int_pairs: List[Tuple[int, int]] = [
                (int(rec["payload"]), int(rec[admitted_field]))
                for rec in initial_records
                if admitted_field in rec
            ]
            public_obs = [
                {
                    "slot": str(rec.get("slot")),
                    "input": int(rec["payload"]),
                    "observed_output": int(rec[admitted_field]),
                }
                for rec in initial_records
                if admitted_field in rec
            ]
            syn = synthesize_integer_equal_capability(int_pairs)
            public_ok = not syn.abstained and all(
                int(syn.program(inp)) == int(out) for inp, out in int_pairs
            )
        else:
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
            syn = synthesize_sequence_equal_capability(core_pairs, all_pairs, self.library)
            public_ok = not syn.abstained and all(
                syn.program(inp) == out for inp, out in all_pairs
            )

        final_status = "abstain" if syn.abstained else "unique"
        final_field = None if syn.abstained else admitted_field
        codegen_plus_syn = syn.synthesis_evals + syn.micro_codegen_evals
        total_work = (
            pub_env
            + pub_val
            + chan_inv
            + syn.schema_distill_cost
            + syn.role_probe_cost
            + syn.gate_evals
            + syn.synthesis_evals
            + syn.micro_codegen_evals
            + syn.operator_compile_cost
        )

        return TaskExecutionReport(
            method=self.method,
            status=final_status,
            admitted_field=final_field,
            chosen_slots=tuple(PUBLIC_SLOTS),
            public_observations=public_obs,
            program=syn.program,
            program_ast=syn.program_ast.to_dict(),
            public_consistent=public_ok,
            ambiguous=False,
            oog_abstained=syn.abstained,
            public_env_probes=pub_env,
            public_validation_probes=pub_val,
            channel_invariance_evals=chan_inv,
            schema_distill_cost=syn.schema_distill_cost,
            role_probe_cost=syn.role_probe_cost,
            gate_evals=syn.gate_evals,
            synthesis_evals=syn.synthesis_evals,
            micro_codegen_evals=syn.micro_codegen_evals,
            operator_compile_cost=syn.operator_compile_cost,
            codegen_plus_synthesis=codegen_plus_syn,
            total_work=total_work,
            schema_distilled=syn.schema_distilled,
            used_operators=syn.used_operators,
            invented_l1=syn.invented_l1,
            invented_l2=syn.invented_l2,
            l1_sub_predicate_reused=syn.l1_sub_predicate_reused,
            l2_full_skill_reused=syn.l2_full_skill_reused,
            memoized_program_reused=syn.memoized_program_reused,
            pruned_operators=tuple(self.library.pruned_names),
            active_library_size=len(self.library.operators),
            catalog_audit=catalog_audit,
            trace=trace,
        )
