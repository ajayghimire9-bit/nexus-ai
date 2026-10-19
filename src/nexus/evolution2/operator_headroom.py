"""Balanced operator-panel contracts over the existing mutation/host stack.

No models/environments are constructed here. Query data cannot fit selectors.
"""
import itertools
import math
import numpy as np
from nexus.evolution1.catalogue import digest
from nexus.evolution2.generated_strategies import StrategyGenerator,compose
from nexus.evolution2.full_policy_source import controllers
from nexus.evolution2.mutation_control import seed_pair,requested_seeds,expected,number,check_real_step

METHODS=('learned',)
KINDS=('switch','rank_blend')


def operators():
    parent=controllers()['successor_anchor'];partner=controllers()['flat_anchor'].left
    return {k:compose(k,parent.left,partner,.25) for k in KINDS}


def decide(rows,c,f,b,g):
    train=[r for r in rows if (r['family'],r['bundle'],r['role'])==(f,b,'training')]
    ids=[r['episode'] for r in train]
    if len(ids)!=len(c['training_episodes']) or set(ids)!=set(c['training_episodes']):raise ValueError('complete_training_before_query')
    means={k:float(np.mean([number(r['paths'][k]['return']) for r in train])) for k in KINDS}
    probabilities=g.mutation_probabilities()
    pick=lambda values:max(KINDS,key=lambda k:values[k])  # exact ties choose switch
    return dict(training_mean_kind=pick(means),credit_kind=pick(probabilities),training_means=means,
        frozen_probabilities=probabilities,training_hash=digest([
            dict(episode=r['episode'],paths={k:dict(actual_return=r['paths'][k]['return'],cpu_s=r['paths'][k]['cpu_s']) for k in ('parent',*KINDS)})
            for r in sorted(train,key=lambda r:r['episode'])]))


def replay_feedback(g,row,c,kinds=KINDS):
    parent=controllers()['successor_anchor']
    for kind,child in operators().items():
        if kind not in kinds:continue
        q=row['protocol'];pair=[]
        for label,strategy in [('parent',parent),(kind,child)]:
            path=row['paths'][label]
            pair.append(dict(kind='observed_full_policy_return',phase='training',strategy=strategy.fingerprint,
                pair_id=q['pair_id']+':'+kind,context_hash=q['context_hash'],reset_seed=q['reset_seed'],
                planner_seed=q['planner_seed'],horizon=200,planning_cap=1536,cpu_s=path['cpu_s'],
                event=digest([label,kind,q['pair_id']]),return_value=path['return']))
        for value in pair:value['return']=value.pop('return_value')
        g.observe_mutation(parent,child,*pair,return_scale=c['return_scale'])


def replay_learning(rows,c):
    final={}
    for f,b in itertools.product(c['families'],c['model_bundles']):
        g=StrategyGenerator(c['proposal_seed'],mutation_credit=True)
        for e in c['training_episodes']+c['evaluation_episodes']:
            row=next(r for r in rows if (r['family'],r['bundle'],r['episode'])==(f,b,e))
            if row['before']!={'learned':g.mutation_probabilities()}:raise ValueError('training_probability_replay')
            if row['role']=='training':replay_feedback(g,row,c)
            else:
                if row['decision']!=decide(rows,c,f,b,g):raise ValueError('sealed_training_only_decision')
            if row['after']!={'learned':g.mutation_probabilities()}:raise ValueError('query_must_not_update')
        final[f'{f}:{b}']={'learned':g.mutation_probabilities()}
    return final


def validate(p,c,*,labels=None,replay=None,planned_real_steps=None):
    ids=[(r['family'],r['bundle'],r['episode'],r['role']) for r in p['rows']]
    if len(ids)!=len(expected(c)) or set(ids)!=expected(c):raise ValueError('complete_registered_panel_grid')
    for row in p['rows']:
        required={'parent',*KINDS} if labels is None else labels(row,c)
        if set(row['paths'])!=required or row['strategies']!={k:s.payload() for k,s in operators().items() if k in required}:raise ValueError('complete_operator_grid')
        reset,planner=seed_pair(c,row['family'],row['bundle'],row['episode'])
        q=row['protocol']
        if q['phase']!=row['role'] or q['reset_seed']!=reset or q['planner_seed']!=planner or q['context_hash']!=digest(row['initial_observation']) or q['horizon']!=200 or q['planning_cap']!=1536:raise ValueError('registered_panel_provenance')
        for name,path in row['paths'].items():
            if len(path['steps'])!=200 or path['restored_hash']!=row['restored_hash'] or number(path['cpu_s'])<=0:raise ValueError('complete_restored_path')
            prev=row['initial_observation']
            for tick,step in enumerate(path['steps']):
                check_real_step(step,prev,tick,planner+tick,row['family']);prev=step['next_obs']
            if not math.isclose(number(path['return']),sum(s['reward'] for s in path['steps']),rel_tol=0,abs_tol=1e-8):raise ValueError('actual_reward_sum')
    replay=replay_learning if replay is None else replay
    if replay(p['rows'],c)!=p['final_policies']:raise ValueError('sealed_final_policy')
    actual=p['resources']['completed']
    wanted_steps=c['real_cap'] if planned_real_steps is None else planned_real_steps
    if type(wanted_steps) is not int or not 0<wanted_steps<=c['real_cap']:raise ValueError('planned_physical_panel_cap')
    if actual!=p['resources']['reserved'] or type(actual['real_steps']) is not int or actual['real_steps']!=wanted_steps or any(p['resources']['unknown_upper'].values()):raise ValueError('complete_metered_panel')
    for key,cap in [('model_calls','model_call_cap'),('network_forwards','network_forward_cap'),('imagined_transitions','imagined_cap')]:
        if type(actual[key]) is not int or not 0<actual[key]<=c[cap] or p['observed'][key]!=actual[key]:raise ValueError('observed_neural_work')
    mids=[(r['family'],r['bundle']) for r in p['models']]
    wanted=set(itertools.product(c['families'],c['model_bundles']))
    if len(mids)!=len(wanted) or set(mids)!=wanted or any(r['before']!=r['after'] for r in p['models']):raise ValueError('frozen_model_grid')
    return True


def values(row):
    r={k:row['paths'][k]['return'] for k in ('parent',*KINDS)}
    return dict(parent=r['parent'],fixed_switch=r['switch'],fixed_blend=r['rank_blend'],
        uniform_expected=(r['switch']+r['rank_blend'])/2,
        training_mean=r[row['decision']['training_mean_kind']],credit_argmax=r[row['decision']['credit_kind']],
        retrospective_best=max(r['switch'],r['rank_blend']))


def paired_contrast(models,a,b):
    x=[m['mean_returns'][a]-m['mean_returns'][b] for m in models]
    mean=float(np.mean(x));half=12.7062047364*float(np.std(x,ddof=1))/math.sqrt(2)
    return dict(mean=mean,ci95=[mean-half,mean+half],per_model=x)


def analyze(rows,c):
    out={};learned_screen=True;headroom_screen=True
    for f in c['families']:
        models=[]
        for b in c['model_bundles']:
            selected=[r for r in rows if (r['family'],r['bundle'],r['role'])==(f,b,'evaluation')]
            paths=[values(r) for r in selected]
            means={k:float(np.mean([r[k] for r in paths])) for k in paths[0]}
            first=selected[0]['decision']
            models.append(dict(bundle=b,mean_returns=means,decision=first,
                training_mean_win_rate=float(np.mean([v['training_mean']>=v['retrospective_best'] for v in paths])),
                query_operator_gaps=[r['paths']['switch']['return']-r['paths']['rank_blend']['return'] for r in selected]))
        contrasts={}
        for a,b in [('training_mean','uniform_expected'),('credit_argmax','uniform_expected'),('credit_argmax','training_mean'),
                    ('training_mean','parent'),('training_mean','fixed_switch'),('training_mean','fixed_blend'),('retrospective_best','uniform_expected')]:
            contrasts[a+'-minus-'+b]=paired_contrast(models,a,b)
        primary=contrasts['training_mean-minus-uniform_expected'];available=contrasts['retrospective_best-minus-uniform_expected']
        passed=primary['mean']>=c['practical_margin'] and primary['ci95'][0]>0 and all(x>0 for x in primary['per_model'])
        headroom=available['mean']>=c['headroom_margin'];learned_screen &= passed;headroom_screen &= headroom
        out[f]=dict(models=models,contrasts=contrasts,selection_screen=passed,finite_suite_headroom_screen=headroom,
            mean_returns={k:float(np.mean([m['mean_returns'][k] for m in models])) for k in models[0]['mean_returns']})
    label=('exploratory_training_mean_selection_screen_passed' if learned_screen else
        'headroom_visible_selection_not_established' if headroom_screen else 'stable_operator_selection_not_established')
    return dict(families=out,label=label,unit='two independent frozen source models per family; df1 unadjusted exploratory intervals',
        dependent_metrics='Best-minus-uniform equals half absolute operator gap; its regret reductions are the same evidence. Uniform is a paired expected mixture, not another executed controller.')
