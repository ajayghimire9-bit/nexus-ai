"""Bounded domain adapters over existing Predicate/Move programs.

List primitives extend the typed domain vocabulary; no Python source, eval,
imports, files, tools, loops or unrestricted execution are accepted.
"""
import itertools
from .core import GRAMMAR, MOVES, Predicate, Move, valid_object
from nexus.evolution1.catalogue import digest
from .relations import Relation,RELATIONS

SCHEMAS=('predicate','list','motion','relation')
LIST_OPS=('reverse','sort','unique','increment','even')


def value(schema,x):
    if schema=='predicate':return valid_object(x)
    if schema=='relation':
        if type(x) is not dict or set(x)!={'first','second'}:raise ValueError('typed_object_pair')
        return {k:valid_object(v) for k,v in x.items()}
    if schema=='list':
        if type(x) is not list or len(x)>16 or any(type(v) is not int or not -64<=v<=64 for v in x):raise ValueError('bounded_integer_list')
        return list(x)
    if schema=='motion':
        if type(x) is not dict or set(x)!={'x','y'} or any(type(v) is not int or not 0<=v<6 for v in x.values()):raise ValueError('typed_grid_point')
        return dict(x)
    raise ValueError('skill_schema')


def program(p):
    if type(p) is not dict or p.get('schema') not in SCHEMAS:raise ValueError('typed_skill_program')
    schema=p['schema']
    if schema=='relation':
        if set(p)!={'schema','name'} or p['name'] not in [r.name for r in RELATIONS]:raise ValueError('finite_relation_program')
    elif schema=='predicate':
        if set(p)!={'schema','literals'} or type(p['literals']) is not list:raise ValueError('predicate_program')
        if any(type(a) is not list or len(a)!=3 or type(a[2]) is not bool for a in p['literals']):raise ValueError('typed_predicate_literal')
        if p['literals'] not in [[list(a) for a in item.literals] for item in GRAMMAR]:raise ValueError('finite_predicate_grammar')
    else:
        if set(p)!={'schema','ops'} or type(p['ops']) is not list or len(p['ops'])>2:raise ValueError('two_operator_program_cap')
        if any(type(op) is not str or op not in (LIST_OPS if schema=='list' else MOVES) for op in p['ops']):raise ValueError('vetted_skill_operator')
    return p


def input_key(schema,x):
    value(schema,x)
    # Predicate programs never read IDs or coordinates. Changing those must
    # not disguise a reused teaching/check example as a new semantic example.
    if schema=='relation':return digest({side:{k:x[side][k] for k in ('x','y','color','shape')} for side in ('first','second')})
    return digest({k:x[k] for k in ('color','shape','size')} if schema=='predicate' else x)


def canonical(p):
    program(p)
    if p['schema']=='list' and len(p['ops'])==2:
        a,b=p['ops']
        if a==b and a in ('sort','unique','even'):return dict(schema='list',ops=[a])
        if a==b=='reverse':return dict(schema='list',ops=[])
        commute=({'increment','reverse'},{'increment','sort'},{'increment','unique'},{'sort','unique'},{'unique','even'})
        if {a,b} in commute:return dict(schema='list',ops=sorted([a,b]))
    return p


def run(p,x):
    p=program(p);x=value(p['schema'],x)
    if p['schema']=='predicate':return Predicate(tuple(tuple(a) for a in p['literals'])).matches(x)
    if p['schema']=='relation':return Relation(p['name']).matches((x['first'],x['second']))
    for op in p['ops']:
        if p['schema']=='motion':
            dx,dy=MOVES[op];x={'x':x['x']+dx,'y':x['y']+dy}
            value('motion',x) # reject boundary crossings, including intermediates
        elif op=='reverse':x=x[::-1]
        elif op=='sort':x=sorted(x)
        elif op=='unique':x=list(dict.fromkeys(x))
        elif op=='increment':x=[v+1 for v in x]
        elif op=='even':x=[v for v in x if v%2==0]
    return value(p['schema'],x)


def catalogue(schema):
    if schema=='predicate':return [dict(schema=schema,literals=[list(a) for a in p.literals]) for p in GRAMMAR]
    if schema=='relation':return [dict(schema=schema,name=r.name) for r in RELATIONS]
    if schema not in SCHEMAS:raise ValueError('skill_schema')
    ops=LIST_OPS if schema=='list' else tuple(MOVES)
    result={}
    for n in range(3):
        for seq in itertools.product(ops,repeat=n):
            p=canonical(dict(schema=schema,ops=list(seq)));result[digest(p)]=p
    return list(result.values())


def labeled(schema,rows):
    if type(rows) is not list or not 1<=len(rows)<=8:raise ValueError('one_to_eight_labeled_examples')
    seen=set()
    for r in rows:
        if type(r) is not dict or set(r)!={'input','output'}:raise ValueError('input_output_example')
        value(schema,r['input'])
        if schema in ('predicate','relation'):
            if type(r['output']) is not bool:raise ValueError('boolean_concept_label')
        else:value(schema,r['output'])
        key=input_key(schema,r['input'])
        if key in seen:raise ValueError('duplicate_example_input')
        seen.add(key)
    return rows


def matches(p,rows):
    try:return all(run(p,r['input'])==r['output'] for r in rows)
    except ValueError:return False


def question(schema,candidates,observed):
    """Unlabeled disagreement only; never supplies its own target answer."""
    from .core import examples
    if len(candidates)<2:return None
    pools={'predicate':examples(),'list':[[],[0],[1],[2,1],[1,1,2],[3,0,2],[2,2,1]],
           'motion':[dict(x=x,y=y) for x in (1,2,3) for y in (1,2,3)],
           'relation':[dict(first=a,second=b) for a in examples() for b in examples()]}
    ranked=[]
    for x in pools[schema]:
        if input_key(schema,x) in observed:continue
        try:groups=[digest(run(p,x)) for p in candidates]
        except ValueError:continue
        counts=[groups.count(k) for k in set(groups)]
        if len(counts)>1:ranked.append((max(counts),digest(x),x))
    return min(ranked,key=lambda r:r[:2])[2] if ranked else None


def moves(p,reference):
    program(p)
    if p['schema']!='motion':raise ValueError('motion_skill_required')
    return tuple(Move(reference,op) for op in p['ops'])
