# Context-conditioned MPC

Starting SHA `24d9b38fb05d294ac4475613694cbb4153344ef3`. Config: `configs/latent_control.yaml`. The runner rejects a drifted file.

The prediction confirmation already passed. This asks whether that same epoch-200 encoder improves H=16 model-predictive control on those four physics. The physics are not a new confirmation set.

Not AGI. Not learning-to-learn. A higher return is not retuned into a new encoder.

## Frozen controller

Pendulum uses the published reward and the three torques. The planner is the existing random-shooting controller: horizon **16**, **16** candidate sequences, chunk size 4. The time budget is off, which is the existing pendulum path, so every controller scores all 16 sequences. The decoder, normalization, and epoch-200 encoder weights stay frozen. Support is the same 128-row confirmation support. Context is inferred once before the episode and is not updated during control.

## Checkpoints

The runner loads the 15 broad students and 15 eight-task baselines named in `artifacts/latent_generalization_confirmation.json` (sha256 `18ef526655e8d0ce9d49fe5b67f4af17997c08bff564f256354e48e1086c04fa`). Each file hash must match. A present file with the wrong hash is not overwritten. A missing file is retrained with the locked procedure and kept only when the new hash matches the record.

The three multitask MLP checkpoints are an external reference. They are not a decoder replication.

## Evaluation

Control episodes use env seeds starting at **110000**, four episodes per task. Those seeds are disjoint from the support seeds. Every controller sees the same resets and the same planner seeds.

The comparisons on each frozen decoder are the broad student, zero context, the global vector, the original encoder, the eight-task student, and the direct teacher fit on that support. The teacher is a fitted latent, not an oracle controller.

The primary number is episodic return. The five student seeds are averaged inside each decoder, together with the four tasks and the four episodes. The interval is a Student-t interval on the three decoder differences. A difference is student return minus the control return.

The screen passes only when the student beats both zero context and the frozen encoder by at least **25** return points, and both intervals have a lower bound above 0. An interval that includes 0 is inconclusive even when the mean is positive. Global context, the eight-task baseline, and the teacher are reported. An episode at or below **-1500** is counted as catastrophic.

No return is used to change the horizon, the encoder, or the teacher rule.

<!-- protocol-lock
confirm_split_hash: baa655fcb94e61bc
confirmation_artifact_sha256: 18ef526655e8d0ce9d49fe5b67f4af17997c08bff564f256354e48e1086c04fa
horizon: 16
n_candidates: 16
support_budget: 128
episodes: 4
confirmation_epoch: 200
n_decoder_seeds: 3
n_student_seeds: 5
n_parameters: 584
n_decoder_parameters: 3748
minimum_effect: 25
catastrophic_return: -1500
control_eval_env0: 110000
primary_unit: decoder
-->

## If the screen fails

The same episodes are not reused for a retune.

If either primary interval includes 0 while a mean is positive, the result is inconclusive.

If both intervals lie above 0 but a mean is below 25, the effect is below the locked margin.

If the teacher clears the margin and the student does not, the remaining gap is the inferred latent.

If neither the student nor the teacher beats zero context, the next question is the planner.

Otherwise the prediction gain did not become a return gain.

## If the screen passes

The context rule stays a candidate for a later control test on physics that were not used here. This run does not start that test.

## Results

The control run has not been started in the implementation commit.
