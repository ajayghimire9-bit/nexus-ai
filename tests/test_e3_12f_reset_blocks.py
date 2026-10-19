"""Authored observations/rewards only; no simulators, trained models or audits."""
from copy import deepcopy
import json
import random
from pathlib import Path
import pytest
from nexus.evolution2 import reset_blocks as blocks

ROOT = Path(__file__).resolve().parents[1]


def observations(family='pendulum'):
    # Four exactly duplicated pairs make the optimum unambiguous and known.
    n = len(blocks.SCALES[family])
    return [dict(reset_id=i, observation=[float(i//2)/4]+[0.]*(n-1)) for i in range(8)]


def panel(plan):
    return [dict(reset_id=int(i), paths={k: {'return': 3. if k == 'switch' else 1., 'cpu_s': .1}
                                       for k in kinds}) for i, kinds in blocks.required_paths(plan).items()]


@pytest.mark.parametrize('family', ['pendulum', 'acrobot'])
def test_matching_balance_determinism_rng_and_schema(family):
    obs = observations(family); old = deepcopy(obs)
    random.seed(91); state = random.getstate()
    p = blocks.make_plan(family, obs, 19)
    assert random.getstate() == state and obs == old
    assert p == blocks.make_plan(family, list(reversed(obs)), 19)
    assert p['pairs'] == [[0, 1], [2, 3], [4, 5], [6, 7]] and p['squared_distance'] == 0
    assert len(list(blocks._matchings(tuple(range(8))))) == 105
    for s in p['schedules'].values():
        assert list(s.values()).count('switch') == list(s.values()).count('rank_blend') == 4
    for a, b in p['pairs']:
        assert p['schedules']['public_blocked'][str(a)] != p['schedules']['public_blocked'][str(b)]


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'outcome', 'bool', 'nan', 'infinity', 'shape', 'string'])
def test_invalid_public_inputs_rejected(fault):
    rows = observations()
    if fault == 'missing': rows.pop()
    elif fault == 'duplicate': rows[0]['reset_id'] = 1
    elif fault == 'outcome': rows[0]['return'] = 900
    elif fault == 'bool': rows[0]['reset_id'] = False
    elif fault == 'shape': rows[0]['observation'].pop()
    else: rows[0]['observation'][0] = {'nan': float('nan'), 'infinity': float('inf'), 'string': '1'}[fault]
    with pytest.raises(ValueError): blocks.make_plan('pendulum', rows, 19)


def test_schedule_immutable_and_hidden_feedback_cannot_enter_selection():
    p = blocks.make_plan('pendulum', observations(), 19); data = panel(p)
    before = deepcopy(p)
    decision = blocks.select_parent_inclusive(p, data, 'public_blocked', 0)
    assert decision['choice'] == 'switch' and decision['observed_counts'] == {'parent': 8, 'switch': 4, 'rank_blend': 4}
    # Force both children into the physical union, finding a deterministic seed.
    p = next(blocks.make_plan('pendulum', observations(), seed) for seed in range(100)
             if any(len(v) == 3 for v in blocks.required_paths(blocks.make_plan('pendulum', observations(), seed)).values()))
    data = panel(p); first = blocks.select_parent_inclusive(p, data, 'public_blocked', 0)
    for row in data:
        chosen = p['schedules']['public_blocked'][str(row['reset_id'])]
        for k in row['paths']:
            if k not in ('parent', chosen): row['paths'][k]['return'] = 1e9
    assert blocks.select_parent_inclusive(p, data, 'public_blocked', 0) == first
    assert before == blocks.make_plan('pendulum', observations(), 19)
    for row in blocks.revealed_rows(p, data, 'public_blocked', 0):
        assert set(row['paths']) == {'parent', row['training_operator']}
    tampered = deepcopy(p); tampered['schedules']['public_blocked']['0'] = 'parent'
    with pytest.raises(ValueError): blocks.required_paths(tampered)


@pytest.mark.parametrize('fault', ['reset', 'duplicate', 'path', 'extra', 'metadata', 'nan', 'bool', 'query'])
def test_full_training_union_validated_before_masking(fault):
    p = blocks.make_plan('pendulum', observations(), 19); rows = panel(p)
    if fault == 'reset': rows.pop()
    elif fault == 'duplicate': rows[-1] = deepcopy(rows[0])
    elif fault == 'path': rows[0]['paths'].pop('parent')
    elif fault == 'extra': rows[0]['paths']['unknown'] = {'return': 1., 'cpu_s': 1.}
    elif fault == 'metadata': rows[0]['paths']['parent']['hidden_query'] = 900
    elif fault == 'query': rows[0]['role'] = 'evaluation'
    else: rows[0]['paths']['parent']['return'] = float('nan') if fault == 'nan' else True
    with pytest.raises(ValueError): blocks.revealed_rows(p, rows, 'public_blocked', 0)


def test_union_costs_and_logical_budgets_are_different():
    for seed in range(20):
        p = blocks.make_plan('acrobot', observations('acrobot'), seed)
        w = blocks.physical_work(p)
        assert 5600 <= w.real_steps <= 7200
        assert w.imagined_transitions == w.real_steps*1536
        assert w.model_calls == w.network_forwards == w.real_steps*50
        for condition in p['schedules']:
            assert sum(len(r['paths']) for r in blocks.revealed_rows(p, panel(p), condition, 1)) == 16


def test_config_is_unregistered_and_cannot_authorize_execution():
    c = json.loads((ROOT/'configs/e3_12f_reset_blocked_proposal.json').read_text())
    result = blocks.validate_proposal(c)
    assert result['execution_allowed'] is False and result['new_environment_steps'] == 0
    for key, value in [('execution_authorized', True), ('numerical_environment_seeds', [1]),
                       ('allocation', {}), ('proposed_real_cap', 22400), ('practical_return_margin', True),
                       ('model_bundles', [False, 1])]:
        bad = deepcopy(c); bad[key] = value
        with pytest.raises(ValueError): blocks.validate_proposal(bad)
