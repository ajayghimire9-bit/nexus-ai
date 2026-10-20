"""Fresh authored investigation transfer, through the existing bounded host.

Policies see a frozen public hypothesis grammar, explicit observed role bindings
and requested support answers. The evaluator owns task laws and final outcomes.
This tests question-order reuse across encodings, not discovery of an unknown
grammar or unrestricted transfer to arbitrary environments.
"""
import copy
import hashlib
import json
import math
import random
import statistics as st
import sys
import time
from functools import lru_cache
from pathlib import Path
from nexus.evolution1.catalogue import digest
from .structure.investigation import learn, run as run_tree
from .question_selection import LabelOracle
from .experimental import write_new

METHODS=['learned','fixed_order','no_library','greedy','exhaustive']
BUDGETS=[1,2,4,8]
FROZEN={'artifacts/seed_contract_gui.json':'cfe06a6737c8e225564ebcaea9ba4678aabd45b61129828e64354e74fa3c8d1b',
        'artifacts/seed_readout_6301.json':'8129cbd4768f4cd5dce938cd8b6740172bf5dbe8742dcb97c497951ad5e87745'}
BITS=[tuple(bool(i & (1<<j)) for j in range(3)) for i in range(8)]


def hypotheses(x):
    a,b,c=x
    return (a,b,c,a and b,a or b,a!=b,sum(x)>=2,not a)


TABLE=tuple(tuple(hypotheses(x)[h] for x in BITS) for h in range(8))


def config_check(c):
    expected=dict(schema='seed_investigation_transfer_v1',tasks=dict(train=list(range(982100,982132)),target=list(range(982200,982232))),
        source_families=['attributes','thresholds'],target_families=['temporal','spatial'],methods=METHODS,budgets=BUDGETS,
        final_episodes=32,tree_depth=3,tree_nodes=15,search_nodes=4096,minimum_question_gain=.5,minimum_accuracy_gain=.05,
        strong_question_tolerance=.25,strong_accuracy_tolerance=.01,max_wall_s=60,max_authored_steps=5000,max_outer_updates=0,
        max_imagined_transitions=0,carried_used_s=1979.6321034559958,carried_remaining_s=1620.3678965440042)
    if digest(c)!=digest(expected): raise ValueError('locked_investigation_recipe')
    return dict(real_steps=5000,imagined_transitions=0,outer_updates=0)


def binding(seed,family):
    names=[f'role{i}' for i in range(3)];random.Random(seed+11).shuffle(names)
    return dict(family=family,roles=names)


def encode(bits,bind,seed):
    rng=random.Random(seed);family=bind['family'];names=bind['roles']
    if family=='attributes': return {name:bit for name,bit in zip(names,bits)}
    if family=='thresholds': return {name:rng.randint(1,20)*(1 if bit else -1) for name,bit in zip(names,bits)}
    if family=='temporal':
        events=[]
        for name,bit in zip(names,bits): events.extend([name+'a',name+'b'] if bit else [name+'b',name+'a'])
        return dict(events=events,episode_token=rng.randrange(1000000))
    return {name:dict(left=rng.randint(0,20),gap=rng.randint(1,5)*(1 if bit else -1)) for name,bit in zip(names,bits)}


def decode(raw,bind):
    """Supplied public sensor adapter, independent of task law and target answers."""
    family=bind['family'];names=bind['roles']
    if family=='attributes': return tuple(raw[n] for n in names)
    if family=='thresholds': return tuple(raw[n]>0 for n in names)
    if family=='temporal': return tuple(raw['events'].index(n+'a')<raw['events'].index(n+'b') for n in names)
    if family=='spatial': return tuple(raw[n]['left']<raw[n]['left']+raw[n]['gap'] for n in names)
    raise ValueError('public_binding_family')


def truth(seed): return random.Random(seed+101).randrange(8)  # evaluator only


def choose(method,posterior,remaining,history,library,random_order,costs):
    """No evaluator, task ID, hidden answer, query or retention argument."""
    if method=='fixed_order': return min(remaining)
    if method=='no_library': return next(i for i in random_order if i in remaining)
    if method=='learned':
        tree=library['tree']
        while tree['op']=='probe':
            costs['tree_nodes']+=1;i=tree['index']
            if i not in history: return i if i in remaining else min(remaining)
            tree=tree['branches'][int(history[i])]
        return min(remaining) # same fixed-order fallback, never secret leaf identity
    def groups(ids,q):
        costs['hypothesis_predictions']+=len(ids)
        return tuple(tuple(h for h in ids if TABLE[h][q] is v) for v in (False,True))
    if method=='greedy':
        return min(remaining,key=lambda q:(sum(len(g)**2 for g in groups(posterior,q)),q))
    if method!='exhaustive': raise ValueError('registered_method')
    nodes=0
    @lru_cache(None)
    def optimal(ids,available):
        nonlocal nodes
        nodes+=1;costs['search_nodes']+=1
        if nodes>4096: raise ValueError('bounded_search_exhausted_invalid_not_silent_fallback')
        if len(ids)<=1:return 0.
        scores=[]
        for q in available:
            children=groups(ids,q)
            if any(len(g)==len(ids) for g in children): continue
            next_av=tuple(i for i in available if i!=q)
            scores.append((1+sum(len(g)/len(ids)*optimal(g,next_av) for g in children if g),q))
        return min(scores)[0] if scores else 9.
    scored=[]
    for q in remaining:
        children=groups(posterior,q);left=tuple(i for i in remaining if i!=q)
        scored.append((1+sum(len(g)/len(posterior)*optimal(g,left) for g in children if g),q))
    return min(scored)[1]


def adapt(method,library,reveal,seed=0):
    posterior=list(range(8));remaining=list(range(8));history={};steps=[];snapshots={}
    order=list(range(8));random.Random(seed).shuffle(order)
    costs=dict(tree_nodes=0,hypothesis_predictions=0,search_nodes=0)
    for budget in range(1,9):
        if len(posterior)>1:
            q=choose(method,tuple(posterior),tuple(remaining),history,library,order,costs)
            # Choice is captured before the only reveal call.
            step=dict(question=q,posterior_before=list(posterior));answer=reveal(q)
            if type(answer) is not bool: raise ValueError('boolean_observed_answer')
            history[q]=answer;remaining.remove(q)
            costs['hypothesis_predictions']+=len(posterior)
            posterior=[h for h in posterior if TABLE[h][q] is answer]
            if not posterior: raise ValueError('inconsistent_support')
            step.update(answer=answer,posterior_after=list(posterior));steps.append(step)
        if budget in BUDGETS: snapshots[str(budget)]=dict(posterior=list(posterior),questions=len(steps))
    return dict(steps=steps,snapshots=snapshots,questions_to_identify=len(steps) if len(posterior)==1 else 9,costs=costs)


def paired(values):
    mean=st.mean(values);half=2.039513*st.stdev(values)/math.sqrt(len(values)) if len(values)>1 else 0
    return dict(mean=mean,low=mean-half,high=mean+half,n=len(values),unit='target_task_conditional_on_one_library_two_families')


def analysis(rows,c):
    means={m:dict(questions=st.mean(r['methods'][m]['questions_to_identify'] for r in rows),
        accuracy={str(b):st.mean(r['methods'][m]['metrics'][str(b)]['accuracy'] for r in rows) for b in BUDGETS},
        brier={str(b):st.mean(r['methods'][m]['metrics'][str(b)]['brier'] for r in rows) for b in BUDGETS}) for m in METHODS}
    contrasts={m:paired([r['methods'][m]['questions_to_identify']-r['methods']['learned']['questions_to_identify'] for r in rows]) for m in METHODS[1:]}
    checks={m:contrasts[m]['mean']>=c['minimum_question_gain'] and contrasts[m]['low']>0 and means['learned']['accuracy']['2']-means[m]['accuracy']['2']>=c['minimum_accuracy_gain'] for m in ('fixed_order','no_library')}
    checks.update({m:means['learned']['questions']<=means[m]['questions']+c['strong_question_tolerance'] and means['learned']['accuracy']['2']>=means[m]['accuracy']['2']-c['strong_accuracy_tolerance'] for m in ('greedy','exhaustive')})
    return dict(means=means,question_savings=contrasts,checks=checks,screen='passed' if all(checks.values()) else 'failed',
        by_family={family:{m:st.mean(r['methods'][m]['questions_to_identify'] for r in rows if r['family']==family) for m in METHODS} for family in c['target_families']},
        claim_scope='authored question-order transfer with supplied sensor bindings and shared finite hypotheses',promoted=False)


def run(request):
    c=request['inputs']['study_config'];config_check(c);start=time.monotonic();directory=Path.cwd()
    work=dict(real_steps=0,imagined_transitions=0,updates=0,network_forwards=0,source_answers=0,target_pool_observations=0,target_answers=0,final_observations=0,assessment_predictions=0)
    result=dict(config=c,declared_complete=False,rows=[],source=[],library=None,analysis=None)
    def check():
        if time.monotonic()-start>c['max_wall_s']-3: raise TimeoutError('registered_cap')
        if work['real_steps']>c['max_authored_steps']: raise ValueError('authored_observation_cap')
    def charge(name,n):work[name]+=n;work['real_steps']+=n;check()
    def persist():
        temp=directory/'progress.tmp';temp.write_text(json.dumps(result,allow_nan=False));temp.replace(directory/'progress.json')
    try:
        root=Path(request['inputs']['repository'])
        checkpoint_hashes=lambda:{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in FROZEN}
        result['frozen_checkpoints_before']=checkpoint_hashes()
        if result['frozen_checkpoints_before']!=FROZEN:raise ValueError('historical_checkpoint_hash')
        traces=[]
        for i,seed in enumerate(c['tasks']['train']):
            family=c['source_families'][i//16];bind=binding(seed,family);law=truth(seed);episodes=[]
            for q,bits in enumerate(BITS):
                raw=encode(bits,bind,seed*1000+q);observed=decode(raw,bind);answer=bool(hypotheses(observed)[law]);charge('source_answers',1)
                episodes.append(dict(id=f'source-{seed}-{q}',raw=raw,bits=list(observed),answer=answer))
            answers=[r['answer'] for r in episodes]
            source_identified=next(h for h in range(8) if list(TABLE[h])==answers)
            traces.append(dict(role='source',episode=f'source-{seed}',answers=answers,hypothesis=source_identified))
            result['source'].append(dict(task=seed,family=family,binding=bind,episodes=episodes))
        fit_start=time.perf_counter()
        library=learn(traces,max_depth=c['tree_depth'],max_nodes=c['tree_nodes']);result['library']=copy.deepcopy(library)
        work.update(source_fit_wall_s=time.perf_counter()-fit_start,source_trace_rows=len(traces),source_trace_answers=sum(len(t['answers']) for t in traces),neural_parameters=0,library_nodes=library['nodes'])
        frozen=digest(library);source_hash=digest(result['source']);result['library_hash']=frozen;result['source_hash']=source_hash
        retention=lambda:[run_tree(library,lambda i,a=t['answers']:a[i],budget=3) for t in traces]
        before=retention()
        write_new(directory/'frozen_library.json',dict(library=library,sha256=frozen,source_hash=source_hash))
        result['frozen_before_target']=True
        pending=[]
        for i,seed in enumerate(c['tasks']['target']):
            check();family=c['target_families'][i//16];bind=binding(seed,family);law=truth(seed)
            pool=[encode(bits,bind,seed*1000+q) for q,bits in enumerate(BITS)];charge('target_pool_observations',8)
            labels=[bool(hypotheses(decode(raw,bind))[law]) for raw in pool]
            row=dict(task=seed,family=family,binding=bind,pool=pool,support_bank_answers=labels,methods={})
            for method in METHODS:
                oracle=LabelOracle(labels,8)
                def reveal(q):
                    value=oracle.reveal(q);work['target_answers']+=1;check();return value
                row['methods'][method]=adapt(method,library,reveal,seed+700)
            pending.append(row);result['rows']=pending;persist()
        locked=digest(pending);write_new(directory/'locked_target_choices.json',dict(sha256=locked,rows=pending))
        result['choices_hash']=locked;result['choices_locked_before_final']=True
        # Only now generate evaluator-owned final episodes; no selection API sees them.
        for row in pending:
            seed=row['task'];law=truth(seed);final=[];rng=random.Random(seed+90000)
            for j in range(c['final_episodes']):
                bits=BITS[rng.randrange(8)];raw=encode(bits,row['binding'],seed*1000+100+j)
                observed=decode(raw,row['binding']);answer=bool(hypotheses(observed)[law]);charge('final_observations',1)
                final.append(dict(id=f'final-{seed}-{j}',raw=raw,bits=list(observed),answer=answer))
            row['final']=final;row['data_hash']=digest(dict(binding=row['binding'],pool=row['pool'],final=final))
            for method,data in row['methods'].items():
                data['predictions']={};data['metrics']={}
                for b in BUDGETS:
                    ids=data['snapshots'][str(b)]['posterior'];pred=[st.mean(hypotheses(r['bits'])[h] for h in ids) for r in final]
                    work['assessment_predictions']+=len(pred);data['predictions'][str(b)]=pred
                    data['metrics'][str(b)]=dict(accuracy=st.mean((p>=.5)==r['answer'] for p,r in zip(pred,final)),brier=st.mean((p-r['answer'])**2 for p,r in zip(pred,final)))
        result['retention_before']=before;result['retention_after']=retention();result['unchanged_library']=digest(library)==frozen
        if not result['unchanged_library'] or result['retention_before']!=result['retention_after']: raise ValueError('frozen_retention_failure')
        result['frozen_checkpoints_after']=checkpoint_hashes()
        if result['frozen_checkpoints_after']!=FROZEN:raise ValueError('historical_checkpoint_changed')
        result['analysis']=analysis(pending,c);result['declared_complete']=True;persist()
    except Exception as error:
        result.update(failure=dict(type=type(error).__name__,message=str(error)),partial_resources=work);persist();raise
    work.update(cpu_s=time.process_time(),worker_wall_s=time.monotonic()-start,
                tree_nodes=sum(d['costs']['tree_nodes'] for r in pending for d in r['methods'].values()),
                hypothesis_predictions=sum(d['costs']['hypothesis_predictions'] for r in pending for d in r['methods'].values()),
                search_nodes=sum(d['costs']['search_nodes'] for r in pending for d in r['methods'].values()),
                cached_retention_reads=sum(t['real_probes'] for t in before+result['retention_after']))
    return dict(adapter=c['schema'],study=result,resources=work,runtime=dict(python=sys.version,device='cpu',threads=1))


def validate_output(output,c,caps):
    config_check(c);r=output['study'];work=output['resources']
    if r.get('frozen_checkpoints_before')!=FROZEN or r.get('frozen_checkpoints_after')!=FROZEN:raise ValueError('frozen_checkpoint_integrity')
    if r.get('declared_complete') is not True or digest(r['config'])!=digest(c) or not r.get('frozen_before_target') or not r.get('choices_locked_before_final'):raise ValueError('incomplete_or_unlocked')
    if [s['task'] for s in r['source']]!=c['tasks']['train'] or [s['task'] for s in r['rows']]!=c['tasks']['target']:raise ValueError('complete_task_grid')
    if digest(r['source'])!=r['source_hash'] or digest(r['library'])!=r['library_hash'] or r['retention_before']!=r['retention_after'] or r['unchanged_library'] is not True:raise ValueError('frozen_library_provenance')
    if len(r['retention_before'])!=32:raise ValueError('retention_grid')
    for i,s in enumerate(r['source']):
        if s['family']!=c['source_families'][i//16] or len(s['episodes'])!=8:raise ValueError('source_grid')
        for q,e in enumerate(s['episodes']):
            if tuple(e['bits'])!=BITS[q] or decode(e['raw'],s['binding'])!=BITS[q] or type(e['answer']) is not bool:raise ValueError('source_binding')
    locked=copy.deepcopy(r['rows'])
    for row in locked:
        for k in ('final','data_hash'):row.pop(k)
        for d in row['methods'].values():
            for k in ('metrics','predictions'):d.pop(k)
    if digest(locked)!=r['choices_hash']:raise ValueError('choice_lock_mismatch')
    answers=0
    for i,row in enumerate(r['rows']):
        if row['family']!=c['target_families'][i//16] or set(row['methods'])!=set(METHODS) or len(row['final'])!=32:raise ValueError('complete_family_method_episode_grid')
        if len(row['pool'])!=8 or len(row['support_bank_answers'])!=8 or any(type(a) is not bool for a in row['support_bank_answers']):raise ValueError('support_grid')
        if any(decode(raw,row['binding'])!=BITS[q] for q,raw in enumerate(row['pool'])):raise ValueError('public_support_binding')
        if [f['id'] for f in row['final']]!=[f"final-{row['task']}-{j}" for j in range(32)]:raise ValueError('final_episode_grid')
        if any(decode(f['raw'],row['binding'])!=tuple(f['bits']) or type(f['answer']) is not bool for f in row['final']):raise ValueError('final_binding')
        if digest(dict(binding=row['binding'],pool=row['pool'],final=row['final']))!=row['data_hash']:raise ValueError('data_hash')
        for method,d in row['methods'].items():
            if set(d['metrics'])!=set(map(str,BUDGETS)) or set(d['predictions'])!=set(map(str,BUDGETS)) or set(d['snapshots'])!=set(map(str,BUDGETS)):raise ValueError('complete_budget_grid')
            questions=[s['question'] for s in d['steps']];answers+=len(questions)
            if len(set(questions))!=len(questions) or len(questions)>8 or any(type(q) is not int or q not in range(8) for q in questions):raise ValueError('question_budget')
            posterior=list(range(8));states=[posterior]
            for s in d['steps']:
                if s['posterior_before']!=posterior or type(s['answer']) is not bool or s['answer']!=row['support_bank_answers'][s['question']]:raise ValueError('revealed_answer_contract')
                posterior=[h for h in posterior if TABLE[h][s['question']] is s['answer']]
                if not posterior or posterior!=s['posterior_after']:raise ValueError('posterior_contract')
                states.append(posterior)
            if d['questions_to_identify']!=(len(questions) if len(posterior)==1 else 9):raise ValueError('identification_cost')
            for b in BUDGETS:
                snap=d['snapshots'][str(b)];n=min(b,len(questions))
                if snap!=dict(posterior=states[n],questions=n):raise ValueError('snapshot_contract')
                pred=d['predictions'][str(b)]
                if len(pred)!=32 or any(type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1 for p in pred):raise ValueError('finite_prediction_grid')
                if pred!=[st.mean(hypotheses(f['bits'])[h] for h in snap['posterior']) for f in row['final']]:raise ValueError('prediction_contract')
                expected=dict(accuracy=st.mean((p>=.5)==f['answer'] for p,f in zip(pred,row['final'])),brier=st.mean((p-f['answer'])**2 for p,f in zip(pred,row['final'])))
                if digest(expected)!=digest(d['metrics'][str(b)]):raise ValueError('metric_arithmetic')
    if digest(analysis(r['rows'],c))!=digest(r['analysis']):raise ValueError('analysis_arithmetic')
    expected=dict(source_answers=256,target_pool_observations=256,target_answers=answers,final_observations=1024,assessment_predictions=20480,real_steps=1536,updates=0,imagined_transitions=0,network_forwards=0)
    if any(type(work.get(k)) is not int or work[k]!=v for k,v in expected.items()):raise ValueError('resource_accounting')
    if any(work[k]>caps[k] for k in ('real_steps','updates','imagined_transitions')):raise ValueError('resource_cap')


def saved_replay(root):
    r=json.loads((Path(root)/'artifacts/seed_investigation_transfer.json').read_text());c=r['config']
    validate_output(dict(study=r,resources=r['resources']),c,dict(real_steps=5000,updates=0,imagined_transitions=0))
    return dict(id='seed-investigation-transfer-1',mode='exploration',status='complete_development',wall_s=r['host_receipt']['wall_s'],memory_mb=r['host_receipt']['peak_sampled_rss_mb'],revision=r['execution_sha'],resources=r['resources'],curve=[],investigation_transfer=r['analysis'])
