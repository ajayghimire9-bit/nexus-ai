"""E3.11B preparation: pure capture/statistics contracts, no runtime worker.

Reuse post_probe.Host/Dispatch and rollout_headroom.walk when the separate
authorization and numerical seed registration have been committed. This module
does not replace a planner, learner, meter, or memory system.
"""
from copy import deepcopy
import hashlib
import itertools
import json
import math
from statistics import mean, stdev


def number(x):
    if type(x) not in (int, float) or not math.isfinite(x):
        raise ValueError('finite_numeric_value_required')
    return float(x)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()


def validate_config(c):
    fixed = dict(version='e3_11b_preparation_v1', execution_authorized=False,
                 seed_registration=None, families=['pendulum', 'acrobot'],
                 model_bundles=[0, 1], episodes=[0, 1, 2, 3],
                 controllers=['successor_anchor', 'rank_blend'],
                 predictors=['policy_forecast', 'common_tail', 'training_mean'],
                 probe_steps=8, forecast_steps=16, continuation_steps=192,
                 numerical_tie_tolerance=1e-6, minimum_accuracy_gain=.125,
                 proposed_time_cap_s=180, proposed_real_steps=6272,
                 proposed_imagined_transitions=9932800,
                 proposed_network_forwards=393728)
    if any(k not in c or digest(c[k]) != digest(v) for k, v in fixed.items()):
        raise ValueError('preparation_profile_changed_requires_protocol_revision')
    n = len(c['families'])*len(c['model_bundles'])*len(c['episodes'])
    if (n*(8+2*192), n*(47744+512+2*192*1491),
            n*(1920+32+192*118)) != (c['proposed_real_steps'],
            c['proposed_imagined_transitions'], c['proposed_network_forwards']):
        raise ValueError('resource_arithmetic')
    return True


def require_execution_authority(c):
    """No side effects/imports precede this gate. Preparation is not a grant."""
    validate_config(c)
    raise PermissionError('E3.11B execution not authorized; numerical seeds, '
                          'reviewed host binding and committed allocation absent')


def expected_grid(c):
    validate_config(c)
    return set(itertools.product(c['families'], c['model_bundles'], c['episodes']))


def training_means(path, expected_sha, c):
    """Read the pinned TRAIN-only prior, never evaluation returns or ridge fits."""
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('training_prior_hash')
    p = json.loads(raw)
    keys = [(r['family'], r['bundle'], r['episode']) for r in p['training_pairs']]
    expected = set(itertools.product(c['families'], c['model_bundles'], range(3)))
    if len(keys) != len(expected) or set(keys) != expected or any(
            r['role'] != 'training' or r['phase'] != 'training'
            for r in p['training_pairs']):
        raise ValueError('training_only_prior_grid')
    values = p['state']['means']
    if set(values) != {f'{f}:{b}' for f in c['families'] for b in c['model_bundles']}:
        raise ValueError('training_prior_model_grid')
    return {k: number(v) for k, v in values.items()}


def capture_pair(key, predictions, persist, evaluate, c):
    """Testable ordering adapter. Trusted host callbacks are not supplied here.

    Predictions are copied and durably acknowledged BEFORE either outcome.
    evaluate(label) must restore the same post-probe state with paired planner
    randomness and return the complete 192 actual immediate rewards.
    """
    if key not in expected_grid(c) or set(predictions) != set(c['predictors']):
        raise ValueError('planned_case_and_predictors_required')
    frozen = {k: number(v) for k, v in predictions.items()}
    receipt = dict(family=key[0], bundle=key[1], episode=key[2], predictions=frozen)
    receipt['forecast_sha256'] = digest(receipt)
    if persist(deepcopy(receipt)) != receipt['forecast_sha256']:
        raise ValueError('durable_forecast_acknowledgment_required')
    rewards = {}
    for label in c['controllers']:
        values = evaluate(label)
        if type(values) is not list or len(values) != c['continuation_steps']:
            raise ValueError('complete_actual_rewards_required')
        rewards[label] = [number(x) for x in values]
    return dict(**receipt, rewards=rewards)


def validate_rows(rows, c):
    if any(type(r['family']) is not str or type(r['bundle']) is not int or
           type(r['episode']) is not int for r in rows):
        raise ValueError('typed_case_identifiers_required')
    keys = [(r['family'], r['bundle'], r['episode']) for r in rows]
    if len(keys) != len(expected_grid(c)) or set(keys) != expected_grid(c):
        raise ValueError('complete_independently_planned_grid')
    for r in rows:
        if set(r['predictions']) != set(c['predictors']) or set(r['rewards']) != set(c['controllers']):
            raise ValueError('complete_conditions_required')
        for x in r['predictions'].values():
            number(x)
        for values in r['rewards'].values():
            if type(values) is not list or len(values) != 192:
                raise ValueError('complete_actual_rewards_required')
            for x in values:
                number(x)
            number(sum(values))
        receipt = {k: r[k] for k in ('family', 'bundle', 'episode', 'predictions')}
        if digest(receipt) != r['forecast_sha256']:
            raise ValueError('forecast_receipt_changed')
    return True


def interval(values):
    """Exploratory paired t95 across TWO pretrained models, df=1."""
    if len(values) != 2:
        raise ValueError('two_model_units_required')
    values = [number(x) for x in values]
    m = mean(values)
    half = 12.706204736432095*stdev(values)/math.sqrt(2)
    return dict(mean=m, low=m-half, high=m+half, n_models=2, df=1)


def analyze(rows, c):
    validate_rows(rows, c)
    tol = c['numerical_tie_tolerance']
    out = {}
    for family in c['families']:
        models = []
        for bundle in c['model_bundles']:
            subset = [r for r in rows if r['family'] == family and r['bundle'] == bundle]
            methods = {}
            for method in c['predictors']:
                records = []
                for r in subset:
                    a, b = (sum(r['rewards'][label]) for label in c['controllers'])
                    a16, b16 = (sum(r['rewards'][label][:16]) for label in c['controllers'])
                    actual, short = b-a, b16-a16
                    forecast = r['predictions'][method]
                    # Numerical forecast ties choose successor, identically for all.
                    choice = int(forecast > tol)
                    actual_sign = 0 if abs(actual) <= tol else (1 if actual > 0 else -1)
                    forecast_sign = 0 if abs(forecast) <= tol else (1 if forecast > 0 else -1)
                    accuracy = .5 if actual_sign == 0 or forecast_sign == 0 else float(actual_sign == forecast_sign)
                    records.append(dict(accuracy=accuracy, forecast_tie=forecast_sign == 0,
                        actual_tie=actual_sign == 0, selected_return=b if choice else a,
                        regret=max(a, b)-(b if choice else a),
                        short_advantage_mae=abs(forecast-short),
                        long_advantage_mae=abs(forecast-actual)))
                methods[method] = {k: mean(r[k] for r in records) for k in records[0]}
            models.append(dict(bundle=bundle, methods=methods))
        comparisons = {}
        for baseline in ('common_tail', 'training_mean'):
            comparisons[baseline] = {metric: interval([
                m['methods']['policy_forecast'][metric]-m['methods'][baseline][metric]
                for m in models]) for metric in ('accuracy', 'selected_return', 'regret')}
        # Prespecified POINT screen; confidence intervals remain exploratory.
        passes = all(comparisons[b]['accuracy']['mean'] >= c['minimum_accuracy_gain']
            and comparisons[b]['selected_return']['mean'] > 0
            and all(m['methods']['policy_forecast']['selected_return'] >=
                    m['methods'][b]['selected_return'] for m in models)
            for b in comparisons)
        out[family] = dict(models=models, paired=comparisons, point_screen=passes)
    return dict(families=out, point_screen=all(x['point_screen'] for x in out.values()),
                scope='Exploratory known-model calibration, not confirmation or useful learning')
