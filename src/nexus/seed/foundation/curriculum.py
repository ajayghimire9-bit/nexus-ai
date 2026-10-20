"""Supplied operator curriculum; fixture completion is not generalization."""
from .programs import literal as L, variable as V, pipeline, execute


def lessons():
    return [
        dict(stage=1,name='identity_and_quantity',family='grounded',input={'items':[1,2,3]},
             program={'op':'count','value':V('items')},expected=3),
        dict(stage=2,name='left_instruction',family='instructions',input={'x':{'x':2,'y':2}},
             program={'op':'skill','program':{'schema':'motion','ops':['left']},'value':V()},expected={'x':1,'y':2}),
        dict(stage=3,name='ordered_events',family='reasoning',input={'events':['key','door']},
             program={'op':'before','events':V('events'),'first':L('key'),'second':L('door')},expected=True),
        dict(stage=4,name='bounded_algorithm',family='coding',input={'x':[3,1,3]},
             program=pipeline(['unique','sort']),expected=[1,3]),
        dict(stage=5,name='conditional_instruction',family='mixed',input={'x':{'x':2,'y':2},'clear':True},
             program={'op':'if','condition':V('clear'),'then':{'op':'skill','program':{'schema':'motion','ops':['left']},'value':V()},'else':V()},expected={'x':1,'y':2}),
        dict(stage=6,name='correction_and_uncertainty',family='interaction',input={'known':None},
             program={'op':'not','value':V('known')},expected=None),
    ]


def exercise(stage):
    if type(stage) is not int or not 1<=stage<=6: raise ValueError('curriculum_stage')
    row=lessons()[stage-1];result=execute(row['program'],row['input'])
    return dict(lesson=row,value=result['value'],passed=result['value']==row['expected'],
                instructions=result['instructions'],label='supplied_operator_exercise_not_learning_evidence')


def generate(history,seed,count=1):
    """Source-feedback scheduling over bounded generated executable exercises.

    Uses the existing meta-controller statistics. Templates/operators are
    supplied; automatic scheduling is not proven learning-rule improvement.
    """
    import random
    from nexus.meta.kind_statistics import kind_value,observe_kind
    from nexus.evolution1.catalogue import digest
    if type(seed) is not int or not 0<=seed<=1000000 or type(count) is not int or not 1<=count<=8:raise ValueError('bounded_curriculum_generation')
    sums={};counts={};families=('coding','reasoning','language','world');rng=random.Random(seed)
    for row in history:observe_kind(sums,counts,row['family'],row['reward'])
    result=[];scheduled=dict(counts)
    for i in range(count):
        unseen=[f for f in families if not scheduled.get(f)]
        family=unseen[0] if unseen else rng.choice(families) if rng.random()<.1 else min(families,key=lambda f:(kind_value(sums,counts,f),families.index(f)))
        scheduled[family]=scheduled.get(family,0)+1
        if family=='coding':
            inputs={'x':[rng.randint(0,9) for _ in range(5)]};program=pipeline(rng.choice([['unique','sort'],['increment','reverse'],['even','sort']]))
        elif family=='reasoning':
            events=['key','door','bell'];rng.shuffle(events);inputs={'events':events};program={'op':'before','events':V('events'),'first':L('key'),'second':L('door')}
        elif family=='language':
            inputs={'x':{'color':rng.choice(['red','blue']),'size':rng.choice(['small','large'])}};program={'op':'eq','left':{'op':'get','value':V(),'key':'color'},'right':L('red')}
        else:
            inputs={'x':{'x':rng.randint(1,4),'y':rng.randint(1,4)}};program={'op':'skill','program':{'schema':'motion','ops':[rng.choice(['left','right','up','down'])]},'value':V()}
        out=execute(program,inputs)
        task=dict(family=family,program=program,inputs=inputs,expected=out['value'],generation_instructions=out['instructions'],label='generated_source_exercise_not_hidden_assessment')
        task['id']=digest(dict(seed=seed,index=i,history=history,task=task));result.append(task)
    return result


PARAPHRASES={'go left':'left','move one position toward the west':'left','take one step to your left':'left',
            'go right':'right','go up':'up','go down':'down'}


def instruction(text):
    if type(text) is not str: raise ValueError('instruction_text')
    direction=PARAPHRASES.get(text.lower().strip(' .'))
    if direction is None: return dict(status='unknown_instruction')
    return dict(status='supplied_grammar',program={'op':'skill','program':{'schema':'motion','ops':[direction]},'value':V()})


def learning_curve(rows, methods, families, budgets=(1,2,4,8)):
    """Strict accounting of provided outcomes; does not manufacture experiments."""
    import math
    if not methods or not families or not budgets or len(methods)!=len(set(methods)) or len(families)!=len(set(families)) or len(budgets)!=len(set(budgets)): raise ValueError('locked_nonempty_unique_grid')
    expected={(m,f,b) for m in methods for f in families for b in budgets};seen=set()
    for r in rows:
        if set(r)!={'method','family','examples','success','questions','instructions','stored_nodes','retention'}: raise ValueError('learning_curve_fields')
        key=(r['method'],r['family'],r['examples'])
        if type(r['examples']) is not int or key not in expected or key in seen: raise ValueError('learning_curve_grid')
        seen.add(key)
        for name in ('success','retention'):
            if type(r[name]) not in (int,float) or not math.isfinite(r[name]) or not 0<=r[name]<=1: raise ValueError('finite_rate')
        for name in ('questions','instructions','stored_nodes'):
            if type(r[name]) is not int or r[name]<0: raise ValueError('actual_cost_count')
    if seen!=expected: raise ValueError('incomplete_learning_curve')
    return [dict(method=m,examples=b,success=sum(r['success'] for r in rows if r['method']==m and r['examples']==b)/len(families),
                 questions=sum(r['questions'] for r in rows if r['method']==m and r['examples']==b),
                 instructions=sum(r['instructions'] for r in rows if r['method']==m and r['examples']==b),
                 stored_nodes=sum(r['stored_nodes'] for r in rows if r['method']==m and r['examples']==b),
                 retention=sum(r['retention'] for r in rows if r['method']==m and r['examples']==b)/len(families)) for m in methods for b in budgets]
