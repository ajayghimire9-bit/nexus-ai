"""One authored development comparison, not a hidden scientific evaluator.

Teacher target is held by the caller; the learner receives objects and charged
boolean labels only. Oracle is explicitly privileged. No user-session files.
"""
import random
import math
import time
from .core import GRAMMAR, Move, Predicate, Session, examples


def features(obj):
    return tuple(obj[k] for k in ('color','shape','size'))


def run_case(config, task, method, task_index, cost_guard=None):
    target = Predicate(tuple(tuple(a) for a in task['literals']))  # teacher side
    word = 'w'+''.join(random.Random(config['surface_seed']+task_index).choices('abcdefghijklmnopqrstuvwxyz', k=9))
    s = Session(); known = {}; labels = []; latency = []
    s.cost_guard=cost_guard
    s.charge('generated_examples', len(examples()))
    rng = random.Random(config['question_seed']+task_index)
    available = examples()
    for step in range(config['teacher_answer_budget']):
        begin=time.perf_counter()
        if method == 'disagreement_question':
            q=s.question(word)
            obj=q.get('object')
            if obj is None:
                # Still charge equal teacher opportunities; no free target hint.
                obj=available[step]
        else:
            obj=rng.choice(available);available.remove(obj)
        yes=target.matches(obj)  # only this label is passed into the learner
        s.teach(word,obj,yes);known[features(obj)]=yes
        labels.append(dict(object=obj,positive=yes,remaining_hypotheses=len(s.candidates(word))))
        latency.append((time.perf_counter()-begin)*1000)
    if method == 'oracle':
        s.definitions[word] = GRAMMAR.index(target)
    positives=[o for o in examples() if target.matches(o)]
    negatives=[o for o in examples() if not target.matches(o)]
    layouts=[];rows=[]
    lrng=random.Random(config['layout_seed']+task_index)
    for layout in range(config['query_layouts_per_task']):
        # One true referent, two distractors; layouts and command compositions
        # absent from teacher object cards. The semantic tasks are the split unit.
        objects=[lrng.choice(positives)]+lrng.sample(negatives,2)
        lrng.shuffle(objects)
        s.world=[dict(o,id=f'o{i+1}',x=2+layout,y=i) for i,o in enumerate(objects)]
        before=[dict(o) for o in s.world]
        s.charge('generated_examples', len(before))
        expected=[o['id'] for o in s.world if target.matches(o)]
        begin=time.perf_counter()
        if method == 'memorization':
            matches=[o['id'] for o in s.world if known.get(features(o)) is True]
            missing=any(features(o) not in known for o in s.world)
            if not missing and len(matches)==1:
                out=s.execute((Move(matches[0],'right'),)+( (Move(matches[0],'down'),) if layout else ()))
            else:
                s.charge('program_evaluations')
                out=dict(type='abstained',trace=[])
        else:
            program=(Move(word,'right'),)+( (Move(word,'down'),) if layout else ())
            out=s.execute(program)
        elapsed=(time.perf_counter()-begin)*1000;latency.append(elapsed)
        correct=out['type']=='acted' and all(t['object']==expected[0] for t in out['trace'])
        rows.append(dict(layout=layout,objects=before,expected=expected,
            command=f'move {word} right'+(f' then move {word} down' if layout else ''),
            response=out,correct=correct,wall_ms=elapsed))
        layouts.append(before)
    return dict(task_id=task['id'],method=method,word=word,labels=labels,queries=rows,
                final_hypotheses=[p.description for p in s.candidates(word)],
                costs=s.counts,latency_ms=latency,teacher_predicate_tests=config['teacher_answer_budget']+36+3*config['query_layouts_per_task'],
                privileged_definition_hints=1 if method=='oracle' else 0,
                teacher_target_exposure='oracle_only' if method=='oracle' else 'boolean_labels_only',
                learner_contains_target_field=any('target' in k for k in s.__dict__))


def validate(config, rows):
    expected={(t['id'],m) for t in config['semantic_tasks'] for m in config['methods']}
    keys=[(r['task_id'],r['method']) for r in rows]
    if len(keys)!=len(expected) or set(keys)!=expected:
        raise ValueError('complete_authored_grid_required')
    for row in rows:
        if len(row['labels'])!=config['teacher_answer_budget'] or len(row['queries'])!=config['query_layouts_per_task'] or row['learner_contains_target_field']:
            raise ValueError('complete_label_query_grid_required')
        if {q['layout'] for q in row['queries']}!=set(range(config['query_layouts_per_task'])) or any(type(q['correct']) is not bool for q in row['queries']):
            raise ValueError('query_schema')
        if any(type(v) is not int or v<0 for v in row['costs'].values()):
            raise ValueError('fixture_cost_schema')
        numbers=row['latency_ms']+[q['wall_ms'] for q in row['queries']]
        if not numbers or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in numbers):
            raise ValueError('finite_numeric_metrics_required')
        if row['costs']['teacher_answers']!=len(row['labels']) or any(type(e['positive']) is not bool for e in row['labels']):
            raise ValueError('charged_label_grid')
    totals={k:sum(r['costs'][k] for r in rows) for k in rows[0]['costs']}
    caps={'teacher_answers':'teacher_label_cap','candidate_evaluations':'candidate_evaluation_cap',
          'predicate_tests':'predicate_test_cap','sandbox_actions':'sandbox_action_cap'}
    if any(totals[k]>config[c] for k,c in caps.items()):
        raise ValueError('authored_comparison_cap')
    return dict(costs=totals,methods={m:dict(correct=sum(q['correct'] for r in rows if r['method']==m for q in r['queries']),
        queries=sum(len(r['queries']) for r in rows if r['method']==m),
        ambiguous=sum(q['response']['type']!='acted' for r in rows if r['method']==m for q in r['queries']),
        remaining_hypotheses=[len(r['final_hypotheses']) for r in rows if r['method']==m]) for m in config['methods']})
