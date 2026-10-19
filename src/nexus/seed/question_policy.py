"""Thin question-policy adapter over the EXISTING NEXUS controller.

No hidden evaluator or user-supplied scalar reward. Feedback is computed only
from a previously asked card and the subsequently revealed boolean label.
This demonstrates bookkeeping, not useful learning-to-learn.
"""
import json
import random

KINDS=('balanced','random')


def choose(events):
    # Optional dependency graph is imported only when meta mode is enabled.
    from nexus.meta.controller import EpsilonGreedyController
    c=EpsilonGreedyController(epsilon=.1)
    for e in events:
        if e.kind=='seed_question_feedback':
            p=json.loads(e.payload_json)
            c.update((),p['policy'],p['reduction'])
    unseen=[k for k in KINDS if c.kind_n.get(k,0)==0]
    rng=random.Random(events[-1].fingerprint if events else 'seed-question-v1')
    if unseen:
        selected=unseen[0]
    elif rng.random()<c.epsilon:
        selected=rng.choice(KINDS)
    else:
        selected=max(KINDS,key=lambda k:(c.predicted_kind_value((),k),-KINDS.index(k)))
    return selected,{k:dict(count=c.kind_n.get(k,0),mean=c.predicted_kind_value((),k)) for k in KINDS}


def pending(events):
    latest=None
    for e in events:
        if e.kind=='seed_question_choice':
            latest=json.loads(e.payload_json)
        elif e.kind in ('seed_teaching','seed_scene','seed_definition','seed_question_feedback'):
            latest=None
    return latest
