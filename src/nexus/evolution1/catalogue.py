"""Closed planning-configuration vocabulary and analytic work bounds.

No planner operators, models, environments or executable source are loaded.
The catalogue digest identifies this schema, not a vetted executable operator.
"""
from dataclasses import dataclass
from enum import Enum
import hashlib
import itertools
import json


class ContractError(ValueError):
    pass


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def positive_int(value,maximum=10**12):
    if type(value) is not int or not 0<value<=maximum:
        raise ContractError('invalid_integer')
    return value


class Rule(Enum):
    FLAT='flat'
    SUCCESSOR='successor'


class Generator(Enum):
    IID='iid'
    BALANCED='balanced_first_action'


HORIZONS=(4,8,16)
CATALOGUE_DIGEST=digest(dict(version='evolution1-fixture-catalogue-v1',
    rules=[r.value for r in Rule],generators=[g.value for g in Generator],
    horizons=HORIZONS,cost_semantics='flat_NH_or_A_plus_ANH_v1'))


@dataclass(frozen=True)
class Variant:
    rule: Rule
    generator: Generator
    horizon: int

    def __post_init__(self):
        if type(self.rule) is not Rule or type(self.generator) is not Generator:
            raise ContractError('unknown_operator')
        if type(self.horizon) is not int or self.horizon not in HORIZONS:
            raise ContractError('invalid_horizon')

    def payload(self):
        return dict(catalogue=CATALOGUE_DIGEST,rule=self.rule.value,
                    generator=self.generator.value,horizon=self.horizon)

    def wire(self):return canonical(self.payload())

    @property
    def fingerprint(self):return digest(self.payload())


def catalogue():
    return tuple(Variant(r,g,h) for r,g,h in itertools.product(Rule,Generator,HORIZONS))


def _unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ContractError('duplicate_field')
        out[k]=v
    return out


def _nonfinite(_):raise ContractError('nonfinite_json')


def parse_proposal(wire):
    if type(wire) is not str or len(wire)>1024:raise ContractError('invalid_message')
    try:data=json.loads(wire,object_pairs_hook=_unique,parse_constant=_nonfinite)
    except (ValueError,TypeError,RecursionError) as exc:raise ContractError('invalid_json') from exc
    if type(data) is not dict or set(data)!={'catalogue','rule','generator','horizon'}:
        raise ContractError('invalid_fields')
    if data['catalogue']!=CATALOGUE_DIGEST:raise ContractError('catalogue_mismatch')
    if type(data['rule']) is not str or type(data['generator']) is not str:raise ContractError('invalid_operator')
    try:return Variant(Rule(data['rule']),Generator(data['generator']),data['horizon'])
    except (ValueError,TypeError) as exc:raise ContractError('invalid_variant') from exc


@dataclass(frozen=True)
class PlanBound:
    candidates_per_root: int
    imagined_per_decision: int


def plan_bound(variant,n_actions,imagined_cap):
    if type(variant) is not Variant:raise ContractError('invalid_variant')
    positive_int(n_actions,16);positive_int(imagined_cap,1536)
    h=variant.horizon
    if variant.rule is Rule.FLAT:
        n=imagined_cap//h;used=n*h
    else:
        n=(imagined_cap-n_actions)//(n_actions*h)
        used=n_actions+n_actions*n*h
    if n<1 or not 0<used<=imagined_cap:raise ContractError('infeasible_plan')
    return PlanBound(n,used)
