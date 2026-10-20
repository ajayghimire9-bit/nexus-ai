"""Four lab interfaces over one existing Session, encoder and skill journal.

No training launcher, arbitrary code execution or scientific evaluation API.
The optional frozen SeedRSSM encoder ranks reusable, schema-compatible skills;
executable checkers remain authoritative. This is not proven neural grounding.
"""
from dataclasses import asdict
import copy
import json
import re
import time
from .core import Move,parse,MOVES
from . import skill_library as lib
from . import skill_programs as ir
from .planning import to_cell,compact,movement_reward
from .working import current,resolve_pronouns


class SharedBrain:
    def __init__(self,session,model=None,model_hash=None):
        self.session=session;self.model=model;self.model_hash=model_hash
        if (model is None)!=(model_hash is None):raise ValueError('shared_encoder_and_hash_pair')
        if model is not None:
            if type(model_hash) is not str or not re.fullmatch('[a-f0-9]{64}',model_hash) or model.training or any(p.requires_grad or p.device.type!='cpu' for p in model.parameters()):raise ValueError('owner_verified_frozen_encoder_required')

    def encode(self,schema,inputs):
        if self.model is None:return None
        import torch
        from .grounded_world import observation,tensors
        sensors=[]
        for x in inputs:
            ir.value(schema,x)
            if schema=='predicate':sensors.append(observation(x));continue
            chars=[ord(ch)%128 for ch in (schema+' '+json.dumps(x,separators=(',',':')))[:24]]
            chars += [0]*(24-len(chars));prop=[0.]*12
            if schema=='relation':
                a,b=x['first'],x['second'];prop[:6]=[a['x']/5,a['y']/5,b['x']/5,b['y']/5,float(a['color']==b['color']),float(a['shape']==b['shape'])]
            elif schema=='motion':prop[:2]=[x['x']/5,x['y']/5]
            else:prop[:min(12,len(x))]=[v/64 for v in x[:12]]
            sensors.append(dict(text=chars,pixels=[[0.]*27 for _ in range(36)],proprio=prop))
        with torch.no_grad():return self.model.encode(*tensors(sensors)).detach()

    def retrieve(self,schema,x):
        s=lib.state(self.session);items=[(name,p) for name,(_,p) in s['active'].items() if p['program']['schema']==schema]
        if not items:return []
        if self.model is None:return sorted(name for name,_ in items)
        import torch
        names=[];prototypes=[]
        for name,p in items:
            origin=s['teaching'][p['attempt']]
            if origin['model_hash']==self.model_hash and origin['prototype'] is not None:
                names.append(name);prototypes.append(origin['prototype'])
        if not names:return sorted(name for name,_ in items)
        with torch.no_grad():_,weights=self.model.retrieve(self.encode(schema,[x]),torch.tensor(prototypes,dtype=torch.float32))
        ranked=sorted(zip(names,weights[0].tolist()),key=lambda v:(-v[1],v[0]))
        return [name for name,_ in ranked]+sorted(name for name,_ in items if name not in names)

    def inspect(self):
        return dict(shared_library=lib.view(self.session),world=copy.deepcopy(self.session.world),
            working_memory=current(self.session.journal.snapshot()).payload(),
            architecture=dict(shared_representation='existing_frozen_SeedRSSM_GRU32' if self.model else 'symbolic_only_optional_encoder_disabled',
                encoder_hash=self.model_hash,neural_cross_domain_usefulness='untested',memory='existing_Session_E1_Journal',
                encoder_parameters=(sum(p.numel() for m in (self.model.text,self.model.pixels,self.model.proprio,self.model.encoder) for p in m.parameters())+self.model.modality.numel()) if self.model else 0,
                frozen_core_parameters=sum(p.numel() for p in self.model.parameters()) if self.model else 0,
                rule_selection='existing_epsilon_greedy_sample_means',skills='typed_finite_programs_with_fresh_authored_checks',
                planning='existing_known_grid_reference_not_neural_MPC',learning_to_learn_demonstrated=False),
            costs=dict(self.session.counts),scientific=False)

    def resolve(self,reference):
        return self.session.resolve(reference)

    def execute_world(self,program):
        if self.session.grounded_agent is not None:raise ValueError('use_shared_encoder_workspace_without_neural_action_controller')
        if not program:return dict(type='already_at_goal',text='Already at goal; no action or reward.',trace=[])
        return self.session.execute(program)

    def request(self,p):
        start=time.perf_counter();s=self.session;before=dict(s.counts);neural=dict(self.model.work) if self.model else {}
        fields={'lab_inspect':{'op'},'lab_ask':{'op','name'},
            'lab_teach':{'op','lab','name','schema','examples','mode','supersedes'},
            'lab_check':{'op','name','attempt','checks'},'lab_rollback':{'op','name','target'},
            'lab_run':{'op','lab','name','input'},'lab_command':{'op','text'},
            'lab_goal':{'op','reference','x','y'},'lab_world_skill':{'op','name','reference'}}
        if type(p) is not dict or p.get('op') not in fields or set(p)!=fields[p['op']]:raise ValueError('typed_shared_lab_request')
        op=p['op'];s._deadline=time.monotonic()+2
        if op not in ('lab_inspect','lab_ask'):s.check()
        if op in ('lab_command','lab_goal','lab_world_skill') and s.grounded_agent is not None:raise ValueError('use_shared_encoder_workspace_without_neural_action_controller')
        if s.stopped and op not in ('lab_inspect','lab_ask'):raise ValueError('resume_session_before_learning_or_acting')
        if op=='lab_inspect':result=dict(status='inspection',text='Four authored labs; one shared skill journal.')
        elif op=='lab_ask':
            entry=next((r for r in lib.view(s)['entries'] if r['name']==p['name']),None)
            if entry is None:raise ValueError('teach_a_skill_first')
            result=dict(status='ask' if entry['question'] is not None else 'no_distinguishing_example',input=entry['question'],text='Supply the correct output; NEXUS has not seen this answer.')
        elif op=='lab_teach':
            ir.labeled(p['schema'],p['examples']);kwargs={k:p[k] for k in ('lab','name','schema','examples','mode','supersedes')}
            # Validate the complete request BEFORE any optional neural inference.
            lib.teaching_payload(s,**kwargs)
            encoded=self.encode(p['schema'],[r['input'] for r in p['examples']]);prototype=encoded.mean(0).tolist() if encoded is not None else None
            order=self.retrieve(p['schema'],p['examples'][0]['input'])
            ref,record=lib.teach(s,**kwargs,prototype=prototype,model_hash=self.model_hash if prototype is not None else None,retrieval_order=order)
            result=dict(status='retain' if not record['candidates'] else 'ask' if len(record['candidates'])>1 else 'proposed',attempt=ref,
                candidate_count=len(record['candidates']),rule=record['rule'],feedback=record['feedback'],text='Evidence saved; existing verified skill remains until fresh checks pass.')
        elif op=='lab_check':
            ref,record=lib.assess(s,**{k:p[k] for k in ('name','attempt','checks')})
            result=dict(status='accepted' if record['accepted'] else 'rejected',revision=ref,text='Authored development check; no confirmation or learning-to-learn claim.')
        elif op=='lab_rollback':
            record=lib.rollback_payload(s,p['name'],p['target']);ref=s.event('seed_shared_rollback',record)
            result=dict(status='rolled_back',revision=ref,text='Restored a compatible tested revision; evidence retained.')
        elif op=='lab_run':
            state=lib.state(s);active=state['active'].get(p['name'])
            if p['lab'] not in lib.LABS or active is None:raise ValueError('verified_shared_skill_required')
            prog=active[1]['program'];ir.value(prog['schema'],p['input'])
            result=dict(status='predicted',output=ir.run(prog,p['input']),skill_id=active[0],program=prog,
                retrieval=self.retrieve(prog['schema'],p['input']),text='Executed a checked typed program; no host code or tool calls.')
            s.charge('program_evaluations',1)
        elif op=='lab_command':
            text,unresolved=resolve_pronouns(p['text'],current(s.journal.snapshot()),set(lib.state(s)['latest']))
            program=parse(text) if text is not None else None
            if type(program) is not tuple:raise ValueError('use_bounded_move_then_grammar_and_taught_references')
            compiled=[]
            for m in program:
                ids,issue=self.resolve(m.reference)
                if issue or len(ids)!=1:raise ValueError('clarify_reference_no_actions_executed')
                compiled.append(Move(ids[0],m.direction,m.steps))
            out=self.execute_world(tuple(compiled));result=dict(status=out['type'],text=out['text'],trace=out['trace'])
        elif op=='lab_world_skill':
            active=lib.state(s)['active'].get(p['name']);ids,issue=self.resolve(p['reference'])
            if not active or active[1]['program']['schema']!='motion' or issue or len(ids)!=1:raise ValueError('verified_motion_skill_and_unambiguous_reference')
            obj=next(o for o in s.world if o['id']==ids[0]);ir.run(active[1]['program'],dict(x=obj['x'],y=obj['y']))
            out=self.execute_world(ir.moves(active[1]['program'],ids[0]));result=dict(status=out['type'],text=out['text'],trace=out['trace'])
        else:
            ids,issue=self.resolve(p['reference'])
            if issue or len(ids)!=1:raise ValueError('clarify_reference_no_actions_executed')
            obj=next(o for o in s.world if o['id']==ids[0]);goal=(p['x'],p['y']);program,cost=to_cell(obj,*goal,s.check)
            out=self.execute_world(compact(program));reward=0.
            if out['type']=='acted':
                for row in out['trace']:
                    x,y=row['before'];dx,dy=MOVES[row['direction']]
                    for _ in range(row['steps']):
                        before_distance=abs(x-goal[0])+abs(y-goal[1]);x+=dx;y+=dy;after=abs(x-goal[0])+abs(y-goal[1])
                        reward+=movement_reward(before_distance,after,after==0)
            result=dict(status=out['type'],trace=out['trace'],reward=reward,goal=list(goal),symbolic_search=cost,text='Known-grid reference planning and existing authored reward; not neural control evidence.')
        return dict(response_type=result['status'],text=result['text'],result=result,state=self.inspect(),
            resources=dict(wall_ms=(time.perf_counter()-start)*1000,neural_work={k:self.model.work[k]-v for k,v in neural.items()} if self.model else {},
                **{k:s.counts[k]-v for k,v in before.items()}))
