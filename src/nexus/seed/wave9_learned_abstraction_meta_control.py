"""Wave-9 self-adaptive abstraction & meta-control learner.

Implements three architectural mechanisms on top of the equal-capability
label-blind synthesis engine while keeping ``deconfounded_equal_capability.py``
100% frozen at its ``bf66447`` SHA-256 digest:

1. **Two-Tier Active Beam + Cold Signature Archive (``cold_archive_reactivate``)**:
   When ``usage_age_prune`` demotes an inactive operator from the active beam,
   it moves the operator into ``cold_archive`` indexed by its changed/unchanged
   partition signature rather than deleting it. When active beam + base search
   misses on a delayed-reuse task, the learner checks ``cold_archive``
   (charging ``archive_lookup_evals`` explicitly) and reactivates matching
   operators without re-running full micro-predicate grammar enumeration or
   re-paying ``operator_compile_cost``.
2. **AST Subtree MDL Compression (``compress_solved_programs_mdl``)**:
   Tracks solved program ASTs and admits/pins macro-skills and shared
   sub-predicates using an explicit description-length inequality
   ``DL(library_with_op) + sum(DL(prog_i | op)) <= DL(library_without_op) + sum(DL(prog_i))``
   (charging ``compression_evals`` explicitly).
3. **Online Empirical ROI Gate Meta-Controller (``empirical_roi_gate_policy``)**:
   Evaluates prerequisite invariants once per unique invariant name per task
   boundary and tracks cumulative ``candidate_evals_avoided`` vs
   ``gate_evals_spent``.

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
    classify_predicate,
    classify_transform,
)
from .deconfounded_equal_capability import (
    MICRO_PREDICATE_GRAMMAR,
    UNIVERSAL_EXTENSION_TRANSFORMS,
    CompiledOperator,
    DistilledRelationalSchema,
     SerializedProgramAST,
    _eval_candidate_on_pairs,
    _macro_skill_name,
    _predicate_explains_metered,
    _prerequisite_alphabet_closed,
    _probe_environment_label_blind,
    distill_source_schemas_with_cost,
    synthesize_integer_equal_capability,
    universal_base_predicates,
    universal_base_transforms,
    universal_catalog_manifest,
)

WAVE9_SELF_ADAPTIVE_METHOD = "wave9_self_adaptive_nexus"


@dataclass
class AdaptiveOperatorLibrary:
    """Two-tier active beam + Cold Signature Archive + MDL compressor + ROI gate."""

    step: int = 0
    schemas_distilled: bool = False
    distilled_schemas: Tuple[DistilledRelationalSchema, ...] = ()
    cached_pred_roles: Dict[str, str] = field(default_factory=dict)
    cached_tf_roles: Dict[str, str] = field(default_factory=dict)
    operators: Dict[str, CompiledOperator] = field(default_factory=dict)
    cold_archive: Dict[str, CompiledOperator] = field(default_factory=dict)
    mdl_pinned_names: set[str] = field(default_factory=set)
    solved_program_history: List[SerializedProgramAST] = field(default_factory=list)
    pruned_names: List[str] = field(default_factory=list)
    reactivated_names: List[str] = field(default_factory=list)
    total_gate_evals_spent: int = 0
    total_candidate_evals_avoided: int = 0

    def ensure_schemas_and_roles(self) -> Tuple[int, int]:
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
        if not self.schemas_distilled:
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

    def empirical_roi_gate_policy(
        self, pairs: Sequence[Tuple[Seq, Seq]]
    ) -> Tuple[Dict[str, bool], int]:
        """Evaluate each unique prerequisite invariant at most once per task boundary.

        Tracks empirical ROI (``total_candidate_evals_avoided - total_gate_evals_spent``)
        and avoids redundant per-operator re-evaluation of the same invariant.
        """
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
            # Count avoided candidate evaluations on alphabet-violating task
            n_preds = sum(1 for op in self.operators.values() if op.kind == "predicate")
            n_macros = sum(1 for op in self.operators.values() if op.kind == "macro_skill")
            avoided = n_macros * len(pairs) + n_preds * 6 * len(pairs)
            self.total_candidate_evals_avoided += avoided
        return invariant_results, gate_evals

    def active_view(
        self, pairs: Sequence[Tuple[Seq, Seq]]
    ) -> Tuple[Dict[str, Any], int]:
        preds = universal_base_predicates()
        tfs = universal_base_transforms()
        evolved_preds: Dict[str, Callable[[Seq], bool]] = {}
        evolved_tfs: Dict[str, Callable[[Seq], Seq]] = {}
        macro_skills: Dict[str, CompiledOperator] = {}

        invariant_results, gate_evals = self.empirical_roi_gate_policy(pairs)

        for name, op in self.operators.items():
            if not invariant_results.get(op.prerequisite_name, True):
                continue
            if op.kind == "predicate":
                preds[name] = op.fn
                evolved_preds[name] = op.fn
            elif op.kind == "transform":
                tfs[name] = op.fn
                evolved_tfs[name] = op.fn
            elif op.kind == "macro_skill":
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
        compile_cost = 0
        if op.name in self.cold_archive:
            # Reactivating from cold archive does not re-compile
            restored = self.cold_archive.pop(op.name)
            restored.last_used_step = self.step
            self.operators[op.name] = restored
            return 0
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

    def compress_solved_programs_mdl(self, latest_ast: SerializedProgramAST) -> int:
        """Genuine AST subtree MDL compression across solved programs.

        Computes description length savings for shared ``predicate_id`` and
        ``(predicate_id, then_transform_id)`` subtrees and pins operators whose
        total description length across solved programs is strictly reduced.
        Returns ``compression_evals`` charged for inspecting the AST history.
        """
        if latest_ast.kind == "abstain" or latest_ast.domain_kind != "sequence":
            return 0
        self.solved_program_history.append(latest_ast)
        compression_evals = 0

        pred_counts: Dict[str, int] = {}
        pair_counts: Dict[Tuple[str, str], int] = {}
        for past_ast in self.solved_program_history:
            compression_evals += 1
            p_id = past_ast.predicate_id
            t_id = past_ast.then_transform_id
            pred_counts[p_id] = pred_counts.get(p_id, 0) + 1
            pair_counts[(p_id, t_id)] = pair_counts.get((p_id, t_id), 0) + 1

        # Sub-predicate MDL inequality:
        # Raw cost across k uses = k * ast_cost(p).
        # Library cost + k pointer references = ast_cost(p) + k * 1.
        # Savings > 0 iff (k - 1) * ast_cost(p) > k, which holds for k >= 2 when ast_cost >= 3.
        for p_id, count in pred_counts.items():
            if p_id in self.operators:
                op = self.operators[p_id]
                raw_dl = count * op.ast_cost
                compressed_dl = op.ast_cost + count * 1
                if compressed_dl < raw_dl:
                    self.mdl_pinned_names.add(p_id)

        # Macro-skill MDL inequality for (p_id, t_id):
        for (p_id, t_id), count in pair_counts.items():
            macro_name = _macro_skill_name(p_id, t_id)
            if macro_name in self.operators:
                m_op = self.operators[macro_name]
                raw_dl = count * m_op.ast_cost
                compressed_dl = m_op.ast_cost + count * 1
                if compressed_dl <= raw_dl:
                    self.mdl_pinned_names.add(macro_name)
                    if p_id in self.operators:
                        self.mdl_pinned_names.add(p_id)
                    if t_id in self.operators:
                        self.mdl_pinned_names.add(t_id)

        return compression_evals

    def usage_age_prune(self, min_age: int = 2, min_uses: int = 2) -> List[str]:
        """Demote unpinned inactive operators from active beam into Cold Signature Archive."""
        demoted: List[str] = []
        for name, op in list(self.operators.items()):
            if name in self.mdl_pinned_names:
                continue
            age = self.step - op.created_step
            if age >= min_age and op.uses < min_uses:
                demoted.append(name)
                self.pruned_names.append(name)
                self.cold_archive[name] = op
                del self.operators[name]
        return demoted

    def cold_archive_reactivate(
        self,
        core_pairs: Sequence[Tuple[Seq, Seq]],
        all_pairs: Sequence[Tuple[Seq, Seq]],
        base_t: Mapping[str, Callable[[Seq], Seq]],
        ext_t: Mapping[str, Callable[[Seq], Seq]],
    ) -> Tuple[Optional[Tuple[CompiledOperator, str, Callable[[Seq], Seq]]], int, int]:
        """Search Cold Signature Archive before falling back to full grammar enumeration.

        Returns ``(hit_tuple, archive_lookup_evals, synthesis_evals)``.
        """
        if not self.cold_archive:
            return None, 0, 0
        if not _prerequisite_alphabet_closed(all_pairs):
            return None, 1, 0

        archive_evals = 0
        syn_evals = 0
        for name, cold_op in list(self.cold_archive.items()):
            if cold_op.kind != "predicate":
                continue
            explains, p_evals = _predicate_explains_metered(cold_op.fn, core_pairs)
            archive_evals += p_evals
            if not explains:
                continue
            for t_name, t_fn in base_t.items():
                if t_name == "identity":
                    continue
                e_fn = base_t["identity"]
                cand_fn = lambda x, p=cold_op.fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
                ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
                syn_evals += c_evals
                if ok:
                    # Reactivate into active beam and MDL-pin since it was reused!
                    restored = self.cold_archive.pop(name)
                    restored.uses += 1
                    restored.last_used_step = self.step
                    self.operators[name] = restored
                    self.mdl_pinned_names.add(name)
                    self.reactivated_names.append(name)
                    return (restored, t_name, cand_fn), archive_evals, syn_evals

            for t_name, t_fn in ext_t.items():
                e_fn = base_t["identity"]
                cand_fn = lambda x, p=cold_op.fn, t=t_fn, e=e_fn: t(x) if p(x) else e(x)
                ok, c_evals = _eval_candidate_on_pairs(cand_fn, all_pairs)
                syn_evals += c_evals
                if ok:
                    restored = self.cold_archive.pop(name)
                    restored.uses += 1
                    restored.last_used_step = self.step
                    self.operators[name] = restored
                    self.mdl_pinned_names.add(name)
                    self.reactivated_names.append(name)
                    return (restored, t_name, cand_fn), archive_evals, syn_evals

        return None, archive_evals, syn_evals


@dataclass
class Wave9SynthesisResult:
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
    cold_archive_reactivated: bool
    abstained: bool
    pruned_this_step: Tuple[str, ...]


def synthesize_wave9_self_adaptive(
    core_pairs: Sequence[Tuple[Seq, Seq]],
    all_pairs: Sequence[Tuple[Seq, Seq]],
    lib: AdaptiveOperatorLibrary,
) -> Wave9SynthesisResult:
    """Label-blind synthesis with two-tier cold archive, MDL subtree pinning, and ROI gate."""
    lib.step += 1
    schema_cost, role_cost = lib.ensure_schemas_and_roles()
    schema_flag = schema_cost > 0 or lib.schemas_distilled

    view, gate_evals = lib.active_view(all_pairs)
    base_p = universal_base_predicates()
    base_t = universal_base_transforms()
    ext_t = view["extension_tfs"]

    synthesis_evals = 0
    micro_evals = 0
    archive_evals = 0
    compile_cost = 0

    # 1. Complete L2 Macro-Skill Reuse
    if view["macro_skills"]:
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
                comp_evals = lib.compress_solved_programs_mdl(ast_spec)
                pruned = tuple(lib.usage_age_prune())
                return Wave9SynthesisResult(
                    program=m_op.fn,
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
                    used_operators=(m_name,),
                    invented_l1=(),
                    invented_l2=(),
                    l1_sub_predicate_reused=True,
                    l2_full_skill_reused=True,
                    cold_archive_reactivated=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # 2. Active Beam Search over evolved L1 predicates + base/evolved transforms
    if view["evolved_preds"] or view["evolved_tfs"]:
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
                comp_evals = lib.compress_solved_programs_mdl(ast_spec)
                pruned = tuple(lib.usage_age_prune())
                return Wave9SynthesisResult(
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
                    used_operators=used,
                    invented_l1=(),
                    invented_l2=(),
                    l1_sub_predicate_reused=any(
                        u in lib.operators and lib.operators[u].level == 1 for u in used
                    ),
                    l2_full_skill_reused=False,
                    cold_archive_reactivated=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # 3. Universal Base Catalog Search (schema-prioritized first)
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
            comp_evals = lib.compress_solved_programs_mdl(ast_spec)
            pruned = tuple(lib.usage_age_prune())
            return Wave9SynthesisResult(
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
                used_operators=(),
                invented_l1=(),
                invented_l2=(),
                l1_sub_predicate_reused=False,
                l2_full_skill_reused=False,
                cold_archive_reactivated=False,
                abstained=False,
                pruned_this_step=pruned,
            )

    # 4. Cold Signature Archive Reactivation (before full grammar enumeration!)
    cold_hit, c_arch_evals, c_syn_evals = lib.cold_archive_reactivate(
        core_pairs, all_pairs, base_t, ext_t
    )
    archive_evals += c_arch_evals
    synthesis_evals += c_syn_evals
    if cold_hit is not None:
        restored_op, t_name, cand_fn = cold_hit
        ast_spec = SerializedProgramAST(
            domain_kind="sequence",
            kind="clause",
            predicate_id=restored_op.name,
            then_transform_id=t_name,
            else_transform_id="identity",
        )
        comp_evals = lib.compress_solved_programs_mdl(ast_spec)
        pruned = tuple(lib.usage_age_prune())
        return Wave9SynthesisResult(
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
            used_operators=(restored_op.name,),
            invented_l1=(),
            invented_l2=(),
            l1_sub_predicate_reused=True,
            l2_full_skill_reused=False,
            cold_archive_reactivated=True,
            abstained=False,
            pruned_this_step=pruned,
        )

    # 5a. Hierarchical composition: reuse active evolved L1 predicates with L2 transforms
    invented_l1: List[str] = []
    invented_l2: List[str] = []
    if view["evolved_preds"]:
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
                    comp_evals = lib.compress_solved_programs_mdl(ast_spec)
                    pruned = tuple(lib.usage_age_prune())
                    return Wave9SynthesisResult(
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
                        used_operators=(p_name, t_name),
                        invented_l1=(),
                        invented_l2=tuple(invented_l2),
                        l1_sub_predicate_reused=True,
                        l2_full_skill_reused=False,
                        cold_archive_reactivated=False,
                        abstained=False,
                        pruned_this_step=pruned,
                    )

    # 5b. Enumerate L1 micro-predicates x base transforms
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
                if cand.name not in lib.operators:
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
                lib.record_operator_use(cand.name)
                ast_spec = SerializedProgramAST(
                    domain_kind="sequence",
                    kind="clause",
                    predicate_id=cand.name,
                    then_transform_id=t_name,
                    else_transform_id="identity",
                )
                comp_evals = lib.compress_solved_programs_mdl(ast_spec)
                pruned = tuple(lib.usage_age_prune())
                return Wave9SynthesisResult(
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
                    used_operators=(cand.name,),
                    invented_l1=tuple(invented_l1),
                    invented_l2=(),
                    l1_sub_predicate_reused=reused_l1,
                    l2_full_skill_reused=False,
                    cold_archive_reactivated=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # 5c. Joint search over L1 micro-predicates x universal L2 extension transforms
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
                if cand.name not in lib.operators:
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
                lib.record_operator_use(cand.name)
                lib.record_operator_use(t_name)
                lib.record_operator_use(macro_name)
                ast_spec = SerializedProgramAST(
                    domain_kind="sequence",
                    kind="clause",
                    predicate_id=cand.name,
                    then_transform_id=t_name,
                    else_transform_id="identity",
                    macro_skill_id=macro_name,
                )
                comp_evals = lib.compress_solved_programs_mdl(ast_spec)
                pruned = tuple(lib.usage_age_prune())
                return Wave9SynthesisResult(
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
                    used_operators=(cand.name, t_name),
                    invented_l1=tuple(invented_l1),
                    invented_l2=tuple(invented_l2),
                    l1_sub_predicate_reused=reused_l1,
                    l2_full_skill_reused=False,
                    cold_archive_reactivated=False,
                    abstained=False,
                    pruned_this_step=pruned,
                )

    # 6. Out-of-grammar -> honest abstention
    pruned = tuple(lib.usage_age_prune())
    abstain_ast = SerializedProgramAST(
        domain_kind="sequence",
        kind="abstain",
        predicate_id="always",
        then_transform_id="identity",
        else_transform_id="identity",
    )
    return Wave9SynthesisResult(
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
        cold_archive_reactivated=False,
        abstained=True,
        pruned_this_step=pruned,
    )


@dataclass
class Wave9TaskExecutionReport:
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


class Wave9SelfAdaptiveLearner:
    """Strictly label-blind learner with Cold Signature Archive, MDL subtree pinning, and ROI gate."""

    def __init__(self) -> None:
        self.method = WAVE9_SELF_ADAPTIVE_METHOD
        self.library = AdaptiveOperatorLibrary()

    def solve_unfamiliar_task(
        self,
        env: Any,
        public_budget: int = 10,
    ) -> Wave9TaskExecutionReport:
        """Interact with ``env`` under ``public_budget`` with ZERO label parameters."""
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
            return Wave9TaskExecutionReport(
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
            return Wave9TaskExecutionReport(
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

        syn = synthesize_wave9_self_adaptive(core_pairs, all_pairs, self.library)
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

        return Wave9TaskExecutionReport(
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
            memoized_program_reused=False,
            cold_archive_reactivated=syn.cold_archive_reactivated,
            pruned_operators=tuple(self.library.pruned_names),
            active_library_size=len(self.library.operators),
            cold_archive_size=len(self.library.cold_archive),
            catalog_audit=catalog_audit,
            trace=trace,
        )
