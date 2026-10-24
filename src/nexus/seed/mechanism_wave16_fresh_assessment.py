"""Fresh evaluator-owned Wave16 suite, authored after freeze 23e9ad9.

No learner imports this module. No w12f_*–w15f_* suite is imported or rerun.
Public rows are observations; reference functions and private rows are evaluator
only. These definitions and all outcomes close permanently after one attempt.
"""
from __future__ import annotations
import random


def core_head_reverse(x):
    # PREPEND_TOK(HEAD(x), REVERSE(x)): five expanded AST nodes.
    return (x[0] if x else '',)+x[::-1]


def length_at_least_four_tail(x):
    return x[1:] if len(x)>=4 else x


def odd_literal_prefix(x):
    return ('∴',)+x if len(x)%2 else x


def length_at_least_three_reverse(x):
    return x[::-1] if len(x)>=3 else x


def length_two_literal_prefix(x):
    return ('◊',)+x if len(x)==2 else x


def length_three_projection(x):
    return x[:-1] if len(x)==3 else x


def embedded_unary(x):
    return core_head_reverse(x)[:-1] if len(x)%2 else x


def embedded_suffix(x):
    return core_head_reverse(x)+('§',) if len(x)%2 else x


def embedded_third_prefix(x):
    return ('≈',)+core_head_reverse(x) if len(x)%2 else x


def nested_suffix(x):
    return ('≈',)+core_head_reverse(x)+('∴',) if len(x)%2 else x


def nested_prefix(x):
    return ('∵','≈')+core_head_reverse(x) if len(x)%2 else x


def two_branch_core_reverse(x):
    return core_head_reverse(x) if len(x)%2 else x[::-1]


def two_branch_suffix_reverse(x):
    return core_head_reverse(x)+('§',) if len(x)%2 else x[::-1]


def equal_ends(x):
    return (x[0] if x else '')==(x[-1] if x else '')


def ends_intro(x):
    return x+('∵',) if equal_ends(x) else x


def odd_double_distractor(x):
    return x+x if len(x)%2 else x


def even_last_prefix_distractor(x):
    return (x[-1] if x else '',)+x if len(x)%2==0 else x


def ends_delayed_reverse(x):
    return x[::-1] if equal_ends(x) else x


def stride_partition_oog(x):
    return x[::2]+x[1::2]


def ambiguous_even_projection(x):
    return x[1:] if len(x)%2==0 else x


def ambiguous_length_four_projection(x):
    return x[1:] if len(x)==4 else x


def fresh_cases():
    base='w16f_base_and_dynamic_literals'
    analogy='w16f_cross_domain_analogy'
    sub='w16f_unassisted_subtree_and_L2'
    piece='w16f_piecewise_multibranch'
    archive='w16f_spurious_distractor_and_delayed_archive'
    oog='w16f_true_oog_and_ambiguous'
    return [
        ('w16f_ge_four_tail',length_at_least_four_tail,base,False,'unique'),
        ('w16f_ge_three_reverse',length_at_least_three_reverse,base,False,'unique'),
        ('w16f_eq_two_prefix',length_two_literal_prefix,analogy,False,'unique'),
        ('w16f_eq_three_projection',length_three_projection,analogy,False,'unique'),
        ('w16f_head_reverse_unary',embedded_unary,sub,False,'unique'),
        ('w16f_head_reverse_suffix',embedded_suffix,sub,False,'unique'),
        ('w16f_head_reverse_third',embedded_third_prefix,sub,False,'unique'),
        ('w16f_hierarchical_suffix',nested_suffix,sub,False,'unique'),
        ('w16f_hierarchical_prefix',nested_prefix,sub,False,'unique'),
        ('w16f_piece_core_reverse',two_branch_core_reverse,piece,False,'unique'),
        ('w16f_piece_suffix_reverse',two_branch_suffix_reverse,piece,False,'unique'),
        ('w16f_equal_ends_intro',ends_intro,archive,True,'unique'),
        ('w16f_intervening_odd_literal',odd_literal_prefix,base,False,'unique'),
        ('w16f_odd_double_distractor',odd_double_distractor,archive,False,'unique'),
        ('w16f_last_prefix_distractor',even_last_prefix_distractor,archive,False,'unique'),
        ('w16f_equal_ends_delayed',ends_delayed_reverse,archive,True,'unique'),
        ('w16f_stride_partition_oog',stride_partition_oog,oog,False,'abstain'),
        ('w16f_observational_guard_fork',ambiguous_even_projection,oog,False,'ambiguous'),
    ]


class FreshWorld:
    def __init__(self,fn,seed=0,pal=False,ambiguous=False):
        words=['cedar','willow','maple','birch','elm','fir','pine','ash']
        random.Random(46000+seed).shuffle(words)
        a,b,c,d,e,f,g,h=words
        self.fn=fn;self.ambiguous=ambiguous
        self.calls=0;self.locked=False;self.private_opened=False
        self.public_map=dict(alpha=(),beta=(a,b,c,d),gamma=(a,b),delta=(b,c,d))
        self.epsilon=(d,e,f)
        self.extra_public_slots={
            'synth0':(b,c),'synth1':(b,c,d,e),
            'synth2':(a,c,e),'synth3':(c,d,e,f),
            'synth4':(b,e,g),'synth5':(h,),
            'synth6':(a,b,c,d,e,f),'synth7':(a,c,e,g,h),
            'remaining0':(c,e,g),'remaining1':(a,c,f,h),
            'confirm_0':(c,f,h),'confirm_1':(b,d,f,h),
            'confirm_2':(a,b,d,g,h),'confirm_3':(a,b,c,e,g,h)}
        if pal:
            # Equality-rich profile includes nonpalindromic equal-endpoint
            # sequences, so equal endpoints and palindrome are distinguishable.
            self.public_map=dict(alpha=(),beta=(a,),gamma=(a,b,a),delta=(a,b,c,a))
            self.epsilon=(a,b,c,d)
            self.extra_public_slots.update({
                'synth0':(b,c,d,b),'synth1':(a,b,c,d,a),
                'synth2':(c,d,c),'synth3':(b,c),
                'synth4':(d,e,f,d),'synth5':(e,),
                'synth6':(a,b,c),'synth7':(b,e,f,g,b),
                'remaining0':(c,d,e,c),'remaining1':(a,b,c,d),
                'confirm_0':(f,g,h,f),'confirm_1':(a,b,c,d),
                'confirm_2':(c,d,e,f,c),'confirm_3':(b,e,f,g)})
        if ambiguous:
            # Both guard rules agree on every public row but disagree for an
            # even length6 input. Distinct channels expose that unresolved fork.
            self.public_map=dict(alpha=(),beta=(a,b,c,d),gamma=(b,c,d),delta=(c,d,e,f))
            self.epsilon=(d,e,f)
            self.extra_public_slots={
                'synth0':(a,c,e),'synth1':(a,b,e,h),
                'synth2':(e,f,g),'synth3':(b,d,g,h),
                'synth4':(f,g,h),'synth5':(c,e,f,h),
                'synth6':(a,d,f),'synth7':(a,c,f,h),
                'confirm_0':(a,b,c),'confirm_1':(c,d,e,f)}
        self.private_map=dict(alpha=(g,),beta=(e,g,h),gamma=(a,d,f,h),delta=(a,c,d,e,f,g,h))
        if pal:self.private_map=dict(alpha=(h,),beta=(g,h,g),gamma=(a,e,f,a),delta=(b,c,d,e))

    def public_read(self,slot):
        self.calls+=1
        x=self.epsilon if slot=='epsilon' else self.public_map.get(slot,self.extra_public_slots.get(slot))
        result=self.fn(x)
        row=dict(payload=x,result=result,echo=x,stamp=self.calls,tick=self.calls,slot=slot)
        if self.ambiguous:row['alias']=ambiguous_length_four_projection(x)
        return row

    def lock(self):
        self.locked=True

    def private_read(self,slot):
        if not self.locked:raise RuntimeError('private_before_lock')
        self.private_opened=True;x=self.private_map[slot]
        return dict(payload=x,result=self.fn(x))
