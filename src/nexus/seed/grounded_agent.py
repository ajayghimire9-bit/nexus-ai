"""Connected Seed runtime: observe, recall, imagine, act, ask, induce, speak.

All neural weights are frozen at runtime. Existing Session/Journal own evidence.
"""
import json
import math
import time
import torch
from nexus.evolution1.catalogue import digest
from nexus.world.seed_rssm import ACTION_NAMES
from .core import GRAMMAR,Move,concept_word
from .grounded_world import observation,tensors,trace_for
from .grounded_meta import program_truth,expression_for,OuterSeedMeta
from .latent_planner import plan


class GroundedAgent:
    def __init__(self,model,model_hash,action_readout=None):
        self.model=model;self.model_hash=model_hash
        self.h,self.z=model.initial();self.context=None;self.flags=[0,0,0]
        self.outer=OuterSeedMeta()
        self.pending_question=None
        self.action_readout=action_readout
        if action_readout is not None and action_readout.parent_hash!=model_hash:raise ValueError('readout_parent_hash')

    def restore_state(self,session):
        for event in reversed(session.journal.snapshot()):
            if event.kind=='seed_grounded_state':
                p=json.loads(event.payload_json)
                if p['model_hash']==self.model_hash and p['context']['world']==digest(session.world):
                    self.h=torch.tensor([p['h']]);self.z=torch.tensor([p['z']]);self.context=p['context'];self.flags=list(p['flags'])
                break

    def teaching_observed(self,session,word,obj,positive,supersedes,ref):
        p=self.pending_question;self.pending_question=None
        if not p or supersedes is not None or p['word']!=word or p['object']!=obj:return
        after=len(session.candidates(word));before=p['before']
        gain=(before-after)/before if 0<after<=before else 0.
        session.event('seed_grounded_information',dict(label_ref=ref,information_gain=gain,
            task_reward=0.,mixed_reward=.05*gain))

    def approved(self,session):
        latest={}
        for e in session.journal.snapshot():
            if e.kind=='seed_grounded_concept':
                p=json.loads(e.payload_json);latest[p['word']]=p
        return {w:p for w,p in latest.items() if p['evidence_hash']==digest([e for e in session.evidence if e['word']==w]) and p['model_hash']==self.model_hash}

    def resolve_concept(self,session,word):
        p=self.approved(session).get(word)
        if p is None:return None
        predicate=GRAMMAR[p['program_index']]
        result=[]
        for o in session.world:
            session.check();session.charge('predicate_tests')
            if program_truth(predicate,o):result.append(o['id'])
        return result

    def memory(self,session,encoded):
        records=self.approved(session)
        prototypes=torch.tensor([p['prototype'] for p in records.values()],dtype=torch.float32).reshape(-1,32)
        vector,weights=self.model.retrieve(encoded,prototypes)
        return vector,dict(names=list(records),weights=weights[0].tolist())

    def assimilate(self,session,obj,goal,action=0):
        encoded=self.model.encode(*tensors([observation(obj,goal,self.flags)]))
        memory,retrieval=self.memory(session,encoded)
        self.h,self.z,_=self.model.observe(self.h,self.z,torch.tensor([action]),encoded,memory,sample=False)
        return encoded,memory,retrieval

    def induce(self,session,word):
        # Current active labels only; old evidence stays in the existing Journal.
        evidence=[e for e in session.evidence if e['word']==word]
        superseded={e['supersedes'] for e in evidence if e['supersedes']}
        active=[e for e in evidence if e['ref'] not in superseded]
        unique={}
        for e in active:
            key=tuple(e['object'][k] for k in ('color','shape','size'))
            unique.setdefault(key,[]).append(e)
        clean=[]
        for group in unique.values():
            # Contradictory duplicates are not counted as independent evidence.
            if len({e['positive'] for e in group})==1:clean.append(group[0])
        pos=[e for e in clean if e['positive']];neg=[e for e in clean if not e['positive']]
        if len(clean)<8 or min(len(pos),len(neg))<2:
            return dict(status='needs_evidence',text='Need at least eight distinct property examples, with positive and negative development checks.')
        train=pos[:-1]+neg[:-2];validation=pos[-1:]+neg[-2:]
        if not train or not any(e['positive'] for e in train) or not any(not e['positive'] for e in train):
            return dict(status='needs_evidence',text='Need more distinct positive and negative training examples.')
        def encoded(group):return self.model.encode(*tensors([observation(e['object']) for e in group]))
        p=encoded([e for e in train if e['positive']]);n=encoded([e for e in train if not e['positive']])
        logits=self.model.propose(p,n);indices=logits.topk(8).indices.tolist()
        baseline=min(sum(e['positive'] for e in validation),sum(not e['positive'] for e in validation))/len(validation)
        scored=[]
        for i in indices:
            def wrong(e):
                session.check();session.charge('predicate_tests')
                return program_truth(GRAMMAR[i],e['object'])!=e['positive']
            # Version-space checks proposed programs; it does not enumerate them.
            if any(wrong(e) for e in train):continue
            error=sum(wrong(e) for e in validation)/len(validation)
            scored.append((error,i))
        if not scored:
            return dict(status='rejected',text='No neural proposal survived the training evidence checker.',candidates=[])
        error,i=min(scored)
        if error>=baseline or error>.2:
            return dict(status='rejected',text='Neural program proposals did not beat the constant development checker.',candidates=scored,baseline_error=baseline)
        payload=dict(word=word,program_index=i,expression_tree=expression_for(GRAMMAR[i]),
            prototype=p.mean(0).tolist(),validation_error=error,baseline_error=baseline,
            evidence_hash=digest(evidence),model_hash=self.model_hash,
            evidence_refs=[e['ref'] for e in validation],development_only=True)
        session.event('seed_grounded_concept',payload)
        return dict(status='adopted_development',text='Kept a neural-proposed program after the bounded development check.',program=GRAMMAR[i].description,record=payload)

    def request(self,session,action,reference,x,y,word):
        started=time.perf_counter()
        if type(action) is not str or action not in ('induce','meta','observe','speak','decide','ranked_decide','ask','store','retrieve') or type(reference) is not str or not 1<=len(reference)<=24 or not concept_word(word):
            raise ValueError('grounded_request_schema')
        if action=='ranked_decide' and self.action_readout is None:raise ValueError('action_readout_not_enabled_by_owner')
        if action=='induce':
            with torch.no_grad():result=self.induce(session,word)
            return result
        if action=='meta':
            if self.context is not None and self.context.get('done') is not True:
                return dict(status='blocked',text='Outer meta-control is available between episodes only.')
            recipe=self.outer.propose(in_episode=False,remaining_s=1,remaining_steps=1)
            return dict(status='proposal_only',text='Outer controller proposes a bounded recipe; it cannot authorize or execute training.',recipe=recipe.__dict__)
        ids,issue=session.resolve(reference)
        if issue or len(ids)!=1:return dict(status='clarification',text='Use one unambiguous object or taught concept.')
        if any(type(v) is not int or not 0<=v<6 for v in (x,y)):raise ValueError('grounded_goal_bounds')
        obj=next(o for o in session.world if o['id']==ids[0]);goal=(x,y)
        context=dict(reference=ids[0],goal=list(goal),world=digest(session.world))
        if self.context is None or any(self.context.get(k)!=context[k] for k in context):
            self.h,self.z=self.model.initial();self.flags=[0,0,0]
        with torch.no_grad():
            encoded,memory,retrieval=self.assimilate(session,obj,goal)
            estimates=self.model.heads(self.h,self.z)
            if action=='observe':
                self.context=dict(context,done=(obj['x'],obj['y'])==goal)
                return dict(status='observed',text='Encoded authored text, rendered pixels and proprioception with one GRU.',
                    h_norm=float(self.h.norm()),z_norm=float(self.z.norm()),retrieval=retrieval,
                    prediction={k:v[0].tolist() for k,v in estimates.items()},modalities=['text','18x18_authored_pixels','proprioception'])
            if action=='speak':
                candidate=self.model.generate(self.h,self.z,memory)
                return dict(status='language',text=f"Observed {ids[0]} at ({obj['x']}, {obj['y']}).",
                    generated_candidate=candidate,candidate_verified=False,
                    language_source='trained_local_decoder_candidate_plus_factual_template',retrieval=retrieval)
            if action not in ('decide','ranked_decide','ask','store','retrieve'):raise ValueError('grounded_action')
            if (obj['x'],obj['y'])==goal:
                self.context=dict(context,done=True)
                return dict(status='already_at_goal',text='Already at this goal. Choose a new goal; no reward was collected.')
            choice={'ask':4,'store':5,'retrieve':6}.get(action)
            planning=None
            if action=='ranked_decide':
                prop=tensors([observation(obj,goal,self.flags)])[2]
                choice,planning=self.action_readout.rank(self.model,self.h,self.z,prop,memory)
                session.event('seed_grounded_action_rank',dict(model_hash=self.model_hash,
                    readout_hash=self.action_readout.sha256,scores=planning['candidate_scores'],selected=choice))
            elif choice is None:choice,planning=plan(self.model,self.h,self.z,memory,seed=len(session.journal.snapshot()))
            before_distance=abs(obj['x']-x)+abs(obj['y']-y);trace=[];result={};move_blocked=False
            if choice<4 or choice>=7:
                names=[ACTION_NAMES[choice]] if choice<4 else (['right','down'] if choice==7 else ['left','up'])
                # Vetted macros use the same per-primitive boundary handling as
                # the collected authored world, while each Session call is atomic.
                executions=[]
                for name in names:
                    actual=session.execute((Move(ids[0],name),));executions.append(actual)
                    trace.extend(actual.get('trace',[]));move_blocked|=actual.get('type')=='blocked'
                result['execution']=executions
            elif choice==4:
                result['question']=session.question(word);self.flags[0]=1
                if result['question'].get('object'):
                    self.pending_question=dict(word=word,object=result['question']['object'],before=len(session.candidates(word)))
            elif choice==5:
                result['concept']=self.induce(session,word);self.flags[1]=int(result['concept']['status']=='adopted_development')
            else:self.flags[2]=int(bool(retrieval['names']))
            obj=next(o for o in session.world if o['id']==ids[0])
            after_distance=abs(obj['x']-x)+abs(obj['y']-y);done=after_distance==0
            # No predicted reward or hypothetical information gain is logged as
            # actual feedback. Human teaching information is settled separately.
            reward=.2*(before_distance-after_distance)-.02+(1. if done else 0.)
            encoded,memory,retrieval=self.assimilate(session,obj,goal,choice)
            generated=self.model.generate(self.h,self.z,memory)
            blocked=move_blocked or (choice==5 and not self.flags[1]) or (choice==6 and not self.flags[2]) or (choice==4 and not result['question'].get('object'))
            actual_text=trace_for(choice,done,blocked=blocked)
            source='trained_trace_decoder' if generated==actual_text else 'grounded_template_fallback'
            self.context=dict(reference=ids[0],goal=list(goal),world=digest(session.world),done=done)
            session.event('seed_grounded_state',dict(model_hash=self.model_hash,h=self.h[0].tolist(),z=self.z[0].tolist(),context=self.context,
                actual_action=choice,actual_reward=reward,done=done,flags=list(self.flags)))
            if done:
                from .grounded_meta import RECIPES
                # Only source/training receipt API is accepted by the adapter;
                # user-session episode return is not a research training grant.
                result['outer_available']=True
            return dict(status='acted',text=actual_text,generated_candidate=generated,language_source=source,
                action=ACTION_NAMES[choice],action_index=choice,actual_reward=reward,done=done,
                planning=planning,retrieval=retrieval,result=result,question=result.get('question'),
                runtime_ms=(time.perf_counter()-started)*1000)
