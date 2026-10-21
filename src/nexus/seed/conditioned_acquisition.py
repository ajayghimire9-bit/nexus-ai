"""Fresh, source-trained query-conditioned acquisition, not a new learner.

Reuses source_acquisition's interpreter, features, source utility cases, fixed
version-space updates, baselines, LabelOracle and the same bounded host/journal.
"""
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time
from nexus.evolution1.catalogue import digest
from . import source_acquisition as a

POLICIES=['conditioned','blind_capacity','blind','variance','model_based','source_prior','source_static','original_order']
METHODS=POLICIES+['uniform_expectation','keep']


def configuration():
    return dict(schema='seed_conditioned_acquisition_v1',families=list(range(1747000001,1747000009)),
        tasks=dict(train=list(range(1747100000,1747100064)),target=list(range(1747200000,1747200064))),
        assignment_seed=1747000900,registration_config='seed_conditioned_acquisition.json',extra_registration_seeds=[1747000900],
        source_registration_offsets=[700,200000],
        prior_config_registry_sha256='eb93436bf84c07a8c3a6b600e945c62c9f0e34823225332430c18d53467434e7',
        source_counts=[1,1,3,3],target_counts=[1,1,3,3],source_tasks_per_repetition=8,target_tasks_per_repetition=8,
        methods=METHODS,budgets=[1,2,4,8],primary_budgets=[1,2,4],ridge=1.,prior_pseudocount=1.,
        catalogue_size=910,feature_counts=dict(blind=10,blind_capacity=13,conditioned=13),
        minimum_fraction=.05,minimum_repetition_wins=6,strong_noninferiority=.005,
        max_wall_s=60,max_authored_steps=2500,max_outer_updates=24,max_imagined_transitions=0,
        carried_used_s=1999.6321034559958,carried_remaining_s=1600.3678965440042)


def config_check(c):
    if digest(c)!=digest(configuration()):raise ValueError('locked_conditioned_recipe')
    return dict(real_steps=2500,imagined_transitions=0,outer_updates=24)


def assignment(c,entries):
    # Historical task identities are excluded using registration metadata only;
    # no historical outcome, score or parameter informs new sampling.
    old=a.assignment(a.configuration(),entries)
    excluded={i for b in old for ids in b.values() for i in ids}
    rng=random.Random(c['assignment_seed']);groups=[[i for i,e in enumerate(entries) if e['group']==g and i not in excluded] for g in range(4)]
    for group in groups:rng.shuffle(group)
    blocks=[]
    for _ in c['families']:
        source=[];target=[]
        for g in range(4):
            n=c['source_counts'][g];k=c['target_counts'][g]
            if len(groups[g])<n+k:raise ValueError('fresh_catalogue_exhausted')
            source+=groups[g][:n];target+=groups[g][n:n+k];groups[g]=groups[g][n+k:]
        rng.shuffle(source);rng.shuffle(target);blocks.append(dict(source=source,target=target))
    ids=[i for b in blocks for xs in b.values() for i in xs]
    if len(ids)!=128 or len(set(ids))!=128 or set(ids)&excluded:raise ValueError('fresh_disjoint_programs')
    return blocks,sorted(excluded)


def extra_features(kind,x,query,cost):
    """Public INPUT geometry only; no truth table, answer or updated parameters."""
    if kind=='conditioned':
        distances=[(x^q).bit_count()/4 for q in query]
        if not distances:raise ValueError('public_query_inputs_required')
        cost['query_distance_operations']+=len(query)
        return [sum(distances)/len(distances),sum(d*d for d in distances)/len(distances),min(distances)]
    if kind=='blind_capacity':
        bits=[float(bool(x&(1<<i))) for i in range(4)]
        cost['candidate_interaction_operations']+=3
        return [bits[0]*bits[1],bits[2]*bits[3],float(x.bit_count()%2)]
    if kind=='blind':return []
    raise ValueError('feature_kind')


def meter():return dict(a.meter(),query_distance_operations=0,candidate_interaction_operations=0)


def features(kind,table,ids,x,observed,remaining,query,cost):
    base=a.features(table,ids,x,observed,remaining,cost)
    extra=extra_features(kind,x,query,cost);cost['feature_scalars']+=len(extra)
    return base+extra


def fit(source,table,groups,c,cost):
    from nexus.nn.ridge import fit_ridge
    base=a.fit_selector(source,table,groups,c,cost,source_count=8)
    models={'blind':dict(scale=base['scale'],beta=base['beta'])}
    for kind in ('blind_capacity','conditioned'):
        x=[case['x']+extra_features(kind,case['candidate'],a.split_inputs(case['task'])[1],cost) for case in base['cases']]
        y=[case['utility'] for case in base['cases']]
        cost['feature_scalars']+=len(x)*3
        scale,beta=fit_ridge(x,y,ridge=c['ridge']);cost['ridge_fits']+=1
        models[kind]=dict(scale=scale.tolist(),beta=beta.tolist())
    return dict(base=base,models=models,source_sha256=digest(source))


def path(kind,table,model,pool,query,reveal,cost):
    import numpy as np
    from nexus.nn.ridge import predict_ridge
    if kind not in ('conditioned','blind_capacity'):
        return a.path('learned' if kind=='blind' else kind,table,model['base'],pool,query,reveal,cost)
    ids=np.arange(len(table));observed=[];remaining=list(range(8));steps=[];snapshots={}
    fitted=model['models'][kind]
    for budget in range(1,9):
        scores=[predict_ridge((np.asarray(fitted['scale']),np.asarray(fitted['beta'])),
            features(kind,table,ids,pool[q],observed,len(remaining),query,cost)) for q in remaining]
        cost['ridge_predictions']+=len(remaining)
        chosen=max(range(len(remaining)),key=lambda j:(scores[j],-remaining[j]));q=remaining[chosen]
        step=dict(index=q,input=pool[q],remaining=list(remaining),scores=scores)
        answer=reveal(q);step['answer']=answer;remaining.remove(q)
        ids=a.update(table,ids,pool[q],answer,cost);observed.append((pool[q],answer));step['posterior']=ids.tolist();steps.append(step)
        if budget in a.BUDGETS:snapshots[str(budget)]=dict(posterior=ids.tolist(),prediction=a.prediction(table,ids,query,cost).tolist())
    return dict(steps=steps,snapshots=snapshots)


def analyze(blocks,c):
    means={m:{str(b):sum(x['means'][m][str(b)] for x in blocks)/8 for b in a.BUDGETS} for m in METHODS}
    primary={m:sum(means[m][str(b)] for b in (1,2,4))/3 for m in METHODS}
    contrasts={m:a.interval([sum(x['means'][m][str(b)]-x['means']['conditioned'][str(b)] for b in (1,2,4))/3 for x in blocks]) for m in METHODS if m!='conditioned'}
    for value in contrasts.values():value['unit']='source-trained selector repetition; one supplied finite catalogue'
    wins={m:sum(sum(x['means'][m][str(b)]-x['means']['conditioned'][str(b)] for b in (1,2,4))>0 for x in blocks) for m in ('blind','blind_capacity')}
    screen=all(primary['conditioned']<=primary[m]*(1-c['minimum_fraction']) and contrasts[m]['low']>0 for m in ('blind','blind_capacity')) and wins['blind']>=c['minimum_repetition_wins']
    noninferior=all(primary['conditioned']<=primary[m]+c['strong_noninferiority'] for m in ('model_based','source_prior'))
    strong=all(primary['conditioned']<=primary[m]*(1-c['minimum_fraction']) and contrasts[m]['low']>0 for m in ('model_based','source_prior'))
    costs={m:{k:sum(r['costs'][m][k] for x in blocks for r in x['rows']) for k in meter()} for m in POLICIES}
    source_cost={k:sum(x['fit_cost'][k] for x in blocks) for k in meter()}
    # Source matrix cost is shared utility data; an isolated method is charged
    # the appropriate base source cost, not the combined three-fit study cost.
    profiles={}
    for m in POLICIES:
        field={'conditioned':'learned_utility_entries','blind_capacity':'learned_utility_entries','blind':'learned_utility_entries','source_prior':'prior_identity_entries','source_static':'static_utility_entries'}.get(m)
        src=sum(x['model']['base']['training_cost_split'][field] for x in blocks) if field else 0
        profiles[m]=dict(source_matrix_entries=src,target_matrix_entries=costs[m]['matrix_entries'],total_matrix_entries=src+costs[m]['matrix_entries'],
            query_distance_operations=(sum(len(x['model']['base']['cases'])*8 for x in blocks) if m=='conditioned' else 0)+costs[m]['query_distance_operations'],
            numerical_fits=8 if m in c['feature_counts'] else 0,source_labels=1024 if field else 0)
    return dict(primary=primary,by_budget=means,contrasts=contrasts,repetition_wins=wins,
        transfer_screen='passed' if screen and noninferior else 'failed',strong_advantage_screen='passed' if strong else 'failed',
        feature_counts=c['feature_counts'],source_fit_cost=source_cost,target_costs=costs,compute_profiles=profiles,
        uniform_assessment_matrix_entries=sum(r['uniform_cost']['matrix_entries'] for x in blocks for r in x['rows']),
        scope='fresh source-development Boolean tasks; one supplied finite catalogue',promoted=False)


def run(request):
    import numpy as np
    c=request['inputs']['study_config'];config_check(c);root=Path(request['inputs']['repository']);start=time.monotonic();cpu=time.process_time()
    r=dict(config=c,declared_complete=False,blocks=[])
    work=dict(real_steps=0,source_labels=0,target_support=0,target_query=0,updates=0,imagined_transitions=0,network_forwards=0,cached_target_answer_exposures=0,target_policy_paths=0)
    def persist():
        p=Path('progress.tmp');p.write_text(json.dumps(r,allow_nan=False));p.replace('progress.json')
    def charge(key,n):
        work[key]+=n;work['real_steps']+=n
        if time.monotonic()-start>c['max_wall_s']-3 or work['real_steps']>c['max_authored_steps']:raise TimeoutError('conditioned_cap')
    hashes=lambda:{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in a.FROZEN}
    try:
        r['seed_audit']=a.seed_audit(root,c);r['frozen_before']=hashes()
        if r['frozen_before']!=a.FROZEN:raise ValueError('frozen_checkpoint_hash')
        entries,instructions=a.catalogue();table=np.asarray([e['answers'] for e in entries],bool);groups=[e['group'] for e in entries]
        r['catalogue_hash']=digest(entries);r['catalogue_instructions']=instructions
        assigned,excluded=assignment(c,entries);r['assignment']=assigned;r['excluded_historical_programs']=excluded
        for i,family in enumerate(c['families']):
            source=[];block=dict(id=family,source=source,rows=[]);r['blocks'].append(block)
            for task,index in zip(c['tasks']['train'][8*i:8*(i+1)],assigned[i]['source']):
                source.append(dict(role='source',task=task,answers=entries[index]['answers']));charge('source_labels',16)
            block['fit_cost']=meter();block['model']=fit(source,table,groups,c,block['fit_cost']);work['updates']+=3
            block['model_hash']=digest(block['model']);persist()
        r['source_fits_frozen_before_targets']=True;persist()
        for i,block in enumerate(r['blocks']):
            for task,index in zip(c['tasks']['target'][8*i:8*(i+1)],assigned[i]['target']):
                pool,query=a.split_inputs(task);answers=[entries[index]['answers'][q] for q in pool];charge('target_support',8)
                methods={};costs={}
                for m in POLICIES:
                    costs[m]=meter();oracle=a.LabelOracle(answers,8)
                    methods[m]=path(m,table,block['model'],pool,query,oracle.reveal,costs[m]);work['cached_target_answer_exposures']+=8;work['target_policy_paths']+=1
                block['rows'].append(dict(task=task,pool=pool,query=query,support_answers=answers,methods=methods,costs=costs))
            block['locked_choices_hash']=digest(block['rows']);persist()
        r['all_choices_locked_before_query_labels']=True;persist()
        for i,block in enumerate(r['blocks']):
            for row,index in zip(block['rows'],assigned[i]['target']):
                labels=[entries[index]['answers'][q] for q in row['query']];row['query_answers']=labels;charge('target_query',8)
                row['metrics']={m:{str(b):float(np.mean((np.asarray(p['snapshots'][str(b)]['prediction'])-labels)**2)) for b in a.BUDGETS} for m,p in row['methods'].items()}
                row['uniform_cost']=meter();row['metrics']['uniform_expectation']=a.uniform_assessment(table,row['pool'],row['query'],row['support_answers'],labels,row['uniform_cost'])
                keep=a.risk(table,np.arange(len(table)),row['query'],labels,meter());row['metrics']['keep']={str(b):keep for b in a.BUDGETS}
            block['means']={m:{str(b):sum(row['metrics'][m][str(b)] for row in block['rows'])/8 for b in a.BUDGETS} for m in METHODS}
            if digest(block['model'])!=block['model_hash']:raise ValueError('source_model_changed')
            persist()
        r['analysis']=analyze(r['blocks'],c);r['frozen_after']=hashes()
        if r['frozen_after']!=a.FROZEN:raise ValueError('frozen_checkpoint_changed')
        r['declared_complete']=True;persist()
    except Exception as e:
        r['failure']=dict(type=type(e).__name__,message=str(e));r['partial_resources']=work;persist();raise
    work.update(cpu_s=time.process_time()-cpu,worker_wall_s=time.monotonic()-start,program_instructions=instructions,
        selector_training_cases=sum(len(x['model']['base']['cases']) for x in r['blocks']),learned_coefficients=8*36,uniform_assessment_subsets=64*107)
    return dict(adapter=c['schema'],study=r,resources=work,runtime=dict(python=sys.version,numpy=np.__version__,device='cpu',threads=1))


def validate_grid(r,c):
    if [b['id'] for b in r['blocks']]!=c['families']:raise ValueError('complete_repetition_grid')
    for i,block in enumerate(r['blocks']):
        if [s['task'] for s in block['source']]!=c['tasks']['train'][8*i:8*(i+1)] or [x['task'] for x in block['rows']]!=c['tasks']['target'][8*i:8*(i+1)]:raise ValueError('complete_task_grid')
        for row in block['rows']:
            if set(row['methods'])!=set(POLICIES) or set(row['metrics'])!=set(METHODS):raise ValueError('complete_method_grid')
            for method in METHODS:
                if set(row['metrics'][method])!={'1','2','4','8'}:raise ValueError('complete_budget_grid')
                if any(type(v) not in (int,float) or not math.isfinite(v) for v in row['metrics'][method].values()):raise ValueError('finite_metric_cells')


def validate_output(o,c,caps):
    import numpy as np
    config_check(c);r=o['study'];root=Path(__file__).resolve().parents[3]
    if r.get('declared_complete') is not True or digest(r['config'])!=digest(c):raise ValueError('complete_conditioned_study')
    validate_grid(r,c)
    if r['source_fits_frozen_before_targets'] is not True or r['all_choices_locked_before_query_labels'] is not True:raise ValueError('feedback_boundaries')
    if digest(r['seed_audit']['config_hashes'])!=c['prior_config_registry_sha256'] or digest(a.seed_audit(root,c,names=r['seed_audit']['config_hashes']))!=digest(r['seed_audit']):raise ValueError('seed_registry_snapshot')
    entries,instructions=a.catalogue();table=np.asarray([e['answers'] for e in entries],bool);groups=[e['group'] for e in entries];assigned,excluded=assignment(c,entries)
    if digest(assigned)!=digest(r['assignment']) or excluded!=r['excluded_historical_programs'] or digest(entries)!=r['catalogue_hash'] or instructions!=r['catalogue_instructions']:raise ValueError('fresh_program_registration')
    for i,block in enumerate(r['blocks']):
        source=[dict(role='source',task=task,answers=entries[index]['answers']) for task,index in zip(c['tasks']['train'][8*i:8*(i+1)],assigned[i]['source'])]
        if digest(source)!=digest(block['source']):raise ValueError('source_supervision')
        fit_cost=meter();model=fit(source,table,groups,c,fit_cost)
        if digest(model)!=digest(block['model']) or digest(model)!=block['model_hash'] or digest(fit_cost)!=digest(block['fit_cost']):raise ValueError('source_only_models_or_scaling')
        locked=[]
        for row,index in zip(block['rows'],assigned[i]['target']):
            pool,query=a.split_inputs(row['task']);answers=[entries[index]['answers'][q] for q in pool];labels=[entries[index]['answers'][q] for q in query]
            if digest((pool,query,answers,labels))!=digest((row['pool'],row['query'],row['support_answers'],row['query_answers'])):raise ValueError('label_separation')
            paths={};costs={};metrics={}
            for m in POLICIES:
                costs[m]=meter();paths[m]=path(m,table,model,pool,query,a.LabelOracle(answers,8).reveal,costs[m])
                metrics[m]={str(b):float(np.mean((np.asarray(paths[m]['snapshots'][str(b)]['prediction'])-labels)**2)) for b in a.BUDGETS}
                # Every observed label remains exactly consistent with every
                # retained hypothesis. No forgetting of taught transitions.
                seen=[]
                for step in paths[m]['steps']:
                    seen.append((step['input'],step['answer']))
                    if any(not np.all(table[step['posterior'],x]==y) for x,y in seen):raise ValueError('known_prefix_retention')
            uniform_cost=meter();metrics['uniform_expectation']=a.uniform_assessment(table,pool,query,answers,labels,uniform_cost)
            metrics['keep']={str(b):a.risk(table,np.arange(len(table)),query,labels,a.meter()) for b in a.BUDGETS}
            if digest((paths,costs,metrics,uniform_cost))!=digest((row['methods'],row['costs'],row['metrics'],row['uniform_cost'])):raise ValueError('paths_metrics_costs')
            if max(metrics[m]['8'] for m in METHODS if m!='keep')-min(metrics[m]['8'] for m in METHODS if m!='keep')>1e-12:raise ValueError('same_final_learner')
            locked.append(dict(task=row['task'],pool=pool,query=query,support_answers=answers,methods=paths,costs=costs))
        if digest(locked)!=block['locked_choices_hash']:raise ValueError('preassessment_lock')
        means={m:{str(b):sum(row['metrics'][m][str(b)] for row in block['rows'])/8 for b in a.BUDGETS} for m in METHODS}
        if digest(means)!=digest(block['means']):raise ValueError('block_aggregation')
    if digest(analyze(r['blocks'],c))!=digest(r['analysis']):raise ValueError('summary_arithmetic')
    if r['frozen_before']!=a.FROZEN or r['frozen_after']!=a.FROZEN:raise ValueError('historical_checkpoint_preservation')
    expected=dict(real_steps=2048,source_labels=1024,target_support=512,target_query=512,updates=24,imagined_transitions=0,network_forwards=0,
        cached_target_answer_exposures=4096,target_policy_paths=512,program_instructions=instructions,selector_training_cases=2304,learned_coefficients=288,uniform_assessment_subsets=6848)
    for k,v in expected.items():
        if type(o['resources'].get(k)) is not int or o['resources'][k]!=v:raise ValueError('resource_accounting')
    if o['resources']['real_steps']>caps['real_steps']:raise ValueError('resource_cap')
    for k in ('cpu_s','worker_wall_s'):
        if type(o['resources'].get(k)) not in (int,float) or not math.isfinite(o['resources'][k]) or o['resources'][k]<0:raise ValueError('finite_runtime')


def saved_replay(root):
    root=Path(root);raw=(root/'artifacts/seed_conditioned_acquisition.json').read_bytes();r=json.loads(raw)
    receipt=json.loads((root/'artifacts/seed_conditioned_acquisition_audit.json').read_text())
    if receipt.get('valid') is not True or receipt.get('raw_sha256')!=hashlib.sha256(raw).hexdigest() or r.get('declared_complete') is not True:raise ValueError('conditioned_audit_receipt_required')
    config_check(r['config'])
    return dict(id='seed-conditioned-acquisition-1',mode='exploration',status='complete_development',wall_s=r['host_receipt']['wall_s'],
        memory_mb=r['host_receipt']['peak_sampled_rss_mb'],revision=r['execution_sha'],resources=r['resources'],curve=[],conditioned_acquisition=r['analysis'])
