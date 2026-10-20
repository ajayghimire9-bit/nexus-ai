"""Data-only executable expressions. No eval, imports, filesystem or simulator.

Unknown is None; it must never silently become a false observation. Functions
are typed JSON expression trees. All recursive calls share one instruction meter.
"""
import copy
import math
from nexus.seed import skill_programs as skills


def bounded(value, depth=0):
    if depth > 6: raise ValueError('value_depth')
    if value is None or type(value) is bool: return value
    if type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1e6: return value
    if type(value) is str and len(value) <= 128: return value
    if type(value) is list and len(value) <= 32:
        for v in value: bounded(v, depth+1)
        return value
    if type(value) is dict and len(value) <= 32 and all(type(k) is str and len(k) <= 32 for k in value):
        for v in value.values(): bounded(v, depth+1)
        return value
    raise ValueError('bounded_data_required')


FIELDS = {'literal': {'value'}, 'var': {'name'}, 'get': {'value','key'},
          'and': {'args'}, 'or': {'args'}, 'not': {'value'},
          'eq': {'left','right'}, 'lt': {'left','right'}, 'add': {'left','right'},
          'if': {'condition','then','else'}, 'let': {'name','value','body'},
          'some': {'items','name','body'}, 'every': {'items','name','body'},
          'map': {'items','name','body'}, 'count': {'value'},
          'repeat': {'times','initial','name','body'}, 'assert': {'condition','value'},
          'skill': {'program','value'}, 'call': {'name','value'},
          'before': {'events','first','second'}, 'after': {'events','first','second'}, 'while': {'events','first','second'},
          'until': {'events','first','second'}}


def validate(tree, depth=0, counter=None):
    counter = [0] if counter is None else counter
    counter[0] += 1
    if depth > 8 or counter[0] > 128: raise ValueError('expression_size')
    if type(tree) is not dict or tree.get('op') not in FIELDS: raise ValueError('typed_expression')
    op = tree['op']
    if set(tree) != FIELDS[op] | {'op'}: raise ValueError('expression_fields')
    for k,v in tree.items():
        if k == 'op': continue
        if k in ('name','key'):
            if type(v) is not str or not v.isidentifier() or len(v)>24: raise ValueError('variable_name')
        elif op == 'literal': bounded(v)
        elif k == 'program': skills.program(v)
        elif k == 'times':
            if type(v) is not int or not 0<=v<=16: raise ValueError('loop_cap')
        elif k == 'args':
            if type(v) is not list or not 1<=len(v)<=8: raise ValueError('logical_arity')
            for a in v: validate(a,depth+1,counter)
        else: validate(v,depth+1,counter)
    return tree


def execute(tree, inputs, functions=None, budget=512):
    validate(tree); bounded(inputs)
    if type(inputs) is not dict: raise ValueError('named_inputs_required')
    functions = {} if functions is None else functions
    if type(budget) is not int or not 1<=budget<=4096 or len(functions)>32: raise ValueError('execution_cap')
    for name, body in functions.items():
        if type(name) is not str or not name.isidentifier() or len(name)>24: raise ValueError('function_name')
        validate(body)
    used=0
    def boolean(v):
        if v is not None and type(v) is not bool: raise ValueError('boolean_required')
        return v
    def go(t, env, stack):
        nonlocal used
        used+=1
        if used>budget: raise ValueError('instruction_budget_exhausted')
        op=t['op']
        def ev(k): return go(t[k],env,stack)
        if op=='literal': out=copy.deepcopy(t['value'])
        elif op=='var': out=copy.deepcopy(env.get(t['name']))
        elif op=='get':
            obj=ev('value')
            if obj is not None and type(obj) is not dict: raise ValueError('record_required')
            out=None if obj is None else obj.get(t['key'])
        elif op in ('and','or'):
            vals=[boolean(go(a,env,stack)) for a in t['args']]
            out=(False if False in vals else None if None in vals else True) if op=='and' else (True if True in vals else None if None in vals else False)
        elif op=='not':
            v=boolean(ev('value'));out=None if v is None else not v
        elif op in ('eq','lt','add'):
            a,b=ev('left'),ev('right')
            if a is None or b is None: out=None
            elif op=='eq': out=type(a) is type(b) and a==b
            else:
                if type(a) not in (int,float) or type(b) not in (int,float): raise ValueError('numeric_required')
                out=a<b if op=='lt' else a+b
        elif op=='if':
            c=boolean(ev('condition'));out=None if c is None else ev('then' if c else 'else')
        elif op=='let': out=go(t['body'],dict(env,**{t['name']:ev('value')}),stack)
        elif op in ('map','some','every'):
            items=ev('items')
            if items is None: out=None
            else:
                if type(items) is not list: raise ValueError('list_required')
                vals=[go(t['body'],dict(env,**{t['name']:v}),stack) for v in items]
                if op=='map': out=vals
                else:
                    vals=[boolean(v) for v in vals]
                    out=(True if True in vals else None if None in vals else False) if op=='some' else (False if False in vals else None if None in vals else True)
        elif op=='count':
            v=ev('value')
            if v is not None and type(v) is not list: raise ValueError('list_required')
            out=None if v is None else len(v)
        elif op=='repeat':
            out=ev('initial')
            for _ in range(t['times']): out=go(t['body'],dict(env,**{t['name']:out}),stack)
        elif op=='assert':
            if boolean(ev('condition')) is not True: raise ValueError('assertion_failed_or_unknown')
            out=ev('value')
        elif op=='skill':
            value=ev('value')
            used+=len(t['program'].get('ops',[None]))
            if used>budget: raise ValueError('instruction_budget_exhausted')
            out=skills.run(t['program'],value)
        elif op=='call':
            name=t['name']
            if name not in functions or name in stack or len(stack)>=8: raise ValueError('unknown_or_recursive_function')
            out=go(functions[name],{'x':ev('value')},stack+(name,))
        else:
            events,a,b=ev('events'),ev('first'),ev('second')
            if events is None or a is None or b is None: out=None
            else:
                if type(events) is not list: raise ValueError('event_list_required')
                if op in ('before','after'):
                    ia=[i for i,v in enumerate(events) if v==a];ib=[i for i,v in enumerate(events) if v==b]
                    out=None if not ia or not ib else (max(ia)<max(ib) if op=='before' else max(ia)>max(ib))
                else:
                    if any(type(v) is not list for v in events): raise ValueError('time_slice_lists_required')
                    if op=='while': out=any(a in v and b in v for v in events)
                    else:
                        stops=[i for i,v in enumerate(events) if b in v]
                        out=None if not stops else all(a in v for v in events[:stops[0]])
        bounded(out);return out
    try:
        result=go(tree,copy.deepcopy(inputs),())
    except ValueError as error:
        error.instructions=used
        raise
    return dict(value=result,instructions=used,hypothetical=True)


def literal(v): return dict(op='literal',value=v)
def variable(n='x'): return dict(op='var',name=n)


def pipeline(ops):
    if type(ops) is not list or len(ops)>8: raise ValueError('pipeline_cap')
    out=variable()
    for op in ops:
        if op not in skills.LIST_OPS: raise ValueError('existing_list_operator_required')
        out=dict(op='skill',program=dict(schema='list',ops=[op]),value=out)
    validate(out);return out
