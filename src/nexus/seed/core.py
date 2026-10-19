"""Finite version-space learning and typed object-world execution.

Reuse E1 Journal/canonical JSON; concept records are domain evidence, not a
second general strategy-memory system. No teacher predicate enters Session.
"""
from dataclasses import asdict, dataclass
import itertools
import random
import re
import threading
import time

from nexus.evolution1.catalogue import digest
from nexus.evolution1.fixtures import Event, Journal, verify_journal

PROPERTIES = {'color': ('red', 'blue', 'green'),
              'shape': ('circle', 'square', 'triangle'), 'size': ('small', 'large')}
WORD = re.compile(r'[a-z][a-z0-9]{0,23}\Z')
MOVES = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}


def concept_word(word):
    return (type(word) is str and WORD.fullmatch(word) is not None and
            word not in {v for vs in PROPERTIES.values() for v in vs} and
            re.fullmatch(r'o[0-9]+', word) is None)


@dataclass(frozen=True, order=True)
class Predicate:
    # Conjunction of up to two literals; depth <=3 (and/not/atom).
    literals: tuple

    def matches(self, obj):
        return all((obj[k] == v) != neg for k, v, neg in self.literals)

    @property
    def description(self):
        return ' and '.join(('not ' if n else '') + v for k, v, n in self.literals)


ATOMS = tuple((k, v, False) for k, vs in PROPERTIES.items() for v in vs)
GRAMMAR = tuple(sorted(set([Predicate((a,)) for a in ATOMS] +
    [Predicate(((k, v, True),)) for k, v, _ in ATOMS] +
    [Predicate(tuple(sorted((a, b)))) for a, b in itertools.combinations(ATOMS, 2) if a[0] != b[0]])))
assert len(GRAMMAR) <= 512


def examples():
    return [dict(id=f'p{i}', color=c, shape=s, size=z, x=i % 6, y=i // 6)
            for i, (c, s, z) in enumerate(itertools.product(*PROPERTIES.values()))]


def scene(number=0):
    # Same property prior, different layout/subset; no teaching target metadata.
    if type(number) is not int or number not in (0, 1):
        raise ValueError('scene_must_be_0_or_1')
    indices = (0, 3, 7, 10, 14, 17) if number == 0 else (1, 4, 8, 11, 13, 16)
    return [dict(examples()[n], id=f'o{i+1}', x=(i*2+number) % 6, y=(i+number) % 5)
            for i, n in enumerate(indices)]


def valid_object(obj):
    if type(obj) is not dict or set(obj) != {'id', 'color', 'shape', 'size', 'x', 'y'}:
        raise ValueError('typed_object_required')
    if type(obj['id']) is not str or not WORD.fullmatch(obj['id']):
        raise ValueError('object_id')
    if any(obj[k] not in vals for k, vals in PROPERTIES.items()):
        raise ValueError('unknown_property')
    if any(type(obj[k]) is not int or not 0 <= obj[k] < 6 for k in ('x', 'y')):
        raise ValueError('grid_bounds')
    return dict(obj)


@dataclass(frozen=True)
class Move:
    reference: str
    direction: str
    steps: int = 1


def parse(text):
    if type(text) is not str or len(text) > 512:
        raise ValueError('message_length')
    text = text.lower().strip().rstrip('.')
    if text in ('help', 'inspect', 'stop', 'ask', 'look'):
        return text
    parts = text.split(' then ')
    if not 1 <= len(parts) <= 8:
        return None
    moves = []
    for part in parts:
        m = re.fullmatch(r'move (?:the )?([a-z][a-z0-9]{0,23}) (left|right|up|down)(?: ([0-9]{1,3}))?', part)
        if not m:
            return None
        moves.append(Move(m[1], m[2], int(m[3] or 1)))
    return tuple(moves)


class Session:
    """JSON-replayable evidence. Cancellation is cooperative and request bounded."""
    def __init__(self):
        self.journal = Journal()
        self.world = scene()
        self.evidence = []
        self.definitions = {}
        self.stopped = False
        self.cancelled = threading.Event()
        self.counts = dict(teacher_answers=0, candidate_evaluations=0,
                           predicate_tests=0, program_evaluations=0, sandbox_actions=0, generated_examples=0)
        self._deadline = float('inf')
        self.cost_guard = None

    def charge(self, key, amount=1):
        if self.cost_guard is not None:
            self.cost_guard(key, amount)
        self.counts[key] += amount

    def check(self):
        if self.cancelled.is_set() or time.monotonic() > self._deadline:
            raise TimeoutError('request_cancelled_or_2_second_cap')

    def event(self, kind, payload):
        if len(self.journal.snapshot()) >= 2048:
            raise ValueError('session_event_cap')
        return self.journal.append(kind, payload).fingerprint

    def test(self, predicate, obj):
        self.check()
        self.charge('predicate_tests')
        return predicate.matches(obj)

    def candidates(self, word):
        evidence = [e for e in self.evidence if e['word'] == word]
        superseded = {e['supersedes'] for e in evidence if e['supersedes'] is not None}
        active = [e for e in evidence if e['ref'] not in superseded]
        if word in self.definitions:
            pool = [GRAMMAR[self.definitions[word]]]
        else:
            pool = GRAMMAR
        result = []
        for p in pool:
            self.check()
            self.charge('candidate_evaluations')
            if all(self.test(p, e['object']) == e['positive'] for e in active):
                result.append(p)
        return result

    def teach(self, word, obj, positive, supersedes=None):
        if not concept_word(word):
            raise ValueError('invented_word_required')
        obj = valid_object(obj)
        if type(positive) is not bool:
            raise ValueError('boolean_label_required')
        if len(self.evidence) >= 256:
            raise ValueError('session_evidence_cap')
        if supersedes is not None:
            prior = next((e for e in self.evidence if e['ref'] == supersedes), None)
            if prior is None or prior['word'] != word or prior['object'] != obj or any(e['supersedes'] == supersedes for e in self.evidence):
                raise ValueError('current_evidence_reference_required')
        self.charge('teacher_answers')
        payload = dict(word=word, object=obj, positive=positive, supersedes=supersedes)
        ref = self.event('seed_teaching', payload)
        self.evidence.append(dict(payload, ref=ref))
        return ref

    def question(self, word, random_seed=None):
        pool = self.candidates(word)
        if not pool:
            return dict(status='contradiction', text='No grammar predicate fits. Correct evidence or expand in a later experiment.')
        ranked = []
        for obj in examples():
            self.check()
            yes = sum(self.test(p, obj) for p in pool)
            self.charge('generated_examples')
            if 0 < yes < len(pool):
                ranked.append((abs(len(pool)-2*yes), obj['id'], obj))
        if not ranked:
            return dict(status='no_distinguishing_example', text='No permitted example distinguishes the remaining meanings.')
        obj = min(ranked)[2] if random_seed is None else random.Random(random_seed).choice(ranked)[2]
        return dict(status='question', word=word, object=obj,
                    text=f"Is this {obj['size']} {obj['color']} {obj['shape']} a {word}?",
                    alternatives=[p.description for p in pool])

    def resolve(self, reference):
        direct = [o['id'] for o in self.world if o['id'] == reference]
        if direct:
            return direct, None
        atom = next((a for a in ATOMS if a[1] == reference), None)
        if atom:
            return [o['id'] for o in self.world if Predicate((atom,)).matches(o)], None
        if not any(e['word'] == reference for e in self.evidence) and reference not in self.definitions:
            return [], 'unknown_concept'
        pool = self.candidates(reference)
        if not pool:
            return [], 'contradiction'
        matches = [tuple(o['id'] for o in self.world if self.test(p, o)) for p in pool]
        if len(set(matches)) != 1:
            return sorted({v for row in matches for v in row}), 'uncertain_meaning'
        return list(matches[0]), None

    def execute(self, program):
        if type(program) is not tuple or not 1 <= len(program) <= 8 or any(type(m) is not Move for m in program):
            raise ValueError('typed_move_program_required')
        if any(type(m.steps) is not int or not 1 <= m.steps <= 128 or m.direction not in MOVES or type(m.reference) is not str for m in program) or sum(m.steps for m in program) > 128:
            raise ValueError('primitive_action_cap_or_invalid_move')
        self.charge('program_evaluations')
        proposed = [dict(o) for o in self.world]
        trace = []
        for move in program:
            self.check()
            ids, issue = self.resolve(move.reference)
            if issue or len(ids) != 1:
                return dict(type=issue or 'ambiguous_reference', text='Teach or clarify using one object ID; no actions executed.', matches=ids, trace=[])
            obj = next(o for o in proposed if o['id'] == ids[0])
            dx, dy = MOVES[move.direction]
            before = [obj['x'], obj['y']]
            for _ in range(move.steps):
                self.check()
                x, y = obj['x']+dx, obj['y']+dy
                if not 0 <= x < 6 or not 0 <= y < 6:
                    return dict(type='blocked', text='Program would leave the grid; no actions executed.', trace=[])
                obj['x'], obj['y'] = x, y
            trace.append(dict(object=ids[0], direction=move.direction, steps=move.steps, before=before, after=[obj['x'], obj['y']]))
        self.charge('sandbox_actions', sum(m.steps for m in program))
        self.event('seed_program', dict(program=[asdict(m) for m in program], trace=trace))
        self.world = proposed
        return dict(type='acted', text='Executed in the authored object world.', trace=trace)

    def inspect(self):
        words = sorted({e['word'] for e in self.evidence} | set(self.definitions))
        return dict(concepts=[dict(word=w, version=sum(e['word'] == w for e in self.evidence),
            origin='explicit_definition' if w in self.definitions else 'inferred_finite_grammar',
            alternatives=[p.description for p in self.candidates(w)],
            evidence_refs=[e['ref'] for e in self.evidence if e['word'] == w]) for w in words],
            evidence=self.evidence, world=self.world, costs=dict(self.counts), stopped=self.stopped,
            grammar=dict(predicates=len(GRAMMAR), depth_cap=3, properties=PROPERTIES,
                         definitions=[dict(id=i,text=p.description) for i,p in enumerate(GRAMMAR)]),
            events=[asdict(e) for e in self.journal.snapshot()])

    def request(self, payload):
        start = time.perf_counter()
        self._deadline = time.monotonic()+2
        before = dict(self.counts)
        result = dict(type='unsupported', text='Supported: move WORD right [N] then move WORD down; inspect, look, help, stop.')
        try:
            if type(payload) is not dict or 'op' not in payload:
                raise ValueError('typed_request_required')
            op = payload['op']
            fields = {'message': {'op','text'}, 'teach': {'op','word','object','positive'},
                      'correct': {'op','word','object','positive','supersedes'}, 'inspect': {'op'},
                      'question': {'op','word'}, 'scene': {'op','number'}, 'stop': {'op'},
                      'resume': {'op'}, 'define': {'op','word','predicate'}}
            if op not in fields or set(payload) != fields[op]:
                raise ValueError('request_schema')
            if op == 'stop' or op == 'message' and payload['text'] == 'stop':
                self.cancelled.set(); self.stopped = True
                self.event('seed_stop', {})
                result = dict(type='stopped', text='Session stopped; Resume explicitly to act again.')
            elif op == 'resume':
                self.cancelled.clear(); self.stopped = False
                self.event('seed_resume', {})
                result = dict(type='resumed', text='Session resumed.')
            elif self.stopped:
                result = dict(type='stopped', text='Resume explicitly first.')
            elif op in ('teach', 'correct'):
                ref = self.teach(payload['word'], payload['object'], payload['positive'], payload.get('supersedes'))
                pool = self.candidates(payload['word'])
                result = dict(type='learned' if pool else 'contradiction', evidence_refs=[ref],
                    text=f"Evidence saved. {len(pool)} consistent grammar meanings.", alternatives=[p.description for p in pool],
                    question=self.question(payload['word']))
            elif op == 'question':
                result = dict(type='clarification', **self.question(payload['word']))
            elif op == 'define':
                word = payload['word']; index = payload['predicate']
                if not concept_word(word) or type(index) is not int or not 0 <= index < len(GRAMMAR):
                    raise ValueError('definition_schema')
                self.definitions[word] = index
                self.event('seed_definition', dict(word=word, predicate=index))
                result = dict(type='defined', text='Explicit grammar definition saved; this is not induced discovery.')
            elif op == 'scene':
                self.world = scene(payload['number'])
                self.event('seed_scene', dict(number=payload['number']))
                result = dict(type='scene', text='Different authored scene loaded; learned evidence retained.')
            elif op == 'inspect':
                result = dict(type='knowledge', text='Evidence and current finite-grammar alternatives.')
            else:
                parsed = parse(payload['text'])
                if type(parsed) is tuple:
                    result = dict(self.execute(parsed), interpretation=[asdict(m) for m in parsed])
                elif parsed in ('inspect', 'look', 'help'):
                    result = dict(type=parsed, text='Authored 6×6 world; teach invented words using labeled examples. Grammar: properties, negations and two-property conjunctions.')
        except (ValueError, TypeError, KeyError) as exc:
            result = dict(type='error', text=str(exc))
        except TimeoutError as exc:
            result = dict(type='incomplete', text=str(exc))
        # Inspect itself is bounded; count its real predicate work in this request.
        try:
            state = self.inspect() if not self.stopped else dict(world=self.world, stopped=True, costs=dict(self.counts), evidence=self.evidence, concepts=[])
        except TimeoutError:
            state = dict(world=self.world, costs=dict(self.counts), incomplete=True)
        return dict(text=result.pop('text'), response_type=result.pop('type'),
                    interpretation=result.pop('interpretation', None), evidence_refs=result.pop('evidence_refs', []),
                    uncertainty=result.pop('alternatives', []), result=result, state=state,
                    resources=dict(wall_ms=(time.perf_counter()-start)*1000,
                                   **{k:self.counts[k]-before[k] for k in before}))

    def snapshot(self):
        events = [asdict(e) for e in self.journal.snapshot()]
        data = dict(schema='nexus_seed_session_v1', events=events, costs=dict(self.counts),
                    world=self.world, stopped=self.stopped,
                    grammar_hash=digest([p.literals for p in GRAMMAR]))
        return dict(data=data, sha256=digest(data))

    @classmethod
    def restore(cls, wire):
        if type(wire) is not dict or set(wire) != {'data','sha256'} or digest(wire['data']) != wire['sha256']:
            raise ValueError('snapshot_hash')
        data = wire['data']
        if set(data) != {'schema','events','costs','world','stopped','grammar_hash'} or data['schema'] != 'nexus_seed_session_v1' or data['grammar_hash'] != digest([p.literals for p in GRAMMAR]) or len(data['events']) > 2048:
            raise ValueError('snapshot_schema')
        events = tuple(Event(**e) for e in data['events'])
        verify_journal(events)
        s = cls()
        for event in events:
            import json
            p = json.loads(event.payload_json)
            if event.kind == 'seed_teaching':
                s.teach(p['word'], p['object'], p['positive'], p['supersedes'])
            elif event.kind == 'seed_definition':
                out = s.request(dict(op='define', **p))
                if out['response_type'] != 'defined':
                    raise ValueError('invalid_saved_definition')
            elif event.kind == 'seed_scene':
                s.world = scene(p['number']); s.event(event.kind, p)
            elif event.kind == 'seed_program':
                out = s.execute(tuple(Move(**m) for m in p['program']))
                if out['type'] != 'acted' or out['trace'] != p['trace']:
                    raise ValueError('saved_program_replay_mismatch')
            elif event.kind in ('seed_stop','seed_resume'):
                s.stopped = event.kind == 'seed_stop'; s.event(event.kind, p)
            else:
                raise ValueError('unknown_saved_event')
        if s.world != data['world'] or s.stopped != data['stopped']:
            raise ValueError('derived_state_mismatch')
        if s.journal.snapshot() != events:
            raise ValueError('event_replay_schema_mismatch')
        if set(data['costs']) != set(s.counts) or any(type(v) is not int or not 0 <= v <= 10**9 for v in data['costs'].values()):
            raise ValueError('saved_cost_schema')
        if any(data['costs'][k] < s.counts[k] for k in ('teacher_answers','program_evaluations','sandbox_actions')):
            raise ValueError('saved_cost_rollback')
        s.counts = dict(data['costs'])
        if s.stopped:
            s.cancelled.set()
        return s
