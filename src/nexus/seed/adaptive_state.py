"""Session-owned small-block learning over frozen Seed representations.

Evidence and durable history remain in Session/E1 Journal. This file is not a
parallel replay/memory framework. No source generation, environment or evaluator
is available to the updater. All temporary question/edit fits are disposable.
"""
import copy
import json
import math
import torch
from nexus.evolution1.catalogue import digest
from .plasticity import PlasticityController,correction,context
from .adaptive_records import CHANNELS,validate_state




def reward_features(h,z,proprio):
    # Current posterior, observed state and candidate action; no next outcome.
    return torch.cat((h.detach().expand(9,-1),z.detach().expand(9,-1),
                      proprio.detach().expand(9,-1),torch.eye(9),torch.ones(9,1)),1)


def meaning_features(encoded,proprio,word):
    # Word identity is observable, not a teacher program/task id. Eight fixed
    # signed hash bits permit different words without access to their meaning.
    bits=torch.tensor([1. if int(c,16)%2 else -1. for c in digest(word)[:8]])
    return torch.cat((encoded.detach().reshape(32),proprio.detach().reshape(12),bits,torch.ones(1)))


class AdaptiveState:
    def __init__(self,controller=None):
        self.controller=controller if controller is not None else PlasticityController(62)
        if self.controller.width!=62:raise ValueError('runtime_controller_width')
        self.blocks={k:torch.zeros(n) for k,n in CHANNELS.items()}
        self.anchors={k:[] for k in CHANNELS};self.development={k:[] for k in CHANNELS}
        self.skills=[];self.seen=[];self.steps=0
        self.work=dict(actual_updates=0,question_hypotheses=0,structural_fits=0,linear_solves=0)

    def tensors(self,channel,rows=None):
        rows=self.anchors[channel] if rows is None else rows
        n=CHANNELS[channel]
        return (torch.tensor([r['x'] for r in rows]).reshape(-1,n),torch.tensor([r['y'] for r in rows]))

    def predict(self,channel,x,key=''):
        value=x@self.blocks[channel]
        for s in self.skills:
            if s['channel']==channel and s['key']==key:value=value+x@torch.tensor(s['theta'])
        return value

    def update(self,channel,x,y,ref,*,key=''):
        if channel not in CHANNELS or x.shape!=(CHANNELS[channel],) or not torch.isfinite(x).all() or not math.isfinite(y) or abs(y)>100 or type(ref) is not str or len(ref)!=64:
            raise ValueError('actual_lesson_schema')
        if ref in self.seen:raise ValueError('duplicate_actual_lesson')
        if self.steps>=24:return dict(status='lesson_cap',updated=False)
        self.seen.append(ref);self.steps+=1
        row=dict(x=x.detach().tolist(),y=float(y),ref=ref,key=key)
        # Every fourth lesson is a reserved development assessment, never used
        # in inner updates, anchors, hypothetical question scoring or repair fits.
        if self.steps%4==0:
            self.development[channel]=(self.development[channel]+[row])[-4:]
            return dict(status='reserved_development',updated=False)
        shared=self.blocks[channel]
        scoped=sum((torch.tensor(s['theta']) for s in self.skills if s['channel']==channel and s['key']==key),torch.zeros_like(shared))
        theta=shared+scoped;a,_=self.tensors(channel)
        before=float((x@theta-y).square())
        d=self.controller(context(theta,x,y,a,float(channel=='meaning')))[:len(theta)].detach()
        with torch.no_grad():new=correction(theta,x,y,a,d)
        self.blocks[channel]=(new-scoped).detach();self.anchors[channel]=(self.anchors[channel]+[row])[-8:]
        self.work['actual_updates']+=1;self.work['linear_solves']+=bool(len(a))
        return dict(status='learned_actual_feedback',updated=True,error_before=before,
                    error_after=float((x@new-y).square()),parameter_change=float((new-theta).norm()),channel=channel)

    def learn(self,channel,x,y,ref,*,key=''):
        """Actual-feedback cycle; at most three automatic edit reviews/session.

        Keep remains a valid outcome. Hypothetical answers never call this API.
        """
        before=self.steps;receipt=self.update(channel,x,y,ref,key=key)
        if self.steps>before and self.steps%8==0:
            receipt['automatic_structural_review']=self.review(channel,key)
        return receipt

    def expected_question(self,xs):
        """Equal .5 answer prior; evaluate remembered *observed* labels only.

        Hypothetical answers never reach update(), seen, journal or theta.
        This is a cheap training-memory proxy, not known future task utility.
        """
        a,y=self.tensors('meaning');theta=self.blocks['meaning'];scores=[]
        if not len(a):return 0,[0. for _ in xs]
        before=float((a@theta-y).square().mean())
        for x in xs:
            outcomes=[]
            for answer in (-.5,.5):
                d=self.controller(context(theta,x,answer,a,1.))[:len(theta)].detach()
                with torch.no_grad():temp=correction(theta,x,answer,a,d)
                outcomes.append(float((a@temp-y).square().mean()))
                self.work['question_hypotheses']+=1;self.work['linear_solves']+=1
            scores.append(before-sum(outcomes)/2)
        return max(range(len(xs)),key=lambda i:scores[i]),scores

    def review(self,channel,key):
        """Vetted edits: keep, repair shared block, add scoped residual, merge.

        Prefix learning curves use only support rows; reserved development rows
        score future-learning error. This is inspected development selection,
        never independent confirmation. Retention uses other-context anchors.
        """
        support=[r for r in self.anchors[channel] if r['key']==key]
        query=[r for r in self.development[channel] if r['key']==key]
        if len(support)<3 or len(query)<2:return dict(status='needs_separate_development',adopted='keep')
        n=CHANNELS[channel];theta=self.blocks[channel]
        sx,sy=self.tensors(channel,support);qx,qy=self.tensors(channel,query)
        old=[r for r in self.anchors[channel] if r['key']!=key];ox,oy=self.tensors(channel,old)
        current_scoped=sum((torch.tensor(s['theta']) for s in self.skills if s['channel']==channel and s['key']==key),torch.zeros(n))
        incumbent=theta+current_scoped
        keep=float((qx@incumbent-qy).square().mean())
        rows=[dict(edit='keep',score=-keep,query_error=keep,forgetting=0.,bytes_added=0,training_updates=0)]
        candidates={}
        for kind in ('repair','add_skill','merge'):
            if kind=='add_skill' and len(self.skills)>=2:continue
            if kind=='merge' and not torch.count_nonzero(current_scoped):continue
            t=incumbent.clone() if kind!='add_skill' else torch.zeros(n)
            curve=[];count=0
            for x,y in zip(sx,sy):
                residual=y-x@theta if kind=='add_skill' else y
                guard=ox if kind!='add_skill' else x.new_zeros((0,n))
                with torch.no_grad():t=correction(t,x,residual,guard,torch.ones(n))
                effective=theta+t if kind=='add_skill' else t
                curve.append(float((qx@effective-qy).square().mean()));count+=1
            effective=theta+t if kind=='add_skill' else t
            forgetting=max(0.,float((ox@effective-oy).square().mean()-(ox@theta-oy).square().mean())) if len(ox) and kind!='add_skill' else 0.
            # Fixed canonical encoding gives actual added storage, not a name.
            skill=dict(channel=channel,key=key,theta=t.tolist())
            storage=len(json.dumps(skill,sort_keys=True,separators=(',',':')).encode()) if kind=='add_skill' else 0
            error=float((qx@effective-qy).square().mean())
            score=-sum(curve)/len(curve)-.5*forgetting-.0001*count-.000001*storage
            rows.append(dict(edit=kind,score=score,query_error=error,forgetting=forgetting,bytes_added=storage,training_updates=count))
            candidates[kind]=(t,skill)
            self.work['structural_fits']+=count;self.work['linear_solves']+=count*bool(len(ox) and kind!='add_skill')
        winner=max(rows,key=lambda r:r['score'])
        # Keep is a real candidate; final query error must also improve by .01.
        if winner['edit']!='keep' and winner['query_error']<=keep-.01:
            kind=winner['edit'];t,skill=candidates[kind]
            if kind=='add_skill':
                self.skills=[s for s in self.skills if not(s['channel']==channel and s['key']==key)]+[skill]
            else:
                self.blocks[channel]=t
                self.skills=[s for s in self.skills if not(s['channel']==channel and s['key']==key)]
            adopted=kind
        else:adopted='keep'
        return dict(status='development_only_edit_check',adopted=adopted,candidates=rows)

    def snapshot(self):
        return dict(schema='seed_adaptive_state_v1',blocks={k:v.tolist() for k,v in self.blocks.items()},
                    anchors=copy.deepcopy(self.anchors),development=copy.deepcopy(self.development),
                    skills=copy.deepcopy(self.skills),seen=list(self.seen),steps=self.steps,work=dict(self.work))

    def restore(self,p):
        validate_state(p)
        self.blocks={k:torch.tensor(v) for k,v in p['blocks'].items()}
        for k in ('anchors','development','skills','seen','steps','work'):setattr(self,k,copy.deepcopy(p[k]))
