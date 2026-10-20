"""Fresh balanced readout fixtures and stdlib completeness/statistics.

No oracle outcome is passed into features or planning. Greedy is privileged
structured-state reference, not evidence of learned reasoning.
"""
import math


def require_manifest(r,root):
    import hashlib,json
    path=root/'artifacts/seed_readout_manifest.json'
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=r.get('manifest_sha256'):raise ValueError('saved_manifest_required')
    m=json.loads(path.read_text())
    if m['config_sha256']!=r['config_sha256'] or m['execution_sha']!=r['execution_sha'] or m['source_hash']!=r['source_hash'] or [h['seed'] for h in m['heads']]!=r['config']['readout_seeds']:raise ValueError('manifest_provenance')
    for h in m['heads']:
        p=root/h['checkpoint']
        if p.parent!=root/'artifacts' or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=h['sha256']:raise ValueError('manifest_checkpoint')
    return True


def interval(values,t=2.364624251):
    if len(values)!=8 or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('eight_task_pairs_required')
    mean=sum(values)/8;se=(sum((v-mean)**2 for v in values)/7/8)**.5
    return dict(mean=mean,ci95=[mean-t*se,mean+t*se],paired_task_values=values)


def summarize(r):
    c=r['config'];average=lambda xs:sum(xs)/len(xs)
    ranking={m:{k:average([float(s['metrics'][m][k]) for s in r['audit']]) for k in ('regret','optimal','reward_mae')} for m in ['frozen']+[f'readout_{s}' for s in c['readout_seeds']]}
    controls={m:dict(mean_return=average([e['return_sum'] for v in r['control'].values() for e in v[m]]),success=average([float(e['success']) for v in r['control'].values() for e in v[m]])) for m in c['methods']}
    contrasts={}
    for baseline in ('frozen','random','greedy','latent_mpc'):
        contrasts[baseline]=interval([average([e['return_sum'] for s in c['readout_seeds'] for e in r['control'][str(t)][f'readout_{s}']])-average([e['return_sum'] for e in r['control'][str(t)][baseline]]) for t in c['control_task_seeds']])
    learned=average([ranking[f'readout_{s}']['regret'] for s in c['readout_seeds']]);frozen=ranking['frozen']['regret']
    success=average([controls[f'readout_{s}']['success'] for s in c['readout_seeds']])
    passed=(frozen>1e-8 and learned<=frozen*(1-c['minimum_regret_reduction']) and success>=controls['frozen']['success']-c['maximum_goal_regression'] and contrasts['frozen']['ci95'][0]>=-c['maximum_return_regression'])
    return dict(ranking=ranking,control=controls,paired_returns=contrasts,screen_passed=passed,unit='eight_fresh_goal_task_streams_conditional_on_one_frozen_core')


def validate(r,c):
    from .grounded_audit import audit_episode
    finite=lambda x:type(x) in (int,float) and math.isfinite(x)
    if r['config']!=c:raise ValueError('locked_config')
    if [m['seed'] for m in r['models']]!=c['readout_seeds']:raise ValueError('complete_readout_seeds')
    count=0
    for split in ('source','development','audit'):
        if [s['seed'] for s in r[split]]!=list(range(c[split]['start'],c[split]['start']+c[split]['states'])):raise ValueError('complete_state_grid')
        for row in r[split]:
            if len(row['actual'])!=9 or any(not finite(v) for v in row['actual']):raise ValueError('nine_finite_outcomes')
            if split=='audit':
                expected={'frozen'}|{f'readout_{s}' for s in c['readout_seeds']}
                if set(row['scores'])!=expected or set(row['metrics'])!=expected:raise ValueError('complete_ranking_conditions')
                for scores in row['scores'].values():
                    if len(scores)!=9 or any(not finite(v) for v in scores):raise ValueError('finite_score_grid')
                for m,v in row['metrics'].items():
                    if set(v)!={'selected','regret','optimal','pairwise_accuracy','score_range','reward_mae','uniform_expected_regret'} or type(v['optimal']) is not bool or any(not finite(x) for k,x in v.items() if k!='optimal'):raise ValueError('complete_finite_metrics')
                    chosen=max(range(9),key=lambda a:row['scores'][m][a])
                    if v['selected']!=chosen or abs(v['regret']-(max(row['actual'])-row['actual'][chosen]))>1e-8:raise ValueError('ranking_arithmetic')
        count+=9*len(r[split])
    if set(r['control'])!={str(t) for t in c['control_task_seeds']}:raise ValueError('complete_control_tasks')
    for task,cells in r['control'].items():
        if set(cells)!=set(c['methods']):raise ValueError('complete_control_methods')
        for episodes in cells.values():
            if [e['seed'] for e in episodes]!=[int(task)+100+j for j in range(c['control_episodes_per_task'])]:raise ValueError('paired_episode_grid')
            for e in episodes:audit_episode(e,c['control_steps'],information_reward=False);count+=len(e['steps'])
    for m in r['models']:
        if len(m['losses'])!=c['updates'] or any(not finite(v) for v in m['losses']):raise ValueError('complete_training')
    if r['frozen_core'] is not True or r['frozen_bank'] is not True:raise ValueError('frozen_integrity')
    if count!=r['authored_steps'] or count>c['max_authored_steps'] or r['imagined_transitions']>c['max_imagined_transitions'] or not finite(r['wall_s']) or r['wall_s']>c['max_wall_s']:raise ValueError('resource_integrity')
    return True
