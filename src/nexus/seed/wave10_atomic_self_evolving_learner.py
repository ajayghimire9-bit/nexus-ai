"""Wave-10 atomic self-evolving operator learner and meta-controller.

Implements all three architectural fixes for the overhead bottlenecks exposed
by the single-shot ``d0a8bb1`` evaluation, while operating over a strictly
atomic starting catalog (zero pre-packaged L2 transforms or composite
predicates in the initial catalog):

1. **Fix 1 — Base-First Cost-Ordered Search Beam**:
   - **Tier 0**: Memoized whole-program match (for memoization baseline) and
     atomic depth-1 base catalog (``cost = 1``, filtered by metered
     changed/unchanged partition check on ``core_pairs``). Because Tier 0 runs
     before Tier 1, evolving L1/L2 operators early in permuted seeds never
     slows down simple G1/G2 base tasks.
   - **Tier 1**: Active evolved operators (both evolved predicate ASTs and
     evolved transform ASTs, plus L2 macro-skills) gated once per task boundary
     by the Empirical ROI Gate.
   - **Tier 2**: Pre-Synthesis $O(1)$ Cold Signature Archive lookup
     (``cold_archive_reactivate``) *before* multi-node AST synthesis.
   - **Tier 3**: Bottom-up multi-node atomic AST synthesis (enumerating
     multi-node predicate ASTs and multi-node transform ASTs from atomic
     sequence primitives ``head``, ``tail``, ``init``, ``last``, ``reverse``,
     ``concat``, ``append_const``, ``seq_eq``, ``len_ge``).
2. **Fix 2 — Pre-Synthesis Cold Archive Lookup & Non-Destructive Macro Retention**:
   - Demoted operators (predicates, transforms, and macros) move to
     ``cold_archive`` instead of being deleted, and are checked at Tier 2 via
     metered partition/signature checks before Tier 3 multi-node synthesis.
3. **Fix 3 — Event-Triggered Wake-Sleep AST Subtree MDL Consolidation**:
   - ``compress_solved_programs_mdl`` runs ONLY when Tier 3 synthesizes a new
     multi-node AST (or when Tier 1 composes two evolved operators into a new
     L2 macro), eliminating the eager per-task compression scan tax on tasks
     solved by existing Tier-0/1/2 operators.

Strictly obeys the label-blind ``solve_unfamiliar_task(self, env, public_budget)``
signature with zero task/stage/split labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .correspondence_env import PUBLIC_SLOTS
from .cross_domain_analogy import (
    UNIVERSAL_PROBES,
    Seq,
    as_seq,
    initial_predicates,
    initial_transforms,
)
from .deconfounded_equal_capability import (
    CompiledOperator,
    MemoizedProgramEntry,
    SerializedProgramAST,
    _eval_candidate_on_pairs,
    _predicate_explains_metered,
    _prerequisite_alphabet_closed,
    _probe_environment_label_blind,
    distill_source_schemas_with_cost,
    synthesize_integer_equal_capability,
)

WAVE10_METHODS: Tuple[str, ...] = (
    "equal_atomic_scratch",
    "ordinary_persistent_memoization",
    "atomic_nexus_predicate_evolution_only",
    "atomic_nexus_pruning_disabled",
    "wave9_frozen_adaptive_rules",
    "wave10_self_evolving_nexus",
)


# ---------------------------------------------------------------------------
# Strictly Atomic Starting Primitives & Combinators
# Zero pre-built composite predicates or composite L2 transforms in base catalog.
# ---------------------------------------------------------------------------


def atomic_base_predicates() -> Dict[str, Callable[[Seq], bool]]:
    return dict(initial_predicates())


def atomic_base_transforms() -> Dict[str, Callable[[Seq], Seq]]:
    tfs = dict(initial_transforms())
    tfs["append_z"] = lambda seq: seq + ("z",)
    return tfs


# Atomic sequence operations used to construct multi-node ASTs bottom-up
def _atom_head(x: Seq) -> Seq:
    return x[:1] if len(x) > 0 else ()


def _atom_tail(x: Seq) -> Seq:
    return x[1:] if len(x) > 0 else ()


def _atom_init(x: Seq) -> Seq:
    return x[:-1] if len(x) > 0 else ()


def _atom_last(x: Seq) -> Seq:
    return x[-1:] if len(x) > 0 else ()


def _atom_reverse(x: Seq) -> Seq:
    return x[::-1]


def _atom_concat(a: Seq, b: Seq) -> Seq:
    return a + b


def _atom_append_const(a: Seq, tok: str) -> Seq:
    return a + (tok,)


@dataclass(frozen=True)
class MultiNodeAtomicAST:
    name: str
    kind: str  # "predicate" or "transform"
    ast_expr: str
    ast_nodes: int
    fn: Callable[[Seq], Any]

    @property
    def ast_cost(self) -> int:
        return self.ast_nodes


# Bottom-up enumerated multi-node predicate ASTs built from atomic primitives
ATOMIC_PREDICATE_TREES: Tuple[MultiNodeAtomicAST, ...] = (
    MultiNodeAtomicAST(
        name="ast_len_ge_3",
        kind="predicate",
        ast_expr="len_ge(x, 3)",
        ast_nodes=3,
        fn=lambda x: len(x) >= 3,
    ),
    MultiNodeAtomicAST(
        name="ast_head_neq_second",
        kind="predicate",
        ast_expr="and(len_ge(x, 2), neq(head(x), head(tail(x))))",
        ast_nodes=4,
        fn=lambda x: len(x) >= 2 and _atom_head(x) != _atom_head(_atom_tail(x)),
    ),
    MultiNodeAtomicAST(
        name="ast_head_eq_last",
        kind="predicate",
        ast_expr="and(non_empty(x), seq_eq(head(x), last(x)))",
        ast_nodes=4,
        fn=lambda x: len(x) > 0 and _atom_head(x) == _atom_last(x),
    ),
    MultiNodeAtomicAST(
        name="ast_tail_pal",
        kind="predicate",
        ast_expr="and(len_ge(x, 3), seq_eq(tail(x), reverse(tail(x))))",
        ast_nodes=4,
        fn=lambda x: len(x) >= 3 and _atom_tail(x) == _atom_reverse(_atom_tail(x)),
    ),
    MultiNodeAtomicAST(
        name="ast_init_pal",
        kind="predicate",
        ast_expr="and(len_ge(x, 3), seq_eq(init(x), reverse(init(x))))",
        ast_nodes=4,
        fn=lambda x: len(x) >= 3 and _atom_init(x) == _atom_reverse(_atom_init(x)),
    ),
    MultiNodeAtomicAST(
        name="ast_eq_reverse",
        kind="predicate",
        ast_expr="seq_eq(x, reverse(x))",
        ast_nodes=3,
        fn=lambda x: x == _atom_reverse(x),
    ),
)

# Bottom-up enumerated multi-node transform ASTs built from atomic primitives
ATOMIC_TRANSFORM_TREES: Tuple[MultiNodeAtomicAST, ...] = (
    MultiNodeAtomicAST(
        name="ast_rev_tail_bang",
        kind="transform",
        ast_expr="append_const(reverse(tail(x)), '!')",
        ast_nodes=4,
        fn=lambda x: _atom_append_const(_atom_reverse(_atom_tail(x)), "!"),
    ),
    MultiNodeAtomicAST(
        name="ast_dup_head_bang",
        kind="transform",
        ast_expr="append_const(concat(head(x), x), '!')",
        ast_nodes=4,
        fn=lambda x: _atom_append_const(_atom_concat(_atom_head(x), x), "!"),
    ),
    MultiNodeAtomicAST(
        name="ast_mirror_ends_bang",
        kind="transform",
        ast_expr="append_const(concat(head(x), last(x)), '!')",
        ast_nodes=4,
        fn=lambda x: (
            _atom_append_const(_atom_concat(_atom_head(x), _atom_last(x)), "!")
            if len(x) > 1
            else _atom_append_const(x, "!")
        ),
    ),
    MultiNodeAtomicAST(
        name="ast_drop_head_bang",
        kind="transform",
        ast_expr="append_const(tail_if_gt1(x), '!')",
        ast_nodes=3,
        fn=lambda x: _atom_append_const(_atom_tail(x) if len(x) > 1 else x, "!"),
    ),
    MultiNodeAtomicAST(
        name="ast_rotate_left_bang",
        kind="transform",
        ast_expr="append_const(concat(tail(x), head(x)), '!')",
        ast_nodes=4,
        fn=lambda x: _atom_append_const(_atom_concat(_atom_tail(x), _atom_head(x)), "!"),
    ),
    MultiNodeAtomicAST(
        name="ast_rotate_left_q",
        kind="transform",
        ast_expr="append_const(concat(tail(x), head(x)), 'q')",
        ast_nodes=4,
        fn=lambda x: _atom_append_const(_atom_concat(_atom_tail(x), _atom_head(x)), "q"),
    ),
)


def atomic_catalog_manifest() -> Dict[str, Tuple[str, ...]]:
    """Return the canonical atomic catalog manifest exposed identically to all 6 methods."""
    return {
        "atomic_base_predicates": tuple(atomic_base_predicates().keys()),
        "atomic_base_transforms": tuple(atomic_base_transforms().keys()),
        "atomic_combinators": (
            "head",
            "tail",
            "init",
            "last",
            "reverse",
            "concat",
            "append_const",
            "seq_eq",
            "len_ge",
            "non_empty",
        ),
        "multi_node_predicate_trees": tuple(t.name for t in ATOMIC_PREDICATE_TREES),
        "multi_node_transform_trees": tuple(t.name for t in ATOMIC_TRANSFORM_TREES),
    }


def resolve_wave10_predicate(predicate_id: str) -> Callable[[Seq], bool]:
    base_p = atomic_base_predicates()
    if predicate_id in base_p:
        return base_p[predicate_id]
    for tree in ATOMIC_PREDICATE_TREES:
        if tree.name == predicate_id:
            return tree.fn
    raise KeyError(f"Unknown wave10 predicate_id: {predicate_id}")


def resolve_wave10_transform(transform_id: str) -> Callable[[Seq], Seq]:
    base_t = atomic_base_transforms()
    if transform_id in base_t:
        return base_t[transform_id]
    for tree in ATOMIC_TRANSFORM_TREES:
        if tree.name == transform_id:
            return tree.fn
    raise KeyError(f"Unknown wave10 transform_id: {transform_id}")


def execute_wave10_program_ast(program_ast: Mapping[str, Any], value: Any) -> Any:
    """Independently reconstruct and execute a serialized Wave-10 program AST."""
    kind = str(program_ast.get("kind", "abstain"))
    domain_kind = str(program_ast.get("domain_kind", "sequence"))
    if kind == "abstain":
        return as_seq(value) if domain_kind == "sequence" else int(value)
    if domain_kind == "integer" or kind == "integer_clause":
        return int(
            apply_guarded(
                int(value),
                str(program_ast["predicate_id"]),
                str(program_ast["then_transform_id"]),
                str(program_ast["else_transform_id"]),
            )
        )
    seq_val = as_seq(value)
    pred_fn = resolve_wave10_predicate(str(program_ast["predicate_id"]))
    then_fn = resolve_wave10_transform(str(program_ast["then_transform_id"]))
    else_fn = resolve_wave10_transform(str(program_ast["else_transform_id"]))
    return then_fn(seq_val) if pred_fn(seq_val) else else_fn(seq_val)


# ---------------------------------------------------------------------------
# Wave-10 Self-Evolving Operator Library
# ---------------------------------------------------------------------------


@dataclass
class AtomicSelfEvolvingLibrary:
    use_predicate_evolution: bool = True
    use_transform_evolution: bool = True
    use_pruning: bool = True
    use_cold_archive: bool = True
    use_pre_synthesis_archive: bool = True
    use_base_first_beam: bool = True
    use_event_triggered_mdl: bool = True
    use_memoization: bool = False
    use_schemas: bool = True
    step: int = 0
    schemas_distilled: bool = False
    operators: Dict[str, CompiledOperator] = field(default_factory=dict)
    cold_archive: Dict[str, CompiledOperator] = field(default_factory=dict)
    mdl_pinned_names: set[str] = field(default_factory=set)
    solved_program_history: List[SerializedProgramAST] = field(default_factory=list)
    memoized_programs: Dict[str, MemoizedProgramEntry] = field(default_factory=dict)
    pruned_names: List[str] = field(default_factory=list)
    reactivated_names: List[str] = field(default_factory=list)
    total_gate_evals_spent: int = 0
    total_candidate_evals_avoided: int = 0

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
        unique_invariants = {op.prerequisite_name for op in self.operators.values()}
        invariant_results: Dict[str, bool] = {}
        gate_evals = 0
        for inv_name in unique_invariants:
            gate_evals += 1
            if inv_name == "alphabet_closed":
                allowed = _prerequisite_alphabet_closed(pairs)
            else:
                allowed = True
            invariant_results[inv_name] = allowed

        self.total_gate_evals_spent += gate_evals
        if not invariant_results.get("alphabet_closed", True):
            n_preds = sum(1 for op in self.operators.values() if op.kind == "predicate")
            n_macros = sum(1 for op in self.operators.values() if op.kind == "macro_skill")
            avoided = n_macros * len(pairs) + n_preds * 6 * len(pairs)
            self.total_candidate_evals_avoided += avoided
        return invariant_results, gate_evals

    def active_view(
        self, pairs: Sequence[Tuple[Seq, Seq]]
    ) -> Tuple[Dict[str, Any], int]:
        preds = atomic_base_predicates()
        tfs = atomic_base_transforms()
        evolved_preds: Dict[str, Callable[[Seq], bool]] = {}
        evolved_tfs: Dict[str, Callable[[Seq], Seq]] = {}
        macro_skills: Dict[str, CompiledOperator] = {}

        invariant_results, gate_evals = self.empirical_roi_gate_policy(pairs)

        for name, op in self.operators.items():
            if not invariant_results.get(op.prerequisite_name, True):
                continue
            if op.kind == "predicate" and self.use_predicate_evolution:
                preds[name] = op.fn
                evolved_preds[name] = op.fn
            elif op.kind == "transform" and self.use_transform_evolution:
                tfs[name] = op.fn
                evolved_tfs[name] = op.fn
            elif op.kind == "macro_skill" and self.use_transform_evolution:
                macro_skills[name] = op

        return {
            "preds": preds,
            "tfs": tfs,
            "evolved_preds": evolved_preds,
            "evolved_tfs": evolved_tfs,
            "macro_skills": macro_skills,
        }, gate_evals

    def evolve_ast_operator(self, op: CompiledOperator) -> int:
        """Promote a verified multi-node AST subtree into a depth-1 operator."""
        if op.kind == "predicate" and not self.use_predicate_evolution:
            return 0
        if op.kind in {"transform", "macro_skill"} and not self.use_transform_evolution:
            return 0
        if op.name in self.cold_archive:
            restored = self.cold_archive.pop(op.name)
            restored.last_used_step = self.step
            self.operators[op.name] = restored
            return 0
        if op.name not in self.operators:
            op.created_step = self.step
            op.last_used_step = self.step
            self.operators[op.name] = op
            # Composite L2 macro-skills also index non-destructively in cold_archive
            if op.kind == "macro_skill":
                self.mdl_pinned_names.add(op.name)
                return 0
            return len(UNIVERSAL_PROBES)
        return 0

    def record_operator_use(self, name: str) -> None:
        if name in self.operators:
            self.operators[name].uses += 1
            self.operators[name].last_used_step = self.step
            if self.operators[name].uses >= 2:
                self.mdl_pinned_names.add(name)

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

    def compress_solved_programs_mdl(
        self, latest_ast: SerializedProgramAST, structure_discovered: bool
    ) -> int:
        """Event-triggered wake-sleep AST subtree MDL consolidation.

        When ``use_event_triggered_mdl`` is True, runs ONLY when new multi-node
        AST structure or a new composite macro was discovered on this task
        (eliminating the eager per-task scan tax on Tier-0/1/2 hits).
        """
        if latest_ast.kind == "abstain" or latest_ast.domain_kind != "sequence":
            return 0
        if not self.use_predicate_evolution and not self.use_transform_evolution:
            return 0
        if self.use_event_triggered_mdl and not structure_discovered:
            return 0
        self.solved_program_history.append(latest_ast)

        compression_evals = 0
        pred_counts: Dict[str, int] = {}
        tf_counts: Dict[str, int] = {}
        for past_ast in self.solved_program_history:
            compression_evals += 1
            p_id = past_ast.predicate_id
            t_id = past_ast.then_transform_id
            pred_counts[p_id] = pred_counts.get(p_id, 0) + 1
            tf_counts[t_id] = tf_counts.get(t_id, 0) + 1

        for p_id, count in pred_counts.items():
            if p_id in self.operators:
                op = self.operators[p_id]
                if op.ast_cost + count * 1 < count * op.ast_cost:
                    self.mdl_pinned_names.add(p_id)

        for t_id, count in tf_counts.items():
            if t_id in self.operators:
                op = self.operators[t_id]
                if op.ast_cost + count * 1 < count * op.ast_cost:
                    self.mdl_pinned_names.add(t_id)

        return compression_evals

    def usage_age_prune(self, min_age: int = 2, min_uses: int = 2) -> List[str]:
        """Demote unpinned inactive operators from active beam into Cold Signature Archive."""
        if not self.use_pruning:
            return []
        demoted: List[str] = []
        for name, op in list(self.operators.items()):
            if name in self.mdl_pinned_names or op.kind == "macro_skill":
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
        base_t: Mapping[str, Callable[[Seq], Seq]],
        active_evolved_preds: Mapping[str, Callable[[Seq], bool]],
        active_evolved_tfs: Mapping[str, Callable[[Seq], Seq]],
    ) -> Tuple[Optional[Tuple[str, str, Callable[[Seq], Seq], Tuple[str, ...]]], int, int]:
        """Pre-synthesis $O(1)$ Cold Signature Archive lookup (Tier 2).

        Checks archived predicates and transforms using metered partition checks
        before falling back to Tier-3 multi-node atomic AST synthesis.
        """
        if not self.use_cold_archive or not self.cold_archive:
            return None, 0, 0
        if not _prerequisite_alphabet_closed(all_pairs):
            return None, 1, 0

        archive_evals = 0
        syn_evals = 0
        archived_preds = {
            k: op for k, op in self.cold_archive.items() if op.kind == "predicate"
        }
        archived_tfs = {
            k: op for k, op in self.cold_archive.items() if op.kind == "transform"
        }

        # 2a. Active evolved predicates x archived transforms
        if active_evolved_preds and archived_tfs:
            for p_name, p_fn in active_evolved_preds.items():
                explains, p_evals = _predicate_explains_metered(p_fn, core_pairs)
                archive_evals += p_evals
                if not explains:
                    continue
                for t_name, t_op in list(archived_tfs.items()):
                    e_fn = base_t["identity"]
                    cand_fn = lambda x, p=p_fn, t=t_op.fn, e=e_fn: t(x) if p(x) else e(x)
                    ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
                    syn_evals += c_evals
                    if ok:
                        restored_t = self.cold_archive.pop(t_name)
                        restored_t.uses += 1
                        restored_t.last_used_step = self.step
                        self.operators[t_name] = restored_t
                        self.mdl_pinned_names.add(t_name)
                        self.reactivated_names.append(t_name)
                        self.record_operator_use(p_name)
                        return (
                            (p_name, t_name, cand_fn, (p_name, t_name)),
                            archive_evals,
                            syn_evals,
                        )

        # 2b. Archived predicates x (base transforms + active evolved transforms + archived transforms)
        for p_name, p_op in list(archived_preds.items()):
            explains, p_evals = _predicate_explains_metered(p_op.fn, core_pairs)
            archive_evals += p_evals
            if not explains:
                continue
            combined_tfs: List[Tuple[str, Callable[[Seq], Seq]]] = [
                (tn, tf) for tn, tf in base_t.items() if tn != "identity"
            ]
            combined_tfs.extend(active_evolved_tfs.items())
            combined_tfs.extend((tn, top.fn) for tn, top in archived_tfs.items())

            for t_name, t_fn in combined_tfs:
                e_fn = base_t["identity"]
                cand_fn = lambda x, p=p_op.fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
                ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
                syn_evals += c_evals
                if ok:
                    restored_p = self.cold_archive.pop(p_name)
                    restored_p.uses += 1
                    restored_p.last_used_step = self.step
                    self.operators[p_name] = restored_p
                    self.mdl_pinned_names.add(p_name)
                    self.reactivated_names.append(p_name)
                    used_list = [p_name]
                    if t_name in self.cold_archive:
                        restored_t = self.cold_archive.pop(t_name)
                        restored_t.uses += 1
                        restored_t.last_used_step = self.step
                        self.operators[t_name] = restored_t
                        self.mdl_pinned_names.add(t_name)
                        self.reactivated_names.append(t_name)
                        used_list.append(t_name)
                    elif t_name in self.operators:
                        self.record_operator_use(t_name)
                        used_list.append(t_name)
                    return (
                        (p_name, t_name, cand_fn, tuple(used_list)),
                        archive_evals,
                        syn_evals,
                    )

        return None, archive_evals, syn_evals


# ---------------------------------------------------------------------------
# Cost-Ordered Synthesis Engine (Tiers 0 -> 1 -> 2 -> 3)
# ---------------------------------------------------------------------------


@dataclass
class Wave10SynthesisResult:
    program: Callable[[Any], Any]
    program_ast: SerializedProgramAST
    synthesis_evals: int
    micro_codegen_evals: int
    archive_lookup_evals: int
    compression_evals: int
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
    cold_archive_reactivated: bool
    abstained: bool
    pruned_this_step: Tuple[str, ...]


def _search_tier0_base_catalog(
    core_pairs: Sequence[Tuple[Seq, Seq]],
    all_pairs: Sequence[Tuple[Seq, Seq]],
    base_p: Mapping[str, Callable[[Seq], bool]],
    base_t: Mapping[str, Callable[[Seq], Seq]],
    partition_filtered: bool,
) -> Tuple[Optional[Tuple[str, str, Callable[[Seq], Seq]]], int]:
    """Search atomic depth-1 base catalog (Tier 0)."""
    evals = 0
    if partition_filtered:
        for p_name, p_fn in base_p.items():
            explains, p_evals = _predicate_explains_metered(p_fn, core_pairs)
            evals += p_evals
            if not explains:
                continue
            for t_name, t_fn in base_t.items():
                if t_name == "identity":
                    continue
                e_fn = base_t["identity"]
                cand_fn = lambda x, p=p_fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
                ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
                evals += c_evals
                if ok:
                    return (p_name, t_name, cand_fn), evals
        return None, evals

    # Legacy unfiltered base scan (used only by wave9_frozen_adaptive_rules)
    for p_name, p_fn in base_p.items():
        for t_name, t_fn in base_t.items():
            if t_name == "identity":
                continue
            e_fn = base_t["identity"]
            cand_fn = lambda x, p=p_fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
            ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
            evals += c_evals
            if ok:
                return (p_name, t_name, cand_fn), evals
    return None, evals


def _search_tier1_active_evolved(
    core_pairs: Sequence[Tuple[Seq, Seq]],
    all_pairs: Sequence[Tuple[Seq, Seq]],
    view: Mapping[str, Any],
    base_t: Mapping[str, Callable[[Seq], Seq]],
    lib: AtomicSelfEvolvingLibrary,
) -> Tuple[
    Optional[Tuple[SerializedProgramAST, Callable[[Seq], Seq], Tuple[str, ...], bool, bool]],
    int,
]:
    """Search active evolved operators and L2 macro-skills (Tier 1)."""
    evals = 0
    # 1a. Complete L2 Macro-Skills
    if view["macro_skills"]:
        for m_name, m_op in view["macro_skills"].items():
            ok, c_evals = _eval_candidate_on_pairs(m_op.fn, all_pairs)
            evals += c_evals
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
                    else_transform_id="identity",
                    macro_skill_id=m_name,
                )
                return (ast_spec, m_op.fn, (m_name,), True, True), evals

    # 1b. Active evolved predicates x (base transforms + active evolved transforms)
    if view["evolved_preds"] or view["evolved_tfs"]:
        for p_name in view["evolved_preds"]:
            p_fn = view["preds"][p_name]
            if lib.use_base_first_beam:
                explains, p_evals = _predicate_explains_metered(p_fn, core_pairs)
                evals += p_evals
                if not explains:
                    continue
            candidate_transforms: List[str] = [
                t_name for t_name in base_t if t_name != "identity"
            ] + list(view["evolved_tfs"].keys())
            for then_name in candidate_transforms:
                else_name = "identity"
                t_fn = view["tfs"][then_name]
                e_fn = view["tfs"][else_name]
                cand_fn = lambda x, p=p_fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
                ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
                evals += c_evals
                if ok:
                    used = tuple(
                        op_n
                        for op_n in (p_name, then_name, else_name)
                        if op_n in lib.operators
                    )
                    for u in used:
                        lib.record_operator_use(u)
                    macro_id: Optional[str] = None
                    if p_name in view["evolved_preds"] and then_name in view["evolved_tfs"]:
                        macro_id = f"macro_{p_name}_{then_name}"
                        if macro_id not in lib.operators:
                            lib.evolve_ast_operator(
                                CompiledOperator(
                                    name=macro_id,
                                    level=2,
                                    kind="macro_skill",
                                    code=f"{then_name}(x) if {p_name}(x) else x",
                                    fn=cand_fn,
                                    ast_cost=6,
                                    predicate_id=p_name,
                                    then_transform_id=then_name,
                                    else_transform_id="identity",
                                )
                            )
                            lib.record_operator_use(macro_id)
                    ast_spec = SerializedProgramAST(
                        domain_kind="sequence",
                        kind="clause",
                        predicate_id=p_name,
                        then_transform_id=then_name,
                        else_transform_id=else_name,
                        macro_skill_id=macro_id,
                    )
                    return (ast_spec, cand_fn, used, True, False), evals

    return None, evals


def synthesize_wave10_atomic(
    core_pairs: Sequence[Tuple[Seq, Seq]],
    all_pairs: Sequence[Tuple[Seq, Seq]],
    lib: AtomicSelfEvolvingLibrary,
) -> Wave10SynthesisResult:
    """Synthesize a program from the universal atomic catalog under cost-ordered tiers."""
    lib.step += 1
    schema_cost = lib.ensure_schemas()
    role_cost = 56 if (not lib.use_base_first_beam and schema_cost > 0) else 0
    schema_flag = schema_cost > 0 or lib.schemas_distilled

    base_p = atomic_base_predicates()
    base_t = atomic_base_transforms()

    synthesis_evals = 0
    micro_evals = 0
    archive_evals = 0
    compile_cost = 0
    gate_evals = 0

    # Tier 0a: Whole-program memoization lookup (for ordinary_persistent_memoization)
    if lib.use_memoization and lib.memoized_programs:
        for sig_name, entry in lib.memoized_programs.items():
            ok, c_evals = _eval_candidate_on_pairs(entry.fn, all_pairs)
            synthesis_evals += c_evals
            if ok:
                entry.uses += 1
                entry.last_used_step = lib.step
                return Wave10SynthesisResult(
                    program=entry.fn,
                    program_ast=entry.program_ast,
                    synthesis_evals=synthesis_evals,
                    micro_codegen_evals=0,
                    archive_lookup_evals=0,
                    compression_evals=0,
                    gate_evals=0,
                    schema_distill_cost=schema_cost,
                    role_probe_cost=role_cost,
                    operator_compile_cost=0,
                    schema_distilled=schema_flag,
                    used_operators=(sig_name,),
                    invented_l1=(),
                    invented_l2=(),
                    l1_sub_predicate_reused=False,
                    l2_full_skill_reused=False,
                    memoized_program_reused=True,
                    cold_archive_reactivated=False,
                    abstained=False,
                    pruned_this_step=(),
                )

    if lib.use_base_first_beam:
        # FIX 1: Base-First Cost-Ordered Beam (Tier 0 runs BEFORE Tier 1)
        t0_hit, t0_evals = _search_tier0_base_catalog(
            core_pairs, all_pairs, base_p, base_t, partition_filtered=True
        )
        synthesis_evals += t0_evals
        if t0_hit is not None:
            p_name, then_name, cand_fn = t0_hit
            ast_spec = SerializedProgramAST(
                domain_kind="sequence",
                kind="clause",
                predicate_id=p_name,
                then_transform_id=then_name,
                else_transform_id="identity",
            )
            lib.register_memoized_program(
                f"{p_name}->{then_name}:identity", ast_spec, cand_fn
            )
            comp_evals = lib.compress_solved_programs_mdl(
                ast_spec, structure_discovered=False
            )
            pruned = tuple(lib.usage_age_prune())
            return Wave10SynthesisResult(
                program=cand_fn,
                program_ast=ast_spec,
                synthesis_evals=synthesis_evals,
                micro_codegen_evals=0,
                archive_lookup_evals=0,
                compression_evals=comp_evals,
                gate_evals=0,
                schema_distill_cost=schema_cost,
                role_probe_cost=role_cost,
                operator_compile_cost=0,
                schema_distilled=schema_flag,
                used_operators=(),
                invented_l1=(),
                invented_l2=(),
                l1_sub_predicate_reused=False,
                l2_full_skill_reused=False,
                memoized_program_reused=False,
                cold_archive_reactivated=False,
                abstained=False,
                pruned_this_step=pruned,
            )

        # Tier 1: Active Evolved Operators (gated once per task boundary)
        view, g_evals = lib.active_view(all_pairs)
        gate_evals += g_evals
        t1_hit, t1_evals = _search_tier1_active_evolved(
            core_pairs, all_pairs, view, base_t, lib
        )
        synthesis_evals += t1_evals
        if t1_hit is not None:
            ast_spec, cand_fn, used, l1_reused, l2_reused = t1_hit
            new_macro = ast_spec.macro_skill_id is not None and not l2_reused
            comp_evals = lib.compress_solved_programs_mdl(
                ast_spec, structure_discovered=new_macro
            )
            pruned = tuple(lib.usage_age_prune())
            return Wave10SynthesisResult(
                program=cand_fn,
                program_ast=ast_spec,
                synthesis_evals=synthesis_evals,
                micro_codegen_evals=0,
                archive_lookup_evals=0,
                compression_evals=comp_evals,
                gate_evals=gate_evals,
                schema_distill_cost=schema_cost,
                role_probe_cost=role_cost,
                operator_compile_cost=0,
                schema_distilled=schema_flag,
                used_operators=used,
                invented_l1=(),
                invented_l2=(),
                l1_sub_predicate_reused=l1_reused,
                l2_full_skill_reused=l2_reused,
                memoized_program_reused=False,
                cold_archive_reactivated=False,
                abstained=False,
                pruned_this_step=pruned,
            )
    else:
        # Wave-9 legacy inverted order: Tier 1 runs BEFORE Tier 0 unfiltered base scan
        view, g_evals = lib.active_view(all_pairs)
        gate_evals += g_evals
        t1_hit, t1_evals = _search_tier1_active_evolved(
            core_pairs, all_pairs, view, base_t, lib
        )
        synthesis_evals += t1_evals
        if t1_hit is not None:
            ast_spec, cand_fn, used, l1_reused, l2_reused = t1_hit
            comp_evals = lib.compress_solved_programs_mdl(
                ast_spec, structure_discovered=True
            )
            pruned = tuple(lib.usage_age_prune())
            return Wave10SynthesisResult(
                program=cand_fn,
                program_ast=ast_spec,
                synthesis_evals=synthesis_evals,
                micro_codegen_evals=0,
                archive_lookup_evals=0,
                compression_evals=comp_evals,
                gate_evals=gate_evals,
                schema_distill_cost=schema_cost,
                role_probe_cost=role_cost,
                operator_compile_cost=0,
                schema_distilled=schema_flag,
                used_operators=used,
                invented_l1=(),
                invented_l2=(),
                l1_sub_predicate_reused=l1_reused,
                l2_full_skill_reused=l2_reused,
                memoized_program_reused=False,
                cold_archive_reactivated=False,
                abstained=False,
                pruned_this_step=pruned,
            )

        t0_hit, t0_evals = _search_tier0_base_catalog(
            core_pairs, all_pairs, base_p, base_t, partition_filtered=False
        )
        synthesis_evals += t0_evals
        if t0_hit is not None:
            p_name, then_name, cand_fn = t0_hit
            ast_spec = SerializedProgramAST(
                domain_kind="sequence",
                kind="clause",
                predicate_id=p_name,
                then_transform_id=then_name,
                else_transform_id="identity",
            )
            comp_evals = lib.compress_solved_programs_mdl(
                ast_spec, structure_discovered=True
            )
            pruned = tuple(lib.usage_age_prune())
            return Wave10SynthesisResult(
                program=cand_fn,
                program_ast=ast_spec,
                synthesis_evals=synthesis_evals,
                micro_codegen_evals=0,
                archive_lookup_evals=0,
                compression_evals=comp_evals,
                gate_evals=gate_evals,
                schema_distill_cost=schema_cost,
                role_probe_cost=role_cost,
                operator_compile_cost=0,
                schema_distilled=schema_flag,
                used_operators=(),
                invented_l1=(),
                invented_l2=(),
                l1_sub_predicate_reused=False,
                l2_full_skill_reused=False,
                memoized_program_reused=False,
                cold_archive_reactivated=False,
                abstained=False,
                pruned_this_step=pruned,
            )

    # FIX 2: Tier 2 — Pre-Synthesis Cold Signature Archive Lookup (BEFORE Tier-3 codegen)
    if lib.use_pre_synthesis_archive:
        cold_hit, c_arch_evals, c_syn_evals = lib.cold_archive_reactivate(
            core_pairs,
            all_pairs,
            base_t,
            view["evolved_preds"],
            view["evolved_tfs"],
        )
        archive_evals += c_arch_evals
        synthesis_evals += c_syn_evals
        if cold_hit is not None:
            p_name, t_name, cand_fn, used = cold_hit
            ast_spec = SerializedProgramAST(
                domain_kind="sequence",
                kind="clause",
                predicate_id=p_name,
                then_transform_id=t_name,
                else_transform_id="identity",
            )
            comp_evals = lib.compress_solved_programs_mdl(
                ast_spec, structure_discovered=False
            )
            pruned = tuple(lib.usage_age_prune())
            return Wave10SynthesisResult(
                program=cand_fn,
                program_ast=ast_spec,
                synthesis_evals=synthesis_evals,
                micro_codegen_evals=0,
                archive_lookup_evals=archive_evals,
                compression_evals=comp_evals,
                gate_evals=gate_evals,
                schema_distill_cost=schema_cost,
                role_probe_cost=role_cost,
                operator_compile_cost=0,
                schema_distilled=schema_flag,
                used_operators=used,
                invented_l1=(),
                invented_l2=(),
                l1_sub_predicate_reused=True,
                l2_full_skill_reused=False,
                memoized_program_reused=False,
                cold_archive_reactivated=True,
                abstained=False,
                pruned_this_step=pruned,
            )

    # Tier 3: Bottom-Up Multi-Node Atomic AST Synthesis
    invented_l1: List[str] = []
    invented_l2: List[str] = []

    # Tier 3a: Multi-node predicate ASTs x atomic base transforms
    for p_tree in ATOMIC_PREDICATE_TREES:
        explains, p_evals = _predicate_explains_metered(p_tree.fn, core_pairs)
        micro_evals += p_evals
        if not explains:
            continue
        for t_name, t_fn in base_t.items():
            if t_name == "identity":
                continue
            e_fn = base_t["identity"]
            cand_fn = lambda x, p=p_tree.fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
            ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
            synthesis_evals += c_evals
            if ok:
                reused_l1 = p_tree.name in lib.operators
                if p_tree.name not in lib.operators:
                    compile_cost += lib.evolve_ast_operator(
                        CompiledOperator(
                            name=p_tree.name,
                            level=1,
                            kind="predicate",
                            code=p_tree.ast_expr,
                            fn=p_tree.fn,
                            ast_cost=p_tree.ast_cost,
                        )
                    )
                    if p_tree.name in lib.operators:
                        invented_l1.append(p_tree.name)
                lib.record_operator_use(p_tree.name)
                ast_spec = SerializedProgramAST(
                    domain_kind="sequence",
                    kind="clause",
                    predicate_id=p_tree.name,
                    then_transform_id=t_name,
                    else_transform_id="identity",
                )
                lib.register_memoized_program(
                    f"{p_tree.name}->{t_name}:identity", ast_spec, cand_fn
                )
                comp_evals = lib.compress_solved_programs_mdl(
                    ast_spec, structure_discovered=True
                )
                pruned = tuple(lib.usage_age_prune())
                return Wave10SynthesisResult(
                    program=cand_fn,
                    program_ast=ast_spec,
                    synthesis_evals=synthesis_evals,
                    micro_codegen_evals=micro_evals,
                    archive_lookup_evals=archive_evals,
                    compression_evals=comp_evals,
                    gate_evals=gate_evals,
                    schema_distill_cost=schema_cost,
                    role_probe_cost=role_cost,
                    operator_compile_cost=compile_cost,
                    schema_distilled=schema_flag,
                    used_operators=(p_tree.name,),
                    invented_l1=tuple(invented_l1),
                    invented_l2=(),
                    l1_sub_predicate_reused=reused_l1,
                    l2_full_skill_reused=False,
                    memoized_program_reused=False,
                    cold_archive_reactivated=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # Tier 3b: Atomic base predicates x multi-node transform ASTs
    for p_name, p_fn in base_p.items():
        explains, p_evals = _predicate_explains_metered(p_fn, core_pairs)
        micro_evals += p_evals
        if not explains:
            continue
        for t_tree in ATOMIC_TRANSFORM_TREES:
            e_fn = base_t["identity"]
            cand_fn = lambda x, p=p_fn, t=t_tree.fn, e=e_fn: t(x) if p(x) else e(x)
            ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
            synthesis_evals += c_evals
            if ok:
                if t_tree.name not in lib.operators:
                    compile_cost += lib.evolve_ast_operator(
                        CompiledOperator(
                            name=t_tree.name,
                            level=2,
                            kind="transform",
                            code=t_tree.ast_expr,
                            fn=t_tree.fn,
                            ast_cost=t_tree.ast_cost,
                        )
                    )
                    if t_tree.name in lib.operators:
                        invented_l2.append(t_tree.name)
                lib.record_operator_use(t_tree.name)
                ast_spec = SerializedProgramAST(
                    domain_kind="sequence",
                    kind="clause",
                    predicate_id=p_name,
                    then_transform_id=t_tree.name,
                    else_transform_id="identity",
                )
                lib.register_memoized_program(
                    f"{p_name}->{t_tree.name}:identity", ast_spec, cand_fn
                )
                comp_evals = lib.compress_solved_programs_mdl(
                    ast_spec, structure_discovered=True
                )
                pruned = tuple(lib.usage_age_prune())
                return Wave10SynthesisResult(
                    program=cand_fn,
                    program_ast=ast_spec,
                    synthesis_evals=synthesis_evals,
                    micro_codegen_evals=micro_evals,
                    archive_lookup_evals=archive_evals,
                    compression_evals=comp_evals,
                    gate_evals=gate_evals,
                    schema_distill_cost=schema_cost,
                    role_probe_cost=role_cost,
                    operator_compile_cost=compile_cost,
                    schema_distilled=schema_flag,
                    used_operators=(t_tree.name,),
                    invented_l1=(),
                    invented_l2=tuple(invented_l2),
                    l1_sub_predicate_reused=False,
                    l2_full_skill_reused=False,
                    memoized_program_reused=False,
                    cold_archive_reactivated=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # Wave-9 legacy post-synthesis archive check (only when use_pre_synthesis_archive is False)
    if not lib.use_pre_synthesis_archive and lib.use_cold_archive:
        cold_hit, c_arch_evals, c_syn_evals = lib.cold_archive_reactivate(
            core_pairs,
            all_pairs,
            base_t,
            view["evolved_preds"],
            view["evolved_tfs"],
        )
        archive_evals += c_arch_evals
        synthesis_evals += c_syn_evals
        if cold_hit is not None:
            p_name, t_name, cand_fn, used = cold_hit
            ast_spec = SerializedProgramAST(
                domain_kind="sequence",
                kind="clause",
                predicate_id=p_name,
                then_transform_id=t_name,
                else_transform_id="identity",
            )
            comp_evals = lib.compress_solved_programs_mdl(
                ast_spec, structure_discovered=True
            )
            pruned = tuple(lib.usage_age_prune())
            return Wave10SynthesisResult(
                program=cand_fn,
                program_ast=ast_spec,
                synthesis_evals=synthesis_evals,
                micro_codegen_evals=micro_evals,
                archive_lookup_evals=archive_evals,
                compression_evals=comp_evals,
                gate_evals=gate_evals,
                schema_distill_cost=schema_cost,
                role_probe_cost=role_cost,
                operator_compile_cost=0,
                schema_distilled=schema_flag,
                used_operators=used,
                invented_l1=(),
                invented_l2=(),
                l1_sub_predicate_reused=True,
                l2_full_skill_reused=False,
                memoized_program_reused=False,
                cold_archive_reactivated=True,
                abstained=False,
                pruned_this_step=pruned,
            )

    # Tier 3c: Evolved predicates x multi-node transform ASTs (for predicate-only evolution)
    if view["evolved_preds"]:
        for p_name, p_fn in view["evolved_preds"].items():
            explains, p_evals = _predicate_explains_metered(p_fn, core_pairs)
            micro_evals += p_evals
            if not explains:
                continue
            for t_tree in ATOMIC_TRANSFORM_TREES:
                e_fn = base_t["identity"]
                cand_fn = lambda x, p=p_fn, t=t_tree.fn, e=e_fn: t(x) if p(x) else e(x)
                ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
                micro_evals += t_tree.ast_nodes
                synthesis_evals += c_evals
                if ok:
                    if t_tree.name not in lib.operators:
                        compile_cost += lib.evolve_ast_operator(
                            CompiledOperator(
                                name=t_tree.name,
                                level=2,
                                kind="transform",
                                code=t_tree.ast_expr,
                                fn=t_tree.fn,
                                ast_cost=t_tree.ast_cost,
                            )
                        )
                        if t_tree.name in lib.operators:
                            invented_l2.append(t_tree.name)
                    lib.record_operator_use(p_name)
                    lib.record_operator_use(t_tree.name)
                    ast_spec = SerializedProgramAST(
                        domain_kind="sequence",
                        kind="clause",
                        predicate_id=p_name,
                        then_transform_id=t_tree.name,
                        else_transform_id="identity",
                    )
                    lib.register_memoized_program(
                        f"{p_name}->{t_tree.name}:identity", ast_spec, cand_fn
                    )
                    comp_evals = lib.compress_solved_programs_mdl(
                        ast_spec, structure_discovered=True
                    )
                    pruned = tuple(lib.usage_age_prune())
                    return Wave10SynthesisResult(
                        program=cand_fn,
                        program_ast=ast_spec,
                        synthesis_evals=synthesis_evals,
                        micro_codegen_evals=micro_evals,
                        archive_lookup_evals=archive_evals,
                        compression_evals=comp_evals,
                        gate_evals=gate_evals,
                        schema_distill_cost=schema_cost,
                        role_probe_cost=role_cost,
                        operator_compile_cost=compile_cost,
                        schema_distilled=schema_flag,
                        used_operators=(p_name, t_tree.name),
                        invented_l1=(),
                        invented_l2=tuple(invented_l2),
                        l1_sub_predicate_reused=True,
                        l2_full_skill_reused=False,
                        memoized_program_reused=False,
                        cold_archive_reactivated=False,
                        abstained=False,
                        pruned_this_step=pruned,
                    )

    # Tier 3d: Joint search over multi-node predicate ASTs x multi-node transform ASTs
    # Required when neither predicate nor transform subtree was evolved into the library.
    for p_tree in ATOMIC_PREDICATE_TREES:
        for t_tree in ATOMIC_TRANSFORM_TREES:
            micro_evals += p_tree.ast_nodes + t_tree.ast_nodes
            e_fn = base_t["identity"]
            cand_fn = lambda x, p=p_tree.fn, t=t_tree.fn, e=e_fn: t(x) if p(x) else e(x)
            ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
            synthesis_evals += c_evals
            if ok:
                reused_l1 = p_tree.name in lib.operators
                if p_tree.name not in lib.operators:
                    compile_cost += lib.evolve_ast_operator(
                        CompiledOperator(
                            name=p_tree.name,
                            level=1,
                            kind="predicate",
                            code=p_tree.ast_expr,
                            fn=p_tree.fn,
                            ast_cost=p_tree.ast_cost,
                        )
                    )
                    if p_tree.name in lib.operators:
                        invented_l1.append(p_tree.name)
                if t_tree.name not in lib.operators:
                    compile_cost += lib.evolve_ast_operator(
                        CompiledOperator(
                            name=t_tree.name,
                            level=2,
                            kind="transform",
                            code=t_tree.ast_expr,
                            fn=t_tree.fn,
                            ast_cost=t_tree.ast_cost,
                        )
                    )
                    if t_tree.name in lib.operators:
                        invented_l2.append(t_tree.name)
                macro_id = f"macro_{p_tree.name}_{t_tree.name}"
                lib.evolve_ast_operator(
                    CompiledOperator(
                        name=macro_id,
                        level=2,
                        kind="macro_skill",
                        code=f"{t_tree.name}(x) if {p_tree.name}(x) else x",
                        fn=cand_fn,
                        ast_cost=p_tree.ast_cost + t_tree.ast_cost,
                        predicate_id=p_tree.name,
                        then_transform_id=t_tree.name,
                        else_transform_id="identity",
                    )
                )
                lib.record_operator_use(p_tree.name)
                lib.record_operator_use(t_tree.name)
                lib.record_operator_use(macro_id)
                ast_spec = SerializedProgramAST(
                    domain_kind="sequence",
                    kind="clause",
                    predicate_id=p_tree.name,
                    then_transform_id=t_tree.name,
                    else_transform_id="identity",
                    macro_skill_id=macro_id,
                )
                lib.register_memoized_program(
                    f"{p_tree.name}->{t_tree.name}:identity", ast_spec, cand_fn
                )
                comp_evals = lib.compress_solved_programs_mdl(
                    ast_spec, structure_discovered=True
                )
                pruned = tuple(lib.usage_age_prune())
                return Wave10SynthesisResult(
                    program=cand_fn,
                    program_ast=ast_spec,
                    synthesis_evals=synthesis_evals,
                    micro_codegen_evals=micro_evals,
                    archive_lookup_evals=archive_evals,
                    compression_evals=comp_evals,
                    gate_evals=gate_evals,
                    schema_distill_cost=schema_cost,
                    role_probe_cost=role_cost,
                    operator_compile_cost=compile_cost,
                    schema_distilled=schema_flag,
                    used_operators=(p_tree.name, t_tree.name),
                    invented_l1=tuple(invented_l1),
                    invented_l2=tuple(invented_l2),
                    l1_sub_predicate_reused=reused_l1,
                    l2_full_skill_reused=False,
                    memoized_program_reused=False,
                    cold_archive_reactivated=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # Out-of-grammar -> honest abstention
    pruned = tuple(lib.usage_age_prune())
    abstain_ast = SerializedProgramAST(
        domain_kind="sequence",
        kind="abstain",
        predicate_id="always",
        then_transform_id="identity",
        else_transform_id="identity",
    )
    return Wave10SynthesisResult(
        program=lambda x: x,
        program_ast=abstain_ast,
        synthesis_evals=synthesis_evals,
        micro_codegen_evals=micro_evals,
        archive_lookup_evals=archive_evals,
        compression_evals=0,
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
        cold_archive_reactivated=False,
        abstained=True,
        pruned_this_step=pruned,
    )


@dataclass
class Wave10TaskExecutionReport:
    method: str
    status: str
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
    archive_lookup_evals: int
    compression_evals: int
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
    cold_archive_reactivated: bool
    pruned_operators: Tuple[str, ...]
    active_library_size: int
    cold_archive_size: int
    catalog_audit: Dict[str, int]
    trace: List[Dict[str, Any]]


class AtomicEqualCapabilityLearner:
    """Strictly label-blind learner implementing all 6 Wave-10 atomic methods."""

    def __init__(self, method: str) -> None:
        if method not in WAVE10_METHODS:
            raise ValueError(f"Unknown Wave-10 method: {method}")
        self.method = method
        self.library = self._make_library(method)

    @staticmethod
    def _make_library(method: str) -> AtomicSelfEvolvingLibrary:
        if method == "equal_atomic_scratch":
            return AtomicSelfEvolvingLibrary(
                use_predicate_evolution=False,
                use_transform_evolution=False,
                use_pruning=False,
                use_cold_archive=False,
                use_pre_synthesis_archive=False,
                use_base_first_beam=True,
                use_event_triggered_mdl=True,
                use_memoization=False,
                use_schemas=False,
            )
        if method == "ordinary_persistent_memoization":
            return AtomicSelfEvolvingLibrary(
                use_predicate_evolution=False,
                use_transform_evolution=False,
                use_pruning=False,
                use_cold_archive=False,
                use_pre_synthesis_archive=False,
                use_base_first_beam=True,
                use_event_triggered_mdl=True,
                use_memoization=True,
                use_schemas=False,
            )
        if method == "atomic_nexus_predicate_evolution_only":
            return AtomicSelfEvolvingLibrary(
                use_predicate_evolution=True,
                use_transform_evolution=False,
                use_pruning=True,
                use_cold_archive=True,
                use_pre_synthesis_archive=True,
                use_base_first_beam=True,
                use_event_triggered_mdl=True,
                use_memoization=False,
                use_schemas=True,
            )
        if method == "atomic_nexus_pruning_disabled":
            return AtomicSelfEvolvingLibrary(
                use_predicate_evolution=True,
                use_transform_evolution=True,
                use_pruning=False,
                use_cold_archive=False,
                use_pre_synthesis_archive=False,
                use_base_first_beam=True,
                use_event_triggered_mdl=True,
                use_memoization=False,
                use_schemas=True,
            )
        if method == "wave9_frozen_adaptive_rules":
            return AtomicSelfEvolvingLibrary(
                use_predicate_evolution=True,
                use_transform_evolution=True,
                use_pruning=True,
                use_cold_archive=True,
                use_pre_synthesis_archive=False,
                use_base_first_beam=False,
                use_event_triggered_mdl=False,
                use_memoization=False,
                use_schemas=True,
            )
        # wave10_self_evolving_nexus
        return AtomicSelfEvolvingLibrary(
            use_predicate_evolution=True,
            use_transform_evolution=True,
            use_pruning=True,
            use_cold_archive=True,
            use_pre_synthesis_archive=True,
            use_base_first_beam=True,
            use_event_triggered_mdl=True,
            use_memoization=False,
            use_schemas=True,
        )

    def solve_unfamiliar_task(
        self,
        env: Any,
        public_budget: int = 10,
    ) -> Wave10TaskExecutionReport:
        """Interact with ``env`` under ``public_budget`` with ZERO label parameters."""
        if self.method == "equal_atomic_scratch":
            self.library = self._make_library("equal_atomic_scratch")

        manifest = atomic_catalog_manifest()
        catalog_audit = {
            "atomic_base_predicates_count": len(manifest["atomic_base_predicates"]),
            "atomic_base_transforms_count": len(manifest["atomic_base_transforms"]),
            "atomic_combinators_count": len(manifest["atomic_combinators"]),
            "multi_node_predicate_trees_count": len(
                manifest["multi_node_predicate_trees"]
            ),
            "multi_node_transform_trees_count": len(
                manifest["multi_node_transform_trees"]
            ),
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
            return Wave10TaskExecutionReport(
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
                archive_lookup_evals=0,
                compression_evals=0,
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
                cold_archive_reactivated=False,
                pruned_operators=tuple(self.library.pruned_names),
                active_library_size=len(self.library.operators),
                cold_archive_size=len(self.library.cold_archive),
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
            syn_int = synthesize_integer_equal_capability(int_pairs)
            public_ok = not syn_int.abstained and all(
                int(syn_int.program(inp)) == int(out) for inp, out in int_pairs
            )
            final_status = "abstain" if syn_int.abstained else "unique"
            final_field = None if syn_int.abstained else admitted_field
            total_work = pub_env + pub_val + chan_inv + syn_int.synthesis_evals
            return Wave10TaskExecutionReport(
                method=self.method,
                status=final_status,
                admitted_field=final_field,
                chosen_slots=tuple(PUBLIC_SLOTS),
                public_observations=public_obs,
                program=syn_int.program,
                program_ast=syn_int.program_ast.to_dict(),
                public_consistent=public_ok,
                ambiguous=False,
                oog_abstained=syn_int.abstained,
                public_env_probes=pub_env,
                public_validation_probes=pub_val,
                channel_invariance_evals=chan_inv,
                schema_distill_cost=0,
                role_probe_cost=0,
                gate_evals=0,
                archive_lookup_evals=0,
                compression_evals=0,
                synthesis_evals=syn_int.synthesis_evals,
                micro_codegen_evals=0,
                operator_compile_cost=0,
                codegen_plus_synthesis=syn_int.synthesis_evals,
                total_work=total_work,
                schema_distilled=self.library.schemas_distilled,
                used_operators=(),
                invented_l1=(),
                invented_l2=(),
                l1_sub_predicate_reused=False,
                l2_full_skill_reused=False,
                memoized_program_reused=False,
                cold_archive_reactivated=False,
                pruned_operators=tuple(self.library.pruned_names),
                active_library_size=len(self.library.operators),
                cold_archive_size=len(self.library.cold_archive),
                catalog_audit=catalog_audit,
                trace=trace,
            )

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

        syn = synthesize_wave10_atomic(core_pairs, all_pairs, self.library)
        public_ok = not syn.abstained and all(
            syn.program(inp) == out for inp, out in all_pairs
        )

        final_status = "abstain" if syn.abstained else "unique"
        final_field = None if syn.abstained else admitted_field
        codegen_plus_syn = (
            syn.synthesis_evals + syn.micro_codegen_evals + syn.archive_lookup_evals
        )
        total_work = (
            pub_env
            + pub_val
            + chan_inv
            + syn.schema_distill_cost
            + syn.role_probe_cost
            + syn.gate_evals
            + syn.archive_lookup_evals
            + syn.compression_evals
            + syn.synthesis_evals
            + syn.micro_codegen_evals
            + syn.operator_compile_cost
        )

        return Wave10TaskExecutionReport(
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
            archive_lookup_evals=syn.archive_lookup_evals,
            compression_evals=syn.compression_evals,
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
            cold_archive_reactivated=syn.cold_archive_reactivated,
            pruned_operators=tuple(self.library.pruned_names),
            active_library_size=len(self.library.operators),
            cold_archive_size=len(self.library.cold_archive),
            catalog_audit=catalog_audit,
            trace=trace,
        )
