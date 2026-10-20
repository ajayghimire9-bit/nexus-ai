# Frozen Seed action scorer: spatial-distribution development transfer

Registered before outcomes. Reuse ActionReadout,SeedRSSM,Belief,AuthoredWorld,
existing H4/16/pruned latent MPC,rank_metrics,audit_episode and df7 intervals.
No fitting,architecture change,new planner,GRU update or retrospective selection.
This continues the useful action path while learning-to-learn remains unproven.

## Hypotheses and fixed conditions

H-transfer: the previously trained nonlinear scorer retains a practically
meaningful control gain over frozen reward ranking on fresh spatial mixtures.
H-overfit: its gain depends on the original start/goal distribution.
Both are plausible; neither is assumed. No old result is reopened for tuning.

Exact config:configs/seed_spatial_transfer.json. Verify original core,all three
trained readouts,manifest and parent result hashes before creating worlds.
Keep normalization/source bank,state contract,rewards and every model weight
fixed. No latent fitting or extra student training. All three heads are evaluated;
do not pick the best one from results.

Four prespecified spatial mixtures: interior start/corner goal; opposite corners;
boundary start/reversed boundary goal; opposed-sign diagonal displacement.
They shift initial geometry within the SAME6×6 dynamics and known attributes.
This is not unseen environment-family or physics confirmation. Each sampler
uses only seed and geometry,not predicted/actual outcomes.

Exclude exact (x,y,color,shape,size,goal) tuples from the parent source,
development,final ranking and control-initial records. Exclusion uses occupancy
only,not performance. Also require unique starts across new ranking and control
roles. Up to256 geometry/property draws are allowed without stepping; exhaustion
is an invalid/incomplete run,not permission to relax exclusion. Later trajectories
may naturally revisit earlier cells; that is not a new interaction-free sample.

For each group,32 ranking states/all9 exact cloned outcomes. Then8 registered
reset streams×2episodes×7methods,20-step cap. Conditions:three fixed readouts,
frozen ranking,random,known-grid greedy and unchanged latent MPC. All methods
share exact initial states. Planner seed=episode_seed×100+step; random policy
uses episode_seed+7. No evaluator outcomes enter scoring. One posterior per
actual observation; context/memory handling is unchanged. Stop at first goal.

## Primary screen and aggregation

Primary metric: readout-minus-frozen episodic return,average the three heads
and two episodes inside each group/reset stream,then equal-weight four groups.
Use8 paired stream differences with Student-t95%,df7,t=2.364624251.
These units are conditional on ONE pretrained core; head seeds,states,actions
and episodes are not extra world-model replications. Intervals are exploratory
and do not establish general control or meta-learning.

Pass only with complete finite results,exact frozen hashes,and ALL:

- pooled mean return gain>=0.2;
- pooled paired95% lower bound>0;
- pooled goal-rate gain>=0.10;
- no group's mean return gain below−0.10.

Report group-specific intervals,ranking regret,goals,all task streams and every
baseline,including greedy. Secondary improvements cannot upgrade primary failure.
Do not change the rule or retune after inspection. Failed transfer is retained.

## Resources and provenance

One run,local CPU,120s cap under standing human authority. Worst-case10,112
authored steps (1,152 exact outcomes+8,960 actual control actions),<=12,000 cap.
Worst-case108,672 imagined transitions,<=120,000 cap. Posterior-prior model rows,
readout calls,real steps and wall time are reported separately. No optimizer
steps. Carried session1905.6321034559958s used /1694.3678965440042s remaining;
enforce the smaller time cap. Save partial results and costs on interruption.
Precommit implementation/tests/protocol; record clean execution SHA,all hashes,
raw traces and final decision. Preserve original checkpoints and artifacts.

## Next decision

If transfer fails,diagnose spatial/history sensitivity before training a larger
model. If it passes,prepare a separate fresh learning-curve study using frozen
state/action features and the existing PlasticityController/correction API.
Require faster held-out1/2/4/8-example learning versus scaled replay,fixed
protection,no adaptation and a tuned source-only simple reference,with forgetting
and action quality measured. Neither a transfer pass nor an ordinary fitted
readout is itself learning-to-learn. No automatic rank-four enablement or new
architecture search follows this experiment.
