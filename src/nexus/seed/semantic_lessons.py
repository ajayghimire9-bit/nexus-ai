"""Opt-in finite unary/relational lessons and typed instruction composition.

Syntax/primitives are supplied,not learned universal language. The existing
Predicate/Move checker is retained. Query meanings never enter feature creation.
"""
from dataclasses import dataclass
import random
import re
import torch
from .core import GRAMMAR,Move,examples
from .adaptive_state import meaning_features
from .grounded_world import observation,tensors
from .plasticity import correction,context


@dataclass(frozen=True)
class Relation:
    name:str

    def matches(self,pair):
        a,b=pair
        return {'left_of':a['x']<b['x'],'right_of':a['x']>b['x'],
                'above':a['y']<b['y'],'below':a['y']>b['y'],
                'same_color':a['color']==b['color'],'same_shape':a['shape']==b['shape']}[self.name]


RELATIONS=tuple(Relation(n) for n in ('left_of','right_of','above','below','same_color','same_shape'))


def input_features(model,obj,word,partner=None):
    with torch.no_grad():
        sensor=tensors([observation(obj)]);encoded=model.encode(*sensor)
        prop=sensor[2].clone()
        if partner is not None:
            # Observable geometry/attributes only,not a target predicate index.
            prop[0]=torch.tensor([obj['x']/5,obj['y']/5,partner['x']/5,partner['y']/5,
                (obj['x']-partner['x'])/5,(obj['y']-partner['y'])/5,
                float(obj['color']==partner['color']),float(obj['shape']==partner['shape']),
                float(obj['size']==partner['size']),0.,0.,1.])
        return meaning_features(encoded,prop,word)


def task(model,seed,kind,index):
    rng=random.Random(seed);word='v'+str(seed);pool=list(examples());rng.shuffle(pool)
    if kind=='unary':
        target=GRAMMAR[index%len(GRAMMAR)];catalogue=GRAMMAR
        support=pool[:8];query=pool[8:]
        def features(o):return input_features(model,o,word)
    else:
        target=RELATIONS[index%len(RELATIONS)];catalogue=RELATIONS
        pairs=[]
        for i in range(18):
            a=dict(rng.choice(pool),x=rng.randrange(6),y=rng.randrange(6));b=dict(rng.choice(pool),x=rng.randrange(6),y=rng.randrange(6));pairs.append((a,b))
        support=pairs[:8];query=pairs[8:]
        def features(o):return input_features(model,o[0],word,o[1])
    sx=torch.stack([features(o) for o in support]);qx=torch.stack([features(o) for o in query])
    # These labels are evaluator/teacher data. Fit functions receive support only.
    sy=torch.tensor([float(target.matches(o))-.5 for o in support]);qy=[target.matches(o) for o in query]
    return dict(seed=seed,kind=kind,word=word,sx=sx,sy=sy,qx=qx,qy=qy,
        support=support,query=query,catalogue=catalogue,target=target)


def fit(sx,sy,controller,k,method):
    from .learning_benchmark import update
    theta=torch.zeros(sx.shape[1]);scale=sx[:k].square().mean(0).sqrt().clamp(min=.01)*sx.shape[1]**.5
    x=sx[:k]/scale
    for i,(row,label) in enumerate(zip(x,sy[:k])):
        anchor=x[max(0,i-8):i];ay=sy[max(0,i-8):i]
        with torch.no_grad():theta=update(theta,row,label,anchor,ay,x[:i+1],sy[:i+1],controller,method,channel=1.)
    return theta,scale


def evaluate(lesson,controller):
    rows=[]
    for k in (1,2,4,8):
        methods={}
        for method in ('learned','fixed','replay','none'):
            theta,scale=fit(lesson['sx'],lesson['sy'],controller,k,method)
            predictions=((lesson['qx']/scale)@theta>0).tolist()
            methods[method]=dict(correct=sum(p==q for p,q in zip(predictions,lesson['qy'])),total=len(predictions),abstentions=0,
                inner_updates=0 if method=='none' else k)
        survivors=[];checks=0
        for p in lesson['catalogue']:
            good=True
            for x,y in zip(lesson['support'][:k],lesson['sy'][:k]):
                checks+=1
                if p.matches(x)!=(float(y)>0):good=False;break
            if good:survivors.append(p)
        correct=0;abstain=0
        for x,y in zip(lesson['query'],lesson['qy']):
            answers={p.matches(x) for p in survivors};checks+=len(survivors)
            if len(answers)!=1:abstain+=1
            else:correct+=answers.pop()==y
        methods['symbolic']=dict(correct=correct,total=len(lesson['query']),abstentions=abstain,predicate_checks=checks)
        rows.append(dict(budget=k,methods=methods))
    return dict(seed=lesson['seed'],kind=lesson['kind'],word=lesson['word'],target=lesson['target'].description if lesson['kind']=='unary' else lesson['target'].name,
        support_labels=(lesson['sy']>0).tolist(),support_inputs=lesson['support'],query_inputs=lesson['query'],query_labels=lesson['qy'],rows=rows)


def compose_instructions(text,lexicon):
    """Supplied bounded syntax; lexicon must contain learned verb bindings.

    Templates differ between teaching and assessment. Unknown forms abstain.
    No arbitrary Python,hidden target or neural-generated execution is accepted.
    """
    parts=text.lower().split(' then ')
    if not 1<=len(parts)<=3:return None
    result=[]
    for part in parts:
        m=re.fullmatch(r'(?:please )?([a-z]+) (?:the )?(o[0-9]+)',part)
        if not m or m[1] not in lexicon:return None
        direction=lexicon[m[1]]
        if direction not in ('left','right','up','down'):raise ValueError('typed_direction')
        result.append(Move(m[2],direction))
    return tuple(result)


def instruction_audit(model,controller,seed,demonstrations=None):
    rng=random.Random(seed);words=['dax','wug','zup','blick'];directions=['left','right','up','down'];rng.shuffle(directions)
    support=[];data=[]
    for word,direction in zip(words,directions):
        objects=examples();rng.shuffle(objects)
        dx,dy={'left':(-1,0),'right':(1,0),'up':(0,-1),'down':(0,1)}[direction]
        demo=dict(word=word,teaching_sentence=f'{word} o1',before=[2,2],after=[2+dx,2+dy],labels=8)
        if demonstrations is not None:
            demo=next(d for d in demonstrations if d['word']==word)
            dx=demo['after'][0]-demo['before'][0];dy=demo['after'][1]-demo['before'][1]
            direction={(-1,0):'left',(1,0):'right',(0,-1):'up',(0,1):'down'}[(dx,dy)]
        sx=torch.stack([input_features(model,dict(o,x=2,y=2),word) for o in objects[:8]])
        q=torch.stack([input_features(model,dict(o,x=3,y=3),word) for o in objects[8:]])
        data.append((word,direction,sx,q));support.append(demo)
    rows=[];truth=dict((w,d) for w,d,_,_ in data)
    for k in (1,2,4,8):
        neural={};symbolic={}
        for word,direction,sx,q in data:
            outputs=[]
            for candidate in ('left','right','up','down'):
                target=torch.tensor([.5 if candidate==direction else -.5]*8)
                theta,scale=fit(sx,target,controller,k,'learned')
                outputs.append(float(((q/scale)@theta).mean()))
            neural[word]=('left','right','up','down')[max(range(4),key=lambda i:outputs[i])]
            symbolic[word]=direction # exact primitive inferred from observed displacement
        for i in range(4):
            text=f'please {words[i]} the o2 then {words[(i+1)%4]} o3'
            expected=compose_instructions(text,truth)
            rows.append(dict(budget=k,sentence=text,neural_exact=compose_instructions(text,neural)==expected,symbolic_exact=compose_instructions(text,symbolic)==expected))
    return dict(seed=seed,support=support,rows=rows,teaching_examples=32,
        limitation='finite supplied syntax; isolated per-word linear heads; transductive unlabelled query observations; one unique displacement answer repeated over 8 objects/word,not arbitrary language understanding')
