"""Answer-free symbolic question scoring plus the existing learned probe tree."""
from collections import Counter
import math
from nexus.seed import skill_programs as ir
from nexus.seed.structure.investigation import learn, run


def choose(candidates, pool, observed=()):
    if not 1<=len(candidates)<=128 or not 1<=len(pool)<=64: raise ValueError('question_search_cap')
    schemas={ir.program(p)['schema'] for p in candidates}
    if len(schemas)!=1: raise ValueError('same_question_schema')
    schema=next(iter(schemas));ranked=[]
    for index,row in enumerate(pool):
        if set(row)!={'input','cost','risk'}: raise ValueError('pre_answer_only_question')
        if any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) or row[k]<0 for k in ('cost','risk')): raise ValueError('question_cost_risk')
        if ir.input_key(schema,row['input']) in observed: continue
        try: groups=Counter(str(ir.run(p,row['input'])) for p in candidates)
        except ValueError: continue
        gain=-sum(n/len(candidates)*math.log2(n/len(candidates)) for n in groups.values())
        ranked.append(dict(index=index,input=row['input'],information_bits=gain,
                           score=gain-row['cost']-row['risk']))
    best=max(ranked,key=lambda r:(r['score'],-r['index'])) if ranked else None
    return dict(choice=best if best and best['score']>0 else None,ranking=ranked,
                rule='uniform_version_space_information_minus_declared_cost_and_risk',
                decision_gain='not_estimated',answers_accessed=0)
