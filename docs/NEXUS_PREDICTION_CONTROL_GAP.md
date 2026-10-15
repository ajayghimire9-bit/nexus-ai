# NEXUS — Prediction-to-control gap

The confirmed 584-parameter context encoder lowers angular-velocity prediction error and, on the ten-decoder H=16 replication, raises return on new episodes of the previous Pendulum physics. The same controllers lose return on the disjoint physics. This diagnostic asks which part of that gap is visible in one shared set of candidate action sequences. It is a mechanism measurement. It is not a new control evaluation, not a retune, and not an architecture change.

The closed ten-decoder returns stay closed. Positive return transfer on the previous physics and negative return transfer on the fresh physics are inputs to the decision rule. They are not remeasured here.

## Competing hypotheses

These hypotheses are registered together. The measurements can support more than one description. The decision rule below picks one later experiment; it does not treat a correlation as a cause.

- **H1 — Action ranking.** Better state prediction does not necessarily rank the available action sequences by realized return.
- **H2 — Distribution shift.** The student can be accurate on newly recorded random transitions and less reliable on the open-loop trajectories the planner scores.
- **H3 — Horizon and reward mismatch.** Lower one-step state error does not necessarily lower the error of the planner's H=16 cumulative score.
- **H4 — Dynamics regimes.** The sign of the prediction-to-regret relationship can differ across physics.

## Protocol lock

The block below is the registered budget. A drift between this block and `configs/prediction_control_gap.yaml` stops the run before any diagnostic outcome is written.

<!-- protocol-lock
states_per_physics: 16
recorded_transitions: 128
horizon: 16
n_candidates: 16
n_actions: 3
target_decoders: 10
n_student_seeds: 5
primary_split: fresh
seed_stride: 20
replication_state_env0: 140000
fresh_state_env0: 142000
replication_recorded_env0: 144000
fresh_recorded_env0: 146000
candidate_rng_base: 151000
recorded_action_base: 147000
time_limit_s: 1800
starting_sha: af32a0398375b72d534417b6459638fedac41297
manifest_sha256: 265cd1822ec73bab8eac6fd792438c3c9fe7834ae5af307b8c33104bf919d06b
control_artifact_sha256: 35c75320e1c243eaa1914cf6e726e9849d246910ebfc79f6ac0f390c86daf0e9
confirm_split_hash: baa655fcb94e61bc
fresh_split_hash: 053e8efca60fb4ac
ranking_metric: regret
prediction_metric: candidate_one_step_angvel
reward_metric: absolute_planner_score_error
selection_atol: 1e-08
full_episode_remeasured: false
fresh_full_episode_student_better: false
replication_full_episode_student_better: true
support_budget: 128
closed_previous_control_eval_env0: 110000
closed_replication_eval_env0: 120000
closed_fresh_eval_env0: 126000
closed_fresh_support_env0: 124000
-->

## Provenance

Before any diagnostic reset, the run checks the closed control artifact, the checkpoint manifest, the original and new decoder files, the broad and baseline student files, the stored global latent vectors, and the frozen decoder fingerprints of seeds 0, 1, and 2. A hash or fingerprint miss stops the run. Nothing in this study writes a checkpoint. The encoder, decoder, planner, and trained weights stay as they were.

GitHub `cursor/latent-control-replication` and the local base were `af32a0398375b72d534417b6459638fedac41297` when this branch was created. The diagnostic seeds below are rejected if they intersect a closed collect or episode seed, including the previous control episodes at 110000, the replication episodes at 120000, and the fresh control episodes at 126000.

## Registered states and actions

Both physics splits use the same budget: 4 tasks, 16 initial states each, 16 candidate sequences, horizon 16. The replication split is `pendulum_lat_cf0` through `pendulum_lat_cf3`. The fresh split is `pendulum_ctrl_rp0` through `pendulum_ctrl_rp3`. State resets are `env0 + 20 * task + index`. Candidate sequences come from one NumPy generator per state, seeded at `151000 + split * 10000 + task * 100 + index`, and are shared by zero context, every student, and the simulator. Recorded random transitions, 128 per task, use 144000 and 146000. Their action-generator bases start at 147000. Those recorded rows are a one-step contrast. They are not the support that sets context, and they are not control-evaluation episodes.

Context for the student is the saved broad encoder applied to the same 128-row supports the closed controller used. Confirmation supports must match the stored support hashes. Zero context is the zero vector. Baseline encoders are hash-checked and not scored. Five student seeds are averaged inside a decoder. The statistical unit is the decoder. Ten decoders are required. States, candidates, and students are not extra replications.

## Same-state comparison

At each registered state the existing random-shooting planner scores the shared sequences under its locked H=16 predicted-reward objective, including its survival weighting. The simulator then resets to that same seed and applies the same sequences. The actual return is the sum of the Gymnasium Pendulum reward, which this code requires to match the published pendulum cost on the current angle, angular velocity, and torque. Predicted scores are computed without the realized returns and without the hidden gravity, mass, or length. The simulator may use those parameters to produce the research target. That target is not written into the model or the context vector.

The selected sequence is the first maximum of the predicted scores. It is counted as correct when its realized return is within `1e-8` of the best return in the shared set. Regret is the best shared return minus the selected return. Ranking correlation is Spearman correlation between predicted scores and realized returns.

## Metrics and decision

Positive improvement means the student is better: lower angular-velocity error, lower regret, or lower absolute error between the planner score and the realized return. The primary prediction metric is one-step angular-velocity error on the candidate trajectories. Full-state error, open-loop error, and recorded-transition error are reported beside it. Intervals are Student-t 95% intervals across the ten decoders. A reliable improvement requires all ten decoders, a positive mean, and a lower bound above zero. An interval that includes zero does not choose a branch.

The primary decision uses the fresh split, because that is where full-episode return transfer failed. The replication split is a contrast.

1. If candidate one-step angular velocity improves and regret gets worse, the present objective is insufficiently aligned with planning decisions. The later experiment should measure or improve action-ranking accuracy. No architecture change is made here.
2. Otherwise, if action ranking and the H=16 reward forecast both improve, audit evaluation variance and the planning implementation before any architecture change. On a split whose closed return already favored the student, this agreement is recorded as a contrast rather than a new control result.
3. Otherwise, if action ranking improves and the closed full-episode return did not, a later experiment should measure receding-horizon sensitivity and distribution shift.
4. Otherwise the sample is inconclusive.

H2 is reported when recorded one-step error improves and candidate open-loop error does not reliably improve. H4 is reported when the four fresh task-mean regret gaps do not share a sign, or when the two splits receive different decision labels. Those descriptions are not causal proof. A Pearson correlation across decoders is reported with the same limit.

If the time limit is reached before all ten decoders finish both splits, the result is incomplete. An incomplete grid does not choose a hypothesis and does not justify an architecture change.

## What this study will not do

It will not remeasure full-episode return, change H or the candidate count, feed realized outcomes or hidden physics into the model, or implement the recommended follow-up. A completed diagnostic is evidence about this planner and these physics. It is not a general control improvement, not learning-to-learn, and not AGI.
