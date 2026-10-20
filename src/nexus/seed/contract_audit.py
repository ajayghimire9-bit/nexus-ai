"""Repository-only arithmetic/completeness; optional explicit local weight audit."""
import hashlib
import json
from pathlib import Path
from .grounded_audit import audit_episode, finite


def identities(c):return [f'{r}_{s}_{k}' for r in c['recipes'] for s in c['model_seeds'] for k in c['conditions']]


def validate(r):
    c=r['config'];expected=identities(c);count=0;imagined=0;updates=0
    if [m['identity'] for m in r['models']]!=expected:raise ValueError('complete_model_seed_contract_grid')
    if [e['seed'] for e in r['source']]!=list(range(c['training_seed_start'],c['training_seed_start']+c['training_episodes'])):raise ValueError('source_grid')
    for e in r['source']:audit_episode(e,c['source_steps'],information_reward=False);count+=len(e['steps'])
    if hashlib.sha256(json.dumps(r['source'],sort_keys=True).encode()).hexdigest()!=r['source_sha256']:raise ValueError('source_hash')
    for m in r['models']:
        tr=m['training'];n=0 if m['condition']=='untrained' else c['updates']
        if tr['updates']!=n or len(tr['losses'])!=n:raise ValueError('training_grid')
        if n and [v['update'] for v in tr['losses']]!=list(range(1,n+1)):raise ValueError('optimizer_schedule')
        if any(not finite(v) for row in tr['losses'] for v in row.values()):raise ValueError('finite_training_losses')
        updates+=n
        if [t['task'] for t in m['concepts']]!=list(range(37)):raise ValueError('concept_task_grid')
        for task in m['concepts']:
            if len(task['support_indices'])!=8 or len(task['query_indices'])!=6 or set(task['support_indices'])&set(task['query_indices']):raise ValueError('concept_support_query_isolation')
            if set(task['conditions'])!={'neural','symbolic_equal_cap','symbolic_full_reference'}:raise ValueError('concept_condition_grid')
            for name,row in task['conditions'].items():
                if row['candidates_tested']>(37 if name=='symbolic_full_reference' else 8) or not 0<=row['query_correct']<=6 or row['query_total']!=6:raise ValueError('concept_budget_or_metric')
    if updates!=r['optimizer_updates']:raise ValueError('optimizer_accounting')
    if [s['seed'] for s in r['ranking']]!=list(range(c['ranking_seed_start'],c['ranking_seed_start']+c['ranking_states'])):raise ValueError('ranking_state_grid')
    for s in r['ranking']:
        if [o['action'] for o in s['outcomes']]!=list(range(9)) or set(s['models'])!=set(expected):raise ValueError('ranking_action_model_grid')
        if any(not finite(o['reward']) or len(o['proprio'])!=12 or any(not finite(v) for v in o['proprio']) for o in s['outcomes']):raise ValueError('finite_true_outcomes')
        count+=9;imagined+=9*3*len(expected)
        for m in s['models'].values():
            if set(m)!={'reward','pixels_non_goal_mae','structured_non_goal_mae'} or not finite(m['pixels_non_goal_mae']) or not finite(m['structured_non_goal_mae']):raise ValueError('perception_metric_grid')
            metrics=m['reward']
            if set(metrics)!={'selected','regret','optimal','pairwise_accuracy','score_range','reward_mae','uniform_expected_regret'} or any(not finite(v) for k,v in metrics.items() if k!='optimal'):raise ValueError('ranking_metric_grid')
    if set(r['control'])!=set(expected):raise ValueError('control_model_grid')
    def control(episodes):
        if [e['seed'] for e in episodes]!=list(range(c['control_seed_start'],c['control_seed_start']+c['control_episodes'])):raise ValueError('paired_control_grid')
        for e in episodes:audit_episode(e,c['control_steps'],information_reward=False)
        return sum(len(e['steps']) for e in episodes)
    for model in expected:
        if set(r['control'][model])!={'pruned','unpruned'}:raise ValueError('pruning_condition_grid')
        for p,rows in r['control'][model].items():
            n=control(rows);count+=n;imagined+=n*(48 if p=='pruned' else 64)
    if set(r['references'])!={'random','greedy'}:raise ValueError('reference_grid')
    for rows in r['references'].values():count+=control(rows)
    if len(r['language']['rows'])!=24 or r['language']['total']!=24 or r['language']['exact']!=sum(row['exact'] for row in r['language']['rows']):raise ValueError('language_grid')
    if count!=r['authored_steps'] or imagined!=r['imagined_transitions']:raise ValueError('interaction_accounting')
    if count>c['max_authored_steps'] or imagined>c['max_imagined_transitions'] or not finite(r['wall_s']) or r['wall_s']>c['max_wall_s']:raise ValueError('resource_cap')
    if set(r['frozen'])!=set(expected) or any(v is not True for v in r['frozen'].values()) or r['historical_artifacts_unchanged'] is not True:raise ValueError('frozen_integrity')
    return dict(complete=True,authored_steps=count,imagined_transitions=imagined,optimizer_updates=updates)


def verify_files(r,root,*,local_checkpoints=False):
    root=Path(root)
    for m in r['models']:
        if local_checkpoints:
            p=root/m['checkpoint']
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=m['sha256']:raise ValueError('required_local_checkpoint_missing_or_wrong: '+str(p))
        if 'gui_sha256' in m:
            p=root/'artifacts/seed_contract_gui.json'
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=m['gui_sha256']:raise ValueError('gui_checkpoint_hash')
    return True
