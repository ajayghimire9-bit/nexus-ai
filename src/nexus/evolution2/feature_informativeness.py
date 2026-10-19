"""Feature-slice adapter over the existing training audit and AdvantagePredictor.

No new learner, source collection, feature construction or planner stack.
"""
import itertools
import math

import numpy as np

from nexus.evolution2 import training_feedback_audit as base
from nexus.evolution2.generated_strategies import AdvantagePredictor
from nexus.evolution2.planner_quality_diagnostic import predict_ridge
from nexus.evolution2.return_feedback import choose

GROUP_ROWS = {
    'full': tuple(range(12)),
    'observation': tuple(range(7)),
    'support_schema': (0, 7, 8, 9),
    'anchor': (0, 10, 11),
}
PERMUTATIONS = tuple(range(19))
MODELS = tuple(itertools.product(base.FAMILIES, base.BUNDLES))


def modes():
    return tuple(GROUP_ROWS) + tuple(f'{g}_perm_{p}' for g in GROUP_ROWS for p in PERMUTATIONS)


def columns(group):
    return [16*r+j for r in GROUP_ROWS[group] for j in range(16)]


def validate_bank(bank, features, profile='e3_6'):
    if profile != 'e3_6': raise ValueError('locked_feature_profile')
    base.validate_bank(bank, features, 'e3_5')
    for row, x in zip(bank, features):
        matrix = np.asarray(x).reshape(12, 16)
        dim = 3 if row['public']['family'] == 'pendulum' else 6
        expected = np.outer([dim/16., 3/16., 200/16.], matrix[0])
        if not np.allclose(matrix[7:10], expected, atol=1e-12, rtol=1e-12):
            raise ValueError('existing_support_slots_are_schema_only')
    for f, b in MODELS:
        arms = [np.asarray(x)[:16] for row, x in zip(bank, features) if base.identity(row)[:2] == (f, b)]
        if any(not np.array_equal(arms[0], v) for v in arms[1:]):
            raise ValueError('fixed_controller_descriptor_required')
    return True


def layout(bank, features, held):
    """Fold design uses no withheld outcomes, including anchor features."""
    if type(held) is not int or held not in range(9): raise ValueError('locked_fold')
    train = [i for i, r in enumerate(bank) if base.identity(r)[2] != held]
    query = [i for i, r in enumerate(bank) if base.identity(r)[2] == held]
    if len(train) != 32 or len(query) != 4: raise ValueError('fold_grid')
    means = base.anchor_means([bank[i] for i in train])
    def prior(i):
        f, b, _ = base.identity(bank[i]); v = means[f'{f}:{b}']
        return v['rank_blend']-v['successor_anchor']
    def phi(i):
        f, b, _ = base.identity(bank[i])
        return base.fold_features(features[i], means[f'{f}:{b}'])
    x = np.asarray([phi(i) for i in train]); q = np.asarray([phi(i) for i in query])
    y = [bank[i]['advantage']-prior(i) for i in train]
    maps = {}
    for p in PERMUTATIONS:
        mapping = list(range(32))
        for k, key in enumerate(MODELS):
            ids = [j for j, i in enumerate(train) if base.identity(bank[i])[:2] == key]
            shuffled = np.random.default_rng(613000+held*10000+p*10+k).permutation(ids)
            for target, source in zip(ids, shuffled): mapping[target] = int(source)
        maps[str(p)] = mapping
    return train, query, means, x, q, y, maps, [prior(i) for i in query]


def design(mode, x, maps):
    group = mode.split('_perm_')[0]
    order = list(range(len(x))) if '_perm_' not in mode else maps[mode.split('_perm_')[1]]
    return x[np.asarray(order)][:, columns(group)]


def predict_fold(bank, features, held_out, fit_guard=None, profile='e3_6'):
    if profile != 'e3_6': raise ValueError('locked_feature_profile')
    train, query, means, x, q, y, maps, priors = layout(bank, features, held_out)
    weights = {}; estimates = [dict(model_mean=v) for v in priors]
    for mode in modes():
        group = mode.split('_perm_')[0]; xx = design(mode, x, maps)
        learner = AdvantagePredictor()
        for j, i in enumerate(train):
            f, b, _ = base.identity(bank[i]); v = means[f'{f}:{b}']
            learner.observe(xx[j], bank[i]['advantage'], baseline=v['rank_blend']-v['successor_anchor'],
                            event=bank[i]['event'], provenance='revealed_source')
        if fit_guard: fit_guard('reserve')
        learner.predict(xx[0])
        if fit_guard: fit_guard('complete')
        weights[mode] = dict(scale=learner.model[0].tolist(), beta=learner.model[1].tolist(), fit_calls=learner.fit_calls)
        for j in range(4): estimates[j][mode] = learner.predict(q[j, columns(group)], baseline=priors[j])
    return dict(held_out=held_out, train_ids=[list(base.identity(bank[i])) for i in train],
                query_ids=[list(base.identity(bank[i])) for i in query], anchor_means=means,
                training_features=x.tolist(), query_features=q.tolist(), training_targets=y,
                within_model_permutations=maps, models=weights,
                predictions=[dict(public=bank[i]['public'].copy(), prior_mean=priors[j], estimates=estimates[j],
                                  choices={m:choose(v) for m,v in estimates[j].items()}) for j,i in enumerate(query)])


def score_predictions(folds, bank, profile='e3_6'):
    """No fitting: raw cell validation precedes all aggregation."""
    if profile != 'e3_6': raise ValueError('locked_feature_profile')
    if len(folds) != 9 or any(type(f['held_out']) is not int for f in folds) or {f['held_out'] for f in folds} != set(range(9)):
        raise ValueError('complete_fold_grid')
    methods = ('model_mean',)+modes(); lookup = {base.identity(r):r for r in bank}; raw = []
    for fold in folds:
        held = fold['held_out']; expected = set(itertools.product(base.FAMILIES,base.BUNDLES,(held,)))
        for name, wanted in (('query_ids',expected), ('train_ids',set(itertools.product(base.FAMILIES,base.BUNDLES,[e for e in range(9) if e!=held])))):
            values = fold[name]
            if len(values)!=len(wanted) or any(len(v)!=3 or type(v[1]) is not int or type(v[2]) is not int for v in values) or set(map(tuple,values))!=wanted:
                raise ValueError('fold_separation')
        if len(fold['predictions']) != 4 or {base.identity(r) for r in fold['predictions']} != expected:
            raise ValueError('complete_prediction_grid')
        for pred in fold['predictions']:
            if type(pred['public']['model_bundle']) is not int or type(pred['public']['episode']) is not int:
                raise ValueError('typed_query_identity')
            row = lookup[base.identity(pred)]; truth = row['advantage']
            if pred['public']!=row['public'] or set(pred['estimates'])!=set(methods) or set(pred['choices'])!=set(methods):
                raise ValueError('complete_method_grid')
            if not base.number(pred['prior_mean']) or pred['prior_mean']!=pred['estimates']['model_mean']:
                raise ValueError('finite_prior')
            if not all(base.number(v) for v in pred['estimates'].values()) or any(pred['choices'][m]!=choose(v) for m,v in pred['estimates'].items()):
                raise ValueError('finite_prediction_or_choice')
            raw.append(dict(public=pred['public'], truth=truth, residual_truth=truth-pred['prior_mean'],
                returns={m:row['returns'][pred['choices'][m]] for m in methods},
                absolute_error={m:abs(pred['estimates'][m]-truth) for m in methods},
                squared_error={m:(pred['estimates'][m]-truth)**2 for m in methods},
                sign_correct={m:(pred['estimates'][m]>0)==(truth>0) for m in methods},
                regret={m:max(row['returns'].values())-row['returns'][pred['choices'][m]] for m in methods}))
    per_model={}; passed={g:True for g in GROUP_ROWS}
    for f,b in MODELS:
        rows=[r for r in raw if base.identity(r)[:2]==(f,b)]
        metrics={m:dict(mae=float(np.mean([r['absolute_error'][m] for r in rows])),
                       rmse=float(np.sqrt(np.mean([r['squared_error'][m] for r in rows]))),
                       selected_return=float(np.mean([r['returns'][m] for r in rows])),
                       sign_accuracy=float(np.mean([r['sign_correct'][m] for r in rows])),
                       regret=float(np.mean([r['regret'][m] for r in rows]))) for m in methods}
        checks={}
        for g in GROUP_ROWS:
            baseline=metrics['model_mean']['mae']; actual=metrics[g]['mae']
            wins=sum(actual<metrics[f'{g}_perm_{p}']['mae'] for p in PERMUTATIONS)
            checks[g]=dict(mae_reduction=baseline-actual, fractional_reduction=(baseline-actual)/baseline if baseline>1e-12 else None,
                           return_gain=metrics[g]['selected_return']-metrics['model_mean']['selected_return'],
                           permutation_wins=wins, passes=baseline>1e-12 and actual<=.95*baseline and wins>=18)
            passed[g] = passed[g] and checks[g]['passes']
        per_model[f'{f}:{b}']=dict(metrics=metrics,checks=checks)
    by_family={f:{m:{metric:float(np.mean([per_model[f'{f}:{b}']['metrics'][m][metric] for b in base.BUNDLES]))
                         for metric in ('mae','rmse','selected_return','sign_accuracy','regret')} for m in methods} for f in base.FAMILIES}
    return dict(raw=raw,per_model=per_model,by_family=by_family,group_screen=passed,point_screen=any(passed.values()),
                label='feature_signal_screen_passed' if any(passed.values()) else 'feature_signal_not_established',
                independent_models_per_family=2,folds_are_independent_models=False,
                support_transition_features_available=False,permutation_ranks_are_not_p_values=True)


def verify_frozen_folds(folds, bank, features, profile='e3_6'):
    """Reconstruct fold-only features and certify saved ridge solutions, no fits."""
    validate_bank(bank,features,profile); analysis=score_predictions(folds,bank,profile)
    for fold in folds:
        train,query,means,x,q,y,maps,priors=layout(bank,features,fold['held_out'])
        if means!=fold['anchor_means'] or maps!=fold['within_model_permutations'] or x.tolist()!=fold['training_features'] or q.tolist()!=fold['query_features']:
            raise ValueError('training_only_layout')
        if not all(base.number(v) for v in fold['training_targets']) or y!=fold['training_targets']:
            raise ValueError('training_only_targets')
        if set(fold['models'])!=set(modes()): raise ValueError('complete_model_grid')
        for mode,weights in fold['models'].items():
            group=mode.split('_perm_')[0]; dim=len(columns(group)); xx=design(mode,x,maps)
            if type(weights['fit_calls']) is not int or weights['fit_calls']!=1 or any(len(weights[k])!=dim or not all(base.number(v) for v in weights[k]) for k in ('scale','beta')):
                raise ValueError('finite_coefficients')
            scale=np.sqrt(np.mean(xx**2,axis=0)); scale=np.where(scale<1e-8,1.,scale)
            if not np.allclose(scale,weights['scale'],atol=1e-12,rtol=1e-12):raise ValueError('fit_only_scaling')
            z=xx/scale;beta=np.asarray(weights['beta'])
            if not np.allclose(2*z.T@(z@beta-y)+beta,0,atol=1e-6,rtol=0):raise ValueError('ridge_normal_equation')
            for j,pred in enumerate(fold['predictions']):
                if pred['public']!=bank[query[j]]['public'] or pred['prior_mean']!=priors[j]:raise ValueError('query_order_or_prior')
                expected=priors[j]+predict_ridge((scale,beta),q[j,columns(group)])
                if not math.isclose(expected,pred['estimates'][mode],abs_tol=1e-10,rel_tol=1e-12):raise ValueError('coefficient_replay')
    return analysis


def variability(bank, features):
    """Descriptive fixed-input audit; no labels, fitting or new features."""
    out={}
    for f,b in MODELS:
        x=np.asarray([v for r,v in zip(bank,features) if base.identity(r)[:2]==(f,b)])
        out[f'{f}:{b}']={g:dict(columns=len(columns(g)),varying_columns=int(np.sum(np.ptp(x[:,columns(g)],axis=0)>1e-12)),
                              centered_rank=int(np.linalg.matrix_rank(x[:,columns(g)]-np.mean(x[:,columns(g)],axis=0),tol=1e-10)))
                          for g in GROUP_ROWS}
    return out
