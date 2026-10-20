"""Source-only repeated-subprogram discovery with separate promotion checks.

Reuses existing list operators. A macro takes x, substitutes the same operator
sequence and cannot change its checks. Compression reduces stored/search tokens,
not underlying primitive execution cost. No generalization claim follows.
"""
from collections import defaultdict
from itertools import product
from nexus.evolution1.catalogue import digest
from .programs import pipeline, execute, FIELDS


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


def expression_children(tree):
    """Only typed expression children; literal records and skill data stay data."""
    if tree['op']=='literal':return []
    out=[]
    for v in tree.values():
        if type(v) is dict and v.get('op') in FIELDS:out.append(v)
        elif type(v) is list:out.extend(x for x in v if type(x) is dict and 'op' in x)
    return out


def expression_nodes(tree):return 1+sum(expression_nodes(x) for x in expression_children(tree))


def free_names(tree,bound=frozenset()):
    if tree['op']=='var':return {tree['name']}-bound
    if tree['op']=='literal':return set()
    if tree['op'] in ('let','map','some','every','repeat'):
        key={'let':'value','map':'items','some':'items','every':'items','repeat':'initial'}[tree['op']]
        return free_names(tree[key],bound)|free_names(tree['body'],bound|{tree['name']})
    return set().union(*(free_names(x,bound) for x in expression_children(tree)))


def expression_rows(rows,minimum=2):
    from .programs import validate,bounded
    if type(rows) is not list or not minimum<=len(rows)<=8:raise ValueError('bounded_expression_tasks')
    names=set()
    for row in rows:
        if type(row) is not dict or set(row)!={'task','program','examples'} or type(row['task']) is not str or not 1<=len(row['task'])<=64 or row['task'] in names:raise ValueError('unique_expression_tasks')
        names.add(row['task']);validate(row['program'])
        if expression_nodes(row['program'])>64:raise ValueError('expression_task_size')
        if type(row['examples']) is not list or not 1<=len(row['examples'])<=4:raise ValueError('expression_example_count')
        for e in row['examples']:
            if type(e) is not dict or set(e)!={'input','output'}:raise ValueError('expression_example_fields')
            bounded(e['input']);bounded(e['output'])


def expression_propose(rows):
    """Discover repeated typed subtrees, including conditions/maps/temporal code.

    Only x may be free; no unreviewed function dependency can enter a proposal.
    This extends the existing checked-library machinery, not a new store.
    """
    expression_rows(rows);groups={};instructions=0
    def visit(tree,task):
        if tree['op']=='call':raise ValueError('source_expression_no_unreviewed_calls')
        n=expression_nodes(tree)
        if n>=4 and free_names(tree)=={'x'}:
            key=digest(tree);entry=groups.setdefault(key,dict(program=tree,tasks=set(),occurrences=0,nodes=n));entry['tasks'].add(task);entry['occurrences']+=1
        for child in expression_children(tree):visit(child,task)
    for row in rows:
        for e in row['examples']:
            out=execute(row['program'],{'x':e['input']});instructions+=out['instructions']
            if digest(out['value'])!=digest(e['output']):raise ValueError('source_expression_failed')
        visit(row['program'],row['task'])
    result=[]
    for key,g in groups.items():
        savings=g['occurrences']*(g['nodes']-2)-g['nodes']
        if len(g['tasks'])>=2 and savings>0:
            result.append(dict(id=key,name='f_'+key[:12],program=g['program'],source_tasks=sorted(g['tasks']),occurrences=g['occurrences'],definition_nodes=g['nodes'],stored_node_savings=savings,source_instructions=instructions))
    return sorted(result,key=lambda x:(-x['stored_node_savings'],x['id']))[:16]


def expression_compress(tree,candidate):
    import copy
    from .programs import variable
    if digest(tree)==candidate['id']:return dict(op='call',name=candidate['name'],value=variable())
    out=copy.deepcopy(tree)
    if tree['op']=='literal':return out
    for key,v in tree.items():
        if type(v) is dict and 'op' in v:out[key]=expression_compress(v,candidate)
        elif type(v) is list:out[key]=[expression_compress(x,candidate) if type(x) is dict and 'op' in x else x for x in v]
    return out


def expression_assess(candidate,source,checks):
    expression_rows(checks)
    if candidate not in expression_propose(source):raise ValueError('source_expression_candidate_required')
    used_tasks={x['task'] for x in source};used_inputs={digest(e['input']) for x in source for e in x['examples']}
    outcomes=[];before=after=0
    for row in checks:
        if row['task'] in used_tasks:raise ValueError('disjoint_expression_checks')
        used_tasks.add(row['task']);compiled=expression_compress(row['program'],candidate)
        if compiled==row['program']:raise ValueError('check_must_exercise_expression')
        for e in row['examples']:
            key=digest(e['input'])
            if key in used_inputs:raise ValueError('fresh_expression_check_inputs')
            used_inputs.add(key)
            original=execute(row['program'],{'x':e['input']});reuse=execute(compiled,{'x':e['input']},{candidate['name']:candidate['program']})
            before+=original['instructions'];after+=reuse['instructions']
            outcomes.append(dict(task=row['task'],correct=digest(original['value'])==digest(reuse['value'])==digest(e['output']),original_instructions=original['instructions'],macro_instructions=reuse['instructions']))
    return dict(accepted=all(x['correct'] for x in outcomes),candidate=candidate,outcomes=outcomes,
        stored_node_savings=candidate['stored_node_savings'],original_instructions=before,macro_instructions=after,
        label='authored_separate_expression_checks_not_scientific_transfer')
