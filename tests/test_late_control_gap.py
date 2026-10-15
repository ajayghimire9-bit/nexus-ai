"""Behavioral safeguards for the locked same-state action intervention."""
import copy
import inspect
import itertools

import numpy as np
import pytest
import torch

from nexus.cl.metrics import seed_level_ci
from nexus.tasks.pendulum_family import pendulum_latent_confirmation
from nexus.tasks.spec import make_task_env
from nexus.world.late_control_gap_design import load_design_config, assert_design_seeds, common_continuation_seed
from nexus.world.late_control_gap import aggregate, validate_grid, policy_return, assert_ready, network_hash, decision
from nexus.world.receding_horizon import restore_state, rollout_actions, true_state, continuation_return, chunked_scores
from nexus.world.prediction_control_gap import candidate_sequences
from test_receding_horizon import _Model


def grid():
    return [dict(decoder=d, task=t, phase=p, visitor=v, student=s,
                 primary=float(s if v == 'student' else -10), policy=0., regret=0.,
                 reward_error=0., agreement=1., student_return=0., zero_return=0.)
            for d,t,p,v,s in itertools.product(range(10), range(4), [16,50,100,150], ['student','zero'], range(5))]


def test_equal_group_weight_and_decoder_ci():
    rows = grid()
    validate_grid(rows)
    result = aggregate(rows, 'primary')
    assert result['per_decoder'] == [-4.] * 10
    assert result['interval'] == seed_level_ci([-4.] * 10)
    values = list(range(10))
    ci = seed_level_ci(values)
    assert ci['df'] == 9
    assert ci['hi'] == pytest.approx(np.mean(values) + 2.262*np.std(values,ddof=1)/np.sqrt(10))


@pytest.mark.parametrize('field,value', [('decoder',9),('task',3),('phase',150),('visitor','zero'),('student',4)])
def test_missing_planned_grid_fails(field,value):
    with pytest.raises(ValueError):
        validate_grid([r for r in grid() if r[field] != value])


@pytest.mark.parametrize('value', [float('nan'), float('inf'), True, '1'])
def test_invalid_metric_fails(value):
    rows = grid(); rows[0]['primary'] = value
    with pytest.raises(ValueError): validate_grid(rows)


def test_duplicate_cell_fails():
    rows=grid(); rows[-1]=copy.deepcopy(rows[0])
    with pytest.raises(ValueError): validate_grid(rows)


def test_closed_seed_rejected():
    cfg=load_design_config(); assert_design_seeds(cfg)
    cfg['eval_env0']=400000
    with pytest.raises(ValueError): assert_design_seeds(cfg)
    assert 'action' not in inspect.signature(common_continuation_seed).parameters


def test_exact_restore_reward_and_boundary_reset():
    env=make_task_env(pendulum_latent_confirmation()[0]); obs,_=env.reset(seed=913)
    state=true_state(env)
    for _ in range(200): env.step(1)
    assert np.array_equal(restore_state(env,state),obs)
    seq=np.array([0,2,1]*5+[2])
    a=rollout_actions(env,state,seq); b=rollout_actions(env,state,seq)
    assert np.array_equal(a['next_obs'],b['next_obs'])
    assert a['return']==sum(a['rewards'])
    assert a['return']==b['return']
    env.close()


def test_candidates_continuation_randomness_and_context():
    env=make_task_env(pendulum_latent_confirmation()[0]); obs,_=env.reset(seed=14)
    state=true_state(env); zero=_Model(); student=_Model()
    student.z=torch.ones(8)
    seq=candidate_sequences(520000,16,16,3)
    chunked_scores(zero,obs,seq); chunked_scores(student,obs,seq)
    assert all(np.array_equal(a,b) for a,b in zip(zero.seen,student.seen))
    seeds=list(range(530000,530016))
    traces=[]
    for action in range(3):
        zero.seen.clear()
        first=continuation_return(env,zero,state,action,seeds)
        traces.append([a.copy() for a in zero.seen])
        assert first==continuation_return(env,zero,state,action,seeds)
    assert all(np.array_equal(a,b) for a,b in zip(traces[0],traces[2]))
    assert torch.equal(zero.z,torch.zeros(8))
    assert torch.equal(student.z,torch.ones(8))
    assert policy_return(env,zero,state,seeds)==policy_return(env,zero,state,seeds)
    env.close()


def test_protocol_and_execution_gate():
    assert_ready()
    assert decision(-2,-3,-1,True)=='same_state_action_worse'
    assert decision(-2,-3,-1,False)=='incomplete'
    assert decision(-.5,-1,-.1,True)=='below_practical_threshold'
    assert decision(-2,-4,1,True)=='action_quality_not_separated'


def test_network_hash_includes_encoder_and_normalization():
    from nexus.world.context_model import ContextWorldModel
    model=ContextWorldModel.create(3,3,seed=4)
    before=network_hash(model)
    model.z=torch.ones(8)
    assert network_hash(model)==before
    with torch.no_grad():
        next(model.encoder.parameters()).add_(.01)
    assert network_hash(model)!=before
    before=network_hash(model)
    model.obs_rms.mean+=.1
    assert network_hash(model)!=before


def test_checkpoint_manifest_rejects_missing_and_wrong_hash(tmp_path):
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity, CheckpointIntegrityError
    import hashlib
    path=tmp_path/'weights.pt'; path.write_bytes(b'registered')
    records={'weights.pt':hashlib.sha256(b'registered').hexdigest()}
    assert verify_checkpoint_integrity(records,tmp_path)['verified']==1
    path.write_bytes(b'changed')
    with pytest.raises(CheckpointIntegrityError): verify_checkpoint_integrity(records,tmp_path)
    path.unlink()
    with pytest.raises(CheckpointIntegrityError): verify_checkpoint_integrity(records,tmp_path)
