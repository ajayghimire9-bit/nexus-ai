"""Sequential application of frozen source-fitted update-utility predictors.

Reuses cumulative proposals, prefix features/prediction, existing trajectories,
bounded/replay updates and the EXPERIMENTAL host. No new fitting or memory stack.
"""
import hashlib
import json
from pathlib import Path
import statistics as st
import sys
import time

from nexus.evolution1.catalogue import digest
from .grounded_audit import finite
from . import cumulative_learning as cum
from . import prefix_consistency as evidence
from . import update_diagnosis as prior

METHODS=['consistency_selector','prefix_selector','constant_damping','replay','bounded_fixed','unit_cumulative','none']
CUSTOM=METHODS[:3]+['unit_cumulative']
BASE={'prefix','theta','update_l2','cumulative_update_l2','query_mse','retention_mse',
      'support_error_before','support_error_after','residual_corrected_fraction'}
EXTRA={'gate','proposal','features','predicted_utility'}


def config_check(c):
    if (c['schema']!='seed_sequential_consistency_v1' or c['methods']!=METHODS or c['constant_seeds']!=[7201,7202,7203] or
        c['tasks']!={'train':list(range(95000000,95110001,10000))} or c['prefixes']!=list(range(9)) or c['curve_budgets']!=[1,2,4,8]):
        raise ValueError('locked_sequential_grid')
    for k,v in dict(fold_count=4,posterior_ridge=.1,utility_threshold=0.,minimum_fraction=.05,
                    minimum_fold_wins=3,retention_excess=.01,max_wall_s=30,max_outer_updates=0).items():
        if type(c[k]) not in (int,float) or c[k]!=v:raise ValueError('locked_sequential_recipe')
    if c['max_wall_s']>c['carried_remaining_s'] or abs(c['carried_used_s']+c['carried_remaining_s']-3600)>1e-8:raise ValueError('carried_budget')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=0)


def source_pack(root,c):
    """Only source arrays and source-fitted frozen state; no old query scores."""
    config_check(c);objects={}
    for key in ('source_plan','predictor_parent','damping_parent'):
        raw=(root/c[key]).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=c[key+'_sha256']:raise ValueError('frozen_parent_hash: '+key)
        objects[key]=json.loads(raw)
    pack=dict(tasks=prior.source_pack(root,objects['source_plan'])['tasks'],frozen_folds={},
        parent_hashes={k:c[k+'_sha256'] for k in ('predictor_parent','damping_parent')},
        damping_config_sha256=digest(objects['damping_parent']['config']))
    for key in ('predictor_parent','damping_parent'):
        if objects[key]['declared_complete'] is not True:raise ValueError('incomplete_frozen_parent')
    for f in range(4):
        p=objects['predictor_parent']['folds'][str(f)];d=objects['damping_parent']['folds'][str(f)]
        if (p['train_ids'],p['excluded_ids'],p['scale'],p['source_sha256'])!=(d['train_ids'],d['excluded_ids'],d['scale'],d['source_sha256']):
            raise ValueError('parent_fold_provenance_mismatch')
        if digest(p['models'])!=p['models_sha256']:raise ValueError('parent_predictor_hash')
        constants={}
        for seed in c['constant_seeds']:
            info=d['models'][str(seed)]['constant_gate'];cum.checkpoint_bytes(info,width=1)
            constants[str(seed)]={k:info[k] for k in ('weights','provenance','sha256','checkpoint')}
        pack['frozen_folds'][str(f)]=dict(train_ids=p['train_ids'],excluded_ids=p['excluded_ids'],scale=p['scale'],tau=d['tau'],
            source_sha256=p['source_sha256'],predictors={k:p['models'][k] for k in ('consistency','prefix_mean')},constants=constants)
    validate_pack(pack,c);return pack


def validate_pack(pack,c):
    if set(pack)!= {'tasks','frozen_folds','parent_hashes','damping_config_sha256'} or pack['parent_hashes']!={k:c[k+'_sha256'] for k in ('predictor_parent','damping_parent')}:
        raise ValueError('source_only_frozen_payload')
    if [t['seed'] for t in pack['tasks']]!=c['tasks']['train'] or set(pack['frozen_folds'])!=set(map(str,range(4))):raise ValueError('frozen_fold_grid')
    for f in range(4):
        meta=pack['frozen_folds'][str(f)];train,held=cum.partition(c,f)
        if (meta['train_ids'],meta['excluded_ids'])!=(train,held) or meta['source_sha256']!=digest([t for t in pack['tasks'] if t['seed'] in train]):
            raise ValueError('source_training_separation')
        if len(meta['scale'])!=33 or any(not finite(v) or v<=0 for v in meta['scale']) or not finite(meta['tau']) or meta['tau']<=0:raise ValueError('frozen_preprocessing')
        if set(meta['predictors'])!={'consistency','prefix_mean'} or set(meta['constants'])!=set(map(str,c['constant_seeds'])):raise ValueError('frozen_model_grid')
        m=meta['predictors']['consistency']
        if m['columns']!=list(range(4,10)) or any(len(m[k])!=6 for k in ('center','scale','beta')) or any(not finite(v) for k in ('center','scale','beta') for v in m[k]) or not finite(m['mean']) or any(v<=0 for v in m['scale']):
            raise ValueError('frozen_predictor_state')
        means=meta['predictors']['prefix_mean']['means']
        if len(means)!=8 or any(not finite(v) for v in means):raise ValueError('frozen_prefix_means')
        for seed,info in meta['constants'].items():
            if info['provenance']!=dict(config_sha256=pack['damping_config_sha256'],fold=f,seed=int(seed),source_sha256=meta['source_sha256'],source_only=True):raise ValueError('damping_training_provenance')
            cum.checkpoint_bytes(info,width=1)
            if info['weights']['logits.weight']!=[[0.,0.,0.,0.]] or len(info['weights']['logits.bias'])!=1 or not finite(info['weights']['logits.bias'][0]):raise ValueError('constant_is_task_independent')
    return True


def replicas(method,c):return list(map(str,c['constant_seeds'])) if method=='constant_damping' else ['frozen']


def updater(method,meta,replica,trace):
    """Only observed support reaches this closure; assessments cannot enter."""
    import torch
    from . import learning_benchmark as lb
    initial=None
    fixed=None
    if method=='constant_damping':
        lb.count('constant_scalar_reads')
        fixed=float((.5+.25*torch.tensor(meta['constants'][replica]['weights']['logits.bias'][0])).clamp(0,1))
    def apply(previous,x,y,anchors,old_y,seen_x,seen_y,controller,ignored):
        nonlocal initial
        if initial is None:initial=previous.detach().clone()
        proposal=cum.posterior(initial,torch.cat((anchors,seen_x)),torch.cat((old_y,seen_y)),torch.ones_like(initial))
        phi=None;prediction=None
        if method=='consistency_selector':
            lb.count('sequential_features');lb.count('consistency_predictor_calls')
            phi=evidence.features(previous.tolist(),proposal.tolist(),x.tolist(),float(y),anchors.tolist(),old_y.tolist(),seen_x.tolist(),seen_y.tolist())
            prediction=evidence.predict(meta['predictors']['consistency'],'consistency',dict(prefix=len(seen_y),features=phi));g=float(prediction>0)
        elif method=='prefix_selector':
            lb.count('prefix_predictor_calls');prediction=meta['predictors']['prefix_mean']['means'][len(seen_y)-1];g=float(prediction>0)
        elif method=='constant_damping':g=fixed
        elif method=='unit_cumulative':g=1.
        else:raise ValueError('sequential_method')
        trace.append(dict(gate=g,proposal=proposal.tolist(),features=phi,predicted_utility=prediction))
        return proposal if g==1 else previous if g==0 else previous+g*(proposal-previous)
    return apply


def summarize(rows,c):
    def value(t,m,key='query_mse',prefixes=None):
        return st.mean(trace[p][key] for trace in rows[str(t)][m].values() for p in (prefixes or c['curve_budgets']))
    per={str(t):{m:value(t,m) for m in METHODS} for t in c['tasks']['train']}
    means={m:st.mean(v[m] for v in per.values()) for m in METHODS}
    contrasts={m:prior.paired([v[m]-v['consistency_selector'] for v in per.values()]) for m in METHODS[1:]}
    retention={m:st.mean(value(t,m,'retention_mse',[8]) for t in c['tasks']['train']) for m in METHODS}
    folds={str(f):{m:st.mean(per[str(t)][m] for t in cum.partition(c,f)[1]) for m in METHODS} for f in range(4)}
    wins=sum(v['consistency_selector']<v['constant_damping'] for v in folds.values())
    improvement=all(contrasts[m]['mean']>=c['minimum_fraction']*means[m] and contrasts[m]['ci95'][0]>0 for m in ('constant_damping','replay','bounded_fixed'))
    retained=retention['consistency_selector']<=retention['constant_damping']+c['retention_excess']
    return dict(curve_means=means,per_task=per,contrasts=contrasts,final_retention=retention,per_fold=folds,fold_wins=wins,
        improvement_pass=improvement,retention_pass=retained,source_screen_pass=improvement and retained and wins>=c['minimum_fold_wins'],
        query_curves={m:{str(p):st.mean(value(t,m,prefixes=[p]) for t in c['tasks']['train']) for p in c['prefixes']} for m in METHODS},
        teaching_updates={m:sum(int(s['gate']) for t in rows.values() for tr in t[m].values() for s in tr[1:]) for m in METHODS[:2]},
        fresh_validation=False,runtime_promotion=False,independent_pretrained_cores=1,
        uncertainty='12 reused task clusters, three frozen damping fits averaged inside tasks; overlapping source folds, not independent world-model replications.')


def validate(r,c,pack):
    config_check(c);validate_pack(pack,c)
    if r['config']!=c or r['source_pack_sha256']!=digest(pack) or r['frozen_before_sha256']!=digest(pack['frozen_folds']) or r['frozen_after_sha256']!=r['frozen_before_sha256']:
        raise ValueError('frozen_sequential_provenance')
    if set(r['rows'])!=set(map(str,c['tasks']['train'])):raise ValueError('complete_task_grid')
    dot=lambda a,b:sum(v*w for v,w in zip(a,b))
    close=lambda a,b:finite(a) and finite(b) and abs(a-b)<2e-6
    lookup={t['seed']:t['arrays'] for t in pack['tasks']}
    for f in range(4):
        meta=pack['frozen_folds'][str(f)];scale=meta['scale'];held=meta['excluded_ids'];flat={}
        for t in held:
            cell=r['rows'][str(t)];a=lookup[t];flat[str(t)]={}
            if set(cell)!=set(METHODS):raise ValueError('complete_method_grid')
            sx=[[x/s for x,s in zip(row,scale)] for row in a['support_x']];ox=[[x/s for x,s in zip(row,scale)] for row in a['old_x']]
            for m in METHODS:
                if set(cell[m])!=set(replicas(m,c)):raise ValueError('complete_replica_grid')
                for rep,trace in cell[m].items():
                    flat[str(t)][m+':'+rep]=trace
                    if [row['prefix'] for row in trace]!=c['prefixes'] or any(type(row['prefix']) is not int for row in trace):raise ValueError('complete_prefix_grid')
                    initial=trace[0]['theta'];old_residual=[v-dot(x,initial) for x,v in zip(ox,a['old_y'])]
                    if len(initial)!=33 or max(abs(.01*v-sum(x[j]*e for x,e in zip(ox,old_residual))) for j,v in enumerate(initial))>2e-5:
                        raise ValueError('anchor_only_initial_fit')
                    for p,row in enumerate(trace):
                        expected=BASE|EXTRA if p and m in CUSTOM else BASE
                        if set(row)!=expected or len(row['theta'])!=33 or any(not finite(v) for v in row['theta']):raise ValueError('trajectory_metric_grid')
                        if any(not finite(row[k]) or row[k]<0 for k in ('query_mse','retention_mse','update_l2','cumulative_update_l2')):raise ValueError('finite_metrics')
                        if not close(row['cumulative_update_l2'],sum((v-b)**2 for v,b in zip(row['theta'],trace[0]['theta']))**.5):raise ValueError('cumulative_norm')
                        if not p:
                            if any(row[k] is not None for k in ('support_error_before','support_error_after','residual_corrected_fraction')):raise ValueError('empty_context_support')
                            continue
                        before=trace[p-1]['theta'];x=sx[p-1];y=a['support_y'][p-1]
                        if not close(row['support_error_before'],(y-dot(x,before))**2) or not close(row['support_error_after'],(y-dot(x,row['theta']))**2):raise ValueError('support_error_arithmetic')
                        if row['residual_corrected_fraction'] is not None and not finite(row['residual_corrected_fraction']):raise ValueError('optional_fraction')
                        if m not in CUSTOM:continue
                        g=row['gate'];proposal=row['proposal']
                        if not finite(g) or not 0<=g<=1 or len(proposal)!=33 or any(not finite(v) for v in proposal):raise ValueError('finite_update_decision')
                        bx=ox+sx[:p];by=a['old_y']+a['support_y'][:p];residual=[v-dot(x,proposal) for x,v in zip(bx,by)]
                        if max(abs(.1*(v-b)-sum(x[j]*e for x,e in zip(bx,residual))) for j,(v,b) in enumerate(zip(proposal,trace[0]['theta'])))>2e-5:raise ValueError('proposal_normal_equation')
                        if m=='consistency_selector':
                            phi=evidence.features(before,proposal,x,y,ox,a['old_y'],sx[:p],a['support_y'][:p])
                            if row['features'] is None or len(row['features'])!=10 or any(not close(v,w) for v,w in zip(row['features'],phi)):raise ValueError('evolving_support_features')
                            prediction=evidence.predict(meta['predictors']['consistency'],'consistency',dict(prefix=p,features=row['features']))
                            if not close(row['predicted_utility'],prediction) or g!=float(prediction>0):raise ValueError('frozen_selector_decision')
                        else:
                            if row['features'] is not None:raise ValueError('unplanned_features')
                            if m=='prefix_selector':
                                prediction=meta['predictors']['prefix_mean']['means'][p-1]
                                if not close(row['predicted_utility'],prediction) or g!=float(prediction>0):raise ValueError('prefix_decision')
                            else:
                                if row['predicted_utility'] is not None:raise ValueError('unmeasured_utility')
                                target=1. if m=='unit_cumulative' else max(0,min(1,.5+.25*meta['constants'][rep]['weights']['logits.bias'][0]))
                                if not close(g,target):raise ValueError('constant_damping')
                        if any(not close(v,b+g*(p-b)) for v,b,p in zip(row['theta'],before,proposal)):raise ValueError('sequential_update_arithmetic')
        prior.validate_source_math({'recorded':flat},dict(scale=scale,tasks=[t for t in pack['tasks'] if t['seed'] in held]))
    if r['analysis']!=summarize(r['rows'],c):raise ValueError('sequential_summary')
    return True


def resources(cpu_s):
    return dict(updates=0,real_steps=0,imagined_transitions=0,world_model_forwards=0,predictor_fits=0,
        trajectories=108,evaluation_snapshots=972,inner_updates=864,initial_solves=108,cumulative_solves=576,
        consistency_predictor_calls=96,prefix_predictor_calls=96,sequential_features=96,constant_scalar_reads=36,
        normalization_source_rows=432,observed_teaching_presentations=864,initial_anchor_rows=432,
        cumulative_support_rows=2592,cumulative_anchor_rows=2304,
        query_score_rows=26244,retention_score_rows=26244,cpu_s=cpu_s)


def run(request):
    import torch
    from . import learning_benchmark as lb
    from .bounded_correction import limiter
    c=request['inputs']['study_config'];config_check(c);pack=request['inputs']['source_pack'];validate_pack(pack,c)
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True);lb.WORK.clear();start=time.monotonic()
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('sequential_wall_cap')
    r=dict(config=c,source_pack_sha256=digest(pack),rows={},declared_complete=False,frozen_before_sha256=digest(pack['frozen_folds']))
    def progress():
        r.update(wall_s=time.monotonic()-start,update_work=dict(lb.WORK));p=Path('progress.tmp');p.write_text(json.dumps(r,allow_nan=False));p.replace('progress.json')
    progress()
    for f in range(4):
        _,held,pre=cum.prepare_fold(pack,c,f,include_bound=False);meta=pack['frozen_folds'][str(f)]
        if pre['scale']!=meta['scale']:raise ValueError('reproduced_frozen_scale')
        for t,task in held.items():
            cell={};r['rows'][str(t)]=cell
            for method in METHODS:
                cell[method]={}
                for rep in replicas(method,c):
                    if method in CUSTOM:
                        trace=[];rows=prior.trajectory(task,None,'fixed',check,update_fn=updater(method,meta,rep,trace))
                        for row,extra in zip(rows[1:],trace):row.update(extra)
                    elif method=='bounded_fixed':rows=prior.trajectory(task,None,'fixed',check,update_fn=limiter(meta['tau'],[]))
                    else:rows=prior.trajectory(task,None,method,check)
                    cell[method][rep]=rows
            progress()
    r.update(analysis=summarize(r['rows'],c),frozen_after_sha256=digest(pack['frozen_folds']))
    validate(r,c,pack);r['declared_complete']=True;progress();a=r['analysis']
    return dict(adapter='seed_sequential_consistency_v1',study=r,curve=[],model=dict(schema='frozen_sequential_state_v1',folds=pack['frozen_folds']),
        metrics=dict(mse=a['curve_means']['consistency_selector'],baseline_mse=min(a['curve_means'][m] for m in ('constant_damping','replay','bounded_fixed'))),
        resources=resources(time.process_time()),runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1))


def validate_output(output,c,caps,pack):
    r=output['study'];validate(r,c,pack);w=output['resources'];expected=resources(0)
    if output['adapter']!='seed_sequential_consistency_v1' or r['declared_complete'] is not True:raise ValueError('incomplete_sequential_execution')
    if output['model']!=dict(schema='frozen_sequential_state_v1',folds=pack['frozen_folds']):raise ValueError('changed_frozen_models')
    if set(w)!=set(expected) or any(type(w[k]) is not int or w[k]!=v for k,v in expected.items() if k!='cpu_s'):raise ValueError('sequential_resource_grid')
    if not finite(w['cpu_s']) or not 0<=w['cpu_s']<=caps['cpu_s'] or w['updates']>caps['updates']:raise ValueError('sequential_caps')
    for key,n in dict(old_anchor_initial_solves=108,cumulative_solves=576,consistency_predictor_calls=96,
                      prefix_predictor_calls=96,sequential_features=96,constant_scalar_reads=36).items():
        if r['update_work'].get(key)!=n:raise ValueError('actual_sequential_work')
    return True


def saved_replay(root):
    c=json.loads((root/'configs/seed_sequential_consistency.json').read_text());r=json.loads((root/'artifacts/seed_sequential_consistency.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_sequential_execution')
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_sequential_adaptation',status=h['status'],failure=h['failure'],wall_s=h['wall_s'],
        memory_mb=h['peak_sampled_rss_mb'],revision=r['execution_sha'],metrics=None,curve=[],resources=r['resources'],
        model_sha256=r['frozen_after_sha256'],study=None,sequential_consistency=r['analysis'])
