"""Read-only stdlib audit of the locked authored pilot; no model execution."""
import hashlib
import json
import math
from pathlib import Path


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def validate_config(c):
    if (c['updates'],c['batch_size'],c['learning_rate'],c['source_episode_steps'],c['control_episode_steps'])!=(120,8,.003,8,12):
        raise ValueError('locked_training_settings')
    if c['recipes']!=['compact_tanh','compact_relu'] or c['methods']!=['latent_mpc','random','greedy'] or c['deployment_recipe']!='compact_tanh':raise ValueError('locked_methods')
    if (c['max_wall_s'],c['max_authored_steps'],c['max_imagined_transitions'])!=(180,4096,100000):raise ValueError('locked_caps')
    groups=[c[k] for k in ('training_seeds','prediction_seeds','control_seeds')]
    if list(map(len,groups))!=[48,6,4] or any(type(s) is not int for g in groups for s in g) or len(set(sum(groups,[])))!=58:raise ValueError('disjoint_collection_seeds')


def audit_episode(e,max_steps):
    steps=e['steps']
    if not 1<=len(steps)<=max_steps or any(s['done'] for s in steps[:-1]) or not (steps[-1]['done'] or len(steps)==max_steps):raise ValueError('complete_episode')
    flags=[0,0,0]
    for i,s in enumerate(steps):
        if type(s['action']) is not int or not 0<=s['action']<9 or type(s['done']) is not bool or not finite(s['reward']):raise ValueError('finite_typed_steps')
        if i and s['before']!=steps[i-1]['after']:raise ValueError('episode_continuity')
        before,after,goal=s['before'],s['after'],s['goal']
        d=lambda obj:abs(obj['x']-goal[0])+abs(obj['y']-goal[1])
        info=.05 if s['action']==4 and not flags[0] else 0.
        if 4<=s['action']<=6:flags[s['action']-4]=1
        expected=.2*(d(before)-d(after))-.02+int(d(after)==0)+info
        if abs(s['reward']-expected)>1e-8 or s['done']!=(d(after)==0):raise ValueError('reward_accounting')
    if 'return_sum' in e and (not finite(e['return_sum']) or abs(e['return_sum']-sum(s['reward'] for s in steps))>1e-8):raise ValueError('return_accounting')


def validate(result,root=None):
    c=result['config'];validate_config(c)
    if [r['recipe'] for r in result['models']]!=c['recipes']:raise ValueError('complete_recipe_grid')
    for name,seeds in [('source_episodes','training_seeds'),('prediction_episodes','prediction_seeds')]:
        if [e['seed'] for e in result[name]]!=c[seeds]:raise ValueError('complete_collection_grid')
        for e in result[name]:audit_episode(e,c['source_episode_steps'])
    real=sum(len(e['steps']) for key in ('source_episodes','prediction_episodes') for e in result[key]);imagined=0
    for row in result['models']:
        tr=row['training'];losses=tr['losses']
        if [r['update'] for r in losses]!=list(range(1,c['updates']+1)):raise ValueError('complete_update_grid')
        if any(not finite(v) for r in losses for k,v in r.items() if k!='update'):raise ValueError('finite_training')
        grads=tr['encoder_gradient_norms']
        if len(grads)!=c['updates'] or any(not finite(g) or g<=0 for g in grads):raise ValueError('encoder_gradient_grid')
        p=row['prediction']
        if any(not finite(p[k]) for k in ('state_mae','reward_mae','done_bce','trace_exact_accuracy')) or set(p['modality_latent_mae'])!={'text','pixels','proprioception'} or any(not finite(v) for v in p['modality_latent_mae'].values()):raise ValueError('finite_prediction_metric')
        if p['observations']!=sum(len(e['steps']) for e in result['prediction_episodes']) or len(p['traces'])!=p['observations']:raise ValueError('prediction_query_grid')
        if row['frozen_evaluation'] is not True:raise ValueError('changed_model')
        if set(row['control'])!=set(c['methods']):raise ValueError('complete_condition_grid')
        for method,episodes in row['control'].items():
            if [e['seed'] for e in episodes]!=c['control_seeds']:raise ValueError('complete_episode_grid')
            for e in episodes:
                audit_episode(e,c['control_episode_steps']);real+=len(e['steps'])
                if method=='latent_mpc':imagined+=48*len(e['steps'])
        if root is not None:
            path=Path(root)/row['checkpoint']
            if path.parent.resolve()!=(Path(root)/'artifacts').resolve() or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('checkpoint_integrity')
            model=json.loads(path.read_text())
            expected=dict(execution_sha=result['execution_sha'],config_sha256=result['config_sha256'],source_data_sha256=result['source_data_sha256'],recipe=row['recipe'])
            if model.get('schema')!='seed_rssm_v1' or model.get('provenance')!=expected:raise ValueError('checkpoint_provenance')
    if real!=result['authored_world_steps'] or imagined!=result['imagined_transitions']:raise ValueError('resource_accounting')
    if real>c['max_authored_steps'] or imagined>c['max_imagined_transitions'] or not finite(result['wall_s']) or result['wall_s']>c['max_wall_s']:raise ValueError('resource_cap')
    return dict(authored_world_steps=real,imagined_transitions=imagined,complete_grid=True)
