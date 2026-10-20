"""Task-blocked question utility, over the existing fixed Seed learner.

Reuse question_selection for trajectories/variance, question_headroom for
counterfactual updates, nn.ridge for regression and the EXPERIMENTAL host.
The public selector sees no candidate answers or assessment outcomes.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import statistics as st
import sys
import time

from nexus.evolution1.catalogue import digest
from .grounded_audit import finite
from . import question_selection as qs
from . import question_headroom as hr
from . import query_replication as qr
from . import cumulative_learning as cum
from .update_diagnosis import paired

METHODS=['learned','action_mean','budget_mean','shuffled_residual','variance','uniform','keep']
FEATURES=['prediction','fit_disagreement','log_variance','anchor_distance','prefix_distance','pool_similarity',
    'anchor_error','prefix_error','prefix_residual','anchor_alignment','prefix_alignment','prefix_fraction']+[
    f'candidate_basis_{i}' for i in range(33)]+[f'action_{i}' for i in range(9)]


def config_check(c):
    expected=dict(schema='seed_question_utility_v1',tasks={'train':list(range(95000000,95110001,10000))},
        constant_seeds=[7201,7202,7203],budgets=[1,2,4,8],fold_count=4,methods=METHODS,
        feature_width=54,ridge=1.0,permutation_seed=8501,minimum_fraction=.05,
        minimum_task_wins=8,minimum_fold_wins=3,retention_excess=.01,max_wall_s=30,max_outer_updates=0)
    if any(digest(c.get(k))!=digest(v) for k,v in expected.items()):raise ValueError('locked_question_utility_recipe')
    if any(not finite(c[k]) or c[k]<0 for k in ('carried_used_s','carried_remaining_s')) or c['max_wall_s']>c['carried_remaining_s'] or abs(c['carried_used_s']+c['carried_remaining_s']-3600)>1e-8:raise ValueError('utility_session_budget')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=0)


def source_pack(root,c):
    config_check(c);root=Path(root)
    for key in ('parent','parent_validation'):
        if hashlib.sha256((root/c[key]).read_bytes()).hexdigest()!=c[key+'_sha256']:raise ValueError('utility_parent_hash: '+key)
    parent=json.loads((root/c['parent']).read_text());qr.verify_offline_receipt(root,parent,parent['config'])
    old=qr.source_pack(root,parent['config']);qr.validate(parent,parent['config'],old)
    if (parent['session_used_s'],parent['session_remaining_s'])!=(c['carried_used_s'],c['carried_remaining_s']):raise ValueError('utility_carried_parent')
    original=json.loads((root/'artifacts/seed_nonlinear_learning.json').read_text())
    hp=json.loads((root/'artifacts/seed_question_headroom.json').read_text());refs=hr.source_pack(root,hp['config'])['reference']
    tasks={str(t['seed']):dict(arrays={k:t['arrays'][k] for k in ('support_x','support_y','old_x','old_y')},
        actions=[r['action'] for r in t['records']['support']]) for t in original['tasks']['train']}
    pack=dict(parent_sha256=c['parent_sha256'],tasks=tasks,frozen_folds=old['frozen_folds'],reference=refs,
        training_queries={t:v['selection']['arrays'] for t,v in parent['queries'].items()},
        assessments={t:{b:dict(before={s:dict(check_mse=v['check_mse'],retention_mse=old['rows'][t][b]['before'][s]['retention_mse']) for s,v in cell['before'].items()},
            candidates={i:{s:dict(check_mse=v['check_mse'],retention_mse=old['rows'][t][b]['candidates'][i][s]['retention_mse']) for s,v in arms.items()} for i,arms in cell['candidates'].items()}) for b,cell in cells.items()} for t,cells in parent['rows'].items()})
    validate_pack(pack,c);return pack


def validate_pack(p,c):
    ids=set(map(str,c['tasks']['train']))
    if set(p)!={'parent_sha256','tasks','frozen_folds','reference','training_queries','assessments'} or p['parent_sha256']!=c['parent_sha256']:raise ValueError('utility_source_payload')
    if any(set(p[k])!=ids for k in ('tasks','reference','training_queries','assessments')) or set(p['frozen_folds'])!=set(map(str,range(4))):raise ValueError('utility_source_task_grid')
    for f in range(4):
        meta=p['frozen_folds'][str(f)]
        if (meta['train_ids'],meta['excluded_ids'])!=cum.partition(c,f):raise ValueError('utility_fold_isolation')
    for t in ids:
        a=p['tasks'][t]['arrays'];actions=p['tasks'][t]['actions']
        if set(a)!={'support_x','support_y','old_x','old_y'} or len(actions)!=8 or any(type(i) is not int or not 0<=i<9 for i in actions):raise ValueError('utility_source_schema')
        for key,n in [('support_x',8),('support_y',8),('old_x',4),('old_y',4)]:
            if len(a[key])!=n:raise ValueError('utility_source_array')
            values=[v for row in a[key] for v in row] if key.endswith('_x') else a[key]
            if key.endswith('_x') and any(len(x)!=33 for x in a[key]) or any(not finite(v) for v in values):raise ValueError('utility_source_array')
        q=p['training_queries'][t]
        if set(q)!={'x','y'} or len(q['x'])!=108 or len(q['y'])!=108 or any(len(x)!=33 or any(not finite(v) for v in x) for x in q['x']) or any(not finite(v) for v in q['y']):raise ValueError('utility_training_query_grid')
        if set(p['assessments'][t])!=set(map(str,c['budgets'])):raise ValueError('utility_assessment_budget_grid')
        for b,cell in p['assessments'][t].items():
            available={str(i) for i in range(8) if i not in p['reference'][t]['order'][:int(b)-1]}
            if set(cell)!={'before','candidates'} or set(cell['candidates'])!=available:raise ValueError('utility_assessment_candidate_grid')
            for arms in [cell['before']]+list(cell['candidates'].values()):
                if set(arms)!=set(map(str,c['constant_seeds'])):raise ValueError('utility_assessment_seed_grid')
                for values in arms.values():
                    if set(values)!={'check_mse','retention_mse'} or any(not finite(v) or v<0 for v in values.values()):raise ValueError('utility_assessment_metric_grid')
    return True


def features(pool,anchors,anchor_y,seen_indices,seen_y,thetas,variance,index,action):
    """Candidate inputs and observed evidence ONLY. No unrequested label."""
    if len(pool)!=8 or len(anchors)!=4 or len(anchor_y)!=4 or len(seen_indices)!=len(seen_y) or len(thetas)!=3 or type(index) is not int or index in seen_indices or type(action) is not int or not 0<=action<9:raise ValueError('public_question_state')
    dot=lambda a,b:sum(x*y for x,y in zip(a,b));norm=lambda x:math.sqrt(dot(x,x))
    cosine=lambda x,y:dot(x,y)/(norm(x)*norm(y)) if norm(x)*norm(y)>1e-12 else 0.
    x=pool[index];theta=[st.mean(v[j] for v in thetas) for j in range(33)]
    seen=[pool[i] for i in seen_indices];ae=[y-dot(v,theta) for v,y in zip(anchors,anchor_y)];se=[y-dot(v,theta) for v,y in zip(seen,seen_y)]
    gradient=lambda rows,errs:[st.mean(v[j]*e for v,e in zip(rows,errs)) for j in range(33)] if rows else [0.]*33
    dist=lambda rows:min(st.mean((a-b)**2 for a,b in zip(x,v)) for v in rows) if rows else 0.
    clip=lambda v:max(-1.,min(1.,v/4));mse=lambda v:st.mean(e*e for e in v) if v else 0.
    predictions=[dot(x,v) for v in thetas];mean=st.mean(predictions)
    values=[clip(mean),min(1.,st.mean((v-mean)**2 for v in predictions)**.5/4),math.log1p(variance)/10,
        min(1.,dist(anchors)),min(1.,dist(seen)),st.mean(cosine(x,v) for v in pool),
        min(1.,mse(ae)/4),min(1.,mse(se)/4),clip(st.mean(se) if se else 0.),
        cosine(x,gradient(anchors,ae)),cosine(x,gradient(seen,se)),len(seen)/8]+list(x)+[float(i==action) for i in range(9)]
    if len(values)!=54 or any(not finite(v) for v in values):raise ValueError('finite_question_features')
    return values


def public_cases(task,ref,c):
    """The only bridge from teaching data to pre-question inference."""
    import torch
    a=task['arrays'];pool=a['support_x'];out={}
    for b in c['budgets']:
        seen=ref['order'][:b-1];scores=qs.variance_scores(torch.tensor(pool),torch.tensor(a['old_x']),seen)
        previous=[ref['paths'][str(s)][b-1]['theta'] for s in c['constant_seeds']]
        out[str(b)]={str(i):dict(index=i,budget=b,action=task['actions'][i],variance=scores[i],
            features=features(pool,a['old_x'],a['old_y'],seen,[a['support_y'][j] for j in seen],previous,scores[i],i,task['actions'][i])) for i in range(8) if i not in seen}
    return out


def scale_task(task,scale):
    import torch
    a=copy.deepcopy(task['arrays'])
    for k in ('support_x','old_x'):a[k]=(torch.tensor(a[k])/torch.tensor(scale)).tolist()
    return dict(arrays=a,actions=list(task['actions']))


def training_inputs(pack,c,fold):
    """Exclude all held-task data, not just labels, from the fitter's API."""
    train,held=cum.partition(c,fold);meta=pack['frozen_folds'][str(fold)]
    if (meta['train_ids'],meta['excluded_ids'])!=(train,held):raise ValueError('utility_train_partition')
    return ({str(t):copy.deepcopy(pack['tasks'][str(t)]) for t in train},
        {str(t):copy.deepcopy(pack['training_queries'][str(t)]) for t in train},copy.deepcopy(meta))


def training_cases(tasks,queries,meta,c,check=lambda:None):
    """Common outer-fold learner: never another fold's target-contaminated fit."""
    import torch
    if set(tasks)!=set(map(str,meta['train_ids'])) or set(queries)!=set(tasks):raise ValueError('utility_training_ids')
    cases={};references={};all_fits={}
    qc=json.loads(json.dumps(c));qc['question_seeds']=[]
    for tid,raw in tasks.items():
        check();task=scale_task(raw,meta['scale']);a=task['arrays'];sx=torch.tensor(a['support_x']);ox=torch.tensor(a['old_x']);oy=torch.tensor(a['old_y'])
        order=qs.orders(sx,ox,int(tid),qc,check)['informative']['fixed']['indices'];paths={};gates={}
        for seed in c['constant_seeds']:
            s=str(seed);gates[s]=float((.5+.25*torch.tensor(meta['constants'][s]['weights']['logits.bias'][0])).clamp(0,1))
            paths[s]=qs.fit_path(sx,ox,oy,qs.LabelOracle(a['support_y'],8),order,gates[s],check)
        ref=dict(order=order,paths=paths);references[tid]=ref;cases[tid]=public_cases(task,ref,c);all_fits[tid]={}
        qx=torch.tensor(queries[tid]['x'])/torch.tensor(meta['scale']);qy=torch.tensor(queries[tid]['y'])
        error=lambda theta:float((qx@torch.tensor(theta)-qy).square().mean())
        for b in c['budgets']:
            seen=order[:b-1];before={s:error(paths[s][b-1]['theta']) for s in gates};all_fits[tid][str(b)]={}
            for i,row in cases[tid][str(b)].items():
                index=int(i);fits={}
                for s,g in gates.items():
                    check();fits[s]=hr.counterfactual(torch.tensor(paths[s][0]['theta']),torch.tensor(paths[s][b-1]['theta']),ox,oy,sx[seen],torch.tensor([a['support_y'][j] for j in seen]),sx[index],torch.tensor(a['support_y'][index]),g)
                    fits[s].update(query_before=before[s],query_after=error(fits[s]['theta']))
                all_fits[tid][str(b)][i]=fits
                row['utility']=st.mean(v['query_before']-v['query_after'] for v in fits.values())
    return cases,references,all_fits


def flatten(cases,ids):return [row for tid in ids for b in ('1','2','4','8') for _,row in sorted(cases[str(tid)][b].items(),key=lambda x:int(x[0]))]


def mean_prediction(model,row):
    return model['action_means'].get(str(row['budget'])+'/'+str(row['action']),model['budget_means'][str(row['budget'])])


def fit_models(cases,train,c,fold):
    """Small fixed ridge, no hyperparameter search or held-data argument."""
    import numpy as np
    from nexus.nn.ridge import fit_ridge
    if set(cases)!=set(map(str,train)):raise ValueError('fitter_training_only')
    rows=flatten(cases,train);budgets={str(b):st.mean(r['utility'] for r in rows if r['budget']==b) for b in c['budgets']}
    groups=sorted({str(r['budget'])+'/'+str(r['action']) for r in rows})
    table=dict(budget_means=budgets,action_means={k:st.mean(r['utility'] for r in rows if str(r['budget'])+'/'+str(r['action'])==k) for k in groups})
    x=np.array([r['features'] for r in rows]);center=x.mean(0);y=np.array([r['utility']-mean_prediction(table,r) for r in rows]);models={}
    permutation=list(range(len(rows)));rng=random.Random(c['permutation_seed']+fold)
    for b in c['budgets']:
        ids=[j for j,r in enumerate(rows) if r['budget']==b];donors=list(ids);rng.shuffle(donors)
        for j,k in zip(ids,donors):permutation[j]=k
    for name,labels in [('learned',y),('shuffled_residual',y[permutation])]:
        scale,beta=fit_ridge(x-center,labels,ridge=c['ridge'])
        models[name]=dict(center=center.tolist(),scale=scale.tolist(),beta=beta.tolist(),table=copy.deepcopy(table))
    models['action_mean']=table;models['budget_mean']=dict(means=budgets)
    return models,permutation


def predict(model,method,row):
    if method=='action_mean':return mean_prediction(model,row)
    if method=='budget_mean':return model['means'][str(row['budget'])]
    return mean_prediction(model['table'],row)+sum((v-mu)/s*b for v,mu,s,b in zip(row['features'],model['center'],model['scale'],model['beta']))


def choose(rows,predictions):
    """Pure choice; only public features and frozen source predictions."""
    if set(predictions)!=set(rows) or any(not finite(v) for v in predictions.values()):raise ValueError('complete_question_predictions')
    return int(max(rows,key=lambda i:(predictions[i],rows[i]['variance'],-int(i))))


def require_lock(path,lock):
    if not Path(path).is_file() or digest(json.loads(Path(path).read_text()))!=digest(lock):raise ValueError('persisted_question_lock')


def decide(held,models):
    result={}
    for t,cases in held.items():
        result[t]={}
        for b,rows in cases.items():
            predicted={m:{i:predict(models[m],m,row) for i,row in rows.items()} for m in ('learned','action_mean','budget_mean','shuffled_residual')}
            choices={m:choose(rows,p) for m,p in predicted.items()};choices['variance']=max((int(i) for i in rows),key=lambda i:(rows[str(i)]['variance'],-i))
            result[t][b]=dict(predictions=predicted,choices=choices)
    return result


def evaluate(decisions,assessments,c):
    cells={}
    for t,cases in decisions.items():
        cells[t]={}
        for b,decision in cases.items():
            predicted=decision['predictions'];choices=decision['choices'];indices=list(predicted['learned'])
            a=assessments[t][b];q={i:st.mean(v['check_mse'] for v in arms.values()) for i,arms in a['candidates'].items()};ret={i:st.mean(v['retention_mse'] for v in arms.values()) for i,arms in a['candidates'].items()}
            keep=st.mean(v['check_mse'] for v in a['before'].values());kr=st.mean(v['retention_mse'] for v in a['before'].values())
            errors={m:q[str(i)] for m,i in choices.items()};errors.update(uniform=st.mean(q.values()),keep=keep)
            retention={m:ret[str(i)] for m,i in choices.items()};retention.update(uniform=st.mean(ret.values()),keep=kr)
            actual={i:keep-v for i,v in q.items()}
            cells[t][b]=dict(predictions=predicted,choices=choices,query_mse=errors,retention_mse=retention,actual_utilities=actual,
                utility_prediction_mse={m:st.mean((p[i]-actual[i])**2 for i in indices) for m,p in predicted.items()},
                sign_accuracy={m:st.mean((p[i]>0)==(actual[i]>0) for i in indices) for m,p in predicted.items()},
                regret={m:errors[m]-min(q.values()) for m in METHODS if m!='keep'})
    return cells


def summarize(folds,c):
    by_task={t:cells for fold in folds.values() for t,cells in fold['evaluation'].items()}
    per={t:{m:st.mean(v['query_mse'][m] for v in cells.values()) for m in METHODS} for t,cells in by_task.items()}
    means={m:st.mean(v[m] for v in per.values()) for m in METHODS};ret={m:st.mean(v['retention_mse'][m] for cells in by_task.values() for v in cells.values()) for m in METHODS}
    contrasts={m:paired([per[str(t)][m]-per[str(t)]['learned'] for t in c['tasks']['train']]) for m in METHODS[1:]}
    per_fold={f:{m:st.mean(per[t][m] for t in fold['evaluation']) for m in METHODS} for f,fold in folds.items()}
    wins=sum(v['learned']<v['keep'] for v in per.values());fwins=sum(v['learned']<v['action_mean'] for v in per_fold.values())
    practical=all(means['learned']<=(1-c['minimum_fraction'])*means[m] for m in ('action_mean','variance','uniform','keep'))
    intervals=all(contrasts[m]['ci95'][0]>0 for m in ('action_mean','variance','keep'))
    retained=ret['learned']<=ret['variance']+c['retention_excess'];shuffle=means['learned']<means['shuffled_residual']
    passed=practical and intervals and retained and shuffle and wins>=c['minimum_task_wins'] and fwins>=c['minimum_fold_wins']
    return dict(label='source_question_learning_supported' if passed else 'source_question_learning_not_demonstrated',source_screen_pass=passed,
        practical_pass=practical,interval_pass=intervals,retention_pass=retained,shuffle_pass=shuffle,task_wins=wins,fold_wins=fwins,
        curve_means=means,contrasts=contrasts,retention_means=ret,per_task=per,per_fold=per_fold,
        query_curves={m:{str(b):st.mean(by_task[str(t)][str(b)]['query_mse'][m] for t in c['tasks']['train']) for b in c['budgets']} for m in METHODS},
        utility_mse={m:st.mean(v['utility_prediction_mse'][m] for cells in by_task.values() for v in cells.values()) for m in ('learned','action_mean','budget_mean','shuffled_residual')},
        sign_accuracy={m:st.mean(v['sign_accuracy'][m] for cells in by_task.values() for v in cells.values()) for m in ('learned','action_mean','budget_mean','shuffled_residual')},
        uncertainty='Exploratory paired df11 source-task intervals, overlapping folds, one frozen core. Previously inspected check rows are source development, not confirmation.',
        independent_pretrained_cores=1,fresh_validation=False,runtime_promotion=False,learning_to_learn_established=False)


def resources(cpu_s):
    return dict(updates=0,real_steps=0,imagined_transitions=0,world_model_forwards=0,cpu_s=cpu_s,
        training_initial_solves=108,training_reference_updates=864,training_counterfactual_updates=2268,
        cumulative_solves=3132,variance_solves=480,reference_variance_scores=2304,public_candidate_scores=1008,
        predictor_ridge_solves=8,predictor_training_rows=1512,predictor_augmented_rows=3024,
        predictor_coefficients=432,training_case_count=756,held_case_count=252,
        training_query_row_scores=291600,cached_assessment_states=900,normalization_fit_rows=0,
        predictor_center_rows=756,predictor_rms_rows=1512)


def validate(r,c,p):
    """Stdlib normal-equation and exact planned-grid audit; never fits."""
    config_check(c);validate_pack(p,c);dot=lambda a,b:sum(x*y for x,y in zip(a,b))
    close=lambda a,b:finite(a) and finite(b) and abs(a-b)<=2e-6
    frozen=digest(p)
    if r['config']!=c or r['source_pack_sha256']!=frozen or r['frozen_before_sha256']!=frozen or r['frozen_after_sha256']!=frozen or r['feature_names']!=FEATURES or set(r['folds'])!=set(map(str,range(4))):raise ValueError('utility_frozen_grid')
    for f in range(4):
        entry=r['folds'][str(f)];train,held=cum.partition(c,f);meta=p['frozen_folds'][str(f)];scale=meta['scale']
        if entry['train_ids']!=train or entry['excluded_ids']!=held or any(set(entry[k])!=set(map(str,train)) for k in ('training_cases','training_references','training_fits')) or set(entry['held_cases'])!=set(map(str,held)):raise ValueError('utility_fold_grid')
        for tid in map(str,train+held):
            a=p['tasks'][tid]['arrays'];sx=[[v/s for v,s in zip(x,scale)] for x in a['support_x']];ox=[[v/s for v,s in zip(x,scale)] for x in a['old_x']]
            ref=entry['training_references'][tid] if int(tid) in train else p['reference'][tid]
            cases=entry['training_cases'][tid] if int(tid) in train else entry['held_cases'][tid]
            if sorted(ref['order'])!=list(range(8)) or any(type(i) is not int for i in ref['order']) or set(ref['paths'])!=set(map(str,c['constant_seeds'])) or set(cases)!=set(map(str,c['budgets'])):raise ValueError('utility_reference_grid')
            for s,path in ref['paths'].items():
                if len(path)!=9 or [v['prefix'] for v in path]!=list(range(9)):raise ValueError('utility_trajectory_grid')
                for n,row in enumerate(path):
                    theta=row['theta'];proposal=row['proposal'];seen=ref['order'][:n]
                    if type(row['prefix']) is not int or len(theta)!=33 or any(not finite(v) for v in theta) or row['index']!=(seen[-1] if n else None):raise ValueError('utility_reference_theta')
                    z=proposal if n else theta;bx=ox+[sx[i] for i in seen];by=a['old_y']+[a['support_y'][i] for i in seen];base=path[0]['theta'] if n else [0.]*33;ridge=.1 if n else .01
                    residual=[y-dot(x,z) for x,y in zip(bx,by)]
                    if max(abs(ridge*(v-w)-sum(x[j]*e for x,e in zip(bx,residual))) for j,(v,w) in enumerate(zip(z,base)))>2e-5:raise ValueError('utility_reference_equation')
                    if n:
                        # Float32 implementation versus scalar replay tolerance.
                        g=max(0.,min(1.,.5+.25*meta['constants'][s]['weights']['logits.bias'][0]));before=path[n-1]['theta']
                        if any(not close(v,w+g*(q-w)) for v,w,q in zip(theta,before,proposal)):raise ValueError('utility_reference_damping')
            for b in c['budgets']:
                seen=ref['order'][:b-1];available=[i for i in range(8) if i not in seen];rows=cases[str(b)]
                if set(rows)!=set(map(str,available)):raise ValueError('utility_candidate_grid')
                if any(not finite(row.get('variance')) or row['variance']<0 for row in rows.values()):raise ValueError('utility_variance_numeric')
                if max(available,key=lambda i:(rows[str(i)]['variance'],-i))!=ref['order'][b-1]:raise ValueError('utility_variance_choice_reproduction')
                if int(tid) in train and set(entry['training_fits'][tid].get(str(b),{}))!=set(rows):raise ValueError('utility_training_fit_grid')
                for i,row in rows.items():
                    index=int(i);expected_fields={'index','budget','action','variance','features'}|({'utility'} if int(tid) in train else set())
                    if set(row)!=expected_fields or type(row['index']) is not int or row['index']!=index or type(row['budget']) is not int or row['budget']!=b or type(row['action']) is not int or row['action']!=p['tasks'][tid]['actions'][index] or not finite(row['variance']) or row['variance']<0 or len(row['features'])!=54:raise ValueError('utility_public_case_schema')
                    phi=features(sx,ox,a['old_y'],seen,[a['support_y'][i] for i in seen],[ref['paths'][str(s)][b-1]['theta'] for s in c['constant_seeds']],row['variance'],index,row['action'])
                    if any(not close(v,w) for v,w in zip(row['features'],phi)):raise ValueError('utility_public_feature_arithmetic')
                    if int(tid) not in train:continue
                    fits=entry['training_fits'][tid][str(b)][i]
                    if set(fits)!=set(map(str,c['constant_seeds'])):raise ValueError('utility_damping_seed_grid')
                    q=p['training_queries'][tid];qx=[[v/s for v,s in zip(x,scale)] for x in q['x']]
                    error=lambda theta:st.mean((dot(x,theta)-y)**2 for x,y in zip(qx,q['y']))
                    for s,fit in fits.items():
                        if set(fit)!={'theta','proposal','support_error_before','support_error_after','query_before','query_after'} or any(len(fit[k])!=33 or any(not finite(v) for v in fit[k]) for k in ('theta','proposal')):raise ValueError('utility_training_snapshot_grid')
                        prev=ref['paths'][s][b-1]['theta'];base=ref['paths'][s][0]['theta'];bx=ox+[sx[j] for j in seen+[index]];by=a['old_y']+[a['support_y'][j] for j in seen+[index]]
                        for name,theta in [('before',prev),('after',fit['theta'])]:
                            if not close(fit['support_error_'+name],(a['support_y'][index]-dot(sx[index],theta))**2):raise ValueError('utility_support_error')
                        residual=[y-dot(x,fit['proposal']) for x,y in zip(bx,by)]
                        if max(abs(.1*(v-z)-sum(x[j]*e for x,e in zip(bx,residual))) for j,(v,z) in enumerate(zip(fit['proposal'],base)))>2e-5:raise ValueError('utility_counterfactual_equation')
                        g=max(0.,min(1.,.5+.25*meta['constants'][s]['weights']['logits.bias'][0]))
                        if any(not close(v,z+g*(q-z)) for v,z,q in zip(fit['theta'],prev,fit['proposal'])):raise ValueError('utility_counterfactual_damping')
                        if not close(fit['query_before'],error(prev)) or not close(fit['query_after'],error(fit['theta'])):raise ValueError('utility_training_label_arithmetic')
                    if not close(row['utility'],st.mean(v['query_before']-v['query_after'] for v in fits.values())):raise ValueError('utility_target')
        rows=flatten(entry['training_cases'],train);models=entry['models']
        if set(models)!={'learned','action_mean','budget_mean','shuffled_residual'}:raise ValueError('utility_model_grid')
        table=models['action_mean'];budgets={str(b):st.mean(r['utility'] for r in rows if r['budget']==b) for b in c['budgets']}
        groups={str(row['budget'])+'/'+str(row['action']) for row in rows}
        if set(table)!={'budget_means','action_means'} or table['budget_means']!=budgets or set(table['action_means'])!=groups or models['budget_mean']!={'means':budgets}:raise ValueError('utility_mean_model')
        for k,v in table['action_means'].items():
            if not close(v,st.mean(r['utility'] for r in rows if str(r['budget'])+'/'+str(r['action'])==k)):raise ValueError('utility_action_mean')
        permutation=list(range(len(rows)));rng=random.Random(c['permutation_seed']+f)
        for b in c['budgets']:
            ids=[j for j,row in enumerate(rows) if row['budget']==b];donors=list(ids);rng.shuffle(donors)
            for j,k in zip(ids,donors):permutation[j]=k
        if entry['permutation']!=permutation:raise ValueError('utility_shuffle_schedule')
        xx=[row['features'] for row in rows];center=[st.mean(x[j] for x in xx) for j in range(54)];sc=[st.mean((x[j]-center[j])**2 for x in xx)**.5 for j in range(54)];sc=[s if s>=1e-8 else 1. for s in sc]
        y=[row['utility']-mean_prediction(table,row) for row in rows]
        for name in ('learned','shuffled_residual'):
            m=models[name]
            if set(m)!={'center','scale','beta','table'} or m['table']!=table or any(len(m[k])!=54 for k in ('center','scale','beta')) or any(not finite(v) for k in ('center','scale','beta') for v in m[k]) or any(not close(v,w) for v,w in zip(m['center'],center)) or any(not close(v,w) for v,w in zip(m['scale'],sc)):raise ValueError('utility_predictor_scaling')
            z=[[(v-mu)/s for v,mu,s in zip(x,center,sc)] for x in xx];target=[y[j] for j in permutation] if name=='shuffled_residual' else y
            residual=[dot(x,m['beta'])-v for x,v in zip(z,target)]
            if max(abs(2*sum(x[j]*v for x,v in zip(z,residual))+c['ridge']*b) for j,b in enumerate(m['beta']))>1e-7:raise ValueError('utility_predictor_equation')
        expected=decide(entry['held_cases'],models)
        if digest(expected)!=digest(entry['decisions']) or digest(entry['evaluation'])!=digest(evaluate(expected,p['assessments'],c)):raise ValueError('utility_decision_evaluation_grid')
        if entry['models_sha256']!=digest(models):raise ValueError('utility_model_fingerprint')
    lock=dict(config_sha256=digest(c),source_pack_sha256=digest(p),models={f:v['models_sha256'] for f,v in r['folds'].items()},decisions={f:v['decisions'] for f,v in r['folds'].items()})
    if r['lock']!=lock or r['lock_sha256']!=digest(lock) or r['locked_before_evaluation'] is not True:raise ValueError('utility_saved_lock')
    if digest(r['analysis'])!=digest(summarize(r['folds'],c)):raise ValueError('utility_summary_arithmetic')
    return True


def run(request):
    import torch
    from . import learning_benchmark as lb
    c=request['inputs']['study_config'];p=request['inputs']['source_pack'];config_check(c);validate_pack(p,c)
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True);lb.WORK.clear();start=time.monotonic()
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('question_utility_wall_cap')
    frozen=digest(p);r=dict(config=c,source_pack_sha256=frozen,frozen_before_sha256=frozen,feature_names=FEATURES,declared_complete=False,folds={},timing_s=dict(training=0.,prediction=0.,assessment=0.))
    def progress():
        r.update(wall_s=time.monotonic()-start,update_work=dict(lb.WORK));path=Path('progress.tmp');path.write_text(json.dumps(r,allow_nan=False));path.replace('progress.json')
    progress()
    try:
        for f in range(4):
            check();tick=time.monotonic();tasks,queries,meta=training_inputs(p,c,f)
            cases,refs,fits=training_cases(tasks,queries,meta,c,check);models,permutation=fit_models(cases,meta['train_ids'],c,f)
            r['timing_s']['training']+=time.monotonic()-tick;tick=time.monotonic()
            held={str(t):public_cases(scale_task(p['tasks'][str(t)],meta['scale']),p['reference'][str(t)],c) for t in meta['excluded_ids']}
            entry=dict(train_ids=meta['train_ids'],excluded_ids=meta['excluded_ids'],training_cases=cases,training_references=refs,training_fits=fits,models=models,permutation=permutation,
                held_cases=held,models_sha256=digest(models),decisions=decide(held,models));r['folds'][str(f)]=entry
            r['timing_s']['prediction']+=time.monotonic()-tick;progress()
        lock=dict(config_sha256=digest(c),source_pack_sha256=digest(p),models={f:v['models_sha256'] for f,v in r['folds'].items()},decisions={f:v['decisions'] for f,v in r['folds'].items()})
        path=Path('question-models-locked.json');path.write_text(json.dumps(lock,allow_nan=False))
        require_lock(path,lock)
        r.update(lock=lock,lock_sha256=digest(lock),locked_before_evaluation=True);progress();tick=time.monotonic()
        for entry in r['folds'].values():entry['evaluation']=evaluate(entry['decisions'],p['assessments'],c)
        r['analysis']=summarize(r['folds'],c);r['timing_s']['assessment']=time.monotonic()-tick;r['frozen_after_sha256']=digest(p)
        validate(r,c,p);check();r['declared_complete']=True;progress()
    except Exception as exc:
        import traceback
        r.update(failure=repr(exc),traceback=traceback.format_exc());progress();raise
    return dict(adapter='seed_question_utility_v1',study=r,resources=resources(time.process_time()),curve=[],
        model=dict(schema='seed_question_utility_models_v1',folds={f:v['models'] for f,v in r['folds'].items()}),
        metrics=dict(mse=r['analysis']['curve_means']['learned'],baseline_mse=r['analysis']['curve_means']['action_mean']),
        runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1))


def validate_output(output,c,caps,p):
    r=output['study'];validate(r,c,p);expected=resources(0);work=output['resources']
    if output['adapter']!='seed_question_utility_v1' or r['declared_complete'] is not True or output['model']!=dict(schema='seed_question_utility_models_v1',folds={f:v['models'] for f,v in r['folds'].items()}):raise ValueError('utility_output_schema')
    if set(work)!=set(expected) or any(type(work[k]) is not int or work[k]!=v for k,v in expected.items() if k!='cpu_s'):raise ValueError('utility_output_resources')
    if not finite(work['cpu_s']) or not 0<=work['cpu_s']<=caps['cpu_s'] or r['update_work']!={'old_anchor_initial_solves':108,'cumulative_solves':3132}:raise ValueError('utility_actual_work')
    return True


def saved_replay(root):
    c=json.loads((root/'configs/seed_question_utility.json').read_text());r=json.loads((root/'artifacts/seed_question_utility.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_question_utility_evidence')
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_question_utility',status=h['status'],failure=h['failure'],wall_s=h['wall_s'],memory_mb=h['peak_sampled_rss_mb'],revision=r['execution_sha'],
        metrics=dict(mse=r['analysis']['curve_means']['learned'],baseline_mse=r['analysis']['curve_means']['action_mean']),curve=[],resources=r['resources'],model_sha256=r['lock_sha256'],question_utility=r['analysis'])
