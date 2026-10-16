"""Recorded complete resume. No new environment collection."""
import json
from pathlib import Path
import pytest
from nexus.world import action_conditioned_q as parent
from nexus.world import action_conditioned_q_resume as m
from nexus.world.planning_value import sha


def test_original_incomplete_capture_is_unchanged():
    p=json.loads(parent.OUTPUT.read_text());fit=json.loads(parent.FIT.read_text())
    assert p['complete'] is False and p['label']=='incomplete' and len(p['cells'])==59
    assert fit['complete'] is True and len(fit['readouts'])==10
    assert sha(parent.OUTPUT)=='6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680'
    assert sha(parent.FIT)=='2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae'
    with pytest.raises(RuntimeError,match='incomplete'):
        parent.audit()


def test_recorded_resume_is_complete_and_keeps_the_fifty_nine_cells():
    completed=json.loads(m.COMPLETED.read_text());cell=json.loads(m.CELL_OUTPUT.read_text())
    assert completed['complete'] is True
    assert completed['label']=='action_conditioned_gain_not_established'
    assert len(completed['cells'])==60 and len(completed['source_cells'])==160
    assert (cell['cell']['decoder'],cell['cell']['task'],cell['cell']['state'],cell['cell']['visitor'])==(9,2,1,'zero')
    kept=[c for c in completed['cells'] if (c['decoder'],c['task'],c['state'])!=m.MISSING]
    assert m.freeze_cells(kept)==m.PRESENT_DIGEST
    assert completed['resume_counts']==dict(collection=50,first_common=192,model_states=64512)
    assert completed['checkpoint_after']==dict(verified=120,missing=0,mismatched=0)
    assert sha(m.COMPLETED)=='aa78514a5a2bb560089453000d8049284aafe3136c83f03c1a88de9dc01a3793'
    assert sha(m.CELL_OUTPUT)=='4ec58dfabe0e18f18ac2fadcbaa3b42420dceff5635995364dcf2d1e0b0a16c8'
    assert sha(m.PARENT_OUTPUT)==completed['parent_raw_sha256']
    v=json.loads(Path('artifacts/action_conditioned_q_resume_verification.json').read_text())
    assert v['audit_passed'] is True and v['fifty_nine_cells_unchanged'] is True
    assert v['exhausted_session_ledger_unchanged'] is True
    usage=json.loads(Path('artifacts/research_session_action_conditioned_q_resume_usage.json').read_text())
    assert usage['remaining_session_allowance_s']==0.0
    assert usage['new_real_environment_steps']==242
    exhausted=json.loads(Path('artifacts/research_session_first_action_value_usage.json').read_text())
    assert sha('artifacts/research_session_first_action_value_usage.json')=='c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462'
    assert exhausted['remaining_session_allowance_s']<60
