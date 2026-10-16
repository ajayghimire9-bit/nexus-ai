"""Next-direction assessment locks. No scientific collection."""
from __future__ import annotations
from pathlib import Path
import json
import pytest
from nexus.world import decision_aware_world_model as dawm
from nexus.world import next_direction_assessment as m
from nexus.world.planning_value import sha


def test_decision_aware_protocol_remains_unauthorized_and_byte_identical():
    m.assert_decision_aware_frozen()
    record=dawm.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    assert sha(dawm.PROTOCOL)==m.DECISION_AWARE_PROTOCOL_SHA
    assert sha(dawm.CONFIG)==m.DECISION_AWARE_CONFIG_SHA
    assert dawm.OUTPUT.exists() is False
    with pytest.raises(PermissionError,match='fresh human approval required'):
        dawm.require_allocation(dawm.load_config())


def test_return_phase_windows_do_not_retune_the_closed_label():
    windows=m.return_phase_windows()
    assert windows['closed_primary_label']=='primarily_late'
    assert windows['exploratory'] is True and windows['retuned'] is False
    assert windows['confirmation_reopened'] is False
    early=windows['early_0_15']['interval'];mid=windows['mid_16_63']['interval']
    late=windows['late_64_127']['interval'];tail=windows['tail_128_199']['interval']
    assert early['lo']<0<early['hi'] and mid['lo']<0<mid['hi']
    assert late['hi']<0 and tail['hi']<0
    late_sum=mid['mean']+late['mean']+tail['mean']
    assert abs(late_sum-windows['late_16_199']['interval']['mean'])<1e-6
    assert abs(early['mean']+late_sum-early['mean']-windows['late_16_199']['interval']['mean'])<1e-6


def test_assessment_recommends_B_with_zero_new_steps():
    report=m.run()
    assert report['recommendation']=='B'
    assert report['new_environment_steps']==0 and report['new_imagined_transitions']==0
    assert report['authorized'] is False and report['training']==0
    assert report['decision_aware_collection_authorized'] is False
    assert report['confirmation_physics_used_for_new_collection'] is False
    assert Path('docs/NEXUS_NEXT_DIRECTION_ASSESSMENT.md').is_file()
    saved=json.loads(m.OUTPUT.read_text())
    assert saved['recommendation']=='B'
