"""Small source-only update-strength test over the existing cumulative solve.

Reuses PlasticityController's scalar logits, fit_source, cross-fit preparation,
trajectory audit and EXPERIMENTAL host. No runtime learner is promoted here.
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
from . import update_diagnosis as prior

METHODS=['learned_gate','constant_gate','fixed_cumulative','replay','fixed_bounded','none']


def config_check(c):
    if (c['schema']!='seed_update_gate_v1' or c['methods']!=METHODS or
        c['outer_seeds']!=[7201,7202,7203] or c['fold_count']!=4 or
        c['tasks']!={'train':list(range(95000000,95110001,10000))} or
        c['prefixes']!=list(range(9)) or c['curve_budgets']!=[1,2,4,8]):
        raise ValueError('locked_gate_grid')
    expected=dict(ridge=.1,meta_updates=64,meta_lr=.01,retention_weight=.5,
                  minimum_fraction=.05,retention_excess=.01,max_wall_s=60,max_outer_updates=1536,
                  gate_intercept=.5,gate_slope=.25)
    if any(type(c[k]) not in (int,float) or c[k]!=v for k,v in expected.items()):raise ValueError('locked_gate_recipe')
    if c['max_wall_s']>c['carried_remaining_s'] or abs(c['carried_used_s']+c['carried_remaining_s']-3600)>1e-8:
        raise ValueError('gate_carried_budget')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=1536)


def source_pack(root,c):
    config_check(c);raw=(root/c['source_plan']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=c['source_plan_sha256']:raise ValueError('source_plan_hash')
    return dict(tasks=prior.source_pack(root,json.loads(raw))['tasks'])


def factory(seed,static):
    from .nonlinear_learning import controller
    return controller(seed,static,width=1)


def gate_value(model,context):
    """Exact retain/full-update endpoints; only the four observed inputs enter."""
    return (.5+.25*model.logits(context).squeeze()).clamp(0,1)


def step(initial,previous,x,y,anchors,old_y,seen_x,seen_y,model,ridge=.1,trace=None):
    import torch
    from . import learning_benchmark as lb
    from .plasticity import context
    c=context(previous,x,y,anchors)
    lb.count('gate_forwards')
    g=gate_value(model,c)
    proposal=cum.posterior(initial,torch.cat((anchors,seen_x)),torch.cat((old_y,seen_y)),torch.ones_like(initial),ridge)
    theta=previous+g*(proposal-previous)
    if trace is not None:
        trace.append(dict(gate=float(g.detach()),gate_context=c.tolist(),proposal=proposal.detach().tolist()))
    return theta


def curve(task,model,method,check=lambda:None):
    from . import learning_benchmark as lb
    theta=lb.initial(task).detach();initial=theta.clone();rows=[];snapshots={}
    for i,(x,y) in enumerate(zip(task.support_x,task.support_y),1):
        check();theta=step(initial,theta,x,y,task.old_x,task.old_y,task.support_x[:i],task.support_y[:i],model)
        if i in (1,2,4,8):
            error=(task.query_x@theta-task.query_y).square().mean()
            forgetting=(task.retention_x@theta-task.retention_y).square().mean()-(task.retention_x@initial-task.retention_y).square().mean()
            rows.append((i,error,forgetting));snapshots[i]=theta.detach().clone()
    return rows,snapshots


def updater(trace):
    initial=None
    def apply(previous,x,y,anchors,old_y,seen_x,seen_y,model,method):
        nonlocal initial
        if initial is None:initial=previous.detach().clone()
        return step(initial,previous,x,y,anchors,old_y,seen_x,seen_y,model,trace=trace)
    return apply


def summarize(rows,c):
    return cum.summarize(rows,c,methods=METHODS,learner='learned_gate',static='constant_gate')


def validate(r,c,pack):
    cum.validate(r,c,pack,config_fn=config_check,methods=METHODS,learner='learned_gate',static='constant_gate',width=1)
    validate_traces(r,pack)
    return True


def validate_traces(r,pack):
    """Independent saved-vector arithmetic; no fitting, Torch or query feedback."""
    c=r['config']
    tasks={str(t['seed']):t['arrays'] for t in pack['tasks']}
    for fold in r['folds'].values():
        scale=fold['scale']
        for seed,models in fold['models'].items():
            for task_id in map(str,fold['excluded_ids']):
                raw=tasks[task_id];x=[[a/b for a,b in zip(row,scale)] for row in raw['support_x']]
                anchors=[[a/b for a,b in zip(row,scale)] for row in raw['old_x']]
                for method in METHODS[:2]:
                    weights=models[method]['weights'];states=r['rows'][seed][task_id][method]
                    initial=states[0]['theta']
                    if any(k in states[0] for k in ('gate','gate_context','proposal')):raise ValueError('zero_prefix_has_no_gate')
                    for p,row in enumerate(states[1:],1):
                        before=states[p-1]['theta'];proposal=row['proposal'];ctx=row['gate_context'];g=row['gate']
                        if len(proposal)!=33 or len(ctx)!=4 or any(not finite(v) for v in proposal+ctx+[g]) or not 0<=g<=1:
                            raise ValueError('finite_gate_trace')
                        expected=[min(4,abs(raw['support_y'][p-1]-sum(a*b for a,b in zip(x[p-1],before))))/4,
                            len(anchors)/16,min(1,min(st.mean((a-b)**2 for a,b in zip(anchor,x[p-1])) for anchor in anchors)),0.]
                        if any(abs(a-b)>2e-6 for a,b in zip(ctx,expected)):raise ValueError('observed_only_gate_context')
                        fitted=max(0,min(1,.5+.25*(sum(a*b for a,b in zip(weights['logits.weight'][0],ctx))+weights['logits.bias'][0])))
                        if abs(g-fitted)>2e-6 or any(abs(t-(b+g*(v-b)))>2e-6 for t,b,v in zip(row['theta'],before,proposal)):
                            raise ValueError('gate_update_arithmetic')
                        # Verify the proposal's normal equations without importing a neural runtime.
                        bx=anchors+x[:p];by=raw['old_y']+raw['support_y'][:p]
                        residual=[y-sum(a*b for a,b in zip(v,proposal)) for v,y in zip(bx,by)]
                        if max(abs(c['ridge']*(v-b)-sum(u[j]*e for u,e in zip(bx,residual))) for j,(v,b) in enumerate(zip(proposal,initial)))>2e-5:
                            raise ValueError('fixed_cumulative_proposal_arithmetic')
    return True


def resources(cpu_s):
    return dict(updates=1536,real_steps=0,imagined_transitions=0,world_model_forwards=0,
        source_support_examples=12288,source_query_examples=165888,source_retention_examples=165888,
        cumulative_train_support_rows=55296,cumulative_train_anchor_rows=49152,
        evaluation_query_examples=52488,evaluation_retention_examples=52488,gate_forwards=12864,
        cumulative_solves=13152,evaluation_update_calls=1728,trained_rules=24,stored_rule_parameters=120,cpu_s=cpu_s)


def run(request):
    import torch
    from . import learning_benchmark as lb
    from .nonlinear_learning import fit_source
    from .bounded_correction import limiter
    c=request['inputs']['study_config'];config_check(c);pack=request['inputs']['source_pack']
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True);lb.WORK.clear();start=time.monotonic()
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('gate_wall_cap')
    r=dict(config=c,source_pack_sha256=digest(pack),folds={},rows={str(s):{} for s in c['outer_seeds']},
        declared_complete=False,frozen_during_evaluation=True)
    def progress():
        r.update(wall_s=time.monotonic()-start,update_work=dict(lb.WORK))
        p=Path('progress.tmp');p.write_text(json.dumps(r,allow_nan=False));p.replace('progress.json')
    progress()
    for fold in range(4):
        train,held,meta=cum.prepare_fold(pack,c,fold);meta['models']={};r['folds'][str(fold)]=meta
        for seed in c['outer_seeds']:
            models={};arms={};meta['models'][str(seed)]=arms
            for static,method in ((False,'learned_gate'),(True,'constant_gate')):
                model,info=fit_source(train,seed+100*fold,static,c,check,curve_fn=curve,model_factory=factory)
                info['provenance']=dict(config_sha256=digest(c),fold=fold,seed=seed,source_sha256=meta['source_sha256'],source_only=True)
                path=Path(f'rule-{fold}-{seed}-{method}.json')
                info.update(checkpoint=path.name,sha256=model.export(path,info['provenance']),weights={k:v.tolist() for k,v in model.state_dict().items()})
                arms[method]=info;models[method]=model;progress()
            before={m:digest({k:v.tolist() for k,v in model.state_dict().items()}) for m,model in models.items()}
            for task_id,task in held.items():
                cell={};r['rows'][str(seed)][str(task_id)]=cell
                for method in METHODS:
                    if method in METHODS[:2]:
                        trace=[];cell[method]=prior.trajectory(task,models[method],'learned',check,update_fn=updater(trace))
                        for row,extra in zip(cell[method][1:],trace):row.update(extra)
                    elif method=='fixed_cumulative':cell[method]=prior.trajectory(task,None,'fixed',check,update_fn=cum.cumulative_updater(c['ridge']))
                    elif method=='fixed_bounded':cell[method]=prior.trajectory(task,None,'fixed',check,update_fn=limiter(meta['tau'],[]))
                    else:cell[method]=prior.trajectory(task,None,method,check)
            r['frozen_during_evaluation'] &= all(digest({k:v.tolist() for k,v in model.state_dict().items()})==before[m] for m,model in models.items())
            progress()
    r.update(analysis=summarize(r['rows'],c),update_work=dict(lb.WORK),wall_s=time.monotonic()-start)
    validate(r,c,pack);r['declared_complete']=True;progress();a=r['analysis']
    return dict(adapter='seed_update_gate_v1',study=r,curve=[],model=dict(schema='source_crossfit_gate_v1',folds=r['folds']),
        metrics=dict(mse=a['curve_means']['learned_gate'],baseline_mse=min(a['curve_means'][m] for m in METHODS[1:]),
            worst_error_increase=a['final_retention']['learned_gate']-a['final_retention']['fixed_cumulative']),
        runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1),resources=resources(time.process_time()))


def validate_output(output,c,caps,pack):
    r=output['study'];validate(r,c,pack);w=output['resources']
    if output['adapter']!='seed_update_gate_v1' or r['declared_complete'] is not True:raise ValueError('incomplete_gate_run')
    if output['model']!=dict(schema='source_crossfit_gate_v1',folds=r['folds']):raise ValueError('gate_model_export')
    expected=resources(0)
    if set(w)!=set(expected) or any(type(w[k]) is not int or w[k]!=v for k,v in expected.items() if k!='cpu_s'):
        raise ValueError('gate_resource_grid')
    if not finite(w['cpu_s']) or not 0<=w['cpu_s']<=caps['cpu_s'] or w['updates']>caps['updates']:raise ValueError('gate_execution_cap')
    if r['update_work'].get('gate_forwards')!=12864 or r['update_work'].get('cumulative_solves')!=13152:
        raise ValueError('actual_gate_work_mismatch')
    return True


def saved_replay(root):
    c=json.loads((root/'configs/seed_update_gate.json').read_text());r=json.loads((root/'artifacts/seed_update_gate.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_gate_evidence')
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_update_gate',status=h['status'],failure=h['failure'],
        wall_s=h['wall_s'],memory_mb=h['peak_sampled_rss_mb'],revision=r['execution_sha'],metrics=None,curve=[],
        resources=r['resources'],model_sha256=digest({f:v['models'] for f,v in r['folds'].items()}),study=None,update_gate=r['analysis'])
