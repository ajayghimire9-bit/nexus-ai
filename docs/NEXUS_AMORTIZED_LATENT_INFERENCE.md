# Amortized latent inference

Starting SHA `13acf89787f8262c43107193ea2b331a4bec3e26`. Config: `configs/amortized_latent_inference.yaml`. The runner rejects a drifted file.

Not AGI. Not control. Not learning-to-learn. The question is whether the existing history encoder can be trained to infer a support-fit latent, so a new task does not need 256 optimization steps.

The direct-latent source audit and the reserved confirmation (hash `87b83c41be34aa1a`) stay as they are. Those four physics are not used to fit the teacher labels or to choose the student.

## Locked teacher

For each of the three history decoders and each meta-training task:

- Load the same checkpoint and check its file hash.
- Freeze FiLM, the trunk, both heads, and normalization.
- Initialize from the stored global vector.
- Adam learning rate 0.1, 256 updates, 128 support transitions, the existing prediction loss.
- The support rows are new episodes of the eight source physics. Query outcomes are not an input.

The student does not change that rule.

## Student

The student is the existing encoder: linear layer of width 32, tanh, then a linear map to eight latent units. Capacity stays at that size. It starts from the checkpoint encoder. Only those encoder weights train. The decoder stays frozen.

The objective on meta-training support is

`L = latent_distillation_loss + λ * support_prediction_loss`

λ is chosen from **0, 10, 100, 1000**. λ = 0 is the distillation-only baseline. The prediction term reads the same support window as the distillation term. Development query rows are not labels.

Training epochs are **40, 120, and 400**, one Adam step per epoch at learning rate **0.001**, with the optimizer carried across those checkpoints. The step is on the sum of the per-task losses, not their mean. Each step sees every meta-training task through a seed-specific contiguous support window of length 16, 32, 64, or 128. The same student seed is reused for every λ, so those windows match across the λ comparison. Ten student seeds share the three frozen decoders. They are ten training runs, not ten independent world models.

## Development selection

Development physics are the existing three context-development tasks. Support and query episodes are new and disjoint. One triple (λ, epoch, support budget) is chosen by the lowest mean held-out angular-velocity MAE. Ties prefer fewer support transitions, then a lower λ, then fewer epochs.

Confirmation of a new physics set runs only if that selected student is strictly below zero context and strictly below the original frozen encoder on this development mean. Otherwise the run stops. A lower support loss, or a small distance to the teacher vector, is not that gate.

<!-- protocol-lock
forbidden_confirm_hash: 87b83c41be34aa1a
amort_confirm_hash: d1fa621351d286cf
teacher_lr: 0.1
teacher_updates: 256
student_lr: 0.001
lambdas: 0,10,100,1000
epochs: 40,120,400
budgets: 16,32,64,128
n_student_seeds: 10
meta_support_env0: 72000
dev_support_env0: 74000
dev_query_env0: 76000
confirm_support_env0: 82000
confirm_query_env0: 84000
-->

## Conditions

Same frozen decoder:

1. Zero latent.
2. Global latent.
3. Original frozen history encoder.
4. Distilled student.
5. Teacher latent fit on that task's support with the locked rule.
6. Wrong-task latent, fit on donor `(i+1) mod n`.

The 1000-update MLP is an external reference. It is not a same-decoder control.

Support budgets 16, 32, 64, and 128 apply to the student and the original encoder. The teacher and the wrong-task vector always use 128 support transitions.

## Recovery fraction

`(error_global - error_student) / (error_global - error_teacher)`

This is reported only when the teacher beats the global vector by at least 5% relative. A positive fraction is not a control result.

## New confirmation physics

These tuples are registered before any student score. They are collected only if the development gate passes.

| Task | g | m | l |
| --- | ---: | ---: | ---: |
| pendulum_amort_c0 | 16.4 | 1.0 | 1.0 |
| pendulum_amort_c1 | 10.0 | 2.6 | 1.0 |
| pendulum_amort_c2 | 10.0 | 1.0 | 0.5 |
| pendulum_amort_c3 | 7.0 | 1.45 | 1.4 |

Split hash `d1fa621351d286cf`.

## Results

The development run has not been started in the implementation commit. Confirmation has not been run.
