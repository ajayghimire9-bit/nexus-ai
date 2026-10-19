"""Versioned JSON codec for the existing fixture LearningCycle, not new memory.

No pickle, generated imports, executors, model loading or permissions. External
hash/provenance anchors are mandatory. This is reproducibility, not a secure
auditor: the fixture gate retains its explicitly public synthetic test key.
"""
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import random

from nexus.evolution1.catalogue import CATALOGUE_DIGEST, Variant, canonical
from nexus.evolution1.fixtures import Event, FixtureCost, Journal, verify_journal
from nexus.evolution1.promotion import FixturePromotionHarness, FixtureSnapshot
from nexus.evolution1.toy_loop import AdaptiveProposer, BY_ID, TEST_KEY
from nexus.evolution2.continual_state import TaskStream
from nexus.evolution2.generated_strategies import Strategy, StrategyGenerator
from nexus.evolution2.learning_cycle import LearningCycle
from nexus.meta.controller import EpsilonGreedyController

VERSION='fixture_cycle_json_v1'
CLASSES={c.__name__:c for c in (LearningCycle,TaskStream,StrategyGenerator,AdaptiveProposer,EpsilonGreedyController)}


def source_hashes():
    import inspect
    modules={inspect.getmodule(c) for c in (*CLASSES.values(),Journal,FixturePromotionHarness,Strategy)}
    return {**{m.__name__:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in modules},
        __name__:hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def fields():
    instances=(LearningCycle(),TaskStream(),StrategyGenerator(7),AdaptiveProposer(),EpsilonGreedyController())
    return {type(x).__name__:set(vars(x)) for x in instances}


def encode(x):
    if x is None or type(x) in (str,bool,int):return x
    if type(x) is float:
        if not math.isfinite(x):raise ValueError('finite_checkpoint_state')
        return x
    if type(x) is bytes:
        raise ValueError('no_credentials_in_cycle_checkpoint')
    if type(x) in (list,tuple,set):
        values=[encode(v) for v in x]
        if type(x) is set:values.sort(key=canonical)
        return {'type':type(x).__name__,'values':values}
    if type(x) is dict:
        return {'type':'dict','values':[[encode(k),encode(v)] for k,v in x.items()]}
    if type(x) is random.Random:return {'type':'rng','state':encode(x.getstate())}
    if type(x) is Variant:return {'type':'variant','id':x.fingerprint}
    if type(x) is Strategy:return {'type':'strategy','values':encode(dict(kind=x.kind,left=x.left,right=x.right,threshold=x.threshold))}
    if type(x) in (FixtureCost,FixtureSnapshot):return {'type':type(x).__name__,'values':encode(asdict(x))}
    if type(x) is Journal:
        return {'type':'journal','events':[asdict(e) for e in x.snapshot()]}
    if type(x) is FixturePromotionHarness:
        return {'type':'gate','values':encode({k:v for k,v in vars(x).items() if k!='_key'})}
    if type(x).__name__ in CLASSES and CLASSES[type(x).__name__] is type(x):
        return {'type':type(x).__name__,'values':encode(vars(x))}
    raise ValueError('unvetted_checkpoint_type')


def decode(x,schema):
    if x is None or type(x) in (str,bool,int,float):
        encode(x);return x
    if type(x) is not dict or type(x.get('type')) is not str:raise ValueError('typed_checkpoint_node')
    t=x['type']
    expected={'rng':{'type','state'},'variant':{'type','id'},'journal':{'type','events'}}.get(t,{'type','values'})
    if set(x)!=expected:raise ValueError('checkpoint_node_fields')
    if t in ('tuple','list','set'):
        values=[decode(v,schema) for v in x['values']]
        result={'tuple':tuple,'list':list,'set':set}[t](values)
        if len(result)!=len(values):raise ValueError('duplicate_checkpoint_entries')
        return result
    if t=='dict':
        result={}
        for k,v in x['values']:
            key=decode(k,schema)
            if key in result:raise ValueError('duplicate_checkpoint_keys')
            result[key]=decode(v,schema)
        return result
    if t=='rng':
        rng=random.Random();rng.setstate(decode(x['state'],schema));return rng
    if t=='variant':
        if x['id'] not in BY_ID:raise ValueError('unknown_vetted_variant')
        return BY_ID[x['id']]
    if t=='journal':
        events=tuple(Event(**v) for v in x['events']);verify_journal(events)
        journal=Journal();journal._events=events;return journal
    values=decode(x['values'],schema)
    if type(values) is not dict:raise ValueError('checkpoint_object_fields')
    if t=='strategy':return Strategy(**values)
    if t=='FixtureCost':return FixtureCost(**values)
    if t=='FixtureSnapshot':return FixtureSnapshot(**values)
    if t=='gate':
        if set(values)!={'_history','_archive','_events','_used_audits'} or not values['_history']:raise ValueError('fixture_gate_state')
        gate=FixturePromotionHarness(values['_history'][0],TEST_KEY);gate.__dict__.update(values);return gate
    if t not in CLASSES:raise ValueError('unvetted_checkpoint_type')
    wanted=schema[t]
    if t=='LearningCycle' and values.get('rule_frozen'):wanted=wanted|{'selected_rule'}
    if set(values)!=wanted:raise ValueError('checkpoint_object_schema')
    obj=object.__new__(CLASSES[t]);obj.__dict__.update(values);return obj


def validate(cycle):
    if type(cycle) is not LearningCycle or cycle.stream.pending is not None:raise ValueError('settled_cycle_checkpoint_required')
    if not cycle.charged.fits(cycle.cap):raise ValueError('checkpoint_budget_exceeded')
    if type(cycle.stream.remaining) is not int or cycle.stream.remaining<0 or cycle.stream.choices<0:raise ValueError('checkpoint_choice_budget')
    if cycle.archive.get(cycle.gate.incumbent.fingerprint)!=cycle.incumbent:raise ValueError('checkpoint_incumbent_binding')
    for journal in (cycle.journal,cycle.stream.journal,cycle.stream.generator.journal):verify_journal(journal.snapshot())
    if cycle.stream.generator.mutation_rule not in ('mean','recent','conservative'):raise ValueError('checkpoint_update_rule')


def save_cycle(cycle,path,*,provenance):
    """Exclusive create: old checkpoints are never overwritten. Return SHA256."""
    validate(cycle)
    if type(provenance) is not dict or not provenance:raise ValueError('explicit_checkpoint_provenance')
    payload=dict(version=VERSION,catalogue=CATALOGUE_DIGEST,source_hashes=source_hashes(),provenance=provenance,state=encode(cycle))
    raw=canonical(payload).encode()
    with Path(path).open('xb') as stream:
        stream.write(raw);stream.flush()
        import os
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def load_cycle(path,*,expected_sha256,provenance):
    """Requires externally recorded anchors; never restores an execution grant."""
    if Path(path).stat().st_size>5_000_000:raise ValueError('checkpoint_size_cap')
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('checkpoint_hash_mismatch')
    p=json.loads(raw)
    if set(p)!={'version','catalogue','source_hashes','provenance','state'} or p['version']!=VERSION or p['catalogue']!=CATALOGUE_DIGEST:raise ValueError('checkpoint_schema')
    if p['source_hashes']!=source_hashes() or p['provenance']!=provenance:raise ValueError('checkpoint_provenance_mismatch')
    cycle=decode(p['state'],fields());validate(cycle)
    return cycle
