"""Recorded late-episode grid. Does not collect again."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from nexus.world import late_episode_decision_trajectory as m
from nexus.world.planning_value import sha


def test_complete_grid_frozen_and_one_run_consumed():
    p=json.loads(m.OUTPUT.read_text())
    assert p['complete'] is True and p['label']=='late_error_growth_not_established'
    assert len(p['cells'])==30
    assert p['counts']=={'episode':12000,'model_states':3084000}
    assert sha(m.OUTPUT)=='743b545d78910f7b0df8c83d15b4eb77190798b1dd803ad4daa51434a6214939'
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    usage=json.loads(Path(record['previous_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])==0.0
    with pytest.raises(PermissionError,match='session allowance exhausted'):
        m.require_allocation(m.load_config())
    exhausted=json.loads(Path('artifacts/research_session_first_action_value_usage.json').read_text())
    assert sha('artifacts/research_session_first_action_value_usage.json')=='c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462'
    assert float(exhausted['remaining_session_allowance_s'])<90
    v=json.loads(Path('artifacts/late_episode_decision_trajectory_verification.json').read_text())
    assert v['audit_passed'] is True and v['three_action_forks']==0
    assert v['exhausted_session_ledger_unchanged'] is True
