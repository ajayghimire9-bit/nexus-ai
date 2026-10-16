"""Offline audit of receding long-term value. No environment collection."""
from __future__ import annotations
import inspect
import json
from pathlib import Path
import numpy as np
from nexus.world.planning import RandomShootingMPC, PENDULUM_PLAN_HORIZON, PENDULUM_PLAN_CANDIDATES
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.rewards import pendulum_step_reward
from nexus.world.terminal_value_execution import save

AUDIT=Path('docs/NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md')
PROTOCOL=Path('docs/NEXUS_BELLMAN_BACKUP_CONTROL_PROTOCOL.md')
OUTPUT=Path('artifacts/receding_long_term_value_audit.json')
CONFIG=Path('configs/bellman_backup_control.yaml')
ALLOCATION=Path('configs/bellman_backup_control_allocation.json')
STARTING='580dfb0d3e0df1c03d561339577f0a2da8f6e893'


def planner_inventory():
    src=inspect.getsource(RandomShootingMPC.act)
    score_src=inspect.getsource(RandomShootingMPC._score_batch)
    return dict(
        chooses_first_action_of_argmax_open_loop_sequence=('int(seqs[best, 0])' in src and 'np.argmax(scores)' in src),
        scores_predicted_reward_along_fixed_action_sequence=('step_reward' in score_src),
        state_dependent_open_loop_scoring=True,
        state_action_value_under_future_receding_policy=False,
        bellman_backup_in_act=False,
        bellman_consistent_long_term_value=False,
        multi_step_return_targets_for_learning=False,
        temporal_abstraction=False,
        uncertainty_aware_decision_making=False,
        uncertainty_penalty_default=float(RandomShootingMPC.__dataclass_fields__['uncertainty_penalty'].default),
        pendulum_horizon=int(PENDULUM_PLAN_HORIZON),
        pendulum_n_candidates=int(PENDULUM_PLAN_CANDIDATES),
        learns_from_observed_control_failures=False,
        note='Deployed Pendulum MPC maximises imagined open-loop H=16 return over 16 sequences, then executes only the first action and replans.',
    )


def bellman_first_action(model,obs,sequences):
    """One-step backup of frozen H=16 open-loop value. No fitted Q."""
    sequences=np.asarray(sequences,dtype=np.int64)
    if sequences.shape!=(16,16): raise ValueError('shared candidate array drifted')
    obs=np.asarray(obs,dtype=np.float32).reshape(1,-1)
    q=[]
    for a in range(3):
        nxt,_p=model.step(obs,np.asarray([a],dtype=np.int64))
        nxt=np.asarray(nxt,dtype=np.float32).reshape(1,-1)
        r=float(np.asarray(pendulum_step_reward(obs,a,nxt),dtype=np.float64).reshape(-1)[0])
        s=np.repeat(nxt,16,axis=0)
        begin=getattr(model,'begin_rollout',None)
        if begin is not None: begin(16)
        alive=np.ones(16,dtype=np.float64);score=np.zeros(16,dtype=np.float64)
        for t in range(16):
            pred,p=model.step(s,sequences[:,t])
            pred=np.asarray(pred,dtype=np.float32).reshape(16,-1)
            p=np.clip(np.asarray(p,dtype=np.float64).reshape(16),0.0,1.0)
            rr=np.asarray(pendulum_step_reward(s,sequences[:,t],pred),dtype=np.float64).reshape(16)
            score+=alive*rr
            alive=alive*(1.0-p)
            s=pred
        q.append(r+float(np.max(score)))
    return int(np.argmax(q)),q


def evidence_matrix():
    return [
        dict(study='planning_value',question='Does exact H=16 sequence selection miss 64-step value?',
             unit='ten decoders; eight source tasks',primary='+34.685 [+22.677, +46.694]',
             registered=True,label='short_objective_misses_practical_value',
             established='Complete-plan H=16 return is not 64-step value under common-zero continuation',
             unknown='Not receding first-action control; not 200-step episodes',
             artifacts_available=True,kind='complete_plan_value'),
        dict(study='prediction_control_gap',question='Does better prediction rank candidates worse?',
             unit='ten decoders; confirmation/replication one-shot states',
             primary='student Spearman 0.680 vs zero 0.620; selected16 regret 3.905 vs 5.218',
             registered=True,label='evaluation_variance / planning_metrics_agree',
             established='Student ranks H=16 candidates better on those states; episode return still favored zero on fresh physics',
             unknown='One-shot ranking is not receding 200-step control',
             artifacts_available=True,kind='complete_plan_ranking'),
        dict(study='action_value_alignment',question='Is the best 16-sequence first action optimal for first-action+replan?',
             unit='ten decoders; 60 development visited states',
             primary='20.254 [11.382, 29.127]; optimal in 18/60',
             registered=True,label='sequence_first_action_misalignment_detected',
             established='Complete-plan value ≠ first-action value under zero-replanning',
             unknown='H=16 selected first-action regret vs best-of-3 is exploratory (~15.3), not a 200-step controller test',
             artifacts_available=True,kind='first_action_value'),
        dict(study='first_action_value',question='Does a source-trained linear Q beat H=16 on 64-step first-action return?',
             unit='ten decoders; development phase-50 visited states',
             primary='−3.535 [−9.840, +2.769]',
             registered=True,label='aligned_first_action_gain_not_established',
             established='This 15-coefficient Q did not beat H=16 on 64-step first-action+zero-replan',
             unknown='Never deployed as a 200-step receding controller; RMSE 107.5 on development',
             artifacts_available=True,kind='fitted_first_action_q'),
        dict(study='action_conditioned_q',question='Does action×observation Q beat H=16 on 64-step first-action return?',
             unit='ten decoders; 60-cell development grid',
             primary='−4.293 [−15.751, +7.165]',
             registered=True,label='action_conditioned_gain_not_established',
             established='Larger state-action Q still did not beat H=16 on the same 64-step intervention',
             unknown='Same 64-step visited-state screen, not full-episode receding',
             artifacts_available=True,kind='fitted_first_action_q'),
        dict(study='terminal_value / source_scalar',question='Does an endpoint readout or scalar correction improve selection?',
             unit='ten decoders; visited-state 64-step',
             primary='terminal −0.221 [−5.881, +5.438]; scalar −9.228 [−22.358, +3.901]',
             registered=True,label='local_first_action_inconclusive / scalar_selection_gain_not_established',
             established='Score correction of complete 16-sequences did not establish better choices',
             unknown='Correction was not a Bellman backup of receding value',
             artifacts_available=True,kind='terminal_score_correction'),
        dict(study='receding_policy_consistency',question='Does executing the selected 16-plan beat receding on 16-step return?',
             unit='ten decoders; 160 source cells',
             primary='commit−recede-fresh −1.787 [−4.324, +0.751]',
             registered=True,label='replan_consistency_not_established',
             established='16-step commit vs recede is inconclusive; search-noise switch 0.500',
             unknown='Not 200-step episodes',
             artifacts_available=True,kind='receding_versus_commit'),
        dict(study='late_control_gap',question='Is student first-action worse than zero at late same states?',
             unit='ten decoders; 16-step common-zero continuation',
             primary='+0.0312 [−0.0827, +0.1452]',
             registered=True,label='action_quality_not_separated',
             established='Same-state 16-step first-action quality not separated',
             unknown='Not 200-step; not a switching policy',
             artifacts_available=True,kind='late_same_state'),
        dict(study='horizon_objective_control',question='Does nested H=8 receding beat archived H=16 on 200-step return?',
             unit='ten decoders; 60 development episodes',
             primary='−174.178 [−265.830, −82.527]',
             registered=True,label='shorter_horizon_hurts_episode_return',
             established='Shortening the open-loop objective hurt complete-episode control while one-step MAE stayed small',
             unknown='Does a Bellman first-action backup of H=16 value beat H=16 receding?',
             artifacts_available=True,kind='full_episode_control'),
    ]


def rank_explanations():
    return [
        dict(code='B',name='incorrect_objective',support='strongest',maps_to='H1',
             why='Planner maximises open-loop sequence return then executes one action. Exact H=16 misses 64-step value; sequence-best first action is not receding-best; nested H=8 hurt 200-step return.'),
        dict(code='D',name='insufficient_or_misaligned_learning_signal',support='strong_for_why_Q_failed',maps_to='H2',
             why='Fitted Q/V used 64-step zero-replan labels at isolated visited states, never 200-step same-policy receding returns. Development RMSE ~96–108.'),
        dict(code='A',name='inaccurate_dynamics',support='real_but_not_dominant_for_H8',maps_to='H3_partial',
             why='H=16 teacher-forced angvel MAE ~1.93, but H=8 (less compounding) hurt control. One-step MAE ~0.09 stayed small while episodes lost ~174 points.'),
        dict(code='C',name='limited_search',support='contributor_not_next_lever',maps_to=None,
             why='Search-noise first-action switch 0.500. Same 16×16 set made H=16 beat H=8, so objective horizon dominated candidate-set identity in that test.'),
        dict(code='E',name='failure_to_adapt_when_physics_change',support='insufficient_for_this_failure',maps_to='H3_partial',
             why='H=8 hurt both student and zero on development. Student-minus-zero 200-step late-episode return included 0. Negative transfer remains a separate closed confirmation result.'),
    ]


def competing_hypotheses():
    return [
        dict(id='H1',name='planning_objective_mismatch',verdict='best_supported',
             why='Open-loop 16-plan value is not first-action value under replanning. Registered: 64-step complete-plan regret 34.685; sequence-to-first-action gap 20.254; nested H=8 hurt 200-step return. The deployed rule still maximises the former.'),
        dict(id='H2',name='state_dependent_action_value_estimation',verdict='explains_closed_Q_failures_not_the_deployed_rule',
             why='Linear and action-conditioned Q failed a 64-step zero-replan screen (RMSE ~96–108). That does not prove a larger network is required; those labels were not receding 200-step returns. Capacity was already increased once and still failed.'),
        dict(id='H3',name='policy_induced_distribution_shift',verdict='open_not_isolated',
             why='Late executed-error growth was not established. Recede-versus-commit on 16-step return includes 0. H=8 hurt complete episodes, which is compatible with H1 without isolating progressive post-choice state shift. Do not treat H3 as demonstrated.'),
    ]


def budget():
    env=10*3*2*200*2
    imagined=10*3*2*200*(16*16+3+3*16*16)
    if env!=24000 or imagined!=12324000: raise ValueError('Bellman backup budget drifted')
    return dict(episode=env,model_states=imagined,time_cap_s=180,training_updates=0)


def run():
    inv=planner_inventory()
    if not inv['chooses_first_action_of_argmax_open_loop_sequence']:
        raise ValueError('planner act() no longer selects the first action of the argmax sequence')
    if inv['bellman_backup_in_act'] or inv['state_action_value_under_future_receding_policy']:
        raise ValueError('unexpected receding-value estimator appeared in act()')
    rec=dict(
        complete=True,new_environment_steps=0,new_imagined_transitions=0,training=0,authorized=False,
        starting_sha=STARTING,planner=inv,evidence_matrix=evidence_matrix(),
        explanation_rank=rank_explanations(),
        strongest='B_incorrect_objective',
        competing=competing_hypotheses(),
        mechanism='one_step_bellman_backup_of_frozen_h16_open_loop_value',
        mechanism_fits=False,new_network=False,confirmation_used=False,
        proposed_budget=budget(),
        ranking_loss_training=False,horizon_sweep=False,score_correction_closed=True,
        note='No environment collection. Nested H=8 result and closed Q/V screens are unchanged.',
    )
    save(OUTPUT,rec);return rec
