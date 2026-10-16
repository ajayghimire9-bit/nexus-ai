"""Fail-closed resume locks. These tests do not collect the missing cell."""
from __future__ import annotations
import copy
import itertools
import json
from pathlib import Path
import pytest
from nexus.world import action_conditioned_q as q
from nexus.world import action_conditioned_q_resume as m
from nexus.world.commitment_value import total, validate_trace
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences


def test_parent_capture_and_fit_hashes_are_frozen():
    assert sha(m.PARENT_OUTPUT)=='6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680'
    assert sha(m.PARENT_FIT)=='2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae'
    assert sha('docs/NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md')=='76c06fd1de355d7176f7165b6e2dc1cfceb0729b67ea5cac244e595207bfa597'
    assert sha('configs/action_conditioned_q.yaml')=='3c260ac2f78278280de8ccaf9a91d6c0e456bcaaad50b95f31e91209b1cad14a'
    raw,fit=m.load_parent()
    assert raw['complete'] is False and raw['label']=='incomplete'
    assert fit['complete'] is True and fit['family']=='action_obs' and len(fit['readouts'])==10


def test_missing_cell_identity_and_visitor_seed_split():
    resume_cfg,cfg=m.load_resume_config()
    raw,_=m.load_parent()
    have=m.present_keys(raw['cells'])
    assert have==m.EXPECTED_PRESENT
    assert m.freeze_cells(raw['cells'])==resume_cfg['present_digest']
    assert m.MISSING==(9,2,1)
    assert resume_cfg['missing_visitor']=='zero'
    assert q.reset_seed(cfg,9,2)==q.reset_seed(cfg,9,2)
    assert q.collection_seeds(cfg,9,2)==q.collection_seeds(cfg,9,2)
    assert q.candidate_seed(cfg,9,2,0)!=q.candidate_seed(cfg,9,2,1)
    assert q.future_seeds(cfg,9,2,0)!=q.future_seeds(cfg,9,2,1)
    sibling=next(r for r in raw['cells'] if (r['decoder'],r['task'],r['state'])==(9,2,0))
    assert sibling['visitor']=='student'
    assert sibling['reset_seed']==q.reset_seed(cfg,9,2)
    assert [step['seed'] for step in sibling['collection']]==q.collection_seeds(cfg,9,2)


def test_source_labels_have_complete_traces_and_rebuild_returns():
    raw,_=m.load_parent();cfg=q.load_config()
    assert len(raw['source_cells'])==160
    for row in raw['source_cells']:
        assert row['reset_seed']==q.source_state_seed(cfg,row['task'],row['state'])
        assert len(row['traces'])==3 and len(row['returns'])==3
        seeds=q.source_future_seeds(cfg,row['task'],row['state'])
        for a,tr in enumerate(row['traces']):
            validate_trace(tr,seeds,0,a)
            assert abs(row['returns'][a]-total(tr['rewards'],64))<1e-8


def test_ten_q_fits_rebuild_from_source_labels():
    raw,fit=m.load_parent();cfg=q.load_config()
    rebuilt=m.inspect_fits(raw,fit,cfg)
    assert set(rebuilt)==set(range(10))
    for d in range(10):
        saved=fit['readouts'][str(d)]
        assert rebuilt[d]['conditioned']==saved['conditioned']['sha256']
        assert rebuilt[d]['additive']==saved['additive']['sha256']
        assert rebuilt[d]['rows']==48


def test_fifty_nine_cells_have_complete_raw_traces_and_rebuild_metrics():
    raw,fit=m.load_parent();cfg=q.load_config()
    assert len(raw['cells'])==59
    for row in raw['cells']:
        assert all(k in row for k in m.REQUIRED_CELL)
        live=row['collection']
        assert len(live)==50 and row['live_replay_matched'] is True
        assert all(type(step['action']) is int and step['action'] in (0,1,2) for step in live)
        assert all(type(step['reward']) in (int,float) for step in live)
        assert len(row['first_traces'])==3
        seeds=q.future_seeds(cfg,row['decoder'],row['task'],row['state'])
        for a,tr in enumerate(row['first_traces']):
            validate_trace(tr,seeds,50,a)
            assert len(tr['rewards'])==64 and len(tr['actions'])==64
        seq=candidate_sequences(q.candidate_seed(cfg,row['decoder'],row['task'],row['state']))
        cond=q.RidgeQ(**fit['readouts'][str(row['decoder'])]['conditioned']['state'])
        add=q.RidgeQ(**fit['readouts'][str(row['decoder'])]['additive']['state'])
        rebuilt=q.row_metrics(row['scores'],seq,[total(tr['rewards'],64) for tr in row['first_traces']],cond,add,row['obs'],cfg['family'],cfg['additive_family'])
        assert rebuilt==row['metrics']
        assert row['before']==row['after']
        assert row['conditioned_sha256']==cond.digest()
        assert row['additive_sha256']==add.digest()


def test_assemble_accepts_only_the_missing_cell_and_freezes_the_fifty_nine():
    raw,fit=m.load_parent();resume_cfg,cfg=m.load_resume_config()
    digest=m.PRESENT_DIGEST
    assert m.freeze_cells(raw['cells'])==digest
    new=copy.deepcopy(raw['cells'][0])
    new.update(decoder=9,task=2,state=1,visitor='zero',visitor_model='zero')
    meta=dict(present_digest=digest,wall_clock_s=1.0,resume_cfg={'time_cap_s':60,'env_cap':242,'model_cap':64512})
    assembled=m.assemble(raw,new,fit,cfg,meta)
    assert m.present_keys(assembled['cells'])==set(itertools.product(range(10),range(3),range(2)))
    assert m.freeze_cells(assembled['cells'][:-1])==digest
    wrong=copy.deepcopy(new);wrong['decoder']=8
    with pytest.raises(ValueError,match='locked missing cell'):
        m.assemble(raw,wrong,fit,cfg,meta)
    mutated=copy.deepcopy(raw);mutated['cells'][0]=copy.deepcopy(raw['cells'][1])
    with pytest.raises(ValueError,match='59-cell set was replaced'):
        m.assemble(mutated,new,fit,cfg,meta)


def test_resume_budget_is_one_cell_and_unauthorized():
    resume_cfg,_=m.load_resume_config();counts=m.budget(resume_cfg)
    assert counts==dict(collection=50,first_common=192,model_states=64512)
    assert resume_cfg['env_cap']==242 and resume_cfg['model_cap']==64512 and resume_cfg['time_cap_s']==60
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    assert record['previous_exhausted_session_sha256']=='c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462'
    with pytest.raises(PermissionError,match='fresh human approval'):
        m.require_allocation(resume_cfg)
    text=Path('docs/NEXUS_ACTION_CONDITIONED_Q_RESUME_PROTOCOL.md').read_text()
    assert 'authorized: false' in text and 'architecture_change_authorized: false' in text
    assert 'NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md' in text
    assert not m.CELL_OUTPUT.exists() and not m.COMPLETED.exists()
