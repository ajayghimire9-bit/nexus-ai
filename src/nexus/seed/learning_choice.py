"""One source-only policy-roll-in refit and protected learning-choice comparison.

Reuses prefix_consistency's solver/features, cumulative posterior, source-fold
packing, update_diagnosis trajectories and the same EXPERIMENTAL host/meter.
No frozen network changes; no new data or parallel memory/controller framework.
"""
import hashlib
import json
import math
from pathlib import Path
import statistics as st
import sys
import time
from nexus.evolution1.catalogue import digest
from .grounded_audit import finite
from . import prefix_consistency as ev
from . import sequential_consistency as seq
from . import cumulative_learning as cum
from . import update_diagnosis as prior
from .learning_decision import decide

METHODS=['reference_refit','rollin_refit','protected_rollin']
CACHED=seq.METHODS
RULES=['reference','rollin']


def config_check(c):
    if (c['schema']!='seed_learning_choice_v1' or c['methods']!=METHODS or c['cached_methods']!=CACHED or
        c['tasks']!={'train':list(range(95000000,95110001,10000))} or c['prefixes']!=list(range(9)) or
        c['curve_budgets']!=[1,2,4,8]):raise ValueError('locked_choice_grid')
    for k,v in dict(fold_count=4,posterior_ridge=.1,predictor_ridge=1.,memory_damage_cap=.01,
                    minimum_fraction=.05,minimum_fold_wins=3,retention_excess=.01,max_wall_s=30,max_outer_updates=0).items():
        if type(c[k]) not in (int,float) or c[k]!=v:raise ValueError('locked_choice_recipe')
    if c['max_wall_s']>c['carried_remaining_s'] or abs(c['carried_used_s']+c['carried_remaining_s']-3600)>1e-8:raise ValueError('carried_budget')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=0)


def source_pack(root,c):
    config_check(c);b=(root/c['parent']).read_bytes()
    if hashlib.sha256(b).hexdigest()!=c['parent_sha256']:raise ValueError('frozen_parent_hash')
    parent=json.loads(b);source=seq.source_pack(root,parent['config']);seq.validate(parent,parent['config'],source)
    if parent['declared_complete'] is not True:raise ValueError('incomplete_parent')
    return dict(source=source,baseline_analysis=parent['analysis'],parent_sha256=c['parent_sha256'])


def fit_rule(cases,ids,c,fold):
    """Receives ONLY this fold's nine training tasks and training utilities."""
    if set(cases)!=set(map(str,ids)) or len(ids)!=9:raise ValueError('training_case_boundary')
    model=ev.fit_predictors(cases,ids,dict(prefixes=list(range(1,9)),predictor_ridge=c['predictor_ridge'],permutation_seed=7301),fold,methods=['consistency'])['consistency']
    rows=ev.training_rows(cases,ids)
    error_scale=st.mean((ev.predict(model,'consistency',r)-r['utility'])**2 for r in rows)**.5
    return dict(model=model,error_scale=error_scale)


def training_cases(tasks,ids,meta,rule,check=lambda:None):
    """Trace first from support only; score training query labels afterward."""
    out={}
    for t,task in zip(ids,tasks):
        selector=None if rule=='reference' else lambda row:ev.predict(meta['predictors']['consistency'],'consistency',row)>0
        trace=ev.support_trace(task.support_x,task.support_y,task.old_x,task.old_y,check,selector=selector)
        x=task.query_x.tolist();y=task.query_y.tolist()
        for r in trace:
            losses={k:st.mean((v-sum(a*b for a,b in zip(row,r[k])))**2 for row,v in zip(x,y)) for k in ('before','proposal')}
            r['utility']=losses['before']-losses['proposal'];r.update(query_before=losses['before'],query_proposal=losses['proposal'])
        out[str(t)]=trace
    return out


def updater(info,protected,c,trace):
    """No query/retention inputs. Pending questions consume no invented labels."""
    import torch
    initial=None
    def apply(previous,x,y,anchors,old_y,seen_x,seen_y,controller,ignored):
        nonlocal initial
        if initial is None:initial=previous.detach().clone()
        proposal=cum.posterior(initial,torch.cat((anchors,seen_x)),torch.cat((old_y,seen_y)),torch.ones_like(initial))
        phi=ev.features(previous.tolist(),proposal.tolist(),x.tolist(),float(y),anchors.tolist(),old_y.tolist(),seen_x.tolist(),seen_y.tolist())
        prediction=ev.predict(info['model'],'consistency',dict(prefix=len(seen_y),features=phi))
        # Total known-anchor excess versus initialization, not a drifting
        # per-step tolerance that could silently accumulate forgetting.
        damage=float(((anchors@proposal-old_y)**2).mean()-((anchors@initial-old_y)**2).mean())
        decision=decide(predicted_gain=prediction,error_scale=info['error_scale'],known_damage=damage,
            damage_cap=c['memory_damage_cap'],remaining_examples=8-len(seen_y)).payload() if protected else None
        learn=decision['action']=='learn' if protected else prediction>0
        trace.append(dict(proposal=proposal.tolist(),features=phi,predicted_utility=prediction,known_damage=damage,decision=decision,gate=float(learn)))
        return proposal if learn else previous
    return apply


def summarize(r,c,pack):
    old=pack['baseline_analysis'];rows=r['rows'];all_methods=METHODS+CACHED
    per={str(t):{**old['per_task'][str(t)],**{m:st.mean(rows[str(t)][m][p]['query_mse'] for p in c['curve_budgets']) for m in METHODS}} for t in c['tasks']['train']}
    means={m:st.mean(v[m] for v in per.values()) for m in all_methods}
    curves={**old['query_curves'],**{m:{str(p):st.mean(rows[str(t)][m][p]['query_mse'] for t in c['tasks']['train']) for p in c['prefixes']} for m in METHODS}}
    retention={**old['final_retention'],**{m:st.mean(rows[str(t)][m][8]['retention_mse'] for t in c['tasks']['train']) for m in METHODS}}
    contrasts={m:prior.paired([v[m]-v['protected_rollin'] for v in per.values()]) for m in all_methods if m!='protected_rollin'}
    coverage=prior.paired([v['reference_refit']-v['rollin_refit'] for v in per.values()])
    fold_means={str(f):{m:st.mean(per[str(t)][m] for t in cum.partition(c,f)[1]) for m in all_methods} for f in range(4)}
    coverage_wins=sum(f['rollin_refit']<f['reference_refit'] for f in fold_means.values())
    safety_wins=sum(f['protected_rollin']<f['rollin_refit'] for f in fold_means.values())
    retention_pass=retention['protected_rollin']<=retention['constant_damping']+c['retention_excess']
    beats=lambda contrast,base:contrast['mean']>=c['minimum_fraction']*base and contrast['ci95'][0]>0
    return dict(curve_means=means,query_curves=curves,per_task=per,per_fold=fold_means,final_retention=retention,contrasts=contrasts,
        reference_minus_rollin_benefit=coverage,coverage_fold_wins=coverage_wins,safety_fold_wins=safety_wins,
        coverage_screen_pass=beats(coverage,means['reference_refit']) and coverage_wins>=3,
        protection_screen_pass=beats(contrasts['rollin_refit'],means['rollin_refit']) and safety_wins>=3 and retention_pass,
        strong_baseline_screen_pass=all(beats(contrasts[m],means[m]) for m in ('constant_damping','replay','bounded_fixed')) and retention_pass,
        retention_pass=retention_pass,
        choices={a:sum(row['decision']['action']==a for t in rows.values() for row in t['protected_rollin'][1:]) for a in ('learn','ask','retain')},
        reasons={a:sum(row['decision']['reason']==a for t in rows.values() for row in t['protected_rollin'][1:]) for a in ('known_memory_risk','predicted_harm','uncertain_benefit','predicted_benefit')},
        known_anchor_cap_pass=all(row['known_damage']<=c['memory_damage_cap'] for t in rows.values() for row in t['protected_rollin'][1:] if row['gate']),
        fresh_validation=False,runtime_promotion=False,independent_pretrained_cores=1,
        question_interpretation='Ask defers to next scheduled source example; no active-query efficiency or new label collection demonstrated.',
        uncertainty='12 reused task clusters, one frozen core, overlapping source folds; conditional exploratory intervals, not confirmation.')


def validate(r,c,pack):
    config_check(c)
    if r['config']!=c or r['source_pack_sha256']!=digest(pack) or r['frozen_before_sha256']!=digest(pack['source']['frozen_folds']) or r['frozen_after_sha256']!=r['frozen_before_sha256']:raise ValueError('choice_provenance')
    if set(r['folds'])!=set(map(str,range(4))) or set(r['rows'])!=set(map(str,c['tasks']['train'])):raise ValueError('complete_choice_grid')
    close=lambda a,b:finite(a) and finite(b) and abs(a-b)<2e-6
    dot=lambda x,t:sum(a*b for a,b in zip(x,t))
    lookup={str(t['seed']):t['arrays'] for t in pack['source']['tasks']}
    for i in range(4):
        f=r['folds'][str(i)];train,held=cum.partition(c,i);meta=pack['source']['frozen_folds'][str(i)];scale=meta['scale']
        if f['train_ids']!=train or f['excluded_ids']!=held or set(f['models'])!=set(RULES) or set(f['cases'])!=set(RULES) or digest(f['models'])!=f['models_sha256']:raise ValueError('training_fold_grid')
        for rule in RULES:
            cases=f['cases'][rule];info=f['models'][rule];m=info['model']
            if set(cases)!=set(map(str,train)) or m['columns']!=list(range(4,10)) or any(len(m[k])!=6 for k in ('center','scale','beta')):raise ValueError('training_only_model_grid')
            for t,trace in cases.items():
                if [row['prefix'] for row in trace]!=list(range(1,9)) or any(type(row['prefix']) is not int for row in trace):raise ValueError('training_prefix_grid')
                a=lookup[t];ox=[[v/s for v,s in zip(x,scale)] for x in a['old_x']];sx=[[v/s for v,s in zip(x,scale)] for x in a['support_x']]
                _proposal_math(trace[0]['before'],[0.]*33,ox,a['old_y'],ridge=.01)
                for p,row in enumerate(trace,1):
                    _proposal_math(row['proposal'],trace[0]['before'],ox+sx[:p],a['old_y']+a['support_y'][:p])
                    phi=ev.features(row['before'],row['proposal'],sx[p-1],a['support_y'][p-1],ox,a['old_y'],sx[:p],a['support_y'][:p])
                    if len(row['features'])!=10 or any(not close(v,w) for v,w in zip(phi,row['features'])):raise ValueError('training_support_features')
                    if p>1:
                        last=trace[p-2];take=rule=='reference' or ev.predict(meta['predictors']['consistency'],'consistency',last)>0
                        if row['before']!=(last['proposal'] if take else last['before']):raise ValueError('training_policy_rollin')
                    for key in ('before','proposal'):
                        err=st.mean((v-dot([x/s for x,s in zip(x,scale)],row[key]))**2 for x,v in zip(a['query_x'],a['query_y']))
                        if not close(row['query_'+key],err):raise ValueError('training_utility_arithmetic')
                    if not close(row['utility'],row['query_before']-row['query_proposal']):raise ValueError('training_utility_label')
            training=ev.training_rows(cases,train);y=[row['utility'] for row in training];mean=st.mean(y)
            xx=[[row['features'][j] for j in m['columns']] for row in training]
            center=[st.mean(x[j] for x in xx) for j in range(6)];rms=[st.mean((x[j]-center[j])**2 for x in xx)**.5 for j in range(6)];sc=[x if x>=1e-8 else 1. for x in rms]
            if any(not close(a,b) for a,b in zip(center,m['center'])) or any(not close(a,b) for a,b in zip(sc,m['scale'])) or not close(m['mean'],mean):raise ValueError('source_only_preprocessing')
            z=[[(a-b)/s for a,b,s in zip(x,center,sc)] for x in xx];error=[dot(x,m['beta'])-(v-mean) for x,v in zip(z,y)]
            if any(not finite(v) for v in m['beta']) or max(abs(2*sum(x[j]*e for x,e in zip(z,error))+m['beta'][j]) for j in range(6))>1e-7:raise ValueError('fitted_ridge_equation')
            if not close(info['error_scale'],st.mean(v*v for v in error)**.5):raise ValueError('training_error_scale')
        flat={}
        for t in held:
            cells=r['rows'][str(t)];a=lookup[str(t)];ox=[[v/s for v,s in zip(x,scale)] for x in a['old_x']];sx=[[v/s for v,s in zip(x,scale)] for x in a['support_x']]
            if set(cells)!=set(METHODS):raise ValueError('complete_method_grid')
            flat[str(t)]=cells
            for method,trace in cells.items():
                if [row['prefix'] for row in trace]!=c['prefixes'] or any(type(row['prefix']) is not int for row in trace):raise ValueError('complete_prefix_grid')
                initial=trace[0]['theta'];_proposal_math(initial,[0.]*33,ox,a['old_y'],ridge=.01)
                for p,row in enumerate(trace):
                    expected=seq.BASE|{'proposal','features','predicted_utility','known_damage','decision','gate'} if p else seq.BASE
                    if set(row)!=expected:raise ValueError('complete_metric_grid')
                    if len(row['theta'])!=33 or any(not finite(v) for v in row['theta']) or any(not finite(row[k]) or row[k]<0 for k in ('query_mse','retention_mse','update_l2','cumulative_update_l2')):raise ValueError('finite_metric_grid')
                    if not close(row['cumulative_update_l2'],sum((v-b)**2 for v,b in zip(row['theta'],initial))**.5):raise ValueError('cumulative_update_norm')
                    if not p:
                        if any(row[k] is not None for k in ('support_error_before','support_error_after','residual_corrected_fraction')):raise ValueError('empty_support')
                        continue
                    info=f['models']['reference' if method=='reference_refit' else 'rollin'];before=trace[p-1]['theta'];proposal=row['proposal']
                    if not close(row['support_error_before'],(a['support_y'][p-1]-dot(sx[p-1],before))**2) or not close(row['support_error_after'],(a['support_y'][p-1]-dot(sx[p-1],row['theta']))**2):raise ValueError('support_score_arithmetic')
                    if row['residual_corrected_fraction'] is not None and not finite(row['residual_corrected_fraction']):raise ValueError('finite_optional_fraction')
                    _proposal_math(proposal,initial,ox+sx[:p],a['old_y']+a['support_y'][:p])
                    phi=ev.features(before,proposal,sx[p-1],a['support_y'][p-1],ox,a['old_y'],sx[:p],a['support_y'][:p]);prediction=ev.predict(info['model'],'consistency',dict(prefix=p,features=phi))
                    damage=st.mean((v-dot(x,proposal))**2-(v-dot(x,initial))**2 for x,v in zip(ox,a['old_y']))
                    if len(row['features'])!=10 or any(not close(v,w) for v,w in zip(phi,row['features'])) or not close(prediction,row['predicted_utility']) or not close(damage,row['known_damage']):raise ValueError('choice_evidence_math')
                    exact_prediction=ev.predict(info['model'],'consistency',dict(prefix=p,features=row['features']))
                    if row['predicted_utility']!=exact_prediction:raise ValueError('saved_prediction_exactness')
                    decision=decide(predicted_gain=exact_prediction,error_scale=info['error_scale'],known_damage=row['known_damage'],damage_cap=c['memory_damage_cap'],remaining_examples=8-p).payload() if method=='protected_rollin' else None
                    # Recorded float32 inputs are independently verified above;
                    # preserve their exact arithmetic when checking the decision.
                    take=decision['action']=='learn' if decision else exact_prediction>0
                    if row['decision']!=decision or not finite(row['gate']) or row['gate']!=float(take) or row['theta']!=(proposal if take else before):raise ValueError('choice_action_contract')
        prior.validate_source_math({'recorded':flat},dict(scale=scale,tasks=[t for t in pack['source']['tasks'] if t['seed'] in held]))
    if r['analysis']!=summarize(r,c,pack):raise ValueError('choice_summary')
    return True


def _proposal_math(theta,initial,x,y,ridge=.1):
    if len(theta)!=33 or any(not finite(v) for v in theta):raise ValueError('finite_proposal')
    residual=[v-sum(a*b for a,b in zip(row,theta)) for row,v in zip(x,y)]
    if max(abs(ridge*(v-b)-sum(row[j]*e for row,e in zip(x,residual))) for j,(v,b) in enumerate(zip(theta,initial)))>2e-5:raise ValueError('proposal_normal_equation')


def resources(cpu_s):
    return dict(updates=0,real_steps=0,imagined_transitions=0,world_model_forwards=0,predictor_fits=8,
        training_cases=576,training_initial_solves=72,training_cumulative_solves=576,
        evaluation_trajectories=36,evaluation_snapshots=324,evaluation_initial_solves=36,evaluation_cumulative_solves=288,
        query_score_rows=39852,retention_score_rows=8748,cached_baseline_trajectories=108,teaching_presentations=864,cpu_s=cpu_s)


def run(request):
    import torch
    import numpy as np
    from . import learning_benchmark as lb
    c=request['inputs']['study_config'];config_check(c);pack=request['inputs']['source_pack'];source=pack['source'];torch.set_num_threads(1);torch.use_deterministic_algorithms(True);lb.WORK.clear();start=time.monotonic()
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('choice_wall_cap')
    r=dict(config=c,source_pack_sha256=digest(pack),folds={},rows={},declared_complete=False,frozen_before_sha256=digest(source['frozen_folds']))
    def progress():
        r.update(wall_s=time.monotonic()-start,update_work=dict(lb.WORK));p=Path('progress.tmp');p.write_text(json.dumps(r,allow_nan=False));p.replace('progress.json')
    progress()
    for f in range(4):
        train_tasks,held,pre=cum.prepare_fold(source,c,f,include_bound=False);meta=source['frozen_folds'][str(f)];train,excluded=cum.partition(c,f)
        if pre['scale']!=meta['scale']:raise ValueError('frozen_scale_reproduction')
        cases={rule:training_cases(train_tasks,train,meta,rule,check) for rule in RULES};models={rule:fit_rule(cases[rule],train,c,f) for rule in RULES}
        r['folds'][str(f)]=dict(train_ids=train,excluded_ids=excluded,cases=cases,models=models,models_sha256=digest(models))
        for t,task in held.items():
            cell={};r['rows'][str(t)]=cell
            for method in METHODS:
                trace=[];rows=prior.trajectory(task,None,'fixed',check,update_fn=updater(models['reference' if method=='reference_refit' else 'rollin'],method=='protected_rollin',c,trace))
                for row,extra in zip(rows[1:],trace):row.update(extra)
                cell[method]=rows
        progress()
    r.update(frozen_after_sha256=digest(source['frozen_folds']),analysis=summarize(r,c,pack));validate(r,c,pack);r['declared_complete']=True;progress()
    return dict(adapter='seed_learning_choice_v1',study=r,curve=[],model=dict(schema='source_utility_models_v1',folds={k:v['models'] for k,v in r['folds'].items()}),
        metrics=dict(mse=r['analysis']['curve_means']['protected_rollin'],baseline_mse=pack['baseline_analysis']['curve_means']['constant_damping']),
        resources=resources(time.process_time()),runtime=dict(python=sys.version,torch=torch.__version__,numpy=np.__version__,device='cpu',threads=1))


def validate_output(output,c,caps,pack):
    r=output['study'];validate(r,c,pack);w=output['resources'];expected=resources(0)
    if output['adapter']!='seed_learning_choice_v1' or r['declared_complete'] is not True:raise ValueError('incomplete_choice_execution')
    if output['model']!=dict(schema='source_utility_models_v1',folds={k:v['models'] for k,v in r['folds'].items()}):raise ValueError('fitted_model_hashes')
    if set(w)!=set(expected) or any(type(w[k]) is not int or w[k]!=v for k,v in expected.items() if k!='cpu_s'):raise ValueError('choice_resource_grid')
    if not finite(w['cpu_s']) or not 0<=w['cpu_s']<=caps['cpu_s'] or caps['updates']!=0 or r['update_work']!={'old_anchor_initial_solves':108,'cumulative_solves':864}:raise ValueError('choice_actual_work')
    return True


def saved_replay(root):
    c=json.loads((root/'configs/seed_learning_choice.json').read_text());r=json.loads((root/'artifacts/seed_learning_choice.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_choice_execution')
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_learning_choice',status=h['status'],failure=h['failure'],wall_s=h['wall_s'],memory_mb=h['peak_sampled_rss_mb'],revision=r['execution_sha'],metrics=dict(mse=r['analysis']['curve_means']['protected_rollin'],baseline_mse=r['analysis']['curve_means']['constant_damping']),curve=[],resources=r['resources'],model_sha256=digest({k:v['models'] for k,v in r['folds'].items()}),learning_choice=r['analysis'])
