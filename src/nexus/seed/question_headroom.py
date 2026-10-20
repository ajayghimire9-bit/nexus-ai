"""Evaluator-only question-pool audit. No new selector or learner.

Only saved SOURCE arrays/reference states enter this adapter. Counterfactuals
reuse the fixed question learner; oracle choices are computed after ALL fits.
"""
import hashlib
import json
from pathlib import Path
import statistics as st
import sys
import time

from nexus.evolution1.catalogue import digest
from .grounded_audit import finite
from . import question_selection as questions
from . import cumulative_learning as cum
from . import update_diagnosis as prior

COMPARISONS=['variance','uniform','keep','query_oracle','cross_block']


def config_check(c):
    expected=dict(schema='seed_question_headroom_v1',tasks={'train':list(range(95000000,95110001,10000))},
        constant_seeds=[7201,7202,7203],budgets=[1,2,4,8],fold_count=4,
        query_blocks=[list(range(i,i+9)) for i in (0,9,18)],posterior_ridge=.1,
        minimum_fraction=.05,minimum_task_wins=8,retention_excess=.01,max_wall_s=30,max_outer_updates=0)
    if any(type(c[k]) is not type(v) or c[k]!=v for k,v in expected.items()):raise ValueError('locked_headroom_recipe')
    for values in [c['constant_seeds'],c['budgets'],c['tasks']['train']]+c['query_blocks']:
        if any(type(i) is not int for i in values):raise ValueError('typed_headroom_grid')
    if any(not finite(c[k]) or c[k]<0 for k in ('carried_used_s','carried_remaining_s')) or c['max_wall_s']>c['carried_remaining_s'] or abs(c['carried_used_s']+c['carried_remaining_s']-3600)>1e-8:
        raise ValueError('headroom_carried_budget')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=0)


def source_pack(root,c):
    config_check(c);objects={}
    for key in ('parent','source_data'):
        raw=(root/c[key]).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=c[key+'_sha256']:raise ValueError('headroom_file_hash: '+key)
        objects[key]=json.loads(raw)
    parent=objects['parent'];qc=parent['config'];qpack=questions.source_pack(root,qc)
    if parent['declared_complete'] is not True:raise ValueError('incomplete_headroom_parent')
    questions.validate(parent,qc,qpack)
    raw_tasks=objects['source_data']['tasks']['train'];blocks={}
    if [t['seed'] for t in raw_tasks]!=c['tasks']['train']:raise ValueError('source_record_task_grid')
    lookup={t['seed']:t for t in qpack['source']['tasks']}
    for t in raw_tasks:
        if digest(t['records'])!=t['record_sha256'] or t['arrays']!=lookup[t['seed']]['arrays']:
            raise ValueError('source_record_array_provenance')
        records=t['records'];seeds=[row['seed'] for role in ('support','old','query','retention') for row in records[role]]
        if len(seeds)!=len(set(seeds)):raise ValueError('source_episode_seed_overlap')
        for role in ('query','retention'):
            if len(records[role])!=3 or any([a['action'] for a in row['outcomes']]!=list(range(9)) for row in records[role]):
                raise ValueError('source_query_block_actions')
        blocks[str(t['seed'])]=dict(record_sha256=t['record_sha256'],episode_seeds={role:[v['seed'] for v in records[role]] for role in ('support','old','query','retention')})
    pack=dict(questions=qpack,question_config=qc,parent_sha256=c['parent_sha256'],source_data_sha256=c['source_data_sha256'],
        reference={str(t):dict(order=parent['orders'][str(t)]['informative']['fixed']['indices'],paths=parent['rows'][str(t)]['informative']['fixed']) for t in c['tasks']['train']},
        query_records=blocks)
    validate_pack(pack,c);return pack


def validate_pack(pack,c):
    if set(pack)!={'questions','question_config','parent_sha256','source_data_sha256','reference','query_records'} or pack['parent_sha256']!=c['parent_sha256'] or pack['source_data_sha256']!=c['source_data_sha256']:
        raise ValueError('headroom_source_payload')
    questions.validate_pack(pack['questions'],pack['question_config'])
    expected=set(map(str,c['tasks']['train']))
    if set(pack['reference'])!=expected or set(pack['query_records'])!=expected:raise ValueError('headroom_reference_grid')
    all_collection_seeds=[]
    for tid,ref in pack['reference'].items():
        if set(ref)!={'order','paths'} or sorted(ref['order'])!=list(range(8)) or any(type(i) is not int for i in ref['order']):raise ValueError('headroom_frozen_order')
        if set(ref['paths'])!=set(map(str,c['constant_seeds'])):raise ValueError('headroom_reference_fit_grid')
        for path in ref['paths'].values():
            if len(path)!=9 or [r['prefix'] for r in path]!=list(range(9)):raise ValueError('headroom_reference_prefix_grid')
            for p,row in enumerate(path):
                if len(row['theta'])!=33 or any(not finite(v) for v in row['theta']) or row['index']!=(ref['order'][p-1] if p else None):raise ValueError('headroom_reference_theta')
        record=pack['query_records'][tid];seeds=record['episode_seeds']
        if set(record)!={'record_sha256','episode_seeds'} or type(record['record_sha256']) is not str or len(record['record_sha256'])!=64 or set(seeds)!={'support','old','query','retention'} or [len(seeds[k]) for k in ('support','old','query','retention')]!=[8,4,3,3]:raise ValueError('headroom_query_record_grid')
        values=sum(seeds.values(),[])
        if any(type(i) is not int for i in values) or len(values)!=len(set(values)):raise ValueError('headroom_query_seed_separation')
        all_collection_seeds.extend(values)
    if len(all_collection_seeds)!=len(set(all_collection_seeds)):raise ValueError('headroom_cross_task_seed_overlap')
    return True


def counterfactual(initial,previous,anchors,old_y,seen_x,seen_y,candidate_x,candidate_y,g):
    """Only permitted teaching reaches the shared fixed learner, no queries."""
    import torch
    x=torch.cat((seen_x,candidate_x[None]));y=torch.cat((seen_y,candidate_y[None]))
    theta,proposal=questions.damped_step(initial,previous,anchors,old_y,x,y,g)
    return dict(theta=theta.tolist(),proposal=proposal.tolist(),
        support_error_before=float((candidate_y-candidate_x@previous).square()),
        support_error_after=float((candidate_y-candidate_x@theta).square()))


def choose_block(block_errors,held_block):
    """Evaluator-only selection excludes the omitted query block's outcomes."""
    if type(held_block) is not int or held_block not in (0,1,2):raise ValueError('query_block_index')
    return min(sorted(block_errors,key=int),key=lambda k:st.mean(v for i,v in enumerate(block_errors[k]) if i!=held_block))


def cell_analysis(cell,c):
    seeds=list(map(str,c['constant_seeds']));candidates=cell['candidates']
    def avg(candidate,metric):return st.mean(candidates[candidate][seed][metric] for seed in seeds)
    block_errors={i:[st.mean(candidates[i][seed]['query_blocks'][b] for seed in seeds) for b in range(3)] for i in candidates}
    oracle=min(sorted(candidates,key=int),key=lambda k:avg(k,'query_mse'));variance=str(cell['variance_index'])
    cross=[choose_block(block_errors,b) for b in range(3)]
    query=dict(variance=avg(variance,'query_mse'),uniform=st.mean(avg(i,'query_mse') for i in candidates),
        keep=st.mean(cell['before'][s]['query_mse'] for s in seeds),query_oracle=avg(oracle,'query_mse'),
        cross_block=st.mean(block_errors[i][b] for b,i in enumerate(cross)))
    retention=dict(variance=avg(variance,'retention_mse'),uniform=st.mean(avg(i,'retention_mse') for i in candidates),
        keep=st.mean(cell['before'][s]['retention_mse'] for s in seeds),query_oracle=avg(oracle,'retention_mse'),
        cross_block=st.mean(avg(i,'retention_mse') for i in cross))
    return dict(query=query,retention=retention,oracle_index=int(oracle),cross_block_indices=list(map(int,cross)),
        useful_fraction=st.mean(float(avg(i,'query_mse')<query['keep']) for i in candidates),
        variance_gain=query['keep']-query['variance'],best_gain=query['keep']-query['query_oracle'],
        oracle_regret=query['variance']-query['query_oracle'],
        candidate_query_mse={i:avg(i,'query_mse') for i in candidates})


def summarize(rows,c):
    cells={str(t):{str(b):cell_analysis(rows[str(t)][str(b)],c) for b in c['budgets']} for t in c['tasks']['train']}
    def per_task(t,key,m):return st.mean(cells[str(t)][str(b)][key][m] for b in c['budgets'])
    per={str(t):{m:per_task(t,'query',m) for m in COMPARISONS} for t in c['tasks']['train']}
    means={m:st.mean(v[m] for v in per.values()) for m in COMPARISONS}
    ret={m:st.mean(per_task(t,'retention',m) for t in c['tasks']['train']) for m in COMPARISONS}
    contrast=lambda a,b:prior.paired([per[str(t)][a]-per[str(t)][b] for t in c['tasks']['train']])
    oracle_wins=sum(v['query_oracle']<v['keep'] for v in per.values());cross_wins=sum(v['cross_block']<v['keep'] for v in per.values())
    oracle_screen=(all(means['query_oracle']<=(1-c['minimum_fraction'])*means[m] for m in ('variance','uniform','keep')) and
        oracle_wins>=c['minimum_task_wins'] and ret['query_oracle']<=ret['variance']+c['retention_excess'])
    cross_screen=(all(means['cross_block']<=(1-c['minimum_fraction'])*means[m] for m in ('variance','keep')) and
        cross_wins>=c['minimum_task_wins'] and ret['cross_block']<=ret['variance']+c['retention_excess'])
    return dict(label='useful_questions_missed' if oracle_screen else 'practical_headroom_not_demonstrated',
        oracle_headroom_pass=oracle_screen,cross_state_pass=cross_screen,curve_means=means,per_task=per,
        primary_contrast=contrast('variance','query_oracle'),oracle_keep_contrast=contrast('keep','query_oracle'),
        cross_variance_contrast=contrast('variance','cross_block'),cross_keep_contrast=contrast('keep','cross_block'),
        retention_means=ret,oracle_task_wins=oracle_wins,cross_task_wins=cross_wins,cells=cells,
        per_fold={str(f):{m:st.mean(per[str(t)][m] for t in cum.partition(c,f)[1]) for m in COMPARISONS} for f in range(4)},
        query_curves={m:{str(b):st.mean(cells[str(t)][str(b)]['query'][m] for t in c['tasks']['train']) for b in c['budgets']} for m in COMPARISONS},
        uncertainty='12 reused source task clusters; three damping fits averaged inside tasks; one core, overlapping fits. Oracle nonnegative regret is by construction, not confirmation.',
        fresh_validation=False,runtime_promotion=False,learning_to_learn_established=False,
        oracle_is_deployable=False,independent_pretrained_cores=1)


def resources(cpu_s):
    return dict(updates=0,real_steps=0,imagined_transitions=0,world_model_forwards=0,
        counterfactual_updates=756,cumulative_solves=756,cumulative_support_rows=1800,cumulative_anchor_rows=3024,
        keep_states=144,evaluated_states=900,query_score_rows=24300,retention_score_rows=24300,
        unique_cached_teaching_labels=96,cached_reference_snapshots=324,constant_scalar_reads=36,
        initial_solves=0,variance_solves=0,normalization_fit_rows=0,cpu_s=cpu_s)


def validate(r,c,pack):
    """No numerical dependencies. Validate the raw grid before summarizing."""
    config_check(c);validate_pack(pack,c)
    frozen=digest(pack['questions']['source']['frozen_folds'])
    if r['config']!=c or r['source_pack_sha256']!=digest(pack) or r['frozen_before_sha256']!=frozen or r['frozen_after_sha256']!=frozen or r['reference_before_sha256']!=digest(pack['reference']) or r['reference_after_sha256']!=r['reference_before_sha256']:
        raise ValueError('headroom_frozen_provenance')
    if set(r['rows'])!=set(map(str,c['tasks']['train'])):raise ValueError('headroom_task_grid')
    lookup={t['seed']:t['arrays'] for t in pack['questions']['source']['tasks']};dot=lambda x,y:sum(a*b for a,b in zip(x,y))
    close=lambda x,y:finite(x) and finite(y) and abs(x-y)<2e-6
    for fold in range(4):
        meta=pack['questions']['source']['frozen_folds'][str(fold)]
        for tid in meta['excluded_ids']:
            a=lookup[tid];ref=pack['reference'][str(tid)];cell=r['rows'][str(tid)]
            if set(cell)!=set(map(str,c['budgets'])):raise ValueError('headroom_budget_grid')
            sx=[[v/s for v,s in zip(x,meta['scale'])] for x in a['support_x']];ox=[[v/s for v,s in zip(x,meta['scale'])] for x in a['old_x']]
            for b in c['budgets']:
                state=cell[str(b)];seen=ref['order'][:b-1];available=[i for i in range(8) if i not in seen]
                if set(state)!={'seen_indices','variance_index','before','candidates'} or state['seen_indices']!=seen or any(type(i) is not int for i in state['seen_indices']) or type(state['variance_index']) is not int or state['variance_index']!=ref['order'][b-1]:raise ValueError('headroom_state_reference')
                if set(state['candidates'])!=set(map(str,available)):raise ValueError('headroom_candidate_grid')
                if set(state['before'])!=set(map(str,c['constant_seeds'])):raise ValueError('headroom_keep_fit_grid')
                for i,arms in [('keep',state['before'])]+list(state['candidates'].items()):
                    if set(arms)!=set(map(str,c['constant_seeds'])):raise ValueError('headroom_fit_grid')
                    for seed,row in arms.items():
                        before=ref['paths'][seed][b-1]['theta'];initial=ref['paths'][seed][0]['theta']
                        fields={'theta','query_mse','retention_mse','query_blocks','retention_blocks'}
                        if i!='keep':fields|={'proposal','support_error_before','support_error_after'}
                        if set(row)!=fields or len(row['theta'])!=33 or any(not finite(v) for v in row['theta']):raise ValueError('headroom_snapshot_grid')
                        for role in ('query','retention'):
                            expected=[(dot([v/s for v,s in zip(x,meta['scale'])],row['theta'])-y)**2 for x,y in zip(a[role+'_x'],a[role+'_y'])]
                            if not close(row[role+'_mse'],st.mean(expected)) or row[role+'_mse']<0 or type(row[role+'_blocks']) is not list or len(row[role+'_blocks'])!=3:raise ValueError('headroom_metric_grid')
                            if any(not finite(actual) or actual<0 or not close(actual,st.mean(expected[j] for j in block)) for actual,block in zip(row[role+'_blocks'],c['query_blocks'])):raise ValueError('headroom_block_arithmetic')
                        if i=='keep':
                            if row['theta']!=before:raise ValueError('headroom_keep_changed')
                            continue
                        index=int(i);proposal=row['proposal']
                        if len(proposal)!=33 or any(not finite(v) for v in proposal):raise ValueError('headroom_proposal_grid')
                        bx=ox+[sx[j] for j in seen+[index]];by=a['old_y']+[a['support_y'][j] for j in seen+[index]]
                        residual=[y-dot(x,proposal) for x,y in zip(bx,by)]
                        if max(abs(.1*(v-z)-sum(x[j]*e for x,e in zip(bx,residual))) for j,(v,z) in enumerate(zip(proposal,initial)))>2e-5:raise ValueError('headroom_posterior_equation')
                        g=max(0,min(1,.5+.25*meta['constants'][seed]['weights']['logits.bias'][0]))
                        if any(not close(v,z+g*(p-z)) for v,z,p in zip(row['theta'],before,proposal)):raise ValueError('headroom_fixed_damping')
                        for name,theta in (('before',before),('after',row['theta'])):
                            if not close(row['support_error_'+name],(a['support_y'][index]-dot(sx[index],theta))**2):raise ValueError('headroom_support_arithmetic')
                        if index==state['variance_index'] and any(not close(x,y) for x,y in zip(row['theta'],ref['paths'][seed][b]['theta'])):raise ValueError('headroom_prior_choice_reproduction')
    if r['analysis']!=summarize(r['rows'],c):raise ValueError('headroom_summary_arithmetic')
    if set(r['timing_s'])!={'fitting','assessment','analysis'} or any(not finite(v) or v<0 for v in r['timing_s'].values()):raise ValueError('headroom_timing')
    return True


def run(request):
    import torch
    from . import learning_benchmark as lb
    c=request['inputs']['study_config'];pack=request['inputs']['source_pack'];config_check(c);validate_pack(pack,c)
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True);lb.WORK.clear();start=time.monotonic()
    def check():
        if time.monotonic()-start>=c['max_wall_s']:raise TimeoutError('headroom_wall_cap')
    frozen=digest(pack['questions']['source']['frozen_folds']);reference=digest(pack['reference'])
    r=dict(config=c,source_pack_sha256=digest(pack),frozen_before_sha256=frozen,reference_before_sha256=reference,
        declared_complete=False,rows={},timing_s=dict(fitting=0.,assessment=0.,analysis=0.))
    def progress():
        r.update(wall_s=time.monotonic()-start,update_work=dict(lb.WORK));p=Path('progress.tmp');p.write_text(json.dumps(r,allow_nan=False));p.replace('progress.json')
    progress();lookup={t['seed']:t['arrays'] for t in pack['questions']['source']['tasks']}
    for f in range(4):
        meta=pack['questions']['source']['frozen_folds'][str(f)]
        for tid in meta['excluded_ids']:
            a=lookup[tid];task=lb.LessonTask(*(torch.tensor(a[k],dtype=torch.float32) for k in lb.LessonTask.__dataclass_fields__))
            task=lb.scaled(task,torch.tensor(meta['scale'],dtype=torch.float32));ref=pack['reference'][str(tid)]
            gates={str(s):float((.5+.25*torch.tensor(meta['constants'][str(s)]['weights']['logits.bias'][0])).clamp(0,1)) for s in c['constant_seeds']}
            cells={};r['rows'][str(tid)]=cells
            for b in c['budgets']:
                seen=ref['order'][:b-1];cell=dict(seen_indices=list(seen),variance_index=ref['order'][b-1],before={},candidates={});cells[str(b)]=cell
                for seed,g in gates.items():
                    initial=torch.tensor(ref['paths'][seed][0]['theta']);previous=torch.tensor(ref['paths'][seed][b-1]['theta']);keep=dict(theta=previous.tolist())
                    tick=time.monotonic();questions.assess([keep],task.query_x,task.query_y,task.retention_x,task.retention_y,blocks=True)
                    r['timing_s']['assessment']+=time.monotonic()-tick;cell['before'][seed]=keep
                    for index in (i for i in range(8) if i not in seen):
                        check();tick=time.monotonic()
                        with torch.no_grad():row=counterfactual(initial,previous,task.old_x,task.old_y,task.support_x[seen],task.support_y[seen],task.support_x[index],task.support_y[index],g)
                        r['timing_s']['fitting']+=time.monotonic()-tick;tick=time.monotonic()
                        questions.assess([row],task.query_x,task.query_y,task.retention_x,task.retention_y,blocks=True)
                        r['timing_s']['assessment']+=time.monotonic()-tick;cell['candidates'].setdefault(str(index),{})[seed]=row
            progress()
    tick=time.monotonic();r['analysis']=summarize(r['rows'],c);r['timing_s']['analysis']=time.monotonic()-tick
    r.update(frozen_after_sha256=digest(pack['questions']['source']['frozen_folds']),reference_after_sha256=digest(pack['reference']))
    validate(r,c,pack);r['declared_complete']=True;progress()
    return dict(adapter='seed_question_headroom_v1',study=r,curve=[],
        model=dict(schema='unchanged_headroom_learner_v1',frozen_sha256=frozen,reference_sha256=reference),
        metrics=dict(mse=r['analysis']['curve_means']['query_oracle'],baseline_mse=r['analysis']['curve_means']['variance']),
        resources=resources(time.process_time()),runtime=dict(python=sys.version,torch=torch.__version__,device='cpu',threads=1))


def validate_output(output,c,caps,pack):
    r=output['study'];validate(r,c,pack);expected=resources(0);work=output['resources']
    if output['adapter']!='seed_question_headroom_v1' or r['declared_complete'] is not True:raise ValueError('incomplete_headroom_execution')
    if output['model']!=dict(schema='unchanged_headroom_learner_v1',frozen_sha256=r['frozen_after_sha256'],reference_sha256=r['reference_after_sha256']):raise ValueError('headroom_model_changed')
    if set(work)!=set(expected) or any(type(work[k]) is not int or work[k]!=v for k,v in expected.items() if k!='cpu_s'):raise ValueError('headroom_resource_grid')
    if not finite(work['cpu_s']) or not 0<=work['cpu_s']<=caps['cpu_s'] or caps['updates']!=0 or r['update_work']!={'cumulative_solves':756}:raise ValueError('headroom_actual_work')
    return True


def saved_replay(root):
    c=json.loads((root/'configs/seed_question_headroom.json').read_text());r=json.loads((root/'artifacts/seed_question_headroom.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('incomplete_headroom_evidence')
    validate(r,c,source_pack(root,c));h=r['host_receipt']
    return dict(id=h['id'],mode='recorded_source_evaluator_only_headroom',status=h['status'],failure=h['failure'],
        wall_s=h['wall_s'],memory_mb=h['peak_sampled_rss_mb'],revision=r['execution_sha'],
        metrics=dict(mse=r['analysis']['curve_means']['query_oracle'],baseline_mse=r['analysis']['curve_means']['variance']),
        curve=[],resources=r['resources'],model_sha256=r['frozen_after_sha256'],question_headroom=r['analysis'])
