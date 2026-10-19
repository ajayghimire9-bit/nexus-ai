"""Stdlib-only independent arithmetic/export of the sealed E3.12 capture."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


def summarize_operator(p,c,partial=False):
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
                values.append(entry)
            means={k:statistics.mean(v[k] for v in values) for k in values[0]}
            models.append(dict(bundle=b,means=means,training_choice=choice,credit_choice=query[0]['decision']['credit_kind'],
                training_gap=training_means['switch']-training_means['rank_blend'],query_gap=means['fixed_switch']-means['fixed_blend'],
                query_wins=sum(v['training_mean']==v['retrospective_best'] for v in values)))
        contrasts={}
        for name,prior in p['analysis']['families'][f]['contrasts'].items():
            a,z=name.split('-minus-');x=[r['means'][a]-r['means'][z] for r in models];mean=statistics.mean(x);half=12.7062047364*statistics.stdev(x)/math.sqrt(2)
            result=dict(mean=mean,ci95=[mean-half,mean+half],per_model=x)
            if abs(mean-prior['mean'])>1e-9 or any(abs(a-b)>1e-8 for a,b in zip(result['ci95'],prior['ci95'])):raise ValueError('independent_interval_replay')
            contrasts[name]=result
        families[f]=dict(models=models,contrasts=contrasts)
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


def main(operator=False,partial=False):
    prefix='e3_12c_partial' if partial else 'e3_12b_operator' if operator else 'e3_12_mutation'
    capture='e3_12c_partial_feedback' if partial else 'e3_12b_operator_headroom' if operator else 'e3_12_mutation_control'
    raw=ROOT/('artifacts/'+capture+'.json');p=json.loads(raw.read_text());c=json.loads((ROOT/('configs/'+capture+'.json')).read_text());v=json.loads((ROOT/('artifacts/'+prefix+'_validation.json')).read_text())
    if not p['declared_complete'] or v['valid'] is not True or v['result_sha256']!=hashlib.sha256(raw.read_bytes()).hexdigest():raise ValueError('sealed_complete_capture_required')
    s=summarize_operator(p,c,partial=partial) if operator or partial else summarize(p,c)
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
    parser=argparse.ArgumentParser();profiles=parser.add_mutually_exclusive_group();profiles.add_argument('--operator-headroom',action='store_true');profiles.add_argument('--partial-feedback',action='store_true');args=parser.parse_args()
    main(args.operator_headroom,args.partial_feedback)
