"""Frozen-tree fallback intervention. Reuses the registered collection/checker."""
import copy
import hashlib
import json
import statistics as st
from pathlib import Path
from nexus.evolution1.catalogue import digest
from . import investigation_transfer as base

METHODS=['tree_fixed','tree_greedy','greedy','fixed_order','no_library']
PARENT='artifacts/seed_investigation_transfer.json'
PARENT_SHA='219b5089d4c2964b45b61d411f10cc199dbb5ba047122bb3e54a42960dd1ba34'
LIBRARY_SHA='c5e68b085ebd654e7dcc57c3319f0099e778dc4bc359aa6cb88b862f67b4e80e'
SOURCE_SHA='4b6e31f8b85edc2e697a4928d7a65a02c0f6cf1268a570aad6a4451bc495ce0f'
GRAMMAR_SHA=digest(base.TABLE)


def configuration():
    return dict(schema='seed_investigation_hybrid_v1',tasks=dict(train=list(range(982100,982132)),target=list(range(983200,983232))),
        source_families=['attributes','thresholds'],target_families=['temporal','spatial'],methods=METHODS,budgets=base.BUDGETS,
        final_episodes=32,tree_depth=3,tree_nodes=15,search_nodes=4096,max_wall_s=60,max_authored_steps=5000,
        max_outer_updates=0,max_imagined_transitions=0,carried_used_s=1981.6321034559958,carried_remaining_s=1618.3678965440042,
        parent_sha256=PARENT_SHA,library_sha256=LIBRARY_SHA,grammar_sha256=GRAMMAR_SHA,
        max_questions=4,question_margin=0,accuracy_tolerance=.01,minimum_search_reduction=.30,minimum_total_reduction=.20)


def config_check(c):
    if digest(c)!=digest(configuration()):raise ValueError('locked_hybrid_recipe')
    return dict(real_steps=5000,imagined_transitions=0,outer_updates=0)


def source_split_checks(tree,rows,depth=0):
    """Exact predicate comparisons in original ID3 candidate partition loops.

    This excludes entropy arithmetic; inherited wall time is also disclosed.
    The recorded tree has no nonpure early-abandon node.
    """
    if tree['op']!='probe':
        if tree['op']=='abandon' and depth<3:raise ValueError('unaccounted_early_abandon')
        return 0
    return 2*len(rows)*(8-depth)+sum(source_split_checks(child,[r for r in rows if r[tree['index']] is bool(j)],depth+1) for j,child in enumerate(tree['branches']))


def load_source(root):
    raw=(Path(root)/PARENT).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('parent_artifact_hash')
    p=json.loads(raw)
    if not p['declared_complete'] or digest(p['library'])!=LIBRARY_SHA or digest(p['source'])!=SOURCE_SHA:raise ValueError('frozen_source_hash')
    answers=[[e['answer'] for e in s['episodes']] for s in p['source']]
    inherited=dict(artifact=PARENT,artifact_sha256=PARENT_SHA,source_sha256=SOURCE_SHA,library_sha256=LIBRARY_SHA,
        labeled_observations=256,source_fit_wall_s=p['resources']['source_fit_wall_s'],source_split_comparisons=source_split_checks(p['library']['tree'],answers),
        charged_to_methods=['tree_fixed','tree_greedy'],new_source_fit=False)
    return dict(source=p['source'],library=p['library'],inherited_source=inherited)


def choose(method,posterior,remaining,history,library,random_order,costs):
    costs.setdefault('greedy_calls',0);costs.setdefault('search_predictions',0);costs.setdefault('fallback_calls',0)
    if method in ('tree_fixed','tree_greedy'):
        tree=library['tree']
        while tree['op']=='probe':
            costs['tree_nodes']+=1;q=tree['index']
            if q not in history:return q
            tree=tree['branches'][int(history[q])]
        costs['fallback_calls']+=1
        if method=='tree_fixed' or tree['op']!='abandon':return min(remaining)
        method='greedy'
    if method=='greedy':
        costs['greedy_calls']+=1;scores=[]
        for q in remaining:
            # One actual table lookup per hypothesis, rather than recomputing
            # both Boolean partitions. Same exact squared-partition criterion.
            yes=sum(base.TABLE[h][q] for h in posterior);no=len(posterior)-yes
            costs['hypothesis_predictions']+=len(posterior)
            costs['search_predictions']+=len(posterior)
            scores.append((yes*yes+no*no,q))
        return min(scores)[1]
    return base.choose(method,posterior,remaining,history,library,random_order,costs)


def adapt(method,library,reveal,seed=0):
    return base.adapt(method,library,reveal,seed,choose_fn=choose)


def prefix_preserved(row,library):
    fixed=row['methods']['tree_fixed']['steps'];hybrid=row['methods']['tree_greedy']['steps']
    tree=library['tree'];n=0
    while tree['op']=='probe' and n<len(fixed):
        if n>=len(hybrid) or fixed[n]!=hybrid[n] or fixed[n]['question']!=tree['index']:return False
        tree=tree['branches'][int(fixed[n]['answer'])];n+=1
    return True


def decision_means(rows,inherited):
    means={m:dict(questions=st.mean(r['methods'][m]['questions_to_identify'] for r in rows),
        accuracy={str(b):st.mean(r['methods'][m]['metrics'][str(b)]['accuracy'] for r in rows) for b in base.BUDGETS},
        brier={str(b):st.mean(r['methods'][m]['metrics'][str(b)]['brier'] for r in rows) for b in base.BUDGETS},
        max_questions=max(r['methods'][m]['questions_to_identify'] for r in rows),
        five_question_tail=sum(r['methods'][m]['questions_to_identify']>=5 for r in rows),
        search_predictions=sum(r['methods'][m]['costs']['search_predictions'] for r in rows),
        greedy_calls=sum(r['methods'][m]['costs']['greedy_calls'] for r in rows),
        tree_visits=sum(r['methods'][m]['costs']['tree_nodes'] for r in rows),
        posterior_checks=sum(r['methods'][m]['costs']['hypothesis_predictions']-r['methods'][m]['costs']['search_predictions'] for r in rows)) for m in METHODS}
    for m,v in means.items():
        v['source_split_comparisons']=inherited['source_split_comparisons'] if m in inherited['charged_to_methods'] else 0
        v['source_observations']=inherited['labeled_observations'] if m in inherited['charged_to_methods'] else 0
        v['total_decision_work']=v['search_predictions']+v['posterior_checks']+v['tree_visits']+v['source_split_comparisons']
    return means


def summarize(rows,c):
    # Costs are deterministic operation counts; they are not FLOP or speed claims.
    source=load_source(Path(__file__).resolve().parents[3]);inherited=source['inherited_source']
    means=decision_means(rows,inherited)
    h=means['tree_greedy'];g=means['greedy']
    question_contrasts={m:base.paired([r['methods'][m]['questions_to_identify']-r['methods']['tree_greedy']['questions_to_identify'] for r in rows]) for m in METHODS if m!='tree_greedy'}
    checks=dict(early_tree_decisions=all(prefix_preserved(r,source['library']) for r in rows),
        tail_removed=h['max_questions']<=c['max_questions'] and means['tree_fixed']['five_question_tail']>0,
        greedy_quality=h['questions']<=g['questions']+c['question_margin'] and all(h['accuracy'][str(b)]>=g['accuracy'][str(b)]-c['accuracy_tolerance'] for b in base.BUDGETS),
        search_reduction=h['search_predictions']<=g['search_predictions']*(1-c['minimum_search_reduction']),
        total_reduction=h['total_decision_work']<=g['total_decision_work']*(1-c['minimum_total_reduction']))
    return dict(variant='selective_greedy_fallback',means=means,question_savings=question_contrasts,checks=checks,screen='passed' if all(checks.values()) else 'failed',
        by_family={f:{m:st.mean(r['methods'][m]['questions_to_identify'] for r in rows if r['family']==f) for m in METHODS} for f in c['target_families']},
        claim_scope='authored fallback intervention; one frozen tree, supplied grammar and sensor bindings',promoted=False)


def run(request):
    source=load_source(request['inputs']['repository'])
    result=base.run(request,config_validator=config_check,methods=METHODS,analyze=summarize,adapt_fn=adapt,source_record=source)
    result['resources']['inherited_source']=source['inherited_source']
    return result


def validate_output(output,c,caps):
    base.validate_output(output,c,caps,config_validator=config_check,methods=METHODS,analyze=summarize,collected_source=False)
    r=output['study'];source=load_source(Path(__file__).resolve().parents[3])
    if r['library_hash']!=LIBRARY_SHA or r['source_hash']!=SOURCE_SHA or r['inherited_source']!=source['inherited_source'] or digest(base.TABLE)!=c['grammar_sha256']:raise ValueError('inherited_library_integrity')
    if output['resources']['inherited_source']!=r['inherited_source']:raise ValueError('inherited_source_cost')
    for row in r['rows']:
        for method,d in row['methods'].items():
            replay=adapt(method,r['library'],base.LabelOracle(row['support_bank_answers'],8).reveal,row['task']+700)
            recorded=copy.deepcopy(d)
            for k in ('metrics','predictions'):recorded.pop(k)
            if digest(recorded)!=digest(replay):raise ValueError('choice_or_compute_replay')


def saved_replay(root):
    r=json.loads((Path(root)/'artifacts/seed_investigation_hybrid.json').read_text())
    validate_output(dict(study=r,resources=r['resources']),r['config'],dict(real_steps=5000,updates=0,imagined_transitions=0))
    return dict(id='seed-investigation-hybrid-1',mode='exploration',status='complete_development',wall_s=r['host_receipt']['wall_s'],memory_mb=r['host_receipt']['peak_sampled_rss_mb'],revision=r['execution_sha'],resources=r['resources'],curve=[],investigation_transfer=r['analysis'])
