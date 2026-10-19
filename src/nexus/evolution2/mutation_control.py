"""Measured mutation-credit study: data-boundary/statistics glue, not a learner.

Uses existing StrategyGenerator, measured_mutation, planners and Host ledger.
"""
import itertools
import math
import numpy as np
from nexus.evolution1.catalogue import digest
from nexus.evolution2.generated_strategies import StrategyGenerator, compose
from nexus.evolution2.full_policy_source import controllers
from nexus.evolution2.calibration_execution import check_real_step

METHODS=('learned','random')


def seed_pair(c,f,b,e):
    offset=c['families'].index(f)*100000+b*20000+e*1000
    return c['env_seed_base']+offset,c['planner_seed_base']+offset


def requested_seeds(c):
    roles=[set(),set()]
    for f,b,e in itertools.product(c['families'],c['model_bundles'],c['training_episodes']+c['evaluation_episodes']):
        reset,planner=seed_pair(c,f,b,e);roles[0].add(reset);roles[1].update(range(planner,planner+200))
    if roles[0]&roles[1]:raise ValueError('seed_role_collision')
    return roles[0]|roles[1]


def expected(c):
    return {(f,b,e,role) for role in ('training','evaluation') for f,b,e in itertools.product(c['families'],c['model_bundles'],c[role+'_episodes'])}


def proposal_uniform(c,f,b,e):
    # Separate from environment/planner streams; no query or feedback input.
    return float(np.random.default_rng(np.random.SeedSequence([c['proposal_seed'],c['families'].index(f),b,e])).random())


def number(x):
    if type(x) not in (int,float) or not math.isfinite(x):raise ValueError('finite_numeric_metric')
    return x


def replay_learning(rows,c):
    models={}
    parent=controllers()['successor_anchor'];partner=controllers()['flat_anchor'].left
    for f,b in itertools.product(c['families'],c['model_bundles']):
        generators={m:StrategyGenerator(c['proposal_seed'],adaptive=m=='learned',mutation_credit=True) for m in METHODS}
        for e in c['training_episodes']+c['evaluation_episodes']:
            row=next(r for r in rows if (r['family'],r['bundle'],r['episode'])==(f,b,e))
            for m,g in generators.items():
                probs=g.mutation_probabilities()
                if row['before'][m]!=probs:raise ValueError('training_only_policy_replay')
                child=g.paired_child(parent,partner,proposal_uniform(c,f,b,e))
                if child.payload()!=row['strategies'][m]:raise ValueError('feedback_independent_proposal_replay')
                if row['role']=='training':
                    a,bpath=row['paths']['parent'],row['paths'][m]
                    protocol=row['protocol']
                    pair=[]
                    for label,strategy,path in [('parent',parent,a),(m,child,bpath)]:
                        pair.append(dict(kind='observed_full_policy_return',phase='training',strategy=strategy.fingerprint,
                            pair_id=protocol['pair_id'],context_hash=protocol['context_hash'],reset_seed=protocol['reset_seed'],
                            planner_seed=protocol['planner_seed'],horizon=200,planning_cap=1536,return_value=sum(x['reward'] for x in path['steps']),
                            cpu_s=path['cpu_s'],event=digest([label,f,b,e])))
                    for item in pair:item['return']=item.pop('return_value')
                    g.observe_mutation(parent,child,*pair,return_scale=c['return_scale'])
                if row['after'][m]!=g.mutation_probabilities():raise ValueError('frozen_evaluation_policy')
        models[f'{f}:{b}']={m:g.mutation_probabilities() for m,g in generators.items()}
    return models


def validate(p,c):
    ids=[(r['family'],r['bundle'],r['episode'],r['role']) for r in p['rows']]
    if len(ids)!=len(expected(c)) or set(ids)!=expected(c):raise ValueError('complete_locked_episode_grid')
    for r in p['rows']:
        labels={'parent',*METHODS}|({'fixed_blend'} if r['role']=='evaluation' else set())
        if set(r['paths'])!=labels or set(r['before'])!=set(METHODS) or set(r['after'])!=set(METHODS):raise ValueError('complete_condition_grid')
        reset,planner=seed_pair(c,r['family'],r['bundle'],r['episode'])
        for path in r['paths'].values():
            if len(path['steps'])!=200 or path['restored_hash']!=r['restored_hash']:raise ValueError('complete_paired_path')
            number(path['cpu_s'])
            prev=r['initial_observation']
            for tick,step in enumerate(path['steps']):
                check_real_step(step,prev,tick,planner+tick,r['family']);prev=step['next_obs']
            if not math.isclose(number(path['return']),sum(s['reward'] for s in path['steps']),abs_tol=1e-8,rel_tol=0):raise ValueError('reward_sum')
        q=r['protocol']
        if q['reset_seed']!=reset or q['planner_seed']!=planner or q['context_hash']!=digest(r['initial_observation']):raise ValueError('registered_path_provenance')
    final=replay_learning(p['rows'],c)
    if final!=p['final_policies']:raise ValueError('final_policy_replay')
    if p['resources']['completed']['real_steps']!=c['real_cap'] or any(p['resources']['unknown_upper'].values()):raise ValueError('complete_physical_execution')
    for key in ('model_calls','network_forwards','imagined_transitions'):
        if p['observed'][key]!=p['resources']['completed'][key]:raise ValueError('instrumented_calls_reconcile')
    modelids=[(r['family'],r['bundle']) for r in p['models']]
    if len(modelids)!=4 or set(modelids)!=set(itertools.product(c['families'],c['model_bundles'])) or any(r['before']!=r['after'] for r in p['models']):raise ValueError('frozen_model_grid')
    return True


def analyze(rows,c):
    result={};screen=True
    for f in c['families']:
        models=[]
        for b in c['model_bundles']:
            selected=[r for r in rows if (r['family'],r['bundle'],r['role'])==(f,b,'evaluation')]
            means={m:float(np.mean([r['paths'][m]['return'] for r in selected])) for m in ('learned','random','parent','fixed_blend')}
            models.append(dict(bundle=b,means=means))
        contrasts={}
        for baseline in ('random','parent','fixed_blend'):
            x=[r['means']['learned']-r['means'][baseline] for r in models]
            mean=float(np.mean(x));half=12.7062047364*float(np.std(x,ddof=1))/math.sqrt(2)
            contrasts[baseline]=dict(mean=mean,ci95=[mean-half,mean+half],per_model=x)
        passed=contrasts['random']['mean']>=c['practical_margin'] and contrasts['random']['ci95'][0]>0 and all(x>0 for x in contrasts['random']['per_model'])
        screen &= passed
        result[f]=dict(models=models,contrasts=contrasts,screen=passed,
            mean_returns={m:float(np.mean([r['means'][m] for r in models])) for m in models[0]['means']})
    return dict(families=result,label='exploratory_mutation_screen_passed' if screen else 'useful_mutation_learning_not_established',
        unit='Two independently pretrained source models per family; unadjusted exploratory t intervals df1, no new-physics confirmation.')
