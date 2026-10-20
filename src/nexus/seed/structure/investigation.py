"""Bounded source-trace decision-tree compression, not a hand-authored learned law.

Probe indices identify permitted observable predicates. Training traces are the
only learning input. A caller supplies real answers through the normal sensor
interface; every answer incurs one probe charge, including rejected branches.
"""
from collections import Counter
import math


def entropy(labels):
    counts = Counter(labels); n = len(labels)
    return -sum(v/n*math.log2(v/n) for v in counts.values()) if n else 0.


def learn(traces, *, max_depth=3, max_nodes=15):
    if type(max_depth) is not int or not 0 <= max_depth <= 3 or type(max_nodes) is not int or not 1 <= max_nodes <= 15: raise ValueError('investigation_growth_cap')
    if not 2 <= len(traces) <= 128: raise ValueError('source_trace_cap')
    width = len(traces[0]['answers'])
    if not 1 <= width <= 16: raise ValueError('probe_cap')
    for row in traces:
        if set(row) != {'role', 'episode', 'answers', 'hypothesis'} or row['role'] != 'source' or len(row['answers']) != width or any(type(a) is not bool for a in row['answers']) or type(row['hypothesis']) is not int or not 0 <= row['hypothesis'] <= 15: raise ValueError('source_trace_only')
    if len({r['episode'] for r in traces}) != len(traces): raise ValueError('independent_source_traces')
    used = 0
    def build(rows, available, depth, budget):
        nonlocal used
        used += 1
        counts = Counter(r['hypothesis'] for r in rows)
        if len(counts) == 1: return dict(op='stop', hypothesis=min(counts), support=len(rows))
        if depth >= max_depth or budget < 3 or not available: return dict(op='abandon', support=len(rows))
        scores = []
        for i in available:
            groups = [[r for r in rows if r['answers'][i] is b] for b in (False, True)]
            gain = entropy([r['hypothesis'] for r in rows])-sum(len(g)/len(rows)*entropy([r['hypothesis'] for r in g]) for g in groups)
            scores.append((gain, -i, groups))
        gain, minus_i, groups = max(scores, key=lambda s:(s[0], s[1]))
        if gain <= 1e-12: return dict(op='abandon', support=len(rows))
        i = -minus_i
        budgets=[(budget-1)//2,budget-1-(budget-1)//2]
        return dict(op='probe', index=i, branches=[build(g, [j for j in available if j != i], depth+1,b) if g else dict(op='abandon', support=0) for g,b in zip(groups,budgets)])
    tree = build(traces, list(range(width)), 0,max_nodes)
    return dict(origin='source_trace_compression', tree=tree, probe_count=width, max_depth=max_depth,
                source_episodes=sorted(r['episode'] for r in traces), nodes=used)


def run(program, observe_probe, *, budget=3):
    if type(budget) is not int or not 0 <= budget <= 4: raise ValueError('probe_budget')
    tree = program['tree']; transcript = []
    for _ in range(min(budget, program['max_depth'])):
        if tree['op'] != 'probe': break
        answer = observe_probe(tree['index'])
        if type(answer) is not bool: raise ValueError('observed_boolean_answer')
        transcript.append(dict(probe=tree['index'], answer=answer, real=True))
        tree = tree['branches'][int(answer)]
    return dict(status=tree['op'] if tree['op'] != 'probe' else 'budget_stop',
                hypothesis=tree.get('hypothesis'), transcript=transcript, real_probes=len(transcript))


def fixed(width):
    """Baseline order, explicitly supplied; no learned classification leaves."""
    return dict(origin='supplied', probe_order=list(range(min(width, 3))))
