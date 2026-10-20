"""Foundation views and versioned additions to the SAME Session/E1 journal.

Every persisted derived payload is recomputed on restore. The client cannot
label a failed proposal accepted, omit checks, or silently overwrite evidence.
"""
import copy
import json
from nexus.evolution1.catalogue import digest
from . import knowledge, library, language, curriculum, programs, inquiry, semantics

KIND='seed_foundation'


def records(session):
    return [(e.fingerprint,json.loads(e.payload_json)) for e in session.journal.snapshot() if e.kind==KIND]


def state(session):
    out=dict(documents=[],proposals={},reviews={},active=None,traces=[],investigations={},used_checks=set(),expression_proposals={},expression_reviews={},active_expressions={},aliases={},lessons={},curriculum_feedback=[])
    for ref,p in records(session):
        op=p['op'];r=p['result']
        if op=='ingest': out['documents'].append(r)
        elif op=='propose': out['proposals'][ref]=p
        elif op=='review':
            out['reviews'][ref]=p
            for row in p['args']['checks']:
                out['used_checks'].add(('task',row['task']))
                out['used_checks'].update(('input',digest(x['input'])) for x in row['examples'])
            if r['accepted']: out['active']=ref
        elif op=='rollback': out['active']=p['args']['target']
        elif op=='language_trace': out['traces'].append(p['args'])
        elif op=='investigation': out['investigations'][ref]=r
        elif op=='expression_propose':out['expression_proposals'][ref]=p
        elif op=='expression_review':
            out['expression_reviews'][ref]=p
            for row in p['args']['checks']:
                out['used_checks'].add(('task',row['task']));out['used_checks'].update(('input',digest(e['input'])) for e in row['examples'])
            if r['accepted']:out['active_expressions'][r['candidate']['name']]=ref
        elif op=='expression_rollback':
            if p['args']['target'] is None:out['active_expressions'].pop(p['args']['name'],None)
            else:out['active_expressions'][p['args']['name']]=p['args']['target']
        elif op=='alias':out['aliases'][p['args']['phrase']]=dict(ref=ref,**r)
        elif op=='curriculum_issue':out['lessons'].update({t['id']:t for t in r['tasks']})
        elif op=='curriculum_submit':out['curriculum_feedback'].append(r)
    return out


def build(session,op,args):
    if session.stopped: raise ValueError('resume_before_foundation_edit')
    if len(records(session))>=128: raise ValueError('foundation_journal_cap')
    s=state(session)
    if type(args) is not dict: raise ValueError('typed_foundation_args')
    fields={'ingest':{'source','text'},'propose':{'programs'},'review':{'proposal','candidate','checks'},
            'rollback':{'target'},'language_trace':{'role','intent','surface'},'investigation':{'traces'}}
    fields.update(expression_propose={'programs'},expression_review={'proposal','candidate','checks'},expression_rollback={'name','target'},alias={'phrase','skill','replace'},curriculum_issue={'seed','count'},curriculum_submit={'task','answer'})
    if op not in fields or set(args)!=fields[op]: raise ValueError('foundation_operation_fields')
    if op=='ingest':
        if len(s['documents'])>=16: raise ValueError('document_count_cap')
        result=knowledge.ingest(**args)
        if any(d['sha256']==result['sha256'] and d['source']==result['source'] for d in s['documents']): raise ValueError('duplicate_document')
    elif op=='propose':
        if any(('task',row['task']) in s['used_checks'] or any(('input',digest(x['input'])) in s['used_checks'] for x in row['examples']) for row in args['programs']): raise ValueError('assessment_cannot_train_library')
        result=library.propose(args['programs'])
    elif op=='review':
        if args['proposal'] not in s['proposals'] or any(p['args']['proposal']==args['proposal'] for p in s['reviews'].values()): raise ValueError('unconsumed_library_proposal')
        source=s['proposals'][args['proposal']];candidate=next((c for c in source['result'] if c['id']==args['candidate']),None)
        if candidate is None: raise ValueError('proposed_candidate_required')
        if any(('task',row['task']) in s['used_checks'] or any(('input',digest(x['input'])) in s['used_checks'] for x in row['examples']) for row in args['checks']): raise ValueError('fresh_assessment_required')
        result=library.assess(candidate,source['args']['programs'],args['checks'])
        result.update(candidate=candidate,previous=s['active'])
    elif op=='rollback':
        if args['target'] is not None and (args['target'] not in s['reviews'] or not s['reviews'][args['target']]['result']['accepted']): raise ValueError('accepted_revision_required')
        result=dict(previous=s['active'],target=args['target'])
    elif op=='language_trace':
        if type(args['intent']) is not str or not 1<=len(args['intent'])<=128: raise ValueError('language_intent')
        language.render(dict(intent=args['intent'],decision='check',reason='source trace',evidence=['trace'],uncertainty=1),[args],{'trace'})
        result=dict(status='source_wording_feedback_not_factual_learning')
    elif op=='investigation':result=inquiry.learn(args['traces'])
    elif op=='expression_propose':
        if any(('task',row['task']) in s['used_checks'] or any(('input',digest(e['input'])) in s['used_checks'] for e in row['examples']) for row in args['programs']):raise ValueError('assessment_cannot_train_library')
        result=library.expression_propose(args['programs'])
    elif op=='expression_review':
        source=s['expression_proposals'].get(args['proposal'])
        if source is None or any(p['args']['proposal']==args['proposal'] for p in s['expression_reviews'].values()):raise ValueError('unconsumed_expression_proposal')
        candidate=next((x for x in source['result'] if x['id']==args['candidate']),None)
        if candidate is None:raise ValueError('known_expression_candidate')
        if len(s['active_expressions'])>=8 and candidate['name'] not in s['active_expressions']:raise ValueError('expression_library_capacity')
        if any(('task',row['task']) in s['used_checks'] or any(('input',digest(e['input'])) in s['used_checks'] for e in row['examples']) for row in args['checks']):raise ValueError('fresh_expression_assessment_required')
        result=library.expression_assess(candidate,source['args']['programs'],args['checks']);result['previous']=s['active_expressions'].get(candidate['name'])
    elif op=='expression_rollback':
        target=args['target'];name=args['name']
        if name not in s['active_expressions'] and target is None:raise ValueError('active_expression_required')
        if target is not None and (target not in s['expression_reviews'] or not s['expression_reviews'][target]['result']['accepted'] or s['expression_reviews'][target]['result']['candidate']['name']!=name):raise ValueError('accepted_expression_revision_required')
        result=dict(previous=s['active_expressions'].get(name),target=target)
    elif op=='alias':
        import re
        from ..skill_library import state as shared_state
        phrase=args['phrase'];known=shared_state(session)['active']
        if type(phrase) is not str or not re.fullmatch(r'[a-z][a-z ]{1,79}',phrase) or type(args['replace']) is not bool:raise ValueError('bounded_taught_phrase')
        if phrase in s['aliases'] and not args['replace']:raise ValueError('explicit_alias_replacement_required')
        if args['skill'] not in known:raise ValueError('verified_shared_skill_required')
        ref,p=known[args['skill']];result=dict(skill=args['skill'],evidence=ref,program=p['program'],origin='owner_taught_grounded_alias')
    elif op=='curriculum_issue':
        tasks=curriculum.generate(s['curriculum_feedback'],args['seed'],args['count'])
        if len(s['lessons'])+len(tasks)>48 or any(t['id'] in s['lessons'] for t in tasks):raise ValueError('unique_bounded_curriculum')
        result=dict(tasks=tasks,selector='existing_kind_statistics_weakest_source_performance_with_epsilon_exploration')
    else:
        if args['task'] not in s['lessons'] or any(x['task']==args['task'] for x in s['curriculum_feedback']):raise ValueError('fresh_issued_source_task')
        task=s['lessons'][args['task']];programs.bounded(args['answer']);out=programs.execute(task['program'],task['inputs'])
        correct=digest(out['value'])==digest(args['answer'])
        result=dict(task=args['task'],family=task['family'],correct=correct,expected=out['value'],instructions=out['instructions'],reward=float(correct)-.001*out['instructions'],role='source',label='public_source_exercise_not_scientific_assessment')
    return dict(op=op,args=copy.deepcopy(args),result=result)


def validate_event(payload,session):
    if type(payload) is not dict or set(payload)!={'op','args','result'} or payload!=build(session,payload['op'],payload['args']): raise ValueError('foundation_event_not_reproduced')


def inspect(session):
    s=state(session)
    from nexus.seed.skill_library import view
    return dict(curriculum=curriculum.lessons(),documents=s['documents'],knowledge=knowledge.consolidate(s['documents']),
                proposals=[dict(ref=r,**p) for r,p in s['proposals'].items()],
                reviews=[dict(ref=r,**p) for r,p in s['reviews'].items()],active_macro=s['active'],
                investigations=s['investigations'],wording_traces=len(s['traces']),skills=view(session)['entries'],
                expression_proposals=[dict(ref=r,**p) for r,p in s['expression_proposals'].items()],expression_reviews=[dict(ref=r,**p) for r,p in s['expression_reviews'].items()],active_expressions=s['active_expressions'],aliases=s['aliases'],
                curriculum_progress=dict(issued=len(s['lessons']),completed=len(s['curriculum_feedback']),feedback=s['curriculum_feedback']),
                limits=dict(events=128,documents=16,instructions=512),
                scope='bounded executable foundation; no demonstrated cumulative intelligence')


def request(session,req):
    if type(req) is not dict or set(req)!={'op','args'} or type(req['op']) is not str or not req['op'].startswith('foundation_') or type(req['args']) is not dict: raise ValueError('foundation_request')
    op=req['op'].removeprefix('foundation_');args=req['args'];s=state(session)
    if op in ('ingest','propose','review','rollback','language_trace','investigation','expression_propose','expression_review','expression_rollback','alias','curriculum_issue','curriculum_submit'):
        p=build(session,op,args);ref=session.event(KIND,p);result=dict(ref=ref,**p['result']) if type(p['result']) is dict else dict(ref=ref,candidates=p['result'])
    elif op=='inspect' and not args: result=inspect(session)
    elif op=='retrieve' and set(args)=={'query'}: result=knowledge.retrieve(s['documents'],args['query'])
    elif op=='exercise' and set(args)=={'stage'}: result=curriculum.exercise(args['stage'])
    elif op=='execute' and set(args)=={'program','inputs'}:
        functions={}
        if s['active']: functions['macro']=programs.pipeline(s['reviews'][s['active']]['result']['candidate']['ops'])
        functions.update({name:s['expression_reviews'][ref]['result']['candidate']['program'] for name,ref in s['active_expressions'].items()})
        result=programs.execute(args['program'],args['inputs'],functions)
    elif op=='phrase' and set(args)=={'phrase','input'}:
        from ..skill_programs import run
        alias=s['aliases'].get(args['phrase'])
        if alias is None:raise ValueError('unknown_taught_phrase')
        result=dict(value=run(alias['program'],args['input']),evidence=alias['evidence'],phrase=alias['ref'],label='execution_of_owner_taught_phrase')
    elif op=='workbench' and not args:
        from ..structure.runtime import inspect as inspect_graph
        result=dict(foundation=inspect(session),graph=inspect_graph(session),phases=[
            dict(phase=i,name=name,status='bounded_workflow_implemented',scientific_scope=scope) for i,name,scope in (
                (1,'Structured state and history','narrow authored prediction evidence'),(2,'Reusable mechanisms','typed planning and supplied mechanisms; general transfer unproven'),
                (3,'Investigation procedures','source development; latest replication is separate read-only evidence'),(4,'Grounded command language','finite meanings, taught aliases and source wording; broad grammar unproven'),
                (5,'Program library growth','checked list and typed-expression abstractions; cumulative scientific benefit unproven'),(6,'Mixed-domain curriculum','generated source exercises and verified progress; cross-domain learning benefit unproven'),
                (7,'Local conversational product','bounded chat, tools and durable sessions; open-ended conversation unproven'))],
                tools=['execute','retrieve','inspect_graph','phrase'],automatic_scientific_execution=False)
    elif op=='tool' and set(args)=={'name','arguments'}:
        names={'execute','retrieve','phrase'}
        if args['name'] in names:return request(session,dict(op='foundation_'+args['name'],args=args['arguments']))
        if args['name']=='inspect_graph' and args['arguments']=={}:
            from ..structure.runtime import inspect as inspect_graph
            result=inspect_graph(session)
        else:raise ValueError('vetted_pure_tool_only')
    elif op=='instruction' and set(args)=={'text','input'}:
        result=curriculum.instruction(args['text'])
        if 'program' in result: result.update(programs.execute(result['program'],{'x':args['input']}))
    elif op=='question' and set(args)=={'candidates','pool','observed'}: result=inquiry.choose(**args)
    elif op=='container' and set(args)=={'graph','item','target','action'}: result=semantics.container(**args)
    elif op=='render' and set(args)=={'record'}:
        known={e.fingerprint for e in session.journal.snapshot()}|{u['id'] for d in s['documents'] for u in d['units']}
        result=language.render(args['record'],s['traces'],known)
    elif op=='investigate' and set(args)=={'ref','answers','budget'}:
        if args['ref'] not in s['investigations']: raise ValueError('known_investigation')
        answers=args['answers']
        if type(answers) is not dict or any(type(v) is not bool for v in answers.values()): raise ValueError('observed_probe_answers')
        result=inquiry.run(s['investigations'][args['ref']],lambda i:answers[str(i)],budget=args['budget'])
        result['observed_answer_reads']=result['real_probes'];result['real_probes']=0
        for row in result['transcript']: row['real']=False
        result.update(label='replay_of_supplied_observations',new_environment_interactions=0)
    else: raise ValueError('foundation_read_fields')
    return dict(text='Bounded foundation operation completed.',result=result)
