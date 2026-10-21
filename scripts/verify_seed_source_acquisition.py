"""Saved arithmetic audit. No registered runner, label collection or live agent."""
import argparse
import hashlib
import itertools as it
import json
import math
from pathlib import Path
import random
import statistics as st
import subprocess
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE='4bd8f381e80eddeae88299ecc0c382cec4409387'


def reference_table():
    # Algebraic parity, independent of the runtime expression interpreter.
    terms=[x for k in (1,2,3) for x in it.combinations(range(4),k)];rows=[];instructions=0
    for k in (2,3):
        for group in it.combinations(terms,k):
            for negate in (0,1):
                rows.append([bool((sum(all(x&(1<<bit) for bit in term) for term in group)+negate)%2) for x in range(16)])
                instructions+=16*(sum(1+len(term) for term in group)+2*(k-1)+negate)
    return np.asarray(rows,bool),instructions


def verify(root=ROOT):
    raw=(root/'artifacts/seed_source_acquisition.json').read_bytes();r=json.loads(raw);c=r['config'];table,instructions=reference_table()
    if r['declared_complete'] is not True or r['registration']['dirty'] or instructions!=r['catalogue_instructions']:raise ValueError('complete_clean_programme_count')
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    gitread=lambda ref,p:subprocess.check_output(['git','show',ref+':'+p],cwd=root)
    for name,h in r['registration']['source_hashes'].items():
        if sha(gitread(r['execution_sha'],name))!=h:raise ValueError('source_provenance')
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'artifacts'],cwd=root,text=True).splitlines()
    for name in paths:
        if (root/name).read_bytes()!=gitread(BASE,name):raise ValueError('historical_evidence_changed')
    used=[i for block in r['assignment'] for indices in block.values() for i in indices]
    if len(used)!=192 or len(set(used))!=192 or [x['id'] for x in r['blocks']]!=c['families']:raise ValueError('disjoint_task_grid')
    means={m:[] for m in c['methods']};source_cases=0;policies=0;target_entries={m:0 for m in c['methods'] if m not in ('keep','uniform_expectation')}
    for bi,block in enumerate(r['blocks']):
        model=block['model'];source={s['task']:s['answers'] for s in block['source']}
        if set(source)!=set(c['tasks']['train'][16*bi:16*(bi+1)]):raise ValueError('source_task_grid')
        for row,index in zip(block['source'],r['assignment'][bi]['source']):
            if row['answers']!=table[index].tolist():raise ValueError('source_labels')
        for case in model['cases']:
            task=case['task'];prefix=case['prefix'];pool0=list(range(16));random.Random(task+200000).shuffle(pool0)
            pool=sorted(pool0[:8]);query=sorted(pool0[8:]);order=list(range(8));random.Random(task+700).shuffle(order)
            ids=np.arange(910);observed=[]
            for q in order[:prefix]:
                x=pool[q];answer=source[task][x];ids=ids[table[ids,x]==answer];observed.append((x,answer))
            x=case['candidate'];p=float(table[ids,x].mean());expected=[1.]+[float(bool(x&(1<<i))) for i in range(4)]+[p,p*(1-p),min(((x^q).bit_count()/4 for q,_ in observed),default=1.),sum(y for _,y in observed)/len(observed) if observed else .5,(8-prefix)/8]
            if not np.allclose(expected,case['x'],rtol=0,atol=1e-12):raise ValueError('preanswer_source_features')
            before=np.mean((table[np.ix_(ids,query)].mean(0)-np.asarray(source[task])[query])**2)
            child=ids[table[ids,x]==source[task][x]];after=np.mean((table[np.ix_(child,query)].mean(0)-np.asarray(source[task])[query])**2)
            if abs(float(before-after)-case['utility'])>1e-12:raise ValueError('source_utility')
            source_cases+=1
        X=np.asarray([v['x'] for v in model['cases']]);Y=np.asarray([v['utility'] for v in model['cases']]);scale=np.sqrt((X*X).mean(0));scale[scale<1e-8]=1.;Z=X/scale
        beta=np.linalg.solve(2*Z.T@Z+c['ridge']*np.eye(10),2*Z.T@Y)
        if not np.allclose(scale,model['scale'],rtol=0,atol=1e-12) or not np.allclose(beta,model['beta'],rtol=0,atol=1e-10):raise ValueError('source_only_ridge')
        task_metrics=[]
        for row,index in zip(block['rows'],r['assignment'][bi]['target']):
            pool=row['pool'];query=row['query'];truth=table[index]
            if set(pool)&set(query) or len(set(pool+query))!=16 or row['support_answers']!=truth[pool].tolist() or row['query_answers']!=truth[query].tolist():raise ValueError('target_separation')
            metrics={}
            for method,path in row['methods'].items():
                ids=np.arange(910);seen=[];observed=[];risk={};entries=0
                for step_number,step in enumerate(path['steps'],1):
                    q=step['index'];available=[i for i in range(8) if i not in seen]
                    if q not in available or step['remaining']!=available or q!=available[max(range(len(available)),key=lambda j:(step['scores'][j],-available[j]))]:raise ValueError('locked_argmax_or_budget')
                    if method in ('learned','variance'):entries+=len(ids)*len(available)
                    elif method in ('model_based','source_prior'):entries+=len(ids)*len(available)*(2*len(query)+1)
                    entries+=len(ids);seen.append(q)
                    if step['answer'] is not row['support_answers'][q]:raise ValueError('revealed_answer')
                    ids=ids[table[ids,pool[q]]==step['answer']];observed.append((pool[q],step['answer']))
                    if ids.tolist()!=step['posterior']:raise ValueError('version_space_update')
                    if step_number in (1,2,4,8):
                        entries+=len(ids)*len(query);pred=table[np.ix_(ids,query)].mean(0)
                        if not np.allclose(pred,path['snapshots'][str(step_number)]['prediction'],rtol=0,atol=1e-12):raise ValueError('predictions')
                        risk[str(step_number)]=float(np.mean((pred-truth[query])**2))
                if len(seen)!=8 or len(set(seen))!=8 or entries!=row['costs'][method]['matrix_entries']:raise ValueError('budget_or_runtime_cost')
                target_entries[method]+=entries;metrics[method]=risk;policies+=1
            uniform={}
            for budget in (1,2,4,8):
                losses=[]
                for subset in it.combinations(range(8),budget):
                    ids=np.arange(910)
                    for q in subset:ids=ids[table[ids,pool[q]]==truth[pool[q]]]
                    pred=table[np.ix_(ids,query)].mean(0);losses.append(float(np.mean((pred-truth[query])**2)))
                uniform[str(budget)]=sum(losses)/len(losses)
            metrics['uniform_expectation']=uniform;metrics['keep']={str(b):.25 for b in (1,2,4,8)}
            for m in c['methods']:
                if set(row['metrics'][m])!={'1','2','4','8'} or any(abs(metrics[m][str(b)]-row['metrics'][m][str(b)])>1e-12 for b in (1,2,4,8)):raise ValueError('query_metric_arithmetic')
            task_metrics.append(metrics)
        if len(task_metrics)!=8:raise ValueError('target_task_grid')
        for m in c['methods']:
            values={str(b):sum(d[m][str(b)] for d in task_metrics)/8 for b in (1,2,4,8)}
            means[m].append(sum(values[str(b)] for b in (1,2,4))/3)
            if any(abs(values[str(b)]-block['means'][m][str(b)])>1e-12 for b in (1,2,4,8)):raise ValueError('repetition_mean')
    intervals={}
    for m,values in means.items():
        if abs(st.mean(values)-r['analysis']['primary'][m])>1e-12:raise ValueError('primary_mean')
        if m=='learned':continue
        d=[x-y for x,y in zip(values,means['learned'])];mean=st.mean(d);half=2.364624251*st.stdev(d)/math.sqrt(8)
        intervals[m]=dict(mean=mean,low=mean-half,high=mean+half)
        if any(abs(v-r['analysis']['contrasts'][m][k])>1e-12 for k,v in intervals[m].items()):raise ValueError('selector_level_interval')
    if policies!=384 or source_cases!=4608 or r['resources']['real_steps']!=3072 or r['execution_debit_s']!=math.ceil(r['host_receipt']['wall_s'])+1:raise ValueError('resources')
    return dict(valid=True,raw_sha256=sha(raw),execution_sha=r['execution_sha'],historical_artifacts_unchanged=len(paths),
        source_cases_verified=source_cases,target_paths_verified=policies,primary_means={m:st.mean(v) for m,v in means.items()},
        paired_selector_intervals=intervals,target_materialized_entries=target_entries,new_collection=0,
        scope='independent saved-data arithmetic, not a new experiment')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',type=Path);args=p.parse_args();result=verify()
    if args.write:
        with args.write.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(result,indent=2))
