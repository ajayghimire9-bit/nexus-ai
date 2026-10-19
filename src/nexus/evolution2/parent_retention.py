"""E3.12D selection/statistics adapter; reuses the existing partial-feedback stack.

No new planner, learner, memory, meter or evaluator. Historical C is unchanged.
"""
import numpy as np
from nexus.evolution2 import partial_feedback as partial
from nexus.evolution2 import operator_headroom as panel
from nexus.evolution2.partial_feedback import METHODS,KINDS,operators,seed_pair,requested_seeds,check_real_step,training_operator


def validate_config(c):
    if c['version']!='e3_12d_parent_retention_v1' or c['families']!=['pendulum','acrobot'] or c['model_bundles']!=[0,1]:raise ValueError('locked_retention_models')
    for k,v in dict(time_cap_s=300,real_cap=22400,imagined_cap=34406400,model_call_cap=1120000,network_forward_cap=1120000).items():
        if type(c[k]) is not int or c[k]!=v:raise ValueError('locked_retention_caps')
    if c['training_episodes']!=list(range(8)) or c['evaluation_episodes']!=list(range(8,12)):raise ValueError('locked_retention_grid')
    for k in ('practical_margin','uniform_margin','parent_noninferiority_margin'):
        if type(c[k]) is not float or c[k]!=1.:raise ValueError('locked_retention_threshold')
    if c['return_scale']!=100. or c['headroom_margin']!=5.:raise ValueError('unchanged_credit_and_secondary_rule')
    if set(c['training_schedule'])!={f'{f}:{b}' for f in c['families'] for b in c['model_bundles']}:raise ValueError('complete_schedule_grid')
    for f in c['families']:
        for b in c['model_bundles']:
            for e in c['training_episodes']:training_operator(c,f,b,e)
    return True


def decide(rows,c,f,b,g):
    result=partial.decide(rows,c,f,b,g)
    result['parent_inclusive']=partial.parent_inclusive_decision(rows,c,f,b)
    return result


def replay_learning(rows,c):return partial.replay_learning(rows,c,decision=decide)


def validate(p,c):
    validate_config(c)
    return panel.validate(p,c,labels=partial.labels,replay=replay_learning)


def analyze(rows,c):
    validate_config(c);out=partial.analyze(rows,c)
    for f,summary in out['families'].items():
        for model in summary['models']:
            query=[r for r in rows if (r['family'],r['bundle'],r['role'])==(f,model['bundle'],'evaluation')]
            actual=[r['paths'][r['decision']['parent_inclusive']['choice']]['return'] for r in query]
            model['mean_returns']['parent_inclusive']=float(np.mean(actual))
            model['parent_retained']=query[0]['decision']['parent_inclusive']['choice']=='parent'
            model['query_cases']=[dict(episode=r['episode'],choice=r['decision']['parent_inclusive']['choice'],
                selected_return=v,parent_return=r['paths']['parent']['return'],
                selected_minus_parent=v-r['paths']['parent']['return'],harmful_change=v<r['paths']['parent']['return']) for r,v in zip(query,actual)]
            model['harmful_change_rate']=float(np.mean([r['harmful_change'] for r in model['query_cases']]))
        for baseline in ('training_mean','uniform_expected','parent','credit_argmax','fixed_switch','fixed_blend'):
            summary['contrasts']['parent_inclusive-minus-'+baseline]=panel.paired_contrast(summary['models'],'parent_inclusive',baseline)
        summary['mean_returns']['parent_inclusive']=float(np.mean([m['mean_returns']['parent_inclusive'] for m in summary['models']]))
        a=summary['contrasts']['parent_inclusive-minus-training_mean'];u=summary['contrasts']['parent_inclusive-minus-uniform_expected'];p=summary['contrasts']['parent_inclusive-minus-parent']
        summary['parent_retention_screen']=bool(a['mean']>=c['practical_margin'] and a['ci95'][0]>0
            and u['mean']>=c['uniform_margin'] and u['ci95'][0]>0 and p['ci95'][0]>-c['parent_noninferiority_margin'])
        summary['retained_parent_models']=sum(m['parent_retained'] for m in summary['models'])
    out['label']='exploratory_parent_retention_screen_passed' if all(s['parent_retention_screen'] for s in out['families'].values()) else 'parent_retention_not_established'
    out['scope']='Fresh source-model query episodes, fixed balanced single-child exploration; no new-model or changed-physics generalization.'
    out['dependent_metrics']+=' Parent retention makes parent differences identically zero for that model; shared selected paths are not independent evidence.'
    return out
