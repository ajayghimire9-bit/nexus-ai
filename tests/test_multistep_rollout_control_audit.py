"""Offline multi-step audit locks. No scientific environment collection."""
from __future__ import annotations
import json
import numpy as np
import pytest
from nexus.world import late_episode_decision_trajectory as late
from nexus.world import multistep_rollout_control_audit as m
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences


class Drift:
    def __init__(self,delta=0.01):
        self.delta=float(delta);self.uses_simulator=False
    def step(self,obs,actions):
        o=np.asarray(obs,dtype=np.float32).reshape(-1,3)
        nxt=o.copy();nxt[:,2]=o[:,2]+self.delta
        return nxt,np.zeros(len(o),dtype=np.float64)


def test_closed_late_episode_capture_is_byte_identical():
    assert sha(late.OUTPUT)==m.LATE_RAW_SHA
    payload=json.loads(late.OUTPUT.read_text())
    inv=m.inventory(payload)
    assert inv['reconstructable']['teacher_forced_action_free_run'] is True
    assert inv['reconstructable']['planned_candidate_open_loop_vs_env'] is False
    assert inv['predicted_full_observations'] is False
    assert inv['next_observation_after_step_199'] is False
    assert inv['n_starts_per_trace']==184


def test_planned_suffix_is_not_labeled_model_error():
    payload=json.loads(late.OUTPUT.read_text())
    rows=m.plan_and_state(payload)
    plan=m.summarize_plan(rows)
    assert plan['receding_suffix_mismatch_is_not_model_error'] is True
    assert plan['causal_components']['separable_from_this_log'] is False
    assert plan['causal_components']['shortened_horizon'] is False
    cell=payload['cells'][0];tr=cell['student']
    seq=candidate_sequences(int(tr['seeds'][0]),16,16)
    assert int(seq[int(tr['selected_index'][0]),0])==int(tr['actions'][0])
    assert int(seq[int(tr['selected_index'][0]),1])==int(tr['planned_second'][0])
    assert plan['receding_suffix_mismatch_is_not_model_error'] is True


def test_teacher_forced_free_run_is_not_teacher_forced_one_step():
    obs0=np.zeros((3,3),dtype=np.float32)
    actions=np.zeros((3,16),dtype=np.int64)
    pred=m.free_run(Drift(0.05),obs0,actions)
    assert pred.shape==(3,16,3)
    assert np.allclose(pred[:,0,2],0.05)
    assert np.allclose(pred[:,15,2],0.80)
    actual=np.zeros((3,16,3),dtype=np.float32)
    actual[:,0,2]=0.05
    err=m.horizon_errors(pred,actual)
    assert err['1']['angvel']==pytest.approx(0.0)
    assert err['16']['angvel']==pytest.approx(0.80)


def test_zero_mismatch_does_not_become_a_full_prefix():
    student={'actions':[1]+[0]*199,'obs':[[1.0,0.0,0.0]]*200,'rewards':[0.0]*200,
             'scores':[[0.0]*16]*200,'selected_index':[0]*200,'planned_second':[0]*200,
             'angvel_err':[0.0]*200,'seeds':[11100000+i for i in range(200)]}
    # Keep reconstruction cheap: only check n_matched helper semantics via first_mismatch.
    from nexus.world.late_episode_decision_trajectory import first_mismatch
    assert first_mismatch([1]+[0]*199,[0]*200)==0
    n=first_mismatch([1]+[0]*199,[0]*200)
    n_matched=int(n if n is not None else 200)
    assert n_matched==0
    assert max(0,n_matched-16)==0


def test_recommend_shortens_when_compounding_is_large_and_student_is_not_better():
    interval=lambda mean,lo,hi: dict(n=10,df=9,mean=mean,lo=lo,hi=hi)
    dummy=dict(interval=interval(0.0,-1.0,1.0),per_decoder=[0.0]*10)
    h=lambda own_s,own_z,iso_mean,iso_lo,iso_hi: {
        'student_on_student':{'interval':interval(own_s,own_s-0.01,own_s+0.01)},
        'zero_on_zero':{'interval':interval(own_z,own_z-0.01,own_z+0.01)},
        'student_on_zero':dummy,'zero_on_student':dummy,
        'angle_student_on_student':dummy,'angle_zero_on_zero':dummy,
    }
    rollouts={'horizons':{str(k):h(0.1,0.1,0.0,-1.0,1.0) for k in (1,2,4,8)}}
    rollouts['horizons']['16']=h(0.9,0.8,0.05,-0.01,0.12)
    rollouts['isolation']={'16':{'interval':interval(0.05,-0.01,0.12)}}
    rec=m.recommend(rollouts,{})
    assert rec['choice']=='shorter_horizon_control'
    assert rec['authorized'] is False
    assert rec['ranking_loss_training'] is False
    assert rec['env_cap']==12000
    rollouts['horizons']['16']=h(0.2,0.25,-0.04,-0.06,-0.02)
    rollouts['isolation']={'16':{'interval':interval(-0.04,-0.06,-0.02)}}
    rec=m.recommend(rollouts,{})
    assert rec['choice']=='longer_horizon_objective'
    assert rec['full_episode_return_is_primary'] is True
    assert rec['practical_threshold']==25.0


def test_simulator_backed_model_is_refused():
    class Env:
        uses_simulator=True
        def step(self,obs,actions):
            return obs,0
    with pytest.raises(RuntimeError,match='simulator-backed'):
        m.wrap_model(Env(),dict(model_states=0,env_steps=0))


def test_audit_module_has_no_execute_collection_entry():
    import inspect
    assert hasattr(m,'run') and not hasattr(m,'execute')
    source=inspect.getsource(m)
    assert 'make_task_env' not in source
    assert 'def execute' not in source
