"""Wave16 typed search: indexed cold composition and complete unary generation.

Reuses Wave14 AST/library contracts and Wave15 support masks. No historical
module or runtime mutation, task labels, learned token constants or lambdas.
"""
from __future__ import annotations
from . import wave14_piecewise_archive_learner as legacy
from . import wave15_support_gated_piecewise_learner as previous
from .wave14_piecewise_archive_learner import *
from .wave15_support_gated_piecewise_learner import (
    ResidualSupportCache as PriorCache, SupportProbeBank, confirm_program, expanded_key)


def structural_order(node):
    return (node.ast_nodes(), repr(expanded_key(node)), node.canonical_key())


def ordered(nodes):
    unique = {node.canonical_key(): node for node in nodes}
    return sorted(unique.values(), key=structural_order)


def contains_literal(node):
    if isinstance(node, ConstNode):
        return node.out_type in (TypeTag.TOK, TypeTag.SEQ) and bool(node.value)
    if isinstance(node, EvolvedMacroNode):
        return contains_literal(node.body_ast) or any(contains_literal(a) for a in node.args)
    return isinstance(node, PrimOpNode) and any(contains_literal(a) for a in node.args)


def shape(x):
    names = {}
    result = []
    for token in x:
        if token not in names:
            names[token] = str(len(names))
        result.append(names[token])
    return tuple(result)


def reference_panel():
    # Reuse the existing universal panel, with the two minimal equality-pattern
    # witnesses distinguishing palindrome from merely equal endpoints.
    rows = {shape(x) for x in UNIVERSAL_PROBES}
    rows.add(('0','1','0'))
    rows.add(('0','1','2','0'))
    return tuple(sorted(rows, key=panel_order))


def panel_order(x):
    return (len(x), x)


REFERENCE_SEQUENCES = reference_panel()


def delta_domain(node):
    # Conservative abstract length interpretation, including empty clamps.
    if isinstance(node, VarNode):
        return {0}
    if isinstance(node, EvolvedMacroNode):
        if len(node.args)==1 and not isinstance(node.args[0], VarNode):
            return None
        return delta_domain(node.body_ast)
    if isinstance(node, PrimOpNode):
        if node.op_name in ('REVERSE','TAIL','INIT','DROP_LAST'):
            base = delta_domain(node.args[0])
            if base is None:
                return None
            return base if node.op_name=='REVERSE' else base | {v-1 for v in base}
        if node.op_name in ('APPEND_TOK','PREPEND_TOK'):
            arg = node.args[0] if node.op_name=='APPEND_TOK' else node.args[1]
            base = delta_domain(arg)
            return None if base is None else {v+1 for v in base}
    return None


class IndexedMacroLibrary(legacy.TypedMacroLibrary):
    def __post_init__(self):
        self._init_indices()

    def _init_indices(self):
        if hasattr(self,'cold_guard_index'):
            return
        self.cold_guard_index = {}
        self.guard_positive_index = {}
        self.cold_transform_index = {}
        self.cold_by_id = {}
        self.cold_literal_guards = set()
        self.indexed_names = set()
        self.index_profiles = {}
        self.index_counter = OpCounter()
        self.index_work = 0
        self.task_index_lookups = 0

    def begin_task(self):
        self._init_indices()
        self.index_counter.steps = 0
        self.index_work = 0
        self.task_index_lookups = 0
        self.reactivated_names = []
        return super().begin_task()

    def active_view(self,pairs,extra_tokens,gate_counter):
        view,checks = super().active_view(pairs,extra_tokens,gate_counter)
        # Count each actually inspected operator admission, not just the shared
        # prerequisite predicate. Applies equally to pruned/unpruned libraries.
        checks += len(self.operators)
        return view,checks

    def usage_age_prune(self, *args, **kwargs):
        self._init_indices()
        demoted = super().usage_age_prune(*args, **kwargs)
        for name in demoted:
            op = self.cold_archive[name]
            self.cold_by_id[op.macro_node.macro_id] = name
            # Already-compiled signatures survive re-eviction without re-execution.
            if name not in self.index_profiles:
                values = tuple(eval_expr_ast(op.macro_node,x,self.index_counter) for x in REFERENCE_SEQUENCES)
                self.index_work += len(values)
                self.index_profiles[name] = values
            values = self.index_profiles[name]
            if op.kind=='bool_macro':
                signature = tuple(bool(v) for v in values)
                self.cold_guard_index.setdefault(signature,set()).add(name)
                if contains_literal(op.macro_node):
                    self.cold_literal_guards.add(name)
                for x, flag in zip(REFERENCE_SEQUENCES,signature):
                    if flag:
                        self.guard_positive_index.setdefault(x,set()).add(name)
                        self.index_work += 1
            elif op.kind=='seq_macro':
                signature = tuple(as_seq(v) for v in values)
                deltas = delta_domain(op.macro_node)
                buckets = {'*'} if deltas is None else deltas
                for delta in buckets:
                    self.cold_transform_index.setdefault(delta,{}).setdefault(signature,set()).add(name)
                    self.index_work += 1
            self.indexed_names.add(name)
        return demoted

    def lookup(self,pairs):
        self._init_indices()
        strict = [(x,y) for x,y in pairs if x!=y]
        if not strict:
            return [],[]
        x0 = strict[0][0]
        self.task_index_lookups += 1
        # Only token-renaming-invariant guards can use a normalized reference key.
        if shape(x0) in REFERENCE_SEQUENCES:
            names = set(self.guard_positive_index.get(shape(x0),()))
            names.update(self.cold_literal_guards)
        else:
            # Explicit safe fallback; never claim arbitrary-input O(1) discovery.
            names = {name for name,op in self.cold_archive.items() if op.kind=='bool_macro'}
        guards = [self.cold_archive[n].macro_node for n in sorted(names) if n in self.cold_archive]
        wanted = {'*'}
        for x,y in strict:
            delta = len(y)-len(x)
            wanted.update((delta,delta-1,delta+1))
        names = set()
        for delta in sorted(wanted,key=str):
            self.task_index_lookups += 1
            for bucket in self.cold_transform_index.get(delta,{}).values():
                names.update(bucket)
        transforms = [self.cold_archive[n].macro_node for n in sorted(names) if n in self.cold_archive]
        return ordered(guards),ordered(transforms)

    def reactivate_nodes(self,program):
        seen = set()
        def visit(node):
            if isinstance(node,EvolvedMacroNode):
                if node.macro_id not in seen:
                    seen.add(node.macro_id)
                    name = self.cold_by_id.get(node.macro_id)
                    if name in self.cold_archive:
                        legacy._reactivate(self,self.cold_archive[name])
                visit(node.body_ast)
                for arg in node.args:
                    visit(arg)
            elif isinstance(node,PrimOpNode):
                for arg in node.args:
                    visit(arg)
        for branch in program.branches:
            visit(branch.guard)
            visit(branch.transform)


class ResidualSupportCache(PriorCache):
    def __init__(self,pairs,counter):
        super().__init__(pairs,counter)
        self.single_checks = {}
        self.archive_points = {}
        self.cold_ids=set()
        self.archive_counter=OpCounter()
        self.extra_archive_evals=0

    def uses_cold(self,node):
        if isinstance(node,EvolvedMacroNode):
            return node.macro_id in self.cold_ids or self.uses_cold(node.body_ast)
        return isinstance(node,PrimOpNode) and any(self.uses_cold(a) for a in node.args)

    def guard(self,node,pairs):
        if not self.uses_cold(node):
            return super().guard(node,pairs)
        key=(node.canonical_key(),tuple(x for x,y in pairs))
        if key not in self.guards:
            self.guards[key]=tuple(bool(eval_expr_ast(node,x,self.archive_counter)) for x,y in pairs)
            self.extra_archive_evals+=len(pairs)
        return self.guards[key],0

    def incremental(self,node,pairs):
        if self.uses_cold(node):
            values=tuple(as_seq(eval_expr_ast(node,x,self.archive_counter)) for x,y in pairs)
            self.extra_archive_evals+=len(pairs)
            return values,0
        return tuple(as_seq(eval_expr_ast(node,x,self.synth_counter)) for x,y in pairs),len(pairs)

    def cold_first_possible(self,node,tokens,archive_counter):
        # Necessary condition for a one-branch solve. A failed point test only
        # defers this macro; it is fully restored before a piecewise attempt.
        index=max(self.strict,key=self.strict_input_order)
        execution=expanded_key(node)
        if execution in self.execution_outputs:
            return True,0
        x,y=self.initial[index]
        key=(execution,index)
        calls=0
        if key not in self.archive_points:
            self.archive_points[key]=as_seq(eval_expr_ast(node,x,archive_counter))
            calls+=1
        value=self.archive_points[key]
        if value==y:
            return True,calls
        candidates=[value[::-1],value[1:],value[:-1]]
        for token in tokens:
            candidates.extend(((token,)+value,value+(token,)))
        # Each computed outer primitive is executed and charged, even on failure.
        archive_counter.steps+=len(candidates)
        calls+=len(candidates)
        return y in candidates,calls

    def strict_input_order(self,index):
        x,y=self.initial[index]
        return (len(x),x,y,index)

    def single(self,guards,transforms,pairs,bank,probe_counter,default):
        found,evaluations = [],0
        for transform in ordered(transforms):
            outputs,calls = self.transform(transform)
            evaluations += calls
            if not self.strict or any(outputs[i]!=pairs[i][1] for i in self.strict):
                continue
            for guard in ordered(guards):
                key=(transform.canonical_key(),guard.canonical_key(),tuple(pairs))
                if key not in self.single_checks:
                    mask,calls = self.guard(guard,pairs)
                    evaluations += calls
                    self.mask_checks += 1
                    self.single_checks[key] = all((outputs[i] if flag else x)==y
                        for i,(flag,(x,y)) in enumerate(zip(mask,pairs)))
                if self.single_checks[key]:
                    found.append(PiecewiseProgramAST((PiecewiseBranch(guard,transform),),default))
        if not found:
            return None,evaluations,False
        found,calls,ambiguous = legacy._disambiguate_programs(found,bank,probe_counter)
        evaluations += calls
        if ambiguous:
            return None,evaluations,True
        for program in found:
            if confirm_program(program,bank,probe_counter,False):
                return program,evaluations,False
        return None,evaluations,False

    def macro_outputs(self,node,archive_counter=None):
        key = node.canonical_key()
        if key in self.outputs:
            return 0
        execution = expanded_key(node)
        if execution in self.execution_outputs:
            values,steps = self.execution_outputs[execution]
            self.remember(node,values,steps)
            return 0
        if archive_counter is None:
            _values,calls = self.transform(node)
            return calls
        before = archive_counter.steps
        values=[];calls=0
        for index,(x,_y) in enumerate(self.initial):
            point=(execution,index)
            if point in self.archive_points:
                values.append(self.archive_points[point])
            else:
                values.append(as_seq(eval_expr_ast(node,x,archive_counter)))
                calls+=1
        values=tuple(values)
        steps = archive_counter.steps-before
        self.execution_outputs[execution] = (values,steps)
        self.remember(node,values,steps)
        return calls

    def prime_wrappers(self,node,tokens):
        # Exact output reuse: execute each outer opcode on the cached macro output.
        values = self.outputs[node.canonical_key()]
        result = [node]
        for op in UNARY_SEQ_OPS:
            wrapped = PrimOpNode(op,(node,),TypeTag.SEQ)
            if op=='REVERSE':
                outputs = tuple(v[::-1] for v in values)
            elif op=='TAIL':
                outputs = tuple(v[1:] for v in values)
            else:
                outputs = tuple(v[:-1] for v in values)
            result.append(wrapped)
            self._prime(wrapped,outputs)
        for token in tokens:
            c = ConstNode(token,TypeTag.TOK)
            for wrapped,outputs in (
                (PrimOpNode('APPEND_TOK',(node,c),TypeTag.SEQ),tuple(v+(token,) for v in values)),
                (PrimOpNode('PREPEND_TOK',(c,node),TypeTag.SEQ),tuple((token,)+v for v in values))):
                result.append(wrapped)
                self._prime(wrapped,outputs)
        return ordered(result)

    def _prime(self,node,outputs):
        key = node.canonical_key()
        execution = expanded_key(node)
        if key in self.outputs:
            return
        if execution in self.execution_outputs:
            old,steps = self.execution_outputs[execution]
            self.remember(node,old,steps)
            return
        self.synth_counter.steps += len(outputs)
        self.execution_outputs[execution] = (outputs,len(outputs))
        self.remember(node,outputs,len(outputs))
        self.mask_checks += len(outputs)  # charge actual wrapper executions as work


    def piecewise(self, pairs, bank, guards, probe_counter, default):
        covers = self.pre_piecewise()
        if not covers:
            return None, 0
        start = self.synth_counter.steps
        archive_start=self.archive_counter.steps
        archive_calls_start=self.extra_archive_evals
        evaluations = 0
        nodes = {node.canonical_key(): node for node, _rank in self.partial.values()}
        participants = {key for cover in covers for key in cover}
        legacy._drain_remaining_probes(bank, pairs)
        strict = frozenset(i for i, (x, y) in enumerate(pairs) if x != y)
        full_outputs, coverage = {}, {}
        for key in sorted(participants):
            node = nodes[key]
            extra,increment_evals = self.incremental(node,pairs[len(self.initial):])
            evaluations += increment_evals
            self.diagnostics['incremental_transform_evaluations'] += len(extra)
            outputs = self.outputs[key] + extra
            full_outputs[key] = outputs
            coverage[key] = frozenset(i for i in strict if outputs[i] == pairs[i][1])
        full_pairs = self.covering_pairs(coverage, strict, full=True)
        if not full_pairs:
            self.diagnostics['piecewise_evaluations'] = evaluations+self.extra_archive_evals-archive_calls_start
            self.diagnostics['piecewise_primitive_steps'] = self.synth_counter.steps-start+self.archive_counter.steps-archive_start
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
        self.diagnostics['piecewise_evaluations'] = evaluations+self.extra_archive_evals-archive_calls_start
        self.diagnostics['piecewise_primitive_steps'] = self.synth_counter.steps-start+self.archive_counter.steps-archive_start
        return solved, evaluations



class TypedProgramEnumerator(legacy.TypedProgramEnumerator):
    """One identical bounded atomic grammar and canonical order for all methods."""
    def enumerate_tier0_base_guards(self,extracted):
        return ordered(super().enumerate_tier0_base_guards(extracted))
    def enumerate_tier0_base_transforms(self,extracted):
        return ordered(super().enumerate_tier0_base_transforms(extracted))
    def enumerate_tier3_guards(self,extracted):
        return ordered(super().enumerate_tier3_guards(extracted))

    def atomic_candidates(self,extracted,pairs,cache):
        by_size = {1:[VarNode(),ConstNode((),TypeTag.SEQ)]}
        tokens = [ConstNode(t,TypeTag.TOK) for t in extracted.tokens]
        tok_ops = [PrimOpNode('HEAD',(VarNode(),),TypeTag.TOK),PrimOpNode('LAST',(VarNode(),),TypeTag.TOK)]
        seen = set()
        evaluations = 0
        output = []
        for size in range(2,self.max_transform_size+1):
            candidates = []
            for core_size,cores in list(by_size.items()):
                for core in cores:
                    if core_size+1==size:
                        for op in UNARY_SEQ_OPS:
                            candidates.append(PrimOpNode(op,(core,),TypeTag.SEQ))
                    if core_size+2==size:
                        for token in tokens:
                            candidates.extend((PrimOpNode('APPEND_TOK',(core,token),TypeTag.SEQ),
                                               PrimOpNode('PREPEND_TOK',(token,core),TypeTag.SEQ)))
                    if core_size+3==size and size<=5:
                        for token in tok_ops:
                            candidates.extend((PrimOpNode('APPEND_TOK',(core,token),TypeTag.SEQ),
                                               PrimOpNode('PREPEND_TOK',(token,core),TypeTag.SEQ)))
            if size<=5:
                for left_size,left_nodes in by_size.items():
                    right_size=size-left_size-1
                    for left in left_nodes:
                        for right in by_size.get(right_size,()):
                            candidates.append(PrimOpNode('CONCAT',(left,right),TypeTag.SEQ))
            by_size[size] = []
            for node in ordered(candidates):
                if size>=6:
                    # Public, method-independent feasibility of outer wrappers.
                    strict = [(x,y) for x,y in pairs if x!=y]
                    if node.op_name=='APPEND_TOK' and not any(y and y[-1]==node.args[1].value for _,y in strict):
                        continue
                    if node.op_name=='PREPEND_TOK' and not any(y and y[0]==node.args[0].value for _,y in strict):
                        continue
                    if node.op_name in UNARY_SEQ_OPS:
                        core = node.args[0]
                        deltas = delta_domain(core)
                        if deltas is not None and not any(
                                len(y)-len(x) in (deltas if node.op_name=='REVERSE' else deltas|{d-1 for d in deltas})
                                for x,y in strict):
                            continue
                values,calls = cache.transform(node)
                evaluations += calls
                signature = tuple(values)
                if signature not in seen:
                    seen.add(signature)
                    by_size[size].append(node)
                    output.append(node)
        return ordered(output),evaluations

def synthesize_wave16(core_pairs, all_pairs, lib, enumerator, extracted, bank=None):
    lib.begin_task()
    schema_cost = lib.ensure_schemas()
    role_probe = len(UNIVERSAL_PROBES)*3 if lib.use_schemas and lib.schemas_distilled else 0
    synth_c, gate_c, arch_c, probe_c, comp_c = (OpCounter() for _ in range(5))
    synth_evals = gate_evals = archive_evals = 0
    pairs = list(all_pairs)
    cache = ResidualSupportCache(pairs, synth_c)
    cache.archive_counter=arch_c
    default = VarNode()

    def finish(program, flags, used=(), invented=(), compile_cost=0, compression_evals=0):
        diagnostics = dict(cache.diagnostics, bitmask_checks=cache.mask_checks,
            initial_strict_indices=sorted(cache.strict), initial_pairs=[(list(x),list(y)) for x,y in cache.initial],
            evaluated_partial_transforms=[dict(ast=node.to_dict(),coverage=sorted(mask))
                                          for mask,(node,_rank) in cache.partial.items()])
        archive_work = archive_evals + cache.extra_archive_evals + lib.index_work + lib.task_index_lookups
        arch_c.steps += lib.index_counter.steps
        diagnostics.update(index_build_evals=lib.index_work,index_build_primitive_steps=lib.index_counter.steps,
            index_hash_probes=lib.task_index_lookups,archive_public_evals=archive_evals+cache.extra_archive_evals)
        result = legacy._finish(program,lib,synth_evals+cache.mask_checks,archive_work,
            compression_evals,gate_evals,schema_cost,compile_cost,role_probe,
            bank.probe_work if bank else 0,bank.confirmatory_probe_work if bank else 0,
            synth_c,gate_c,arch_c,probe_c,comp_c,tuple(used),tuple(invented),flags)
        result.support_diagnostics = diagnostics
        return result

    def accept(program, cold=False):
        lib.reactivate_nodes(program)
        used, invented, compilation = legacy._promote_solved(lib, program)
        lib.register_memoized_program(program)
        comp_ev, extra = lib.compress_solved_programs_mdl(program,True,comp_c)
        return finish(program,dict(sub_macro_reused=bool(used),subtree_macro_invented=bool(extra),
            cold_archive_reactivated=bool(lib.reactivated_names)),used,tuple(invented)+extra,compilation,comp_ev)

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
    tier1_t = []
    for op in view['seq_macros']:
        synth_evals += cache.macro_outputs(op.macro_node)
        tier1_t.extend(cache.prime_wrappers(op.macro_node,extracted.tokens))
    tier1_g = ordered(tier0_g+[op.macro_node for op in view['bool_macros']])
    hit, ev, ambiguous = cache.single(tier1_g,ordered(tier1_t+tier0_t),pairs,bank,probe_c,default)
    synth_evals += ev
    if ambiguous:
        return finish(PiecewiseProgramAST((),default),dict(ambiguous=True,abstained=True))
    if hit is not None:
        return accept(hit)

    cold_g,cold_nodes = lib.lookup(pairs) if lib.use_cold_archive else ([],[])
    cache.cold_ids.update(node.macro_id for node in cold_g+cold_nodes)
    cold_t = [];deferred_cold=[]
    for node in cold_nodes:
        possible,calls=cache.cold_first_possible(node,extracted.tokens,arch_c)
        archive_evals+=calls
        if not possible:
            deferred_cold.append(node)
            continue
        archive_evals += cache.macro_outputs(node,arch_c)
        cold_t.extend(cache.prime_wrappers(node,extracted.tokens))
    # Guard execution belongs to archive counters, including failed verification.
    for node in cold_g:
        key = (node.canonical_key(),tuple(x for x,_ in pairs))
        if key not in cache.guards:
            cache.guards[key] = tuple(bool(eval_expr_ast(node,x,arch_c)) for x,_ in pairs)
            archive_evals += len(pairs)
    if cold_g or cold_t:
        hit, ev, ambiguous = cache.single(ordered(tier1_g+cold_g),ordered(tier0_t+tier1_t+cold_t),pairs,bank,probe_c,default)
        synth_evals += ev
        if ambiguous:
            return finish(PiecewiseProgramAST((),default),dict(ambiguous=True,abstained=True))
        if hit is not None:
            return accept(hit,cold=True)

    def piecewise_guards():
        nodes = tier0_g+[g for g in enumerator.enumerate_tier3_guards(extracted) if g.ast_nodes()<=4]
        nodes += [op.macro_node for op in view['bool_macros']]
        nodes += cold_g
        return list({node.canonical_key():node for node in nodes}.values())

    # Exhaust the same structural atomic candidates before any piecewise attempt.
    atomic, ev = enumerator.atomic_candidates(extracted,pairs,cache)
    synth_evals += ev
    tier3_g = enumerator.enumerate_tier3_guards(extracted)
    hit, ev, ambiguous = cache.single(ordered(tier0_g+tier3_g),atomic,pairs,bank,probe_c,default)
    synth_evals += ev
    if ambiguous:
        return finish(PiecewiseProgramAST((),default),dict(ambiguous=True,abstained=True))
    if hit is not None:
        return accept(hit)

    # Point rejection cannot remove a different branch's partial evidence.
    for node in deferred_cold:
        archive_evals += cache.macro_outputs(node,arch_c)
        cache.prime_wrappers(node,extracted.tokens)
    hit, ev = cache.piecewise(pairs,bank,piecewise_guards,probe_c,default)
    synth_evals += ev
    if hit is not None:
        return accept(hit,cold=bool(lib.cold_archive))
    return finish(PiecewiseProgramAST((),default),dict(abstained=True))


class TypedEqualCapabilityLearner(legacy.TypedEqualCapabilityLearner):
    """Original label-blind report contract with Wave16 library and enumerator."""
    def __init__(self,method,max_guard_size=6,max_transform_size=7):
        super().__init__(method,max_guard_size,max_transform_size)
        self.enumerator = TypedProgramEnumerator(max_guard_size,max_transform_size,10)

    @staticmethod
    def _make_library(method):
        original = legacy.TypedEqualCapabilityLearner._make_library(method)
        return IndexedMacroLibrary(**vars(original))

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
            syn = synthesize_wave16(
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


