"""Saved-source residual-update diagnosis; no worlds or neural inference.

The host selects permitted fields. Trajectories receive source arrays only;
assessment outcomes cannot influence inner corrections or restored weights.
"""
import hashlib
import json
import math
import statistics as st
import sys
import time

from nexus.evolution1.catalogue import digest
from .grounded_audit import finite

METHODS = ['learned', 'static', 'fixed', 'replay', 'none']


def config_check(c):
    if (c['schema'] != 'seed_update_diagnosis_v1' or c['methods'] != METHODS or
        c['outer_seeds'] != [6401,6402,6403] or c['prefixes'] != list(range(9)) or
        c['tasks'] != {'train': list(range(95000000,95110001,10000))}):
        raise ValueError('locked_source_diagnosis_grid')
    if c['max_wall_s'] != 30 or c['max_wall_s'] > c['carried_remaining_s']:
        raise ValueError('diagnosis_budget')
    if c['large_step_ratio'] != 2 or c['minimum_harmed_tasks'] != 8:
        raise ValueError('locked_descriptive_rule')
    return dict(real_steps=0, imagined_transitions=0, outer_updates=0)


def source_pack(root, c):
    """Only permitted training arrays, scale and source-fitted weights cross API."""
    config_check(c)
    raw = (root/c['input']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != c['input_sha256']:
        raise ValueError('source_artifact_hash')
    r = json.loads(raw)
    tasks = r['tasks']['train']
    if [t['seed'] for t in tasks] != c['tasks']['train']:
        raise ValueError('source_task_grid')
    for t in tasks:
        if digest(t['arrays']) != t['array_sha256']:
            raise ValueError('source_array_hash')
    pack = dict(scale=r['scale'], tasks=[dict(seed=t['seed'], arrays=t['arrays'],
                array_sha256=t['array_sha256']) for t in tasks],
                controllers=[dict(seed=m['seed'], arms={a:m['arms'][a]['weights']
                    for a in ('learned','static')}) for m in r['controllers']])
    if [m['seed'] for m in pack['controllers']] != c['outer_seeds']:
        raise ValueError('source_controller_grid')
    return pack


def trajectory(task, controller, method, check=lambda: None):
    import torch
    from . import learning_benchmark as lb
    theta = lb.initial(task).detach()
    original = theta.clone()
    rows = []
    for prefix in range(9):
        check()
        if prefix:
            i = prefix-1; x,y = task.support_x[i],task.support_y[i]
            before = float(x@theta)
            prior = theta.clone()
            with torch.no_grad():
                theta = lb.update(theta,x,y,task.old_x,task.old_y,
                    task.support_x[:prefix],task.support_y[:prefix],controller,
                    'learned' if method == 'static' else method)
            change = float(torch.linalg.vector_norm(theta-prior))
            after = float(x@theta)
            residual = float(y)-before
            fraction = (after-before)/residual if abs(residual)>1e-12 else None
            support_before, support_after = residual**2, (float(y)-after)**2
        else:
            change=0.; fraction=None; support_before=support_after=None
        rows.append(dict(prefix=prefix, theta=theta.tolist(), update_l2=change,
            cumulative_update_l2=float(torch.linalg.vector_norm(theta-original)),
            query_mse=float(((task.query_x@theta-task.query_y)**2).mean()),
            retention_mse=float(((task.retention_x@theta-task.retention_y)**2).mean()),
            support_error_before=support_before, support_error_after=support_after,
            residual_corrected_fraction=fraction))
    return rows


def paired(values):
    mean=st.mean(values); half=2.200985160*st.stdev(values)/math.sqrt(12)
    return dict(mean=mean, ci95=[mean-half,mean+half], paired_task_values=values,
                unit='12_reused_source_tasks_one_frozen_core', exploratory=True)


def summarize(rows, c):
    def values(method, prefix, key):
        return [st.mean(rows[str(s)][str(t)][method][prefix][key] for s in c['outer_seeds'])
                for t in c['tasks']['train']]
    curve={m:{str(p):st.mean(values(m,p,'query_mse')) for p in c['prefixes']} for m in METHODS}
    norms={m:values(m,1,'update_l2') for m in METHODS}
    ratios=[a/b if b>1e-12 else None for a,b in zip(norms['learned'],norms['replay'])]
    first_delta=[a-b for a,b in zip(values('learned',1,'query_mse'),values('learned',0,'query_mse'))]
    median=st.median(ratios) if all(v is not None for v in ratios) else None
    pattern=median is not None and median>c['large_step_ratio'] and sum(v>0 for v in first_delta)>=c['minimum_harmed_tasks']
    return dict(label='large_first_update_pattern' if pattern else 'pattern_not_supported',
        median_task_norm_ratio=median,first_step_norms={m:st.mean(v) for m,v in norms.items()},
        harmed_source_tasks=sum(v>0 for v in first_delta),first_query_error_change=paired(first_delta),
        first_replay_minus_learned=paired([a-b for a,b in zip(values('replay',1,'query_mse'),values('learned',1,'query_mse'))]),
        source_query_curves=curve,
        source_retention_curves={m:{str(p):st.mean(values(m,p,'retention_mse')) for p in c['prefixes']} for m in METHODS},
        source_support_after={m:st.mean(rows[str(s)][str(t)][m][1]['support_error_after'] for s in c['outer_seeds'] for t in c['tasks']['train']) for m in METHODS},
        task_norm_ratios=ratios,undefined_ratio_tasks=[t for t,r in zip(c['tasks']['train'],ratios) if r is None],
        generalization_test=False,causation_established=False)


def validate(r,c,pack=None):
    config_check(c)
    if r['config']!=c or r['frozen_controllers'] is not True or r['source_only'] is not True:
        raise ValueError('source_frozen_integrity')
    if set(r['rows'])!=set(map(str,c['outer_seeds'])):
        raise ValueError('seed_grid')
    for tasks in r['rows'].values():
        if set(tasks)!=set(map(str,c['tasks']['train'])):raise ValueError('task_grid')
        for methods in tasks.values():
            if set(methods)!=set(METHODS):raise ValueError('method_grid')
            for snapshots in methods.values():
                if [v['prefix'] for v in snapshots]!=c['prefixes']:raise ValueError('prefix_grid')
                for v in snapshots:
                    if any(not finite(v[k]) or v[k]<0 for k in ('query_mse','retention_mse','update_l2','cumulative_update_l2')):
                        raise ValueError('finite_required_metrics')
                    if len(v['theta'])!=33 or any(not finite(x) for x in v['theta']):raise ValueError('theta_grid')
                    for k in ('support_error_before','support_error_after','residual_corrected_fraction'):
                        if v[k] is not None and not finite(v[k]):raise ValueError('finite_optional_metrics')
                    if type(v['prefix']) is not int:raise ValueError('typed_prefix')
                    if v['prefix'] and any(v[k] is None for k in ('support_error_before','support_error_after')):
                        raise ValueError('missing_support_metrics')
    if r['analysis']!=summarize(r['rows'],c):raise ValueError('summary_arithmetic')
    if pack is not None:
        if r['source_pack_sha256']!=digest(pack):raise ValueError('source_pack_hash')
        scale=pack['scale'];source={str(t['seed']):t['arrays'] for t in pack['tasks']}
        for tasks in r['rows'].values():
            for task_id,methods in tasks.items():
                a=source[task_id]
                for snapshots in methods.values():
                    previous=snapshots[0]['theta']
                    for row in snapshots:
                        theta=row['theta']
                        for role in ('query','retention'):
                            mse=st.mean((sum(v*w/s for v,w,s in zip(x,theta,scale))-y)**2
                                for x,y in zip(a[role+'_x'],a[role+'_y']))
                            if abs(mse-row[role+'_mse'])>2e-6:raise ValueError('source_mse_arithmetic')
                        norm=sum((x-y)**2 for x,y in zip(theta,previous))**.5
                        if abs(norm-row['update_l2'])>2e-6:raise ValueError('update_norm_arithmetic')
                        previous=theta
    return True


def run(request):
    import torch
    from . import learning_benchmark as lb
    from .plasticity import PlasticityController
    c=request['inputs']['study_config'];config_check(c)
    pack=request['inputs']['source_pack'];before=digest(pack)
    start=time.monotonic();torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('diagnosis_wall_cap')
    scale=torch.tensor(pack['scale']);tasks={}
    for item in pack['tasks']:
        a=item['arrays']
        t=lb.LessonTask(*(torch.tensor(a[k],dtype=torch.float32) for k in
            ('support_x','support_y','query_x','query_y','old_x','old_y','retention_x','retention_y')))
        tasks[item['seed']]=lb.scaled(t,scale)
    rows={};lb.WORK.clear();frozen=True
    for seed_record in pack['controllers']:
        seed=seed_record['seed'];rows[str(seed)]={};models={}
        for method,weights in seed_record['arms'].items():
            m=PlasticityController(33);m.load_state_dict({k:torch.tensor(v) for k,v in weights.items()})
            m.eval();m.requires_grad_(False);models[method]=m
        initial_weights={m:digest({k:v.tolist() for k,v in model.state_dict().items()}) for m,model in models.items()}
        for task_id,task in tasks.items():
            rows[str(seed)][str(task_id)]={m:trajectory(task,models.get(m),m,check) for m in METHODS}
        frozen &= all(digest({k:v.tolist() for k,v in model.state_dict().items()})==initial_weights[m] for m,model in models.items())
    r=dict(config=c,rows=rows,source_pack_sha256=before,source_only=True,
           frozen_controllers=frozen and digest(pack)==before,update_work=dict(lb.WORK),
           analysis=summarize(rows,c),wall_s=time.monotonic()-start,declared_complete=False)
    validate(r,c,pack);r['declared_complete']=True
    a=r['analysis'];curve=a['source_query_curves']
    return dict(adapter='seed_update_diagnosis_v1',study=r,
        metrics=dict(mse=curve['learned']['1'],baseline_mse=curve['replay']['1'],worst_error_increase=a['first_query_error_change']['mean']),
        curve=[],model=dict(schema='unchanged_source_controllers_v1',controllers=pack['controllers']),
        runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1),
        resources=dict(updates=0,real_steps=0,imagined_transitions=0,world_model_forwards=0,
            network_forwards=576,controller_forwards=576,inner_update_calls=1440,
            active_corrections=1152,cpu_s=time.process_time(),parameter_count=990,trainable_parameters=0))


def validate_output(output,c,caps,pack=None):
    validate(output['study'],c,pack)
    if output['adapter']!='seed_update_diagnosis_v1' or output['study']['declared_complete'] is not True:
        raise ValueError('diagnosis_incomplete')
    work=output['resources']
    if any(not finite(v) or v<0 for v in work.values()):raise ValueError('finite_resource_metrics')
    if any(work[k]!=0 for k in ('updates','real_steps','imagined_transitions','world_model_forwards','trainable_parameters')):
        raise ValueError('source_only_zero_new_execution')
    if work['inner_update_calls']!=1440 or work['active_corrections']!=1152 or work['controller_forwards']!=576 or work['network_forwards']!=576 or work['cpu_s']>caps['cpu_s']:
        raise ValueError('diagnosis_work_grid')
    return True


def saved_replay(root):
    """Stdlib-only recorded-source card. Never replays the update algorithm."""
    r=json.loads((root/'artifacts/seed_update_diagnosis.json').read_text())
    c=json.loads((root/'configs/seed_update_diagnosis.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_source_diagnosis')
    validate(r,c,source_pack(root,c))
    h=r['host_receipt'];a=r['analysis']
    return dict(id=h['id'],mode='recorded_source_only_diagnosis',status=h['status'],
        failure=h['failure'],wall_s=h['wall_s'],memory_mb=h['peak_sampled_rss_mb'],
        revision=r['execution_sha'],metrics=None,curve=[],model_sha256=r['source_pack_sha256'],
        resources=r['resources'],study=None,diagnosis=a)
