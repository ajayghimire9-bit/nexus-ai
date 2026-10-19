"""Nested feedback budgets using the existing frozen selector, not a learner."""
import json
import numpy as np

from nexus.evolution2 import return_feedback as r
from nexus.evolution2 import full_policy_source as h

BUDGETS=(3,6,9)


def paths(budget):
    if budget not in BUDGETS:raise ValueError('locked_budget')
    return (h.ROOT/f'artifacts/e3_4_predictor_b{budget}.json',h.ROOT/f'artifacts/e3_4_predictions_b{budget}.jsonl')


class CoverageSelectors:
    """Fit all snapshots before evaluation; each sees its own training prefix."""
    def __init__(self,c,persist=True):
        if c['version']!='coverage_feedback_v1':raise ValueError('coverage_profile_only')
        self.c=c;self.selectors={b:r.FrozenReturnSelector(c,persist,b,*paths(b)) for b in BUDGETS}

    def fit(self,rows):
        if any(s.ready for s in self.selectors.values()):raise RuntimeError('frozen_coverage_no_updates')
        r.paired_training(rows,self.c,9)
        for b,s in self.selectors.items():s.fit(tuple(row for row in rows if row['episode']<b))

    def decide(self,public):
        return {**public,'budgets':{str(b):s.decide(public) for b,s in self.selectors.items()}}

    def files(self):
        return {str(b):dict(manifest_path=str(paths(b)[0].relative_to(h.ROOT)),manifest_sha256=h.sha(paths(b)[0]),
                           predictions_path=str(paths(b)[1].relative_to(h.ROOT)),predictions_sha256=h.sha(paths(b)[1])) for b in BUDGETS}


def analyze(p,c):
    if any(set(record['budgets'])!={str(b) for b in BUDGETS} for record in p['selection_decisions']):raise ValueError('budget_grid')
    for record in p['selection_decisions']:
        for inner in record['budgets'].values():
            if any(record[k]!=inner[k] for k in ('family','model_bundle','episode','initial_obs','completed_real_steps')):raise ValueError('paired_budget_context')
    analyses={str(b):r.analyze_selection(p,c,[row['budgets'][str(b)] for row in p['selection_decisions']]) for b in BUDGETS}
    # Shared physical returns; budget comparisons are paired, not new episodes.
    coverage={}
    primary={}
    for f in c['families']:
        a=analyses['9']['by_family'][f];primary[f]=a['predictor_minus_baselines']['model_mean']>=1. and all(
            m['quality_predictor']>m['model_mean'] for m in a['per_model_returns'].values())
        coverage[f]=dict(predictor_return_9_minus_3=a['mean_returns']['quality_predictor']-analyses['3']['by_family'][f]['mean_returns']['quality_predictor'],
            relative_gain_9_minus_3=a['predictor_minus_baselines']['model_mean']-analyses['3']['by_family'][f]['predictor_minus_baselines']['model_mean'])
    return dict(by_budget=analyses,primary_budget=9,primary_point_screen_by_family=primary,primary_point_screen=all(primary.values()),
        broad_baseline_screen=analyses['9']['point_screen'],coverage_effect=coverage,
        independent_models_per_family=2,generalization_or_learning_to_learn_established=False)


def verify_selectors(p,c):
    """Zero-fit replay against exactly the recorded prefix, cached source data."""
    expected={str(b) for b in BUDGETS}
    if set(p['predictor_files'])!=expected:raise ValueError('predictor_file_grid')
    training=[row for row in p['episodes'] if row['split']=='training']
    for b in BUDGETS:
        file=p['predictor_files'][str(b)];mp,pp=paths(b)
        if file['manifest_path']!=str(mp.relative_to(h.ROOT)) or file['predictions_path']!=str(pp.relative_to(h.ROOT)):raise ValueError('predictor_paths')
        h.verify_file(mp,file['manifest_sha256']);h.verify_file(pp,file['predictions_sha256'])
        m=json.loads(mp.read_text());s=r.FrozenReturnSelector.restore(c,m)
        bank=r.paired_training([row for row in training if row['episode']<b],c,b)
        if bank!=m['training_pairs'] or len(bank)!=4*b or m['training_real_steps']!=1600*b:raise ValueError('prefix_training_provenance')
        if m['training_budget']!=b:raise ValueError('budget_identity')
        for family in c['families']:
            n=r.FamilyNormalizer.fit(family,r.load_source_train_obs(family,(0,1)))
            if n.mean.tolist()!=m['normalizers'][family]['mean'] or n.std.tolist()!=m['normalizers'][family]['std']:raise ValueError('source_normalization')
        for key,support in s.supports.items():
            if r.digest(dict(obs=support.obs.tolist(),action=support.action.tolist(),next_obs=support.next_obs.tolist()))!=m['support_sha256'][key]:raise ValueError('source_support_hash')
        if [s.features(row['public']).tolist() for row in bank]!=m['feature_rows']:raise ValueError('training_feature_reproduction')
        if set(m['models'])!={'quality_predictor','shuffled_pair_labels'}:raise ValueError('coefficient_model_grid')
        x=np.asarray(m['feature_rows']);scale=np.sqrt(np.mean(x*x,axis=0));scale=np.where(scale<1e-8,1.,scale)
        perm=np.random.default_rng(31).permutation(len(bank)).tolist()
        if perm!=m['shuffle_permutation']:raise ValueError('locked_shuffle')
        for name,w in m['models'].items():
            if w['fit_calls']!=1 or not np.allclose(scale,w['scale'],rtol=1e-12,atol=1e-12):raise ValueError('prefix_scaling')
            z=x/scale;beta=np.asarray(w['beta']);y=np.asarray([row['advantage'] for row in bank])
            if name=='shuffled_pair_labels':y=y[perm]
            if not np.allclose(2*z.T@(z@beta-y)+beta,0,rtol=0,atol=1e-6):raise ValueError('prefix_ridge_normal_equation')
        records=[row['budgets'][str(b)] for row in p['selection_decisions']]
        if [json.loads(line) for line in pp.read_text().splitlines()]!=records:raise ValueError('predecision_file')
        for row in records:
            public={k:row[k] for k in ('family','model_bundle','episode','initial_obs','completed_real_steps')}
            if s.decide(public)!=row:raise ValueError('predecision_reproduction')
    return analyze(p,c)
