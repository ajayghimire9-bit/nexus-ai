"""Compact recurrent SYMBOLIC working state, derived from the existing journal.

No second memory database, learned recurrent weights, or new checkpoint schema.
"""
from dataclasses import dataclass, asdict
import json
import re


@dataclass(frozen=True)
class WorkingState:
    last_object: str | None = None
    last_concept: str | None = None
    source_event: str | None = None

    def advance(self, event):
        p=json.loads(event.payload_json)
        if event.kind=='seed_program':
            return WorkingState(p['trace'][-1]['object'],self.last_concept,event.fingerprint)
        if event.kind in ('seed_scene','seed_stop'):
            return WorkingState(None,self.last_concept,event.fingerprint)
        if event.kind in ('seed_teaching','seed_definition'):
            return WorkingState(None,p['word'],event.fingerprint)
        return self

    def payload(self):
        return dict(asdict(self),kind='symbolic_recurrent_state_not_neural_GRU')


def current(events):
    state=WorkingState()
    for event in events:
        state=state.advance(event)
    return state


def resolve_pronouns(text, state, taught_words):
    if type(text) is not str:
        return text,False
    words=re.findall(r'\b(?:it|that)\b',text.lower())
    unresolved=[w for w in words if w not in taught_words]
    if not unresolved:
        return text,False
    if state.last_object is None:
        return None,True
    out=text.lower()
    for word in set(unresolved):
        out=re.sub(r'\b'+word+r'\b',state.last_object,out)
    return out,True
