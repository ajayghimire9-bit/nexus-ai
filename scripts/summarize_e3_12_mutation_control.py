"""Stdlib-only independent arithmetic/export of the sealed E3.12 capture."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


def summarize_blocked(p,c):
    """Independent stdlib arithmetic; never calls the production selector."""
    def finite(x):
        if type(x) not in (int,float) or not math.isfinite(x):raise ValueError('finite_blocked_metric')
        return x
    families=['pendulum','acrobot'];bundles=[0,1];conditions=('random_balanced','public_blocked')
    if c['families']!=families or c['model_bundles']!=bundles or c['training_episodes']!=list(range(8)) or c['evaluation_episodes']!=list(range(8,12)):raise ValueError('fixed_blocked_export_grid')
    expected={(f,b,e,'training' if e<8 else 'evaluation') for f in families for b in bundles for e in range(12)}
    ids=[(r['family'],r['bundle'],r['episode'],r['role']) for r in p['rows']]
    if len(ids)!=len(expected) or set(ids)!=expected:raise ValueError('complete_blocked_export_grid')
    keys={f'{f}:{b}' for f in families for b in bundles}
    if set(p['reset_plans'])!=keys or set(p['sealed_decisions'])!=keys or set(p['analysis']['families'])!=set(families):raise ValueError('complete_blocked_export_models')
    phase={k:dict(physical_episodes=0,real_steps=0,path_cpu_s=0.) for k in ('training','evaluation')};result={}
    for f in families:
        models=[]
        for b in bundles:
            key=f'{f}:{b}';schedules=p['reset_plans'][key]['schedules']
            if set(schedules)!=set(conditions):raise ValueError('complete_blocked_schedules')
            for schedule in schedules.values():
                if set(schedule)!=set(map(str,range(8))) or sorted(schedule.values())!=['rank_blend']*4+['switch']*4:raise ValueError('balanced_export_schedules')
            rows=[r for r in p['rows'] if (r['family'],r['bundle'])==(f,b)]
            train=[r for r in rows if r['role']=='training'];query=[r for r in rows if r['role']=='evaluation']
            choices={};paired_choices={};training_diagnostics={}
            for condition in conditions:
                means={'parent':statistics.mean(finite(r['paths']['parent']['return']) for r in train)}
                for kind in ('switch','rank_blend'):
                    means[kind]=statistics.mean(finite(r['paths'][kind]['return']) for r in train if schedules[condition][str(r['episode'])]==kind)
                choice=max(('parent','switch','rank_blend'),key=means.get);choices[condition]=choice
                sealed=p['sealed_decisions'][key][condition]
                if sealed['choice']!=choice or sealed['observed_counts']!={'parent':8,'switch':4,'rank_blend':4}:raise ValueError('independent_blocked_choice')
                if set(sealed['training_means'])!=set(means) or any(abs(finite(sealed['training_means'][k])-v)>1e-9 for k,v in means.items()):raise ValueError('independent_blocked_means')
                gains={'parent':0.}
                for kind in ('switch','rank_blend'):
                    gains[kind]=statistics.mean(finite(r['paths'][kind]['return'])-finite(r['paths']['parent']['return'])
                        for r in train if schedules[condition][str(r['episode'])]==kind)
                paired_choices[condition]=max(gains,key=gains.get)
                groups={kind:statistics.mean(finite(r['paths']['parent']['return']) for r in train if schedules[condition][str(r['episode'])]==kind) for kind in ('switch','rank_blend')}
                training_diagnostics[condition]=dict(parent_group_means=groups,parent_pooled_mean=means['parent'],
                    parent_group_offsets={k:v-means['parent'] for k,v in groups.items()},
                    absolute_parent_group_gap=abs(groups['switch']-groups['rank_blend']),
                    raw_choice=choice,paired_choice=paired_choices[condition])
                sealed_paired=p['sealed_decisions'][key]['paired_secondary'][condition]
                if (sealed_paired['choice']!=paired_choices[condition] or set(sealed_paired['matched_advantages'])!=set(gains)
                    or any(abs(finite(sealed_paired['matched_advantages'][k])-v)>1e-9 for k,v in gains.items())
                    or sealed_paired['observed_counts']!={'parent':8,'switch':4,'rank_blend':4}):raise ValueError('independent_paired_gain_choice')
            for row in rows:
                wanted={'parent',*(s[str(row['episode'])] for s in schedules.values())} if row['role']=='training' else {'parent','switch','rank_blend'}
                if set(row['paths'])!=wanted:raise ValueError('independent_union_conditions')
                if row['role']=='evaluation' and row['decision']!=p['sealed_decisions'][key]:raise ValueError('independent_frozen_choice')
                for path in row['paths'].values():
                    rewards=[finite(s['reward']) for s in path['steps']]
                    if len(rewards)!=200 or abs(math.fsum(rewards)-finite(path['return']))>1e-8 or finite(path['cpu_s'])<=0:raise ValueError('independent_complete_union_path')
                    out=phase[row['role']];out['physical_episodes']+=1;out['real_steps']+=200;out['path_cpu_s']+=path['cpu_s']
            values=[]
            for row in query:
                returns={k:finite(v['return']) for k,v in row['paths'].items()}
                values.append({**{k:returns[v] for k,v in choices.items()},'parent':returns['parent'],
                    **{k+'_paired':returns[v] for k,v in paired_choices.items()},
                    'fixed_switch':returns['switch'],'fixed_blend':returns['rank_blend'],'uniform_expected':(returns['switch']+returns['rank_blend'])/2})
            models.append(dict(bundle=b,means={k:statistics.mean(v[k] for v in values) for k in values[0]},choices=choices,
                paired_choices=paired_choices,training_diagnostics=training_diagnostics))
        baseline_names=('random_balanced','parent','fixed_switch','fixed_blend','uniform_expected')
        prior=p['analysis']['families'][f]
        if set(prior['contrasts'])!=set(baseline_names):raise ValueError('complete_blocked_contrasts')
        contrasts={}
        for baseline in baseline_names:
            x=[m['means']['public_blocked']-m['means'][baseline] for m in models]
            mean=statistics.mean(x);half=12.7062047364*statistics.stdev(x)/math.sqrt(2)
            values=dict(mean=mean,ci95=[mean-half,mean+half],per_model=x)
            old=prior['contrasts'][baseline]
            if set(old)!=set(values):raise ValueError('complete_interval_fields')
            for k in values:
                a=old[k] if type(old[k]) is list else [old[k]];z=values[k] if type(values[k]) is list else [values[k]]
                if len(a)!=len(z) or any(abs(finite(i)-j)>1e-8 for i,j in zip(a,z)):raise ValueError('independent_blocked_interval')
            contrasts[baseline]=values
        primary=contrasts['random_balanced'];passed=primary['mean']>=1. and primary['ci95'][0]>0 and all(v>0 for v in primary['per_model'])
        if prior['screen_passed'] is not passed:raise ValueError('independent_blocked_screen')
        pairs=[('public_blocked_paired','random_balanced_paired'),('public_blocked_paired','public_blocked'),
               ('random_balanced_paired','random_balanced'),('public_blocked_paired','parent'),('random_balanced_paired','parent')]
        secondary={}
        if set(prior['secondary_contrasts'])!={a+'-minus-'+z for a,z in pairs}:raise ValueError('complete_secondary_contrasts')
        for a,z in pairs:
            x=[m['means'][a]-m['means'][z] for m in models];mean=statistics.mean(x);half=12.7062047364*statistics.stdev(x)/math.sqrt(2)
            values=dict(mean=mean,ci95=[mean-half,mean+half],per_model=x);old=prior['secondary_contrasts'][a+'-minus-'+z]
            if set(old)!=set(values):raise ValueError('secondary_interval_fields')
            for k in values:
                left=old[k] if type(old[k]) is list else [old[k]];right=values[k] if type(values[k]) is list else [values[k]]
                if len(left)!=len(right) or any(abs(finite(i)-j)>1e-8 for i,j in zip(left,right)):raise ValueError('independent_secondary_interval')
            secondary[a+'-minus-'+z]=values
        result[f]=dict(models=models,contrasts=contrasts,secondary_contrasts=secondary,screen_passed=passed)
    actual=sum(v['real_steps'] for v in phase.values())
    if actual!=p['resources']['completed']['real_steps'] or not 22400<=actual<=28800:raise ValueError('independent_union_resource_sum')
    label='exploratory_reset_blocking_screen_passed' if all(f['screen_passed'] for f in result.values()) else 'reset_blocking_not_established'
    if p['analysis']['label']!=label:raise ValueError('independent_blocked_label')
    return dict(families=result,phase_accounting=phase,label=label,physical_real_steps=actual,
                limitations='Masked shared panels; two pretrained models/family; no extra model replication from query paths.')


def summarize_operator(p,c,partial=False,retention=False):
    """Independent stdlib checks of balanced-panel selection and contrasts."""
    expected={(f,b,e,role) for role in ('training','evaluation') for f in c['families'] for b in c['model_bundles'] for e in c[role+'_episodes']}
    ids=[(r['family'],r['bundle'],r['episode'],r['role']) for r in p['rows']]
    if len(ids)!=len(expected) or set(ids)!=expected:raise ValueError('complete_operator_panel')
    kinds=('switch','rank_blend');families={};phase={k:dict(physical_episodes=0,real_steps=0,path_cpu_s=0.) for k in ('training','evaluation')};error=0.
    for r in p['rows']:
        required={'parent',*kinds}
        if partial and r['role']=='training':
            chosen=c['training_schedule'][f'{r["family"]}:{r["bundle"]}'][c['training_episodes'].index(r['episode'])]
            if r.get('training_operator')!=chosen:raise ValueError('registered_partial_operator')
            required={'parent',chosen}
        if set(r['paths'])!=required:raise ValueError('balanced_operator_conditions')
        for v in r['paths'].values():
            rewards=[s['reward'] for s in v['steps']]
            if len(rewards)!=200 or any(type(x) not in (int,float) or not math.isfinite(x) for x in rewards):raise ValueError('finite_complete_paths')
            error=max(error,abs(math.fsum(rewards)-v['return']))
            phase[r['role']]['physical_episodes']+=1;phase[r['role']]['real_steps']+=len(rewards);phase[r['role']]['path_cpu_s']+=v['cpu_s']
    if error>1e-8:raise ValueError('independent_reward_sum')
    for f in c['families']:
        models=[]
        for b in c['model_bundles']:
            train=[r for r in p['rows'] if (r['family'],r['bundle'],r['role'])==(f,b,'training')]
            query=[r for r in p['rows'] if (r['family'],r['bundle'],r['role'])==(f,b,'evaluation')]
            training_means={k:statistics.mean(r['paths'][k]['return'] for r in train if k in r['paths']) for k in kinds}
            gains={k:statistics.mean(r['paths'][k]['return']-r['paths']['parent']['return'] for r in train if k in r['paths']) for k in kinds}
            counts={k:sum(k in r['paths'] for r in train) for k in kinds}
            gain_kind=max(kinds,key=gains.get);guard=gain_kind if gains[gain_kind]>0 else 'parent'
            parent_means={'parent':statistics.mean(r['paths']['parent']['return'] for r in train),**training_means}
            parent_choice=max(('parent',*kinds),key=parent_means.get)
            choice=max(kinds,key=training_means.get);values=[]
            for r in query:
                if r['decision']['training_mean_kind']!=choice or any(abs(r['decision']['training_means'][k]-training_means[k])>1e-10 for k in kinds):raise ValueError('training_only_choice_replay')
                a,z=(r['paths'][k]['return'] for k in kinds);credit=r['decision']['credit_kind']
                entry=dict(parent=r['paths']['parent']['return'],fixed_switch=a,fixed_blend=z,uniform_expected=(a+z)/2,
                    training_mean=r['paths'][choice]['return'],credit_argmax=r['paths'][credit]['return'],retrospective_best=max(a,z))
                if partial:
                    d=r['decision']
                    if counts!={'switch':4,'rank_blend':4} or d['observed_counts']!=counts or d['paired_gain_kind']!=gain_kind or d['guarded_kind']!=guard:raise ValueError('partial_baseline_choice_replay')
                    if any(abs(d['training_gains'][k]-gains[k])>1e-10 for k in kinds):raise ValueError('paired_gain_training_replay')
                    entry.update(paired_gain=r['paths'][gain_kind]['return'],guarded=r['paths'][guard]['return'])
                if retention:
                    d=r['decision']['parent_inclusive']
                    if d['choice']!=parent_choice or d['two_child_choice']!=choice or d['observed_counts']!={'parent':8,'switch':4,'rank_blend':4}:raise ValueError('independent_parent_choice')
                    if any(abs(d['training_means'][k]-parent_means[k])>1e-10 for k in parent_means):raise ValueError('independent_parent_means')
                    entry['parent_inclusive']=r['paths'][parent_choice]['return']
                values.append(entry)
            means={k:statistics.mean(v[k] for v in values) for k in values[0]}
            models.append(dict(bundle=b,means=means,training_choice=choice,credit_choice=query[0]['decision']['credit_kind'],
                training_gap=training_means['switch']-training_means['rank_blend'],query_gap=means['fixed_switch']-means['fixed_blend'],
                query_wins=sum(v['training_mean']==v['retrospective_best'] for v in values)))
        contrasts={}
        if retention and not {'parent_inclusive-minus-'+k for k in ('training_mean','uniform_expected','parent','credit_argmax','fixed_switch','fixed_blend')}<=set(p['analysis']['families'][f]['contrasts']):raise ValueError('required_parent_contrasts')
        for name,prior in p['analysis']['families'][f]['contrasts'].items():
            a,z=name.split('-minus-');x=[r['means'][a]-r['means'][z] for r in models];mean=statistics.mean(x);half=12.7062047364*statistics.stdev(x)/math.sqrt(2)
            result=dict(mean=mean,ci95=[mean-half,mean+half],per_model=x)
            if abs(mean-prior['mean'])>1e-9 or any(abs(a-b)>1e-8 for a,b in zip(result['ci95'],prior['ci95'])):raise ValueError('independent_interval_replay')
            contrasts[name]=result
        families[f]=dict(models=models,contrasts=contrasts)
        if retention:
            a=contrasts['parent_inclusive-minus-training_mean'];u=contrasts['parent_inclusive-minus-uniform_expected'];v=contrasts['parent_inclusive-minus-parent']
            passed=a['mean']>=c['practical_margin'] and a['ci95'][0]>0 and u['mean']>=c['uniform_margin'] and u['ci95'][0]>0 and v['ci95'][0]>-c['parent_noninferiority_margin']
            families[f]['parent_retention_screen']=passed
            if p['analysis']['families'][f]['parent_retention_screen'] is not passed:raise ValueError('independent_parent_screen')
    if retention:
        label='exploratory_parent_retention_screen_passed' if all(x['parent_retention_screen'] for x in families.values()) else 'parent_retention_not_established'
        if p['analysis']['label']!=label:raise ValueError('independent_parent_label')
    return dict(families=families,phase_accounting=phase,max_independent_reward_sum_error=error,label=p['analysis']['label'],
        limitations=('Two models/family; single-child training feedback, complete query panels.' if partial else 'Two models/family; diagnostic full-information panel.')+' Expected uniform and retrospective best reuse executed paths; not extra controller replications.')


def summarize(p,c):
    expected={(f,b,e,role) for role in ('training','evaluation') for f in c['families'] for b in c['model_bundles'] for e in c[role+'_episodes']}
    ids=[(r['family'],r['bundle'],r['episode'],r['role']) for r in p['rows']]
    if len(ids)!=len(expected) or set(ids)!=expected:raise ValueError('complete_grid')
    maxerr=0.;same=0;changes=0;by_phase={r:dict(episodes=0,real_steps=0,path_cpu_s=0.) for r in ('training','evaluation')}
    for row in p['rows']:
        labels={'parent','learned','random'}|({'fixed_blend'} if row['role']=='evaluation' else set())
        if set(row['paths'])!=labels:raise ValueError('condition_grid')
        for path in row['paths'].values():
            values=[s['reward'] for s in path['steps']]
            if len(values)!=200 or any(type(x) not in (int,float) or not math.isfinite(x) for x in values):raise ValueError('finite_complete_rewards')
            maxerr=max(maxerr,abs(math.fsum(values)-path['return']))
            out=by_phase[row['role']];out['episodes']+=1;out['real_steps']+=len(values);out['path_cpu_s']+=path['cpu_s']
        same+=row['paths']['learned']['steps']==row['paths']['random']['steps']
        changes+=row['before']['learned']!=row['after']['learned']
    if maxerr>1e-8:raise ValueError('independent_reward_sum')
    families={}
    for f in c['families']:
        modelmeans=[]
        for b in c['model_bundles']:
            rows=[r for r in p['rows'] if (r['family'],r['bundle'],r['role'])==(f,b,'evaluation')]
            modelmeans.append({k:statistics.mean(r['paths'][k]['return'] for r in rows) for k in ('learned','random','parent','fixed_blend')})
        contrasts={}
        for k in ('random','parent','fixed_blend'):
            values=[r['learned']-r[k] for r in modelmeans];mean=statistics.mean(values);half=12.7062047364*statistics.stdev(values)/math.sqrt(2)
            contrasts[k]=dict(mean=mean,ci95=[mean-half,mean+half],per_model=values)
            prior=p['analysis']['families'][f]['contrasts'][k]
            if not math.isclose(mean,prior['mean'],abs_tol=1e-10,rel_tol=0) or any(abs(x-y)>1e-9 for x,y in zip(contrasts[k]['ci95'],prior['ci95'])):raise ValueError('independent_statistical_replay')
        families[f]=dict(contrasts=contrasts,mean_returns={k:statistics.mean(r[k] for r in modelmeans) for k in modelmeans[0]})
    return dict(families=families,phase_accounting=by_phase,identical_learned_random_paths=same,
        training_probability_updates=changes,query_choice_differences=sum(r['strategies']['learned']!=r['strategies']['random'] for r in p['rows'] if r['role']=='evaluation'),
        final_probabilities=p['final_policies'],max_independent_reward_sum_error=maxerr,
        interpretation='No sampled proposal changes; zero empirical interval does not prove equality of expected policies or future returns.',
        next_question='Do both operators have stable paired return differences when evaluated at every fresh reset?',
        label=p['analysis']['label'])


def main(operator=False,partial=False,retention=False,blocked=False):
    prefix='e3_12f_reset_blocked' if blocked else 'e3_12d_parent' if retention else 'e3_12c_partial' if partial else 'e3_12b_operator' if operator else 'e3_12_mutation'
    capture='e3_12f_reset_blocked' if blocked else 'e3_12d_parent_retention' if retention else 'e3_12c_partial_feedback' if partial else 'e3_12b_operator_headroom' if operator else 'e3_12_mutation_control'
    config_name='e3_12f_reset_blocked_runtime_v2' if blocked else capture
    raw=ROOT/('artifacts/'+capture+'.json');p=json.loads(raw.read_text());c=json.loads((ROOT/('configs/'+config_name+'.json')).read_text());v=json.loads((ROOT/('artifacts/'+prefix+'_validation.json')).read_text())
    if not p['declared_complete'] or v['valid'] is not True or v['result_sha256']!=hashlib.sha256(raw.read_bytes()).hexdigest():raise ValueError('sealed_complete_capture_required')
    s=summarize_blocked(p,c) if blocked else summarize_operator(p,c,partial=partial or retention,retention=retention) if operator or partial or retention else summarize(p,c)
    s.update(result_sha256=v['result_sha256'],source_commit=p['provenance']['source_commit'],session_used_after_s=v['session_used_after_s'],session_remaining_after_s=v['session_remaining_after_s'])
    target=ROOT/('artifacts/'+prefix+'_summary.json')
    with target.open('x') as stream:stream.write(json.dumps(s,indent=2,allow_nan=False)+'\n')
    with (ROOT/('artifacts/'+prefix+'_returns.csv')).open('x') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(['family','bundle','episode','role','condition','strategy_kind','actual_return','parent_difference','path_cpu_s'])
        for row in p['rows']:
            for name,path in row['paths'].items():
                kind=row['strategies'][name]['kind'] if name in row['strategies'] else ('leaf' if name=='parent' else 'rank_blend')
                writer.writerow([row['family'],row['bundle'],row['episode'],row['role'],name,kind,path['return'],path['return']-row['paths']['parent']['return'],path['cpu_s']])
    print(json.dumps(s,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();profiles=parser.add_mutually_exclusive_group();profiles.add_argument('--operator-headroom',action='store_true');profiles.add_argument('--partial-feedback',action='store_true');profiles.add_argument('--parent-retention',action='store_true');profiles.add_argument('--reset-blocked',action='store_true');args=parser.parse_args()
    main(args.operator_headroom,args.partial_feedback,args.parent_retention,args.reset_blocked)
