"""Optional fixed-shape MLP inference over an explicitly bounded command domain.

Training reuses nexus.nn.factory.build_mlp. Inference uses exported JSON only,
so the default/local runtime need not import Torch. This is not an NN framework.
"""
import hashlib
import json
import math
from pathlib import Path
import re

DIRECTIONS = ('left', 'right', 'up', 'down')
DIRECTION_WORDS = ('left', 'right', 'up', 'down', 'west', 'east', 'north', 'south')
VOCAB = ('<ref>', 'move', 'shift', 'push', 'take', 'please', 'the', 'to', 'towards',
         *DIRECTION_WORDS)
VERBS = ('move', 'shift', 'push', 'take')
SCHEMA = 'seed_direction_mlp_v1'
HIDDEN = 16


def slots(text):
    if type(text) is not str or len(text) > 512:
        return None
    tokens = text.lower().strip().rstrip('.').split()
    if not 3 <= len(tokens) <= 9 or any(not re.fullmatch('[a-z][a-z0-9]{0,23}', t) for t in tokens):
        return None
    # This recognizer establishes domain eligibility, not the direction label.
    # Unsupported/multi-direction/negated commands must not enter neural routing.
    if sum(t in VERBS for t in tokens) != 1 or sum(t in DIRECTION_WORDS for t in tokens) != 1:
        return None
    refs = [t for t in tokens if t not in VOCAB]
    if len(refs) != 1:
        return None
    ref = refs[0]
    # Restrict syntactic slots; an unknown word outside this slot is not masked
    # into an apparently valid command. The model maps direction words to labels.
    normalized = [('<ref>' if t == ref else t) for t in tokens]
    pattern = ' '.join(normalized)
    if not re.fullmatch(r'(?:please )?(?:move|shift|push|take) (?:the )?<ref> (?:to (?:the )?|towards )?(?:left|right|up|down|west|east|north|south)', pattern):
        return None
    return ref, normalized


def features(tokens):
    return [tokens.count(t) / len(tokens) for t in VOCAB]


class TinyCommandEncoder:
    def __init__(self, data):
        if type(data) is not dict or set(data) != {'schema','vocab','hidden','labels','weights','trained','provenance'}:
            raise ValueError('encoder_schema')
        if data['schema'] != SCHEMA or data['vocab'] != list(VOCAB) or data['hidden'] != HIDDEN or data['labels'] != list(DIRECTIONS) or data['trained'] is not True:
            raise ValueError('trained_fixed_architecture_required')
        w = data['weights']
        if set(w) != {'w1','b1','w2','b2'}:
            raise ValueError('encoder_weight_names')
        shapes = {'w1':(HIDDEN,len(VOCAB)), 'b1':(HIDDEN,), 'w2':(4,HIDDEN), 'b2':(4,)}
        def check(value, shape):
            if not shape:
                return type(value) in (int,float) and math.isfinite(value) and abs(value)<100
            return type(value) is list and len(value)==shape[0] and all(check(v,shape[1:]) for v in value)
        if not all(check(w[k], shape) for k,shape in shapes.items()):
            raise ValueError('finite_fixed_weight_shapes')
        self.data = data
        self.forward_calls = 0

    @classmethod
    def load(cls, path, expected_sha256):
        path=Path(path)
        if path.stat().st_size > 128_000:
            raise ValueError('encoder_file_cap')
        raw=path.read_bytes()
        if type(expected_sha256) is not str or hashlib.sha256(raw).hexdigest()!=expected_sha256:
            raise ValueError('encoder_hash')
        return cls(json.loads(raw))

    def logits(self, tokens):
        self.forward_calls += 1
        x=features(tokens);w=self.data['weights']
        hidden=[math.tanh(sum(a*b for a,b in zip(row,x))+bias) for row,bias in zip(w['w1'],w['b1'])]
        return [sum(a*b for a,b in zip(row,hidden))+bias for row,bias in zip(w['w2'],w['b2'])]

    def propose(self, text):
        parsed=slots(text)
        if parsed is None:
            return None
        ref,tokens=parsed;scores=self.logits(tokens)
        order=sorted(range(4),key=lambda i:(-scores[i],i))
        margin=scores[order[0]]-scores[order[1]]
        if margin<0.5:
            return None
        return dict(reference=ref,direction=DIRECTIONS[order[0]],steps=1,
                    logit_margin=margin,score_is_calibrated_confidence=False)

    @property
    def parameter_count(self):
        return HIDDEN*len(VOCAB)+HIDDEN+4*HIDDEN+4
