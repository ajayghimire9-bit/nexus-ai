"""Source-free exact question-policy compilation; retrospective saved-bank audit.

Reuses investigation_transfer.adapt/LabelOracle and hybrid.choose. No collector,
teacher fit, neural inference, or live-agent promotion is invoked.
"""
import copy
import hashlib
import json
import math
import statistics as st
import sys
import time
from pathlib import Path
from nexus.evolution1.catalogue import digest
from . import investigation_transfer as b, investigation_hybrid as h

PARENT = 'artifacts/seed_investigation_replication.json'
PARENT_SHA = '8e1c4ab0c32d3c1753463eb82c4cf7992b64f0220e644c88e72b701e785f7a47'
METHODS = ['compiled_greedy', 'greedy', 'tree_greedy']


def configuration():
    return dict(schema='seed_compiled_greedy_v1', parent=PARENT, parent_sha256=PARENT_SHA,
        grammar_sha256=digest(b.TABLE), tasks=dict(saved=list(range(995300,995396))),
        replications=[995001,995002,995003], methods=METHODS, budgets=b.BUDGETS,
        max_wall_s=30,max_authored_steps=0,max_outer_updates=0,max_imagined_transitions=0,
        carried_used_s=1985.6321034559958,carried_remaining_s=1614.3678965440042,
        minimum_work_reduction=.20,construction_charge='once_per_32_task_block',
        claim_scope='retrospective source-development arithmetic and cost audit')


def config_check(c):
    if digest(c)!=digest(configuration()):raise ValueError('locked_compiled_recipe')
    return dict(real_steps=0,imagined_transitions=0,outer_updates=0)


def key(ids,remaining):
    return ','.join(map(str,ids))+'|'+','.join(map(str,remaining))


def compile_policy():
    """Only public grammar input. No source examples, task IDs or target answers.

    Memoize reachable version spaces. Scoring uses the same squared-partition
    objective and lowest-question tie-break as online greedy. Partition reads
    are charged separately from candidate-scoring reads.
    """
    nodes={};cost=dict(score_table_reads=0,partition_table_reads=0,candidate_scores=0,nodes=0)
    def visit(ids,remaining):
        k=key(ids,remaining)
        if k in nodes:return
        cost['nodes']+=1
        if len(ids)==1:nodes[k]=dict(posterior=list(ids),question=None);return
        scores=[]
        for q in remaining:
            yes=sum(b.TABLE[i][q] for i in ids);cost['score_table_reads']+=len(ids)
            scores.append((yes*yes+(len(ids)-yes)**2,q));cost['candidate_scores']+=1
        q=min(scores)[1];nodes[k]=dict(posterior=list(ids),question=q)
        groups=[[],[]]
        for i in ids:
            groups[int(b.TABLE[i][q])].append(i);cost['partition_table_reads']+=1
        if any(len(g)==len(ids) for g in groups):raise ValueError('nonseparating_grammar')
        for child in groups:
            if child:visit(tuple(child),tuple(x for x in remaining if x!=q))
    visit(tuple(range(8)),tuple(range(8)))
    return dict(grammar_sha256=digest(b.TABLE),nodes=nodes,construction=cost)


def choose(method,posterior,remaining,history,library,order,costs):
    if method!='compiled_greedy':return h.choose(method,posterior,remaining,history,library,order,costs)
    costs.setdefault('search_predictions',0);costs.setdefault('greedy_calls',0)
    costs['tree_nodes']+=1  # One cached policy lookup, not a grammar prediction.
    return library['nodes'][key(posterior,remaining)]['question']


def adapt(policy,reveal):
    return b.adapt('compiled_greedy',policy,reveal,choose_fn=choose)


def scored(data,final):
    data['metrics']={};data['predictions']={}
    for budget in b.BUDGETS:
        ids=data['snapshots'][str(budget)]['posterior']
        pred=[st.mean(b.hypotheses(r['bits'])[i] for i in ids) for r in final]
        data['predictions'][str(budget)]=pred
        data['metrics'][str(budget)]=dict(accuracy=st.mean((p>=.5)==r['answer'] for p,r in zip(pred,final)),
            brier=st.mean((p-r['answer'])**2 for p,r in zip(pred,final)))
    return data


def decision(data):
    return {k:v for k,v in data.items() if k!='costs'}


def summarize(blocks,policy):
    result={}
    build=policy['construction'];construction=build['score_table_reads']+build['partition_table_reads']
    for method in METHODS:
        entries=[x['means'][method] for x in blocks]
        result[method]=dict(questions=st.mean(x['questions'] for x in entries),
            accuracy={str(k):st.mean(x['accuracy'][str(k)] for x in entries) for k in b.BUDGETS},
            **{k:sum(x[k] for x in entries) for k in ('runtime_work','construction_work','total_work','source_observations','search_reads','posterior_checks','policy_visits')})
    exact=all(decision(row['methods']['compiled_greedy'])==decision(row['methods']['greedy']) for x in blocks for row in x['rows'])
    differences=[x['means']['compiled_greedy']['questions']-x['means']['tree_greedy']['questions'] for x in blocks]
    if len(differences)!=3:raise ValueError('three_saved_blocks_required')
    mean=st.mean(differences);half=4.30265272991*st.stdev(differences)/math.sqrt(3)
    return dict(means=result,exact_decisions_and_predictions=exact,
        primary_work_reduction=1-result['compiled_greedy']['total_work']/result['tree_greedy']['total_work'],
        single_shared_compilation_work=result['compiled_greedy']['runtime_work']+construction,
        block_question_differences=differences,
        exploratory_question_interval=dict(mean=mean,low=mean-half,high=mean+half,n=3,df=2,
            unit='reused_source_library_block, not newly learned compiled-policy replication'),
        scope='deterministic saved-bank audit, not new confirmation or independent learning replication',promoted=False)


def load_parent(root,c):
    raw=(Path(root)/c['parent']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=c['parent_sha256']:raise ValueError('parent_hash')
    parent=json.loads(raw)
    if parent.get('declared_complete') is not True:raise ValueError('parent_incomplete')
    if [x['id'] for x in parent['replications']]!=c['replications']:raise ValueError('parent_block_grid')
    return parent


def replay_block(saved,policy):
    rows=[];timing={m:0. for m in METHODS};library=saved['study']['library']
    frozen=digest(library);policy_hash=digest(policy)
    for row in saved['study']['rows']:
        methods={}
        for m in METHODS:
            oracle=b.LabelOracle(row['support_bank_answers'],8)
            start=time.perf_counter()
            d=adapt(policy,oracle.reveal) if m=='compiled_greedy' else h.adapt(m,library,oracle.reveal,row['task']+700)
            timing[m]+=time.perf_counter()-start
            methods[m]=scored(d,row['final'])
            if m!='compiled_greedy' and methods[m]!=row['methods'][m]:raise ValueError('historical_replay_mismatch')
        rows.append(dict(task=row['task'],family=row['family'],methods=methods))
    if digest(library)!=frozen or digest(policy)!=policy_hash:raise ValueError('policy_mutation')
    answers=[[e['answer'] for e in s['episodes']] for s in saved['study']['source']]
    source_cost=h.source_split_checks(library['tree'],answers);means={}
    for m in METHODS:
        ds=[r['methods'][m] for r in rows]
        search=sum(d['costs']['search_predictions'] for d in ds)
        posterior=sum(d['costs']['hypothesis_predictions']-d['costs']['search_predictions'] for d in ds)
        visits=sum(d['costs']['tree_nodes'] for d in ds)
        build=policy['construction']
        construction=(build['score_table_reads']+build['partition_table_reads']) if m=='compiled_greedy' else source_cost if m=='tree_greedy' else 0
        means[m]=dict(questions=st.mean(d['questions_to_identify'] for d in ds),
            accuracy={str(k):st.mean(d['metrics'][str(k)]['accuracy'] for d in ds) for k in b.BUDGETS},
            runtime_work=search+posterior+visits,construction_work=construction,total_work=construction+search+posterior+visits,
            source_observations=256 if m=='tree_greedy' else 0,search_reads=search,posterior_checks=posterior,policy_visits=visits)
    return dict(id=saved['id'],rows=rows,means=means,policy_wall_s=timing,
        historical_source_fit_wall_s=saved['resources']['source_fit_wall_s'],library_hash=frozen,unchanged_library=True,
        serialized_library_bytes=len(json.dumps(library,sort_keys=True,separators=(',',':')).encode()))


def run(request):
    c=request['inputs']['study_config'];config_check(c);root=Path(request['inputs']['repository'])
    start=time.monotonic();cpu=time.process_time();r=dict(config=c,declared_complete=False,blocks=[])
    def persist():
        Path('progress.json').write_text(json.dumps(r,allow_nan=False))
    try:
        before={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in b.FROZEN}
        if before!=b.FROZEN:raise ValueError('frozen_checkpoint_hash')
        t=time.perf_counter();policy=compile_policy();build_wall=time.perf_counter()-t
        r.update(policy=policy,policy_hash=digest(policy),build_wall_s=build_wall,
            serialized_policy_bytes=len(json.dumps(policy,sort_keys=True,separators=(',',':')).encode()),
            compiled_before_saved_answers_loaded=True,frozen_checkpoints_before=before)
        persist()  # Persist source-free construction before opening saved target data.
        parent=load_parent(root,c)
        for saved in parent['replications']:
            if time.monotonic()-start>c['max_wall_s']-3:raise TimeoutError('audit_cap')
            r['blocks'].append(replay_block(saved,policy));persist()
        r['analysis']=summarize(r['blocks'],policy)
        r['analysis']['screen']='passed' if r['analysis']['exact_decisions_and_predictions'] and r['analysis']['primary_work_reduction']>=c['minimum_work_reduction'] else 'failed'
        r['frozen_checkpoints_after']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in b.FROZEN}
        if r['frozen_checkpoints_after']!=before:raise ValueError('frozen_changed')
        r['declared_complete']=True;persist()
    except Exception as e:
        r['failure']=dict(type=type(e).__name__,message=str(e));persist();raise
    work=dict(real_steps=0,updates=0,imagined_transitions=0,network_forwards=0,source_fits=0,
        cached_target_tasks=96,cached_final_observations=3072,
        answer_exposures=sum(len(row['methods'][m]['steps']) for x in r['blocks'] for row in x['rows'] for m in METHODS),
        assessment_predictions=96*3*4*32,worker_wall_s=time.monotonic()-start,cpu_s=time.process_time()-cpu)
    work.update(compilation_wall_s=build_wall,serialized_policy_bytes=r['serialized_policy_bytes'],
        policy_wall_s={m:sum(x['policy_wall_s'][m] for x in r['blocks']) for m in METHODS},
        historical_hybrid_source_fit_wall_s=sum(x['historical_source_fit_wall_s'] for x in r['blocks']))
    work['serialized_hybrid_library_bytes']=[x['serialized_library_bytes'] for x in r['blocks']]
    return dict(adapter=c['schema'],study=r,resources=work,runtime=dict(python=sys.version,device='cpu',threads=1))


def validate_output(o,c,caps):
    config_check(c);r=o['study'];parent=load_parent(Path(__file__).resolve().parents[3],c)
    if r.get('declared_complete') is not True or digest(r['config'])!=digest(c):raise ValueError('incomplete_audit')
    if [x['id'] for x in r['blocks']]!=c['replications']:raise ValueError('complete_block_grid')
    if digest(r['policy'])!=digest(compile_policy()) or r['policy_hash']!=digest(r['policy']):raise ValueError('source_free_policy_hash')
    if r.get('compiled_before_saved_answers_loaded') is not True:raise ValueError('compile_before_answers')
    numeric=[r['build_wall_s'],o['resources']['cpu_s'],o['resources']['worker_wall_s']]
    if any(set(x['policy_wall_s'])!=set(METHODS) for x in r['blocks']):raise ValueError('complete_timing_grid')
    numeric += [v for x in r['blocks'] for v in x['policy_wall_s'].values()]
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in numeric):raise ValueError('finite_runtime_metrics')
    if r['serialized_policy_bytes']!=len(json.dumps(r['policy'],sort_keys=True,separators=(',',':')).encode()):raise ValueError('serialized_bytes')
    for x,saved in zip(r['blocks'],parent['replications']):
        if [row['task'] for row in x['rows']]!=[row['task'] for row in saved['study']['rows']]:raise ValueError('complete_task_grid')
        expected=replay_block(saved,r['policy'])
        for k in ('rows','means','library_hash','unchanged_library','serialized_library_bytes','historical_source_fit_wall_s'):
            if digest(x[k])!=digest(expected[k]):raise ValueError('replay_or_complete_method_budget_grid')
    analysis=summarize(r['blocks'],r['policy'])
    analysis['screen']='passed' if analysis['exact_decisions_and_predictions'] and analysis['primary_work_reduction']>=c['minimum_work_reduction'] else 'failed'
    if digest(analysis)!=digest(r['analysis']):raise ValueError('aggregation')
    if r['frozen_checkpoints_before']!=b.FROZEN or r['frozen_checkpoints_after']!=b.FROZEN:raise ValueError('checkpoint_preservation')
    for k,v in dict(real_steps=0,updates=0,imagined_transitions=0,network_forwards=0,source_fits=0,cached_target_tasks=96,cached_final_observations=3072,assessment_predictions=36864).items():
        if type(o['resources'].get(k)) is not int or o['resources'][k]!=v:raise ValueError('resource_accounting')
    if type(o['resources']['answer_exposures']) is not int or o['resources']['answer_exposures']!=sum(len(row['methods'][m]['steps']) for x in r['blocks'] for row in x['rows'] for m in METHODS):raise ValueError('cached_answer_accounting')


def saved_replay(root):
    r=json.loads((Path(root)/'artifacts/seed_compiled_greedy.json').read_text())
    validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=0))
    return dict(id='seed-compiled-greedy-1',mode='exploration',status='complete_development',
        wall_s=r['host_receipt']['wall_s'],memory_mb=r['host_receipt']['peak_sampled_rss_mb'],revision=r['execution_sha'],
        resources=r['resources'],curve=[],compiled_greedy=r['analysis'])
