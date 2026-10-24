"""Post-4f4deaa authored evaluator fixtures. Not imported by the inner learner.

Three vocabulary permutations of new rules, not independent neural models.
Independent Python fixture oracles are checked against explicit target ASTs.
"""
from __future__ import annotations
import random

from .wave17_exact_cache_boundary_learner import (
    VarNode,ConstNode,PrimOpNode,PiecewiseBranch,PiecewiseProgramAST,TypeTag,
    FilterSeqNode,MapReplaceTokNode,DedupAdjSeqNode,HasTokNode,StateRecord,
    canonical_input,eval_expr_ast)

X=VarNode();IX=VarNode(TypeTag.INT)
REMOVE='vexel';CANCEL='cancel=ves';COMMIT='commit=nov';INTENT='intent=nuro'


def tok(value):return ConstNode(value,TypeTag.TOK)


def unary(op,node=X):return PrimOpNode(op,(node,),TypeTag.SEQ)


def pre(value,node=X):return PrimOpNode('PREPEND_TOK',(tok(value),node),TypeTag.SEQ)


def post(node,value):return PrimOpNode('APPEND_TOK',(node,tok(value)),TypeTag.SEQ)


def parity(value,kind=TypeTag.SEQ):
    scalar=IX if kind==TypeTag.INT else PrimOpNode('LEN',(X,),TypeTag.INT)
    return PrimOpNode('INT_EQ',(PrimOpNode('MOD2',(scalar,),TypeTag.INT),ConstNode(value,TypeTag.INT)),TypeTag.BOOL)


def single(guard,transform,kind=TypeTag.SEQ):
    return PiecewiseProgramAST((PiecewiseBranch(guard,transform),),VarNode(kind))


def vocabulary(seed):
    values=['rivu','tova','zemi','kesh','nulor','paxi','drel','suvu','qem','tiru','gavo','lenk']
    random.Random(7810+seed).shuffle(values)
    return values


def sequences(seed):
    a,b,c,d,e,f=vocabulary(seed)[:6];m=REMOVE
    return [
        (a,m,b,c,d),(b,c,m,a,m,d,e),(a,b,m,c),(m,a,b,m,c,d),
        (c,d,m,b,a),(a,b,m,c,d,e,a),(a,m,b,c,d,e,a,b),(a,b,m,c,d,a),
        (a,b,c,d,m),(b,m,c,a,d,m,e),(c,m,d,a,b,c),(a,c,m,b,d),
        (b,a,c,m,d,a,m),(c,b,a,m,d,e),(a,b,m,c,e,d,a),(c,m,b,a),
        (a,m,d,c,b,e,m),(b,c,m,d,a,e,a,b),(d,a,m,b,c),(e,m,a,b,c,d),
        (f,a,m,c,b,d,e),(b,m,f,a,c,d),(c,f,b,a,m),(d,m,c,f,b,a,e)]


def private_sequences(seed):
    a,b,c,d,e,f=vocabulary(seed)[:6]
    return [(f,REMOVE,e,d,c,b,a),(a,e,REMOVE,f,b,c),
        (b,c,e,f,REMOVE),(e,f,REMOVE,a,b,c,d,a)]


def state_inputs(seed,cancellation=True):
    words=vocabulary(seed);rows=[]
    for i in range(24):
        fields=[('intent',words[(i//2)%6]),('slot',words[(i+2)%6]),('meta',words[(i+4)%6])]
        if cancellation and i%2:
            fields.append(('cancel','ves'))
            if i%8==1:fields.append(('cancel','ves'))
        else:fields.append(('state','hold'))
        rows.append(StateRecord(tuple(fields)))
    return rows


def piece_inputs(seed):
    a,b,c,d,e,f=vocabulary(seed)[:6];m=REMOVE
    even=[(a,m,b,c),(b,c,m,a,d,e),(a,m,b,c,d,e,a,b),
        (a,b,m,m,b,a),(e,m,c,f,b,a),(a,b,m,b,a,b)]
    pal=[(a,b,m,b,a),(b,a,m,a,b),(a,c,b,m,b,c,a),
        (e,d,m,d,e),(f,a,m,a,f),(c,e,a,m,a,e,c)]
    default=[(a,m,b,c,a),(c,m,d,a,b),(d,a,b,m,c),
        (e,m,a,f,b),(b,c,m,d,a,e,f),(f,m,b,a,c)]
    # Initial8: three effective branch0, three branch1, two default rows.
    order=[even[0],pal[0],default[0],even[1],pal[1],default[1],even[2],pal[2]]
    order+=even[3:]+pal[3:]+default[2:]
    confirmations=[(a,f,m,b),(f,b,a,m,c,d),(d,f,m,f,d),
        (b,e,c,m,c,e,b),(e,f,m,a,b),(b,a,f,m,c)]
    return order+confirmations


def core_oracle(value):
    tail=value[1:];rotated=tail[-1:]+tail[:-1]
    return tuple(t for t in rotated if t!=REMOVE)


def dedup_oracle(value):
    return tuple(v for i,v in enumerate(value) if i==0 or value[i-1]!=v)


def base_dedup(value):return dedup_oracle(value)+('bulo',) if len(value)%2==0 else value


def base_replace(value):return tuple('ravu' if t==REMOVE else t for t in value) if len(value)%2 else value


def base_boundary(value):
    if len(value)<5:return value
    swapped=value[-1:]+value[1:-1]+value[:1] if len(value)>1 else value
    return ('drax',)+swapped


def math_double(value):return value*2 if value%2==0 else value


def math_shift(value):return value-4 if value%2 else value


def comp_first(value):return ('nemi',)+core_oracle(value) if len(value)%2 else value


def comp_second(value):return core_oracle(value)+('yavo',) if len(value)%2 else value


def comp_third(value):return ('porel',)+core_oracle(value) if len(value)%2 else value


def comp_fourth(value):return (('porel',)+core_oracle(value))[::-1] if len(value)%2 else value


def comp_fifth(value):return (('porel',)+core_oracle(value))[::-1][:-1] if len(value)%2 else value


def piece_first(value):
    if len(value)%2==0:return core_oracle(value)
    return value+('sora',) if value==value[::-1] else value


def piece_second(value):
    if len(value)%2==0:return core_oracle(value)[::-1]
    return ('fenu',)+value if value==value[::-1] else value


def state_intro(value):
    value=canonical_input(value)
    return tuple(t for t in value if t!=CANCEL)+(COMMIT,) if CANCEL in value else value


def state_reuse(value):
    value=canonical_input(value)
    return ('audit=vek',)+state_intro(value) if CANCEL in value else value


def state_reverse(value):
    value=canonical_input(value)
    return value[::-1] if len(value)%2 else value


def state_tail(value):
    value=canonical_input(value)
    return value[1:] if len(value)%2==0 else value


def sorted_outside(value):return tuple(sorted(value))


def ambiguous_oracle(value):
    return ('reply=zun',)+tuple(t for t in value if t!=INTENT) if INTENT in value else value


def make_spec(identifier,split,program,oracle,input_factory=sequences,private_factory=private_sequences,
              gold='unique',confirm_count=2,min_branch_support=2):
    seeds={}
    for seed in (0,1,2):
        public=input_factory(seed);private=private_factory(seed)
        seeds[seed]=dict(public=[(x,oracle(x)) for x in public],
            private=[(x,oracle(x)) for x in private],confirm_count=confirm_count)
    return dict(id=identifier,split=split,gold=gold,target_ast=program.to_dict() if program else None,
        seeds=seeds,min_branch_support=min_branch_support)


def integer_inputs(seed):return list(range(-9,15))


def integer_private(seed):return [-15,-12,17,20]


def other_states(seed):
    rows=[]
    for i,state in enumerate(state_inputs(seed,False)):
        x=canonical_input(state)
        rows.append(x+tuple('extra%d=ves'%j for j in range(i%4)))
    return rows


def state_private(seed):
    words=vocabulary(seed)[6:10]
    return [StateRecord((('cancel','ves'),('intent',words[0]),('slot',words[1]),('meta',words[2]))),
        StateRecord((('state','hold'),('intent',words[1]),('slot',words[2]),('meta',words[3]))),
        StateRecord((('cancel','ves'),('cancel','ves'),('intent',words[2]),('slot',words[3]),('meta',words[0]))),
        StateRecord((('state','hold'),('intent',words[3]),('slot',words[0]),('meta',words[1])))]


def other_state_private(seed):
    return [canonical_input(x) for x in state_private(seed)]


def outside_inputs(seed):
    rng=random.Random(19871+seed);words=vocabulary(seed);rows=[]
    for i in range(24):
        x=list(words);rng.shuffle(x);rows.append(tuple(x[:6+i%6]))
    return rows


def outside_private(seed):return outside_inputs(seed+31)[:4]


def intent_inputs(seed):
    a,b,c,d,e=vocabulary(seed)[:5];rows=[]
    for i in range(12):
        # On the public bank, membership and length5 intentionally coincide.
        if i%2:rows.append((a,INTENT,b,INTENT,c))
        else:rows.append((b,INTENT,c,d,a))
        rows.append((e,b,c,d))
    return rows


def intent_private(seed):
    a,b,c,d,e=vocabulary(seed)[:5]
    return [(a,b,c,d,e),(a,b,INTENT,c,d,e,a),(d,c,b,a)]


def fresh_specs():
    core=FilterSeqNode(unary('ROT_RIGHT',unary('TAIL')),tok(REMOVE))
    odd=parity(1);even=parity(0)
    pal=PrimOpNode('SEQ_EQ',(X,unary('REVERSE')),TypeTag.BOOL)
    state_guard=HasTokNode(tok(CANCEL),X)
    state_transform=post(FilterSeqNode(X,tok(CANCEL)),COMMIT)
    first=pre('nemi',core);second=post(core,'yavo');third=pre('porel',core)
    fourth=unary('REVERSE',third);fifth=unary('DROP_LAST',fourth)
    a='w17f_base_and_dynamic_literals';b='w17f_cross_domain_analogy'
    c='w17f_unassisted_subtree_and_L2';d='w17f_piecewise_multibranch'
    e='w17f_spurious_distractor_and_delayed_archive';f='w17f_true_oog_and_ambiguous'
    p1=PiecewiseProgramAST((PiecewiseBranch(even,core),PiecewiseBranch(pal,post(X,'sora'))),X)
    p2=PiecewiseProgramAST((PiecewiseBranch(even,unary('REVERSE',core)),PiecewiseBranch(pal,pre('fenu',X))),X)
    threshold=PrimOpNode('INT_GE',(PrimOpNode('LEN',(X,),TypeTag.INT),ConstNode(5,TypeTag.INT)),TypeTag.BOOL)
    specs=[
        make_spec('w17f_even_stream_stamp',a,single(even,post(DedupAdjSeqNode(X),'bulo')),base_dedup),
        make_spec('w17f_odd_token_rewrite',a,single(odd,MapReplaceTokNode(X,tok(REMOVE),tok('ravu'))),base_replace),
        make_spec('w17f_even_integer_scaling',b,single(parity(0,TypeTag.INT),PrimOpNode('INT_MUL',(IX,ConstNode(2,TypeTag.INT)),TypeTag.INT),TypeTag.INT),math_double,integer_inputs,integer_private),
        make_spec('w17f_odd_integer_shift',b,single(parity(1,TypeTag.INT),PrimOpNode('INT_SUB',(IX,ConstNode(4,TypeTag.INT)),TypeTag.INT),TypeTag.INT),math_shift,integer_inputs,integer_private),
        make_spec('w17f_loop_prefix_introduction',c,single(odd,first),comp_first),
        make_spec('w17f_loop_suffix_introduction',c,single(odd,second),comp_second),
        make_spec('w17f_new_loop_wrapper',c,single(odd,third),comp_third),
        make_spec('w17f_hierarchical_reversal',c,single(odd,fourth),comp_fourth),
        make_spec('w17f_hierarchical_projection',c,single(odd,fifth),comp_fifth),
        make_spec('w17f_priority_loop_commit',d,p1,piece_first,piece_inputs,private_sequences,confirm_count=6,min_branch_support=4),
        make_spec('w17f_priority_loop_involution',d,p2,piece_second,piece_inputs,private_sequences,confirm_count=6,min_branch_support=4),
        make_spec('w17f_state_cancel_introduction',e,single(state_guard,state_transform),state_intro,state_inputs,state_private),
        make_spec('w17f_boundary_slot_commit',a,single(threshold,pre('drax',unary('SWAP_ENDS'))),base_boundary),
        make_spec('w17f_dialogue_order_distractor',e,single(odd,unary('REVERSE')),state_reverse,other_states,other_state_private),
        make_spec('w17f_dialogue_head_distractor',e,single(even,unary('TAIL')),state_tail,other_states,other_state_private),
        make_spec('w17f_state_delayed_audit',e,single(state_guard,pre('audit=vek',state_transform)),state_reuse,state_inputs,state_private),
        make_spec('w17f_outside_lexicographic_order',f,None,sorted_outside,outside_inputs,outside_private,gold='abstain'),
        make_spec('w17f_underspecified_intent',f,None,ambiguous_oracle,intent_inputs,intent_private,gold='ambiguous')]
    intent_transform=pre('reply=zun',FilterSeqNode(X,tok(INTENT)))
    intent_guard=HasTokNode(tok(INTENT),X)
    length_guard=PrimOpNode('INT_EQ',(PrimOpNode('LEN',(X,),TypeTag.INT),ConstNode(5,TypeTag.INT)),TypeTag.BOOL)
    specs[-1]['ambiguous_witnesses']=[single(intent_guard,intent_transform).to_dict(),single(length_guard,intent_transform).to_dict()]
    # Evaluator-only, no learner invocation: enforce the registered construction.
    assert core.ast_nodes()==5 and [first.ast_nodes(),second.ast_nodes(),third.ast_nodes()]==[7,7,7]
    assert fourth.ast_nodes()==8 and fifth.ast_nodes()==9
    for item in specs[9:11]:
        program=p1 if item['id']=='w17f_priority_loop_commit' else p2
        for part in item['seeds'].values():
            default_count=0;confirm=[0,0,0]
            for index,(x,y) in enumerate(part['public']):
                branch=2
                for j,bn in enumerate(program.branches):
                    if eval_expr_ast(bn.guard,x):branch=j;break
                default_count+=int(branch==2)
                if index>=len(part['public'])-6:confirm[branch]+=1
            assert default_count>=4 and confirm==[2,2,2]
    assert len(specs)==18 and len({s['id'] for s in specs})==18
    return specs
