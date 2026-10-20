"""Ten-scalar pre-answer selector; reuse the fixed learner and trusted host.

This is an offline source-development adapter, never a live question policy.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import statistics as st
import sys
import time
from nexus.evolution1.catalogue import digest
from .grounded_audit import finite
from . import question_utility as base
from . import question_selection as qs
from .update_diagnosis import paired

FEATURES=['prediction','fit_disagreement','log_variance','anchor_distance',
          'prefix_distance','anchor_mse','prefix_mse','prefix_residual',
          'anchor_alignment','remaining_fraction']
METHODS=['learned','variance','uniform','original_order','keep','source_mean','oracle']
SCHEMA='seed_answer_free_utility_v1'


def config_check(c):
    expected=dict(schema=SCHEMA,starting_revision='1a6167073321d2a7241227ded4627599a63b4386',
        tasks={'train':list(range(95000000,95110001,10000))},constant_seeds=[7201,7202,7203],
        budgets=[1,2,4,8],primary_budgets=[1,2,4],fold_count=4,feature_names=FEATURES,
        ridge=1.0,methods=METHODS,minimum_fraction=.05,minimum_task_wins=8,
        retention_excess=.01,max_wall_s=60,max_outer_updates=0,
        carried_used_s=1963.6321034559958,carried_remaining_s=1636.3678965440042)
    if any(digest(c.get(k))!=digest(v) for k,v in expected.items()):raise ValueError('locked_answer_free_recipe')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=0)


def source_pack(root,c):
    config_check(c);root=Path(root)
    legacy=json.loads((root/'configs/seed_question_utility.json').read_text())
    p=base.source_pack(root,legacy)  # independently verifies the complete dependency chain
    raw=(root/'artifacts/seed_question_utility.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=c['previous_result_sha256']:raise ValueError('previous_utility_hash')
    prior=json.loads(raw)
    if not prior['declared_complete'] or (prior['session_used_s'],prior['session_remaining_s'])!=(c['carried_used_s'],c['carried_remaining_s']):raise ValueError('answer_free_carried_ledger')
    bank=json.loads((root/legacy['parent']).read_text())
    original=json.loads((root/'artifacts/seed_nonlinear_learning.json').read_text())
    p['evaluator']={str(t['seed']):dict(check=bank['queries'][str(t['seed'])]['check']['arrays'],
        retention={k:t['arrays'][k] for k in ('retention_x','retention_y')}) for t in original['tasks']['train']}
    p['cached_fits']=json.loads((root/'artifacts/seed_question_headroom.json').read_text())['rows']
    return p


def features(candidate,anchors,anchor_y,observed_x,observed_y,thetas,variance,remaining):
    """Pure function: no answer, post-update parameters, task ID or query API."""
    if len(candidate)!=33 or len(anchors)!=4 or len(anchor_y)!=4 or len(observed_x)!=len(observed_y) or len(thetas)!=3 or type(remaining) is not int or not 1<=remaining<=8:raise ValueError('pre_answer_schema')
    vectors=[candidate]+anchors+observed_x+thetas
    if any(len(x)!=33 or any(not finite(v) for v in x) for x in vectors) or any(not finite(v) for v in anchor_y+observed_y+[variance]) or variance<0:raise ValueError('pre_answer_numeric')
    dot=lambda x,y:sum(v*w for v,w in zip(x,y))
    theta=[st.mean(t[j] for t in thetas) for j in range(33)]
    pred=[dot(candidate,t) for t in thetas];mean=st.mean(pred)
    ae=[y-dot(x,theta) for x,y in zip(anchors,anchor_y)]
    pe=[y-dot(x,theta) for x,y in zip(observed_x,observed_y)]
    grad=[st.mean(x[j]*e for x,e in zip(anchors,ae)) for j in range(33)]
    norm=math.sqrt(dot(candidate,candidate)*dot(grad,grad))
    distance=lambda rows:min(st.mean((v-w)**2 for v,w in zip(candidate,x)) for x in rows) if rows else 0.
    clip=lambda v:max(-1.,min(1.,v/4))
    return [clip(mean),min(1.,st.mean((v-mean)**2 for v in pred)**.5/4),
        math.log1p(variance)/10,min(1.,distance(anchors)),min(1.,distance(observed_x)),
        min(1.,st.mean(e*e for e in ae)/4),min(1.,st.mean(e*e for e in pe)/4) if pe else 0.,
        clip(st.mean(pe) if pe else 0.),dot(candidate,grad)/norm if norm>1e-12 else 0.,remaining/8]


def public_cases(task,ref,c):
    """Only previously observed labels cross into the pure feature function."""
    import torch
    a=task['arrays'];sx=a['support_x'];out={}
    for b in c['budgets']:
        seen=ref['order'][:b-1];v=qs.variance_scores(torch.tensor(sx),torch.tensor(a['old_x']),seen)
        theta=[ref['paths'][str(s)][b-1]['theta'] for s in c['constant_seeds']]
        out[str(b)]={str(i):dict(index=i,budget=b,variance=v[i],features=features(sx[i],a['old_x'],a['old_y'],
            [sx[j] for j in seen],[a['support_y'][j] for j in seen],theta,v[i],8-len(seen))) for i in range(8) if i not in seen}
    return out


def training_cases(tasks,queries,meta,c,check=lambda:None):
    # Rebuild under CURRENT outer fold's constants, never pool old own-fold cases.
    old,refs,fits=base.training_cases(tasks,queries,meta,c,check)
    for tid in old:
        # Reuse the variance already computed; no additional solves for new features.
        a=base.scale_task(tasks[tid],meta['scale'])['arrays'];ref=refs[tid]
        for b,rows in old[tid].items():
            seen=ref['order'][:int(b)-1]
            for i,row in rows.items():
                row['features']=features(a['support_x'][int(i)],a['old_x'],a['old_y'],
                    [a['support_x'][j] for j in seen],[a['support_y'][j] for j in seen],
                    [ref['paths'][str(s)][int(b)-1]['theta'] for s in c['constant_seeds']],row['variance'],8-len(seen))
                del row['action']
    return old,refs,fits


def fit(cases,train,c):
    import numpy as np
    from nexus.nn.ridge import fit_ridge
    if set(cases)!=set(map(str,train)):raise ValueError('training_tasks_only')
    rows=base.flatten(cases,train);x=np.array([r['features'] for r in rows]);y=np.array([r['utility'] for r in rows])
    center=x.mean(0);mean=float(y.mean());scale,beta=fit_ridge(x-center,y-mean,ridge=c['ridge'])
    return dict(center=center.tolist(),scale=scale.tolist(),beta=beta.tolist(),mean=mean)


def predict(model,row):return model['mean']+sum((x-m)/s*b for x,m,s,b in zip(row['features'],model['center'],model['scale'],model['beta']))


def decide(cases,model):
    out={}
    for tid,bs in cases.items():
        out[tid]={}
        for b,rows in bs.items():
            predictions={i:predict(model,row) for i,row in rows.items()}
            if any(not finite(v) for v in predictions.values()):raise ValueError('nonfinite_prediction')
            # All score ties use original row order; source mean is necessarily identical.
            choices=dict(learned=int(max(rows,key=lambda i:(predictions[i],-int(i)))),
                variance=int(max(rows,key=lambda i:(rows[i]['variance'],-int(i)))),
                original_order=min(map(int,rows)),source_mean=min(map(int,rows)))
            out[tid][b]=dict(predictions=predictions,choices=choices)
    return out


def evaluate(decisions,p,c):
    out={}
    for tid,bs in decisions.items():
        out[tid]={}
        for b,d in bs.items():
            # Independent next-update interventions: each policy gets b-1 observed
            # labels plus exactly one chosen answer, only AFTER the global lock.
            reveals={}
            for method,index in d['choices'].items():
                oracle=qs.LabelOracle(p['tasks'][tid]['arrays']['support_y'],int(b))
                for i in p['reference'][tid]['order'][:int(b)-1]:oracle.reveal(i)
                answer=oracle.reveal(index)
                reveals[method]=dict(index=index,answer=float(answer),labels=int(b))
            a=p['assessments'][tid][b]
            scores={i:st.mean(v['check_mse'] for v in ss.values()) for i,ss in a['candidates'].items()}
            ret={i:st.mean(v['retention_mse'] for v in ss.values()) for i,ss in a['candidates'].items()}
            best=min(scores,key=lambda i:(scores[i],int(i)))
            mse={m:scores[str(i)] for m,i in d['choices'].items()}
            retention={m:ret[str(i)] for m,i in d['choices'].items()}
            mse.update(uniform=st.mean(scores.values()),keep=st.mean(v['check_mse'] for v in a['before'].values()),oracle=scores[best])
            retention.update(uniform=st.mean(ret.values()),keep=st.mean(v['retention_mse'] for v in a['before'].values()),oracle=ret[best])
            actual={i:mse['keep']-v for i,v in scores.items()}
            out[tid][b]=dict(query_mse=mse,retention_mse=retention,reveals=reveals,
                actual_utilities=actual,regret={m:v-scores[best] for m,v in mse.items()},
                utility_mse=st.mean((d['predictions'][i]-v)**2 for i,v in actual.items()),
                source_mean_utility_mse=st.mean((p['_mean'][tid]-v)**2 for v in actual.values()))
    return out


def summarize(folds,c):
    cells={t:v for f in folds.values() for t,v in f['evaluation'].items()}
    per={t:{m:st.mean(bs[str(b)]['query_mse'][m] for b in c['primary_budgets']) for m in METHODS} for t,bs in cells.items()}
    means={m:st.mean(v[m] for v in per.values()) for m in METHODS}
    ret={m:st.mean(bs[str(b)]['retention_mse'][m] for bs in cells.values() for b in c['primary_budgets']) for m in METHODS}
    contrasts={m:paired([per[str(t)][m]-per[str(t)]['learned'] for t in c['tasks']['train']]) for m in METHODS if m!='learned'}
    gates=dict(practical=all(means['learned']<=.95*means[m] for m in ('variance','uniform','original_order','keep')),
        intervals=all(contrasts[m]['ci95'][0]>0 for m in ('variance','keep')),
        task_wins=sum(v['learned']<v['keep'] for v in per.values())>=8,retention=ret['learned']<=ret['variance']+.01)
    return dict(label='source_screen_passed' if all(gates.values()) else 'source_screen_failed',source_screen_pass=all(gates.values()),
        gates=gates,primary_means=means,per_task=per,contrasts=contrasts,retention_means=ret,
        task_wins=sum(v['learned']<v['keep'] for v in per.values()),
        by_budget={str(b):{m:st.mean(bs[str(b)]['query_mse'][m] for bs in cells.values()) for m in METHODS} for b in c['budgets']},
        selection_regret={m:st.mean(bs[str(b)]['regret'][m] for bs in cells.values() for b in c['primary_budgets']) for m in METHODS},
        utility_mse={k:st.mean(bs[str(b)][k] for bs in cells.values() for b in c['primary_budgets']) for k in ('utility_mse','source_mean_utility_mse')},
        uncertainty='Exploratory paired task intervals, df11; overlapping source folds and one frozen core; not confirmation.',
        runtime_promotion=False,learning_to_learn_established=False)


def resources(cpu):
    r=base.resources(cpu)
    r.update(predictor_ridge_solves=4,predictor_training_rows=756,predictor_augmented_rows=1512,
        predictor_coefficients=44,predictor_rms_rows=756,post_lock_label_reveals=720)
    return r


def validate(r,c,p):
    """Read-only scalar equations, planned cells and arithmetic; never refits."""
    config_check(c);frozen=digest(p);dot=lambda x,y:sum(a*b for a,b in zip(x,y))
    close=lambda x,y:finite(x) and finite(y) and abs(x-y)<2e-6
    if r['config']!=c or r['source_pack_sha256']!=frozen or r['frozen_after_sha256']!=frozen or r['feature_names']!=FEATURES or set(r['folds'])!=set(map(str,range(4))):raise ValueError('answer_free_frozen_grid')
    for fid,f in r['folds'].items():
        train,held=base.cum.partition(c,int(fid));meta=p['frozen_folds'][fid]
        if (f['train_ids'],f['excluded_ids'])!=(train,held) or any(set(f[k])!=set(map(str,train)) for k in ('training_cases','training_references','training_fits')) or set(f['held_cases'])!=set(map(str,held)):raise ValueError('answer_free_fold_grid')
        for t in map(str,train+held):
            a=p['tasks'][t]['arrays'];scale=meta['scale'];sx=[[v/s for v,s in zip(x,scale)] for x in a['support_x']];ox=[[v/s for v,s in zip(x,scale)] for x in a['old_x']]
            ref=f['training_references'][t] if int(t) in train else p['reference'][t]
            cases=f['training_cases'][t] if int(t) in train else f['held_cases'][t]
            if sorted(ref['order'])!=list(range(8)) or set(cases)!=set(map(str,c['budgets'])) or set(ref['paths'])!=set(map(str,c['constant_seeds'])):raise ValueError('answer_free_budget_grid')
            for seed,path in ref['paths'].items():
                if len(path)!=9:raise ValueError('answer_free_path_grid')
                for n,z in enumerate(path):
                    if z['prefix']!=n or z['index']!=(ref['order'][n-1] if n else None):raise ValueError('answer_free_reference_index')
                    rows=ox+[sx[j] for j in ref['order'][:n]];ys=a['old_y']+[a['support_y'][j] for j in ref['order'][:n]]
                    audit_fit(z,rows,ys,path[0]['theta'] if n else [0.]*33,path[n-1]['theta'] if n else None,meta,seed,n>0)
            for b in c['budgets']:
                seen=ref['order'][:b-1];rows=cases[str(b)];available=set(map(str,set(range(8))-set(seen)))
                if set(rows)!=available:raise ValueError('answer_free_candidate_grid')
                if int(t) in train and set(f['training_fits'][t].get(str(b),{}))!=available:raise ValueError('answer_free_fit_grid')
                for i,row in rows.items():
                    expected={'index','budget','variance','features'}|({'utility'} if int(t) in train else set())
                    if set(row)!=expected or type(row['index']) is not int or row['index']!=int(i) or type(row['budget']) is not int or row['budget']!=b or not finite(row['variance']) or row['variance']<0 or len(row['features'])!=10:raise ValueError('answer_free_row_schema')
                    phi=features(sx[int(i)],ox,a['old_y'],[sx[j] for j in seen],[a['support_y'][j] for j in seen],
                        [ref['paths'][str(s)][b-1]['theta'] for s in c['constant_seeds']],row['variance'],8-len(seen))
                    if any(not close(x,y) for x,y in zip(phi,row['features'])):raise ValueError('answer_free_feature_arithmetic')
                    if int(t) not in train:continue
                    fits=f['training_fits'][t][str(b)][i]
                    if set(fits)!=set(map(str,c['constant_seeds'])):raise ValueError('answer_free_seed_grid')
                    q=p['training_queries'][t];qx=[[v/s for v,s in zip(x,scale)] for x in q['x']]
                    error=lambda theta:st.mean((dot(x,theta)-y)**2 for x,y in zip(qx,q['y']))
                    for s,z in fits.items():
                        prev=ref['paths'][s][b-1]['theta']
                        audit_fit(z,ox+[sx[j] for j in seen+[int(i)]],a['old_y']+[a['support_y'][j] for j in seen+[int(i)]],ref['paths'][s][0]['theta'],prev,meta,s,True)
                        if not close(z['query_before'],error(prev)) or not close(z['query_after'],error(z['theta'])):raise ValueError('answer_free_target_query')
                    if not close(row['utility'],st.mean(z['query_before']-z['query_after'] for z in fits.values())):raise ValueError('answer_free_target')
        rows=base.flatten(f['training_cases'],train);m=f['model']
        if set(m)!={'center','scale','beta','mean'} or not close(m['mean'],st.mean(z['utility'] for z in rows)) or any(len(m[k])!=10 or any(not finite(v) for v in m[k]) for k in ('center','scale','beta')):raise ValueError('answer_free_model_schema')
        center=[st.mean(row['features'][j] for row in rows) for j in range(10)]
        scale=[st.mean((row['features'][j]-center[j])**2 for row in rows)**.5 for j in range(10)];scale=[s if s>=1e-8 else 1. for s in scale]
        if any(not close(v,w) for v,w in zip(center,m['center'])) or any(not close(v,w) for v,w in zip(scale,m['scale'])):raise ValueError('answer_free_preprocessing')
        z=[[(v-u)/s for v,u,s in zip(row['features'],center,scale)] for row in rows];err=[dot(x,m['beta'])-(row['utility']-m['mean']) for x,row in zip(z,rows)]
        if max(abs(2*sum(x[j]*e for x,e in zip(z,err))+c['ridge']*v) for j,v in enumerate(m['beta']))>1e-7:raise ValueError('answer_free_normal_equation')
        if digest(decide(f['held_cases'],m))!=digest(f['decisions']):raise ValueError('answer_free_decisions')
        eval_pack={**p,'_mean':{t:m['mean'] for t in f['decisions']}}
        if digest(evaluate(f['decisions'],eval_pack,c))!=digest(f['evaluation']):raise ValueError('answer_free_evaluation_grid')
    lock=make_lock(r,c,p)
    if r['lock']!=lock or r['lock_sha256']!=digest(lock) or r['locked_before_evaluation'] is not True or digest(summarize(r['folds'],c))!=digest(r['analysis']):raise ValueError('answer_free_lock_summary')
    audit_assessments(p,c)
    return True


def audit_assessments(p,c):
    """Replay cached excluded-task states on recorded CHECK and retention rows."""
    dot=lambda x,y:sum(v*w for v,w in zip(x,y))
    for fid in map(str,range(4)):
        meta=p['frozen_folds'][fid];scale=meta['scale']
        for tid in map(str,meta['excluded_ids']):
            a=p['tasks'][tid]['arrays'];sx=[[v/s for v,s in zip(x,scale)] for x in a['support_x']];ox=[[v/s for v,s in zip(x,scale)] for x in a['old_x']];ref=p['reference'][tid]
            query=p['evaluator'][tid]['check'];ret=p['evaluator'][tid]['retention']
            qx=[[v/s for v,s in zip(x,scale)] for x in query['x']];rx=[[v/s for v,s in zip(x,scale)] for x in ret['retention_x']]
            if set(p['assessments'][tid])!=set(map(str,c['budgets'])) or set(p['cached_fits'][tid])!=set(map(str,c['budgets'])):raise ValueError('answer_free_cached_budget')
            for b in c['budgets']:
                seen=ref['order'][:b-1];cell=p['assessments'][tid][str(b)];cache=p['cached_fits'][tid][str(b)]
                if set(cell)!= {'before','candidates'} or set(cell['candidates'])!=set(map(str,set(range(8))-set(seen))) or set(cache['candidates'])!=set(cell['candidates']):raise ValueError('answer_free_cached_candidate')
                for index,arms in [('before',cache['before'])]+list(cache['candidates'].items()):
                    expected=cell['before'] if index=='before' else cell['candidates'][index]
                    if set(arms)!=set(map(str,c['constant_seeds'])) or set(expected)!=set(arms):raise ValueError('answer_free_cached_seed')
                    for s,z in arms.items():
                        if index=='before':
                            if z['theta']!=ref['paths'][s][b-1]['theta']:raise ValueError('answer_free_cached_before')
                        else:
                            js=seen+[int(index)]
                            audit_fit(z,ox+[sx[j] for j in js],a['old_y']+[a['support_y'][j] for j in js],ref['paths'][s][0]['theta'],ref['paths'][s][b-1]['theta'],meta,s,True)
                        qm=st.mean((dot(x,z['theta'])-y)**2 for x,y in zip(qx,query['y']))
                        rm=st.mean((dot(x,z['theta'])-y)**2 for x,y in zip(rx,ret['retention_y']))
                        if set(expected[s])!={'check_mse','retention_mse'} or any(not finite(v) for v in expected[s].values()) or abs(expected[s]['check_mse']-qm)>2e-6 or abs(expected[s]['retention_mse']-rm)>2e-6:raise ValueError('answer_free_cached_assessment')


def audit_fit(z,x,y,initial,previous,meta,seed,updated):
    dot=lambda a,b:sum(v*w for v,w in zip(a,b));theta=z['theta'];proposal=z['proposal'] if updated else theta
    if any(len(v)!=33 or any(not finite(w) for w in v) for v in (theta,proposal)):raise ValueError('answer_free_fit_numeric')
    ridge=.1 if updated else .01;res=[v-dot(row,proposal) for row,v in zip(x,y)]
    if max(abs(ridge*(v-w)-sum(row[j]*e for row,e in zip(x,res))) for j,(v,w) in enumerate(zip(proposal,initial)))>2e-5:raise ValueError('answer_free_fit_equation')
    if updated:
        g=max(0.,min(1.,.5+.25*meta['constants'][seed]['weights']['logits.bias'][0]))
        if any(abs(v-(w+g*(q-w)))>2e-6 for v,w,q in zip(theta,previous,proposal)):raise ValueError('answer_free_damping')


def make_lock(r,c,p):
    return dict(config_sha256=digest(c),source_pack_sha256=digest(p),
        models={f:digest(v['model']) for f,v in r['folds'].items()},decisions={f:v['decisions'] for f,v in r['folds'].items()})


def run(request):
    import torch
    from . import learning_benchmark as lb
    c=request['inputs']['study_config'];p=request['inputs']['source_pack'];config_check(c)
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True);lb.WORK.clear();start=time.monotonic();frozen=digest(p)
    r=dict(config=c,source_pack_sha256=frozen,feature_names=FEATURES,folds={},declared_complete=False)
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('answer_free_cap')
    def progress():
        r.update(wall_s=time.monotonic()-start,update_work=dict(lb.WORK));Path('progress.json').write_text(json.dumps(r,allow_nan=False))
    progress()
    try:
        for f in range(4):
            check();tasks,queries,meta=base.training_inputs(p,c,f);cases,refs,fits=training_cases(tasks,queries,meta,c,check);model=fit(cases,meta['train_ids'],c)
            held={str(t):public_cases(base.scale_task(p['tasks'][str(t)],meta['scale']),p['reference'][str(t)],c) for t in meta['excluded_ids']}
            r['folds'][str(f)]=dict(train_ids=meta['train_ids'],excluded_ids=meta['excluded_ids'],training_cases=cases,training_references=refs,training_fits=fits,held_cases=held,model=model,decisions=decide(held,model));progress()
        lock=make_lock(r,c,p);path=Path('answer-free-locked.json');path.write_text(json.dumps(lock,allow_nan=False));base.require_lock(path,lock)
        r.update(lock=lock,lock_sha256=digest(lock),locked_before_evaluation=True);progress()
        for f in r['folds'].values():
            check();f['evaluation']=evaluate(f['decisions'],{**p,'_mean':{t:f['model']['mean'] for t in f['decisions']}},c)
        r.update(analysis=summarize(r['folds'],c),frozen_after_sha256=digest(p));validate(r,c,p);check();r['declared_complete']=True;progress()
    except Exception as exc:
        r['failure']=repr(exc);progress();raise
    return dict(adapter=SCHEMA,study=r,resources=resources(time.process_time()),curve=[],
        model=dict(folds={f:v['model'] for f,v in r['folds'].items()}),
        metrics=dict(mse=r['analysis']['primary_means']['learned'],baseline_mse=r['analysis']['primary_means']['variance']),
        runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1))


def validate_output(out,c,caps,p):
    validate(out['study'],c,p);expected=resources(0);work=out['resources']
    if out['adapter']!=SCHEMA or out['study']['declared_complete'] is not True or out['model']!={'folds':{f:v['model'] for f,v in out['study']['folds'].items()}}:raise ValueError('answer_free_output')
    if set(work)!=set(expected) or any(type(work[k]) is not int or work[k]!=v for k,v in expected.items() if k!='cpu_s') or not finite(work['cpu_s']) or not 0<=work['cpu_s']<=caps['cpu_s']:raise ValueError('answer_free_resources')
    if out['study']['update_work']!={'old_anchor_initial_solves':108,'cumulative_solves':3132}:raise ValueError('answer_free_work')
    return True


def saved_replay(root):
    root=Path(root);c=json.loads((root/'configs/seed_answer_free_utility.json').read_text());r=json.loads((root/'artifacts/seed_answer_free_utility.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_answer_free_result')
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_answer_free',status=h['status'],failure=h['failure'],revision=r['execution_sha'],wall_s=h['wall_s'],memory_mb=h['peak_sampled_rss_mb'],
        metrics=dict(mse=r['analysis']['primary_means']['learned'],baseline_mse=r['analysis']['primary_means']['variance']),
        curve=[],resources=r['resources'],model_sha256=r['lock_sha256'],answer_free_utility=r['analysis'])
