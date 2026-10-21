"""Independent saved-data reconstruction. No collection or candidate training."""
import hashlib
import itertools as it
import json
import math
from pathlib import Path
import random
import statistics as st
import subprocess
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from verify_seed_source_acquisition import reference_table
from nexus.seed import conditioned_acquisition as q
from nexus.evolution1.catalogue import digest

BASE='a290b4a10da40db27bc2c41c754d45e7dfbba11d'


def inputs(task):
    xs=list(range(16));random.Random(task+200000).shuffle(xs)
    return sorted(xs[:8]),sorted(xs[8:])


def base_features(t,x,observed,remaining):
    p=float(t[:,x].mean())
    return [1.]+[float(bool(x&(1<<i))) for i in range(4)]+[p,p*(1-p),min(((x^z).bit_count()/4 for z,_ in observed),default=1.),sum(y for _,y in observed)/len(observed) if observed else .5,remaining/8]


def extra(kind,x,query):
    if kind=='conditioned':
        ds=np.asarray([(x^z).bit_count()/4 for z in query]);return [float(ds.mean()),float(np.mean(ds*ds)),float(ds.min())]
    if kind=='blind_capacity':return [float(bool(x&1) and bool(x&2)),float(bool(x&4) and bool(x&8)),float(x.bit_count()%2)]
    return []


def weighted_gain(t,x,query,w):
    ys=t[:,query].astype(float);p=ys.mean(0);w=w/w.sum()
    before=float(np.average(np.mean((ys-p)**2,axis=1),weights=w));after=0.
    for answer in (False,True):
        mask=t[:,x]==answer
        if mask.any():after+=float(np.dot(w[mask],np.mean((ys[mask]-ys[mask].mean(0))**2,axis=1)))
    return before-after


def verify(root=ROOT):
    raw=(root/'artifacts/seed_conditioned_acquisition.json').read_bytes();r=json.loads(raw);c=r['config'];q.config_check(c);q.validate_grid(r,c)
    table,instructions=reference_table();sha=lambda b:hashlib.sha256(b).hexdigest()
    assert r['declared_complete'] is True and r['registration']['dirty'] is False
    assert r['catalogue_instructions']==instructions
    old=json.loads((root/'artifacts/seed_source_acquisition.json').read_text())['assignment']
    excluded={i for b in old for ids in b.values() for i in ids}
    assert sorted(excluded)==r['excluded_historical_programs']
    used=[i for b in r['assignment'] for ids in b.values() for i in ids]
    assert len(used)==len(set(used))==128 and not set(used)&excluded
    # Derive the new assignment independently from registered group sizes.
    # Catalogue alternates nonnegated/negated WITHIN each monomial tuple.
    groups=[0,1]*91+[2,3]*364
    bins=[[i for i,g in enumerate(groups) if g==j and i not in excluded] for j in range(4)]
    rng=random.Random(c['assignment_seed'])
    for b in bins:rng.shuffle(b)
    for b in r['assignment']:
        src=[];target=[]
        for g in range(4):
            n=c['source_counts'][g];k=c['target_counts'][g];src+=bins[g][:n];target+=bins[g][n:n+k];bins[g]=bins[g][n+k:]
        rng.shuffle(src);rng.shuffle(target);assert b==dict(source=src,target=target)
    source_cases=0;paths=0;means={m:[] for m in q.METHODS};all_costs={m:0 for m in q.POLICIES}
    for bi,block in enumerate(r['blocks']):
        base=block['model']['base'];source={s['task']:s['answers'] for s in block['source']}
        for s,index in zip(block['source'],r['assignment'][bi]['source']):assert s['role']=='source' and s['answers']==table[index].tolist()
        assert len(base['cases'])==288
        source_entries=0;feature_entries=0
        for s in block['source']:
            source_entries+=table.size;pool,query=inputs(s['task']);order=list(range(8));random.Random(s['task']+700).shuffle(order);ids=np.arange(910)
            for prefix,idx in enumerate(order):
                source_entries+=len(ids)*8
                for available in (j for j in range(8) if j not in order[:prefix]):
                    child=ids[table[ids,pool[available]]==s['answers'][pool[available]]]
                    source_entries+=2*len(ids)+8*len(child);feature_entries+=len(ids)
                source_entries+=len(ids);ids=ids[table[ids,pool[idx]]==s['answers'][pool[idx]]]
        assert block['fit_cost']['matrix_entries']==source_entries
        assert block['fit_cost']['feature_scalars']==288*16 and block['fit_cost']['ridge_fits']==3
        assert block['fit_cost']['query_distance_operations']==288*8 and block['fit_cost']['candidate_interaction_operations']==288*3
        split=base['training_cost_split'];identity=8*table.size
        assert split==dict(prior_identity_entries=identity,utility_feature_entries=feature_entries,learned_utility_entries=source_entries-identity,static_utility_entries=source_entries-identity-feature_entries)
        for case in base['cases']:
            task=case['task'];pool,query=inputs(task);order=list(range(8));random.Random(task+700).shuffle(order);ids=np.arange(910);seen=[]
            for idx in order[:case['prefix']]:
                x=pool[idx];y=source[task][x];ids=ids[table[ids,x]==y];seen.append((x,y))
            x=case['candidate'];f=base_features(table[ids],x,seen,8-case['prefix'])
            assert np.allclose(f,case['x'],atol=1e-12,rtol=0)
            truth=np.asarray(source[task])[query];before=np.mean((table[np.ix_(ids,query)].mean(0)-truth)**2)
            child=ids[table[ids,x]==source[task][x]];after=np.mean((table[np.ix_(child,query)].mean(0)-truth)**2)
            assert abs(float(before-after)-case['utility'])<1e-12;source_cases+=1
        for kind in ('blind','blind_capacity','conditioned'):
            X=np.asarray([v['x']+extra(kind,v['candidate'],inputs(v['task'])[1]) for v in base['cases']]);Y=np.asarray([v['utility'] for v in base['cases']])
            scale=np.sqrt((X*X).mean(0));scale[scale<1e-8]=1.;Z=X/scale
            beta=np.linalg.solve(2*Z.T@Z+c['ridge']*np.eye(X.shape[1]),2*Z.T@Y)
            fitted=block['model']['models'][kind]
            assert np.allclose(scale,fitted['scale'],atol=1e-12,rtol=0) and np.allclose(beta,fitted['beta'],atol=1e-10,rtol=0)
        assert base['scale']==block['model']['models']['blind']['scale'] and base['beta']==block['model']['models']['blind']['beta']
        counts=[sum(groups[i]==g for i in r['assignment'][bi]['source']) for g in range(4)]
        assert counts==base['group_counts']
        weights=np.asarray([(counts[g]+1)/([91,91,364,364][g]) for g in groups])
        assert np.allclose(weights,base['prior_weights'],atol=1e-12,rtol=0)
        static=[]
        for x in range(16):
            ys=[v['utility'] for v in base['cases'] if v['candidate']==x]
            static.append(st.mean(ys) if ys else st.mean([v['utility'] for v in base['cases']]))
        assert np.allclose(static,base['static'],atol=1e-12,rtol=0)
        task_metrics=[]
        for row,index in zip(block['rows'],r['assignment'][bi]['target']):
            pool,query=inputs(row['task']);truth=table[index]
            assert row['pool']==pool and row['query']==query and not set(pool)&set(query)
            assert row['support_answers']==truth[pool].tolist() and row['query_answers']==truth[query].tolist()
            metrics={}
            for method,path in row['methods'].items():
                ids=np.arange(910);seen=[];remaining=list(range(8));errors={};entries=0
                for number,step in enumerate(path['steps'],1):
                    scores=[]
                    for idx in remaining:
                        x=pool[idx];t=table[ids]
                        if method in c['feature_counts']:
                            f=base_features(t,x,seen,len(remaining))+extra(method,x,query);fitted=block['model']['models'][method]
                            score=float(np.asarray(f)/fitted['scale']@np.asarray(fitted['beta']));entries+=len(ids)
                        elif method=='variance':
                            p=float(t[:,x].mean());score=p*(1-p);entries+=len(ids)
                        elif method in ('model_based','source_prior'):
                            w=np.ones(len(ids)) if method=='model_based' else weights[ids];score=weighted_gain(t,x,query,w);entries+=len(ids)*17
                        elif method=='source_static':score=static[x]
                        else:score=-idx
                        scores.append(score)
                    # Tie tolerance is NOT changed for arithmetic replay. If
                    # roundoff changes the exact argmax, saved scores below
                    # remain the canonical tie reference and are checked 1e-12.
                    assert np.allclose(scores,step['scores'],atol=1e-12,rtol=0)
                    best=max(range(len(remaining)),key=lambda j:(step['scores'][j],-remaining[j]));idx=remaining[best]
                    assert step['index']==idx and step['input']==pool[idx] and step['remaining']==remaining
                    assert step['answer'] is row['support_answers'][idx]
                    entries+=len(ids);remaining.remove(idx);ids=ids[table[ids,pool[idx]]==step['answer']];seen.append((pool[idx],step['answer']))
                    assert ids.tolist()==step['posterior'] and all(np.all(table[ids,x]==y) for x,y in seen)
                    if number in (1,2,4,8):
                        pred=table[np.ix_(ids,query)].mean(0);entries+=8*len(ids)
                        assert np.allclose(pred,path['snapshots'][str(number)]['prediction'],atol=1e-12,rtol=0)
                        errors[str(number)]=float(np.mean((pred-truth[query])**2))
                cost=row['costs'][method];assert not remaining and cost['matrix_entries']==entries
                dimension=c['feature_counts'].get(method,0)
                assert cost['feature_scalars']==36*dimension and cost['ridge_predictions']==(36 if dimension else 0)
                assert cost['query_distance_operations']==(288 if method=='conditioned' else 0)
                assert cost['candidate_interaction_operations']==(108 if method=='blind_capacity' else 0)
                metrics[method]=errors;all_costs[method]+=entries;paths+=1
            random_metrics={};uniform_entries=0
            for budget in (1,2,4,8):
                losses=[]
                for subset in it.combinations(range(8),budget):
                    ids=np.arange(910)
                    for idx in subset:
                        uniform_entries+=len(ids);ids=ids[table[ids,pool[idx]]==truth[pool[idx]]]
                    uniform_entries+=8*len(ids);p=table[np.ix_(ids,query)].mean(0);losses.append(float(np.mean((p-truth[query])**2)))
                random_metrics[str(budget)]=st.mean(losses)
            assert row['uniform_cost']['matrix_entries']==uniform_entries and row['uniform_cost']['uniform_subsets']==107
            metrics['uniform_expectation']=random_metrics;metrics['keep']={str(b):.25 for b in (1,2,4,8)}
            for method in q.METHODS:
                assert all(abs(metrics[method][str(b)]-row['metrics'][method][str(b)])<1e-12 for b in (1,2,4,8))
            assert max(metrics[m]['8'] for m in q.METHODS if m!='keep')-min(metrics[m]['8'] for m in q.METHODS if m!='keep')<1e-12
            task_metrics.append(metrics)
        for method in q.METHODS:
            by_budget={str(b):st.mean([v[method][str(b)] for v in task_metrics]) for b in (1,2,4,8)}
            assert all(abs(by_budget[str(b)]-block['means'][method][str(b)])<1e-12 for b in (1,2,4,8))
            means[method].append(st.mean([by_budget[str(b)] for b in (1,2,4)]))
    intervals={}
    for method,values in means.items():
        assert abs(st.mean(values)-r['analysis']['primary'][method])<1e-12
        if method=='conditioned':continue
        ds=[x-y for x,y in zip(values,means['conditioned'])];mean=st.mean(ds);half=2.364624251*st.stdev(ds)/math.sqrt(8)
        intervals[method]=dict(mean=mean,low=mean-half,high=mean+half)
        assert all(abs(v-r['analysis']['contrasts'][method][k])<1e-12 for k,v in intervals[method].items())
    primary={m:st.mean(v) for m,v in means.items()};wins={m:sum(x>y for x,y in zip(means[m],means['conditioned'])) for m in ('blind','blind_capacity')}
    transfer=all(primary['conditioned']<=primary[m]*.95 and intervals[m]['low']>0 for m in ('blind','blind_capacity')) and wins['blind']>=6 and all(primary['conditioned']<=primary[m]+.005 for m in ('model_based','source_prior'))
    strong=all(primary['conditioned']<=primary[m]*.95 and intervals[m]['low']>0 for m in ('model_based','source_prior'))
    assert wins==r['analysis']['repetition_wins'] and r['analysis']['transfer_screen']==('passed' if transfer else 'failed') and r['analysis']['strong_advantage_screen']==('passed' if strong else 'failed')
    assert source_cases==2304 and paths==512 and r['resources']['real_steps']==2048 and r['resources']['updates']==24
    assert r['execution_debit_s']==math.ceil(r['host_receipt']['wall_s'])+1
    assert abs(r['session_used_s']-c['carried_used_s']-r['execution_debit_s'])<1e-8
    assert r['frozen_before']==r['frozen_after']==q.a.FROZEN
    for name,h in q.a.FROZEN.items():assert sha((root/name).read_bytes())==h
    for name,h in r['registration']['source_hashes'].items():assert sha(subprocess.check_output(['git','show',r['execution_sha']+':'+name],cwd=root))==h
    historical=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'artifacts'],cwd=root,text=True).splitlines()
    for name in historical:assert (root/name).read_bytes()==subprocess.check_output(['git','show',BASE+':'+name],cwd=root)
    return dict(valid=True,raw_sha256=sha(raw),execution_sha=r['execution_sha'],historical_artifacts_unchanged=len(historical),
        source_cases_verified=source_cases,target_paths_verified=paths,primary_means=primary,paired_intervals=intervals,
        target_matrix_entries=all_costs,transfer_screen=transfer,strong_advantage_screen=strong,new_collection=0)


if __name__=='__main__':
    result=verify()
    if '--write' in sys.argv:
        with (ROOT/'artifacts/seed_conditioned_acquisition_audit.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
