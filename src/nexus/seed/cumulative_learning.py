"""Task-blocked training of the existing small precision controller.

The decoder is never loaded. New rules see nine permitted source tasks only.
All inner updates are based solely on observed teaching and old-anchor rows.
"""
import hashlib
import json
import math
import statistics as st
import sys
import time

from nexus.evolution1.catalogue import digest
from .grounded_audit import finite
from . import update_diagnosis as prior

METHODS=['learned_cumulative','static_cumulative','fixed_cumulative','replay','fixed_bounded','none']


def config_check(c):
    if (c['schema']!='seed_cumulative_learning_v1' or c['methods']!=METHODS or
        c['outer_seeds']!=[7101,7102,7103] or c['fold_count']!=4 or
        c['tasks']!={'train':list(range(95000000,95110001,10000))} or
        c['prefixes']!=list(range(9)) or c['curve_budgets']!=[1,2,4,8]):raise ValueError('locked_cumulative_grid')
    expected=dict(ridge=.1,meta_updates=64,meta_lr=.01,retention_weight=.5,
                  minimum_fraction=.05,retention_excess=.01,max_wall_s=60,max_outer_updates=1536)
    if any(type(c[k]) not in (int,float) or c[k]!=v for k,v in expected.items()) or c['max_wall_s']>c['carried_remaining_s']:
        raise ValueError('locked_cumulative_recipe')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=1536)


def partition(c,fold):
    ids=c['tasks']['train']
    if type(fold) is not int or not 0<=fold<c['fold_count']:raise ValueError('fold_id')
    return ([t for i,t in enumerate(ids) if i%4!=fold], [t for i,t in enumerate(ids) if i%4==fold])


def source_pack(root,c):
    config_check(c);raw=(root/c['source_plan']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=c['source_plan_sha256']:raise ValueError('source_plan_hash')
    # Deliberately discard legacy globally fitted scale and controller weights.
    return dict(tasks=prior.source_pack(root,json.loads(raw))['tasks'])


def prepare_fold(pack,c,fold):
    import torch
    from . import learning_benchmark as lb
    train_ids,excluded=partition(c,fold);tasks={}
    for item in pack['tasks']:
        a=item['arrays'];tasks[item['seed']]=lb.LessonTask(*(torch.tensor(a[k],dtype=torch.float32) for k in
            ('support_x','support_y','query_x','query_y','old_x','old_y','retention_x','retention_y')))
    scale=lb.scale_features(torch.cat([x for t in train_ids for x in (tasks[t].support_x,tasks[t].old_x)]))
    tasks={t:lb.scaled(task,scale) for t,task in tasks.items()}
    rms=float(torch.cat([tasks[t].support_y-tasks[t].support_x@lb.initial(tasks[t]) for t in train_ids]).square().mean().sqrt())
    source=[t for t in pack['tasks'] if t['seed'] in train_ids]
    return [tasks[t] for t in train_ids], {t:tasks[t] for t in excluded}, dict(
        train_ids=train_ids,excluded_ids=excluded,scale=scale.tolist(),tau=max(1e-6,.25*rms),
        source_sha256=digest(source),scale_fit_rows=108,tau_fit_rows=72)


def posterior(initial,x,y,diagonal,ridge=.1):
    import torch
    from . import learning_benchmark as lb
    if (initial.ndim!=1 or x.ndim!=2 or x.shape[1]!=len(initial) or
        y.shape!=(len(x),) or diagonal.shape!=initial.shape or not finite(ridge) or ridge<=0):
        raise ValueError('posterior_shapes_or_ridge')
    if any(not torch.isfinite(v).all() for v in (initial,x,y,diagonal)) or not (diagonal>0).all():
        raise ValueError('finite_positive_precision')
    lb.count('cumulative_solves')
    xd=x*diagonal
    answer=initial+diagonal*(x.T@torch.linalg.solve(ridge*torch.eye(len(x),dtype=x.dtype,device=x.device)+xd@x.T,y-x@initial))
    if not torch.isfinite(answer).all():raise ValueError('finite_posterior')
    return answer


def cumulative_step(initial,previous,x,y,anchors,old_y,seen_x,seen_y,controller,method,ridge=.1):
    import torch
    from . import learning_benchmark as lb
    from .plasticity import context
    if method=='learned':
        lb.count('cumulative_controller_forwards');diagonal=controller(context(previous,x,y,anchors))
    elif method=='fixed':diagonal=torch.ones_like(initial)
    else:raise ValueError('cumulative_method')
    return posterior(initial,torch.cat((anchors,seen_x)),torch.cat((old_y,seen_y)),diagonal,ridge)


def curve(task,controller,method,check=lambda:None,*,ridge=.1):
    from . import learning_benchmark as lb
    theta=lb.initial(task).detach();initial=theta.clone();rows=[];snaps={}
    for i,(x,y) in enumerate(zip(task.support_x,task.support_y),1):
        check();theta=cumulative_step(initial,theta,x,y,task.old_x,task.old_y,
            task.support_x[:i],task.support_y[:i],controller,method,ridge)
        if i in (1,2,4,8):
            error=(task.query_x@theta-task.query_y).square().mean()
            forgetting=(task.retention_x@theta-task.retention_y).square().mean()-(task.retention_x@initial-task.retention_y).square().mean()
            rows.append((i,error,forgetting));snaps[i]=theta.detach().clone()
    return rows,snaps


def cumulative_updater(ridge):
    initial=None
    def update(theta,x,y,anchors,old_y,seen_x,seen_y,controller,method):
        nonlocal initial
        if initial is None:initial=theta.detach().clone()
        return cumulative_step(initial,theta,x,y,anchors,old_y,seen_x,seen_y,controller,method,ridge)
    return update


def seed_interval(values):
    if len(values)!=3 or any(not finite(v) for v in values):raise ValueError('three_meta_training_units')
    mean=st.mean(values);half=4.302652730*st.stdev(values)/math.sqrt(3)
    return dict(mean=mean,ci95=[mean-half,mean+half],paired_seed_values=values,
                unit='three_update_rule_training_seeds_conditional_on_one_core_and_fixed_source_bank',exploratory=True)


def summarize(rows,c,*,methods=METHODS,learner='learned_cumulative',static='static_cumulative'):
    def error(s,m,ids,key='query_mse',prefixes=None):
        return st.mean(rows[str(s)][str(t)][m][p][key] for t in ids for p in (prefixes or c['curve_budgets']))
    ids=c['tasks']['train'];seeds=c['outer_seeds']
    per={m:[error(s,m,ids) for s in seeds] for m in methods}
    means={m:st.mean(v) for m,v in per.items()}
    contrasts={m:seed_interval([a-b for a,b in zip(per[m],per[learner])]) for m in methods[1:]}
    retention={m:st.mean(error(s,m,ids,'retention_mse',[8]) for s in seeds) for m in methods}
    passed=all(contrasts[m]['mean']>=c['minimum_fraction']*means[m] and contrasts[m]['ci95'][0]>0
               for m in (static,'fixed_cumulative','replay','fixed_bounded'))
    retained=retention[learner]<=retention['fixed_cumulative']+c['retention_excess']
    return dict(curve_means=means,per_seed_curve=per,contrasts=contrasts,final_retention=retention,
        learned_screen_pass=passed,retention_pass=retained,source_screen_pass=passed and retained,
        generic_fixed_minus_replay=seed_interval([a-b for a,b in zip(per['fixed_cumulative'],per['replay'])]),
        query_curves={m:{str(p):st.mean(error(s,m,ids,prefixes=[p]) for s in seeds) for p in c['prefixes']} for m in methods},
        per_fold={str(f):{m:st.mean(error(s,m,partition(c,f)[1]) for s in seeds) for m in methods} for f in range(4)},
        per_task={str(t):{m:st.mean(error(s,m,[t]) for s in seeds) for m in methods} for t in ids},
        fresh_validation=False,runtime_promotion=False,independent_pretrained_cores=1)


def checkpoint_bytes(info,*,width=33):
    provenance={k:info['provenance'][k] for k in ('config_sha256','fold','seed','source_sha256','source_only')}
    raw=json.dumps(dict(schema='seed_plasticity_v1',width=width,provenance=provenance,
        weights={k:info['weights'][k] for k in ('logits.weight','logits.bias')}),allow_nan=False).encode()
    if hashlib.sha256(raw).hexdigest()!=info['sha256']:raise ValueError('nonreproducible_new_rule_checkpoint')
    return raw


def complete_grid(r,c,*,methods=METHODS):
    prior.validate_rows(r['rows'],c,methods)
    if set(r['folds'])!=set(map(str,range(4))):raise ValueError('fold_grid')
    for fold in range(4):
        entry=r['folds'][str(fold)];train,held=partition(c,fold)
        if entry['train_ids']!=train or entry['excluded_ids']!=held:raise ValueError('fold_assignment')
        if set(entry['models'])!=set(map(str,c['outer_seeds'])):raise ValueError('model_seed_grid')
        for arms in entry['models'].values():
            if set(arms)!=set(c['methods'][:2]):raise ValueError('fitted_arm_grid')
            for info in arms.values():
                if [row['update'] for row in info['training']]!=list(range(1,65)):raise ValueError('outer_update_grid')
                if type(info['checkpoint']) is not str or type(info['sha256']) is not str or len(info['sha256'])!=64:
                    raise ValueError('required_checkpoint_grid')
    return True


def validate(r,c,pack,*,config_fn=config_check,methods=METHODS,learner='learned_cumulative',static='static_cumulative',width=33):
    config_fn(c)
    if r['config']!=c or r['source_pack_sha256']!=digest(pack) or r['frozen_during_evaluation'] is not True:
        raise ValueError('cumulative_source_integrity')
    complete_grid(r,c,methods=methods)
    all_source={t['seed']:t for t in pack['tasks']}
    for fold in range(4):
        entry=r['folds'][str(fold)];train,held=partition(c,fold)
        if entry['train_ids']!=train or entry['excluded_ids']!=held or set(train)&set(held):raise ValueError('fold_training_separation')
        if entry['source_sha256']!=digest([all_source[t] for t in train]):raise ValueError('fold_source_hash')
        scale=entry['scale']
        if len(scale)!=33 or any(not finite(x) or x<=0 for x in scale):raise ValueError('fold_scale')
        features=[row for t in train for k in ('support_x','old_x') for row in all_source[t]['arrays'][k]]
        expected=[max(.01,st.mean(row[j]**2 for row in features)**.5)*33**.5 for j in range(33)]
        if any(abs(a-b)>2e-6 for a,b in zip(scale,expected)):raise ValueError('train_only_scale_arithmetic')
        if not finite(entry['tau']) or entry['tau']<=0:raise ValueError('fold_bound')
        if set(entry['models'])!=set(map(str,c['outer_seeds'])):raise ValueError('model_seed_grid')
        for seed,arms in entry['models'].items():
            if set(arms)!={learner,static}:raise ValueError('fitted_arm_grid')
            if arms[learner]['source_schedule_sha256']!=arms[static]['source_schedule_sha256']:
                raise ValueError('paired_source_schedule')
            for method,info in arms.items():
                provenance=dict(config_sha256=digest(c),fold=fold,seed=int(seed),source_sha256=entry['source_sha256'],source_only=True)
                if info['provenance']!=provenance or info['checkpoint']!=f'rule-{fold}-{seed}-{method}.json':raise ValueError('rule_training_provenance')
                if [v['update'] for v in info['training']]!=list(range(1,65)):raise ValueError('outer_update_grid')
                if any(set(row)!={'update','task_index','query_mse','forgetting','gradient_norm'} for row in info['training']):
                    raise ValueError('required_training_metric_grid')
                if any(not finite(v) for row in info['training'] for v in row.values()):raise ValueError('finite_training_metrics')
                if any(type(row['update']) is not int or type(row['task_index']) is not int or not 0<=row['task_index']<9 for row in info['training']):raise ValueError('source_schedule_bounds')
                if digest([v['task_index'] for v in info['training']])!=info['source_schedule_sha256']:raise ValueError('source_schedule_arithmetic')
                if info['trainable_parameters']!=(5*width if method==learner else width):raise ValueError('rule_trainable_parameter_count')
                w=info['weights']
                if set(w)!={'logits.weight','logits.bias'} or len(w['logits.weight'])!=width or len(w['logits.bias'])!=width:
                    raise ValueError('rule_weight_grid')
                if any(len(row)!=4 or any(not finite(v) for v in row) for row in w['logits.weight']) or any(not finite(v) for v in w['logits.bias']):
                    raise ValueError('finite_rule_weights')
                if method==static and any(v!=0 for row in w['logits.weight'] for v in row):raise ValueError('static_contextual_weights')
                if not finite(info['parameter_change_l2']) or not finite(info['seconds']):raise ValueError('finite_rule_diagnostics')
                checkpoint_bytes(info,width=width)
        subset={s:{str(t):methods[str(t)] for t in held} for s,methods in r['rows'].items()}
        prior.validate_source_math(subset,dict(scale=scale,tasks=[all_source[t] for t in held]))
    if r['analysis']!=summarize(r['rows'],c,methods=methods,learner=learner,static=static):raise ValueError('cumulative_summary_arithmetic')
    return True


def run(request):
    import torch
    from pathlib import Path
    from . import learning_benchmark as lb
    from .nonlinear_learning import fit_source
    from .bounded_correction import limiter
    c=request['inputs']['study_config'];config_check(c);pack=request['inputs']['source_pack'];fingerprint=digest(pack)
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True);lb.WORK.clear();start=time.monotonic()
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('cumulative_wall_cap')
    r=dict(config=c,source_pack_sha256=fingerprint,folds={},rows={str(s):{} for s in c['outer_seeds']},
           declared_complete=False,frozen_during_evaluation=True)
    def progress():
        r.update(wall_s=time.monotonic()-start,update_work=dict(lb.WORK))
        temporary=Path('progress.tmp');temporary.write_text(json.dumps(r,allow_nan=False));temporary.replace('progress.json')
    progress()
    for fold in range(4):
        train,held,meta=prepare_fold(pack,c,fold);meta['models']={};r['folds'][str(fold)]=meta
        for seed in c['outer_seeds']:
            models={};arms={};meta['models'][str(seed)]=arms
            for static,method in ((False,'learned_cumulative'),(True,'static_cumulative')):
                callback=lambda t,m,k,chk:curve(t,m,k,chk,ridge=c['ridge'])
                model,info=fit_source(train,seed+100*fold,static,c,check,curve_fn=callback)
                info['provenance']=dict(config_sha256=digest(c),fold=fold,seed=seed,source_sha256=meta['source_sha256'],source_only=True)
                path=Path(f'rule-{fold}-{seed}-{method}.json')
                info.update(checkpoint=path.name,sha256=model.export(path,info['provenance']),weights={k:v.tolist() for k,v in model.state_dict().items()})
                arms[method]=info;models[method]=model
                progress()
            before={m:digest({k:v.tolist() for k,v in model.state_dict().items()}) for m,model in models.items()}
            for task_id,task in held.items():
                cell={};r['rows'][str(seed)][str(task_id)]=cell
                for method in METHODS:
                    if method.endswith('_cumulative'):
                        base='fixed' if method=='fixed_cumulative' else 'static' if method=='static_cumulative' else 'learned'
                        cell[method]=prior.trajectory(task,models.get(method),base,check,update_fn=cumulative_updater(c['ridge']))
                    elif method=='fixed_bounded':cell[method]=prior.trajectory(task,None,'fixed',check,update_fn=limiter(meta['tau'],[]))
                    else:cell[method]=prior.trajectory(task,None,method,check)
            r['frozen_during_evaluation'] &= all(digest({k:v.tolist() for k,v in model.state_dict().items()})==before[m] for m,model in models.items())
            progress()
    r.update(analysis=summarize(r['rows'],c),update_work=dict(lb.WORK),wall_s=time.monotonic()-start)
    validate(r,c,pack);r['declared_complete']=True;progress();a=r['analysis']
    return dict(adapter='seed_cumulative_learning_v1',study=r,curve=[],
        model=dict(schema='source_crossfit_rules_v1',folds=r['folds']),
        metrics=dict(mse=a['curve_means']['learned_cumulative'],baseline_mse=min(a['curve_means'][m] for m in METHODS[1:]),
                     worst_error_increase=a['final_retention']['learned_cumulative']-a['final_retention']['fixed_cumulative']),
        runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1),
        resources=dict(updates=1536,real_steps=0,imagined_transitions=0,world_model_forwards=0,
            source_support_examples=12288,source_query_examples=165888,source_retention_examples=165888,
            cumulative_train_support_rows=55296,cumulative_train_anchor_rows=49152,
            evaluation_query_examples=52488,evaluation_retention_examples=52488,controller_forwards=12864,
            cumulative_solves=13152,evaluation_update_calls=1728,trained_rules=24,stored_rule_parameters=3960,
            cpu_s=time.process_time()))


def validate_output(output,c,caps,pack):
    r=output['study'];validate(r,c,pack);w=output['resources']
    if output['adapter']!='seed_cumulative_learning_v1' or r['declared_complete'] is not True:raise ValueError('incomplete_cumulative_run')
    if output['model']!=dict(schema='source_crossfit_rules_v1',folds=r['folds']):raise ValueError('trained_rule_output_mismatch')
    expected=dict(updates=1536,real_steps=0,imagined_transitions=0,world_model_forwards=0,
        source_support_examples=12288,source_query_examples=165888,source_retention_examples=165888,
        cumulative_train_support_rows=55296,cumulative_train_anchor_rows=49152,
        evaluation_query_examples=52488,evaluation_retention_examples=52488,controller_forwards=12864,
        cumulative_solves=13152,evaluation_update_calls=1728,trained_rules=24,stored_rule_parameters=3960)
    if set(w)!=set(expected)|{'cpu_s'} or any(type(w[k]) is not int or w[k]!=v for k,v in expected.items()):raise ValueError('cumulative_resource_grid')
    if not finite(w['cpu_s']) or not 0<=w['cpu_s']<=caps['cpu_s'] or w['updates']>caps['updates']:raise ValueError('cumulative_execution_cap')
    if r['update_work'].get('cumulative_solves')!=13152 or r['update_work'].get('cumulative_controller_forwards')!=12864:
        raise ValueError('actual_cumulative_work_mismatch')
    return True


def saved_replay(root):
    """Read-only recorded cross-fit results; no training or neural imports."""
    c=json.loads((root/'configs/seed_cumulative_learning.json').read_text())
    r=json.loads((root/'artifacts/seed_cumulative_learning.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_cumulative_evidence')
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_task_blocked_learning',status=h['status'],
        failure=h['failure'],wall_s=h['wall_s'],memory_mb=h['peak_sampled_rss_mb'],
        revision=r['execution_sha'],metrics=None,curve=[],resources=r['resources'],
        model_sha256=digest({f:v['models'] for f,v in r['folds'].items()}),study=None,cumulative=r['analysis'])
