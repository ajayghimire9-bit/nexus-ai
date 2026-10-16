"""Source-only lookahead synthesis locks. No environment collection."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from nexus.world import lookahead_generalization_synthesis as synth
from nexus.world.planning_value import sha


def test_cited_closed_screens_match_saved_artifacts():
    rows=synth.load_cited()
    by={row['name']:row for row in rows}
    assert by['pendulum_unmatched_development']['mean']==155.647
    assert by['pendulum_compute_matched']['mean']==60.182
    assert by['acrobot_unmatched_development']['mean']==27.914
    assert by['acrobot_compute_matched']['mean']==12.834
    assert by['acrobot_compute_matched']['label']=='acrobot_compute_matched_lookahead_not_established'
    assert by['mountaincar_compute_matched']['mean']==54.649
    assert by['mountaincar_unmatched_transfer']['mean']==50.366
    assert by['mountaincar_continuous_unmatched_development']['mean']==69.758
    assert by['cartpole_h3']['mean']==4.0
    assert by['linear_first_action_q']['mean']==-3.535
    assert by['terminal_value']['mean']==-0.221
    assert by['action_conditioned_q']['mean']==-4.293
    assert sha(synth.SYNTHESIS)==synth.LOCKED_SYNTHESIS


def test_extra_search_explains_acrobot_remainder_not_pendulum_or_mountaincar():
    share=synth.extra_search_share()
    assert share['acrobot']['unpaired_points_closed']==15.080
    assert share['acrobot']['remainder_clears_margin'] is False
    assert share['pendulum']['remainder_clears_margin'] is True
    assert share['mountaincar']['remainder_clears_margin'] is True
    assert share['mountaincar']['matched']==54.649


def test_audit_is_source_only_and_execute_refuses_collection():
    payload=synth.audit()
    assert payload['authorized'] is False
    assert payload['new_environment_steps']==0
    assert payload['new_imagined_transitions']==0
    assert payload['confirmation_outcomes_read'] is False
    assert payload['conclusions']['cross_family_learning_supported'] is False
    assert payload['conclusions']['meta_learning_supported'] is False
    assert payload['conclusions']['proposed_mechanism']=='tree_reuse_lookahead'
    assert payload['conclusions']['proposed_imagined_per_step']==259
    saved=json.loads(Path(synth.OUTPUT).read_text())
    assert saved['label']=='lookahead_generalization_synthesis_source_only'
    with pytest.raises(PermissionError, match='source-only'):
        synth.execute()
