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

Implementation SHA `29931126df34da0064a67fd3b8a239c673412f72`. The source tree was clean. Artifact `artifacts/amortized_latent_dev.json`. Plot `artifacts/amortized_latent_dev.svg`. The development grid is complete: 5130 of 5130 cells. Wall time **230 s**. Confirmation was not run.

The development rule chose distillation only, λ = **0**, epoch **120**, support budget **128**. Ties were not involved. Every one of the 48 student cells had higher angular-velocity error than zero context. The lowest cell is the one reported below. Epoch 400 was worse than epoch 120 for every λ and every budget. Raising λ above 0 made the development error worse, especially at 400 epochs.

Held-out development angular-velocity MAE, same frozen decoder:

| Condition | Angular velocity | State MAE | Cos | Sin | Latent distance to the task teacher |
| --- | ---: | ---: | ---: | ---: | ---: |
| Student, λ 0, epoch 120, 128 rows | 0.1747 | 0.0628 | 0.0073 | 0.0065 | 2.72 |
| Zero context | 0.1587 | 0.0570 | 0.0059 | 0.0063 | 3.01 |
| Global vector | 0.1478 | 0.0534 | 0.0060 | 0.0065 | 2.75 |
| Frozen encoder, 128 rows | 0.1773 | 0.0640 | 0.0082 | 0.0065 | 2.89 |
| Teacher, locked 128-row fit | 0.0781 | 0.0322 | 0.0077 | 0.0108 | 0 |
| Wrong-task teacher | 0.1364 | 0.0522 | 0.0096 | 0.0106 | 3.44 |
| MLP, external reference | 0.1458 | 0.0527 | 0.0064 | 0.0058 | — |

Open-loop error for the student was 0.182, 0.430, and 0.683 at horizons 3, 8, and 16. Zero context was 0.164, 0.380, and 0.618. The teacher was 0.082, 0.183, and 0.346.

Paired contrasts use the ten student seeds after averaging the three decoders and the three development tasks. The sign is control minus student, so a positive number would mean the student had lower error. Student-t intervals, df = 9:

| Control | Mean difference | 95% interval |
| --- | ---: | --- |
| Zero | −0.0159 | [−0.0170, −0.0149] |
| Frozen encoder | +0.0026 | [+0.0015, +0.0037] |
| Global | −0.0269 | [−0.0280, −0.0258] |
| Teacher | −0.0966 | [−0.0976, −0.0955] |
| Wrong-task teacher | −0.0383 | [−0.0394, −0.0372] |

The student interval itself is 0.1747 [0.1736, 0.1758]. All ten seeds sit between 0.1719 and 0.1768, above zero context. These are ten training runs on three shared decoders, not ten world models.

The gate required the student to be strictly below both zero context and the frozen encoder. It is slightly below the frozen encoder and reliably above zero context. The gate fails. The new confirmation physics, hash `d1fa621351d286cf`, were not collected.

The recovery fraction is **−0.39**. The teacher beats the global vector by enough for the denominator to be defined. The negative value means the student is worse than the global vector, so it keeps none of the teacher's reduction. That fraction is not a control result.

By decoder, the same student label versus that decoder's zero context was 0.1948 versus 0.1533, 0.1912 versus 0.1567, and 0.1380 versus 0.1663. The third decoder is the only one whose student beat its own zero context, and there the student is level with its frozen encoder (0.1383) and still far from its teacher (0.0769). The pre-registered average is the gate, and that average failed.

Teacher fits used the locked rule. Meta-training support loss moved from 0.00114 to 0.00040. Development support loss moved from 0.00067 to 0.00024. No fit was nonfinite. Within each decoder the eight meta-training teachers occupy about six latent directions. Development teachers are not copies of a nearby training teacher: the nearest training teacher is between 0.57 and 4.44 away. The labels are task-specific. They are also far from the vectors the student emits.

A post-hoc check retrained λ = 0 with the same seeds and the saved teacher vectors. It did not choose a new student and did not read confirmation physics. Development latent distance at epoch 120 was 2.725, matching the artifact. Training-set latent distance was 1.53 at epoch 40, 1.37 at epoch 120, and 1.27 at epoch 400. Development distance went 2.78, 2.72, 2.74. Extra epochs pulled the training codes a little closer and made held-out prediction worse. The encoder has 584 parameters. Mean inference time was 1.3 ms. A teacher fit for one decoder, covering that decoder's meta-training and development fits, took 1.4–1.8 s. Recorded student-epoch steps were 48000. Teacher Adam steps were 10752. Environment steps were 1024 meta-training support, 384 development support, and 2400 development query.

The useful latent is still the one optimized at test time. This student does not imitate it closely, and the small movement it does make does not lower held-out error below zero context. Not control. Not learning-to-learn. Not AGI.
