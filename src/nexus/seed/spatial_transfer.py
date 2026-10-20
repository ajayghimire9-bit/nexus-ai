"""Registered spatial fixtures and data-only analysis over existing Seed APIs."""
import math
from .readout_validation import interval


def identity(obj,goal):
    return tuple(obj[k] for k in ('x','y','color','shape','size'))+tuple(goal)


def closed_initials(parent):
    used={identity(s['before'],s['goal']) for role in ('source','development','audit') for s in parent[role]}
    used.update(identity(e['steps'][0]['before'],e['steps'][0]['goal']) for cells in parent['control'].values() for rows in cells.values() for e in rows)
    return used


def world(seed,group,excluded):
    """Geometry/seed only. No prediction or reward is read to select a state."""
    import random
    from .grounded_world import AuthoredWorld
    r=random.Random(seed+77);w=AuthoredWorld(seed);w.information_reward=False
    for _ in range(256):
        w.obj.update(color=r.choice(('red','blue','green')),shape=r.choice(('square','circle','triangle')),size=r.choice(('small','large')))
        if group=='corner_goal':
            w.obj.update(x=r.randrange(1,5),y=r.randrange(1,5));w.goal=(r.choice((0,5)),r.choice((0,5)))
        elif group=='opposite_corners':
            x,y=r.choice((0,5)),r.choice((0,5));w.obj.update(x=x,y=y);w.goal=(5-x,5-y)
        elif group=='boundary_reversal':
            x,y=r.choice((0,5)),r.randrange(1,5);w.obj.update(x=x,y=y);w.goal=(5-x,y)
        elif group=='cross_diagonal':
            x,y=r.randrange(1,5),r.randrange(1,5);d=r.choice((-1,1));w.obj.update(x=x,y=y);w.goal=(x+d,y-d)
        else:raise ValueError('registered_spatial_group_required')
        if identity(w.obj,w.goal) not in excluded:return w
    raise ValueError('fresh_spatial_state_space_exhausted')


def summarize(r):
    c=r['config'];mean=lambda xs:sum(xs)/len(xs);groups={};all_diffs={b:[] for b in ('frozen','random','greedy','latent_mpc')}
    for group in c['groups']:
        cells=r['control'][group];stats={m:dict(return_mean=mean([e['return_sum'] for rows in cells.values() for e in rows[m]]),goal_rate=mean([float(e['success']) for rows in cells.values() for e in rows[m]])) for m in c['methods']}
        diffs={b:[mean([e['return_sum'] for s in c['head_seeds'] for e in cells[str(i)][f'readout_{s}']])-mean([e['return_sum'] for e in cells[str(i)][b]]) for i in range(c['streams'])] for b in all_diffs}
        for b in all_diffs:all_diffs[b].append(diffs[b])
        regret={m:mean([float(s['metrics'][m]['regret']) for s in r['ranking'][group]]) for m in ['frozen']+[f'readout_{s}' for s in c['head_seeds']]}
        groups[group]=dict(control=stats,regret=regret,paired_returns={b:interval(v) for b,v in diffs.items()})
    pooled={b:interval([mean([v[i] for v in arrays]) for i in range(c['streams'])]) for b,arrays in all_diffs.items()}
    goal_gain=mean([mean([g['control'][f'readout_{s}']['goal_rate'] for s in c['head_seeds']])-g['control']['frozen']['goal_rate'] for g in groups.values()])
    passed=pooled['frozen']['mean']>=c['minimum_return_gain'] and pooled['frozen']['ci95'][0]>0 and goal_gain>=c['minimum_goal_gain'] and all(g['paired_returns']['frozen']['mean']>=-c['maximum_group_return_regression'] for g in groups.values())
    return dict(groups=groups,pooled_paired_returns=pooled,pooled_goal_gain=goal_gain,screen_passed=passed,unit='eight_paired_reset_streams_conditional_on_one_frozen_core',learning_to_learn_tested=False)


def validate(r,c):
    from .grounded_audit import audit_episode
    finite=lambda v:type(v) in (int,float) and math.isfinite(v)
    if r['config']!=c or set(r['ranking'])!=set(c['groups']) or set(r['control'])!=set(c['groups']):raise ValueError('locked_group_grid')
    real=0;imagined=0;initials=[]
    for gi,g in enumerate(c['groups']):
        if [s['seed'] for s in r['ranking'][g]]!=[c['ranking_seed_start']+gi*10000+j for j in range(c['ranking_states_per_group'])]:raise ValueError('ranking_state_grid')
        for s in r['ranking'][g]:
            initials.append(identity(s['before'],s['goal']))
            expected={'frozen'}|{f'readout_{seed}' for seed in c['head_seeds']}
            if len(s['actual'])!=9 or any(not finite(v) for v in s['actual']) or set(s['scores'])!=expected or set(s['metrics'])!=expected:raise ValueError('complete_action_grid')
            for m,scores in s['scores'].items():
                if len(scores)!=9 or any(not finite(v) for v in scores):raise ValueError('finite_scores')
                a=max(range(9),key=lambda i:scores[i]);v=s['metrics'][m]
                if set(v)!={'selected','regret','optimal','pairwise_accuracy','score_range','reward_mae','uniform_expected_regret'} or type(v['optimal']) is not bool or any(not finite(x) for k,x in v.items() if k!='optimal'):raise ValueError('complete_finite_metrics')
                if v['selected']!=a or not finite(v['regret']) or abs(v['regret']-(max(s['actual'])-s['actual'][a]))>1e-8:raise ValueError('ranking_arithmetic')
            real+=9;imagined+=9
        if set(r['control'][g])!={str(i) for i in range(c['streams'])}:raise ValueError('stream_grid')
        for si,cells in r['control'][g].items():
            if set(cells)!=set(c['methods']):raise ValueError('method_grid')
            expected_seeds=[c['control_seed_start']+gi*10000+int(si)*100+j for j in range(c['episodes_per_stream'])]
            paired=None
            for m,episodes in cells.items():
                if [e['seed'] for e in episodes]!=expected_seeds:raise ValueError('paired_reset_grid')
                starts=[identity(e['steps'][0]['before'],e['steps'][0]['goal']) for e in episodes]
                if paired is None:paired=starts;initials.extend(starts)
                if starts!=paired:raise ValueError('same_initial_states_required')
                for e in episodes:
                    if type(e['success']) is not bool or e['success']!=e['steps'][-1]['done']:raise ValueError('terminal_success_accounting')
                    audit_episode(e,c['episode_steps'],information_reward=False);real+=len(e['steps'])
                    imagined+=len(e['steps'])*(48 if m=='latent_mpc' else 9 if m=='frozen' or m.startswith('readout_') else 0)
    if len(initials)!=len(set(initials)) or any(v in set(map(tuple,r['closed_initials'])) for v in initials):raise ValueError('fresh_disjoint_initials')
    if real!=r['authored_steps'] or imagined!=r['imagined_transitions'] or real>c['max_authored_steps'] or imagined>c['max_imagined_transitions'] or not finite(r['wall_s']) or r['wall_s']>c['max_wall_s']:raise ValueError('resource_accounting')
    if r['frozen_core'] is not True or r['frozen_bank'] is not True or r['frozen_readouts'] is not True:raise ValueError('frozen_integrity')
    return True
