"""Recorded complete horizon-alignment screen. No new environment collection."""
import json
from pathlib import Path
import pytest
from nexus.world import horizon_alignment as m
from nexus.world.planning_value import sha


def test_recorded_horizon_alignment_is_complete_and_boundary_specific():
    p=json.loads(m.OUTPUT.read_text())
    assert p['complete'] is True and p['identity_ok'] is True
    assert p['label']=='boundary_specific_alignment'
    assert len(p['cells'])==60
    assert p['counts']==dict(short_fixed=960,short_aligned=960,full_fixed=12000,full_aligned=12000,model_states=6405120)
    assert p['checkpoint_after']==dict(verified=120,missing=0,mismatched=0)
    full=p['groups']['pooled']['gain_full']['interval']
    short=p['groups']['pooled']['gain_short']['interval']
    assert full['n']==10 and full['mean']<25 and full['lo']<0<full['hi']
    assert short['mean']>=1.0 and short['lo']>0
    rebuilt=m.summarize(p['cells'],m.load_config())
    assert rebuilt['label']==p['label'] and rebuilt['identity_ok'] is True
    assert rebuilt['groups']['pooled']['gain_full']['interval']==full
    assert sha(m.OUTPUT)=='910ada43a1c0abc43ca2898bafb7e7678654a21c0e8e7806d19508a3dbd2032e'
    audit=m.audit()
    assert audit['audit_passed'] is True and audit['raw_sha256']==sha(m.OUTPUT)
    v=json.loads(Path('artifacts/horizon_alignment_verification.json').read_text())
    assert v['audit_passed'] is True and v['n_cells']==60 and v['identity_ok'] is True
    assert v['exhausted_session_ledger_unchanged'] is True
    usage=json.loads(Path('artifacts/research_session_horizon_alignment_usage.json').read_text())
    assert usage['remaining_session_allowance_s']==0.0
    assert usage['new_real_environment_steps']==25920
    assert usage['new_imagined_transitions']==6405120
    assert sha('artifacts/research_session_first_action_value_usage.json')=='c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462'
    assert sha('artifacts/same_set_planning.json')=='2aac48a16c7dbce512fdf190d5fc4694f7aed3eba2189a0a953b7a704500368d'
    with pytest.raises(PermissionError,match='session allowance exhausted'):
        m.execute()
