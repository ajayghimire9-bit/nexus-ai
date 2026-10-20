"""Observed graph with bounded history, explicit unknowns, and no simulator handle."""
from dataclasses import dataclass, field, asdict
import copy
import math
import re

TOKEN = re.compile(r'[a-zA-Z][a-zA-Z0-9_-]{0,31}\Z')
MAX_ENTITIES, MAX_EVENTS, MAX_RELATIONS = 32, 32, 64


def token(x):
    if type(x) is not str or not TOKEN.fullmatch(x): raise ValueError('typed_identifier')
    return x


def scalar(x):
    if x is None or type(x) is bool: return x
    if type(x) in (int, float) and math.isfinite(x) and abs(x) <= 1e6: return x
    raise ValueError('bounded_scalar_or_unknown')


def observation(x):
    if type(x) is not dict or set(x) != {'entities', 'relations', 'events', 'time', 'source'}:
        raise ValueError('observation_only_schema')
    if type(x['time']) is not int or not 0 <= x['time'] < 10**9: raise ValueError('observation_time')
    token(x['source'])
    if type(x['entities']) is not list or len(x['entities']) > MAX_ENTITIES: raise ValueError('entity_cap')
    ids = set()
    for e in x['entities']:
        if type(e) is not dict or set(e) != {'id', 'type', 'attributes'}: raise ValueError('entity_schema')
        token(e['id']); token(e['type'])
        if e['id'] in ids: raise ValueError('duplicate_entity')
        ids.add(e['id'])
        if type(e['attributes']) is not dict or len(e['attributes']) > 8: raise ValueError('attribute_cap')
        for k, v in e['attributes'].items(): token(k); scalar(v)
    if type(x['relations']) is not list or len(x['relations']) > MAX_RELATIONS: raise ValueError('relation_cap')
    for r in x['relations']:
        if type(r) is not dict or set(r) != {'type', 'arguments'}: raise ValueError('relation_schema')
        token(r['type'])
        if type(r['arguments']) is not list or not 1 <= len(r['arguments']) <= 3 or any(a not in ids for a in r['arguments']): raise ValueError('typed_relation_bindings')
    if type(x['events']) is not list or len(x['events']) > MAX_EVENTS: raise ValueError('event_cap')
    for e in x['events']:
        if type(e) is not dict or set(e) != {'code', 'entity', 'time'}: raise ValueError('event_schema')
        if type(e['code']) is not int or not 0 <= e['code'] < 4 or e['entity'] not in ids or type(e['time']) is not int or not 0 <= e['time'] <= x['time']: raise ValueError('typed_observed_event')
    times = [e['time'] for e in x['events']]
    if times != sorted(set(times)): raise ValueError('event_time_order')
    return copy.deepcopy(x)


@dataclass
class State:
    episode: str = 'initial'
    time: int = -1
    current: list = field(default_factory=list)
    remembered: dict = field(default_factory=dict)
    relations: list = field(default_factory=list)
    events: list = field(default_factory=list)
    truncated: bool = False
    provenance: list = field(default_factory=list)

    def wire(self): return copy.deepcopy(asdict(self))


def observe(state, raw):
    x = observation(raw)
    if x['time'] <= state.time: raise ValueError('strict_observation_clock')
    if state.events and x['events'] and x['events'][0]['time'] <= state.events[-1]['time']: raise ValueError('duplicate_or_backdated_event')
    out = copy.deepcopy(state)
    out.time = x['time']; out.current = x['entities']; out.relations = x['relations']
    for e in x['entities']:
        previous=out.remembered.get(e['id'])
        if previous and previous['entity']['type']!=e['type']:raise ValueError('entity_identity_type_changed')
        out.remembered[e['id']] = dict(entity=e, observed_at=x['time'], source=x['source'])
    if len(out.remembered) > MAX_ENTITIES: raise ValueError('remembered_entity_cap')
    history = out.events + [dict(e, source=x['source']) for e in x['events']]
    out.truncated |= len(history) > MAX_EVENTS
    out.events = history[-MAX_EVENTS:]
    out.provenance = (out.provenance + [dict(time=x['time'], source=x['source'])])[-MAX_EVENTS:]
    return out


def entity(state, binding):
    return next((e for e in state.current if e['id'] == binding), None)
