# Amortized latent generalization confirmation

Starting SHA `5299ddc956f6f9cea73c5281a15445260b0b7adf`. Config: `configs/latent_generalization_confirmation.yaml`. The runner rejects a drifted file.

This asks whether the 584-parameter mean-pooling encoder, after the locked twelve-task training, lowers prediction error on a new Pendulum split. The development pass is not this result.

Not AGI. Not learning-to-learn. No MPC. Hashes `87b83c41be34aa1a` and `d1fa621351d286cf` stay closed.

## What stays frozen

The three history decoders stay frozen. The encoder stays the mean pool with width 32, eight latent numbers, and 584 parameters. The student learning rate stays **0.01** for **200** epochs. Each of the twelve source physics keeps two independent 128-row supports and its own teacher. The teacher rule stays Adam learning rate 0.1 for 256 updates from the stored global vector, with the decoder locked before the fit. The confirmation score uses epoch 200 only. Epochs 40 and 100 are still produced by the locked training loop. They do not choose a checkpoint.

## Reproduction before any new physics

The runner retrains the five student seeds on each of the three decoders. It then compares that run with `artifacts/latent_generalization_dev.json` (sha256 `c8438e09c383fc669b3b9f4cad275725d7daa9f49d2616083f256cefa1f24aba`).

Training and history teacher bindings must match exactly. Development angular velocity, the epoch-40 and epoch-100 trajectory, the training latent distance, the history latent distance, and the teacher-pair median must each land within **0.0001**. Teacher steps must be 30720 and student steps 96000. The decoder digest must match the file on disk.

A miss stops the run. The confirmation environments are not created. Numerical settings are not changed to force a match.

The matched epoch-200 encoders are written under `artifacts/latent_generalization_confirmation_checkpoints/`. Those `.pt` files are gitignored. The result artifact records each file hash. Reload a file with `torch.load` into the checkpoint encoder's `state_dict`. There are 30 files: three decoders, five student seeds, and both the broad student and the eight-task baseline.

## Confirmation physics

Four tasks, split hash `baa655fcb94e61bc`:

- `pendulum_lat_cf0`: gravity 5.1, mass 0.88, length 0.96
- `pendulum_lat_cf1`: gravity 15.8, mass 0.92, length 1.04
- `pendulum_lat_cf2`: gravity 10.4, mass 2.45, length 0.58
- `pendulum_lat_cf3`: gravity 11.4, mass 0.48, length 1.82

Each one falls outside the twelve-task box of gravity {7.3, 8.7, 13.2}, mass {0.65, 1.05}, and length {0.78, 1.22}. They are disjoint from development, validation, source, transfer, meta, and both reserved confirmation splits. Support uses env seed 102000. Query uses env seed 103000. Support is 128 transitions. Query is 4 episodes and 800 transitions.

## Primary rule

The primary number is held-out angular-velocity MAE. Tasks are averaged inside each decoder, and the five student seeds are averaged inside that same decoder. The uncertainty is a Student-t interval on those three decoder differences. The five seeds are not five pretrained world models.

The screen passes only when the student beats all three of zero context, the frozen encoder, and the global vector by at least **0.01** angular-velocity MAE, and each paired interval has a lower bound above 0. A lower bound of 0 fails. The eight-task baseline and the direct teacher are reported. The teacher is fit on that task's own 128 support rows. It is a reference, including when it loses to zero context.

Task rows are a sensitivity check. They do not replace the three-decoder mean.

## If the screen fails

The split is not retuned.

If the teacher loses to zero context on at least half the tasks, the diagnosis is teacher failure.

If the three decoders disagree in sign against zero context, the diagnosis is decoder variability.

If the reproduced history distance and the confirmation student-to-teacher distance are both above 0.5, the diagnosis is support-history uncertainty.

Otherwise the diagnosis is a shift in the task distribution.

## If the screen passes

The conclusion is only that amortized context inference improved prediction on these four dynamics. The next experiment may ask whether that context improves H=16 MPC return. That question is not part of this run.

<!-- protocol-lock
confirm_split_hash: baa655fcb94e61bc
forbidden_confirm_hash: 87b83c41be34aa1a
amort_confirm_hash: d1fa621351d286cf
development_artifact_sha256: c8438e09c383fc669b3b9f4cad275725d7daa9f49d2616083f256cefa1f24aba
teacher_lr: 0.1
teacher_updates: 256
student_lr: 0.01
confirmation_epoch: 200
n_student_seeds: 5
n_decoder_seeds: 3
support_budget: 128
minimum_effect: 0.01
repro_atol: 0.0001
n_parameters: 584
confirm_support_env0: 102000
confirm_query_env0: 103000
primary_unit: decoder
-->

## Results

The confirmation run has not been started in the implementation commit.
