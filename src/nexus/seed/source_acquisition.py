"""Bounded acquisition learning over supplied executable Boolean programs.

Reuses foundation.programs, LabelOracle, nn.ridge, family intervals, and the
EXPERIMENTAL host. No world-model changes, simulator, or live-agent promotion.
"""
import copy
import hashlib
import itertools as it
import json
import math
from pathlib import Path
import random
import sys
import time
from nexus.evolution1.catalogue import digest
from .foundation import programs
from .question_selection import LabelOracle
from .inferred_investigation import interval,seed_audit
from .investigation_transfer import FROZEN

POLICIES=['learned','variance','model_based','source_prior','source_static','original_order']
METHODS=POLICIES+['uniform_expectation','keep']
BUDGETS=[1,2,4,8]


def configuration():
    return dict(schema='seed_source_acquisition_v1',families=list(range(1745000001,1745000009)),
        tasks=dict(train=list(range(1745100000,1745100128)),target=list(range(1745200000,1745200064))),
        assignment_seed=1745000900,methods=METHODS,budgets=BUDGETS,primary_budgets=[1,2,4],
        registration_config='seed_source_acquisition.json',extra_registration_seeds=[1745000900],source_registration_offsets=[700,200000],
        prior_config_registry_sha256='c673552263b0a60eba387f9ec42f72d3521c10cbaac95c39f67b55fcefc0db6f',
        source_tasks_per_repetition=16,target_tasks_per_repetition=8,source_counts=[6,6,2,2],target_counts=[3,3,1,1],
        features=10,ridge=1.0,prior_pseudocount=1.0,catalogue_size=910,
        max_wall_s=60,max_authored_steps=4000,max_outer_updates=8,max_imagined_transitions=0,
        carried_used_s=1990.6321034559958,carried_remaining_s=1609.3678965440042,
        minimum_fraction=.05,minimum_repetition_wins=6,strong_noninferiority=.005)


def config_check(c):
    if digest(c)!=digest(configuration()):raise ValueError('locked_acquisition_recipe')
    return dict(real_steps=4000,imagined_transitions=0,outer_updates=8)


def catalogue():
    """Public finite prior: ANF polynomials, two/three distinct monomials.

    Each program executes in the existing bounded interpreter. Hidden task
    identity is never an argument to a selector, feature function or learner.
    """
    monomials=[a for size in (1,2,3) for a in it.combinations(range(4),size)]
    entries=[];instructions=0
    for count in (2,3):
        for terms in it.combinations(monomials,count):
            nodes=[dict(op='and',args=[programs.variable('abcd'[i]) for i in term]) for term in terms]
            body=nodes[0]
            for child in nodes[1:]:body=dict(op='not',value=dict(op='eq',left=body,right=child))
            for negated in (False,True):
                program=dict(op='not',value=body) if negated else body;answers=[]
                for x in range(16):
                    out=programs.execute(program,{name:bool(x&(1<<i)) for i,name in enumerate('abcd')})
                    instructions+=out['instructions'];answers.append(out['value'])
                entries.append(dict(program=program,answers=answers,group=(count-2)*2+int(negated)))
    if len(entries)!=910 or len({tuple(e['answers']) for e in entries})!=910:raise ValueError('unique_program_catalogue')
    return entries,instructions


def assignment(c,entries):
    rng=random.Random(c['assignment_seed']);groups=[[i for i,e in enumerate(entries) if e['group']==g] for g in range(4)]
    for ids in groups:rng.shuffle(ids)
    assigned=[]
    for i in range(8):
        source=[];target=[]
        for g in range(4):
            n=c['source_counts'][g];k=c['target_counts'][g]
            source+=groups[g][:n];target+=groups[g][n:n+k];groups[g]=groups[g][n+k:]
        rng.shuffle(source);rng.shuffle(target);assigned.append(dict(source=source,target=target))
    all_ids=[j for a in assigned for ids in a.values() for j in ids]
    if len(set(all_ids))!=192:raise ValueError('globally_disjoint_task_rules')
    return assigned


def split_inputs(seed):
    indices=list(range(16));random.Random(seed+200000).shuffle(indices)
    return sorted(indices[:8]),sorted(indices[8:])


def read_table(table,ids,columns,cost):
    import numpy as np
    cost['matrix_entries']+=len(ids)*len(columns)
    return table[np.ix_(ids,columns)]


def update(table,ids,x,answer,cost):
    import numpy as np
    if type(answer) is not bool:raise ValueError('boolean_teaching')
    values=read_table(table,ids,[x],cost)[:,0];result=np.asarray(ids)[values==answer]
    if len(result)==0:raise ValueError('empty_version_space')
    return result


def features(table,ids,x,observed,remaining,cost):
    """Ten scalar PRE-answer inputs. No candidate label or assessment argument."""
    p=float(read_table(table,ids,[x],cost).mean())
    distance=min(((x^q).bit_count()/4 for q,_ in observed),default=1.)
    positive=sum(y for _,y in observed)/len(observed) if observed else .5
    result=[1.]+[float(bool(x&(1<<i))) for i in range(4)]+[p,p*(1-p),distance,positive,remaining/8]
    cost['feature_scalars']+=10
    return result


def prediction(table,ids,query,cost):return read_table(table,ids,query,cost).mean(axis=0)


def risk(table,ids,query,labels,cost):
    import numpy as np
    return float(np.mean((prediction(table,ids,query,cost)-np.asarray(labels))**2))


def expected_gain(table,ids,x,query,weights,cost):
    """Expected MSE improvement of the SAME uniform-posterior learner.

    The selector sees query INPUTS, never labels. Optional source-derived
    weights change the acquisition belief, not the underlying fixed learner.
    """
    import numpy as np
    values=read_table(table,ids,query,cost);answers=read_table(table,ids,[x],cost)[:,0]
    w=weights[ids];w=w/w.sum();p=values.mean(axis=0);truth=np.average(values,axis=0,weights=w)
    before=float(np.mean(p*p+truth*(1-2*p)));after=0.
    for a in (False,True):
        mask=answers==a;prob=float(w[mask].sum())
        if not prob:continue
        sub=values[mask];cost['matrix_entries']+=int(mask.sum())*len(query)
        pred=sub.mean(axis=0);truth=np.average(sub,axis=0,weights=w[mask])
        after+=prob*float(np.mean(pred*pred+truth*(1-2*pred)))
    return before-after


def fit_selector(source,table,groups,c,cost):
    import numpy as np
    from nexus.nn.ridge import fit_ridge
    if len(source)!=16 or any(row.get('role')!='source' for row in source):raise ValueError('source_only_fit')
    x=[];y=[];cases=[];static=[[] for _ in range(16)];counts=[0]*4;identity_entries=0;feature_entries=0
    for row in source:
        full=row['answers']
        matches=np.flatnonzero(np.all(table==full,axis=1));cost['matrix_entries']+=int(table.size)
        identity_entries+=int(table.size)
        if len(matches)!=1:raise ValueError('source_program_identity')
        counts[groups[int(matches[0])]]+=1
        pool,query=split_inputs(row['task']);order=list(range(8));random.Random(row['task']+700).shuffle(order)
        ids=np.arange(len(table));observed=[]
        for prefix,next_index in enumerate(order):
            remaining=[q for q in range(8) if q not in order[:prefix]]
            before=risk(table,ids,query,[full[q] for q in query],cost)
            for q in remaining:
                f=features(table,ids,pool[q],observed,len(remaining),cost)
                feature_entries+=len(ids)
                child=update(table,ids,pool[q],full[pool[q]],cost)
                utility=before-risk(table,child,query,[full[t] for t in query],cost)
                x.append(f);y.append(utility);static[pool[q]].append(utility)
                cases.append(dict(task=row['task'],prefix=prefix,candidate=pool[q],x=f,utility=utility))
            observed.append((pool[next_index],full[pool[next_index]]));ids=update(table,ids,pool[next_index],full[pool[next_index]],cost)
    scale,beta=fit_ridge(x,y,ridge=c['ridge']);cost['ridge_fits']+=1
    group_sizes=[sum(g==i for g in groups) for i in range(4)]
    weights=[(counts[g]+c['prior_pseudocount'])/group_sizes[g] for g in groups]
    return dict(scale=scale.tolist(),beta=beta.tolist(),static=[sum(a)/len(a) if a else float(np.mean(y)) for a in static],
        prior_weights=weights,source_hash=digest(source),cases=cases,group_counts=counts,parameter_count=10,
        training_cost_split=dict(prior_identity_entries=identity_entries,utility_feature_entries=feature_entries,
            learned_utility_entries=cost['matrix_entries']-identity_entries,
            static_utility_entries=cost['matrix_entries']-identity_entries-feature_entries))


def path(method,table,model,pool,query,reveal,cost):
    import numpy as np
    from nexus.nn.ridge import predict_ridge
    ids=np.arange(len(table));observed=[];remaining=list(range(8));steps=[];snapshots={}
    for budget in range(1,9):
        scores=[]
        for q in remaining:
            x=pool[q]
            if method=='learned':
                f=features(table,ids,x,observed,len(remaining),cost)
                score=predict_ridge((np.asarray(model['scale']),np.asarray(model['beta'])),f);cost['ridge_predictions']+=1
            elif method=='variance':
                p=float(read_table(table,ids,[x],cost).mean());score=p*(1-p)
            elif method in ('model_based','source_prior'):
                w=np.ones(len(table)) if method=='model_based' else np.asarray(model['prior_weights'])
                score=expected_gain(table,ids,x,query,w,cost)
            elif method=='source_static':score=model['static'][x]
            elif method=='original_order':score=-q
            else:raise ValueError('acquisition_policy')
            scores.append(float(score))
        chosen=max(range(len(remaining)),key=lambda j:(scores[j],-remaining[j]));q=remaining[chosen]
        step=dict(index=q,input=pool[q],remaining=list(remaining),scores=scores) # Locked BEFORE reveal.
        answer=reveal(q);step['answer']=answer;remaining.remove(q)
        ids=update(table,ids,pool[q],answer,cost);observed.append((pool[q],answer));step['posterior']=ids.tolist();steps.append(step)
        if budget in BUDGETS:snapshots[str(budget)]=dict(posterior=ids.tolist(),prediction=prediction(table,ids,query,cost).tolist())
    return dict(steps=steps,snapshots=snapshots)


def uniform_assessment(table,pool,query,answers,labels,cost):
    """Evaluator-only exact random-order expectation, never a selector input."""
    import numpy as np
    result={}
    for budget in BUDGETS:
        losses=[]
        for subset in it.combinations(range(8),budget):
            ids=np.arange(len(table))
            for q in subset:ids=update(table,ids,pool[q],answers[q],cost)
            losses.append(risk(table,ids,query,labels,cost));cost['uniform_subsets']+=1
        result[str(budget)]=sum(losses)/len(losses)
    return result


def meter():return dict(matrix_entries=0,feature_scalars=0,ridge_fits=0,ridge_predictions=0,uniform_subsets=0)


def summarize(blocks,c):
    means={m:{str(b):sum(x['means'][m][str(b)] for x in blocks)/8 for b in BUDGETS} for m in METHODS}
    primary={m:sum(means[m][str(b)] for b in c['primary_budgets'])/3 for m in METHODS}
    contrasts={m:dict(interval([sum(x['means'][m][str(b)]-x['means']['learned'][str(b)] for b in c['primary_budgets'])/3 for x in blocks]),
        unit='source-trained selector repetition; disjoint tasks from one finite catalogue') for m in METHODS if m!='learned'}
    wins=sum(sum(x['means']['variance'][str(b)]-x['means']['learned'][str(b)] for b in (1,2,4))>0 for x in blocks)
    heuristic=all(primary['learned']<=primary[m]*(1-c['minimum_fraction']) for m in ('variance','source_static','original_order','uniform_expectation','keep')) and contrasts['variance']['low']>0 and wins>=6
    noninferior=all(primary['learned']<=primary[m]+c['strong_noninferiority'] for m in ('model_based','source_prior'))
    strong=all(primary['learned']<=primary[m]*(1-c['minimum_fraction']) and contrasts[m]['low']>0 for m in ('model_based','source_prior'))
    profiles={}
    for m in POLICIES:
        field={'learned':'learned_utility_entries','source_static':'static_utility_entries','source_prior':'prior_identity_entries'}.get(m)
        source=sum(x['model']['training_cost_split'][field] for x in blocks) if field else 0
        runtime=sum(row['costs'][m]['matrix_entries'] for x in blocks for row in x['rows'])
        profiles[m]=dict(source_matrix_entries=source,target_matrix_entries=runtime,total_matrix_entries=source+runtime,
            source_labels=2048 if field else 0,
            target_feature_scalars=sum(row['costs'][m]['feature_scalars'] for x in blocks for row in x['rows']))
    return dict(primary=primary,by_budget=means,contrasts=contrasts,repetition_wins_vs_variance=wins,
        heuristic_transfer_screen='passed' if heuristic and noninferior else 'failed',strong_advantage_screen='passed' if strong else 'failed',
        parameter_count_per_selector=10,independent_selector_fits=8,compute_profiles=profiles,
        uniform_assessment_matrix_entries=sum(row['uniform_cost']['matrix_entries'] for x in blocks for row in x['rows']),
        scope='source development on disjoint tasks from one supplied finite program family',promoted=False)


def run(request):
    import numpy as np
    c=request['inputs']['study_config'];config_check(c);root=Path(request['inputs']['repository'])
    start=time.monotonic();cpu=time.process_time();r=dict(config=c,declared_complete=False,blocks=[])
    cost=meter();work=dict(real_steps=0,source_labels=0,target_support=0,target_query=0,updates=0,imagined_transitions=0,network_forwards=0,
        cached_target_answer_exposures=0,target_policy_paths=0)
    def persist():
        p=Path('progress.tmp');p.write_text(json.dumps(r,allow_nan=False));p.replace('progress.json')
    def charge(k,n):
        work[k]+=n;work['real_steps']+=n
        if time.monotonic()-start>c['max_wall_s']-3 or work['real_steps']>c['max_authored_steps']:raise TimeoutError('acquisition_cap')
    hashes=lambda:{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in FROZEN}
    try:
        r['seed_audit']=seed_audit(root,c)
        r['frozen_before']=hashes()
        if r['frozen_before']!=FROZEN:raise ValueError('frozen_checkpoint_hash')
        entries,instructions=catalogue();table=np.asarray([e['answers'] for e in entries],bool);groups=[e['group'] for e in entries]
        r['catalogue_hash']=digest(entries);r['catalogue_instructions']=instructions;assigned=assignment(c,entries)
        r['assignment']=assigned
        for i,family in enumerate(c['families']):
            source=[];block=dict(id=family,source=source,rows=[]);r['blocks'].append(block)
            for task,index in zip(c['tasks']['train'][16*i:16*(i+1)],assigned[i]['source']):
                source.append(dict(role='source',task=task,answers=entries[index]['answers']));charge('source_labels',16)
            block['fit_cost']=meter();block['model']=fit_selector(source,table,groups,c,block['fit_cost'])
            block['model_hash']=digest(block['model']);work['updates']+=1;persist()
        r['all_source_fits_frozen_before_targets']=True;persist()
        for i,block in enumerate(r['blocks']):
            for task,index in zip(c['tasks']['target'][8*i:8*(i+1)],assigned[i]['target']):
                pool,query=split_inputs(task);answers=[entries[index]['answers'][q] for q in pool];charge('target_support',8)
                methods={};costs={}
                for m in POLICIES:
                    costs[m]=meter();oracle=LabelOracle(answers,8)
                    methods[m]=path(m,table,block['model'],pool,query,oracle.reveal,costs[m])
                    work['cached_target_answer_exposures']+=len(oracle.revealed);work['target_policy_paths']+=1
                block['rows'].append(dict(task=task,pool=pool,query=query,support_answers=answers,methods=methods,costs=costs))
            block['locked_choices_hash']=digest(block['rows']);persist()
        r['all_choices_locked_before_query_labels']=True;persist()
        for i,block in enumerate(r['blocks']):
            for row,index in zip(block['rows'],assigned[i]['target']):
                labels=[entries[index]['answers'][q] for q in row['query']];row['query_answers']=labels;charge('target_query',8)
                row['metrics']={m:{str(b):float(np.mean((np.asarray(d['snapshots'][str(b)]['prediction'])-labels)**2)) for b in BUDGETS} for m,d in row['methods'].items()}
                row['uniform_cost']=meter();row['metrics']['uniform_expectation']=uniform_assessment(table,row['pool'],row['query'],row['support_answers'],labels,row['uniform_cost'])
                keep=risk(table,np.arange(len(table)),row['query'],labels,cost);row['metrics']['keep']={str(b):keep for b in BUDGETS}
            block['means']={m:{str(b):sum(row['metrics'][m][str(b)] for row in block['rows'])/8 for b in BUDGETS} for m in METHODS}
            if digest(block['model'])!=block['model_hash']:raise ValueError('frozen_source_model_changed')
            persist()
        r['analysis']=summarize(r['blocks'],c);r['frozen_after']=hashes()
        if r['frozen_after']!=FROZEN:raise ValueError('frozen_checkpoint_changed')
        r['declared_complete']=True;persist()
    except Exception as e:
        r['failure']=dict(type=type(e).__name__,message=str(e));r['partial_resources']=work;persist();raise
    work.update(cpu_s=time.process_time()-cpu,worker_wall_s=time.monotonic()-start,program_instructions=instructions,
        fitted_ridge_models=work['updates'],learned_coefficients=sum(len(x['model']['beta']) for x in r['blocks']),
        selector_training_cases=sum(len(x['model']['cases']) for x in r['blocks']),
        uniform_assessment_subsets=sum(row['uniform_cost']['uniform_subsets'] for x in r['blocks'] for row in x['rows']))
    r['evaluation_auxiliary_cost']=cost
    return dict(adapter=c['schema'],study=r,resources=work,runtime=dict(python=sys.version,numpy=np.__version__,device='cpu',threads=1))


def validate_output(o,c,caps):
    import numpy as np
    config_check(c);r=o['study']
    if r.get('declared_complete') is not True or digest(r['config'])!=digest(c) or [x['id'] for x in r['blocks']]!=c['families']:raise ValueError('complete_selector_grid')
    if r['all_source_fits_frozen_before_targets'] is not True or r['all_choices_locked_before_query_labels'] is not True:raise ValueError('answer_boundaries')
    root=Path(__file__).resolve().parents[3]
    if digest(r['seed_audit']['config_hashes'])!=c['prior_config_registry_sha256'] or digest(r['seed_audit'])!=digest(seed_audit(root,c,names=r['seed_audit']['config_hashes'])):raise ValueError('seed_snapshot')
    entries,instructions=catalogue();table=np.asarray([e['answers'] for e in entries],bool);groups=[e['group'] for e in entries]
    assigned=assignment(c,entries)
    if len(entries)!=c['catalogue_size']:raise ValueError('catalogue_size')
    if digest(assigned)!=digest(r['assignment']) or digest(entries)!=r['catalogue_hash'] or instructions!=r['catalogue_instructions']:raise ValueError('catalogue_assignment')
    for i,block in enumerate(r['blocks']):
        source=[dict(role='source',task=task,answers=entries[index]['answers']) for task,index in zip(c['tasks']['train'][16*i:16*(i+1)],assigned[i]['source'])]
        if digest(source)!=digest(block['source']):raise ValueError('source_grid_or_labels')
        fit_cost=meter();model=fit_selector(source,table,groups,c,fit_cost)
        if digest(model)!=digest(block['model']) or digest(fit_cost)!=digest(block['fit_cost']) or digest(model)!=block['model_hash']:raise ValueError('source_only_model_or_normalization')
        if [row['task'] for row in block['rows']]!=c['tasks']['target'][8*i:8*(i+1)]:raise ValueError('complete_task_grid')
        locked=[]
        for row,index in zip(block['rows'],assigned[i]['target']):
            pool,query=split_inputs(row['task']);answers=[entries[index]['answers'][q] for q in pool];labels=[entries[index]['answers'][q] for q in query]
            if digest((pool,query,answers,labels))!=digest((row['pool'],row['query'],row['support_answers'],row['query_answers'])):raise ValueError('support_query_separation')
            if set(row['methods'])!=set(POLICIES) or set(row['metrics'])!=set(METHODS):raise ValueError('complete_method_grid')
            methods={};costs={};metrics={}
            for m in POLICIES:
                costs[m]=meter();methods[m]=path(m,table,model,pool,query,LabelOracle(answers,8).reveal,costs[m])
                metrics[m]={str(b):float(np.mean((np.asarray(methods[m]['snapshots'][str(b)]['prediction'])-labels)**2)) for b in BUDGETS}
            if digest((methods,costs))!=digest((row['methods'],row['costs'])):raise ValueError('choices_or_costs')
            uniform_cost=meter();metrics['uniform_expectation']=uniform_assessment(table,pool,query,answers,labels,uniform_cost)
            keep=risk(table,np.arange(len(table)),query,labels,meter());metrics['keep']={str(b):keep for b in BUDGETS}
            if digest(metrics)!=digest(row['metrics']) or digest(uniform_cost)!=digest(row['uniform_cost']):raise ValueError('metrics_or_budget_grid')
            if max(metrics[m]['8'] for m in METHODS if m!='keep')-min(metrics[m]['8'] for m in METHODS if m!='keep')>1e-12:raise ValueError('same_final_learner')
            locked.append(dict(task=row['task'],pool=pool,query=query,support_answers=answers,methods=methods,costs=costs))
        if digest(locked)!=block['locked_choices_hash']:raise ValueError('preassessment_choice_hash')
        means={m:{str(b):sum(row['metrics'][m][str(b)] for row in block['rows'])/8 for b in BUDGETS} for m in METHODS}
        if digest(means)!=digest(block['means']):raise ValueError('repetition_aggregation')
    if digest(summarize(r['blocks'],c))!=digest(r['analysis']):raise ValueError('source_acquisition_arithmetic')
    if r['frozen_before']!=FROZEN or r['frozen_after']!=FROZEN:raise ValueError('historical_checkpoint_preservation')
    expected=dict(real_steps=3072,source_labels=2048,target_support=512,target_query=512,updates=8,
        imagined_transitions=0,network_forwards=0,fitted_ridge_models=8,learned_coefficients=80,selector_training_cases=4608,program_instructions=instructions,
        cached_target_answer_exposures=3072,target_policy_paths=384,uniform_assessment_subsets=6848)
    for k,v in expected.items():
        if type(o['resources'].get(k)) is not int or o['resources'][k]!=v:raise ValueError('resource_accounting')
    if o['resources']['real_steps']>caps['real_steps']:raise ValueError('resource_cap')
    for k in ('cpu_s','worker_wall_s'):
        if type(o['resources'].get(k)) not in (int,float) or not math.isfinite(o['resources'][k]) or o['resources'][k]<0:raise ValueError('finite_runtime')


def saved_replay(root):
    root=Path(root);raw=(root/'artifacts/seed_source_acquisition.json').read_bytes();r=json.loads(raw)
    audit=json.loads((root/'artifacts/seed_source_acquisition_audit.json').read_text())
    # GUI is a read-only receipt view, NOT an implicit numerical refit.
    # Explicit verify_seed_source_acquisition remains the full numerical audit.
    if audit.get('valid') is not True or audit.get('raw_sha256')!=hashlib.sha256(raw).hexdigest() or r.get('declared_complete') is not True:raise ValueError('saved_acquisition_audit_required_or_hash_mismatch')
    config_check(r['config'])
    return dict(id='seed-source-acquisition-1',mode='exploration',status='complete_development',
        wall_s=r['host_receipt']['wall_s'],memory_mb=r['host_receipt']['peak_sampled_rss_mb'],revision=r['execution_sha'],
        resources=r['resources'],curve=[],source_acquisition=r['analysis'],verification='saved_independent_audit_hash')
