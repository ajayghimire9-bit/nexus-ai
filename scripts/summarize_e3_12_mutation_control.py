"""Stdlib-only independent arithmetic/export of the sealed E3.12 capture."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


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


def main():
    raw=ROOT/'artifacts/e3_12_mutation_control.json';p=json.loads(raw.read_text());c=json.loads((ROOT/'configs/e3_12_mutation_control.json').read_text());v=json.loads((ROOT/'artifacts/e3_12_mutation_validation.json').read_text())
    if not p['declared_complete'] or v['valid'] is not True or v['result_sha256']!=hashlib.sha256(raw.read_bytes()).hexdigest():raise ValueError('sealed_complete_capture_required')
    s=summarize(p,c);s.update(result_sha256=v['result_sha256'],source_commit=p['provenance']['source_commit'],session_used_after_s=v['session_used_after_s'],session_remaining_after_s=v['session_remaining_after_s'])
    target=ROOT/'artifacts/e3_12_mutation_summary.json'
    with target.open('x') as stream:stream.write(json.dumps(s,indent=2,allow_nan=False)+'\n')
    with (ROOT/'artifacts/e3_12_mutation_returns.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['family','bundle','episode','role','condition','strategy_kind','actual_return','parent_difference','path_cpu_s'])
        for row in p['rows']:
            for name,path in row['paths'].items():
                kind=row['strategies'][name]['kind'] if name in ('learned','random') else ('leaf' if name=='parent' else 'rank_blend')
                writer.writerow([row['family'],row['bundle'],row['episode'],row['role'],name,kind,path['return'],path['return']-row['paths']['parent']['return'],path['cpu_s']])
    print(json.dumps(s,indent=2))


if __name__=='__main__':main()
