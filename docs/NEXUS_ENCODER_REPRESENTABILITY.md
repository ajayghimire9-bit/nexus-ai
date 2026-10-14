# Encoder representability

Starting SHA `e657935e60074964069a9075fa46696fd1cf9312`. Config: `configs/encoder_representability.yaml`. The runner rejects a drifted file.

This asks whether the existing mean-pooling encoder can reproduce eight saved teacher codes. It does not ask whether that encoder generalizes, and it does not ask about control.

Not AGI. Not learning-to-learn. No MPC. Neither reserved confirmation split is collected. Hash `87b83c41be34aa1a` and hash `d1fa621351d286cf` stay closed.

## Targets

The training labels are the eight meta-training teacher vectors already stored for each frozen decoder in `artifacts/amortized_latent_dev.json`. The file hash is `cd120f53ffdd1efbaaff8b632faad01b251e3b4e4afccd201af28c267ac1162f`. Each vector hash and each support hash in that file is checked again. The support rows are recollected with the original seeds, and the run stops if those hashes differ.

The decoder, FiLM, both heads, and normalization stay frozen. The teacher rule is not refit to make a new label.

## Consistency diagnostic

The saved file contains one fit per task. A second fit is not a training label. It is a separate check, locked here before the run.

For each of the eight source tasks, collect a new 128-row support at environment seeds starting at 90000. Fit a latent with the locked teacher rule: initialize from the stored global vector, Adam learning rate 0.1, 256 updates, the existing prediction loss, decoder frozen. Compare that vector with the saved teacher. Also score both vectors on both supports.

A pair is far when the latent distance exceeds 0.5. It is prediction-equivalent when it is far and each foreign vector's support loss is within 10% of the native vector's loss on that support. A decoder is ambiguous when its median distance exceeds 0.5 and at least half of its far pairs are prediction-equivalent.

## Representability test

The encoder stays the checkpoint encoder: width 32, tanh, eight outputs, 584 parameters. It reads the full 128-row saved support. The loss is the mean, over the eight tasks, of the mean squared error against the saved teacher. There is no support-window sampling and no development query term.

Adam runs for 2000 steps. The learning rates are **0.001, 0.01, and 0.1**. The rate 0.001 is the previous student rate. The run records steps 0, 1, 100, 400, 1000, and 2000. It does not continue past 2000, and it does not pick an earlier checkpoint after seeing the curve. The decision uses the final step of the learning rate with the lowest mean training distance. Ties prefer the lower rate.

The constant predictor is the mean of the eight saved teachers for that decoder. An encoder that only emits that average does not pass.

A decoder passes when, at that final step, its mean latent distance is at most **0.25**, its worst task is at most **0.5**, and its mean distance is strictly below the constant predictor. All three decoders must pass. A missing log step, a nonfinite loss, or a changed decoder rejects the run.

<!-- protocol-lock
teacher_artifact_sha256: cd120f53ffdd1efbaaff8b632faad01b251e3b4e4afccd201af28c267ac1162f
forbidden_confirm_hash: 87b83c41be34aa1a
amort_confirm_hash: d1fa621351d286cf
teacher_lr: 0.1
teacher_updates: 256
learning_rates: 0.001,0.01,0.1
max_steps: 2000
mean_l2_threshold: 0.25
max_l2_threshold: 0.5
equivalence_l2: 0.5
equivalence_relative_gap: 0.1
grad_vanish_norm: 1e-8
consistency_env0: 90000
meta_support_env0: 72000
n_parameters: 584
-->

## Decision after the measurement

If any decoder's second support fit is ambiguous, the next experiment examines prediction-equivalent latents. Encoder capacity stays as it is.

If the targets are not ambiguous and the encoder misses the threshold while the final gradient norm is below 1e-8, the next experiment changes the optimizer on this same encoder.

If the targets are not ambiguous and the encoder misses the threshold with a live gradient, the one architectural change is a learned attention pool over the existing 32-unit features, still writing an eight-dimensional code. That is a separate experiment. No GRU, Transformer, ensemble, or meta-controller.

If the encoder meets the threshold and the targets are not ambiguous, the next experiment tests generalization on development tasks with a wider set of meta-training physics. It still does not open either confirmation split.

Training-set memorization is not learning-to-learn.

## Results

Implementation SHA `76c1e4aa87a611217288de15ccc59544689ff9da`. The source tree was clean. Artifact `artifacts/encoder_representability.json`. Wall time **19.0 s**. The grid is complete. Confirmation was not run.

The training-best rate is **0.01**. At step 2000 the mean latent distance is **0.0074, 0.0021, and 0.000024** on the three decoders. The worst task on those runs is **0.0089, 0.0026, and 0.000030**. The constant mean-teacher distances are **1.311, 1.748, and 1.514**. The encoder's output spread matches the teacher spread (0.529, 0.722, and 0.638). All three decoders pass. The threshold holds.

The previous rate, 0.001, does not pass. After 2000 steps its mean distances are 0.074, 0.252, and 0.068. Decoder 1 also exceeds the worst-task bar at 0.534. Rate 0.1 does pass, with means 0.0036, 0.075, and 0.0000, but its average is worse than 0.01 and decoder 1 moves back up after step 400. The decision stays at the final step of 0.01. The step budget was not extended.

The initial distances, before any encoder step, were 1.32, 2.42, and 1.57. At rate 0.01 those distances are already near zero by step 1000. This is a fit of eight support-to-code pairs. It is not a claim that a new support maps to the same code.

The consistency fits were not used as labels. A second 128-row support of the same source task lands a median distance of **1.42, 1.43, and 0.87** from the saved teacher. Seven, seven, and five of the eight tasks on the three decoders are farther than 0.5. Only one, one, and zero of those far pairs are prediction-equivalent under the 10% loss rule. No decoder is ambiguous. The alternate code is usually a worse predictor of the support it did not see, so the saved vector is not a unique task code. The encoder reproduced the saved one anyway.

Encoder steps were 18000. Consistency teacher steps were 6144. Environment steps were 1024 for the saved supports and 1024 for the second supports. The encoder has 584 parameters. Neither confirmation hash was collected.

The next experiment is a development-only generalization test with a broader set of meta-training tasks, at the training-selected rate 0.01, scored by held-out query error. The teacher for a task has to be fit on that task's own support. Not control. Not learning-to-learn. Not AGI.
