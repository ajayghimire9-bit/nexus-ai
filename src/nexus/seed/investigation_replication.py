"""Three independent source-tree replications within the carried 5000-row cap."""
import copy
import json
import math
import os
from pathlib import Path
import statistics as st
import sys
import time
from nexus.evolution1.catalogue import digest
from . import investigation_transfer as b, investigation_hybrid as h
from .experimental import write_new


def configuration():
    return dict(schema='seed_investigation_replication_v1',tasks=dict(train=list(range(995100,995196)),target=list(range(995300,995396))),
        replications=[995001,995002,995003],methods=h.METHODS,budgets=b.BUDGETS,source_families=['attributes','thresholds'],
        target_families=['temporal','spatial'],tree_depth=3,tree_nodes=15,final_episodes=32,max_wall_s=60,max_authored_steps=5000,
        max_outer_updates=0,max_imagined_transitions=0,carried_used_s=1983.6321034559958,carried_remaining_s=1616.3678965440042,
        grammar_sha256=digest(b.TABLE),max_questions=4,question_margin=0,accuracy_tolerance=.01,
        minimum_search_reduction=.30,minimum_total_reduction=.20,upper_excess_question_ci=.25)


def config_check(c):
    if digest(c)!=digest(configuration()):raise ValueError('locked_replication_config')
    return dict(real_steps=5000,imagined_transitions=0,outer_updates=0)


def subconfig(c,i):
    d=copy.deepcopy(c);d['tasks']={k:v[i*32:(i+1)*32] for k,v in c['tasks'].items()}
    d['target_laws']={str(seed):j%8 for j,seed in enumerate(d['tasks']['target'])}
    d['target_family_by_task']={str(seed):c['target_families'][(j//8)%2] for j,seed in enumerate(d['tasks']['target'])}
    return d


def tree_summary(r):
    answers=[[e['answer'] for e in s['episodes']] for s in r['source']]
    source=dict(labeled_observations=256,source_split_comparisons=h.source_split_checks(r['library']['tree'],answers),charged_to_methods=['tree_fixed','tree_greedy'])
    return dict(means=h.decision_means(r['rows'],source),source_cost=source,
        prefix_preserved=all(h.prefix_preserved(row,r['library']) for row in r['rows']),
        by_family={f:{m:st.mean(row['methods'][m]['questions_to_identify'] for row in r['rows'] if row['family']==f) for m in h.METHODS} for f in ('temporal','spatial')})


def interval(values):
    if len(values)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('three_independent_tree_values_required')
    mean=st.mean(values);half=4.30265272991*st.stdev(values)/math.sqrt(3)
    return dict(mean=mean,low=mean-half,high=mean+half,n=3,df=2,unit='independently_source_trained_tree')


def summarize(records,c):
    means={}
    for m in h.METHODS:
        entries=[x['study']['analysis']['means'][m] for x in records]
        means[m]=dict(questions=st.mean(x['questions'] for x in entries),accuracy={str(budget):st.mean(x['accuracy'][str(budget)] for x in entries) for budget in b.BUDGETS},
            brier={str(budget):st.mean(x['brier'][str(budget)] for x in entries) for budget in b.BUDGETS},
            **{k:sum(x[k] for x in entries) for k in ('search_predictions','greedy_calls','tree_visits','posterior_checks','source_split_comparisons','source_observations','total_decision_work','five_question_tail')},
            max_questions=max(x['max_questions'] for x in entries))
    contrasts={m:interval([x['study']['analysis']['means'][m]['questions']-x['study']['analysis']['means']['tree_greedy']['questions'] for x in records]) for m in h.METHODS if m!='tree_greedy'}
    hybrid=means['tree_greedy'];greedy=means['greedy']
    checks=dict(early_tree_decisions=all(x['study']['analysis']['prefix_preserved'] for x in records),
        tail_removed=hybrid['max_questions']<=c['max_questions'] and means['tree_fixed']['five_question_tail']>0,
        greedy_quality=hybrid['questions']<=greedy['questions'] and contrasts['greedy']['low']>=-c['upper_excess_question_ci'] and all(hybrid['accuracy'][str(k)]>=greedy['accuracy'][str(k)]-c['accuracy_tolerance'] for k in b.BUDGETS),
        search_reduction=hybrid['search_predictions']<=greedy['search_predictions']*(1-c['minimum_search_reduction']),
        total_reduction=hybrid['total_decision_work']<=greedy['total_decision_work']*(1-c['minimum_total_reduction']))
    return dict(variant='independent_rule_balanced_replication',means=means,question_savings=contrasts,checks=checks,
        screen='passed' if all(checks.values()) else 'failed',promoted=False,independent_trees=3,
        per_tree={str(x['id']):x['study']['analysis'] for x in records},
        claim_scope='three independently source-trained trees; supplied grammar; authored rule-balanced development')


def run(request):
    c=request['inputs']['study_config'];config_check(c);directory=Path.cwd();start=time.monotonic();cpu=time.process_time()
    result=dict(config=c,declared_complete=False,replications=[],analysis=None)
    def persist():
        p=directory/'progress.tmp';p.write_text(json.dumps(result,allow_nan=False));p.replace(directory/'progress.json')
    try:
        for i,identifier in enumerate(c['replications']):
            if time.monotonic()-start>c['max_wall_s']-5:raise TimeoutError('replication_cap')
            path=directory/str(identifier);path.mkdir();os.chdir(path)
            try:
                sub=subconfig(c,i)
                out=b.run(dict(request,inputs=dict(request['inputs'],study_config=sub)),config_validator=lambda d:None,
                    methods=h.METHODS,adapt_fn=h.adapt,analyze=lambda rows,d:None)
            finally:os.chdir(directory)
            out['study']['analysis']=tree_summary(out['study']);result['replications'].append(dict(id=identifier,**out));persist()
            if sum(x['resources']['real_steps'] for x in result['replications'])>c['max_authored_steps']:raise ValueError('global_observation_cap')
        result['analysis']=summarize(result['replications'],c);result['declared_complete']=True;persist()
    except Exception as e:
        result['failure']=dict(type=type(e).__name__,message=str(e))
        if 'path' in locals() and (path/'progress.json').exists():result['last_tree_progress']=json.loads((path/'progress.json').read_text())
        persist();raise
    keys=('real_steps','source_answers','target_pool_observations','target_answers','final_observations','assessment_predictions','tree_nodes','hypothesis_predictions','search_nodes','cached_retention_reads','source_trace_rows','source_trace_answers')
    work={k:sum(x['resources'][k] for x in result['replications']) for k in keys}
    work.update(cpu_s=time.process_time()-cpu,worker_wall_s=time.monotonic()-start,updates=0,imagined_transitions=0,network_forwards=0,neural_parameters=0,
        source_fit_wall_s=sum(x['resources']['source_fit_wall_s'] for x in result['replications']))
    return dict(adapter=c['schema'],study=result,resources=work,runtime=dict(python=sys.version,device='cpu',threads=1))


def validate_output(o,c,caps):
    config_check(c);r=o['study']
    if r.get('declared_complete') is not True or digest(r['config'])!=digest(c) or [x['id'] for x in r['replications']]!=c['replications']:raise ValueError('complete_independent_tree_grid')
    for i,x in enumerate(r['replications']):
        sub=subconfig(c,i)
        b.validate_output(x,sub,caps,config_validator=lambda d:None,methods=h.METHODS,analyze=lambda rows,d:tree_summary(dict(x['study'],rows=rows)))
        for row in x['study']['rows']:
            law=sub['target_laws'][str(row['task'])]
            if row['support_bank_answers']!=list(b.TABLE[law]):raise ValueError('rule_balance_binding')
            if any(f['answer'] is not b.hypotheses(f['bits'])[law] for f in row['final']):raise ValueError('final_evaluator_rule_binding')
            for m,d in row['methods'].items():
                expected=h.adapt(m,x['study']['library'],b.LabelOracle(row['support_bank_answers'],8).reveal,row['task']+700)
                recorded={k:v for k,v in d.items() if k not in ('metrics','predictions')}
                if digest(expected)!=digest(recorded):raise ValueError('policy_compute_replay')
    if len({x['study']['source_hash'] for x in r['replications']})!=3:raise ValueError('independent_source_data_required')
    if len({digest([[e['answer'] for e in s['episodes']] for s in x['study']['source']]) for x in r['replications']})!=3:raise ValueError('renamed_duplicate_sources')
    if digest(summarize(r['replications'],c))!=digest(r['analysis']):raise ValueError('independent_tree_aggregation')
    work=o['resources']
    if any(type(work.get(k)) is not int or work[k]!=v for k,v in dict(real_steps=4608,source_answers=768,target_pool_observations=768,final_observations=3072,assessment_predictions=61440,updates=0,imagined_transitions=0,network_forwards=0).items()):raise ValueError('resource_accounting')
    for k in ('target_answers','tree_nodes','hypothesis_predictions','search_nodes','cached_retention_reads'):
        if work[k]!=sum(x['resources'][k] for x in r['replications']):raise ValueError('resource_sum')
    if work['real_steps']>caps['real_steps']:raise ValueError('resource_cap')


def saved_replay(root):
    r=json.loads((Path(root)/'artifacts/seed_investigation_replication.json').read_text())
    validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=5000,updates=0,imagined_transitions=0))
    return dict(id='seed-investigation-replication-1',mode='exploration',status='complete_development',wall_s=r['host_receipt']['wall_s'],memory_mb=r['host_receipt']['peak_sampled_rss_mb'],revision=r['execution_sha'],resources=r['resources'],curve=[],investigation_transfer=r['analysis'])
