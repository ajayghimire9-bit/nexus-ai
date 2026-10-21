"""Source-inferred outcome models and frozen query procedures, not meta-learning.

Reuses the existing ID3 tree, LabelOracle/adapt, exact compiler, hybrid and host.
Only authored query-response observations are collected; no simulator or neural
model runs. Hidden tables belong to the evaluator, not the planner API.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics as st
import sys
import time
from nexus.evolution1.catalogue import digest
from . import investigation_transfer as b, investigation_hybrid as h, compiled_greedy as cg
from .structure.investigation import learn

METHODS=['tree_greedy','compiled_greedy','greedy','fixed_order','no_library']


def configuration():
    return dict(schema='seed_inferred_investigation_v1',families=list(range(1743000001,1743000009)),
        tasks=dict(train=list(range(1743100000,1743100256)),target=list(range(1743200000,1743200256))),
        methods=METHODS,budgets=b.BUDGETS,final_episodes=32,source_episodes=32,target_episodes=32,
        source_rule='one_per_class_plus_24_uniform_then_shuffle',target_rule='four_per_class',
        table_rule='eight_unique_nonconstant_8bit_rows_without_replacement',tree_depth=3,tree_nodes=15,
        max_wall_s=60,max_authored_steps=13000,max_imagined_transitions=0,max_outer_updates=0,
        carried_used_s=1987.6321034559958,carried_remaining_s=1612.3678965440042,
        minimum_work_reduction=.20,question_margin=0,accuracy_tolerance=.01,
        prior_config_registry_sha256='335faba6544dadbcd5ce84af1ba1a64173620157e417894efe0ce12dcaa5645d',
        weak_question_gain=.25,claim_scope='fresh authored source development, ordinary model learning and investigation transfer')


def config_check(c):
    if digest(c)!=digest(configuration()):raise ValueError('locked_inferred_recipe')
    return dict(real_steps=13000,imagined_transitions=0,outer_updates=0)


def seed_audit(root,c,*,names=None):
    """Exact explicit config values, including YAML and all registered offsets.

    Not a proof about unavailable runs or every implicit historical formula.
    Record hashes and that coverage limit instead of claiming global closure.
    """
    planned=set(c['families']+c['tasks']['train']+c['tasks']['target'])
    planned.update(x+10000 for x in c['families'])
    planned.update(x+200000 for x in c['tasks']['target'])
    planned.update(x+700 for x in c['tasks']['target'])
    files={}
    folder=Path(root)/'configs'
    paths=folder.iterdir() if names is None else (folder/name for name in names)
    for p in sorted(paths):
        if p.parent!=folder or p.name!=str(p.relative_to(folder)):raise ValueError('config_path')
        if p.suffix not in ('.json','.yaml','.yml') or p.name=='seed_inferred_investigation.json':continue
        raw=p.read_bytes();text=raw.decode()
        numbers={int(x.replace('_','')) for x in re.findall(r'(?<![\w.])[0-9][0-9_]*(?![\w.])',text)}
        if planned & numbers:raise ValueError('closed_or_existing_config_identifier:'+p.name)
        files[p.name]=hashlib.sha256(raw).hexdigest()
    return dict(config_files=len(files),planned_identifiers_and_rng_seeds=len(planned),config_hashes=files,
        coverage='explicit JSON/YAML integers only; not unavailable runs or arbitrary implicit seed formulae')


def evaluator_table(seed):
    """Evaluator ONLY. Query IDs are opaque; no fixed Boolean law is supplied."""
    return [[bool(code & (1<<q)) for q in range(8)] for code in random.Random(seed).sample(range(1,255),8)]


def source_classes(seed):
    rng=random.Random(seed+10000);classes=list(range(8))+[rng.randrange(8) for _ in range(24)]
    rng.shuffle(classes);return classes


def fit_outcomes(source):
    """Only source-role traces. Identical outcomes required; no noise imputation.

    Source class annotations are legitimate teaching, not target identifiers.
    A missing class or inconsistent response is a correctness failure.
    """
    table=[None]*8;reads=checks=0
    if len(source)!=32 or len({r['episode'] for r in source})!=32:raise ValueError('source_grid')
    for row in source:
        if set(row)!={'role','episode','answers','hypothesis'} or row['role']!='source':raise ValueError('source_only')
        i=row['hypothesis'];answers=row['answers']
        if type(i) is not int or not 0<=i<8 or len(answers)!=8 or any(type(v) is not bool for v in answers):raise ValueError('typed_source')
        reads+=8
        if table[i] is None:table[i]=list(answers)
        else:
            checks+=8
            if table[i]!=answers:raise ValueError('noisy_or_inconsistent_source')
    if any(row is None for row in table) or len({tuple(row) for row in table})!=8:raise ValueError('incomplete_class_model')
    return dict(table=table,source_sha256=digest(source),work=dict(response_reads=reads,consistency_checks=checks,class_label_reads=len(source)))


def fit_procedures(source):
    # No evaluator object or target argument is accepted by this boundary.
    model=fit_outcomes(source);start=time.perf_counter();library=learn(source,max_depth=3,max_nodes=15)
    tree_wall=time.perf_counter()-start;start=time.perf_counter();policy=cg.compile_table(model['table'])
    compile_wall=time.perf_counter()-start
    return dict(model=model,library=library,policy=policy,fit_wall_s=dict(tree=tree_wall,compile=compile_wall))


def adapt(method,fitted,reveal,seed=0):
    table=fitted['model']['table']
    def choose(m,ids,remaining,history,library,order,costs):
        if m=='compiled_greedy':return cg.choose(m,ids,remaining,history,fitted['policy'],order,costs)
        return h.choose(m,ids,remaining,history,fitted['library'],order,costs,table=table)
    return b.adapt(method,{},reveal,seed,choose_fn=choose,table=table)


def score(data,final,table):
    data.update(predictions={},metrics={})
    for budget in b.BUDGETS:
        ids=data['snapshots'][str(budget)]['posterior']
        probs=[st.mean(table[i][r['query']] for i in ids) for r in final]
        data['predictions'][str(budget)]=probs
        data['metrics'][str(budget)]=dict(accuracy=st.mean((p>=.5)==r['answer'] for p,r in zip(probs,final)),
            brier=st.mean((p-r['answer'])**2 for p,r in zip(probs,final)))
    return data


def interval(values):
    if len(values)!=8 or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('eight_family_values')
    mean=st.mean(values);half=2.364624251*st.stdev(values)/math.sqrt(8)
    return dict(mean=mean,low=mean-half,high=mean+half,n=8,df=7,unit='independently_sampled_query_response_family')


def family_summary(block):
    fitted=block['fitted'];model=fitted['model'];common=sum(model['work'].values())
    source_checks=h.source_split_checks(fitted['library']['tree'],[r['answers'] for r in block['source']])
    build=fitted['policy']['construction'];compile_checks=build['score_table_reads']+build['partition_table_reads']
    means={}
    for m in METHODS:
        ds=[row['methods'][m] for row in block['rows']]
        runtime=sum(d['costs']['hypothesis_predictions']+d['costs']['tree_nodes'] for d in ds)
        construction=source_checks if m=='tree_greedy' else compile_checks if m=='compiled_greedy' else 0
        means[m]=dict(questions=st.mean(d['questions_to_identify'] for d in ds),
            accuracy={str(k):st.mean(d['metrics'][str(k)]['accuracy'] for d in ds) for k in b.BUDGETS},
            brier={str(k):st.mean(d['metrics'][str(k)]['brier'] for d in ds) for k in b.BUDGETS},
            model_fit_work=common,construction_work=construction,runtime_work=runtime,total_work=common+construction+runtime,
            source_response_observations=256,source_class_annotations=32,
            search_reads=sum(d['costs']['search_predictions'] for d in ds),
            policy_visits=sum(d['costs']['tree_nodes'] for d in ds),max_questions=max(d['questions_to_identify'] for d in ds))
    return means


def summarize(blocks,c):
    means={}
    for m in METHODS:
        entries=[x['means'][m] for x in blocks]
        means[m]=dict(questions=st.mean(x['questions'] for x in entries),
            accuracy={str(k):st.mean(x['accuracy'][str(k)] for x in entries) for k in b.BUDGETS},
            brier={str(k):st.mean(x['brier'][str(k)] for x in entries) for k in b.BUDGETS},
            **{k:sum(x[k] for x in entries) for k in ('model_fit_work','construction_work','runtime_work','total_work','source_response_observations','source_class_annotations','search_reads','policy_visits')})
    contrasts={m:interval([x['means'][m]['questions']-x['means']['tree_greedy']['questions'] for x in blocks]) for m in METHODS if m!='tree_greedy'}
    exact=all(cg.decision(row['methods']['compiled_greedy'])==cg.decision(row['methods']['greedy']) for x in blocks for row in x['rows'])
    tree=means['tree_greedy'];compiled=means['compiled_greedy'];online=means['greedy']
    checks=dict(compiled_exactness=exact,
        compiled_efficiency=compiled['total_work']<=online['total_work']*(1-c['minimum_work_reduction']),
        hybrid_quality=tree['questions']<=compiled['questions']+c['question_margin'] and all(tree['accuracy'][str(k)]>=compiled['accuracy'][str(k)]-c['accuracy_tolerance'] for k in b.BUDGETS),
        hybrid_efficiency=tree['total_work']<=compiled['total_work']*(1-c['minimum_work_reduction']),
        weak_baseline_gain=all(contrasts[m]['mean']>=c['weak_question_gain'] and contrasts[m]['low']>0 for m in ('fixed_order','no_library')))
    return dict(means=means,question_savings=contrasts,checks=checks,
        source_model_recovery=all(x['fitted']['model']['table']==x['evaluator_table'] for x in blocks),
        hybrid_screen='passed' if all(checks[k] for k in ('hybrid_quality','hybrid_efficiency','weak_baseline_gain')) else 'failed',
        compiled_screen='passed' if exact and checks['compiled_efficiency'] else 'failed',
        family_count=8,per_family={str(x['id']):x['means'] for x in blocks},promoted=False,
        scope='ordinary source model inference and frozen investigation reuse, not learned learning-rule improvement')


def run(request):
    c=request['inputs']['study_config'];config_check(c);root=Path(request['inputs']['repository'])
    start=time.monotonic();cpu=time.process_time();r=dict(config=c,declared_complete=False,blocks=[])
    work=dict(real_steps=0,source_responses=0,source_annotations=0,target_support=0,final_observations=0,
        cached_answer_exposures=0,assessment_predictions=0,updates=0,imagined_transitions=0,network_forwards=0)
    def persist():
        temp=Path('progress.tmp');temp.write_text(json.dumps(r,allow_nan=False));temp.replace('progress.json')
    def charge(k,n):
        work[k]+=n;work['real_steps']+=n
        if work['real_steps']>c['max_authored_steps'] or time.monotonic()-start>c['max_wall_s']-3:raise TimeoutError('registered_resource_cap')
    hashes=lambda:{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in b.FROZEN}
    try:
        r['seed_audit']=seed_audit(root,c)
        r['frozen_before']=hashes()
        if r['frozen_before']!=b.FROZEN:raise ValueError('frozen_checkpoint_hash')
        for i,identifier in enumerate(c['families']):
            hidden=evaluator_table(identifier);classes=source_classes(identifier);source=[]
            block=dict(id=identifier,source=source,rows=[]);r['blocks'].append(block)
            for seed,law in zip(c['tasks']['train'][i*32:(i+1)*32],classes):
                source.append(dict(role='source',episode=f'source-{seed}',answers=copy.deepcopy(hidden[law]),hypothesis=law))
                charge('source_responses',8);charge('source_annotations',1)
            fitted=fit_procedures(source)
            block.update(source_hash=digest(source),fitted=fitted,fitted_hash=digest(fitted))
            persist()
        # All source learners are frozen BEFORE any target experience or scores.
        r['all_sources_frozen_before_targets']=True;persist()
        for i,block in enumerate(r['blocks']):
            hidden=evaluator_table(block['id'])
            for j,seed in enumerate(c['tasks']['target'][i*32:(i+1)*32]):
                answers=copy.deepcopy(hidden[j%8]);charge('target_support',8)
                methods={m:adapt(m,block['fitted'],b.LabelOracle(answers,8).reveal,seed+700) for m in METHODS}
                work['cached_answer_exposures']+=sum(len(d['steps']) for d in methods.values())
                block['rows'].append(dict(task=seed,support_answers=answers,methods=methods))
            block['locked_choices_hash']=digest(block['rows']);persist()
        r['all_choices_locked_before_final']=True;persist()
        for block in r['blocks']:
            hidden=evaluator_table(block['id']);table=block['fitted']['model']['table']
            for j,row in enumerate(block['rows']):
                rng=random.Random(row['task']+200000);final=[]
                for k in range(c['final_episodes']):
                    q=rng.randrange(8);final.append(dict(id=f"final-{row['task']}-{k}",query=q,answer=hidden[j%8][q]));charge('final_observations',1)
                row['final']=final;row['final_hash']=digest(final)
                for d in row['methods'].values():score(d,final,table);work['assessment_predictions']+=32*4
            block['evaluator_table']=hidden;block['means']=family_summary(block)
            if digest(block['fitted'])!=block['fitted_hash']:raise ValueError('frozen_procedures_changed')
            persist()
        r['analysis']=summarize(r['blocks'],c);r['frozen_after']=hashes()
        if r['frozen_before']!=r['frozen_after']:raise ValueError('frozen_checkpoint_changed')
        r['declared_complete']=True;persist()
    except Exception as e:
        r['failure']=dict(type=type(e).__name__,message=str(e));r['partial_resources']=work;persist();raise
    work.update(cpu_s=time.process_time()-cpu,worker_wall_s=time.monotonic()-start,source_model_fits=8,source_tree_fits=8)
    return dict(adapter=c['schema'],study=r,resources=work,runtime=dict(python=sys.version,device='cpu',threads=1))


def validate_output(o,c,caps):
    config_check(c);r=o['study']
    if r.get('declared_complete') is not True or digest(r['config'])!=digest(c) or [x['id'] for x in r['blocks']]!=c['families']:raise ValueError('complete_family_grid')
    snapshot=r['seed_audit']['config_hashes']
    if digest(snapshot)!=c['prior_config_registry_sha256'] or digest(r['seed_audit'])!=digest(seed_audit(Path(__file__).resolve().parents[3],c,names=snapshot)):raise ValueError('seed_audit_provenance')
    if r['all_sources_frozen_before_targets'] is not True or r['all_choices_locked_before_final'] is not True:raise ValueError('source_assessment_boundaries')
    for i,block in enumerate(r['blocks']):
        hidden=evaluator_table(block['id']);expected_sources=[]
        for seed,law in zip(c['tasks']['train'][i*32:(i+1)*32],source_classes(block['id'])):
            expected_sources.append(dict(role='source',episode=f'source-{seed}',answers=hidden[law],hypothesis=law))
        if digest(block['source'])!=digest(expected_sources) or block['source_hash']!=digest(block['source']):raise ValueError('source_provenance')
        expected=fit_procedures(block['source'])
        for k in ('model','library','policy'):
            if digest(block['fitted'][k])!=digest(expected[k]):raise ValueError('source_only_fitting')
        if digest(block['fitted'])!=block['fitted_hash']:raise ValueError('frozen_procedure_hash')
        if [row['task'] for row in block['rows']]!=c['tasks']['target'][i*32:(i+1)*32]:raise ValueError('complete_task_grid')
        locked=[]
        for j,row in enumerate(block['rows']):
            if row['support_answers']!=hidden[j%8] or set(row['methods'])!=set(METHODS):raise ValueError('complete_method_or_support_grid')
            rng=random.Random(row['task']+200000);final=[]
            for k in range(32):
                q=rng.randrange(8);final.append(dict(id=f"final-{row['task']}-{k}",query=q,answer=hidden[j%8][q]))
            if digest(row['final'])!=digest(final) or row['final_hash']!=digest(final):raise ValueError('final_episode_provenance')
            unscored={}
            for m in METHODS:
                d=adapt(m,block['fitted'],b.LabelOracle(row['support_answers'],8).reveal,row['task']+700)
                unscored[m]=copy.deepcopy(d)
                if digest(score(d,final,expected['model']['table']))!=digest(row['methods'][m]):raise ValueError('decisions_metrics_costs_or_budget_grid')
            locked.append(dict(task=row['task'],support_answers=row['support_answers'],methods=unscored))
        if digest(locked)!=block['locked_choices_hash'] or digest(hidden)!=digest(block['evaluator_table']) or digest(family_summary(block))!=digest(block['means']):raise ValueError('locked_choices_or_family_aggregation')
        for v in block['fitted']['fit_wall_s'].values():
            if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('finite_fit_time')
    if digest(summarize(r['blocks'],c))!=digest(r['analysis']):raise ValueError('family_aggregation')
    if r['frozen_before']!=b.FROZEN or r['frozen_after']!=b.FROZEN:raise ValueError('frozen_checkpoint_hash')
    expected=dict(real_steps=12544,source_responses=2048,source_annotations=256,target_support=2048,final_observations=8192,
        assessment_predictions=163840,updates=0,imagined_transitions=0,network_forwards=0,source_model_fits=8,source_tree_fits=8)
    for k,v in expected.items():
        if type(o['resources'].get(k)) is not int or o['resources'][k]!=v:raise ValueError('resource_accounting')
    for k in ('cpu_s','worker_wall_s'):
        if type(o['resources'].get(k)) not in (int,float) or not math.isfinite(o['resources'][k]) or o['resources'][k]<0:raise ValueError('finite_runtime')
    if o['resources']['real_steps']>caps['real_steps']:raise ValueError('resource_cap')
    if o['resources']['cached_answer_exposures']!=sum(len(d['steps']) for x in r['blocks'] for row in x['rows'] for d in row['methods'].values()):raise ValueError('cached_answer_accounting')


def saved_replay(root):
    r=json.loads((Path(root)/'artifacts/seed_inferred_investigation.json').read_text())
    validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=13000))
    return dict(id='seed-inferred-investigation-1',mode='exploration',status='complete_development',
        wall_s=r['host_receipt']['wall_s'],memory_mb=r['host_receipt']['peak_sampled_rss_mb'],revision=r['execution_sha'],
        resources=r['resources'],curve=[],inferred_investigation=r['analysis'])
