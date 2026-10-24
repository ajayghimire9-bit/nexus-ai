"""Cached residual support gate over the existing typed AST and macro library.

No task identities, reference programs, private rows or static task tokens enter
this learner. Historical Wave-14 implementation and frozen suites stay untouched.
"""
from __future__ import annotations

from . import wave14_piecewise_archive_learner as legacy
from .wave14_piecewise_archive_learner import *


def expanded_key(node, bound=None):
    """Exact beta expansion for output-cache keys; never an AST evaluation."""
    if isinstance(node, VarNode):
        return bound if bound is not None else node.canonical_key()
    if isinstance(node, EvolvedMacroNode):
        argument = expanded_key(node.args[0], bound) if len(node.args) == 1 else bound
        return expanded_key(node.body_ast, argument)
    if isinstance(node, PrimOpNode):
        return (node.op_name, node.out_type.value, tuple(expanded_key(a, bound) for a in node.args))
    return node.canonical_key()


class ResidualSupportCache:
    def __init__(self, pairs, synth_counter):
        self.initial = tuple(pairs)
        self.synth_counter = synth_counter
        self.outputs = {}
        self.execution_outputs = {}
        self.partial = {}
        self.guards = {}
        self.strict = frozenset(i for i, (x, y) in enumerate(pairs) if x != y)
        self.mask_checks = 0
        self.diagnostics = dict(gate1=None, gate2=None, piecewise_evaluations=0,
            piecewise_primitive_steps=0, initial_partial_masks=0, cover_pairs=0,
            incremental_transform_evaluations=0, piecewise_guard_evaluations=0,
            aborted_before_piecewise=False, min_branch_support=MIN_BRANCH_SUPPORT)

    @staticmethod
    def preference(node, primitive_steps):
        return (primitive_steps, not legacy._contains_macro(node), node.ast_nodes(), node.canonical_key())

    def remember(self, node, outputs, primitive_steps):
        key = node.canonical_key()
        self.outputs[key] = tuple(outputs)
        coverage = frozenset(i for i in self.strict if outputs[i] == self.initial[i][1])
        if coverage:
            previous = self.partial.get(coverage)
            rank = self.preference(node, primitive_steps)
            if previous is None or rank < previous[1]:
                self.partial[coverage] = (node, rank)

    def transform(self, node):
        key = node.canonical_key()
        if key in self.outputs:
            return self.outputs[key], 0
        execution_key = expanded_key(node)
        if execution_key in self.execution_outputs:
            values, steps = self.execution_outputs[execution_key]
            self.remember(node, values, steps)
            return values, 0
        before = self.synth_counter.steps
        values = tuple(as_seq(eval_expr_ast(node, x, self.synth_counter)) for x, _ in self.initial)
        steps = self.synth_counter.steps-before
        self.execution_outputs[execution_key] = (values, steps)
        self.remember(node, values, steps)
        return values, len(values)

    def guard(self, node, pairs):
        key = (node.canonical_key(), tuple(x for x, _ in pairs))
        if key in self.guards:
            return self.guards[key], 0
        values = tuple(bool(eval_expr_ast(node, x, self.synth_counter)) for x, _ in pairs)
        self.guards[key] = values
        return values, len(values)

    def single(self, guards, transforms, pairs, bank, probe_counter, default):
        found, evaluations = [], 0
        for transform in transforms:
            outputs, ev = self.transform(transform)
            evaluations += ev
            if not self.strict or any(outputs[i] != pairs[i][1] for i in self.strict):
                continue
            for guard in guards:
                mask, ev = self.guard(guard, pairs)
                evaluations += ev
                self.mask_checks += 1
                if all((outputs[i] if flag else x) == y for i, (flag, (x, y)) in enumerate(zip(mask, pairs))):
                    found.append(PiecewiseProgramAST((PiecewiseBranch(guard, transform),), default))
        if not found:
            return None, evaluations, False
        found, ev, ambiguous = legacy._disambiguate_programs(found, bank, probe_counter)
        evaluations += ev
        if ambiguous:
            return None, evaluations, True
        for program in found:
            if confirm_program(program, bank, probe_counter, require_branches=False):
                return program, evaluations, False
        return None, evaluations, False

    def covering_pairs(self, coverage, strict, full=False):
        out = []
        for first, cov1 in coverage.items():
            if len(cov1) < MIN_BRANCH_SUPPORT:
                continue
            remaining = strict-cov1
            if len(remaining) < (MIN_BRANCH_SUPPORT if full else 1):
                continue
            for second, cov2 in coverage.items():
                self.mask_checks += 1
                if (cov1 | cov2) == strict:
                    out.append((first, second))
        return out

    def pre_piecewise(self):
        self.diagnostics['initial_partial_masks'] = len(self.partial)
        self.diagnostics['gate_coverage_snapshot'] = [sorted(mask) for mask in self.partial]
        first = any(len(mask) >= MIN_BRANCH_SUPPORT for mask in self.partial)
        self.diagnostics['gate1'] = first
        coverage = {node.canonical_key(): mask for mask, (node, _rank) in self.partial.items()}
        covers = self.covering_pairs(coverage, self.strict) if first else []
        self.diagnostics['gate2'] = bool(covers)
        self.diagnostics['cover_pairs'] = len(covers)
        self.diagnostics['aborted_before_piecewise'] = not bool(covers)
        return covers

    def piecewise(self, pairs, bank, guards, probe_counter, default):
        covers = self.pre_piecewise()
        if not covers:
            return None, 0
        start = self.synth_counter.steps
        evaluations = 0
        nodes = {node.canonical_key(): node for node, _rank in self.partial.values()}
        participants = {key for cover in covers for key in cover}
        legacy._drain_remaining_probes(bank, pairs)
        strict = frozenset(i for i, (x, y) in enumerate(pairs) if x != y)
        full_outputs, coverage = {}, {}
        for key in sorted(participants):
            node = nodes[key]
            extra = tuple(as_seq(eval_expr_ast(node, x, self.synth_counter)) for x, _ in pairs[len(self.initial):])
            evaluations += len(extra)
            self.diagnostics['incremental_transform_evaluations'] += len(extra)
            outputs = self.outputs[key] + extra
            full_outputs[key] = outputs
            coverage[key] = frozenset(i for i in strict if outputs[i] == pairs[i][1])
        full_pairs = self.covering_pairs(coverage, strict, full=True)
        if not full_pairs:
            self.diagnostics['piecewise_evaluations'] = evaluations
            self.diagnostics['piecewise_primitive_steps'] = self.synth_counter.steps-start
            return None, evaluations
        # Guard pool is created only after full transform coverage is established.
        pool = guards()
        masks = []
        for node in pool:
            mask, ev = self.guard(node, pairs)
            evaluations += ev
            self.diagnostics['piecewise_guard_evaluations'] += ev
            masks.append((node, frozenset(i for i, flag in enumerate(mask) if flag)))
        all_indices = frozenset(range(len(pairs)))
        solved = None
        for first, second in full_pairs:
            good1 = frozenset(i for i, (_, y) in enumerate(pairs) if full_outputs[first][i] == y)
            good2 = frozenset(i for i, (_, y) in enumerate(pairs) if full_outputs[second][i] == y)
            for g1, mask1 in masks:
                self.mask_checks += 1
                if len(mask1 & strict) < MIN_BRANCH_SUPPORT or not mask1 <= good1:
                    continue
                remaining = all_indices-mask1
                residual = remaining & strict
                if len(residual) < MIN_BRANCH_SUPPORT:
                    continue
                for g2, mask2 in masks:
                    self.mask_checks += 1
                    if mask2 & remaining != residual or not residual <= good2:
                        continue
                    program = PiecewiseProgramAST((PiecewiseBranch(g1, nodes[first]), PiecewiseBranch(g2, nodes[second])), default)
                    if confirm_program(program, bank, probe_counter, require_branches=True):
                        solved = program
                        break
                if solved is not None:
                    break
            if solved is not None:
                break
        self.diagnostics['piecewise_evaluations'] = evaluations
        self.diagnostics['piecewise_primitive_steps'] = self.synth_counter.steps-start
        return solved, evaluations


class SupportProbeBank(PublicProbeBank):
    def __init__(self, env, admitted_field, unread, confirmations):
        super().__init__(env, admitted_field, unread)
        self.confirmation_slots = list(confirmations)
        self.confirmed_pairs = None


def confirm_program(program, bank, counter, require_branches):
    if bank is None:
        return not require_branches
    if isinstance(bank, SupportProbeBank) and bank.confirmation_slots:
        if bank.confirmed_pairs is None:
            bank.confirmed_pairs = []
            for slot in bank.confirmation_slots:
                pair = bank.read_slot(slot, confirmatory=True)
                if pair is not None:
                    bank.confirmed_pairs.append(pair)
        pairs = bank.confirmed_pairs
    else:
        pairs = legacy._collect_confirm_pairs(bank)
    if not pairs and require_branches:
        return False
    branch_seen = set()
    for x, y in pairs:
        if eval_piecewise(program, x, counter) != y:
            return False
        for i, branch in enumerate(program.branches):
            if bool(eval_expr_ast(branch.guard, x, counter)):
                branch_seen.add(i)
                break
    return not require_branches or len(branch_seen) == len(program.branches)


class CoverageAtomicSearch(legacy.TypedProgramEnumeratorSearch):
    def __init__(self, enumerator, cache):
        super().__init__(enumerator)
        self.cache = cache

    # Atomic expansion implementation below is adapted without changing grammar.
    def expand_atomic(
            self,
            extracted: ExtractedConstants,
            all_inputs: Sequence[Seq],
            pairs: Sequence[Tuple[Seq, Seq]],
            synth_c: OpCounter,
        ) -> Tuple[List[ExprAST], int]:
            evals = 0
            x_node = VarNode()
            tok_consts = [ConstNode(token, TypeTag.TOK) for token in extracted.tokens]
            tok_ops = [
                PrimOpNode("HEAD", (x_node,), TypeTag.TOK),
                PrimOpNode("LAST", (x_node,), TypeTag.TOK),
            ]
            seq_by_size: Dict[int, List[ExprAST]] = {1: [x_node, ConstNode((), TypeTag.SEQ)]}
            seen: Dict[Tuple[Seq, ...], ExprAST] = {}
    
            def register(size: int, cands: Sequence[ExprAST]) -> int:
                local = 0
                bucket: List[ExprAST] = list(seq_by_size.get(size, []))
                for cand in cands:
                    if cand.ast_nodes() != size:
                        continue
                    values, ev = self.cache.transform(cand)
                    local += ev
                    sig = tuple(values)
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
                    PrimOpNode("DROP_LAST", (x_node,), TypeTag.SEQ),
                    PrimOpNode("REVERSE", (x_node,), TypeTag.SEQ),
                ],
            )
            cands3: List[ExprAST] = [PrimOpNode("CONCAT", (x_node, x_node), TypeTag.SEQ)]
            for tok in tok_consts:
                cands3.append(PrimOpNode("APPEND_TOK", (x_node, tok), TypeTag.SEQ))
                cands3.append(PrimOpNode("PREPEND_TOK", (tok, x_node), TypeTag.SEQ))
            evals += register(3, cands3)
            for level in range(4, 6):
                cands: List[ExprAST] = []
                for seq_size in range(1, level):
                    for seq_node in seq_by_size.get(seq_size, ()):
                        for tok in tok_consts:
                            if seq_size + 1 + 1 == level:
                                cands.append(PrimOpNode("APPEND_TOK", (seq_node, tok), TypeTag.SEQ))
                                cands.append(PrimOpNode("PREPEND_TOK", (tok, seq_node), TypeTag.SEQ))
                        for tok_op in tok_ops:
                            if seq_size + tok_op.ast_nodes() + 1 == level:
                                cands.append(PrimOpNode("APPEND_TOK", (seq_node, tok_op), TypeTag.SEQ))
                                cands.append(PrimOpNode("PREPEND_TOK", (tok_op, seq_node), TypeTag.SEQ))
                        if seq_size + 1 == level:
                            for unary in UNARY_SEQ_OPS:
                                cands.append(PrimOpNode(unary, (seq_node,), TypeTag.SEQ))
                        if seq_size + 2 == level:
                            cands.append(PrimOpNode("CONCAT", (seq_node, x_node), TypeTag.SEQ))
                            cands.append(PrimOpNode("CONCAT", (x_node, seq_node), TypeTag.SEQ))
                evals += register(level, cands)
            cores: List[ExprAST] = []
            for size in range(1, 6):
                cores.extend(seq_by_size.get(size, ()))
            starts, ends, unary_keep, _keep_len = legacy._observed_wrapper_hints(pairs, extracted)
            wrap_cands: List[ExprAST] = []
            for core in cores:
                if core.ast_nodes() < 4:
                    continue
                if core.ast_nodes() > 5:
                    continue
                for token in starts:
                    wrap_cands.append(
                        PrimOpNode(
                            "PREPEND_TOK",
                            (ConstNode(token, TypeTag.TOK), core),
                            TypeTag.SEQ,
                        )
                    )
                for token in ends:
                    wrap_cands.append(
                        PrimOpNode(
                            "APPEND_TOK",
                            (core, ConstNode(token, TypeTag.TOK)),
                            TypeTag.SEQ,
                        )
                    )
                if unary_keep:
                    for unary in UNARY_SEQ_OPS:
                        wrap_cands.append(PrimOpNode(unary, (core,), TypeTag.SEQ))
            for cand in wrap_cands:
                size = cand.ast_nodes()
                if 6 <= size <= self.enumerator.max_transform_size:
                    evals += register(size, [cand])
            all_seq: List[ExprAST] = []
            for size in sorted(seq_by_size):
                all_seq.extend(seq_by_size[size])
            return all_seq, evals


def synthesize_wave15(core_pairs, all_pairs, lib, enumerator, extracted, bank=None):
    lib.begin_task()
    schema_cost = lib.ensure_schemas()
    role_probe = len(UNIVERSAL_PROBES)*3 if lib.use_schemas and lib.schemas_distilled else 0
    synth_c, gate_c, arch_c, probe_c, comp_c = (OpCounter() for _ in range(5))
    synth_evals = gate_evals = archive_evals = 0
    pairs = list(all_pairs)
    cache = ResidualSupportCache(pairs, synth_c)
    default = VarNode()

    def finish(program, flags, used=(), invented=(), compile_cost=0, compression_evals=0):
        diagnostics = dict(cache.diagnostics, bitmask_checks=cache.mask_checks,
            initial_strict_indices=sorted(cache.strict), initial_pairs=[(list(x),list(y)) for x,y in cache.initial],
            evaluated_partial_transforms=[dict(ast=node.to_dict(),coverage=sorted(mask))
                                          for mask,(node,_rank) in cache.partial.items()])
        result = legacy._finish(program,lib,synth_evals+cache.mask_checks,archive_evals,
            compression_evals,gate_evals,schema_cost,compile_cost,role_probe,
            bank.probe_work if bank else 0,bank.confirmatory_probe_work if bank else 0,
            synth_c,gate_c,arch_c,probe_c,comp_c,tuple(used),tuple(invented),flags)
        result.support_diagnostics = diagnostics
        return result

    def accept(program, cold=False):
        if cold:
            text = str(program.to_dict())
            for name, op in list(lib.cold_archive.items()):
                if op.macro_node.macro_id in text:
                    legacy._reactivate(lib,op)
        used, invented, compilation = legacy._promote_solved(lib, program)
        lib.register_memoized_program(program)
        comp_ev, extra = lib.compress_solved_programs_mdl(program,True,comp_c)
        return finish(program,dict(sub_macro_reused=bool(used),subtree_macro_invented=bool(extra),
            cold_archive_reactivated=cold and bool(lib.reactivated_names)),used,tuple(invented)+extra,compilation,comp_ev)

    if lib.use_memoization:
        for entry in lib.memoized_programs.values():
            ok, ev = legacy._eval_pairs(entry.program,pairs,synth_c)
            synth_evals += ev
            if ok and confirm_program(entry.program,bank,probe_c,False):
                entry.uses += 1
                entry.last_used_step = lib.step
                return finish(entry.program,dict(memoized_program_reused=True),(entry.signature_name,))

    tier0_g = enumerator.enumerate_tier0_base_guards(extracted)
    tier0_t = enumerator.enumerate_tier0_base_transforms(extracted)
    hit, ev, ambiguous = cache.single(tier0_g,tier0_t,pairs,bank,probe_c,default)
    synth_evals += ev
    if ambiguous:
        return finish(PiecewiseProgramAST((),default),dict(ambiguous=True,abstained=True))
    if hit is not None:
        return accept(hit)

    view, gate_evals = lib.active_view(pairs,extracted.tokens,gate_c)
    seq_ops = []
    for op in view['seq_macros']:
        # Coverage, rather than one chosen residual, admits both branch macros.
        wrapper_relevant, gev = legacy._macro_relevance_gate(op,pairs,gate_c)
        gate_evals += gev
        outputs, ev = cache.transform(op.macro_node)
        synth_evals += ev
        gate_evals += 1
        if wrapper_relevant or any(outputs[i] == pairs[i][1] for i in cache.strict):
            seq_ops.append(op)
    tier1_t = legacy._tier1_macro_beam(seq_ops,extracted)
    tier1_g = list(tier0_g)+[op.macro_node for op in view['bool_macros']]
    if tier1_t or view['bool_macros']:
        hit, ev, ambiguous = cache.single(tier1_g,tier1_t+tier0_t,pairs,bank,probe_c,default)
        synth_evals += ev
        if ambiguous:
            return finish(PiecewiseProgramAST((),default),dict(ambiguous=True,abstained=True))
        if hit is not None:
            return accept(hit)

    if lib.use_cold_archive and lib.cold_archive:
        archived = list(lib.cold_archive.values())
        archive_evals += len(archived)
        cold_g = [op.macro_node for op in archived if op.kind=='bool_macro']
        cold_t = [op.macro_node for op in archived if op.kind=='seq_macro']
        affixes = []
        for token in extracted.tokens:
            tok = ConstNode(token,TypeTag.TOK)
            affixes.extend((PrimOpNode('APPEND_TOK',(default,tok),TypeTag.SEQ),
                            PrimOpNode('PREPEND_TOK',(tok,default),TypeTag.SEQ)))
        hit, ev, ambiguous = cache.single(tier1_g+cold_g,tier0_t+tier1_t+cold_t+affixes,pairs,bank,probe_c,default)
        synth_evals += ev
        if ambiguous:
            return finish(PiecewiseProgramAST((),default),dict(ambiguous=True,abstained=True))
        if hit is not None:
            return accept(hit,cold=True)

    def piecewise_guards():
        nodes = tier0_g+[g for g in enumerator.enumerate_tier3_guards(extracted) if g.ast_nodes()<=4]
        nodes += [op.macro_node for op in view['bool_macros']]
        if lib.use_cold_archive:
            nodes += [op.macro_node for op in lib.cold_archive.values() if op.kind=='bool_macro']
        return list({node.canonical_key():node for node in nodes}.values())

    # Tier-3 first tries its guards against transforms already evaluated. A
    # complete cached branch certificate need not force atomic rediscovery of
    # existing macros. The same lazy rule applies to every method.
    tier3_g = enumerator.enumerate_tier3_guards(extracted)
    hit, ev, ambiguous = cache.single(tier0_g+tier3_g,tier0_t+tier1_t,pairs,bank,probe_c,default)
    synth_evals += ev
    if ambiguous:
        return finish(PiecewiseProgramAST((),default),dict(ambiguous=True,abstained=True))
    if hit is not None:
        return accept(hit)
    if cache.pre_piecewise():
        hit, ev = cache.piecewise(pairs,bank,piecewise_guards,probe_c,default)
        synth_evals += ev
        if hit is not None:
            return accept(hit,cold=bool(lib.cold_archive))
        return finish(PiecewiseProgramAST((),default),dict(abstained=True))

    # No probe drain before the support gate. Every atomic candidate evaluated
    # during signature enumeration contributes to the same coverage cache.
    search = CoverageAtomicSearch(enumerator,cache)
    atomic, ev = search.expand_atomic(extracted,[x for x,_ in pairs],pairs,synth_c)
    synth_evals += ev
    tier3_g = enumerator.enumerate_tier3_guards(extracted)
    hit, ev, ambiguous = cache.single(tier0_g+tier3_g,atomic,pairs,bank,probe_c,default)
    synth_evals += ev
    if ambiguous:
        return finish(PiecewiseProgramAST((),default),dict(ambiguous=True,abstained=True))
    if hit is not None:
        return accept(hit)

    hit, ev = cache.piecewise(pairs,bank,piecewise_guards,probe_c,default)
    synth_evals += ev
    if hit is not None:
        return accept(hit,cold=bool(lib.cold_archive))
    return finish(PiecewiseProgramAST((),default),dict(abstained=True))


class TypedEqualCapabilityLearner(legacy.TypedEqualCapabilityLearner):
    """Same library ownership, typed grammar and report contract as Wave 14."""
    def solve_unfamiliar_task(self, env: Any, public_budget: int) -> Wave14TaskExecutionReport:
            self.last_diagnostics = dict(piecewise_evaluations=0,piecewise_primitive_steps=0)
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
            probed = legacy._probe_environment_label_blind(env, public_budget)
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
            all_slots = extra_public_slot_names(env)
            confirmations = [s for s in all_slots if s.startswith('confirm_')]
            extras = [s for s in all_slots if s not in confirmations]
            synth_slots = extras[:EXTRA_SYNTH_CAP]
            hold_slots = extras[EXTRA_SYNTH_CAP:]
            bank = SupportProbeBank(env, str(admitted_field), list(hold_slots), confirmations)
            for slot in synth_slots:
                pair = bank.read_slot(slot, confirmatory=False)
                if pair is None:
                    continue
                all_pairs.append(pair)
                public_obs.append(bank.observations[-1])
                trace.append({"phase": "public", "kind": "extra_synth", "slot": slot, "before_lock": True})
            extracted = extract_task_constants(public_obs)
            syn = synthesize_wave15(
                core_pairs, all_pairs, self.library, self.enumerator, extracted, bank
            )
            self.last_diagnostics = syn.support_diagnostics
            trace.append(dict(phase='support_gate', **self.last_diagnostics))
            public_obs.extend(
                [
                    row
                    for row in bank.observations
                    if row not in public_obs
                ]
            )
            verify_c = OpCounter()
            public_ok = (
                (not syn.abstained)
                and (not syn.ambiguous)
                and all(
                    execute_wave14_program_ast(syn.program_ast_dict, src, verify_c) == dst
                    for src, dst in all_pairs
                )
            )
            probe_work = pub_env + pub_val + chan + syn.extra_probe_work
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
                + syn.probe_primitive_op_steps
                + syn.compression_primitive_op_steps
            )
            if syn.ambiguous:
                out_status = "ambiguous"
            elif syn.abstained:
                out_status = "abstain"
            else:
                out_status = "unique"
            return Wave14TaskExecutionReport(
                method=self.method,
                status=out_status,
                admitted_field=None if out_status != "unique" else admitted_field,
                chosen_slots=tuple(PUBLIC_SLOTS),
                public_observations=public_obs,
                program_ast=syn.program_ast_dict,
                public_consistent=public_ok,
                ambiguous=syn.ambiguous or out_status == "ambiguous",
                oog_abstained=out_status == "abstain",
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
                probe_primitive_op_steps=syn.probe_primitive_op_steps,
                compression_primitive_op_steps=syn.compression_primitive_op_steps,
                total_primitive_op_steps=primitive_total,
                confirmatory_probe_work=syn.confirmatory_probe_work,
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
                max_hierarchy_depth=syn.max_hierarchy_depth,
                final_verify_primitive_op_steps=verify_c.steps,
            )
