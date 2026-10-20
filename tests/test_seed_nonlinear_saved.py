"""Completed artifact only. No neural imports or new scientific collection."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from nexus.seed.nonlinear_learning_audit import validate,saved_replay

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def result():
    return json.loads((ROOT/'artifacts/seed_nonlinear_learning.json').read_text())


def test_saved_grid_arithmetic_and_replay_without_local_weights(result):
    c=json.loads((ROOT/'configs/seed_nonlinear_learning.json').read_text());assert validate(result,c)
    card=saved_replay(ROOT)
    assert card['study']==result['analysis'] and card['mode']=='recorded_development_replay'
    assert card['study']['screen_passed'] is False


@pytest.mark.parametrize('missing',['seed','task','method','budget','metric','nan','string','score','transition'])
def test_saved_result_invalidations_fail_closed(result,missing):
    c=result['config'];r=deepcopy(result);cells=r['curves']['audit'];task=cells['6401']['97000000'];row=task['learned'][0]
    if missing=='seed':del cells['6401']
    elif missing=='task':del cells['6401']['97000000']
    elif missing=='method':del task['static']
    elif missing=='budget':task['learned'].pop()
    elif missing=='metric':del row['query_mse']
    elif missing=='nan':row['query_mse']=float('nan')
    elif missing=='string':row['query_mse']='0.1'
    elif missing=='score':row['scores'][0]+=1
    else:r['tasks']['audit'][0]['records']['query'][0]['outcomes'][0]['reward']+=1
    with pytest.raises((ValueError,KeyError)):validate(r,c)


def test_actual_learned_static_fixed_actions_are_identical(result):
    for cells in result['control'].values():
        for s in result['config']['outer_seeds']:
            for method in ('static','fixed'):
                a=cells[f'{s}/learned'];b=cells[f'{s}/{method}']
                assert [[v['action'] for v in e['steps']] for e in a]==[[v['action'] for v in e['steps']] for e in b]
