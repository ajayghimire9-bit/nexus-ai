"""Vetted graph IR, explicit applicability, and bounded composition.

The legacy skill adapter delegates unchanged to skill_programs.run. Graph IR
adds only typed scalar effects on a bound observed entity; supplied laws are
never marked discovered. No code strings, simulator calls or hidden outcomes.
"""
import copy
import time
from collections import deque
from nexus.evolution1.catalogue import digest
from .state import entity, scalar, token
from .features import validate, evaluate


def mechanism(p):
    fields = {'id', 'entity_type', 'precondition', 'effects', 'origin', 'evidence', 'known_failures', 'uncertainty'}
    if type(p) is not dict or set(p) != fields: raise ValueError('mechanism_schema')
    token(p['id']); token(p['entity_type'])
    if p['origin'] not in ('supplied', 'source_learned'): raise ValueError('mechanism_origin')
    if p['precondition'] is not None: validate(p['precondition'])
    if type(p['effects']) is not list or not 1 <= len(p['effects']) <= 8: raise ValueError('instruction_cap')
    for e in p['effects']:
        if type(e) is not dict or set(e) != {'op', 'attribute', 'value', 'type'} or e['op'] not in ('set', 'add'): raise ValueError('typed_graph_instruction')
        token(e['attribute']); scalar(e['value'])
        if e['type'] not in ('boolean', 'number') or (e['type'] == 'boolean' and (type(e['value']) is not bool or e['op'] != 'set')) or (e['type'] == 'number' and type(e['value']) not in (float, int)): raise ValueError('effect_type')
    for field in ('evidence', 'known_failures'):
        if type(p[field]) is not list or len(p[field]) > 64 or any(type(v) is not str or len(v) > 128 for v in p[field]): raise ValueError('evidence_bounds')
    if p['origin'] == 'source_learned' and not p['evidence']: raise ValueError('learned_requires_evidence')
    u = p['uncertainty']
    if type(u) not in (float, int) or not 0 <= u <= 1: raise ValueError('uncertainty_probability')
    return copy.deepcopy(p)


def execute(p, state, binding, meter):
    p = mechanism(p); meter['retrieval_tests'] = meter.get('retrieval_tests', 0)+1
    obj = entity(state, binding)
    if obj is None or obj['type'] != p['entity_type']: return dict(status='failed_precondition', state=state)
    condition = True if p['precondition'] is None else evaluate(p['precondition'], state, binding)
    if condition is None: return dict(status='unknown', state=state)
    if not condition: return dict(status='failed_precondition', state=state)
    out = copy.deepcopy(state); target = entity(out, binding)
    for instruction in p['effects']:
        meter['instructions'] = meter.get('instructions', 0)+1
        name = instruction['attribute']; old = target['attributes'].get(name)
        if instruction['op'] == 'add':
            if type(old) not in (int, float): return dict(status='unknown', state=state)
            new = scalar(old+instruction['value'])
        else: new = instruction['value']
        if name not in target['attributes'] or (old is not None and type(old) is bool and instruction['type'] != 'boolean') or (old is not None and type(old) in (int, float) and instruction['type'] != 'number'): return dict(status='type_mismatch', state=state)
        target['attributes'][name] = new
    return dict(status='predicted', state=out, uncertainty=p['uncertainty'], hypothetical=True)


def run_skill(program, x):
    from nexus.seed.skill_programs import run
    return run(program, x)


def plan(state, mechanisms, binding, goal, *, depth=3, nodes=64, max_instructions=512, timeout=.05):
    """Small graph backend: grid-only to_cell cannot express typed scalar effects."""
    if type(depth) is not int or not 0 <= depth <= 4 or type(nodes) is not int or not 1 <= nodes <= 128 or type(max_instructions) is not int or not 1 <= max_instructions <= 1024 or type(timeout) not in (int, float) or not 0 <= timeout <= .5: raise ValueError('planning_caps')
    validate(goal)
    if len(mechanisms) > 16: raise ValueError('branch_cap')
    mechanisms = sorted([mechanism(p) for p in mechanisms], key=lambda p:p['id'])
    meter = dict(retrieval_tests=0, instructions=0, expanded=0, rejected=0)
    queue = deque([(state, [])]); seen = {digest(state.wire())}; start = time.monotonic()
    while queue:
        if time.monotonic()-start >= timeout: return dict(status='timeout', path=None, costs=meter)
        current, path = queue.popleft()
        if evaluate(goal, current, binding) is True: return dict(status='planned', path=path, costs=meter, hypothetical=True)
        if len(path) >= depth: continue
        if meter['expanded'] >= nodes: return dict(status='node_cap', path=None, costs=meter)
        meter['expanded'] += 1
        for p in mechanisms:
            if meter['instructions']+len(p['effects']) > max_instructions: return dict(status='instruction_cap', path=None, costs=meter)
            result = execute(p, current, binding, meter)
            if result['status'] != 'predicted': meter['rejected'] += 1; continue
            child = result['state']; key = digest(child.wire())
            if key not in seen: seen.add(key); queue.append((child, path+[p['id']]))
    return dict(status='no_known_plan', path=None, costs=meter)
