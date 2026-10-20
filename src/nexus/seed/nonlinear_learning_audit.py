"""Stdlib-only locked-grid, cost and paired-task audit; never executes models."""
import math
import statistics as st
from nexus.evolution1.catalogue import digest
from .grounded_audit import audit_episode

METHODS=['learned','static','fixed','replay','none']


def numeric(v):
    return type(v) in (int,float) and math.isfinite(v)


def bound(c):
    n=sum(len(v['seeds']) for v in c['tasks'].values());a=len(c['tasks']['audit']['seeds'])
    adaptive=len(c['outer_seeds'])*len(c['methods']);steps=a*c['control_episodes']*c['control_steps']
    return dict(real_steps=n*66+steps*(adaptive+len(c['references'])),
        imagined_transitions=n*18*9+steps*((adaptive+2)*9+48),
        posterior_rows=n*18+steps*(adaptive+3),outer_updates=2*len(c['outer_seeds'])*c['meta_updates'])


def config_check(c):
    if c['schema']!='seed_nonlinear_learning_v1' or c['methods']!=METHODS or c['budgets']!=[1,2,4,8]:
        raise ValueError('locked_methods_budgets')
    if c['outer_seeds']!=[6401,6402,6403] or c['meta_updates']!=64 or c['meta_lr']!=.01:
        raise ValueError('locked_source_optimization')
    if list(c['tasks'])!=['train','development','audit'] or [len(v['seeds']) for v in c['tasks'].values()]!=[12,4,8]:
        # JSON canonicalization sorts keys: order is not scientifically relevant.
        if set(c['tasks'])!={'train','development','audit'} or [len(c['tasks'][k]['seeds']) for k in ('train','development','audit')]!=[12,4,8]:
            raise ValueError('locked_task_roles')
    seeds=[s for v in c['tasks'].values() for s in v['seeds']]
    goals=[tuple(g) for v in c['tasks'].values() for g in v['goals']]
    if len(seeds)!=len(set(seeds)) or len(goals)!=len(set(goals)) or tuple(c['old_goal']) in goals:
        raise ValueError('task_role_overlap')
    for v in c['tasks'].values():
        if len(v['goals'])!=len(v['seeds']) or any(type(s) is not int for s in v['seeds']):raise ValueError('task_registration')
    if c['references']!=['frozen_readout','frozen_world','greedy','random','latent_mpc']:
        raise ValueError('locked_controller_references')
    b=bound(c)
    if b['real_steps']>c['max_authored_steps'] or b['imagined_transitions']>c['max_imagined_transitions']:
        raise ValueError('unsafe_worst_case_bounds')
    if c['max_wall_s']>min(180,c['carried_remaining_s']) or c['max_authored_steps']>100000:
        raise ValueError('standing_or_protocol_limit')
    return b


def interval(values):
    if len(values)!=8 or any(not numeric(v) for v in values):raise ValueError('eight_finite_task_units')
    m=st.mean(values);h=2.364624251*st.stdev(values)/math.sqrt(8)
    return dict(mean=m,ci95=[m-h,m+h],paired_values=values,
                unit='eight_tasks_outer_seeds_averaged_one_frozen_core',adjustment='exploratory_unadjusted')


def summarize(r):
    c=r['config'];audit=c['tasks']['audit']['seeds'];curves=r['curves']['audit']
    per={m:[] for m in METHODS};forget={m:[] for m in METHODS};by_budget={}
    for m in METHODS:
        for task in audit:
            rows=[x for s in c['outer_seeds'] for x in curves[str(s)][str(task)][m]]
            per[m].append(st.mean(x['query_mse'] for x in rows));forget[m].append(st.mean(x['forgetting'] for x in rows))
    for budget in c['budgets']:
        by_budget[str(budget)]={m:dict(mse=interval([st.mean(curves[str(s)][str(t)][m][c['budgets'].index(budget)]['query_mse'] for s in c['outer_seeds']) for t in audit]),
            regret=st.mean(curves[str(s)][str(t)][m][c['budgets'].index(budget)]['regret'] for s in c['outer_seeds'] for t in audit),
            optimal_rate=st.mean(curves[str(s)][str(t)][m][c['budgets'].index(budget)]['optimal_rate'] for s in c['outer_seeds'] for t in audit)) for m in METHODS}
    contrasts={b:interval([x-y for x,y in zip(per[b],per['learned'])]) for b in METHODS[1:]}
    learning_pass=all(v['mean']>=c['learning_min_fraction']*st.mean(per[b]) and v['ci95'][0]>0 for b,v in contrasts.items())
    forgetting={m:st.mean(v) for m,v in forget.items()}
    retention_pass=forgetting['learned']<=forgetting['fixed']+c['maximum_forgetting_excess']
    returns={};goals={}
    for m in METHODS+c['references']:
        returns[m]=[];goals[m]=[]
        for t in audit:
            episodes=([e for s in c['outer_seeds'] for e in r['control'][str(t)][f'{s}/{m}']] if m in METHODS else r['control'][str(t)][m])
            returns[m].append(st.mean(e['return_sum'] for e in episodes));goals[m].append(st.mean(float(e['success']) for e in episodes))
    control_contrasts={b:interval([x-y for x,y in zip(returns['learned'],returns[b])]) for b in METHODS[1:]+c['references']}
    nonregression=all(control_contrasts[b]['ci95'][0]>=c['minimum_control_return_lower_bound'] and
        st.mean(goals['learned'])-st.mean(goals[b])>=c['minimum_goal_difference'] for b in METHODS[1:]+['frozen_readout'])
    return dict(curve_means={m:st.mean(v) for m,v in per.items()},per_budget=by_budget,
        learning_contrasts=contrasts,forgetting=forgetting,
        control_means={m:dict(mean_return=st.mean(returns[m]),goal_rate=st.mean(goals[m])) for m in returns},
        control_contrasts=control_contrasts,learning_pass=learning_pass,retention_pass=retention_pass,
        control_nonregression_pass=nonregression,screen_passed=learning_pass and retention_pass and nonregression,
        interpretation='bounded_development_screen_not_general_learning_to_learn')


def complete_grid(r,c):
    """Expected sets come from the locked plan, never from produced rows."""
    if set(r['tasks'])!=set(c['tasks']) or set(r['curves'])!={'development','audit'}:
        raise ValueError('split_grid')
    if [x['seed'] for x in r['controllers']]!=c['outer_seeds']:raise ValueError('outer_seed_grid')
    for role,plan in c['tasks'].items():
        if [x['seed'] for x in r['tasks'][role]]!=plan['seeds']:raise ValueError('task_grid')
    for role in ('development','audit'):
        if set(r['curves'][role])!=set(map(str,c['outer_seeds'])):raise ValueError('curve_outer_seed_grid')
        for cells in r['curves'][role].values():
            if set(cells)!=set(map(str,c['tasks'][role]['seeds'])):raise ValueError('curve_task_grid')
            for methods in cells.values():
                if set(methods)!=set(c['methods']):raise ValueError('curve_method_grid')
                if any([v['budget'] for v in rows]!=c['budgets'] for rows in methods.values()):raise ValueError('budget_grid')
    return True


def validate(r,c):
    config_check(c)
    complete_grid(r,c)
    if r['config']!=c or not all(r[k] is True for k in ('frozen_core','frozen_bank','frozen_readout')):raise ValueError('config_frozen_integrity')
    if set(r['tasks'])!=set(c['tasks']) or set(r['curves'])!={'development','audit'}:raise ValueError('split_grid')
    identities=[];collection=0
    for role,plan in c['tasks'].items():
        if [t['seed'] for t in r['tasks'][role]]!=plan['seeds']:raise ValueError('task_grid')
        for i,t in enumerate(r['tasks'][role]):
            if t['goal']!=plan['goals'][i] or set(t['records'])!={'support','old','query','retention'}:raise ValueError('goal_role_grid')
            if [len(t['records'][k]) for k in ('support','old','query','retention')]!=[8,4,3,3]:raise ValueError('collection_grid')
            if digest(t['records'])!=t['record_sha256'] or digest(t['arrays'])!=t['array_sha256'] or t['dtype']!='float32':raise ValueError('transition_record_hash')
            for kind,rows in t['records'].items():
                for row in rows:
                    obj=row['before'];identities.append(tuple(obj[k] for k in ('x','y','color','shape','size'))+tuple(row['goal']))
                    outs=row['outcomes']
                    if [a['action'] for a in outs]!=(list(range(9)) if kind in ('query','retention') else [row['action']]):raise ValueError('observed_action_grid')
                    for a in outs:
                        if not numeric(a['reward']) or type(a['done']) is not bool or a['truncated'] is not False or len(a['next_proprio'])!=12 or any(not numeric(v) for v in a['next_proprio']):raise ValueError('observed_transition')
                        audit_episode(dict(steps=[dict(before=obj,after=a['after'],goal=row['goal'],action=a['action'],reward=a['reward'],done=a['done'])]),1,False)
                        collection+=1
            for key,shape in [('support_x',(8,33)),('query_x',(27,33)),('old_x',(4,33)),('retention_x',(27,33))]:
                a=t['arrays'][key]
                if len(a)!=shape[0] or any(len(row)!=shape[1] or any(not numeric(v) for v in row) for row in a):raise ValueError('feature_grid')
                ys=t['arrays'][key[:-1]+'y']
                if len(ys)!=shape[0] or any(not numeric(v) for v in ys):raise ValueError('label_grid')
    if len(identities)!=len(set(identities)) or set(identities)&set(map(tuple,r['closed_initials'])):raise ValueError('initial_role_or_historical_overlap')
    if len(r['scale'])!=33 or any(not numeric(v) or v<=0 for v in r['scale']):raise ValueError('source_only_scaling')
    if [v['seed'] for v in r['controllers']]!=c['outer_seeds']:raise ValueError('outer_seed_grid')
    for model in r['controllers']:
        if set(model['arms'])!={'learned','static'}:raise ValueError('source_arm_grid')
        for m,v in model['arms'].items():
            if [p['update'] for p in v['training']]!=list(range(1,c['meta_updates']+1)):raise ValueError('optimizer_grid')
            if any(not numeric(x) for p in v['training'] for x in p.values()):raise ValueError('finite_source_metrics')
            if not numeric(v['parameter_change_l2']) or not numeric(v['seconds']):raise ValueError('source_learning_diagnostics')
        if model['arms']['learned']['source_schedule_sha256']!=model['arms']['static']['source_schedule_sha256']:raise ValueError('paired_source_schedule')
    if r['locked_before_audit']['weights_sha256']!=digest(r['controllers']):raise ValueError('changed_rules_after_audit')
    for role in ('development','audit'):
        if set(r['curves'][role])!=set(map(str,c['outer_seeds'])):raise ValueError('curve_outer_seed_grid')
        for s,cells in r['curves'][role].items():
            if set(cells)!=set(map(str,c['tasks'][role]['seeds'])):raise ValueError('curve_task_grid')
            for task,methods in cells.items():
                if set(methods)!=set(METHODS):raise ValueError('curve_method_grid')
                for m,rows in methods.items():
                    if [x['budget'] for x in rows]!=c['budgets']:raise ValueError('budget_grid')
                    for row in rows:
                        if any(not numeric(row[k]) for k in ('query_mse','forgetting','regret','optimal_rate')) or len(row['theta'])!=33 or any(not numeric(v) for v in row['theta']):raise ValueError('finite_learning_curve')
                        if len(row['scores'])!=27 or any(not numeric(v) for v in row['scores']):raise ValueError('query_score_grid')
                        raw=next(t for t in r['tasks'][role] if str(t['seed'])==task)
                        dot=lambda x,w:sum(a*b/s for a,b,s in zip(x,w,r['scale']))
                        errors=[(dot(x,row['theta'])-y)**2 for x,y in zip(raw['arrays']['query_x'],raw['arrays']['query_y'])]
                        if abs(st.mean(errors)-row['query_mse'])>2e-6:raise ValueError('query_mse_arithmetic')
                        ff=st.mean((dot(x,row['theta'])-y)**2-(dot(x,raw['initial_theta'])-y)**2 for x,y in zip(raw['arrays']['retention_x'],raw['arrays']['retention_y']))
                        if abs(ff-row['forgetting'])>2e-6:raise ValueError('forgetting_arithmetic')
                        scores=[];actual=[]
                        for rr in raw['records']['query']:
                            scores.extend(rr['base']);actual.extend(a['reward'] for a in rr['outcomes'])
                        predicted=[b+dot(x,row['theta']) for b,x in zip(scores,raw['arrays']['query_x'])]
                        if any(abs(a-b)>2e-6 for a,b in zip(predicted,row['scores'])):raise ValueError('prediction_arithmetic')
                        chosen=[max(range(9),key=lambda j:row['scores'][i+j]) for i in (0,9,18)]
                        regret=st.mean(max(actual[i:i+9])-actual[i+a] for i,a in zip((0,9,18),chosen))
                        optimal=st.mean(float(max(actual[i:i+9])-actual[i+a]<1e-8) for i,a in zip((0,9,18),chosen))
                        if abs(regret-row['regret'])>1e-8 or abs(optimal-row['optimal_rate'])>1e-8:raise ValueError('ranking_arithmetic')
    if set(r['control'])!=set(map(str,c['tasks']['audit']['seeds'])):raise ValueError('control_task_grid')
    control=0;imagined=len(identities)*9;posterior=len(identities)
    control_ids=[]
    for task,cell in r['control'].items():
        expected={f'{s}/{m}' for s in c['outer_seeds'] for m in METHODS}|set(c['references'])
        if set(cell)!=expected:raise ValueError('control_method_grid')
        starts=None
        for method,episodes in cell.items():
            if [e['seed'] for e in episodes]!=[int(task)+1000+j for j in range(c['control_episodes'])]:raise ValueError('paired_control_seed_grid')
            current=[(e['steps'][0]['before'],e['steps'][0]['goal']) for e in episodes]
            if starts is None:
                starts=current
                control_ids.extend(tuple(obj[k] for k in ('x','y','color','shape','size'))+tuple(goal) for obj,goal in current)
            if current!=starts:raise ValueError('paired_initial_states')
            for e in episodes:
                if type(e['success']) is not bool or e['success']!=e['steps'][-1]['done']:raise ValueError('goal_flags')
                audit_episode(e,c['control_steps'],False);n=len(e['steps']);control+=n
                neural=method not in ('greedy','random')
                if neural:
                    posterior+=n;imagined+=n*(48 if method=='latent_mpc' else 9)
    if collection!=r['costs']['collection'] or control!=r['costs']['control']:raise ValueError('real_interaction_accounting')
    all_ids=identities+control_ids
    if len(all_ids)!=len(set(all_ids)) or set(control_ids)&set(map(tuple,r['closed_initials'])):raise ValueError('fresh_control_initials')
    if imagined!=r['imagined_transitions'] or posterior!=r['posterior_rows']:raise ValueError('model_work_accounting')
    if r['model_work']['transition_rows']!=imagined+posterior:raise ValueError('actual_model_row_accounting')
    if collection+control>c['max_authored_steps'] or imagined>c['max_imagined_transitions'] or not numeric(r['wall_s']) or r['wall_s']>c['max_wall_s']:raise ValueError('execution_cap')
    if r['analysis']!=summarize(r):raise ValueError('summary_reproduction')
    return True


def validate_output(output,c,caps):
    if type(output) is not dict or set(output)!={'adapter','study','metrics','curve','model','runtime','resources'} or output['adapter']!='seed_nonlinear_learning_v1':raise ValueError('study_worker_schema')
    r=output['study'];validate(r,c)
    if r['declared_complete'] is not True:raise ValueError('incomplete_study')
    metrics=output['metrics'];a=r['analysis']
    if metrics!=dict(mse=a['curve_means']['learned'],baseline_mse=min(a['curve_means'][m] for m in METHODS[1:]),worst_error_increase=a['forgetting']['learned']-a['forgetting']['fixed']):raise ValueError('study_summary_metrics')
    if output['model']!=dict(schema='seed_update_rules_v1',controllers=r['controllers']):raise ValueError('study_model_grid')
    if [x['update'] for x in output['curve']]!=c['budgets']:raise ValueError('gui_budget_grid')
    work=output['resources']
    if any(not numeric(v) or v<0 for v in work.values()):raise ValueError('finite_resource_metrics')
    if work['real_steps']!=sum(r['costs'].values()) or work['imagined_transitions']!=r['imagined_transitions'] or work['updates']!=bound(c)['outer_updates']:raise ValueError('host_study_accounting')
    if any(work[k]>caps[k] for k in ('real_steps','imagined_transitions','updates','cpu_s')):raise ValueError('study_grant_cap')
    return True
