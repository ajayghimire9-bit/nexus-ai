"""Source-only curricula and independent bounded-expression witnesses."""
import ast
import copy
import runpy
from pathlib import Path

import pytest
from nexus.seed.wave16_peeled_archive_unary_learner import (
    TypedEqualCapabilityLearner,TypedProgramEnumerator,IndexedMacroLibrary,
    ResidualSupportCache,OpCounter,PrimOpNode,VarNode,TypeTag,ConstNode,
    execute_wave14_program_ast,eval_expr_ast,extract_task_constants,structural_order,
    UNARY_SEQ_OPS,expanded_key,REFERENCE_SEQUENCES)

ROOT=Path(__file__).resolve().parents[1]
SOURCE=runpy.run_path(str(ROOT/'tests/test_seed_wave15_support_gated.py'))
SourceEnv=SOURCE['SourceEnv']


def two_init(x):
    return x[:-2] if len(x)%2==0 else x


def source_cases():
    cases=SOURCE['source_cases']()
    cases[13]=('source_two_init',two_init,'archive',False,'unique')
    return cases


def check_private(report,env):
    env.lock()
    if report.status=='unique':
        for slot in env.private_map:
            obs=env.private_read(slot)
            assert execute_wave14_program_ast(report.program_ast,obs['payload'])==obs['result']


def test_static_and_historical_freezes():
    tree=ast.parse((ROOT/'src/nexus/seed/wave16_peeled_archive_unary_learner.py').read_text())
    assert not any(isinstance(n,ast.Lambda) for n in ast.walk(tree))
    forbidden={'task_id','family','split','mechanism','private_map','_private_pairs'}
    assert not any(isinstance(n,ast.Attribute) and n.attr in forbidden for n in ast.walk(tree))
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='solve_unfamiliar_task')
    assert [a.arg for a in method.args.args]==['self','env','public_budget']


def test_atomic_size_three_unary_witness_and_structural_order():
    pairs=[(('a','b','c','d'),('a','b')), (('b','c','d'),('b',))]
    cache=ResidualSupportCache(pairs,OpCounter())
    ex=extract_task_constants([dict(input=list(x),observed_output=list(y)) for x,y in pairs])
    nodes,_=TypedProgramEnumerator().atomic_candidates(ex,pairs,cache)
    assert nodes==sorted(nodes,key=structural_order)
    # Independent semantic witness: double projection really is reachable at size3.
    witness=PrimOpNode('INIT',(PrimOpNode('INIT',(VarNode(),),TypeTag.SEQ),),TypeTag.SEQ)
    expected=tuple(eval_expr_ast(witness,x) for x,y in pairs)
    assert any(n.ast_nodes()==3 and tuple(eval_expr_ast(n,x) for x,y in pairs)==expected for n in nodes)


@pytest.mark.parametrize('wrapper',['bare','REVERSE','TAIL','DROP_LAST','APPEND_TOK','PREPEND_TOK'])
def test_evicted_macro_one_step_reachability_and_exact_outputs(wrapper):
    lib=IndexedMacroLibrary();lib._init_indices()
    x=VarNode()
    core=PrimOpNode('PREPEND_TOK',(PrimOpNode('LAST',(x,),TypeTag.TOK),PrimOpNode('INIT',(x,),TypeTag.SEQ)),TypeTag.SEQ)
    op,_=lib.promote_ast_subtree(core,'seq_macro')
    # Three no-use episode boundaries; no repeated promotion or secret label.
    for _ in range(3):lib.begin_task()
    assert op.name in lib.cold_archive
    if wrapper=='bare':node=op.macro_node
    elif wrapper=='APPEND_TOK':node=PrimOpNode(wrapper,(op.macro_node,ConstNode('new',TypeTag.TOK)),TypeTag.SEQ)
    elif wrapper=='PREPEND_TOK':node=PrimOpNode(wrapper,(ConstNode('new',TypeTag.TOK),op.macro_node),TypeTag.SEQ)
    else:node=PrimOpNode(wrapper,(op.macro_node,),TypeTag.SEQ)
    inputs=[('a','b','c','d'),('d','c','a'),('c','d')]
    pairs=[(v,eval_expr_ast(node,v)) for v in inputs]
    _g,transforms=lib.lookup(pairs)
    assert op.macro_node in transforms
    archive=OpCounter();cache=ResidualSupportCache(pairs,OpCounter())
    calls=cache.macro_outputs(op.macro_node,archive)
    assert calls==len(pairs) and archive.steps>0
    options=cache.prime_wrappers(op.macro_node,['new'])
    assert node in options
    assert cache.outputs[node.canonical_key()]==tuple(y for _,y in pairs)
    from nexus.seed.wave16_peeled_archive_unary_learner import PiecewiseProgramAST,PiecewiseBranch
    guard=TypedProgramEnumerator().enumerate_tier0_base_guards(extract_task_constants([]))[0]
    lib.reactivate_nodes(PiecewiseProgramAST((PiecewiseBranch(guard,node),),VarNode()))
    assert op.name in lib.operators and op.name not in lib.cold_archive


def test_guard_index_verifies_current_rows_not_reference_alias():
    lib=IndexedMacroLibrary();lib._init_indices();x=VarNode()
    guard=PrimOpNode('SEQ_EQ',(x,PrimOpNode('REVERSE',(x,),TypeTag.SEQ)),TypeTag.BOOL)
    op,_=lib.promote_ast_subtree(guard,'bool_macro')
    for _ in range(3):lib.begin_task()
    assert lib.cold_guard_index
    g,_=lib.lookup([(('z','q','z'),('new',)),(('z','q'),('z','q'))])
    assert op.macro_node in g
    assert eval_expr_ast(g[0],('z','q','z')) and not eval_expr_ast(g[0],('z','q'))
    assert lib.task_index_lookups>0


def delayed_curriculum(kind):
    def left(x):return x[1:]+x[:1]
    def intro(x):return left(x) if len(x)%2==0 else x
    def delayed(x):
        if kind=='guard':return ('^',)+x if x==x[::-1] else x
        if len(x)%2:return x
        value=left(x)
        if kind=='REVERSE':return value[::-1]
        if kind=='TAIL':return value[1:]
        return value+('fresh_source',)
    scores={}
    for method in ('nexus_typed_full','nexus_typed_without_pruning'):
        learner=TypedEqualCapabilityLearner(method)
        history=[]
        curriculum=[(intro,False),(SOURCE['palindrome_first'],True),
                    (SOURCE['even_reverse'],False),(SOURCE['odd_reverse'],False),(SOURCE['even_tail'],False)]
        for fn,pal in curriculum:
            env=SourceEnv(fn,pal=pal)
            report=learner.solve_unfamiliar_task(env,10)
            history.append(report)
            assert report.status=='unique'
            check_private(report,env)
        env=SourceEnv(delayed,pal=kind=='guard')
        report=learner.solve_unfamiliar_task(env,10)
        assert report.status=='unique', (kind,method,report.status)
        check_private(report,env)
        if method=='nexus_typed_full':assert report.cold_archive_reactivated
        report.source_curriculum_totals={metric:sum(getattr(r,metric) for r in history+[report])
            for metric in ('gate_evals','synthesis_evals','total_work','total_primitive_op_steps')}
        scores[method]=report
    return scores


def test_curriculum_pruning_invariant_delayed_solves_and_lower_cost():
    # All four required delayed categories, equal weight. Costs are aggregated
    # across this complete block; individual-task savings are not guaranteed.
    blocks=[delayed_curriculum(kind) for kind in ('guard','REVERSE','TAIL','APPEND_TOK')]
    for metric in ('gate_evals','synthesis_evals','total_work','total_primitive_op_steps'):
        full=sum(getattr(b['nexus_typed_full'],metric) for b in blocks)
        retained=sum(getattr(b['nexus_typed_without_pruning'],metric) for b in blocks)
        assert full<retained,(metric,full,retained)
        full_with_build=sum(b['nexus_typed_full'].source_curriculum_totals[metric] for b in blocks)
        retained_with_build=sum(b['nexus_typed_without_pruning'].source_curriculum_totals[metric] for b in blocks)
        assert full_with_build<retained_with_build,('including_index_build',metric,full_with_build,retained_with_build)


def test_source_suite_all_methods_three_seeds():
    from scripts.run_wave16_peeled_archive_assessment import assess_cases
    from scripts.verify_wave16_peeled_archive_enumerator import verify_payload
    payload=assess_cases(source_cases(),SourceEnv,seeds=(0,1,2),development=True)
    full=payload['totals']['suite']['nexus_typed_full']
    assert full['mapping_correct']==full['private_correct']==54,full
    assert full['cold_archive_reactivated']>=3
    assert not full['false_unique']
    assert full['ambiguous_correctly_declared']==3
    for name,row in payload['totals']['suite'].items():
        if name=='nexus_typed_full':continue
        assert full['total_work']<row['total_work'],(name,full,row)
        assert full['total_primitive_op_steps']<row['total_primitive_op_steps'],(name,full,row)
    assert verify_payload(payload)['valid']
    assert payload['gates']['passed']


def test_oog_no_piecewise_and_private_isolation():
    for method in ('nexus_typed_full','nexus_typed_without_pruning','equal_typed_scratch'):
        learner=TypedEqualCapabilityLearner(method)
        for fn in ('source_wrapped','source_wrapped_second','source_l2'):
            learner.solve_unfamiliar_task(SourceEnv(SOURCE[fn]),10)
        a=SourceEnv(SOURCE['swap_pairs']);b=SourceEnv(SOURCE['swap_pairs'])
        b.private_map={'alpha':('changed',)}
        other=copy.deepcopy(learner)
        r=learner.solve_unfamiliar_task(a,10);s=other.solve_unfamiliar_task(b,10)
        assert r.status==s.status=='abstain'
        assert r.program_ast==s.program_ast and r.total_work==s.total_work
        assert learner.last_diagnostics['piecewise_evaluations']==0
        assert learner.last_diagnostics['piecewise_primitive_steps']==0
        assert not a.private_opened and not b.private_opened


@pytest.mark.parametrize('op',['REVERSE','TAIL','DROP_LAST','APPEND_TOK','PREPEND_TOK'])
def test_outer_size_six_seven_independent_semantic_witness(op):
    x=VarNode()
    core=PrimOpNode('APPEND_TOK',(PrimOpNode('TAIL',(x,),TypeTag.SEQ),PrimOpNode('HEAD',(x,),TypeTag.TOK)),TypeTag.SEQ)
    token=ConstNode('only_source',TypeTag.TOK)
    if op=='APPEND_TOK':witness=PrimOpNode(op,(core,token),TypeTag.SEQ)
    elif op=='PREPEND_TOK':witness=PrimOpNode(op,(token,core),TypeTag.SEQ)
    else:witness=PrimOpNode(op,(core,),TypeTag.SEQ)
    inputs=[('a','b','c','d'),('b','d','c'),('d','b','a','c','f')]
    pairs=[(v,eval_expr_ast(witness,v)) for v in inputs]
    ex=extract_task_constants([dict(input=list(v),observed_output=list(y)) for v,y in pairs])
    nodes,_=TypedProgramEnumerator().atomic_candidates(ex,pairs,ResidualSupportCache(pairs,OpCounter()))
    target=tuple(y for v,y in pairs)
    assert any(tuple(eval_expr_ast(n,v) for v in inputs)==target for n in nodes),(op,witness)


def test_unknown_reference_shape_keeps_safe_guard_fallback():
    lib=IndexedMacroLibrary();lib._init_indices();x=VarNode()
    guard=PrimOpNode('SEQ_EQ',(x,PrimOpNode('REVERSE',(x,),TypeTag.SEQ)),TypeTag.BOOL)
    op,_=lib.promote_ast_subtree(guard,'bool_macro')
    for _ in range(3):lib.begin_task()
    unfamiliar=('u',)*11
    guards,_=lib.lookup([(unfamiliar,('new',))])
    assert op.macro_node in guards


def test_point_gate_defers_but_never_discards_other_branch_support():
    from nexus.seed.wave16_peeled_archive_unary_learner import EvolvedMacroNode
    x=VarNode();body=PrimOpNode('REVERSE',(x,),TypeTag.SEQ)
    node=EvolvedMacroNode('source_deferred',body,(x,),TypeTag.SEQ)
    pairs=[(('a','b','c','d'),('c','d')), (('a','b','c'),('c','b','a'))]
    cache=ResidualSupportCache(pairs,OpCounter());archive=OpCounter()
    possible,calls=cache.cold_first_possible(node,[],archive)
    assert not possible and calls>0
    # Later piecewise preparation must recover the second row's useful mask.
    cache.macro_outputs(node,archive)
    cache.prime_wrappers(node,[])
    assert any(1 in mask for mask in cache.partial)


def test_archive_point_gate_is_numerically_exact_for_all_wrappers():
    from nexus.seed.wave16_peeled_archive_unary_learner import EvolvedMacroNode
    x=VarNode();body=PrimOpNode('REVERSE',(x,),TypeTag.SEQ)
    node=EvolvedMacroNode('point_shared',body,(x,),TypeTag.SEQ)
    pairs=[(('a','b','c'),('new','c','b','a')), (('d','e'),('new','e','d'))]
    cache=ResidualSupportCache(pairs,OpCounter());archive=OpCounter()
    possible,_=cache.cold_first_possible(node,['new'],archive)
    assert possible
    cache.macro_outputs(node,archive)
    for candidate in cache.prime_wrappers(node,['new']):
        assert cache.outputs[candidate.canonical_key()]==tuple(eval_expr_ast(candidate,v) for v,y in pairs)


def test_incremental_cold_transform_and_guard_costs_stay_in_archive_meter():
    from nexus.seed.wave16_peeled_archive_unary_learner import EvolvedMacroNode
    x=VarNode();node=EvolvedMacroNode('cold_meter',PrimOpNode('REVERSE',(x,),TypeTag.SEQ),(x,),TypeTag.SEQ)
    cache=ResidualSupportCache([(('a','b'),('b','a'))],OpCounter())
    cache.cold_ids.add('cold_meter')
    values,synthetic_calls=cache.incremental(node,[(('c','d'),('d','c'))])
    assert values==(('d','c'),) and synthetic_calls==0
    assert cache.archive_counter.steps==1 and cache.synth_counter.steps==0
    assert cache.extra_archive_evals==1


@pytest.fixture(scope='module')
def source_payload():
    from scripts.run_wave16_peeled_archive_assessment import assess_cases
    return assess_cases(source_cases(),SourceEnv,seeds=(0,1,2),development=True)


@pytest.mark.parametrize('missing',['seed','task','condition','cost','index'])
def test_complete_grid_and_archive_receipts_fail_closed(source_payload,missing):
    from scripts.verify_wave16_peeled_archive_enumerator import verify_payload
    payload=copy.deepcopy(source_payload)
    if missing=='seed':
        payload['seeds']=[0,1]
        payload['assessment']=[r for r in payload['assessment'] if r['source_seed']!=2]
    elif missing=='task':
        identifier=payload['task_manifest'].pop()['id']
        payload['assessment']=[r for r in payload['assessment'] if r['task_id']!=identifier]
    elif missing=='condition':payload['assessment']=[r for r in payload['assessment'] if r['method']!='nexus_typed_full']
    elif missing=='cost':payload['assessment'][0]['synthesis_evals']=True
    else:
        row=next(r for r in payload['assessment'] if 'index_hash_probes' in r['support_gate'])
        row['support_gate']['index_hash_probes']+=1
    assert not verify_payload(payload)['valid']
