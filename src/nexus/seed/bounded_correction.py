"""One source-only output-bound intervention on the existing update rule.

No query rows enter the limiter. Cached controls are verified, not re-executed.
No change to runtime adaptation defaults or historical weights.
"""
import copy
import hashlib
import json
import math
import statistics as st
import sys
import time

from nexus.evolution1.catalogue import digest
from .grounded_audit import finite
from . import update_diagnosis as prior

BOUNDED = ['learned_bounded','static_bounded','fixed_bounded']
METHODS = BOUNDED + prior.METHODS


def config_check(c):
    if (c['schema']!='seed_bounded_correction_v1' or c['methods']!=METHODS or
        c['tasks']!={'train':list(range(95000000,95110001,10000))} or
        c['outer_seeds']!=[6401,6402,6403] or c['prefixes']!=list(range(9)) or
        c['curve_budgets']!=[1,2,4,8]):raise ValueError('locked_bounded_grid')
    expected=dict(bound_fraction=.25,minimum_bound=1e-6,stabilization_min_fraction=.1,
                  replay_min_fraction=.05,learned_specific_min_fraction=.05,retention_excess=.01,max_wall_s=30)
    if any(type(c[k]) not in (int,float) or c[k]!=v for k,v in expected.items()):
        raise ValueError('locked_bound_or_screen')
    if c['max_wall_s']>c['carried_remaining_s']:raise ValueError('bounded_budget')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=0)


def source_pack(root,c):
    config_check(c)
    cfg=(root/c['source_plan']).read_bytes();raw=(root/c['baseline']).read_bytes()
    if hashlib.sha256(cfg).hexdigest()!=c['source_plan_sha256'] or hashlib.sha256(raw).hexdigest()!=c['baseline_sha256']:
        raise ValueError('cached_source_provenance')
    old_c=json.loads(cfg);data=prior.source_pack(root,old_c);reference=json.loads(raw)
    if reference['declared_complete'] is not True:raise ValueError('incomplete_cached_control')
    prior.validate(reference,old_c,data)
    return dict(data=data,cached_rows=reference['rows'])


def bounded_delta(theta,candidate,design,tau):
    """Prediction RMS trust bound on observed design rows only."""
    import torch
    if not finite(tau) or tau<=0 or design.ndim!=2 or not len(design):raise ValueError('positive_output_bound')
    delta=candidate-theta
    raw=float((design@delta).square().mean().sqrt())
    if not finite(raw):raise ValueError('nonfinite_candidate')
    alpha=min(1.,tau/max(raw,1e-12))
    result=theta+alpha*delta
    actual=float((design@(result-theta)).square().mean().sqrt())
    if not torch.isfinite(result).all() or actual>tau+2e-6:raise ValueError('output_bound_violation')
    return result,dict(alpha=alpha,candidate_rms=raw,actual_rms=actual,design_rows=len(design))


def limiter(tau,logs):
    def update(theta,x,y,anchors,old_y,seen_x,seen_y,controller,method):
        import torch
        from . import learning_benchmark as lb
        candidate=lb.update(theta,x,y,anchors,old_y,seen_x,seen_y,controller,method)
        result,info=bounded_delta(theta,candidate,torch.cat((anchors,seen_x)),tau)
        logs.append(dict(prefix=len(seen_x),**info))
        return result
    return update


def summarize(rows,limits,c):
    def task_values(m,key,prefixes):
        return [st.mean(rows[str(s)][str(t)][m][p][key] for s in c['outer_seeds'] for p in prefixes)
                for t in c['tasks']['train']]
    curves={m:task_values(m,'query_mse',c['curve_budgets']) for m in METHODS}
    means={m:st.mean(v) for m,v in curves.items()}
    contrasts={m:prior.paired([a-b for a,b in zip(curves[m],curves['learned_bounded'])])
               for m in ('learned','replay','fixed_bounded')}
    retention={m:st.mean(task_values(m,'retention_mse',[8])) for m in METHODS}
    def advantage(m,fraction):
        return contrasts[m]['mean']>=fraction*means[m] and contrasts[m]['ci95'][0]>0
    stable=advantage('learned',c['stabilization_min_fraction']) and retention['learned_bounded']<=retention['learned']+c['retention_excess']
    return dict(curve_means=means,contrasts=contrasts,final_retention=retention,
        stabilization_pass=stable,beats_replay=advantage('replay',c['replay_min_fraction']),
        learned_specific_pass=advantage('fixed_bounded',c['learned_specific_min_fraction']),
        advance_source_screen=stable and advantage('replay',c['replay_min_fraction']),
        query_curves={m:{str(p):st.mean(task_values(m,'query_mse',[p])) for p in c['prefixes']} for m in METHODS},
        worst_prefix_mse={m:max(st.mean(task_values(m,'query_mse',[p])) for p in range(1,9)) for m in METHODS},
        clamp_rates={m:st.mean(float(v['alpha']<1) for tasks in limits.values() for methods in tasks.values() for v in methods[m]) for m in BOUNDED},
        generalization_test=False,runtime_promotion=False)


def validate(r,c,pack):
    config_check(c)
    if r['config']!=c or r['frozen_controllers'] is not True or r['source_only'] is not True or r['source_pack_sha256']!=digest(pack):
        raise ValueError('bounded_source_integrity')
    prior.validate_rows(r['rows'],c,METHODS)
    prior.validate_source_math(r['rows'],pack['data'])
    if not finite(r['tau']) or r['tau']<=0:raise ValueError('finite_bound')
    if not finite(r['source_residual_rms']) or r['tau']!=max(c['minimum_bound'],c['bound_fraction']*r['source_residual_rms']):
        raise ValueError('source_bound_rule')
    if set(r['limit_trace'])!=set(map(str,c['outer_seeds'])):raise ValueError('limit_seed_grid')
    arrays={str(t['seed']):t['arrays'] for t in pack['data']['tasks']};scale=pack['data']['scale']
    initial_seed=str(c['outer_seeds'][0])
    residual_rms=st.mean((y-sum(x*w/z for x,w,z in zip(row,pack['cached_rows'][initial_seed][t]['none'][0]['theta'],scale)))**2
        for t,a in arrays.items() for row,y in zip(a['support_x'],a['support_y']))**.5
    if abs(residual_rms-r['source_residual_rms'])>2e-6:raise ValueError('support_only_scale_arithmetic')
    for s,tasks in r['rows'].items():
        if set(r['limit_trace'][s])!=set(tasks):raise ValueError('limit_task_grid')
        for t,methods in tasks.items():
            if set(r['limit_trace'][s][t])!=set(BOUNDED):raise ValueError('limit_method_grid')
            for m in prior.METHODS:
                if methods[m]!=pack['cached_rows'][s][t][m]:raise ValueError('cached_control_changed')
            for m in BOUNDED:
                if methods[m][0]!=methods['learned'][0]:raise ValueError('initial_fit_mismatch')
                logs=r['limit_trace'][s][t][m]
                if [v['prefix'] for v in logs]!=list(range(1,9)):raise ValueError('limit_prefix_grid')
                for p,v in enumerate(logs,1):
                    if type(v['prefix']) is not int:raise ValueError('typed_limit_prefix')
                    if any(not finite(v[k]) or v[k]<0 for k in ('alpha','candidate_rms','actual_rms')) or v['alpha']>1:
                        raise ValueError('finite_limiter_metrics')
                    if type(v['design_rows']) is not int or v['design_rows']!=4+p:raise ValueError('prefix_only_design')
                    before=methods[m][p-1]['theta'];after=methods[m][p]['theta']
                    design=arrays[t]['old_x']+arrays[t]['support_x'][:p]
                    rms=st.mean(sum(x*(a-b)/z for x,a,b,z in zip(row,after,before,scale))**2 for row in design)**.5
                    if abs(rms-v['actual_rms'])>2e-6 or rms>r['tau']+2e-6:raise ValueError('actual_bound_arithmetic')
    if r['analysis']!=summarize(r['rows'],r['limit_trace'],c):raise ValueError('bounded_summary_arithmetic')
    return True


def run(request):
    import torch
    from . import learning_benchmark as lb
    from .plasticity import PlasticityController
    c=request['inputs']['study_config'];config_check(c);pack=request['inputs']['source_pack']
    fingerprint=digest(pack);start=time.monotonic();torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('bounded_wall_cap')
    data=pack['data'];scale=torch.tensor(data['scale']);tasks={};lb.WORK.clear()
    for item in data['tasks']:
        a=item['arrays'];task=lb.LessonTask(*(torch.tensor(a[k],dtype=torch.float32) for k in
            ('support_x','support_y','query_x','query_y','old_x','old_y','retention_x','retention_y')))
        tasks[item['seed']]=lb.scaled(task,scale)
    residuals=torch.cat([t.support_y-t.support_x@lb.initial(t) for t in tasks.values()])
    rms=float(residuals.square().mean().sqrt());tau=max(c['minimum_bound'],c['bound_fraction']*rms)
    rows=copy.deepcopy(pack['cached_rows']);limits={};frozen=True
    for record in data['controllers']:
        s=str(record['seed']);limits[s]={};models={}
        for name,weights in record['arms'].items():
            model=PlasticityController(33);model.load_state_dict({k:torch.tensor(v) for k,v in weights.items()})
            model.eval();model.requires_grad_(False);models[name]=model
        original={m:digest({k:v.tolist() for k,v in model.state_dict().items()}) for m,model in models.items()}
        for task_id,task in tasks.items():
            t=str(task_id);limits[s][t]={}
            for method in BOUNDED:
                logs=[];base=method.removesuffix('_bounded')
                rows[s][t][method]=prior.trajectory(task,models.get(base),base,check,update_fn=limiter(tau,logs))
                limits[s][t][method]=logs
        frozen &= all(digest({k:v.tolist() for k,v in model.state_dict().items()})==original[m] for m,model in models.items())
    r=dict(config=c,rows=rows,limit_trace=limits,tau=tau,source_residual_rms=rms,
        source_pack_sha256=fingerprint,source_only=True,frozen_controllers=frozen and digest(pack)==fingerprint,
        update_work=dict(lb.WORK),analysis=summarize(rows,limits,c),declared_complete=False,wall_s=time.monotonic()-start)
    validate(r,c,pack);r['declared_complete']=True;a=r['analysis']
    return dict(adapter='seed_bounded_correction_v1',study=r,curve=[],
        metrics=dict(mse=a['curve_means']['learned_bounded'],baseline_mse=a['curve_means']['replay'],
            worst_error_increase=a['final_retention']['learned_bounded']-a['final_retention']['learned']),
        model=dict(schema='unchanged_source_controllers_v1',controllers=data['controllers']),
        runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1),
        resources=dict(updates=0,real_steps=0,imagined_transitions=0,world_model_forwards=0,
            controller_forwards=576,inner_update_calls=864,cached_update_calls=1440,
            cached_snapshots=1620,new_snapshots=972,initial_solves=120,source_scale_examples=96,
            bound_design_rows=7344,bound_prediction_examples=14688,source_query_examples=26244,
            source_retention_examples=26244,cpu_s=time.process_time(),parameter_count=990,trainable_parameters=0))


def validate_output(output,c,caps,pack):
    r=output['study'];validate(r,c,pack);work=output['resources']
    if output['adapter']!='seed_bounded_correction_v1' or r['declared_complete'] is not True:raise ValueError('incomplete_bounded_run')
    if any(not finite(v) or v<0 for v in work.values()):raise ValueError('finite_bounded_costs')
    if any(work[k]!=0 for k in ('updates','real_steps','imagined_transitions','world_model_forwards','trainable_parameters')) or work['cpu_s']>caps['cpu_s']:
        raise ValueError('bounded_resource_cap')
    expected=dict(calls_learned=576,calls_fixed=288,old_anchor_initial_solves=120,
                  protected_current_examples=864,protected_anchor_examples=3456,protected_solves=864)
    if r['update_work']!=expected:raise ValueError('actual_update_work_mismatch')
    expected_costs=dict(updates=0,real_steps=0,imagined_transitions=0,world_model_forwards=0,
        controller_forwards=576,inner_update_calls=864,cached_update_calls=1440,cached_snapshots=1620,
        new_snapshots=972,initial_solves=120,source_scale_examples=96,bound_design_rows=7344,
        bound_prediction_examples=14688,source_query_examples=26244,source_retention_examples=26244,
        parameter_count=990,trainable_parameters=0)
    if set(work)!=set(expected_costs)|{'cpu_s'} or any(type(work[k]) is not int or work[k]!=v for k,v in expected_costs.items()):
        raise ValueError('reported_bounded_costs_mismatch')
    return True


def saved_replay(root):
    """Recorded evidence only; stdlib arithmetic, no correction execution."""
    c=json.loads((root/'configs/seed_bounded_correction.json').read_text())
    r=json.loads((root/'artifacts/seed_bounded_correction.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_bounded_evidence')
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_only_comparison',status=h['status'],
        failure=h['failure'],wall_s=h['wall_s'],memory_mb=h['peak_sampled_rss_mb'],
        revision=r['execution_sha'],metrics=None,curve=[],resources=r['resources'],
        model_sha256=r['source_pack_sha256'],study=None,bounded=r['analysis'])
