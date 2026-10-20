"""Stdlib-only exact-grid and accounting audit of residual action learning."""
import hashlib
import json
from pathlib import Path
from .grounded_audit import audit_episode, finite


def require_manifest(r,root):
    root=Path(root);p=root/'artifacts/seed_action_readout_manifest.json'
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=r['manifest_sha256']:raise ValueError('saved_manifest_required')
    m=json.loads(p.read_text());c=r['config']
    if m['config_sha256']!=r['config_sha256'] or m['source_sha256']!=r['source_sha256'] or m['execution_sha']!=r['execution_sha']:raise ValueError('manifest_provenance')
    if [row['recipe'] for row in m['models']]!=c['model_recipes'] or any([h['seed'] for h in row['heads']]!=c['readout_seeds'] for row in m['models']):raise ValueError('locked_manifest_grid')
    return m


def validate(r,root):
    root=Path(root);c=r['config'];count=0;imagined=0
    if [m['recipe'] for m in r['models']]!=c['model_recipes']:raise ValueError('complete_parent_grid')
    config_path=root/'configs/seed_action_readout.json'
    if hashlib.sha256(config_path.read_bytes()).hexdigest()!=r['config_sha256'] or json.loads(config_path.read_text())!=c:raise ValueError('locked_configuration')
    manifest=require_manifest(r,root)
    if manifest['config_sha256']!=r['config_sha256'] or manifest['source_sha256']!=r['source_sha256'] or manifest['execution_sha']!=r['execution_sha']:raise ValueError('manifest_provenance')
    expected_models=[]
    for m in r['models']:
        if [h['seed'] for h in m['heads']]!=c['readout_seeds']:raise ValueError('complete_seed_grid')
        expected_models.append(dict(recipe=m['recipe'],parent_hash=m['parent_hash'],heads=[{k:h[k] for k in ('seed','checkpoint','sha256')} for h in m['heads']]))
        for h in m['heads']:
            if len(h['losses'])!=c['updates'] or not all(finite(v) for v in h['losses']):raise ValueError('finite_update_grid')
            p=root/h['checkpoint']
            if p.parent.resolve()!=(root/'artifacts').resolve() or hashlib.sha256(p.read_bytes()).hexdigest()!=h['sha256']:raise ValueError('readout_integrity')
            if json.loads(p.read_text())['provenance']!=dict(parent_hash=m['parent_hash'],source_sha256=r['source_sha256'],config_sha256=r['config_sha256'],execution_sha=r['execution_sha'],seed=h['seed']):raise ValueError('readout_provenance')
    if expected_models!=manifest['models']:raise ValueError('manifest_model_grid')
    for key,n,start in [('source',c['training_states'],c['training_seed_start']),('audit',c['audit_states'],c['audit_seed_start'])]:
        if [s['seed'] for s in r[key]]!=list(range(start,start+n)):raise ValueError('complete_state_grid')
        for s in r[key]:
            if [o['action'] for o in s['outcomes']]!=list(range(9)):raise ValueError('complete_action_grid')
            if any(not finite(o['reward']) for o in s['outcomes']):raise ValueError('finite_outcomes')
            count+=9;imagined+=9*len(c['model_recipes'])
    if hashlib.sha256(json.dumps(r['source'],sort_keys=True).encode()).hexdigest()!=r['source_sha256']:raise ValueError('source_hash')
    conditions=['frozen_reward','source_mean']+[f'calibrated_{s}' for s in c['readout_seeds']]
    for s in r['audit']:
        if set(s['models'])!=set(c['model_recipes']):raise ValueError('audit_parent_grid')
        for m in s['models'].values():
            if set(m['scores'])!=set(conditions) or set(m['metrics'])!=set(conditions):raise ValueError('audit_condition_grid')
            for name in conditions:
                if len(m['scores'][name])!=9 or not all(finite(v) for v in m['scores'][name]):raise ValueError('finite_score_grid')
                if set(m['metrics'][name])!={'selected','regret','optimal','pairwise_accuracy','score_range','reward_mae','uniform_expected_regret'} or any(not finite(v) for k,v in m['metrics'][name].items() if k!='optimal'):raise ValueError('finite_metric_grid')
    if set(r['control'])!=set(c['model_recipes']):raise ValueError('control_parent_grid')
    for model in c['model_recipes']:
        if set(r['control'][model])!=set(c['methods']):raise ValueError('control_condition_grid')
        for method,episodes in r['control'][model].items():
            if [e['seed'] for e in episodes]!=list(range(c['control_seed_start'],c['control_seed_start']+c['control_episodes'])):raise ValueError('control_episode_grid')
            for e in episodes:
                audit_episode(e,c['control_steps']);n=len(e['steps']);count+=n
                imagined+=n*(48 if method=='latent_mpc' else 9 if method=='frozen_reward' or method.startswith('calibrated_') else 0)
    if count!=r['authored_steps'] or imagined!=r['imagined_transitions']:raise ValueError('resource_accounting')
    if count>c['max_authored_steps'] or imagined>c['max_imagined_transitions'] or not finite(r['wall_s']) or r['wall_s']>c['max_wall_s']:raise ValueError('execution_caps')
    if set(r['frozen'])!=set(c['model_recipes']) or not all(r['frozen'].values()):raise ValueError('changed_frozen_network')
    return dict(authored_steps=count,imagined_transitions=imagined,complete=True)
