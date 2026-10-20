"""Input-only question choice over the existing source bank and frozen learner.

Reuse sequential source provenance, cumulative posterior, anchor initialization,
paired task intervals and the EXPERIMENTAL host. No new learner or world model.
The selector has no label argument; fitting has no query/retention argument.
"""
import hashlib
import json
from pathlib import Path
import random
import statistics as st
import sys
import time

from nexus.evolution1.catalogue import digest
from .grounded_audit import finite
from . import sequential_consistency as seq
from . import cumulative_learning as cum
from . import update_diagnosis as prior

METHODS=['informative','random','original_order']


def config_check(c):
    expected=dict(schema='seed_question_selection_v1',methods=METHODS,
        constant_seeds=[7201,7202,7203],question_seeds=list(range(8101,8111)),
        tasks={'train':list(range(95000000,95110001,10000))},fold_count=4,
        prefixes=list(range(9)),curve_budgets=[1,2,4,8],posterior_ridge=.1,
        minimum_fraction=.05,minimum_fold_wins=3,retention_excess=.01,
        max_wall_s=60,max_outer_updates=0)
    if any(type(c[k]) is not type(v) or c[k]!=v for k,v in expected.items()):
        raise ValueError('locked_question_recipe')
    for key in ('constant_seeds','question_seeds','prefixes','curve_budgets'):
        if any(type(v) is not int for v in c[key]):raise ValueError('typed_question_grid')
    if any(not finite(c[k]) for k in ('carried_used_s','carried_remaining_s')) or c['max_wall_s']>c['carried_remaining_s'] or abs(c['carried_used_s']+c['carried_remaining_s']-3600)>1e-8:
        raise ValueError('question_carried_budget')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=0)


def source_pack(root,c):
    config_check(c);raw=(root/c['parent']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=c['parent_sha256']:raise ValueError('question_parent_hash')
    parent=json.loads(raw)
    if parent['declared_complete'] is not True:raise ValueError('incomplete_question_parent')
    source=seq.source_pack(root,parent['config'])
    if digest(source)!=parent['source_pack_sha256']:raise ValueError('question_source_hash')
    # Previous query results never cross into the worker or selector.
    return dict(source=source,parent_config=parent['config'],parent_sha256=c['parent_sha256'])


def validate_pack(pack,c):
    if set(pack)!={'source','parent_config','parent_sha256'} or pack['parent_sha256']!=c['parent_sha256']:
        raise ValueError('question_source_only_payload')
    seq.validate_pack(pack['source'],pack['parent_config'])
    if pack['parent_config']['tasks']!=c['tasks']:raise ValueError('question_task_provenance')
    for t in pack['source']['tasks']:
        a=t['arrays']
        shapes={'support_x':(8,33),'support_y':(8,),'old_x':(4,33),'old_y':(4,),
            'query_x':(27,33),'query_y':(27,),'retention_x':(27,33),'retention_y':(27,)}
        if set(a)!=set(shapes) or digest(a)!=t['array_sha256']:raise ValueError('question_array_hash')
        for k,shape in shapes.items():
            if type(a[k]) is not list or len(a[k])!=shape[0]:raise ValueError('question_array_shape')
            if len(shape)==2:
                if any(type(x) is not list or len(x)!=shape[1] for x in a[k]):raise ValueError('question_feature_shape')
                values=[v for x in a[k] for v in x]
            else:values=a[k]
            if any(not finite(v) for v in values):raise ValueError('finite_question_arrays')
        if len({digest(x) for x in a['support_x']})!=8:raise ValueError('duplicate_question_inputs')
        if set(map(digest,a['support_x'])) & set(map(digest,a['query_x']+a['retention_x'])):
            raise ValueError('question_assessment_input_overlap')
    return True


class LabelOracle:
    """Evaluator-owned reveal boundary. No query data, repeated or free labels."""
    def __init__(self,labels,budget):
        if type(budget) is not int or not 0<=budget<=len(labels):raise ValueError('label_budget')
        self.__labels=tuple(labels);self.budget=budget;self.revealed=[]

    def reveal(self,index):
        if type(index) is not int or not 0<=index<len(self.__labels):raise ValueError('label_index')
        if len(self.revealed)>=self.budget or index in self.revealed:raise ValueError('label_budget_or_duplicate')
        self.revealed.append(index)
        return self.__labels[index]


def variance_scores(pool,anchors,selected):
    """Linear input variance only. Float64, fixed ridge; never sees outcomes."""
    import torch
    if (pool.ndim!=2 or anchors.ndim!=2 or anchors.shape[1]!=pool.shape[1] or
        len(set(selected))!=len(selected) or any(type(i) is not int or not 0<=i<len(pool) for i in selected)):
        raise ValueError('variance_input_shape')
    if not torch.isfinite(pool).all() or not torch.isfinite(anchors).all():raise ValueError('finite_variance_inputs')
    x=torch.cat((anchors.double(),pool[selected].double()))
    cross=x@pool.double().T
    solved=torch.linalg.solve(.1*torch.eye(len(x),dtype=torch.float64)+x@x.T,cross)
    scores=(pool.double().square().sum(1)-(cross*solved).sum(0))/.1
    if not torch.isfinite(scores).all() or float(scores.min()) < -1e-8:raise ValueError('invalid_input_variance')
    return scores.clamp(min=0).tolist()


def orders(pool,anchors,task_id,c,check=lambda:None):
    selected=[];trace=[]
    for _ in range(8):
        check();scores=variance_scores(pool,anchors,selected)
        scores=[None if i in selected else v for i,v in enumerate(scores)]
        index=max((i for i in range(8) if i not in selected),key=lambda i:scores[i])
        trace.append(dict(index=index,scores=scores));selected.append(index)
    random_orders={}
    for seed in c['question_seeds']:
        order=list(range(8));random.Random(seed+task_id).shuffle(order)
        random_orders[str(seed)]=dict(indices=order,variance_trace=None)
    return dict(informative={'fixed':dict(indices=selected,variance_trace=trace)},
        random=random_orders,original_order={'fixed':dict(indices=list(range(8)),variance_trace=None)})


def damped_step(initial,previous,anchors,old_y,seen_x,seen_y,g):
    """Original fixed learner expression; observed labels only, no evaluation."""
    import torch
    proposal=cum.posterior(initial,torch.cat((anchors,seen_x)),
        torch.cat((old_y,seen_y)),torch.ones_like(initial))
    theta=proposal if g==1 else previous if g==0 else previous+g*(proposal-previous)
    return theta,proposal


def fit_path(pool,anchors,old_y,oracle,order,g,check=lambda:None):
    """Only requested teaching and known anchors. No assessment tensors here."""
    import torch
    from . import learning_benchmark as lb
    if type(g) not in (float,int) or not finite(g) or not 0<=g<=1:raise ValueError('fixed_damping')
    if sorted(order)!=list(range(len(pool))):raise ValueError('complete_question_order')
    initial=lb.initial(type('Anchors',(),dict(old_x=anchors,old_y=old_y))()).detach()
    theta=initial.clone();rows=[dict(prefix=0,theta=theta.tolist(),proposal=None,index=None,
        support_error_before=None,support_error_after=None)]
    xs=[];ys=[]
    for p,index in enumerate(order,1):
        check();x=pool[index];y=oracle.reveal(index);before=float(x@theta)
        xs.append(x);ys.append(y)
        theta,proposal=damped_step(initial,theta,anchors,old_y,torch.stack(xs),torch.tensor(ys,dtype=pool.dtype),g)
        rows.append(dict(prefix=p,index=index,theta=theta.tolist(),proposal=proposal.tolist(),
            support_error_before=(float(y)-before)**2,support_error_after=(float(y)-float(x@theta))**2))
    return rows


def assess(path,query_x,query_y,retention_x,retention_y,*,blocks=False):
    """Evaluator-only, called AFTER the whole fitted path has been frozen."""
    import torch
    for row in path:
        theta=torch.tensor(row['theta'],dtype=query_x.dtype)
        errors=dict(query=(query_x@theta-query_y).square(),retention=(retention_x@theta-retention_y).square())
        row.update({role+'_mse':float(error.mean()) for role,error in errors.items()})
        if blocks:
            if any(len(error)!=27 for error in errors.values()):raise ValueError('three_nine_action_query_blocks')
            row.update({role+'_blocks':[float(error[i:i+9].mean()) for i in (0,9,18)] for role,error in errors.items()})
    return path


def order_ids(method,c):return list(map(str,c['question_seeds'])) if method=='random' else ['fixed']


def summarize(rows,c):
    def value(t,m,key='query_mse',budgets=None):
        return st.mean(path[p][key] for replicas in rows[str(t)][m].values() for path in replicas.values() for p in (budgets or c['curve_budgets']))
    tasks=c['tasks']['train'];per={str(t):{m:value(t,m) for m in METHODS} for t in tasks}
    means={m:st.mean(v[m] for v in per.values()) for m in METHODS}
    contrast=prior.paired([per[str(t)]['random']-per[str(t)]['informative'] for t in tasks])
    retention={m:st.mean(value(t,m,'retention_mse',[8]) for t in tasks) for m in METHODS}
    folds={str(f):{m:st.mean(per[str(t)][m] for t in cum.partition(c,f)[1]) for m in METHODS} for f in range(4)}
    wins=sum(v['informative']<v['random'] for v in folds.values())
    improved=contrast['mean']>=c['minimum_fraction']*means['random'] and contrast['ci95'][0]>0
    retained=retention['informative']<=retention['random']+c['retention_excess']
    return dict(curve_means=means,primary_contrast=contrast,per_task=per,per_fold=folds,fold_wins=wins,
        improvement_pass=improved,retention_pass=retained,source_screen_pass=improved and retained and wins>=c['minimum_fold_wins'],
        final_retention=retention,
        forgetting={m:st.mean(value(t,m,'retention_mse',[8])-value(t,m,'retention_mse',[0]) for t in tasks) for m in METHODS},
        query_curves={m:{str(p):st.mean(value(t,m,budgets=[p]) for t in tasks) for p in c['prefixes']} for m in METHODS},
        per_budget_contrasts={str(p):prior.paired([value(t,'random',budgets=[p])-value(t,'informative',budgets=[p]) for t in tasks]) for p in c['curve_budgets']},
        fresh_validation=False,runtime_promotion=False,independent_pretrained_cores=1,
        uncertainty='12 reused source task clusters; damping fits and random orders averaged inside tasks; overlapping folds, one core. Exploratory unadjusted intervals.',
        learned_question_policy=False,learning_to_learn_established=False)


def resources(cpu_s):
    return dict(updates=0,real_steps=0,imagined_transitions=0,world_model_forwards=0,
        trajectories=432,inner_updates=3456,initial_solves=432,cumulative_solves=3456,
        variance_solves=96,candidate_variance_scores=768,available_candidate_scores=432,random_permutations=120,
        constant_scalar_reads=432,normalization_source_rows=432,
        observed_teaching_presentations=3456,unique_cached_teaching_labels=96,
        initial_anchor_rows=1728,cumulative_support_rows=15552,cumulative_anchor_rows=13824,
        evaluation_snapshots=3888,query_score_rows=104976,retention_score_rows=104976,cpu_s=cpu_s)


def validate(r,c,pack):
    """Stdlib-only grid/arithmetic audit. Expected cells come from locked c."""
    config_check(c);validate_pack(pack,c);source=pack['source']
    if r['config']!=c or r['source_pack_sha256']!=digest(pack) or r['frozen_before_sha256']!=digest(source['frozen_folds']) or r['frozen_after_sha256']!=r['frozen_before_sha256']:
        raise ValueError('question_frozen_provenance')
    if set(r['rows'])!=set(map(str,c['tasks']['train'])) or set(r['orders'])!=set(r['rows']):raise ValueError('question_task_grid')
    dot=lambda x,y:sum(a*b for a,b in zip(x,y))
    close=lambda a,b:finite(a) and finite(b) and abs(a-b)<2e-6
    lookup={t['seed']:t['arrays'] for t in source['tasks']}
    for f in range(4):
        meta=source['frozen_folds'][str(f)]
        for task in meta['excluded_ids']:
            a=lookup[task];cell=r['rows'][str(task)];selected=r['orders'][str(task)]
            if set(cell)!=set(METHODS) or set(selected)!=set(METHODS):raise ValueError('question_method_grid')
            sx=[[v/s for v,s in zip(x,meta['scale'])] for x in a['support_x']]
            ox=[[v/s for v,s in zip(x,meta['scale'])] for x in a['old_x']]
            for m in METHODS:
                if set(cell[m])!=set(order_ids(m,c)) or set(selected[m])!=set(order_ids(m,c)):raise ValueError('question_order_grid')
                for order_id,replicas in cell[m].items():
                    order=selected[m][order_id]['indices'];variance=selected[m][order_id]['variance_trace']
                    if sorted(order)!=list(range(8)) or any(type(i) is not int for i in order):raise ValueError('question_unique_budget')
                    if m=='random':
                        expected=list(range(8));random.Random(int(order_id)+task).shuffle(expected)
                        if order!=expected or variance is not None:raise ValueError('random_schedule_reproduction')
                    elif m=='original_order':
                        if order!=list(range(8)) or variance is not None:raise ValueError('original_schedule')
                    else:
                        if type(variance) is not list or len(variance)!=8:raise ValueError('variance_trace_grid')
                        for i,info in enumerate(variance):
                            scores=info['scores']
                            if len(scores)!=8 or info['index']!=order[i] or any(scores[j] is not None for j in order[:i]) or any(not finite(scores[j]) or scores[j]<0 for j in order[i:]):raise ValueError('variance_metric_grid')
                            if max(order[i:],key=lambda j:(scores[j],-j))!=order[i]:raise ValueError('maximum_variance_choice')
                    if set(replicas)!=set(map(str,c['constant_seeds'])):raise ValueError('question_damping_grid')
                    for rep,path in replicas.items():
                        if len(path)!=9 or [row['prefix'] for row in path]!=c['prefixes']:raise ValueError('question_prefix_grid')
                        initial=path[0]['theta'];old_res=[y-dot(x,initial) for x,y in zip(ox,a['old_y'])]
                        if len(initial)!=33 or max(abs(.01*v-sum(x[j]*e for x,e in zip(ox,old_res))) for j,v in enumerate(initial))>2e-5:raise ValueError('question_anchor_initial')
                        g=max(0,min(1,.5+.25*meta['constants'][rep]['weights']['logits.bias'][0]))
                        for p,row in enumerate(path):
                            if set(row)!={'prefix','index','theta','proposal','support_error_before','support_error_after','query_mse','retention_mse'} or type(row['prefix']) is not int or len(row['theta'])!=33 or any(not finite(v) for v in row['theta']):raise ValueError('question_snapshot_schema')
                            for role in ('query','retention'):
                                score=st.mean((dot([v/s for v,s in zip(x,meta['scale'])],row['theta'])-y)**2 for x,y in zip(a[role+'_x'],a[role+'_y']))
                                if not finite(row[role+'_mse']) or row[role+'_mse']<0 or not close(score,row[role+'_mse']):raise ValueError('question_evaluation_arithmetic')
                            if not p:
                                if any(row[k] is not None for k in ('index','proposal','support_error_before','support_error_after')):raise ValueError('question_empty_context')
                                continue
                            index=order[p-1];proposal=row['proposal'];before=path[p-1]['theta']
                            if row['index']!=index or type(row['index']) is not int or len(proposal)!=33 or any(not finite(v) for v in proposal):raise ValueError('question_reveal_identity')
                            bx=ox+[sx[i] for i in order[:p]];by=a['old_y']+[a['support_y'][i] for i in order[:p]]
                            residual=[y-dot(x,proposal) for x,y in zip(bx,by)]
                            if max(abs(.1*(v-b)-sum(x[j]*e for x,e in zip(bx,residual))) for j,(v,b) in enumerate(zip(proposal,initial)))>2e-5:raise ValueError('question_posterior_equation')
                            if any(not close(v,b+g*(q-b)) for v,b,q in zip(row['theta'],before,proposal)):raise ValueError('question_fixed_learner')
                            for name,theta in (('before',before),('after',row['theta'])):
                                if not close(row['support_error_'+name],(a['support_y'][index]-dot(sx[index],theta))**2):raise ValueError('question_support_loss')
    if r['analysis']!=summarize(r['rows'],c):raise ValueError('question_summary_arithmetic')
    if any(not finite(v) or v<0 for v in r['timing_s'].values()) or set(r['timing_s'])!={'selection','fitting','assessment'}:raise ValueError('question_timing')
    return True


def run(request):
    import torch
    from . import learning_benchmark as lb
    c=request['inputs']['study_config'];pack=request['inputs']['source_pack'];config_check(c);validate_pack(pack,c)
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True);lb.WORK.clear();start=time.monotonic()
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('question_wall_cap')
    r=dict(config=c,source_pack_sha256=digest(pack),rows={},orders={},declared_complete=False,
        timing_s=dict(selection=0.,fitting=0.,assessment=0.),frozen_before_sha256=digest(pack['source']['frozen_folds']))
    def progress():
        r.update(wall_s=time.monotonic()-start,update_work=dict(lb.WORK));p=Path('progress.tmp');p.write_text(json.dumps(r,allow_nan=False));p.replace('progress.json')
    progress()
    for f in range(4):
        _,held,pre=cum.prepare_fold(pack['source'],c,f,include_bound=False);meta=pack['source']['frozen_folds'][str(f)]
        if pre['scale']!=meta['scale']:raise ValueError('question_reproduced_scale')
        for task_id,task in held.items():
            tick=time.monotonic();selected=orders(task.support_x,task.old_x,task_id,c,check)
            r['timing_s']['selection']+=time.monotonic()-tick;r['orders'][str(task_id)]=selected
            cell={};r['rows'][str(task_id)]=cell
            for m in METHODS:
                cell[m]={}
                for order_id,info in selected[m].items():
                    cell[m][order_id]={}
                    for seed in c['constant_seeds']:
                        g=float((.5+.25*torch.tensor(meta['constants'][str(seed)]['weights']['logits.bias'][0])).clamp(0,1))
                        tick=time.monotonic()
                        with torch.no_grad():path=fit_path(task.support_x,task.old_x,task.old_y,LabelOracle(task.support_y.tolist(),8),info['indices'],g,check)
                        r['timing_s']['fitting']+=time.monotonic()-tick;tick=time.monotonic()
                        cell[m][order_id][str(seed)]=assess(path,task.query_x,task.query_y,task.retention_x,task.retention_y)
                        r['timing_s']['assessment']+=time.monotonic()-tick
            progress()
    r.update(frozen_after_sha256=digest(pack['source']['frozen_folds']),analysis=summarize(r['rows'],c))
    validate(r,c,pack);r['declared_complete']=True;progress()
    return dict(adapter='seed_question_selection_v1',study=r,curve=[],
        model=dict(schema='unchanged_question_learner_v1',frozen_sha256=r['frozen_after_sha256']),
        metrics=dict(mse=r['analysis']['curve_means']['informative'],baseline_mse=r['analysis']['curve_means']['random']),
        resources=resources(time.process_time()),runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1))


def validate_output(output,c,caps,pack):
    r=output['study'];validate(r,c,pack);w=output['resources'];expected=resources(0)
    if output['adapter']!='seed_question_selection_v1' or r['declared_complete'] is not True:raise ValueError('incomplete_question_execution')
    if output['model']!=dict(schema='unchanged_question_learner_v1',frozen_sha256=r['frozen_after_sha256']):raise ValueError('question_changed_learner')
    if set(w)!=set(expected) or any(type(w[k]) is not int or w[k]!=v for k,v in expected.items() if k!='cpu_s'):raise ValueError('question_resource_grid')
    if not finite(w['cpu_s']) or not 0<=w['cpu_s']<=caps['cpu_s'] or caps['updates']!=0 or r['update_work']!={'old_anchor_initial_solves':432,'cumulative_solves':3456}:raise ValueError('question_actual_work')
    return True


def saved_replay(root):
    c=json.loads((root/'configs/seed_question_selection.json').read_text());r=json.loads((root/'artifacts/seed_question_selection.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_question_execution')
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_question_selection',status=h['status'],failure=h['failure'],
        wall_s=h['wall_s'],memory_mb=h['peak_sampled_rss_mb'],revision=r['execution_sha'],
        metrics=dict(mse=r['analysis']['curve_means']['informative'],baseline_mse=r['analysis']['curve_means']['random']),
        curve=[],resources=r['resources'],model_sha256=r['frozen_after_sha256'],question_selection=r['analysis'])
