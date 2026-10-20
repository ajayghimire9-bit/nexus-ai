"""Connected Seed runtime: observe, recall, imagine, act, ask, induce, speak.

Core weights are frozen. Owner-enabled small adapters learn actual feedback.
Existing Session/Journal own evidence and all adaptation snapshots.
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
from .state_contract import Belief,world_memory


class GroundedAgent:
    def __init__(self,model,model_hash,action_readout=None,adaptive=None,controller_hash=None,surprise_gate=None):
        self.model=model;self.model_hash=model_hash
        self.h,self.z=model.initial();self.context=None;self.flags=[0,0,0]
        self._belief=Belief(model)
        self.outer=OuterSeedMeta()
        self.pending_question=None
        self.action_readout=action_readout
        self.adaptive=adaptive;self.controller_hash=controller_hash
        self.surprise_gate=surprise_gate
        if action_readout is not None and action_readout.parent_hash!=model_hash:raise ValueError('readout_parent_hash')

    def restore_state(self,session):
        if self.surprise_gate is not None:
            self.surprise_gate.seen.update(json.loads(e.payload_json)['actual_ref'] for e in session.journal.snapshot() if e.kind=='seed_surprise')
        if self.adaptive is not None:
            for event in reversed(session.journal.snapshot()):
                if event.kind=='seed_adaptive_state':
                    p=json.loads(event.payload_json)
                    if p['model_hash']==self.model_hash and p['controller_hash']==self.controller_hash:self.adaptive.restore(p['state'])
                    break
        for event in reversed(session.journal.snapshot()):
            if event.kind=='seed_grounded_state':
                p=json.loads(event.payload_json)
                if p['model_hash']==self.model_hash and p['context']['world']==digest(session.world):
                    self.h=torch.tensor([p['h']]);self.z=torch.tensor([p['z']]);self.context=p['context'];self.flags=list(p['flags'])
                    self._belief.h=self.h;self._belief.z=self.z;self._belief.token=0
                break

    def teaching_observed(self,session,word,obj,positive,supersedes,ref):
        if self.adaptive is not None and supersedes is not None:
            # Previously learned labels cannot remain trusted anchors after a
            # correction. Conservative invalidation avoids free replay training.
            self.adaptive.blocks['meaning'].zero_()
            self.adaptive.anchors['meaning']=[];self.adaptive.development['meaning']=[]
            self.adaptive.skills=[s for s in self.adaptive.skills if s['channel']!='meaning']
            self.adaptive.reviews={};self.adaptive.undo=[]
            self.save_adaptive(session,ref,dict(status='meaning_invalidated_after_correction',updated=False))
        if self.adaptive is not None and supersedes is None:
            from .adaptive_state import meaning_features
            with torch.no_grad():
                sensors=tensors([observation(obj)])
                x=meaning_features(self.model.encode(*sensors),sensors[2],word)
                receipt=self.adaptive.learn('meaning',x,float(positive)-.5,ref,key=word)
            self.save_adaptive(session,ref,receipt)
        p=self.pending_question;self.pending_question=None
        if not p or supersedes is not None or p['word']!=word or p['object']!=obj:return
        after=len(session.candidates(word));before=p['before']
        gain=(before-after)/before if 0<after<=before else 0.
        session.event('seed_grounded_information',dict(label_ref=ref,information_gain=gain,
            task_reward=0.,mixed_reward=.05*gain))

    def save_adaptive(self,session,ref,receipt):
        session.event('seed_adaptive_state',dict(model_hash=self.model_hash,controller_hash=self.controller_hash,
                      source_ref=ref,state=self.adaptive.snapshot(),receipt=receipt))

    def adaptive_question(self,session,word):
        from .core import examples
        from .adaptive_state import meaning_features
        pool=session.candidates(word);candidates=[]
        seen={tuple(e['object'][k] for k in ('color','shape','size')) for e in session.evidence if e['word']==word}
        for obj in examples():
            session.check();session.charge('generated_examples')
            yes=sum(session.test(p,obj) for p in pool)
            if 0<yes<len(pool) and tuple(obj[k] for k in ('color','shape','size')) not in seen:candidates.append(obj)
            if len(candidates)==4:break
        if not candidates:return dict(status='no_distinguishing_example',text='No unseen example distinguishes current meanings.')
        xs=[]
        for obj in candidates:
            sensor=tensors([observation(obj)])
            xs.append(meaning_features(self.model.encode(*sensor),sensor[2],word))
        index,scores=self.adaptive.expected_question(xs);obj=candidates[index]
        return dict(status='question',word=word,object=obj,policy='expected_remembered_error_reduction',
                    expected_scores=scores,answer_prior=.5,estimated_not_observed=True,
                    text=f"Is this {obj['size']} {obj['color']} {obj['shape']} a {word}?")

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

    def assimilate(self,session,obj,goal,action=0,*,advance=False,belief=None,commit=True,flags=None):
        b=self._belief if belief is None else belief
        if not commit:b=b.clone()
        if b.token is None or advance or b.encoded is None:
            encoded=self.model.encode(*tensors([observation(obj,goal,self.flags if flags is None else flags)]))
            if b.token is None or advance:
                b.observe(encoded,torch.tensor([action]),0 if b.token is None else b.token+1)
            else:
                # Restore cached sensors without assimilating saved history twice.
                b.encoded=encoded;b.memory=world_memory(self.model,encoded)
        _,retrieval=self.memory(session,b.encoded)
        retrieval['world_conditioning']='fixed_source_bank' if self.model.world_memory_bank is not None else 'empty_bank'
        if commit:self.h,self.z=b.h,b.z
        return b,b.memory,retrieval

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
        if type(action) is not str or action not in ('induce','meta','observe','speak','decide','decide_unpruned','ranked_decide','adaptive_decide','adaptive_ask','adaptive_review','adaptive_review_reward','adaptive_rollback','ask','store','retrieve') or type(reference) is not str or not 1<=len(reference)<=24 or not concept_word(word):
            raise ValueError('grounded_request_schema')
        if action.startswith('adaptive_') and self.adaptive is None:raise ValueError('adaptation_not_enabled_by_owner')
        if action=='adaptive_rollback':
            result=self.adaptive.rollback()
            source=next((e.fingerprint for e in reversed(session.journal.snapshot()) if e.kind in ('seed_teaching','seed_grounded_state')),None)
            if source:self.save_adaptive(session,source,result)
            return dict(result,text='Checked structural rollback; evidence and spent work are preserved.')
        if action=='adaptive_review':
            result=self.adaptive.review('meaning',word)
            source=next((e.fingerprint for e in reversed(session.journal.snapshot()) if e.kind=='seed_teaching'),None)
            if source:self.save_adaptive(session,source,result)
            return dict(result,text='Bounded keep/repair/scoped-skill/merge check on reserved development lessons; not confirmation.')
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
        if action=='adaptive_review_reward':
            result=self.adaptive.review('reward',digest((ids[0],goal)))
            source=next((e.fingerprint for e in reversed(session.journal.snapshot()) if e.kind=='seed_grounded_state'),None)
            if source:self.save_adaptive(session,source,result)
            return dict(result,text='Development-only bounded reward-skill edit check; no world-model change.')
        context=dict(reference=ids[0],goal=list(goal),world=digest(session.world))
        changed=self.context is None or any(self.context.get(k)!=context[k] for k in context)
        readonly=action in ('observe','speak')
        belief=Belief(self.model) if changed else self._belief
        if changed and not readonly:
            self._belief=belief;self.h,self.z=belief.h,belief.z;self.flags=[0,0,0]
        with torch.no_grad():
            b,memory,retrieval=self.assimilate(session,obj,goal,belief=belief,commit=not readonly,flags=[0,0,0] if changed else self.flags)
            estimates=self.model.heads(b.h,b.z)
            if action=='observe':
                learned_meaning=None
                if self.adaptive is not None:
                    from .adaptive_state import meaning_features
                    sensors=tensors([observation(obj)])
                    mx=meaning_features(self.model.encode(*sensors),sensors[2],word)
                    learned_meaning=dict(word=word,raw_score=.5+float(self.adaptive.predict('meaning',mx,key=word)),
                        calibrated=False,execution_authorized=False)
                return dict(status='observed',text='Encoded authored text, rendered pixels and proprioception with one GRU.',
                    adaptive_meaning=learned_meaning,
                    h_norm=float(b.h.norm()),z_norm=float(b.z.norm()),retrieval=retrieval,state_advanced=False,
                    prediction={k:v[0].tolist() for k,v in estimates.items()},modalities=['text','18x18_authored_pixels','proprioception'])
            if action=='speak':
                candidate=self.model.generate(b.h,b.z,memory)
                return dict(status='language',text=f"Observed {ids[0]} at ({obj['x']}, {obj['y']}).",
                    generated_candidate=candidate,candidate_verified=False,
                    language_source='trained_local_decoder_candidate_plus_factual_template',retrieval=retrieval)
            if action not in ('decide','decide_unpruned','ranked_decide','adaptive_decide','adaptive_ask','ask','store','retrieve'):raise ValueError('grounded_action')
            if (obj['x'],obj['y'])==goal:
                self.context=dict(context,done=True)
                return dict(status='already_at_goal',text='Already at this goal. Choose a new goal; no reward was collected.')
            choice={'ask':4,'adaptive_ask':4,'store':5,'retrieve':6}.get(action)
            planning=None
            rx=None;base=None
            if self.adaptive is not None or self.surprise_gate is not None:
                from .adaptive_state import reward_features
                prop=tensors([observation(obj,goal,self.flags)])[2]
                rx=reward_features(self.h,self.z,prop)
                nh,nz,_,_=self.model.transition(self.h.expand(9,-1),self.z.expand(9,-1),torch.arange(9),memory.expand(9,-1))
                base=self.model.heads(nh,nz)['reward']
            if action=='adaptive_decide':
                scores=base+self.adaptive.predict('reward',rx,key=digest((ids[0],goal)))
                choice=int(scores.argmax());planning=dict(kind='adaptive_one_step_reward_not_MPC',scores=scores.tolist(),imagined_transitions=9)
            elif action=='ranked_decide':
                prop=tensors([observation(obj,goal,self.flags)])[2]
                choice,planning=self.action_readout.rank(self.model,self.h,self.z,prop,memory)
                session.event('seed_grounded_action_rank',dict(model_hash=self.model_hash,
                    readout_hash=self.action_readout.sha256,scores=planning['candidate_scores'],selected=choice))
            elif choice is None:choice,planning=plan(self.model,self.h,self.z,memory,seed=len(session.journal.snapshot()),prune=action!='decide_unpruned')
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
                result['question']=self.adaptive_question(session,word) if action=='adaptive_ask' else session.question(word);self.flags[0]=1
                if result['question'].get('object'):
                    self.pending_question=dict(word=word,object=result['question']['object'],before=len(session.candidates(word)))
            elif choice==5:
                result['concept']=self.induce(session,word);self.flags[1]=1
            else:self.flags[2]=1
            obj=next(o for o in session.world if o['id']==ids[0])
            after_distance=abs(obj['x']-x)+abs(obj['y']-y);done=after_distance==0
            # No predicted reward or hypothetical information gain is logged as
            # actual feedback. Human teaching information is settled separately.
            reward=.2*(before_distance-after_distance)-.02+(1. if done else 0.)
            _,memory,retrieval=self.assimilate(session,obj,goal,choice,advance=True)
            generated=self.model.generate(self.h,self.z,memory)
            blocked=move_blocked or (choice==5 and result['concept']['status']!='adopted_development') or (choice==6 and not retrieval['names']) or (choice==4 and not result['question'].get('object'))
            actual_text=trace_for(choice,done,blocked=blocked)
            source='trained_trace_decoder' if generated==actual_text else 'grounded_template_fallback'
            self.context=dict(reference=ids[0],goal=list(goal),world=digest(session.world),done=done)
            actual_ref=session.event('seed_grounded_state',dict(model_hash=self.model_hash,h=self.h[0].tolist(),z=self.z[0].tolist(),context=self.context,
                actual_action=choice,actual_reward=reward,done=done,flags=list(self.flags)))
            if self.adaptive is not None:
                receipt=self.adaptive.learn('reward',rx[choice],reward-float(base[choice]),actual_ref,key=digest((ids[0],goal)))
                self.save_adaptive(session,actual_ref,receipt);result['adaptation']=receipt
            if self.surprise_gate is not None:
                surprise=self.surprise_gate.observe(actual_reward=reward,predicted_reward=float(base[choice]),receipt_id=actual_ref,phase='actual_experience')
                session.event('seed_surprise',dict(actual_ref=actual_ref,model_hash=self.model_hash,**surprise))
                result['surprise']=surprise
            if done:
                from .grounded_meta import RECIPES
                # Only source/training receipt API is accepted by the adapter;
                # user-session episode return is not a research training grant.
                result['outer_available']=True
            return dict(status='acted',text=actual_text,generated_candidate=generated,language_source=source,
                action=ACTION_NAMES[choice],action_index=choice,actual_reward=reward,done=done,
                planning=planning,retrieval=retrieval,result=result,question=result.get('question'),
                runtime_ms=(time.perf_counter()-started)*1000)
