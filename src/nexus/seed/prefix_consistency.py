"""Source-only counterfactual update-utility feature audit, not a live learner.

Uses cumulative posterior/folds, the existing numeric ridge primitive and the
EXPERIMENTAL host. Reference trajectories never use query feedback.
"""
import hashlib
import json
import math
from pathlib import Path
import random
import statistics as st
import sys
import time
from types import SimpleNamespace

from nexus.evolution1.catalogue import digest
from .grounded_audit import finite
from . import cumulative_learning as cum
from . import update_diagnosis as prior

METHODS=['constant','prefix_mean','current','current_prefix','consistency','full','permuted_full']
COLUMNS={'current':list(range(4)),'current_prefix':list(range(4))+[9],
         'consistency':list(range(4,10)),'full':list(range(10)),'permuted_full':list(range(10))}
FEATURES=['residual','anchor_count','novelty','channel','prior_prefix_error','prior_prefix_gain',
          'prior_conflict_fraction','gradient_agreement','anchor_damage','prefix_fraction']


def config_check(c):
    if (c['schema']!='seed_prefix_consistency_v1' or c['methods']!=METHODS or c['prefixes']!=list(range(1,9)) or
        c['tasks']!={'train':list(range(95000000,95110001,10000))}):raise ValueError('locked_prefix_audit_grid')
    for k,v in dict(fold_count=4,posterior_ridge=.1,predictor_ridge=1.,permutation_seed=7301,
                    minimum_fraction=.05,minimum_fold_wins=3,max_wall_s=30,max_outer_updates=0).items():
        if type(c[k]) not in (int,float) or c[k]!=v:raise ValueError('locked_prefix_audit_recipe')
    if c['max_wall_s']>c['carried_remaining_s'] or abs(c['carried_used_s']+c['carried_remaining_s']-3600)>1e-8:raise ValueError('carried_budget')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=0)


def source_pack(root,c):
    config_check(c);raw=(root/c['source_plan']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=c['source_plan_sha256']:raise ValueError('source_plan_hash')
    return dict(tasks=prior.source_pack(root,json.loads(raw))['tasks'])


def features(previous,proposal,x,y,old_x,old_y,seen_x,seen_y):
    """Observed data only. Also used by the stdlib saved-result auditor."""
    dot=lambda a,b:sum(v*w for v,w in zip(a,b))
    n=len(seen_y);residual=[v-dot(row,previous) for row,v in zip(seen_x[:-1],seen_y[:-1])]
    after=[v-dot(row,proposal) for row,v in zip(seen_x[:-1],seen_y[:-1])]
    mse=lambda a:st.mean(v*v for v in a) if a else 0.
    current=[min(4,abs(y-dot(x,previous)))/4,len(old_x)/16,
             min(1,min(st.mean((a-b)**2 for a,b in zip(row,x)) for row in old_x)),0.]
    a=[(y-dot(x,previous))*v for v in x]
    b=[st.mean(e*row[j] for e,row in zip(residual,seen_x[:-1])) for j in range(len(x))] if residual else [0.]*len(x)
    norm=math.sqrt(dot(a,a)*dot(b,b));agreement=dot(a,b)/norm if norm>1e-12 else 0.
    damage=st.mean((v-dot(row,proposal))**2-(v-dot(row,previous))**2 for row,v in zip(old_x,old_y))
    clip=lambda v:max(-1,min(1,v/4))
    return current+[min(1,mse(residual)/4),clip(mse(residual)-mse(after)),
        st.mean(v*v>e*e for v,e in zip(after,residual)) if residual else 0.,
        max(-1,min(1,agreement)),clip(damage),n/8]


def support_trace(support_x,support_y,old_x,old_y,check=lambda:None):
    """No query argument, evaluator or file access; returns a fixed reference."""
    import torch
    from . import learning_benchmark as lb
    initial=lb.initial(SimpleNamespace(old_x=old_x,old_y=old_y)).detach();previous=initial;rows=[]
    for p in range(1,len(support_y)+1):
        check();proposal=cum.posterior(initial,torch.cat((old_x,support_x[:p])),torch.cat((old_y,support_y[:p])),torch.ones_like(initial))
        before=previous.tolist();after=proposal.tolist()
        phi=features(before,after,support_x[p-1].tolist(),float(support_y[p-1]),old_x.tolist(),old_y.tolist(),support_x[:p].tolist(),support_y[:p].tolist())
        rows.append(dict(prefix=p,before=before,proposal=after,features=phi));previous=proposal
    return rows


def label_trace(trace,task):
    """Evaluator-only scoring after feature construction; never fits a policy."""
    dot=lambda x,t:sum(a*b for a,b in zip(x,t))
    for row in trace:
        for role in ('query','retention'):
            x=getattr(task,role+'_x').tolist();y=getattr(task,role+'_y').tolist()
            for name in ('before','proposal'):row[role+'_'+name]=st.mean((v-dot(a,row[name]))**2 for a,v in zip(x,y))
        row['utility']=row['query_before']-row['query_proposal']
    return trace


def permute_ids(train,c,fold):
    shift=random.Random(c['permutation_seed']+fold).randrange(1,len(train))
    return train[shift:]+train[:shift]


def training_rows(cases,ids):return [row for t in ids for row in cases[str(t)]]


def fit_predictors(cases,train,c,fold):
    """Receives only permitted training cases, never an excluded query table."""
    import numpy as np
    from nexus.nn.ridge import fit_ridge
    rows=training_rows(cases,train);y=np.asarray([r['utility'] for r in rows]);mean=float(y.mean())
    models={'constant':dict(mean=mean),'prefix_mean':dict(means=[st.mean(r['utility'] for r in rows if r['prefix']==p) for p in c['prefixes']])}
    permutation=permute_ids(train,c,fold)
    for method,cols in COLUMNS.items():
        source=training_rows(cases,permutation) if method=='permuted_full' else rows
        x=np.asarray([[r['features'][j] for j in cols] for r in source]);center=x.mean(0)
        scale,beta=fit_ridge(x-center,y-mean,ridge=c['predictor_ridge'])
        models[method]=dict(columns=cols,center=center.tolist(),mean=mean,scale=scale.tolist(),beta=beta.tolist())
    return models


def predict(model,method,row):
    if method=='constant':return model['mean']
    if method=='prefix_mean':return model['means'][row['prefix']-1]
    return model['mean']+sum((row['features'][j]-mu)/s*b for j,mu,s,b in zip(model['columns'],model['center'],model['scale'],model['beta']))


def summarize(folds,c):
    task_metrics={};per_fold={}
    for f in folds.values():
        per_fold[str(f['fold'])]={}
        for t in f['excluded_ids']:
            rows=f['cases'][str(t)];task_metrics[str(t)]={}
            for m in METHODS:
                errs=[(r['predictions'][m]-r['utility'])**2 for r in rows]
                regrets=[max(0,r['utility'])-(r['utility'] if r['predictions'][m]>0 else 0) for r in rows]
                task_metrics[str(t)][m]=dict(mse=st.mean(errs),sign_accuracy=st.mean((r['predictions'][m]>0)==(r['utility']>0) for r in rows),
                    regret=st.mean(regrets),selected_gain=st.mean(r['utility'] if r['predictions'][m]>0 else 0 for r in rows))
        for m in METHODS:per_fold[str(f['fold'])][m]=st.mean(task_metrics[str(t)][m]['mse'] for t in f['excluded_ids'])
    means={m:{k:st.mean(v[m][k] for v in task_metrics.values()) for k in ('mse','sign_accuracy','regret','selected_gain')} for m in METHODS}
    wins=sum(v['full']<v['current_prefix'] for v in per_fold.values())
    signal=(all(means['full']['mse']<=(1-c['minimum_fraction'])*means[m]['mse'] for m in ('constant','prefix_mean','current_prefix')) and
        means['full']['mse']<means['permuted_full']['mse'] and wins>=c['minimum_fold_wins'] and means['full']['regret']<=means['constant']['regret'])
    return dict(metrics=means,per_fold_mse=per_fold,per_task=task_metrics,fold_wins=wins,signal_screen_pass=signal,
        contrasts={m:prior.paired([v[m]['mse']-v['full']['mse'] for v in task_metrics.values()]) for m in METHODS if m!='full'},
        fresh_validation=False,runtime_promotion=False,independent_pretrained_cores=1,
        uncertainty='Exploratory task-cluster intervals conditional on fixed out-of-fold fits; overlapping training folds and reused source data limit inference.',
        trajectory_interpretation='One-step counterfactual utilities at fixed reference states, not realized adaptive learning curves or episode returns.')


def validate(r,c,pack):
    config_check(c)
    if r['config']!=c or r['source_pack_sha256']!=digest(pack) or r['feature_names']!=FEATURES or set(r['folds'])!=set(map(str,range(4))):raise ValueError('complete_source_fold_grid')
    lookup={v['seed']:v['arrays'] for v in pack['tasks']}
    close=lambda a,b:finite(a) and finite(b) and abs(a-b)<2e-6
    dot=lambda a,b:sum(v*w for v,w in zip(a,b))
    for i in range(4):
        f=r['folds'][str(i)];train,held=cum.partition(c,i)
        if type(f['fold']) is not int or f['fold']!=i or f['train_ids']!=train or f['excluded_ids']!=held or set(f['cases'])!=set(map(str,train+held)) or set(f['models'])!=set(METHODS):raise ValueError('complete_case_model_grid')
        if f['source_sha256']!=digest([t for t in pack['tasks'] if t['seed'] in train]):raise ValueError('source_fit_hash')
        scale=f['scale'];raw_features=[x for t in train for k in ('support_x','old_x') for x in lookup[t][k]]
        expected=[max(.01,st.mean(row[j]**2 for row in raw_features)**.5)*33**.5 for j in range(33)]
        if len(scale)!=33 or any(not close(a,b) for a,b in zip(scale,expected)):raise ValueError('training_only_scale')
        for t in train+held:
            rows=f['cases'][str(t)];a=lookup[t]
            if [v['prefix'] for v in rows]!=c['prefixes'] or any(type(v['prefix']) is not int for v in rows):raise ValueError('complete_prefix_grid')
            sx=[[x/s for x,s in zip(row,scale)] for row in a['support_x']];ox=[[x/s for x,s in zip(row,scale)] for row in a['old_x']]
            initial=rows[0]['before']
            for p,row in enumerate(rows,1):
                if any(len(row[k])!=33 or any(not finite(v) for v in row[k]) for k in ('before','proposal')) or len(row['features'])!=10:raise ValueError('finite_state_feature_grid')
                if p>1 and row['before']!=rows[p-2]['proposal']:raise ValueError('fixed_reference_trajectory')
                for theta,bx,by,ridge,center in ((initial,ox,a['old_y'],.01,[0.]*33),(row['proposal'],ox+sx[:p],a['old_y']+a['support_y'][:p],.1,initial)):
                    residual=[y-dot(x,theta) for x,y in zip(bx,by)]
                    if max(abs(ridge*(v-b)-sum(x[j]*e for x,e in zip(bx,residual))) for j,(v,b) in enumerate(zip(theta,center)))>2e-5:raise ValueError('posterior_normal_equation')
                phi=features(row['before'],row['proposal'],sx[p-1],a['support_y'][p-1],ox,a['old_y'],sx[:p],a['support_y'][:p])
                if any(not close(u,v) for u,v in zip(phi,row['features'])):raise ValueError('support_only_feature_arithmetic')
                for role in ('query','retention'):
                    for name in ('before','proposal'):
                        err=st.mean((y-sum(v*w/s for v,w,s in zip(x,row[name],scale)))**2 for x,y in zip(a[role+'_x'],a[role+'_y']))
                        if not close(row[role+'_'+name],err):raise ValueError('utility_score_arithmetic')
                if not close(row['utility'],row['query_before']-row['query_proposal']):raise ValueError('utility_label')
                if t in held:
                    if set(row['predictions'])!=set(METHODS) or any(not close(row['predictions'][m],predict(f['models'][m],m,row)) for m in METHODS):raise ValueError('prediction_grid_arithmetic')
                elif 'predictions' in row:raise ValueError('training_case_scoring_unplanned')
        training=training_rows(f['cases'],train);y=[v['utility'] for v in training];mean=st.mean(y)
        if f['permutation']!=permute_ids(train,c,i):raise ValueError('training_permutation')
        if not close(f['models']['constant']['mean'],mean):raise ValueError('training_mean')
        pm=f['models']['prefix_mean']['means']
        if len(pm)!=8 or any(not close(pm[p-1],st.mean(v['utility'] for v in training if v['prefix']==p)) for p in c['prefixes']):raise ValueError('training_prefix_means')
        for method,cols in COLUMNS.items():
            m=f['models'][method];source=training_rows(f['cases'],f['permutation']) if method=='permuted_full' else training
            xx=[[v['features'][j] for j in cols] for v in source];center=[st.mean(row[j] for row in xx) for j in range(len(cols))]
            if m['columns']!=cols or any(len(m[k])!=len(cols) for k in ('center','scale','beta')) or not close(m['mean'],mean):raise ValueError('predictor_model_grid')
            rms=[st.mean((row[j]-center[j])**2 for row in xx)**.5 for j in range(len(cols))];sc=[v if v>=1e-8 else 1. for v in rms]
            if any(not close(u,v) for u,v in zip(center,m['center'])) or any(not close(u,v) for u,v in zip(sc,m['scale'])) or any(not finite(v) for v in m['beta']):raise ValueError('training_only_predictor_normalization')
            z=[[(v-mu)/s for v,mu,s in zip(row,center,sc)] for row in xx]
            error=[dot(row,m['beta'])-(label-mean) for row,label in zip(z,y)]
            if max(abs(2*sum(row[j]*e for row,e in zip(z,error))+c['predictor_ridge']*b) for j,b in enumerate(m['beta']))>1e-7:raise ValueError('ridge_normal_equation')
        if f['models_sha256']!=digest(f['models']):raise ValueError('immutable_predictor_hash')
    if r['analysis']!=summarize(r['folds'],c):raise ValueError('feature_summary_arithmetic')
    return True


def resources(cpu_s):
    return dict(updates=0,real_steps=0,imagined_transitions=0,world_model_forwards=0,
        reference_initial_solves=48,reference_posterior_solves=384,predictor_ridge_solves=20,predictor_fits=28,
        feature_rows=384,training_cases_presented=2016,augmented_ridge_rows=2880,
        held_prediction_cases=672,query_score_rows=20736,retention_score_rows=20736,cpu_s=cpu_s)


def run(request):
    import torch
    import numpy as np
    from . import learning_benchmark as lb
    c=request['inputs']['study_config'];config_check(c);pack=request['inputs']['source_pack'];torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True);lb.WORK.clear();start=time.monotonic()
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('prefix_audit_wall_cap')
    r=dict(config=c,source_pack_sha256=digest(pack),feature_names=FEATURES,declared_complete=False,folds={})
    def progress():
        r.update(wall_s=time.monotonic()-start,update_work=dict(lb.WORK));p=Path('progress.tmp');p.write_text(json.dumps(r,allow_nan=False));p.replace('progress.json')
    progress()
    for i in range(4):
        train_tasks,held,meta=cum.prepare_fold(pack,c,i,include_bound=False);train,excluded=cum.partition(c,i)
        cases={str(t):label_trace(support_trace(task.support_x,task.support_y,task.old_x,task.old_y,check),task) for t,task in zip(train,train_tasks)}
        check();models=fit_predictors(cases,train,c,i)
        for t,task in held.items():
            cases[str(t)]=label_trace(support_trace(task.support_x,task.support_y,task.old_x,task.old_y,check),task)
            for row in cases[str(t)]:row['predictions']={m:predict(models[m],m,row) for m in METHODS}
        r['folds'][str(i)]=dict(fold=i,train_ids=train,excluded_ids=excluded,scale=meta['scale'],source_sha256=meta['source_sha256'],
            cases=cases,models=models,models_sha256=digest(models),permutation=permute_ids(train,c,i))
        progress()
    r['analysis']=summarize(r['folds'],c);validate(r,c,pack);r['declared_complete']=True;progress();a=r['analysis']
    return dict(adapter='seed_prefix_consistency_v1',study=r,curve=[],model=dict(schema='prefix_utility_ridge_v1',folds={k:v['models'] for k,v in r['folds'].items()}),
        metrics=dict(mse=a['metrics']['full']['mse'],baseline_mse=a['metrics']['constant']['mse'],worst_error_increase=0.),
        resources=resources(time.process_time()),runtime=dict(python=sys.version,torch=torch.__version__,numpy=np.__version__,device='cpu',threads=1))


def validate_output(output,c,caps,pack):
    r=output['study'];validate(r,c,pack);w=output['resources'];expected=resources(0)
    if output['adapter']!='seed_prefix_consistency_v1' or r['declared_complete'] is not True:raise ValueError('incomplete_prefix_audit')
    if output['model']!=dict(schema='prefix_utility_ridge_v1',folds={k:v['models'] for k,v in r['folds'].items()}):raise ValueError('predictor_export')
    if set(w)!=set(expected) or any(type(w[k]) is not int or w[k]!=v for k,v in expected.items() if k!='cpu_s'):raise ValueError('prefix_audit_resources')
    if not finite(w['cpu_s']) or not 0<=w['cpu_s']<=caps['cpu_s'] or w['updates']>caps['updates']:raise ValueError('prefix_audit_caps')
    if r['update_work']!={'old_anchor_initial_solves':48,'cumulative_solves':384}:raise ValueError('actual_reference_work')
    return True


def saved_replay(root):
    c=json.loads((root/'configs/seed_prefix_consistency.json').read_text());r=json.loads((root/'artifacts/seed_prefix_consistency.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_prefix_audit')
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_feature_audit',status=h['status'],failure=h['failure'],wall_s=h['wall_s'],
        memory_mb=h['peak_sampled_rss_mb'],revision=r['execution_sha'],metrics=None,curve=[],resources=r['resources'],
        model_sha256=digest({k:v['models'] for k,v in r['folds'].items()}),study=None,prefix_consistency=r['analysis'])
