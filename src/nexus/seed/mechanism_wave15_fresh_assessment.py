"""Wave15 fresh definitions, authored only AFTER freeze 4810ae6.

Evaluator-owned functions and hidden rows. No learner imports this module.
The runner locks each program/status before opening private rows. No outcomes
from this suite may alter frozen Phase1 code or these definitions.
"""
from __future__ import annotations
import random


def left_cycle(x):
    return x[1:]+x[:1]


def base_odd_tail(x):
    return x[1:] if len(x)%2 else x


def base_even_init(x):
    return x[:-1] if len(x)%2==0 else x


def base_even_new_prefix(x):
    return ('=',)+x if len(x)%2==0 else x


def relational_three(x):
    return ('|',)+x if len(x)==3 else x


def relational_four(x):
    return x[1:] if len(x)==4 else x


def first_embedded(x):
    return left_cycle(x)+('=',) if len(x)%2 else x


def second_embedded(x):
    return (':',)+left_cycle(x) if len(x)%2 else x


def third_embedded(x):
    return left_cycle(x)+('|',) if len(x)%2 else x


def hierarchy_first(x):
    return (':',)+left_cycle(x)+('|',) if len(x)%2 else x


def hierarchy_reuse(x):
    return ('=',)+left_cycle(x)+('|',) if len(x)%2 else x


def branch_cycle_reverse(x):
    return left_cycle(x) if len(x)%2 else x[::-1]


def branch_wrapped_cycle(x):
    return left_cycle(x)+('|',) if len(x)%2 else x[::-1]


def palindrome_tail(x):
    return x[1:] if x==x[::-1] else x


def distractor_even_two_init(x):
    return x[:-2] if len(x)%2==0 else x


def distractor_odd_two_tail(x):
    return x[2:] if len(x)%2 else x


def palindrome_init(x):
    return x[:-1] if x==x[::-1] else x


def interleaved_separator(x):
    output=[]
    for token in x:
        output.extend((token,'/'))
    return tuple(output)


def fresh_cases():
    # Introduction + two archive distractors + interleaved base task + reuse.
    base='w15f_base_and_dynamic_literals'
    analogy='w15f_cross_domain_analogy'
    subtree='w15f_unassisted_subtree_and_L2'
    piece='w15f_piecewise_multibranch'
    archive='w15f_spurious_distractor_and_delayed_archive'
    oog='w15f_true_oog_and_ambiguous'
    return [
        ('w15f_odd_tail',base_odd_tail,base,False,'unique'),
        ('w15f_even_init',base_even_init,base,False,'unique'),
        ('w15f_length_three_prefix',relational_three,analogy,False,'unique'),
        ('w15f_length_four_tail',relational_four,analogy,False,'unique'),
        ('w15f_leftcycle_suffix',first_embedded,subtree,False,'unique'),
        ('w15f_leftcycle_prefix',second_embedded,subtree,False,'unique'),
        ('w15f_leftcycle_third',third_embedded,subtree,False,'unique'),
        ('w15f_nested_first',hierarchy_first,subtree,False,'unique'),
        ('w15f_nested_reuse',hierarchy_reuse,subtree,False,'unique'),
        ('w15f_leftcycle_even_reverse',branch_cycle_reverse,piece,False,'unique'),
        ('w15f_leftcycle_wrapped_reverse',branch_wrapped_cycle,piece,False,'unique'),
        ('w15f_palindrome_tail_intro',palindrome_tail,archive,True,'unique'),
        ('w15f_intervening_even_prefix',base_even_new_prefix,base,False,'unique'),
        ('w15f_even_two_init_distractor',distractor_even_two_init,archive,False,'unique'),
        ('w15f_odd_two_tail_distractor',distractor_odd_two_tail,archive,False,'unique'),
        ('w15f_palindrome_init_reuse',palindrome_init,archive,True,'unique'),
        ('w15f_interleaved_separator_oog',interleaved_separator,oog,False,'abstain'),
        ('w15f_guard_and_channel_ambiguity',base_odd_tail,oog,False,'ambiguous'),
    ]


class FreshWorld:
    def __init__(self,fn,seed=0,pal=False,ambiguous=False):
        names=['amber','indigo','copper','ivory','jade','violet','ochre','azure']
        random.Random(31000+seed).shuffle(names)
        a,b,c,d,e,f,g,h=names
        self.fn=fn;self.ambiguous=ambiguous
        self.locked=False;self.private_opened=False;self.calls=0
        self.public_map=dict(alpha=(),beta=(a,b,c),gamma=(a,b,c,d),delta=(b,c,d,e,f))
        self.epsilon=(c,d,e,f,g,h)
        self.extra_public_slots={
            'probe0':(b,c,d),'probe1':(b,c,d,e),
            'probe2':(c,d,e,f,g),'probe3':(a,c,d,e,f,g),
            'probe4':(d,e,f),'probe5':(c,e,f,g),
            'probe6':(a,b,d,f,h),'probe7':(a,b,c,e,g,h),
            'remaining0':(e,f,g),'remaining1':(a,c,f,h),
            'confirm_0':(e,g,h),'confirm_1':(b,d,f,h),
            'confirm_2':(a,c,e,g,h),'confirm_3':(a,b,c,d,g,h)}
        if pal:
            self.public_map=dict(alpha=(),beta=(a,),gamma=(a,b,a),delta=(a,b,c,a))
            self.epsilon=(a,b,c,d)
            self.extra_public_slots.update({
                'probe0':(b,c,b),'probe1':(a,b,c,b,a),
                'probe2':(b,c,d,b),'probe3':(a,c),
                'probe4':(d,e,d),'probe5':(a,b,c),
                'probe6':(e,),'probe7':(b,d,e,b),
                'remaining0':(c,d,c),'remaining1':(a,b,c,d),
                'confirm_0':(f,g,f),'confirm_1':(a,c,d,a),
                'confirm_2':(c,d,e,d,c),'confirm_3':(b,e,f,g)})
        if ambiguous:
            # Odd parity and LEN_EQ(3) agree on every public row. A duplicate
            # invariant result channel also makes interface identification
            # ambiguous. This tests refusal, not proof of semantic uncertainty.
            self.public_map=dict(alpha=(),beta=(a,b,c),gamma=(a,b,c,d),delta=(b,c,d))
            self.epsilon=(c,d,e,f)
            self.extra_public_slots={
                'probe0':(b,c,d),'probe1':(b,c,d,e),
                'probe2':(d,e,f),'probe3':(c,e,f,g),
                'probe4':(e,f,g),'probe5':(a,c,f,h),
                'probe6':(f,g,h),'probe7':(a,b,e,h),
                'confirm_0':(a,c,e),'confirm_1':(b,d,f,h)}
        self.private_map=dict(alpha=(f,g,h),beta=(e,f,g,h),
                              gamma=(a,d,f,g,h),delta=(b,c,e,f,g,h))
        if pal:self.private_map=dict(alpha=(h,),beta=(g,h,g),gamma=(a,f,g,a),delta=(b,c,d,e))

    def public_read(self,slot):
        self.calls+=1
        x=self.epsilon if slot=='epsilon' else self.public_map.get(slot,self.extra_public_slots.get(slot))
        result=self.fn(x)
        row=dict(payload=x,result=result,echo=x,stamp=self.calls,tick=self.calls,slot=slot)
        if self.ambiguous:row['alias']=result
        return row

    def lock(self):
        self.locked=True

    def private_read(self,slot):
        if not self.locked:raise RuntimeError('private_before_lock')
        self.private_opened=True
        x=self.private_map[slot]
        return dict(payload=x,result=self.fn(x))
