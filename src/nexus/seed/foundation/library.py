"""Source-only repeated-subprogram discovery with separate promotion checks.

Reuses existing list operators. A macro takes x, substitutes the same operator
sequence and cannot change its checks. Compression reduces stored/search tokens,
not underlying primitive execution cost. No generalization claim follows.
"""
from collections import defaultdict
from itertools import product
from nexus.evolution1.catalogue import digest
from .programs import pipeline, execute


def propose(programs):
    if type(programs) is not list or not 2<=len(programs)<=24: raise ValueError('source_program_count')
    seen=set();groups=defaultdict(set);source_instructions=0;windows=0
    for row in programs:
        if set(row)!={'task','ops','examples'} or type(row['task']) is not str or row['task'] in seen: raise ValueError('unique_source_task')
        seen.add(row['task']);pipeline(row['ops']);check_rows(row['examples'])
        for r in row['examples']:
            result=execute(pipeline(row['ops']),{'x':r['input']});source_instructions+=result['instructions']
            if result['value']!=r['output']: raise ValueError('source_program_failed')
        for n in range(2,min(5,len(row['ops']))+1):
            for i in range(len(row['ops'])-n+1):
                windows+=1;groups[tuple(row['ops'][i:i+n])].add(row['task'])
    proposals=[]
    for ops,tasks in groups.items():
        # Charge one macro definition plus one invocation per occurrence.
        occurrences=sum(count(row['ops'],ops) for row in programs)
        savings=occurrences*(len(ops)-1)-len(ops)
        if len(tasks)>=2 and savings>0:
            proposals.append(dict(id=digest(list(ops)),ops=list(ops),source_tasks=sorted(tasks),
                                  token_savings=savings,origin='source_subprogram_compression',
                                  shared_search_cost=dict(source_instructions=source_instructions,windows=windows)))
    return sorted(proposals,key=lambda p:(-p['token_savings'],p['id']))


def count(sequence,part):
    i=n=0
    while i<=len(sequence)-len(part):
        if tuple(sequence[i:i+len(part)])==tuple(part): n+=1;i+=len(part)
        else: i+=1
    return n


def run_ops(ops,x): return execute(pipeline(ops),{'x':x})['value']


def check_rows(rows):
    from nexus.seed.skill_programs import labeled
    labeled('list',rows)


def search(rows, candidate=None, cap=128):
    """Bounded example-directed synthesis over the EXISTING list primitives.

Each candidate receives identical labeled search examples. This is an authored
development search-cost check, not hidden-query performance. All failed calls
count. A returned solution is verified against every supplied example.
"""
    from nexus.seed.skill_programs import LIST_OPS
    from .programs import variable
    check_rows(rows)
    if type(cap) is not int or not 1<=cap<=128: raise ValueError('search_cap')
    operators=(('macro',) if candidate else ())+LIST_OPS
    tested=instructions=0
    functions={'macro':pipeline(candidate['ops'])} if candidate else {}
    for depth in range(4):
        for ops in product(operators,repeat=depth):
            if tested>=cap: return dict(status='incomplete',candidates=tested,instructions=instructions,solution=None)
            tree=variable()
            for op in ops:
                tree=dict(op='call',name='macro',value=tree) if op=='macro' else dict(op='skill',program=dict(schema='list',ops=[op]),value=tree)
            tested+=1;correct=True
            for row in rows:
                try:
                    out=execute(tree,{'x':row['input']},functions);instructions+=out['instructions']
                    if out['value']!=row['output']: correct=False;break
                except ValueError as error:
                    # Preserve the failed interpreter's count as well as the
                    # candidate attempt; rejected calls are not free work.
                    instructions+=getattr(error,'instructions',0);correct=False;break
            if correct: return dict(status='solved',candidates=tested,instructions=instructions,solution=list(ops))
    return dict(status='not_found',candidates=tested,instructions=instructions,solution=None)


def assess(candidate,source,checks):
    if candidate not in propose(source): raise ValueError('source_candidate_required')
    if type(checks) is not list or not 2<=len(checks)<=8: raise ValueError('separate_check_tasks')
    source_tasks={r['task'] for r in source};seen=set()
    used={digest(r['input']) for p in source for r in p['examples']}
    outcomes=[];search_checks=[]
    for task in checks:
        if set(task)!={'task','ops','examples'} or type(task['task']) is not str or task['task'] in source_tasks|seen: raise ValueError('disjoint_check_tasks')
        seen.add(task['task']);pipeline(task['ops']);check_rows(task['examples'])
        if not count(task['ops'],candidate['ops']): raise ValueError('macro_not_used_by_check')
        for row in task['examples']:
            key=digest(row['input'])
            if key in used: raise ValueError('fresh_check_inputs')
            used.add(key)
            # Execute a macro invocation through the SAME interpreter, not an
            # assumed-equivalent expanded path; assertions remain external.
            tree=compressed(task['ops'],candidate)
            out=execute(tree,{'x':row['input']},{'macro':pipeline(candidate['ops'])})
            outcomes.append(dict(task=task['task'],correct=out['value']==row['output'],instructions=out['instructions']))
        baseline=search(task['examples']);reuse=search(task['examples'],candidate)
        search_checks.append(dict(task=task['task'],without_library=baseline,with_library=reuse))
    cheaper=all(r['without_library']['status']=='solved' and r['with_library']['status']=='solved' and
                r['with_library']['instructions']<r['without_library']['instructions'] for r in search_checks)
    return dict(accepted=all(r['correct'] for r in outcomes) and cheaper,outcomes=outcomes,search_checks=search_checks,
                label='authored_separate_checks_not_scientific_transfer')


def compressed(ops,candidate):
    from .programs import variable
    tree=variable();i=0;part=candidate['ops']
    while i<len(ops):
        if ops[i:i+len(part)]==part: tree=dict(op='call',name='macro',value=tree);i+=len(part)
        else: tree=dict(op='skill',program=dict(schema='list',ops=[ops[i]]),value=tree);i+=1
    return tree
