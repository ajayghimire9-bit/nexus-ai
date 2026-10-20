"""Stdlib completeness/statistics for registered fresh tasks; no local binaries."""
import math
import statistics as st
from .grounded_audit import audit_episode


def interval(values):
    if len(values)!=8:raise ValueError('eight_task_stream_units_required')
    mean=st.mean(values);half=2.364624251*st.stdev(values)/8**.5
    return dict(mean=mean,ci95=[mean-half,mean+half],paired_values=values,
        unit='fresh_teaching_task_stream_conditional_on_one_frozen_core')


def summarize(r):
    c=r['config'];controllers=r['controllers'];learning={};forget={}
    for method in ('learned','fixed','replay','none','neutral'):
        learning[method]=[st.mean(row['query_mse'] for m in controllers for row in m['curves']['audit'][i]['methods'][method]) for i in range(8)]
        forget[method]=st.mean(row['forgetting'] for m in controllers for t in m['curves']['audit'] for row in t['methods'][method])
    contrasts={b:interval([x-y for x,y in zip(learning[b],learning['learned'])]) for b in ('fixed','replay','none','neutral')}
    learning_pass=all(v['mean']>=c['learning_min_fraction']*st.mean(learning[b]) and v['ci95'][0]>0 for b,v in contrasts.items()) and forget['learned']<=forget['fixed']+.01
    regrets={m:[] for m in ('learned','fixed','frozen')};goals={m:[] for m in regrets};returns={m:[] for m in regrets}
    for i,seed in enumerate(c['task_seeds']['audit']):
        for method in ('learned','fixed'):
            regrets[method].append(st.mean(rank['metrics']['regret'] for m in controllers for rank in m['curves']['audit'][i]['methods'][method][-1]['ranking']))
            episodes=[e for s in c['controller_seeds'] for e in r['control'][str(seed)][f'{s}/{method}']]
            goals[method].append(st.mean(e['success'] for e in episodes));returns[method].append(st.mean(e['return_sum'] for e in episodes))
        truths=r['tasks']['audit'][i]['records']['query']
        regrets['frozen'].append(st.mean(max(t['actual'])-t['actual'][max(range(9),key=lambda j:t['base'][j])] for t in truths))
        episodes=r['control'][str(seed)]['frozen'];goals['frozen'].append(st.mean(e['success'] for e in episodes));returns['frozen'].append(st.mean(e['return_sum'] for e in episodes))
    action_contrasts={b:interval([a-bb for a,bb in zip(returns['learned'],returns[b])]) for b in ('fixed','frozen')}
    action_pass=all(st.mean(regrets['learned'])<=st.mean(regrets[b])*(1-c['action_min_fraction']) and st.mean(goals['learned'])>=st.mean(goals[b])+c['goal_min_difference'] and action_contrasts[b]['ci95'][0]>0 for b in ('fixed','frozen'))
    return dict(learning=dict(passed=learning_pass,means={m:st.mean(v) for m,v in learning.items()},forgetting=forget,contrasts=contrasts),
        actions=dict(passed=action_pass,regret={m:st.mean(v) for m,v in regrets.items()},goal_rate={m:st.mean(v) for m,v in goals.items()},mean_return={m:st.mean(v) for m,v in returns.items()},contrasts=action_contrasts))


def numeric(v):return type(v) in (int,float) and math.isfinite(v)


def resource_bound(c):
    tasks=sum(map(len,c['task_seeds'].values()));audit=len(c['task_seeds']['audit']);controllers=len(c['controller_seeds'])
    collection=tasks*(8+4+3*9+3*9)
    control=audit*(controllers*4+2)*c['control_episodes']*c['control_steps']
    labels=len(c['meaning_seeds'])*18+32+(len(c['selector_train_seeds'])+len(c['selector_audit_seeds']))*18+len(c['transfer_seeds'])*16
    imagined=(tasks*18+audit*(controllers*4+1)*c['control_episodes']*c['control_steps'])*9
    return dict(max_world_steps=collection+control,max_supervised_answers=labels,max_authored_interactions=collection+control+labels,max_imagined_rows=imagined)


def validate(r,c):
    bound=resource_bound(c)
    if bound['max_authored_interactions']>c['max_authored_interactions'] or bound['max_imagined_rows']>c['max_imagined_transitions']:raise ValueError('unsafe_registered_resource_bound')
    if r['config']!=c or r['frozen_core'] is not True:raise ValueError('config_or_frozen_core')
    if [x['seed'] for x in r['controllers']]!=c['controller_seeds']:raise ValueError('controller_grid')
    roles={'support','old','query','retention','control','meaning_labels','instruction_demonstrations','selector_authored_label_bank'}
    if r['transfer']['status']=='executed_after_object_success':roles.add('list_teaching_and_query_labels')
    if set(r['costs'])!=roles or any(type(v) is not int or v<0 for v in r['costs'].values()) or sum(r['costs'].values())>c['max_authored_interactions']:raise ValueError('resource_roles')
    work=r['update_work']
    if work['imagined_rows']>c['max_imagined_transitions'] or r['model_work']['transition_rows']!=work['imagined_rows']+work['posterior_prior_rows'] or not numeric(r['wall_s']) or r['wall_s']>c['max_wall_s']:raise ValueError('compute_cap')
    for model in r['controllers']:
        if [t['step'] for t in model['training']]!=list(range(1,c['meta_updates']+1)) or any(not numeric(v) for t in model['training'] for v in t.values()):raise ValueError('optimizer_grid')
    for split,seeds in c['task_seeds'].items():
        if [t['seed'] for t in r['tasks'][split]]!=seeds:raise ValueError('task_grid')
        for task in r['tasks'][split]:
            if set(task['records'])!={'support','old','query','retention'}:raise ValueError('task_roles')
            if [len(task['records'][k]) for k in ('support','old','query','retention')]!=[8,4,3,3]:raise ValueError('task_row_grid')
        for model in r['controllers']:
            if [t['seed'] for t in model['curves'][split]]!=seeds:raise ValueError('curve_task_grid')
            for task in model['curves'][split]:
                if set(task['methods'])!={'learned','fixed','replay','none','neutral'}:raise ValueError('method_grid')
                for rows in task['methods'].values():
                    if [t['budget'] for t in rows]!=c['budgets']:raise ValueError('budget_grid')
                    for t in rows:
                        if not numeric(t['query_mse']) or not numeric(t['forgetting']) or len(t['ranking'])!=3:raise ValueError('numeric_curve')
                        for rank in t['ranking']:
                            if len(rank['predicted'])!=9 or any(not numeric(v) for v in rank['predicted']) or set(rank['metrics'])!={'selected','regret','optimal','pairwise_accuracy','score_range','reward_mae','uniform_expected_regret'}:raise ValueError('ranking_grid')
                            if any(not numeric(v) for k,v in rank['metrics'].items() if k!='optimal'):raise ValueError('finite_ranking')
                            if type(rank['metrics']['optimal']) is not bool:raise ValueError('ranking_optimal_type')
    count=0
    if set(r['control'])!=set(map(str,c['task_seeds']['audit'])):raise ValueError('control_tasks')
    for seed in c['task_seeds']['audit']:
        cell=r['control'][str(seed)];names={f'{s}/{m}' for s in c['controller_seeds'] for m in ('learned','fixed','replay','none')}|{'frozen','grid'}
        if set(cell)!=names:raise ValueError('control_methods')
        for episodes in cell.values():
            if [e['seed'] for e in episodes]!=[seed+1000+i for i in range(c['control_episodes'])]:raise ValueError('paired_control_seeds')
            for e in episodes:
                if type(e['success']) is not bool:raise ValueError('goal_success_type')
                if not e['steps'] or len(e['steps'])>c['control_steps'] or not numeric(e['return_sum']):raise ValueError('control_episode')
                if abs(sum(s['reward'] for s in e['steps'])-e['return_sum'])>1e-7:raise ValueError('reward_accounting')
                audit_episode(dict(e,steps=[dict(s,goal=e['goal']) for s in e['steps']]),c['control_steps'],information_reward=False)
                count+=len(e['steps'])
    if count!=r['costs']['control'] or r['costs']['support']!=24*8 or r['costs']['old']!=24*4 or r['costs']['query']!=24*27 or r['costs']['retention']!=24*27:raise ValueError('executed_interactions')
    if [x['controller_seed'] for x in r['meaning']]!=c['controller_seeds'] or [x['controller_seed'] for x in r['selection']]!=c['controller_seeds']:raise ValueError('capability_controller_grid')
    for model in r['meaning']:
        if [t['seed'] for t in model['tasks']]!=c['meaning_seeds']:raise ValueError('meaning_tasks')
        for task in model['tasks']:
            if [row['budget'] for row in task['rows']]!=c['budgets']:raise ValueError('meaning_budgets')
            for row in task['rows']:
                if set(row['methods'])!={'learned','fixed','replay','none','symbolic'}:raise ValueError('meaning_methods')
                for m in row['methods'].values():
                    if type(m['correct']) is not int or not 0<=m['correct']<=m['total'] or m['total']!=10:raise ValueError('meaning_metrics')
        if [r['budget'] for r in model['instructions']['rows']]!=[k for k in c['budgets'] for _ in range(4)]:raise ValueError('instruction_grid')
        if any(type(row[k]) is not bool for row in model['instructions']['rows'] for k in ('neural_exact','symbolic_exact')):raise ValueError('instruction_outcome_type')
    for model in r['selection']:
        if set(model['policies'])!={'adaptive','random','fixed'}:raise ValueError('selection_methods')
        for rows in model['policies'].values():
            if [t['seed'] for t in rows]!=c['selector_audit_seeds']:raise ValueError('selection_tasks')
            for t in rows:
                if not 0<t['labels']<=16 or len(t['trace'])>8 or t['hidden_query_used_for_learning'] is not False or not numeric(t['final_query_mse']) or not numeric(t['improvement_per_cost']):raise ValueError('selection_boundaries')
    expected=summarize(r)
    if expected!=r['screens']:raise ValueError('screen_arithmetic')
    if not all(expected[k]['passed'] for k in ('learning','actions')) and r['transfer']['status']!='not_run_object_success_gate_failed':raise ValueError('transfer_gate')
    return True
