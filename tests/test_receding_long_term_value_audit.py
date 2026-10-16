"""Offline receding-value audit. No scientific collection."""
from __future__ import annotations
import numpy as np
import pytest
from nexus.world import receding_long_term_value_audit as m
from nexus.world.prediction_control_gap import candidate_sequences


class Drift:
    uses_simulator=False
    def step(self,obs,actions):
        o=np.asarray(obs,dtype=np.float32).reshape(-1,3)
        a=np.asarray(actions,dtype=np.int64).reshape(-1)
        nxt=o.copy();nxt[:,2]=o[:,2]+0.01*(a+1)
        return nxt,np.zeros(len(o),dtype=np.float64)


def test_planner_inventory_has_no_receding_q():
    inv=m.planner_inventory()
    assert inv['chooses_first_action_of_argmax_open_loop_sequence'] is True
    assert inv['state_action_value_under_future_receding_policy'] is False
    assert inv['bellman_backup_in_act'] is False
    assert inv['bellman_consistent_long_term_value'] is False
    assert inv['state_dependent_open_loop_scoring'] is True
    assert inv['uncertainty_aware_decision_making'] is False
    assert inv['uncertainty_penalty_default']==0.0
    assert inv['pendulum_horizon']==16 and inv['pendulum_n_candidates']==16


def test_bellman_first_action_is_not_open_loop_prefix_selection():
    seq=candidate_sequences(13100000,16,16)
    action,q=m.bellman_first_action(Drift(),np.array([1.0,0.0,0.2],dtype=np.float32),seq)
    assert action in (0,1,2) and len(q)==3
    assert seq[int(np.argmax(np.zeros(16))),0] in (0,1,2)
    open_loop_first=int(seq[0,0])
    assert isinstance(open_loop_first,int)


def test_audit_run_is_unauthorized_and_zero_env():
    report=m.run()
    assert report['complete'] is True
    assert report['new_environment_steps']==0
    assert report['new_imagined_transitions']==0
    assert report['training']==0
    assert report['authorized'] is False
    assert report['strongest']=='B_incorrect_objective'
    assert report['competing'][0]['id']=='H1' and report['competing'][0]['verdict']=='best_supported'
    assert report['competing'][1]['id']=='H2'
    assert report['competing'][2]['id']=='H3' and report['competing'][2]['verdict']=='open_not_isolated'
    assert report['mechanism']=='one_step_bellman_backup_of_frozen_h16_open_loop_value'
    assert report['new_network'] is False
    assert m.OUTPUT.exists() is True


def test_budget_identity():
    b=m.budget()
    assert b['episode']==24000
    assert b['model_states']==12324000
    assert b['training_updates']==0
