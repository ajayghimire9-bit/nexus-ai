"""Training-only blocked-reset audit of the existing AdvantagePredictor.

No environments, dynamics checkpoints, source NPZs, or new learning stack.
"""
import itertools
import math

import numpy as np

from nexus.evolution1.catalogue import digest
from nexus.evolution2.generated_strategies import AdvantagePredictor
from nexus.evolution2.planner_quality_diagnostic import predict_ridge
from nexus.evolution2.return_feedback import choose, METHODS, ESTIMATES

FAMILIES=('pendulum','acrobot')
BUNDLES=(0,1)
EPISODES=(0,1,2)
CONTROLLERS=('successor_anchor','rank_blend')


def number(x):
    return type(x) in (int,float) and math.isfinite(x)


def identity(row):
    p=row['public'];return p['family'],p['model_bundle'],p['episode']


def anchor_means(rows):
    return {f'{f}:{b}':{k:float(np.mean([r['returns'][k] for r in rows if identity(r)[:2]==(f,b)]))
        for k in CONTROLLERS} for f,b in itertools.product(FAMILIES,BUNDLES)}


def fold_features(raw,anchors):
    """Exact outer-product reconstruction, replacing BOTH outcome-derived rows.

    Existing advantage_features is outer(task[12], arm[16]); task[0]=1.
    Last two task coordinates are revealed anchor means / 100.
    Preserve the first ten task rows; never reuse old full-bank anchors.
    """
    x=np.asarray(raw,dtype=float).reshape(12,16).copy()
    if not np.isfinite(x).all() or set(anchors)!=set(CONTROLLERS):raise ValueError('feature_schema')
    for i,k in enumerate(CONTROLLERS):
        if not number(anchors[k]):raise ValueError('finite_anchor')
        x[10+i]=x[0]*(anchors[k]/100.)
    return x.ravel()


def validate_bank(bank,features):
    expected=set(itertools.product(FAMILIES,BUNDLES,EPISODES))
    if len(bank)!=12 or len(features)!=12:raise ValueError('complete_training_bank')
    ids=[identity(r) for r in bank]
    if set(ids)!=expected or len(set(ids))!=12:raise ValueError('exact_training_id_grid')
    for r,x in zip(bank,features):
        p=r['public'];f,b,e=identity(r)
        if set(p)!={'family','model_bundle','episode','initial_obs'} or type(b) is not int or type(e) is not int:
            raise ValueError('training_public_schema')
        if len(p['initial_obs'])!=(3 if f=='pendulum' else 6) or not all(number(v) for v in p['initial_obs']):raise ValueError('observation_schema')
        if set(r['returns'])!=set(CONTROLLERS) or not all(number(v) for v in r['returns'].values()) or not number(r['advantage']):raise ValueError('finite_return')
        truth=r['returns']['rank_blend']-r['returns']['successor_anchor']
        if not math.isclose(truth,r['advantage'],abs_tol=1e-9,rel_tol=1e-12):raise ValueError('advantage_accounting')
        seed=2111000000+FAMILIES.index(f)*10000+b*100+e
        if r['event']!=digest(dict(public=p,returns=r['returns'],reset_seed=seed)):raise ValueError('training_receipt')
        if len(x)!=192 or not all(number(v) for v in x):raise ValueError('feature_schema')
    means=anchor_means(bank)
    for r,x in zip(bank,features):
        f,b,_=identity(r)
        if not np.allclose(fold_features(x,means[f'{f}:{b}']),x,atol=1e-12,rtol=1e-12):raise ValueError('saved_feature_layout')
    return True


def predict_fold(bank,features,held_out,fit_guard=None):
    """Fitting path reads ONLY training labels; no query returns are returned."""
    if type(held_out) is not int or held_out not in EPISODES:raise ValueError('locked_fold')
    train=[i for i,r in enumerate(bank) if identity(r)[2]!=held_out]
    query=[i for i,r in enumerate(bank) if identity(r)[2]==held_out]
    if len(train)!=8 or len(query)!=4:raise ValueError('fold_grid')
    rows=[bank[i] for i in train];means=anchor_means(rows)
    family={f:float(np.mean([r['advantage'] for r in rows if identity(r)[0]==f])) for f in FAMILIES}
    global_mean=float(np.mean([r['advantage'] for r in rows]))
    def feature(i):
        f,b,_=identity(bank[i]);return fold_features(features[i],means[f'{f}:{b}'])
    x=[feature(i) for i in train];y=[bank[i]['advantage'] for i in train]
    perm=np.random.default_rng(31+held_out).permutation(8).tolist()
    predictors={};weights={}
    for mode in ('quality_predictor','shuffled_pair_labels'):
        m=AdvantagePredictor()
        for j,i in enumerate(train):
            m.observe(x[j],y[j] if mode=='quality_predictor' else y[perm[j]],event=bank[i]['event'],provenance='revealed_source')
        if fit_guard:fit_guard('reserve')
        m.predict(x[0]);predictors[mode]=m
        if fit_guard:fit_guard('complete')
        weights[mode]=dict(scale=m.model[0].tolist(),beta=m.model[1].tolist(),fit_calls=m.fit_calls)
    records=[]
    for i in query:
        public=bank[i]['public'];f,b,e=identity(bank[i]);phi=feature(i)
        estimates={k:m.predict(phi) for k,m in predictors.items()}
        estimates.update(model_mean=means[f'{f}:{b}']['rank_blend']-means[f'{f}:{b}']['successor_anchor'],
                         family_mean=family[f],global_mean=global_mean)
        choices={k:choose(v) for k,v in estimates.items()}
        choices.update(always_successor='successor_anchor',always_rank_blend='rank_blend',
            uniform='rank_blend' if int(digest(('E3.3_uniform',f,b,e))[:8],16)%2 else 'successor_anchor')
        records.append(dict(public=public.copy(),feature=phi.tolist(),estimates=estimates,choices=choices))
    return dict(held_out=held_out,train_ids=[list(identity(bank[i])) for i in train],query_ids=[list(identity(bank[i])) for i in query],
        anchor_means=means,family_means=family,global_mean=global_mean,shuffle_permutation=perm,models=weights,
        training_features=[v.tolist() for v in x],design_rank=int(np.linalg.matrix_rank(x)),predictions=records)


def score_predictions(folds,bank):
    """Scoring only, after predictions are frozen: query labels become visible."""
    if len(folds)!=3 or {f['held_out'] for f in folds}!=set(EPISODES):raise ValueError('complete_fold_grid')
    lookup={identity(r):r for r in bank};out=[]
    for fold in folds:
        held=fold['held_out']
        expected=set(itertools.product(FAMILIES,BUNDLES,(held,)))
        train=set(itertools.product(FAMILIES,BUNDLES,tuple(e for e in EPISODES if e!=held)))
        if len(fold['train_ids'])!=8 or set(map(tuple,fold['train_ids']))!=train or len(fold['query_ids'])!=4 or set(map(tuple,fold['query_ids']))!=expected:
            raise ValueError('fold_separation')
        if len(fold['predictions'])!=4 or {identity(r) for r in fold['predictions']}!=expected:raise ValueError('complete_prediction_grid')
        for pred in fold['predictions']:
            if type(pred['public']['model_bundle']) is not int or type(pred['public']['episode']) is not int:raise ValueError('prediction_identity_type')
            if set(pred['estimates'])!=set(ESTIMATES) or set(pred['choices'])!=set(METHODS):raise ValueError('method_grid')
            if not all(number(v) for v in pred['estimates'].values()) or any(v not in CONTROLLERS for v in pred['choices'].values()):raise ValueError('finite_prediction')
            row=lookup[identity(pred)];values=row['returns'];truth=row['advantage']
            if pred['public']!=row['public']:raise ValueError('public_identity')
            for m,value in pred['estimates'].items():
                if pred['choices'][m]!=choose(value):raise ValueError('choice_prediction_mismatch')
            out.append(dict(public=pred['public'],truth=truth,returns={m:values[k] for m,k in pred['choices'].items()},
                regret={m:max(values.values())-values[k] for m,k in pred['choices'].items()},
                advantage_error={m:abs(v-truth) for m,v in pred['estimates'].items()},
                sign_correct={m:(v>0)==(truth>0) for m,v in pred['estimates'].items()}))
    if len(out)!=12 or len({identity(r) for r in out})!=12:raise ValueError('result_grid')
    summary={};screens={}
    for f in FAMILIES:
        per_model={str(b):{m:float(np.mean([r['returns'][m] for r in out if identity(r)[:2]==(f,b)])) for m in METHODS} for b in BUNDLES}
        mean={m:float(np.mean([v[m] for v in per_model.values()])) for m in METHODS}
        mae={m:float(np.mean([r['advantage_error'][m] for r in out if identity(r)[0]==f])) for m in ESTIMATES}
        gain=mean['quality_predictor']-mean['model_mean'];error_gain=mae['model_mean']-mae['quality_predictor']
        screens[f]=gain>=1. and error_gain>0 and all(v['quality_predictor']>v['model_mean'] for v in per_model.values())
        summary[f]=dict(per_model_returns=per_model,mean_returns=mean,predictor_minus_baselines={m:mean['quality_predictor']-mean[m] for m in METHODS if m!='quality_predictor'},
            advantage_mae=mae,mae_reduction_vs_model_mean=error_gain,
            sign_accuracy={m:float(np.mean([r['sign_correct'][m] for r in out if identity(r)[0]==f])) for m in ESTIMATES},
            mean_regret={m:float(np.mean([r['regret'][m] for r in out if identity(r)[0]==f])) for m in METHODS})
    return dict(raw=out,by_family=summary,point_screen_by_family=screens,point_screen=all(screens.values()),
        label='training_only_feature_signal_screen_passed' if all(screens.values()) else 'training_only_feature_signal_not_established',
        independent_models_per_family=2,folds_are_independent_models=False,regret_gain_equals_return_gain=True)


def verify_frozen_folds(folds,bank,features):
    """Independent coefficient replay without observe(), optimization or fitting."""
    validate_bank(bank,features)
    score_predictions(folds,bank)
    for fold in folds:
        train=[r for r in bank if identity(r)[2]!=fold['held_out']]
        means=anchor_means(train)
        if means!=fold['anchor_means']:raise ValueError('fold_anchor_leak')
        original={identity(row):x for row,x in zip(bank,features)}
        x=[fold_features(original[identity(row)],means[f'{identity(row)[0]}:{identity(row)[1]}']) for row in train]
        if [v.tolist() for v in x]!=fold['training_features']:raise ValueError('training_features')
        scale=np.sqrt(np.mean(np.asarray(x)**2,axis=0));scale=np.where(scale<1e-8,1.,scale)
        if set(fold['models'])!={'quality_predictor','shuffled_pair_labels'}:raise ValueError('model_grid')
        perm=np.random.default_rng(31+fold['held_out']).permutation(8).tolist()
        if perm!=fold['shuffle_permutation']:raise ValueError('locked_shuffle')
        for name,weights in fold['models'].items():
            if any(len(weights[k])!=192 or not all(number(v) for v in weights[k]) for k in ('scale','beta')):raise ValueError('finite_coefficient_grid')
            if type(weights['fit_calls']) is not int or weights['fit_calls']!=1 or not np.allclose(scale,weights['scale'],rtol=1e-12,atol=1e-12):raise ValueError('fold_only_scaling')
            z=np.asarray(x)/scale;beta=np.asarray(weights['beta']);y=np.asarray([row['advantage'] for row in train])
            if name=='shuffled_pair_labels':y=y[perm]
            if not np.allclose(2*z.T@(z@beta-y)+beta,0,rtol=0,atol=1e-6):raise ValueError('ridge_training_normal_equation')
        for pred in fold['predictions']:
            f,b,_=identity(pred);expected=fold_features(original[identity(pred)],means[f'{f}:{b}'])
            if expected.tolist()!=pred['feature']:raise ValueError('query_feature_leak')
            for name,w in fold['models'].items():
                if not math.isclose(predict_ridge((np.asarray(w['scale']),np.asarray(w['beta'])),expected),pred['estimates'][name],abs_tol=1e-10,rel_tol=1e-12):raise ValueError('coefficient_replay')
            simple=dict(model_mean=means[f'{f}:{b}']['rank_blend']-means[f'{f}:{b}']['successor_anchor'],
                family_mean=float(np.mean([r['advantage'] for r in train if identity(r)[0]==f])),global_mean=float(np.mean([r['advantage'] for r in train])))
            if any(v!=pred['estimates'][k] for k,v in simple.items()):raise ValueError('baseline_training_only')
            uniform='rank_blend' if int(digest(('E3.3_uniform',*identity(pred)))[:8],16)%2 else 'successor_anchor'
            if pred['choices']['uniform']!=uniform or pred['choices']['always_rank_blend']!='rank_blend' or pred['choices']['always_successor']!='successor_anchor':raise ValueError('fixed_baseline_rule')
    return score_predictions(folds,bank)
