"""Skill-specific view of the existing Session/E1 journal, not another store.

Teaching proposes; fresh authored development checks alone can activate.
Validation answers never fit candidates or update the learning-rule bandit.
"""
import json
import random
from .core import WORD,concept_word
from . import skill_programs as ir
from nexus.evolution1.catalogue import digest
from nexus.meta.kind_statistics import kind_value,observe_kind

LABS=('language','coding','reasoning','world')
RULES=('enumerate','reuse_first')
EVENTS=('seed_shared_teaching','seed_shared_check','seed_shared_rollback')


def records(session):
    return [(e.fingerprint,e.kind,json.loads(e.payload_json)) for e in session.journal.snapshot() if e.kind in EVENTS]


def state(session):
    teaching={};latest={};active={};checks={};used=set()
    for ref,kind,p in records(session):
        if kind=='seed_shared_teaching':teaching[ref]=p;latest[p['name']]=(ref,p)
        elif kind=='seed_shared_check':
            checks[ref]=p;used.update((p['name'],ir.input_key(p['program']['schema'],v['input'])) for v in p['checks'])
            if p['accepted']:active[p['name']]=(ref,p)
        else:active[p['name']]=(p['target'],checks[p['target']])
    return dict(teaching=teaching,latest=latest,active=active,checks=checks,used=used)


def support(s,name):
    rows=[(ref,p) for ref,p in s['teaching'].items() if p['name']==name]
    superseded={p['supersedes'] for _,p in rows if p['supersedes'] is not None}
    return [v for ref,p in rows if ref not in superseded for v in p['examples']]


def named(lab,name,schema):
    if lab not in LABS or type(name) is not str or not WORD.fullmatch(name) or schema not in ir.SCHEMAS:raise ValueError('typed_lab_name_schema')
    if schema=='predicate' and not concept_word(name):raise ValueError('new_nonreserved_concept_name_required')


def controller(s):
    # Same extracted statistics as EpsilonGreedyController; stdlib-only replay.
    c=dict(name='existing_epsilon_greedy_statistics',epsilon=.1,kind_sum={},kind_n={})
    for p in s['teaching'].values():
        for f in p['feedback']:
            observe_kind(c['kind_sum'],c['kind_n'],p['schema']+'/'+f['rule'],f['reward'])
    return c


def rule_choice(s,schema,mode,feedback=()):
    if mode not in ('adaptive',)+RULES:raise ValueError('shared_learning_rule')
    if mode!='adaptive':return mode,'fixed_rule'
    c=controller(s)
    for f in feedback:observe_kind(c['kind_sum'],c['kind_n'],schema+'/'+f['rule'],f['reward'])
    unseen=[r for r in RULES if not c['kind_n'].get(schema+'/'+r,0)]
    # Assessment data/labels are deliberately absent from proposal randomness.
    rng=random.Random(digest(dict(source=list(s['teaching'].values()),revealed_feedback=list(feedback))))
    if unseen:return unseen[0],'existing_epsilon_greedy'
    if rng.random()<c['epsilon']:return rng.choice(RULES),'existing_epsilon_greedy'
    return max(RULES,key=lambda r:(kind_value(c['kind_sum'],c['kind_n'],schema+'/'+r),-RULES.index(r))),'existing_epsilon_greedy'


def candidates(s,name,schema,rows,rule,order):
    tested=0
    if rule=='reuse_first':
        prior={digest(s['active'][name][1]['program']):s['active'][name][1]['program'] for name in order}
        for p in prior.values():
            tested+=1
            if ir.matches(p,rows):return [p],tested,'shared_verified_skill'
    found=[]
    for p in ir.catalogue(schema):
        tested+=1
        if ir.matches(p,rows):found.append(p)
    return found,tested,'bounded_catalogue'


def future_feedback(s,name,new_rows):
    if name not in s['latest']:return []
    _,old=s['latest'][name];known={ir.input_key(old['schema'],v['input']) for v in support(s,name)}
    fresh=[v for v in new_rows if ir.input_key(old['schema'],v['input']) not in known]
    if not fresh:return []
    def loss(p,r):
        if p is None:return 1.
        try:return float(ir.run(p,r['input'])!=r['output'])
        except ValueError:return 1.
    before=old['before_program'];after=old['candidates'][0] if len(old['candidates'])==1 else None
    b=sum(loss(before,r) for r in fresh)/len(fresh);a=sum(loss(after,r) for r in fresh)/len(fresh)
    return [dict(rule=old['rule'],before_error=b,after_error=a,labels=len(fresh),
                 compute=old['candidate_evaluations'],reward=b-a-.001*old['candidate_evaluations'])]


def teaching_payload(session,*,lab,name,schema,examples,mode='adaptive',supersedes=None,prototype=None,model_hash=None,retrieval_order=None):
    named(lab,name,schema);ir.labeled(schema,examples);s=state(session)
    if schema=='predicate' and (name in session.definitions or any(e['word']==name for e in session.evidence)):raise ValueError('existing_seed_word_uses_original_teaching_and_correction')
    if len(s['teaching'])>=128 or len(s['latest'])>=32 and name not in s['latest']:raise ValueError('shared_library_cap')
    if name in s['latest'] and s['latest'][name][1]['schema']!=schema:raise ValueError('named_skill_schema_is_fixed')
    if any((name,ir.input_key(schema,v['input'])) in s['used'] for v in examples):raise ValueError('assessment_examples_cannot_become_teaching')
    if supersedes is not None:
        if supersedes not in s['teaching'] or s['teaching'][supersedes]['name']!=name or any(p['supersedes']==supersedes for p in s['teaching'].values()):raise ValueError('active_teaching_reference_required')
    old_rows=[(ref,p) for ref,p in s['teaching'].items() if p['name']==name]
    omitted={p['supersedes'] for _,p in old_rows if p['supersedes'] is not None}|({supersedes} if supersedes else set())
    rows=[v for ref,p in old_rows if ref not in omitted for v in p['examples']]+examples
    if len(rows)>64:raise ValueError('teaching_rows_per_skill_cap')
    eligible=sorted(n for n,(_,p) in s['active'].items() if p['program']['schema']==schema)
    order=eligible if retrieval_order is None else retrieval_order
    if type(order) is not list or len(order)!=len(set(order)) or set(order)!=set(eligible):raise ValueError('compatible_shared_retrieval_order')
    feedback=[] if supersedes else future_feedback(s,name,examples)
    rule,selector=rule_choice(s,schema,mode,feedback);found,tests,origin=candidates(s,name,schema,rows,rule,order)
    before=s['active'][name][1]['program'] if name in s['active'] else None
    return dict(lab=lab,name=name,schema=schema,examples=examples,mode=mode,supersedes=supersedes,
        rule=rule,selector=selector,candidates=found,candidate_evaluations=tests,origin=origin,
        before_program=before,feedback=feedback,
        prototype=prototype,model_hash=model_hash,retrieval_order=order)


def teach(session,**kwargs):
    p=teaching_payload(session,**kwargs);ref=session.event('seed_shared_teaching',p)
    session.charge('teacher_answers',len(p['examples']));session.charge('candidate_evaluations',p['candidate_evaluations'])
    return ref,p


def check_payload(session,*,name,attempt,checks):
    s=state(session)
    if name not in s['latest'] or s['latest'][name][0]!=attempt:raise ValueError('current_attempt_required')
    p=s['teaching'][attempt];ir.labeled(p['schema'],checks)
    if any(q['attempt']==attempt for q in s['checks'].values()):raise ValueError('assessment_attempt_consumed')
    if len(p['candidates'])!=1:raise ValueError('clarify_teaching_before_assessment')
    training={ir.input_key(p['schema'],v['input']) for v in support(s,name)}
    if any(ir.input_key(p['schema'],v['input']) in training or (name,ir.input_key(p['schema'],v['input'])) in s['used'] for v in checks):raise ValueError('fresh_disjoint_assessment_required')
    candidate=p['candidates'][0];accepted=ir.matches(candidate,checks) and ir.matches(candidate,support(s,name))
    return dict(name=name,attempt=attempt,checks=checks,program=candidate,accepted=accepted,
        prior=s['active'][name][0] if name in s['active'] else None,
        label='authored_development_check_not_confirmation')


def assess(session,**kwargs):
    p=check_payload(session,**kwargs);ref=session.event('seed_shared_check',p)
    session.charge('teacher_answers',len(p['checks']));session.charge('program_evaluations',1)
    return ref,p


def rollback_payload(session,name,target):
    s=state(session)
    if name not in s['active'] or target not in s['checks'] or not s['checks'][target]['accepted'] or s['checks'][target]['name']!=name:raise ValueError('verified_skill_revision_required')
    if not ir.matches(s['checks'][target]['program'],support(s,name)):raise ValueError('rollback_conflicts_current_teaching')
    return dict(name=name,target=target,prior=s['active'][name][0])


def validate_event(kind,p,session):
    """Rebuild derived records on save/load without neural inference or fitting."""
    if session.stopped:raise ValueError('shared_event_while_stopped')
    if kind=='seed_shared_teaching':
        if type(p) is not dict or set(p)!={'lab','name','schema','examples','mode','supersedes','rule','selector','candidates','candidate_evaluations','origin','before_program','feedback','prototype','model_hash','retrieval_order'}:raise ValueError('shared_teaching_fields')
        proto=p['prototype'];model_hash=p['model_hash']
        if proto is not None:
            import math
            import re
            if type(proto) is not list or len(proto)!=32 or any(type(v) not in (int,float) or not math.isfinite(v) for v in proto) or type(model_hash) is not str or not re.fullmatch('[a-f0-9]{64}',model_hash):raise ValueError('shared_prototype_shape_hash')
        elif model_hash is not None:raise ValueError('prototype_and_model_hash_pair')
        expected=teaching_payload(session,**{k:p[k] for k in ('lab','name','schema','examples','mode','supersedes','prototype','retrieval_order')},model_hash=model_hash)
    elif kind=='seed_shared_check':
        if type(p) is not dict or set(p)!={'name','attempt','checks','program','accepted','prior','label'}:raise ValueError('shared_assessment_fields')
        expected=check_payload(session,**{k:p[k] for k in ('name','attempt','checks')})
    elif kind=='seed_shared_rollback':
        expected=rollback_payload(session,p['name'],p['target'])
    else:raise ValueError('shared_event_kind')
    if p!=expected:raise ValueError('shared_event_not_reproduced')
    if kind=='seed_shared_teaching':
        session.charge('teacher_answers',len(p['examples']));session.charge('candidate_evaluations',p['candidate_evaluations'])
    if kind=='seed_shared_check':session.charge('teacher_answers',len(p['checks']));session.charge('program_evaluations',1)


def view(session):
    s=state(session);entries=[]
    for name,(ref,p) in s['latest'].items():
        active=s['active'].get(name);rows=support(s,name)
        entries.append(dict(name=name,schema=p['schema'],origin_lab=p['lab'],attempt=ref,candidate_count=len(p['candidates']),
            status='verified_on_authored_checks' if active else 'needs_teaching' if len(p['candidates'])!=1 else 'needs_fresh_checks',
            active_revision=active[0] if active else None,program=active[1]['program'] if active else None,
            prior_revision=active[1]['prior'] if active else None,example_input=rows[0]['input'] if rows else None,
            candidates=p['candidates'],question=ir.question(p['schema'],p['candidates'],{ir.input_key(p['schema'],v['input']) for v in rows}|{h for n,h in s['used'] if n==name}),
            current_teaching_consistent=ir.matches(active[1]['program'],rows) if active else None,
            model_hash=p['model_hash'],teaching_examples=len(rows),selector=p['selector']))
    meta=controller(s)
    return dict(entries=entries,learning_rules=meta,program_catalogue={schema:len(ir.catalogue(schema)) for schema in ir.SCHEMAS},
        evidence_events=len(records(session)),scientific=False,learning_to_learn_demonstrated=False)
