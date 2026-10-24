"""Only authored SOURCE fixtures. Never import any closed/fresh assessment."""
import ast
import copy
import itertools
from pathlib import Path

import pytest
from nexus.seed.wave17_exact_cache_boundary_learner import (
    VarNode,ConstNode,PrimOpNode,EvolvedMacroNode,PiecewiseProgramAST,PiecewiseBranch,
    TypeTag,OpCounter,ExactCache,TypedProgramEnumerator,TypedEqualCapabilityLearner,
    FilterSeqNode,MapReplaceTokNode,DedupAdjSeqNode,HasTokNode,StateRecord,
    eval_expr_ast,eval_program,expr_ast_from_dict,ast_key,walk,new_counters,extract_constants,
    select_max_entropy_probe,canonical_input,validate_task_fixture_semantics,
    CANONICAL_BOUNDARY_INPUTS,WORK_KEYS,PRIMITIVE_KEYS)

ROOT=Path(__file__).resolve().parents[1]
X=VarNode();IX=VarNode(TypeTag.INT)


def unary(op,node=X):return PrimOpNode(op,(node,),TypeTag.SEQ)


def token(value):return ConstNode(value,TypeTag.TOK)


def append(node,value):return PrimOpNode('APPEND_TOK',(node,token(value)),TypeTag.SEQ)


def prepend(value,node):return PrimOpNode('PREPEND_TOK',(token(value),node),TypeTag.SEQ)


def parity(kind=TypeTag.SEQ,value=0):
    scalar=IX if kind==TypeTag.INT else PrimOpNode('LEN',(X,),TypeTag.INT)
    return PrimOpNode('INT_EQ',(PrimOpNode('MOD2',(scalar,),TypeTag.INT),ConstNode(value,TypeTag.INT)),TypeTag.BOOL)


def program(transform,guard=None,kind=TypeTag.SEQ):
    return PiecewiseProgramAST((PiecewiseBranch(guard or parity(kind),transform),),VarNode(kind))


def source_inputs(seed=0,short=False):
    a,b,c=('source_a'+str(seed),'source_b'+str(seed),'source_c'+str(seed))
    m='source_remove'
    rows=[(a,m,m,b),(b,m,a),(a,a,m,c,a,a),(b,b,m,c,b),
        (a,m,b,c,a,m),(c,m,c),(a,m,b,c,b,a),(b,m,b,m,b),
        (a,b,c,b),(a,b,a),(a,b,b,a),(a,b,c),
        (m,a,a,m,b,b),(b,m,c,c,a),(a,m,a,b,c,m,b,c),
        (c,c,m,b,a,m,a),(a,b,m,b,a),(m,b,c,m,a,b),
        (a,b,c,a,b,c,a,b),(a,m,b,m,c),
        (b,m,a,c,c,b),(c,m,b,a,c)]
    if short:rows[0]=();rows[1]=(a,);rows[5]=(a,b)
    return rows


def spec(identifier,target,fn,split='source',short=False,integers=False,gold='unique'):
    seeds={}
    for seed in (0,1,2):
        inputs=list(range(-8,14)) if integers else source_inputs(seed,short)
        private=list(range(15,19)) if integers else [tuple(reversed(x)) for x in source_inputs(seed,short)[-4:]]
        seeds[seed]=dict(public=[(x,fn(x)) for x in inputs],private=[(x,fn(x)) for x in private],confirm_count=2)
    return dict(id=identifier,split=split,gold=gold,target_ast=target.to_dict() if target else None,seeds=seeds)


def source_specs():
    # Independent Python oracles check interpreter fixture semantics.
    def even_reverse(x):return x[::-1] if len(x)%2==0 else x
    def odd_reverse(x):return x[::-1] if len(x)%2 else x
    def even_tail(x):return x[1:] if len(x)%2==0 else x
    def filtered(x):return tuple(v for v in x if v!='source_remove')
    def even_filter(x):return filtered(x) if len(x)%2==0 else x
    def dedup(x):return tuple(v for i,v in enumerate(x) if i==0 or x[i-1]!=v)
    def core_fn(x):return x[1:]+x[:-1]
    def sub1(x):return ('source_left',)+core_fn(x) if len(x)%2==0 else x
    def sub2(x):return core_fn(x)+('source_right',) if len(x)%2==0 else x
    def sub3(x):return core_fn(x)[::-1] if len(x)%2==0 else x
    def sub4(x):return ('source_outer',)+core_fn(x)[::-1] if len(x)%2==0 else x
    def sub5(x):return (('source_outer',)+core_fn(x)[::-1])[::-1] if len(x)%2==0 else x
    def p1(x):return ('source_even',)+x if len(x)%2==0 else x+('source_odd',)
    def p2(x):return ('source_even',)+filtered(x) if len(x)%2==0 else x+('source_odd',)
    def pal(x):return x==x[::-1]
    def intro(x):return x+('source_pal',) if pal(x) else x
    def reuse(x):return ('source_return',)+x if pal(x) else x
    def int_add(x):return x+3 if x%2==0 else x
    def int_neg(x):return -x if x%2 else x
    def oog(x):
        result=[]
        for i in range(0,len(x),2):result.extend(x[i:i+2][::-1])
        return tuple(result)
    core=PrimOpNode('CONCAT',(unary('TAIL'),unary('DROP_LAST')),TypeTag.SEQ)
    pal_guard=PrimOpNode('SEQ_EQ',(X,unary('REVERSE')),TypeTag.BOOL)
    piece1=PiecewiseProgramAST((PiecewiseBranch(parity(),prepend('source_even',X)),
        PiecewiseBranch(parity(value=1),append(X,'source_odd'))),X)
    piece2=PiecewiseProgramAST((PiecewiseBranch(parity(),prepend('source_even',FilterSeqNode(X,token('source_remove')))),
        PiecewiseBranch(parity(value=1),append(X,'source_odd'))),X)
    cases=[
        spec('src_base_reverse',program(unary('REVERSE')),even_reverse,short=True),
        spec('src_base_odd',program(unary('REVERSE'),parity(value=1)),odd_reverse,short=True),
        spec('src_int_add',program(PrimOpNode('INT_ADD',(IX,ConstNode(3,TypeTag.INT)),TypeTag.INT),kind=TypeTag.INT),int_add,integers=True),
        spec('src_filter_transfer',program(FilterSeqNode(X,token('source_remove'))),even_filter),
        spec('src_core_prepend',program(prepend('source_left',core)),sub1),
        spec('src_core_append',program(append(core,'source_right')),sub2),
        spec('src_core_reverse',program(unary('REVERSE',core)),sub3),
        spec('src_l2_prepend',program(prepend('source_outer',unary('REVERSE',core))),sub4),
        spec('src_l2_reverse',program(unary('REVERSE',prepend('source_outer',unary('REVERSE',core)))),sub5),
        spec('src_piecewise',piece1,p1,short=True),
        spec('src_piecewise_filter',piece2,p2),
        spec('src_archive_intro',program(append(X,'source_pal'),pal_guard),intro,short=True),
        spec('src_base_third_distractor',program(unary('TAIL')),even_tail,short=True),
        spec('src_int_distractor',program(PrimOpNode('INT_NEG',(IX,),TypeTag.INT),parity(TypeTag.INT,1),TypeTag.INT),int_neg,integers=True),
        spec('src_reverse_distractor',program(unary('REVERSE')),even_reverse,short=True),
        spec('src_archive_reuse',program(prepend('source_return',X),pal_guard),reuse,short=True)]
    outside=spec('src_outside',None,oog,gold='abstain')
    for seed,part in outside['seeds'].items():
        inputs=[tuple('source_%d_%d'%(seed,k) for k in range(n)) for n in range(6,28)]
        part['public']=[(x,oog(x)) for x in inputs]
        part['private']=[(x,oog(x)) for x in inputs[-4:]]
    cases.append(outside)
    # Two guards agree on all available public inputs but differ at length 5.
    g1=parity(value=1)
    g2=PrimOpNode('INT_EQ',(PrimOpNode('LEN',(X,),TypeTag.INT),ConstNode(3,TypeTag.INT)),TypeTag.BOOL)
    p=program(append(X,'source_intent'),g1);q=program(append(X,'source_intent'),g2)
    ambiguous=spec('src_ambiguous',None,odd_reverse,gold='ambiguous')
    for seed,part in ambiguous['seeds'].items():
        xs=[x for x in source_inputs(seed) if len(x) in (3,4)]
        xs=(xs*4)[:22]
        part['public']=[(x,eval_program(p,x)) for x in xs]
        private=[('u','v','w','z','q')]
        part['private']=[(x,eval_program(p,x)) for x in private]
    ambiguous['ambiguous_witnesses']=[p.to_dict(),q.to_dict()]
    cases.append(ambiguous)
    return cases


def test_static_boundaries_and_historical_runtime():
    source=(ROOT/'src/nexus/seed/wave17_exact_cache_boundary_learner.py').read_text()
    tree=ast.parse(source)
    assert not any(isinstance(n,ast.Lambda) for n in ast.walk(tree))
    forbidden={'task_id','family','split','mechanism','private_map','_private_pairs'}
    assert not any(isinstance(n,ast.Attribute) and n.attr in forbidden for n in ast.walk(tree))
    solve=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='solve_unfamiliar_task')
    assert [a.arg for a in solve.args.args]==['self','env','public_budget']
    import hashlib
    assert hashlib.sha256((ROOT/'src/nexus/seed/local_model_runtime.py').read_bytes()).hexdigest()=='5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781'


def fuzz_nodes():
    nodes=[X,ConstNode((),TypeTag.SEQ)]
    for op in ('REVERSE','TAIL','INIT','DROP_LAST','ROT_LEFT','ROT_RIGHT','SWAP_ENDS','DEDUP_ADJ'):
        nodes.append(unary(op))
    for value in ('','a','b'):
        nodes.extend((append(X,value),prepend(value,X),FilterSeqNode(X,token(value)),
            MapReplaceTokNode(X,token(value),token('b')),HasTokNode(token(value),X)))
    nodes.extend((PrimOpNode('HEAD',(X,),TypeTag.TOK),PrimOpNode('LAST',(X,),TypeTag.TOK),
        PrimOpNode('LEN',(X,),TypeTag.INT),PrimOpNode('CONCAT',(X,X),TypeTag.SEQ),parity(),
        PrimOpNode('SEQ_EQ',(X,unary('REVERSE')),TypeTag.BOOL),
        PrimOpNode('TOK_EQ',(PrimOpNode('HEAD',(X,),TypeTag.TOK),PrimOpNode('LAST',(X,),TypeTag.TOK)),TypeTag.BOOL)))
    nodes.append(PrimOpNode('INT_GE',(PrimOpNode('LEN',(X,),TypeTag.INT),ConstNode(2,TypeTag.INT)),TypeTag.BOOL))
    nodes.append(PrimOpNode('IF_THEN_ELSE',(parity(),unary('TAIL'),X),TypeTag.SEQ))
    bases=list(nodes)
    for n in bases:
        if n.out_type==TypeTag.SEQ:
            for op in ('REVERSE','TAIL','DROP_LAST'):
                nodes.append(unary(op,n));nodes.append(FilterSeqNode(unary(op,n),token('')))
    return nodes


def test_differential_boundary_masks_and_expanded_observations():
    inputs=[(),('',),('a',),('a',''),('','b'),('a','b'),('a','a'),('a','b','c')]
    nodes=fuzz_nodes();assert len(nodes)*len(inputs)>=500
    opcodes={n.op_name for node in nodes for n in walk(node) if isinstance(n,PrimOpNode)}
    assert {'HEAD','TAIL','INIT','LAST','REVERSE','CONCAT','APPEND_TOK','PREPEND_TOK','DROP_LAST',
        'LEN','MOD2','TOK_EQ','SEQ_EQ','INT_EQ','INT_GE','IF_THEN_ELSE','FILTER_NEQ','MAP_REPLACE','DEDUP_ADJ','TOK_IN_SEQ'}<=opcodes
    for node in nodes:
        pairs=[(x,eval_expr_ast(node,x)) for x in inputs]
        cache=ExactCache(pairs[:4],new_counters());cache.transform(node)
        cache.pairs.extend(pairs[4:]);cache.refresh_partial()
        outputs,cov=cache.transform(node)
        assert outputs==tuple(eval_expr_ast(node,x) for x in inputs)
        expected={i for i,(x,y) in enumerate(pairs) if x!=y and eval_expr_ast(node,x)==y}
        assert cov==expected and cache.errors==0
        for stored,mask in cache.partial.values():
            assert mask=={i for i,(x,y) in enumerate(pairs) if x!=y and eval_expr_ast(stored,x)==y}


def test_empty_token_wrappers_and_exact_per_element_charges():
    for node in (append(X,''),prepend('',X)):
        assert eval_expr_ast(node,())==()
        assert eval_expr_ast(node,('a',))==('a',)
    for node in (FilterSeqNode(X,token('a')),MapReplaceTokNode(X,token('a'),token('b')),DedupAdjSeqNode(X)):
        c=OpCounter();eval_expr_ast(node,('a','a','b',''),c);assert c.steps==4
    c=OpCounter();assert eval_expr_ast(HasTokNode(token('a'),X),('b','a','c'),c)
    assert c.steps==2


def test_legacy_primitive_semantics_and_op_counts_are_unchanged():
    from nexus.seed import wave14_piecewise_archive_learner as old
    cases=0
    for node in fuzz_nodes():
        if any(isinstance(n,PrimOpNode) and n.op_name not in old.ALLOWED_PRIM_OPCODES for n in walk(node)):continue
        legacy_node=old.expr_ast_from_dict(node.to_dict())
        for x in ((),('',),('a',),('a',''),('','b'),('a','b'),('a','a'),('a','b','c')):
            a=OpCounter();b=OpCounter()
            assert eval_expr_ast(node,x,a)==old.eval_expr_ast(legacy_node,x,b)
            assert a.steps==b.steps;cases+=1
    assert cases>=200


def test_task_observations_prevent_boundary_only_deduplication():
    # These tokens do not occur in any canonical boundary reference sequence.
    a=FilterSeqNode(X,token('task_only'));b=X
    cache=ExactCache([(('task_only','a'),('a',))],new_counters())
    assert len(cache.deduplicate([a,b]))==2
    # Full signatures include empty/singleton lengths even for long tasks.
    a=unary('TAIL');b=unary('DROP_LAST')
    assert len(cache.deduplicate([a,b]))==2
    calls=cache.counters['synth_evals']
    one=cache.deduplicate([unary('INIT'),unary('DROP_LAST'),unary('INIT')])
    assert len(one)==1
    once=cache.counters['synth_evals'];cache.deduplicate(one*3)
    assert cache.counters['synth_evals']==once


def test_active_probe_uses_only_inputs_and_maximal_split():
    cache=ExactCache([(('a','b'),('a','b'))],new_counters())
    guards=[parity(),parity(value=1),ConstNode(True,TypeTag.BOOL)]
    result,score=select_max_entropy_probe(guards,[('b',('a',)),('a',('a','b'))],cache)
    assert result[0]=='a' and score==1
    assert cache.counters['probe_evals']>0
    same,score=select_max_entropy_probe([ConstNode(True,TypeTag.BOOL)]*2,[('a',())],cache)
    assert same is None and score==0


@pytest.mark.parametrize('wrapper',['bare','REVERSE','TAIL','DROP_LAST','APPEND_TOK','PREPEND_TOK','FILTER_NEQ'])
def test_cold_archive_exact_wrapper_reachability(wrapper):
    learner=TypedEqualCapabilityLearner('nexus_typed_full');lib=learner.library
    core=unary('ROT_LEFT',FilterSeqNode(X,token('erase')))
    op,_=lib.promote_ast_subtree(core,'seq_macro')
    for _ in range(3):lib.begin_task()
    assert op.name in lib.cold_archive
    if wrapper=='bare':target=op.macro_node
    elif wrapper=='APPEND_TOK':target=append(op.macro_node,'new')
    elif wrapper=='PREPEND_TOK':target=prepend('new',op.macro_node)
    elif wrapper=='FILTER_NEQ':target=FilterSeqNode(op.macro_node,token('new'))
    else:target=unary(wrapper,op.macro_node)
    xs=[(),('a',),('a','erase','b','new'),('erase','a','new','b','a')]
    pairs=[(x,eval_expr_ast(target,x)) for x in xs]
    gs,cold=lib.lookup(pairs,TypeTag.SEQ)
    assert op.macro_node in cold
    assert op.name in lib.cold_archive and op.name not in lib.operators
    assert lib.promote_ast_subtree(core,'seq_macro')==(None,0)
    assert op.name in lib.cold_archive and op.uses==1
    cache=ExactCache(pairs,new_counters());cache.cold_ids.add(op.macro_node.macro_id)
    enum=TypedProgramEnumerator(TypeTag.SEQ,('new','erase'),(0,1,2),cache)
    candidates=[n for m in cold for n in enum.wrappers(m)]
    assert ast_key(target) in [ast_key(n) for n in candidates]
    for n in candidates:
        out,mask=cache.transform(n)
        assert out==tuple(eval_expr_ast(n,x) for x in xs)
    assert cache.counters['archive_evals']>0 and cache.counters['archive_ops'].steps>0
    assert op.name in lib.cold_archive  # Merely evaluating cannot reactivate.
    locked=PiecewiseProgramAST((PiecewiseBranch(ConstNode(True,TypeTag.BOOL),target),),X)
    assert lib.reactivate_locked(locked)==[op.macro_node.macro_id]
    assert op.name in lib.operators and op.uses==2 and op.inactive_age==0


def test_end_to_end_pruning_invariant_delayed_curriculum():
    from scripts.run_wave17_exact_cache_assessment import PublicWorld
    costs={name:dict(gate_evals=0,synthesis_evals=0,total_work=0,total_primitive_op_steps=0)
        for name in ('nexus_typed_full','nexus_typed_without_pruning')}
    def intro_fn(x):return x[1:]+x[:1] if len(x)%2==0 else x
    core=unary('ROT_LEFT')
    intro=spec('src_rotation_intro',program(core),intro_fn,short=True)
    for wrapper in ('guard','REVERSE','TAIL','APPEND_TOK'):
        if wrapper=='guard':
            cases=source_specs();curriculum=[cases[11],cases[12],cases[13],cases[14],cases[15]]
        else:
            target=append(core,'source_delayed') if wrapper=='APPEND_TOK' else unary(wrapper,core)
            def reference(x):
                if len(x)%2:return x
                rotated=x[1:]+x[:1]
                if wrapper=='REVERSE':return rotated[::-1]
                if wrapper=='TAIL':return rotated[1:]
                return rotated+('source_delayed',)
            cases=source_specs()
            curriculum=[intro,cases[0],cases[2],cases[12],spec('src_delayed_'+wrapper,program(target),reference,short=True)]
        for name in costs:
            learner=TypedEqualCapabilityLearner(name)
            for item in curriculum:
                part=item['seeds'][0];report=learner.solve_unfamiliar_task(PublicWorld(part),24)
                assert report.status=='unique'
                assert all(eval_program(report.program_ast,x)==canonical_input(y) for x,y in part['private'])
                for metric in costs[name]:costs[name][metric]+=getattr(report,metric)
            if name=='nexus_typed_full':assert report.cold_archive_reactivated,wrapper
    for metric in costs['nexus_typed_full']:
        assert costs['nexus_typed_full'][metric]<costs['nexus_typed_without_pruning'][metric],(metric,costs)


def test_loop_state_and_integer_runtime_isolation():
    state=StateRecord((('cancel','yes'),('slot','old')))
    assert canonical_input(state)==('cancel=yes','slot=old')
    target=append(FilterSeqNode(X,token('slot=old')),'slot=new')
    assert eval_expr_ast(target,state)==('cancel=yes','slot=new')
    cache=ExactCache([(2,5),(-1,-1)],new_counters())
    enum=TypedProgramEnumerator(TypeTag.INT,(),(0,1,2,3),cache)
    nodes=enum.atomic()+enum.guards()
    assert not any(n.op_name in ('HEAD','TAIL','FILTER_NEQ','TOK_IN_SEQ') for tree in nodes for n in walk(tree) if isinstance(n,PrimOpNode))
    n=PrimOpNode('INT_ADD',(IX,ConstNode(3,TypeTag.INT)),TypeTag.INT)
    learner=TypedEqualCapabilityLearner('nexus_typed_full')
    op,_=learner.library.promote_ast_subtree(n,'int_macro')
    assert op.macro_node.out_type==TypeTag.INT and eval_expr_ast(op.macro_node,4)==7
    # Exact internal support from two solved tasks is durable; a review is not
    # counted as a new task and once-used unrelated roots remain evictable.
    core=PrimOpNode('CONCAT',(unary('TAIL'),unary('DROP_LAST')),TypeTag.SEQ)
    lib=learner.library
    for node in (prepend('source_l1a',core),append(core,'source_l1b')):
        lib.begin_task();lib.compress_solved_programs_mdl(program(node),True,OpCounter())
        history=len(lib.solved_program_history)
        assert lib.compress_solved_programs_mdl(program(node),True,OpCounter())==(0,())
        assert len(lib.solved_program_history)==history
    supported=[op for op in lib.operators.values() if op.macro_node.body_ast.canonical_key()==core.canonical_key()]
    assert len(supported)==1 and supported[0].uses>=2 and supported[0].name in lib.mdl_subtree_names
    for _ in range(4):lib.begin_task()
    assert supported[0].name in lib.operators
    plain=ExactCache([(('a','b'),('b','a'))],new_counters())
    enum=TypedProgramEnumerator(TypeTag.SEQ,('unobserved',),(0,1,2),plain)
    assert not enum.filter_tokens and not enum.replace_pairs
    assert not any(isinstance(n,(FilterSeqNode,MapReplaceTokNode)) for n in enum.wrappers(X))
    observed=ExactCache([(('old','old','x'),('new','x'))],new_counters())
    enum=TypedProgramEnumerator(TypeTag.SEQ,('old','new'),(0,1,2),observed)
    assert enum.filter_tokens=={'old'} and enum.replace_pairs=={('old','new')}


def test_state_policy_is_synthesized_from_observed_rows_only():
    from scripts.run_wave17_exact_cache_assessment import PublicWorld
    rows=[]
    for i in range(22):
        items=[('slot',str(i%4)),('intent','book')]
        if i%2:
            items.append(('cancel','yes'))
            if i%8==1:items.append(('cancel','yes'))  # repeated cancellation event
        if (i//2)%2:items.append(('extra','seen'))
        state=StateRecord(tuple(items));x=canonical_input(state)
        y=tuple(t for t in x if t!='cancel=yes')+('commit=yes',) if 'cancel=yes' in x else x
        rows.append((state,y))
    learner=TypedEqualCapabilityLearner('nexus_typed_full')
    result=learner.solve_unfamiliar_task(PublicWorld(dict(public=rows)),24)
    assert result.status=='unique'
    for x,y in rows:assert eval_program(result.program_ast,x)==y
    assert any(n.op_name=='TOK_IN_SEQ' for b in result.program_ast['branches']
        for n in walk(expr_ast_from_dict(b['guard'])) if isinstance(n,PrimOpNode))


def test_private_labels_cannot_change_choice_or_cost():
    from scripts.run_wave17_exact_cache_assessment import PublicWorld
    s=source_specs()[0];part=s['seeds'][0]
    other=copy.deepcopy(part);other['private']=[(('changed',),('hidden',))]
    a=TypedEqualCapabilityLearner('nexus_typed_full');b=TypedEqualCapabilityLearner('nexus_typed_full')
    ar=a.solve_unfamiliar_task(PublicWorld(part),24);br=b.solve_unfamiliar_task(PublicWorld(other),24)
    assert ar.program_ast==br.program_ast and ar.total_work==br.total_work


def test_fixture_validator_rejects_wrong_empty_and_short_nested_semantics():
    good=source_specs()[0];assert validate_task_fixture_semantics(good)['valid']
    bad=copy.deepcopy(good);bad['seeds'][0]['public'][0]=((),('unintended',))
    assert not validate_task_fixture_semantics(bad)['valid']
    bad=spec('bad_nested',program(unary('TAIL',unary('TAIL'))),tuple,short=True)
    assert not validate_task_fixture_semantics(bad)['valid']


def test_source_fixture_semantics_and_ambiguity():
    cases=source_specs();assert len(cases)==18
    for item in cases:
        result=validate_task_fixture_semantics(item)
        assert result['valid'],(item['id'],result)


@pytest.fixture(scope='module')
def source_payload(tmp_path_factory):
    import json,time
    from scripts.run_wave17_exact_cache_assessment import assess_specs
    folder=tmp_path_factory.mktemp('wave17_source');start=time.perf_counter()
    with (folder/'rows.jsonl').open('w') as stream:
        def emit(row):
            stream.write(json.dumps(row)+'\n');stream.flush()
            if row['arrival_index']==17:
                print('source block',row['source_seed'],row['method'],'elapsed',round(time.perf_counter()-start,2),flush=True)
        payload=assess_specs(source_specs(),development=True,emit=emit)
    (folder/'payload.json').write_text(json.dumps(payload))
    print('source receipt',folder,flush=True)
    return payload


def test_complete_source_suite_five_methods_gate(source_payload):
    from scripts.verify_wave17_exact_cache_enumerator import verify_payload
    full=source_payload['totals']['suite']['nexus_typed_full']
    assert full['private_correct']==54,full
    assert full['ambiguous_correctly_declared']==3 and not full['false_unique']
    assert full['cold_archive_reactivated']>=3
    assert verify_payload(source_payload,source_specs())['valid']
    assert source_payload['gates']['passed'],source_payload['gates']


@pytest.mark.parametrize('axis',['seed','task','method','mask','cost'])
def test_independent_verifier_rejects_incomplete_or_corrupt_results(source_payload,axis):
    from scripts.verify_wave17_exact_cache_enumerator import verify_payload
    payload=copy.deepcopy(source_payload)
    if axis=='seed':payload['assessment']=[r for r in payload['assessment'] if r['source_seed']!=2]
    elif axis=='task':payload['task_manifest'].pop()
    elif axis=='method':payload['methods'].pop()
    elif axis=='cost':payload['assessment'][0]['total_work']+=1
    else:
        row=next(r for r in payload['assessment'] if r['support_gate'].get('evaluated_partial_transforms'))
        row['support_gate']['evaluated_partial_transforms'][0]['coverage'].append(999)
    assert not verify_payload(payload,source_specs())['valid']
