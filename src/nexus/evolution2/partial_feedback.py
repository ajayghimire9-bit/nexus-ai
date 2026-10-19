"""Single-child explore-then-commit adapter over the existing operator audit.

No new learner/planner/memory/meter. Query outcomes cannot fit choices.
"""
import itertools
import numpy as np
from nexus.evolution1.catalogue import digest
from nexus.evolution2 import operator_headroom as panel
from nexus.evolution2.operator_headroom import METHODS,KINDS,operators,seed_pair,requested_seeds,check_real_step,number
from nexus.evolution2.generated_strategies import StrategyGenerator


def training_operator(c,f,b,e):
    ids=c['training_episodes']
    if len(ids)!=8 or len(set(ids))!=8 or e not in ids:raise ValueError('eight_registered_exploration_trials')
    rng=np.random.default_rng(np.random.SeedSequence([c['schedule_seed'],c['families'].index(f),b]))
    schedule=rng.permutation([0]*4+[1]*4)
    if c['training_schedule'][f'{f}:{b}']!=[KINDS[int(i)] for i in schedule]:raise ValueError('registered_schedule_derivation')
    return KINDS[int(schedule[ids.index(e)])]


def labels(row,c):
    if row['role']=='training':
        kind=training_operator(c,row['family'],row['bundle'],row['episode'])
        if row.get('training_operator')!=kind:raise ValueError('registered_training_operator')
        return {'parent',kind}
    if 'training_operator' in row:raise ValueError('query_has_no_exploration_draw')
    return {'parent',*KINDS}


def decide(rows,c,f,b,g):
    train=[r for r in rows if (r['family'],r['bundle'],r['role'])==(f,b,'training')]
    ids=[r['episode'] for r in train]
    if len(ids)!=8 or set(ids)!=set(c['training_episodes']):raise ValueError('complete_partial_training')
    means={};gains={};counts={}
    for k in KINDS:
        selected=[]
        for r in train:
            wanted=labels(r,c)
            if set(r['paths'])!=wanted:raise ValueError('unrevealed_training_operator')
            if k in wanted:selected.append(r)
        counts[k]=len(selected)
        if counts[k]!=4:raise ValueError('four_observed_returns_per_operator')
        means[k]=float(np.mean([number(r['paths'][k]['return']) for r in selected]))
        gains[k]=float(np.mean([number(r['paths'][k]['return'])-number(r['paths']['parent']['return']) for r in selected]))
    pick=lambda values:max(KINDS,key=lambda k:values[k])
    best=pick(gains);probs=g.mutation_probabilities()
    return dict(training_mean_kind=pick(means),credit_kind=pick(probs),paired_gain_kind=best,
        guarded_kind=best if gains[best]>0 else 'parent',training_means=means,training_gains=gains,observed_counts=counts,
        frozen_probabilities=probs,training_hash=digest([
            dict(episode=r['episode'],operator=r['training_operator'],paths={k:dict(actual_return=v['return'],cpu_s=v['cpu_s']) for k,v in r['paths'].items()})
            for r in sorted(train,key=lambda r:r['episode'])]))


def replay_learning(rows,c):
    final={}
    for f,b in itertools.product(c['families'],c['model_bundles']):
        g=StrategyGenerator(c['proposal_seed'],mutation_credit=True)
        for e in c['training_episodes']+c['evaluation_episodes']:
            row=next(r for r in rows if (r['family'],r['bundle'],r['episode'])==(f,b,e))
            if row['before']!={'learned':g.mutation_probabilities()}:raise ValueError('partial_training_probability_replay')
            if row['role']=='training':
                labels(row,c);panel.replay_feedback(g,row,c,kinds=(row['training_operator'],))
            elif row['decision']!=decide(rows,c,f,b,g):raise ValueError('training_only_partial_decision')
            if row['after']!={'learned':g.mutation_probabilities()}:raise ValueError('query_must_not_update')
        final[f'{f}:{b}']={'learned':g.mutation_probabilities()}
    return final


def validate(p,c):
    planned=len(c['families'])*len(c['model_bundles'])*(2*len(c['training_episodes'])+3*len(c['evaluation_episodes']))*200
    if c['real_cap']!=planned:raise ValueError('physical_partial_grid_cap')
    return panel.validate(p,c,labels=labels,replay=replay_learning)


def analyze(rows,c):
    out=panel.analyze(rows,c)
    for f,summary in out['families'].items():
        for model in summary['models']:
            chosen=[r for r in rows if (r['family'],r['bundle'],r['role'])==(f,model['bundle'],'evaluation')]
            for name,key in [('paired_gain','paired_gain_kind'),('guarded','guarded_kind')]:
                model['mean_returns'][name]=float(np.mean([r['paths'][r['decision'][key]]['return'] for r in chosen]))
        for a,b in [('paired_gain','uniform_expected'),('guarded','uniform_expected'),('credit_argmax','paired_gain'),
                    ('credit_argmax','guarded'),('training_mean','guarded')]:
            summary['contrasts'][a+'-minus-'+b]=panel.paired_contrast(summary['models'],a,b)
        for key in ('paired_gain','guarded'):
            summary['mean_returns'][key]=float(np.mean([m['mean_returns'][key] for m in summary['models']]))
    passed=all(f['selection_screen'] for f in out['families'].values())
    out['label']='exploratory_partial_feedback_selection_screen_passed' if passed else 'partial_feedback_selection_not_established'
    out['scope']='Eight single-child exploration trials; four/operator; frozen exploitation, not adaptive exploration or new-physics confirmation.'
    return out
