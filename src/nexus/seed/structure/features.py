"""Finite pure history predicates. Event codes are observed categories, not laws."""
import itertools
from contextvars import ContextVar
from .state import entity, token

WORK = ContextVar('structure_feature_work', default=None)


def validate(p, depth=0):
    if type(p) is not dict or depth > 1: raise ValueError('feature_depth')
    op = p.get('op')
    fields = {'exists': {'op', 'code'}, 'count2': {'op', 'code'}, 'last': {'op', 'code'},
              'after': {'op', 'first', 'second'}, 'attribute': {'op', 'name'},
              'relation': {'op', 'name'}, 'and': {'op', 'terms'}}
    if op not in fields or set(p) != fields[op]: raise ValueError('feature_grammar')
    for k in ('code', 'first', 'second'):
        if k in p and (type(p[k]) is not int or not 0 <= p[k] < 4): raise ValueError('observed_event_category')
    if op == 'after' and p['first'] == p['second']: raise ValueError('distinct_categories')
    if op in ('attribute', 'relation'): token(p['name'])
    if op == 'and':
        if type(p['terms']) is not list or len(p['terms']) != 2: raise ValueError('binary_conjunction')
        for t in p['terms']: validate(t, depth+1)
    return p


def evaluate(p, state, binding='object'):
    meter=WORK.get()
    if meter is not None:meter['feature_executions']=meter.get('feature_executions',0)+1
    validate(p); e = entity(state, binding)
    if e is None: return None
    op = p['op']; codes = [v['code'] for v in state.events if v['entity'] == binding]
    if op == 'attribute':
        x = e['attributes'].get(p['name'])
        return x if type(x) is bool else None
    if op == 'relation': return any(r['type'] == p['name'] and binding in r['arguments'] for r in state.relations)
    if op == 'and':
        values = [evaluate(t, state, binding) for t in p['terms']]
        return False if False in values else None if None in values else True
    if op == 'last': return (codes[-1] == p['code']) if codes else (None if state.truncated else False)
    if op == 'exists': result = p['code'] in codes
    elif op == 'count2': result = codes.count(p['code']) >= 2
    else:
        a = [i for i, c in enumerate(codes) if c == p['first']]
        b = [i for i, c in enumerate(codes) if c == p['second']]
        result = bool(a and (not b or a[-1] > b[-1]))
        # Most recent A after most recent B; A observed in retained suffix proves it.
        if result: return True
        if b: return False
    return result if result or not state.truncated else None


def complexity(p):
    validate(p)
    return 1 + sum(complexity(t) for t in p.get('terms', []))


def grammar():
    atoms = [dict(op=op, code=k) for op in ('exists', 'count2', 'last') for k in range(4)]
    atoms += [dict(op='after', first=a, second=b) for a, b in itertools.permutations(range(4), 2)]
    return atoms + [dict(op='and', terms=[a, b]) for a, b in itertools.combinations(atoms[:12], 2)]
