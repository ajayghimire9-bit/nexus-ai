"""Authored source-only fixtures; never imports a closed/fresh assessment suite."""
import ast
import json
from pathlib import Path
import random

import pytest
from nexus.seed.wave15_support_gated_piecewise_learner import (
    TypedEqualCapabilityLearner, ResidualSupportCache, OpCounter, VarNode,
    PrimOpNode, TypeTag, execute_wave14_program_ast, extract_task_constants,
    synthesize_wave15, TypedMacroLibrary, TypedProgramEnumerator,
)
from nexus.seed.wave14_piecewise_archive_learner import report_to_row, reconstruct_total_work, reconstruct_primitive_steps

ROOT=Path(__file__).resolve().parents[1]


def rotate(x):
    return x[-1:]+x[:-1] if x else x


def even_reverse(x):
    return x[::-1] if len(x)%2==0 else x


def odd_reverse(x):
    return x[::-1] if len(x)%2 else x


def even_tail(x):
    return x[1:] if len(x)%2==0 else x


def source_wrapped(x):
    return rotate(x)+('~',) if len(x)%2==0 else x


def source_wrapped_second(x):
    return ('^',)+rotate(x) if len(x)%2==0 else x


def source_reuse(x):
    return rotate(x)+('+',) if len(x)%2==0 else x


def source_l2(x):
    return ('~',)+rotate(x)+('+',) if len(x)%2==0 else x


def source_l2_second(x):
    return ('^',)+rotate(x)+('+',) if len(x)%2==0 else x


def two_branch(x):
    return rotate(x) if len(x)%2==0 else x[::-1]


def two_branch_wrapped(x):
    return rotate(x)+('+',) if len(x)%2==0 else x[::-1]


def palindrome_first(x):
    return x+('~',) if x==x[::-1] else x


def palindrome_last(x):
    return ('^',)+x if x==x[::-1] else x


def swap_pairs(x):
    result=[]
    for i in range(0,len(x),2):
        result.extend(x[i:i+2][::-1])
    return tuple(result)


class SourceEnv:
    def __init__(self,fn,seed=0,pal=False,ambiguous=False):
        rng=random.Random(seed)
        vocab=list('abcdefghijklmnopqrstuvwx');rng.shuffle(vocab)
        a,b,c,d,e,f=vocab[:6]
        self.fn=fn;self.ambiguous=ambiguous;self.locked=False;self.private_opened=False
        self.public_map=dict(alpha=(),beta=(a,b,c,d),gamma=(a,b),delta=(c,d,e))
        if pal:self.public_map=dict(alpha=(),beta=(a,),gamma=(a,b,a),delta=(a,b))
        self.epsilon=(b,c,d)
        self.extra_public_slots={
            'bank0':(a,b),'bank1':(a,b,c,d),'bank2':(b,c,d),'bank3':(b,c,d,e),
            'bank4':(a,b,c),'bank5':(d,e),'bank6':(c,d,e,f),'bank7':(c,d,e),
            'hold0':(a,b,c,d,e,f),'hold1':(a,c,d,e,f),
            'confirm_0':(b,c,d,e),'confirm_1':(c,d,e),'confirm_2':(a,b,a),'confirm_3':(a,b,c,d,e,f)}
        if pal:
            for k in ('bank0','bank1','bank3','bank5'):
                self.extra_public_slots[k]=(a,b,a)
            self.extra_public_slots['confirm_0']=(b,c,b)
        self.private_map=dict(alpha=(e,f),beta=(f,e,d),gamma=(e,f,d,c),delta=())
        self.calls=0

    def public_read(self,slot):
        self.calls+=1
        x=self.epsilon if slot=='epsilon' else self.public_map.get(slot,self.extra_public_slots.get(slot))
        y=self.fn(x)
        row=dict(payload=x,result=y,echo=x,stamp=self.calls,tick=self.calls,slot=slot)
        if self.ambiguous:row['alias']=y
        return row

    def lock(self):self.locked=True

    def private_read(self,slot):
        if not self.locked:raise RuntimeError('private_before_lock')
        self.private_opened=True;x=self.private_map[slot]
        return dict(payload=x,result=self.fn(x))


def source_cases():
    # 18 SOURCE development cases. No w15f identities/rules are defined here.
    return [
        ('base_even',even_reverse,'base',False,'unique'),
        ('base_odd',odd_reverse,'base',False,'unique'),
        ('analogy_tail',even_tail,'analogy',False,'unique'),
        ('analogy_rev',odd_reverse,'analogy',False,'unique'),
        ('sub_first',source_wrapped,'subtree',False,'unique'),
        ('sub_second',source_wrapped_second,'subtree',False,'unique'),
        ('sub_third',source_reuse,'subtree',False,'unique'),
        ('sub_l2',source_l2,'subtree',False,'unique'),
        ('sub_l2_reuse',source_l2_second,'subtree',False,'unique'),
        ('piece_one',two_branch,'piecewise',False,'unique'),
        ('piece_two',two_branch_wrapped,'piecewise',False,'unique'),
        ('archive_intro',palindrome_first,'archive',True,'unique'),
        ('base_third_intervening',even_tail,'base',False,'unique'),
        ('archive_distractor_one',even_reverse,'archive',False,'unique'),
        ('archive_distractor_two',odd_reverse,'archive',False,'unique'),
        ('archive_reuse',palindrome_last,'archive',True,'unique'),
        ('outside_grammar',swap_pairs,'oog',False,'abstain'),
        ('ambiguous_channel',even_reverse,'oog',False,'ambiguous'),
    ]


def test_static_grammar_and_label_blind_source():
    source=(ROOT/'src/nexus/seed/wave15_support_gated_piecewise_learner.py').read_text()
    tree=ast.parse(source)
    assert not any(isinstance(n,ast.Lambda) for n in ast.walk(tree))
    forbidden={'task_id','family','split','mechanism','_private_pairs','private_map'}
    assert not any(isinstance(n,ast.Attribute) and n.attr in forbidden for n in ast.walk(tree))
    solve=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='solve_unfamiliar_task')
    assert [a.arg for a in solve.args.args]==['self','env','public_budget']


def test_cached_gate_never_evaluates_ast_or_reads_probes(monkeypatch):
    pairs=[(('a','b'),('b','a')), (('c','d'),('c','d','c'))]
    counter=OpCounter();cache=ResidualSupportCache(pairs,counter)
    cache.transform(PrimOpNode('REVERSE',(VarNode(),),TypeTag.SEQ))
    before=counter.steps
    import nexus.seed.wave15_support_gated_piecewise_learner as module
    def forbidden(*args,**kwargs):raise AssertionError('new AST evaluation')
    monkeypatch.setattr(module,'eval_expr_ast',forbidden)
    assert not cache.pre_piecewise()
    assert counter.steps==before
    assert cache.diagnostics['piecewise_evaluations']==0


def test_oog_with_populated_macros_has_zero_piecewise_overhead():
    costs={}
    for method in ('nexus_typed_full','equal_typed_scratch'):
        learner=TypedEqualCapabilityLearner(method)
        if method=='nexus_typed_full':
            for fn in (source_wrapped,source_wrapped_second,source_l2):
                learner.solve_unfamiliar_task(SourceEnv(fn),10)
        env=SourceEnv(swap_pairs)
        report=learner.solve_unfamiliar_task(env,10)
        assert report.status=='abstain'
        diag=learner.last_diagnostics
        assert diag['aborted_before_piecewise']
        assert diag['piecewise_evaluations']==diag['piecewise_primitive_steps']==0
        costs[method]=report.total_work
    assert costs['nexus_typed_full'] < 1.05*costs['equal_typed_scratch'],costs


@pytest.mark.parametrize('seed',range(10))
def test_piecewise_ten_seeds_under_1500(seed):
    learner=TypedEqualCapabilityLearner('nexus_typed_full')
    for fn in (source_wrapped,source_wrapped_second,source_reuse):
        assert learner.solve_unfamiliar_task(SourceEnv(fn,seed),10).status=='unique'
    env=SourceEnv(two_branch,seed)
    report=learner.solve_unfamiliar_task(env,10)
    assert report.status=='unique',(seed,report.status,learner.last_diagnostics)
    assert learner.last_diagnostics['gate1'] and learner.last_diagnostics['gate2']
    env.lock()
    for slot in env.private_map:
        row=env.private_read(slot)
        assert execute_wave14_program_ast(report.program_ast,row['payload'])==row['result']
    assert report.total_work < 1500,report.total_work


def test_full_source_suite_domination_and_standalone_verifier():
    from scripts.run_wave15_support_gated_assessment import assess_cases
    from scripts.verify_wave15_support_gated_enumerator import verify_payload
    payload=assess_cases(source_cases(),SourceEnv,seeds=(0,),development=True)
    full=payload['totals']['suite']['nexus_typed_full']
    assert full['mapping_correct']==18
    assert full['cold_archive_reactivated']>=1
    for method,row in payload['totals']['suite'].items():
        if method=='nexus_typed_full':continue
        assert full['total_work'] < row['total_work'],(method,full,row)
        assert full['total_primitive_op_steps'] < row['total_primitive_op_steps'],(method,full,row)
    assert verify_payload(payload)['valid']


def test_exact_macro_output_reuse_charges_only_executed_primitive_steps():
    from nexus.seed.wave15_support_gated_piecewise_learner import EvolvedMacroNode
    body=PrimOpNode('REVERSE',(VarNode(),),TypeTag.SEQ)
    macro=EvolvedMacroNode('source_only',body,(VarNode(),),TypeTag.SEQ)
    cache=ResidualSupportCache([(('a','b'),('b','a'))],OpCounter())
    values,calls=cache.transform(body)
    before=cache.synth_counter.steps
    assert calls==1
    assert cache.transform(macro)==(values,0)
    assert cache.synth_counter.steps==before
    assert next(iter(cache.partial.values()))[0]==macro


def test_private_outcomes_cannot_change_program_or_costs():
    a=SourceEnv(source_wrapped);b=SourceEnv(source_wrapped)
    b.private_map={slot:('unseen','different','private') for slot in b.private_map}
    ra=TypedEqualCapabilityLearner('nexus_typed_full').solve_unfamiliar_task(a,10)
    rb=TypedEqualCapabilityLearner('nexus_typed_full').solve_unfamiliar_task(b,10)
    assert ra.program_ast==rb.program_ast
    assert ra.total_work==rb.total_work
    assert not a.private_opened and not b.private_opened


@pytest.mark.parametrize('tamper',['row','cost','mask','seed','private'])
def test_verifier_rejects_missing_or_tampered_evidence(tamper):
    from scripts.run_wave15_support_gated_assessment import assess_cases
    from scripts.verify_wave15_support_gated_enumerator import verify_payload
    payload=assess_cases(source_cases(),SourceEnv,seeds=(0,),development=True)
    if tamper=='row':payload['assessment'].pop()
    elif tamper=='cost':payload['assessment'][0]['total_work']+=1
    elif tamper=='seed':payload['seeds'].append(0)
    elif tamper=='private':payload['assessment'][0]['private_evaluations'].pop()
    else:
        row=next(r for r in payload['assessment'] if r['support_gate'].get('evaluated_partial_transforms'))
        row['support_gate']['evaluated_partial_transforms'][0]['coverage']=[]
    assert not verify_payload(payload)['valid']
