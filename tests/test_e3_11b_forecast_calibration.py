"""Authored numbers/callbacks and saved TRAIN metadata only; no inference."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest
from nexus.evolution2 import forecast_calibration as f

ROOT = Path(__file__).resolve().parents[1]


def config():
    return json.loads((ROOT/'configs/e3_11b_forecast_calibration.json').read_text())


def rows():
    c = config()
    return [f.capture_pair(key, dict(policy_forecast=2., common_tail=0., training_mean=-1.),
        lambda p: p['forecast_sha256'],
        lambda label: [1. if label == 'rank_blend' else 0.]*192, c)
        for key in sorted(f.expected_grid(c))]


def test_predictions_durably_saved_before_outcomes_and_no_aliasing():
    c = config(); events = []; forecasts = dict(policy_forecast=2., common_tail=0., training_mean=-1.)
    def persist(p):
        events.append('saved'); forecasts['policy_forecast'] = 999.
        return p['forecast_sha256']
    def evaluate(label):
        assert events[0] == 'saved'
        events.append(label)
        return [0.]*192
    r = f.capture_pair(('pendulum', 0, 0), forecasts, persist, evaluate, c)
    assert r['predictions']['policy_forecast'] == 2.
    assert events == ['saved', 'successor_anchor', 'rank_blend']


def test_failed_persistence_prevents_any_outcome_call():
    def forbidden(label):
        pytest.fail('must not evaluate without receipt')
    with pytest.raises(ValueError, match='acknowledgment'):
        f.capture_pair(('pendulum', 0, 0), rows()[0]['predictions'], lambda p: None, forbidden, config())


@pytest.mark.parametrize('fault', ['family', 'model', 'episode', 'duplicate', 'predictor',
    'controller', 'reward', 'nan', 'infinity', 'string', 'boolean', 'forecast_change',
    'boolean_model', 'string_episode', 'overflow'])
def test_completeness_is_from_configuration_not_produced_rows(fault):
    r = rows()
    if fault == 'family': r = [x for x in r if x['family'] != 'pendulum']
    elif fault == 'model': r = [x for x in r if x['bundle'] != 1]
    elif fault == 'episode': r.pop()
    elif fault == 'duplicate': r[-1] = deepcopy(r[0])
    elif fault == 'predictor': r[0]['predictions'].pop('common_tail')
    elif fault == 'controller': r[0]['rewards'].pop('rank_blend')
    elif fault == 'reward': r[0]['rewards']['rank_blend'].pop()
    elif fault == 'forecast_change': r[0]['predictions']['policy_forecast'] += 1
    elif fault == 'boolean_model': r[0]['bundle'] = False
    elif fault == 'string_episode': r[0]['episode'] = '0'
    elif fault == 'overflow': r[0]['rewards']['rank_blend'] = [1e308]*192
    else:
        value = dict(nan=float('nan'), infinity=float('inf'), string='1', boolean=True)[fault]
        r[0]['rewards']['rank_blend'][0] = value
    with pytest.raises(ValueError): f.analyze(r, config())


def test_primary_uses_192_actual_rewards_and_first16_is_secondary():
    r = rows()
    for x in r: x['rewards']['rank_blend'] = [1.]*16 + [-1.]*176
    result = f.analyze(r, config())
    p = result['families']['pendulum']['models'][0]['methods']['policy_forecast']
    assert p['accuracy'] == 0 and p['selected_return'] == -160
    assert p['short_advantage_mae'] == 14 and p['long_advantage_mae'] == 162
    assert result['point_screen'] is False


def test_random_fixed_baseline_can_win_and_screen_is_not_numerical_headroom():
    r = rows()
    assert f.analyze(r, config())['point_screen'] is True
    for x in r:
        x['predictions']['policy_forecast'] = -2.
        receipt = {k: x[k] for k in ('family', 'bundle', 'episode', 'predictions')}
        x['forecast_sha256'] = f.digest(receipt)
    result = f.analyze(r, config())
    assert result['point_screen'] is False
    assert result['families']['acrobot']['paired']['common_tail']['accuracy']['mean'] == -.5


def test_forecast_ties_get_half_credit_but_choose_successor():
    r = rows(); result = f.analyze(r, config())
    m = result['families']['pendulum']['models'][0]['methods']['common_tail']
    assert m['accuracy'] == .5 and m['selected_return'] == 0 and m['forecast_tie'] == 1


def test_two_model_interval_does_not_count_episodes_as_replications():
    r = rows()
    result = f.analyze(r, config())['families']['pendulum']['paired']['training_mean']['selected_return']
    assert result['n_models'] == 2 and result['df'] == 1
    assert f.interval([1., 3.])['low'] == pytest.approx(2-12.706204736432095)
    with pytest.raises(ValueError): f.interval([1.]*8)


def test_training_mean_is_pinned_training_only_and_no_fit(tmp_path):
    c = config()
    means = f.training_means(ROOT/c['training_prior'], c['training_prior_sha256'], c)
    assert means['pendulum:0'] == pytest.approx(120.76657462937548)
    path = tmp_path/'modified.json'; path.write_bytes((ROOT/c['training_prior']).read_bytes()+b' ')
    with pytest.raises(ValueError, match='hash'):
        f.training_means(path, c['training_prior_sha256'], c)


@pytest.mark.parametrize('field,value', [('execution_authorized', True), ('seed_registration', {}),
    ('forecast_steps', 8), ('episodes', [0]), ('minimum_accuracy_gain', 0.), ('proposed_time_cap_s', 900)])
def test_preparation_cannot_silently_become_execution(field, value):
    c = config(); c[field] = value
    with pytest.raises(ValueError): f.validate_config(c)


def test_execution_gate_rejects_before_runtime_imports():
    with pytest.raises(PermissionError, match='not authorized'): f.require_execution_authority(config())
    p = subprocess.run([sys.executable, str(ROOT/'scripts/prepare_e3_11b_forecast_calibration.py'), '--execute'],
                       capture_output=True, text=True)
    assert p.returncode != 0 and 'not authorized' in p.stderr


def test_preparation_report_zero_work_and_exact_budget():
    c = config(); assert f.validate_config(c)
    p = subprocess.run([sys.executable, str(ROOT/'scripts/prepare_e3_11b_forecast_calibration.py')],
                       capture_output=True, text=True, check=True)
    result = json.loads(p.stdout)
    assert result['real_steps'] == result['imagined_transitions'] == result['model_inference'] == 0
    assert not result['numerical_seeds_registered']
