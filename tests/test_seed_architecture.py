"""Authored engineering tests; optional neural/meta code is not general learning."""
import copy
import hashlib
import json
from pathlib import Path
import socket
import pytest
from nexus.seed.core import Session, examples
from nexus.seed.perception import (TinyCommandEncoder, SCHEMA, VOCAB, DIRECTIONS,
                                   HIDDEN, slots)
from nexus.seed.working import current


def fixture_encoder():
    # Hand-authored output for routing tests, NOT a trained model result.
    return TinyCommandEncoder(dict(schema=SCHEMA,vocab=list(VOCAB),hidden=HIDDEN,
        labels=list(DIRECTIONS),trained=True,provenance={'kind':'handwritten_test_fixture'},
        weights=dict(w1=[[0.]*len(VOCAB) for _ in range(HIDDEN)],b1=[0.]*HIDDEN,
                     w2=[[0.]*HIDDEN for _ in range(4)],b2=[0.,2.,0.,0.])))


def test_neural_route_is_optional_and_only_proposes_typed_moves():
    encoder=fixture_encoder();s=Session(language_encoder=encoder)
    before=json.dumps(encoder.data,sort_keys=True)
    out=s.request(dict(op='message',text='please shift o1 towards east'))
    assert out['response_type']=='acted'
    assert out['result']['perception']=='trained_tiny_mlp'
    assert out['interpretation']==[dict(reference='o1',direction='right',steps=1)]
    assert out['resources']['neural_forward_calls']==1
    assert json.dumps(encoder.data,sort_keys=True)==before
    assert Session().request(dict(op='message',text='please shift o1 towards east'))['response_type']=='unsupported'


@pytest.mark.parametrize('text',['do not move o1 north','run o1 north','move o1 north south',
                                'push o1 north then shell','push o1 north quickly','push two objects north'])
def test_oov_negation_and_multiple_directions_never_act(text):
    s=Session(language_encoder=fixture_encoder());before=copy.deepcopy(s.world)
    out=s.request(dict(op='message',text=text))
    assert out['response_type']=='unsupported'
    assert s.world==before and out['resources']['neural_forward_calls']==0


def test_symbolic_parser_remains_authoritative_and_bounds_apply():
    s=Session(language_encoder=fixture_encoder())
    out=s.request(dict(op='message',text='move o1 left'))
    assert out['response_type']=='blocked'  # Fixture encoder would say right.
    assert out['resources']['neural_forward_calls']==0


def test_working_reference_persists_and_clears_on_scene_or_teaching():
    s=Session();s.request(dict(op='message',text='move o1 right'))
    restored=Session.restore(s.snapshot())
    assert current(restored.journal.snapshot()).last_object=='o1'
    out=restored.request(dict(op='message',text='move it right'))
    assert out['response_type']=='acted' and out['interpretation'][0]['reference']=='o1'
    restored.request(dict(op='scene',number=1))
    assert restored.request(dict(op='message',text='move it right'))['response_type']=='clarification'
    s.teach('foo',examples()[0],True)
    assert s.request(dict(op='message',text='move it right'))['response_type']=='clarification'


def test_unknown_paraphrase_concept_does_not_bypass_teaching():
    s=Session(language_encoder=fixture_encoder())
    out=s.request(dict(op='message',text='push norg east'))
    assert out['response_type']=='unknown_concept' and not out['result']['trace']


def test_model_hash_schema_shapes_nonfinite_and_margin(tmp_path):
    model=fixture_encoder();path=tmp_path/'model.json';path.write_text(json.dumps(model.data))
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    assert TinyCommandEncoder.load(path,sha).parameter_count==356
    with pytest.raises(ValueError,match='hash'):TinyCommandEncoder.load(path,'0'*64)
    for key,value in [('b1',[0.]),('b2',[float('nan'),0,0,0])]:
        data=copy.deepcopy(model.data);data['weights'][key]=value
        with pytest.raises(ValueError):TinyCommandEncoder(data)
    model.data['weights']['b2']=[0.]*4
    assert model.propose('push o1 east') is None


def test_controller_receives_only_answered_card_feedback_and_restores():
    pytest.importorskip('torch')
    s=Session(meta_questions=True)
    q=s.request(dict(op='question',word='foo',mode='meta'))['result']
    assert q['policy']=='balanced'
    # Withholding feedback cannot update a strategy's count or mean.
    again=s.request(dict(op='question',word='foo',mode='meta'))['result']
    assert again['meta_statistics']==q['meta_statistics']
    s.request(dict(op='teach',word='foo',object=again['object'],positive=True))
    feedback=[e for e in s.journal.snapshot() if e.kind=='seed_question_feedback']
    assert len(feedback)==1
    nextq=s.request(dict(op='question',word='foo',mode='meta'))['result']
    assert nextq['meta_statistics']['balanced']['count']==1 and nextq['policy']=='random'
    restored=Session.restore(s.snapshot())
    assert restored.snapshot()==s.snapshot()
    # Saved data does not grant optional runtime capabilities.
    assert not restored.meta_questions and restored.language_encoder is None


def test_corrections_wrong_examples_and_client_rewards_cannot_update_meta():
    pytest.importorskip('torch')
    s=Session(meta_questions=True)
    q=s.request(dict(op='question',word='foo',mode='meta'))['result']
    different=next(o for o in examples() if o!=q['object'])
    s.request(dict(op='teach',word='foo',object=different,positive=True))
    assert not any(e.kind=='seed_question_feedback' for e in s.journal.snapshot())
    assert s.request(dict(op='reward',value=100))['response_type']=='error'
    s2=Session()
    assert s2.request(dict(op='question',word='foo',mode='meta'))['response_type']=='error'


def test_neural_path_has_no_external_network(monkeypatch):
    monkeypatch.setattr(socket,'socket',lambda *a,**k: (_ for _ in ()).throw(AssertionError('no network')))
    s=Session(language_encoder=fixture_encoder())
    assert s.request(dict(op='message',text='push o1 east'))['response_type']=='acted'


def test_bounded_symbolic_goal_planner_executes_shortest_program():
    s=Session();out=s.request(dict(op='plan',reference='o1',x=3,y=3))
    assert out['response_type']=='acted'
    assert sum(t['steps'] for t in out['result']['trace'])==6
    assert [s.world[0]['x'],s.world[0]['y']]==[3,3]
    assert out['result']['symbolic_search']['expanded']<=36
    assert s.request(dict(op='plan',reference='o1',x=3,y=3))['response_type']=='already_at_goal'
    assert s.request(dict(op='plan',reference='o1',x=True,y=3))['response_type']=='error'
    assert s.request(dict(op='plan',reference='unlearned',x=3,y=3))['response_type']=='unknown_concept'


def test_search_cap_does_not_change_world():
    from nexus.seed.planning import to_cell
    s=Session();before=copy.deepcopy(s.world)
    with pytest.raises(TimeoutError):to_cell(s.world[0],5,5,s.check,max_expansions=1)
    assert s.world==before
