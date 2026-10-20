"""Known-domain capability audits, not new program/language discovery."""
import random
import torch
from .core import GRAMMAR,Move,examples,parse
from .grounded_world import observation,tensors


def language_audit():
    rows=[]
    for direction,synonym in zip(('left','right','up','down'),('west','east','north','south')):
        for text in (f'move o1 {direction}',f'move the o1 {direction}',f'please move o1 {direction}',f'push o1 {synonym}',f'move o1 to the {direction}',f'shift o1 {direction}'):
            expected=(Move('o1',direction),);actual=parse(text)
            rows.append(dict(text=text,direction=direction,exact=actual==expected,supported=actual is not None))
    return dict(rows=rows,exact=sum(r['exact'] for r in rows),total=len(rows),
        neural_instruction_decoder='unavailable_trace_generator_is_not_an_instruction_parser')


def concept_audit(model,seed):
    rows=[];objects=examples()
    for i,target in enumerate(GRAMMAR):
        order=list(range(18));rng=random.Random(seed+i);rng.shuffle(order)
        support=[objects[j] for j in order[:8]];query=[objects[j] for j in order[-6:]]
        labels=[target.matches(o) for o in support]
        positive=[o for o,l in zip(support,labels) if l];negative=[o for o,l in zip(support,labels) if not l]
        neural=[]
        with torch.no_grad():
            if positive and negative:
                p=model.encode(*tensors([observation(o) for o in positive]));n=model.encode(*tensors([observation(o) for o in negative]))
                neural=model.propose(p,n).topk(8).indices.tolist()
        symbolic=list(range(len(GRAMMAR)));rng.shuffle(symbolic)
        conditions={}
        for name,candidates in [('neural',neural),('symbolic_equal_cap',symbolic[:8]),('symbolic_full_reference',symbolic)]:
            chosen=None;checks=0;tested=0
            for index in candidates:
                tested+=1;good=True
                for o,label in zip(support,labels):
                    checks+=1
                    if GRAMMAR[index].matches(o)!=label:good=False;break
                if good:chosen=index;break
            correct=0 if chosen is None else sum(GRAMMAR[chosen].matches(o)==target.matches(o) for o in query)
            conditions[name]=dict(chosen=chosen,query_correct=correct,query_total=6,predicate_checks=checks,candidates_tested=tested,abstained=chosen is None)
        rows.append(dict(task=i,support_indices=order[:8],query_indices=order[-6:],labels=labels,neural_proposals=neural,symbolic_order=symbolic,conditions=conditions))
    return rows
