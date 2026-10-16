"""Recorded resume feasibility. No new environment collection."""
import json
from nexus.world import action_conditioned_q_resume as m
from nexus.world.planning_value import sha


def test_feasibility_artifact_is_offline_and_reconstructs_parent():
    p=json.loads(m.FEASIBILITY.read_text())
    assert p['complete'] is True
    assert p['new_environment_steps']==0 and p['new_imagined_transitions']==0
    assert p['authorized'] is False
    assert p['development_outcomes_used_for_tuning'] is False
    assert p['original_protocol_unmodified'] is True
    assert p['n_source_cells']==160 and p['n_eval_cells']==59
    assert p['missing']=={'decoder':9,'task':2,'state':1,'visitor':'zero'}
    assert p['reconstruction']['possible'] is True
    assert p['parent_output_sha256']=='6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680'
    assert p['parent_fit_sha256']=='2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae'
    assert set(map(int,p['fits']))==set(range(10))
    assert p['config_sha256']==sha(m.CONFIG)
    assert p['protocol_sha256']==sha(m.PROTOCOL)
    assert sha(m.PARENT_OUTPUT)==p['parent_output_sha256']
    assert sha(m.PARENT_FIT)==p['parent_fit_sha256']
