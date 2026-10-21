"""Bounded conversational adapter over SharedBrain and the SAME Session journal.

Parsing, execution and rendering are separate. No LLM, new learner or store.
Saved turns are validated as data, never dispatched again on restoration.
"""
from dataclasses import dataclass,field
import copy
import json
import re
from .core import WORD,GRAMMAR,PROPERTIES,examples
from . import skill_library as lib
from . import skill_programs as ir
from .working import current

KIND='seed_conversation_turn'
INITIAL=dict(active_name=None,lab='coding',pending=None,last_teaching=None)


@dataclass(frozen=True)
class Intent:
    kind:str
    values:dict=field(default_factory=dict)


def turns(session):return [json.loads(e.payload_json) for e in session.journal.snapshot() if e.kind==KIND]
def context(session):
    rows=turns(session)
    return copy.deepcopy(rows[-1]['context'] if rows else INITIAL)


def interpret(text,ctx):
    """Pure bounded intent parser. It cannot inspect answers or execute code."""
    if type(text) is not str or not 1<=len(text.strip())<=3000 or '\x00' in text:raise ValueError('chat_text_limit')
    raw=text.strip();t=re.sub(r'\s+',' ',raw.lower()).strip(' .!?')
    if t in ('hi','hello','hey','good morning'):return Intent('hello')
    if t in ('help','what can you do','what do you do','how does this work'):return Intent('help')
    if t in ('save','save this conversation','save conversation','save our conversation'):return Intent('save')
    if t in ('stop','cancel','pause'):return Intent('stop')
    if t in ('resume','continue','keep going'):return Intent('resume')
    if t in ('what have you learned','show memory','show me your memory','inspect memory','what do you remember'):return Intent('memory')
    if t in ('show the world','show world','look around','where are the objects'):return Intent('world')
    if t in ('that answer was wrong','that was wrong','correct my previous example','correct the previous example','correct that','change my last example'):return Intent('correct')
    if t in ('show me some examples','show examples','examples','give me an example'):return Intent('examples')
    if t in ('show foundation','show curriculum','foundation','curriculum'):return Intent('foundation')
    if t in ('show phases','show all phases','open workbench'):return Intent('workbench')
    if t in ('show master architecture','master architecture','inspect master'):return Intent('master_inspect')
    if t in ('generate lessons','give me lessons','create curriculum'):return Intent('curriculum_generate')
    if any(p in t for p in ('how are you','how are u','how r u','how is it going','how\'s it going','how do you feel','who are you','what are you','what is your name','tell me about yourself','introduce yourself')) or t in ('thanks','thank you','thx','ty','good job','great job','awesome'):return Intent('master_dialogue',dict(text=raw))
    if any(p in t for p in ('learning to learn','meta learning','meta-learning','general intelligence','are you agi','did we achieve','run general suite')):return Intent('master_dialogue',dict(text=raw))
    if t.startswith(('solve ','calculate ','compute ')) or re.fullmatch(r'[0-9x\+\-\*\/\(\)\.\s=]+',t) and any(op in t for op in ('+','-','*','/','=')):return Intent('master_dialogue',dict(text=raw))
    if re.fullmatch(r'["“][a-z][a-z0-9_]{0,23}["”] means .+',t):return Intent('master_dialogue',dict(text=raw))
    if re.search(r'^if .+ is .+ (?:of|than) .+ and .+ is .+ (?:of|than) .+',t):return Intent('master_dialogue',dict(text=raw))
    if ('arrange' in t or 'sort' in t) and ('smallest to largest' in t or 'largest to smallest' in t):return Intent('master_dialogue',dict(text=raw))
    m=re.fullmatch(r'(teach|replace) phrase "([a-z ]+)" as ([a-z][a-z0-9_]*)',t)
    if m:return Intent('alias',dict(phrase=m[2],skill=m[3],replace=m[1]=='replace'))
    m=re.fullmatch(r'run phrase "([a-z ]+)" on (.+)',raw,flags=re.I)
    if m:
        try:value=json.loads(m[2])
        except ValueError:return Intent('unsupported')
        return Intent('phrase',dict(phrase=m[1].lower(),input=value))
    m=re.fullmatch(r'answer lesson (\d+):\s*(.+)',raw,flags=re.I|re.S)
    if m:
        try:value=json.loads(m[2])
        except ValueError:return Intent('unsupported')
        return Intent('curriculum_answer',dict(index=int(m[1])-1,answer=value))
    m=re.fullmatch(r'(?:write code to|run code to) (.+?)(?: on (\[.*\]))?[.!?]?',raw,flags=re.I)
    if m:
        aliases={'sort':'sort','sort a list':'sort','reverse':'reverse','reverse a list':'reverse','remove duplicates':'unique','keep even numbers':'even','increment':'increment'}
        parts=re.split(r'\s+(?:then|and)\s+',m[1].lower().strip())
        if not 1<=len(parts)<=8 or any(p not in aliases for p in parts):return Intent('unsupported')
        try:value=json.loads(m[2]) if m[2] else None
        except ValueError:return Intent('unsupported')
        return Intent('compose_code',dict(ops=[aliases[p] for p in parts],input=value))
    if t.startswith('remember text:'):return Intent('ingest',dict(text=raw.split(':',1)[1].strip()))
    m=re.fullmatch(r'(?:what does|what is) (?:the )?(.+?)(?: mean)?',t)
    if m:return Intent('meaning',{'name':m[1]})
    m=re.fullmatch(r'(?:a |an )?([a-z][a-z0-9]{0,23}) (?:means|is) (?:an object that is |a |an )?(.+?)(?: object)?',t)
    if m:return Intent('definition',dict(name=m[1],definition=m[2]))
    m=re.fullmatch(r'(?:use|run|apply) (?:the )?(.+?) (?:on|to) (\[.*\])\s*[.!?]?',raw,flags=re.I|re.S)
    if m:
        name=m[1].lower()
        if name not in ('this skill','that skill','this word','that word','that pattern'):name=re.sub(r' (?:skill|pattern)$','',name)
        try:value=json.loads(m[2])
        except (ValueError,RecursionError):return Intent('unsupported')
        return Intent('run',dict(name=name,input=value))
    m=re.fullmatch(r'move (?:the )?(.+?) (?:object )?to (?:the )?(.+)',t)
    if m:return Intent('goal',dict(reference=m[1].removesuffix(' object'),goal=m[2]))
    m=re.fullmatch(r'move (?:the )?(.+?) (left|right|up|down)(?: (\d+))?',t)
    if m:return Intent('move',dict(reference=m[1].removesuffix(' object'),direction=m[2],steps=int(m[3] or 1)))
    if re.search(r'(?:teach|learn).*(?:word|concept)',t):return Intent('start',dict(lab='language',schema='predicate'))
    if re.search(r'(?:teach|learn).*(?:skill|program|code)',t):return Intent('start',dict(lab='coding',schema='list'))
    if 'pattern' in t or t in ('reason with me','reasoning lab'):return Intent('start',dict(lab='reasoning',schema='list'))
    if 'teach' in t and 'relation' in t:return Intent('start',dict(lab='reasoning',schema='relation'))
    pending=ctx['pending']
    if pending:
        if pending['kind']=='name':return Intent('name',dict(name=t.removeprefix('call it ').removeprefix('name it ')))
        if pending['kind'] in ('label','check_label') and t in ('yes','true','no','false'):
            return Intent('label',dict(output=t in ('yes','true')))
        if pending['kind']=='object' and WORD.fullmatch(t):return Intent('object',dict(reference=t))
        if pending['kind'] in ('examples','checks','correction'):
            try:
                if '->' in raw or '→' in raw:
                    rows=[]
                    for line in raw.splitlines():
                        a,b=re.split(r'\s*(?:->|→)\s*',line,maxsplit=1);rows.append(dict(input=json.loads(a),output=json.loads(b)))
                else:
                    rows=json.loads(raw)
                    if type(rows) is dict:rows=[rows]
                return Intent('rows',dict(rows=rows))
            except (ValueError,TypeError,RecursionError):return Intent('clarify_examples')
    return Intent('unsupported')


def validate_turn(p,session):
    """Schema/reference checks only; absolutely no intent execution on replay."""
    if type(p) is not dict or set(p)!={'id','user','assistant','status','cards','context','evidence_refs'}:raise ValueError('chat_turn_schema')
    if type(p['id']) is not str or not re.fullmatch('[a-f0-9]{32}',p['id']) or any(row['id']==p['id'] for row in turns(session)):raise ValueError('chat_turn_id')
    if any(type(p[k]) is not str or not 1<=len(p[k])<=5000 for k in ('user','assistant')) or p['status'] not in ('reply','clarification','success','error'):raise ValueError('chat_turn_text')
    c=p['context']
    if type(c) is not dict or set(c)!=set(INITIAL) or c['lab'] not in lib.LABS or c['active_name'] is not None and (type(c['active_name']) is not str or not WORD.fullmatch(c['active_name'])):raise ValueError('chat_context_schema')
    s=lib.state(session);known={e.fingerprint for e in session.journal.snapshot()}
    if type(p['evidence_refs']) is not list or len(p['evidence_refs'])>8 or any(v not in known for v in p['evidence_refs']):raise ValueError('chat_evidence_reference')
    if c['last_teaching'] is not None and c['last_teaching'] not in s['teaching']:raise ValueError('chat_teaching_reference')
    pending=c['pending']
    if pending is not None:
        if type(pending) is not dict or pending.get('kind') not in ('name','examples','checks','label','check_label','correction','object') or len(json.dumps(pending))>6000:raise ValueError('chat_pending_schema')
        allowed={'kind','schema','input','goal','attempt','supersedes'}
        if set(pending)-allowed:raise ValueError('chat_pending_fields')
        if pending.get('schema') not in ir.SCHEMAS+(None,):raise ValueError('chat_pending_domain')
        for key in ('attempt','supersedes'):
            if key in pending and pending[key] not in s['teaching']:raise ValueError('chat_pending_reference')
        if 'input' in pending:ir.value(pending['schema'],pending['input'])
        if 'goal' in pending and (type(pending['goal']) is not list or len(pending['goal'])!=2 or any(type(v) is not int or not 0<=v<6 for v in pending['goal'])):raise ValueError('chat_goal_schema')
    if type(p['cards']) is not list or len(p['cards'])>8:raise ValueError('chat_cards')
    for card in p['cards']:
        if type(card) is not dict or set(card)!={'title','data'} or type(card['title']) is not str or len(card['title'])>120 or len(json.dumps(card['data'],allow_nan=False))>6000:raise ValueError('chat_card_schema')
    if len(json.dumps(p,allow_nan=False).encode())>14000:raise ValueError('chat_turn_size')


class Conversation:
    def __init__(self,brain):self.brain=brain;self.session=brain.session

    def view(self):
        rows=turns(self.session)
        return dict(messages=rows,context=context(self.session),state=self.brain.inspect(),stopped=self.session.stopped,
            limits=dict(turns=160,text_characters=3000),supported_scope='Finite authored concepts, bounded list/relation programs and known-grid movement; no external LLM.')

    def send(self,text,identifier):
        if type(identifier) is not str or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('chat_request_id')
        existing=next((r for r in turns(self.session) if r['id']==identifier),None)
        if existing:
            if existing['user']!=text:raise ValueError('chat_id_text_mismatch')
            return dict(text=existing['assistant'],chat=self.view(),save_requested=False,duplicate=True)
        if len(turns(self.session))>=160 or len(self.session.journal.snapshot())>2030:raise ValueError('chat_turn_cap')
        ctx=context(self.session);intent=interpret(text,ctx);before=len(self.session.journal.snapshot());costs=dict(self.session.counts)
        cards=[];status='reply';save=False
        def card(title,data):cards.append(dict(title=title,data=data))
        try:
            reply,status,save=self.execute(intent,ctx,card)
        except (ValueError,TypeError,KeyError,TimeoutError) as exc:
            reply=self.friendly_error(str(exc));status='clarification' if str(exc).startswith('clarify_') else 'error';card('What happened',dict(reason=str(exc),previous_verified_skills_retained=True))
        row=dict(id=identifier,user=text,assistant=reply,status=status,cards=cards,context=ctx,
            evidence_refs=[e.fingerprint for e in self.session.journal.snapshot()[before:]])
        validate_turn(row,self.session);self.session.event(KIND,row)
        return dict(text=reply,chat=self.view(),save_requested=save,duplicate=False,
            resources={k:self.session.counts[k]-v for k,v in costs.items()})

    @staticmethod
    def friendly_error(reason):
        if reason=='phrase_revision_no_longer_active':return 'That phrase points to a rolled-back revision. Teach it again using a currently verified skill or function.'
        if reason=='clarify_name':return 'Which word or skill do you mean? Tell me its name.'
        if 'fresh_disjoint' in reason or 'assessment_examples_cannot_become_teaching' in reason:return 'That example was already used for teaching or checking. Please give a different input for the separate check.'
        if 'consumed' in reason:return 'That check attempt has already been used. Add a new teaching example to make a new proposal before checking again.'
        if 'verified_shared_skill' in reason:return 'That skill is not verified yet. Teach examples and complete a separate check before using it.'
        if 'explicit_alias_replacement_required' in reason:return 'That phrase already has a meaning. Use “Replace phrase ... as ...” if you want to update it.'
        if 'issued_lesson_number' in reason or 'fresh_issued_source_task' in reason:return 'Choose an unanswered lesson number from the latest issued curriculum batch (for example, “Answer lesson 1: [1, 2]”).'
        if 'name' in reason or 'word' in reason:return 'Choose a short name using letters and numbers, starting with a letter. Property names such as “red” are already reserved.'
        if 'resume' in reason or 'cancel' in reason:return 'This conversation is paused. Say “resume” before teaching or acting again.'
        if 'bounded_integer' in reason:return 'Use a list of at most 16 integers between −64 and 64.'
        return f'I couldn’t complete that request ({reason}). Your earlier evidence is preserved. Try the suggested example format or ask “What can you do?” for help.'

    def resolve_name(self,name,ctx):
        if name in ('that word','this word','that skill','this skill','it','that pattern'):
            if ctx['pending'] and ctx['pending']['kind']=='name':raise ValueError('clarify_name')
            name=ctx['active_name'] or current(self.session.journal.snapshot()).last_concept
        if not name:raise ValueError('clarify_name')
        return name

    def proposal(self,ctx,rows,card,supersedes=None):
        p=ctx['pending'];schema=p['schema'];name=ctx['active_name']
        response=self.brain.request(dict(op='lab_teach',lab=ctx['lab'],name=name,schema=schema,examples=rows,mode='enumerate',supersedes=supersedes))['result']
        ctx['last_teaching']=response['attempt'];entry=next(v for v in lib.view(self.session)['entries'] if v['name']==name)
        card('Teaching evidence',dict(name=name,examples=rows,candidate_count=entry['candidate_count']))
        if response['candidate_count']==0:
            ctx['pending']=dict(kind='correction',schema=schema,supersedes=response['attempt'])
            return 'These examples conflict with the supported programs. I kept any earlier verified skill. Correct this teaching batch or add a compatible example.','clarification',False
        if response['candidate_count']>1:
            q=entry['question']
            if q is not None and schema in ('predicate','relation'):
                ctx['pending']=dict(kind='label',schema=schema,input=q);card('A question for you',q)
                return f'I saved your examples. {entry["candidate_count"]} meanings still fit. Is this example a {name}? Reply yes or no.','clarification',False
            ctx['pending']=dict(kind='examples',schema=schema);card('Distinguishing input',q)
            return f'I saved your examples. {entry["candidate_count"]} programs still fit. What output should this new input produce? Send input -> output.','clarification',False
        ctx['pending']=dict(kind='checks',schema=schema,attempt=response['attempt'])
        if schema=='predicate':
            used={ir.input_key(schema,r['input']) for r in lib.support(lib.state(self.session),name)}|{h for n,h in lib.state(self.session)['used'] if n==name}
            q=next(x for x in examples() if ir.input_key(schema,x) not in used)
            ctx['pending']=dict(kind='check_label',schema=schema,attempt=response['attempt'],input=q);card('Separate check — you supply the answer',q)
            return f'One meaning fits {name}. Before I mark it verified, is this different object a {name}? Reply yes or no.','clarification',False
        card('Separate check — you supply the answer',{'input_suggestion':[9,3,1,9]} if schema=='list' else {'input_suggestion':{'first':examples()[0],'second':examples()[3]}})
        return f'One program fits {name}. Give a different input and its expected output as a separate check. I won’t train on this check.','clarification',False

    def execute(self,intent,ctx,card):
        k=intent.kind;v=intent.values;s=lib.state(self.session)
        if k in ('master_inspect','master_dialogue'):
            from .master.runtime import MasterSeedArchitecture
            arch=MasterSeedArchitecture(self.session,self.brain)
            if k=='master_inspect':
                info=arch.inspect()
                card('Master architecture (15 components)',dict(schema=info['architecture_schema'],components=info['components_implemented'],scientific_claim=info['scientific_claim']))
                return 'All 15 NEXUS Seed master architecture components are active over this Session and SharedBrain. This is a bounded research architecture, not a claim of AGI or learning-to-learn.','reply',False
            out=arch.handle_dialogue_turn(v['text'])
            card('Master cognitive trace',dict(exchange_kind=out['exchange_kind'],meta_operation=out['meta_decision']['selected_operation'],compute_tier=out['compute_tier']['tier_name'],verified=out['response']['verification_passed']))
            status='clarification' if out['exchange_kind'] in ('learning','clarification') else 'success'
            return out['response']['text'],status,False
        if k in ('workbench','curriculum_generate','curriculum_answer','alias','phrase'):
            from .foundation import runtime
            if k=='workbench':
                result=runtime.request(self.session,dict(op='foundation_workbench',args={}))['result']
                card('Seven connected phases',result['phases'])
                return 'All seven bounded workflows share this session. Open /foundation for graph state, typed programs, checked libraries, curriculum and tools. Each phase lists its evidence limits.','reply',False
            if k=='curriculum_generate':
                state=runtime.state(self.session);args=dict(seed=123000+len(state['lessons']),count=4)
                result=runtime.request(self.session,dict(op='foundation_curriculum_issue',args=args))['result']
                for i,task in enumerate(result['tasks']):card('Lesson '+str(i+1),{key:task[key] for key in ('id','family','program','inputs','label')})
                return 'I generated four source practice tasks. Read each program and input, then reply “Answer lesson 1: <JSON answer>”. These are public authored exercises; the results are not scientific confirmation.','reply',False
            if k=='curriculum_answer':
                state=runtime.state(self.session)
                # Lesson numbers refer to the most recently issued batch, even
                # after another answer; they cannot shift and grade another task.
                all_tasks=list(state['lessons'].values())[-4:]
                if not 0<=v['index']<len(all_tasks):raise ValueError('issued_lesson_number')
                task=all_tasks[v['index']];result=runtime.request(self.session,dict(op='foundation_curriculum_submit',args=dict(task=task['id'],answer=v['answer'])))['result']
                card('Actual source exercise result',result)
                return ('That answer matches the executable task.' if result['correct'] else 'That answer differs from the executable task; the result card shows the expected value.')+' I recorded it as source practice feedback.','success' if result['correct'] else 'reply',False
            result=runtime.request(self.session,dict(op='foundation_'+k,args=v))['result'];card('Grounded phrase evidence',result)
            return ('I saved that phrase as a reference to the separately verified skill.' if k=='alias' else 'I executed the taught phrase using its verified program.'),'success',False
        if k=='compose_code':
            if self.session.stopped:raise ValueError('resume_required')
            from .foundation.programs import pipeline,execute
            tree=pipeline(v['ops'])
            lines={'sort':'x = sorted(x)','reverse':'x = list(reversed(x))','unique':'x = list(dict.fromkeys(x))','even':'x = [v for v in x if v % 2 == 0]','increment':'x = [v + 1 for v in x]'}
            data=dict(kind='bounded_code',python='def transform(x):\n'+''.join('    '+lines[o]+'\n' for o in v['ops'])+'    return x',program=tree,operators=v['ops'],executed=False)
            if v['input'] is not None:
                ir.value('list',v['input'])
                outcome=execute(tree,{'x':v['input']},budget=128)
                data.update(executed=True,input=v['input'],output=outcome['value'],instructions=outcome['instructions'])
            card('Executable list program',data)
            return 'I composed these supplied list operators. The displayed Python is an equivalent explanation; execution uses the bounded expression interpreter, with no file or shell access. This is not unrestricted code generation.','success',False
        if k=='foundation':
            from .foundation.runtime import inspect
            view=inspect(self.session)
            card('Foundation curriculum',view['curriculum']);card('Evidence-linked knowledge',view['knowledge'][:8])
            return 'The foundation has six supplied operator stages. Use /foundation for program execution, ingestion and checked abstraction learning. Supplied operators are not learned discoveries.','reply',False
        if k=='ingest':
            from .foundation.runtime import request
            result=request(self.session,dict(op='foundation_ingest',args=dict(source='conversation',text=v['text'])))['result']
            card('Attributed source text',dict(ref=result['ref'],sha256=result['sha256'],units=len(result['units'])))
            return 'I retained the text and its source. Recognized facts remain attributed assertions; conflicts are preserved, and this text cannot execute commands.','success',False
        if k=='hello':return 'Hello! I’m NEXUS Seed. Teach me a word or a small skill, explore a pattern, or move something in our object world. What shall we try?','reply',False
        if k=='help':return 'I can learn finite object meanings and small list programs from examples, check them separately, remember verified skills, and move objects on a 6×6 grid. Try “A dax means a red object” or “Teach you a skill from examples.” I don’t use an external language model.','reply',False
        if k=='save':return 'Save requested. The local revision receipt will confirm when it is safely stored.','reply',True
        if k in ('stop','resume'):
            self.session.request(dict(op=k));return ('Paused. Say “resume” when you’re ready.' if k=='stop' else 'Ready again. What would you like to do?'),'success',False
        if k=='world':card('Authored world',self.session.world);return 'Here is our 6×6 world. Tell me which object to move and where.','reply',False
        if k=='memory':
            entries=lib.view(self.session)['entries'];card('Remembered concepts and skills',entries)
            return ('I remember '+', '.join(f'{e["name"]} ({"verified" if e["active_revision"] else "still learning"})' for e in entries)+'.' if entries else 'No concepts or skills saved in this conversation yet. What would you like to teach me?'),'reply',False
        if k=='meaning':
            name=self.resolve_name(v['name'],ctx);entry=next((e for e in lib.view(self.session)['entries'] if e['name']==name),None)
            if not entry:return f'I don’t have a learned meaning for {name} yet. Say “I want to teach you a word.”','clarification',False
            if ctx['active_name']!=name:ctx['pending']=None
            ctx['active_name']=name;card('Stored meaning',dict(name=name,status=entry['status'],program=entry['program'],candidates=entry['candidates']))
            return f'{name} is {"verified on your separate authored check" if entry["active_revision"] else "still a proposal; it needs teaching or a separate check"}. The stored interpretation is shown below.','reply',False
        if k=='start':
            ctx.update(active_name=None,lab=v['lab'],pending=dict(kind='name',schema=v['schema']))
            return ('What word would you like to teach me?' if v['schema']=='predicate' else 'What shall we call this skill or pattern?'),'clarification',False
        if k=='name':
            ir_schema=ctx['pending']['schema'];lib.named(ctx['lab'],v['name'],ir_schema);ctx['active_name']=v['name'];ctx['pending']=dict(kind='examples',schema=ir_schema)
            card('Example format', '[3, 1, 2, 1] -> [1, 2, 1, 3]' if ir_schema=='list' else {'input':examples()[0],'output':True})
            return ('Describe its meaning, for example “A '+v['name']+' means a red object.” Or send labeled object examples.' if ir_schema=='predicate' else 'Show me input -> output examples. I’ll propose only a small, supported program, then ask for a separate check.'),'clarification',False
        if k=='definition':
            target=next((g for g in GRAMMAR if sorted(g.description.split(' and '))==sorted(v['definition'].split(' and '))),None)
            if target is None:
                if any(w in v['definition'] for w in ('reverse','sequence','bright','sort')):
                    from .master.runtime import MasterSeedArchitecture
                    out=MasterSeedArchitecture(self.session,self.brain).handle_dialogue_turn(f'"{v["name"]}" means {v["definition"]}')
                    card('Master cognitive trace',dict(exchange_kind=out['exchange_kind'],meta_operation=out['meta_decision']['selected_operation'],compute_tier=out['compute_tier']['tier_name'],verified=out['response']['verification_passed']))
                    return out['response']['text'],'clarification',False
                return 'I can use colors, shapes, sizes, “not”, and two properties joined by “and”. For example: “A dax means red and small.”','clarification',False
            lib.named('language',v['name'],'predicate');ctx.update(active_name=v['name'],lab='language',pending=dict(kind='examples',schema='predicate'))
            # Labels are consequences of the USER'S explicit definition, never
            # model-generated assessment answers. Checks still require the user.
            pool=list(GRAMMAR);rows=[]
            for _ in range(8):
                if len(pool)==1:break
                available=[x for x in examples() if ir.input_key('predicate',x) not in {ir.input_key('predicate',r['input']) for r in rows}]
                x=min(available,key=lambda x:sum(g.matches(x)==target.matches(x) for g in pool));answer=target.matches(x)
                rows.append(dict(input=x,output=answer));pool=[g for g in pool if g.matches(x)==answer]
            if not rows:rows=[dict(input=examples()[0],output=target.matches(examples()[0]))]
            return self.proposal(ctx,rows,card)
        if k in ('rows','label'):
            p=ctx['pending'];rows=v['rows'] if k=='rows' else [dict(input=p['input'],output=v['output'])]
            if p['kind'] in ('checks','check_label'):
                out=self.brain.request(dict(op='lab_check',name=ctx['active_name'],attempt=p['attempt'],checks=rows))['result'];ctx['pending']=None
                card('Separate check',dict(status=out['status'],revision=out['revision'],examples=rows))
                return (f'{ctx["active_name"]} passed your separate check and is now verified.' if out['status']=='accepted' else 'That check failed. I retained any earlier verified version. Add a new teaching example to make another proposal.'),('success' if out['status']=='accepted' else 'error'),False
            return self.proposal(ctx,rows,card,p.get('supersedes'))
        if k=='correct':
            ref=ctx['last_teaching']
            if not ref or ref not in s['teaching']:return 'Which example should I correct? No teaching example is active in this conversation.','clarification',False
            old=s['teaching'][ref];ctx.update(active_name=old['name'],lab=old['lab'],pending=dict(kind='correction',schema=old['schema'],supersedes=ref));card('Teaching batch to replace',old['examples'])
            return 'Send the corrected input/output batch. It will supersede this teaching evidence, not erase it. Any earlier verified version remains until a fresh check passes.','clarification',False
        if k=='run':
            name=self.resolve_name(v['name'],ctx);out=self.brain.request(dict(op='lab_run',lab=ctx['lab'],name=name,input=v['input']))['result']
            if ctx['active_name']!=name:ctx['pending']=None
            ctx['active_name']=name;card('Executed verified skill',dict(name=name,input=v['input'],output=out['output']))
            return f'{name} returned {json.dumps(out["output"])}.','success',False
        if k=='examples':
            p=ctx['pending']
            if p and 'input' in p:card('Your current question',p['input']);return 'Here is the example I’m waiting for. You supply its answer; I haven’t labeled it for you.','clarification',False
            card('Try an example', '[3, 1, 2, 1] -> [1, 2, 1, 3]' if ctx['lab']!='language' else examples()[:3]);return 'Here are example inputs. Supply their outputs or labels when teaching; they are not automatically added to memory.','reply',False
        if k in ('goal','object','move'):
            goalmap={'top-right corner':[5,0],'top right corner':[5,0],'top-left corner':[0,0],'top left corner':[0,0],'bottom-right corner':[5,5],'bottom right corner':[5,5],'bottom-left corner':[0,5],'bottom left corner':[0,5]}
            if k=='object':goal=ctx['pending']['goal'];reference=v['reference']
            elif k=='goal':
                goal=goalmap.get(v['goal']);reference=v['reference']
                if goal is None:
                    m=re.fullmatch(r'\[?([0-5])\s*,\s*([0-5])\]?',v['goal']);goal=[int(x) for x in m.groups()] if m else None
                if goal is None:return 'Choose a corner, or coordinates such as “move o1 to 4, 2”.','clarification',False
            else:goal=None;reference=v['reference']
            if reference in ('it','that','that object','this object'):
                reference=current(self.session.journal.snapshot()).last_object
                if not reference:return 'Which object do you mean? Use an ID such as o1.','clarification',False
            ids,issue=self.brain.resolve(reference)
            if issue or len(ids)!=1:
                card('Choose one object',[o for o in self.session.world if not ids or o['id'] in ids])
                if goal is not None:ctx['pending']=dict(kind='object',goal=goal)
                return 'Which object do you mean? Reply with its ID, such as o1. Nothing has moved.','clarification',False
            if goal is None:
                result=self.brain.request(dict(op='lab_command',text=f'move {ids[0]} {v["direction"]} {v["steps"]}'))['result']
            else:result=self.brain.request(dict(op='lab_goal',reference=ids[0],x=goal[0],y=goal[1]))['result']
            ctx['pending']=None;ctx['lab']='world';card('Actual world outcome',dict(result=result,world=self.session.world))
            return ('Moved '+ids[0]+'. The world card shows the actual result.' if result['status']=='acted' else 'No move was executed: '+result['text']),('success' if result['status'] in ('acted','already_at_goal') else 'error'),False
        if k=='clarify_examples':return 'Use input -> output, one example per line, or a JSON list of {"input": ..., "output": ...}. Ask “show examples” for a template.','clarification',False
        card('Try one of these supported commands',[
            'How are you?',
            '"Flip" means reverse the order of a sequence.',
            'Could you arrange these from smallest to largest? [4, 1, 3, 2]',
            'If A is north of B and B is north of C, where is A relative to C?',
            'Solve 3*x + 7 = 22',
            'Did we achieve learning to learn?',
        ])
        return 'I can’t do that yet. I support natural check-ins, taught object words, concept/skill definitions, relational & math reasoning, checked list programs, and 6×6 grid movement. Try one of the prompts below!','clarification',False
