# NEXUS control replication

Not AGI. Not learning-to-learn. The previous H=16 comparison stays inconclusive. Its episode seeds stay closed, and its returns are not used to retune the encoder, the decoder, the planner, or this protocol.

## Question

Does the 584-parameter student improve H=16 pendulum return when the uncertainty is the independently trained decoder, not the episode?

The pass rule is unchanged. Across ten decoders, the mean student-minus-zero return and the mean student-minus-frozen-encoder return must each be at least 25, and both Student-t 95% intervals must have lower bounds above zero. A lower bound above 25 is reported as stronger evidence. It is not a second pass rule.

## What stays frozen

- Mean-pooling encoder, 584 parameters, latent dimension 8
- Residual decoder and FiLM, 3748 parameters
- Pendulum horizon 16, 16 candidate sequences, three torques, published reward
- No online weight updates and no privileged task parameters
- Support budget 128
- Student Adam learning rate 0.01 for 200 epochs
- Teacher Adam learning rate 0.1 for 256 updates, fit on that support only
- Catastrophic return at or below −1500, reported and not used for selection

## Decoder replication

The original seeds are 0, 1, and 2. They are re-scored on new episodes. They are not new replicates.

The new seeds are 3, 4, 5, 6, 7, 8, and 9. Each one repeats the locked history-decoder recipe: 3000 joint context updates, then 1000 encoder and FiLM updates with the trunk frozen, on eight source tasks and 400 transitions each. The global vector is the locked pooled fit, Adam learning rate 0.01 for 300 updates from zeros. The student then trains on the same twelve-task supports used before, with teachers fit on those supports. The eight-task baseline uses the same epoch and learning rate.

Before any new seed is trained, the recipe must reproduce the saved weights and global vectors of seeds 0, 1, and 2. A mismatch stops the run. New files go in `artifacts/control_replication_checkpoints/`. The original checkpoint directories are not write targets. A hash mismatch does not overwrite a file.

If fewer than ten decoders finish inside the time limit, the study is incomplete. The pass rule is not recomputed on the finished subset.

## Evaluation registration

Two sets, both registered before returns:

- Replication: the four previous confirmation physics, new episode seeds starting at 120000. The previous support rows are reused so the episode sample is the new factor. These tasks are not a fresh physics confirmation.
- Fresh physics hash `053e8efca60fb4ac`: `(3.6, 0.42, 1.35)`, `(18.5, 1.85, 0.62)`, `(9.1, 3.1, 1.05)`, `(13.7, 0.22, 1.95)`. Support seeds start at 124000. Episode seeds start at 126000.

Four episodes per controller. The same reset and the same planner seed are used for every controller. Every controller scores 16 candidates.

Primary controllers: student, zero, frozen encoder. Secondary: global latent, direct teacher, eight-task baseline, multitask MLP.

## Statistics

One paired return difference per decoder, after averaging that decoder's student seeds, tasks, and episodes. The interval uses those decoder differences. Episodes and student seeds that share a decoder are not model replications.

Missing cells, a timeout, or fewer than ten decoders make `declared_complete` false and the gate fail. Partial numbers can be reported as exploratory.

Decoder variability is the standard deviation of the decoder-level paired differences. Episode variability is the root-mean-square of the within-decoder episode standard deviations. The larger one is reported as dominating. That split is descriptive.

## Prediction-to-action diagnostic

The planner is not changed. The run records:

- whether the first action agrees, which is the same-state comparison
- the fraction of later actions that agree, which is path-dependent once the states diverge
- rank disagreement of the 16 candidate scores at the first decision
- the realized return of the next 16 rewards on the trajectory that was actually visited
- one-step prediction error on the visited transitions
- the correlation, across decoders, between visited-prediction improvement and paired return improvement

That correlation is not evidence that prediction error causes the return difference.

## Outcomes

Both splits must pass before a control improvement is claimed. The registered follow-up is then a separate cross-task adaptation-efficiency study.

If the replication split passes and the fresh physics do not, the result is negative transfer. If visited prediction improves and the return intervals do not, the follow-up is planner sensitivity and control-oriented evaluation. If the intervals still cross zero, the variance split says whether decoder noise or episode noise is larger. This evaluation set is not reused for a retune.

The time limit is 9000 seconds. A run that stops at the limit is incomplete.

<!-- protocol-lock
target_decoders: 10
original_seeds: 0,1,2
new_seeds: 3,4,5,6,7,8,9
horizon: 16
n_candidates: 16
episodes: 4
support_budget: 128
student_lr: 0.01
student_epochs: 200
teacher_lr: 0.1
teacher_updates: 256
minimum_effect: 25
catastrophic_return: -1500
replication_eval_env0: 120000
fresh_eval_env0: 126000
fresh_support_env0: 124000
fresh_split_hash: 053e8efca60fb4ac
confirm_split_hash: baa655fcb94e61bc
primary_unit: decoder
time_limit_s: 9000
n_parameters: 584
n_decoder_parameters: 3748
context_updates: 3000
history_updates: 1000
-->
